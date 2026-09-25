"""e2e_browser_render_scale.py — UX-2 (audit 2026-09-24): the desk on a HiDPI screen.

No suite in the gate had ever set `deviceScaleFactor`; every viewport sweep ran at
DPR 1 (1440/1280/1024/1000/480/390 px). A 2x display is the ordinary case on the
laptops this desk is used on, and it was the one rendering variable nothing
watched.

What is asserted is LAYOUT INVARIANCE, not "it looks fine at 2x": the same
document metrics at DPR 1 and DPR 2. That is a real invariant — the CSS pixel is
defined independently of the device pixel ratio — and it is the one a
scale-dependent mistake (a hard-coded devicePixelRatio, a canvas sized in device
pixels, a hit area measured in device pixels) would break. The DPR reading is
checked too, so the comparison cannot pass by the emulation silently not applying.

Deliberately NOT asserted here: "text must resize to 200%". The type scale is px
by an explicit product decision (style.css `:root`; user call 2026-09-12 — "keep
13px script body; v2.1's 16px declined"), so the app does not follow the browser's
default font size, and WCAG 1.4.4 is met through browser zoom, which is how the
resize is actually performed. A test asserting that text scales would be
asserting against the design, and a test asserting nothing would be the vacuous
shape this repo forbids. The reasoning is recorded in
docs/audit/implementation_2026-09-24.md instead.

Run:  python tests/e2e_browser_render_scale.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests  # noqa: E402
from e2e_browser_common import studio_headers, Checks, launch, open_studio, assert_no_js_errors  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

checks = Checks()
check = checks.ok

# Everything a scale-dependent bug would move. Read in one round trip so the
# numbers belong to the same frame.
METRICS = """() => {
  const de = document.documentElement;
  const c = document.getElementById('manuscript-container');
  const page = document.querySelector('.scene-page');
  const btn = document.getElementById('room-cowrite-btn');
  const body = document.body;
  return {
    dpr: window.devicePixelRatio,
    docOverflow: de.scrollWidth - de.clientWidth,
    scenes: document.querySelectorAll('.scene-page').length,
    bodyFontSize: getComputedStyle(body).fontSize,
    lineHeight: page ? getComputedStyle(page).lineHeight : null,
    sceneWidth: page ? Math.round(page.getBoundingClientRect().width) : null,
    buttonHeight: btn ? Math.round(btn.getBoundingClientRect().height) : null,
    paneHeight: c ? Math.round(c.getBoundingClientRect().height) : null,
  };
}"""


def metrics(page):
    return page.evaluate(METRICS)


def main():
    with open_studio() as base:
        r = requests.post(f"{base}/api/sample", headers=studio_headers(base), timeout=60)
        assert r.status_code in (200, 201), r.text
        project = r.json()["project"]

        with sync_playwright() as pw:
            # ---------- DPR 1: the baseline ----------
            browser, page, errors = launch(pw)
            page.goto(base)
            page.wait_for_load_state("networkidle")
            page.evaluate("async (p) => { await openProject(p); }", project)
            page.wait_for_timeout(1500)
            one = metrics(page)
            check("the baseline really is DPR 1 (precondition)",
                  one["dpr"] == 1 and one["scenes"] > 0, json.dumps(one))
            check("the baseline has no horizontal overflow of the document (precondition)",
                  one["docOverflow"] <= 0, json.dumps(one))
            browser.close()

            # ---------- DPR 2: the same document, twice the pixels ----------
            browser2, page2, errors2 = launch(pw, device_scale_factor=2)
            page2.goto(base)
            page2.wait_for_load_state("networkidle")
            page2.evaluate("async (p) => { await openProject(p); }", project)
            page2.wait_for_timeout(1500)
            two = metrics(page2)
            check("the emulation actually applied (precondition — otherwise this compares DPR 1 to itself)",
                  two["dpr"] == 2, json.dumps(two))

            for key in ("docOverflow", "scenes", "bodyFontSize", "lineHeight",
                        "sceneWidth", "paneHeight"):
                check(f"a HiDPI screen does not change the {key}",
                      two[key] == one[key],
                      json.dumps({"dpr1": one[key], "dpr2": two[key]}))

            # A hit target is measured in CSS pixels; if any control were sized
            # from device pixels it would halve on a 2x screen and this would say so.
            check("a control's hit area is the same size on a 2x screen",
                  two["buttonHeight"] == one["buttonHeight"] and two["buttonHeight"] >= 20,
                  json.dumps({"dpr1": one["buttonHeight"], "dpr2": two["buttonHeight"]}))

            # ...and the desk still works there, not merely renders.
            page2.evaluate("() => openBeatboardView()")
            page2.wait_for_timeout(1400)
            check("the desk is still operable at 2x",
                  page2.evaluate("() => document.getElementById('beatboard-view').style.display !== 'none'"),
                  "the Beat Board did not open at DPR 2")

            assert_no_js_errors(checks, errors)
            assert_no_js_errors(checks, errors2, name="no JS page errors at DPR 2")
            browser2.close()

    checks.finish()


if __name__ == "__main__":
    main()
