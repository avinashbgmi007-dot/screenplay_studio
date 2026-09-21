"""E2E: design session console — four surfaces, dawn sync, layout modes, walk bar.

DOM/text assertions only (project rule: no screenshots).

**What this suite is (pass 14).** The console is a **lab artifact, not shipped
surface** — nothing in the app links to it, and `docs/CRITICAL_REVIEW_2026-09-18.md`
classifies it as LAB-ONLY by design. It sat in `REQUIRES_LIVE_STUDIO`, which
described it as needing a studio running at `E2E_BASE`; that label was false in a
way that mattered, because **no port would ever have made it pass**.

The console frames the studio's own SPA in its fourth cell, and the SPA shipped
`frame-ancestors 'none'` (`_SPA_CSP`). Chrome refused the frame outright:

    Framing 'http://127.0.0.1:<port>/' violates the following Content Security
    Policy directive: "frame-ancestors 'none'". The request has been blocked.

So the "live" cell had been blank for as long as that header has existed, and
because this suite was skipped in every gate run, nothing ever said so. That is
the "dead coverage looks like safety" failure in its purest form.

**Pass 13 pinned the block instead of fixing it**, which was the wrong call: it
turned a broken product surface into a documented one. The block was never the
goal — the goal was that a FOREIGN page cannot frame the desk, and `'self'`
still delivers exactly that while letting the app frame itself. Pass 14 relaxes
the directive to `'self'`, fixes the console's one hardcoded host:port (the only
one anywhere in `webapp/`), and this suite now asserts the frame **renders**.

What the suite does: it **boots its own studio** (like the rest of the gate) and
verifies everything the console is meant to do — the three same-origin
prototypes plus the live studio, dawn sync across all four, layout modes, solo,
the comparison overlay and the guided walk — and that **no CSP refusal is logged
at all**.

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

# A CSP refusal would name the directive that refused. The console used to
# produce exactly one of these, by design; now it must produce none, and this
# marker is how we notice if the directive ever goes back to blocking 'self'.
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

        # ---- 1. all four surfaces are mounted and reachable -----------------
        frames = page.eval_on_selector_all(
            ".cell-frame iframe",
            "els => els.map(e => ({key: e.closest('.cell').dataset.key,"
            " src: e.src.split('/').slice(-2).join('/'),"
            " ok: !!(e.contentDocument && e.contentDocument.body)}))")
        check("console: four surfaces mounted", len(frames) == 4, f"{len(frames)} frame(s)")

        unreachable = [f"{f['key']}={f['src']}" for f in frames if not f["ok"]]
        check("console: all four surfaces reachable same-origin (incl. the live desk)",
              not unreachable, f"unreachable={unreachable}")

        # ---- 2. the live cell really is the SPA, not an error page ---------
        # `contentDocument` being non-null proves framing was permitted; that the
        # document carries the SPA's own chrome proves it is the app and not a
        # 404/blank served with a frameable header. Both halves matter: a
        # same-origin 404 would satisfy the first check on its own.
        live = page.eval_on_selector(
            ".cell.live iframe",
            """e => ({doc: !!e.contentDocument,
                      src: e.src,
                      title: e.contentDocument ? e.contentDocument.title : '',
                      hasChrome: e.contentDocument
                        ? !!e.contentDocument.querySelector('#shelf-trigger, #manuscript-container, .app-shell')
                        : false})""")
        check("console: the live cell is framed by the console at all",
              live["src"].endswith("/"), f"live src={live['src']!r}")
        check("console: the live cell renders the SPA (not blocked, not an error page)",
              live["doc"] and live["hasChrome"],
              f"framed={live['doc']} title={live['title']!r} chrome={live['hasChrome']}")

        # ---- 3. nothing was refused on the way in --------------------------
        blocked = [m for m in console_errors if CSP_BLOCK_MARKER in m]
        check("console: zero CSP framing refusals (the directive allows 'self')",
              not blocked, f"{len(blocked)} refusal(s): {blocked[:1]}")

        # ---- 4. dawn sync flips the prototype bodies ----------------------
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

        # ---- 5. dawn actually changes the rendered background -------------
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

        # ---- 5b. the dawn sync reaches the LIVE desk too -------------------
        # The console's headline claim is "toggle dawn/night across ALL four
        # surfaces (prototypes AND live studio)". With the frame now rendering,
        # that claim is finally testable — and it is the half that was silently
        # dead for as long as the frame was blank.
        live_dawn_before = page.eval_on_selector(
            ".cell.live iframe",
            "e => e.contentDocument.body.classList.contains('dawn')")
        page.click("#syncDawn")
        page.wait_for_timeout(500)
        live_dawn_after = page.eval_on_selector(
            ".cell.live iframe",
            "e => e.contentDocument.body.classList.contains('dawn')")
        check("console: dawn sync reaches the live studio inside the frame",
              live_dawn_before != live_dawn_after,
              f"live body.dawn {live_dawn_before} -> {live_dawn_after}")
        page.click("#syncDawn")  # leave it in the night theme
        page.wait_for_timeout(300)

        # ---- 6. layout modes ----------------------------------------------
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

        # ---- 7. solo -------------------------------------------------------
        page.click(".cell[data-key='lumen'] .icon-btn")
        page.wait_for_timeout(200)
        check("console: solo isolates one surface",
              _visible_cells(page) == ["lumen"], f"visible={_visible_cells(page)}")
        page.click("#layQuad")

        # ---- 8. comparison overlay -----------------------------------------
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

        # ---- 9. guided walk (close the overlay first: it would intercept) --
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

        # ---- 10. nothing else went wrong ----------------------------------
        assert_no_js_errors(checks, errors, "console: zero uncaught JS errors")
        unexpected = [m for m in console_errors if CSP_BLOCK_MARKER not in m]
        check("console: zero console errors at all",
              not console_errors, "; ".join(unexpected[:3]))
        browser.close()

    checks.finish()


if __name__ == "__main__":
    env_base = os.environ.get("E2E_BASE")
    if env_base:
        run(env_base.rstrip("/"))
    else:
        with open_studio() as base:
            run(base)
