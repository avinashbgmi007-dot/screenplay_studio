"""Kit B: small scripts are read whole, not summarized."""
from screenplay_analyzer import pipeline as P


class _El:
    def __init__(self, t):
        self.text = t


class _Scene:
    def __init__(self, n, texts):
        self.scene_number = n
        self.elements = [_El(t) for t in texts]


class _Doc:
    scene_count = 2
    scenes = [_Scene(1, ["INT. FLAT - DAY", "Raj wakes. It was a dream."]),
              _Scene(2, ["INT. FLAT - DAY", "He writes the article."])]


def test_small_script_overview_contains_full_text():
    stats = {}
    overview, source = P.build_script_level_source(_Doc(), "summary text", stats)
    assert source == "full_text"
    assert "It was a dream." in overview


def test_large_script_keeps_summary_path():
    big = _Doc()
    big.scenes = [_Scene(i, ["x" * 5000]) for i in range(1, 6)]
    stats = {}
    overview, source = P.build_script_level_source(big, "summary text", stats)
    assert source == "overview"
    assert overview == "summary text"


def test_dream_reveal_detected():
    from screenplay_analyzer.reveal_scan import scan_reveals

    class _E(dict):
        pass

    doc = _Doc()
    found = scan_reveals(doc)
    assert any("dream" in f["match"].lower() for f in found), \
        "the gunpen acceptance case: 'It was a dream.' must surface"
    assert found[0]["scene"] == 1


def test_reveal_candidates_reach_report_json_and_markdown():
    """B2 is only real if the candidates survive serialization: the scan runs
    in-memory, so a missing JSON key silently drops the whole feature."""
    import os
    from screenplay_parser import parse_fountain
    from screenplay_analyzer.pipeline import AnalysisResult
    from screenplay_analyzer import report as report_mod
    fixture = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "fixtures", "pain_tenglish.fountain")
    r = AnalysisResult(parse_fountain(fixture))
    r.reveal_candidates = [{"scene": 3, "line": "It was a dream.",
                            "match": "dream"}]
    payload = report_mod.to_findings_json(r)
    assert payload["reveal_candidates"] == r.reveal_candidates
    md = report_mod.render_markdown(r)
    assert "Story mechanics to consider" in md and "It was a dream." in md
    assert "contrary findings" in md


class _TwistClient:
    """Fake model endpoint: canned reply text, call counting."""

    def __init__(self, reply=None, exc=None):
        self.reply = reply
        self.exc = exc
        self.calls = 0
        self.last_system = None
        self.last_user = None

    def chat_json(self, system, user, **kw):
        self.calls += 1
        self.last_system = system
        self.last_user = user
        if self.exc is not None:
            raise self.exc
        return self.reply


def _twist_doc():
    return _Doc()


def test_confirm_twist_skips_call_without_candidates():
    from screenplay_analyzer.reveal_scan import confirm_twist

    class PlainDoc(_Doc):
        scenes = []

    client = _TwistClient(reply={})
    assert confirm_twist(PlainDoc(), client) is None
    assert client.calls == 0, "candidate-gated: no scan hit means no model call"


def test_confirm_twist_parses_json_and_grounds_location_from_quote():
    from screenplay_analyzer.reveal_scan import confirm_twist
    client = _TwistClient(reply={
        "twist": True, "scene": 2,
        "line": "It was a dream.", "kind": "dream"})
    verdict = confirm_twist(_twist_doc(), client)
    assert verdict == {
        "twist": True, "scene": 1, "line": "It was a dream.",
        "kind": "dream", "status": "interpretation",
        "coverage": {"scope": "full_script", "characters_sent": 81,
                     "script_characters": 81},
    }


def test_confirm_twist_false_and_garbage_yield_none():
    from screenplay_analyzer.reveal_scan import confirm_twist
    neg = _TwistClient(reply={"twist": False, "scene": None,
                              "line": "", "kind": "none"})
    assert confirm_twist(_twist_doc(), neg) is None
    garb = _TwistClient(reply={"huh": "??"})
    assert confirm_twist(_twist_doc(), garb) is None
    prose = _TwistClient(reply='Some thinking.\n{"twist": true, "scene": 2,'
                              ' "line": "It was a dream.", "kind": "dream"}')
    verdict = confirm_twist(_twist_doc(), prose)
    assert verdict is not None and verdict["scene"] == 1
    assert verdict["status"] == "interpretation"


def test_confirm_twist_model_error_yields_none():
    from screenplay_analyzer.reveal_scan import confirm_twist
    client = _TwistClient(exc=RuntimeError("model down"))
    assert confirm_twist(_twist_doc(), client) is None


