"""E2E gate — the verdict channel, in a real browser, against a real server.

Unit tests prove the store and the routes. They cannot prove the UI exists, that
pressing the control writes the right id, or that the number the writer watches
move is the number the API reports. This suite does.

What it pins, in the order the risk matters:

1. THE ROW EXISTS and asks its own question ("is it right?") with exactly three
   named controls (correct / partial / wrong) — every glyph carries an
   accessible name, same contract as the intent row.
2. THE INTENT ROW IS UNTOUCHED — still exactly 4 glyph verbs, still ONE row.
   The verdict row lives in its own container precisely so it cannot re-wrap the
   row the suite already gates (rung 17's defect, arriving from the other side).
3. A PRESS PERSISTS — ✓ writes the finding's id to the server store, and the
   control reads back as active.
4. IT SURVIVES A RELOAD — the verdict is re-hydrated from `/edits`, not from a
   client-side memory that dies with the tab.
5. THE METER READS IT — the Coverage section prints the accuracy line computed
   from the writer's own verdicts, which is the whole point of the channel.

Run:  python tests/e2e_browser_verdict_channel.py   (boots its own demo studio;
      set E2E_BASE to reuse an already-running one)
"""
import os
import sys

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import (Checks, launch, open_dock_section,  # noqa: E402
                                open_dock_section_holding, open_studio,
                                studio_headers)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok


def click_dom(page, selector):
    """Press a dock-card control the way this repo's other suites do.

    The Evidence lens scrolls: a card's verbs sit far below the fold (measured
    at y≈2140 on a 900px viewport), so Playwright's actionability check refuses
    the click and `clicked()` returns False — which reads exactly like a broken
    control and is really an off-screen element. `e2e_browser_readiness_gate.py`
    hit this first and solved it the same way: dispatch the press in the page,
    where the handler, the fetch and the store are identical to a real click.
    """
    return page.evaluate("""(sel) => {
      const b = document.querySelector(sel);
      if (!b) return false;
      b.click();
      return true;
    }""", selector)

# Deterministic findings, seeded into client state so the suite does not depend
# on what the demo model happened to write. The SERVER round-trip below is real:
# the ids these produce are the ids the routes store and read back.
SEED_JS = """(args) => {
  const mk = (o) => Object.assign({
    description: o.issue + " (seeded for the verdict fixture)",
    why_it_matters: "Seeded so the verdict row has a card to sit on.",
  }, o);
  const fs = [
    mk({ category: "dialogue", severity: "high", scene_refs: [1], evidence_quote: args.quote,
         issue: "VERDICT seed one" }),
    mk({ category: "structure", severity: "medium", scene_refs: [2], evidence_quote: null,
         issue: "VERDICT seed two" }),
    mk({ category: "theme", severity: "low", scene_refs: [], evidence_quote: null,
         issue: "VERDICT seed three" }),
  ];
  state.findings = fs;
  state.report = Object.assign({}, state.report || {}, { findings: fs });
  state.findingIds = fs.map((f) => computeFindingId(f));
  state.findingStatus = {};
  state.findingMarks = {};
  if (args.resetVerdicts !== false) state.findingVerdicts = {};
  state.ghostedIds = new Set();
  state.fixQueue = state.fixQueue || {};
  state.fixQueue.dismissed_flags = [];
  refreshAllFindingSurfaces();
  return { n: fs.length, ids: state.findingIds };
}"""


def seed_and_analyze(base, title):
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{base}/api/projects",
                          headers=studio_headers(base),
                          files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    name = r.json().get("project") or r.json().get("name") or title
    r2 = requests.post(f"{base}/api/projects/{name}/analyze",
                       headers=studio_headers(base), json={"force": True}, timeout=300)
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
    page.wait_for_timeout(450)  # the dock animates width 0 -> 380px


ROW_SHAPE_JS = """() => {
  const card = document.querySelector('.dock-lens[data-lens="evidence"] .finding-note');
  if (!card) return null;
  const row = card.querySelector('.finding-verdict-row');
  const actions = card.querySelector('.finding-note-actions');
  const kids = actions ? [...actions.children].filter((c) => c.getBoundingClientRect().height > 0) : [];
  return {
    hasRow: !!row,
    label: row && row.querySelector('.finding-verdict-label')
      ? row.querySelector('.finding-verdict-label').textContent.trim() : null,
    verdicts: row ? [...row.querySelectorAll('.verdict-btn')].map((b) => ({
      glyph: (b.textContent || '').trim(), aria: b.getAttribute('aria-label') })) : [],
    intentBtns: card.querySelectorAll('.intent-btn').length,
    actionRows: new Set(kids.map((c) => Math.round(c.getBoundingClientRect().top))).size,
    actionH: actions ? Math.round(actions.getBoundingClientRect().height) : null,
    verdictAboveIntent: !!(row && actions
      && row.getBoundingClientRect().top < actions.getBoundingClientRect().top),
  };
}"""


