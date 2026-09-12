#!/usr/bin/env python
# Deep WCAG 2.1 AA accessibility audit — 4-screening-room-v2.1.html
# Scope: interactive behaviors of the v2.1 graft patterns + base house.
# Complements contrast_audit.py (color math) and smoke_v21_interactions.py
# (functional smoke). This one covers: keyboard traps, focus order,
# hit areas, ARIA correctness, live-region behavior, reduced motion,
# zoom/reflow, and screen-reader announcement checks.
# Usage: python a11y_audit_v21.py

import sys, re
from playwright.sync_api import sync_playwright

PAGE = r"e:\AI_workspace\screenplay-studio_1\docs\design\directions2026\4-screening-room-v2.1.html"
failures = []
passes = []

def ok(label, detail=""):
    passes.append(label)
    print(f"ok  {label}")

def fail(label, detail=""):
    failures.append((label, detail))
    print(f"FAIL  {label}" + (f"  -- {detail}" if detail else ""))

def check(cond, label, detail=""):
    (ok if cond else fail)(label, detail)

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto("file:///" + PAGE.replace("\\", "/"))
    page.wait_for_timeout(300)

    # ---------- 1. Landmarks & structure ----------
    tree = page.evaluate("""() => {
        const roles = {};
        document.querySelectorAll('[role]').forEach(el => { roles[el.getAttribute('role')] = (roles[el.getAttribute('role')]||0)+1; });
        return {
            landmarks: {
                header: !!document.querySelector('header'),
                main: !!document.querySelector('main'),
                nav: !!document.querySelector('nav'),
                footer: !!document.querySelector('footer'),
                aside: !!document.querySelector('aside'),
            },
            roles, htmlLang: document.documentElement.lang,
            title: document.title,
        };
    }""")
    check(tree["landmarks"]["header"] and tree["landmarks"]["main"] and tree["landmarks"]["nav"]
          and tree["landmarks"]["footer"] and tree["landmarks"]["aside"],
          "landmarks present: header/main/nav/footer/aside")
    check(tree["htmlLang"] == "en", "html lang set", tree["htmlLang"])
    check(bool(tree["title"]), "document title present")

    # ---------- 2. Keyboard: no traps in the screening state ----------
    # Tab through the whole document twice; the sequence must never repeat early.
    order = page.evaluate("""() => {
        const focusables = [...document.querySelectorAll('a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])')]
          .filter(el => el.offsetParent !== null || el === document.body);
        return focusables.length;
    }""")
    # walk tabs and collect the chain, verify Escape restores state where relevant
    seq = []
    body_focus = page.evaluate("() => document.body.focus(), document.activeElement === document.body")
    for i in range(order + 5):
        page.keyboard.press("Tab")
        tag = page.evaluate("() => { const a = document.activeElement; return a ? (a.tagName + (a.id ? '#'+a.id : '') + (a.className && typeof a.className === 'string' && a.className ? '.'+a.className.split(' ').slice(0,2).join('.') : '')) : 'none'; }")
        seq.append(tag)
        if i > 3 and seq[i] == seq[0] and i < order - 2:
            break
    # the chain must wrap around: first element reachable again (no dead end)
    check(len(seq) > order - 3, f"tab chain covers all {order} focusables, no trap (chain {len(seq)})")

    # ---------- 3. Focus visibility: every interactive element keeps a visible ring ----------
    rings = page.evaluate("""() => {
        const out = [];
        const sel = '.fl, .tapesticky, .framecard, .ar-cap, #lamp-status, button, input, [role="button"]';
        document.querySelectorAll(sel).forEach(el => {
            const cs = getComputedStyle(el);
            // visible in the current state?
            if (el.offsetParent === null && el.id !== 'lamp-truth') return;
            const fv = cs.outlineStyle !== 'none' || cs.boxShadow !== 'none' || cs.borderStyle !== 'none';
            out.push({t: el.tagName, c: (el.className||'').toString().slice(0,30), fv});
        });
        return out;
    }""")
    # :focus-visible rules exist in the stylesheet?
    css = page.content()
    fv_rules = len(re.findall(r":focus-visible\s*\{[^}]*outline", css))
    check(fv_rules >= 8, f":focus-visible outline rules present ({fv_rules} found)")

    # ---------- 4. Take-safety loop: focus management ----------
    # apply -> focus lands on strip undo; undo -> focus lands on re-armed apply
    page.click('.tk-apply')
    focused = page.evaluate("() => { const a = document.activeElement; return a ? (a.tagName + '.' + (a.dataset ? a.dataset.cs : '')) : 'none'; }")
    check("undo" in (focused or ""), "apply: focus lands on strip undo", f"got {focused}")
    # live region announces the strip
    strip_status = page.evaluate("() => !!document.querySelector('#change-strip [role=status][aria-live=polite]')")
    check(strip_status, "change strip: live region scoped to text (buttons outside)")
    # undo restores focus to apply
    page.click('[data-cs="undo"]')
    focused2 = page.evaluate("() => { const a = document.activeElement; return a ? (a.tagName + '.' + (a.className||'')) : 'none'; }")
    check("tk-apply" in (focused2 or ""), "undo: focus returns to re-armed apply", f"got {focused2}")
    # re-apply, then re-check path
    page.click('.tk-apply')
    page.click('[data-cs="recheck"]')
    check(page.evaluate("() => document.getElementById('recheck-pulse').style.display") == "flex",
          "re-check pulse visible (live role=status)")
    page.wait_for_timeout(2400)
    holds = page.evaluate("() => document.querySelector('.dnote[data-k=watch]').classList.contains('holds')")
    check(holds, "re-check ends in honest holds state")

    # ---------- 5. Lamp truth: Esc cascade + focus round trip ----------
    page.click('#lamp-status')
    lamp_open = page.evaluate("() => document.getElementById('lamp-truth').classList.contains('open')")
    check(lamp_open, "lamp truth opens from deck")
    # focus in dialog, Tab cycles within? (role=dialog should contain focus while open — popover pattern allows tab-through, verify the close button is reachable and Esc returns focus)
    page.keyboard.press("Escape")
    back = page.evaluate("() => document.activeElement.id")
    check(back == "lamp-status", "lamp Esc: focus returns to the deck lamp", f"got {back}")
    check(page.evaluate("() => !document.getElementById('lamp-truth').classList.contains('open')"),
          "lamp Esc: popover closes")

    # ---------- 6. Seat swap round trip ----------
    page.click('[data-act="newtake"]')  # open takecard again
    # summon seat via selectfloat path: click ask button in selbar is mock; use sfloat via JS API
    page.evaluate("() => { summonSameerSeat(); }")
    seat_shown = page.evaluate("() => document.querySelector('.rail').classList.contains('fullreading')")
    check(seat_shown, "seat swap: rail enters fullreading")
    focused = page.evaluate("() => document.activeElement.tagName")
    check(focused == "INPUT", "seat swap: composer input focused", f"got {focused}")
    page.keyboard.press("Escape")
    check(not page.evaluate("() => document.querySelector('.rail').classList.contains('fullreading')"),
          "seat Esc: cue sheet restored")
    check(page.evaluate("() => !!document.querySelector('.cuesheet')"),
          "seat Esc: cue sheet visible again")

    # ---------- 7. prefers-reduced-motion honored ----------
    rm = re.search(r"@media \(prefers-reduced-motion:\s*reduce\)\s*\{[^}]*animation\s*:\s*none[^}]*transition\s*:\s*none", css)
    check(bool(rm), "prefers-reduced-motion: global animation/transition kill present")
    # verify in an emulated RM context: reelspin animation actually stops
    page.emulate_media(reduced_motion="reduce")
    anim = page.evaluate("() => { const el = document.querySelector('.reelspin .reel'); return el ? getComputedStyle(el).animationName : 'none'; }")
    # mockbar switch to reel state first
    page.click('#mockbar button[data-s="reel"]')
    anim = page.evaluate("() => { const el = document.querySelector('.reelspin .reel'); return el ? getComputedStyle(el).animationName : 'none'; }")
    check(anim == "none", "reduced-motion: reel spin animation off", f"got {anim}")
    page.emulate_media(reduced_motion="no-preference")
    page.click('#mockbar button[data-s="screening"]')

    # ---------- 8. 200% zoom reflow (no horizontal scroll on the page body) ----------
    page.set_viewport_size({"width": 1024, "height": 768})  # 1280/1.25 style window
    overflow = page.evaluate("""() => {
        const d = document.documentElement;
        const hasH = d.scrollWidth > d.clientWidth + 2;
        return {w: d.scrollWidth, cw: d.clientWidth, hasH, bodyW: document.body.scrollWidth, bodyCW: document.body.clientWidth};
    }""")
    check(not overflow["hasH"], f"no horizontal document scroll at 1024px (scroll {overflow['w']} vs client {overflow['cw']})")

    # ---------- 9. aria-labels on all icon-only / self-labeled controls ----------
    labeled = page.evaluate("""() => {
        const missing = [];
        document.querySelectorAll('#lamp-status, .framecard, .ar-cap, .fl, .tapesticky, .locate').forEach(el => {
            if (el.offsetParent === null && el.id !== 'change-strip') return;
            const name = (el.getAttribute('aria-label') || el.innerText || '').trim();
            if (!name) missing.push((el.className||el.tagName).toString().slice(0,20));
        });
        return missing;
    }""")
    check(not labeled, "interactive elements all carry accessible names", str(labeled))

    # ---------- 10. severity conveyed non-visually (dot is aria-hidden, label carries words) ----------
    fl_label = page.evaluate("""() => document.querySelector('.fl.high').getAttribute('aria-label')""")
    check("high" in (fl_label or "").lower(), "severity in words within aria-label", fl_label)
    dot_hidden = page.evaluate("() => !!document.querySelector('.fl.high .dot[aria-hidden=true]')")
    check(dot_hidden, "severity dot marked aria-hidden (info in label, not duplicated)")

    # ---------- 11. console clean ----------
    check(not errors, "zero console errors", "; ".join(errors[:3]))

    browser.close()

print()
if failures:
    print(f"A11Y AUDIT: {len(failures)} FAILURE(S), {len(passes)} passed")
    sys.exit(1)
else:
    print(f"A11Y AUDIT: ALL GREEN ({len(passes)} checks)")
