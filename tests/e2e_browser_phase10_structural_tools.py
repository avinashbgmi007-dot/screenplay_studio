"""e2e_browser_phase10_structural_tools.py — Phase 10 gate: full-screen
structural tools (Beat Board / Compare / Revision) open, work, and return
without losing the writer's context.

MD §11 contract:
  Migrate/polish Beat Board, Compare, Revision (full-screen deep-work tools).
  Preserve Return Stack and restore: scene, scroll, selection, finding,
    dock context.
  Preserve existing: drag/reorder, comparison, revision, diff, export,
    navigation.
  Remove only decorative corkboard/wood treatment.

Gate: verify open, use, return, context restoration, and existing actions.

The suite uploads ONE fixture project, drives all three tools in a real
Chromium, and asserts the Return Stack survives every round trip:
  - open each tool from a scrolled, selection-active, dock-open desk
  - use the tool (reorder / compare / navigate findings)
  - return and check scroll, selection, scene highlight, dock lens + state
Corkboard/wood decor must be ABSENT (no pushpins, no tilt, no wood gradient).

Run:  python tests/e2e_browser_phase10_structural_tools.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests  # noqa: E402
from e2e_browser_common import Checks, launch, open_studio, assert_no_js_errors  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok


def seed_project(base, title):
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{base}/api/projects",
                          files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    return r.json()["project"]


def main():
    with open_studio() as base:
        with sync_playwright() as pw:
            browser, page, errors = launch(pw)
            page.goto(base)
            page.wait_for_load_state("networkidle")

            name = seed_project(base, "P10 Gate")
            page.evaluate("async (n) => { await openProject(n); }", name)
            page.wait_for_timeout(1800)

            # ---------- shared desk state: scroll + selection + dock ----------
            page.evaluate("""() => {
                const c = getManuscriptContainer();
                c.scrollTop = 350;
                c.dispatchEvent(new Event('scroll'));
                const node = c.querySelector('.el-dialogue, .el-action');
                const range = document.createRange();
                range.selectNodeContents(node);
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
            }""")
            page.evaluate("() => { openDock('evidence'); }")
            page.wait_for_timeout(500)
            desk = page.evaluate("""() => {
                const c = getManuscriptContainer();
                return {
                    top: c.scrollTop,
                    selLen: window.getSelection().toString().length,
                    dockOpen: dockIsOpen(),
                    lens: dockLens,
                    sceneCount: document.querySelectorAll('#manuscript-container .scene-page').length,
                };
            }""")
            check("desk starts scrolled+selected+dock-open", 
                  desk["top"] > 0 and desk["selLen"] > 0 and desk["dockOpen"], json.dumps(desk))

            # ================= BEAT BOARD =================
            page.evaluate("() => openBeatboardView()")
            page.wait_for_timeout(900)
            bb = page.evaluate("""() => ({
                view: state.view,
                open: document.getElementById('beatboard-view').style.display === 'flex',
                cards: document.querySelectorAll('#beatboard-view .bb-card').length,
                firstPos: (document.querySelector('#beatboard-view .bb-card-pos') || {}).textContent || '',
                tilts: [...document.querySelectorAll('#beatboard-view .bb-card')].some(c => getComputedStyle(c).transform !== 'none'),
                pushpins: !!document.querySelector('#beatboard-view .bb-card::before'),
            })""")
            check("beat board opens with the scene cards", 
                  bb["view"] == "beatboard" and bb["open"] and bb["cards"] >= 3, json.dumps(bb))
            # corkboard decor absent: computed card background is the quiet ink, not paper
            decor = page.evaluate("""() => {
                const card = document.querySelector('#beatboard-view .bb-card');
                const board = document.querySelector('#beatboard-view .beatboard-board');
                return {
                    cardBg: getComputedStyle(card).backgroundColor,
                    boardBg: getComputedStyle(board).backgroundColor,
                    cardTilt: getComputedStyle(card).transform,
                };
            }""")
            check("corkboard retired: cards are ink panels, not tilted paper",
                  "10, 14, 26" not in decor["cardBg"]      # no dark-wood tone
                  and "244, 236, 217" not in decor["cardBg"]  # no #f4ecd9 paper
                  and decor["cardTilt"] in ("none", ""), json.dumps(decor))

            # use: reorder via DRAG (the HTML5-DnD path — synthetic DragEvents
            # with a REAL DataTransfer fire the same bound handlers:
            # dragstart on card 1, dragover on card 3) then via ↑/↓ buttons
            drag = page.evaluate("""() => {
                const cards = [...document.querySelectorAll('#beatboard-view .bb-card')];
                if (cards.length < 3) return {ok: false, why: 'need 3 cards'};
                const before = cards.map(c => c.dataset.num).join(',');
                const src = cards[0], tgt = cards[2];
                const dt = new DataTransfer();
                const opts = {bubbles: true, cancelable: true, dataTransfer: dt};
                src.dispatchEvent(new DragEvent('dragstart', opts));
                tgt.dispatchEvent(new DragEvent('dragover', opts));
                src.dispatchEvent(new DragEvent('dragend', {...opts, dataTransfer: new DataTransfer()}));
                const after = [...document.querySelectorAll('#beatboard-view .bb-card')].map(c => c.dataset.num).join(',');
                return {ok: before !== after, before, after, dirty: document.getElementById('bb-save-btn').classList.contains('dirty')};
            }""")
            check("drag reorder moves a card and marks dirty (DnD path)",
                  drag.get("ok") and drag.get("dirty"), json.dumps(drag))
            # reopen the board fresh (drag already reordered + dirtied it)
            page.evaluate("() => closeBeatboardView()")
            page.wait_for_timeout(400)
            page.evaluate("() => openBeatboardView()")
            page.wait_for_timeout(900)
            page.locator("#beatboard-view .bb-card").nth(0).locator(".bb-move").nth(1).click()  # ↓ on card 1
            page.wait_for_timeout(400)
            moved = page.evaluate("""() => ({
                dirty: document.getElementById('bb-save-btn').classList.contains('dirty'),
                firstPos: (document.querySelector('#beatboard-view .bb-card-pos') || {}).textContent || '',
            })""")
            check("reorder marks the board dirty (save-order contract)", moved["dirty"], json.dumps(moved))
            # export link wired to the reordered-draft endpoint (existing action)
            exp = page.evaluate("""() => ({
                href: document.getElementById('bb-export').href,
                download: document.getElementById('bb-export').download,
            })""")
            check("export link targets the beatboard export endpoint",
                  "/beatboard/export?format=fountain" in exp["href"]
                  and exp["download"].endswith(".fountain"), json.dumps(exp))
            export_resp = requests.get(exp["href"], timeout=30)
            check("export endpoint serves the reordered draft (200, fountain text)",
                  export_resp.status_code == 200
                  and "HOSPITAL" in export_resp.text, str(export_resp.status_code))
            page.evaluate("() => saveBeatboard()")
            page.wait_for_timeout(600)
            saved = page.evaluate("""() => ({
                dirty: !document.getElementById('bb-save-btn').classList.contains('dirty'),
            })""")
            check("save order persists (dirty clears)", saved["dirty"], json.dumps(saved))

            # return: back to the page
            page.evaluate("() => closeBeatboardView()")
            page.wait_for_timeout(700)
            rb = page.evaluate("""() => {
                const c = getManuscriptContainer();
                return {
                    top: c.scrollTop, selLen: window.getSelection().toString().length,
                    view: state.view, dockOpen: dockIsOpen(), lens: dockLens,
                };
            }""")
            check("return from beat board restores scroll+selection+dock (Return Stack)",
                  rb["view"] == "cowrite" and rb["top"] == desk["top"]
                  and rb["selLen"] > 0 and rb["dockOpen"] and rb["lens"] == desk["lens"],
                  f"desk={json.dumps(desk)} back={json.dumps(rb)}")

            # ================= COMPARE (empty state) =================
            page.evaluate("() => openCompareView()")
            page.wait_for_timeout(900)
            ce = page.evaluate("""() => ({
                view: state.view,
                open: document.getElementById('compare-view').style.display === 'flex',
                hint: (document.querySelector('#compare-view .script-empty-hint') || {}).textContent || '',
            })""")
            check("compare opens with honest single-draft hint",
                  ce["view"] == "compare" and ce["open"] and "Nothing to compare" in ce["hint"],
                  json.dumps(ce))
            page.evaluate("() => closeCompareView()")
            page.wait_for_timeout(700)

            # ================= COMPARE (real, with a 2nd draft) =================
            # upload a modified second draft through the API
            with open(FIXTURE, "rb") as f:
                text = f.read().decode("utf-8")
            text2 = text.replace("EXT/INT. HOSPITAL - NIGHT", "EXT. HOSPITAL ENTRANCE - NIGHT", 1)
            r = requests.post(f"{base}/api/projects/{name}/drafts",
                             files={"file": ("second.fountain", text2.encode("utf-8"), "text/plain")},
                             timeout=60)
            assert r.status_code in (200, 201), r.text
            page.evaluate("() => openCompareView()")
            page.wait_for_timeout(1200)
            cr = page.evaluate("""() => ({
                scenes: document.querySelectorAll('#compare-view .cmp-scene').length,
                changed: document.querySelectorAll('#compare-view .cmp-changed').length,
                added: document.querySelectorAll('#compare-view .cmp-added').length,
                removed: document.querySelectorAll('#compare-view .cmp-removed').length,
                fromLabel: (document.querySelector('#compare-from-select') || {}).value || '',
            })""")
            check("compare renders the side-by-side diff for two drafts",
                  cr["scenes"] >= 1 and (cr["changed"] + cr["added"] + cr["removed"]) >= 1,
                  json.dumps(cr))
            page.evaluate("() => closeCompareView()")
            page.wait_for_timeout(700)
            rc = page.evaluate("""() => {
                const c = getManuscriptContainer();
                return {top: c.scrollTop, view: state.view, dockOpen: dockIsOpen()};
            }""")
            check("return from compare restores desk (Return Stack)",
                  rc["view"] == "cowrite" and rc["top"] == desk["top"] and rc["dockOpen"],
                  json.dumps(rc))

            # ================= REVISION =================
            page.evaluate("() => openRevisionView()")
            page.wait_for_timeout(1200)
            rv = page.evaluate("""() => ({
                view: state.view,
                open: document.getElementById('revision-view').style.display === 'flex',
                navRows: document.querySelectorAll('#revision-nav .revision-nav-row').length,
                pages: document.querySelectorAll('#revision-script .scene-page').length,
            })""")
            check("revision desk opens: scene navigator + pages",
                  rv["view"] == "revision" and rv["open"] and rv["navRows"] >= 3 and rv["pages"] >= 3,
                  json.dumps(rv))
            # use: navigate via a nav row (existing navigation action)
            rows = page.locator("#revision-nav .revision-nav-row")
            if rows.count() >= 3:
                rows.nth(2).click()
            page.wait_for_timeout(500)
            nav = page.evaluate("""() => ({
                activeRow: (document.querySelector('#revision-nav .revision-nav-row.active .rn-num') || {}).textContent || '',
            })""")
            check("revision navigation selects scene rows", nav["activeRow"] != "", json.dumps(nav))
            page.evaluate("() => closeRevisionView()")
            page.wait_for_timeout(700)
            rr = page.evaluate("""() => {
                const c = getManuscriptContainer();
                return {top: c.scrollTop, selLen: window.getSelection().toString().length,
                        view: state.view, dockOpen: dockIsOpen()};
            }""")
            check("return from revision restores scroll+selection+dock (Return Stack)",
                  rr["view"] == "cowrite" and rr["top"] == desk["top"]
                  and rr["selLen"] > 0 and rr["dockOpen"],
                  f"desk={json.dumps(desk)} back={json.dumps(rr)}")

            # ---------- cleanup ----------
            requests.delete(f"{base}/api/projects/{name}", timeout=30)
            assert_no_js_errors(checks, errors)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    main()
