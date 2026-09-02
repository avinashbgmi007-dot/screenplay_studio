"""PREVIEW-REDESIGNS e2e — verify the six UIUX mockups + gallery, via Playwright.

SELF-CONTAINED like every e2e_browser_* suite (see e2e_browser_common): no
Flask studio needed here — the previews are pure static files, so this suite
boots a plain http.server over screenplay_studio/webapp/ on a free port and
drives each mockup at 1440x900:

Per design (noir, paper, brutal, swiss, terminal, organic):
  1. loads, welcome screen active
  2. journey walk: welcome -> desk -> cowrite -> feedback, each reachable
     via its [data-go] buttons with NO horizontal overflow
  3. pane summon: opener click (.edge-tab / .spine-tab) -> some .pane-pop.open
  4. click-outside dismissal: body click -> no .pane-pop.open
  5. explore chips: expanded before typing, .collapsed after first composer input
  6. composer auto-grows on multi-line input
  7. zero console/page errors (Google-Fonts network failures are reported
     separately as environmental, not design failures)
  8. screenshots of every screen -> preview-redesigns/shots/<id>-<screen>.png

Gallery (index.html): 6 cards, live switcher opens the frame view, picker
lists all six, zero console errors, screenshot -> shots/gallery.png.

Run:  python tests/e2e_browser_preview_redesigns.py
Needs: playwright (+ chromium) installed; nothing else.
"""
import os
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

from e2e_browser_common import Checks, REPO_ROOT, free_port, launch

WEBAPP_DIR = os.path.join(REPO_ROOT, "screenplay_studio", "webapp")
SHOTS_DIR = os.path.join(WEBAPP_DIR, "preview-redesigns", "shots")

DESIGNS = {
    "noir": ".edge-tab",
    "paper": ".spine-tab",
    "brutal": ".edge-tab",
    "swiss": ".edge-tab",
    "terminal": ".edge-tab",
    "organic": ".edge-tab",
}
SCREENS = ["welcome", "desk", "cowrite", "feedback"]

# a long multi-line draft to prove the composer grows past its one-line height
MULTILINE = ("What if Rishi keeps the diary but never opens it —\n"
              "the audience sees him hide it twice,\n"
              "and the doctor only finds it after the fire,\n"
              "when the burn marks make the last page unreadable?")


def serve_webapp():
    """http.server over the webapp dir; returns (base_url, proc)."""
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=WEBAPP_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    import urllib.request
    while time.time() < deadline:
        try:
            urllib.request.urlopen(base + "/preview-redesigns/index.html",
                                   timeout=2)
            return base, proc
        except Exception:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("static server never came up")


def no_overflow(page):
    return page.evaluate(
        "() => Math.max(document.documentElement.scrollWidth,"
        "              document.body.scrollWidth) <= window.innerWidth")


def active_screen(page, name):
    return page.evaluate(
        "n => document.querySelector(`section[data-screen=\"${n}\"]`)"
        ".classList.contains('active')", name)


def one_screen_only(page):
    """The screen-switch contract: exactly one active section, every
    inactive section computed display:none, and the page is exactly one
    viewport tall (no stacked screens). Catches the
    `.s-x{display:flex}`-beats-`[data-screen]{display:none}` cascade bug."""
    info = page.evaluate(
        "() => {"
        " const secs = [...document.querySelectorAll('[data-screen]')];"
        " const active = secs.filter(e => e.classList.contains('active'));"
        " const visible_inactive = secs.filter(e =>"
        "     !e.classList.contains('active') &&"
        "     getComputedStyle(e).display !== 'none');"
        " return {n_active: active.length,"
        "         n_visible_inactive: visible_inactive.length,"
        "         body_h: document.body.scrollHeight,"
        "         win_h: window.innerHeight};"
        "}")
    return (info["n_active"] == 1
            and info["n_visible_inactive"] == 0
            and info["body_h"] <= info["win_h"] + 4), info


def open_panes_count(page):
    return page.evaluate(
        "() => document.querySelectorAll('.pane-pop.open').length")


def go(page, screen):
    page.locator(f'button[data-go="{screen}"]').first.click()
    page.wait_for_timeout(350)  # let screen transitions settle


