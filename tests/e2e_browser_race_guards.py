"""e2e_browser_race_guards.py — three races where a flight's RESULT must not
outlive the situation it was started in (re-audit 2026-09-24, M1/M2/M3).

  * **M2 — two project opens.** A project open is several awaited round trips.
    The flight that finished LAST used to win every write, so the writer opening
    A and then B could end up reading A's manuscript while every later POST went
    to B.
  * **M1 — a chat reply landing minutes later.** The completion handler read
    `state.currentBranch`/`state.currentProject` at COMPLETION time, so a reply
    from a local model that took its time was written into whatever the writer
    had switched to — another branch's history, or another project's list.
  * **M3 — the Beat Board save.** The PUT body is a snapshot; the ↑/↓ buttons stay
    live during the flight, and success cleared the dirty flag unconditionally, so
    the board said "Order saved" over moves that were never sent.

Each probe HOLDS one request open — but inside the page, by wrapping `window.fetch`
for the URLs the probe names, and releasing it from the test when the writer has
moved on. That is the only way to make a race deterministic in a real browser, and
it keeps the delay inside the app's own transport (a Playwright on-the-wire route
hold stalls the whole page's network stack in this setup, which measures nothing).
Reverting the three fixes turns every probe red (witnessed by controlled
reversion), which is what makes them regression tests rather than prose.

Run:  python tests/e2e_browser_race_guards.py
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

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

# The second project needs its own SCRIPT, not just its own title: after the race
# the desk has to be readable as "this is B's pages", so B's headings must differ
# from A's (the only shipped fixture is pain_tenglish).
OTHER_SCRIPT = b"""Title: Quiet Kitchen

INT. QUIET KITCHEN - DAWN

The kettle ticks as it cools. Nobody is up yet.

EXT. HARBOUR WALL - NIGHT

