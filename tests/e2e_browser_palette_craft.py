"""The seven craft questions in the command palette must reach a composer the
writer can actually see and send from.

Why this suite exists: every one of the seven `type: "craft"` rows in
`paletteCommands()` routes through `openSameerWith()`, which used to guard on
`state.view !== "cowrite"` before opening the room. Opening a project ends with
`setRoom("cowrite")` and the drawer CLOSED, so from the state a writer is
actually in the guard never fired, `openCowriteRoom()` never ran, and the
question was written into `#input` while the drawer was still hidden
(`visibility: hidden`, `pointer-events: none`) with focus landing on `<body>`.
The command looked like it did nothing, and the text resurfaced later unasked.

`palette_restyle.py` covers what the palette LOOKS like; nothing here before
covered what a row DOES.

Checks are on computed style and the real DOM — no screenshots (project rule).
"""

import sys

sys.path.insert(0, "tests")

import playwright.sync_api as pw_sync  # noqa: E402
import requests  # noqa: E402

from e2e_browser_common import (  # noqa: E402
    Checks, assert_no_js_errors, launch, open_studio, studio_headers,
)

checks = Checks()
check = checks.ok

CRAFT_QUERY = "dialogue"           # matches "Why doesn't my dialogue land?"
CRAFT_PREFIX = "Analyze my dialogue"

with pw_sync.sync_playwright() as p:
    with open_studio() as base:
        browser, page, errors = launch(p)
        page.goto(base, wait_until="networkidle")

        # ---- a project, because the palette's craft rows are the flagship
        # path for someone who has one open -------------------------------
        seeded = requests.post(f"{base}/api/sample",
                               headers=studio_headers(base), timeout=120)
        assert seeded.status_code in (200, 201), seeded.text
        project = seeded.json()["project"]
        page.evaluate("async (n) => { await openProject(n); }", project)
        page.wait_for_timeout(1500)

        # ---- the precondition IS the bug's trigger ------------------------
        # If the drawer were already open this path would work even with the
        # guard, so a suite that skipped this assertion would pass for the
        # wrong reason.
        pre = page.evaluate(
            "() => ({ view: state.view,"
            "        open: !!document.querySelector('#room-drawer.open') })")
        check("after opening a project the room is cowrite (precondition)",
              pre["view"] == "cowrite", str(pre))
        check("...and the partner drawer is CLOSED (precondition)",
              pre["open"] is False,
              f"{pre} — without a closed drawer there is nothing to catch")

        # ---- run the row the way a writer does: Ctrl+K, type, Enter -------
        page.keyboard.press("Control+k")
        page.wait_for_timeout(300)
        page.fill("#palette-input", CRAFT_QUERY)
        page.wait_for_timeout(300)
        rows = page.locator(".palette-row")
        check("the craft row is listed for the query",
              rows.count() > 0, f"rows={rows.count()}")
        page.keyboard.press("Enter")
        page.wait_for_timeout(600)

        after = page.evaluate(
            """() => {
              const i = document.querySelector('#input');
              const cs = i ? getComputedStyle(i) : null;
              const drawer = document.querySelector('#room-drawer');
              return {
                drawerOpen: !!drawer && drawer.classList.contains('open'),
                paletteClosed: document.querySelector('#palette-modal').style
                                 .display === 'none',
                value: i ? i.value : null,
                visibility: cs ? cs.visibility : null,
                pointer: cs ? cs.pointerEvents : null,
                focused: i ? (i === document.activeElement) : false,
                activeTag: document.activeElement
                             ? document.activeElement.tagName + '#' +
                               (document.activeElement.id || '')
                             : null,
              };
            }""")

        check("the palette closes on Enter",
              after["paletteClosed"], str(after))
        check("the craft question opens the partner drawer",
              after["drawerOpen"], str(after))
        check("the composer holds the question",
              bool(after["value"]) and after["value"].startswith(CRAFT_PREFIX),
              repr(after["value"])[:120])
        check("the composer is actually visible (not hidden chrome)",
              after["visibility"] == "visible", str(after))
        check("the composer accepts input (pointer-events not none)",
              after["pointer"] != "none", str(after))
        check("focus is in the composer — one keystroke from sending",
              after["focused"],
              f"activeElement={after['activeTag']} {after['drawerOpen']}")

        assert_no_js_errors(checks, errors)
        browser.close()

checks.finish()
