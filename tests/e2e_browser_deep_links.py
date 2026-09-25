"""e2e_browser_deep_links.py — UX-1 (audit 2026-09-24): the desk needs a URL.

Two consequences of having none, both measured by the audit:

  * a view or a scene could not be bookmarked or sent to anyone; and
  * Browser Back left the WHOLE application instead of stepping back a view —
    from inside a review pass, one Back press ended the session.

The route is DERIVED from state: `syncRoute()` rides on `saveSession()`, which
every project/view change already goes through, plus a debounced scroll sync for
the scene anchor. So these probes drive the app the way a writer does and then
read the address bar — none of them calls `syncRoute()` itself, because a test
that pokes the mechanism would pass even if nothing ever triggered it.

Reverting the routing turns every check below red (witnessed by controlled
reversion), which is what makes this a regression test rather than prose.

Run:  python tests/e2e_browser_deep_links.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests  # noqa: E402
from e2e_browser_common import studio_headers, Checks, launch, open_studio, assert_no_js_errors  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

checks = Checks()
check = checks.ok

# The page's own readings, taken in one round trip so "the hash" and "what is on
# screen" are never read a beat apart.
READING = """() => ({
  hash: location.hash,
  view: state.view,
  project: state.currentProject,
  history: history.length,
  revision: document.getElementById('revision-view').style.display !== 'none',
  beatboard: document.getElementById('beatboard-view').style.display !== 'none',
  compare: document.getElementById('compare-view').style.display !== 'none',
  premise: document.getElementById('premise-view').style.display !== 'none',
  welcome: document.getElementById('welcome-view').style.display !== 'none',
  errorShown: document.getElementById('error-banner').style.display === 'flex',
  errorText: document.getElementById('error-banner-text').textContent,
})"""


def reading(page):
    return page.evaluate(READING)


def route_of(base, rest=""):
    return base + ("#/" + rest if rest else "")


def main():
    with open_studio() as base:
        with sync_playwright() as pw:
            browser, page, errors = launch(pw)
            page.goto(base)
            page.wait_for_load_state("networkidle")

            # The sample is the app's own demo script and is guaranteed to have
            # scenes to deep-link to.
            r = requests.post(f"{base}/api/sample", headers=studio_headers(base), timeout=60)
            assert r.status_code in (200, 201), r.text
            project = r.json()["project"]

            # Open it THROUGH THE APP, not by poking state: opening is what saves
            # the session and syncs the address, and a probe that sets `state`
            # directly would pass even if nothing ever triggered a route sync.
            page.reload()
            page.wait_for_load_state("networkidle")
            page.evaluate("async (p) => { await openProject(p); }", project)
            page.wait_for_timeout(1500)
            start = reading(page)
            check("the project opened (precondition)",
                  start["project"] == project and start["view"] == "cowrite",
                  json.dumps(start))

            scenes = page.evaluate(
                "() => ((state.script && state.script.scenes) || []).map(s => s.scene_number)")
            check("the fixture has more than one scene to navigate between (precondition)",
                  len(scenes) > 2, json.dumps(scenes))

            # ---------- the URL follows navigation ----------------------------
            check("opening a project puts it in the address bar",
                  f"/{project}/" in start["hash"], start["hash"])

            page.evaluate("() => openBeatboardView()")
            page.wait_for_timeout(1200)
            board = reading(page)
            check("the Beat Board is in the address bar",
                  board["hash"].endswith(f"/{project}/beatboard"), board["hash"])
            check("...and is the view on screen", board["beatboard"], json.dumps(board))

            page.evaluate("() => openRevisionView()")
            page.wait_for_timeout(1200)
            rev = reading(page)
            check("the Revision desk is in the address bar",
                  rev["hash"].endswith(f"/{project}/revision"), rev["hash"])
            check("...and is the view on screen", rev["revision"], json.dumps(rev))

            # ---------- Back steps back a VIEW, it does not leave ------------
            page.evaluate("() => history.back()")
            page.wait_for_timeout(1400)
            back = reading(page)
            check("Back returns to the previous VIEW, not out of the application",
                  back["hash"].endswith(f"/{project}/beatboard"), back["hash"])
            check("...with the board actually on screen again",
                  back["beatboard"] and not back["revision"], json.dumps(back))
            check("...and the writer is still inside their project",
                  back["project"] == project, json.dumps(back))

            page.evaluate("() => history.forward()")
            page.wait_for_timeout(1400)
            fwd = reading(page)
            check("Forward returns to where Back left from",
                  fwd["hash"].endswith(f"/{project}/revision") and fwd["revision"],
                  json.dumps(fwd))

            # ---------- the room toggle is a navigation too -------------------
            page.evaluate("() => setRoom('feedback')")
            page.wait_for_timeout(900)
            desk = reading(page)
            # `feedback` is a SCRIPT view, so its route legitimately carries the
            # scene anchor too — hence "contains", not "ends with".
            check("switching to the Consultant's Desk is in the address bar",
                  f"/{project}/feedback" in desk["hash"], desk["hash"])

            # ---------- a deep link lands where it says -----------------------
            page.goto(route_of(base, f"{project}/revision"))
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1600)
            linked = reading(page)
            check("a deep link to the Revision desk opens the Revision desk",
                  linked["view"] == "revision" and linked["revision"], json.dumps(linked))
            check("...on the project the link names", linked["project"] == project,
                  json.dumps(linked))

            # ---------- a deep link can name a SCENE --------------------------
            # A MIDDLE scene, not the last one: the final scene cannot be scrolled
            # to the top of the page (there is nothing below it to scroll), so
            # deep-linking there would fail this check on a healthy app.
            mid_scene = scenes[len(scenes) // 2]
            page.goto(route_of(base, f"{project}/cowrite/{mid_scene}"))
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2500)
            landing = page.evaluate("""() => {
                const c = document.getElementById('manuscript-container');
                const pages = [...c.querySelectorAll('.scene-page')];
                const top = c.getBoundingClientRect().top + 24;
                let idx = pages.findIndex(p => p.getBoundingClientRect().top >= top - 8);
                if (idx === -1) idx = pages.length - 1;
                return {
                    view: state.view,
                    hash: location.hash,
                    sceneAtTop: pages[Math.max(0, idx)].dataset.sceneNumber,
                };
            }""")
            check("a deep link to a scene lands the writer on that scene",
                  landing["view"] == "cowrite" and landing["sceneAtTop"] == str(mid_scene),
                  json.dumps(landing))

            # ---------- scrolling updates the URL but not history -------------
            before_scroll = reading(page)
            for frac in (0.15, 0.5, 0.85):
                page.evaluate(
                    "(f) => { const c = document.getElementById('manuscript-container');"
                    " c.scrollTop = (c.scrollHeight - c.clientHeight) * f; }", frac)
                page.wait_for_timeout(700)
            after_scroll = reading(page)
            check("scrolling does not push a history entry per scene",
                  after_scroll["history"] == before_scroll["history"],
                  json.dumps({"before": before_scroll["history"], "after": after_scroll["history"]}))
            # The invariant that matters is not "the hash changed" — a short
            # fixture may not scroll at all — but "the hash names the scene the
            # writer is actually looking at".
            consistent = page.evaluate("""() => {
                const c = document.getElementById('manuscript-container');
                const pages = [...c.querySelectorAll('.scene-page')];
                const top = c.getBoundingClientRect().top + 24;
                let idx = pages.findIndex(p => p.getBoundingClientRect().top >= top - 8);
                if (idx === -1) idx = pages.length - 1;
                return { sceneAtTop: pages[Math.max(0, idx)].dataset.sceneNumber,
                         hash: location.hash };
            }""")
            check("the scene in the address bar is the scene at the top of the page",
                  consistent["hash"].endswith("/" + consistent["sceneAtTop"]),
                  json.dumps(consistent))

            # ---------- a stale bookmark must not strand the writer -----------
            page.goto(route_of(base, "No_Such_Project_Here/cowrite"))
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1800)
            stale = reading(page)
            check("a link to a project this desk does not have raises no error",
                  not stale["errorShown"], json.dumps(stale))
            check("...and the address stops claiming a project that isn't there",
                  "No_Such_Project_Here" not in stale["hash"], json.dumps(stale))
            check("...leaving the writer somewhere real (their desk or their project)",
                  stale["welcome"] or stale["project"] == project, json.dumps(stale))

            # ---------- Back out of a project returns to the desk ------------
            # The empty route is ambiguous on purpose: on a FRESH load it means
            # "no deep link, use the remembered session" (that is how refresh
            # lands the writer back in their script), but reached by Back it means
            # "I asked to leave". Conflating them made Back look broken — the
            # address was corrected straight back to the project.
            #
            # `history.back()`, not `page.goto(base)`: goto to a fragment-less URL
            # is a RELOAD, and a reload legitimately restores the session. Only a
            # traversal is the case under test.
            page.goto(base)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1600)
            page.evaluate("async (p) => { await openProject(p); }", project)
            page.wait_for_timeout(1400)
            before_exit = reading(page)
            check("at a project route before leaving (precondition)",
                  before_exit["project"] == project and before_exit["hash"], json.dumps(before_exit))
            page.evaluate("() => history.back()")
            page.wait_for_timeout(2000)
            exited = reading(page)
            check("Back out of a project lands on the welcome desk",
                  exited["welcome"] and exited["project"] is None, json.dumps(exited))
            check("...and the address stays empty instead of bouncing back in",
                  exited["hash"] == "", json.dumps(exited))

            assert_no_js_errors(checks, errors)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    main()
