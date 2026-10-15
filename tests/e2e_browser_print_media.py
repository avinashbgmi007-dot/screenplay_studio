#!/usr/bin/env python3
"""Print media must show the draft as clean paper, and nothing else.

**The regression this exists for (Track A, found 2026-10-15).** The section 3
edit removed the `.gutter` selector from the `@media print` hide list and took
the list's shared `{ display: none !important; }` block with it. What remained
was a dangling selector list, which is valid CSS: ~25 chrome selectors merged
into the following rule and absorbed `display: block !important` from
`#manuscript-workspace`.

The result was that printing a screenplay put the sidebar, both toolbars, the
project bar, the composer and every modal on top of the script.

**Why this file exists at all.** That regression survived four rounds of
review, including three after it was broken. `style.css` balanced at 1451/1451
and `node --check` passed on the destroyed stylesheet. The source-level guard
in `test_css_selector_list_integrity.py` catches the shape of it, and
`test_spa_contract.py` counts the `@media print` rules — but both are static,
and nothing in the corpus rendered print media until this suite.

Proven non-vacuous by a failing-then-passing pair, run against the real
commits: on `6510e2f` (broken) 10 chrome elements were visible and the
manuscript was crushed to 187px; on `c28cb50` (fixed) every chrome element is
hidden and the manuscript renders at 1438x898.

Run: `python tests/e2e_browser_print_media.py`
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e2e_browser_common import Checks, launch, open_studio, assert_no_js_errors  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

CHECKS = Checks()

# The chrome that must not reach the paper. Sourced from the `@media print`
# hide list in style.css, minus `.gutter` (deleted in Track A section 3).
# If someone adds a selector to that list, add it here too, or this suite
# silently stops covering it.
PRINT_CHROME = [
    "#sidebar", "#error-banner", "#welcome-view", "#beatboard-view",
    "#compare-view", "#palette-modal", "#settings-modal", "#rewrite-modal",
    "#desk-toolbar", "#draft-bar", "#diff-banner", "#composer", ".note-add",
    ".finding-note-actions", "#project-bar", "#room-chip", "#partner-card",
    "#feedback-tabs", ".note-mine-actions", "#print-btn", "#undo-btn",
    "#redo-btn", "#reset-edits-btn", "#cowrite-panel", "#feedback-panel",
    "#status-strip", ".drawer", ".desk", "#context-dock",
    "#right-edge-affordance", "#scene-index",
]

# The paper. This is the one thing print must SHOW.
PRINT_PAPER = "#manuscript-workspace"


# Computed display plus a real box for one selector under print media.
# `display: none` elements legitimately report a zero box, so the check is on
# `display` — but the box is reported anyway, because it is what makes the
# "manuscript crushed to 187px" failure legible.
_JS = """(sel) => {
  const els = [...document.querySelectorAll(sel)];
  if (!els.length) return {present: false, display: null, box: null,
                           hidden: [], shown: []};
  const hidden = [], shown = [];
  for (const el of els) {
    const cs = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    const isHidden = cs.display === 'none' || box.height === 0 || box.width === 0;
    (isHidden ? hidden : shown).push(el.id || el.className || el.tagName);
  }
  return {present: true,
          display: getComputedStyle(els[0]).display,
          box: Math.round(els[0].getBoundingClientRect().width) + 'x'
               + Math.round(els[0].getBoundingClientRect().height),
          hidden, shown};
}"""


def main():
    with open_studio() as base:
        with sync_playwright() as pw:
            browser, page, errors = launch(pw)
            page.goto(base + "/", wait_until="networkidle")
            page.wait_for_timeout(600)

            # ---- 0. the screen state is the control ------------------------
            # Emulating print without ever having seen the screen state leaves
            # "everything is hidden" indistinguishable from "print is correct".
            # Assert the chrome IS visible first, so a PASS below means print
            # suppressed it, not that it was never there.
            page.emulate_media(media="screen")
            page.wait_for_timeout(200)
            CHECKS.ok("control: the sidebar is visible on screen",
                      page.locator("#sidebar").is_visible())
            CHECKS.ok("control: the manuscript is visible on screen",
                      page.locator(PRINT_PAPER).is_visible())

            # ---- 1. print media ---------------------------------------------
            page.emulate_media(media="print")
            page.wait_for_timeout(400)

            visible_chrome = []
            for sel in PRINT_CHROME:
                # Only probe selectors that are actually on screen; the point
                # is that print removes what the screen showed.
                if page.locator(sel).count() == 0:
                    continue
                detail = page.evaluate(_JS, sel)
                if detail["shown"]:
                    visible_chrome.append((sel, detail["shown"]))

            CHECKS.ok(
                f"print hides all {len(PRINT_CHROME)} chrome selectors",
                not visible_chrome,
                "still visible under print media: "
                + "; ".join(f"{s} -> {v}" for s, v in visible_chrome))

            paper = page.evaluate(_JS, PRINT_PAPER)
            CHECKS.ok("print shows the manuscript workspace",
                      paper.get("present") and paper.get("display") != "none",
                      str(paper))

            # A manuscript crushed to a sliver is the specific symptom of the
            # broken build: the chrome absorbed `display: block` and crowded it
            # out. A bare "not display:none" would pass on a 187px box.
            box_w = paper.get("box", "").split("x")[0]
            CHECKS.ok("print gives the manuscript the page width (not crushed)",
                      int(box_w) > 1000 if box_w.isdigit() else False,
                      f"manuscript box {paper.get('box')} (broken build renders 187x)")

            assert_no_js_errors(CHECKS, errors)
            CHECKS.finish()


if __name__ == "__main__":
    main()