"""
Orchestrates the full analysis pipeline:

  1. Deterministic passes (no model): formatting checks, stats — from
     screenplay_parser.stats and formatting_check.
  2. Scene-summary pass (model, chunked): compress every scene to 1-2
     sentences so script-level categories can see the whole story without
     spending context on raw dialogue.
  3. Scene-level pass (model, chunked, full text): dialogue-quality
     findings (on-the-nose, exposition dumps, overwritten action).
  4. Script-level pass (model, once each): theme, character, structure,
     scene-function findings — using the compact scene-summary overview.
  5. Coverage pass (model, once): logline/genre/synopsis/recommendation.
  6. Verification: every model-produced finding with an evidence_quote gets
     checked against the actual parsed scene text.

Returns an AnalysisResult with everything report.py needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from screenplay_parser.models import ScriptDocument
from screenplay_parser import stats as stats_module

from . import prompts
from .grammar import findings_grammar, scene_summary_grammar, coverage_grammar
from .formatting_check import check_formatting
from .verifier import verify_findings, verification_summary
from .llm_client import LlamaServerClient, LlamaServerError
from .rules_context import RulesContext
from .principles_engine import run_principles_engine
from screenplay_parser.knowledge_graph import build_knowledge_graph


class _NullRulesContext:
    """Fallback when the knowledge_base package isn't available alongside this
    one — prompts still work exactly as before, just without KB-grounded rules
    injected. analyze() surfaces a warning when this fallback is used, so a
    silent quality degradation doesn't go unnoticed."""
    def prompt_fragment_for_category(self, category: str) -> str:
        return ""

    def prompt_fragment_for_rule(self, rule_id: str) -> str:
        return ""


