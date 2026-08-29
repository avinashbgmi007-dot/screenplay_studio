"""e2e_browser_spark_wall.py — cross-check that the Spark Wall (chosen world)
is FULLY live in the app, not a stale cache and not a mockup-only patch.

Walks the three shipped surfaces in a real Chromium:

  0. fresh assets      -> hx1b101/102/103 actually served (cache lie detector)
  1. new DOM at boot   -> spark-ambience, #flow-btn, .dawn-wash, #river-current
  2. the wall (idea)   -> glass page on the void, threads, pill, graduate text
  3. chips contract    -> SVG icons; collapse to icons on first input, un-collapse on clear
  4. river read        -> #flow-btn toggles body.river-read; current dots per scene;
                          wave separator styling; Esc leaves the river
  5. dawn meter wiring -> updateDawnMeter() drives --spark-dawn from fixQueue state
  6. zero JS errors

Dual-mode like every suite: E2E_BASE=<url> audits THAT running studio
(creates one tagged idea + the sample project if missing, cleans the idea up),
otherwise boots a private throwaway studio.

Run:  python tests/e2e_browser_spark_wall.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_browser_common import Checks, assert_no_js_errors, launch, open_studio  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

IDEA_TITLE = "spark-wall-e2e-probe"


def main():
    c = Checks()
    with open_studio() as base, sync_playwright() as pw:
        browser, page, errors = launch(pw)
        live = bool(os.environ.get("E2E_BASE"))
        shot_prefix = "live" if live else "self"
        os.makedirs("preview_shots", exist_ok=True)

        # ---- 0. fresh assets: the cache lie detector -----------------------
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(600)
        assets = page.evaluate("""async () => {
            const html = await (await fetch('/', {cache: 'reload'})).text();
            return {
                htmlBust: /v=hx1b1\\d\\d/.test(html),
                cssLink: (html.match(/style\\.css\\?v=([a-z0-9]+)/) || [])[1] || null,
                hasAmbience: html.includes('spark-ambience'),
                hasFlowBtn: html.includes('flow-btn'),
            };
        }""")
        c.check("index.html serves the hx1b10x cache-bust", assets["htmlBust"],
                json.dumps(assets))
        c.check("index.html ships spark-ambience markup", assets["hasAmbience"])
        c.check("index.html ships the flow button", assets["hasFlowBtn"])

        # ---- 1. new DOM at boot --------------------------------------------
        boot = page.evaluate("""() => ({
            ambience: !!document.querySelector('.spark-ambience'),
            threads: !!document.querySelector('.spark-threads'),
            flowBtn: !!document.getElementById('flow-btn'),
            dawnWash: !!document.querySelector('.dawn-wash'),
            riverHolder: !!document.getElementById('river-current'),
        })""")
        c.check("boot DOM carries all four Spark Wall mounts", all(boot.values()),
                json.dumps(boot))

        # ---- 2. the wall: create an idea through the real button -----------
        page.evaluate("""async (title) => {
            // clean slate for the probe title, then create through the API the
            // button itself uses (the button click path is covered below when
            // the shelf is reachable; API keeps this suite dual-mode safe)
            const list = await (await fetch('/api/ideas')).json();
            for (const old of list) {
                if (old.title === title) await fetch('/api/ideas/' + old.id, {method: 'DELETE'});
            }
            await fetch('/api/ideas', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                       body: JSON.stringify({title})});
        }""", IDEA_TITLE)
        # drive the real UI: ideas flyout -> new idea button (self-host fresh
        # shelf has exactly our probe idea)
        page.locator("#ideas-section").hover()
        page.wait_for_timeout(400)
        page.locator("#new-idea-btn").click()
        page.wait_for_timeout(1400)
        wall = page.evaluate("""() => {
            const c = document.getElementById('idea-canvas');
            const amb = document.querySelector('.spark-ambience');
            const content = document.getElementById('idea-content');
            const grad = document.getElementById('idea-graduate-btn');
            return {
                open: c ? c.style.display === 'flex' : false,
                ambienceShown: amb ? getComputedStyle(amb).display === 'block' : false,
                glassRadius: content ? getComputedStyle(content).borderRadius : '',
                glassBorder: content ? getComputedStyle(content).borderTopColor : '',
                graduate: grad ? grad.textContent.trim() : '',
                threadPaths: document.querySelectorAll('.spark-threads path').length,
                pill: !!document.getElementById('idea-sam-pill'),
            };
        }""")
        c.check("idea page opens on the wall (canvas flex)", wall["open"])
        c.check("ambience layer is displayed over the void", wall["ambienceShown"])
        c.check("the page renders as a glass card (16px radius)",
                wall["glassRadius"] == "16px", wall["glassRadius"])
        c.check("glass border is the spark edge tint", "160, 180, 255" in wall["glassBorder"],
                wall["glassBorder"])
        c.check("graduate reads 'Grow into pages'", "Grow into pages" in wall["graduate"],
                wall["graduate"])
        c.check("thread paths present in the ambience svg", wall["threadPaths"] >= 1)
        c.check("Sameer pill rides the wall", wall["pill"])
        # VISUAL assertions — pin the look numerically, not just DOM presence
        look = page.evaluate("""() => ({
            canvasBg: getComputedStyle(document.getElementById('idea-canvas')).backgroundColor,
            pageBg: getComputedStyle(document.getElementById('idea-content')).backgroundColor,
            threadOp: getComputedStyle(document.querySelector('.spark-threads')).opacity,
        })""")
        c.check("the void is actually dark (#0a0e1a)", look["canvasBg"] == "rgb(10, 14, 26)",
                json.dumps(look))
        c.check("the page is real dark glass, not a whisper",
                look["pageBg"] == "rgba(13, 17, 32, 0.78)", look["pageBg"])
        c.check("threads read at >= 0.7 opacity", float(look["threadOp"]) >= 0.7,
                look["threadOp"])
        page.screenshot(path=f"preview_shots/e2e-spark-idea-{shot_prefix}.png")

        # ---- 3. chips contract ---------------------------------------------
        chips = page.evaluate("""() => {
            const wrap = document.querySelector('#idea-explore .explore-chips');
            return { count: wrap ? wrap.children.length : 0,
                     svg: document.querySelectorAll('#idea-explore .chip-ic').length };
        }""")
        c.check("explore chips render 6 SVG-icon chips", chips["count"] == 6 and chips["svg"] == 6,
                json.dumps(chips))
        page.locator("#idea-content").fill("A courier story about regret.")
        page.wait_for_timeout(300)
        collapsed = page.evaluate("""() => {
            const w = document.querySelector('#idea-explore .explore-chips');
            const lbl = w && w.querySelector('.explore-chip .lbl');
            return { collapsed: w ? w.classList.contains('collapsed') : false,
                     lblHidden: lbl ? getComputedStyle(lbl).display === 'none' : false };
        }""")
        c.check("first input collapses chips to icons", collapsed["collapsed"] and collapsed["lblHidden"],
                json.dumps(collapsed))
        page.locator("#idea-content").fill("")
        page.wait_for_timeout(300)
        restored = page.evaluate(
            "() => document.querySelector('#idea-explore .explore-chips').classList.contains('collapsed')")
        c.check("clearing the input un-collapses the chips", restored is False)

        # ---- 4. river read --------------------------------------------------
        # the sample project (3 scenes) is the river's test body; we're inside
        # the idea room here, so desk buttons are hidden — create via API and
        # open through the app's own openProject() path
        made = page.evaluate("""async () => {
            const ps = await (await fetch('/api/projects')).json();
            if ((ps.projects || []).some(p => p.project === 'The Late Hour')) {
                return 'The Late Hour';
            }
            const r = await fetch('/api/sample', { method: 'POST' });
            return (await r.json()).project;
        }""")
        page.evaluate("async (name) => { await openProject(name); }", made)
        page.wait_for_timeout(2500)
        page.locator("#flow-btn").click()
        page.wait_for_timeout(700)
        river = page.evaluate("""() => {
            const dots = document.querySelectorAll('#river-current i');
            const firstDotOn = dots.length ? dots[0].classList.contains('on') : false;
            const sp = document.querySelector('#script-scenes .scene-page');
            const wave = sp ? getComputedStyle(sp, '::after').backgroundImage : '';
            return {
                mode: document.body.classList.contains('river-read'),
                dots: dots.length,
                firstDotOn,
                btnActive: document.getElementById('flow-btn').classList.contains('active'),
                waveStyled: wave.includes('svg'),
            };
        }""")
        c.check("flow button toggles body.river-read", river["mode"] and river["btnActive"],
                json.dumps(river))
        c.check("current nav carries one dot per scene (3)", river["dots"] == 3 and river["firstDotOn"],
                f"dots={river['dots']}")
        c.check("wave separator styled between pages", river["waveStyled"])
        glassy = page.evaluate("""() => {
            const sp = document.querySelector('#script-scenes .scene-page');
            const act = sp.querySelector('.el-action');
            return {
                spBg: getComputedStyle(sp).backgroundColor,
                actColor: act ? getComputedStyle(act).color : null,
            };
        }""")
        c.check("river pages are dark glass, not paper",
                glassy["spBg"] == "rgba(10, 14, 26, 0.82)", json.dumps(glassy))
        c.check("script text reads light on the dark glass",
                glassy["actColor"] == "rgb(207, 224, 218)", glassy["actColor"])
        page.screenshot(path=f"preview_shots/e2e-spark-river-{shot_prefix}.png")
        # dot click jumps scenes: click dot 3, expect scroll to move
        page.locator("#river-current i").nth(2).click()
        page.wait_for_timeout(900)
        scrolled = page.evaluate("""() => {
            const sc = document.getElementById('script-scenes');
            const dots = [...document.querySelectorAll('#river-current i')];
            return { top: sc.scrollTop, lastOn: dots[2].classList.contains('on') };
        }""")
        c.check("clicking a current dot jumps its scene", scrolled["top"] > 200 and scrolled["lastOn"],
                json.dumps(scrolled))
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        left = page.evaluate("() => document.body.classList.contains('river-read')")
        c.check("Esc leaves the river back to the desk", left is False)

        # ---- 5. dawn meter wiring ------------------------------------------
        dawn = page.evaluate("""() => {
            if (typeof updateDawnMeter !== 'function') return { fn: false };
            state.fixQueue = { items: [
                { status: 'addressed' }, { status: 'open' }, { status: 'open' }] };
            updateDawnMeter();
            const pct = getComputedStyle(document.documentElement).getPropertyValue('--spark-dawn').trim();
            state.fixQueue = { items: [] };
            updateDawnMeter();
            const pctEmpty = getComputedStyle(document.documentElement).getPropertyValue('--spark-dawn').trim();
            return { fn: true, pct, pctEmpty };
        }""")
        ok = dawn.get("fn") and abs(float(dawn.get("pct", "0") or 0) - 0.333) < 0.01 and float(dawn.get("pctEmpty", "1") or 1) == 0.0
        c.check("updateDawnMeter drives --spark-dawn from fixQueue (1/3 -> 0.333, empty -> 0)", ok,
                json.dumps(dawn))
        page.evaluate("""() => {
            state.fixQueue = { items: [
                { status: 'addressed' }, { status: 'open' }, { status: 'open' }] };
            updateDawnMeter();
        }""")
        page.wait_for_timeout(750)  # the wash eases in over 0.6s — sample after
        wash = page.evaluate("() => getComputedStyle(document.querySelector('.dawn-wash')).opacity")
        page.evaluate("""() => {
            state.fixQueue = { items: [] };
            updateDawnMeter();
        }""")
        c.check("dawn wash visibly answers (1/3 resolved -> ~0.283 opacity)",
                abs(float(wash) - 0.283) < 0.02, wash)

        # ---- cleanup: remove the probe idea (live-server runs stay clean) ---
        page.evaluate("""async (title) => {
            const list = await (await fetch('/api/ideas')).json();
            for (const old of list) {
                if (old.title === title) await fetch('/api/ideas/' + old.id, {method: 'DELETE'});
            }
        }""", IDEA_TITLE)

        assert_no_js_errors(c, errors)
        browser.close()
    c.finish()


if __name__ == "__main__":
    main()
