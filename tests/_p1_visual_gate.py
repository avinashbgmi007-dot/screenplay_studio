"""P1 visual truth gate — the spec §11 walk on the Gun_Pen report.

Green tests prove the DOM says the right thing; they do not prove the desk is
readable. This boots the real studio (demo model) against a COPY of the analyzed
gun_pen_2 project, walks the surfaces P1 rebuilt, and for each one records both a
screenshot AND the pixel-level facts (width budget, section open/closed,
overflow, surface overlap) so "review against §11" is evidence, not opinion.

    python tests/_p1_visual_gate.py

Shots + facts land in impl-shots/runs/latest/ (gitignored - regenerate on demand).
The project dir is copied, never served in place: this run must not mark up the
writer's real project stores.
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import playwright.sync_api as pw_sync
from e2e_browser_common import launch, start_studio

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PROJECT = os.path.join(_REPO, "studio_projects", "gun_pen_2")
SHOTS = os.path.join(_REPO, "impl-shots", "runs", "latest")
os.makedirs(SHOTS, exist_ok=True)

# The §11 measurement set. One dict per shot: the layout facts are read in the
# same instant the pixels are taken, so a claim and its image can't drift apart.
MEASURE = r"""() => {
  const r = (n) => { if (!n) return null; const b = n.getBoundingClientRect();
    return {x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width),
            h: Math.round(b.height)}; };
  const q = (s) => document.querySelector(s);
  const doc = document.documentElement;
  const ms = q('#manuscript-container'), dock = q('#context-dock');
  const secs = [...document.querySelectorAll('#context-dock .dock-section')];
  const overlap = (a, b) => (!a || !b) ? false :
      !(a.x + a.w <= b.x || b.x + b.w <= a.x ||
        a.y + a.h <= b.y || b.y + b.h <= a.y);
  const a = ms && ms.getBoundingClientRect(), d = dock && dock.getBoundingClientRect();
  return {
    viewport: [window.innerWidth, window.innerHeight],
    overflowX: doc.scrollWidth - doc.clientWidth,
    manuscript: r(ms), dock: r(dock),
    manuscriptPct: a && d ? +(100 * a.width / window.innerWidth).toFixed(1) : null,
    dockOpen: !!(d && d.width > 0 && ms && (a.x + a.width) <= d.x + 1),
    surfacesOverlap: overlap(r(ms), r(dock)),
    sections: secs.length,
    sectionsOpen: secs.filter(s => s.dataset.open === 'true').length,
    sectionCountsHidden: secs.filter(s => s.dataset.open !== 'true')
      .some(s => s.querySelector('.dock-section-body-inner').offsetHeight > 2),
    arrival: r(q('.dock-arrival-strip')),
    arrivalHeadline: (q('.dock-arrival-strip') || {}).innerText || null,
    shelf: r(q('.craft-shelf')),
    queueRows: document.querySelectorAll('.dock-section-fixqueue .fix-row').length,
    rowBox: r(document.querySelector('.dock-section-fixqueue .fix-row')),
    sevText: (document.querySelector('.dock-section-fixqueue .sev-badge') || {}).textContent || null,
    badges: document.querySelectorAll('.dock-section-fixqueue .fix-row .finding-deep-badge').length,
    // P2.13: a chip whose label cannot fit its own box reads as an icon and says
    // nothing — the pixels have to reject that, not just find the node.
    ruleChip: (() => { const b = document.querySelector('#context-dock .finding-rule-btn');
      if (!b) return null;
      const box = b.getBoundingClientRect();
      return { text: b.textContent, w: Math.round(box.width),
               clipped: b.scrollWidth > b.clientWidth + 1 }; })(),
  };
}"""

facts = {}
EL_SHOTS = []


def shot(page, name):
    # the desk auto-hides its chrome 4s after the pointer leaves the top 120px
    # (a real affordance, not a bug), so a naive screenshot shows an empty band
    # where the toolbar is. Park the pointer there first: the gate must judge the
    # desk the writer is looking at, not the desk at rest.
    page.mouse.move(720, 40)
    page.wait_for_timeout(500)
    page.screenshot(path=os.path.join(SHOTS, name + ".png"))
    facts[name] = page.evaluate(MEASURE)
    print("   ", name)


def element_shot(page, selector, name):
    from e2e_browser_common import open_dock_section_holding
    EL_SHOTS.append(name)
    if not page.locator(selector).count():
        facts[name] = "no such element"
        print("   ", name + " (element) MISSING")
        return
    open_dock_section_holding(page, selector)
    node = page.locator(selector + " >> visible=true").first
    if not node.count():
        facts[name] = "closed section"
        print("   ", name + " (element) HIDDEN")
        return
    node.scroll_into_view_if_needed()
    page.mouse.move(720, 40)
    page.wait_for_timeout(400)
    node.screenshot(path=os.path.join(SHOTS, name + ".png"))
    facts[name] = "ok"
    print("   ", name + " (element)")


def open_project(page, base):
    page.goto(base, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_selector("#shelf-trigger", timeout=20000)
    page.locator("#shelf-trigger").hover()
    page.wait_for_timeout(400)
    page.locator(".project-item").filter(has_text="gun_pen").first.click()
    page.wait_for_selector("#manuscript-container .scene-page", timeout=30000)
    page.wait_for_timeout(800)


def ledger(page, tab="evidence"):
    # Escape closes the dock but can leave #context-dock.open in the DOM, so the
    # class is not proof the writer can see it. Ask the tab itself.
    for _ in range(2):
        if page.locator(f"#dock-tab-{tab} >> visible=true").count():
            break
        aff = page.locator("#right-edge-affordance >> visible=true")
        if aff.count():
            aff.first.click()
            page.wait_for_timeout(500)
    else:
        raise RuntimeError("the dock will not open — no edge affordance")
    page.locator(f"#dock-tab-{tab}").click()
    page.wait_for_timeout(600)


def register(page, to_dawn):
    # the rail's Dawn button is hidden while the rail is collapsed; the status
    # strip carries the same control, so click whichever the writer can see.
    btn = page.locator("#dawn-btn >> visible=true")
    if not btn.count():
        btn = page.locator("#status-dawn >> visible=true")
    btn.first.click(timeout=6000)
    page.wait_for_timeout(900)
    print("   register ->", "dawn" if to_dawn else "night")


def main():
    assert os.path.isdir(SRC_PROJECT), f"no analyzed fixture at {SRC_PROJECT}"
    tmp = tempfile.TemporaryDirectory(prefix="p1gate_")
    proj = os.path.join(tmp.name, "projects", "gun_pen_2")
    shutil.copytree(SRC_PROJECT, proj)
    with start_studio(projects_dir=os.path.join(tmp.name, "projects")) as studio:
        base = studio.base_url
        with pw_sync.sync_playwright() as p:
            browser, page, errors = launch(p)
            open_project(page, base)

            def desk():
                shot(page, "01_desk_night_no_ledger")
            desk()

            def ledger_night():
                ledger(page)
                shot(page, "02_ledger_night_default")
            ledger_night()

            def ledger_expanded():
                # the writer's own move: open the first section, check the body paints
                page.locator("#context-dock .dock-section-head").first.click()
                page.wait_for_timeout(600)
                shot(page, "03_ledger_night_expanded")
                element_shot(page, ".dock-section-fixqueue .fix-queue > .craft-panel-head",
                             "03b_fixqueue_night")
                element_shot(page, ".dock-section .finding-note", "03c_card_night")
                element_shot(page, ".dock-section-fixqueue .fix-row",
                             "03d_queue_row_night")
                # P2.13: a KB rule is now a button whose popover cites the rule's
                # name and author. It has to READ as an answer in a 380px column —
                # a DOM assertion cannot tell a citation from a squeezed strip.
                rule_chip = page.locator(".dock-section .finding-rule-btn >> visible=true")
                if not rule_chip.count():
                    raise RuntimeError("no visible KB-rule chip on the real report — "
                                       "the popover surface was never photographed")
                rule_chip.first.scroll_into_view_if_needed()
                element_shot(page, ".dock-section .finding-rule-btn",
                             "03f_rule_chip_night")
                rule_chip.first.click()
                page.wait_for_timeout(900)
                element_shot(page, ".rule-popover", "03e_rule_popover_night")
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            ledger_expanded()

            def ledger_scene():
                # "this scene" chip both directions: filter on, then off. Runs
                # BEFORE the shelf opens — with the shelf up no scene page is under
                # the reader, and app.js correctly withholds the chip rather than
                # labelling a scope it cannot see (app.js:6110).
                ledger(page)
                chip = page.locator("#context-dock .fchip-scene >> visible=true")
                if not chip.count():
                    facts["05_debug"] = page.evaluate(
                        "() => ({ dockOpen: !!document.querySelector('#context-dock.open'),"
                        " chips: [...document.querySelectorAll('#context-dock .fchip')].map("
                        "c => c.className + '|' + (c.offsetHeight > 0)) })")
                    raise RuntimeError("no visible This-scene chip to click: "
                                       + json.dumps(facts["05_debug"])[:300])
                before = page.evaluate(MEASURE)["queueRows"]
                chip.first.click()
                page.wait_for_timeout(600)
                shot(page, "04_ledger_night_this_scene")
                facts["05_filtered"] = {"before": before,
                                        "after": facts["04_ledger_night_this_scene"]["queueRows"]}
                page.locator("#context-dock .fchip-scene >> visible=true").first.click()
                page.wait_for_timeout(600)
                facts["05_clears"] = page.evaluate(MEASURE)
                facts["05_restored"] = facts["05_clears"]["queueRows"] == before
            ledger_scene()

            def shelf_night():
                page.keyboard.press("a")
                page.wait_for_timeout(900)
                shot(page, "05_shelf_night")
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
            shelf_night()

            def dawn():
                register(page, True)
                ledger(page)  # the shelf's Escape closed the dock with it
                shot(page, "06_ledger_dawn")
            dawn()

            def dawn_expanded():
                from e2e_browser_common import open_dock_section_holding
                open_dock_section_holding(page, ".finding-note")
                page.wait_for_timeout(600)
                shot(page, "07_ledger_dawn_expanded")
                element_shot(page, ".dock-section .finding-note", "07b_card_dawn")
                element_shot(page, ".dock-section-fixqueue .fix-queue > .craft-panel-head",
                             "07c_fixqueue_dawn")
                page.keyboard.press("a")
                page.wait_for_timeout(900)
                shot(page, "08_shelf_dawn")
            dawn_expanded()

            facts["_js_errors"] = errors[:5]
            browser.close()

    with open(os.path.join(SHOTS, "p1_visual_gate.json"), "w", encoding="utf-8") as f:
        json.dump(facts, f, indent=1, ensure_ascii=False)

    print("\n--- §11 measurements ---")
    bad = []
    for k, v in facts.items():
        if k.startswith("_") or not isinstance(v, dict) or "manuscriptPct" not in v:
            continue
        w = v.get("manuscriptPct")
        rc = v.get("ruleChip")
        line = [k, f"ms={w}%" if w is not None else "ms=?",
                f"secs={v.get('sectionsOpen')}/{v.get('sections')}",
                f"ovfX={v.get('overflowX')}",
                f"chip={rc['w']}px" if rc else "chip=-",
                "OVERLAP" if v.get("surfacesOverlap") else ""]
        if v.get("surfacesOverlap"):
            bad.append(k + " surfaces overlap")
        if (v.get("overflowX") or 0) > 2:
            bad.append(f"{k} horizontal overflow {v['overflowX']}px")
        if w is not None and v.get("dockOpen") and w < 50:
            bad.append(f"{k} manuscript {w}% < 50% with the dock open")
        if v.get("sectionCountsHidden"):
            bad.append(f"{k} a closed section still paints its body")
        rb = v.get("rowBox") or {}
        if rb.get("h", 0) > 260:
            bad.append(f"{k} a queue row stands {rb['h']}px tall — its text column "
                       "is being squeezed by the chips beside it")
        if rc and (rc.get("clipped") or rc.get("w", 0) < 60):
            bad.append(f"{k} the KB-rule chip is unreadable (w={rc.get('w')} "
                       f"clipped={rc.get('clipped')} text={rc.get('text')!r})")
        print("   " + "  ".join(x for x in line if x))
    for n in EL_SHOTS:
        if facts.get(n) != "ok":
            bad.append(f"{n} never reached the pixels ({facts.get(n)})")
    print("\narrival:", (facts.get("02_ledger_night_default") or {}).get("arrivalHeadline"))
    print("scene chip:", facts.get("05_filtered"), "restored:", facts.get("05_restored"))
    if not facts.get("05_filtered"):
        bad.append("the This-scene chip never ran (spec §11 'both directions')")
    elif not facts.get("05_restored"):
        bad.append("the This-scene chip did not restore the queue when cleared")
    print("js errors:", facts.get("_js_errors") or "none")
    print("FAILURES:", bad or "none")
    tmp.cleanup()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
