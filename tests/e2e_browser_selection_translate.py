"""Browser-level e2e: room auto-hide, selection -> Ask Sameer, translate.

Flow: type page lines -> summon /sameer (room opens) -> click editor (room
auto-hides) -> highlight a line (chip floats) -> Ask Sameer (quote card rides)
-> reply lands grounded on the selection -> click the globe (translation
appears inline).
"""
import re

from playwright.sync_api import expect, sync_playwright

from e2e_browser_common import (Checks, assert_no_js_errors, clicked, last_reply,
                                launch, open_studio, seen_visible, send_chat)
L1 = "A courier in Mumbai discovers her delivery bag swaps whatever is inside with an object from regret."
L2 = "She keeps one swapped item: a brass key nobody has claimed."

checks = Checks()
check = checks.ok


def run(base):
    with sync_playwright() as p:
        browser, page, errors = launch(p)

        page.goto(base, wait_until="networkidle")
        page.locator("#new-idea-btn").click()
        page.wait_for_timeout(400)

        ed = page.locator("#idea-content")
        ed.click()
        ed.type(L1 + "\n" + L2 + "\n/sameer", delay=3)
        page.wait_for_timeout(1100)
        # "room opens via summon" — assert the ROOM actually opened. The throwing
        # wait only proved a context card appeared, and `check(name, True)`
        # asserted nothing, so a summon that painted a card but never opened the
        # drawer passed. `#room-drawer.open` is the app's own definition of open
        # (the same test the auto-hide check below uses).
        card_ok = seen_visible(page.locator(".idea-context-card").first, timeout=15000)
        room_open = "open" in (page.locator("#room-drawer").get_attribute("class") or "")
        check("room opens via summon", card_ok and room_open,
              f"contextCard={card_ok} drawerOpen={room_open}")

        # ---- auto-hide: clicking the editor dismisses the drawer -------------
        ed.click(position={"x": 10, "y": 10})
        page.wait_for_timeout(500)
        drawer_open = page.locator("#room-drawer.open").count()
        check("room auto-hides when the editor is clicked", drawer_open == 0,
              f"open drawers={drawer_open}")

        # ---- selection -> floating chip --------------------------------------
        target = page.locator("#idea-content")
        # select L2 by triple-clicking its line region (select all then narrow:
        # use keyboard select of the last line via shift+home after End)
        # deterministic selection (soft-wrap makes Home/End visual-line keys,
        # so keyboard navigation selects arbitrary fragments). setSelectionRange
        # reproduces exactly what a writer's mouse-drag would capture.
        sel_text = "She keeps one swapped item: a brass key nobody has claimed."
        ok = page.evaluate(
            """([needle]) => {
              const el = document.querySelector('#idea-content');
              const i = el.value.indexOf(needle);
              if (i < 0) return false;
              el.focus();
              el.setSelectionRange(i, i + needle.length);
              return true;
            }""",
            [sel_text])
        # A bare `assert` here was a CRASH-shaped guard: it aborted the run and
        # masked every later check — and because `finish()` sits at the END of
        # run(), a plain `return` would have exited 0 and SWALLOWED the failure.
        # finish() exits 1, so the gap is named and the run stays honest.
        if not ok:
            check("selection: the target line is present to select", False,
                  "needle line not found on the page — the selection contract "
                  "was NOT exercised")
            checks.finish()
        page.wait_for_timeout(400)
        chip = page.locator("#idea-quote-float")
        # "floats OVER the idea page" — assert it is POSITIONED, not merely
        # present. `to_be_visible()` is satisfied by a zero-size element, and the
        # old `check(name, True)` was satisfied by anything at all.
        chip_ok = seen_visible(chip, timeout=5000)
        box = chip.bounding_box() or {}
        floats = box.get("width", 0) > 0 and box.get("height", 0) > 0
        check("selection chip floats over the idea page", chip_ok and floats,
              f"visible={chip_ok} box={box}")

        # ---- Ask Sameer: quote card + grounded reply --------------------------
        got = chip.get_attribute("data-text")
        check("chip carries the exact highlighted passage", got == sel_text, f"got={got!r}")
        chip.click()
        page.wait_for_timeout(800)
        quote_card = page.locator(".quote-card, .composer-quote, [class*='quote']").first
        composer_txt = page.locator("#input").input_value()
        check("ask pre-filled referencing the selection",
              "brass key" in composer_txt.lower() or "part" in composer_txt.lower(),
              composer_txt[:80])
        # Bounded: if the drawer never opened the composer is display:none, and an
        # unguarded fill() would time out and ABORT the run — masking the named
        # failure above and every check below (mutation-verified with the
        # drawer-open class removed).
        sent = send_chat(page, "yes -- that exact line. what does it mean for her?")
        check("ask: the composer accepted the turn", sent,
              "the composer was not usable — the room drawer never opened")
        page.wait_for_timeout(2000)
        r1 = last_reply(page).lower()
        check("reply grounds on the selected passage",
              "key" in r1 or "claimed" in r1 or "brass" in r1, r1[:140])

        # ---- translate button (hover menu UX) ---------------------------------
        # translating is DISPLAY-ONLY: it must not add a chat turn. Capture the
        # turn count before the action so the check below can actually compare
        # (it used to be `check(name, True)` — a hardcoded pass that carried the
        # count in its detail but never asserted anything about it).
        turns_before = page.locator(".msg.assistant").count()
        globe = page.locator(".msg.assistant .translate-btn").last
        # Bounded end-to-end: with no assistant reply there is no translate button,
        # and the old scroll_into_view / hover / expect chain RAISED — aborting the
        # run and masking every later check (mutation-verified: with the drawer-open
        # class removed, the suite died here before printing its summary).
        try:
            globe.scroll_into_view_if_needed(timeout=4000)
            globe.hover(timeout=4000)
            menu_open = seen_visible(page, ".lang-menu", timeout=8000)
        except Exception:
            menu_open = False
        picked = menu_open and clicked(
            page.locator(".lang-menu").last.locator(
                ".lang-menu-item", has_text=re.compile(r"^English$")), timeout=4000)
        panel_ok = picked and seen_visible(page, ".msg-translation-text", timeout=15000)
        tr_txt = (page.locator(".msg-translation-text").last.inner_text().lower()
                  if panel_ok else "")
        check("translation renders inline in English",
              panel_ok and len(tr_txt) > 5,
              f"menuOpen={menu_open} picked={picked} text={tr_txt[:120]}")
        # display-only: history count unchanged
        msgs = page.locator(".msg.assistant").count()
        check("translation adds no new chat turns", msgs == turns_before,
              f"before={turns_before} after={msgs}")

        assert_no_js_errors(checks, errors)
        page.screenshot(path="_browser_sel_tr.png", full_page=True)
        browser.close()

    checks.finish()


if __name__ == "__main__":
    with open_studio() as base:
        run(base)
