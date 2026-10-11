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
