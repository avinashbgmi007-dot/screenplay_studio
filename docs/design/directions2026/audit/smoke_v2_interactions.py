#!/usr/bin/env python
# V2-specific interaction battery: keyboard activation, bidirectional locate,
# tapesticky pulse, act-reel expansion, focus visibility. DOM/class assertions only.
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'tests')))
from playwright.sync_api import sync_playwright

DIR = os.path.dirname(os.path.abspath(__file__)).rsplit(os.sep + 'audit', 1)[0]
URL = 'file:///' + os.path.join(DIR, '4-screening-room-v2.html').replace('\\', '/')

def run():
    fails = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(URL)
        page.wait_for_timeout(400)

        # 1. keyboard: focus a finding line, press Enter -> its dnote lights
        fl = page.locator('.fl[data-k="watch"]')
        fl.focus()
        page.keyboard.press('Enter')
        page.wait_for_timeout(400)
        if not page.locator('.dnote[data-k="watch"]').evaluate('el => el.classList.contains("lit")'):
            print('FAIL: Enter on .fl[watch] did not light its dnote'); fails += 1
        else:
            print('ok  Enter on finding line -> director note lights')

        # 2. keyboard: focus the dnote, press Space -> its line pulses
        page.wait_for_timeout(300)  # let lit clear
        dn = page.locator('.dnote[data-k="blocking"]')
        dn.focus()
        page.keyboard.press(' ')
        page.wait_for_timeout(300)
        if not page.locator('.fl[data-k="blocking"]').evaluate('el => el.classList.contains("pulse")'):
            print('FAIL: Space on dnote[blocking] did not pulse its line'); fails += 1
        else:
            print('ok  Space on director note -> finding line pulses')

        # 3. tapesticky Enter -> watch line pulses
        page.wait_for_timeout(3600)  # pulse clears after 3.4s
        ts = page.locator('.tapesticky')
        ts.focus()
        page.keyboard.press('Enter')
        page.wait_for_timeout(300)
        if not page.locator('.fl[data-k="watch"]').evaluate('el => el.classList.contains("pulse")'):
            print('FAIL: Enter on tapesticky did not pulse the watch line'); fails += 1
        else:
            print('ok  Enter on tape sticky -> taped line pulses')

        # 4. act reel expansion: click act ii cap -> actreel gains open
        page.locator('.actreel:not(.open) .ar-cap').first.click()
        page.wait_for_timeout(200)
        if page.locator('.actreel.open').count() != 2:
            print('FAIL: act ii did not open'); fails += 1
        else:
            print('ok  act ii expands on ar-cap click')

        # 5. keyboard reachability inventory (3 fl + 3 dnote + 7 framecard + 3 ar-cap + 1 tapesticky = 17)
        reach = page.evaluate('() => document.querySelectorAll(".fl[tabindex], .dnote[tabindex], .framecard[tabindex], .ar-cap[tabindex], .tapesticky[tabindex]").length')
        if reach != 17:
            print(f'FAIL: keyboard-reachable interactive divs = {reach} (expect 17)')
            fails += 1
        else:
            print('ok  keyboard-reachable interactive elements: 17')

        # 6. focus-visible rings exist in CSS
        css = page.evaluate('() => [...document.styleSheets].flatMap(s => { try { return [...s.cssRules].map(r => r.cssText) } catch(e) { return [] } }).join(" ")')
        for sel in ['.fl:focus-visible', '.framecard:focus-visible', '.dnote:focus-visible', '.tapesticky:focus-visible']:
            if sel.replace(' ', '') not in css.replace(' ', ''):
                print(f'FAIL: missing focus-visible rule for {sel}'); fails += 1
        print('ok  focus-visible rings present on all interactive families' if fails == 0 else '')

        real = [e for e in errors if 'favicon' not in e.lower()]
        if real:
            print(f'FAIL: console errors: {real[:3]}'); fails += 1
        else:
            print('ok  zero console errors')
        browser.close()
    print()
    print('V2 INTERACTION: ALL GREEN' if fails == 0 else f'V2 INTERACTION: {fails} FAILURES')
    return fails

if __name__ == '__main__':
    sys.exit(1 if run() else 0)
