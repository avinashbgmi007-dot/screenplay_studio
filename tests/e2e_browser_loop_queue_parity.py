"""The keyboard fix loop walks the queue the writer sees (spec 14.54).

`loopList()` consumes the SAME ordered projection the fix queue's lanes
render (core.queueProjection). Before the repair it walked state.findings in
report order through findingPassesFilter and admitted rows the queue never
renders — observation rows (not tasks; dropped by the lane grouping) and
ungrounded rows behind the kit-A toggle — so N could differ and steps landed
out of the rendered order (measured: queue [1,0,5] vs loop [0,1,2,3,4,5];
within a lane [1,0] vs [0,1]).

Path under test (no client seeding — flags are planted in the report on
disk, so every hop is exercised):

    report.findings.json (one TASK row gains ungrounded: True)
      -> GET /fixqueue
      -> the Evidence lens fix queue (the planted row hidden by default, its
         grounded sibling still listed)
      -> loopList() / startLoop() / stepLoop(): N == rendered rows, the walk
         order equals the rendered order, and the hidden row is never stepped
      -> the "Show ungrounded (1)" toggle: the row returns in its ranked
         place and the loop admits exactly it

The planted row must be a TASK (a lane member the queue actually renders):
the demo analysis emits observation rows too, and hiding an observation
would prove nothing — so the fixture discovers the rendered rows once, then
plants into one of them and reloads.

Run:  python tests/e2e_browser_loop_queue_parity.py
"""
import json
import os
import sys
import tempfile

import requests
from playwright.sync_api import sync_playwright

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from e2e_browser_common import (Checks, assert_no_js_errors, became_true,  # noqa: E402
                                clicked, launch, start_studio, studio_headers)

MARKER = "LOOP-PARITY-PROBE-L7"

DOCK_QUEUE = '.dock-lens[data-lens="evidence"] .dock-section-fixqueue'
QUEUE_TITLE = DOCK_QUEUE + " .craft-panel-title"
ROW = " .finding-note.queue-row"      # the queue's rendered row = the card the loop expands

# One read: the rendered queue order (finding ids, in DOM order) and the
# loop's own walk order, from the SHIPPED loopList — plus the planted row's
# identity and the section's text.
SNAPSHOT_JS = """() => {
  const idOf = (i) => (state.findingIds && state.findingIds[i]) || String(i);
  const rows = Array.from(document.querySelectorAll(
    '.dock-lens[data-lens="evidence"] .dock-section-fixqueue'
    + ' .finding-note.queue-row'));
  const rowIds = rows.map((r) => idOf(+r.dataset.findingIndex));
  const list = loopList().map((e) => e.id);
  const planted = (state.findings || []).map((f, i) => ({
      id: idOf(i), issue: f.issue || "" }))
    .filter((x) => x.issue.includes("%MARKER%"))[0] || null;
  const sec = document.querySelector(
    '.dock-lens[data-lens="evidence"] .dock-section-fixqueue');
  return { rowIds, list, plantedId: planted && planted.id,
           sectionText: sec ? (sec.textContent || '').slice(0, 300) : "" };
}""".replace("%MARKER%", MARKER)

# The loop's own walk: start, sample every position through one full cycle,
# exit. Each sample names the finding the loop cursor sits on (from the
# shipped loopList/loopState) and the card that got `.loop-current`.
STEPS_JS = """() => {
  startLoop();
  const N = loopList().length;
  const seq = [];
  for (let k = 0; k < N; k++) {
    if (k) stepLoop(1);
    const cur = loopList()[loopState.pos];
    const card = document.querySelector(
      '.dock-lens[data-lens="evidence"] .finding-note.loop-current');
    const bar = document.querySelector('#loop-bar .loop-pos');
    seq.push({
      expectId: cur ? cur.id : null,
      cardId: card ? ((state.findingIds[+card.dataset.findingIndex])
                      || String(+card.dataset.findingIndex)) : null,
      posText: bar ? bar.textContent : null,
    });
  }
  exitLoop();
  return { N, seq, barGone: !document.getElementById('loop-bar') };
}"""


def report_path(projects_dir):
    for d in sorted(os.listdir(projects_dir)):
        p = os.path.join(projects_dir, d, "report.findings.json")
        if os.path.isfile(p):
            return p
    raise AssertionError(f"no report.findings.json under {projects_dir}")


def load_report(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_report(path, report):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f)


