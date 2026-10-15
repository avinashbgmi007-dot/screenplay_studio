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


def _dims(detail: dict):
    """(width, height) from a probe detail's '1438x898' box string."""
    box = str(detail.get("box") or "")
    parts = box.split("x")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return 0, 0
    return int(parts[0]), int(parts[1])


def _wait_for_project_open(page):
    """Open the sample page and wait for the desk to actually be there.

    Two waits, not one. `openProject` flips the title and reveals `.workspace`
    in the same tick, but the async load can settle either order — smoke.py
    learned this the hard way, when a title-only wait passed on a stale
    placeholder.
    """
    page.locator("#sample-btn").click()
    try:
        page.wait_for_function(
            """() => {
                 const t = document.getElementById('project-title');
                 if (!t) return false;
                 const s = (t.textContent || '').trim();
                 return s.length > 0 && s !== '\u2014';
               }""",
            timeout=30000)
        page.wait_for_selector(".workspace", state="visible", timeout=30000)
    except Exception as exc:  # noqa: BLE001 - the check below IS the report
        return False, str(exc)
    return True, ""


def main():
    with open_studio() as base:
        with sync_playwright() as pw:
            browser, page, errors = launch(pw)
            page.goto(base + "/", wait_until="networkidle")
            page.wait_for_timeout(600)

            # ---- 0a. control, welcome view ---------------------------------
            # The sidebar is asserted HERE, while the welcome screen is up.
            # This is the view it certainly lives in. The first draft asserted
            # it and the manuscript together in one block, which could not work:
            # `#manuscript-workspace` has no box at all until a project is open,
            # so the manuscript control was measuring 0x0 and passing/failing
            # for reasons unrelated to print.
            CHECKS.ok("control: the shelf is visible on the welcome screen",
                      page.locator("#sidebar").is_visible())
            CHECKS.ok("control: the welcome screen is up",
                      page.locator("#welcome-view").is_visible())

            # ---- 0b. open a project so a manuscript exists -----------------
            opened, why = _wait_for_project_open(page)
            CHECKS.ok("control: the sample page opened onto the desk",
                      opened, why)

            # ---- 0c. control, desk view -----------------------------------
            CHECKS.ok("control: the manuscript is visible on screen",
                      page.locator(PRINT_PAPER).is_visible())
            # A bare is_visible() on a container that has just appeared is
            # weak, so the control also insists it has real area. Without this
            # the suite could sail past a manuscript that is present but empty,
            # and then say something confident about its printed width.
            on_screen = page.evaluate(_JS, PRINT_PAPER)
            sw, sh = _dims(on_screen)
            CHECKS.ok("control: the manuscript has real area on screen",
                      sw > 1000 and sh > 300,
                      f"screen box {on_screen.get('box')} (want >1000x>300)")

            # ---- 1. print media --------------------------------------------
            page.emulate_media(media="print")
            page.wait_for_timeout(400)

            visible_chrome = []
            for sel in PRINT_CHROME:
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

            # The manuscript crushed to a sliver is the specific symptom of the
            # broken build: the chrome absorbed `display: block` and crowded it
            # out. A bare "not display:none" passes on the broken build's 187px.
            pw_, ph = _dims(paper)
            CHECKS.ok("print gives the manuscript the page width (not crushed)",
                      pw_ > 1000,
                      f"print box {paper.get('box')} (broken build renders 187x)")

            assert_no_js_errors(CHECKS, errors)
            CHECKS.finish()


if __name__ == "__main__":
    main()