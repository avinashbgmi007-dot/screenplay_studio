"""E2E gate — the withdrawal ledger, in a real browser, against a real server.

The integrity gate withdraws mechanically-false findings before they are carded.
The pipeline test proves the arithmetic (`findings` + `withdrawals` == the
pre-gate list); the report test proves the JSON carries them. Neither proves the
writer can SEE them, and "nothing lost" is only half-kept if the removals are
invisible. This suite drives the whole path for real:

    report.findings.json on disk
      -> GET /report (sanitizer + scene-key pass, which must not drop the field)
      -> client state.report.withdrawals
      -> the Withdrawals dock section, its rows, and its reasons

It does NOT seed the client. The report is written to the project directory and
the page is reloaded, so every hop above is exercised — a client-side seed would
pass even if the server silently stripped the field.

What it pins, in the order the risk matters:

1. NO SECTION when the report carries no withdrawals — the surface is a fact
   about the report, not a permanent empty header.
2. THE FIELD SURVIVES THE SERVE PATH — `/report` returns the withdrawals the
   file holds (the sanitizer rebuilds `findings` and `verification_summary`; it
   must pass unknown top-level keys through, and this is what proves it).
3. THE SECTION EXISTS AND NAMES ITS COUNT — header = "Withdrawals — N left the
   delivered set (…)", so the count is visible while the section is collapsed.
4. EACH ROW CARRIES action + the withdrawn finding's text + the REASON, which is
   the whole point: a removal the writer cannot interrogate is a silent drop.
5. THE NOTE SAYS NOTHING WAS DELETED and points at the file.

Run:  python tests/e2e_browser_withdrawal_ledger.py   (boots its own demo
      studio; set E2E_BASE to reuse an already-running one — but then the
      on-disk injection cannot happen and the suite says so)
"""
import json
import os
import sys
import tempfile

import requests
from playwright.sync_api import sync_playwright

from e2e_browser_common import (Checks, launch, open_dock_section,  # noqa: E402
                                start_studio, studio_headers)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pain_tenglish.fountain")

checks = Checks()
check = checks.ok

# Two removals, one of each action the gate can take, with the real reason
# strings the gate emits (finding_integrity.py). The em dash in the first reason
# is deliberate: it is what the gate actually writes, and it must survive the
# disk -> JSON -> DOM trip.
INJECTED = [
    {"index": 3, "action": "reject",
     "reason": "reports the ABSENCE of a defect \u2014 a clean bill of health filed as a finding",
     "finding": {"category": "dialogue", "severity": "low", "scene_refs": [1],
                 "issue": "WITHDRAWN one: no subtext problem in the opening exchange."}},
    {"index": 5, "action": "merge",
     "reason": "duplicate of #4 (same scene, same evidence/observation)",
     "finding": {"category": "structure", "severity": "medium", "scene_refs": [2],
                 "issue": "WITHDRAWN two: the midpoint turn is stated twice."}},
]


def report_path(projects_dir):
    """The one project's report.findings.json. Derived, not assumed: the project
    directory name is the server's to choose, and the suite must not guess it."""
    for d in sorted(os.listdir(projects_dir)):
        p = os.path.join(projects_dir, d, "report.findings.json")
        if os.path.isfile(p):
            return p
    raise AssertionError(f"no report.findings.json under {projects_dir}")


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


SECTION_JS = """() => {
  const sec = document.querySelector(
    '.dock-lens[data-lens="evidence"] .dock-section[data-key="withdrawals"]');
  if (!sec) return null;
  return {
    title: (sec.querySelector('.dock-section-title') || {}).textContent || '',
    open: sec.getAttribute('data-open'),
    rows: [...sec.querySelectorAll('.dock-wd-row')].map((r) => ({
      action: (r.querySelector('.dock-wd-action') || {}).textContent || '',
      issue: (r.querySelector('.dock-wd-issue') || {}).textContent || '',
      reason: (r.querySelector('.dock-wd-reason') || {}).textContent || '',
    })),
    note: (sec.querySelector('.dock-wd-note') || {}).textContent || '',
  };
}"""


