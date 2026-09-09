"""e2e_browser_phase11_responsive.py — Phase 11 gate: the responsive
system recomposes (not shrinks) across desktop / tablet / mobile.

MD §12 contract:
  Tablet (~768-1199): compact scene index, manuscript primary, dock overlay.
  Mobile (<768): manuscript full-width, scene index sheet/overlay, Context
    Dock bottom sheet, structural tools fill viewport, touch targets >= 44px.
  Gate: test desktop + tablet + mobile critical flows.

Run:  python tests/e2e_browser_phase11_responsive.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from e2e_browser_common import Checks, launch, open_studio, assert_no_js_errors  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok


def main():
    with open_studio() as base:
        with sync_playwright() as pw:
            browser, page, errors = launch(pw)

            name = None
            with open(FIXTURE, "rb") as f:
                r = requests.post(f"{base}/api/projects",
                                  files={"file": ("P11 Gate.fountain", f, "text/plain")},
                                  data={"title": "P11 Gate"}, timeout=60)
            name = r.json()["project"]

            # ==================== DESKTOP (1440) ====================
            page.goto(base)
            page.wait_for_load_state("networkidle")
            page.evaluate("async (n) => { await openProject(n); }", name)
            page.wait_for_timeout(1800)
            d = page.evaluate("""() => {
                const si = document.getElementById('scene-index');
                const mc = document.getElementById('manuscript-container');
                const r = mc.getBoundingClientRect();
                return {
                    vw: window.innerWidth,
                    indexW: Math.round(si.getBoundingClientRect().width),
                    indexPos: getComputedStyle(si).position,
                    manusW: Math.round(r.width),
                };
            }""")
            check("desktop: scene index is the in-flow 44px strip",
                  d["vw"] >= 1200 and d["indexW"] == 44 and d["indexPos"] == "absolute",
                  json.dumps(d))
            # dock is the in-flow sibling
            page.evaluate("() => openDock('evidence')")
            page.wait_for_timeout(500)
            dd = page.evaluate("""() => {
                const dock = document.getElementById('context-dock');
                const r = dock.getBoundingClientRect();
                const mc = document.getElementById('manuscript-container').getBoundingClientRect();
                return {pos: getComputedStyle(dock).position, w: Math.round(r.width),
                        manusKept: mc.width >= (window.innerWidth * 0.5)};
            }""")
            check("desktop: dock is the in-flow sibling (manuscript keeps >=50%)",
                  dd["pos"] != "fixed" and dd["manusKept"], json.dumps(dd))
            page.evaluate("() => closeDock()")

            # ==================== TABLET (1024) ====================
            page.set_viewport_size({"width": 1024, "height": 768})
            page.wait_for_timeout(400)
            t = page.evaluate("""() => {
                const si = document.getElementById('scene-index');
                const mc = document.getElementById('manuscript-container');
                const r = mc.getBoundingClientRect();
                return {
                    vw: window.innerWidth,
                    indexW: Math.round(si.getBoundingClientRect().width),
                    manusW: Math.round(r.width),
                    manusPrimary: r.width >= (window.innerWidth * 0.55),
                };
            }""")
            check("tablet: compact scene index (40px), manuscript primary",
                  768 <= t["vw"] <= 1199 and t["indexW"] == 40 and t["manusPrimary"],
                  json.dumps(t))
            # dock becomes the right overlay
            page.evaluate("() => openDock('evidence')")
            page.wait_for_timeout(500)
            td = page.evaluate("""() => {
                const dock = document.getElementById('context-dock');
                const r = dock.getBoundingClientRect();
                return {pos: getComputedStyle(dock).position, right: Math.round(window.innerWidth - r.right),
                        w: Math.round(r.width)};
            }""")
            check("tablet: dock becomes the right overlay (fixed, flush right)",
                  td["pos"] == "fixed" and td["right"] == 0 and td["w"] > 0, json.dumps(td))
            page.evaluate("() => closeDock()")

            # ==================== MOBILE (390) ====================
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(400)
            m = page.evaluate("""() => {
                const si = document.getElementById('scene-index');
                const mc = document.getElementById('manuscript-container');
                const r = mc.getBoundingClientRect();
                const items = document.querySelectorAll('.scene-index-item');
                const toggle = document.getElementById('scene-index-toggle');
                const tr = toggle.getBoundingClientRect();
                return {
                    vw: window.innerWidth,
                    indexPos: getComputedStyle(si).position,
                    indexW: Math.round(si.getBoundingClientRect().width),
                    handleW: Math.round(tr.width),
                    manusW: Math.round(r.width),
                    manusFull: r.width >= (window.innerWidth - 2),  // full-width minus index handle
                    itemH: items.length ? Math.round(items[0].getBoundingClientRect().height) : 0,
                    toggleH: Math.round(tr.height),
                    hOverflow: document.documentElement.scrollWidth > window.innerWidth,
                };
            }""")
            check("mobile: scene index is the 44px handle of an overlay sheet",
                  m["indexPos"] == "fixed" and m["handleW"] == 44 and m["indexW"] == 44,
                  json.dumps(m))
            check("mobile: manuscript fills the viewport beside the handle",
                  m["manusFull"] and not m["hOverflow"], json.dumps(m))
            check("mobile: touch targets >= 44px (index rows + toggle)",
                  m["itemH"] >= 44 and m["toggleH"] >= 44, json.dumps(m))

            # the sheet opens (overlay) and dismisses (✕ + outside tap)
            page.evaluate("() => document.getElementById('scene-index-toggle').click()")
            page.wait_for_timeout(500)
            so = page.evaluate("""() => {
                const si = document.getElementById('scene-index');
                return {w: Math.round(si.getBoundingClientRect().width),
                        glyph: document.getElementById('scene-index-toggle').textContent.trim(),
                        overlay: si.getBoundingClientRect().width > 44};
            }""")
            check("mobile: toggle opens the scene sheet as overlay (glyph -> ✕)",
                  so["overlay"] and so["glyph"] == "✕", json.dumps(so))
            # outside tap (on the manuscript) closes it
            page.evaluate("""() => {
                const mc = document.getElementById('manuscript-container');
                mc.dispatchEvent(new MouseEvent('click', {bubbles: true}));
            }""")
            page.wait_for_timeout(400)
            sc = page.evaluate("""() => {
                const si = document.getElementById('scene-index');
                return {w: Math.round(si.getBoundingClientRect().width),
                        glyph: document.getElementById('scene-index-toggle').textContent.trim()};
            }""")
            check("mobile: outside tap closes the sheet (glyph -> ☰)",
                  sc["w"] == 44 and sc["glyph"] == "☰", json.dumps(sc))

            # dock = bottom sheet
            page.evaluate("() => openDock('evidence')")
            page.wait_for_timeout(600)
            md = page.evaluate("""() => {
                const dock = document.getElementById('context-dock');
                const r = dock.getBoundingClientRect();
                return {pos: getComputedStyle(dock).position, w: Math.round(r.width),
                        bottom: Math.round(r.bottom), vw: window.innerWidth,
                        h: Math.round(r.height)};
            }""")
            check("mobile: Context Dock is the bottom sheet (full width, flush bottom)",
                  md["pos"] == "fixed" and md["w"] == md["vw"] and md["bottom"] == 844,
                  json.dumps(md))
            page.evaluate("() => closeDock()")

            # structural tools fill the viewport
            page.evaluate("() => openBeatboardView()")
            page.wait_for_timeout(800)
            bb = page.evaluate("""() => {
                const board = document.querySelector('.beatboard-board');
                const card = document.querySelector('#beatboard-view .bb-card');
                const move = document.querySelector('#beatboard-view .bb-move');
                return {
                    boardW: Math.round(board.getBoundingClientRect().width),
                    cardW: Math.round(card.getBoundingClientRect().width),
                    moveH: move ? Math.round(move.getBoundingClientRect().height) : 0,
                    fills: Math.abs(board.getBoundingClientRect().width - window.innerWidth) <= 2,
                    hOverflow: document.documentElement.scrollWidth > window.innerWidth,
                };
            }""")
            check("mobile: Beat Board fills the viewport, 1-column cards",
                  bb["fills"] and not bb["hOverflow"] and bb["cardW"] < 390, json.dumps(bb))
            check("mobile: bb move buttons meet 44px",
                  bb["moveH"] >= 44, json.dumps(bb))
            page.evaluate("() => closeBeatboardView()")

            page.evaluate("() => openRevisionView()")
            page.wait_for_timeout(900)
            rv = page.evaluate("""() => {
                const body = document.querySelector('.revision-body');
                const nav = document.querySelector('.revision-nav');
                const script = document.querySelector('.revision-script');
                const row = document.querySelector('.revision-nav-row');
                return {
                    stacked: getComputedStyle(body).flexDirection === 'column',
                    navW: Math.round(nav.getBoundingClientRect().width),
                    scriptBelow: script.getBoundingClientRect().top >= nav.getBoundingClientRect().bottom - 1,
                    rowH: row ? Math.round(row.getBoundingClientRect().height) : 0,
                    fills: Math.abs(nav.getBoundingClientRect().width - window.innerWidth) <= 2,
                    hOverflow: document.documentElement.scrollWidth > window.innerWidth,
                };
            }""")
            check("mobile: Revision desk stacks (nav strip -> pages -> findings)",
                  rv["stacked"] and rv["scriptBelow"] and rv["fills"] and not rv["hOverflow"],
                  json.dumps(rv))
            check("mobile: revision nav rows meet 44px", rv["rowH"] >= 44, json.dumps(rv))
            page.evaluate("() => closeRevisionView()")

            # a real compare needs a second draft (working copy != snapshot)
            with open(FIXTURE, "rb") as f:
                text = f.read().decode("utf-8")
            text2 = text.replace("EXT/INT. HOSPITAL - NIGHT", "EXT. HOSPITAL ENTRANCE - NIGHT", 1)
            r2 = requests.post(f"{base}/api/projects/{name}/drafts",
                               files={"file": ("second.fountain", text2.encode("utf-8"), "text/plain")},
                               timeout=60)
            assert r2.status_code in (200, 201), r2.text

            page.evaluate("() => openCompareView()")
            page.wait_for_timeout(800)
            cm = page.evaluate("""() => {
                const pane = document.querySelector('.compare-panes');
                const cols = document.querySelector('.cmp-columns');
                return {
                    fills: Math.abs(pane.getBoundingClientRect().width - window.innerWidth) <= 2,
                    singleCol: cols ? getComputedStyle(cols).gridTemplateColumns.split(' ').length === 1 : null,
                    hOverflow: document.documentElement.scrollWidth > window.innerWidth,
                };
            }""")
            check("mobile: Compare fills the viewport, single column",
                  cm["fills"] and cm["singleCol"] and not cm["hOverflow"], json.dumps(cm))
            page.evaluate("() => closeCompareView()")

            # ---- desktop regression: resize back, in-flow dock returns ----
            page.set_viewport_size({"width": 1440, "height": 900})
            page.wait_for_timeout(400)
            back = page.evaluate("""() => {
                const si = document.getElementById('scene-index');
                return {indexW: Math.round(si.getBoundingClientRect().width), vw: window.innerWidth};
            }""")
            check("resize back: desktop strip restored (no stuck mobile state)",
                  back["indexW"] == 44 and back["vw"] == 1440, json.dumps(back))

            requests.delete(f"{base}/api/projects/{name}", timeout=30)
            assert_no_js_errors(checks, errors)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    main()