def test_wrong_model_scene_is_replaced_by_quote_location():
    # A model's scene number is not authoritative; exact source text locates it.
    from screenplay_analyzer.reveal_scan import confirm_twist
    client = _TwistClient(reply={"twist": True, "scene": 99,
                                 "line": "It was a dream.", "kind": "dream"})
    verdict = confirm_twist(_twist_doc(), client)
    assert verdict is not None and verdict["twist"] is True
    assert verdict["scene"] == 1


def test_null_scene_can_be_recovered_from_exact_quote():
    from screenplay_analyzer.reveal_scan import confirm_twist
    client = _TwistClient(reply={"twist": True, "scene": None,
                                 "line": "It was a dream.", "kind": "dream"})
    verdict = confirm_twist(_twist_doc(), client)
    assert verdict is not None and verdict["scene"] == 1
    assert verdict["status"] == "interpretation"


def test_fabricated_keyword_citation_is_rejected_not_replaced():
    # A reveal keyword is not proof that a cited line exists in the script.
    from screenplay_analyzer.reveal_scan import confirm_twist
    client = _TwistClient(reply={"twist": True, "scene": 1,
                                 "line": "It was all a dream and the city vanished.",
                                 "kind": "dream"})
    assert confirm_twist(_twist_doc(), client) is None


def test_ordinary_dream_metaphor_hypothetical_and_ambiguous_quotes_stay_provisional():
    # Grounding verifies the words, not whether a dream phrase is literal plot.
    from screenplay_analyzer.reveal_scan import confirm_twist, confirmed_twist_block
    lines = [
        "MAYA dreams of a better job. It was a dream she had at lunch.",
        "MAYA calls the promotion 'It was a dream' as a metaphor for its ease.",
        "She says, 'It was a dream if the promotion happened,' but is speculating.",
        "MAYA wakes. It was a dream, perhaps; the ending leaves it unresolved.",
    ]
    for line in lines:
        doc = _Doc()
        doc.scenes = [_Scene(1, [line])]
        client = _TwistClient(reply={"twist": True, "scene": 1,
                                     "line": line, "kind": "dream"})
        verdict = confirm_twist(doc, client)
        block = confirmed_twist_block(verdict)
        assert verdict is not None and verdict["status"] == "interpretation"
        assert "not an established fact" in block
        assert "contrary findings" in block
        assert "suspect" not in block.lower()


def test_prefix_probe_reports_coverage_and_only_accepts_quote_in_prefix():
    from screenplay_analyzer.reveal_scan import confirm_twist, confirmed_twist_block
    doc = _Doc()
    doc.scenes = [_Scene(1, ["MAYA dreams. It was a dream."]),
                  _Scene(2, ["LATER: " + "x" * 9200, "Beyond budget line."])]
    client = _TwistClient(reply={"twist": True, "scene": 1,
                                 "line": "It was a dream.", "kind": "dream"})
    verdict = confirm_twist(doc, client)
    assert verdict is not None
    assert verdict["coverage"]["scope"] == "prefix"
    assert verdict["coverage"]["script_characters"] > verdict["coverage"]["characters_sent"]
    assert "later text has not been assessed" in client.last_user.lower()
    assert "later text was not assessed" in confirmed_twist_block(verdict).lower()

    late = _TwistClient(reply={"twist": True, "scene": 2,
                               "line": "Beyond budget line.",
                               "kind": "dream"})
    assert confirm_twist(doc, late) is None


def test_non_int_scene_is_still_rejected():
    """Null is a hedge; strings and booleans are not scene numbers."""
    from screenplay_analyzer.reveal_scan import parse_twist_verdict
    assert parse_twist_verdict({"twist": True, "scene": "three",
                                "line": "He wakes up.", "kind": "dream"}) is None
    assert parse_twist_verdict({"twist": True, "scene": True,
                                "line": "He wakes up.", "kind": "dream"}) is None


def test_unrelated_real_quote_is_rejected_not_replaced_by_candidate():
    # An authentic but unrelated line is not evidence for a twist; preserve the
    # independent deterministic cue rather than substituting it into a verdict.
    from screenplay_analyzer.reveal_scan import confirm_twist, scan_reveals
    client = _TwistClient(reply={"twist": True, "scene": 2,
                                 "line": "He writes the article.",
                                 "kind": "dream"})
    assert confirm_twist(_twist_doc(), client) is None
    assert scan_reveals(_twist_doc())[0]["line"] == "Raj wakes. It was a dream."


def test_overlong_quote_is_rejected_before_truncation():
    from screenplay_analyzer.reveal_scan import confirm_twist
    client = _TwistClient(reply={"twist": True, "scene": 1,
                                 "line": " " * 185 + "It was a dream." + " invented" * 30,
                                 "kind": "dream"})
    assert confirm_twist(_twist_doc(), client) is None


