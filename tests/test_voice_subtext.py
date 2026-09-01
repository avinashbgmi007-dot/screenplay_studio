"""Tests for the deterministic craft passes (voice-bleed, on-the-nose
subtext), finding normalization, and token-budget chunking."""

import os
import tempfile

from screenplay_parser import parse_fountain
from screenplay_analyzer import pipeline
from screenplay_analyzer.voice import (
    run_voice_analysis,
    run_subtext_analysis,
    VOICE_SIMILARITY_THRESHOLD,
)


def _parse(text):
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False, encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        return parse_fountain(path)
    finally:
        os.unlink(path)


# Two characters with identical verbal tics (same repeated filler words,
# same sentence shapes) — should be flagged as one voice.
TWINS = """Title: Twins
Author: T

INT. ROOM - NIGHT

AARAV enters, hands in pockets.

AARAV
So like, you know what I mean, it's really hard to say this.

MEERA
So like, you know what I mean, it's really hard to hear this.

AARAV
You know, I feel like it's really hard to keep going.

MEERA
You know, I feel like it's really hard to stop talking.

CUT TO:

INT. KITCHEN - NIGHT

AARAV sits, looking down.

AARAV
Like, you know, it's really hard to look at you now.

MEERA
Like, you know, it's really hard to look at me too.
"""

# Distinct voices: AARAV terse and blunt, MEERA long and lyrical.
DISTINCT = """Title: Distinct
Author: T

INT. ROOM - NIGHT

AARAV enters, hands in pockets.

AARAV
No.

MEERA
I wasn't asking whether you could, I was asking whether you would
have the courage to, given everything that happened between us.

AARAV
Why.

MEERA
Because the answer matters more than the excuse, and you've never
once given me a straight one.

AARAV
Fine.

MEERA
Fine was never fine, and you know it.
"""

ON_THE_NOSE = """Title: Subtext
Author: T

INT. ROOM - NIGHT

RIA faces KABIR.

RIA
I'm so angry at you right now.

KABIR
(calm)
I'm sorry.

RIA
I hate this. I feel tired all the time.

CUT TO:

INT. HALL - DAY

RIA packs a bag.

RIA
You know what, the weather is nice today.
"""


class TestVoiceBleed:
    def test_identical_voices_flagged(self):
        doc = _parse(TWINS)
        findings, errors = run_voice_analysis(doc)
        assert errors == []
        pairs = {(f["issue"] for _ in [0]) for f in findings}
        assert any("AARAV and MEERA" in f["issue"] for f in findings)
        assert all(f["category"] == "voice" for f in findings)
        assert all(f["severity"] == "medium" for f in findings)
        assert all(f["scene_refs"] for f in findings)  # they share scenes

    def test_distinct_voices_not_flagged(self):
        doc = _parse(DISTINCT)
        findings, _ = run_voice_analysis(doc)
        assert findings == []

    def test_threshold_sanity(self):
        # identical fingerprints score >= the threshold
        doc = _parse(TWINS)
        findings, _ = run_voice_analysis(doc)
        assert findings, "expected at least one flagged pair"
        assert len(findings) <= 6  # capped

    def test_voice_analysis_skips_underdeveloped_characters(self):
        doc = _parse(ON_THE_NOSE)  # RIA has 3 lines, KABIR 1 -> no pair
        findings, _ = run_voice_analysis(doc)
        assert findings == []


class TestSubtext:
    def test_on_the_nose_lines_flagged(self):
        doc = _parse(ON_THE_NOSE)
        findings, errors = run_subtext_analysis(doc)
        assert errors == []
        issues = " | ".join(f["issue"] for f in findings)
        assert "I'm so angry" in issues
        assert "I hate this" in issues
        assert "I feel tired" in issues
        # the neutral weather line is NOT flagged
        assert "weather is nice" not in issues
        assert all(f["category"] == "subtext" for f in findings)
        # quotes are verbatim script lines
        assert all(f["evidence_quote"] in ("I'm so angry at you right now.", "I hate this. I feel tired all the time.") for f in findings if "angry" in f["issue"] or "hate" in f["issue"])

    def test_no_false_positives_on_normal_dialogue(self):
        doc = _parse(DISTINCT)
        findings, _ = run_subtext_analysis(doc)
        assert findings == []


