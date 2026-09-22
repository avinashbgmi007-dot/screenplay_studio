"""One counting path (plan P0.3, the N3 law): the fix-queue header, the dawn
meter, the `#finding-summary` chips and the revision strip must ALL print
counts derived from `findingDisposition` / `findingCounts` / `queueCounts` —
never from the raw server-observed `item.status`.

Why this suite exists: the server observes status from the WORKING COPY diff
(`findings_status`), while the writer's intent lives in a second store
(`finding_marks.json`, read into `state.findingMarks`). Two stores, and the
queue header + dawn meter read the wrong one: marking a finding
intent=addressed moved the summary chips (they read `findingDisposition`) but
left the queue header and the dawn meter unchanged, so the desk printed two
different "open" numbers at the same moment. The contract: writer intent moves
ALL of them, never a subset.

The expectation is computed in the page from the app's own contract functions
(`findingDisposition` over `state.findings`), the same shape as the gun-pen
audit's row C — so this suite asserts surfaces AGREE WITH THE LEDGER, not with
a number this file hardcodes.

Run:  python tests/e2e_browser_counting_contract.py
"""
import json
import os
import re
import sys
import urllib.request

# Running a script puts only its own directory on sys.path; the repo root goes
# on explicitly (same pattern as e2e_browser_finding_id_parity.py).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from e2e_browser_common import (Checks, assert_no_js_errors, launch,  # noqa: E402
                                open_dock_section_holding)
from playwright.sync_api import sync_playwright  # noqa: E402


def post(base, path, body=None):
    req = urllib.request.Request(
        base + path, data=json.dumps(body or {}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode() or "{}")


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=60) as r:
        return json.loads(r.read().decode() or "{}")


# The disposition ledger, asked of the app itself: open = findings whose
# findingDisposition is "open"; total = the whole report (nothing dismissed is
# seeded here, so the queue's ledger is the report's finding list).
# P1.10: the craft shelf no longer embeds a copy of the queue, so the desk has
# ONE queue header to read - the ledger's. (Before, .first silently picked the
# shelf clone and the contract was checked against a duplicate.)
DOCK_QUEUE_TITLE = ".dock-section-fixqueue .fix-queue .craft-panel-title"

CONTRACT_JS = """() => {
  const findings = state.findings || [];
  let open = 0;
  findings.forEach((f, i) => { if (findingDisposition(f, i) === "open") open += 1; });
  return { open, total: findings.length };
}"""


def read_surfaces(page):
    """The three desk count surfaces, parsed from what the writer actually sees."""
    title = page.locator(DOCK_QUEUE_TITLE).first.text_content() or ""
    m = re.search(r"(\d+) open / (\d+) shown / (\d+) total", title)
    chip = page.locator("#finding-summary .fs-chip.open").first.text_content() or ""
    mc = re.search(r"(\d+)\s*open", chip)
    dawn = page.locator(".dawn-pct").first.text_content() or ""
    mdawn = re.search(r"(\d+)%", dawn)
    return {
        "queue_open": int(m.group(1)) if m else None,
        "queue_total": int(m.group(3)) if m else None,
        "chip_open": int(mc.group(1)) if mc else None,
        "dawn_pct": int(mdawn.group(1)) if mdawn else None,
        "raw": f"title={title!r} chip={chip!r} dawn={dawn!r}",
    }


def expected_dawn_pct(ledger):
    if not ledger["total"]:
        return 0
    return round(100 * (ledger["total"] - ledger["open"]) / ledger["total"])


# Disposition ledger, asked of the app itself: how many findings the writer
# has resolved (intent OR observed) — the number every "done" style must match.
ADDRESSED_JS = """() => {
  const findings = state.findings || [];
  let n = 0;
  findings.forEach((f, i) => { if (findingDisposition(f, i) === "addressed") n += 1; });
  return n;
}"""