def run(base, projects_dir):
    with sync_playwright() as pw:
        browser, page, errors = launch(pw)
        name = seed_and_analyze(base, "Withdrawal fixture")
        open_project(page, base, name)
        open_dock(page)

        # --- 1. the demo report has no withdrawals: no section, no empty header ---
        absent = page.evaluate(SECTION_JS)
        check("a report with no withdrawals renders NO withdrawals section",
              absent is None, str(absent))

        # --- 2. write the ledger to disk; the serve path must carry it through ---
        path = report_path(projects_dir)
        with open(path, encoding="utf-8") as f:
            report = json.load(f)
        report["withdrawals"] = INJECTED
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f)

        served = requests.get(f"{base}/api/projects/{name}/report",
                              headers=studio_headers(base), timeout=15).json()
        check("GET /report serves the withdrawals written to disk",
              len(served.get("withdrawals") or []) == 2,
              str(len(served.get("withdrawals") or [])))
        check("the serve-time passes do not drop the field or its reasons",
              (served.get("withdrawals") or [{}])[0].get("reason", "").startswith(
                  "reports the ABSENCE of a defect"),
              str((served.get("withdrawals") or [{}])[0].get("reason")))

        # --- 3-5. reload so the CLIENT fetches it, then read the DOM ---
        page.reload()
        page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)
        page.wait_for_timeout(700)
        open_dock(page)
        # The ledger lives inside the collapsed "Context" disclosure at the lens
        # foot, so summon Tier 2 the way the writer does — that OPENS Context and
        # makes the nested headers real click targets (the same step
        # e2e_browser_dock_sections.py takes before opening a nested section).
        page.evaluate("() => setEvidenceTier(2)")
        page.wait_for_timeout(600)

        sec = page.evaluate(SECTION_JS)
        check("the Withdrawals section exists in the Evidence lens", sec is not None, str(sec))
        check("its header names the count and the breakdown",
              sec and "Withdrawals" in sec["title"]
              and "2 left the delivered set" in sec["title"]
              and "1 false" in sec["title"] and "1 duplicate" in sec["title"],
              str(sec and sec["title"]))
        check("the count is legible in the header even while the section is CLOSED "
              "(a ledger header, not a buried line)",
              sec and sec["open"] == "false", str(sec and sec["open"]))

        # A REAL click on the header — the same control a writer presses.
        opened = open_dock_section(page, "withdrawals")
        page.wait_for_timeout(350)
        sec = page.evaluate(SECTION_JS)
        check("clicking its header opens it for real", opened and sec["open"] == "true",
              f"opened={opened} state={sec and sec['open']}")

        rows = (sec or {}).get("rows") or []
        check("both removals are listed, one row each", len(rows) == 2, str(len(rows)))
        check("each row names its action (withdrawn / duplicate)",
              [r["action"].strip().lower() for r in rows] == ["withdrawn", "duplicate"],
              str([r["action"] for r in rows]))
        check("each row carries the withdrawn finding's own text",
              all("WITHDRAWN" in r["issue"] for r in rows),
              str([r["issue"] for r in rows]))
        check("each row carries the REASON it was withdrawn (never a silent drop)",
              all(r["reason"].strip() for r in rows)
              and "ABSENCE of a defect" in rows[0]["reason"],
              str([r["reason"] for r in rows]))
        check("the note says nothing was deleted and names the file",
              "Nothing was deleted" in (sec or {}).get("note", "")
              and "report.findings.json" in (sec or {}).get("note", ""),
              str((sec or {}).get("note")))

        check("no JS page errors", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()

    checks.finish()


if __name__ == "__main__":
    if os.environ.get("E2E_BASE"):
        # The on-disk injection is impossible against a studio we did not boot,
        # so the suite refuses rather than reporting a false green.
        print("E2E_BASE is set: this suite must boot its own studio to write the "
              "report to disk. Unset E2E_BASE and re-run.")
        sys.exit(2)
    with tempfile.TemporaryDirectory(prefix="withdrawals_e2e_") as tmp:
        projects = os.path.join(tmp, "projects")
        os.makedirs(projects, exist_ok=True)
        with start_studio(projects_dir=projects) as studio:
            run(studio.base_url, studio.projects_dir)
