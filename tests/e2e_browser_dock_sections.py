"""P1.6 gate — the Evidence dock's sections REALLY collapse (plan §5).

The dock's own comment promised "sections stack vertically and collapse under one
header each" while every `.dock-section-title` was a plain div: nothing collapsed,
nothing persisted. This suite pins the contract that makes the sentence true:

  * every ledger section is `.dock-section[data-key][data-open="true|false"]`
  * its header is a real <button> carrying aria-expanded + a chevron
  * the default is CLOSED — and the three orientation surfaces (arrival strip,
    the ONE filter row, the current-scene strip) are NOT sections: they stay
    always visible, so they must have no `.dock-section` ancestor
  * clicking the head flips data-open, follows with aria-expanded, and really
    hides/shows the body (the cards inside are unreachable while closed)
  * the choice is written to prefs["dock_section_<key>"] and survives a reload
  * the height animation sits behind `prefers-reduced-motion: no-preference`:
    under `reduce` the body carries no transition at all

Run:  python tests/e2e_browser_dock_sections.py   (boots its own demo studio;
      set E2E_BASE to reuse an already-running one)
"""
import os
import re

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import (Checks, clicked, launch, note,  # noqa: E402
                                open_dock_section, open_studio)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok

PREFS_JS = "JSON.parse(localStorage.getItem('screenplay_studio.prefs.v1') || '{}')"


def seed_and_analyze(base, title):
    """Upload the fixture and run the demo-model analysis to completion.

    The title is a display hint — the server names the project (safe-id
    charset), so the returned name is always used (same contract as
    e2e_browser_phase6_evidence.py).
    """
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{base}/api/projects",
                          files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    name = r.json().get("project") or r.json().get("name") or title
    r2 = requests.post(f"{base}/api/projects/{name}/analyze",
                       json={"force": True}, timeout=300)
    assert r2.status_code in (200, 201), r2.text[:400]
    return name


def open_project(page, base, name):
    page.goto(base)
    page.wait_for_load_state("networkidle")
    page.locator("#shelf-trigger").hover()
    page.wait_for_timeout(400)
    row = page.locator(".project-item").filter(has_text=name.split("_")[0])
    if not row.count():
        row = page.locator(".project-item").filter(has_text=name.replace("_", " "))
    row.first.click()
    page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)


def open_dock(page):
    page.locator("#right-edge-affordance").click()
    page.wait_for_selector("#context-dock.open", timeout=5000)
    page.wait_for_timeout(450)  # the dock animates width 0 → 380px


def section_head_is_a_button(page):
    """Every header is a real <button type=button> whose aria-expanded matches
    its section's data-open — one attribute the CSS, the tests and the screen
    reader all read."""
    return page.evaluate(
        """() => {
             const hs = [...document.querySelectorAll(
               '.dock-lens[data-lens="evidence"] .dock-section-head')];
             return hs.length > 0 && hs.every((h) => h.tagName === "BUTTON"
               && h.type === "button"
               && h.getAttribute("aria-expanded")
                  === h.closest(".dock-section").getAttribute("data-open"));
           }""")


def transition_duration(page, selector):
    return page.evaluate(
        """(sel) => {
             const el = document.querySelector(sel);
             return el ? getComputedStyle(el).transitionDuration : "missing";
           }""", selector)


def seconds(value):
    """'0.18s' / '1e-06s' / '120ms' -> seconds (None when unparsable).

    The duration is compared numerically because the app has its own global
    reduced-motion clamp (`style.css`: `* { transition-duration: 0.001ms
    !important }`), so under `reduce` the computed value is 1e-06s, not 0s.
    """
    v = (value or "").split(",")[0].strip()
    try:
        if v.endswith("ms"):
            return float(v[:-2]) / 1000.0
        if v.endswith("s"):
            return float(v[:-1])
    except ValueError:
        return None
    return None



