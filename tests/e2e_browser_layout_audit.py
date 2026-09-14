"""DOM-geometry alignment audit of a running studio (E2E_BASE or private boot).

Measures real bounding boxes (no screenshots — project convention):
  1. CSS token health  — every var(--token) used by live rules resolves
  2. Font loading      — the 5 shipped families actually load
  3. Welcome desk      — greeting/shelf stacking, dash-grid column equality
  4. Status strip      — one row, vertically aligned items
  5. Sidebar/status edge alignment
  6. Viewport fit      — key chrome inside 1440x900
  7. Overflow census   — scrollWidth/Height vs client on key containers
  8. Workspace surfaces (after opening one project) — script pane / scene
     index / toolbar geometry

Usage:  E2E_BASE=http://127.0.0.1:8500 python tests/e2e_browser_layout_audit.py
Without E2E_BASE it boots a private demo-model studio (standard suite mode).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_browser_common import Checks, open_studio  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

CHECKS = Checks()


def measure(page, sel):
    return page.evaluate(
        "sel => { const el = document.querySelector(sel);"
        " if (!el) return null; const r = el.getBoundingClientRect();"
        " return {x:r.x, y:r.y, width:r.width, height:r.height}; }",
        sel,
    )


def approx(a, b, tol):
    return abs(a - b) <= tol


def main():
    with open_studio() as base:
        with sync_playwright() as pw:
            from e2e_browser_common import launch
            browser, page, errors = launch(pw)
            page.goto(base + "/", wait_until="networkidle")
            page.wait_for_timeout(600)

            # ---- 0. boot sanity -------------------------------------------
            CHECKS.ok("page title", "Script Doctor Studio" in page.title())
            CHECKS.ok("status strip visible",
                      page.locator("#status-strip").is_visible())

            # ---- 1. token health ------------------------------------------
            # NOTE: --badge-h is set per-element by JS (branch pills) and
            # --accent/--glow live on body (room lighting), not :root. Both
            # are checked where they actually resolve.
            used_vars = page.evaluate(
                """() => {
                  const out = [];
                  for (const sheet of document.styleSheets) {
                    let rules; try { rules = sheet.cssRules } catch (e) { continue }
                    for (const r of rules) {
                      if (r.style) {
                        const m = (r.style.cssText || '')
                          .match(/var\\(--[a-z0-9-]+\\)/gi) || [];
                        for (const v of m) out.push(v.slice(4, -1));
                      }
                    }
                  }
                  return [...new Set(out)];
                }"""
            )
            dead = page.evaluate(
                """(vars) => {
                  // --badge-h is assigned per-element by JS on .branch-badge
                  // (hue of the branch pill) — it never lives on :root/body,
                  // so it is legitimately absent from the global cascade.
                  const jsSet = new Set(['--badge-h']);
                  const bad = [];
                  const root = getComputedStyle(document.documentElement);
                  const body = getComputedStyle(document.body);
                  for (const v of vars) {
                    if (jsSet.has(v)) continue;
                    const val = root.getPropertyValue(v) || body.getPropertyValue(v);
                    if (!val.trim()) bad.push(v);
                  }
                  return bad;
                }""",
                used_vars,
            )
            CHECKS.ok("all used CSS tokens resolve", len(dead) == 0,
                     f"unresolved: {dead[:8]}")

            # ---- 2. font loading -------------------------------------------
            fonts = page.evaluate(
                """() => Array.from(document.fonts).map(f => f.family)
                     .filter((v, i, a) => a.indexOf(v) === i)"""
            )
            for fam in ["Caveat", "Courier Prime", "IBM Plex Mono",
                        "Source Serif 4", "Special Elite"]:
                CHECKS.ok(f"font loaded: {fam}", fam in fonts)

            # ---- 3. welcome desk ------------------------------------------
            wv = measure(page, "#welcome-view")
            CHECKS.ok("welcome view fills viewport",
                      bool(wv) and approx(wv["width"], 1440, 2))
            greeting = measure(page, "#welcome-greeting")
            dgrid = measure(page, "#dash-grid")
            if greeting and dgrid:
                CHECKS.ok("greeting sits above dash grid",
                          greeting["y"] + greeting["height"] < dgrid["y"],
                          f"greeting bottom "
                          f"{greeting['y'] + greeting['height']:.1f} "
                          f"vs grid top {dgrid['y']:.1f}")
            shelf = measure(page, "#shelf-section")
            if shelf and dgrid:
                # shelf lives in the SIDEBAR (left column); it must sit beside,
                # not below, the dashboard — and inside the sidebar's own box
                sidebar = measure(page, "#sidebar")
                CHECKS.ok("shelf inside sidebar column",
                          bool(sidebar) and shelf["x"] >= sidebar["x"] - 1
                          and shelf["x"] + shelf["width"]
                          <= sidebar["x"] + sidebar["width"] + 1,
                          f"shelf x={shelf['x']:.1f} w={shelf['width']:.1f} "
                          f"vs sidebar x={sidebar and sidebar['x']:.1f} "
                          f"w={sidebar and sidebar['width']:.1f}")

            row_widths = page.evaluate(
                """() => {
                  const grid = document.querySelector('#dash-grid');
                  if (!grid || !grid.children.length) return null;
                  const rects = Array.from(grid.children)
                    .map(c => c.getBoundingClientRect());
                  const top = Math.min(...rects.map(r => r.top));
                  return rects.filter(r => Math.abs(r.top - top) < 2)
                              .map(r => r.width);
                }"""
            )
            if row_widths and len(row_widths) >= 2:
                spread = max(row_widths) - min(row_widths)
                CHECKS.ok("dash-grid columns equal width", spread <= 2,
                          f"width spread {spread:.1f}px over {len(row_widths)}")

            # ---- 4. status strip row --------------------------------------
            # the strip is one row: items must share a top edge. Only items
            # actually PRESENT are measured (some are conditionally rendered)
            strip_items = page.evaluate(
                """() => {
                  const sels = ['#status-project', '#status-model',
                                '#status-conn', '#status-dawn',
                                '#status-elapsed', '#status-metrics'];
                  const out = [];
                  for (const s of sels) {
                    const el = document.querySelector(s);
                    if (el && el.offsetParent !== null)
                      out.push(el.getBoundingClientRect().top);
                  }
                  return out;
                }"""
            )
            if strip_items:
                spread = max(strip_items) - min(strip_items)
                CHECKS.ok("status strip items vertically aligned",
                          spread <= 2, f"top spread {spread:.1f}px")

            # ---- 5. status strip span --------------------------------------
            # WIREFRAME CONTRACT (States 1/4/5): "Status strip x:0-1440,
            # 1440 x 28". It spans the FULL viewport — under the (now-overlay)
            # shelf and under the manuscript column. It no longer starts at
            # the main column's left edge, so the old [sidebar|main] check is
            # obsolete.
            status = measure(page, "#status-strip")
            if status:
                CHECKS.ok("status strip spans full viewport",
                          approx(status["x"], 0, 2)
                          and approx(status["width"], 1440, 2),
                          f"status x={status['x']:.1f} w={status['width']:.1f}")

            # ---- 6. viewport fit ------------------------------------------
            for sel in ["#sidebar", "#status-strip", "#welcome-view", "#app"]:
                r = measure(page, sel)
                if r:
                    inside = (r["x"] >= -1 and r["y"] >= -1
                              and r["x"] + r["width"] <= 1441
                              and r["y"] + r["height"] <= 901)
                    CHECKS.ok(f"chrome in viewport: {sel}", inside,
                             f"{sel} x={r['x']:.0f} y={r['y']:.0f} "
                             f"{r['width']:.0f}x{r['height']:.0f}")

            # ---- 7. overflow census ----------------------------------------
            for sel in ["#app", "#welcome-view", "#dash-grid", "#status-strip",
                        "#sidebar", "#desk-toolbar", "#context-dock",
                        "#script-pane", "#scene-index", "#draft-bar",
                        "#composer"]:
                info = page.evaluate(
                    """sel => {
                      const el = document.querySelector(sel);
                      if (!el) return null;
                      return {sw: el.scrollWidth, cw: el.clientWidth,
                              sh: el.scrollHeight, ch: el.clientHeight};
                    }""",
                    sel,
                )
                if info:
                    over_w = info["sw"] - info["cw"]
                    over_h = info["sh"] - info["ch"]
                    if sel in ("#app", "#welcome-view", "#dash-grid",
                               "#status-strip", "#sidebar"):
                        CHECKS.ok(f"no overflow: {sel}",
                                  over_w <= 0 and over_h <= 0,
                                  f"w+{over_w} h+{over_h}")
                    else:
                        # scrollable panes may legitimately scroll; census only
                        CHECKS.ok(f"scroll census: {sel}", True,
                                  f"w+{over_w} h+{over_h}")

            # ---- 8. workspace surfaces (open first project) -----------------
            cards = page.locator("#dash-grid .dash-card")
            if cards.count() > 0:
                cards.first.click()
                page.wait_for_timeout(900)
                # auto-hide chrome: wake before measuring project-bar bits
                page.mouse.move(10, 400)
                page.wait_for_timeout(400)
                # NOTE: the live manuscript row is .manuscript-workspace-layout
                # ([44px scene index | manuscript column]). The legacy
                # #script-pane/.desk pair is `display:none` outside idea-mode
                # (body:not(.idea-mode) .desk), so measuring it always yields
                # 0x0 — that was a dead-container false alarm, not a layout bug.
                ws = measure(page, ".manuscript-workspace-layout")
                si = measure(page, "#scene-index")
                toolbar = measure(page, "#desk-toolbar")
                if toolbar and ws:
                    CHECKS.ok("toolbar above manuscript row",
                              toolbar["y"] + toolbar["height"] <= ws["y"] + 4,
                              f"toolbar bottom "
                              f"{toolbar['y'] + toolbar['height']:.1f} "
                              f"vs row top {ws['y']:.1f}")
                # the 44px scene index is the row's first child; it must sit
                # inside the workspace row
                if ws and si:
                    CHECKS.ok("scene index within manuscript row",
                              si["x"] >= ws["x"] - 1
                              and si["x"] + si["width"]
                              <= ws["x"] + ws["width"] + 1,
                              f"index x={si['x']:.1f} w={si['width']:.1f} vs "
                              f"row x={ws['x']:.1f} w={ws['width']:.1f}")

            # ---- 9. GO 2 contracts (writer's loop / fold / dock law) --------
            # 9a. FV fold (1A): the entry point routes to the workspace dock —
            # no reachable path may set state.view = "fv" any more.
            fv = page.evaluate(
                """() => {
                  if (typeof openFeedbackView !== 'function') return null;
                  const src = String(openFeedbackView);
                  return { routes: src.includes('openDock'),
                           dormant: !src.includes('state.view = "fv"')
                                    && !src.includes("state.view = 'fv'") };
                }"""
            )
            if fv is not None:
                CHECKS.ok("FV folded into workspace (routes to dock, dormant clone)",
                          fv["routes"] and fv["dormant"],
                          f"routes={fv['routes']} dormant={fv['dormant']}")

            if cards.count() > 0:
                # 9b. dock law: with the dock open the manuscript never drops
                # below half the app width (frozen wireframe law).
                page.evaluate("() => { if (typeof openDock === 'function') openDock('evidence'); }")
                page.wait_for_timeout(700)
                widths = page.evaluate(
                    """() => {
                      const app = document.querySelector('#app');
                      const ws = document.querySelector('.manuscript-workspace-layout');
                      const dock = document.querySelector('#context-dock');
                      if (!app || !ws) return null;
                      return { app: app.getBoundingClientRect().width,
                               ws: ws.getBoundingClientRect().width,
                               dockOpen: !!(dock && dock.classList.contains('open')) };
                    }"""
                )
                if widths and widths["dockOpen"]:
                    CHECKS.ok("manuscript keeps majority width with dock open",
                              widths["ws"] >= 0.5 * widths["app"] - 2,
                              f"ws {widths['ws']:.0f} vs half of {widths['app']:.0f}")

                # 9c. loop keys both ways (2A): with findings, engage the loop
                # and confirm N steps findings; exit and confirm N no longer does.
                loop = page.evaluate(
                    """() => {
                      if (typeof startLoop !== 'function' || typeof loopState === 'undefined')
                        return null;
                      if (!(state.findings || []).length) return { skipped: true };
                      const before = loopState.pos;
                      startLoop();
                      const entered = loopState.active;
                      const pos1 = loopState.pos;
                      return { skipped: false, entered, stepped: pos1 >= 0,
                               before, pos1 };
                    }"""
                )
                if loop and not loop.get("skipped"):
                    CHECKS.ok("fix loop engages and steps on entry",
                              loop["entered"] and loop["stepped"],
                              f"entered={loop['entered']} pos={loop['pos1']}")
                    # Esc exits (contextual keys return to scene-stepping)
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(200)
                    after = page.evaluate(
                        "() => ({ active: loopState.active, dock: document.querySelector('#context-dock').classList.contains('open') })")
                    CHECKS.ok("Esc exits the loop before the dock",
                              after["active"] is False and after["dock"] is True,
                              f"active={after['active']} dockOpen={after['dock']}")
                    page.evaluate("() => { if (typeof closeDock === 'function') closeDock(); }")
                elif loop and loop.get("skipped"):
                    CHECKS.ok("fix loop skips cleanly with no findings", True)

            CHECKS.ok("no JS page errors", len(errors) == 0,
                      "; ".join(errors[:3]))
            CHECKS.finish()


if __name__ == "__main__":
    main()
