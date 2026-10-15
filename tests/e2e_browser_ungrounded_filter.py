"""Ungrounded rows hide by default and return behind an explicit toggle.

Accuracy kit A demotes weak findings (no quote, no observation) with
`ungrounded: True` instead of deleting them. The Fix Queue default view must
not present such a row as a grounded note: it stays out of the rows AND out
of the header counts until the writer explicitly asks for it.

Path under test (no client seeding — the flag is planted in the report on
disk, then the page is loaded, so every hop is exercised):

    report.findings.json on disk (one row gains ungrounded: True)
      -> GET /fixqueue (the allowlist must carry the flag)
      -> the Evidence lens Fix queue section (row absent, counts exclude it)
      -> the "Show ungrounded (N)" toggle (row returns, counts include it)

Run:  python tests/e2e_browser_ungrounded_filter.py
"""
import json
import os
import re
import sys
import tempfile

import requests
from playwright.sync_api import sync_playwright

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from e2e_browser_common import (Checks, assert_no_js_errors, became_true,  # noqa: E402
                                clicked, launch, start_studio,
                                studio_headers)

MARKER = "UNGROUNDED-PROBE-Z9"
CONTEST_MARKER = "CONTESTED-PROBE-Z9"

DOCK_QUEUE = '.dock-lens[data-lens="evidence"] .dock-section-fixqueue'
QUEUE_TITLE = DOCK_QUEUE + " .craft-panel-title"

TITLE_RE = re.compile(r"(\d+) open / (\d+) shown / (\d+) total")


def report_path(projects_dir):
    for d in sorted(os.listdir(projects_dir)):
        p = os.path.join(projects_dir, d, "report.findings.json")
        if os.path.isfile(p):
            return p
    raise AssertionError(f"no report.findings.json under {projects_dir}")


def queue_text(page):
    return page.locator(DOCK_QUEUE).first.text_content(timeout=5000) or ""


def queue_title(page):
    return page.locator(QUEUE_TITLE).first.text_content(timeout=5000) or ""


