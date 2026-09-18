"""The same defect filed under related rules becomes one finding (§5 item 3).

Measured on a real report (`gun_pen_2`, scene 2), one on-the-nose exposition problem
arrived as THREE findings under `On-the-Nose Dialogue vs. Subtext`,
`Say the Opposite` and `Exposition as Ammunition` — while a fourth dialogue finding
in the same scene, `Distinct Character Voice`, is a genuinely different defect.

Two measured facts shaped the implementation, and both rule out the obvious
approach. They are pinned here because each cost a wrong implementation:

1. **Text similarity finds nothing.** Across all 36 findings no pair reached 0.19
   similarity, so a text-based dedup is a no-op. What separates the trio from the
   voice finding is the knowledge base.
2. **The transitive closure of `related_rules` is far too coarse.** It collapses 271
   rules into clusters of up to 61, and puts `distinct_character_voice` in the SAME
   cluster as `on_the_nose_vs_subtext`. The first implementation used it and merged
   36 findings down to 10, swallowing the voice finding. The merge predicate is
   therefore a DIRECT edge, evaluated only between findings present and in one scene.
"""

import copy

import pytest

from screenplay_analyzer import pipeline
from screenplay_analyzer.dedupe import (
    SEVERITY_ORDER, _by_name, dedupe_related_findings, directly_related, related_map,
    resolve_rule_key,
)


@pytest.fixture(scope="module")
def kb():
    from knowledge_base import KnowledgeBase
    return KnowledgeBase()


# The real rule titles, as the model-driven pass writes them into `rule_id`.
ON_THE_NOSE = "On-the-Nose Dialogue vs. Subtext"
SAY_OPPOSITE = "Say the Opposite (Subtext Through Contradiction)"
EXPOSITION = "Exposition as Ammunition, Not Data Dump"
VOICE = "Distinct Character Voice"


def _f(rule, scene, severity="medium", issue="an issue"):
    return {"category": "dialogue", "rule_id": rule, "severity": severity,
            "issue": issue, "why_it_matters": "because", "scene_refs": [scene]}


# --------------------------------------------------------------------------
# the relation map
# --------------------------------------------------------------------------

class TestTheRelationMap:
    def test_it_is_symmetric(self, kb):
        """The KB writes related-ness one way (`exposition_as_ammunition ->
        [on_the_nose_vs_subtext]` with no back-reference). A one-way read would
        make the merge depend on which rule happened to fire."""
        adj = related_map(kb)
        for rule, neighbours in adj.items():
            for n in neighbours:
                assert rule in adj.get(n, ()), f"{rule} -> {n} is not mirrored"

    def test_a_direct_edge_is_detected_both_ways(self, kb):
        adj = related_map(kb)
        assert directly_related(adj, "exposition_as_ammunition", "on_the_nose_vs_subtext")
        assert directly_related(adj, "on_the_nose_vs_subtext", "exposition_as_ammunition")

    def test_a_rule_is_not_related_to_itself(self, kb):
        """Otherwise every finding would merge with every other finding sharing
        its rule, regardless of scene."""
        assert not directly_related(related_map(kb), "exposition_as_ammunition",
                                    "exposition_as_ammunition")

    def test_unrelated_rules_are_not_linked(self, kb):
        """The pair that must stay apart: the voice rule has no direct edge to any
        of the exposition trio, even though the KB's CLOSURE puts them together."""
        adj = related_map(kb)
        for other in ("on_the_nose_vs_subtext", "exposition_as_ammunition",
                      "martell_say_the_opposite"):
            assert not directly_related(adj, "distinct_character_voice", other)

    def test_the_closure_would_have_been_too_coarse(self, kb):
        """Documents WHY the predicate is a direct edge rather than a closure: the
        closure does put the voice rule and the exposition rule together, which is
        exactly the merge that must not happen."""
        adj = related_map(kb)

        def component(start):
            seen, frontier = {start}, [start]
            while frontier:
                for nxt in adj.get(frontier.pop(), ()):
                    if nxt not in seen:
                        seen.add(nxt)
                        frontier.append(nxt)
            return seen

        blob = component("distinct_character_voice")
        assert "on_the_nose_vs_subtext" in blob, "the closure no longer conflates them"
        assert len(blob) > 20, (
            "the closure is expected to be huge; if the KB got tighter this "
            "justification should be revisited"
        )

    def test_an_unknown_rule_reference_resolves_to_none(self, kb):
        adj = related_map(kb)
        assert resolve_rule_key("no_such_rule", {}, set(adj)) is None
        assert resolve_rule_key(None, {}, set(adj)) is None
        assert resolve_rule_key("", {}, set(adj)) is None


