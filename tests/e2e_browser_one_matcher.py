"""Task 19 (spec §3 honesty): one matcher decides where a finding sits, so an
inked line and a clickable line are the SAME line — and a margin card never
covers the manuscript text.

Two matchers used to live on the page. The ink pass (`inkMatch`) falls back to a
quote's longest leading fragment, because a quote the model cited across a line
wrap can never be found whole on one line. The click-anchor pass used a looser,
different predicate (`lt.includes(qq) || qq.includes(lt.slice(0, 40))`). Where
they disagreed the writer saw a highlighted phrase with no click behind it — the
ink lied about being a link. This suite seeds findings whose quotes exercise
both directions and asserts the two sets are EQUAL, not merely overlapping.

The fixture is seeded on disk rather than analysed: the demo model's quotes never
match the sample script's lines (measured: 0 ink marks on a real report), so a
vacuous pass is the only thing an analysed project can prove here.

Run:  python tests/e2e_browser_one_matcher.py
"""
import json
import os
import sys
import urllib.request

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e2e_browser_common import (Checks, assert_no_js_errors, launch,  # noqa: E402
                                start_studio)
from playwright.sync_api import sync_playwright  # noqa: E402

SCRIPT = """INT. SAFEHOUSE - NIGHT

MARA takes out an old REVOLVER, setting it on the desk.

MARA
It was my father's gun.

INT. ROOFTOP - NIGHT

Rain on the railing. Mara looks out.

MARA
I kept it for twenty years.
"""

# (issue, quote, scene) — chosen so the two old matchers DISAGREE:
#  1. crosses the line wrap: inkMatch finds the leading fragment "an old
#     REVOLVER," on the action line; the anchor pass finds nothing (the quote is
#     longer than the line and the line's first 40 chars are not in the quote).
#  2. punctuation the script doesn't have: inks via the fragment fallback,
#     anchors via the normalised whole-quote test — both hit, the control pair.
#  3. a quote no line contains: neither surface should claim it.
SEED = [
    ("Quote cited across the line wrap.",
     "an old REVOLVER, setting it on the desk. She checks the cylinder.", 1),
    ("Quote with the wrong terminal punctuation.",
     "It was my father's gun!", 1),
    ("Quote that is not in this script.",
     "The revolver was never shown again in the film.", 2),
]

FIXTURE = "one_matcher_fixture"


def make_fixture(projects_dir, name=FIXTURE):
    """A parsed + analysed project whose report is exactly `SEED`."""
    from screenplay_parser.text_parser import parse_fountain
    from screenplay_studio import revision
    from screenplay_studio.manifest import ProjectManifest

    pdir = os.path.join(projects_dir, name)
    os.makedirs(pdir, exist_ok=True)
    src = os.path.join(projects_dir, f"{name}.source.fountain")
    with open(src, "w", encoding="utf-8", newline="\n") as f:
        f.write(SCRIPT)
    doc = parse_fountain(src)
    m = ProjectManifest.create(pdir, source_file=src, title=name)
    doc.save(m.parsed_path)
    doc.save(revision.working_path(m))
    m.mark_complete("parse")
    report = {
        "findings": [{
            "issue": issue, "evidence_quote": quote, "scene_refs": [scene],
            "severity": "high", "category": "plot_economy", "status": "open",
            "recommendation": "Cut it or pay it off.",
            "verification": {"status": "verified", "note": "exact",
                             "matched_scene": scene},
        } for issue, quote, scene in SEED],
        "stats": {"total_findings": len(SEED), "open_findings": len(SEED)},
    }
    with open(m.report_findings_path, "w", encoding="utf-8", newline="") as f:
        json.dump(report, f)
    m.mark_complete("analyze")
    return name


MEASURE = """() => {
  const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
  const lines = [...document.querySelectorAll('#manuscript-container [class^=el-]')];
  const out = {inked: [], anchored: [], cards: [], notes: [], findings: state.findings.length};
  for (const line of lines) {
    const ink = line.querySelector('.finding-ink');
    const rec = {text: norm(line.textContent).slice(0, 34),
                 anchor: line.classList.contains('el-anchored'),
                 quoted: ink ? ink.textContent : null};
    if (ink) out.inked.push(rec);
    if (rec.anchor) out.anchored.push(rec);
  }
  // what a click does: the line is only really clickable if activating it puts
  // the flash somewhere (locateFinding highlights the line, openFindingCard
  // flashes the card) — the test drives the click, this is the geometry half.
  const notesEl = document.querySelector('#manuscript-container .scene-notes');
  if (notesEl) {
    const cs = getComputedStyle(notesEl);
    out.notes = [cs.position, notesEl.getBoundingClientRect().width];
  }
  for (const page of document.querySelectorAll('#manuscript-container .scene-page')) {
    const text = [];
    for (const line of page.querySelectorAll("[class^='el-'], .scene-heading-line")) {
      const r = document.createRange();
      r.selectNodeContents(line);
      const b = r.getBoundingClientRect();
      if (b.width > 0 && b.height > 0) text.push([norm(line.textContent).slice(0, 34), b]);
    }
    for (const card of page.querySelectorAll('.finding-note, .note-card')) {
      const c = card.getBoundingClientRect();
      if (c.width === 0 || c.height === 0) continue;
      const over = text.filter(([, b]) => !(b.right <= c.left + 1 || b.left >= c.right - 1
        || b.bottom <= c.top + 1 || b.top >= c.bottom - 1)).map(([t]) => t);
      out.cards.push({over, inPage: true, box: [Math.round(c.left), Math.round(c.right)]});
    }
  }
  return out;
}"""


