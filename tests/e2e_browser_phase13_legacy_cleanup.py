"""Phase 13 — Legacy cleanup: parity + dead-code gate.

Proves the migration's end state: ONE presentation architecture.

  * the legacy surfaces are GONE (markup, class, and renderer):
    #script-scenes, #script-toolbar / .script-toolbar, .premise-pane,
    renderScriptView(), and the getManuscriptContainer() fallback
  * every migrated control still has a reachable home:
    #desk-toolbar (finding chips, search), #premise-view, the Stash &
    Notes dock lens, the selection floats
  * the Problem Board is VISIBLE in script mode. It spent every phase
    since Stage 3B nested inside .desk (display:none in script mode), so
    toggling it "open" rendered 0x0 — the phase 5/6 gates asserted
    count() > 0 (existence) and never saw it. Visibility is asserted here.
  * mode rules point at the LIVE row: spotlight hides the desk toolbar
    (and the board), focus mode dims it (filter, still visible)

Run:  python tests/e2e_browser_phase13_legacy_cleanup.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import Checks, assert_no_js_errors, launch, open_studio

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok


def probe(page, sel):
    """Return (exists, display, visible-with-box) for a selector."""
    return page.evaluate(
        """(sel) => {
        const el = document.querySelector(sel);
        if (!el) return null;
        const cs = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { display: cs.display,
                 visible: cs.display !== 'none' && r.width > 0 && r.height > 0,
                 w: Math.round(r.width), h: Math.round(r.height) };
    }""",
        sel,
    )


def main():
    with open_studio() as base:
        with sync_playwright() as pw:
            browser, page, errors = launch(pw)
            with open(FIXTURE, "rb") as f:
                resp = requests.post(
                    f"{base}/api/projects",
                    files={"file": ("P13D Verify.fountain", f, "text/plain")},
                    data={"title": "P13D Verify"},
                    timeout=60,
                )
            name = resp.json()["project"]

            page.goto(base)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(600)
            page.evaluate("async (n) => { await openProject(n); }", name)
            page.wait_for_timeout(2000)

            # ---- 1. dead-code absence -------------------------------------
            for sel, label in [
                ("#script-scenes", "script-scenes container"),
                ("#script-toolbar", "script-toolbar row"),
                ("#premise-pane", "premise pane"),
                (".script-toolbar", "script-toolbar class"),
                (".script-scenes", "script-scenes class"),
            ]:
                check(f"absent from DOM: {label}",
                      page.locator(sel).count() == 0)

            check("renderScriptView undefined",
                  page.evaluate("() => typeof renderScriptView === 'undefined'"))
            check("getManuscriptContainer returns the live container",
                  page.evaluate(
                      "() => getManuscriptContainer()?.id === 'manuscript-container'"))

            # ---- 2. the live desk row is intact ---------------------------
            tb = probe(page, "#desk-toolbar")
            check("desk toolbar visible on the desk",
                  bool(tb and tb["visible"]), str(tb))
            fs = probe(page, "#finding-summary")
            check("finding chips render on the desk row",
                  bool(fs and fs["visible"]), str(fs))

            # ---- 3. Problem Board relocation (the buried-since-3B fix) ---
            # Seed findings onto state — no model needed (the real analysis
            # path is the phase 8 gate's job). The board renders from
            # state.findings, and the auto-expand observer keys off the
            # active scene, so these belong to scene 1.
            page.evaluate(
                """() => {
        state.findings = [
          { category: 'Pacing', issue: 'Scene drags',
            description: 'Scene 1 sags in the middle.', severity: 'high',
            scene_refs: [1], scene: 1 },
          { category: 'Dialogue', issue: 'On-the-nose line',
            description: 'A character says exactly what they mean.',
            severity: 'medium', scene_refs: [1], scene: 1 },
          { category: 'Structure', issue: 'Late inciting incident',
            description: 'Nothing tilts until page 12.', severity: 'low',
            scene_refs: [1], scene: 1 },
        ];
    }""")
            page.evaluate("() => toggleProblemBoard()")
            page.wait_for_timeout(800)
            board = probe(page, "#problem-board")
            check("problem board VISIBLE after toggle (script mode)",
                  bool(board and board["visible"]), str(board))
            check("board is inside the live workspace row",
                  page.evaluate(
                      "() => !!document.querySelector('.manuscript-workspace-layout > #problem-board')"))
            n_items = page.locator("#pb-list .pb-item").count()
            check("board renders its findings", n_items == 3, f"items={n_items}")

            # collapse -> the edge tab must surface (sibling pairing survived
            # the move). Assert from real state, not from a toggle-count guess:
            # with no findings on the active scene the board auto-collapses on
            # the very first toggle, so "which phase are we in" is a state read.
            def board_state():
                return page.evaluate(
                    """() => {
            const b = document.getElementById('problem-board');
            const t = document.getElementById('pb-edge-tab');
            const tr = t.getBoundingClientRect();
            return { collapsed: b.classList.contains('pb-collapsed'),
                     visible: b.classList.contains('visible'),
                     tab_visible: getComputedStyle(t).display !== 'none' && tr.width > 0 };
        }""")

            if not board_state()["collapsed"]:
                page.evaluate("() => toggleProblemBoard()")
                page.wait_for_timeout(700)
            st = board_state()
            check("collapsed board surfaces the edge tab (visible)",
                  bool(st["collapsed"] and st["tab_visible"]), str(st))

            # the collapsed board (translateX(105%)) must be fully outside
            # the row it lives in — the row clips it, so nothing bleeds into
            # the transparent 56px gutter.
            geom = page.evaluate(
                """() => {
        const b = document.getElementById('problem-board').getBoundingClientRect();
        const row = document.querySelector('.manuscript-workspace-layout');
        const r = row.getBoundingClientRect();
        return { board_left: Math.round(b.left), row_right: Math.round(r.right),
                 clipped: getComputedStyle(row).overflow !== 'visible',
                 vw: window.innerWidth };
    }""")
            check("collapsed board is clipped, never bleeds into the gutter",
                  bool(geom["clipped"] and geom["board_left"] >= geom["row_right"]),
                  str(geom))

            # two handles share the row's right edge — the Board tab must not
            # cover the dock's "Context" affordance (it did at right:0, which
            # made the dock unopenable whenever the board was collapsed).
            reach = page.evaluate(
                """() => {
        const a = document.getElementById('right-edge-affordance').getBoundingClientRect();
        const hit = document.elementFromPoint(a.left + a.width / 2, a.top + a.height / 2);
        return { hit: hit && (hit.id || hit.className), w: Math.round(a.width) };
    }""")
            check("collapsed board does not cover the Context affordance",
                  reach["hit"] == "right-edge-affordance", str(reach))

            page.locator("#pb-edge-tab").click(timeout=8000)
            page.wait_for_timeout(700)
            st2 = board_state()
            check("edge tab reopens (expands) the board",
                  bool(not st2["collapsed"] and st2["visible"]), str(st2))

            # an open dock must not be buried by the board (sibling rule)
            page.evaluate("() => openDock('evidence')")
            page.wait_for_timeout(700)
            dock_geom = page.evaluate(
                """() => {
        const b = document.getElementById('problem-board').getBoundingClientRect();
        const d = document.getElementById('context-dock').getBoundingClientRect();
        return { board_right: Math.round(b.right), dock_left: Math.round(d.left),
                 dock_open: document.getElementById('context-dock').classList.contains('open') };
    }""")
            # the board bows LEFT of an open dock — no overlap (1px tolerance)
            check("board bows to an open dock (does not cover it)",
                  bool(not dock_geom["dock_open"]
                       or dock_geom["board_right"] <= dock_geom["dock_left"] + 1),
                  str(dock_geom))
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)

            # ---- 4. mode swaps: spotlight hides the NEW toolbar row -------
            page.evaluate("() => toggleSpotlight()")
            page.wait_for_timeout(600)
            st = probe(page, "#desk-toolbar")
            check("spotlight hides the desk toolbar",
                  bool(st and not st["visible"]), str(st))
            board_sp = probe(page, "#problem-board")
            check("spotlight hides the problem board too (nothing but the page)",
                  bool(board_sp and not board_sp["visible"]), str(board_sp))
            page.evaluate("() => exitSpotlight()")
            page.wait_for_timeout(600)

            # focus mode dims the toolbar (filter swap, not disappearance)
            page.evaluate("() => applyFocusMode(true)")
            page.wait_for_timeout(600)
            fm = page.evaluate(
                """() => {
        const el = document.querySelector('#desk-toolbar');
        const cs = getComputedStyle(el);
        return { display: cs.display, filter: cs.filter,
                 visible: cs.display !== 'none' && el.getBoundingClientRect().height > 0 };
    }""")
            check("focus mode dims the desk toolbar (filter, still visible)",
                  bool(fm and fm["visible"] and fm["filter"] and fm["filter"] != "none"),
                  str(fm))
            page.evaluate("() => applyFocusMode && applyFocusMode(false)")
            page.wait_for_timeout(400)

            # ---- 6. migrated surfaces still have reachable homes ---------
            # Stash & Notes lens (P13-A), premise view (P13-B), floats (P13-C)
            page.locator("#right-edge-affordance").click()
            page.wait_for_timeout(500)
            page.locator("#dock-tab-notes").click()
            page.wait_for_timeout(500)
            check("Stash & Notes lens opens on the dock",
                  page.locator('.dock-lens[data-lens="notes"]').is_visible())
            check("stash list container present",
                  page.locator("#stash-list").count() > 0)
            page.locator("#dock-note-input").fill("P13 parity note")
            page.locator("#dock-note-form button[type=submit]").click()
            page.wait_for_timeout(700)
            check("note posts into the dock rail",
                  page.locator("#rail-notes .rail-note").count() > 0,
                  f"notes={page.locator('#rail-notes .rail-note').count()}")
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)

            # premise: the card is a full-screen view now (was a dead-end pane)
            page.evaluate("() => togglePremisePane()")
            page.wait_for_timeout(700)
            pv = probe(page, "#premise-view")
            check("premise view opens as a full-screen view",
                  bool(pv and pv["visible"]), str(pv))
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)

            # selection floats live on the manuscript workspace (P13-C)
            shown = page.evaluate(
                """() => {
        const line = document.querySelector('#manuscript-container [class^=el-]');
        if (!line) return null;
        const r = document.createRange();
        r.selectNodeContents(line);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(r);
        line.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, clientX: 300, clientY: 300 }));
        return true;
    }""")
            page.wait_for_timeout(500)
            fl = probe(page, "#quote-float")
            check("selection float shows on the live workspace",
                  bool(shown and fl and fl["visible"]), str(fl))

            # ---- 7. no JS errors across the whole flow -------------------
            assert_no_js_errors(checks, errors)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    main()
