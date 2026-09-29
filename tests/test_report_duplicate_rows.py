"""Rung 20a — a report must not carry the same note twice, and must not claim a
total the rows cannot back up.

Measured on the real shelf: the stored reports hold 94 findings, and two of those
rows are word-for-word indistinguishable from a row already in the same report
(`P11_Gate`, `Pain_3`). A second real collision class — one quoted line flagged
under two different craft rules (`Rain_Courier_7`, `gun_pen_2`) — is two notes
about one line, and must stay two rows.

WHERE the collapse runs is the point of this file. `pipeline.py`'s step 8b states
the law: cross-rule dedup "runs before the verification summary and the evidence
depth so every downstream count describes the set the writer actually receives".
Dropping a row after those are frozen makes `stats.evidence_depth.total` and
`verification` publish a total that the rendered rows contradict — in `report.md`,
in the served findings JSON and in the live desk. So the collapse belongs in 8b,
beside the dedup, not at the report write path.

It keys on the WHOLE row, so it can only ever drop a row that carries nothing the
survivor lacks: a difference in severity, rule id, reasoning, suggestion or scene
order survives, because that difference is information the writer would lose.
"""
from __future__ import annotations

import json
import os

from screenplay_analyzer import pipeline
from screenplay_analyzer.dedupe import collapse_exact_duplicates
from screenplay_analyzer.pipeline import AnalysisResult
from screenplay_analyzer.report import save_report
from screenplay_parser.models import ScriptDocument
from screenplay_studio.revision import compute_finding_id

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "pain_tenglish.fountain")


def _note(issue="Scene 6 slug repeats the previous scene heading.",
          quote="INT. KID SIDDHU'S HOUSE - NIGHT", category="continuity",
          scenes=(6,), **over):
    f = {"category": category, "evidence_quote": quote, "issue": issue,
         "scene_refs": list(scenes), "severity": "medium", "rule_id": None,
         "why_it_matters": "", "suggestion": None}
    f.update(over)
    return f


# --------------------------------------------------------------------------
# what may be dropped
# --------------------------------------------------------------------------

def test_identical_rows_collapse_to_one():
    rows = collapse_exact_duplicates([_note(), _note()])
    assert len(rows) == 1


def test_same_quote_different_note_keeps_both_rows():
    """The real collision on the shelf: one quote, two different craft rules.

    These are two pieces of work, so two rows and two marks. Nothing here may
    merge them.
    """
    rows = collapse_exact_duplicates([
        _note(issue="Dialogue is redundant and explains the action shown.",
              quote="RAHUL Light banchey!", category="dialogue"),
        _note(issue="Character voice is indistinguishable and lacks markers.",
              quote="RAHUL Light banchey!", category="dialogue"),
    ])
    assert len(rows) == 2


def test_a_note_in_two_scenes_is_still_one_note():
    """scene_refs is a set on one row, not one row per scene."""
    assert len(collapse_exact_duplicates([_note(scenes=(1, 2)),
                                         _note(scenes=(1, 2))])) == 1


def test_the_same_issue_in_another_scene_is_another_note():
    rows = collapse_exact_duplicates([_note(quote=None, category="dialogue",
                                            scenes=(1,)),
                                      _note(quote=None, category="dialogue",
                                            scenes=(4,))])
    assert len(rows) == 2


def test_a_row_that_differs_only_in_severity_is_not_a_duplicate():
    """First-seen would win and the higher claim would be lost, so it stays."""
    rows = collapse_exact_duplicates([_note(severity="low"), _note(severity="high")])
    assert len(rows) == 2


def test_a_row_that_differs_only_in_its_reasoning_is_not_a_duplicate():
    rows = collapse_exact_duplicates([_note(why_it_matters=""),
                                      _note(why_it_matters="Chekhov's gun.")])
    assert len(rows) == 2


def test_a_row_that_differs_only_in_its_rule_is_not_a_duplicate():
    """`craft_principles` reads rule_id; dropping it silently ungrounds a finding."""
    rows = collapse_exact_duplicates([_note(rule_id=None),
                                      _note(rule_id="see-and-say-rule")])
    assert len(rows) == 2


