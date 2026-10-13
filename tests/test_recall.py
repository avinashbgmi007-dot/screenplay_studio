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
    assert "Story mechanics" in md and "It was a dream." in md


class _TwistClient:
    """Fake model endpoint: canned reply text, call counting."""

    def __init__(self, reply=None, exc=None):
        self.reply = reply
        self.exc = exc
        self.calls = 0

    def chat_json(self, system, user, **kw):
        self.calls += 1
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


def test_confirm_twist_parses_trailing_json():
    from screenplay_analyzer.reveal_scan import confirm_twist
    client = _TwistClient(reply={
        "twist": True, "scene": 2,
        "line": "It was a dream.", "kind": "dream"})
    verdict = confirm_twist(_twist_doc(), client)
    assert verdict == {"twist": True, "scene": 2,
                       "line": "It was a dream.", "kind": "dream"}


def test_confirm_twist_false_and_garbage_yield_none():
    from screenplay_analyzer.reveal_scan import confirm_twist
    neg = _TwistClient(reply={"twist": False, "scene": None,
                              "line": "", "kind": "none"})
    assert confirm_twist(_twist_doc(), neg) is None
    garb = _TwistClient(reply={"huh": "??"})
    assert confirm_twist(_twist_doc(), garb) is None
    prose = _TwistClient(reply='Some thinking.\n{"twist": true, "scene": 2,'
                              ' "line": "It was a dream.", "kind": "dream"}')
    assert confirm_twist(_twist_doc(), prose) == {
        "twist": True, "scene": 2,
        "line": "It was a dream.", "kind": "dream"}


def test_confirm_twist_model_error_yields_none():
    from screenplay_analyzer.reveal_scan import confirm_twist
    client = _TwistClient(exc=RuntimeError("model down"))
    assert confirm_twist(_twist_doc(), client) is None


def test_impossible_scene_number_is_kept_honest():
    """Trial acceptance: the model confirmed the dream but cited scene 4 of
    a 3-scene script. Keep the verdict (detection is the valuable part),
    drop the false precision — never print a scene that does not exist."""
    from screenplay_analyzer.reveal_scan import confirm_twist
    client = _TwistClient(reply={"twist": True, "scene": 99,
                                 "line": "It was a dream.", "kind": "dream"})
    verdict = confirm_twist(_twist_doc(), client)
    assert verdict is not None and verdict["twist"] is True
    assert verdict["scene"] is None


def test_confirmed_twist_with_null_scene_is_kept():
    """Autopsy 2026-10-13: 7/8 live probes confirmed the dream; the null
    came from scene:null (location hedge), which the parser rejected.
    Every stored verdict carries scene None anyway — accept it."""
    from screenplay_analyzer.reveal_scan import confirm_twist
    client = _TwistClient(reply={"twist": True, "scene": None,
                                 "line": "He wakes up.", "kind": "dream"})
    assert confirm_twist(_twist_doc(), client) == {
        "twist": True, "scene": None,
        "line": "He wakes up.", "kind": "dream"}


def test_non_int_scene_is_still_rejected():
    """Null is a hedge; a string scene is garbage — the bar stays."""
    from screenplay_analyzer.reveal_scan import parse_twist_verdict
    assert parse_twist_verdict({"twist": True, "scene": "three",
                                "line": "He wakes up.", "kind": "dream"}) is None


def test_unrelated_cited_line_falls_back_to_candidate():
    """Live 8-probe finding: 3 confirmations cited an unrelated beat.
    The deterministic candidate replaces the model's pick."""
    from screenplay_analyzer.reveal_scan import confirm_twist
    client = _TwistClient(reply={"twist": True, "scene": 2,
                                 "line": "He writes the article.",
                                 "kind": "dream"})
    verdict = confirm_twist(_twist_doc(), client)
    assert verdict is not None and verdict["twist"] is True
    assert verdict["line"] == "Raj wakes. It was a dream."
    assert verdict["scene"] == 1


def test_matching_cited_line_is_kept():
    """A citation that matches the candidate (or carries twist vocabulary)
    is the model's to keep."""
    from screenplay_analyzer.reveal_scan import confirm_twist
    client = _TwistClient(reply={"twist": True, "scene": 2,
                                 "line": "It was a dream.",
                                 "kind": "dream"})
    verdict = confirm_twist(_twist_doc(), client)
    assert verdict is not None
    assert verdict["line"] == "It was a dream."


def test_confirmed_block_replaces_candidate_block():
    from screenplay_analyzer.reveal_scan import confirmed_twist_block
    assert confirmed_twist_block(None) == ""
    assert confirmed_twist_block({"twist": False}) == ""
    block = confirmed_twist_block({"twist": True, "scene": 3,
                                   "line": "It was a dream.", "kind": "dream"})
    assert "CONFIRMED" in block and "Scene 3" in block


def test_twist_verdict_reaches_report_json_and_markdown():
    import os
    from screenplay_parser import parse_fountain
    from screenplay_analyzer.pipeline import AnalysisResult
    from screenplay_analyzer import report as report_mod
    fixture = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "fixtures", "pain_tenglish.fountain")
    r = AnalysisResult(parse_fountain(fixture))
    r.twist_verdict = {"twist": True, "scene": 3,
                       "line": "It was a dream.", "kind": "dream"}
    payload = report_mod.to_findings_json(r)
    assert payload["twist_verdict"] == r.twist_verdict
    md = report_mod.render_markdown(r)
    assert "confirmed twist" in md.lower() and "It was a dream." in md


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
        def resolve_model(self):
            return "mock"

        def chat_json(self, system, user, grammar=None, max_tokens=0,
                      temperature=0.0, **kw):
            if "reality-twist" in system:
                return {"twist": True, "scene": 2,
                        "line": "It was a dream.", "kind": "dream"}
            if "ummar" in system.lower():
                return {"summaries": [
                    {"scene_number": s.scene_number, "summary": "Things happen."}
                    for s in doc.scenes]}
            return {"findings": []}

    result = P.analyze(doc, TwistClient(), run_categories=("theme",),
                       progress_cb=None)
    assert result.twist_verdict == {"twist": True, "scene": 2,
                                    "line": "It was a dream.", "kind": "dream"}
    assert any("dream" in str(c.get("match", "")).lower()
               for c in result.reveal_candidates)
