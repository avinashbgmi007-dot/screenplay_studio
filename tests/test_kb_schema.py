"""Schema guards for the craft knowledge base.

The KB is content — 263 hand-authored rules across ~26 JSON files — and
nothing validated its *shape*. That made a whole class of defect invisible:
a cross-reference to a rule that does not exist, or a misspelled capability
token, fails silently and only shows up as grounding that quietly does
nothing. It is the same failure class as the `plot` / `plot_thread` mapping
bug and the six `rule_id`s that named no real rule.

`related_rules` and `requires` are declared but not routed today: the
pipeline grounds by `taxonomy_level` (see `screenplay_analyzer/rules_context.py`).
They are validated here anyway, so that whichever consumer arrives first
finds correct data rather than a schema that merely looks complete.
"""

from __future__ import annotations

import pytest

from knowledge_base import KnowledgeBase

# Rules that are referenced by `related_rules` but were never authored. These
# are cross-references to concepts the KB intends to cover — a to-author list,
# not noise — so they are allowed rather than deleted. The assertion is a
# SUBSET check: authoring one of these rules is fine, adding a NEW dangling
# reference is not.
_KNOWN_UNAUTHORED_TARGETS = frozenset({
    ("cognitive_bias_anchoring", "contrast_effect_in_scene"),
    ("cron_external_plot_spur", "cron_third_rail"),
    ("cron_external_plot_spur", "weiland_structure_character_synergy"),
    ("martell_theme_through_characters", "egri_central_thesis"),
    ("power_selective_honesty", "manipulation_flattery"),
    ("profiling_baseline_shift", "nonverbal_cluster_reading"),
    ("profiling_deception_indicators", "nonverbal_incongruence"),
    ("stc_save_the_cat_scene", "hero_must_be_active"),
})

_REQUIRED_TEXT_FIELDS = (
    "id", "name", "taxonomy_level", "category", "definition",
    "detection_signal", "counter_considerations", "severity_default",
    "confidence_tier",
)

_LEVELS = {"high", "medium", "low"}


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase()


def test_every_rule_fills_the_fields_the_prompt_builder_reads(kb):
    """`to_prompt_fragment()` interpolates these directly, so a blank one
    renders a prompt section that says nothing ("Definition: ")."""
    blank = []
    for rule in kb.all():
        for name in _REQUIRED_TEXT_FIELDS:
            if not str(getattr(rule, name, "") or "").strip():
                blank.append(f"{rule.id}.{name}")
    assert not blank, f"rules with blank required fields: {sorted(blank)}"


def test_severity_and_confidence_use_the_declared_vocabulary(kb):
    """`severity_default` now rides the prompt and sets the finding's severity
    (T0.6 / T1.5); an out-of-vocabulary value would flow straight through."""
    bad = [(r.id, r.severity_default) for r in kb.all() if r.severity_default not in _LEVELS]
    assert not bad, f"severity_default outside {sorted(_LEVELS)}: {bad}"
    bad = [(r.id, r.confidence_tier) for r in kb.all() if r.confidence_tier not in _LEVELS]
    assert not bad, f"confidence_tier outside {sorted(_LEVELS)}: {bad}"


def test_every_capability_token_is_declared(kb):
    """`requires` is free text in the JSON. An undeclared token — "knowledge
    graph", "sceneText" — would mis-gate a rule the day anything consumes it."""
    known = set(kb.CAPABILITIES)
    unknown = sorted({t for r in kb.all() for t in (r.requires or []) if t not in known})
    assert not unknown, (
        f"undeclared capability token(s) {unknown}; add to KnowledgeBase.CAPABILITIES "
        f"if intentional (declared: {sorted(known)})"
    )


def test_related_rules_resolve_or_are_documented_as_unauthored(kb):
    """A cross-reference to a rule that does not exist is a broken promise."""
    ids = {r.id for r in kb.all()}
    dangling = {(r.id, target)
                for r in kb.all()
                for target in (r.related_rules or [])
                if target not in ids}
    new = sorted(dangling - _KNOWN_UNAUTHORED_TARGETS)
    assert not new, f"new dangling related_rules references: {new}"


def test_no_rule_relates_to_itself(kb):
    selfish = [r.id for r in kb.all() if r.id in (r.related_rules or [])]
    assert not selfish, f"rules listing themselves in related_rules: {selfish}"


def test_rule_ids_are_unique(kb):
    ids = [r.id for r in kb.all()]
    assert len(ids) == len(set(ids)), "duplicate rule ids"


def test_the_query_api_partitions_the_rule_set(kb):
    """`for_category`, `requiring` and `by_confidence_tier` are the KB's
    declared query surface (review item F9). They are not routed into
    grounding yet, so this is what keeps them honest: each must return exactly
    the rules that match it, and every rule must be reachable through the
    axes it declares.
    """
    everything = kb.all()

    # by_confidence_tier — the three tiers must account for every rule, and
    # stats() now builds its distribution through this same filter.
    by_tier = {t: kb.by_confidence_tier(t) for t in _LEVELS}
    assert sum(len(v) for v in by_tier.values()) == len(everything)
    assert kb.stats()["by_confidence_tier"] == {t: len(v) for t, v in by_tier.items()}

    # requiring — each rule must come back for every capability it declares.
    for rule in everything:
        for capability in rule.requires or []:
            assert rule in kb.requiring(capability), (
                f"{rule.id} declares {capability!r} but requiring() omits it"
            )

    # for_category — likewise for the fine-grained category tag.
    for rule in everything:
        assert rule in kb.for_category(rule.category), (
            f"{rule.id} is not returned by for_category({rule.category!r})"
        )