def test_scene_order_is_part_of_the_note():
    """The first scene ref is what the report and the act/heading lookup show, so
    [1,2] and [2,1] point the writer at different scenes."""
    rows = collapse_exact_duplicates([_note(scenes=(1, 2)), _note(scenes=(2, 1))])
    assert len(rows) == 2


def test_collapsing_never_changes_the_ids_the_strip_counts():
    """The no-compromise guard.

    Fixed/new arithmetic counts DISTINCT content ids. If a collapse ever removed
    a distinct note, the arrival strip would report a finding as fixed that no
    writer ever addressed.
    """
    findings = [_note(), _note(), _note(severity="high"),
                _note(quote=None, scenes=(1,)), _note(quote=None, scenes=(1,))]
    before = {compute_finding_id(f) for f in findings}
    rows = collapse_exact_duplicates(findings)
    assert {compute_finding_id(f) for f in rows} == before
    assert len(rows) < len(findings)


def test_row_order_survives_the_collapse():
    rows = collapse_exact_duplicates([_note(issue="SECOND"), _note(issue="FIRST"),
                                      _note(issue="SECOND")])
    assert [r["issue"] for r in rows] == ["SECOND", "FIRST"]


def test_the_input_list_is_never_mutated():
    findings = [_note(), _note()]
    collapse_exact_duplicates(findings)
    assert len(findings) == 2


# --------------------------------------------------------------------------
# where it runs: the counts the pipeline publishes must match the rows
# --------------------------------------------------------------------------

class _Client:
    """Answers every call, so the seeded rows arrive the way a chunked pass sends
    them — once per chunk, which is exactly how the duplicate is born."""

    def __init__(self, findings):
        self._findings = findings

    def resolve_model(self):
        return "t"

    def chat_json(self, system, user, grammar=None, max_tokens=None, **kw):
        if "summarize" in system.lower():
            return {"summaries": [{"scene_number": n, "summary": "s"} for n in range(1, 8)]}
        return {"findings": [dict(f) for f in self._findings]}


def _analyze(findings):
    from screenplay_parser import parse_fountain
    return pipeline.analyze(parse_fountain(FIXTURE), _Client(findings),
                            run_categories=("dialogue",), progress_cb=None)


def test_the_published_counts_describe_the_rows_that_survive():
    seeded = _note(issue="Dialogue repeats an action the page already showed.",
                   quote="RAHUL Light banchey!", category="dialogue", scenes=(4,))
    result = _analyze([seeded, dict(seeded)])

    kept = [f for f in result.findings if f.get("issue") == seeded["issue"]]
    assert len(kept) == 1, f"the same note was carded {len(kept)} times"

    depth = (result.stats or {}).get("evidence_depth") or {}
    assert depth.get("total") == len(result.findings), (
        f"evidence_depth totals {depth.get('total')} rows, report carries "
        f"{len(result.findings)}")
    assert sum(result.verification.values()) == len(result.findings), (
        f"verification_summary totals {sum(result.verification.values())}, "
        f"report carries {len(result.findings)}")


def test_both_writers_agree_with_the_counts_they_print():
    seeded = _note(issue="Dialogue repeats an action the page already showed.",
                   quote="RAHUL Light banchey!", category="dialogue", scenes=(4,))
    result = _analyze([seeded, dict(seeded)])

    md, js = "report.md", "report.findings.json"
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        mdp, jsp = os.path.join(d, md), os.path.join(d, js)
        save_report(result, mdp, jsp)
        payload = json.load(open(jsp, encoding="utf-8"))
        rows, text = payload["findings"], open(mdp, encoding="utf-8").read()
        depth = payload["stats"]["evidence_depth"]

    assert len(rows) == len(result.findings)
    assert text.count(seeded["issue"]) == 1, "report.md still renders the dropped row"
    assert depth["total"] == len(rows)
