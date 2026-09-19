"""§5 item 2 — selective raw-text access for the script-level passes.

The ceiling §2 named: theme / character / structure / scene_function judge from
MODEL-WRITTEN scene summaries, so a share of every report is about a *description*
of the script rather than the script. The trade is deliberate (context window),
but it bites hardest exactly where a story turns — the act break, the midpoint,
the climax.

So those four passes are handed the RAW PAGES for a small, deterministic set of
scenes: the structural checkpoints plus the scenes the earlier passes flagged
most, inside a bounded budget. Deterministic (no model call, same script → same
set) and disclosed — the report names the scenes, because "we read some of your
pages" is a scope the writer is entitled to see.

New symbols are reached through the MODULE rather than imported by name, so this
file still IMPORTS on the pre-fix code: each test then fails on its own assertion
instead of the whole module collapsing into a collection error. That is what makes
the stash-based mutation check readable.
"""

import io
import os
import re

import pytest

from screenplay_analyzer import pipeline
from screenplay_analyzer.report import render_markdown
from screenplay_parser import parse_fountain
from screenplay_parser.models import Element, ElementType, Scene, ScriptDocument

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "pain_tenglish.fountain")

# A line that exists only in the PAGES — never in a summary of them.
RAW_LINE = "Rishi, ippativarku Siddharth unconscious unnadani cheppaledu"


def _doc(scene_count=20, pages=None, text="INT. ROOM - DAY\n\nSomething happens here."):
    """A synthetic script. `pages` is an optional per-scene page_end list."""
    scenes = []
    for i in range(1, scene_count + 1):
        scenes.append(Scene(
            scene_number=i,
            heading_raw=f"INT. ROOM {i} - DAY",
            page_end=(pages[i - 1] if pages else None),
            elements=[Element(type=ElementType.ACTION, text=text)],
        ))
    return ScriptDocument(title="T", author="A", source_format="fountain",
                          source_filename="t.fountain", scenes=scenes)


# --------------------------------------------------------------------------
# which scenes get read
# --------------------------------------------------------------------------

class TestWhichScenesGetRead:
    def test_selection_is_deterministic(self):
        doc = _doc(20)
        first = pipeline.select_checkpoint_scenes(doc, [])
        assert pipeline.select_checkpoint_scenes(doc, []) == first

    def test_the_order_the_findings_arrive_in_does_not_change_the_answer(self):
        doc = _doc(20)
        a = pipeline.select_checkpoint_scenes(
            doc, [{"scene_refs": [7]}, {"scene_refs": [11]}])
        b = pipeline.select_checkpoint_scenes(
            doc, [{"scene_refs": [11]}, {"scene_refs": [7]}])
        assert a == b

    def test_it_reads_the_structural_checkpoints(self):
        picked = pipeline.select_checkpoint_scenes(_doc(20), [])
        assert 20 in picked, f"the climax is always a checkpoint: {picked}"
        for want in (5, 10, 15):  # the quarter, middle and three-quarter marks
            assert any(abs(n - want) <= 1 for n in picked), (want, picked)

    def test_position_is_measured_in_pages_when_the_parser_supplied_them(self):
        """Scene 1 covers 40 of 49 pages. By SCENE INDEX the quarter-mark is
        scene 3; by PAGES it is scene 1. Pages win — that is where the turn
        actually sits in the script a reader holds."""
        pages = [40] + [41 + i for i in range(9)]
        picked = pipeline.select_checkpoint_scenes(_doc(10, pages=pages), [])
        assert 1 in picked, picked
        assert 5 not in picked, picked
        assert 10 in picked, picked

    def test_it_adds_the_scenes_the_earlier_passes_flagged(self):
        doc = _doc(20)
        assert 3 not in pipeline.select_checkpoint_scenes(doc, [])
        flagged = pipeline.select_checkpoint_scenes(
            doc, [{"scene_refs": [3]}, {"scene_refs": [3]}, {"scene_refs": [3]}])
        assert 3 in flagged, flagged

    def test_it_is_bounded(self):
        doc = _doc(20)
        every = [{"scene_refs": [n]} for n in range(1, 21)]
        assert len(pipeline.select_checkpoint_scenes(doc, every, limit=2)) == 2
        assert (len(pipeline.select_checkpoint_scenes(doc, every))
                <= pipeline.MAX_CHECKPOINT_SCENES)

    def test_it_never_returns_a_scene_that_is_not_in_the_document(self):
        picked = pipeline.select_checkpoint_scenes(
            _doc(5), [{"scene_refs": [999]}, {"scene_refs": ["x"]}, {"scene_refs": [None]}])
        assert all(1 <= n <= 5 for n in picked), picked

    def test_an_empty_document_yields_nothing(self):
        assert pipeline.select_checkpoint_scenes(_doc(0), []) == []

    def test_a_zero_limit_yields_nothing(self):
        assert pipeline.select_checkpoint_scenes(_doc(20), [], limit=0) == []


