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
