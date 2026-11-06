"""Gap 93 — the report must never show a percentage without the excluded mass.

Filed defect, measured on the demo over a real screenplay: 16 findings, 3 quotable
and all 3 verified, 0 with an observation. The report's own summary read
**"100.0% (3 of 3)"** while thirteen other rows carried nothing a machine could
check — and the words `observation` did not appear in the report at all.

Reproduced here with the filing's exact shape: `verified=3, no_quote=13`. Before
the fix, `render_markdown` produced the 100% line and no coverage sentence;
`observation_bearing` / `observation_pct` existed only in `to_findings_json`.

The two rules this file holds:

1. A rate is always stated as a fraction of what it actually measured, with the
   excluded count in the same breath. "3 of 3" beside 13 unchecked rows is a
   number the writer will quote back with the wrong meaning.
2. Observation coverage is a first-class sentence in the report, not a JSON-only
   field. A quote makes a finding citable; an observation makes it falsifiable.
   A report where no finding carries one is a report whose claims cannot be
   checked, and that belongs on the page.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from screenplay_analyzer.pipeline import AnalysisResult          # noqa: E402
from screenplay_analyzer.report import (                        # noqa: E402
    render_markdown,
    to_findings_json,
)
from screenplay_parser import parse_screenplay                  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "pain_tenglish.fountain")


def _result(verified=0, not_found=0, no_quote=0, scene_not_found=0,
            observations=0, quoted_findings=None):
    """The filing's scenario, built to shape rather than to numbers I invented."""
    doc = parse_screenplay(FIXTURE)
    findings = []
    for i in range(quoted_findings if quoted_findings is not None else verified + not_found):
        findings.append({"category": "dialogue", "severity": "medium",
                         "title": f"quoted {i}", "quote": "Rey!",
                         "observation": "a checkable statement" if i < observations else "",
                         "verification": {"status": "verified" if i < verified else "not_found"}})
    for i in range(no_quote):
        findings.append({"category": "theme", "severity": "low", "title": f"themed {i}",
                         "observation": "a checkable statement" if len(findings) < observations else "",
                         "verification": {"status": "no_quote"}})
    for i in range(scene_not_found):
        findings.append({"category": "continuity", "severity": "high",
                         "title": f"ghost scene {i}",
                         "verification": {"status": "scene_not_found"}})
    res = AnalysisResult(doc=doc, findings=findings)
    res.verification = {"verified": verified, "not_found": not_found,
                        "no_quote": no_quote, "scene_not_found": scene_not_found}
    return res


def _section(md: str) -> str:
    return md[md.index("## Evidence Verification"):]


# ---------- the filed case, exactly ----------

def test_a_high_rate_never_stands_without_the_excluded_mass():
    """`verified=3, no_quote=13` — the run the gap was filed about."""
    section = _section(render_markdown(_result(verified=3, no_quote=13)))

    assert "100.0%" in section, "the rate itself is not wrong — only its context was"
    assert "3 of 3" in section
    # the excluded thirteen must be in the SAME sentence as the rate
    rate_line = [l for l in section.splitlines() if "Quote-verified rate" in l][0]
    assert "13" in rate_line, f"the rate line hides the excluded count: {rate_line}"
    assert "excluded" in rate_line


def test_coverage_is_stated_before_the_rate():
    """Order matters: a reader who stops after the first line should have the
    covering number, not the flattering one."""
    section = _section(render_markdown(_result(verified=3, no_quote=13)))
    cov = section.index("Evidence coverage")
    rate = section.index("Quote-verified rate")
    assert cov < rate, "coverage must be stated before the rate"


def test_observation_coverage_is_in_the_report_at_all():
    """Before the fix the word did not appear in the markdown once."""
    md = render_markdown(_result(verified=3, no_quote=13, observations=0))
    assert "checkable observation" in md.lower()


def test_zero_observations_is_an_explicit_warning_not_a_silence():
    section = _section(render_markdown(_result(verified=3, no_quote=13)))
    assert "No finding in this report carries a checkable observation" in section
    assert "falsifying" in section, "say WHY it matters, not just that the count is 0"


def test_a_report_with_observations_does_not_warn():
    md = render_markdown(_result(verified=3, no_quote=13, observations=5))
    assert "No finding in this report carries a checkable observation" not in md
    assert "5 of 16" in md


# ---------- the denominator rules that already existed must survive ----------

def test_no_percentage_when_nothing_was_checkable():
    """A percentage over nothing is a lie — the rule `verification_rate` owns."""
    section = _section(render_markdown(_result(no_quote=16)))
    assert "Quote-verified rate" not in section or "No quote-verified rate" in section
    assert "not a clean bill of health" in section


def test_a_clean_run_still_reads_clean():
    """Do not over-correct: 3 quoted, 3 verified, everything observed is good news
    and must not be dressed as a warning."""
    md = render_markdown(_result(verified=3, observations=3))
    section = _section(md)
    assert "100.0%" in section
    assert "No finding in this report carries" not in section


def test_scene_not_found_is_reported_separately():
    section = _section(render_markdown(_result(verified=1, scene_not_found=2)))
    assert "cite scenes that do not exist" in section


# ---------- the JSON and the markdown must agree ----------

def test_the_json_carries_the_same_coverage_numbers():
    js = to_findings_json(_result(verified=3, no_quote=13))
    vs = js["verification_summary"]
    assert vs["quote_bearing"] == 3
    assert vs["observation_bearing"] == 0
    assert vs["observation_pct"] == 0.0
    # and the markdown must print those same two numbers
    section = _section(render_markdown(_result(verified=3, no_quote=13)))
    assert f"{vs['quote_bearing']} of {vs['verified'] + vs['no_quote']}" in section


def test_observation_pct_is_none_rather_than_zero_over_nothing():
    js = to_findings_json(_result())
    assert js["verification_summary"]["observation_pct"] is None


# ---------- the desk's readout (core.js) carries it too ----------

def _js() -> str:
    with open(os.path.join(ROOT, "screenplay_studio", "webapp", "core.js"),
              encoding="utf-8") as f:
        return f.read()


def test_the_desk_readout_prints_observation_coverage():
    js = _js()
    body = js[js.index("function verificationReadoutText"):]
    body = body[:body.index("\n}")]
    assert "observation_bearing" in body
    assert "checkable observation" in body


def test_the_desk_readout_does_not_invent_a_zero_for_old_reports():
    """Reports analysed before the field existed must not be accused of carrying
    zero observations — they were never measured for it."""
    js = _js()
    body = js[js.index("function verificationReadoutText"):]
    body = body[:body.index("\n}")]
    assert "typeof vs.observation_bearing" in body, (
        "presence must be checked, not defaulted to 0")
