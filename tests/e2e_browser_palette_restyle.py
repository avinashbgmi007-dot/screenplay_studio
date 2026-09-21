"""Ctrl+K command-palette restyle + behaviour guard.

Promoted 2026-09-21 from the root-level `_r3_palette_probe.py`, which had two
problems that together made it worth nothing:

  * **Nothing ran it.** It was not named `e2e_browser_*.py`, so
    `tests/run_browser_suites.py` never discovered it; pytest ignores it (no
    `test_` prefix) and CI never invoked it. It was a probe, not a gate.
  * **It crashed instead of failing.** It filtered the palette on the query
    `"script"`, and in a project-less studio that matches nothing: the only
    label containing it is *"Search the script"*, which `paletteCommands()`
    marks **project-only** and hides when no project is open (by design —
    `app.js:7367`, so the palette never lists a command that would silently
    do nothing). `.palette-row` therefore never appeared and
    `rows.first.evaluate(...)` raised a Playwright TimeoutError 30 s in —
    a crash, not a reported failure, which is why it looked fine for months.

The restyle it covers is still uncovered elsewhere: `phase9_idea_canvas`
exercises which commands the palette *offers*, not what it looks like. The
restyle is the R3 design contract (input border, double-glow focus, row hover
wash, selected wash, modal elevation).

Checks are behavioural or computed-style — no screenshots (project rule).
"""

import sys

sys.path.insert(0, "tests")

import playwright.sync_api as pw_sync  # noqa: E402

from e2e_browser_common import (  # noqa: E402
    Checks, assert_no_js_errors, launch, open_studio,
)

checks = Checks()
check = checks.ok

# The retired accent-deep token the R3 restyle replaced. Its presence on the
# palette input means the restyle did not land.
RETIRED_ACCENT = "rgb(85, 81, 102)"

with pw_sync.sync_playwright() as p:
    with open_studio() as base:
        browser, page, errors = launch(p)
        page.goto(base, wait_until="networkidle")

        # ---- open via the real shortcut ------------------------------------
        page.keyboard.press("Control+k")
        page.wait_for_timeout(300)

        modal = page.locator("#palette-modal")
        check("palette opens on Ctrl+K",
              modal.is_visible()
              and modal.evaluate("el => el.style.display") == "flex")

        inp = page.locator("#palette-input")
        check("palette input focused on open (keyboard users can type at once)",
              inp.evaluate("el => el === document.activeElement"))

        # ---- restyle: border + focus glow ----------------------------------
        border = inp.evaluate("el => getComputedStyle(el).borderColor")
        check("input border is not the retired accent-deep token",
              RETIRED_ACCENT not in border and border not in ("", "none"), border)

        # The accent is THEME-DEPENDENT and the deleted probe hardcoded one
        # theme's value: `style.css` pins `--lamp: #7e6bff` (violet), but
        # `tungsten.css` is a cascade override layer that loads AFTER it and
        # re-pins `--lamp: #e8c56a` (gold). The probe asserted the violet, so
        # it asserted a colour the app stopped shipping. `#palette-input:
        # focus-visible` sets BOTH `border-color: var(--accent)` and the ring
        # to `var(--accent)`, so comparing the ring against the input's own
        # border colour proves the glow tracks the live accent without naming
        # any colour at all.
        shadow = inp.evaluate("el => getComputedStyle(el).boxShadow")
        check("focus ring uses the live accent token (theme-independent)",
              border in shadow, f"border={border} shadow={shadow[:140]}")
        check("focus is the double glow (2px ring + 4px halo)",
              "0px 0px 0px 2px" in shadow and "0px 0px 0px 4px" in shadow,
              shadow[:140])

        # ---- rows render ---------------------------------------------------
        # The default (empty) query lists every available command, so this is
        # project-independent. The old probe's "script" query was not, and the
        # resulting empty list crashed it rather than failing it.
        rows = page.locator(".palette-row")
        n = rows.count()
        check("palette rows render for the default query", n > 0, f"rows={n}")
        if n == 0:
            # Everything below reads a row. Report the real cause once and stop,
            # rather than raising a TimeoutError that hides which check broke.
            check("row-dependent restyle checks could run", False,
                  "no .palette-row rendered — the restyle cannot be verified")
            assert_no_js_errors(checks, errors)
            browser.close()
            checks.finish()

        # ---- row hover wash -------------------------------------------------
        if n > 1:
            card_bg = page.locator("#palette-modal .modal").evaluate(
                "el => getComputedStyle(el).backgroundColor")
            target = rows.nth(1)
            before = target.evaluate("el => getComputedStyle(el).backgroundColor")
            target.hover()
            page.wait_for_timeout(150)
            hovered = target.evaluate("el => getComputedStyle(el).backgroundColor")
            check("row hover paints an accent wash (differs from the card)",
                  hovered not in ("rgba(0, 0, 0, 0)", "transparent")
                  and hovered != card_bg,
                  f"before={before} hovered={hovered} card={card_bg}")
        else:
            check("row hover paints an accent wash (differs from the card)", False,
                  f"only {n} row(s) — a hover comparison needs two")

        # ---- modal elevation -------------------------------------------------
        modal_shadow = page.locator("#palette-modal .modal").evaluate(
            "el => getComputedStyle(el).boxShadow")
        check("palette card carries the elevation shadow",
              modal_shadow not in ("", "none") and "rgba" in modal_shadow,
              modal_shadow[:80])

        # ---- keyboard navigation --------------------------------------------
        # Reopen first. The hover check above fires the rows' `mousemove`
        # handler, which sets `paletteIndex` to the hovered row
        # (`app.js:7478`), so ArrowDown would move from THERE, not from row 0.
        # Reopening resets it, which makes the assertion about ArrowDown
        # rather than about whatever the hover left behind.
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
        page.keyboard.press("Control+k")
        page.wait_for_timeout(300)
        # Row 0 starts with `.sel`; ArrowDown must MOVE the selection to row 1.
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(120)
        sel_i = page.evaluate(
            "() => { const r = document.querySelector('.palette-row.sel');"
            " return r ? r.dataset.i : null; }")
        check("ArrowDown moves the selection to the next row",
              sel_i == "1", f"selected data-i={sel_i!r} (expected '1')")

        # ---- Esc closes ------------------------------------------------------
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)
        check("Esc closes the palette",
              page.locator("#palette-modal").evaluate(
                  "el => el.style.display") == "none")

        assert_no_js_errors(checks, errors)
        browser.close()

checks.finish()