class TestRuleReferenceResolution:
    """The passes disagree about what goes in `rule_id` — a snake_case id from the
    deterministic ones, a display NAME from the model-driven ones. Both must work
    or half the report is invisible to the dedup."""

    def test_a_snake_case_id_resolves(self, kb):
        adj = related_map(kb)
        assert resolve_rule_key("on_the_nose_vs_subtext", {}, set(adj)) == "on_the_nose_vs_subtext"

    def test_a_display_name_resolves_to_its_id(self, kb):
        adj = related_map(kb)
        assert resolve_rule_key(ON_THE_NOSE, _by_name(kb), set(adj)) == "on_the_nose_vs_subtext"

    def test_name_matching_is_case_insensitive(self, kb):
        adj = related_map(kb)
        assert resolve_rule_key(ON_THE_NOSE.upper(), _by_name(kb), set(adj)) == "on_the_nose_vs_subtext"

    def test_a_non_kb_id_is_left_unresolved(self, kb):
        """`unmarked_time_flip` is emitted by the continuity pass but is NOT a KB
        rule id, so nothing can relate it to anything. It must resolve to None
        rather than raise — the dedup simply has no opinion about it."""
        adj = related_map(kb)
        assert resolve_rule_key("unmarked_time_flip", _by_name(kb), set(adj)) is None


# --------------------------------------------------------------------------
# the merge
# --------------------------------------------------------------------------

class TestTheMerge:
    def test_the_exposition_trio_collapses_to_one(self, kb):
        findings = [_f(ON_THE_NOSE, 2), _f(SAY_OPPOSITE, 2), _f(EXPOSITION, 2)]
        out = dedupe_related_findings(findings, kb)
        assert len(out) == 1
        assert sorted(out[0]["merged_rule_ids"]) == sorted([SAY_OPPOSITE, EXPOSITION])

    def test_the_voice_finding_is_NOT_swallowed(self, kb):
        """The load-bearing case. A closure-based merge takes this one too — the
        first implementation did, and the real report caught it."""
        findings = [_f(VOICE, 2), _f(ON_THE_NOSE, 2), _f(SAY_OPPOSITE, 2), _f(EXPOSITION, 2)]
        out = dedupe_related_findings(findings, kb)
        assert len(out) == 2
        rules = {f["rule_id"] for f in out}
        assert VOICE in rules, "a genuinely different defect was merged away"
        assert ON_THE_NOSE in rules

    def test_the_same_defect_in_two_scenes_stays_two_findings(self, kb):
        """Two separate fixes for two separate pages. This is the Pain_3 case: the
        same rule firing at scenes 13 and 17 is not a duplicate."""
        findings = [_f(ON_THE_NOSE, 2), _f(ON_THE_NOSE, 3)]
        assert len(dedupe_related_findings(findings, kb)) == 2

    def test_the_same_rule_twice_in_one_scene_merges(self, kb):
        findings = [_f(ON_THE_NOSE, 2, issue="first"), _f(ON_THE_NOSE, 2, issue="second")]
        out = dedupe_related_findings(findings, kb)
        assert len(out) == 1
        assert out[0]["merged_rule_ids"] == [ON_THE_NOSE]

    def test_a_finding_with_no_scene_is_never_merged(self, kb):
        """Script-level findings carry no scene_refs; merging them by rule alone
        would combine observations from different parts of the script."""
        findings = [
            {"category": "theme", "rule_id": ON_THE_NOSE, "severity": "medium",
             "issue": "a", "scene_refs": []},
            {"category": "theme", "rule_id": SAY_OPPOSITE, "severity": "medium",
             "issue": "b", "scene_refs": []},
        ]
        assert len(dedupe_related_findings(findings, kb)) == 2

    def test_a_chain_of_direct_edges_merges(self, kb):
        """on_the_nose links to both neighbours directly, even though the two
        neighbours are not linked to each other."""
        findings = [_f(ON_THE_NOSE, 1), _f(SAY_OPPOSITE, 1), _f(EXPOSITION, 1)]
        assert len(dedupe_related_findings(findings, kb)) == 1

    def test_unrelated_rules_in_the_same_scene_do_not_merge(self, kb):
        findings = [_f(VOICE, 2), _f(ON_THE_NOSE, 2)]
        assert len(dedupe_related_findings(findings, kb)) == 2


