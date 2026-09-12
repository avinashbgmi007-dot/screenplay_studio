#!/usr/bin/env python
# v2.1 HARVEST interaction battery: take-safety loop (apply/undo/re-check/holds),
# fresh strip copy on re-apply, seat swap + Esc, lamp truth cycle, positional
# select-to-ask, note actions, graduation receipt, orphan-free rail, keyboard
# inventory. DOM/class/text assertions only, no screenshots.
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'tests')))
from playwright.sync_api import sync_playwright

DIR = os.path.dirname(os.path.abspath(__file__)).rsplit(os.sep + 'audit', 1)[0]
URL = 'file:///' + os.path.join(DIR, '4-screening-room-v2.1.html').replace('\\', '/')

def run():
    fails = 0
    def ok(cond, label):
        nonlocal fails
        if cond:
            print(f'ok  {label}')
        else:
            print(f'FAIL {label}'); fails += 1

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(URL)
        page.wait_for_timeout(400)

        # 0. structural: grafts present exactly once, strip/seat/card hidden at rest, rail has no orphan nodes
        ok(page.locator('#takecard').count() == 1, 'takecard present once')
        ok(page.locator('#change-strip').count() == 1, 'change strip present once')
        ok(page.locator('#lamp-truth').count() == 1, 'lamp truth present once')
        ok(page.locator('.rail .lamptruth').count() == 0, 'lamp truth left the rail (deck-anchored now)')
        ok(page.locator('#readingseat').count() == 1, 'reading seat present once')
        ok(not page.locator('#change-strip').is_visible(), 'strip hidden at rest')
        ok(not page.locator('#readingseat').is_visible(), 'reading seat hidden at rest')
        ok(not page.locator('#takecard').is_visible(), 'takecard collapsed at rest (rail belongs to the notes)')
        ok(page.locator('.cuesheet').first.is_visible(), 'cue sheet visible at rest')
        orphans = page.evaluate('() => document.querySelectorAll(".rail > .key, .rail > h4, .rail > p, .rail > .cue").length')
        ok(orphans == 0, f'rail has no orphan note fragments (found {orphans})')
        dups = page.evaluate('() => document.querySelectorAll(".dnote[data-k=\\"watch\\"]").length')
        ok(dups == 1, f'exactly one watch dnote (found {dups})')
        htag = page.locator('.dnote[data-k="watch"] .holds-tag')
        ok(htag.count() == 1 and not htag.is_visible(), 'holds-tag present, hidden until re-check')
        # a11y structure: notes are NOT button-role containers (nested-interactives fix);
        # locate affordance is a real button; no role=button on .dnote
        ok(page.evaluate('() => document.querySelectorAll(".dnote[role=button]").length') == 0, 'no role=button on note containers (4.1.2)')
        ok(page.locator('.dnote[data-k="watch"] .locate').count() == 1, 'watch note has a real locate button')
        # live regions scoped: status on the strip text block + pulse + lamp deck
        ok(page.evaluate('() => document.querySelectorAll("#change-strip [role=status]").length') == 1, 'strip live region scoped to text block')
        ok(page.evaluate('() => document.getElementById("recheck-pulse").getAttribute("role")') == 'status', 're-check pulse announces (role=status)')
        ok(page.evaluate('() => document.getElementById("lamp-status").getAttribute("aria-live")') == 'polite', 'lamp deck is a live region')

        # 1. open the takecard via the note's own action (new take), then apply
        page.locator('.dnote[data-k="watch"] [data-act="newtake"]').click()
        page.wait_for_timeout(250)
        ok(page.locator('#takecard').is_visible(), 'new take action opens the collapsed card')
        page.locator('.tk-apply').click()
        page.wait_for_timeout(250)
        line = page.locator('.fl[data-k="watch"]')
        ok("like a letter he's read a hundred times" in line.inner_text(), 'apply: watch line carries the new take')
        ok(line.evaluate('el => el.classList.contains("taken")'), 'apply: line marked .taken')
        ok(page.locator('#change-strip').is_visible(), 'apply: change strip visible on the page')
        title = page.locator('#change-strip .cs-title').inner_text().lower()
        ok('take applied' in title, 'apply: strip title is the fresh applied copy')
        # severity honesty: the dot keeps its severity color (take never repaints it)
        dot_bg = line.evaluate('el => getComputedStyle(el.querySelector(".dot")).backgroundColor')
        ok(dot_bg == 'rgb(196, 86, 58)', f'apply: severity dot stays high-severity red (got {dot_bg})')
        # focus never drops: after apply, focus sits on the strip undo
        ok(page.evaluate('() => document.activeElement === document.querySelector(\'#change-strip [data-cs="undo"]\')'),
           'focus managed: after apply, focus on the strip undo')

        # 2. undo -> line restored, strip hidden, focus returned to the apply button
        page.locator('#change-strip [data-cs="undo"]').click()
        page.wait_for_timeout(250)
        ok(line.inner_text().strip() == '(a beat — he turns the pocket watch over in his palm)', 'undo: original wording restored')
        ok(not line.evaluate('el => el.classList.contains("taken")'), 'undo: .taken removed')
        ok(not page.locator('#change-strip').is_visible(), 'undo: strip hidden')
        ok(page.evaluate('() => document.activeElement === document.querySelector(".tk-apply")'),
           'focus managed: after undo, focus back on the re-armed apply')

        # 3. re-apply (fresh-copy regression), then re-check -> honest .holds state
        page.locator('.tk-apply').click()
        page.wait_for_timeout(250)
        title = page.locator('#change-strip .cs-title').inner_text().lower()
        ok('take applied' in title and 're-checked' not in title, 're-apply: strip copy restored (stale-copy regression fixed)')
        page.locator('#change-strip [data-cs="recheck"]').click()
        page.wait_for_timeout(500)
        ok(page.locator('#recheck-pulse').is_visible(), 're-check: thinking pulse shows')
        page.wait_for_timeout(2300)
        note = page.locator('.dnote[data-k="watch"]')
        ok(note.evaluate('el => el.classList.contains("holds")'), 're-check: note holds (still-present state)')
        ok(not note.evaluate('el => el.classList.contains("cleared")'), 're-check: NOT cleared — finding stands')
        ok(page.locator('.dnote[data-k="watch"] .holds-tag').is_visible(), 're-check: holds-tag visible (honest copy)')
        st = page.locator('#change-strip .cs-title').inner_text().lower()
        ok('still watching' in st and 'finding stands' in st, 're-check: strip carries the still-watching verdict')
        ok(not st.startswith('✓'), 're-check: no resolution glyph on a non-resolution verdict')
        # the pick chip leaves the AX tree when held (display:none, not opacity)
        ok(not page.locator('.dnote[data-k="watch"] .dpick').is_visible(), 'holds: pick chip fully removed (AX tree clean)')
        # undo clears holds too
        page.locator('#change-strip [data-cs="undo"]').click()
        page.wait_for_timeout(250)
        ok(not note.evaluate('el => el.classList.contains("holds")'), 'undo after re-check: holds cleared')

        # 4. tk-keep dismisses the card WITHOUT summoning (no naggy auto-summon)
        page.locator('.dnote[data-k="watch"] [data-act="newtake"]').click()
        page.wait_for_timeout(200)
        page.locator('.tk-keep').click()
        page.wait_for_timeout(250)
        ok(not page.locator('#takecard').is_visible(), 'keep the shot: takecard dismissed')
        ok(not page.locator('.rail').evaluate('el => el.classList.contains("fullreading")'),
           'keep the shot: no uninvited seat summon (writer decides when to talk)')

        # 5. SEAT SWAP via positional select-to-ask (the real UX path):
        #    selection on the page -> float at the rect -> ask the room -> seat
        page.evaluate('''() => {
          const target = [...document.querySelectorAll('.frame .sline.dial')][0];
          const range = document.createRange();
          range.selectNodeContents(target);
          const sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
          target.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
        }''')
        page.wait_for_timeout(200)
        sfloat = page.locator('.selectfloat')
        ok(sfloat.is_visible(), 'select: float rises at the selection')
        ok(page.evaluate('() => document.querySelector(".selectfloat").dataset.quote.startsWith("You said eleven")'),
           'select: quote captured')
        sfloat.locator('[data-sf="ask"]').click()
        page.wait_for_timeout(200)
        rail = page.locator('.rail')
        ok(rail.evaluate('el => el.classList.contains("fullreading")'), 'ask the room: seat summoned')
        ok(not page.locator('.cuesheet').first.is_visible(), 'seat swap: cue sheet hidden')
        ok(page.locator('#readingseat').is_visible(), 'seat swap: Sameer seated')
        ok(page.evaluate('() => document.activeElement === document.getElementById("readingseat").querySelector("input")'),
           'seat swap: composer focused for the ask')
        seeded = page.evaluate('() => document.getElementById("readingseat").querySelector("input").value')
        ok(seeded.startswith('About "You said eleven'), 'ask the room: composer seeded with the quoted text')
        ok(not sfloat.is_visible(), 'ask the room: float dismissed, selection cleared')
        # amber stays Sameer's in the seat (no moon theft — Sushruta's color is his alone)
        seat_who_color = page.evaluate('() => getComputedStyle(document.querySelector(".readingseat .who")).color')
        ok(seat_who_color == 'rgb(224, 180, 92)', f'seat swap: Sameer keeps amber (got {seat_who_color})')
        # Esc returns the seat AND the focus (round trip)
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)
        ok(not rail.evaluate('el => el.classList.contains("fullreading")'), 'Esc: seat returned, cue sheet back')
        ok(page.locator('.cuesheet').first.is_visible(), 'Esc: cue sheet visible again')
        ok(page.evaluate('() => document.activeElement !== document.body'), 'Esc: focus restored, not dropped to body')

        # 6. NACTS: consider it / cleared (writer's explicit dismissal)
        page.locator('.dnote[data-k="watch"] [data-act="consider"]').click()
        page.wait_for_timeout(150)
        ok(page.locator('.dnote[data-k="watch"] [data-act="consider"]').inner_text().startswith('✓'),
           'consider it: noted for tonight')
        page.locator('.dnote[data-k="watch"] [data-act="clear"]').click()
        page.wait_for_timeout(150)
        note = page.locator('.dnote[data-k="watch"]')
        ok(note.evaluate('el => el.classList.contains("cleared")'), 'cleared: note dismissed')
        ok(page.locator('.dnote[data-k="watch"] .cleared-tag').is_visible(), 'cleared: teal receipt visible')
        # distinctness: cleared must NOT show the holds tag
        ok(not page.locator('.dnote[data-k="watch"] .holds-tag').is_visible(), 'cleared: holds-tag stays hidden (states distinct)')
        # exclusivity regression: cleared AFTER a hold records both truths, never stacks both tags
        page.locator('.dnote[data-k="watch"] [data-act="newtake"]').click()
        page.wait_for_timeout(150)
        page.locator('.tk-apply').click()
        page.wait_for_timeout(150)
        page.locator('#change-strip [data-cs="recheck"]').click()
        page.wait_for_timeout(2800)
        page.locator('.dnote[data-k="watch"] [data-act="clear"]').click()
        page.wait_for_timeout(150)
        ok(not page.locator('.dnote[data-k="watch"] .holds-tag').is_visible(),
           'cleared supersedes holds (writer decides; tags never stack)')
        ct = page.locator('.dnote[data-k="watch"] .cleared-tag').inner_text().lower()
        ok('writer cleared' in ct and 'still watching' in ct, 'honest receipt: writer cleared · machine still watching')

        # 7. LAMP TRUTH (deck-anchored popover): closed at rest, opens from the
        #    deck lamp, cycles real -> demo -> dead -> real, deck follows, Esc closes
        lamp = page.locator('#lamp-truth')
        ok(not lamp.is_visible(), 'lamp truth: popover closed at rest (rail belongs to the notes)')
        page.locator('#lamp-status').click()
        page.wait_for_timeout(150)
        ok(lamp.is_visible(), 'lamp truth: deck lamp opens the popover above the deck')
        lamp.locator('button').click(); page.wait_for_timeout(120)
        ok(lamp.evaluate('el => el.classList.contains("demo")'), 'lamp cycle 1: demo craft model')
        ok('demo craft model' in page.locator('#lamp-status').inner_text().lower(), 'lamp cycle 1: deck follows')
        lamp.locator('button').click(); page.wait_for_timeout(120)
        ok(lamp.evaluate('el => el.classList.contains("dead")'), 'lamp cycle 2: unreachable, honest')
        ok('unreachable' in page.locator('#lamp-status').inner_text().lower(), 'lamp cycle 2: deck follows')
        lamp.locator('button').click(); page.wait_for_timeout(120)
        ok(lamp.evaluate('el => !el.classList.contains("demo") && !el.classList.contains("dead")'),
           'lamp cycle 3: back to real model verified')
        ok('model verified' in page.locator('#lamp-status').inner_text().lower(), 'lamp cycle 3: deck restored')
        page.keyboard.press('Escape')
        page.wait_for_timeout(150)
        ok(not lamp.is_visible(), 'lamp truth: Esc closes the popover (cascade: lamp before seat)')
        ok(page.evaluate('() => document.activeElement === document.getElementById("lamp-status")'),
           'lamp truth: focus returns to the deck lamp')
        # keyboard path: Enter on the deck lamp also toggles
        page.locator('#lamp-status').focus()
        page.keyboard.press('Enter')
        page.wait_for_timeout(150)
        ok(lamp.is_visible(), 'lamp truth: Enter on the deck lamp opens it (keyboard-operable)')
        page.keyboard.press('Escape')
        page.wait_for_timeout(150)

        # 8. GRADUATION RECEIPT (idea state)
        page.locator('#mockbar button[data-s="idea"]').click()
        page.wait_for_timeout(300)
        before = page.locator('#s-idea .beats .b').count()
        page.locator('.idea-side .sam-presence .ask button').click()
        page.wait_for_timeout(200)
        after = page.locator('#s-idea .beats .b').count()
        ok(after == before + 1 and 'graduated' in page.locator('#s-idea .beats .b').last.inner_text().lower(),
           f'graduation receipt appended ({before} -> {after} beats)')

        # 9. keyboard inventory: div-based interactives are now 14
        #    (3 fl + 7 framecard + 3 ar-cap + 1 tapesticky) — the 3 dnote containers
        #    dropped their div-button pattern for real .locate <button>s (4.1.2 fix),
        #    and graft buttons (nacts, tk-*, cs-*, lamp, seat send) are all real <button>s
        reach = page.evaluate('() => document.querySelectorAll(".fl[tabindex], .framecard[tabindex], .ar-cap[tabindex], .tapesticky[tabindex]").length')
        ok(reach == 14, f'keyboard-reachable interactive divs: {reach} (expect 14 — dnote locate is a real button now)')
        # and every .locate button is genuinely focusable + labeled
        locs = page.evaluate('() => [...document.querySelectorAll(".dnote .locate")].every(b => b.tabIndex >= 0 && b.getAttribute("aria-label"))')
        ok(locs, 'all three locate buttons focusable with aria-labels')

        real = [e for e in errors if 'favicon' not in e.lower()]
        ok(not real, f'zero console errors {real[:2] if real else ""}')
        browser.close()
    print()
    print('V2.1 INTERACTION: ALL GREEN' if fails == 0 else f'V2.1 INTERACTION: {fails} FAILURES')
    return fails

if __name__ == '__main__':
    sys.exit(1 if run() else 0)
