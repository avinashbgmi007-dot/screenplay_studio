"""Kit A guardrails: weak findings are demoted, never deleted."""
from screenplay_analyzer.pipeline import AnalysisResult


def _result_with(*rows):
    # Plain dataclass, no validation on construct — doc=None is fine for
    # tests that only touch findings (mirrors test_generation_timeout.py).
    r = AnalysisResult(doc=None)
    r.findings = [dict(f) for f in rows]
    return r


def test_quoteless_observationless_row_is_flagged_not_dropped():
    from screenplay_analyzer import pipeline as P
    r = _result_with(
        {"category": "scene_function", "issue": "Scene 21 provides a neat resolution.",
         "severity": "medium", "scene_refs": [21],
         "evidence_quote": None, "observation": None},
        {"category": "dialogue", "issue": "On-the-nose line.",
         "severity": "medium", "scene_refs": [2],
         "evidence_quote": "Who cares!", "observation": None},
    )
    P.apply_evidence_floor(r)
    assert len(r.findings) == 2, "flag-don't-drop: demote, never delete"
    assert r.findings[0].get("ungrounded") is True
    assert r.findings[0]["severity"] == "low"
    assert r.findings[1].get("ungrounded", False) is False
    assert r.findings[1]["severity"] == "medium"


def test_refuting_observation_demotes_one_step():
    from screenplay_analyzer import pipeline as P
    r = _result_with(
        {"category": "character", "issue": "Supporting character lacks motivation.",
         "severity": "high", "scene_refs": [3],
         "evidence_quote": "Who asked you?",
         "observation": "The note claims no motivation; however, the script explicitly shows a direct confrontation."},
    )
    P.apply_evidence_floor(r)
    assert r.findings[0].get("contested") is True
    assert r.findings[0]["severity"] == "medium"


SHORT_SCRIPT_PAGES = 6.0


def test_framework_demand_on_short_demoted_with_marker():
    from screenplay_analyzer import pipeline as P
    r = _result_with(
        {"category": "structure", "issue": "No midpoint shift from reaction to action.",
         "severity": "medium", "scene_refs": [2],
         "evidence_quote": "INT. SAME APARTMENT - LATE EVENING", "observation": None},
    )
    P.apply_short_form_gate(r.findings, page_count=SHORT_SCRIPT_PAGES)
    assert r.findings[0].get("form_mismatch") is True
    assert r.findings[0]["severity"] == "low"


def test_long_script_untouched():
    from screenplay_analyzer import pipeline as P
    r = _result_with(
        {"category": "structure", "issue": "No midpoint shift from reaction to action.",
         "severity": "medium", "scene_refs": [2],
         "evidence_quote": "INT. SAME APARTMENT - LATE EVENING", "observation": None},
    )
    P.apply_short_form_gate(r.findings, page_count=28.0)
    assert r.findings[0].get("form_mismatch", False) is False


def test_untranslated_barrier_finding_is_filtered():
    from screenplay_analyzer.feedback_filter import is_non_writing_feedback
    assert is_non_writing_feedback({
        "issue": "Dialogue relies on untranslated foreign language that obscures meaning.",
        "why_it_matters": "The audience cannot follow the stakes without translation.",
    }) is True


def test_absence_rows_dropped_and_caps_demote():
    from screenplay_analyzer import pipeline as P
    rows = [
        {"category": "dialogue", "issue": "N/A - No dialogue present to evaluate.",
         "severity": "low", "scene_refs": [5],
         "evidence_quote": None, "observation": "Scene 5 has no dialogue."},
    ]
    rows += [
        {"category": "character", "issue": f"Protagonist lacks trait {i}.",
         "severity": "high", "scene_refs": [1],
         "evidence_quote": "He enters.", "observation": "Enters quietly."}
        for i in range(9)
    ]
    P.apply_absence_and_caps(rows, page_count=6.0)
    assert not [f for f in rows if (f.get("issue") or "").strip().lower().startswith("n/a")], \
        "absence is not a finding"
    kept = [f for f in rows if f.get("category") == "character"]
    assert sum(1 for f in kept if f.get("capped")) >= 3, "same-anchor pileup demoted"
