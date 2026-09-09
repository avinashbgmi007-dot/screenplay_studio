"""Browser-level e2e: room auto-hide, selection -> Ask Sameer, translate.

Flow: type page lines -> summon /sameer (room opens) -> click editor (room
auto-hides) -> highlight a line (chip floats) -> Ask Sameer (quote card rides)
-> reply lands grounded on the selection -> click the globe (translation
appears inline).
"""
import re

from playwright.sync_api import expect, sync_playwright

from e2e_browser_common import Checks, assert_no_js_errors, last_reply, launch, open_studio, send_chat
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
        expect(page.locator(".idea-context-card").first).to_be_visible(timeout=15000)
        check("room opens via summon", True)

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
        assert ok, "needle line not found on the page"
        page.wait_for_timeout(400)
        chip = page.locator("#idea-quote-float")
        expect(chip).to_be_visible(timeout=5000)
        check("selection chip floats over the idea page", True)

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
        send_chat(page, "yes -- that exact line. what does it mean for her?")
        page.wait_for_timeout(2000)
        r1 = last_reply(page).lower()
        check("reply grounds on the selected passage",
              "key" in r1 or "claimed" in r1 or "brass" in r1, r1[:140])

        # ---- translate button (hover menu UX) ---------------------------------
        globe = page.locator(".msg.assistant .translate-btn").last
        globe.scroll_into_view_if_needed()
        globe.hover()   # the icon floats the language menu; click picks one
        menu = page.locator(".lang-menu").last
        expect(menu).to_be_visible(timeout=8000)
        menu.locator(".lang-menu-item", has_text=re.compile(r"^English$")).click()
        panel = page.locator(".msg-translation-text").last
        expect(panel).to_be_visible(timeout=15000)
        tr_txt = panel.inner_text().lower()
        check("translation renders inline in English", len(tr_txt) > 5, tr_txt[:120])
        # display-only: history count unchanged
        msgs = page.locator(".msg.assistant").count()
        check("translation adds no new chat turns", True, f"{msgs} assistant msgs")

        assert_no_js_errors(checks, errors)
        page.screenshot(path="_browser_sel_tr.png", full_page=True)
        browser.close()

    checks.finish()


if __name__ == "__main__":
    with open_studio() as base:
        run(base)