class TestNormalization:
    def test_missing_severity_and_category_filled(self):
        raw = [
            {"issue": "X", "why_it_matters": "W", "scene_refs": [1], "evidence_quote": "q"},
            {"issue": "Y", "severity": "high", "category": "structure"},
        ]
        out = pipeline._normalize_findings(raw, "dialogue", default_severity="low")
        assert out[0]["category"] == "dialogue"
        assert out[0]["severity"] == "low"
        assert out[0]["rule_id"] is None
        assert out[1]["severity"] == "high"  # explicit value untouched
        assert out[1]["why_it_matters"] == ""

    def test_non_dict_entries_dropped(self):
        raw = [{"issue": "ok"}, "junk", None, 42]
        out = pipeline._normalize_findings(raw, "theme")
        assert len(out) == 1
        assert out[0]["category"] == "theme"

    def test_dialogue_analysis_normalizes_output(self):
        items = [{"issue": "blank severity", "why_it_matters": "w",
                  "severity": None, "scene_refs": [1], "evidence_quote": None}]
        doc = _parse(DISTINCT)
        findings, _ = pipeline.run_dialogue_analysis(
            doc, _StubClient(items), rules_ctx=_StubRules()
        )
        assert findings[0]["severity"] == "low"
        assert findings[0]["category"] == "dialogue"


class TestBudgetChunking:
    def test_budget_splits_large_scenes(self):
        scenes = [{"full_text": "word " * 600} for _ in range(4)]  # ~600 tokens each
        chunks = pipeline._chunk_by_budget(scenes, chunk_size=3, budget=1500)
        assert all(len(c) <= 3 for c in chunks)
        assert sum(len(c) for c in chunks) == 4
        assert len(chunks) > 1  # budget forced a split below the cap

    def test_small_scenes_stay_at_cap(self):
        scenes = [{"full_text": "short scene text"} for _ in range(5)]
        chunks = pipeline._chunk_by_budget(scenes, chunk_size=3, budget=1500)
        assert [len(c) for c in chunks] == [3, 2]


class _StubRules:
    def prompt_fragment_for_category(self, category):
        return ""

    def prompt_fragment_for_rule(self, rule):
        return ""

    def fragment_for_pass(self, pass_name):
        return ""


class _StubClient:
    def __init__(self, items):
        self._items = items

    def resolve_model(self):
        return "stub-model"

    def chat_json(self, *args, **kwargs):
        return self._items


class TestCraftPassesInsideAnalyze:
    """Regression: the voice/subtext passes once referenced `all_findings`
    before it was initialized, so they crashed inside analyze() and their
    findings silently never made it into reports (caught live on the full
    Pain script run: 'cannot access local variable all_findings')."""

    def test_voice_findings_flow_into_analyze_result(self):
        doc = _parse(TWINS)  # identical voices -> must be flagged
        client = _StubClient({"findings": []})  # model dialogue finds nothing
        result = pipeline.analyze(doc, client, run_categories=("dialogue",))
        voice_issues = [f["issue"] for f in result.findings if f.get("category") == "voice"]
        assert any("AARAV and MEERA" in i for i in voice_issues), voice_issues
        assert not any("Craft passes" in e for e in result.errors), result.errors

    def test_subtext_findings_flow_into_analyze_result(self):
        doc = _parse(ON_THE_NOSE)
        client = _StubClient({"findings": []})
        result = pipeline.analyze(doc, client, run_categories=("dialogue",))
        subtext = [f["issue"] for f in result.findings if f.get("category") == "subtext"]
        assert any("I'm so angry" in i for i in subtext), subtext


class TestContextHardening:
    """The live full-script run blew the model's context window (scenes 6/7/14
    failed with finish_reason='length', and so did the structure pass). These
    tests lock in the caps that prevent over-stuffed prompts."""

    def test_scene_text_capped_for_model(self):
        long_text = "A" * 5000
        capped = pipeline._cap_scene_text(long_text)
        assert len(capped) < 5000
        assert pipeline.TRUNCATION_MARKER in capped
        # small scenes pass through untouched
        assert pipeline._cap_scene_text("short") == "short"

    def test_scene_full_text_capped(self):
        doc = _parse("Title: T\nAuthor: A\n\nINT. X - DAY\n\n" + ("MARA walks. " * 600) + "\n\nMARA\nHi.\n")
        text = pipeline._scene_full_text(doc.scenes[0])
        assert len(text) <= pipeline.MAX_SCENE_CHARS + len(pipeline.TRUNCATION_MARKER) + 1

    def test_chunker_respects_completion_reserve(self):
        # two big scenes must not share a chunk: prompt + requested completion
        # would exceed the model's window
        scenes = [{"full_text": "word " * 900} for _ in range(3)]  # ~3000 chars ≈ 1000+ tokens each
        chunks = pipeline._chunk_by_budget(scenes, chunk_size=3, budget=pipeline.TOKEN_BUDGET)
        assert all(len(c) == 1 for c in chunks), [len(c) for c in chunks]

    def test_overview_capped(self):
        doc = _parse("Title: T\nAuthor: A\n\nINT. X - DAY\n\nMARA enters.\n\nMARA\nHi.\n")
        overview = pipeline.build_scene_overview_text(doc, {1: "word " * 3000})
        assert len(overview) <= pipeline.MAX_OVERVIEW_CHARS + 80
        assert "truncated" in overview
