"""The script search box filters the manuscript — and must not rebuild it per
keystroke.

Two contracts, one of which no suite had ever touched:

1. FILTER HONESTY. A query hides the scenes that do not contain it, a nonsense
   query says so out loud instead of leaving a blank page, and clearing the box
   puts the whole draft back. This is the behaviour a writer relies on to read
   one thread through a 120-page script.

2. ONE RENDER PER BURST. The `input` handler called `renderManuscript()`, which
   starts with `container.innerHTML = ""` and rebuilds every scene page *plus*
   the five craft panels. Typing "revolver" therefore tore the manuscript down
   and rebuilt it eight times — and every in-place edit caret, ink mark and
   scroll anchor went with it. A debounce is only worth having if something
   counts the rebuilds, so this suite counts them.

The fixture is seeded on disk (2 scenes, no model): one query matches scene 2
only, one matches both, one matches nothing.

Run:  python tests/e2e_browser_script_search.py
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e2e_browser_common import (Checks, assert_no_js_errors, launch,  # noqa: E402
                                start_studio)
from e2e_browser_one_matcher import make_fixture
from playwright.sync_api import sync_playwright  # noqa: E402

FIXTURE = "script_search_fixture"

SPY = """() => {
  window.__rebuilds = 0;
  if (!window.__spied) {
    const orig = window.renderManuscript;
    window.renderManuscript = function (...a) {
      window.__rebuilds++;
      return orig.apply(this, a);
    };
    window.__spied = true;
  }
}"""

# Which scene pages are on the page and which are hidden: the filter works by
# leaving matching pages attached, so count what a reader actually sees.
SEEN = """() => {
  const pages = [...document.querySelectorAll('#manuscript-container .scene-page')];
  const shown = pages.filter((p) => !p.classList.contains('hidden'));
  return {
    pages: pages.length,
    shown: shown.length,
    heads: shown.map((p) => (p.querySelector('.scene-heading-line') || {}).textContent || ''),
    hint: (document.querySelector('#manuscript-container .script-empty-hint') || {})
            .textContent || null,
    rebuilds: window.__rebuilds,
  };
}"""


def type_query(checks, page, text, settle=250):
    """Focus the box, wipe any previous query, then type `text` key by key.

    The counter starts after the wipe so it measures the burst, not the reset.
    """
    page.evaluate(SPY)
    box = page.locator("#script-search")
    box.click()
    box.press("Control+a")
    box.press("Delete")
    page.wait_for_timeout(600)
    page.evaluate("() => { window.__rebuilds = 0; }")
    if text:
        box.press_sequentially(text, delay=45)
    page.wait_for_timeout(settle)
    return page.evaluate(SEEN)


def run(base, projects_dir):
    checks = Checks()
    make_fixture(projects_dir, FIXTURE)
    with sync_playwright() as pw:
        browser, page, errors = launch(pw)
        page.goto(base)
        page.evaluate("async (n) => { await openProject(n); }", FIXTURE)
        page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)

        both = type_query(checks, page, "mara")
        checks.ok("a query both scenes answer keeps both on the page",
                  both["shown"] == 2 and both["pages"] == 2, str(both))

        one = type_query(checks, page, "rooftop")
        checks.ok("a query only one scene answers hides the other",
                  one["shown"] == 1 and "ROOFTOP" in one["heads"][0], str(one))

        none = type_query(checks, page, "zebrax", settle=700)
        checks.ok("a query nothing answers says so, instead of a blank page",
                  none["hint"] and "No scenes match" in none["hint"], str(none))

        # The regression: one typing burst, one manuscript rebuild.
        checks.ok("a 6-character burst rebuilds the manuscript once",
                  none["rebuilds"] <= 2,
                  f"{none['rebuilds']} rebuilds for 'zebrax' typed in 6 keys")

        # Clearing is one keystroke and it must put the whole draft back.
        page.evaluate("() => { window.__rebuilds = 0; }")
        page.locator("#script-search").press("Control+a")
        page.locator("#script-search").press("Delete")
        page.wait_for_timeout(700)
        cleared = page.evaluate(SEEN)
        checks.ok("clearing the box puts the whole draft back",
                  cleared["shown"] == 2 and not cleared["hint"], str(cleared))
        checks.ok("clearing with one keystroke rebuilds once",
                  cleared["rebuilds"] <= 2, f"{cleared['rebuilds']} rebuilds")

        assert_no_js_errors(checks, errors)
        browser.close()

    checks.finish()


if __name__ == "__main__":
    import tempfile

    with start_studio(projects_dir=tempfile.mkdtemp(prefix="script_search_")) as studio:
        run(studio.base_url, studio.projects_dir)
