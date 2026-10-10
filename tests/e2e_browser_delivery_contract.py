"""E2E gate — the delivery contract, in a real browser, against a real server.

Gate 8's Python guard proves every documented report field REACHES the
`/findings` row. It cannot prove the field reaches a RENDERER — that is the other
half of the contract ("lands in a named renderer or is declared internal"), and
it is the half that failed: `rule_id` and `check_id` had renderers in the client
all along while the route dropped the fields, so the wire was missing and no
unit test could see it.

This suite drives the whole path for real:

    report.findings.json on disk
      -> GET /report and GET /findings (sanitizer + scene-key pass)
      -> the Evidence lens deep card
      -> the observation line, the KB-rule chip, the mechanical-check line

It does NOT seed the client: the report is written to the project directory and
the page reloaded, so every hop is exercised.

What it pins:

1. NO OBSERVATION LINE on a report that carries none — the line is a fact about
   the finding, not permanent chrome.
2. THE OBSERVATION REACHES THE CARD, verbatim, from disk.
3. IT SITS ABOVE THE QUOTE — the quote is the evidence FOR the observation;
   reading them in the other order is what makes a note feel asserted.
4. THE ATTRIBUTION SURVIVES THE ROUTE — the KB-rule chip (rule_id) and the
   mechanical-check line (check_id) render from the injected finding.
5. A MERGE IS INSPECTABLE — `merged_findings` (the dedupe's absorbed claims)
   renders as a COLLAPSED disclosure on the deep card, OUTSIDE the pinned action
   row, and opens onto the absorbed finding's own words.
6. A RECOVERY IS NOT A FAILURE — `recoveries` renders as a quiet run caveat,
   injected with zero errors and no failed categories, and is never nested inside
   the failure banner (whose head reads "N passes reported a problem").

Run:  python tests/e2e_browser_delivery_contract.py
"""
import json
import os
import sys
import tempfile

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import Checks, launch, start_studio, studio_headers  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok

OBSERVATION = "MARA states the revelation aloud in one line, in scene 1."
# A REAL knowledge-base id, deliberately: the serve path validates `rule_id`
# against the KB (the schema says it MUST resolve), so an invented id comes back
# null and the chip never renders. That validation is correct — this suite has to
# use an id the product would actually emit.
RULE_ID = "comedy_subtext_not_literal"          # "Dialogue Must Have Subtext"
CHECK_ID = "voice_bleed"
QUOTE = "I'll tell you everything when this is over."
# The two fields added to this suite second. Both were DELIVERED on the wire and read
# by nothing in the desk — the same class of defect as the dropped `rule_id`, caught
# this time by asking "which renderer?" of every documented field.
MERGED_ISSUE = "The same beat is restated instead of escalated."
MERGED_OBS = "In scene 1 the beat repeats without raising the stakes."
MERGED_QUOTE = "This is not what we agreed."
MERGED_RULE = "comedy_subtext_not_literal"
RECOVERY_NOTE = ("Dialogue analysis: the model's reply hit its output limit on 1 chunk(s) "
                 "(scenes 4-6) and the chunk was re-run in smaller pieces.")


def report_path(projects_dir):
    for d in sorted(os.listdir(projects_dir)):
        p = os.path.join(projects_dir, d, "report.findings.json")
        if os.path.isfile(p):
            return p
    raise AssertionError(f"no report.findings.json under {projects_dir}")


