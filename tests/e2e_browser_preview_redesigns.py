"""PREVIEW-REDESIGNS e2e — the six concept worlds + gallery, via Playwright.

SELF-CONTAINED like every e2e_browser_* suite (see e2e_browser_common): the
previews are pure static files, so this suite boots a plain http.server over
screenplay_studio/webapp/ on a free port and drives each world at 1440x900.

WHAT THIS SUITE DELIBERATELY DOES *NOT* ASSERT
---------------------------------------------
Its predecessor named a screen model that no longer exists. It walked
`welcome -> desk -> cowrite -> feedback`, summoned panes via `.edge-tab` /
`.spine-tab` and `.pane-pop`, and read a gallery of `a.card`. Every one of those
selectors is now absent from all six worlds — the worlds were redesigned to
`upload/pages/verdict/debate/spark` (and brutal to
`wall/verdict/debate/grad/river/drop`), the pane mechanism was replaced, and the
gallery became a JS-built card grid. So that suite was not "one bug"; its entire
contract was obsolete, and it crashed on the first world it tried to inspect.

Rewriting 48 selector-coupled checks against a frozen prototype would recreate
the same trap for the next redesign. This suite instead asserts the invariants
that SURVIVE a redesign:

  per world
    1. loads with EXACTLY ONE active screen
    2. no inactive screen is left computed-visible (the
       `.s-x{display:flex}`-beats-`[data-screen]{display:none}` cascade bug)
    3. no horizontal overflow
    4. zero uncaught JS exceptions
    5. `[data-go]` navigation really switches the active screen — or, for a
       single-screen world, that it declares no navigation at all
  gallery
    6. a card per design, and every design reachable by link
    7. zero uncaught JS exceptions  (this is the check that catches a gallery
       script dying on a null getElementById — see below)
    8. Live view swaps the card grid for the frame view
    9. opening a card points the frame at that design

Screen NAMES are intentionally not asserted: a redesign renames them, and the
gallery is the one place that enumerates designs, so the two cannot drift
silently (check 6 compares the links against this file's own DESIGNS list).

No screenshots are written. The predecessor dumped 25 PNGs into
preview-redesigns/shots/, which is why that directory still holds
`*-welcome.png` / `*-cowrite.png` evidence for screens the worlds no longer
have. Assertions belong in a test; regenerating tracked artifacts on every run
only produces review churn.

Run:  python tests/e2e_browser_preview_redesigns.py
Needs: playwright (+ chromium) installed; nothing else.
"""
import os
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

from e2e_browser_common import Checks, REPO_ROOT, assert_no_js_errors, free_port, launch

WEBAPP_DIR = os.path.join(REPO_ROOT, "screenplay_studio", "webapp")

# The six concept worlds, in gallery order. Check 6 asserts the gallery links
# match this list exactly, so adding a world means updating both.
DESIGNS = ["noir", "paper", "brutal", "swiss", "organic", "terminal"]

# Reads every invariant that is independent of a world's screen names.
PROBE = """() => {
  const secs = [...document.querySelectorAll('[data-screen]')];
  const active = secs.filter(e => e.classList.contains('active'));
  const visibleInactive = secs.filter(e =>
      !e.classList.contains('active') && getComputedStyle(e).display !== 'none');
  return {
    n_screens: secs.length,
    n_active: active.length,
    activeName: active.length === 1 ? active[0].dataset.screen : null,
    n_visible_inactive: visibleInactive.length,
    scroll_w: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
    inner_w: window.innerWidth,
    go: [...document.querySelectorAll('[data-go]')].map(b => b.dataset.go),
  };
}"""


def serve_webapp():
    """http.server over the webapp dir; returns (base_url, proc)."""
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=WEBAPP_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            urllib.request.urlopen(base + "/preview-redesigns/index.html",
                                   timeout=2)
            return base, proc
        except Exception:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("static server never came up")


