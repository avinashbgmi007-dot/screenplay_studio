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

Run (server + test in ONE command -- background processes get reaped):
  SCREENPLAY_STUDIO_DEMO_MODEL=1 python3 -m screenplay_studio.webapp_server \\
    --port 8565 --projects-dir /tmp/e2e_lib & sleep 2;
  E2E_BASE=http://127.0.0.1:8565 python3 tests/e2e_browser_library_delete.py; kill %1

Needs: pip install playwright && python -m playwright install chromium
"""
import os
import sys

import requests
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixtures", "pain_tenglish.fountain")
BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8565")

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append((name, detail))
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   [{detail}]" if detail and not cond else ""))


def seed(title):
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{BASE}/api/projects",
                          files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    return r.json().get("name", title)


def run():
    # self-cleaning: the sweep shares one projects dir across suites -- purge
    # leftovers so this suite's counts mean exactly what it seeded
    for p0 in requests.get(f"{BASE}/api/projects", timeout=15).json():
        requests.delete(f"{BASE}/api/projects/{p0['project']}", timeout=15)
    seed("Rain Courier")
    seed("Night Ferry")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("dialog", lambda d: d.accept())
        page.goto(BASE, wait_until="networkidle")

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
        names = {p["project"] for p in requests.get(f"{BASE}/api/projects", timeout=15).json()}
        lib_names = {e["project"] for e in requests.get(f"{BASE}/api/writer-library", timeout=15).json()["projects"]}
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
            remaining = requests.get(f"{BASE}/api/projects", timeout=15).json()
            if not remaining:
                break
            page.wait_for_timeout(250)
        check("shelf delete emptied the disk", not remaining, f"{remaining}")
        page.hover("#library-trigger")        # peek into Your library again
        page.wait_for_selector("#library-list .empty-hint", timeout=8000)
        check("no ghost entry -- library empties after a shelf delete", True)

        check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()

    print(f"\n=== {len(PASS)} passed, {len(FAIL)} failed ===")
    for n, d in FAIL:
        print(f"FAILED: {n}: {d}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    run()
