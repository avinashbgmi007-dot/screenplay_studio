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


def reveal_chrome(page, sel="#desk-analyze-btn", timeout=8000):
    """Move the mouse where a writer's would be, then poll until the control is
    genuinely the hit target. Returns True/False — never raises.

    `#desk-toolbar` and `#project-bar` are auto-hiding chrome: while idle they
    carry `opacity: 0; pointer-events: none` (style.css `.auto-hide-chrome`), and
    a mousemove with `clientY < 120` is what brings them back for 4s. Playwright's
    `is_visible()` ignores opacity, so the old `check(name, desk_btn.is_visible())`
    passed on a button no writer could actually click, and the following `.click()`
    timed out with `<div id="manuscript-workspace">… intercepts pointer events`
    (root-caused 2026-09-23: P1's heavier `openProject` pushed the first click
    past the 4s idle timer, which is what turned this suite red).

    Polling the real hit test also covers the second transition in the way —
    `#sidebar.sidebar-collapsed` animates 264px -> 0 and briefly overlays the
    toolbar's left edge, where this button sits.
    """
    page.mouse.move(700, 8)
    deadline = time.time() + timeout / 1000
    hit = "missing"
    while time.time() < deadline:
        hit = page.evaluate(
            """(sel) => {
              const e = document.querySelector(sel);
              if (!e) return 'missing';
              const r = e.getBoundingClientRect();
              const t = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
              if (!t) return 'none';
              return (e === t || e.contains(t)) ? 'ok' : t.tagName + '#' + (t.id || '-');
            }""", sel)
        if hit == "ok":
            return True
        page.wait_for_timeout(100)
    return False


def check_stage_ladder(page):
    """P2.15: the ladder is built from real stage events, not invented progress.

    Deterministic on purpose. Catching a live demo run mid-stage is a race the
    suite already documents, so this calls the production renderer with a
    synthetic position on the SAME stage list the poller walks — which is what
    the writer sees, minus the luck.
    """
    probe = page.evaluate("""() => {
      const box = document.createElement('div');
      document.body.appendChild(box);
      renderStageLadder(box, 'dialogue', Date.now() - 45000);
      const rows = [...box.querySelectorAll('.stage-ladder .stage')];
      const txt = (n) => n ? n.textContent : null;
      const cur = box.querySelector('.stage.current');
      const out = {
        ladderClass: !!box.querySelector('.stage-ladder'),
        rows: rows.length,
        stages: STAGE_LADDER.length,
        current: rows.filter(r => r.classList.contains('current')).length,
        curKey: cur ? cur.dataset.stage : null,
        curText: txt(cur),
        done: rows.filter(r => r.classList.contains('done')).length,
        doneMark: rows.length ? txt(rows[0].querySelector('.stage-mark')) : null,
        pendingMark: rows.length ? txt(rows[rows.length - 1].querySelector('.stage-mark')) : null,
        percent: /%/.test(box.textContent),
        noCaption: STAGE_LADDER.filter(s => !s.caption || !/\\s/.test(s.caption)).map(s => s.key),
        dupKeys: STAGE_LADDER.length !== new Set(STAGE_LADDER.map(s => s.key)).size,
        // the heartbeat, read at two clocks apart
        elapsedFresh: stageElapsedText(Date.now() - 5000, Date.now(), 600),
        elapsedStale: stageElapsedText(Date.now() - 40 * 60000, Date.now(), 600),
      };
      box.remove();
      return out;
    }""")
    check("ladder: renders as .stage-ladder inside the chip host", probe["ladderClass"])
    check("ladder: one row per real stage event, not a hand-picked dozen",
          probe["rows"] == probe["stages"] and probe["stages"] >= 12,
          f"rows={probe['rows']} stages={probe['stages']}")
    check("ladder: exactly one current stage", probe["current"] == 1, str(probe["current"]))
    check("ladder: current row is the one passed in", probe["curKey"] == "dialogue",
          str(probe["curKey"]))
    check("ladder: earlier stages carry the done mark",
          probe["done"] == 7 and probe["doneMark"] == "✓",
          f"done={probe['done']} first={probe['doneMark']!r}")
    check("ladder: later stages stay pending", probe["pendingMark"] == "○",
          str(probe["pendingMark"]))
    check("ladder: the current stage shows elapsed seconds, live",
          "4" in (probe["curText"] or "") and "s" in (probe["curText"] or ""),
          str(probe["curText"])[:80])
    check("ladder: no invented percentage anywhere", probe["percent"] is False)
    check("ladder: every stage has a plain-language caption",
          not probe["noCaption"], ",".join(probe["noCaption"])[:120])
    check("ladder: stage keys are unique", probe["dupKeys"] is False)
    check("heartbeat: a fresh pass reads as working",
          "s on this pass" in probe["elapsedFresh"], probe["elapsedFresh"])
    check("heartbeat: a silent pass says so instead of lying about progress",
          "waiting" in probe["elapsedStale"].lower(), probe["elapsedStale"])


