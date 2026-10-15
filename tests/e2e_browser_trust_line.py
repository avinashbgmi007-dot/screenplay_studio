"""The dock's trust line, from the SERVED report — the whole chain, unpinned
until now.

The pieces each had a test, but never the chain: the server-side
`verification_summary` stamp was unit-pinned (test_verification_summary_surface),
the readout STRING was pinned against a hand-seeded block
(e2e_browser_dock_sections seeds `verification_summary` straight into
state.report — a state no server response ever produced before the bundle), and
the demo model could not prove the real path (its findings carry no quotes, so
the honest line is the no-quote count — worth pinning in its own right, but not
the percentage shape).

This suite seeds a PRE-BUNDLE report on disk (findings with quotes, NO
verification_summary key at all) and drives the real product loop — open the
project, the SPA GETs /report, `_sanitize_report` stamps the block at serve
time, `verificationReadout()` renders it in BOTH orientation strips — so the
pin covers exactly what a writer with an old project sees after the upgrade.

Run:  python tests/e2e_browser_trust_line.py
"""
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e2e_browser_common import (Checks, assert_no_js_errors, launch,  # noqa: E402
                                start_studio)
from e2e_browser_one_matcher import SCRIPT  # the standard two-scene fixture
from playwright.sync_api import sync_playwright  # noqa: E402

FIXTURE = "trust_line_fixture"


def make_fixture(projects_dir, name=FIXTURE):
    """A parsed + analysed project whose stored report is PRE-BUNDLE: quotes
    that verify (2 of them), one that will not (1), one quote-less finding —
    and NO verification_summary key, exactly what the trust bundle shipped."""
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
        "findings": [
            {"issue": "The gun is introduced without payoff.",
             "evidence_quote": "MARA takes out an old REVOLVER, setting it on the desk.",
             "scene_refs": [1], "severity": "high", "category": "plot_economy",
             "status": "open", "recommendation": "Pay it off.",
             "verification": {"status": "verified", "matched_scene": 1,
                              "confidence": 1.0}},
            {"issue": "The gun's history is told flat.",
             "evidence_quote": "It was my father's gun.",
             "scene_refs": [1], "severity": "medium", "category": "dialogue",
             "status": "open", "recommendation": "Let it land later.",
             "verification": {"status": "verified", "matched_scene": 1,
                              "confidence": 1.0}},
            {"issue": "The rooftop line promises nothing.",
             "evidence_quote": "I kept it for twenty years.",
             "scene_refs": [2], "severity": "low", "category": "dialogue",
             "status": "open", "recommendation": "Tie it to the gun.",
             "verification": {"status": "not_found", "matched_scene": None,
                              "confidence": 0.41}},
            {"issue": "Scene 2 has no turn.",
             "evidence_quote": None,
             "scene_refs": [2], "severity": "medium", "category": "structure",
             "status": "open", "recommendation": "Give it one.",
             "verification": {"status": "no_quote", "matched_scene": None,
                              "confidence": None}},
        ],
        # Deliberately NO "verification_summary": the serve-time stamp is the
        # thing under test.
        "stats": {"total_findings": 4},
    }
    with open(m.report_findings_path, "w", encoding="utf-8", newline="") as f:
        json.dump(report, f)
    m.mark_complete("analyze")
    return name


def make_noreport_fixture(projects_dir, name="trust_line_noreport_fixture"):
    """A parsed project with NO analysis at all — the switch target for the
    leak check: a previous project's trust numbers must not survive here."""
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
    return name


TRUST_JS = """() => {
  const strips = [...document.querySelectorAll(
    '.dock-lens[data-lens="evidence"] .dock-trust')];
  return {
    count: strips.length,
    texts: strips.map((e) => e.textContent.trim()),
  };
}"""


def run(base, projects_dir):
    checks = Checks()
    make_fixture(projects_dir, FIXTURE)
    with sync_playwright() as pw:
        browser, page, errors = launch(pw)
        page.goto(base)
        page.evaluate("async (n) => { await openProject(n); }", FIXTURE)
        page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)

        # The dock is closed on first open; the trust line lives in the
        # evidence lens, inside sections that animate open after render — so
        # wait for ATTACHED (a hidden-but-resolved span is the collapsed-
        # section race, not a missing render), then poll for the words.
        page.locator("#right-edge-affordance").click()
        page.wait_for_selector("#context-dock.open", timeout=5000)
        page.wait_for_selector(
            '.dock-lens[data-lens="evidence"] .dock-trust',
            state="attached", timeout=10000)
        import time as _time
        deadline = _time.time() + 10
        trust = {"count": 0, "texts": []}
        while _time.time() < deadline:
            trust = page.evaluate(TRUST_JS)
            if any("quotes verified" in t or "no quote" in t
                   for t in trust["texts"]):
                break
            page.wait_for_timeout(250)

        # One strip on a FIRST pass (the arrival strip needs pass history to
        # compare; the mass strip always renders). The words come from the
        # SERVE-time block: 2 verified + 1 not_found = 3 quote-bearing, 67%
        # (one-decimal rule, server-side), the quote-less finding as a count.
        want = "2 of 3 quotes verified (67%) \u00B7 1 carried no quote"
        checks.ok("the trust line renders from a PRE-BUNDLE served report",
                  trust["count"] >= 1, f"count={trust['count']}")
        checks.ok("the mass strip prints the serve-derived sentence",
                  want in trust["texts"],
                  f"got={trust['texts']} want={want!r}")

        # The served JSON is where the line came from — pin the half-chain too,
        # so a future failure names the right half.
        import urllib.request
        with urllib.request.urlopen(f"{base}/api/projects/{FIXTURE}/report",
                                    timeout=30) as resp:
            vs = json.load(resp).get("verification_summary") or {}
        checks.ok("the served report carries the recomputed block",
                  vs.get("verified") == 2 and vs.get("not_found") == 1
                  and vs.get("quote_bearing") == 3
                  and vs.get("verified_pct_of_quoted") == 66.7,
                  str(vs))

        # A project switch must not leak the previous script's trust numbers
        # into a project that has no report: openProject resets state.report
        # BEFORE the new load, so the strips cannot print the old script's
        # percentage over the new script's manuscript.
        make_noreport_fixture(projects_dir)
        page.evaluate("async (n) => { await openProject(n); }",
                      "trust_line_noreport_fixture")
        page.wait_for_selector("#manuscript-container .scene-page", timeout=20000)
        page.wait_for_timeout(500)
        leaks = page.evaluate(
            """() => ({
                 reportVs: !!(state.report && state.report.verification_summary),
                 trustTexts: [...document.querySelectorAll('.dock-trust')]
                   .map((e) => e.textContent.trim()),
               })""")
        checks.ok("switching to a report-less project clears the old trust line",
                  not leaks["reportVs"]
                  and not any("67%" in t for t in leaks["trustTexts"]),
                  str(leaks))

        assert_no_js_errors(checks, errors)
        browser.close()

    checks.finish()


if __name__ == "__main__":
    import tempfile

    with start_studio(projects_dir=tempfile.mkdtemp(prefix="trust_line_")) as studio:
        run(studio.base_url, studio.projects_dir)