# --------------------------------------------------------------------------
# the block that gets sent
# --------------------------------------------------------------------------

class TestTheRawBlock:
    def test_it_carries_the_pages_not_a_summary(self):
        doc = parse_fountain(FIXTURE)
        text = pipeline.build_checkpoint_text(
            doc, pipeline.select_checkpoint_scenes(doc, []))
        assert RAW_LINE in text, "the block is not the raw page text"

    def test_it_names_the_scene_it_quotes(self):
        doc = parse_fountain(FIXTURE)
        text = pipeline.build_checkpoint_text(doc, [2])
        assert text.startswith("Scene 2 [")
        assert doc.scenes[1].heading_raw in text

    def test_the_budget_is_strict_and_names_what_it_dropped(self):
        doc = _doc(20, text="x" * 1500)
        text = pipeline.build_checkpoint_text(doc, list(range(1, 21)), budget=4000)
        assert "omitted for the context budget" in text
        assert text.count("Scene ") >= 1
        # nothing vanishes quietly: every dropped scene is named in the notice
        dropped = [n for n in range(1, 21) if f"Scene {n} [" not in text]
        assert dropped, "the budget did not actually bind — the test is vacuous"
        notice = text.split("omitted for the context budget:")[1]
        for n in dropped:
            assert str(n) in notice, f"scene {n} was dropped without being named"

    def test_a_budget_too_small_for_even_one_scene_yields_nothing(self):
        """Not a truncated fragment: "" so the caller leaves the pass on
        summaries rather than claiming a reading that did not happen."""
        assert pipeline.build_checkpoint_text(_doc(3), [1, 2], budget=10) == ""

    def test_an_unknown_scene_number_is_ignored(self):
        assert pipeline.build_checkpoint_text(_doc(3), [999], budget=4000) == ""

    def test_the_budget_cannot_silently_swallow_every_checkpoint(self):
        """If MAX_CHECKPOINT_CHARS ever fell below one scene's cap, every block
        would be dropped and the report would quietly revert to summaries-only."""
        assert pipeline.MAX_CHECKPOINT_CHARS >= 2 * pipeline.MAX_SCENE_CHARS

    def test_a_real_script_always_yields_some_pages(self):
        doc = parse_fountain(FIXTURE)
        assert pipeline.build_checkpoint_text(
            doc, pipeline.select_checkpoint_scenes(doc, [])) != ""


# --------------------------------------------------------------------------
# the overview the script-level passes actually receive
# --------------------------------------------------------------------------