def test_intent_updates_every_mounted_surface(base, checks):
    """P0.4: refreshAllFindingSurfaces — marking an intent in the dock must
    re-render EVERY mounted finding surface in the same gesture, with no
    reload: the dock card, the summary chips, AND a mounted #feedback-fixqueue
    tab, plus a fresh metrics pull. Pre-fix, setFindingIntent re-rendered the
    dock + manuscript but never the queue tab, so the desk's own queue kept
    counting the marked finding as open until something else re-rendered it.
    """
    sample = post(base, "/api/sample")
    name = sample.get("project")
    checks.ok("intent-e2e: sample project created", bool(name), f"got {name!r}")
    if not name:
        return
    post(base, f"/api/projects/{name}/analyze")
    queue = get(base, f"/api/projects/{name}/fixqueue")
    items = queue.get("items") or []
    checks.ok("intent-e2e: demo analysis produced a fix queue",
              len(items) > 0, f"{len(items)} items")
    if not items:
        return

    with sync_playwright() as pw:
        browser, page, errors = launch(pw)
        page.goto(base)
        page.evaluate("async (n) => { await openProject(n); }", name)
        page.wait_for_selector("#finding-summary .fs-chip.open",
                               state="attached", timeout=15000)

        # Mount BOTH surfaces: the Feedback room's Fix Queue tab and the
        # dock's Evidence lens (the deep cards there carry the intent buttons).
        page.evaluate("async () => { await loadFeedbackPanels(); }")
        page.evaluate("() => { setRoom('feedback'); switchFeedbackTab('fixqueue'); }")
        page.wait_for_selector("#feedback-fixqueue .fix-row",
                               state="attached", timeout=15000)
        page.evaluate("() => { openDock('evidence'); }")
        page.wait_for_selector('.dock-lens[data-lens="evidence"] .finding-note',
                               state="attached", timeout=15000)
        # P1.6: the dock's cards live behind collapsible section headers, and a
        # closed body is hidden (not clickable). Open the section holding them —
        # the writer's own first move.
        checks.ok("intent-e2e: the section holding the dock cards opens",
                  open_dock_section_holding(page, ".finding-note") > 0)

        # spy on the metrics pull — a mutation must leave the strip fresh
        page.evaluate("""() => {
          window.__metricCalls = 0;
          const orig = refreshMetrics;
          window.refreshMetrics = function () { window.__metricCalls += 1; return orig(); };
        }""")

        ledger0 = page.evaluate(CONTRACT_JS)
        title0 = page.locator("#feedback-fixqueue .craft-panel-title").first.text_content() or ""

        # the writer marks the first dock card addressed — ONE gesture
        chip0 = page.locator("#finding-summary .fs-chip.open").first.text_content() or ""
        card = page.locator('.dock-lens[data-lens="evidence"] .finding-note').first
        card.locator('.intent-btn[title^="My call"]').click()
        # the round-trip completed once the summary chips re-render (an
        # addressed card leaves the dock's open list, so the chips are the
        # stable post-mark signal)
        page.wait_for_function(
            "(t) => { const c = document.querySelector('#finding-summary .fs-chip.open');"
            " return c && c.textContent !== t; }",
            arg=chip0, timeout=15000)

        ledger1 = page.evaluate(CONTRACT_JS)
        checks.ok("intent-e2e: the mark reached the client ledger (one fewer open)",
                  ledger1["open"] == ledger0["open"] - 1
                  and ledger1["total"] == ledger0["total"],
                  f"before={ledger0} after={ledger1}")

        chip = page.locator("#finding-summary .fs-chip.open").first.text_content() or ""
        checks.ok("intent-e2e: the summary chips moved with the mark",
                  f"{ledger1['open']} open" in chip,
                  f"chip={chip!r} ledger={ledger1}")

        # THE contract: the mounted Fix Queue tab shows the SAME ledger NOW —
        # no reload, no tab switch, no second gesture.
        title1 = page.locator("#feedback-fixqueue .craft-panel-title").first.text_content() or ""
        m = re.search(r"(\d+) open /", title1)
        checks.ok("intent-e2e: the mounted Fix Queue tab re-rendered on the mark — SAME open count as the chips",
                  m is not None and int(m.group(1)) == ledger1["open"],
                  f"tab title before={title0!r} after={title1!r} ledger open={ledger1['open']} "
                  "(pre-fix: setFindingIntent re-rendered dock+manuscript but never the queue tab)")
        addressed = page.evaluate(ADDRESSED_JS)
        done = page.locator("#feedback-fixqueue .fix-row.done").count()
        checks.ok("intent-e2e: queue rows read the SAME disposition ledger (done rows == addressed)",
                  done == addressed,
                  f"done rows={done} ledger addressed={addressed}")

        metrics_calls = page.evaluate("() => window.__metricCalls")
        checks.ok("intent-e2e: the mutation pulled fresh metrics (no openProject wait)",
                  metrics_calls >= 1,
                  f"refreshMetrics calls during the mark: {metrics_calls}")

        assert_no_js_errors(checks, errors)
        browser.close()