A boat knocks against the wall, twice.
"""

# HOLD: wrap fetch so the requests the probes name stay pending until
# __release(key). The M2 key holds the WHOLE per-project data batch
# (/api/projects/RaceA/script, /edits, /drafts, /notes) — that is the flight the
# race is about: it enters loadScriptData while RaceA is still the current
# project, and the writer switches to RaceB while those four are in the air. A
# key holds a LIST, because the batch is four concurrent requests.
HOLD = """
() => {
  window.__held = {};
  window.__holdKey = (u, m) => {
    if (/\\/api\\/projects\\/RaceA\\//.test(u) && m === 'GET') return 'A';
    if (/\\/messages\\/stream$/.test(u) && m === 'POST') return 'turn';
    if (/\\/beatboard$/.test(u) && m === 'PUT') return 'bb';
    return null;
  };
  const real = window.fetch.bind(window);
  window.fetch = function (url, opts) {
    const key = window.__holdKey(String(url), ((opts && opts.method) || 'GET').toUpperCase());
    if (!key) return real(url, opts);
    return new Promise((resolve) => {
      (window.__held[key] = window.__held[key] || []).push(() => resolve(real(url, opts)));
    });
  };
  window.__release = (key) => {
    const list = window.__held[key] || [];
    delete window.__held[key];
    list.forEach((go) => go());
  };
}
"""

checks = Checks()
check = checks.ok


def upload(base, title, path, body=None):
    if body is None:
        with open(path, "rb") as f:
            files = {"file": (f"{title}.fountain", f, "text/plain")}
            r = requests.post(f"{base}/api/projects", headers=studio_headers(base),
                              files=files, data={"title": title}, timeout=60)
    else:
        r = requests.post(f"{base}/api/projects", headers=studio_headers(base),
                          files={"file": (f"{title}.fountain", body, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    return r.json()["project"]


def main():
    with open_studio() as base:
        with sync_playwright() as pw:
            browser, page, errors = launch(pw)
            page.goto(base)
            page.wait_for_load_state("networkidle")

            upload(base, "RaceA", FIXTURE)                      # A: OPEN PARK …
            upload(base, "RaceB", FIXTURE, OTHER_SCRIPT)        # B: QUIET KITCHEN …
            page.evaluate(HOLD)

            # ---------- M2: two opens, the slower one must lose ---------------
            page.evaluate("(n) => { openProject(n); }", "RaceA")   # fire-and-forget
            page.wait_for_timeout(600)
            inflight = page.evaluate("() => Object.keys(window.__held)")
            check("A's data batch is genuinely in flight (the probe is holding it)",
                  "A" in inflight, json.dumps(inflight))
            page.evaluate("async (n) => { await openProject(n); }", "RaceB")
            page.wait_for_timeout(1400)
            desk = page.evaluate("""() => ({
                current: state.currentProject,
                text: document.getElementById('manuscript-container').textContent.slice(0, 6000),
            })""")
            check("B is the project on screen before A's slow flight lands (precondition)",
                  desk["current"] == "RaceB" and "QUIET KITCHEN" in desk["text"],
                  json.dumps({"current": desk["current"], "hasB": "QUIET KITCHEN" in desk["text"]}))
            page.evaluate("() => window.__release('A')")
            page.wait_for_timeout(1800)
            after = page.evaluate("""() => ({
                current: state.currentProject,
                scriptKeys: state.script ? Object.keys(state.script).slice(0, 14) : null,
                scriptPath: state.script ? (state.script.path || state.script.source_path || state.script.project || null) : null,
                scriptTitle: state.script ? state.script.title : null,
                firstHeading: state.script && state.script.scenes && state.script.scenes[0]
                    ? (state.script.scenes[0].heading_raw || state.script.scenes[0].heading || null) : null,
                text: document.getElementById('manuscript-container').textContent.slice(0, 4000),
                projTitle: document.getElementById('project-title').textContent,
            })""")
            print("M2 after-release readings:", json.dumps({k: v for k, v in after.items() if k != "text"})[:400])
            check("the late flight cannot install its script as the writer's pages",
                  after["scriptTitle"] == "Quiet Kitchen" and "OPEN PARK" not in after["text"]
                  and "QUIET KITCHEN" in after["text"],
                  json.dumps({"current": after["current"], "scriptTitle": after["scriptTitle"],
                              "hasA": "OPEN PARK" in after["text"],
                              "hasB": "QUIET KITCHEN" in after["text"]}))
            check("and the desk still says which project it is",
                  after["current"] == "RaceB", after["current"])

            page.evaluate("""() => { window.__holdKey = (u, m) => {
                if (/\\/messages\\/stream$/.test(u) && m === 'POST') return 'turn';
                if (/\\/beatboard$/.test(u) && m === 'PUT') return 'bb';
                return null;
            }; }""")

            # ---------- M1: a reply that lands after the writer moved on ------
            page.evaluate("() => openCowriteRoom()")
            page.wait_for_timeout(800)
            page.locator("#input").fill("a question spanning the harbour scene")
            page.get_by_role("button", name="Send", exact=True).click()
            page.wait_for_timeout(1400)
            inflight = page.evaluate("() => Object.keys(window.__held)")
            check("the chat turn's stream is in flight (the probe is holding it)",
                  "turn" in inflight, json.dumps(inflight))
            # the writer opens the OTHER project while the model is still writing
            page.evaluate("async (n) => { await openProject(n); }", "RaceA")
            page.wait_for_timeout(1200)
            parked = page.evaluate("""() => ({
                current: state.currentProject,
                branch: state.currentBranch,
                messages: ((state.branches[state.currentBranch] || {}).messages || []).length,
            })""")
            check("the writer is on the other project with its own thread (precondition)",
                  parked["current"] == "RaceA" and parked["messages"] == 0, json.dumps(parked))
            page.evaluate("() => window.__release('turn')")
            page.wait_for_timeout(2500)
            landed = page.evaluate("""() => ({
                current: state.currentProject,
                here: JSON.stringify(state.branches),
                text: document.getElementById('messages-scroll').textContent,
            })""")
            ask = "a question spanning the harbour scene"
            check("the reply does not land in the project the writer switched TO",
                  ask not in landed["here"] and ask not in landed["text"],
                  json.dumps({"current": landed["current"],
                              "inState": ask in landed["here"], "onScreen": ask in landed["text"]}))

            # ---------- M3: the Beat Board save must not clear a newer move ----
            page.evaluate("""() => { window.__holdKey = (u, m) =>
                (/\\/beatboard$/.test(u) && m === 'PUT') ? 'bb' : null; }""")
            page.evaluate("() => openBeatboardView()")
            page.wait_for_timeout(1600)
            page.locator("#beatboard-board .bb-card").nth(0).locator(".bb-move").nth(1).click()
            page.wait_for_timeout(400)
            check("the board is dirty before the save (precondition)",
                  page.evaluate("() => document.getElementById('bb-save-btn').classList.contains('dirty')"))
            page.evaluate("() => { saveBeatboard(); }")
            page.wait_for_timeout(700)
            inflight = page.evaluate("() => Object.keys(window.__held)")
            check("the save request is in flight (the probe is holding it)",
                  "bb" in inflight, json.dumps(inflight))
            # a move the PUT does not carry, made while it flies
            page.locator("#beatboard-board .bb-card").nth(1).locator(".bb-move").nth(1).click()
            page.wait_for_timeout(500)
            page.evaluate("() => window.__release('bb')")
            page.wait_for_timeout(1500)
            saved = page.evaluate("""() => {
                const b = document.getElementById('bb-save-btn');
                return {dirty: b.classList.contains('dirty'), disabled: b.disabled, label: b.textContent};
            }""")
            check("the save does not claim an order it never sent",
                  saved["dirty"] and not saved["disabled"], json.dumps(saved))

            assert_no_js_errors(checks, errors)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    main()