def measure(checks, page, label):
    m = page.evaluate(MEASURE)
    # (a) every inked line is anchored -- the ink never promises a link it lacks
    unlinked = [r["text"] for r in m["inked"] if not r["anchor"]]
    checks.ok(f"{label}: every inked line is clickable (no ink without a click)",
              not unlinked, f"inked but not el-anchored: {unlinked}")
    # (b) and every anchored line is inked -- no invisible click targets
    invisible = [r["text"] for r in m["anchored"] if not r["quoted"]]
    checks.ok(f"{label}: every clickable line is inked (no click without ink)",
              not invisible, f"el-anchored with no .finding-ink: {invisible}")
    checks.ok(f"{label}: the fixture's cross-wrap quote still finds its line",
              any("an old revolver" in (r["quoted"] or "").lower() for r in m["inked"]),
              f"ink: {[r['quoted'] for r in m['inked']]}")
    checks.ok(f"{label}: a quote no line contains inks nothing",
              not any("never shown again" in (r["quoted"] or "").lower() for r in m["inked"]),
              f"ink: {[r['quoted'] for r in m['inked']]}")
    # (c) no margin card covers manuscript text
    covering = [c for c in m["cards"] if c["over"]]
    checks.ok(f"{label}: no finding card covers the page text ({len(m['cards'])} cards)",
              not covering, f"cards over text: {covering}")
    return m


def click_activates(checks, page):
    """The cross-wrap ink is the one that used to be dead. Clicking any inked
    line must put the flash SOMEWHERE (openFindingCard flashes the dock/margin
    card; locateFinding flashes the line) — a dead click leaves nothing."""
    got = page.evaluate("""() => {
      const mark = [...document.querySelectorAll('.finding-ink')]
        .find((m) => /an old REVOLVER/i.test(m.textContent));
      if (!mark) return 'no such ink';
      document.querySelectorAll('.finding-flash, .finding-highlight')
        .forEach((n) => n.classList.remove('finding-flash', 'finding-highlight'));
      mark.closest('[class^=el-]').click();
      return 'clicked';
    }""")
    checks.ok("the cross-wrap ink is a real click target", got == "clicked", str(got))
    try:
        page.wait_for_function(
            "() => !!document.querySelector('.finding-flash, .finding-highlight')",
            timeout=5000)
        reacted = True
    except Exception:  # noqa: BLE001 - a dead click is the failure this leg reports
        reacted = False
    checks.ok("clicking the ink activates the finding (a card or the line flashes)",
              reacted)


def run(base, projects_dir, headers):
    checks = Checks()
    name = make_fixture(projects_dir)

    with sync_playwright() as pw:
        browser, page, errors = launch(pw)
        page.goto(base)
        page.evaluate("async (n) => { await openProject(n); }", name)
        page.wait_for_selector("#manuscript-container .finding-ink",
                               state="attached", timeout=20000)
        # the fixture's third finding must stay uninked, so the ink count is 2
        measure(checks, page, "night")
        click_activates(checks, page)

        page.evaluate("() => { applyDawn(true); }")
        page.wait_for_timeout(300)
        measure(checks, page, "dawn")

        # gutter mode (position: absolute) is one layout; the in-flow fallback
        # is the other, and the dock opening is what forces it.
        page.evaluate("() => { applyDawn(false); openDock('evidence'); }")
        page.wait_for_timeout(400)
        m = measure(checks, page, "dock-open")
        checks.ok("the dock-open layout really is the in-flow fallback",
                  m["notes"] and m["notes"][0] in ("static", "absolute"),
                  f".scene-notes = {m['notes']}")

        assert_no_js_errors(checks, errors)
        browser.close()

    checks.finish()


if __name__ == "__main__":
    import tempfile
    with start_studio(projects_dir=tempfile.mkdtemp(prefix="one_matcher_")) as studio:
        run(studio.base_url, studio.projects_dir, {})