def verify_world(checks, page, errors, base, design):
    page.goto(f"{base}/preview-redesigns/{design}.html")
    page.wait_for_timeout(700)
    info = page.evaluate(PROBE)

    checks.check(f"{design}: exactly one active screen",
                 info["n_active"] == 1,
                 f"{info['n_active']} active of {info['n_screens']} "
                 f"(active={info['activeName']!r})")
    checks.check(f"{design}: no inactive screen left visible",
                 info["n_visible_inactive"] == 0,
                 f"{info['n_visible_inactive']} inactive screen(s) still displayed")
    checks.check(f"{design}: no horizontal overflow",
                 info["scroll_w"] <= info["inner_w"],
                 f"{info['scroll_w']} > {info['inner_w']}")

    # Navigation: a multi-screen world must actually navigate; a single-screen
    # world must not pretend to. Both branches assert something real, so neither
    # is a skip that could hide a regression.
    targets = [t for t in info["go"] if t != info["activeName"]]
    if targets:
        want = targets[0]
        page.locator(f'[data-go="{want}"]').first.click()
        page.wait_for_timeout(450)
        after = page.evaluate(PROBE)
        checks.check(f"{design}: data-go navigation switches screens",
                     after["activeName"] == want and after["n_active"] == 1,
                     f"asked for {want!r}, active is {after['activeName']!r} "
                     f"({after['n_active']} active)")
    else:
        checks.check(f"{design}: single-screen world declares no navigation",
                     info["n_screens"] == 1,
                     f"{info['n_screens']} screens but no [data-go] to reach them")

    assert_no_js_errors(checks, errors, f"{design}: zero JS errors")


def verify_gallery(checks, page, errors, base):
    page.goto(f"{base}/preview-redesigns/index.html")
    page.wait_for_timeout(700)

    links = page.evaluate(
        "() => [...document.querySelectorAll('.card .open-link')]"
        ".map(a => a.getAttribute('href'))")
    got = sorted(h[:-len(".html")] for h in links if h and h.endswith(".html"))
    checks.check("gallery: one card per design, all six reachable",
                 got == sorted(DESIGNS),
                 f"links={got} expected={sorted(DESIGNS)}")
    checks.check("gallery: card grid rendered",
                 page.locator("#cards .card").count() == len(DESIGNS),
                 f"{page.locator('#cards .card').count()} card(s)")

    # BEFORE interacting: if the gallery script died early, this is the check
    # that says so by name. It is the one that catches a null getElementById —
    # the buttons still exist and still look clickable, so the only visible
    # symptom is the uncaught exception (and the controls doing nothing).
    assert_no_js_errors(checks, errors, "gallery: zero JS errors")

    # Live view: the switcher must swap the grid for the frame. Guarded so a
    # dead script reports as a named failure rather than a click timeout that
    # aborts the suite before the remaining checks run.
    def _click(locator):
        try:
            locator.click(timeout=4000)
            page.wait_for_timeout(300)
            return True
        except Exception:
            return False

    clicked = _click(page.locator('#viewbar button[data-view="fr"]'))
    frame_on = page.evaluate(
        "() => document.getElementById('frameView').classList.contains('on')")
    cards_hidden = page.evaluate(
        "() => getComputedStyle(document.getElementById('cards')).display === 'none'")
    checks.check("gallery: Live view swaps the grid for the frame",
                 clicked and frame_on and cards_hidden,
                 f"switcherClickable={clicked} frameView.on={frame_on} "
                 f"cardsHidden={cards_hidden}")

    # Opening a card must point the frame at that design. `.first` matters: the
    # grid holds one card per design, and a bare `#cards .card` locator trips
    # Playwright's strict mode instead of clicking anything.
    _click(page.locator('#viewbar button[data-view="cards"]'))
    card_clicked = _click(page.locator("#cards .card").first)
    state = page.evaluate(
        "() => ({src: document.getElementById('live').getAttribute('src'),"
        "        pick: document.getElementById('pick').value})")
    checks.check("gallery: opening a card points the frame at that design",
                 card_clicked and state["src"] == f"{DESIGNS[0]}.html"
                 and state["pick"] == DESIGNS[0],
                 f"clicked={card_clicked} src={state['src']!r} pick={state['pick']!r}")


if __name__ == "__main__":
    checks = Checks()
    base, proc = serve_webapp()
    try:
        with sync_playwright() as pw:
            browser, page, errors = launch(pw)
            for design in DESIGNS:
                errors.clear()
                verify_world(checks, page, errors, base, design)
            errors.clear()
            verify_gallery(checks, page, errors, base)
            browser.close()
    finally:
        proc.terminate()
    checks.finish()
