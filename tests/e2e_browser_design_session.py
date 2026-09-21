"""E2E: design session console — four surfaces, dawn sync, layout modes, walk bar.

DOM/text assertions only (project rule: no screenshots).

**What this suite is (pass 13).** The console is a **lab artifact, not shipped
surface** — nothing in the app links to it, and `docs/CRITICAL_REVIEW_2026-09-18.md`
classifies it as LAB-ONLY by design. It sat in `REQUIRES_LIVE_STUDIO`, which
described it as needing a studio running at `E2E_BASE`; that label was false in a
way that mattered, because **no port would ever have made it pass**.

The console frames the studio's own SPA in its fourth cell, and the SPA ships
`frame-ancestors 'none'` (`_SPA_CSP`). Chrome refuses the frame outright:

    Framing 'http://127.0.0.1:<port>/' violates the following Content Security
    Policy directive: "frame-ancestors 'none'". The request has been blocked.

So the "live" cell has been blank for as long as that header has existed, and
because this suite was skipped in every gate run, nothing ever said so. That is
the "dead coverage looks like safety" failure in its purest form.

**The fix is NOT to relax the header.** `frame-ancestors 'none'` protects the
*shipped* app; the only thing it blocks is an unlinked lab page. Trading a real
security property for a dead artifact would be the wrong direction, so the block
is left in place and **pinned as a check below** — if anyone ever relaxes the CSP,
this suite fails and forces that decision into the open instead of letting it
pass quietly.

What the suite now does: it **boots its own studio** (like the rest of the gate)
and verifies everything that is genuinely meant to work — the three same-origin
prototypes, dawn sync, layout modes, solo, the comparison overlay and the guided
walk — plus the deliberate block. `design_session` is no longer a SKIP row.

Run:  python tests/e2e_browser_design_session.py
      (set E2E_BASE to drive a studio you already have running)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright  # noqa: E402

from e2e_browser_common import (Checks, assert_no_js_errors, launch,  # noqa: E402
                                open_studio)

checks = Checks()
check = checks.ok

PROTOTYPES = ("nocta", "lumen", "beatwall")

# The one console error the page is SUPPOSED to produce. Matched on the CSP
# directive name rather than the full text, because the message embeds the
# studio's port.
CSP_BLOCK_MARKER = "frame-ancestors"


def _cell_state(page, key):
    """{dawn, dark} for one cell's iframe body, or {'err': ...} if unreachable."""
    return page.evaluate(
        """(key) => {
             const f = document.querySelector('.cell[data-key="' + key + '"] iframe');
             try {
               return {dawn: f.contentDocument.body.classList.contains('dawn'),
                       dark: f.contentDocument.body.classList.contains('dark')};
             } catch (e) { return {err: String(e)}; }
           }""",
        key,
    )


def _visible_cells(page):
    return page.eval_on_selector_all(
        ".cell", "els => els.filter(e => getComputedStyle(e).display !== 'none')"
                 ".map(e => e.dataset.key)")


