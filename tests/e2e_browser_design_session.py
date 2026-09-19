"""E2E: design session console — four surfaces, dawn sync, layout modes, walk bar.
DOM/text assertions only (project rule: no screenshots).
Uses the SHARED :8500 studio deliberately (the console embeds the live app with real
project data for the design comparison; this suite never mutates project state)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright  # noqa: E402

BASE = "http://127.0.0.1:8500"  # shared studio, read-only usage in this suite

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    pg.goto(f"{BASE}/design_session.html", wait_until="networkidle")
    pg.wait_for_timeout(1200)

    # 1. All four iframes alive?
    frames = pg.eval_on_selector_all(".cell-frame iframe", "els => els.map(e => ({src: e.src.split('/').slice(-2).join('/'), ok: !!(e.contentDocument && e.contentDocument.body)}))")
    print("FRAMES:", frames)
    assert len(frames) == 4, "expected 4 iframes"
    for f in frames:
        assert f["ok"], f"frame not reachable: {f['src']}"

    # 2. Live frame actually shows the app (not a blank/error page)
    live_body_len = pg.eval_on_selector(".cell.live iframe", "e => e.contentDocument.body.innerHTML.length")
    print("live body html length:", live_body_len)
    assert live_body_len > 10000, "live frame looks empty"

    # 3. Dawn sync flips all four bodies
    pg.click("#syncDawn")
    pg.wait_for_timeout(400)
    states = pg.evaluate("""() => {
      const g = k => { const f = document.querySelector('.cell[data-key="'+k+'"] iframe');
        try { return {dawn: f.contentDocument.body.classList.contains('dawn'), dark: f.contentDocument.body.classList.contains('dark')}; }
        catch(e){ return {err: String(e)} } };
      return {nocta: g('nocta'), lumen: g('lumen'), beatwall: g('beatwall'), live: g('live')};
    }""")
    print("AFTER 1st click (dawn=true):", states)
    assert states["nocta"]["dawn"] and states["lumen"]["dawn"], "nocta/lumen should carry .dawn"
    assert states["beatwall"]["dark"], "beatwall should carry .dark for night"
    assert states["live"]["dawn"], "live should carry .dawn"

    pg.click("#syncDawn")
    pg.wait_for_timeout(400)
    states2 = pg.evaluate("""() => {
      const g = k => { const f = document.querySelector('.cell[data-key="'+k+'"] iframe');
        try { return {dawn: f.contentDocument.body.classList.contains('dawn'), dark: f.contentDocument.body.classList.contains('dark')}; }
        catch(e){ return {err: String(e)} } };
      return {nocta: g('nocta'), lumen: g('lumen'), beatwall: g('beatwall'), live: g('live')};
    }""")
    print("AFTER 2nd click (dawn=false):", states2)
    assert not states2["nocta"]["dawn"] and not states2["lumen"]["dawn"] and not states2["beatwall"]["dark"] and not states2["live"]["dawn"], "all should be back to night/default"

    # 4. Dawn actually changes the visual (bg color shift on nocta)
    bg_before = pg.eval_on_selector(".cell[data-key='nocta'] iframe", "e => getComputedStyle(e.contentDocument.body).backgroundColor")
    pg.click("#syncDawn"); pg.wait_for_timeout(300)
    bg_after = pg.eval_on_selector(".cell[data-key='nocta'] iframe", "e => getComputedStyle(e.contentDocument.body).backgroundColor")
    print(f"nocta bg: {bg_before} -> {bg_after}")
    assert bg_before != bg_after, "dawn sync must change the background"

    # 5. Layout modes
    pg.click("#layProto"); pg.wait_for_timeout(200)
    n_visible = pg.eval_on_selector_all(".cell:not([style*='display: none'])", "els => els.filter(e => getComputedStyle(e).display !== 'none').length")
    print("proto mode visible cells:", n_visible)
    assert n_visible == 3, "3proto mode should show exactly the 3 prototypes"
    pg.click("#layLive"); pg.wait_for_timeout(200)
    n_visible = pg.eval_on_selector_all(".cell", "els => els.filter(e => getComputedStyle(e).display !== 'none').length")
    print("live mode visible cells:", n_visible)
    assert n_visible == 1, "live mode should show only live"
    pg.click("#layQuad"); pg.wait_for_timeout(200)
    n_visible = pg.eval_on_selector_all(".cell", "els => els.filter(e => getComputedStyle(e).display !== 'none').length")
    print("quad mode visible cells:", n_visible)
    assert n_visible == 4, "quad mode should show all four"

    # 6. Solo button
    pg.click(".cell[data-key='lumen'] .icon-btn"); pg.wait_for_timeout(200)
    visible = pg.eval_on_selector_all(".cell", "els => els.filter(e => getComputedStyle(e).display !== 'none').map(e => e.dataset.key)")
    print("solo lumen visible:", visible)
    assert visible == ["lumen"], "solo mode should show only lumen"
    pg.click("#layQuad")

    # 7. Comparison overlay
    pg.click("#btnCompare"); pg.wait_for_timeout(300)
    cls = pg.get_attribute("#compare", "class")
    assert "open" in cls, "compare overlay should open"
    txt = pg.inner_text("#compare")
    for needle in ["Typography", "Density", "Navigation model", "Dawn / light theme", "Motion language", "Georgia + system-ui"]:
        assert needle in txt, f"comparison overlay missing: {needle}"
    print("compare overlay OK (5 axes + inherit table)")

    # 8. Guided walk (close the compare overlay first so it can't intercept)
    pg.click("#btnCompare"); pg.wait_for_timeout(300)
    pg.click("#btnWalk"); pg.wait_for_timeout(200)
    q1 = pg.inner_text("#qText")
    print("Q1:", q1[:80])
    assert "Fonts" in q1, "walk Q1 should be about fonts"
    n_ans = pg.eval_on_selector_all("#qAns button", "els => els.length")
    assert n_ans == 3, "Q1 should have 3 answer buttons"
    pg.click("#qAns button:nth-child(1)"); pg.wait_for_timeout(150)
    q2 = pg.inner_text("#qText")
    assert "Density" in q2, "Q2 should be density"
    pg.click("#qAns button:nth-child(2)"); pg.wait_for_timeout(150)
    q3 = pg.inner_text("#qText")
    assert "Navigation" in q3, "Q3 should be navigation"
    pg.click("#qAns button:nth-child(3)"); pg.wait_for_timeout(150)
    q4 = pg.inner_text("#qText")
    assert "Dawn" in q4, "Q4 should be dawn"
    pg.click("#qAns button:nth-child(4)"); pg.wait_for_timeout(150)
    q5 = pg.inner_text("#qText")
    assert "Motion" in q5, "Q5 should be motion"
    pg.click("#qAns button:nth-child(3)"); pg.wait_for_timeout(400)
    print("walk complete; dialog suppressed check — page errors:", [e for e in errors if "alert" not in e.lower()])
    assert not [e for e in errors if "alert" not in e.lower()], f"console/page errors: {errors}"

    b.close()

print("DESIGN SESSION CONSOLE: ALL CHECKS PASS")
