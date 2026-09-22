"""Phase 13 — Legacy cleanup: parity + dead-code gate.

Proves the migration's end state: ONE presentation architecture.

  * the legacy surfaces are GONE (markup, class, and renderer):
    #script-scenes, #script-toolbar / .script-toolbar, .premise-pane,
    renderScriptView(), and the getManuscriptContainer() fallback
  * every migrated control still has a reachable home:
    #desk-toolbar (finding chips, search), #premise-view, the Stash &
    Notes dock lens, the selection floats
  * the Problem Board is RETIRED (P0.2). This suite used to prove its
    visibility/geometry; the board graduated into the Evidence dock, so the
    gate here is its absence: no markup, no edge tab, no helpers.
  * mode rules point at the LIVE row: spotlight hides the desk toolbar
    (focus mode dims it — filter, still visible)

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

            # ---- 3. Problem Board RETIRED (P0.2) — the gate is its absence --
            # Seed findings onto state — no model needed (the real analysis
            # path is the phase 8 gate's job). Section 3b below still renders
            # margin pins from these; the board that used to read them is gone.
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
            check("P0.2: the Problem Board is gone from the DOM",
                  page.locator("#problem-board").count() == 0)
            check("P0.2: its edge tab is gone",
                  page.locator("#pb-edge-tab").count() == 0)
            check("P0.2: its helpers are gone from the page scope",
                  page.evaluate(
                      "() => typeof toggleProblemBoard === 'undefined'"
                      " && typeof renderProblemBoard === 'undefined'"
                      " && typeof collapseProblemBoard === 'undefined'"))

            # the dock's "Context" affordance must stay hittable now that no
            # board tab shares the row's right edge (the old conflict is moot;
            # this is the surviving half of that check)
            reach = page.evaluate(
                """() => {
        const a = document.getElementById('right-edge-affordance').getBoundingClientRect();
        const hit = document.elementFromPoint(a.left + a.width / 2, a.top + a.height / 2);
        return { hit: hit && (hit.id || hit.className), w: Math.round(a.width) };
    }""")
            check("the Context affordance owns its edge (no board tab fights it)",
                  reach["hit"] == "right-edge-affordance", str(reach))

            # the dock still opens beside the page (the board used to bow to it;
            # with the board retired this is the surviving sanity check)
            page.evaluate("() => openDock('evidence')")
            page.wait_for_timeout(700)
            check("dock opens on the Evidence lens",
                  bool(page.evaluate(
                      "() => document.getElementById('context-dock')"
                      ".classList.contains('open')")))
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)

            # ---- 3b. R6: the margin pins (occlusion + recession contract) --
            # The same findings, rendered into the manuscript this time. Two
            # laws came out of the UI walk: the margin NEVER covers the script
            # (it used to overlap 164px of every line it sat on), and a margin
            # pin POINTS at a finding instead of being a fourth place to judge
            # it (Locate only — Rewrite/Discuss live in the dock).
            # the scroll position is preserved across the re-render on purpose:
            # the margin walk reads geometry, and a reset-to-top would re-measure
            # mid-suite against a different viewport slice.
            page.evaluate(
                """() => {
        const mc = document.getElementById('manuscript-container');
        const top = mc.scrollTop;
        renderManuscript(mc);
        mc.scrollTop = top;
    }""")
            page.wait_for_timeout(700)
            check("R6: the margin renders a pin per finding on its scene",
                  page.locator(".scene-notes .finding-note").count() == 3,
                  f"pins={page.locator('.scene-notes .finding-note').count()}")

            MARGIN_GEOM = """() => {
        const out = {pins: 0, overlapping: 0, worst: 0, position: null,
                     pin_left: null, page_right: null};
        for (const m of document.querySelectorAll('.scene-notes')) {
          const pg = m.closest('.scene-page');
          const lines = [...pg.querySelectorAll('[class^=el-]')]
            .map(e => e.getBoundingClientRect()).filter(r => r.width > 0);
          if (out.position === null) out.position = getComputedStyle(m).position;
          for (const pin of m.querySelectorAll('.finding-note')) {
            out.pins += 1;
            const p = pin.getBoundingClientRect(), pr = pg.getBoundingClientRect();
            out.pin_left = Math.round(p.left);
            out.page_right = Math.round(pr.right);
            let overlap = 0;
            for (const r of lines) {
              if (Math.min(p.right, r.right) - Math.max(p.left, r.left) > 0
                  && Math.min(p.bottom, r.bottom) - Math.max(p.top, r.top) > 0)
                overlap = Math.max(overlap,
                                   Math.min(p.right, r.right) - Math.max(p.left, r.left));
            }
            if (overlap > 0) {
              out.overlapping += 1;
              out.worst = Math.max(out.worst, Math.round(overlap));
            }
          }
        }
        return out;
    }"""
            flow = page.evaluate(MARGIN_GEOM)
            check("R6: no margin pin covers a line of script (pins in the "
                  "page's flow)",
                  bool(flow["pins"] and flow["overlapping"] == 0), str(flow))

            LABELS = """() => {
        const labels = el => el ? [...el.querySelectorAll(
            '.finding-note-actions button')].map(b => b.textContent.trim()) : [];
        const has = (list, word) => list.some(t => t.includes(word));
        const of = (list, word) => list.filter(t => t.includes(word)).length;
        const pin = labels(document.querySelector('.scene-notes .finding-note'));
        return { pin,
                 pin_has: { Locate: has(pin, 'Locate'), Rewrite: has(pin, 'Rewrite'),
                            Discuss: has(pin, 'Discuss') } };
    }"""
            actions = page.evaluate(LABELS)
            check("R6: a margin pin points (Locate) but carries no judgment controls",
                  bool(actions["pin_has"]["Locate"] and not actions["pin_has"]["Rewrite"]
                       and not actions["pin_has"]["Discuss"]), str(actions))
            # (the other half of that contract — that Rewrite/Discuss still have
            # a home — is asserted where they live: phase6's dock evidence lens
            # walks Locate + Discuss on the deep cards from a REAL analysis. The
            # dock needs state.report, which this suite does not seed.)

            # the margin walks straight into its final state — the board's
            # overlay that used to force a collapse/expand dance is retired
            gutter = page.evaluate(MARGIN_GEOM)
            check("R6: the pins take the paper's gutter (no board overlay)",
                  bool(gutter["position"] == "absolute"
                       and gutter["pin_left"] >= gutter["page_right"]), str(gutter))
            check("R6: the gutter column clears the paper (still zero overlap)",
                  bool(gutter["overlapping"] == 0), str(gutter))

            # ---- 4. mode swaps: spotlight hides the NEW toolbar row -------
            page.evaluate("() => toggleSpotlight()")
            page.wait_for_timeout(600)
            st = probe(page, "#desk-toolbar")
            check("spotlight hides the desk toolbar",
                  bool(st and not st["visible"]), str(st))
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
