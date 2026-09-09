"""
Tier 1: character-perception read + logline test.

The perception read reports how each character actually comes across to a
stranger vs. what the script appears to intend; the logline test judges
whether the premise lands in one sentence (strong/workable/muddled, no
grades). Both are diagnosis-only, evidence-verified, and respect the report
language.
"""

import io
import os

from screenplay_analyzer import pipeline, prompts
from screenplay_analyzer import grammar as grammar_mod
from screenplay_analyzer.report import render_markdown, to_findings_json
from screenplay_parser import parse_fountain


def _mini_doc():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "pain_tenglish.fountain")
    return parse_fountain(path)


# ---------------------------------------------------------------------------
# grammar
# ---------------------------------------------------------------------------

def test_logline_test_grammar_rules():
    g = grammar_mod.logline_test_grammar()
    for fragment in ("signal", "strong", "workable", "muddled", "what_works", "tightened"):
        assert fragment in g


def test_character_reads_grammar_rules():
    g = grammar_mod.character_reads_grammar()
    for fragment in ("reads-array", "how_reads", "apparent_intent", "evidence_quote", "scene_refs"):
        assert fragment in g


# ---------------------------------------------------------------------------
# prompts — language + diagnosis-only stance
# ---------------------------------------------------------------------------

def test_logline_prompt_carries_language():
    system, _ = prompts.logline_test_prompt("A logline.", "overview", "T", language="hindi")
    assert "Devanagari" in system
    # diagnosis only — never prescribes a rewrite as the deliverable
    assert "diagnose" in system.lower() or "diagnosis" in system.lower()


def test_character_reads_prompt_carries_language():
    system, _ = prompts.character_reads_prompt("overview", "T", ["A"], language="tenglish")
    assert "Tenglish" in system
    assert "stranger" in system.lower()


# ---------------------------------------------------------------------------
# pipeline functions
# ---------------------------------------------------------------------------

class QueueClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def chat_json(self, system, user, grammar=None, max_tokens=None, **kw):
        self.calls += 1
        if self.responses:
            return self.responses.pop(0)
        return {"findings": []}

    def resolve_model(self):
        return "test-model"


def test_run_character_reads_normalizes_and_verifies():
    doc = _mini_doc()
    reads = [
        {"character": "RAHUL", "how_reads": "comes across as passive", "apparent_intent": "tragic victim",
         "gap": "the passivity reads as weakness", "scene_refs": [4],
         "evidence_quote": "Siddhu kind of jerked, switches off the light immediately."},
        {"character": "MEERA", "how_reads": "sharp", "apparent_intent": "sharp",
         "gap": "minimal", "scene_refs": [2], "evidence_quote": "This quote does not exist anywhere."},
        {"character": "ONLY-NAME"},  # missing fields — must not crash
    ]
    out = pipeline.run_character_reads(doc, "overview", QueueClient([{"reads": reads}]), ["RAHUL", "MEERA", "ONLY-NAME"])
    assert len(out) == 3
    assert out[0]["scene_refs"] == [4]
    assert out[2]["how_reads"] == ""
    statuses = {r["character"]: r["verification"]["status"] for r in out}
    assert statuses["RAHUL"] == "verified"
    assert statuses["MEERA"] == "not_found"
    assert statuses["ONLY-NAME"] == "no_quote"


def test_run_character_reads_tolerates_bare_array_and_empty():
    doc = _mini_doc()
    items = [{"character": "RAHUL", "how_reads": "h", "apparent_intent": "i", "gap": "g"}]
    out = pipeline.run_character_reads(doc, "overview", QueueClient([items]), ["RAHUL"])
    assert len(out) == 1 and out[0]["character"] == "RAHUL"
    assert pipeline.run_character_reads(doc, "overview", QueueClient([{"reads": "garbage"}]), ["RAHUL"]) == []
    assert pipeline.run_character_reads(doc, "overview", QueueClient([{"reads": []}]), []) == []