def seed_and_analyze(base, title):
    with open(FIXTURE, "rb") as f:
        r = requests.post(f"{base}/api/projects", headers=studio_headers(base),
                          files={"file": (f"{title}.fountain", f, "text/plain")},
                          data={"title": title}, timeout=60)
    assert r.status_code in (200, 201), r.text
    name = r.json().get("project") or r.json().get("name") or title
    r2 = requests.post(f"{base}/api/projects/{name}/analyze", headers=studio_headers(base),
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
    page.wait_for_timeout(450)
    page.evaluate("() => setEvidenceTier(2)")   # paints the deep cards
    page.wait_for_timeout(600)


CARD_JS = """() => {
  const cards = [...document.querySelectorAll(
    '.dock-lens[data-lens="evidence"] .finding-note')];
  const withObs = cards.find((c) => c.querySelector('.finding-deep-observation'));
  const withCheck = cards.find((c) => c.querySelector('.finding-check'));
  const out = {cards: cards.length, found: !!withObs};
  if (withObs) {
    const deep = withObs.querySelector('.finding-deep');
    out.observation = (withObs.querySelector('.finding-deep-observation') || {}).textContent || '';
    out.quote = (withObs.querySelector('.finding-deep-quote') || {}).textContent || '';
    out.rule = (withObs.querySelector('.finding-rule-btn') || {}).textContent || '';
    out.order = [...deep.children].map((n) => n.className);
  }
  out.check = withCheck ? ((withCheck.querySelector('.finding-check') || {}).textContent || '') : '';
  return out;
}"""

MERGED_JS = """() => {
  const cards = [...document.querySelectorAll(
    '.dock-lens[data-lens="evidence"] .finding-note')];
  const card = cards.find((c) => c.querySelector('.finding-merged'));
  const out = {cards: cards.length, found: !!card};
  if (!card) return out;
  const wrap = card.querySelector('.finding-merged');
  const btn = wrap.querySelector('.finding-merged-toggle');
  const body = wrap.querySelector('.finding-merged-body');
  out.label = (btn && btn.textContent) || '';
  out.expandedBefore = btn && btn.getAttribute('aria-expanded');
  out.hiddenBefore = !!(body && body.hidden);
  out.inActions = !!(btn && btn.closest('.finding-note-actions'));
  out.bodyText = (body && body.textContent) || '';
  if (btn) btn.click();
  out.expandedAfter = btn && btn.getAttribute('aria-expanded');
  out.hiddenAfter = !!(body && body.hidden);
  return out;
}"""

CAVEAT_JS = """() => {
  const lens = document.querySelector('.dock-lens[data-lens="evidence"]');
  const caveat = lens && lens.querySelector('.run-caveat');
  return {
    found: !!caveat,
    text: caveat ? caveat.textContent : '',
    inBanner: !!(caveat && caveat.closest('.failure-banner')),
  };
}"""


def run(base, projects_dir):
    with sync_playwright() as pw:
        browser, page, errors = launch(pw)
        name = seed_and_analyze(base, "Delivery fixture")
        open_project(page, base, name)
        open_dock(page)

        before = page.evaluate(CARD_JS)
        check("the demo report carries no observation: no observation line renders",
              not before["found"], str(before))

        # inject the fields the route used to drop
        path = report_path(projects_dir)
        with open(path, encoding="utf-8") as f:
            report = json.load(f)
        findings = report.get("findings") or []
        assert findings, "the demo analysis produced no findings to inject into"
        target = findings[0]
        target["observation"] = OBSERVATION
        target["rule_id"] = RULE_ID
        target["check_id"] = None
        target["evidence_source"] = "pages"
        target["evidence_quote"] = QUOTE
        target["merged_rule_ids"] = []
        # The absorbed half of a merge: the dedupe preserves it in `merged_findings`,
        # and until now the desk showed only the survivor.
        target["merged_findings"] = [{
            "category": "dialogue",
            "issue": MERGED_ISSUE,
            "severity": "medium",
            "scene_refs": [1],
            "evidence_quote": MERGED_QUOTE,
            "observation": MERGED_OBS,
            "rule_id": MERGED_RULE,
        }]
        # The run caveat. Deliberately injected with NO errors and no failed
        # categories, so the suite proves the caveat renders on its own — a run can
        # split a chunk and still report every pass `ok`.
        report["recoveries"] = [RECOVERY_NOTE]
        # A SECOND finding carries only a check_id. The card shows the KB-rule
        # chip OR the mechanical-check line, never both — a check is a
        # measurement with no authority to cite, a rule is a button you can ask
        # — so one finding cannot prove both renderers.
        second = dict(target)
        second["issue"] = (target.get("issue") or "second row") + " (second row)"
        second["observation"] = "A second observation, on its own row."
        second["rule_id"] = None
        second["check_id"] = CHECK_ID
        second["evidence_quote"] = None
        # Only ONE card carries the merge, so the probe cannot read the wrong one.
        second["merged_findings"] = None
        findings.append(second)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f)

        # --- the route must carry them (the wire Gate 8 repaired) ---
        served = requests.get(f"{base}/api/projects/{name}/findings",
                              headers=studio_headers(base), timeout=15).json()
        row = next((i for i in served.get("items", []) if i.get("observation") == OBSERVATION), None)
        check("GET /findings delivers the observation it was dropping", row is not None,
              str(served.get("count")))
        check("GET /findings delivers rule_id and evidence_source",
              row is not None and row.get("rule_id") == RULE_ID
              and row.get("evidence_source") == "pages",
              str(row and {k: row.get(k) for k in ("rule_id", "check_id", "evidence_source")}))
        row2 = next((i for i in served.get("items", []) if i.get("check_id") == CHECK_ID), None)
        check("GET /findings delivers check_id on the finding that carries it",
              row2 is not None, str(row2 and row2.get("check_id")))

        # --- reload so the CLIENT fetches it, then read the DOM ---
        page.reload()
        page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)
        page.wait_for_timeout(700)
        open_dock(page)

        card = page.evaluate(CARD_JS)
        check("the observation renders in the deep card", card["found"], str(card))
        check("it renders verbatim, from disk to DOM",
              card.get("observation") == OBSERVATION, str(card.get("observation")))
        check("the KB-rule chip renders from rule_id (craft attribution is the product)",
              RULE_ID in (card.get("rule") or ""), str(card.get("rule")))
        check("the mechanical-check line renders from check_id",
              CHECK_ID in (card.get("check") or ""), str(card.get("check")))
        order = card.get("order") or []
        # Unconditional on purpose: a check inside an `if` records NOTHING when
        # the guard is false, which is how a suite silently stops checking.
        # test_browser_check_hygiene ratchets that, and it is right to.
        check("the observation sits ABOVE the quote (the claim, then its evidence)",
              "finding-deep-observation" in order and "finding-deep-quote" in order
              and order.index("finding-deep-observation") < order.index("finding-deep-quote"),
              str(order))

        # --- the two fields the desk dropped on the floor ---------------------
        merged = page.evaluate(MERGED_JS)
        check("the absorbed claims of a merge render on the card", merged["found"], str(merged))
        check("the disclosure is COLLAPSED by default — a merge is inspectable, not shown twice",
              merged.get("hiddenBefore") is True and merged.get("expandedBefore") == "false",
              str(merged))
        check("it sits OUTSIDE the pinned action row (that row is 4 verbs, one row, <=30px)",
              merged.get("inActions") is False, str(merged))
        check("the absorbed finding's own words and rule are inside, verbatim",
              MERGED_ISSUE in (merged.get("bodyText") or "")
              and MERGED_RULE in (merged.get("bodyText") or ""),
              str(merged.get("bodyText"))[:220])
        check("opening it flips aria-expanded and reveals the body",
              merged.get("hiddenAfter") is False and merged.get("expandedAfter") == "true",
              str(merged))

        caveat = page.evaluate(CAVEAT_JS)
        check("the run caveat reaches the desk (before this it reached report.md only)",
              caveat["found"], str(caveat))
        check("it renders the note verbatim, from disk to DOM",
              RECOVERY_NOTE in (caveat.get("text") or ""), str(caveat.get("text"))[:220])
        check("a recovery is NOT dressed as a failure (never inside the failure banner)",
              caveat.get("inBanner") is False, str(caveat))

        check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()

    checks.finish()


if __name__ == "__main__":
    if os.environ.get("E2E_BASE"):
        print("E2E_BASE is set: this suite must boot its own studio to write the "
              "report to disk. Unset E2E_BASE and re-run.")
        sys.exit(2)
    with tempfile.TemporaryDirectory(prefix="delivery_e2e_") as tmp:
        projects = os.path.join(tmp, "projects")
        os.makedirs(projects, exist_ok=True)
        with start_studio(projects_dir=projects) as studio:
            run(studio.base_url, studio.projects_dir)
