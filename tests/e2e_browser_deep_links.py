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

Every wait below is a BOUNDED POLL on the exact condition the assertion that
follows reads (`settle()`), never a fixed sleep: the route settles through
pushState + a 300 ms debounce, so a wall-clock wait asserts on luck, not on
evidence. The checks and what they assert are unchanged.

Reverting the routing turns every check below red (witnessed by controlled
reversion), which is what makes this a regression test rather than prose.

Run:  python tests/e2e_browser_deep_links.py
"""
import json
import os
import sys
import time

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


def settled_when(expr):
    """Poll predicate: the asserted state AND the router not mid-apply.

    `applyRoute()` holds the page-global `routeApplying` across its whole await
    chain, and `syncRoute()` returns early while it is set — so a state that has
    merely painted is not yet settled, and the NEXT action taken inside that
    window has its route sync silently dropped (measured: driving `setRoom`
    right after the Revision view painted left the bar on /revision forever).
    Waiting on the flag is evidence, not wall clock: it clears when the app
    itself says the route is applied.
    """
    return f"() => !routeApplying && !!({expr})"


def settle(page, condition, budget_ms, label):
    """Bounded poll: wait until `condition` (a JS predicate) is true, ≤ budget_ms.

    Replaces the fixed `wait_for_timeout` that used to precede every state
    assertion here: an assertion must land on the thing it waited FOR — the
    router/view having settled — not on elapsed luck. Playwright's own
    `wait_for_function` is the primitive: it returns the moment the predicate
    turns truthy and hard-stops at the deadline, so no wait can ever sleep
    past its budget.

    NEVER raises. A condition that never becomes true is a fact the named
    check below asserts — with a `SETTLE-TIMEOUT` note naming the condition and
    the elapsed budget in its printed detail — rather than a crash that aborts
    the run and masks every later check (the same poll-then-assert rule as
    e2e_browser_common.seen_visible).
    """
    t0 = time.monotonic()
    try:
        page.wait_for_function(condition, timeout=budget_ms)
        return ""
    except Exception:
        waited = int((time.monotonic() - t0) * 1000)
        return (f" [SETTLE-TIMEOUT: {label} did not become true within the "
                f"{budget_ms}ms budget (waited {waited}ms)]")


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
            P = json.dumps(project)  # the project name as a JS string literal

            # Open it THROUGH THE APP, not by poking state: opening is what saves
            # the session and syncs the address, and a probe that sets `state`
            # directly would pass even if nothing ever triggered a route sync.
            page.reload()
            page.wait_for_load_state("networkidle")
            page.evaluate("async (p) => { await openProject(p); }", project)
            # Poll exactly what the precondition and the address-bar check read:
            # the project open, on the writing desk, with its route in the bar.
            settled = settle(
                page,
                settled_when(
                    f"state.currentProject === {P} && state.view === 'cowrite' && "
                    f"location.hash.indexOf('/' + {P} + '/') !== -1"),
                4000, "openProject settled the desk AND the route")
            start = reading(page)
            check("the project opened (precondition)",
                  start["project"] == project and start["view"] == "cowrite",
                  json.dumps(start) + settled)

            scenes = page.evaluate(
                "() => ((state.script && state.script.scenes) || []).map(s => s.scene_number)")
            check("the fixture has more than one scene to navigate between (precondition)",
                  len(scenes) > 2, json.dumps(scenes))

            # ---------- the URL follows navigation ----------------------------
            check("opening a project puts it in the address bar",
                  f"/{project}/" in start["hash"], start["hash"] + settled)

            page.evaluate("() => openBeatboardView()")
            settled = settle(
                page,
                settled_when(
                    f"location.hash.endsWith('/' + {P} + '/beatboard') && "
                    f"document.getElementById('beatboard-view').style.display !== 'none'"),
                3000, "the Beat Board route AND its view settled")
            board = reading(page)
            check("the Beat Board is in the address bar",
                  board["hash"].endswith(f"/{project}/beatboard"), board["hash"] + settled)
            check("...and is the view on screen", board["beatboard"], json.dumps(board))

            page.evaluate("() => openRevisionView()")
            settled = settle(
                page,
                settled_when(
                    f"location.hash.endsWith('/' + {P} + '/revision') && "
                    f"document.getElementById('revision-view').style.display !== 'none'"),
                3000, "the Revision route AND its view settled")
            rev = reading(page)
            check("the Revision desk is in the address bar",
                  rev["hash"].endswith(f"/{project}/revision"), rev["hash"] + settled)
            check("...and is the view on screen", rev["revision"], json.dumps(rev))

            # ---------- Back steps back a VIEW, it does not leave ------------
            page.evaluate("() => history.back()")
            # The traversal only counts as settled when the bar AND the painted
            # views agree — the exact conjunction all three checks below read.
            settled = settle(
                page,
                settled_when(
                    f"state.currentProject === {P} && "
                    f"location.hash.endsWith('/' + {P} + '/beatboard') && "
                    f"document.getElementById('beatboard-view').style.display !== 'none' && "
                    f"document.getElementById('revision-view').style.display === 'none'"),
                4000, "Back settled on the Beat Board (route + views + project)")
            back = reading(page)
            check("Back returns to the previous VIEW, not out of the application",
                  back["hash"].endswith(f"/{project}/beatboard"), back["hash"] + settled)
            check("...with the board actually on screen again",
                  back["beatboard"] and not back["revision"], json.dumps(back))
            check("...and the writer is still inside their project",
                  back["project"] == project, json.dumps(back))

            page.evaluate("() => history.forward()")
            settled = settle(
                page,
                settled_when(
                    f"location.hash.endsWith('/' + {P} + '/revision') && "
                    f"document.getElementById('revision-view').style.display !== 'none'"),
                4000, "Forward settled back on the Revision desk")
            fwd = reading(page)
            check("Forward returns to where Back left from",
                  fwd["hash"].endswith(f"/{project}/revision") and fwd["revision"],
                  json.dumps(fwd) + settled)

            # ---------- the room toggle is a navigation too -------------------
            page.evaluate("() => setRoom('feedback')")
            settled = settle(
                page,
                settled_when(
                    f"location.hash.indexOf('/' + {P} + '/feedback') !== -1"),
                3000, "the feedback room landed in the address bar")
            desk = reading(page)
            # `feedback` is a SCRIPT view, so its route legitimately carries the
            # scene anchor too — hence "contains", not "ends with".
            check("switching to the Consultant's Desk is in the address bar",
                  f"/{project}/feedback" in desk["hash"], desk["hash"] + settled)

            # ---------- a deep link lands where it says -----------------------
            page.goto(route_of(base, f"{project}/revision"))
            page.wait_for_load_state("networkidle")
            # A fresh load's state is empty and the Revision view is display:none
            # in the HTML, so this predicate cannot go true before the app has
            # actually applied the route — no transient early pass.
            settled = settle(
                page,
                settled_when(
                    f"state.view === 'revision' && state.currentProject === {P} && "
                    f"document.getElementById('revision-view').style.display !== 'none'"),
                4500, "the deep link applied the Revision desk")
            linked = reading(page)
            check("a deep link to the Revision desk opens the Revision desk",
                  linked["view"] == "revision" and linked["revision"], json.dumps(linked) + settled)
            check("...on the project the link names", linked["project"] == project,
                  json.dumps(linked))

            # ---------- a deep link can name a SCENE --------------------------
            # A MIDDLE scene, not the last one: the final scene cannot be scrolled
            # to the top of the page (there is nothing below it to scroll), so
            # deep-linking there would fail this check on a healthy app.
            mid_scene = scenes[len(scenes) // 2]
            page.goto(route_of(base, f"{project}/cowrite/{mid_scene}"))
            page.wait_for_load_state("networkidle")
            # Same DOM reading the check below performs, as the poll predicate:
            # the target scene at the top of the page. Before the scroll lands,
            # scene 1 is at the top, so this cannot pass transiently.
            settled = settle(
                page, """() => {
                    if (routeApplying) return false;
                    const c = document.getElementById('manuscript-container');
                    if (!c) return false;
                    const pages = [...c.querySelectorAll('.scene-page')];
                    if (!pages.length) return false;
                    const top = c.getBoundingClientRect().top + 24;
                    let idx = pages.findIndex(p => p.getBoundingClientRect().top >= top - 8);
                    if (idx === -1) idx = pages.length - 1;
                    return state.view === 'cowrite'
                        && pages[Math.max(0, idx)].dataset.sceneNumber === """
                + json.dumps(str(mid_scene)) + ";}",
                5000, "the scene deep link scrolled its scene to the top")
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
                  json.dumps(landing) + settled)

            # ---------- scrolling updates the URL but not history -------------
            before_scroll = reading(page)
            # Deliberately FIXED waits: this is the suite's NEGATIVE assertion —
            # it parks at three reading positions and observes that NOTHING
            # happens (no history entry per scene, across the 300 ms debounce).
            # A poll can only wait for presence, never for absence, so the
            # settle window itself is the evidence here.
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
            # writer is actually looking at". After the final position the
            # debounced sync still owes a replaceState, so poll that agreement
            # before reading it.
            settled = settle(
                page, """() => {
                    if (routeApplying) return false;
                    const c = document.getElementById('manuscript-container');
                    const pages = [...c.querySelectorAll('.scene-page')];
                    if (!pages.length) return false;
                    const top = c.getBoundingClientRect().top + 24;
                    let idx = pages.findIndex(p => p.getBoundingClientRect().top >= top - 8);
                    if (idx === -1) idx = pages.length - 1;
                    return location.hash.endsWith('/' + pages[Math.max(0, idx)].dataset.sceneNumber);
                }""",
                2000, "the address agreed with the scene at the top")
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
                  json.dumps(consistent) + settled)

            # ---------- a stale bookmark must not strand the writer -----------
            page.goto(route_of(base, "No_Such_Project_Here/cowrite"))
            page.wait_for_load_state("networkidle")
            # The load's OWN hash names the missing project and nothing rewrites
            # it until the app has fallen back to the remembered session or the
            # desk — so "the bar stopped claiming it" is also the settle signal.
            settled = settle(
                page,
                settled_when(
                    f"location.hash.indexOf('No_Such_Project_Here') === -1 && "
                    f"document.getElementById('error-banner').style.display !== 'flex' && "
                    f"(document.getElementById('welcome-view').style.display !== 'none' || "
                    f"state.currentProject === {P})"),
                4500, "the stale link fell back to a real destination without an error")
            stale = reading(page)
            check("a link to a project this desk does not have raises no error",
                  not stale["errorShown"], json.dumps(stale) + settled)
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
            # The remembered session names this project, so boot restores it;
            # poll that restoration into port before driving openProject ourselves,
            # so the two chains cannot interleave mid-sequence (the old blind
            # 1600 ms sleep only made it unlikely, not ordered).
            settled = settle(
                page,
                settled_when(f"state.currentProject === {P} && !!location.hash"),
                4000, "boot's session restoration landed back inside the project")
            page.evaluate("async (p) => { await openProject(p); }", project)
            settled2 = settle(
                page,
                settled_when(f"state.currentProject === {P} && !!location.hash"),
                4000, "the project route was in the bar before leaving")
            before_exit = reading(page)
            check("at a project route before leaving (precondition)",
                  before_exit["project"] == project and before_exit["hash"],
                  json.dumps(before_exit) + settled + settled2)
            page.evaluate("() => history.back()")
            # All three readings below are the traversal's settled state at once:
            # welcome desk shown, no project open, and an EMPTY bar that has not
            # been bounced back to the project. Right after the traversal the
            # project is still current, so this cannot pass before it is handled.
            settled = settle(
                page,
                settled_when(
                    f"state.currentProject === null && location.hash === '' && "
                    f"document.getElementById('welcome-view').style.display !== 'none'"),
                4000, "Back out of the project settled on the empty-route welcome desk")
            exited = reading(page)
            check("Back out of a project lands on the welcome desk",
                  exited["welcome"] and exited["project"] is None, json.dumps(exited) + settled)
            check("...and the address stays empty instead of bouncing back in",
                  exited["hash"] == "", json.dumps(exited))

            assert_no_js_errors(checks, errors)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    main()
