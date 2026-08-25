"""
Principles Engine — Chekhov's Gun and dialogue-promise checking.

Two-stage pattern (revised — see note below):
  1. Find candidates — DETERMINISTIC, done already by Piece 1's
     knowledge_graph.py (prop_candidates, promise_candidates). Free, no
     model call, but has no idea which candidates actually matter.
  2. Judge significance — was this candidate actually given narrative
     weight, or is it just ordinary continuity, and if significant, was it
     paid off? (one model call per candidate, using the real mention text
     from the knowledge graph, not a paraphrase)

Diagnosis only — deliberately no "suggest a resolution" stage. An earlier
version of this engine combined judgment with a fix-suggestion in the same
call, which violated the intended diagnose/prescribe split: Piece 2's job
is to say what's wrong and why; proposing how to fix it belongs in Piece 3,
generated conversationally, only when and if the writer actually asks for
it. See SPEC_entity_tracking_and_diagnose_prescribe.md Part 1 for the full
reasoning behind this correction.

This is designed to extend to other candidate types beyond Chekhov's Gun
(the knowledge graph's timeline/character-trait data could feed the same
pattern for continuity checks) without restructuring — see
run_principles_engine's docstring.
"""

from __future__ import annotations

from screenplay_parser.knowledge_graph import KnowledgeGraph

from . import prompts
from .grammar import principle_judgment_grammar
from .llm_client import LlamaServerClient, LlamaServerError

# candidates below this many mentions or with an implausibly generic name
# aren't worth spending a model call on — cheap pre-filter before stage 2
MIN_PROP_NAME_LENGTH = 3


def _judge_candidate(
    client: LlamaServerClient,
    rules_fragment: str,
    candidate_kind: str,
    candidate_name: str,
    mention_contexts: list[dict],
    total_scenes: int,
    language: str = "eng",
) -> dict:
    grammar = principle_judgment_grammar()
    system, user = prompts.principle_judgment_prompt(
        candidate_kind, candidate_name, mention_contexts, rules_fragment, total_scenes, language=language
    )
    return client.chat_json(system, user, grammar=grammar, max_tokens=500)


def _finding_from_judgment(
    candidate_kind: str, candidate_name: str, scenes_mentioned: list[int], judgment: dict, rule_id: str
) -> dict | None:
    """Only emit a finding when it's actually actionable: significant AND
    not paid off. A significant-and-paid-off candidate, or a not-significant
    one, isn't something the writer needs to act on.

    Diagnosis only — no suggested_resolution field. Piece 2 explains what's
    wrong and why; proposing how to fix it is Piece 3's job, and only when
    the writer actually asks for it."""
    if not isinstance(judgment, dict):
        return None  # model returned a non-object (e.g. bare array) — not actionable
    if not judgment.get("significant") or judgment.get("paid_off"):
        return None

    kind_label = "Recurring detail never paid off" if candidate_kind == "recurring_object" else "Promise never fulfilled"

    return {
        "category": "plot_thread",
        "rule_id": rule_id,
        "issue": f'{kind_label}: "{candidate_name}"',
        "why_it_matters": judgment.get("reasoning", ""),
        "severity": "medium",
        "scene_refs": scenes_mentioned,
        "evidence_quote": None,  # candidate mentions are cited by scene_refs; verifier can still check scene existence
    }


def run_principles_engine(
    kg: KnowledgeGraph,
    client: LlamaServerClient,
    rules_ctx,
    total_scenes: int,
    max_candidates: int = 15,
    language: str = "eng",
) -> tuple[list[dict], list[str]]:
    """
    Returns (findings, errors). Caps at max_candidates total (props +
    promises combined) to keep call count bounded on scripts with many
    recurring objects — takes the most-mentioned candidates first, since
    mention frequency is a reasonable proxy for narrative emphasis worth
    spending a judgment call on.
    """
    findings = []
    errors = []

    rules_fragment = rules_ctx.prompt_fragment_for_category("plot_thread") if hasattr(rules_ctx, "prompt_fragment_for_category") else ""

    prop_candidates = sorted(kg.prop_candidates, key=lambda p: -p.mention_count)[:max_candidates]
    remaining_budget = max_candidates - len(prop_candidates)
    promise_candidates = kg.promise_candidates[:max(0, remaining_budget)]

    for prop in prop_candidates:
        try:
            judgment = _judge_candidate(
                client, rules_fragment, "recurring_object", prop.name,
                prop.mention_texts, total_scenes, language,
            )
            finding = _finding_from_judgment("recurring_object", prop.name, prop.scenes_mentioned, judgment, "chekhovs_gun")
            if finding:
                findings.append(finding)
        except LlamaServerError as e:
            errors.append(f"Principles engine judgment failed for prop '{prop.name}': {e}")

    for promise in promise_candidates:
        try:
            mention_contexts = [{"scene": promise.scene_number, "text": promise.text}]
            judgment = _judge_candidate(
                client, rules_fragment, "dialogue_promise", promise.text,
                mention_contexts, total_scenes, language,
            )
            finding = _finding_from_judgment(
                "dialogue_promise", promise.text, [promise.scene_number], judgment, "setup_payoff_general"
            )
            if finding:
                findings.append(finding)
        except LlamaServerError as e:
            errors.append(f"Principles engine judgment failed for promise in scene {promise.scene_number}: {e}")

    return findings, errors
