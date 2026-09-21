"""Browser-level e2e: Your library <-> On the shelf are ONE source of truth.

The library has no storage of its own -- build_library() projects each shelf
project's parsed.json. This suite pins the writer-facing consequences:

  A. library entries appear for parsed shelf projects
  B. hovering a library row reveals a delete button (it never had one)
  C. deleting from the LIBRARY removes the script everywhere:
     library row gone, shelf row gone, project files gone (GET /api/projects),
     library digest gone (GET /api/writer-library)
  D. deleting the rest from the SHELF drops the last library row too --
     no ghost entry, without a page reload
  E. zero JS page errors

Run:  python tests/e2e_browser_library_delete.py   (boots its own demo studio;
      set E2E_BASE to reuse an already-running one)\

Needs: pip install playwright && python -m playwright install chromium
"""
import os
import time

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import Checks, assert_no_js_errors, launch, open_studio

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok


def seed(base, title):
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{base}/api/projects",
                          files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    return r.json().get("name", title)


def run(base):
    # self-cleaning for shared-server sweeps: purge leftovers so this suite's
    # counts mean exactly what it seeded (a no-op on a fresh private studio)
    for p0 in requests.get(f"{base}/api/projects", timeout=15).json():
        requests.delete(f"{base}/api/projects/{p0['project']}", timeout=15)
    seed(base, "Rain Courier")
    seed(base, "Night Ferry")

    with sync_playwright() as p:
        browser, page, errors = launch(p)
        page.goto(base, wait_until="networkidle")

        # ---- A. both parsed projects show up as library entries -------------
        page.hover("#library-trigger")
        page.wait_for_selector("#library-list .idea-item", timeout=8000)
        n_lib = page.locator("#library-list .idea-item").count()
        check("library lists both parsed scripts", n_lib == 2, f"rows={n_lib}")

        # ---- B. hover reveals a delete button on a library row --------------
        first = page.locator("#library-list .idea-item").first
        doomed = first.locator(".project-item-row").inner_text().strip()
        first.hover()
        # 0.12s CSS reveal transition -- poll it out instead of racing it
        op = 0.0
        for _ in range(20):
            op = first.locator(".project-delete").evaluate("el => getComputedStyle(el).opacity")
            if float(op) > 0.9:
                break
            page.wait_for_timeout(100)
        check("library row delete button appears on hover",
              page.locator("#library-list .project-delete").count() == 2 and float(op) > 0.9,
              f"opacity={op}")

        # ---- C. deleting FROM THE LIBRARY removes the script everywhere ----
        first.locator(".project-delete").click()   # dialog auto-accepted
        page.wait_for_timeout(900)
        names = {p["project"] for p in requests.get(f"{base}/api/projects", timeout=15).json()}
        lib_names = {e["project"] for e in requests.get(f"{base}/api/writer-library", timeout=15).json()["projects"]}
        check("deleted entry is gone from every pane + the disk",
              len(names) == 1 and len(lib_names) == 1,
              f"projects={sorted(names)} library={sorted(lib_names)}")
        n_left = page.locator("#library-list .idea-item").count()
        check("library row disappears immediately", n_left == 1, f"rows={n_left}")
        shelf_txt = page.locator("#project-list").inner_text()
        check("shelf row goes with it", doomed.split("\n")[0] not in shelf_txt, shelf_txt[:80])

        # ---- D. deleting the LAST one from the SHELF empties the library ---
        page.hover("#shelf-trigger")          # reopen its flyout like a writer would
        page.wait_for_selector("#project-list .project-item", timeout=8000)
        second = page.locator("#project-list .project-item").first
        second.hover()
        second.locator(".project-delete").click()
        # judge the source of truth first: the disk must be empty
        #
        # BUDGET, not iterations. The old loop allowed 20 x 250 ms = 5 s, and this
        # is the check that has flaked TWICE in the gate (pass 3, and again in
        # pass 10 — 30/31 suites green, this the only failure, then 3/3 standalone).
        # Two causes are possible and the old detail could not tell them apart, so
        # it now reports which:
        #   * the removal is merely SLOW under gate load — a project dir is
        #     O(files) to delete and 33 suites run back-to-back, or
        #   * the server returned an ERROR. `delete_project` calls
        #     `shutil.rmtree(..., ignore_errors=False)` with NO retry, and on
        #     Windows that raises WinError 32 whenever any handle is still open —
        #     which surfaces as a 500 and leaves the row in place.
        # The status code makes the next occurrence self-diagnosing.
        deadline = time.time() + 30
        remaining, status = None, None
        while time.time() < deadline:
            resp = requests.get(f"{base}/api/projects", timeout=15)
            status = resp.status_code
            remaining = resp.json() if status == 200 else remaining
            if not remaining:
                break
            page.wait_for_timeout(250)
        check("shelf delete emptied the disk", not remaining,
              f"after 30s: status={status} remaining={remaining}")
        page.hover("#library-trigger")        # peek into Your library again
        # Poll instead of wait_for_selector: the flyout re-render can lag on a
        # loaded machine (this suite timed out once inside the 32-suite gate and
        # then passed 2/2 standalone), and a wait_for_selector timeout reads as a
        # CRASH rather than a failed check. The assertion is the check itself now
        # -- it used to be a hardcoded True behind that wait, so the ghost-entry
        # guarantee was never actually asserted.
        empty_hints, rows = 0, 0
        # Same budget reasoning as above — and this check DEPENDS on it: if the
        # shelf delete did not land, the library legitimately still has a row, so
        # this fails as a CONSEQUENCE rather than as an independent defect. Both
        # are real failures; the status code above says which came first.
        deadline = time.time() + 30
        while time.time() < deadline:
            empty_hints = page.locator("#library-list .empty-hint").count()
            rows = page.locator("#library-list .idea-item").count()
            if empty_hints and not rows:
                break
            page.wait_for_timeout(250)
        check("no ghost entry -- library empties after a shelf delete",
              empty_hints >= 1 and rows == 0,
              f"empty_hints={empty_hints} library_rows={rows}")

        assert_no_js_errors(checks, errors)
        browser.close()

    checks.finish()


if __name__ == "__main__":
    with open_studio() as base:
        run(base)