def test_run_logline_test_passthrough_and_robustness():
    doc = _mini_doc()
    good = {"logline": "A comic artist returns to the city that destroyed him.",
            "signal": "workable", "what_works": "specific", "what_muddles": "stakes vague",
            "missing": "stakes", "tightened": "A disgraced comic artist must confront the city that destroyed him before it takes his brother too."}
    assert pipeline.run_logline_test(good["logline"], "overview", "T", QueueClient([good])) == good
    # non-dict and empty-logline cases must not fail
    assert pipeline.run_logline_test(good["logline"], "overview", "T", QueueClient([["bare"]])) == {}
    assert pipeline.run_logline_test("", "overview", "T", QueueClient([])) == {}


# ---------------------------------------------------------------------------
# full pipeline — both stages land in the result, the report, and the JSON
# ---------------------------------------------------------------------------

class SmartClient:
    """Routes responses by what the prompt is asking, so the full analyze()
    call doesn't depend on exact call counts."""

    def __init__(self):
        self.seen = []

    def resolve_model(self):
        return "test-model"

    def chat_json(self, system, user, grammar=None, max_tokens=None, **kw):
        self.seen.append(system)
        if "Summarize each of these scenes" in user or "summarize" in system.lower():
            return {"summaries": [{"scene_number": n, "summary": "Scene does something."} for n in range(1, 7)]}
        if "logline" in system.lower():
            return {"logline": "A comic artist returns to the city that destroyed him.",
                    "signal": "workable", "what_works": "specific protagonist",
                    "what_muddles": "stakes are vague", "missing": "clear stakes",
                    "tightened": "Tightened line."}
        if "impartial first-time reader" in system or "come across" in system.lower():
            return {"reads": [
                {"character": "RAHUL", "how_reads": "reads as passive", "apparent_intent": "tragic",
                 "gap": "passivity reads as weakness", "scene_refs": [4],
                 "evidence_quote": "Siddhu kind of jerked, switches off the light immediately."},
                {"character": "MEERA", "how_reads": "sharp", "apparent_intent": "sharp",
                 "gap": "minimal", "scene_refs": [2], "evidence_quote": None},
            ]}
        if "coverage" in system.lower():
            return {"logline": "A comic artist returns to the city that destroyed him.",
                    "genre": "drama", "tone": "dark", "one_page_synopsis": "Synopsis.",
                    "strengths": ["voice"], "weaknesses": ["pacing"],
                    "comparable_films": ["The Lunchbox"], "recommendation": "consider"}
        return {"findings": []}


def test_full_pipeline_includes_tier1_sections():
    doc = _mini_doc()
    client = SmartClient()
    result = pipeline.analyze(
        doc, client,
        run_categories=("theme", "character", "structure", "scene_function", "coverage", "char_reads", "logline_test"),
        progress_cb=None,
    )
    # no hard errors, both sections present
    assert not result.errors
    assert len(result.character_reads) == 2
    assert result.character_reads[0]["character"] == "RAHUL"
    assert result.character_reads[0]["verification"]["status"] in ("verified", "not_found")
    assert result.logline_test and result.logline_test["signal"] == "workable"

    md = render_markdown(result)
    assert "## Logline Test" in md
    assert "## How the Characters Read" in md
    assert "workable" in md.lower()
    assert "RAHUL" in md

    j = to_findings_json(result)
    assert len(j["character_reads"]) == 2
    assert j["logline_test"]["signal"] == "workable"


def test_logline_test_skipped_without_coverage_logline():
    """The logline test judges the coverage pass's logline — no logline, no test."""
    doc = _mini_doc()
    client = SmartClient()
    client.skip_logline = True
    # a client variant that produces coverage WITHOUT a logline
    class NoLogline(SmartClient):
        def chat_json(self, system, user, grammar=None, max_tokens=None, **kw):
            if "logline" in system.lower() and "tightened" in system:
                return {"logline": "", "signal": "muddled", "what_works": "", "what_muddles": "", "missing": "", "tightened": ""}
            if "coverage" in system.lower():
                return {"genre": "drama", "tone": "dark", "one_page_synopsis": "S.",
                        "strengths": [], "weaknesses": [], "recommendation": "pass"}
            return super().chat_json(system, user, grammar=grammar, max_tokens=max_tokens)

    result = pipeline.analyze(
        doc, NoLogline(),
        run_categories=("coverage", "char_reads", "logline_test"),
        progress_cb=None,
    )
    # coverage ran but produced no logline -> the test is skipped, not failed
    assert result.coverage is not None
    assert result.coverage.get("logline") in (None, "")
    assert result.logline_test is None
