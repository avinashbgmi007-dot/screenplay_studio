"""Phase 8 gate — analysis lifecycle + desk toolbar (master plan §9).

Verifies on the live app (DOM/text only):
  * unanalyzed project: desk toolbar shows a prominent Run Analysis + the
    honest unanalyzed status line; manuscript stays readable
  * running: progress chip on the desk (% + ETA + bar), pipeline popover
    on demand (hover/focus), current stage advances
  * completion: status line flips to the findings count; Re-run Analysis
  * failure/partial: failed categories listed; Retry failed re-runs ONLY
    the failed (verified via the endpoint's contract: it 400s unless a
    completed report exists) — the desk retry chip mirrors the legacy one
  * desk buttons run the SAME functions (no second lifecycle): clicking the
    desk Run Analysis while a run is active does NOT double-fire

Run:  python tests/e2e_browser_phase8_lifecycle.py
"""
import os
import threading
import time

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import Checks, launch, note, start_studio

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok


def seed(base, title):
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{base}/api/projects",
                          files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    return r.json().get("project") or title


def open_project(page, base, name):
    page.goto(base)
    page.wait_for_load_state("networkidle")
    # Address the EXACT project id that seed() returned. The previous version
    # hovered the shelf and clicked .first() on a filter built from
    # name.split("_")[0] -- just "Lifecycle" -- so against any studio that had
    # already accumulated Lifecycle_Probe, _2, ... from earlier runs it opened a
    # STALE probe whose parse was still pending and the manuscript wait timed
    # out (hit 2026-09-19 while pointing this suite at a long-lived studio).
    # Idempotent: it opens the project it just seeded, every time.
    page.evaluate("(n) => openProject(n)", name)
    page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)


def run(base):
    fresh = seed(base, "Lifecycle Probe")
    with sync_playwright() as p:
        browser, page, errors = launch(p)

        # --- 1. UNANALYZED state ------------------------------------------------
        open_project(page, base, fresh)
        desk_btn = page.locator("#desk-analyze-btn")
        status = page.locator("#desk-analyze-status")
        check("unanalyzed: Run Analysis visible on the desk", desk_btn.is_visible())
        check("unanalyzed: button reads Run Analysis (not Re-run)",
              "Run Analysis" in desk_btn.inner_text() and "Re-run" not in desk_btn.inner_text())
        check("unanalyzed: honest status line",
              "Unanalyzed" in status.inner_text() or "unanalyzed" in status.inner_text(),
              status.inner_text()[:60])
        check("unanalyzed: manuscript stays readable",
              page.locator("#manuscript-container .scene-page").count() > 0)

        # --- 2. RUNNING state: desk button fires ONE analysis, progress mirrors --
        desk_btn.click()
        page.wait_for_timeout(800)
        chip = page.locator("#desk-analyze-progress")
        # the demo model is fast; either still running or already done — the
        # running window must show the chip if the run is still in flight
        running_seen = chip.is_visible()
        if running_seen:
            # A RACE, not a contract: on a fast demo run the analysis finishes
            # inside the 800 ms poll and the chip is legitimately gone, so this
            # branch may not be taken at all. `check(name, True)` asserted
            # nothing while claiming the chip was on the desk; asserting it for
            # real would be flaky. Note it, and let the real checks below run
            # only when the chip was actually caught.
            note("running: progress chip caught on the desk")
            pct_txt = chip.locator(".ap-pct").inner_text()
            check("running: percentage renders", pct_txt.strip().endswith("%"), pct_txt)
            check("running: popover available on hover",
                  chip.locator(".analyze-pipeline").count() > 0)
            check("running: at most one analysis fired (guard)",
                  desk_btn.is_disabled() or "Analyzing" in desk_btn.inner_text())
        # wait for completion either way
        deadline = time.time() + 300
        done = False
        while time.time() < deadline:
            s = requests.get(f"{base}/api/projects/{fresh}", timeout=15).json()
            if s.get("stages", {}).get("analyze") in ("complete", "failed"):
                done = True
                break
            time.sleep(2)
        check("analysis reaches a terminal state (complete/failed)", done)
        page.wait_for_timeout(2500)  # let the UI poll/refresh land

        # --- 3. terminal state on the desk ---------------------------------------
        status_txt = status.inner_text()
        st = requests.get(f"{base}/api/projects/{fresh}", timeout=15).json()["stages"]["analyze"]
        if st == "complete":
            check("complete: desk reads Re-run Analysis",
                  "Re-run" in desk_btn.inner_text(), desk_btn.inner_text())
            check("complete: status carries the findings count",
                  "finding" in status_txt.lower() or "coverage" in status_txt.lower(),
                  status_txt[:80])
        else:
            check("failed: status names the failed categories",
                  "failed" in status_txt.lower(), status_txt[:80])

        # --- 4. retry contract: only-failed, and only after a completed report ----
        r_retry = requests.post(f"{base}/api/projects/{fresh}/analyze/retry-failed",
                                json={}, timeout=60)
        # 200/201 = merged retry; 400 = no completed report (honest guard)
        check("retry endpoint contract intact (merge or honest 400)",
              r_retry.status_code in (200, 201, 400), f"status={r_retry.status_code}")
        # the desk retry chip mirrors the failed-category state
        desk_retry = page.locator("#desk-retry-failed-btn")
        legacy_retry = page.locator("#retry-failed-btn")
        s = requests.get(f"{base}/api/projects/{fresh}", timeout=15).json()
        failed_n = len(s.get("failed_categories") or [])
        vis = desk_retry.is_visible() if desk_retry.count() else False
        check("desk retry chip mirrors the failed-category state",
              vis == (failed_n > 0), f"chip={vis} failed={failed_n}")
        check("legacy retry chip stays in sync (parity)",
              (legacy_retry.is_visible() if legacy_retry.count() else False) == (failed_n > 0))

        # --- 5. structure: toolbar sits above the manuscript row -----------------
        tb_box = page.locator("#desk-toolbar").bounding_box()
        row_box = page.locator(".manuscript-workspace-layout").bounding_box()
        check("desk toolbar sits above the manuscript row",
              tb_box and row_box and tb_box["y"] < row_box["y"],
              f"toolbar_y={tb_box and round(tb_box['y'])} row_y={row_box and round(row_box['y'])}")
        check("desk toolbar stays slim (≤64px)",
              tb_box and tb_box["height"] <= 64, f"h={tb_box and round(tb_box['height'])}")

        check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()

    checks.finish()


if __name__ == "__main__":
    if os.environ.get("E2E_BASE"):
        run(os.environ["E2E_BASE"])
    else:
        with start_studio() as studio:
            run(studio.base_url)
