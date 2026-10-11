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
