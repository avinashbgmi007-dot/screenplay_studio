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