def run(base):
    with sync_playwright() as p:
        browser, page, errors = launch(p)
        # launch() traps uncaught page errors; the console channel is separate and
        # is where a dead script shows up (see the gallery defect in pass 9).
        console_errors = []
        page.on("console",
                lambda m: console_errors.append(m.text) if m.type == "error" else None)

        page.goto(f"{base}/design_session.html", wait_until="networkidle")
        page.wait_for_timeout(1200)

        # ---- 1. the three prototypes are mounted and reachable ------------
        frames = page.eval_on_selector_all(
            ".cell-frame iframe",
            "els => els.map(e => ({key: e.closest('.cell').dataset.key,"
            " src: e.src.split('/').slice(-2).join('/'),"
            " ok: !!(e.contentDocument && e.contentDocument.body)}))")
        check("console: four surfaces mounted", len(frames) == 4, f"{len(frames)} frame(s)")

        # Keyed on the cell, not on the src shape: the live frame's shortened src
        # is "<host>/", which is not a stable thing to match on.
        proto_unreachable = [f["src"] for f in frames
                             if not f["ok"] and f["key"] != "live"]
        check("console: all three prototypes reachable same-origin",
              not proto_unreachable, f"unreachable={proto_unreachable}")

        # ---- 2. the live cell is blocked BY OUR OWN CSP, deliberately -----
        # See the module docstring: this is the shipped app refusing to be
        # framed, and it is asserted rather than worked around. If the CSP is
        # ever relaxed to 'self' so the console can frame the app, THIS check
        # fails — which is the point, because that is a decision someone has to
        # make on purpose.
        live = page.eval_on_selector(
            ".cell.live iframe",
            "e => ({doc: !!e.contentDocument, src: e.src})")
        check("console: the live cell is framed by the console at all",
              live["src"].endswith("/"), f"live src={live['src']!r}")
        check("console: live cell is blocked by the app's frame-ancestors 'none'",
              not live["doc"],
              "the SPA is framable — if that is deliberate, relax _SPA_CSP to "
              "'self' and update this check and its test")

        blocked = [m for m in console_errors if CSP_BLOCK_MARKER in m]
        check("console: exactly one CSP framing refusal is logged",
              len(blocked) == 1, f"{len(blocked)} CSP refusal(s)")

        # ---- 3. dawn sync flips the prototype bodies ----------------------
        page.click("#syncDawn")
        page.wait_for_timeout(400)
        on = {k: _cell_state(page, k) for k in PROTOTYPES}
        check("console: dawn sync sets .dawn on the prototypes",
              bool(on["nocta"].get("dawn") and on["lumen"].get("dawn")), f"{on}")
        check("console: dawn sync sets .dark on beatwall (night)",
              bool(on["beatwall"].get("dark")), f"{on['beatwall']}")

        page.click("#syncDawn")
        page.wait_for_timeout(400)
        off = {k: _cell_state(page, k) for k in PROTOTYPES}
        check("console: second click returns the prototypes to the default theme",
              not any(off[k].get("dawn") for k in PROTOTYPES)
              and not off["beatwall"].get("dark"), f"{off}")

        # ---- 4. dawn actually changes the rendered background -------------
        bg_before = page.eval_on_selector(
            ".cell[data-key='nocta'] iframe",
            "e => getComputedStyle(e.contentDocument.body).backgroundColor")
        page.click("#syncDawn")
        page.wait_for_timeout(300)
        bg_after = page.eval_on_selector(
            ".cell[data-key='nocta'] iframe",
            "e => getComputedStyle(e.contentDocument.body).backgroundColor")
        check("console: dawn visibly repaints (bg changes)",
              bg_before != bg_after, f"{bg_before} -> {bg_after}")

        # ---- 5. layout modes ----------------------------------------------
        page.click("#layProto")
        page.wait_for_timeout(200)
        check("console: proto mode shows exactly the 3 prototypes",
              len(_visible_cells(page)) == 3, f"visible={_visible_cells(page)}")

        page.click("#layLive")
        page.wait_for_timeout(200)
        check("console: live mode shows only the live surface",
              _visible_cells(page) == ["live"], f"visible={_visible_cells(page)}")

        page.click("#layQuad")
        page.wait_for_timeout(200)
        check("console: quad mode shows all four",
              len(_visible_cells(page)) == 4, f"visible={_visible_cells(page)}")

        # ---- 6. solo -------------------------------------------------------
        page.click(".cell[data-key='lumen'] .icon-btn")
        page.wait_for_timeout(200)
        check("console: solo isolates one surface",
              _visible_cells(page) == ["lumen"], f"visible={_visible_cells(page)}")
        page.click("#layQuad")

        # ---- 7. comparison overlay -----------------------------------------
        page.click("#btnCompare")
        page.wait_for_timeout(300)
        cls = page.get_attribute("#compare", "class") or ""
        check("console: compare overlay opens", "open" in cls, f"class={cls!r}")
        txt = page.inner_text("#compare")
        missing = [n for n in ("Typography", "Density", "Navigation model",
                               "Dawn / light theme", "Motion language",
                               "Georgia + system-ui") if n not in txt]
        check("console: compare overlay lists all five axes + the inherit table",
              not missing, f"missing={missing}")

        # ---- 8. guided walk (close the overlay first: it would intercept) --
        page.click("#btnCompare")
        page.wait_for_timeout(300)
        page.click("#btnWalk")
        page.wait_for_timeout(200)

        q1 = page.inner_text("#qText")
        check("walk: Q1 asks about fonts", "Fonts" in q1, q1[:80])
        check("walk: Q1 offers 3 answers",
              page.eval_on_selector_all("#qAns button", "els => els.length") == 3)

        expected = [(1, "Density"), (2, "Navigation"), (3, "Dawn"), (4, "Motion")]
        walked = True
        for nth, topic in expected:
            page.click(f"#qAns button:nth-child({nth})")
            page.wait_for_timeout(150)
            q = page.inner_text("#qText")
            if topic not in q:
                walked = False
                check(f"walk: Q{nth + 1} asks about {topic.lower()}", False, q[:80])
        check("walk: the five questions advance in order", walked)

        page.click("#qAns button:nth-child(3)")
        page.wait_for_timeout(400)

        # ---- 9. nothing else went wrong -----------------------------------
        assert_no_js_errors(checks, errors, "console: zero uncaught JS errors")
        unexpected = [m for m in console_errors if CSP_BLOCK_MARKER not in m]
        check("console: zero console errors beyond the deliberate CSP refusal",
              not unexpected, "; ".join(unexpected[:3]))
        browser.close()

    checks.finish()


if __name__ == "__main__":
    env_base = os.environ.get("E2E_BASE")
    if env_base:
        run(env_base.rstrip("/"))
    else:
        with open_studio() as base:
            run(base)