# ---------------------------------------------------------------------------
# P1.7 (plan Task 7; spec §5 + §14.3): the scene is a FILTER dimension, never a
# surface of its own. Three claims, three different questions:
#   1. the This-scene chip prints the scope of the count it carries (the N3
#      counting contract: no count without the scope it describes) and turns the
#      ONE filter's scene clause on/off — the live list AND the page ink narrow
#      together, and clearing restores both;
#   2. the DEFAULT stays the whole ledger, all live findings, highs first,
#      grouped by category (red-team W2: a scene-scoped default renders a dead
#      panel on clean scenes and hides cross-scene crown jewels);
#   3. a scene with zero LIVE findings shows the rail's quiet ✓ (spec §14.3),
#      derived from findingDisposition — never a second counter.
# ---------------------------------------------------------------------------
SCENE_CHIP = ".fchip-scene"
LIVE_LIST = '.dock-section[data-key="by-category"]'

# The ledger, asked of the app itself (the gun-pen audit's row-C pattern): how
# many findings are OPEN on `scene`, null meaning the whole script? Counted
# through the app's own contract function — never a second counter in the test —
# under the severity rule the default chips apply, so the number is directly
# comparable with the DOM counts below.
OPEN_ON_SCENE_JS = """(scene) => {
  const sevs = ["high", "medium", "low"];
  let n = 0;
  (state.findings || []).forEach((f, i) => {
    if (findingDisposition(f, i) !== "open") return;
    if (!sevs.includes(((f && f.severity) || "low").toLowerCase())) return;
    if (scene == null) { n += 1; return; }
    const refs = (f && f.scene_refs) || [];
    if (refs.includes(scene) || refs.includes(String(scene))) n += 1;
  });
  return n;
}"""

# Ink, tagged with the scene page that owns it. A bare count of .finding-ink
# cannot answer "did the page narrow?" — the ancestor scene page can.
INK_BY_SCENE_JS = """() => {
  const out = {};
  document.querySelectorAll("#manuscript-container .finding-ink").forEach((m) => {
    const sp = m.closest(".scene-page");
    const n = sp ? sp.dataset.sceneNumber : "?";
    out[n] = (out[n] || 0) + 1;
  });
  return out;
}"""

# Two real lines of text per scene, straight out of the rendered manuscript, so
# the seeded findings below can quote them and the page REALLY inks (the demo
# report carries almost no quotes — this fixture is about the filter, not the
# model). Distinct, non-nested lines only: one mark per line.
SEED_LINES_JS = """(scenes) => {
  const out = {};
  for (const n of scenes) {
    const sp = document.querySelector(
      '#manuscript-container .scene-page[data-scene-number="' + n + '"]');
    if (!sp) continue;
    const picks = [];
    for (const l of sp.querySelectorAll(".el-action, .el-dialogue")) {
      const t = (l.textContent || "").trim();
      if (t.length < 14) continue;
      if (picks.some((p) => p.includes(t) || t.includes(p))) continue;
      picks.push(t);
      if (picks.length === 2) break;
    }
    out[n] = picks;
  }
  return out;
}"""

# Replace the ledger with a fixture this suite owns end to end: two scenes, two
# open findings each, every finding quoting a line that exists (phase13's
# seeding pattern — no model, no server round trip). state.report.findings is
# the dock's source and state.findings the page's, so both move together.
SEED_JS = """(args) => {
  const mk = (cat, sev, scene, quote, issue) => ({
    category: cat, severity: sev, scene_refs: [scene], issue: issue,
    description: issue + " (seeded for the scene-filter fixture)",
    evidence_quote: quote,
  });
  const a = args.a, b = args.b;
  const fs = [
    mk("dialogue", "low", a.scene, a.lines[0], "SEED low dialogue on " + a.scene),
    mk("dialogue", "high", a.scene, a.lines[1], "SEED high dialogue on " + a.scene),
    mk("pacing", "medium", b.scene, b.lines[0], "SEED medium pacing on " + b.scene),
    mk("structure", "low", b.scene, b.lines[1], "SEED low structure on " + b.scene),
  ];
  state.findings = fs;
  state.report = Object.assign({}, state.report || {}, { findings: fs });
  state.findingIds = fs.map((f) => computeFindingId(f));
  state.findingStatus = {};
  state.findingMarks = {};
  state.ghostedIds = new Set();
  state.fixQueue = state.fixQueue || {};
  state.fixQueue.dismissed_flags = [];
  refreshAllFindingSurfaces(); // the ONE re-render entry point (P0.4)
  return { ids: state.findingIds };
}"""

