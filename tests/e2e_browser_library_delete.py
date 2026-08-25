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
        remaining = None
        for _ in range(20):
            remaining = requests.get(f"{base}/api/projects", timeout=15).json()
            if not remaining:
                break
            page.wait_for_timeout(250)
        check("shelf delete emptied the disk", not remaining, f"{remaining}")
        page.hover("#library-trigger")        # peek into Your library again
        page.wait_for_selector("#library-list .empty-hint", timeout=8000)
        check("no ghost entry -- library empties after a shelf delete", True)

        assert_no_js_errors(checks, errors)
        browser.close()

    checks.finish()


if __name__ == "__main__":
    with open_studio() as base:
        run(base)