def verify_design(checks, page, base, design_id, opener_sel):
    console_errs, font_errs = [], []

    def on_console(msg):
        if msg.type != "error":
            return
        text = msg.text
        # Google Fonts CDN unreachable is environmental (offline sandbox),
        # the mockups degrade to system stacks by design.
        if "Failed to load resource" in text and "fonts.g" in text:
            font_errs.append(text)
        else:
            console_errs.append(text)

    page.on("console", on_console)

    url = f"{base}/preview-redesigns/{design_id}.html"
    page.goto(url)
    page.wait_for_timeout(500)

    c = lambda name, cond, detail="": checks.ok(f"{design_id}: {name}",
                                                cond, detail)

    c("loads with welcome screen active", active_screen(page, "welcome"))
    c("welcome: no horizontal overflow", no_overflow(page),
      page.evaluate("() => document.documentElement.scrollWidth"))

    # --- journey walk: desk -> cowrite -> feedback --------------------------
    for screen in SCREENS[1:]:
        go(page, screen)
        c(f"{screen}: reachable via preview bar",
          active_screen(page, screen))
        ok, info = one_screen_only(page)
        c(f"{screen}: exactly one screen visible, page fits viewport", ok,
          str(info))
        c(f"{screen}: no horizontal overflow", no_overflow(page))

    # --- behaviors on the desk screen ---------------------------------------
    go(page, "desk")
    desk = page.locator('section[data-screen="desk"]')

    # script-first: pages are the hero, partner tools hidden until summoned
    c("desk: script pages visible",
      desk.locator(".scene-page, .pages").first.is_visible())

    # pane summon + click-outside dismissal (the idea-room model)
    opener = page.locator(f'{opener_sel} >> nth=0')
    if opener.count() == 0:  # openers may live outside the section
        opener = page.locator(f'{opener_sel} >> nth=0')
    opener.click()
    page.wait_for_timeout(300)
    c("pane summons via edge tab", open_panes_count(page) > 0)

    page.evaluate("() => document.body.click()")  # a click outside any pane
    page.wait_for_timeout(250)
    c("pane dismisses on outside click", open_panes_count(page) == 0)

    # explore chips lifecycle
    chips = page.locator('section[data-screen="desk"] .explore-chips').first
    composer = page.locator('section[data-screen="desk"] .composer').first
    c("chips expanded before first input",
      chips.is_visible() and "collapsed" not in (chips.get_attribute("class")
                                                 or ""))

    h0 = composer.bounding_box()["height"]
    composer.fill(MULTILINE)
    page.wait_for_timeout(250)
    c("chips collapse after first input",
      "collapsed" in (chips.get_attribute("class") or ""))
    h1 = composer.bounding_box()["height"]
    c("composer grows with multi-line input", h1 > h0 + 20,
      f"{h0:.0f}px -> {h1:.0f}px")

    # --- screenshots of every screen ----------------------------------------
    for screen in SCREENS:
        go(page, screen)
        page.screenshot(path=os.path.join(
            SHOTS_DIR, f"{design_id}-{screen}.png"))

    if font_errs:
        print(f"  note  {design_id}: {len(font_errs)} Google-Fonts network "
              f"error(s) (environmental, graceful fallback by design)")
    c("zero console/page errors", len(console_errs) == 0,
      "; ".join(console_errs[:3]))
    page.remove_listener("console", on_console)


def verify_gallery(checks, page, base):
    page.goto(f"{base}/preview-redesigns/index.html")
    page.wait_for_timeout(600)
    c = lambda name, cond, detail="": checks.ok(f"gallery: {name}",
                                                cond, detail)
    c("six design cards render", page.locator(".card").count() == 6,
      str(page.locator(".card").count()))
    c("picker lists all six designs",
      page.locator("#pick option").count() == 6)
    c("no horizontal overflow", no_overflow(page))
    page.locator(".card").first.click()
    page.wait_for_timeout(600)
    frame = page.locator("#frameView")
    c("card click opens live frame view", "on" in (frame.get_attribute("class")
                                                   or ""))
    src = page.locator("#live").get_attribute("src") or ""
    c("live frame points at a design", src.endswith(".html"), src)
    page.screenshot(path=os.path.join(SHOTS_DIR, "gallery-live.png"))


def main():
    os.makedirs(SHOTS_DIR, exist_ok=True)
    checks = Checks()
    base, server = serve_webapp()
    try:
        with sync_playwright() as pw:
            browser, page, errors = launch(pw)
            try:
                for design_id, opener_sel in DESIGNS.items():
                    print(f"\n--- {design_id} ---")
                    verify_design(checks, page, base, design_id, opener_sel)
                print("\n--- gallery ---")
                verify_gallery(checks, page, base)
                checks.ok("gallery-run: no JS page errors", len(errors) == 0,
                          "; ".join(errors[:3]))
            finally:
                browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
    checks.finish()


if __name__ == "__main__":
    main()
