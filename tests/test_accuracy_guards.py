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
        _TScene(1, ["INT. FLAT - DAY", "Raj enters, exhausted.", "RAJ: life is choices.",
                    "RAJ: The feeling is very high from good decisions."],
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


def test_template_flood_across_scenes_demoted_by_similarity():
    """D3: sixteen near-identical 'Uncomplicated outcome' rows on distinct
    scenes must not all survive — same anchor key never fires there."""
    from screenplay_analyzer import pipeline as P
    template = ("Uncomplicated 'yes' outcome: the protagonist achieves his goal "
                "of SCENE{} without cost and no new problem arises.")
    rows = [
        {"category": "scene_function", "issue": template.format(i),
         "severity": "medium", "scene_refs": [i],
         "evidence_quote": None, "observation": f"Scene {i} ends quietly."}
        for i in range(1, 9)
    ]
    P.apply_absence_and_caps(rows, page_count=28.0)
    assert sum(1 for f in rows if f.get("capped")) >= 4, \
        "template flood across scenes must demote"


def test_distinct_issues_in_category_not_capped():
    from screenplay_analyzer import pipeline as P
    rows = [
        {"category": "scene_function",
         "issue": "The montage compresses a week of rehearsal into seconds.",
         "severity": "medium", "scene_refs": [1],
         "evidence_quote": "Montage:", "observation": "A montage opens the act."},
        {"category": "scene_function",
         "issue": "The interrogation inverts power with a single prop move.",
         "severity": "medium", "scene_refs": [2],
         "evidence_quote": "He slides the photo.", "observation": "A photo moves."},
        {"category": "scene_function",
         "issue": "The farewell lands without setup and earns no tears.",
         "severity": "medium", "scene_refs": [3],
         "evidence_quote": "Goodbye.", "observation": "A farewell closes."},
    ]
    P.apply_absence_and_caps(rows, page_count=28.0)
    assert not [f for f in rows if f.get("capped")], \
        "distinct issues must never trip the similarity cap"


def test_plot_point_and_catalyst_markers_skip_shorts():
    """D4: the trial rerun's Plot-Point-1 demand on a 6-page short sailed
    through — the marker set named midpoints but not plot points."""
    from screenplay_analyzer import pipeline as P
    rows = [
        {"category": "structure",
         "issue": "No clear Plot Point 1 or Catalyst to enter Confrontation.",
         "severity": "high", "scene_refs": [1, 2, 3],
         "evidence_quote": "Some line.", "observation": "Three scenes."},
        {"category": "structure",
         "issue": "No Call to Adventure or Inciting Incident in Act One.",
         "severity": "high", "scene_refs": [1],
         "evidence_quote": "Some line.", "observation": "Opens quiet."},
    ]
    P.apply_short_form_gate(rows, page_count=6.0)
    assert all(f.get("form_mismatch") for f in rows)
    assert all(f["severity"] == "low" for f in rows)


def test_possessive_apostrophe_is_not_a_quote_opener():
    """Trial rerun: "Raj's ... 'choices'" built a 16-word span from the
    possessive to the next quote, which matched nothing and misfired."""
    from screenplay_analyzer.verifier import verify_observation
    f = {"category": "character", "scene_refs": [1],
         "evidence_quote": None,
         "observation": "Raj's internal monologue references decisions."}
    assert verify_observation(f, _TDoc()) is True


def test_gloss_paraphrase_is_supported_but_invention_is_not():
    """A quoted gloss shares content words with the scene even when fuzzy
    matching rejects the rewording (0.44 here); a fabricated line shares
    almost none (0.38, zero overlap). Ratios measured, not assumed."""
    from screenplay_analyzer.verifier import verify_observation
    gloss = {"category": "dialogue", "scene_refs": [1],
             "evidence_quote": None,
             "observation": 'Raj says "decisions bring a high" twice.'}
    assert verify_observation(gloss, _TDoc()) is True
    invented = {"category": "dialogue", "scene_refs": [1],
                "evidence_quote": None,
                "observation": 'Raj declares "yes indeed sir, I agree" twice.'}
    assert verify_observation(invented, _TDoc()) is False


def test_quoteless_scene_function_row_flagged_and_demoted():
    """Trial-5 follow-up: a scene note with no evidence_quote is a summary
    opinion — flagged summary_only, one severity step down, never dropped."""
    from screenplay_analyzer import pipeline as P
    rows = [
        {"category": "scene_function", "issue": "Transitional bridge scene.",
         "severity": "medium", "scene_refs": [18],
         "evidence_quote": None, "observation": "Single action block."},
        {"category": "scene_function", "issue": "Static rehearsal scene.",
         "severity": "medium", "scene_refs": [8],
         "evidence_quote": "Rishi as he roams to and fro",
         "observation": "Speaks to himself."},
        {"category": "dialogue", "issue": "On-the-nose line.",
         "severity": "medium", "scene_refs": [2],
         "evidence_quote": None, "observation": "States the plan outright."},
    ]
    P.apply_scene_quote_rule(rows)
    assert len(rows) == 3
    assert rows[0].get("summary_only") is True
    assert rows[0]["severity"] == "low"
    assert rows[1].get("summary_only", False) is False
    assert rows[1]["severity"] == "medium"
    assert rows[2].get("summary_only", False) is False
    assert rows[2]["severity"] == "medium"


def test_quoteless_scene_function_low_row_flagged_not_double_demoted():
    """Already-low rows take the flag but severity floors at low."""
    from screenplay_analyzer import pipeline as P
    rows = [{"category": "scene_function", "issue": "Slow opening.",
             "severity": "low", "scene_refs": [7],
             "evidence_quote": None, "observation": "Walking and a call."}]
    P.apply_scene_quote_rule(rows)
    assert rows[0].get("summary_only") is True
    assert rows[0]["severity"] == "low"


def test_identity_parties_from_observation():
    from screenplay_analyzer import pipeline as P
    f = {"category": "character",
         "issue": "Protagonist Identity Ambiguity: Raj's role is unclear because he does not appear to be the 'Pen Guy'.",
         "observation": "The character labeled 'PEN_GUY' is a distinct entity not named Raj.",
         "severity": "high", "scene_refs": [1, 2, 3]}
    assert P._identity_parties(f) == ("RAJ", "PEN GUY")


def test_identity_single_name_returns_none():
    from screenplay_analyzer import pipeline as P
    assert P._identity_parties({"issue": "Rahul never appears after scene 4."}) is None
    assert P._identity_parties({"issue": "He never speaks to her."}) is None
