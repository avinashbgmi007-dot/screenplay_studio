"""Browser walk for the six preview-next worlds (design artifacts, shared demo payload).

Self-hosted by default (demo craft model, throwaway projects dir — no llama-server
needed); set E2E_BASE to sweep against an already-running studio instead.

Run:  python tests/e2e_browser_preview_next.py
Needs: pip install playwright && python -m playwright install chromium
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_browser_common import Checks, assert_no_js_errors, launch, open_studio
from playwright.sync_api import sync_playwright

WORLDS = ["ledger", "midnight", "screening", "quarterly", "terminal", "studio-wall"]

# per-world finder params (each world names its own finding rows / desk pages)
FINDING_SEL = {
    "ledger": '.finding[data-finding="1"]',
    "midnight": '.case-note[data-finding="1"]',
    "screening": '.slide[data-slide-i="0"]',          # slides: only the current one shows
    "quarterly": '.item[data-finding="1"]',
    "terminal": '.warnline[data-finding="1"]',
    "studio-wall": '.cardpin[data-finding="1"]',
}
PAGE_SEL = {
    "ledger": ".page",
    "midnight": ".page",
    "screening": ".strip-page",
    "quarterly": ".sheet",
    "terminal": ".scenebuf",
    "studio-wall": ".sheet",
}
PAGE_COUNT = 4


def walk_world(checks, page, errors, w):
    tag = w
    page.goto(f"{base}/preview-next/{w}.html")

    # journey: shelf is the first paint; the upload moment resolves onto the desk
    checks.check(f"{tag}: shelf is first paint",
                 page.locator('[data-screen="shelf"].active').count() == 1)
    page.locator('[data-screen="shelf"] [data-open]').click()
    checks.check(f"{tag}: upload moment shows", page.locator('[data-screen="upload"].active').count() == 1)
    page.locator("#submit-btn").click()
    page.wait_for_timeout(1300)
    checks.check(f"{tag}: desk is the default landing after submit",
                 page.locator('[data-room="desk"].active').count() == 1)
    checks.check(f"{tag}: all {PAGE_COUNT} script pages render",
                 page.locator(PAGE_SEL[tag]).count() == PAGE_COUNT)

    # feedback lifecycle: empty / running / complete all reachable from the review bar
    page.locator('#pv [data-go="feedback"]').click()
    for state in ("empty", "running", "complete"):
        page.locator(f'#pv [data-fb="{state}"]').click()
        checks.check(f"{tag}: feedback {state} renders",
                     page.locator(f'[data-state="{state}"]').is_visible())
    page.locator('#pv [data-fb="complete"]').click()

    # bridges: Locate flips to the desk and flashes the exact scene; Discuss pre-fills
    page.locator(f'{FINDING_SEL[tag]} [data-act="locate"]').first.click()
    checks.check(f"{tag}: Locate flips to the desk",
                 page.locator('[data-room="desk"].active').count() == 1)
    checks.check(f"{tag}: scene flash applied", page.locator(".flash-target").count() == 1)
    page.locator('#pv [data-go="feedback"]').click()
    page.locator(f'{FINDING_SEL[tag]} [data-act="discuss"]').first.click()
    checks.check(f"{tag}: Discuss opens co-write with the quote pre-filled",
                 page.locator("#in-quote").is_visible()
                 and len(page.locator("#in-quote-text").inner_text().strip()) > 20)
    page.keyboard.press("Escape")
    checks.check(f"{tag}: Esc dismisses the quote", not page.locator("#in-quote").is_visible())

    # idea room: chips tuck to the rail on first input, restore on clear
    page.locator('#pv [data-go="idea"]').click()
    ta = page.locator("#idea-content")
    chips = page.locator(".chips")
    ta.fill("a bird wakes when she sings")
    checks.check(f"{tag}: chips tuck away on input",
                 "tucked" in (chips.get_attribute("class") or ""))
    ta.fill("")
    checks.check(f"{tag}: chips restore on clear",
                 "tucked" not in (chips.get_attribute("class") or ""))

    # composer grows with the writing
    page.locator('#pv [data-go="cowrite"]').click()
    box = page.locator("#input")
    before = box.bounding_box()["height"]
    box.fill("line one\nline two\nline three")
    after = box.bounding_box()["height"]
    checks.check(f"{tag}: composer grows multi-line", after > before + 10)

    assert_no_js_errors(checks, errors, f"{tag}: zero JS errors")


if __name__ == "__main__":
    checks = Checks()
    with open_studio() as base, sync_playwright() as pw:
        browser, page, errors = launch(pw)
        # gallery first
        page.goto(f"{base}/preview-next/index.html")
        checks.check("gallery serves with six world links",
                     page.locator("a.card[href*='.html']").count() == 6)
        for w in WORLDS:
            walk_world(checks, page, errors, w)
        browser.close()
    checks.finish()
