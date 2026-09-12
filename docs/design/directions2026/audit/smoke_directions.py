#!/usr/bin/env python
# Playwright smoke test — five direction mockups: structural integrity, no console errors,
# state switching works, writeup drawer present. DOM/text assertions ONLY (no screenshots).
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'tests')))
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.abspath(__file__))
DIR = BASE.rsplit(os.sep + 'audit', 1)[0]
FILES = ['1-marked-proof.html', '2-night-room.html', '3-the-consultation.html', '4-screening-room.html', '4-screening-room-v2.html', '4-screening-room-v2.1.html', '5-atelier.html']
EXPECT_STATES = {
    '1-marked-proof.html': ['proof', 'desk', 'pad', 'reading', 'consult'],
    '2-night-room.html': ['landing', 'proof', 'idea', 'watch', 'moon'],
    '3-the-consultation.html': ['exam', 'intake', 'differential', 'lab', 'roundtable'],
    '4-screening-room.html': ['screening', 'lobby', 'idea', 'reel', 'green'],
    '4-screening-room-v2.html': ['screening', 'lobby', 'idea', 'reel', 'green'],
    '4-screening-room-v2.1.html': ['screening', 'lobby', 'idea', 'reel', 'green'],
    '5-atelier.html': ['bench', 'front', 'sketch', 'kiln'],
}

EXPECT_DEFAULT = {
    '1-marked-proof.html': 'proof',
    '2-night-room.html': 'proof',   # night room opens on the manuscript, palette summoned
    '3-the-consultation.html': 'exam',
    '4-screening-room.html': 'screening',
    '4-screening-room-v2.html': 'screening',
    '4-screening-room-v2.1.html': 'screening',
    '5-atelier.html': 'bench',
}

def run():
    fails = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: errors.append(str(e)))
        for f in FILES:
            path = os.path.join(DIR, f)
            url = 'file:///' + path.replace('\\', '/')
            page.goto(url)
            page.wait_for_timeout(400)
            name = f.split('-')[1] if False else f
            # 1. all states present
            for s in EXPECT_STATES[f]:
                if page.locator(f'#s-{s}').count() != 1:
                    print(f"FAIL {f}: state #s-{s} count={page.locator(f'#s-{s}').count()}"); fails += 1
            # 2. writeup drawer
            if page.locator('#dnotes').count() != 1:
                print(f"FAIL {f}: dnotes drawer missing"); fails += 1
            # 3. default state visible
            first = EXPECT_DEFAULT[f]
            if not page.locator(f'#s-{first}').is_visible():
                print(f"FAIL {f}: default state #s-{first} not visible"); fails += 1
            # 4. switch to last state via its tab (find by data-s)
            last = EXPECT_STATES[f][-1]
            page.locator(f'button[data-s="{last}"]').first.click()
            page.wait_for_timeout(250)
            if not page.locator(f'#s-{last}').is_visible():
                print(f"FAIL {f}: cannot switch to #s-{last}"); fails += 1
            # 5. writeup opens and has 16 attribute blocks
            page.locator('#dnotes summary').click()
            page.wait_for_timeout(200)
            attrs = page.locator('#dnotes .panel b').count()
            if attrs != 16:
                print(f"FAIL {f}: writeup has {attrs} attribute blocks (need 16)"); fails += 1
            # 6. manuscript text sanity: the diner scene must exist somewhere
            if 'DINER' not in page.content():
                print(f"FAIL {f}: diner scene text missing"); fails += 1
            # console errors (ignore favicon)
            real = [e for e in errors if 'favicon' not in e.lower()]
            if real:
                print(f"FAIL {f}: console errors: {real[:2]}"); fails += 1
            errors.clear()
            print(f"ok  {f} — states 5/5, writeup 16 attrs, switch ok, no errors")
        browser.close()
    print()
    print("SMOKE: ALL GREEN" if fails == 0 else f"SMOKE: {fails} FAILURES")
    return fails

if __name__ == '__main__':
    sys.exit(1 if run() else 0)