class TestWhatTheSurvivorKeeps:
    def test_the_highest_severity_survives(self, kb):
        findings = [_f(ON_THE_NOSE, 2, severity="low"),
                    _f(SAY_OPPOSITE, 2, severity="high")]
        out = dedupe_related_findings(findings, kb)
        assert out[0]["severity"] == "high"
        assert out[0]["rule_id"] == SAY_OPPOSITE

    def test_a_tie_keeps_the_earliest_for_stable_order(self, kb):
        findings = [_f(ON_THE_NOSE, 2, issue="first"), _f(SAY_OPPOSITE, 2, issue="second")]
        assert dedupe_related_findings(findings, kb)[0]["issue"] == "first"

    def test_the_scene_refs_are_unioned(self, kb):
        a = _f(ON_THE_NOSE, 2)
        b = _f(SAY_OPPOSITE, 3)
        b["scene_refs"] = [2, 3]   # overlap on 2 is what allows the merge
        out = dedupe_related_findings([a, b], kb)
        assert out[0]["scene_refs"] == [2, 3]

    def test_it_states_what_it_absorbed_on_the_finding_itself(self, kb):
        """A writer reading one card must be able to see that other rules agreed —
        a side field nobody renders is not disclosure."""
        findings = [_f(ON_THE_NOSE, 2), _f(SAY_OPPOSITE, 2), _f(EXPOSITION, 2)]
        why = dedupe_related_findings(findings, kb)[0]["why_it_matters"]
        assert "Also flagged under" in why
        assert SAY_OPPOSITE in why and EXPOSITION in why

    def test_it_records_the_absorbed_rules_as_data_too(self, kb):
        findings = [_f(ON_THE_NOSE, 2), _f(SAY_OPPOSITE, 2)]
        assert dedupe_related_findings(findings, kb)[0]["merged_rule_ids"] == [SAY_OPPOSITE]

    def test_it_never_mutates_the_input(self, kb):
        findings = [_f(ON_THE_NOSE, 2), _f(SAY_OPPOSITE, 2)]
        snapshot = copy.deepcopy(findings)
        dedupe_related_findings(findings, kb)
        assert findings == snapshot, "the caller's findings were modified in place"

    def test_nothing_is_ever_dropped_silently(self, kb):
        """Every merged-away finding is named by the survivor. This is the
        'flag, don't silently drop' contract the verifier uses for findings."""
        findings = [_f(ON_THE_NOSE, 2), _f(SAY_OPPOSITE, 2), _f(EXPOSITION, 2)]
        out = dedupe_related_findings(findings, kb)
        accounted = {out[0]["rule_id"]} | set(out[0]["merged_rule_ids"])
        assert accounted == {ON_THE_NOSE, SAY_OPPOSITE, EXPOSITION}


