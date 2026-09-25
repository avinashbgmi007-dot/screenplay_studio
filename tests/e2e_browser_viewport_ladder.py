"""e2e_browser_viewport_ladder.py — the shell holds at the viewports nothing ran.

UX-2 (round-3 audit 2026-09-25): the shared `launch()` helper hardcodes
**1440x900** and only 6 of 49 suites override it, so the fleet exercised exactly
one viewport. `phase11_responsive` covers the **width** ladder well (1440 / 1024 /
390, with real assertions about the scene index, the dock, touch targets and the
overlays). The gaps it named are a different axis:

  * **no short viewport** — a 1366x768 laptop or 1440x720, the shapes most likely
    to clip the status strip or the manuscript's vertical rhythm;
  * **no touch emulation** — `set_viewport_size` changes the viewport but NOT
    `has_touch` / `is_mobile`, which are CONTEXT options. So no suite ever ran
    with a real touch capability, and the SPA can take a different path when
    `ontouchstart` exists. Each config below therefore gets its own context;
  * **no mobile landscape** (844x390), where height is the scarce dimension.

**Measured before this suite was written:** there is no defect here. Every config
reports zero horizontal overflow, the manuscript keeps >=50% of the viewport (the
rule UI_UX_SPECIFICATION §3.2 states), the status strip is never clipped, and an
OPEN dock or drawer keeps its own close button inside the viewport. So this is
coverage, not a fix — the suite exists so a future layout change that breaks any
of it fails here instead of in front of a writer.

Two non-vacuity guards, because this shape of suite passes trivially otherwise:
every config asserts the manuscript actually RENDERED (a blank page has no
overflow), and the touch configs assert the emulation really took.

Run:  python tests/e2e_browser_viewport_ladder.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests  # noqa: E402
from e2e_browser_common import (  # noqa: E402
    Checks,
    assert_no_js_errors,
    launch,
    open_studio,
    studio_headers,
)
from playwright.sync_api import sync_playwright  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

# (label, width, height, touch) — the baseline first as the control, then the
# three shapes the audit named as never having run.
CONFIGS = [
    ("1440x900 baseline", 1440, 900, False),
    ("1366x768 short laptop", 1366, 768, False),
    ("1440x720 short", 1440, 720, False),
    ("844x390 mobile landscape", 844, 390, True),
    ("390x844 mobile portrait", 390, 844, True),
]

MIN_MANUSCRIPT_FRACTION = 0.5   # UI_UX_SPECIFICATION §3.2
MIN_MANUSCRIPT_PX = 120         # a page column shorter than this is not readable
MIN_TOUCH_TARGET_PX = 44        # the spec's touch-target minimum

MEASURE = """() => {
  const de = document.documentElement;
  const rect = (id) => {
    const el = document.getElementById(id);
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return {w: Math.round(b.width), h: Math.round(b.height),
            left: Math.round(b.left), right: Math.round(b.right),
            top: Math.round(b.top), bottom: Math.round(b.bottom)};
  };
  const dock = document.getElementById('context-dock');
  const drawer = document.getElementById('room-drawer');
  const mc = document.getElementById('manuscript-container');
  const rows = document.querySelectorAll('.scene-index-item');
  return {
    vw: de.clientWidth, vh: de.clientHeight,
    hOverflow: de.scrollWidth - de.clientWidth,
    manuscript: rect('manuscript-container'),
    statusStrip: rect('status-strip'),
    sceneIndex: rect('scene-index'),
    dock: rect('context-dock'),
    dockOpen: !!dock && dock.classList.contains('open'),
    dockClose: rect('dock-close'),
    drawer: rect('room-drawer'),
    drawerOpen: !!drawer && drawer.classList.contains('open'),
    drawerClose: rect('drawer-close'),
    renderedPages: mc ? mc.querySelectorAll('.scene-page').length : 0,
    sceneRowHeight: rows.length ? Math.round(rows[0].getBoundingClientRect().height) : 0,
    maxTouchPoints: navigator.maxTouchPoints || 0,
  };
}"""


def _inside(box, vw, vh):
    """Is the box fully within the viewport? A control you cannot reach is not a
    control."""
    if not box:
        return False
    return (box["left"] >= -1 and box["right"] <= vw + 1
            and box["top"] >= -1 and box["bottom"] <= vh + 1)


def _settle(page, ms=20000):
    try:
        page.wait_for_function(
            "() => document.querySelectorAll('#manuscript-container .scene-page')"
            ".length > 0", timeout=ms)
        return True
    except Exception:
        return False


def main():
    checks = Checks()
    check = checks.ok

    with open_studio() as base:
        with sync_playwright() as pw:
            browser, _page, errors = launch(pw)
            seeded = requests.post(f"{base}/api/sample",
                                   headers=studio_headers(base), timeout=60)
            assert seeded.status_code in (200, 201), seeded.text
            project = seeded.json()["project"]

            for label, w, h, touch in CONFIGS:
                # A context per config: `has_touch` / `is_mobile` are context
                # options, so `set_viewport_size` alone cannot emulate a touch
                # device — which is exactly the gap this suite closes.
                ctx = browser.new_context(viewport={"width": w, "height": h},
                                          has_touch=touch, is_mobile=touch)
                page = ctx.new_page()
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on("dialog", lambda d: d.accept())
                try:
                    page.goto(base)
                    page.wait_for_load_state("networkidle")
                    page.evaluate("async (p) => { await openProject(p); }", project)
                    if not _settle(page):
                        check(f"{label}: the manuscript rendered (precondition)",
                              False, "no .scene-page appeared")
                        continue
                    page.wait_for_timeout(350)
                    m = page.evaluate(MEASURE)
                    ms, ss = m["manuscript"], m["statusStrip"]

                    # --- non-vacuity ------------------------------------------
                    check(f"{label}: the manuscript rendered (precondition)",
                          m["renderedPages"] > 0 and ms["w"] > 0 and ms["h"] > 0,
                          json.dumps({"pages": m["renderedPages"], "box": ms}))
                    if touch:
                        check(f"{label}: the touch emulation is real (precondition)",
                              m["maxTouchPoints"] > 0,
                              f"maxTouchPoints={m['maxTouchPoints']}")

                    # --- the layout invariants --------------------------------
                    check(f"{label}: no horizontal overflow",
                          m["hOverflow"] <= 0, f"{m['hOverflow']}px past the viewport")
                    check(f"{label}: the manuscript keeps "
                          f"{int(MIN_MANUSCRIPT_FRACTION * 100)}% of the desk",
                          ms["w"] >= m["vw"] * MIN_MANUSCRIPT_FRACTION,
                          json.dumps({"manuscript": ms["w"], "viewport": m["vw"]}))
                    check(f"{label}: the manuscript column is tall enough to read",
                          ms["h"] >= MIN_MANUSCRIPT_PX, f"{ms['h']}px")
                    check(f"{label}: the status strip is not clipped off the bottom",
                          _inside(ss, m["vw"], m["vh"]),
                          json.dumps({"strip": ss, "vh": m["vh"]}))

                    # --- the panels, OPEN -------------------------------------
                    page.evaluate("() => { const e = document.getElementById("
                                  "'right-edge-affordance'); if (e) e.click(); }")
                    page.wait_for_timeout(450)
                    opened = page.evaluate(MEASURE)
                    check(f"{label}: the dock opens", opened["dockOpen"],
                          json.dumps({"dock": opened["dock"]}))
                    check(f"{label}: an open dock keeps its close button in reach",
                          _inside(opened["dockClose"], opened["vw"], opened["vh"]),
                          json.dumps({"close": opened["dockClose"], "vw": opened["vw"]}))
                    check(f"{label}: an open dock does not push the page below the floor",
                          opened["manuscript"]["w"] >= opened["vw"] * MIN_MANUSCRIPT_FRACTION,
                          json.dumps({"manuscript": opened["manuscript"]["w"],
                                      "viewport": opened["vw"]}))

                    page.evaluate("() => { if (typeof openRoomDrawer === 'function') "
                                  "openRoomDrawer(); }")
                    page.wait_for_timeout(450)
                    drawn = page.evaluate(MEASURE)
                    check(f"{label}: the partner drawer opens", drawn["drawerOpen"],
                          json.dumps({"drawer": drawn["drawer"]}))
                    check(f"{label}: an open drawer keeps its close button in reach",
                          _inside(drawn["drawerClose"], drawn["vw"], drawn["vh"]),
                          json.dumps({"close": drawn["drawerClose"], "vw": drawn["vw"]}))

                    if touch:
                        check(f"{label}: scene-index rows meet the "
                              f"{MIN_TOUCH_TARGET_PX}px touch target",
                              m["sceneRowHeight"] >= MIN_TOUCH_TARGET_PX,
                              f"{m['sceneRowHeight']}px")
                finally:
                    ctx.close()

            assert_no_js_errors(checks, errors)
            browser.close()

    checks.finish()


if __name__ == "__main__":
    main()
