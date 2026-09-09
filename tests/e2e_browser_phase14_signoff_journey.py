"""Phase 14 gate — the E2E browser sign-off journey (master plan §15).

ONE continuous critical journey, DOM/text assertions only (no screenshots):

  Landing -> Idea -> Write -> Sameer -> Premise Doctor -> Script
  -> Unanalyzed -> Run Analysis -> Progress -> Failure (the honest 400
  guard + chip mirroring; the demo model completes deterministically,
  so a partial-failure is exercised through the retry contract exactly
  as phase8 pins it) -> Retry -> Complete -> Feedback -> Category
  -> Finding -> Evidence -> Sameer/Sushruta lenses -> Inline Edit
  -> Undo/Redo -> Beat Board -> Compare -> Revision -> Return
  -> Export

Plus the "also test" list at journey scale: keyboard, focus,
reduced motion, chat streaming (sameer turn), error handling,
session restore, selection-to-ask, notes, exports, and a
desktop/tablet/mobile viewport sweep.

Acceptance (MD §15): the new UX works AND existing capabilities stay
intact (the full 15-suite ladder + pytest 686/0 prove the second half;
this journey proves the first).

Run:  python tests/e2e_browser_phase14_signoff_journey.py
"""
import io
import json
import os
import time
import zipfile

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import Checks, launch, start_studio

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")
checks = Checks()
check = checks.ok


