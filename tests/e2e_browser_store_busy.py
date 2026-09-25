"""e2e_browser_store_busy.py — the writer is TOLD when the studio is busy.

BE-3 (round-3 audit 2026-09-25). Two halves, and the second is why this suite
exists:

1. A contended store used to answer **500** with
   `{"error":"Unexpected error: timed out after 10s waiting for another process
   to release working.json"}` — a crash report for a transient condition, on the
   two routes that render the writer's script. It answers **503 + `Retry-After`**
   now, with a sentence they can act on.
2. **That fix would have been invisible.** `openProject` wrapped its
   `loadScriptData()` in `catch (_) { /* no parse yet */ }`, swallowing EVERY
   failure as "this project has no parse yet" — so a busy store (and any 500)
   left the manuscript pane showing nothing and said nothing. The two other
   `loadScriptData` call sites already did `showError("Couldn't load the
   script: " + e.message)`; the project-open path was the odd one out.

The contention is REAL and cross-process: a child holds `working.json`'s lock
while the page reloads the project. In-process contention cannot produce the
timeout at all (the in-process `RLock` is acquired with no timeout), and a
browser suite cannot monkeypatch a server it spawned — so a real holder is the
only honest way to reach the state this suite is about.

Run:  python tests/e2e_browser_store_busy.py
"""
import json
import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# The repo root too: `test_undo_redo_lock_race` imports `screenplay_studio`, and a
# suite run directly has neither on the path (the pytest suites get it from
# conftest, which a standalone script never loads).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402
from e2e_browser_common import (  # noqa: E402
    Checks,
    assert_no_js_errors,
    launch,
    start_studio,
    studio_headers,
)
from playwright.sync_api import sync_playwright  # noqa: E402

from test_undo_redo_lock_race import _spawn  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

# Long enough to outlast the studio's own LOCK_TIMEOUT_SECONDS (10s) with margin,
# so the page's request genuinely expires rather than waiting the holder out.
HOLD_S = 45

_HOLDER = textwrap.dedent(
    """
    import sys, time
    from screenplay_studio.jsonio import lock_for

    target, hold = sys.argv[1], float(sys.argv[2])
    with lock_for(target):
        print("HELD", flush=True)
        time.sleep(hold)
    """
)

BANNER_JS = """() => {
  const b = document.getElementById('error-banner');
  const t = document.getElementById('error-banner-text');
  return {
    visible: !!b && getComputedStyle(b).display !== 'none',
    text: t ? (t.textContent || '') : '',
  };
}"""


def _wait_for(page, condition, ms=10000):
    try:
        page.wait_for_function(condition, timeout=ms)
        return True
    except Exception:
        return False


def main():
    checks = Checks()
    check = checks.ok

    studio = start_studio()
    holder = None
    try:
        base = studio.base_url
        with sync_playwright() as pw:
            browser, page, errors = launch(pw)
            page.goto(base)
            page.wait_for_load_state("networkidle")

            seeded = requests.post(f"{base}/api/sample",
                                   headers=studio_headers(base), timeout=60)
            assert seeded.status_code in (200, 201), seeded.text
            project = seeded.json()["project"]

            page.evaluate("async (p) => { await openProject(p); }", project)
            loaded = _wait_for(page, "() => state.script && state.script.scenes "
                                     "&& state.script.scenes.length > 0", 20000)
            check("the project loads while nothing is contending (precondition)",
                  loaded)
            check("...and no error banner is shown for a healthy load",
                  not page.evaluate(BANNER_JS)["visible"],
                  json.dumps(page.evaluate(BANNER_JS)))

            # ---- now make the store genuinely busy --------------------------
            lock_target = os.path.join(studio.projects_dir, project, "working.json")
            check("the working copy exists to contend on (precondition)",
                  os.path.exists(lock_target), lock_target)
            holder = _spawn(_HOLDER, lock_target, HOLD_S)
            assert holder.stdout.readline().strip() == "HELD", (
                "the holder never took the lock — this run would prove nothing")

            # Re-open the project, which is the path that used to swallow the
            # failure. The request expires at the studio's own 10s timeout.
            page.evaluate("async (p) => { await openProject(p); }", project)
            shown = _wait_for(page, "() => { const b = document.getElementById("
                                    "'error-banner'); return !!b && "
                                    "getComputedStyle(b).display !== 'none'; }", 30000)
            banner = page.evaluate(BANNER_JS)

            check("a busy store is reported to the writer, not swallowed",
                  shown and banner["visible"], json.dumps(banner))
            check("...with a sentence they can act on, not an internal crash string",
                  "busy" in banner["text"].lower() and "Unexpected error" not in banner["text"],
                  json.dumps(banner["text"][:200]))
            check("...and it names the script as what could not be loaded",
                  "script" in banner["text"].lower(), json.dumps(banner["text"][:200]))

            assert_no_js_errors(checks, errors)
            browser.close()
    finally:
        if holder and holder.poll() is None:
            holder.kill()
            try:
                holder.communicate(timeout=30)
            except Exception:
                pass
        studio.close()

    checks.finish()


if __name__ == "__main__":
    main()
