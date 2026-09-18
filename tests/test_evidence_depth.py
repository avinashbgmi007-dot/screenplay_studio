"""The report states how much of it read the pages (Wave 4 / §5 item 4).

The script-level passes judge from the MODEL-WRITTEN scene summaries, never the raw
pages — a deliberate trade to fit the context window, and the single biggest honest
limitation of the analysis. §2 called it "the summary-telephone ceiling": a large
share of findings are about a *description* of the script rather than the script.

Until now the writer could not see the trade's SIZE. The report said "expected for
theme/character/structure/scene-function findings, which reason from scene
summaries" — a caveat in prose. "18 of 30 came from a summary" is a scope.

The classification is recorded WHERE EACH PASS RUNS, not inferred from the finding's
category, and the tests below hold that line: `pacing` emits its drag findings under
category "structure", so a category-based rule would report every pace drag — which
read the parsed pages directly — as a summary-derived judgement.
"""

import io
import os
import re

import pytest

from screenplay_analyzer import pipeline
from screenplay_analyzer.pipeline import (
    EVIDENCE_FULL_TEXT, EVIDENCE_OVERVIEW, _tag_evidence, evidence_depth,
)
from screenplay_analyzer.report import render_markdown

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "pain_tenglish.fountain")


# --------------------------------------------------------------------------
# the counter itself
# --------------------------------------------------------------------------

class TestEvidenceDepth:
    def test_it_counts_both_sides(self):
        findings = [
            {"evidence_source": EVIDENCE_FULL_TEXT},
            {"evidence_source": EVIDENCE_OVERVIEW},
            {"evidence_source": EVIDENCE_OVERVIEW},
        ]
        assert evidence_depth(findings) == {
            "full_text": 1, "overview": 2, "unknown": 0, "total": 3,
        }

    def test_an_unattributed_finding_is_counted_as_unknown(self):
        """Not folded into either side: a pass that forgot to declare its source
        must not silently read as full-text, which is the flattering direction."""
        findings = [{"evidence_source": EVIDENCE_FULL_TEXT}, {}, {"evidence_source": "??"}]
        depth = evidence_depth(findings)
        assert depth["unknown"] == 2
        assert depth["full_text"] == 1

    def test_an_empty_report_is_all_zeros(self):
        assert evidence_depth([]) == {"full_text": 0, "overview": 0, "unknown": 0, "total": 0}

    def test_tagging_stamps_every_finding(self):
        findings = [{}, {"category": "x"}]
        assert _tag_evidence(findings, EVIDENCE_OVERVIEW) is findings
        assert all(f["evidence_source"] == EVIDENCE_OVERVIEW for f in findings)

    def test_tagging_does_not_drop_existing_keys(self):
        findings = [{"category": "structure", "issue": "i"}]
        _tag_evidence(findings, EVIDENCE_FULL_TEXT)
        assert findings[0]["category"] == "structure" and findings[0]["issue"] == "i"


# --------------------------------------------------------------------------
# every pass declares what it read
# --------------------------------------------------------------------------

class TestEveryPassDeclaresItsSource:
    """The real guard. A new pass that extends all_findings without declaring its
    source would land in `unknown` — visible, but only after someone reads the
    report. This catches it at the source instead."""

    def _src(self):
        return io.open(pipeline.__file__, encoding="utf-8").read()

    def test_every_extend_is_tagged(self):
        untagged = re.findall(r"all_findings\.extend\((?!_tag_evidence)", self._src())
        assert untagged == [], (
            f"{len(untagged)} pass(es) extend all_findings without declaring an "
            f"evidence source — they would report as 'unknown'"
        )

    def test_there_is_more_than_one_pass_so_the_guard_is_meaningful(self):
        assert self._src().count("all_findings.extend(_tag_evidence(") >= 8

    def test_the_mixed_category_is_split_by_pass_not_by_category(self):
        """`pacing` files its drag findings under category "structure", the same
        category the script-level pass uses for a summary-derived judgement. The
        two must be tagged differently, or the count lies about the pace drags."""
        src = self._src()
        assert "drag_findings(result.pacing), EVIDENCE_FULL_TEXT)" in src
        assert "run_script_level_category(fn, client, rules_fragment" in src
        assert re.search(
            r"_tag_evidence\(\s*run_script_level_category\(.*?\),\s*EVIDENCE_OVERVIEW\)",
            src, re.S,
        ), "the script-level categories must be tagged overview"

    def test_the_summary_based_passes_are_tagged_overview(self):
        src = self._src()
        assert "dangling_findings(ledger, existing_plot, rules_ctx=rules_ctx), EVIDENCE_OVERVIEW)" in src
        assert "genre_findings, EVIDENCE_OVERVIEW)" in src

    def test_the_document_reading_passes_are_tagged_full_text(self):
        src = self._src()
        for call in ("voice_findings", "subtext_findings", "idiolect_findings",
                     "continuity_findings", "dialogue_findings", "principle_findings"):
            assert f"{call}, EVIDENCE_FULL_TEXT)" in src, f"{call} lost its source tag"


# --------------------------------------------------------------------------
# the pipeline stamps every finding it emits
# --------------------------------------------------------------------------

class _Client:
    """Routes responses by prompt, so analyze() doesn't depend on call counts."""

    def resolve_model(self):
        return "test-model"

    def chat_json(self, system, user, grammar=None, max_tokens=None, **kw):
        if "summarize" in system.lower() or "Summarize each" in user:
            return {"summaries": [{"scene_number": n, "summary": "Something happens."}
                                  for n in range(1, 8)]}
        if "coverage" in system.lower():
            return {"logline": "A line.", "genre": "drama", "tone": "dark",
                    "one_page_synopsis": "S.", "strengths": ["voice"], "weaknesses": ["pacing"],
                    "comparable_films": [], "recommendation": "consider"}
        return {"findings": [
            {"issue": "A summary-level observation", "why_it_matters": "Because.",
             "severity": "medium", "scene_refs": [1], "evidence_quote": None},
        ]}