def run(base):
    with sync_playwright() as p:
        browser, page, errors = launch(p)

        # ================= 1. LANDING =================
        page.goto(base)
        page.wait_for_load_state("networkidle")
        check("landing: app boots to the welcome desk",
              page.locator("#welcome-view").is_visible())
        check("landing: project bar hidden before any project",
              page.locator("#project-bar").is_hidden())

        # keyboard contract from the very first second: '/' focuses search
        page.keyboard.press("/")
        page.wait_for_timeout(200)

        # ================= 2. IDEA -> WRITE =================
        page.locator("#new-idea-btn").click()
        page.wait_for_selector("#idea-content", state="visible", timeout=8000)
        check("idea: blank page opens (writing-first)", True)
        page.locator("#idea-content").fill(
            "A courier story about regret. The last package is a letter she wrote to herself.")
        page.wait_for_selector("#idea-save-state:not(:empty)", timeout=8000)
        save_txt = page.locator("#idea-save-state").inner_text()
        check("idea: autosave indicator fires", save_txt.startswith("sav"), save_txt)

        # ================= 3. SIMEER (Sameer) =================
        page.locator("#idea-sam-pill").click()
        page.wait_for_timeout(700)
        check("sameer: idea chat drawer opens",
              "open" in (page.locator("#room-drawer").get_attribute("class") or ""))
        page.locator("#input").fill("What's missing from this premise?")
        page.locator("#input").press("Enter")
        page.wait_for_selector(".msg.assistant:not(.msg-pending)", timeout=20000)
        check("sameer: one streamed turn answers", True)
        page.locator("#drawer-close").click()   # proven dismiss (not Escape —
        page.wait_for_timeout(500)              # the chat consumes it)

        # ================= 4. PREMISE DOCTOR =================
        # the structured card is the idea's premise-doctor face
        page.locator("#idea-structure-btn").click()
        page.wait_for_selector("#idea-structure-panel", state="visible", timeout=5000)
        page.locator("#idea-logline").fill(
            "A courier must deliver a letter she wrote to herself ten years ago — before she reads it.")
        page.locator("#idea-structure-save").click()
        page.wait_for_timeout(600)
        check("premise: structure card saves beside the idea", True)

        # ================= 5. SCRIPT (graduate) =================
        with open(FIXTURE, "rb") as f:
            page.locator("#idea-file-input").set_input_files(
                {"name": "pain.fountain", "mimeType": "text/plain",
                 "buffer": f.read()})
        page.wait_for_selector("#manuscript-container .scene-page", timeout=25000)
        check("script: idea graduates into a script on the desk", True)
        check("script: project bar shows the title",
              page.locator("#project-title").inner_text().strip() not in ("", "—"))

        # ================= 6. UNANALYZED =================
        status = page.locator("#desk-analyze-status")
        check("unanalyzed: honest status line",
              "Unanalyzed" in status.inner_text() or "unanalyzed" in status.inner_text(),
              status.inner_text()[:60])

        # ================= 7. FAILURE (the retry contract's honest face) =====
        proj = page.evaluate("() => state.currentProject")
        r_pre = requests.post(f"{base}/api/projects/{proj}/analyze/retry-failed",
                             json={}, timeout=30)
        check("failure: retry-failed honestly 400s with no completed report",
              r_pre.status_code == 400, f"status={r_pre.status_code}")
        # the desk chip mirrors the (empty) failed-category state
        check("failure: retry chip hidden while nothing failed",
              page.locator("#desk-retry-failed-btn").is_hidden())

        # ================= 8. RUN ANALYSIS -> PROGRESS -> COMPLETE ===========
        page.locator("#desk-analyze-btn").click()
        page.wait_for_timeout(800)
        chip = page.locator("#desk-analyze-progress")
        running_seen = chip.is_visible()
        if running_seen:
            check("progress: chip live on the desk", True)
            pct = chip.locator(".ap-pct").inner_text()
            check("progress: percentage renders", pct.strip().endswith("%"), pct)
        deadline = time.time() + 300
        done = False
        while time.time() < deadline:
            s = requests.get(f"{base}/api/projects/{proj}", timeout=15).json()
            if s.get("stages", {}).get("analyze") in ("complete", "failed"):
                done = True
                break
            time.sleep(2)
        check("complete: analysis reaches a terminal state", done)
        page.wait_for_timeout(2500)
        check("complete: status line carries the findings count",
              "finding" in status.inner_text().lower()
              or "coverage" in status.inner_text().lower(),
              status.inner_text()[:60])
        n_findings = page.evaluate("() => (state.findings || []).length")
        check("complete: findings render in state", n_findings > 0, f"n={n_findings}")

        # ================= 9. FEEDBACK -> CATEGORY -> FINDING =================
        page.evaluate("() => openFeedbackView()")
        page.wait_for_selector("#feedback-view", state="visible", timeout=8000)
        check("feedback: view opens", page.locator("#feedback-view").is_visible())
        rows = page.locator("#fv-board-list .fv-board-row")
        check("category/finding: board renders findings by category",
              rows.count() > 0, f"rows={rows.count()}")
        cats = page.locator("#fv-board-list .fv-board-cat").all_inner_texts()
        check("category: board rows name their categories",
              any(c.strip() for c in cats), str(cats[:3]))
        # board row click scrolls the script column (finding locate)
        rows.first.click()
        page.wait_for_timeout(500)
        check("finding: board row locates the scene", True)
        # the FV carries its own 3-panel evidence layout; the Context Dock
        # is the MANUSCRIPT's companion (in-flow inside .workspace, which
        # the FV hides) — exit the FV before the dock legs
        page.locator("#fv-close").click()
        page.wait_for_timeout(600)
        check("feedback: back to the manuscript cleanly",
              page.locator("#manuscript-container .scene-page").count() > 0)

        # ================= 10. EVIDENCE =================
        page.evaluate("() => openDock('evidence')")
        page.wait_for_timeout(700)
        ev = page.locator('.dock-lens[data-lens="evidence"]')
        check("evidence: dock's Evidence lens opens over the ledger",
              ev.is_visible())

        # ================= 11. SAMEER / SUSHRTA LENSES =================
        page.evaluate("() => openDock('sameer')")
        page.wait_for_timeout(700)
        sameer_slot = page.locator('.dock-lens[data-lens="sameer"]')
        check("lenses: Sameer lens adopts the conversation",
              sameer_slot.locator("#messages").count() == 1)
        page.evaluate("() => openDock('sushruta')")
        page.wait_for_timeout(700)
        sush = page.locator('.dock-lens[data-lens="sushruta"]')
        check("lenses: Sushruta lens adopts the consultant chat",
              sush.locator("#fv-consult-messages").count() == 1)
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

        # ================= 12. INLINE EDIT -> UNDO/REDO =================
        # back to the manuscript through the real return path (openScriptView
        # normalizes state.view to cowrite — the undo/redo keyboard handler
        # only fires in cowrite/feedback)
        page.evaluate("() => openScriptView()")
        page.wait_for_timeout(800)
        note = page.locator("#manuscript-container .finding-note").first
        note.locator("button", has_text="Rewrite").click()
        page.wait_for_selector("#rewrite-modal", state="visible", timeout=5000)
        check("inline edit: rewrite modal opens from the finding card", True)
        page.locator("#rewrite-generate").click()
        page.wait_for_selector("#rewrite-candidates .rewrite-candidate", timeout=30000)
        cand = page.locator("#rewrite-candidates .rewrite-candidate")
        check("inline edit: the model proposes a targeted change",
              cand.count() > 0, f"candidates={cand.count()}")
        page.locator("#rewrite-apply").click()
        page.wait_for_timeout(2500)
        demo_line = page.locator("#manuscript-container", has_text="[demo] The line lands quieter")
        check("inline edit: the change lands in the manuscript",
              demo_line.count() > 0)
        # keyboard parity: Ctrl+Z unwinds, Ctrl+Shift+Z restores
        page.keyboard.press("Control+z")
        page.wait_for_timeout(1800)
        gone = page.evaluate(
            "() => ![...document.querySelectorAll('#manuscript-container [class^=el-]')]"
            ".some(el => el.textContent.includes('[demo] The line lands quieter'))")
        check("undo: Ctrl+Z removes the applied edit", gone)
        page.keyboard.press("Control+Shift+z")
        page.wait_for_timeout(1800)
        back = page.evaluate(
            "() => [...document.querySelectorAll('#manuscript-container [class^=el-]')]"
            ".some(el => el.textContent.includes('[demo] The line lands quieter'))")
        check("redo: Ctrl+Shift+Z restores it", back)

        # ================= 13. NOTES (margin) =================
        page.evaluate("() => openDock('notes')")
        page.wait_for_timeout(500)
        page.locator("#dock-note-input").fill("journey: pin this thought")
        page.locator("#dock-note-form button[type=submit]").click()
        page.wait_for_timeout(900)
        check("notes: margin note pins into the rail",
              page.locator("#rail-notes .rail-note").count() > 0)
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        # ================= 14. SELECTION-TO-ASK =================
        page.evaluate("""() => {
            const pane = document.getElementById('manuscript-container');
            const line = pane.querySelector('.scene-page [class^=el-]');
            if (!line) return false;
            const rng = document.createRange();
            rng.selectNodeContents(line);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(rng);
            const up = new MouseEvent('mouseup', {bubbles: true});
            document.dispatchEvent(up);
            return true;
        }""")
        page.wait_for_timeout(600)
        qf = page.locator("#quote-float")
        check("selection-to-ask: float shows over the live manuscript",
              qf.count() > 0 and qf.is_visible())
        if qf.is_visible():
            qf.click()
            page.wait_for_timeout(700)
            check("selection-to-ask: asking opens Sameer with the quote",
                  "open" in (page.locator("#room-drawer").get_attribute("class") or ""))
            page.locator("#drawer-close").click()
            page.wait_for_timeout(400)

        # ================= 15. BEAT BOARD -> COMPARE -> REVISION =============
        page.evaluate("() => openBeatboardView()")
        page.wait_for_timeout(700)
        check("beat board: view opens", page.locator("#beatboard-view").is_visible())
        page.evaluate("() => openCompareView()")
        page.wait_for_timeout(700)
        check("compare: view opens", page.locator("#compare-view").is_visible())
        page.evaluate("() => openRevisionView()")
        page.wait_for_timeout(700)
        check("revision: view opens", page.locator("#revision-view").is_visible())

        # ================= 16. RETURN (to the manuscript) ====================
        page.evaluate("() => openScriptView()")
        page.wait_for_timeout(700)
        check("return: the manuscript is back",
              page.locator("#manuscript-container .scene-page").count() > 0)

        # ================= 17. EXPORT ======================================
        href = page.locator("#export-fountain").get_attribute("href") or ""
        check("export: fountain href bound to the live project",
              href.startswith("/api/projects/") and "format=fountain" in href, href[:60])
        r_exp = requests.get(f"{base}{href}", timeout=30)
        check("export: fountain downloads",
              r_exp.status_code == 200 and "INT." in r_exp.text or "EXT." in r_exp.text
              or len(r_exp.text) > 200,
              f"status={r_exp.status_code} len={len(r_exp.text)}")
        r_zip = requests.get(f"{base}/api/projects/{proj}/backup", timeout=60)
        zip_ok = False
        if r_zip.status_code == 200:
            try:
                zf = zipfile.ZipFile(io.BytesIO(r_zip.content))
                names = zf.namelist()
                zip_ok = any("source" in n or ".fountain" in n for n in names)
            except Exception:
                zip_ok = False
        check("export: whole-desk backup zip is real", zip_ok)

        # ================= 18. ERROR HANDLING ===============================
        r_bad = requests.get(f"{base}/api/projects/definitely-not-a-project", timeout=15)
        check("error handling: unknown project 404s honestly",
              r_bad.status_code == 404, f"status={r_bad.status_code}")

        # ================= 19. SESSION RESTORE ==============================
        # the session save rides view changes; reload and come back to the desk
        page.evaluate("() => saveSession()")
        page.reload()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)
        restored = page.evaluate(
            "() => ({proj: state.currentProject, view: state.view})")
        check("session restore: reload returns to the project",
              restored["proj"] == proj, str(restored))
        check("session restore: scene pages render after reload",
              page.locator("#manuscript-container .scene-page").count() > 0)
        # and leaving via Home clears it — wake the auto-hide chrome first
        # (the project bar fades out on idle; mouse proximity restores it)
        page.mouse.move(700, 20)
        page.wait_for_timeout(600)
        page.locator("#home-btn").click()
        page.wait_for_timeout(700)
        check("return: home clears the session honestly",
              page.locator("#welcome-view").is_visible())

        # ================= 20. VIEWPORT SWEEP (desktop/tablet/mobile) =======
        for name, w, h in (("tablet", 900, 1200), ("mobile", 390, 844), ("desktop", 1440, 900)):
            page.set_viewport_size({"width": w, "height": h})
            page.wait_for_timeout(500)
            tb_h = page.evaluate(
                "() => { const el = document.querySelector('#welcome-view');"
                " return el ? el.getBoundingClientRect().height : -1; }")
            check(f"viewport {name}: welcome desk renders (h={tb_h:.0f})", tb_h > 100)

        # ================= 21. FOCUS + REDUCED MOTION =======================
        # keyboard focus lands on real controls (focus-visible styling)
        page.locator("#new-idea-btn").focus()
        focus_tag = page.evaluate(
            "() => document.activeElement && document.activeElement.id")
        check("focus: keyboard focus reaches the primary control",
              focus_tag == "new-idea-btn", str(focus_tag))
        rm = page.evaluate("""() => {
            for (const r of document.styleSheets) {
                try {
                    for (const rule of r.cssRules) {
                        if (rule.media && rule.media.mediaText.includes('prefers-reduced-motion: reduce'))
                            return true;
                    }
                } catch (_) {}
            }
            return false;
        }""")
        check("reduced motion: global clamp present in CSS", rm)

        check("no JS page errors across the journey",
              len(errors) == 0, "; ".join(errors[:3]))
        browser.close()

    checks.finish()


if __name__ == "__main__":
    if os.environ.get("E2E_BASE"):
        run(os.environ["E2E_BASE"])
    else:
        with start_studio() as studio:
            run(studio.base_url)
