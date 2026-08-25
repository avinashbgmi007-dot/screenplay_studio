"""Browser-level regression e2e for the three reported UI bugs:

  1. Idea page collapsed into a small scrollable textarea once the mic chip
     reparented it into .mic-wrap (flex chain broken) -> the canvas must fill
     the page again.
  2. After visiting an idea room, opening ANY project left #idea-canvas
     visible, stacking the idea page over the top half of the script ->
     switching views must hide the canvas.
  3. An open sidebar flyout overlays the sections below it and swallows their
     hover/clicks (ideas flyout blocking shelf/library) -> moving the pointer
     to another trigger must close the stray flyout and open the right one.

Run:  python tests/e2e_browser_ui_fixes.py   (boots its own demo studio;
      set E2E_BASE to reuse an already-running one)

Needs: pip install playwright && python -m playwright install chromium
"""
import os

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import Checks, assert_no_js_errors, launch, open_studio
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok


def seed_project(base):
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{base}/api/projects",
                          files={"file": ("Rain Courier.fountain", f, "text/plain")},
                          data={"title": "Rain Courier"}, timeout=60)
    assert r.status_code in (200, 201), r.text
    return r.json()["name"] if isinstance(r.json(), dict) and "name" in r.json() else "Rain Courier"


def glide(page, x0, y0, x1, y1, steps=8):
    """Move in small steps so mousemove-driven UI actually sees the travel."""
    for i in range(1, steps + 1):
        page.mouse.move(x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)
        page.wait_for_timeout(30)


def visible_flyouts(page):
    return page.evaluate("""() => {
        const vis = {};
        for (const [k, sel] of [["ideas","#idea-list"],["shelf","#project-list"],["library","#library-list"]]) {
            const el = document.querySelector(sel);
            vis[k] = !!el && getComputedStyle(el).display !== 'none';
        }
        return vis;
    }""")


