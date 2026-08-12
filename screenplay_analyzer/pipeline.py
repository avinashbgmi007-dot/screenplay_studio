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
from .grammar import findings_grammar, scene_summary_grammar, coverage_grammar, logline_test_grammar, character_reads_grammar
from .formatting_check import check_formatting
from .verifier import verify_findings, verification_summary
from .feedback_filter import filter_findings
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
    """Full scene text for the MODEL passes — capped so a long scene can
    never fill the context window by itself (see MAX_SCENE_CHARS)."""
    return _cap_scene_text("\n".join(e.text for e in scene.elements))


@dataclass
class AnalysisResult:
    doc: ScriptDocument
    findings: list[dict] = field(default_factory=list)
    coverage: dict | None = None
    character_reads: list[dict] = field(default_factory=list)
    logline_test: dict | None = None
    formatting_findings: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    verification: dict = field(default_factory=dict)
    model_used: str | None = None
    errors: list[str] = field(default_factory=list)


def _normalize_findings(findings: list, category: str, default_severity: str = "low") -> list[dict]:
    """Fill in the fields real local models sometimes leave null (seen live:
    severity and category missing on GGUF output). Every downstream consumer
    — the report, the fix queue, the UI severity badge — assumes these exist,
    so normalize at collection time with values the pipeline already knows."""
    out = []
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        f = dict(f)
        f["category"] = f.get("category") or category
        f["severity"] = f.get("severity") or default_severity
        f.setdefault("scene_refs", [])
        f.setdefault("evidence_quote", None)
        f.setdefault("rule_id", None)
        f.setdefault("why_it_matters", "")
        out.append(f)
    return out


TOKEN_BUDGET = 1400  # per-call ceiling for the PROMPT portion only (see below)
# The completion we request is generated INSIDE the same context window as the
# prompt. A local model on a limited --ctx-size fills the window with
# prompt+completion together — the live full-script run blew the window at
# prompt_tokens≈2200-3000 with a 1200-token completion. The chunker must keep
# prompt+completion under the model's real ceiling, so the completion budget
# is reserved out of the prompt budget.
COMPLETION_RESERVE = 1400
# chars/token: English runs ≈4 chars/token, but Tenglish/Latin + mixed-script
# dialogue tokens run shorter (~3 chars/token). Under-estimating is exactly
# how chunks overshoot the window, so estimate conservatively.
CHARS_PER_TOKEN = 3
# a single scene can be far longer than the model can hold (scene 14 of the
# full Pain script is 3.8k chars ≈ 1.3k tokens alone) — cap what's sent so a
# scene can never blow the window by itself; the pass still sees the scene's
# full opening and its beats, and a marker keeps the truncation honest.
MAX_SCENE_CHARS = 2200
# script-level categories see the whole-script overview (scene summaries); a
# long script's overview can exceed the window too (structure failed live at
# prompt_tokens≈3000) — cap it the same way.
MAX_OVERVIEW_CHARS = 6000

TRUNCATION_MARKER = "\n[...scene text truncated for context budget...]"


