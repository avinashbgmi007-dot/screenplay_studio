"""Task 18 (spec §15.4): the revision arc — ONE line under the arrival strip.

The desk already told the writer how the LAST pass compared to the one before
it, and forgot everything else the moment the next analysis landed. `pass_history
.json` keeps those numbers beyond one generation, and this suite pins what the
client is allowed to do with them: say one thing, in one line, with the trend
word derived from the same two numbers the sparkline plots. A dashboard of
per-pass rows is explicitly the failure mode the spec names ("One line, not a
dashboard"), so it is asserted as an absence.

Run:  python tests/e2e_browser_pass_arc.py
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


def post(base, path, body=None, headers=None):
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(base + path, data=json.dumps(body or {}).encode(),
                                 headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode() or "{}")


def get(base, path, headers=None):
    req = urllib.request.Request(base + path, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or "{}")


ARC_JS = """() => {
  const a = document.querySelector('.dock-pass-arc');
  if (!a) return null;
  const svg = a.querySelector('svg');
  const plotted = svg
    ? [...svg.querySelectorAll('polyline')].map((p) => (p.getAttribute('points') || '')
        .trim().split(/\\s+/).filter(Boolean).length).reduce((x, y) => x + y, 0)
    : 0;
  const box = a.getBoundingClientRect();
  return {
    text: a.textContent.replace(/\\s+/g, ' ').trim(),
    title: a.getAttribute('title') || '',
    svg: !!svg,
    plotted,
    rows: a.querySelectorAll('li, table tr, .dock-pass-row').length,
    // "one line": the element must not wrap into a block of prose
    lineHeightish: Math.round(box.height),
  };
}"""


def _trend(open_prev, open_now):
    if open_now < open_prev:
        return "converging"
    if open_now == open_prev:
        return "steady"
    return "widening"


def test_arc_after_one_analysis(base, projects_dir, headers, checks, name):
    """One point is not an arc: the line says so plainly, no arrow, no trend."""
    with sync_playwright() as pw:
        browser, page, errors = launch(pw)
        page.goto(base)
        page.evaluate("async (n) => { await openProject(n); }", name)
        page.wait_for_function("() => !!(state.report && state.report.findings)", timeout=30000)
        # the ledger is the evidence dock's board, so the line mounts with it
        page.evaluate("() => openDock('evidence')")
        page.wait_for_timeout(600)
        open_now = get(base, f"/api/projects/{name}/passes", headers)["passes"][-1]["open"]
        arc = page.evaluate(ARC_JS)
        checks.ok("pass 1: the arc line is mounted under the arrival strip",
                  arc is not None, f"arc={arc!r}")
        if arc:
            checks.ok("pass 1: the line reads Pass 1",
                      "Pass 1" in arc["text"], f"text={arc['text']!r}")
            checks.ok("pass 1: no arrow, no trend word (one point cannot move)",
                      "\u2192" not in arc["text"]
                      and not any(w in arc["text"] for w in ("converging", "steady", "widening")),
                      f"text={arc['text']!r}")
            checks.ok("pass 1: the open count is the ledger's own number",
                      f"{open_now} open" in arc["text"],
                      f"text={arc['text']!r} ledger open={open_now}")
        assert_no_js_errors(checks, errors)
        browser.close()


def test_arc_after_two_analyses(base, projects_dir, headers, checks, name):
    passes = get(base, f"/api/projects/{name}/passes", headers)["passes"]
    checks.ok("two analyses produced two points on the arc",
              len(passes) == 2, f"{len(passes)} passes")
    if len(passes) != 2:
        return
    prev, now = passes[-2]["open"], passes[-1]["open"]

    with sync_playwright() as pw:
        browser, page, errors = launch(pw)
        page.goto(base)
        page.evaluate("async (n) => { await openProject(n); }", name)
        page.wait_for_function("() => !!(state.report && state.report.findings)", timeout=30000)
        # the ledger is the evidence dock's board, so the line mounts with it
        page.evaluate("() => openDock('evidence')")
        page.wait_for_timeout(600)
        arc = page.evaluate(ARC_JS)
        checks.ok("pass 2: the line exists", arc is not None, f"arc={arc!r}")
        if arc:
            checks.ok("pass 2: the line reads Pass 2", "Pass 2" in arc["text"],
                      f"text={arc['text']!r}")
            checks.ok("pass 2: X -> Y open, straight from the store",
                      f"{prev} \u2192 {now} open" in arc["text"],
                      f"text={arc['text']!r} store=({prev}, {now})")
            checks.ok("pass 2: the trend word agrees with the two numbers it prints",
                      _trend(prev, now) in arc["text"],
                      f"text={arc['text']!r} expected={_trend(prev, now)!r}")
            checks.ok("the sparkline is inline SVG, plotted from the same entries",
                      arc["svg"] and arc["plotted"] == len(passes),
                      f"svg={arc['svg']} plotted={arc['plotted']}")
            checks.ok("hover explains where the numbers come from (spec §3)",
                      "analysis" in arc["title"].lower(),
                      f"title={arc['title']!r}")
            checks.ok("one line, not a dashboard: no per-pass rows",
                      arc["rows"] == 0, f"rows={arc['rows']}")
            checks.ok("one line, not a paragraph",
                      arc["lineHeightish"] <= 60, f"height={arc['lineHeightish']}")
        assert_no_js_errors(checks, errors)
        browser.close()


def run(base, projects_dir, headers):
    checks = Checks()
    sample = post(base, "/api/sample", headers=headers)
    name = sample.get("project")
    checks.ok("sample project created", bool(name), f"got {name!r}")
    if not name:
        checks.finish()
        return

    post(base, f"/api/projects/{name}/analyze", headers=headers)
    test_arc_after_one_analysis(base, projects_dir, headers, checks, name)
    post(base, f"/api/projects/{name}/analyze", {"force": True}, headers)
    test_arc_after_two_analyses(base, projects_dir, headers, checks, name)

    checks.finish()


if __name__ == "__main__":
    import tempfile
    with start_studio(projects_dir=tempfile.mkdtemp(prefix="pass_arc_")) as studio:
        run(studio.base_url, studio.projects_dir, {})