# The rail's marks, as the writer sees them: a clean ✓, or severity dots?
RAIL_MARKS_JS = """() => {
  return [...document.querySelectorAll("#scene-index-list .scene-index-item")].map((it) => {
    const clean = it.querySelector(".scene-index-clean");
    return {
      scene: it.dataset.sceneNumber,
      clean: !!clean,
      cleanLabel: clean ? (clean.getAttribute("aria-label") || "") : null,
      dots: it.querySelectorAll(".scene-index-dots .dot").length,
      aria: it.getAttribute("aria-label") || "",
    };
  });
}"""

# The cards of one category group, in render order — the highs-first contract.
GROUP_CARDS_JS = """(label) => {
  const sec = document.querySelector(
    '.dock-lens[data-lens="evidence"] .dock-section[data-key="by-category"]');
  if (!sec) return null;
  const group = [...sec.querySelectorAll(".dock-cat-group")]
    .find((g) => {
      const t = g.querySelector(".dock-section-title");
      return t && (t.textContent || "").toLowerCase().includes(label.toLowerCase());
    });
  if (!group) return null;
  return [...group.querySelectorAll(".finding-note .finding-note-text")]
    .map((n) => (n.textContent || "").trim());
}"""


def chip_label(lens):
    """The This-scene chip's printed label ("" when the chip is missing)."""
    chip = lens.locator(SCENE_CHIP)
    return (chip.first.inner_text() or "").strip() if chip.count() else ""


def live_cards(lens):
    """Cards in the ledger's live list — the default all-live-findings section."""
    return lens.locator(LIVE_LIST + " .finding-note").count()


def mass_strip_text(lens):
    strip = lens.locator(".dock-mass-total")
    return (strip.first.inner_text() or "").strip() if strip.count() else ""


def click_scene_chip(page, lens):
    """Bounded click: False when the chip could not be clicked (never raises)."""
    try:
        lens.locator(SCENE_CHIP).first.click(timeout=6000)
    except Exception:
        return False
    page.wait_for_timeout(400)  # the full re-render (dock + page + chips)
    return True


def check_scene_filter(page, lens):
    """P1.7 — scene as a FILTER, on the report the app actually analysed.

    The label's scope contract plus the narrowing itself, on real data: no
    fixture. The ink half asserts that every mark still on the page lives in the
    current scene (the demo report quotes almost nothing, so exact ink==list
    parity belongs to the seeded pass below).
    """
    chip = lens.locator(SCENE_CHIP)
    check("P1.7: the ONE filter row carries a This-scene chip",
          chip.count() == 1, f"{chip.count()} .fchip-scene")
    scene = page.evaluate("() => currentManuscriptScene()")
    check("P1.7: the desk knows which scene the writer is on",
          scene is not None, f"currentManuscriptScene()={scene!r}")
    if scene is None:
        return
    check("P1.7: the ledger's live list is open", open_dock_section(page, "by-category"))

    whole_ledger = page.evaluate(OPEN_ON_SCENE_JS, None)
    whole_cards = live_cards(lens)
    off_label = chip_label(lens)
    check("P1.7: chip off — the label prints the scope of its count ('N open')",
          re.match(r"^This scene \u00b7 \d+ open$", off_label) is not None, off_label)
    check("P1.7: the DEFAULT ledger is every live finding, not the current scene's "
          "(red-team W2)",
          whole_cards == whole_ledger and whole_ledger > 0,
          f"cards={whole_cards} ledger={whole_ledger}")
    check("P1.7: with no scene set the mass strip claims no narrowing",
          "shown by filter" not in mass_strip_text(lens), mass_strip_text(lens))

    scoped = page.evaluate(OPEN_ON_SCENE_JS, scene)
    ink_before = page.evaluate(INK_BY_SCENE_JS)
    check("P1.7: this scene holds some of the ledger, not all of it (so narrowing "
          "is provable here)",
          scoped < whole_ledger, f"scene={scene} scoped={scoped} whole={whole_ledger}")

    check("P1.7: clicking the chip lands", click_scene_chip(page, lens))
    on_label = chip_label(lens)
    check("P1.7: chip on — the label prints the scene scope ('N open on this scene')",
          re.match(r"^This scene \u00b7 %d open on this scene$" % scoped,
                   on_label) is not None, on_label)
    check("P1.7: the dock's live list narrows to the current scene",
          live_cards(lens) == scoped, f"cards={live_cards(lens)} scoped={scoped}")
    ink_after = page.evaluate(INK_BY_SCENE_JS)
    check("P1.7: the page ink narrows with it — every mark left is in this scene",
          sum(ink_after.values()) == ink_after.get(str(scene), 0)
          and sum(ink_after.values()) <= sum(ink_before.values()),
          f"before={ink_before} after={ink_after}")
    check("P1.7: the mass strip now labels its narrowed count",
          "shown by filter" in mass_strip_text(lens), mass_strip_text(lens))
    check("P1.7: the filter state carries the scene number",
          page.evaluate("() => state.findingFilter.scene") == scene,
          page.evaluate("() => state.findingFilter.scene"))

    check("P1.7: clicking again clears the scene clause", click_scene_chip(page, lens))
    check("P1.7: the label stops claiming a scene scope",
          re.match(r"^This scene \u00b7 \d+ open$", chip_label(lens)) is not None,
          chip_label(lens))
    check("P1.7: and the whole ledger is back",
          live_cards(lens) == whole_cards, f"cards={live_cards(lens)} whole={whole_cards}")
    check("P1.7: the filter state is null again (cleared, not parked)",
          page.evaluate("() => state.findingFilter.scene") is None,
          page.evaluate("() => state.findingFilter.scene"))