def run(base, projects_dir):
    checks = Checks()
    headers = studio_headers(base)

    sample = requests.post(f"{base}/api/sample", headers=headers,
                           json={}, timeout=60).json()
    name = sample.get("project")
    checks.ok("sample project created", bool(name), f"got {name!r}")
    if not name:
        checks.finish()
        return
    r = requests.post(f"{base}/api/projects/{name}/analyze",
                      headers=headers, json={}, timeout=300)
    checks.ok("demo analysis accepted", r.status_code in (200, 201),
              f"status={r.status_code} {r.text[:200]}")

    queue = requests.get(f"{base}/api/projects/{name}/fixqueue",
                         headers=headers, timeout=60).json()
    items = queue.get("items") or []
    checks.ok("demo analysis produced a fix queue", len(items) > 0,
              f"{len(items)} items")
    if not items:
        checks.finish()
        return
    n_items = len(items)

    # --- plant the flag in the report on disk (no client seeding) ---
    path = report_path(projects_dir)
    with open(path, encoding="utf-8") as f:
        report = json.load(f)
    findings = report.get("findings") or []
    checks.ok("report carries findings to plant into", len(findings) > 0,
              f"{len(findings)} findings")
    if not findings:
        checks.finish()
        return
    target = findings[0]
    target["ungrounded"] = True
    target["issue"] = (target.get("issue") or "first row") + f" {MARKER}"
    # A second planted row: contested but grounded (carries a quote), so it
    # stays visible by default AND must wear its contested mark. D1.
    if len(findings) > 1:
        second = findings[1]
        second["contested"] = True
        second["evidence_quote"] = second.get("evidence_quote") or "a quoted line"
        second["issue"] = (second.get("issue") or "second row") + f" {CONTEST_MARKER}"
    # Deterministic fixture: the demo pipeline's own evidence floor may flag
    # every row (demo rows carry no quote/observation), which would leave the
    # queue ALL-hidden and prove nothing about the default view. One planted
    # ungrounded row among grounded rows is the case under test.
    for other in findings[1:]:
        other["ungrounded"] = False
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f)

    # --- the wire must carry the flag (the route allowlist) ---
    served = requests.get(f"{base}/api/projects/{name}/fixqueue",
                          headers=headers, timeout=60).json()
    row = next((i for i in served.get("items", [])
                if MARKER in (i.get("issue") or "")), None)
    checks.ok("GET /fixqueue delivers the planted row", row is not None,
              str(served.get("items") and len(served["items"])))
    checks.ok("GET /fixqueue carries ungrounded on the row",
              row is not None and row.get("ungrounded") is True,
              str(row and {k: row.get(k) for k in ("issue", "ungrounded")})
              [:220])
    nungr = sum(1 for i in served.get("items", []) if i.get("ungrounded"))
    checks.ok("exactly the planted row is ungrounded on the wire", nungr == 1,
              f"ungrounded rows={nungr} items={len(served.get('items', []))}")
    ncont = [i for i in served.get("items", [])
             if CONTEST_MARKER in (i.get("issue") or "")]
    checks.ok("GET /fixqueue carries contested on the row",
              len(ncont) == 1 and ncont[0].get("contested") is True,
              str(ncont and {k: ncont[0].get(k) for k in ("issue", "contested")}))
    checks.ok("enough rows for a hide-one/show-rest assertion", n_items >= 2,
              f"{n_items} items")
    if n_items < 2:
        checks.finish()
        return

    with sync_playwright() as pw:
        browser, page, errors = launch(pw)
        page.goto(base)
        page.evaluate("async (n) => { await openProject(n); }", name)
        page.evaluate("() => { openDock('evidence'); setEvidenceTier(1); }")
        page.wait_for_selector(QUEUE_TITLE, state="attached", timeout=15000)
        page.wait_for_selector(DOCK_QUEUE + " .fix-row, "
                               + DOCK_QUEUE + " .craft-panel-title",
                               state="attached", timeout=15000)
        page.wait_for_timeout(500)  # settle the tier gesture

        # --- default view: the row is hidden and the counts exclude it ---
        text = queue_text(page)
        checks.ok("default: the ungrounded row is hidden from the queue",
                  MARKER not in text, text[:220])
        checks.ok("default: the contested row stays visible (grounded)",
                  CONTEST_MARKER in text, text[:220])
        contest_row = page.evaluate(
            f"() => {{ const rows = Array.from(document.querySelectorAll("
            f"'{DOCK_QUEUE} .fix-row')); const hit = rows.find("
            f"n => (n.textContent || '').includes('{CONTEST_MARKER}')); "
            f"return hit ? !!hit.querySelector('.row-flag-contested') : null; }}")
        checks.ok("default: the contested row wears its mark",
                  contest_row is True,
                  "no .row-flag-contested badge on the contested row")
        title = queue_title(page)
        m = TITLE_RE.search(title)
        checks.ok("default: the queue header renders counts", m is not None,
                  f"title={title!r}")
        shown = int(m.group(2)) if m else None
        checks.ok("default: header shown excludes the hidden row",
                  shown == n_items - 1,
                  f"title={title!r} items={n_items} "
                  "(pre-fix: the row is shown, so shown == items)")

        # --- the toggle brings it back ---
        toggle = page.locator(DOCK_QUEUE + " .fq-toggle-ungrounded")
        checks.ok("an explicit ungrounded toggle is offered",
                  toggle.count() > 0, queue_title(page)[:160])
        label = (toggle.first.text_content(timeout=5000) or "") if toggle.count() else ""
        checks.ok("the toggle reads Show ungrounded (N)",
                  "Show ungrounded" in label, f"label={label!r}")
        if toggle.count():
            checks.ok("the toggle is clickable",
                      clicked(toggle.first),
                      "the toggle button never became clickable")
            back = became_true(
                page,
                f"() => (document.querySelector('{DOCK_QUEUE}') || {{}})"
                f".textContent.includes('{MARKER}')",
                timeout=15000)
            checks.ok("toggle: the ungrounded row returns", back,
                      queue_text(page)[:220])
            ungr_row = page.evaluate(
                f"() => {{ const rows = Array.from(document.querySelectorAll("
                f"'{DOCK_QUEUE} .fix-row')); const hit = rows.find("
                f"n => (n.textContent || '').includes('{MARKER}')); "
                f"return hit ? !!hit.querySelector('.row-flag-ungrounded') : null; }}")
            checks.ok("toggle: the returned row wears its ungrounded mark",
                      ungr_row is True,
                      "no .row-flag-ungrounded badge on the returned row")
            title2 = queue_title(page)
            m2 = TITLE_RE.search(title2)
            checks.ok("toggle: header shown includes it again",
                      m2 is not None and int(m2.group(2)) == n_items,
                      f"title={title2!r} items={n_items}")

        assert_no_js_errors(checks, errors)
        browser.close()

    checks.finish()


if __name__ == "__main__":
    if os.environ.get("E2E_BASE"):
        print("E2E_BASE is set: this suite must boot its own studio to write "
              "the report to disk. Unset E2E_BASE and re-run.")
        sys.exit(2)
    with tempfile.TemporaryDirectory(prefix="ungrounded_e2e_") as tmp:
        projects = os.path.join(tmp, "projects")
        os.makedirs(projects, exist_ok=True)
        with start_studio(projects_dir=projects) as studio:
            run(studio.base_url, studio.projects_dir)
