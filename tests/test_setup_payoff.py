"""Synthetic regression tests for setup/payoff evidence boundaries."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_parser import parse_fountain
from screenplay_analyzer.setup_payoff import (
    adjudicate_ledger,
    dangling_findings,
    run_setup_payoff_ledger,
    _time_pressure_seeds,
)
from screenplay_analyzer.grammar import setup_payoff_ledger_grammar

SAMPLE = """Title: Ledger Test
Author: T

INT. ROOM - NIGHT

MARA holds a small CIGAR, turning it over.

MARA
I'll tell you everything when this is over.

CUT TO:

INT. HALL - DAY

The CIGAR sits on the table, untouched.

MARA
(scared)
The debt is coming.
"""


def _parse(text=SAMPLE):
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False,
                                     encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        return parse_fountain(path)
    finally:
        os.unlink(path)


class FakeClient:
    def __init__(self, ledger=None, error=None):
        self.ledger = ledger if ledger is not None else {"ledger": []}
        self.error = error

    def chat_json(self, system, user, grammar=None, max_tokens=0, temperature=0.0):
        if self.error:
            raise self.error
        return self.ledger


def test_ledger_cleaning_and_model_failure():
    from screenplay_parser.knowledge_graph import build_knowledge_graph
    kg = build_knowledge_graph(_parse())
    client = FakeClient({"ledger": [
        {"setup": "The cigar", "kind": "object", "setup_scenes": [1],
         "payoff_scenes": None, "status": "dangling", "note": "Not used."},
        {"setup": "The debt", "kind": "theme", "setup_scenes": [2],
         "payoff_scenes": [2], "status": "paid", "note": "Lands."},
        {"setup": "", "kind": "other", "setup_scenes": [],
         "payoff_scenes": None, "status": "paid", "note": ""},
    ]})
    entries, errors = run_setup_payoff_ledger("overview", kg, client, "", 2)
    assert errors == []
    assert [e["setup"] for e in entries] == ["The cigar", "The debt"]
    assert setup_payoff_ledger_grammar()
    failed, errors = run_setup_payoff_ledger(
        "overview", kg, FakeClient(error=RuntimeError("synthetic failure")), "", 2)
    assert failed == [] and len(errors) == 1


def test_later_recurrence_is_only_a_candidate():
    row = {"setup": "The cigar", "kind": "object", "setup_scenes": [1],
           "payoff_scenes": None, "status": "dangling", "note": "Not used."}
    result = adjudicate_ledger([row], _parse())[0]
    assert result["status"] == "unverified"
    assert result["verified"] is False
    assert result["model_status"] == "dangling"
    assert result["model_note"] == "Not used."
    assert result["candidate_recurrence_scenes"] == [2]
    assert result["payoff_scenes"] is None
    assert "not confirmation" in result["verify_note"]


def test_absence_does_not_prove_abandonment():
    result = adjudicate_ledger([{
        "setup": "The moonstone amulet", "kind": "object",
        "setup_scenes": [1], "payoff_scenes": None,
        "status": "abandoned", "note": "Never appears again."}], _parse())[0]
    assert result["status"] == "unverified"
    assert result["verified"] is False
    assert result["model_status"] == "abandoned"
    assert result["candidate_recurrence_scenes"] == []
    assert "cannot establish" in result["verify_note"]


def test_misgrounded_setup_and_backward_payoff_are_flagged():
    doc = _parse("""Title: T
Author: T

INT. ROOM - NIGHT

The X mark is burned here.

CUT TO:

INT. HALL - DAY