# The writer's own navigation, done by hand: land scene `n` in the middle of the
# viewport so `currentManuscriptScene()` — the scene the chip scopes to — is
# that scene. Rect math, not offsetTop: the container's offsetParent is not part
# of the contract.
SCROLL_TO_SCENE_JS = """(n) => {
  const c = document.getElementById("manuscript-container");
  const sp = c && c.querySelector('.scene-page[data-scene-number="' + n + '"]');
  if (!c || !sp) return null;
  const delta = sp.getBoundingClientRect().top - c.getBoundingClientRect().top
    - Math.round(c.clientHeight / 2) + 40;
  c.scrollTop = Math.max(0, c.scrollTop + delta);
  return currentManuscriptScene();
}"""


def check_seeded_scene_filter(page, lens):
    """P1.7 — the seeded fixture: ink/list parity in both states, highs first,
    and the rail's clean-scene ✓ (spec §14.3, findingDisposition-driven)."""
    scene_a = page.evaluate("() => currentManuscriptScene()")
    check("P1.7/seed: the current scene is known", scene_a is not None, f"{scene_a!r}")
    if scene_a is None:
        return
    numbers = page.evaluate(
        "() => ((state.script && state.script.scenes) || []).map((s) => s.scene_number)")
    lines_map = page.evaluate(SEED_LINES_JS, numbers) or {}
    rich = [n for n in numbers if len(lines_map.get(str(n)) or []) >= 2]
    check("P1.7/seed: the fixture offers two scenes with two quotable lines each",
          len(rich) >= 2, f"scenes={numbers} rich={rich}")
    if len(rich) < 2:
        return
    scene_a, scene_b = rich[0], rich[1]
    scene_c = next((n for n in numbers
                    if str(n) not in (str(scene_a), str(scene_b))), None)
    if scene_c is None:
        check("P1.7/seed: the fixture has a third scene to leave clean", False,
              f"scenes={numbers}")
        return
    landed = page.evaluate(SCROLL_TO_SCENE_JS, scene_a)
    page.wait_for_timeout(350)
    a_lines, b_lines = lines_map.get(str(scene_a)) or [], lines_map.get(str(scene_b)) or []
    check("P1.7/seed: scrolling lands the desk on scene A (the scene the chip scopes to)",
          str(landed) == str(scene_a), f"landed on {landed!r}, wanted {scene_a!r}")

    seeded = page.evaluate(SEED_JS, {"a": {"scene": scene_a, "lines": a_lines},
                                     "b": {"scene": scene_b, "lines": b_lines}}) or {}
    page.wait_for_timeout(400)
    ids = seeded.get("ids") or []
    check("P1.7/seed: the fixture ledger is in place (4 open findings across 2 scenes)",
          page.evaluate(OPEN_ON_SCENE_JS, None) == 4, f"ids={ids}")
    # the ledger re-render collapses the manuscript scroll — the writer scrolls
    # back to the scene they were reading, and THAT is the scene "this scene"
    # means when the chip is clicked.
    relanded = page.evaluate(SCROLL_TO_SCENE_JS, scene_a)
    page.wait_for_timeout(350)
    check("P1.7/seed: after the re-render the desk is back on scene A",
          str(relanded) == str(scene_a), f"landed on {relanded!r}, wanted {scene_a!r}")
    check("P1.7/seed: the live section is open", open_dock_section(page, "by-category"))

    cards = live_cards(lens)
    ink = page.evaluate(INK_BY_SCENE_JS)
    check("P1.7/seed: chip off — the list is EVERY live finding (both scenes)",
          cards == 4, f"cards={cards}")
    check("P1.7/seed: chip off — the ink count equals the list count",
          sum(ink.values()) == cards == 4, f"ink={ink} cards={cards}")
    check("P1.7/seed: and the ink is split across both scenes",
          ink.get(str(scene_a)) == 2 and ink.get(str(scene_b)) == 2, f"ink={ink}")

    group = page.evaluate(GROUP_CARDS_JS, "Dialogue") or []
    check("P1.7: the live groups read highs first",
          len(group) == 2 and group[0].startswith("SEED high")
          and group[1].startswith("SEED low"), f"{group}")

    check("P1.7/seed: clicking the chip lands", click_scene_chip(page, lens))
    cards_on = live_cards(lens)
    ink_on = page.evaluate(INK_BY_SCENE_JS)
    check("P1.7/seed: chip on — the list narrows to the current scene's two findings",
          cards_on == 2, f"cards={cards_on}")
    check("P1.7/seed: chip on — the ink narrows IDENTICALLY (ink count == list count)",
          sum(ink_on.values()) == cards_on == 2
          and ink_on.get(str(scene_a)) == 2 and str(scene_b) not in ink_on,
          f"ink={ink_on} cards={cards_on}")
    check("P1.7/seed: chip on — the label prints the scene scope",
          re.match(r"^This scene \u00b7 2 open on this scene$", chip_label(lens)) is not None,
          chip_label(lens))

    cleared = click_scene_chip(page, lens)
    back_ink = page.evaluate(INK_BY_SCENE_JS)
    check("P1.7/seed: clearing restores the list and the ink together",
          cleared and live_cards(lens) == 4 and sum(back_ink.values()) == 4,
          f"cards={live_cards(lens)} ink={back_ink}")

    # --- spec §14.3: the rail's clean-scene ✓ ------------------------------
    marks = {m["scene"]: m for m in page.evaluate(RAIL_MARKS_JS)}
    a = marks.get(str(scene_a)) or {}
    b = marks.get(str(scene_b)) or {}
    c = marks.get(str(scene_c)) or {}
    check("P1.7/rail: a scene with live findings keeps its severity dots — no ✓",
          a.get("clean") is False and a.get("dots", 0) >= 1
          and b.get("clean") is False and b.get("dots", 0) >= 1,
          f"scene {scene_a}={a} scene {scene_b}={b}")
    check("P1.7/rail: a scene with ZERO live findings shows the quiet ✓ instead",
          c.get("clean") is True and c.get("dots", 0) == 0, f"scene {scene_c}={c}")
    check("P1.7/rail: the ✓ is labelled (aria), not just painted",
          c.get("cleanLabel") == "No live findings"
          and "no live findings" in (c.get("aria") or "").lower(),
          f"glyph={c.get('cleanLabel')!r} item aria={c.get('aria')!r}")

    # The ✓ must read findingDisposition: mark scene B's two findings addressed
    # and its dots have to become the ✓ in the same gesture.
    marked = page.evaluate(
        """(ids) => {
             ids.forEach((id) => { state.findingMarks[id] = "addressed"; });
             refreshAllFindingSurfaces();
             return Object.keys(state.findingMarks).length;
           }""", ids[2:])
    page.wait_for_timeout(300)
    marks2 = {m["scene"]: m for m in page.evaluate(RAIL_MARKS_JS)}
    b2 = marks2.get(str(scene_b)) or {}
    a2 = marks2.get(str(scene_a)) or {}
    check("P1.7/rail: addressed findings stop being live — the ✓ follows "
          "findingDisposition, never a second counter",
          marked == 2 and b2.get("clean") is True and b2.get("dots", 0) == 0
          and a2.get("clean") is False,
          f"marks={marked} scene {scene_b}={b2} scene {scene_a}={a2}")