class TestDegradation:
    def test_no_kb_available_leaves_the_findings_alone(self, monkeypatch):
        """A dedup that cannot read the relation map must not guess at what is
        related. (`kb=None` means "load the default KB", so unavailability is
        simulated by breaking the import, which is the real failure mode.)"""
        import sys
        findings = [_f(ON_THE_NOSE, 2), _f(SAY_OPPOSITE, 2)]
        monkeypatch.setitem(sys.modules, "knowledge_base", None)
        assert dedupe_related_findings(findings, kb=None) == findings

    def test_an_empty_list_is_safe(self, kb):
        assert dedupe_related_findings([], kb) == []

    def test_a_finding_with_no_rule_is_left_alone(self, kb):
        findings = [{"category": "dialogue", "issue": "no rule", "scene_refs": [1]},
                    {"category": "dialogue", "issue": "also none", "scene_refs": [1]}]
        assert len(dedupe_related_findings(findings, kb)) == 2

    def test_it_is_idempotent(self, kb):
        """Running the dedup twice must not merge a second time — the survivor's
        own rule_id is one of the merged set, so a naive re-run could chain."""
        findings = [_f(ON_THE_NOSE, 2), _f(SAY_OPPOSITE, 2), _f(EXPOSITION, 2)]
        once = dedupe_related_findings(findings, kb)
        twice = dedupe_related_findings(once, kb)
        assert [f["rule_id"] for f in twice] == [f["rule_id"] for f in once]

    def test_severity_order_is_declared(self):
        assert SEVERITY_ORDER["high"] < SEVERITY_ORDER["medium"] < SEVERITY_ORDER["low"]


# --------------------------------------------------------------------------
# the pipeline runs it
# --------------------------------------------------------------------------

class TestThePipelineRunsIt:
    def test_the_pipeline_calls_the_dedup(self, monkeypatch):
        """Wiring guard: the module can be perfect and never run."""
        called = {}
        real = pipeline.dedupe_related_findings if hasattr(pipeline, "dedupe_related_findings") else None

        import screenplay_analyzer.dedupe as dedupe_mod
        original = dedupe_mod.dedupe_related_findings

        def spy(findings, kb=None):
            called["yes"] = True
            return original(findings, kb)

        monkeypatch.setattr(dedupe_mod, "dedupe_related_findings", spy)

        from screenplay_parser import parse_fountain
        import os
        fixture = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "fixtures", "pain_tenglish.fountain")

        class C:
            def resolve_model(self):
                return "t"

            def chat_json(self, system, user, grammar=None, max_tokens=None, **kw):
                if "summarize" in system.lower():
                    return {"summaries": [{"scene_number": n, "summary": "s"} for n in range(1, 8)]}
                return {"findings": []}

        pipeline.analyze(parse_fountain(fixture), C(), run_categories=("dialogue",),
                         progress_cb=None)
        assert called.get("yes"), "the pipeline never invoked the cross-rule dedup"

    def test_a_dedup_failure_never_fails_the_run(self, monkeypatch):
        """A dedup is a tidy-up, not a dependency — if it blows up the report must
        still be produced, with the error recorded."""
        import screenplay_analyzer.dedupe as dedupe_mod

        def boom(findings, kb=None):
            raise RuntimeError("no KB")

        monkeypatch.setattr(dedupe_mod, "dedupe_related_findings", boom)

        from screenplay_parser import parse_fountain
        import os
        fixture = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "fixtures", "pain_tenglish.fountain")

        class C:
            def resolve_model(self):
                return "t"

            def chat_json(self, system, user, grammar=None, max_tokens=None, **kw):
                return {"findings": []}

        result = pipeline.analyze(parse_fountain(fixture), C(),
                                  run_categories=("dialogue",), progress_cb=None)
        assert any("dedup skipped" in e for e in result.errors), (
            "the failure was swallowed without a trace"
        )
