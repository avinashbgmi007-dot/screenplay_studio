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

from e2e_browser_common import (Checks, clicked, filled, launch, note,
                                seen_visible, start_studio)

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
        # "blank page opens (writing-first)" promises TWO things the throwing wait
        # never checked: that the editor opened, AND that it is BLANK — the
        # writing-first contract is a fresh empty page, not a prefilled one. The
        # old `check(name, True)` earned neither, and a failure was a crash.
        ok = seen_visible(page, "#idea-content", timeout=8000)
        blank = (page.locator("#idea-content").input_value() or "").strip() == ""
        check("idea: blank page opens (writing-first)", ok and blank,
              f"visible={ok} blank={blank}")
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
        # "one streamed turn ANSWERS" — so assert the answer is a real one: the
        # turn landed AND its text is substantive (not an empty bubble, not the
        # unreachable-model copy). The throwing wait only proved a bubble existed.
        ok = seen_visible(page, ".msg.assistant:not(.msg-pending)", timeout=20000)
        answer = page.locator(".msg.assistant:not(.msg-pending)").last.inner_text().strip()
        check("sameer: one streamed turn answers",
              ok and len(answer) > 40 and "couldn't be reached" not in answer,
              f"visible={ok} chars={len(answer)} head={answer[:60]!r}")
        page.locator("#drawer-close").click()   # proven dismiss (not Escape —
        page.wait_for_timeout(500)              # the chat consumes it)

        # ================= 4. PREMISE DOCTOR =================
        # the structured card is the idea's premise-doctor face
        page.locator("#idea-structure-btn").click()
        page.wait_for_selector("#idea-structure-panel", state="visible", timeout=5000)
        page.locator("#idea-logline").fill(
            "A courier must deliver a letter she wrote to herself ten years ago — before she reads it.")
        page.locator("#idea-structure-save").click()
        # The save confirms on the button itself: saveIdeaStructure() sets
        # textContent to "Saved ✓" and reverts it 1400ms later. The check's name
        # claims the card SAVES, so assert the confirmation rather than sleeping
        # 600ms and passing unconditionally -- the old form could not fail even
        # if the POST never happened. (Initial text is "Save structure", so
        # matching the "Saved" prefix cannot be satisfied by the resting state.)
        confirmed = False
        try:
            page.wait_for_function(
                "() => { const b = document.querySelector('#idea-structure-save');"
                " return !!b && b.textContent.indexOf('Saved') === 0; }",
                timeout=5000)
            confirmed = True
        except Exception:
            confirmed = False
        check("premise: structure card saves beside the idea", confirmed,
              "the save button never showed its confirmation")

        # ================= 5. SCRIPT (graduate) =================
        with open(FIXTURE, "rb") as f:
            page.locator("#idea-file-input").set_input_files(
                {"name": "pain.fountain", "mimeType": "text/plain",
                 "buffer": f.read()})
        # "idea GRADUATES INTO A SCRIPT on the desk" — assert the scene page has
        # real rendered text, so an empty manuscript shell cannot pass. The
        # throwing wait only proved a `.scene-page` element appeared.
        ok = seen_visible(page, "#manuscript-container .scene-page", timeout=25000)
        first_page = page.locator("#manuscript-container .scene-page").first.inner_text().strip()
        check("script: idea graduates into a script on the desk",
              ok and len(first_page) > 20,
              f"visible={ok} firstPageChars={len(first_page)}")
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
            # The chip being visible is a RACE with the demo model, not a
            # contract: on a fast run the whole analysis finishes inside the
            # 800 ms poll and the chip is legitimately gone. `check(name, True)`
            # claimed the chip was "live on the desk" while asserting nothing,
            # and asserting it for real would be flaky — the `library_delete`
            # trap in reverse. So it is a note; the real checks below run only
            # when the chip was actually caught.
            note("progress: chip caught live on the desk")
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
        # GO 2 fold (ratified): openFeedbackView() routes to the workspace + the
        # dock's Evidence lens — that lens IS the Problem Board. The old
        # #feedback-view 3-panel clone is deliberately dormant and unreachable
        # (grep-gated in the layout audit). Asserting the clone's visibility here
        # was a stale check that could never pass; assert the LIVE surface, and
        # pin the clone as hidden so a regression can't quietly revive it.
        page.evaluate("() => openFeedbackView()")
        page.wait_for_selector("#context-dock.open", timeout=8000)
        page.wait_for_timeout(500)
        lens = page.locator('.dock-lens[data-lens="evidence"]')
        check("feedback: the Evidence lens opens (the folded board)", lens.is_visible())
        check("category/finding: the board renders findings by scene",
              lens.locator(".dock-evidence-scene").count() > 0,
              f"scenes={lens.locator('.dock-evidence-scene').count()}")
        check("feedback: the retired clone stays dormant",
              not page.locator("#feedback-view").is_visible())
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
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
        # NOTE: `note` is the imported diagnostic helper — do NOT shadow it with a
        # locator, or Python makes `note` local for the whole function and the
        # earlier `note(...)` call raises UnboundLocalError (ruff F823 caught it).
        note_el = page.locator("#manuscript-container .finding-note").first
        note_el.locator("button", has_text="Rewrite").click()
        # "rewrite modal OPENS FROM THE FINDING CARD" — assert it opened AND is
        # armed (its generate control exists), so an empty modal shell cannot
        # pass. The throwing wait proved only that the element became visible.
        ok = seen_visible(page, "#rewrite-modal", timeout=5000)
        # is_visible, not count()>0: PRESENCE is satisfied by a hidden button, so a
        # modal that opened as an empty shell would still pass. This is the half of
        # the claim the throwing wait never covered.
        armed = page.locator("#rewrite-generate").is_visible()
        check("inline edit: rewrite modal opens from the finding card", ok and armed,
              f"modalVisible={ok} generateVisible={armed}")
        # Bounded follow-on actions. With the modal unarmed, the old code walked
        # straight into `page.locator("#rewrite-generate").click()`, which TIMES
        # OUT and aborts the run — so the named failure above never printed and
        # every later check was masked. Mutation-verified.
        gen_clicked = clicked(page, "#rewrite-generate")
        cands_seen = gen_clicked and seen_visible(
            page, "#rewrite-candidates .rewrite-candidate", timeout=30000)
        cand = page.locator("#rewrite-candidates .rewrite-candidate")
        check("inline edit: the model proposes a targeted change",
              cands_seen and cand.count() > 0,
              f"generateClicked={gen_clicked} candidates={cand.count()}")
        apply_clicked = clicked(page, "#rewrite-apply")
        page.wait_for_timeout(2500)
        demo_line = page.locator("#manuscript-container", has_text="[demo] The line lands quieter")
        check("inline edit: the change lands in the manuscript",
              apply_clicked and demo_line.count() > 0, f"applyClicked={apply_clicked}")
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

        if not armed:
            # An armed-modal failure leaves the modal OPEN, and an open overlay
            # intercepts every later click — so the rest of the journey would die
            # on a click timeout instead of reporting. Close it and carry on.
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)

        # ================= 13. NOTES (margin) =================
        page.evaluate("() => openDock('notes')")
        page.wait_for_timeout(500)
        # Bounded: if the dock never opened (an overlay still up, a failed prior
        # step), an unguarded fill()/click() times out and ABORTS the run —
        # masking every later check. Mutation-verified via the un-armed modal.
        typed = filled(page, "#dock-note-input", "journey: pin this thought")
        submitted = typed and clicked(page, "#dock-note-form button[type=submit]")
        page.wait_for_timeout(900)
        check("notes: margin note pins into the rail",
              submitted and page.locator("#rail-notes .rail-note").count() > 0,
              f"typed={typed} submitted={submitted}")
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
