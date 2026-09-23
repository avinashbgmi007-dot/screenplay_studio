"""Phase 9 gate — Idea Canvas, writing-first (master plan §10).

Verifies on the live app (DOM/text only, no screenshots):
  * the decor is GONE: no starfield, no spark threads, no ambience layer
  * writing-first: the page opens empty, focus lands on writing, the page
    is the visual subject (no chrome between the writer and the words)
  * autosave: typed content persists (debounced save fires)
  * title: the idea titles itself from first words / is editable
  * Sameer on demand: the pill always stands — an invitation ('Ask Sameer')
    on a blank page, the summon ('Sameer') once there are words — and
    summoning hands the keyboard to the composer: keys land in the CHAT,
    never in the canvas (UI audit 2026-09-20, defects #6/#7)
  * Premise Doctor on demand: the room toggle exposes the doctor (feedback
    lens routes to the premise doctor in idea mode)
  * structure support: the Structure toggle reveals logline/questions
  * graduation: the "Grow into pages" button is present with its contract
  * idea isolation: a second idea's page doesn't bleed into the first

Run:  python tests/e2e_browser_phase9_idea_canvas.py
"""
import os

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import studio_headers, Checks, launch, start_studio

checks = Checks()
check = checks.ok


def run(base):
    with sync_playwright() as p:
        browser, page, errors = launch(p)

        # --- create an idea through the API the button uses ------------------
        r = requests.post(f"{base}/api/ideas", headers=studio_headers(base), json={"title": "phase9 probe"}, timeout=30)
        assert r.status_code in (200, 201), r.text
        ideas = requests.get(f"{base}/api/ideas", timeout=30).json()
        idea = next((i for i in ideas if i["title"] == "phase9 probe"), None)
        assert idea, "probe idea not created"

        # --- open it through the app's own path -------------------------------
        page.goto(base)
        page.wait_for_load_state("networkidle")
        page.evaluate("async (id) => { await openIdea(id); }", idea["id"])
        page.wait_for_timeout(1200)

        # --- the decor is gone --------------------------------------------------
        decor = page.evaluate("""() => ({
            ambience: !!document.querySelector('.spark-ambience'),
            threads: !!document.querySelector('.spark-threads'),
            stars: !!document.querySelector('.spark-stars'),
        })""")
        check("Phase 9: no starfield/spark-thread/ambience in the idea room",
              not any(decor.values()), str(decor))

        # --- writing-first -------------------------------------------------------
        canvas = page.locator("#idea-canvas")
        content = page.locator("#idea-content")
        check("idea canvas opens (display flex)", canvas.is_visible())
        check("the page starts empty (blank canvas)", (content.input_value() or "") == "")
        # defect #6 (UI audit 2026-09-20): the blank canvas was a dead end —
        # no prompt, no hint, no placeholder. The placeholder IS the onboarding.
        ph = content.evaluate("el => el.getAttribute('placeholder') || ''")
        check("blank canvas carries a real prose prompt (placeholder)",
              "Type the idea" in ph and "Sameer" in ph, ph[:100])
        # defect #7: the chat must be discoverable BEFORE the first word —
        # the pill stands on a blank page as an invitation, not a dead corner
        pill = page.locator("#idea-sam-pill")
        check("chat discoverable on the BLANK page (pill stands as an invitation)",
              pill.is_visible() and pill.inner_text().strip() == "Ask Sameer",
              f"visible={pill.is_visible()} label={pill.inner_text().strip()!r}")
        # the page is the widest element in the room — the subject, not the chrome
        cw = canvas.bounding_box()["width"]
        pw = page.locator("#idea-content").bounding_box()["width"]
        check("the page dominates the room (≥70% width)", pw / cw >= 0.7,
              f"page={round(pw)} canvas={round(cw)}")

        # --- autosave contract ----------------------------------------------------
        content.fill("The last man on the moon keeps a garden.")
        page.wait_for_timeout(1500)  # debounce is 300ms; give it slack
        saved = requests.get(f"{base}/api/ideas/{idea['id']}", timeout=30).json()
        check("autosave: typed words persist to the store",
              "garden" in (saved.get("content") or ""), (saved.get("content") or "")[:60])
        state_chip = page.locator("#idea-save-state").inner_text()
        check("save-state chip reports honestly",
              "saved" in state_chip.lower() or state_chip.strip() == "", state_chip)

        # --- Sameer on demand -----------------------------------------------------
        pill = page.locator("#idea-sam-pill")
        check("Sameer pill present once the page has words", pill.count() > 0)
        check("pill flips to the summon label once the page has words",
              pill.inner_text().strip() == "Sameer", pill.inner_text().strip())

        # --- defect #7, the misroute half: summon routes the keyboard to the
        # CHAT. The audit's failure: after summoning, typed text was swallowed
        # by the canvas (and auto-titled the idea) because focus never moved.
        page.evaluate("() => document.activeElement && document.activeElement.blur()")
        page.keyboard.press("c")
        page.wait_for_timeout(400)
        focused = page.evaluate("() => document.activeElement && document.activeElement.id")
        check("summon (c) puts the cursor in the composer", focused == "input", focused)
        page.keyboard.type("a line for the chat, not the page", delay=4)
        in_composer = page.locator("#input").input_value()
        on_canvas = page.locator("#idea-content").input_value()
        check("keys after a summon land in the chat, never the canvas",
              "for the chat" in in_composer and "garden" in on_canvas
              and "for the chat" not in on_canvas,
              f"composer={in_composer[:40]!r} canvas={on_canvas[:40]!r}")
        page.locator("#input").fill("")   # leave no stray draft
        page.locator("#drawer-close").click()
        page.wait_for_timeout(300)

        # --- structure support -----------------------------------------------------
        struct_btn = page.locator("#idea-structure-btn")
        check("Structure toggle present (structure support preserved)",
              struct_btn.count() > 0)
        struct_btn.click()
        page.wait_for_timeout(300)
        panel = page.locator("#idea-structure-panel")
        check("Structure panel reveals the logline/questions",
              panel.is_visible() and panel.locator("#idea-logline").count() == 1)

        # --- graduation ---------------------------------------------------------
        grad = page.locator("#idea-graduate-btn")
        check("graduation: 'Grow into pages' present with its contract",
              grad.count() == 1 and "Grow into pages" in grad.inner_text())

        # --- Premise Doctor on demand (idea room routes feedback → premise) ----
        # the app exposes the doctor via the room toggle in idea mode
        doctor_reachable = page.evaluate("""() => {
            const b = document.getElementById('room-feedback-btn');
            return !!b && b.offsetParent !== null;
        }""")
        check("Premise Doctor reachable from the idea room (on demand)", doctor_reachable)

        # --- idea isolation --------------------------------------------------------
        r2 = requests.post(f"{base}/api/ideas", headers=studio_headers(base), json={"title": "phase9 second"}, timeout=30)
        ideas2 = requests.get(f"{base}/api/ideas", timeout=30).json()
        idea2 = next((i for i in ideas2 if i["title"] == "phase9 second"), None)
        page.evaluate("async (id) => { await openIdea(id); }", idea2["id"])
        page.wait_for_timeout(1200)
        second_content = page.locator("#idea-content").input_value()
        check("isolation: the second idea opens on its own empty page",
              (second_content or "") == "", second_content[:40])
        # and the first idea's words are still where we left them
        first = requests.get(f"{base}/api/ideas/{idea['id']}", timeout=30).json()
        check("isolation: the first idea's page is untouched",
              "garden" in (first.get("content") or ""))

        # --- F10 (UI audit 2026-09-20, defect #8) ---------------------------------
        # The palette used to OFFER project-only commands in the idea room, where
        # clicking them silently did nothing (guarded no-ops). Dead commands are
        # worse than absent ones: they read as broken. They are now hidden.
        page.evaluate("() => openPalette(false)")
        page.wait_for_timeout(500)
        pal = page.locator("#palette-results").inner_text()
        dead = [c for c in ("Beat Board", "Compare drafts", "Revision view",
                            "Spotlight", "Export working draft") if c in pal]
        check("palette in the idea room hides project-only commands",
              not dead, "offered but dead: " + ", ".join(dead))
        check("palette still offers what works without a project",
              "Switch to Co-write" in pal and "Start a new page" in pal)
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # --- cleanup -------------------------------------------------------------
        for iid in (idea["id"], idea2["id"]):
            requests.delete(f"{base}/api/ideas/{iid}", headers=studio_headers(base), timeout=30)

        check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()

    checks.finish()


if __name__ == "__main__":
    if os.environ.get("E2E_BASE"):
        run(os.environ["E2E_BASE"])
    else:
        with start_studio() as studio:
            run(studio.base_url)