He looks at the X mark and sighs.
""")
    result = adjudicate_ledger([{
        "setup": "The moonstone amulet", "kind": "object",
        "setup_scenes": [1], "payoff_scenes": [2], "status": "paid",
        "note": "Lands."}], doc)[0]
    assert result["setup_ungrounded"] is True
    assert result["status"] == "unverified"
    row = adjudicate_ledger([{
        "setup": "The X mark", "kind": "object", "setup_scenes": [2],
        "payoff_scenes": [1], "status": "paid", "note": "Lands."}], doc)[0]
    assert row["status"] == "unverified"
    assert row["payoff_citation_before_setup"] is True
    assert row["payoff_scenes"] is None


def test_adjudication_is_idempotent_and_preserves_model_claims():
    row = {"setup": "The cigar", "kind": "object", "setup_scenes": [1],
           "payoff_scenes": [2], "status": "paid", "note": "It matters."}
    first = adjudicate_ledger([row], _parse())[0]
    saved = {k: first.get(k) for k in (
        "model_status", "model_note", "model_setup_scenes", "model_payoff_scenes",
        "candidate_setup_scenes", "candidate_recurrence_scenes", "status",
        "verified", "verify_note", "payoff_scenes")}
    second = adjudicate_ledger([first], _parse())[0]
    assert {k: second.get(k) for k in saved} == saved
    assert second["status"] == "unverified"
    assert second["model_status"] == "paid"


def test_adjudicated_rows_do_not_enter_fix_queue():
    ledger = adjudicate_ledger([{
        "setup": "The cigar", "kind": "object", "setup_scenes": [1],
        "payoff_scenes": None, "status": "dangling", "note": "Not used."}], _parse())
    assert dangling_findings(ledger, [], doc=_parse()) == []


def test_legacy_unadjudicated_dangling_rows_still_make_findings():
    entries = [{"setup": "The cigar", "kind": "object", "setup_scenes": [1],
                "payoff_scenes": None, "status": "dangling", "note": "Not used."}]
    findings = dangling_findings(entries, [])
    assert len(findings) == 1
    assert findings[0]["category"] == "plot_thread"
    assert "cigar" in findings[0]["issue"].lower()


def test_report_never_calls_legacy_paid_row_verified():
    from screenplay_analyzer.pipeline import AnalysisResult
    from screenplay_analyzer.report import render_markdown
    result = AnalysisResult(doc=_parse())
    result.setup_payoff = [{
        "setup": "The cigar", "kind": "object", "setup_scenes": [1],
        "payoff_scenes": [2], "status": "paid", "verified": True,
        "note": "Terms recur in scene 2.",
    }]
    md = render_markdown(result)
    assert "Model assessment (unverified): paid off" in md
    assert "model-cited Scene 2 (not verified)" in md
    assert "✅ Paid off" not in md
    assert "payoff: never" not in md


def test_verifier_normalizes_direct_scene_refs_and_flags_bad_refs():
    from screenplay_analyzer.verifier import (
        verify_finding, verify_observation, verification_summary,
    )
    doc = _parse()
    quote = "The CIGAR sits on the table, untouched."
    for ref in (2, "2", "Scene 2"):
        assert verify_finding({"scene_refs": [ref], "evidence_quote": quote}, doc)[
            "verification"]["status"] == "verified"
    assert verify_finding({"scene_refs": ["Scene 9"], "evidence_quote": quote}, doc)[
        "verification"]["status"] == "scene_not_found"
    malformed = verify_finding({"scene_refs": ["Scene 2 maybe"],
                                "evidence_quote": quote}, doc)
    assert malformed["verification"]["status"] == "invalid_scene_ref"
    assert verify_observation({"scene_refs": ["Scene 2 maybe"],
                               "observation": "The cigar is present."}, doc) is None
    assert verification_summary([malformed])["invalid_scene_ref"] == 1


def test_time_pressure_seeds_preserve_boundaries_and_skip_set_dressing():
    doc = _parse("""Title: T
Author: T

INT. ROOM - NIGHT

MARA
Inka 3 mints a undi, hurry up now.

CUT TO:

INT. HALL - DAY

The wall clock reads 00:00 sharp and stops.

CUT TO:

INT. PHONE ROOM - NIGHT

The phone alarm rings loudly across the room now.
""")
    seeds = _time_pressure_seeds(doc)
    assert len(seeds) == 3
    assert "3 mints" in seeds[0]
    assert "00:00" in seeds[1]
    assert "alarm" in seeds[2].lower()
    plain = _parse("Title: T\nAuthor: T\n\nINT. ROOM - NIGHT\n\nA wall clock hangs here quietly.\n")
    assert _time_pressure_seeds(plain) == []
