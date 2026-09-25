"""e2e_browser_two_contexts.py — two real browser windows on one project.

Why this suite exists, twice over:

  * **BE-1** (round-3 audit 2026-09-25) was a lost update on `POST /edits/apply`
    that survived the whole fleet because **no suite had ever opened a second
    browser context**. Every other suite drives one page; the multi-window
    workflow — a writer with their project open twice, which is the shape
    `app.run(threaded=True)` makes two threads — had zero coverage. Two
    contexts is also what makes the race honest: one context means one cookie
    jar and one page's own JS thread, which is not what two windows are.
  * **The probe must not serialise itself.** `page.evaluate` does not return
    until its promise settles, so awaiting an apply before starting the second
    one runs them one after the other and measures nothing. A scratch version
    of this probe did exactly that and reported a clean 0/40 divergence. The
    dispatch below is deliberately fire-and-forget, and every round records the
    two requests' start/end so a later reader can see they genuinely overlapped
    rather than having to trust it.

Run:  python tests/e2e_browser_two_contexts.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests  # noqa: E402
from e2e_browser_common import (  # noqa: E402
    Checks,
    assert_no_js_errors,
    launch,
    open_studio,
    studio_headers,
)
from playwright.sync_api import sync_playwright  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

ROUNDS = 5
SPIN_MS = 120  # both windows dispatch at the same wall-clock instant

# Fire-and-forget ON PURPOSE — see the module docstring. Returns immediately, so
# the other window's request is in flight at the same time.
DISPATCH_JS = """
(a) => {
  while (Date.now() < a.startAt) { /* spin to a shared instant */ }
  window.__race = { started: Date.now(), done: null };
  api(`/projects/${encodeURIComponent(a.project)}/edits/apply`, {
    method: 'POST',
    body: JSON.stringify({
      scene_number: a.scene,
      replacements: [{ old: a.old, new: a.new }],
    }),
  }).then((r) => {
    window.__race.done = { applied: ((r && r.applied) || []).length,
                           ended: Date.now() };
  }).catch((e) => {
    window.__race.done = { error: String(e), ended: Date.now() };
  });
  return true;
}
"""

READ_JS = "() => window.__race"

SCENES_JS = """() => (state.script.scenes || []).map(
    (s) => ({n: s.scene_number, texts: (s.elements || []).map((e) => e.text)}))"""

SCRIPT_JS = "() => state.script.scenes.map((s) => (s.elements || []).map((e) => e.text))"


def _wait_for(page, condition, ms=10000):
    """Bounded poll. Never raises — a timeout is a fact to assert on, not a crash."""
    try:
        page.wait_for_function(condition, timeout=ms)
        return True
    except Exception:
        return False


def _open_both(base, pages, project):
    for page in pages:
        page.goto(base)
        page.wait_for_load_state("networkidle")
    for page in pages:
        page.evaluate("async (p) => { await openProject(p); }", project)
    return all(
        _wait_for(page,
                  "() => state.script && state.script.scenes && state.script.scenes.length > 1")
        for page in pages)


def main():
    checks = Checks()
    check = checks.ok

    with open_studio() as base:
        with sync_playwright() as pw:
            browser, page1, errors = launch(pw)
            # A SECOND CONTEXT, not a second page: separate cookie jar, separate
            # storage, which is what "open the project in another window" is.
            ctx2 = browser.new_context(viewport={"width": 1440, "height": 900})
            page2 = ctx2.new_page()
            page2.on("pageerror", lambda e: errors.append(str(e)))
            page2.on("dialog", lambda d: d.accept())
            pages = (page1, page2)

            check("the two windows are independent browser contexts",
                  page1.context is not ctx2,
                  "two pages of one context would share a cookie jar and a JS thread")

            seeded = requests.post(f"{base}/api/sample",
                                   headers=studio_headers(base), timeout=60)
            assert seeded.status_code in (200, 201), seeded.text
            project = seeded.json()["project"]

            opened = _open_both(base, pages, project)
            check("both windows have the same project open (precondition)", opened)

            # Two scenes, so neither window's edit depends on the other's text.
            scenes = page1.evaluate(SCENES_JS)
            usable = [s for s in scenes if s["texts"]]
            check("the fixture offers two scenes with text (precondition)",
                  len(usable) >= 2, json.dumps([s["n"] for s in scenes]))
            scene_a, scene_b = usable[0]["n"], usable[1]["n"]
            line_a, line_b = usable[0]["texts"][0], usable[1]["texts"][0]

            rounds, failures = [], []
            for i in range(1, ROUNDS + 1):
                new_a, new_b = f"W1-{i}", f"W2-{i}"
                start_at = int(time.time() * 1000) + SPIN_MS
                page1.evaluate(DISPATCH_JS, {"project": project, "scene": scene_a,
                                             "old": line_a, "new": new_a,
                                             "startAt": start_at})
                page2.evaluate(DISPATCH_JS, {"project": project, "scene": scene_b,
                                             "old": line_b, "new": new_b,
                                             "startAt": start_at})

                settled = all(
                    _wait_for(p, "() => window.__race && window.__race.done", 20000)
                    for p in pages)
                if not settled:
                    failures.append(f"round {i}: a window never reported its result")
                    break

                ra, rb = page1.evaluate(READ_JS), page2.evaluate(READ_JS)
                rounds.append((i, ra, rb))
                for tag, r in (("window 1", ra), ("window 2", rb)):
                    if r["done"].get("error") or r["done"].get("applied") != 1:
                        failures.append(f"round {i} {tag}: {r['done']}")
                line_a, line_b = new_a, new_b

            # The control: a green below must mean "nothing was lost", never
            # "nothing raced". Both requests have to have been in flight at once.
            overlapped = [i for i, ra, rb in rounds
                          if min(ra["done"]["ended"], rb["done"]["ended"])
                          > max(ra["started"], rb["started"])]
            check("every round's two applies were genuinely concurrent",
                  len(overlapped) == len(rounds) == ROUNDS,
                  f"overlapped={overlapped} of {[i for i, _, _ in rounds]}")

            check("neither window lost an edit it accepted", not failures,
                  "; ".join(failures[:3]))

            # Both edits must be in the STORED script, not just in the two pages'
            # in-memory copies — that is the divergence BE-1 produced.
            stored = requests.get(f"{base}/api/projects/{project}/script",
                                  headers=studio_headers(base), timeout=60).json()
            stored_lines = [el["text"] for s in stored["scenes"] for el in s["elements"]]
            check("the stored script carries both windows' last edits",
                  f"W1-{ROUNDS}" in stored_lines and f"W2-{ROUNDS}" in stored_lines,
                  json.dumps({"want": [f"W1-{ROUNDS}", f"W2-{ROUNDS}"],
                              "got": [t for t in stored_lines if t.startswith("W")]}))

            # And a window that reloads must see the same thing as the other one:
            # two windows disagreeing about the script is the user-visible form
            # of the same defect.
            page2.reload()
            page2.wait_for_load_state("networkidle")
            _wait_for(page2, "() => state.script && state.script.scenes")
            seen2 = page2.evaluate(SCRIPT_JS)
            flat2 = [t for scene in seen2 for t in scene]
            check("a reloaded window agrees with what was stored",
                  f"W1-{ROUNDS}" in flat2 and f"W2-{ROUNDS}" in flat2,
                  json.dumps([t for t in flat2 if t.startswith("W")]))

            assert_no_js_errors(checks, errors)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    main()