def run(base):
    name = seed_project(base)
    with sync_playwright() as p:
        browser, page, errors = launch(p)
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(500)

        # ---- Bug 1: the idea page fills its canvas -------------------------
        page.locator("#new-idea-btn").click()
        page.wait_for_timeout(600)
        geo = page.evaluate("""() => {
            const ta = document.querySelector('#idea-content');
            return { h: Math.round(ta.getBoundingClientRect().height),
                     mic: !!(ta.closest('.mic-wrap')?.querySelector('.mic-btn')) };
        }""")
        check("idea page is a full-height surface again (>480px)",
              geo["h"] > 480, f"h={geo['h']}")
        check("mic chip still rides the idea page", geo["mic"])

        # ---- Bug 3: each trigger opens ITS OWN flyout, no dead zones -------
        def center(sel):
            b = page.locator(sel).bounding_box()
            return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2

        ix, iy = center("#ideas-trigger")
        page.mouse.move(ix, iy); page.wait_for_timeout(350)
        st = visible_flyouts(page)
        check("hover Ideas -> only ideas flyout",
              st == {"ideas": True, "shelf": False, "library": False}, str(st))

        # ---- Bug 4: hover scope -- "+ New idea" sits BESIDE the Ideas
        # trigger in the same head row; hovering it must never drop the
        # ideas list. Only the trigger owns the flyout.
        nx, ny = center("#new-idea-btn")
        glide(page, ix, iy, nx, ny)     # straight from Ideas onto '+ New idea'
        page.wait_for_timeout(450)
        st = visible_flyouts(page)
        check("Ideas -> '+ New idea' closes the ideas list",
              st == {"ideas": False, "shelf": False, "library": False}, str(st))

        # fresh approach: hovering '+ New idea' cold opens NOTHING
        page.mouse.move(720, 500)
        page.wait_for_timeout(450)      # park off the sidebar; let all close
        page.hover("#new-idea-btn")
        page.wait_for_timeout(450)
        st = visible_flyouts(page)
        check("hovering '+ New idea' alone drops no flyout",
              st == {"ideas": False, "shelf": False, "library": False}, str(st))

        # Accordion layout: opening one list PUSHES the tabs below it down,
        # and leaving it collapses everything again -- so a long single glide
        # can overshoot as the layout reflows under the pointer. A writer's
        # hand corrects in small steps; the test converges the same way.
        # (These legs used to be impossible dead zones when the flyout
        # overlaid the sibling tabs.)
        def converge(trig, want):
            last = None
            st = None
            for _ in range(5):
                tx, ty = center(trig)
                if last:
                    glide(page, last[0], last[1], tx, ty)
                else:
                    page.mouse.move(tx, ty)
                page.wait_for_timeout(380)
                st = visible_flyouts(page)
                if st == want:
                    return st
                last = (tx, ty)
            return st

        st = converge("#shelf-trigger",
                      {"ideas": False, "shelf": True, "library": False})
        check("move to Shelf -> ideas closes, shelf opens", bool(st and st["shelf"]), str(st))

        st = converge("#library-trigger",
                      {"ideas": False, "shelf": False, "library": True})
        check("move to Library -> only library flyout", bool(st and st["library"]), str(st))

        # ---- Bug 2: idea room -> project must put the canvas away ----------
        page.locator("#idea-content").fill("A courier story about regret.")
        page.wait_for_timeout(500)          # autosave
        page.hover("#shelf-trigger")        # fresh position; opens the shelf list
        page.wait_for_timeout(400)
        page.locator("#project-list .project-item").first.click()
        expect_visible = page.wait_for_selector("#script-scenes .scene-page", timeout=25000)
        st2 = page.evaluate("""() => ({
            canvas: getComputedStyle(document.querySelector('#idea-canvas')).display,
            idea_mode: document.body.classList.contains('idea-mode'),
        })""")
        check("opening a project hides the idea canvas",
              st2["canvas"] == "none" and not st2["idea_mode"], str(st2))
        check("project pages actually render", expect_visible is not None)

        # margin-note input keeps its row width after mic reparenting
        rn = page.evaluate("""() => {
            const i = document.querySelector('#rail-note-input');
            if (!i) return null;
            return { i: i.getBoundingClientRect().width,
                     f: i.closest('form').getBoundingClientRect().width };
        }""")
        check("margin-note input fills its row",
              rn is not None and rn["f"] > 0 and rn["i"] / rn["f"] > 0.5, str(rn))

        # welcome desk also puts it away
        page.locator("#home-btn").click()
        page.wait_for_timeout(600)
        st3 = page.evaluate(
            "() => getComputedStyle(document.querySelector('#idea-canvas')).display")
        check("welcome desk keeps the idea canvas hidden", st3 == "none", st3)

        # ...and returning to the SAME idea still shows the words
        page.hover("#ideas-trigger")
        page.wait_for_timeout(400)
        page.locator("#idea-list .idea-item").first.click()
        page.wait_for_timeout(700)
        val = page.locator("#idea-content").input_value()
        check("reopening the idea restores its content",
              "courier story" in val, val[:60])

        # ---- Bug 5: composer input keeps its width + grows multi-line ------
        page.locator("#idea-sam-pill").click()   # open this idea's chat drawer
        page.wait_for_timeout(700)
        comp = page.evaluate("""() => {
            const w = (s) => document.querySelector(s)?.getBoundingClientRect().width || 0;
            return { ta: w('#input'), form: w('#composer') };
        }""")
        check("composer ask box fills the composer (>55% of its row)",
              comp["form"] > 0 and comp["ta"] / comp["form"] > 0.55, str(comp))
        ask = page.locator("#input")
        ask.click()
        # Shift+Enter wraps (Enter alone SENDS -- standard chat contract)
        ask.type("line one", delay=4)
        ask.press("Shift+Enter")
        ask.type("line two", delay=4)
        ask.press("Shift+Enter")
        ask.type("line three", delay=4)
        page.wait_for_timeout(250)
        grew = page.evaluate("""() => {
            const t = document.querySelector('#input');
            return { client: t.clientHeight,
                     fits: t.scrollHeight - t.clientHeight <= 2 };
        }""")
        check("multi-line ask grows visibly and never clips",
              grew["client"] >= 60 and grew["fits"], str(grew))
        ask.fill("")   # leave no stray draft behind

        # autosave trust signal appears on the idea head after typing
        page.keyboard.press("Escape")   # drawer away; back to the page
        page.wait_for_timeout(300)
        ed2 = page.locator("#idea-content")
        ed2.click()
        ed2.press("End")
        ed2.type(" more words.", delay=4)
        page.wait_for_selector("#idea-save-state:not(:empty)", timeout=8000)
        state_txt = page.locator("#idea-save-state").inner_text()
        check("autosave indicator shows on the idea head",
              state_txt.startswith("saving") or state_txt.startswith("saved"), state_txt)

        # ---- Bug 6: Clear chat works INSIDE the idea room ------------------
        # (it used to read the project-session state and silently no-op when
        #  only an idea was open)
        page.locator("#idea-sam-pill").click()   # this idea's chat drawer back
        page.wait_for_timeout(500)
        ask2 = page.locator("#input")
        page.wait_for_selector("#input", state="visible", timeout=5000)
        ask2.click()
        ask2.type("seed line before clearing", delay=4)
        ask2.press("Enter")
        page.wait_for_selector(".msg.assistant:not(.msg-pending)", timeout=15000)
        old_sid = page.evaluate("state.currentIdeaSession")
        got_old = page.evaluate(
            "async (sid) => (await fetch(`/api/ideas/${state.currentIdea.id}/chat/sessions/${sid}`)).status",
            old_sid)
        check("session exists server-side before clear", got_old == 200, f"GET {got_old}")
        page.locator("#clear-chat-btn").click()   # dialog auto-accepted
        # the fresh-page note itself renders as .msg.assistant -- so judge the
        # wipe by USER bubbles only + the note's own text
        page.get_by_text("Fresh page", exact=False).first.wait_for(timeout=8000)
        user_bubbles = page.locator(".msg.user").count()
        new_sid = page.evaluate("state.currentIdeaSession")
        check("clear chat wipes the thread and starts fresh",
              user_bubbles == 0 and new_sid and new_sid != old_sid,
              f"user_bubbles={user_bubbles} sid {old_sid} -> {new_sid}")
        gone = page.evaluate(
            "async (sid) => (await fetch(`/api/ideas/${state.currentIdea.id}/chat/sessions/${sid}`)).status",
            old_sid)
        check("cleared conversation is really deleted server-side",
              gone == 404, f"GET old session after clear: {gone}")

        assert_no_js_errors(checks, errors)
        page.screenshot(path="_browser_ui_fixes.png", full_page=True)
        browser.close()

    checks.finish()


if __name__ == "__main__":
    with open_studio() as base:
        run(base)