def run(base, projects_dir, headers):
    checks = Checks()

    # ---- a real project with a real (demo-model) analysis -------------------
    sample = post(base, "/api/sample")
    name = sample.get("project")
    checks.ok("sample project created", bool(name), f"got {name!r}")
    post(base, f"/api/projects/{name}/analyze")

    queue = get(base, f"/api/projects/{name}/fixqueue")
    items = queue.get("items") or []
    checks.ok("demo analysis produced a fix queue", len(items) > 0,
              f"{len(items)} items")
    if not items:
        checks.finish()
        return
    target = items[0]

    with sync_playwright() as pw:
        browser, page, errors = launch(pw)
        page.goto(base)
        page.evaluate("async (n) => { await openProject(n); }", name)
        # the queue lives in the Evidence ledger only (P1.10) — open the dock for it
        page.evaluate("() => { openDock('evidence'); }")
        page.wait_for_selector(DOCK_QUEUE_TITLE, state="attached", timeout=15000)
        page.wait_for_selector("#finding-summary .fs-chip.open",
                               state="attached", timeout=15000)


        # ---- baseline: unmarked, the surfaces agree (control) ---------------
        before = read_surfaces(page)
        ledger0 = page.evaluate(CONTRACT_JS)
        checks.ok("baseline: queue header and chips render counts",
                  before["queue_open"] is not None and before["chip_open"] is not None,
                  before["raw"])
        checks.ok("baseline: queue header, chips and the ledger agree",
                  before["queue_open"] == before["chip_open"] == ledger0["open"]
                  and before["queue_total"] == ledger0["total"],
                  f"{before['raw']} ledger={ledger0}")

        # ---- the writer marks one finding addressed --------------------------
        post(base, f"/api/projects/{name}/findings/intent",
             {"finding_id": target["finding_id"], "intent": "addressed"})
        # re-open so state.findingMarks reloads from the intent store and every
        # surface re-renders (openProject awaits loadScriptData + renderManuscript)
        page.evaluate("async (n) => { await openProject(n); }", name)

        ledger1 = page.evaluate(CONTRACT_JS)
        checks.ok("the mark reached the client ledger (one fewer open)",
                  ledger1["open"] == ledger0["open"] - 1
                  and ledger1["total"] == ledger0["total"],
                  f"before={ledger0} after={ledger1}")

        after = read_surfaces(page)
        checks.ok("writer intent moves the summary chips",
                  after["chip_open"] == ledger1["open"],
                  f"{after['raw']} ledger={ledger1}")
        checks.ok("writer intent moves the queue header — SAME open count as the chips",
                  after["queue_open"] == after["chip_open"] == ledger1["open"],
                  f"{after['raw']} ledger={ledger1} "
                  "(pre-fix: the header read raw item.status and never saw the mark)")
        checks.ok("the dawn meter reads the SAME ledger",
                  after["dawn_pct"] == expected_dawn_pct(ledger1),
                  f"dawn says {after['dawn_pct']}% but the ledger implies "
                  f"{expected_dawn_pct(ledger1)}% ({ledger1['total'] - ledger1['open']} of "
                  f"{ledger1['total']} resolved)")
        checks.ok("the queue header's total is the ledger's total",
                  after["queue_total"] == ledger1["total"],
                  f"{after['raw']} ledger={ledger1}")

        # ---- the revision strip reads the same ledger -------------------------
        page.evaluate("async () => { await openRevisionView(); }")
        strip = page.locator("#revision-status").text_content() or ""
        checks.ok("revision strip open count agrees with the chips",
                  f"{ledger1['open']} open" in strip,
                  f"strip={strip!r} ledger open={ledger1['open']}")
        page.evaluate("() => { closeRevisionView(); }")

        assert_no_js_errors(checks, errors)
        browser.close()

    # P0.4: one re-render entry point — a writer mark must move every MOUNTED
    # surface in the same gesture (see the function docstring)
    test_intent_updates_every_mounted_surface(base, checks)

    checks.finish()


if __name__ == "__main__":
    from e2e_browser_common import start_studio
    with start_studio() as studio:
        run(studio.base_url, studio.projects_dir, {})

