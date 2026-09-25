"""BE-2 (audit 2026-09-24) — an empty knowledge base must be LOUD.

`KnowledgeBase._load()` globs `rules/*.json` and yields `{}` when the glob finds
nothing: no exception, no warning, no log line. `pipeline.analyze()` handled "the
package is absent" (ImportError) but not "the package is present and empty" — so
every finding silently lost its "grounded in rule X" attribution and the report
looked exactly like a healthy one. It is the repo's own recorded worst case
(`rules_context.py`'s header documents the same class of bug from the "plot" vs
"plot_thread" key).

The only guard was build-time (`test_packaging_data_files.py` requires >= 26 rule
files inside the wheel), which does not cover a permissions problem, a path
refactor or a renamed file — all of which reach the *runtime* path.

The guard is deliberately non-fatal: the pipeline still runs and the writer is
told, because an ungrounded report the writer knows is ungrounded is worth more
than a crashed run.
"""
from __future__ import annotations

import pytest

from screenplay_analyzer.pipeline import _empty_kb_message, _NullRulesContext
from screenplay_analyzer.rules_context import RulesContext

SHIPPED_RULE_FLOOR = 263


@pytest.fixture
def empty_kb_ctx(tmp_path):
    """A real KnowledgeBase pointed at a directory that holds no rules."""
    from knowledge_base import KnowledgeBase
    empty = tmp_path / "rules"
    empty.mkdir()
    return RulesContext(kb=KnowledgeBase(rules_dir=str(empty)))


class TestTheCountIsReal:
    def test_a_directory_with_no_rules_reports_zero(self, empty_kb_ctx):
        assert empty_kb_ctx.rule_count() == 0

    def test_a_directory_that_does_not_exist_also_reports_zero(self, tmp_path):
        """`rules_dir` need not exist for the glob to find nothing — and a wrong
        path is the most likely runtime cause of this state."""
        from knowledge_base import KnowledgeBase
        ctx = RulesContext(kb=KnowledgeBase(rules_dir=str(tmp_path / "nope")))
        assert ctx.rule_count() == 0

    def test_a_kb_that_cannot_be_enumerated_reports_none_not_zero(self):
        """A transient read error on a FULL knowledge base must not be reported as
        an empty one. "Cannot count" and "counted zero" are different facts, and
        collapsing them raises a false alarm on a healthy install."""
        class _Broken:
            def all(self):
                raise OSError("transient read error")

        ctx = RulesContext(kb=_Broken())
        assert ctx.rule_count() is None, "a failure to count was reported as zero"
        assert _empty_kb_message(ctx) is None

    def test_the_shipped_knowledge_base_reports_every_rule(self):
        ctx = RulesContext()
        assert ctx.rule_count() >= SHIPPED_RULE_FLOOR, (
            f"the shipped KB reports only {ctx.rule_count()} rules — that much "
            "grounding is missing from every report")


class TestTheMessageIsRaised:
    def test_an_empty_kb_produces_a_message_naming_the_directory(self, empty_kb_ctx, tmp_path):
        msg = _empty_kb_message(empty_kb_ctx)
        assert msg, "an empty knowledge base produced no message — the silent path"
        assert "ZERO rules" in msg
        assert str(tmp_path) in msg, "the message must name where it looked"

    def test_a_healthy_kb_produces_no_message(self):
        assert _empty_kb_message(RulesContext()) is None

    def test_the_null_fallback_does_not_double_report(self):
        """`_NullRulesContext` already emits its own, more specific reason
        ("knowledge_base not found"); a second message would be noise."""
        assert _empty_kb_message(_NullRulesContext()) is None

    def test_a_stand_in_that_cannot_count_is_left_alone(self):
        class _Opaque:
            def prompt_fragment_for_category(self, category):
                return ""

        assert _empty_kb_message(_Opaque()) is None


class TestAnalyzeSurfacesIt:
    def test_the_error_reaches_result_errors(self, monkeypatch, tmp_path, sample_fountain):
        """The end-to-end assertion: a zero-rule KB must appear in
        `result.errors` — that list is what the report and the UI read, so it is
        the difference between "degraded" and "silently degraded"."""
        from knowledge_base import KnowledgeBase
        from screenplay_analyzer import pipeline
        from screenplay_parser import parse_fountain

        empty = tmp_path / "rules"
        empty.mkdir()
        real_rules_context = RulesContext
        monkeypatch.setattr(
            pipeline, "RulesContext",
            lambda: real_rules_context(kb=KnowledgeBase(rules_dir=str(empty))))

        class _Client:
            def resolve_model(self):
                return "test-model"

            def chat_json(self, *args, **kwargs):
                return {"findings": []}

        result = pipeline.analyze(parse_fountain(sample_fountain), _Client(),
                                  run_categories=(), progress_cb=None)
        assert any("ZERO rules" in e for e in result.errors), (
            f"an ungrounded run reported no error: {result.errors}")