@pytest.fixture(scope="module")
def doc():
    from screenplay_parser import parse_fountain
    return parse_fountain(FIXTURE)


@pytest.fixture(scope="module")
def full_run(doc):
    return pipeline.analyze(doc, _Client(), run_categories=None, progress_cb=None)


class TestAFullRunLeavesNothingUnknown:
    def test_no_finding_is_unattributed(self, full_run):
        depth = (full_run.stats or {}).get("evidence_depth")
        assert depth, "the pipeline did not record an evidence depth"
        assert depth["unknown"] == 0, (
            "a pass emitted findings without declaring an evidence source"
        )
        assert depth["total"] == len(full_run.findings)

    def test_the_two_sides_account_for_every_finding(self, full_run):
        depth = full_run.stats["evidence_depth"]
        assert depth["full_text"] + depth["overview"] == depth["total"]

    def test_both_sides_are_non_empty_on_a_real_script(self, full_run):
        """If one side were always 0 the number would carry no information."""
        depth = full_run.stats["evidence_depth"]
        assert depth["full_text"] > 0, "no pass read the pages?"
        assert depth["overview"] > 0, "no summary-derived findings?"

    def test_every_finding_carries_a_source(self, full_run):
        for f in full_run.findings:
            assert f.get("evidence_source") in (EVIDENCE_FULL_TEXT, EVIDENCE_OVERVIEW)


# --------------------------------------------------------------------------
# the report says it
# --------------------------------------------------------------------------

def _result_with(depth, findings=None):
    from screenplay_analyzer.pipeline import AnalysisResult
    from screenplay_parser import parse_fountain
    r = AnalysisResult(parse_fountain(FIXTURE))
    r.stats = {"evidence_depth": depth} if depth is not None else {}
    r.verification = {"verified": 1, "not_found": 0, "no_quote": 1, "scene_not_found": 0}
    r.findings = findings if findings is not None else []
    return r


class TestTheReportStatesIt:
    def test_the_depth_line_is_rendered(self):
        md = render_markdown(_result_with(
            {"full_text": 12, "overview": 18, "unknown": 0, "total": 30}))
        assert "Evidence depth" in md
        assert "12" in md and "18" in md and "30" in md

    def test_it_names_both_sides_in_the_writer_s_terms(self):
        md = render_markdown(_result_with(
            {"full_text": 1, "overview": 1, "unknown": 0, "total": 2}))
        assert "full script text" in md
        assert "scene summaries" in md
        assert "not as a reading of your pages" in md, "say what it means, not just the count"

    def test_unattributed_findings_are_disclosed_not_hidden(self):
        md = render_markdown(_result_with(
            {"full_text": 1, "overview": 1, "unknown": 3, "total": 5}))
        assert "could not be attributed" in md
        assert "rather than counted as either" in md

    def test_no_depth_no_line(self):
        """An older report with no depth must not render a broken sentence."""
        md = render_markdown(_result_with(None))
        assert "Evidence depth" not in md

    def test_the_older_prose_caveat_survives(self):
        """The depth line ADDS a number; it does not replace the explanation."""
        md = render_markdown(_result_with(
            {"full_text": 1, "overview": 1, "unknown": 0, "total": 2}))
        assert "reason from scene summaries rather than full text" in md


class TestTheServedReportCarriesIt:
    def test_stats_reaches_the_report_json(self, full_run):
        from screenplay_analyzer.report import to_findings_json
        served = to_findings_json(full_run)
        assert served["stats"]["evidence_depth"]["total"] == len(full_run.findings)

    def test_the_depth_is_computed_on_the_filtered_list(self, full_run):
        """The number the writer is shown must describe the findings they are
        shown — not the pre-filter set."""
        depth = full_run.stats["evidence_depth"]
        assert depth["total"] == len(full_run.findings)


# --------------------------------------------------------------------------
# the app shows it too
# --------------------------------------------------------------------------

class TestTheAppShowsIt:
    """The webapp is JS, so these pin the wiring; the rendered result is covered
    by the browser gates. The load-bearing detail is the GUARD: reports analysed
    before this field existed have no `stats.evidence_depth`, and the line must
    not render as "undefined of undefined"."""

    def _app_js(self):
        import screenplay_studio.webapp_server as ws
        return io.open(ws.__file__.replace("webapp_server.py", "webapp/app.js"),
                       encoding="utf-8").read()

    def test_the_coverage_panel_renders_the_depth(self):
        js = self._app_js()
        assert "dock-cov-depth" in js
        assert "from the full script text" in js

    def test_it_is_guarded_against_a_report_without_the_field(self):
        js = self._app_js()
        assert "state.report.stats.evidence_depth" in js
        assert re.search(r"if \(depth && depth\.total\)", js), (
            "an unguarded render would print 'undefined of undefined' on every "
            "report analysed before this field existed"
        )

    def test_the_hover_explains_what_it_means(self):
        js = self._app_js()
        assert "second opinion on structure" in js

    def test_the_style_uses_tokens(self):
        import screenplay_studio.webapp_server as ws
        css = io.open(ws.__file__.replace("webapp_server.py", "webapp/style.css"),
                      encoding="utf-8").read()
        rule = re.search(r"\.dock-cov-depth\s*\{(.*?)\}", css, re.S)
        assert rule, "the .dock-cov-depth rule is missing"
        assert "var(--fs-" in rule.group(1) and "var(--sp-" in rule.group(1)