class TestTheOverviewThePassesReceive:
    def test_no_checkpoints_leaves_the_overview_alone(self):
        assert pipeline.build_script_level_overview("OV", "") == "OV"

    def test_the_header_tells_the_model_to_trust_the_pages(self):
        out = pipeline.build_script_level_overview("OV", "Scene 1 [X]:\nbody")
        assert "RAW PAGES OF KEY SCENES" in out
        assert "NOT summaries" in out
        assert "trust the pages" in out

    def test_it_is_an_addition_not_a_replacement(self):
        out = pipeline.build_script_level_overview("OV", "Scene 1 [X]:\nbody")
        assert out.startswith("OV"), "the summaries were replaced, not extended"
        assert "Scene 1 [X]:" in out


# --------------------------------------------------------------------------
# the wiring — the load-bearing part
# --------------------------------------------------------------------------

class _Recorder:
    """Routes responses by prompt and keeps every (system, user) pair, so the
    tests can ask what each pass was ACTUALLY handed."""

    def __init__(self):
        self.calls = []

    def resolve_model(self):
        return "test-model"

    def chat_json(self, system, user, grammar=None, max_tokens=None, **kw):
        self.calls.append((system, user))
        if "Summarize each" in user or "summarize" in system.lower():
            return {"summaries": [{"scene_number": n, "summary": "Something happens."}
                                  for n in range(1, 40)]}
        if "professional script coverage" in system:
            return {"logline": "A line.", "genre": "drama", "tone": "dark",
                    "one_page_synopsis": "S.", "strengths": ["voice"],
                    "weaknesses": ["pacing"], "comparable_films": [],
                    "recommendation": "consider"}
        return {"findings": [
            {"issue": "An observation", "why_it_matters": "Because.",
             "severity": "medium", "scene_refs": [1], "evidence_quote": None},
        ]}

    def script_level_calls(self):
        return [u for _, u in self.calls if pipeline.CHECKPOINT_HEADER in u]

    def coverage_calls(self):
        return [u for s, u in self.calls if "professional script coverage" in s]


@pytest.fixture(scope="module")
def run():
    doc = parse_fountain(FIXTURE)
    rec = _Recorder()
    return doc, rec, pipeline.analyze(doc, rec, progress_cb=None)


class TestThePassesActuallyReceiveThePages:
    def test_the_four_script_level_passes_get_the_raw_pages(self, run):
        _, rec, _ = run
        assert len(rec.script_level_calls()) == 4, (
            "expected theme/character/structure/scene_function each to receive the "
            "checkpoint pages"
        )

    def test_coverage_does_not_get_them(self, run):
        """§5 item 2 scopes this to the script-level passes. Coverage produces the
        logline and genre from the summaries; widening it would move genre
        detection, which is deliberately not part of this change."""
        _, rec, _ = run
        assert rec.coverage_calls(), "coverage never ran — this check is vacuous"
        for user in rec.coverage_calls():
            assert pipeline.CHECKPOINT_HEADER not in user

    def test_the_pages_really_are_the_pages(self, run):
        _, rec, _ = run
        assert any(RAW_LINE in u for u in rec.script_level_calls())

    def test_the_summaries_are_still_there(self, run):
        """The pages are an addition to the overview, not a replacement: a pass
        that lost the summaries would lose the whole-story view."""
        _, rec, _ = run
        assert any("Something happens." in u for u in rec.script_level_calls())

    def test_script_level_findings_are_tagged_mixed(self, run):
        _, _, result = run
        mixed = [f for f in result.findings
                 if f.get("evidence_source") == pipeline.EVIDENCE_OVERVIEW_AND_CHECKPOINTS]
        assert mixed, "no finding carries the mixed bucket"
        assert {f["category"] for f in mixed} <= set(pipeline.SCRIPT_LEVEL_CATEGORIES)

    def test_no_script_level_finding_is_still_tagged_pure_overview(self, run):
        """The other direction: leaving them on `overview` would understate what
        they read, and would also mean the pages never reached them."""
        _, _, result = run
        stale = [f for f in result.findings
                 if f.get("evidence_source") == pipeline.EVIDENCE_OVERVIEW
                 and f.get("category") in pipeline.SCRIPT_LEVEL_CATEGORIES]
        assert stale == [], "a script-level finding still reports as a pure summary read"

    def test_the_result_records_which_scenes_were_read(self, run):
        doc, _, result = run
        cov = result.stats.get("checkpoint_coverage")
        assert cov and cov["scenes"], "the report cannot name the scenes"
        assert cov["of"] == doc.scene_count
        assert cov["chars"] > 0
        assert all(1 <= n <= doc.scene_count for n in cov["scenes"])

    def test_the_recorded_scenes_are_the_ones_the_block_contains(self, run):
        doc, _, result = run
        scenes = result.stats["checkpoint_coverage"]["scenes"]
        text = pipeline.build_checkpoint_text(doc, scenes)
        for n in scenes:
            assert f"Scene {n} [" in text, f"scene {n} was recorded but not sent"