def run(base):
    with sync_playwright() as pw:
        browser, page, errors = launch(pw)
        name = seed_and_analyze(base, "Verdict fixture")
        open_project(page, base, name)
        open_dock(page)

        seeded = page.evaluate(SEED_JS, {"quote": ""})
        page.wait_for_timeout(300)
        open_dock_section_holding(page, ".finding-note")
        page.wait_for_timeout(400)

        # --- 1. the row exists, asks its own question, carries three names ---
        shape = page.evaluate(ROW_SHAPE_JS)
        check("the finding card carries the verdict row", shape and shape["hasRow"], str(shape))
        check("the row asks its own question (is it right?)",
              shape and (shape["label"] or "").lower().startswith("is it right"),
              str(shape and shape["label"]))
        check("exactly three verdicts, each named for a screen reader",
              shape and len(shape["verdicts"]) == 3
              and all((v["aria"] or "").strip() for v in shape["verdicts"]),
              str(shape and shape["verdicts"]))
        check("the truth row sits ABOVE the intent row (two questions, in order)",
              shape and shape["verdictAboveIntent"], str(shape and shape["verdictAboveIntent"]))

        # --- 2. the intent row is untouched (the contract the suite gates) ---
        check("the intent row still carries exactly 4 glyph verbs",
              shape and shape["intentBtns"] == 4, str(shape and shape["intentBtns"]))
        check("the intent row is still ONE row (<=30px), not re-wrapped",
              shape and shape["actionRows"] == 1 and shape["actionH"] <= 30, str(shape))

        # --- 3. pressing ✓ persists, and paints active ---
        landed = click_dom(page, '.dock-lens[data-lens="evidence"] .finding-note '
                                 '.verdict-btn[aria-label^="Correct"]')
        check("the ✓ control is reachable and the press lands", landed,
              "no verdict button found in the dock")
        page.wait_for_timeout(450)
        after = page.evaluate("() => ({ n: Object.keys(state.findingVerdicts || {}).length,"
                              "        v: Object.values(state.findingVerdicts || {}) })")
        check("pressing ✓ records exactly one verdict",
              after["n"] == 1 and after["v"] == ["correct"], str(after))

        active = page.evaluate("""() => {
          const b = document.querySelector('.dock-lens[data-lens="evidence"] '
            + '.finding-note .verdict-btn.active');
          return b ? b.getAttribute('aria-label') : null;
        }""")
        check("the pressed verdict reads back as active", (active or "").startswith("Correct"),
              str(active))

        api = requests.get(f"{base}/api/projects/{name}/findings/verdicts",
                           headers=studio_headers(base), timeout=10).json()
        check("the verdict is persisted server-side (the API agrees)",
              list(api.get("verdicts", {}).values()) == ["correct"], str(api))

        # --- 4. it survives a reload (re-hydrated from /edits, not from memory) ---
        page.reload()
        page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)
        page.wait_for_timeout(700)
        open_dock(page)
        still = page.evaluate("() => Object.values(state.findingVerdicts || {})")
        check("the verdict survives a reload", still == ["correct"], str(still))

        # --- 5. the meter reads it ---
        # Re-seed the population but KEEP the verdict, so the meter has something
        # to count. The seeded ids are content-derived, so the reloaded verdict
        # lands on the same finding.
        page.evaluate(SEED_JS, {"quote": "", "resetVerdicts": False})
        page.wait_for_timeout(300)
        open_dock_section(page, "coverage")
        page.wait_for_timeout(300)
        meter = page.evaluate("""() => {
          const b = document.querySelector('.dock-lens[data-lens="evidence"] .dock-accuracy');
          if (!b) return null;
          return { head: (b.querySelector('.dock-acc-head') || {}).textContent || '',
                   subs: [...b.querySelectorAll('.dock-acc-sub')].map((p) => p.textContent) };
        }""")
        check("the Coverage section prints the accuracy meter", meter is not None, str(meter))
        check("the meter names the writer's own verdicts as its source",
              meter and "Accuracy" in meter["head"] and "judged" in meter["head"], str(meter))
        check("the meter tallies the one verdict that exists (1 correct of 1 judged)",
              meter and "1 correct" in " ".join(meter["subs"]), str(meter))

        check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()

    checks.finish()


if __name__ == "__main__":
    with open_studio() as studio_base:
        run(studio_base)
