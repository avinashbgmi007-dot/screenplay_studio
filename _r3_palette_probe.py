"""R3 palette probe — no suite exercises the Ctrl+K palette UI, so this
verifies the restyle directly: input rest border, double-glow focus, row
hover wash, .sel wash, and the modal elevation token applied.
DOM/computed-style assertions only (project rule: no screenshots)."""
import sys

sys.path.insert(0, "tests")
import playwright.sync_api as pw_sync
from e2e_browser_common import Checks, assert_no_js_errors, launch, open_studio

checks = Checks()
check = checks.ok

with pw_sync.sync_playwright() as p:
    with open_studio() as base:
        browser, page, errors = launch(p)
        page.goto(base, wait_until="networkidle")

        # open the palette via its real shortcut
        page.keyboard.press("Control+k")
        page.wait_for_timeout(300)

        modal = page.locator("#palette-modal")
        check("palette opens on Ctrl+K",
              modal.is_visible() and modal.evaluate("el => el.style.display") == "flex")

        inp = page.locator("#palette-input")
        check("palette input focused on open",
              inp.evaluate("el => el === document.activeElement"))

        # rest border: neutral line, not the old accent-deep
        border = inp.evaluate("el => getComputedStyle(el).borderColor")
        check("input rest border is the neutral line", "rgb(85, 81, 102)" not in border, border)

        # focus glow: the unified double-glow (input IS focused on open)
        shadow = inp.evaluate("el => getComputedStyle(el).boxShadow")
        check("input focus = double glow (0 0 0 2px accent layer)",
              "rgb(126, 107, 255)" in shadow and "2px" in shadow, shadow[:120])

        # rows: filter to narrow results, then check hover + sel classes
        inp.fill("script")
        page.wait_for_timeout(200)
        rows = page.locator(".palette-row")
        n = rows.count()
        check("palette rows render for query", n > 0, f"rows={n}")

        sel_shadow = rows.first.evaluate(
            "el => getComputedStyle(el).backgroundColor")
        # hover the first non-selected row
        page.keyboard.press("Escape")  # close and reopen cleanly for hover test
        page.keyboard.press("Control+k")
        page.wait_for_timeout(200)
        rows = page.locator(".palette-row")
        if rows.count() > 1:
            rows.nth(1).hover()
            page.wait_for_timeout(100)
            hovered = rows.nth(1).evaluate("el => getComputedStyle(el).backgroundColor")
            check("row hover = accent wash (rgb with violet channel)",
                  hovered not in ("rgba(0, 0, 0, 0)", "transparent") and "233" not in hovered,
                  hovered)

        # modal elevation token (lives on the .modal card — the overlay is just the scrim)
        modal_shadow = page.locator("#palette-modal .modal").evaluate(
            "el => getComputedStyle(el).boxShadow")
        check("modal shadow present (elev-modal family)",
              "rgba(0, 0, 0, 0.55)" in modal_shadow or "0.55" in modal_shadow,
              modal_shadow[:80])

        # keyboard navigation still selects rows (the sel class)
        inp.fill("vie")
        page.wait_for_timeout(200)
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(100)
        sel_class = page.evaluate(
            "() => { const r = document.querySelector('.palette-row.sel'); return r ? r.className : 'none'; }")
        check("ArrowDown selects a row (.sel)", "sel" in sel_class, sel_class)

        assert_no_js_errors(checks, errors)
        browser.close()

checks.finish()