def run(base):
    name = seed_and_analyze(base, "Ledger Collapse")
    with sync_playwright() as p:
        browser, page, errors = launch(p)
        open_project(page, base, name)
        open_dock(page)
        lens = page.locator('.dock-lens[data-lens="evidence"]')
        # the ledger assembles from the report — bounded wait, so a missing
        # section reports as a NAMED failure instead of crashing the run
        try:
            page.wait_for_selector('.dock-lens[data-lens="evidence"] .dock-section[data-key]',
                                   timeout=20000)
        except Exception:
            note("the ledger rendered no collapsible section (data-key)",
                 "the checks below fail by name")

        # --- 1. the section contract ----------------------------------------
        n_secs = lens.locator(".dock-section").count()
        keyed = lens.locator(".dock-section[data-key]")
        n_keyed = keyed.count()
        check("the ledger renders its collapsible sections",
              n_keyed >= 5, f"{n_keyed} keyed of {n_secs} .dock-section")
        check("every .dock-section IS a collapsible section (data-key on all)",
              n_secs == n_keyed and n_keyed > 0, f"{n_keyed}/{n_secs} keyed")
        keys = [keyed.nth(i).get_attribute("data-key") for i in range(n_keyed)]
        note("section keys", ", ".join(k or "?" for k in keys))
        states = [keyed.nth(i).get_attribute("data-open") for i in range(n_keyed)]
        check("every section declares data-open true|false",
              bool(states) and all(v in ("true", "false") for v in states), str(states))
        check("every section starts CLOSED (P1.6 default)",
              bool(states) and all(v == "false" for v in states), str(states))
        for key in ("fix-queue", "by-category", "coverage"):
            check(f"the plan's section set includes {key!r}", key in keys, str(keys))
        check("the fix-queue section keeps its hook class",
              lens.locator(".dock-section-fixqueue").count() == 1,
              lens.locator(".dock-section-fixqueue").count())

        check("every header is a real <button> with aria-expanded",
              section_head_is_a_button(page))
        chevrons = lens.locator(".dock-section .dock-section-head .dock-section-chevron")
        check("every header carries a chevron",
              n_keyed > 0 and chevrons.count() == n_keyed,
              f"{chevrons.count()} chevrons for {n_keyed} sections")
        check("every craft panel lives inside a collapsible section",
              page.evaluate(
                  """() => {
                       const ps = [...document.querySelectorAll(
                         '.dock-lens[data-lens="evidence"] .craft-panel')];
                       return ps.length > 0 && ps.every((p) => {
                         const s = p.closest(".dock-section");
                         return s && s.getAttribute("data-key");
                       });
                     }"""))

        # --- 2. the orientation surfaces are NOT sections --------------------
        check("the ONE filter row stays outside the collapsibles",
              page.evaluate(
                  """() => { const r = document.querySelector(".dock-filter-row");
                       return !!r && r.offsetParent !== null && !r.closest(".dock-section"); }"""))
        check("the current-scene strip stays outside the collapsibles",
              page.evaluate(
                  """() => { const s = document.querySelector(".dock-evidence-scene");
                       return !!s && !s.closest(".dock-section"); }""")
              and lens.locator(".dock-evidence-scene").is_visible())

        # --- 3. by-category: closed → open, for real -------------------------
        sec = lens.locator('.dock-section[data-key="by-category"]')
        check("the by-category section exists exactly once", sec.count() == 1, sec.count())
        if not sec.count():
            check("the collapse contract was exercised", False,
                  "no by-category section to open (the checks above failed first)")
            check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
            browser.close()
            checks.finish()
        head = sec.locator(".dock-section-head")
        body = sec.locator(".dock-section-body")
        card = sec.locator(".finding-note").first
        check("it starts data-open=false", sec.get_attribute("data-open") == "false",
              sec.get_attribute("data-open"))
        check("its body is hidden while closed",
              body.count() == 1 and not body.is_visible())
        check("the cards inside are unreachable while closed",
              card.count() > 0 and not card.is_visible(),
              f"cards={card.count()}")
        check("clicking the head opens the section",
              clicked(head) and sec.get_attribute("data-open") == "true",
              sec.get_attribute("data-open"))
        page.wait_for_timeout(350)  # the body's height animation settles
        check("aria-expanded follows data-open",
              head.get_attribute("aria-expanded") == "true",
              head.get_attribute("aria-expanded"))
        check("the body is actually shown", body.is_visible())
        check("and so are the cards inside it", card.count() > 0 and card.is_visible())

        stored = page.evaluate(f"() => ({PREFS_JS})['dock_section_by-category']")
        check("the open state is written to prefs[dock_section_<key>]",
              stored is True, repr(stored))

        # --- 4. the choice survives a reload ---------------------------------
        page.reload()
        page.wait_for_load_state("networkidle")
        # the session picks the project back up; if this build lands on the desk
        # instead, reopen it by hand — the PREF is what is under test
        try:
            page.wait_for_selector("#manuscript-container .scene-page", timeout=8000)
        except Exception:
            note("reload landed on the desk", "reopening the project by hand")
            open_project(page, base, name)
        open_dock(page)
        page.wait_for_selector('.dock-lens[data-lens="evidence"] .dock-section[data-key]',
                               timeout=20000)
        sec = lens.locator('.dock-section[data-key="by-category"]')
        check("the open state survives page.reload()",
              sec.count() == 1 and sec.get_attribute("data-open") == "true",
              sec.get_attribute("data-open") if sec.count() else "no section")
        check("the body is open again after the reload (not just the attribute)",
              sec.count() == 1 and sec.locator(".dock-section-body").is_visible())
        keyed = lens.locator(".dock-section[data-key]")
        others = [
            keyed.nth(i).get_attribute("data-open")
            for i in range(keyed.count())
            if keyed.nth(i).get_attribute("data-key") != "by-category"
        ]
        check("the sections the writer never opened are still closed",
              all(v == "false" for v in others), str(others))

        # --- 5. closing persists too -----------------------------------------
        check("clicking again closes it",
              clicked(sec.locator(".dock-section-head"))
              and sec.get_attribute("data-open") == "false")
        page.wait_for_timeout(350)
        check("its body is hidden again", not sec.locator(".dock-section-body").is_visible())
        check("the closed state is written back to prefs too",
              page.evaluate(f"() => ({PREFS_JS})['dock_section_by-category']") is False,
              page.evaluate(f"() => ({PREFS_JS})['dock_section_by-category']"))

        # --- 6. motion: the height animation is opt-in -----------------------
        body_sel = '.dock-section[data-key="by-category"] .dock-section-body'
        page.emulate_media(reduced_motion="reduce")
        reduced = transition_duration(page, body_sel)
        check("under prefers-reduced-motion: reduce the body has no height animation",
              (seconds(reduced) is not None and seconds(reduced) < 0.01), reduced)
        page.emulate_media(reduced_motion="no-preference")
        animated = transition_duration(page, body_sel)
        check("with motion allowed the collapse animates (height transition present)",
              (seconds(animated) is not None and seconds(animated) >= 0.1), animated)

        # --- 7. P1.7: the scene is a FILTER, not a surface (contracts above) --
        check_scene_filter(page, lens)
        check_seeded_scene_filter(page, lens)

        check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()

    checks.finish()


if __name__ == "__main__":
    with open_studio() as studio_base:
        run(studio_base)