# --------------------------------------------------------------------------
# the report says it
# --------------------------------------------------------------------------

def _result_with(stats, findings=None):
    from screenplay_analyzer.pipeline import AnalysisResult
    r = AnalysisResult(parse_fountain(FIXTURE))
    r.stats = stats
    r.verification = {"verified": 1, "not_found": 0, "no_quote": 1, "scene_not_found": 0}
    r.findings = findings if findings is not None else []
    return r


class TestTheReportStatesIt:
    def test_it_names_the_middle_bucket_and_the_scenes(self):
        md = render_markdown(_result_with({
            "evidence_depth": {"full_text": 4, "overview": 6,
                               "overview_and_checkpoints": 5, "unknown": 0, "total": 15},
            "checkpoint_coverage": {"scenes": [2, 5, 9], "of": 20, "chars": 4200},
        }))
        assert "Evidence depth" in md
        assert "raw pages of the" in md
        assert "scenes 2, 5, 9" in md

    def test_an_older_report_without_the_bucket_still_renders(self):
        md = render_markdown(_result_with({
            "evidence_depth": {"full_text": 4, "overview": 6, "unknown": 0, "total": 10},
        }))
        assert "Evidence depth" in md
        assert "raw pages" not in md

    def test_it_never_restates_the_mixed_group_as_a_full_read(self):
        md = render_markdown(_result_with({
            "evidence_depth": {"full_text": 0, "overview": 0,
                               "overview_and_checkpoints": 3, "unknown": 0, "total": 3},
            "checkpoint_coverage": {"scenes": [1], "of": 3, "chars": 100},
        }))
        assert "second opinion on structure, not as a reading" in md

    def test_the_scene_list_is_omitted_rather_than_faked(self):
        """A report with the bucket but no recorded scenes must not render
        "scenes " with nothing after it."""
        md = render_markdown(_result_with({
            "evidence_depth": {"full_text": 0, "overview": 0,
                               "overview_and_checkpoints": 2, "unknown": 0, "total": 2},
        }))
        assert "raw pages of the" in md
        assert "scenes )" not in md and "scenes ." not in md


# --------------------------------------------------------------------------
# the app shows it
# --------------------------------------------------------------------------

class TestTheAppShowsIt:
    def _app_js(self):
        import screenplay_studio.webapp_server as ws
        return io.open(ws.__file__.replace("webapp_server.py", "webapp/app.js"),
                       encoding="utf-8").read()

    def test_the_coverage_panel_renders_the_middle_bucket(self):
        js = self._app_js()
        assert "overview_and_checkpoints" in js
        assert "raw pages of the key scenes" in js

    def test_it_names_the_scenes(self):
        js = self._app_js()
        assert "checkpoint_coverage" in js
        assert "cov2.scenes.join" in js

    def test_it_is_guarded_for_reports_without_the_field(self):
        js = self._app_js()
        assert "state.report.stats.evidence_depth" in js
        assert re.search(r"if \(depth && depth\.total\)", js), (
            "an unguarded render would print 'undefined of undefined' on reports "
            "analysed before this field existed"
        )