def open_desk(page, base, name):
    page.goto(base)
    page.evaluate("async (n) => { await openProject(n); }", name)
    page.evaluate("() => { openDock('evidence'); setEvidenceTier(1); }")
    page.wait_for_selector(QUEUE_TITLE, state="attached", timeout=15000)
    page.wait_for_timeout(500)  # settle the tier gesture


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

    path = report_path(projects_dir)
    report = load_report(path)
    findings = report.get("findings") or []
    checks.ok("report carries findings to plant into", len(findings) >= 2,
              f"{len(findings)} findings")
    if len(findings) < 2:
        checks.finish()
        return

    # --- phase A: discover which findings the queue actually RENDERS ---
    # The demo pipeline flags its rows ungrounded (they carry no quote or
    # observation), which would leave the queue all-hidden and prove nothing;
    # clear every flag so the queue renders its full set, then read the task
    # rows in rendered order.
    for f in findings:
        f["ungrounded"] = False
    save_report(path, report)

    with sync_playwright() as pw:
        browser, page, errors = launch(pw)
        # (identity anchoring is the runner's job — anchored_run.py asserts the
        # served code rev before a suite starts; an env-optional check here
        # would be an if-guard with no else, which tests/test_browser_check_
        # hygiene.py's ratchet counts and refuses. Keep this suite guard-free.)
        open_desk(page, base, name)
        task_ids = page.evaluate(
            """() => Array.from(document.querySelectorAll(
                 '.dock-lens[data-lens="evidence"] .dock-section-fixqueue'
                 + ' .finding-note.queue-row'))
                 .map((r) => +r.dataset.findingIndex)""")
        checks.ok("the demo report yields enough task rows for a walk",
                  len(task_ids) >= 2, f"task rows={task_ids}")
        if len(task_ids) < 2:
            browser.close()
            checks.finish()
            return
        task_idx = [int(i) for i in task_ids]
        browser.close()

    # --- phase B: plant on the FIRST task row, clear everything else ---
    findings[task_idx[0]]["ungrounded"] = True
    findings[task_idx[0]]["issue"] = ((findings[task_idx[0]].get("issue")
                                       or "planted row") + f" {MARKER}")
    for k, f in enumerate(findings):
        if k != task_idx[0]:
            f["ungrounded"] = False
    save_report(path, report)

    served = requests.get(f"{base}/api/projects/{name}/fixqueue",
                          headers=headers, timeout=60).json()
    nungr = sum(1 for i in served.get("items", []) if i.get("ungrounded"))
    checks.ok("exactly the planted row is ungrounded on the wire", nungr == 1,
              f"ungrounded rows={nungr} items={len(served.get('items', []))}")

    with sync_playwright() as pw:
        browser, page, errors = launch(pw)
        open_desk(page, base, name)

        # --- default view: rendered order == loop order, planted row absent ---
        snap = page.evaluate(SNAPSHOT_JS)
        rows, walk = snap["rowIds"], snap["list"]
        checks.ok("default: the planted row is hidden from the queue",
                  snap["plantedId"] is not None
                  and MARKER not in snap["sectionText"],
                  snap["sectionText"][:200])
        checks.ok("default: the grounded sibling still renders",
                  len(rows) == len(task_ids) - 1,
                  f"rows={len(rows)} tasks={len(task_ids)}")
        checks.ok("default: the loop's N equals the rendered row count",
                  len(walk) == len(rows) and len(walk) > 0,
                  f"loop N={len(walk)} rendered rows={len(rows)}")
        checks.ok("default: the loop walks the rendered order, exactly",
                  walk == rows, f"loop={walk} rows={rows}")
        checks.ok("default: the hidden ungrounded row is not walked",
                  snap["plantedId"] not in walk,
                  f"planted={snap['plantedId']} walk={walk}")
        checks.ok("default: the toggle offers the hidden row by count",
                  "(1)" in snap["sectionText"].split("Show ungrounded")[-1][:8],
                  snap["sectionText"][:200])

        # --- stepping: every step lands on the next row the queue shows ---
        steps = page.evaluate(STEPS_JS)
        n_steps = steps["N"]
        seq = steps["seq"]
        landed = [s["cardId"] for s in seq]
        checks.ok("the walk has the same N inside the loop",
                  n_steps == len(walk), f"N={n_steps} walk={len(walk)}")
        checks.ok("the loop bar counts 1..N of N across the walk",
                  all(s["posText"] == f"{k + 1} of {n_steps}"
                      for k, s in enumerate(seq)),
                  f"positions={[s['posText'] for s in seq]}")
        checks.ok("every step lands its card on the next rendered row",
                  landed == rows and None not in landed,
                  f"landed={landed} rows={rows} N={n_steps}")
        checks.ok("exitLoop clears the bar", steps["barGone"],
                  str(steps)[:160])

        # --- the toggle: the planted row returns, ranked, and is now walked ---
        toggle = page.locator(DOCK_QUEUE + " .fq-toggle-ungrounded")
        checks.ok("the ungrounded toggle is offered", toggle.count() > 0,
                  snap["sectionText"][:160])
        if toggle.count():
            checks.ok("the toggle is clickable", clicked(toggle.first),
                      "the toggle button never became clickable")
            back = became_true(
                page,
                f"() => (document.querySelector('{DOCK_QUEUE}') || {{}})"
                f".textContent.includes('{MARKER}')",
                timeout=15000)
            checks.ok("toggle: the planted row returns to the queue", back,
                      snap["sectionText"][:160])
            snap2 = page.evaluate(SNAPSHOT_JS)
            rows2, walk2 = snap2["rowIds"], snap2["list"]
            checks.ok("toggle: the loop admits exactly the shown rows",
                      len(walk2) == len(rows2) == len(task_ids),
                      f"loop N={len(walk2)} rows={len(rows2)} "
                      f"tasks={len(task_ids)}")
            checks.ok("toggle: rendered order still equals the walk order",
                      walk2 == rows2, f"loop={walk2} rows={rows2}")
            checks.ok("toggle: the planted row is walked, in its ranked place",
                      snap2["plantedId"] in walk2
                      and walk2.index(snap2["plantedId"])
                      == rows2.index(snap2["plantedId"]),
                      f"planted={snap2['plantedId']} walk={walk2}")

        assert_no_js_errors(checks, errors)
        browser.close()

    checks.finish()


if __name__ == "__main__":
    if os.environ.get("E2E_BASE"):
        print("E2E_BASE is set: this suite must boot its own studio to write "
              "the report to disk. Unset E2E_BASE and re-run.")
        sys.exit(2)
    with tempfile.TemporaryDirectory(prefix="loop_parity_e2e_") as tmp:
        projects = os.path.join(tmp, "projects")
        os.makedirs(projects, exist_ok=True)
        with start_studio(projects_dir=projects) as studio:
            run(studio.base_url, studio.projects_dir)
