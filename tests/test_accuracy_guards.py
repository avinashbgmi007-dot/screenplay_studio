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


class _TEl:
    def __init__(self, text):
        self.text = text


class _TScene:
    def __init__(self, number, texts, characters):
        self.scene_number = number
        self.elements = [_TEl(t) for t in texts]
        self.characters_present = characters


class _TDoc:
    all_characters = ["RAJ", "GUN GUY", "PEN GUY"]
    scenes = [
        _TScene(1, ["INT. FLAT - DAY", "Raj enters, exhausted.", "RAJ: life is choices."],
                ["RAJ"]),
        _TScene(2, ["INT. FLAT - NIGHT", "Gun Guy loads his weapon.",
                    "GUN GUY: Who are you?", "PEN GUY: A journalist."],
                ["GUN GUY", "PEN GUY"]),
    ]


def test_observation_naming_absent_character_is_contradicted():
    """D2 acceptance case (trial rerun #9): the observation puts Raj in a
    confrontation his scene never contains."""
    from screenplay_analyzer.verifier import verify_observation
    f = {"category": "character", "scene_refs": [2],
         "evidence_quote": None,
         "observation": "Gun Guy and Pen Guy exist solely to facilitate "
                        "a confrontation with Raj."}
    assert verify_observation(f, _TDoc()) is False


def test_supported_observation_passes():
    from screenplay_analyzer.verifier import verify_observation
    f = {"category": "character", "scene_refs": [2],
         "evidence_quote": None,
         "observation": "Gun Guy loads his weapon while Pen Guy watches."}
    assert verify_observation(f, _TDoc()) is True


def test_missing_observation_is_skipped_not_weak():
    from screenplay_analyzer.verifier import verify_observation
    assert verify_observation({"scene_refs": [1]}, _TDoc()) is None
    assert verify_observation({"scene_refs": [1], "observation": "  "},
                              _TDoc()) is None


def test_fabricated_quoted_fragment_is_contradicted():
    from screenplay_analyzer.verifier import verify_observation
    f = {"category": "dialogue", "scene_refs": [1],
         "evidence_quote": None,
         "observation": 'Raj declares "yes indeed sir, I agree completely" twice.'}
    assert verify_observation(f, _TDoc()) is False


def test_stage_directions_are_not_characters():
    """ALL-CAPS non-names (CUT TO, THE END) must never count as characters."""
    from screenplay_analyzer.verifier import verify_observation
    f = {"category": "scene_function", "scene_refs": [1],
         "evidence_quote": None,
         "observation": "CUT TO after Raj enters. THE END follows."}
    assert verify_observation(f, _TDoc()) is True


def test_pipeline_flags_weak_observations_and_demotes():
    from screenplay_analyzer import pipeline as P
    rows = [
        {"category": "character", "issue": "No motivation.", "severity": "high",
         "scene_refs": [2], "evidence_quote": None,
         "observation": "Gun Guy and Pen Guy exist solely to facilitate "
                        "a confrontation with Raj."},
        {"category": "character", "issue": "Flat arc.", "severity": "medium",
         "scene_refs": [2], "evidence_quote": None,
         "observation": "Gun Guy loads his weapon while Pen Guy watches."},
    ]
    P.apply_observation_check(rows, _TDoc())
    assert rows[0].get("observation_weak") is True
    assert rows[0]["severity"] == "medium"
    assert rows[1].get("observation_weak", False) is False
    assert rows[1]["severity"] == "medium"
