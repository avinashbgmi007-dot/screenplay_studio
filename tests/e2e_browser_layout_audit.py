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
  9. GO 2 contracts — FV fold, dock width law, fix-loop keys

The suite SEEDS its own desk (one analyzed project + one plain upload) rather
than measuring whatever happens to be on screen. Without a project, sections 8
and 9 recorded nothing at all: every check in them sat behind `if
cards.count()`, so the "manuscript never drops below half" law and the fix-loop
contract stopped being asserted while the suite still printed PASS. (R6-E2E-2.)

Usage:  E2E_BASE=http://127.0.0.1:8500 python tests/e2e_browser_layout_audit.py
Without E2E_BASE it boots a private demo-model studio (standard suite mode).
"""
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_browser_common import (  # noqa: E402
    Checks, note, open_studio, studio_headers)

from playwright.sync_api import sync_playwright  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "pain_tenglish.fountain")

SUBJECT_TITLE = "Layout Audit Subject"
SECOND_TITLE = "Layout Audit Second"

CHECKS = Checks()


def seed_desk(base):
    """Put two projects on the desk: one analyzed (so the fix loop has findings
    to step) and one plain (so the dashboard grid has a row of columns to
    compare). The desk sorts by recency, so the plain upload is the FIRST card —
    which is exactly the trap section 8 has to avoid."""
    names = []
    for title in (SUBJECT_TITLE, SECOND_TITLE):
        with open(FIXTURE, "rb") as f:
            r = requests.post(f"{base}/api/projects", headers=studio_headers(base),
                              files={"file": (f"{title}.fountain", f, "text/plain")},
                              data={"title": title}, timeout=60)
        assert r.status_code in (200, 201), f"seed upload failed: {r.text[:200]}"
        names.append(r.json().get("project") or r.json().get("name") or title)
    a = requests.post(f"{base}/api/projects/{names[0]}/analyze",
                      headers=studio_headers(base), json={"force": True}, timeout=300)
    assert a.status_code == 200, f"seed analyze failed: {a.text[:200]}"
    return names[0]



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
        seed_desk(base)
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
            # Precondition, not decoration: a missing element IS the failure this
            # section exists to catch, so it folds into the condition instead of
            # skipping the check (an `if greeting and dgrid:` recorded nothing
            # when either was renamed).
            CHECKS.ok("greeting sits above dash grid",
                      bool(greeting) and bool(dgrid)
                      and greeting["y"] + greeting["height"] < dgrid["y"],
                      f"greeting={greeting} grid={dgrid}")
            shelf = measure(page, "#shelf-section")
            sidebar = measure(page, "#sidebar")
            # shelf lives in the SIDEBAR (left column); it must sit beside,
            # not below, the dashboard — and inside the sidebar's own box
            CHECKS.ok("shelf inside sidebar column",
                      bool(shelf) and bool(dgrid) and bool(sidebar)
                      and shelf["x"] >= sidebar["x"] - 1
                      and shelf["x"] + shelf["width"]
                      <= sidebar["x"] + sidebar["width"] + 1,
                      f"shelf={shelf} sidebar={sidebar}")

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
            else:
                # The desk is seeded with two projects precisely so this law has
                # two columns to compare. One card means the fixture (or the
                # grid) changed, and silence here is how the law stops existing.
                CHECKS.ok("dash-grid renders a comparable row", False,
                          f"{len(row_widths or [])} card(s) in the top row — "
                          "the seeded desk should show two")

            # ---- 4. status strip row --------------------------------------
            # the strip is one row: items must sit on ONE LINE. #status-strip
            # is `align-items: center`, so the invariant is a shared MIDLINE,
            # not a shared top edge — tops only ever matched while every item
            # happened to be the same height, and WCAG 2.5.8 ends that (a 24px
            # button beside a 15px span is correct, not crooked). Measuring the
            # top here would fail on a row that is visually perfect.
            # Only items actually PRESENT are measured (some are conditionally
            # rendered), and each must stay inside the strip's own box.
            strip_items = page.evaluate(
                """() => {
                  const strip = document.querySelector('#status-strip');
                  const sr = strip && strip.getBoundingClientRect();
                  const sels = ['#status-project', '#status-model',
                                '#status-conn', '#status-dawn',
                                '#status-elapsed', '#status-metrics'];
                  const mid = [], outside = [];
                  for (const s of sels) {
                    const el = document.querySelector(s);
                    if (!el || el.offsetParent === null) continue;
                    const r = el.getBoundingClientRect();
                    mid.push(r.top + r.height / 2);
                    if (sr && (r.top < sr.top - 1 || r.bottom > sr.bottom + 1))
                      outside.push(s);
                  }
                  return { mid, outside };
                }"""
            )
            if strip_items["mid"]:
                spread = max(strip_items["mid"]) - min(strip_items["mid"])
                CHECKS.ok("status strip items share one line (midline aligned)",
                          spread <= 2, f"midline spread {spread:.1f}px")
                CHECKS.ok("status strip items stay inside the strip's row",
                          not strip_items["outside"],
                          ", ".join(strip_items["outside"]))
            else:
                # Genuinely conditional on the DESK (project/model/dawn items
                # only render once there is something to report), so this is a
                # coverage note rather than a red — but section 8 re-measures the
                # strip with a project open, where "one line" is not optional.
                note("status strip items", "none visible on the desk")

            # ---- 5. status strip span --------------------------------------
            # WIREFRAME CONTRACT (States 1/4/5): "Status strip x:0-1440,
            # 1440 x 28". It spans the FULL viewport — under the (now-overlay)
            # shelf and under the manuscript column. It no longer starts at
            # the main column's left edge, so the old [sidebar|main] check is
            # obsolete.
            status = measure(page, "#status-strip")
            CHECKS.ok("status strip spans full viewport",
                      bool(status) and approx(status["x"], 0, 2)
                      and approx(status["width"], 1440, 2),
                      f"status={status}")

            # ---- 6. viewport fit ------------------------------------------
            for sel in ["#sidebar", "#status-strip", "#welcome-view", "#app"]:
                r = measure(page, sel)
                inside = (bool(r) and r["x"] >= -1 and r["y"] >= -1
                          and r["x"] + r["width"] <= 1441
                          and r["y"] + r["height"] <= 901)
                # All four are chrome the SPA always renders, so `r is None` is a
                # rename or a removed element — the loudest possible outcome here,
                # and previously a silent skip.
                CHECKS.ok(f"chrome in viewport: {sel}", inside,
                          f"{sel} {r}")

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
                if sel in ("#app", "#welcome-view", "#dash-grid",
                           "#status-strip", "#sidebar"):
                    over = ("missing" if not info else
                            f"w+{info['sw'] - info['cw']} h+{info['sh'] - info['ch']}")
                    CHECKS.ok(f"no overflow: {sel}",
                              bool(info) and info["sw"] - info["cw"] <= 0
                              and info["sh"] - info["ch"] <= 0,
                              f"{sel} {over}")
                elif info:
                    # Scrollable panes may legitimately scroll, so there is no
                    # invariant to assert — this is a census, not a check. It
                    # used to be `CHECKS.ok(..., True, f"w+{over_w} h+{over_h}")`,
                    # whose detail prints only on FAILURE: the census was
                    # invisible on every green run. note() actually prints it.
                    note(f"scroll census: {sel}",
                         f"w+{info['sw'] - info['cw']} "
                         f"h+{info['sh'] - info['ch']}")

            # ---- 8. workspace surfaces (open the seeded project) ------------
            cards = page.locator("#dash-grid .dash-card")
            CHECKS.ok("the seeded desk offers a project card",
                      cards.count() > 0, f"{cards.count()} card(s)")
            # Click the ANALYZED card, not `.first`. The desk orders by recency, so
            # `.first` is the parse-only upload, which has no findings — and every
            # fix-loop claim below then takes its "nothing to step" branch and the
            # suite prints green while testing none of it. This is the R6-E2E-2
            # shape biting again, one layer down, and the new precondition check
            # caught it.
            subject = page.locator("#dash-grid .dash-card").filter(
                has_text=SUBJECT_TITLE)
            found = subject.count() > 0
            CHECKS.ok("the analyzed project is on the desk", found,
                      f"{subject.count()} card matching {SUBJECT_TITLE!r}")
            if not found:
                # Everything below measures the OPENED workspace, so there is
                # nothing left to assert honestly. Say which laws went unmeasured
                # and stop with a red summary — rather than letting Playwright
                # time out on the click 30s later and print an ERROR that names
                # none of them.
                CHECKS.ok("workspace, dock-width and fix-loop contracts measured",
                          False, "no analyzed project card to open")
                browser.close()
                CHECKS.finish()
                return
            subject.first.click()
            # The real sync point is the manuscript rendering, not a sleep.
            try:
                page.wait_for_selector("#manuscript-container .scene-page",
                                       timeout=20000)
                loaded = True
            except Exception:
                loaded = False
            CHECKS.ok("opening the desk card loads the manuscript", loaded,
                      "no .scene-page within 20s")
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
            CHECKS.ok("toolbar above manuscript row",
                      bool(toolbar) and bool(ws)
                      and toolbar["y"] + toolbar["height"] <= ws["y"] + 4,
                      f"toolbar={toolbar} ws={ws}")
            # the 44px scene index is the row's first child; it must sit
            # inside the workspace row
            CHECKS.ok("scene index within manuscript row",
                      bool(ws) and bool(si)
                      and si["x"] >= ws["x"] - 1
                      and si["x"] + si["width"] <= ws["x"] + ws["width"] + 1,
                      f"index={si} ws={ws}")
            # Re-measure the status strip HERE, where the desk version of this
            # audit could only note "none visible": with a project open, the
            # project/model/connection items are all real text, so "one row" is
            # a law rather than an accident.
            strip_ws = page.evaluate(
                """() => {
                  const strip = document.querySelector('#status-strip');
                  const sr = strip && strip.getBoundingClientRect();
                  const sels = ['#status-conn', '#status-dawn', '#status-elapsed',
                                '#status-metrics'];
                  const mid = [], outside = [];
                  for (const s of sels) {
                    const el = document.querySelector(s);
                    if (!el || el.offsetParent === null) continue;
                    const r = el.getBoundingClientRect();
                    mid.push(r.top + r.height / 2);
                    if (sr && (r.top < sr.top - 1 || r.bottom > sr.bottom + 1))
                      outside.push(s);
                  }
                  return { mid, outside };
                }"""
            )
            CHECKS.ok("status strip keeps one line with a project open",
                      bool(strip_ws["mid"])
                      and max(strip_ws["mid"]) - min(strip_ws["mid"]) <= 2
                      and not strip_ws["outside"],
                      f"mid={strip_ws['mid']} outside={strip_ws['outside']}")

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
            else:
                CHECKS.ok("FV folded into workspace (routes to dock, dormant clone)",
                          False, "openFeedbackView is not a function any more")

            # 9b. dock law: with the dock open the manuscript never drops below
            # half the app width (frozen wireframe law, restated in AGENTS.md).
            # This ran behind `if cards.count() > 0:` and then `if widths and
            # widths["dockOpen"]:` — two guards, neither with an else. On a desk
            # with no project it recorded NOTHING and the suite still printed
            # PASS; that is how the project's headline layout law stopped being
            # tested. Both guards now have a loud failure.
            page.evaluate("() => { if (typeof openDock === 'function') openDock('evidence'); }")
            try:
                page.wait_for_selector("#context-dock.open", timeout=8000)
            except Exception:
                pass
            # `.open` lands at the START of the slide, not the end: measured, the
            # pane is 1375px the instant the class appears and 1014px 300ms later,
            # so a width assertion taken here reads a mid-animation box — which is
            # how this law passed at any threshold up to 99%. Wait for the pane to
            # stop moving (bounded), then measure.
            page.wait_for_function(
                """() => {
                  const p = document.querySelector('#manuscript-container');
                  if (!p) return true;
                  const w = Math.round(p.getBoundingClientRect().width);
                  const stable = window.__panePrev === w;
                  window.__panePrev = w;
                  return stable;
                }""", timeout=5000)
            widths = page.evaluate(
                """() => {
                  const app = document.querySelector('#app');
                  const ws = document.querySelector('.manuscript-workspace-layout');
                  const pane = document.querySelector('#manuscript-container');
                  const dock = document.querySelector('#context-dock');
                  if (!app || !ws) return null;
                  return { app: app.getBoundingClientRect().width,
                           ws: ws.getBoundingClientRect().width,
                           pane: pane ? pane.getBoundingClientRect().width : 0,
                           dockW: dock ? dock.getBoundingClientRect().width : 0,
                           dockOpen: !!(dock && dock.classList.contains('open')) };
                }"""
            )
            CHECKS.ok("the Evidence dock opens on the workspace",
                      bool(widths) and widths["dockOpen"], f"widths={widths}")
            # THE LAW, AND THE BOX IT APPLIES TO. This compared `.manuscript-
            # workspace-layout` against #app — but that row CONTAINS the dock, so
            # it stays 1438/1440 whatever the dock does, and the check passed even
            # at a 95% threshold (proved by re-running with the threshold
            # tightened). The manuscript is what must never drop below half, and
            # #manuscript-container does move: 1394 closed → 1014 with the 380px
            # dock open, i.e. 70% of the viewport.
            CHECKS.ok("manuscript keeps majority width with dock open",
                      bool(widths) and widths["pane"] >= 0.5 * widths["app"] - 2,
                      f"pane {widths['pane']:.0f} of {widths['app']:.0f} "
                      f"({100 * widths['pane'] / widths['app']:.0f}%), "
                      f"dock {widths['dockW']:.0f}"
                      if widths else "no #app / .manuscript-workspace-layout")

            # 9c. loop keys both ways (2A): with findings, engage the loop
            # and confirm N steps findings; exit and confirm N no longer does.
            loop = page.evaluate(
                """() => {
                  if (typeof startLoop !== 'function' || typeof loopState === 'undefined')
                    return null;
                  if (!(state.findings || []).length) return { skipped: true };
                  // startLoop() seats the cursor at -1 and then calls
                  // stepLoop(1), so the shipped claim `pos1 >= 0` could
                  // almost never fail, and comparing against the previous
                  // pos depended on how the suite had driven the loop
                  // earlier. The promise in the check's name is that the
                  // loop ADVANCES, so advance it twice and require movement.
                  startLoop();
                  const entered = loopState.active;
                  const landed = loopState.pos;
                  stepLoop(1);
                  return { skipped: false, entered, landed,
                           moved: loopState.pos !== landed, n: loopList().length };
                }"""
            )
            # A one-item loopList wraps back onto itself, so `moved` would be
            # false for a working loop; `n` therefore has to be part of the
            # precondition, not only the detail.
            CHECKS.ok("the seeded report gives the fix loop more than one finding",
                      bool(loop) and not loop.get("skipped") and loop["n"] > 1,
                      f"loop={loop}")
            CHECKS.ok("fix loop engages and steps on entry",
                      bool(loop) and not loop.get("skipped")
                      and loop["entered"] and loop["landed"] >= 0 and loop["moved"],
                      f"entered={loop.get('entered')} landed={loop.get('landed')} "
                      f"moved={loop.get('moved')} of {loop.get('n')}"
                      if loop else "startLoop/loopState missing")
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
            after = page.evaluate(
                "() => ({ active: loopState.active, "
                "dock: document.querySelector('#context-dock')"
                ".classList.contains('open') })")
            CHECKS.ok("Esc exits the loop before the dock",
                      after["active"] is False and after["dock"] is True,
                      f"active={after['active']} dockOpen={after['dock']}")
            page.evaluate("() => { if (typeof closeDock === 'function') closeDock(); }")

            CHECKS.ok("no JS page errors", len(errors) == 0,
                      "; ".join(errors[:3]))
            CHECKS.finish()


if __name__ == "__main__":
    main()