def _chunk(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _with_chunk_backoff(chunk: list, call_fn, min_size: int = 1) -> tuple[list, list[str]]:
    """
    Runs call_fn(chunk) -> list of results. On LlamaServerError, if the
    chunk has more than min_size scenes, splits it in half and retries each
    half independently, merging results.

    This is a generic mitigation for any failure mode correlated with
    prompt size — context exhaustion, a misconfigured batch/ubatch
    relationship, KV-cache instability at higher token counts, etc.
    Shrinking the request and retrying is the right generic response
    regardless of which specific cause is in play, and costs nothing extra
    when the original chunk size already works fine (the happy path is a
    single call_fn invocation, same as before this existed).

    Returns (results, errors) — errors is non-empty only for scenes that
    still couldn't succeed even at min_size (a single scene alone was too
    much, or the server is down/broken regardless of size).
    """
    try:
        return call_fn(chunk), []
    except LlamaServerError as e:
        if len(chunk) <= min_size:
            scene_num = chunk[0].get("scene_number", "?") if chunk else "?"
            return [], [f"Scene {scene_num}: {e}"]
        mid = len(chunk) // 2
        left_results, left_errors = _with_chunk_backoff(chunk[:mid], call_fn, min_size)
        right_results, right_errors = _with_chunk_backoff(chunk[mid:], call_fn, min_size)
        return left_results + right_results, left_errors + right_errors


def _scene_full_text(scene) -> str:
    return "\n".join(e.text for e in scene.elements)


@dataclass
class AnalysisResult:
    doc: ScriptDocument
    findings: list[dict] = field(default_factory=list)
    coverage: dict | None = None
    formatting_findings: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    verification: dict = field(default_factory=dict)
    model_used: str | None = None
    errors: list[str] = field(default_factory=list)


def build_scene_summaries(doc: ScriptDocument, client: LlamaServerClient, chunk_size: int = 6) -> tuple[dict[int, str], list[str]]:
    summaries: dict[int, str] = {}
    errors: list[str] = []
    grammar = scene_summary_grammar()
    scene_dicts = [
        {
            "scene_number": s.scene_number,
            "heading_raw": s.heading_raw,
            "characters_present": s.characters_present,
            "full_text": _scene_full_text(s),
        }
        for s in doc.scenes
    ]

    def call(chunk_):
        system, user = prompts.scene_summary_prompt(chunk_)
        result = client.chat_json(system, user, grammar=grammar, max_tokens=800)
        return result.get("summaries", [])

    for chunk in _chunk(scene_dicts, chunk_size):
        items, errs = _with_chunk_backoff(chunk, call)
        errors.extend(errs)
        for item in items:
            try:
                summaries[int(item["scene_number"])] = item["summary"]
            except (KeyError, ValueError, TypeError):
                continue
    return summaries, errors


def build_scene_overview_text(doc: ScriptDocument, summaries: dict[int, str]) -> str:
    lines = []
    for s in doc.scenes:
        summary = summaries.get(s.scene_number, "(no summary available)")
        chars = ", ".join(s.characters_present) or "none"
        page = f" p.{s.page_start}" if s.page_start else ""
        lines.append(f"Scene {s.scene_number} [{s.heading_raw}{page}] ({chars}): {summary}")
    return "\n".join(lines)


def run_dialogue_analysis(doc: ScriptDocument, client: LlamaServerClient, rules_ctx, chunk_size: int = 3) -> tuple[list[dict], list[str]]:
    findings = []
    errors: list[str] = []
    grammar = findings_grammar()
    rules_fragment = rules_ctx.prompt_fragment_for_category("dialogue")
    chekhov_fragment = rules_ctx.prompt_fragment_for_rule("chekhovs_gun")
    scene_dicts = [
        {"scene_number": s.scene_number, "heading_raw": s.heading_raw, "full_text": _scene_full_text(s)}
        for s in doc.scenes
    ]

    def call(chunk_):
        system, user = prompts.dialogue_analysis_prompt(chunk_, rules_fragment=rules_fragment, chekhov_fragment=chekhov_fragment)
        result = client.chat_json(system, user, grammar=grammar, max_tokens=1200)
        return result.get("findings", [])

    for chunk in _chunk(scene_dicts, chunk_size):
        items, errs = _with_chunk_backoff(chunk, call)
        findings.extend(items)
        errors.extend(errs)
    return findings, errors


def run_script_level_category(prompt_fn, client: LlamaServerClient, rules_fragment: str, *args) -> list[dict]:
    grammar = findings_grammar()
    system, user = prompt_fn(*args, rules_fragment=rules_fragment)
    result = client.chat_json(system, user, grammar=grammar, max_tokens=1500)
    return result.get("findings", [])


def run_coverage(doc: ScriptDocument, overview: str, client: LlamaServerClient) -> dict:
    grammar = coverage_grammar()
    system, user = prompts.coverage_prompt(overview, doc.title, doc.author)
    return client.chat_json(system, user, grammar=grammar, max_tokens=900)


def analyze(
    doc: ScriptDocument,
    client: LlamaServerClient,
    scene_chunk_size: int = 3,
    summary_chunk_size: int = 6,
    run_categories: tuple[str, ...] = ("dialogue", "theme", "character", "structure", "scene_function", "principles", "coverage"),
) -> AnalysisResult:
    result = AnalysisResult(doc=doc)

    try:
        rules_ctx = RulesContext()
    except ImportError:
        rules_ctx = _NullRulesContext()
        result.errors.append(
            "Knowledge base not found alongside this package — analysis is running "
            "without craft-principle grounding. Copy the knowledge_base/ folder next "
            "to screenplay_analyzer/ to restore it."
        )

    # 1. deterministic passes — always run, never fail the whole pipeline
    result.formatting_findings = check_formatting(doc)
    result.stats = stats_module.full_stats_report(doc)

    if not doc.scenes:
        result.errors.append("Document has no parsed scenes — skipping model-based analysis.")
        return result

    try:
        result.model_used = client.resolve_model()
    except LlamaServerError as e:
        result.errors.append(f"Could not reach model server: {e}")
        return result

    # 2. scene summaries (needed for every script-level category + coverage)
    needs_summaries = any(c in run_categories for c in ("theme", "character", "structure", "scene_function", "coverage"))
    overview = ""
    if needs_summaries:
        try:
            summaries, summary_errors = build_scene_summaries(doc, client, chunk_size=summary_chunk_size)
            overview = build_scene_overview_text(doc, summaries)
            if summary_errors:
                result.errors.append(
                    f"Scene summarization had {len(summary_errors)} unresolved failure(s) even after "
                    f"reducing batch size: {'; '.join(summary_errors[:3])}"
                    + (f" (+{len(summary_errors) - 3} more)" if len(summary_errors) > 3 else "")
                )
        except LlamaServerError as e:
            result.errors.append(f"Scene summarization failed: {e}")

    all_findings = []

    # 3. scene-level dialogue analysis
    if "dialogue" in run_categories:
        try:
            dialogue_findings, dialogue_errors = run_dialogue_analysis(doc, client, rules_ctx, chunk_size=scene_chunk_size)
            all_findings.extend(dialogue_findings)
            if dialogue_errors:
                result.errors.append(
                    f"Dialogue analysis had {len(dialogue_errors)} unresolved failure(s) even after "
                    f"reducing batch size: {'; '.join(dialogue_errors[:3])}"
                    + (f" (+{len(dialogue_errors) - 3} more)" if len(dialogue_errors) > 3 else "")
                )
        except LlamaServerError as e:
            result.errors.append(f"Dialogue analysis failed: {e}")

    # 4. script-level categories
    category_prompts = {
        "theme": (prompts.theme_analysis_prompt, (overview, doc.title)),
        "character": (prompts.character_analysis_prompt, (overview, doc.title, doc.all_characters)),
        "structure": (prompts.structure_analysis_prompt, (overview, doc.title, doc.scene_count, doc.estimated_page_count)),
        "scene_function": (prompts.scene_function_prompt, (overview, doc.title)),
    }
    for cat, (fn, args) in category_prompts.items():
        if cat in run_categories and overview:
            try:
                rules_fragment = rules_ctx.prompt_fragment_for_category(cat)
                all_findings.extend(run_script_level_category(fn, client, rules_fragment, *args))
            except LlamaServerError as e:
                result.errors.append(f"{cat} analysis failed: {e}")

    # 4b. Principles Engine — Chekhov's Gun / promise-payoff, using Piece 1's
    # knowledge graph as the candidate source. Runs independent of the
    # summary-based overview (it works directly off the knowledge graph),
    # so it's not gated behind `overview` like the script-level categories above.
    if "principles" in run_categories:
        try:
            kg = build_knowledge_graph(doc)
            principle_findings, principle_errors = run_principles_engine(kg, client, rules_ctx, doc.scene_count)
            all_findings.extend(principle_findings)
            result.errors.extend(principle_errors)
        except Exception as e:
            result.errors.append(f"Principles engine failed: {e}")

    # 5. verification — check every quoted finding against real scene text
    all_findings = verify_findings(all_findings, doc)
    result.findings = all_findings
    result.verification = verification_summary(all_findings)

    # 6. coverage
    if "coverage" in run_categories and overview:
        try:
            result.coverage = run_coverage(doc, overview, client)
        except LlamaServerError as e:
            result.errors.append(f"Coverage generation failed: {e}")

    return result