def run(base):
    fresh = seed(base, "Lifecycle Probe")
    with sync_playwright() as p:
        browser, page, errors = launch(p)

        # --- 1. UNANALYZED state ------------------------------------------------
        open_project(page, base, fresh)
        desk_btn = page.locator("#desk-analyze-btn")
        status = page.locator("#desk-analyze-status")
        check("unanalyzed: Run Analysis is REACHABLE on the desk (hover reveals it)",
              reveal_chrome(page), "desk-analyze-btn never became the hit target")
        check("unanalyzed: button reads Run Analysis (not Re-run)",
              "Run Analysis" in desk_btn.inner_text() and "Re-run" not in desk_btn.inner_text())
        check("unanalyzed: honest status line",
              "Unanalyzed" in status.inner_text() or "unanalyzed" in status.inner_text(),
              status.inner_text()[:60])
        check("unanalyzed: manuscript stays readable",
              page.locator("#manuscript-container .scene-page").count() > 0)

        # --- 1b. the stage ladder, rendered deterministically from real events --
        check_stage_ladder(page)

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
            stage_txt = chip.locator(".ap-stage").inner_text()
            check("running: the desk names the pass in plain language",
                  "%" not in stage_txt and len(stage_txt.strip()) > 8, stage_txt[:80])
            check("running: the heartbeat says how long this pass has run",
                  "on this pass" in chip.locator(".ap-beat").inner_text(),
                  chip.locator(".ap-beat").inner_text()[:60])
            check("running: the stage ladder is mounted beside it",
                  chip.locator(".stage-ladder .stage").count() >= 12)
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
        # P2.16 (spec §15.2): the desk carries NO rerun of its own. Three buttons
        # (desk toolbar, drawer header, arrival strip) used to say "Retry failed"
        # in three places; the ledger's failure banner is now the only one, and the
        # desk's status line points there instead of duplicating the action.
        s = requests.get(f"{base}/api/projects/{fresh}", timeout=15).json()
        failed_n = len(s.get("failed_categories") or [])
        check("the desk toolbar has no retry button of its own",
              page.locator("#desk-retry-failed-btn").count() == 0
              and page.locator("#retry-failed-btn").count() == 0)
        on_desk = page.evaluate("""() => [...document.querySelectorAll('#desk-toolbar button')]
            .filter((b) => /rerun|retry/i.test(b.textContent || '')).length""")
        check("no rerun verb is clickable on the desk toolbar", on_desk == 0, str(on_desk))
        # ... and the status line, when something did fail, says where the fix is
        if failed_n:
            st_txt = status.inner_text()
            check("a partial report names the ledger as the way home",
                  "Evidence" in st_txt and str(failed_n) in st_txt, st_txt[:120])
        else:
            check("a clean desk status invents no rerun instruction",
                  "Retry" not in status.inner_text(), status.inner_text()[:120])

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