def test_duplicate_quote_uses_model_scene_only_if_that_scene_matches():
    from screenplay_analyzer.reveal_scan import confirm_twist
    doc = _Doc()
    doc.scenes = [_Scene(1, ["It was a dream."]), _Scene(2, ["It was a dream."])]
    client = _TwistClient(reply={"twist": True, "scene": 2,
                                 "line": "It was a dream.", "kind": "dream"})
    verdict = confirm_twist(doc, client)
    assert verdict is not None and verdict["scene"] == 2


def test_matching_cited_line_is_kept():
    from screenplay_analyzer.reveal_scan import confirm_twist
    client = _TwistClient(reply={"twist": True, "scene": 2,
                                 "line": "It was a dream.",
                                 "kind": "dream"})
    verdict = confirm_twist(_twist_doc(), client)
    assert verdict is not None
    assert verdict["line"] == "It was a dream."
    assert verdict["scene"] == 1


def test_twist_block_is_provisional_and_does_not_suppress_candidates():
    from screenplay_analyzer.reveal_scan import confirmed_twist_block, reveal_context_block
    assert confirmed_twist_block(None) == ""
    assert confirmed_twist_block({"twist": False}) == ""
    block = confirmed_twist_block({"twist": True, "scene": 3,
                                   "line": "It was a dream.", "kind": "dream"})
    candidates = reveal_context_block([{"scene": 1, "line": "A dream."}])
    assert "not an established fact" in block and "Scene 3" in block
    assert "suspect" not in block.lower()
    assert "Possible story-mechanic cues" in candidates
    assert "do not dismiss a finding" in candidates


def test_twist_interpretation_reaches_report_json_and_markdown():
    import os
    from screenplay_parser import parse_fountain
    from screenplay_analyzer.pipeline import AnalysisResult
    from screenplay_analyzer import report as report_mod
    fixture = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "fixtures", "pain_tenglish.fountain")
    r = AnalysisResult(parse_fountain(fixture))
    r.twist_verdict = {
        "twist": True, "scene": 3, "line": "It was a dream.",
        "kind": "dream", "status": "interpretation",
        "coverage": {"scope": "prefix", "characters_sent": 9000,
                     "script_characters": 12000},
    }
    payload = report_mod.to_findings_json(r)
    assert payload["twist_verdict"] == r.twist_verdict
    md = report_mod.render_markdown(r)
    assert "Possible reading: reality twist" in md
    assert "not an established fact" in md and "It was a dream." in md
    assert "later text was not assessed" in md
    assert "Confirmed twist" not in md


DREAM_DOC = """Title: Twist Test
Author: T

INT. ROOM - NIGHT

MARA stares at the door.

CUT TO:

INT. HALL - DAY

MARA wakes with a start. It was a dream.
"""


def test_pipeline_sets_twist_verdict_on_dream_doc(tmp_path):
    """End-to-end through analyze(): candidates found, probe confirms,
    verdict stored. FakeClient answers the probe; everything else canned."""
    import os
    from screenplay_parser import parse_fountain
    from screenplay_analyzer import pipeline as P

    path = os.path.join(str(tmp_path), "dream.fountain")
    with open(path, "w", encoding="utf-8") as f:
        f.write(DREAM_DOC)
    doc = parse_fountain(path)

    class TwistClient:
        def __init__(self):
            self.calls = []

        def resolve_model(self):
            return "mock"

        def chat_json(self, system, user, grammar=None, max_tokens=0,
                      temperature=0.0, **kw):
            self.calls.append((system, user))
            if system.startswith("You are offering one possible reading"):
                return {"twist": True, "scene": 2,
                        "line": "It was a dream.", "kind": "dream"}
            if "ummar" in system.lower():
                return {"summaries": [
                    {"scene_number": s.scene_number, "summary": "Things happen."}
                    for s in doc.scenes]}
            return {"findings": []}

    client = TwistClient()
    result = P.analyze(doc, client, run_categories=("theme",),
                       progress_cb=None)
    assert result.twist_verdict["twist"] is True
    assert result.twist_verdict["scene"] == 2
    assert result.twist_verdict["line"] == "It was a dream."
    assert result.twist_verdict["status"] == "interpretation"
    assert result.twist_verdict["coverage"]["scope"] == "full_script"
    assert any("dream" in str(c.get("match", "")).lower()
               for c in result.reveal_candidates)
    category_prompts = [system for system, _user in client.calls
                        if "Possible story-mechanic cues" in system]
    assert category_prompts
    assert "Model-suggested reality-twist reading" in category_prompts[0]
    assert "not an established fact" in category_prompts[0]
