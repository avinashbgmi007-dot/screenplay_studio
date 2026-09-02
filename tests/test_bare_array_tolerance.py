"""Tests for tolerance of model outputs that arrive as a bare JSON array
instead of the keyed object (some local GBNF/GGUF models ignore the grammar
shape and emit the list directly). Regression for a real failure hit during
the live llama-server E2E: `'list' object has no attribute 'get'`."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_parser import parse_fountain
from screenplay_analyzer import pipeline
from screenplay_analyzer.genre import run_genre_check
from screenplay_analyzer.principles_engine import _finding_from_judgment


SAMPLE = """Title: Array Test
Author: T

INT. ROOM - NIGHT

MARA enters slowly, holding a glass of water.

MARA
I can't stay.

DEREK
Then don't.

CUT TO:

INT. HALL - DAY

MARA stands at the door, key in hand.
"""


class BareArrayClient:
    """Stands in for LlamaServerClient — every chat_json returns a bare list."""

    def __init__(self, items):
        self._items = items

    def chat_json(self, *args, **kwargs):
        return self._items


class StubRules:
    def prompt_fragment_for_category(self, category):
        return ""

    def prompt_fragment_for_rule(self, rule):
        return ""

    def fragment_for_pass(self, pass_name):
        return ""


def _doc():
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE)
        path = f.name
    try:
        return parse_fountain(path)
    finally:
        os.unlink(path)


def test_dialogue_analysis_tolerates_bare_array():
    doc = _doc()
    items = [{"category": "dialogue", "issue": "X", "why_it_matters": "Y",
              "severity": "low", "scene_refs": [1], "evidence_quote": None}]
    findings, errors = pipeline.run_dialogue_analysis(
        doc, BareArrayClient(items), rules_ctx=StubRules()
    )
    assert len(findings) == 1
    assert findings[0]["category"] == "dialogue"
    assert errors == []


def test_summaries_tolerate_bare_array():
    doc = _doc()
    items = [{"scene_number": 1, "summary": "MARA hesitates."},
             {"scene_number": 2, "summary": "MARA leaves."}]
    summaries, errors = pipeline.build_scene_summaries(doc, BareArrayClient(items))
    assert summaries == {1: "MARA hesitates.", 2: "MARA leaves."}
    assert errors == []


def test_script_level_category_tolerates_bare_array():
    items = [{"category": "theme", "issue": "T", "why_it_matters": "W",
              "severity": "low", "scene_refs": [], "evidence_quote": None}]
    findings = pipeline.run_script_level_category(
        lambda *a, **k: ("sys", "usr"),
        BareArrayClient(items),
        rules_fragment="",
    )
    assert len(findings) == 1


def test_genre_check_tolerates_bare_array():
    items = [{"category": "genre", "issue": "G", "why_it_matters": "W",
              "severity": "low", "scene_refs": [], "evidence_quote": None}]
    findings = run_genre_check({"genre": "Drama"}, "overview", BareArrayClient(items))
    assert len(findings) == 1
    assert findings[0]["category"] == "genre"


def test_genre_check_tolerates_scalar_garbage():
    assert run_genre_check({"genre": "Drama"}, "overview", BareArrayClient("nonsense")) == []


def test_principle_judgment_tolerates_bare_array():
    finding = _finding_from_judgment("recurring_object", "REVOLVER", [1, 3], ["a", "b"], "chekhovs_gun")
    assert finding is None  # a non-dict judgment is never actionable