def _token_estimate(text: str) -> int:
    return max(1, len(text or "") // CHARS_PER_TOKEN) + 25


def _cap_scene_text(text: str, max_chars: int = MAX_SCENE_CHARS) -> str:
    text = text or ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + TRUNCATION_MARKER


def _chunk_by_budget(scene_dicts: list, chunk_size: int, budget: int = TOKEN_BUDGET) -> list[list]:
    """Chunk scenes so no model call's PROMPT exceeds a token budget (the
    completion reserve is subtracted implicitly by keeping the prompt well
    under the window), while never exceeding the caller's intended max chunk
    size. Prevents the live failure pattern (finish_reason='length' from
    over-stuffed prompts) before it happens instead of only recovering
    after it."""
    chunks: list[list] = []
    cur: list = []
    cur_tokens = 0
    for s in scene_dicts:
        t = _token_estimate(s.get("full_text") or "") + 30
        # budget is the PROMPT ceiling; it's set low enough that the prompt
        # plus the completion we'll request stays under the model's window
        # (see COMPLETION_RESERVE above).
        if cur and (len(cur) >= chunk_size or cur_tokens + t > budget):
            chunks.append(cur)
            cur, cur_tokens = [], 0
        cur.append(s)
        cur_tokens += t
    if cur:
        chunks.append(cur)
    return chunks


def _extract_items(result, key: str) -> list:
    """Model output for findings/summaries may come back as the keyed object
    OR as a bare JSON array (some local models ignore the grammar and emit
    the list directly). Normalize both shapes so callers never hit a
    TypeError on a list where a dict was expected."""
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        items = result.get(key)
        return items if isinstance(items, list) else []
    return []


def build_scene_summaries(doc: ScriptDocument, client: LlamaServerClient, chunk_size: int = 6, language: str = "eng") -> tuple[dict[int, str], list[str]]:
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
        system, user = prompts.scene_summary_prompt(chunk_, language=language)
        result = client.chat_json(system, user, grammar=grammar, max_tokens=800)
        return _extract_items(result, "summaries")

    for chunk in _chunk_by_budget(scene_dicts, chunk_size):
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
    overview = "\n".join(lines)
    if len(overview) > MAX_OVERVIEW_CHARS:
        overview = overview[:MAX_OVERVIEW_CHARS].rstrip() + "\n[...scene overview truncated for context budget...]"
    return overview


def run_dialogue_analysis(doc: ScriptDocument, client: LlamaServerClient, rules_ctx, chunk_size: int = 3, language: str = "eng") -> tuple[list[dict], list[str]]:
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
        system, user = prompts.dialogue_analysis_prompt(chunk_, rules_fragment=rules_fragment, chekhov_fragment=chekhov_fragment, language=language)
        result = client.chat_json(system, user, grammar=grammar, max_tokens=1200)
        return _extract_items(result, "findings")

    for chunk in _chunk_by_budget(scene_dicts, chunk_size):
        items, errs = _with_chunk_backoff(chunk, call)
        findings.extend(items)
        errors.extend(errs)
    findings = _normalize_findings(findings, "dialogue", default_severity="low")
    return findings, errors


def run_script_level_category(prompt_fn, client: LlamaServerClient, rules_fragment: str, *args, category: str = "theme", default_severity: str = "low", language: str = "eng") -> list[dict]:
    grammar = findings_grammar()
    system, user = prompt_fn(*args, rules_fragment=rules_fragment, language=language)
    result = client.chat_json(system, user, grammar=grammar, max_tokens=1500)
    items = _extract_items(result, "findings")
    return _normalize_findings(items, category, default_severity=default_severity)


def run_coverage(doc: ScriptDocument, overview: str, client: LlamaServerClient, language: str = "eng") -> dict:
    grammar = coverage_grammar()
    system, user = prompts.coverage_prompt(overview, doc.title, doc.author, language=language)
    result = client.chat_json(system, user, grammar=grammar, max_tokens=900)
    if isinstance(result, dict):
        return result
    return {}  # model returned a non-object — coverage is unavailable, not fatal


def _top_characters(stats: dict, doc: ScriptDocument, limit: int = 8) -> list[str]:
    """Characters ordered by scene presence (from the deterministic stats pass),
    so the perception read spends its budget on the people who matter."""
    arcs = (stats or {}).get("character_arc") or []
    ordered = [c.get("character") for c in arcs if c.get("character")]
    rest = [c for c in doc.all_characters if c not in ordered]
    return (ordered + rest)[:limit]


def run_character_reads(doc: ScriptDocument, overview: str, client: LlamaServerClient, characters: list[str], language: str = "eng") -> list[dict]:
    """The character-perception read: how each character actually comes across
    to a stranger vs. what the script appears to intend. Evidence quotes get
    the same verification as findings."""
    if not characters:
        return []
    grammar = character_reads_grammar()
    system, user = prompts.character_reads_prompt(overview, doc.title, characters, language=language)
    result = client.chat_json(system, user, grammar=grammar, max_tokens=1200)
    items = _extract_items(result, "reads")
    reads = [r for r in items if isinstance(r, dict) and r.get("character")]
    for r in reads:
        r.setdefault("scene_refs", [])
        r.setdefault("evidence_quote", None)
        r.setdefault("how_reads", "")
        r.setdefault("apparent_intent", "")
        r.setdefault("gap", "")
    return verify_findings(reads, doc)


def run_logline_test(logline: str, overview: str, title: str, client: LlamaServerClient, language: str = "eng") -> dict:
    """The logline test: does the premise land in one clean sentence? Signal is
    strong / workable / muddled — diagnosis only, no grades."""
    if not logline or not logline.strip():
        return {}
    grammar = logline_test_grammar()
    system, user = prompts.logline_test_prompt(logline, overview, title, language=language)
    result = client.chat_json(system, user, grammar=grammar, max_tokens=700)
    if isinstance(result, dict):
        return result
    return {}


def analyze(
    doc: ScriptDocument,
    client: LlamaServerClient,
    scene_chunk_size: int = 3,
    summary_chunk_size: int = 6,
    run_categories: tuple[str, ...] = ("dialogue", "theme", "character", "structure", "scene_function", "principles", "coverage", "genre", "char_reads", "logline_test"),
    progress_cb=None,
    report_language: str = "eng",
) -> AnalysisResult:
    """progress_cb: optional callable(dict) called at every stage boundary with
    {"stage": str, "status": "running"|"complete", "detail": str} — lets a UI
    show live per-stage progress instead of a frozen spinner."""
    result = AnalysisResult(doc=doc)

    def emit(stage, status, detail=""):
        if progress_cb:
            progress_cb({"stage": stage, "status": status, "detail": detail})

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
    emit("formatting", "running", "Formatting checks & analytics")
    result.formatting_findings = check_formatting(doc)
    result.stats = stats_module.full_stats_report(doc)
    emit("formatting", "complete")

    if not doc.scenes:
        result.errors.append("Document has no parsed scenes — skipping model-based analysis.")
        return result

    try:
        result.model_used = client.resolve_model()
    except LlamaServerError as e:
        result.errors.append(f"Could not reach model server: {e}")
        return result

    # 1b. deterministic craft passes — voice-bleed & on-the-nose subtext.
    # No model call, never fail the pipeline, and they read the parsed text
    # directly (so they work even when the server's context is too small for
    # the dialogue pass). all_findings is initialized here, before the first
    # consumer, so these passes can contribute findings.
    all_findings = []
    try:
        emit("voice", "running", "Comparing character voices")
        from .voice import run_voice_analysis, run_subtext_analysis
        voice_findings, _ = run_voice_analysis(doc)
        all_findings.extend(voice_findings)
        emit("voice", "complete")
        emit("subtext", "running", "Scanning for on-the-nose lines")
        subtext_findings, _ = run_subtext_analysis(doc)
        all_findings.extend(subtext_findings)
        emit("subtext", "complete")
    except Exception as e:
        result.errors.append(f"Craft passes (voice/subtext) failed: {e}")
        emit("voice", "complete", f"failed: {e}")

    # 2. scene summaries (needed for every script-level category + coverage)
    needs_summaries = any(c in run_categories for c in ("theme", "character", "structure", "scene_function", "coverage", "genre", "char_reads", "logline_test"))
    overview = ""
    if needs_summaries:
        try:
            emit("summaries", "running", "Summarizing each scene")
            summaries, summary_errors = build_scene_summaries(doc, client, chunk_size=summary_chunk_size, language=report_language)
            emit("summaries", "complete")
            overview = build_scene_overview_text(doc, summaries)
            if summary_errors:
                result.errors.append(
                    f"Scene summarization had {len(summary_errors)} unresolved failure(s) even after "
                    f"reducing batch size: {'; '.join(summary_errors[:3])}"
                    + (f" (+{len(summary_errors) - 3} more)" if len(summary_errors) > 3 else "")
                )
        except LlamaServerError as e:
            result.errors.append(f"Scene summarization failed: {e}")

    # 3. scene-level dialogue analysis
    if "dialogue" in run_categories:
        try:
            emit("dialogue", "running", "Reading dialogue & action")
            dialogue_findings, dialogue_errors = run_dialogue_analysis(doc, client, rules_ctx, chunk_size=scene_chunk_size, language=report_language)
            emit("dialogue", "complete")
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
                emit(cat, "running", f"Analyzing {cat.replace('_', ' ')}")
                rules_fragment = rules_ctx.prompt_fragment_for_category(cat)
                all_findings.extend(run_script_level_category(fn, client, rules_fragment, *args, category=cat, language=report_language))
                emit(cat, "complete")
            except LlamaServerError as e:
                result.errors.append(f"{cat} analysis failed: {e}")
                emit(cat, "complete", f"failed: {e}")

    # 4b. Principles Engine — Chekhov's Gun / promise-payoff, using Piece 1's
    # knowledge graph as the candidate source. Runs independent of the
    # summary-based overview (it works directly off the knowledge graph),
    # so it's not gated behind `overview` like the script-level categories above.
    if "principles" in run_categories:
        try:
            emit("principles", "running", "Checking setups & payoffs")
            kg = build_knowledge_graph(doc)
            principle_findings, principle_errors = run_principles_engine(kg, client, rules_ctx, doc.scene_count, language=report_language)
            all_findings.extend(principle_findings)
            result.errors.extend(principle_errors)
            emit("principles", "complete")
        except Exception as e:
            result.errors.append(f"Principles engine failed: {e}")
            emit("principles", "complete", f"failed: {e}")

    # 4c. character-perception read — how each character comes across to a
    # stranger vs. apparent intent. Needs the overview + character list; runs
    # after the character arc pass so the deterministic stats are ready.
    if "char_reads" in run_categories and overview:
        try:
            emit("char_reads", "running", "Reading how characters come across")
            result.character_reads = run_character_reads(
                doc, overview, client,
                _top_characters(result.stats, doc),
                language=report_language,
            )
            emit("char_reads", "complete")
        except LlamaServerError as e:
            result.errors.append(f"Character-perception read failed: {e}")
            emit("char_reads", "complete", f"failed: {e}")
        except Exception as e:
            result.errors.append(f"Character-perception read failed: {e}")
            emit("char_reads", "complete", f"failed: {e}")

    # 5. verification — check every quoted finding against real scene text
    emit("verification", "running", "Verifying quotes against the script")
    all_findings = verify_findings(all_findings, doc)
    result.findings = all_findings
    result.verification = verification_summary(all_findings)
    emit("verification", "complete")

    # 6. coverage
    if "coverage" in run_categories and overview:
        try:
            emit("coverage", "running", "Writing coverage")
            result.coverage = run_coverage(doc, overview, client, language=report_language)
            emit("coverage", "complete")
        except LlamaServerError as e:
            result.errors.append(f"Coverage generation failed: {e}")
            emit("coverage", "complete", f"failed: {e}")

    # 6a. logline test — does the premise land in one sentence? Diagnosis only;
    # runs after coverage because it judges the coverage pass's logline.
    if "logline_test" in run_categories and overview and result.coverage and result.coverage.get("logline"):
        try:
            emit("logline_test", "running", "Testing the logline")
            result.logline_test = run_logline_test(
                result.coverage["logline"], overview, doc.title, client, language=report_language
            )
            emit("logline_test", "complete")
        except LlamaServerError as e:
            result.errors.append(f"Logline test failed: {e}")
            emit("logline_test", "complete", f"failed: {e}")
        except Exception as e:
            result.errors.append(f"Logline test failed: {e}")
            emit("logline_test", "complete", f"failed: {e}")

    # 6b. genre-convention check — uses the genre coverage just produced, so it
    # runs after coverage and only when a genre was reported.
    if "genre" in run_categories and result.coverage and result.coverage.get("genre"):
        try:
            emit("genre", "running", "Checking genre conventions")
            from .genre import run_genre_check
            genre_findings = _normalize_findings(run_genre_check(result.coverage, overview, client, language=report_language), "genre")
            # genre findings get the same quote-verification as every other finding
            all_findings = verify_findings(all_findings + genre_findings, doc)
            result.findings = all_findings
            result.verification = verification_summary(all_findings)
            emit("genre", "complete")
        except LlamaServerError as e:
            result.errors.append(f"Genre-convention check failed: {e}")
            emit("genre", "complete", f"failed: {e}")
        except Exception as e:
            result.errors.append(f"Genre-convention check failed: {e}")
            emit("genre", "complete", f"failed: {e}")

    # 7. drop non-writing feedback — meta-commentary about the script's
    # language (dialect identification, subtitles for non-native speakers)
    # is noise for the writer, not feedback. Filter after verification so
    # the summary reflects exactly what the writer will see.
    result.findings = filter_findings(result.findings)
    result.verification = verification_summary(result.findings)

    emit("done", "complete", "Analysis complete")
    return result
