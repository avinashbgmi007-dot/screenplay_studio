"""
Builds what the model actually sees each turn:

  1. A system prompt: persona + mode + a compact standing summary of the
     report (coverage + all findings, since findings are the whole point
     of the conversation and are small enough to keep in context wholesale
     for a feature-length script).
  2. On-demand scene text: when the current user message references
     specific scene numbers, pull those scenes' FULL original text from
     the Piece 1 JSON and inject it — this is what lets the model quote
     exact lines rather than vaguely paraphrase from memory of a summary,
     since a stateless chat API has no persistent memory of the script
     beyond what's resent each turn.

Reads Piece 1/2 JSON as plain dicts, not by importing their packages —
Piece 3 should work standalone even if those packages aren't installed
alongside it, per the composability goal from the start of this project.
"""

from __future__ import annotations

import json
import os
import re
import warnings
from difflib import SequenceMatcher

from .personas import persona_text, persona_examples, mode_text, DOCTOR_PERSONA

SCENE_REF_RE = re.compile(r"[Ss]cene\s+(\d+)")

# ---------------------------------------------------------------------------
# Global prompt budget (C7, M1).
#
# Every block that rides into the co-writer's system prompt is individually
# capped — findings are "small enough to keep wholesale", the map caps its
# character list, PAST WORK caps its project count, the craft block caps its
# rules. Nothing capped their SUM. A feature-length script with a heavily
# flagged report assembles a prompt far larger than a small local model's
# window, and llama.cpp truncates it silently: the model then answers from a
# mangled context with no sign anything was lost.
#
# ON BY DEFAULT (M1). It used to require SCREENPLAY_PROMPT_BUDGET, which
# nobody sets, so the protection existed only on paper. When the budget bites,
# whole blocks are dropped lowest-value-first and the omission is STATED in the
# prompt, so a degraded turn is honest instead of silently wrong.
#
# The value is normally DERIVED from the model's own reported context window
# (BaseLlamaClient.context_window -> budget_for_context), because a fixed
# number is wrong in both directions: a 90k-token model would shed garnish it
# can easily afford, while a 4k-token model would still truncate. The constant
# below is only the fallback for servers that don't answer /props.
#
# Sizing, measured on the staged projects: the irreducible floor (persona, mode,
# examples, guards, findings) is ~8.5k chars; a 22-scene project assembles ~14k;
# the largest staged report (36 findings) assembles ~27.5k; a feature-length
# script with a heavy report projects to ~30k, before the turn adds up to 4 full
# scenes plus a 16-message history window. 48k leaves headroom over every
# project on disk while still bounding a runaway prompt.
#
# SCREENPLAY_PROMPT_BUDGET overrides it; an explicit 0 restores unlimited.
# ---------------------------------------------------------------------------
DEFAULT_PROMPT_CHAR_BUDGET = 48000


def _budget_from_env(default: int) -> int:
    """SCREENPLAY_PROMPT_BUDGET, or `default` when unset, blank or unparseable.

    An explicit 0 means unlimited — the pre-M1 behaviour, kept because the CLI
    and the tests rely on being able to turn the budget off completely. A typo
    must not silently disable the protection, so a value that isn't a number
    falls back to the default rather than to 0."""
    raw = (os.environ.get("SCREENPLAY_PROMPT_BUDGET") or "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


PROMPT_CHAR_BUDGET = _budget_from_env(DEFAULT_PROMPT_CHAR_BUDGET)

# How the budget is derived from a model's reported window.
#
# Both factors are deliberately conservative, and the asymmetry is the point:
# over-trimming is visible, graceful and stated in the prompt, while
# under-trimming is the silent truncation this whole mechanism exists to stop.
# - The system prompt is only half the turn. The rest is the reply, the
#   16-message history window, and up to MAX_SCENES_INJECTED_PER_TURN full
#   scenes — so the prompt may claim half the window, not all of it.
# - 2 chars/token rather than the usual ~4: this app is built for
#   Telugu/Hindi/Tenglish writers, and Indic scripts tokenize far worse than
#   English. Under-estimating the budget costs a shed block; over-estimating it
#   costs the writer their context without telling them.
#
# At these two settings the product is 1.0, so the budget is simply "one
# character per token of the model's window" — the factors are kept separate
# because they encode different assumptions (how much of the window this block
# may use vs. how many characters a token is worth) and either may need to move
# without the other. The chars-per-token figure remains an APPROXIMATION: it is
# conservative for English and still optimistic for a dense Indic script, which
# is why the env var exists as the operator's override.
PROMPT_BUDGET_CONTEXT_FRACTION = 0.5
PROMPT_BUDGET_CHARS_PER_TOKEN = 2.0


def budget_for_context(n_ctx_tokens: int | None) -> int | None:
    """A prompt budget in characters for a model reporting `n_ctx_tokens`.

    None when the window is unknown or nonsensical — the caller then uses
    PROMPT_CHAR_BUDGET. Pure, so the derivation is testable without a server."""
    if not n_ctx_tokens or n_ctx_tokens <= 0:
        return None
    return int(n_ctx_tokens * PROMPT_BUDGET_CONTEXT_FRACTION * PROMPT_BUDGET_CHARS_PER_TOKEN)

MAX_SCENES_INJECTED_PER_TURN = 4  # cap context growth if someone mentions ten scene numbers at once

# The craft-principles block is derived from the report's rule ids, so it is
# already bounded by how many distinct rules a report cites — but cap it anyway
# so a pathological report can't blow the prompt (see C7: the findings summary
# itself is uncapped, so this block must not add to that problem).
MAX_CRAFT_RULES = 10
MAX_CRAFT_CHARS = 3000

# Standing rule: the writer knows what language their pages are in — the
# co-writer never comments on the script's language itself (dialect
# identification, subtitles, non-native-speaker accessibility). Kept in the
# system prompt every turn, and strip_language_meta() (engine.py) backs it
# up on the reply side for models that ignore instructions.
LANGUAGE_META_INSTRUCTION = (
    "The writer knows what language their pages are in. Never comment on the "
    "script's LANGUAGE itself: do not identify, classify, or speculate about what "
    "language or dialect it's written in (e.g. \"reads as regional\", \"probably "
    "Telugu\", \"mixed language\", \"code-switching\"), and never mention subtitles, "
    "translation, or what non-native speakers will or won't understand. Keep every "
    "note about story, character, dialogue, structure, and craft."
)

# Some local models (reasoning / JSON-tuned distills) decide on their own to
# wrap chat replies in JSON or code fences even when nothing asks for it.
# State it plainly up front so the reply reads like a colleague's note, not a
# serialized object.
PLAIN_TEXT_INSTRUCTION = (
    "Reply in plain conversational prose — the writer reads your message "
    "directly. Never emit JSON, code fences, XML, or any structured or wrapped "
    "format; if an answer would benefit from structure, use short paragraphs "
    "or simple sentences instead."
)

# Local models fill gaps in the provided material by inventing plausible
# script content — a scene that doesn't exist, a line nobody said, a name not
# in the pages. That reads as hallucination to the writer. State the knowledge
# boundary plainly every turn: specificity must come from the pages or the
# writer, never from guessing (the character-AI playbook: the companion only
# knows what it has been shown, and its honesty about the gap is what makes it
# feel like a real collaborator rather than a bot performing helpfulness).
#
# The idea room has its own boundary: there are NO pages, so the model must
# never pretend it has read any — it works only from what the writer says and
# the premise card they're shaping together.
IDEA_GROUNDING_INSTRUCTION = (
    "GROUNDING — There is no script yet: the idea and the premise card are the "
    "only material. Never pretend you've read pages, never invent scenes, "
    "characters, or details of the story the writer hasn't shared, and never "
    "reference 'the report', 'the analysis', or 'the script'. If you need "
    "something you don't have, say so plainly and ask."
    " The page is the WRITER's material — never recite it back, never summarize "
    "what they already wrote down; they know what's on it. Respond to what's "
    "new in their message, build on the page in your own words, and when the "
    "next step isn't obvious, probe: one sharp question about the part that's "
    "still fuzzy beats a paragraph of restatement."
)

GROUNDING_INSTRUCTION = (
    "GROUNDING — Only refer to what is actually in the script text and report "
    "provided to you. Never invent a scene, a line, an action, a name, or a "
    "detail that isn't in that material. If something isn't in front of you "
    "(e.g. the exact wording of a scene you haven't been shown), say so plainly "
    "— 'I don't have that scene in front of me — where does it happen?' — and "
    "ask, rather than guessing to sound helpful. If you quote the script, quote "
    "it exactly."
)


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class ScriptContext:
    """Thin wrapper over a Piece 1 ScriptDocument JSON dict."""

    def __init__(self, data: dict = None):
        self.data = data or {}
        self._by_scene = {s["scene_number"]: s for s in self.data.get("scenes", [])}

    @property
    def title(self):
        return self.data.get("title")

    def scene_text(self, scene_number: int):
        scene = self._by_scene.get(scene_number)
        if not scene:
            return None
        lines = [f"[Scene {scene_number} — {scene.get('heading_raw', '')}]"]
        for el in scene.get("elements", []):
            lines.append(el.get("text", ""))
        return "\n".join(lines)

    def has_scene(self, scene_number: int) -> bool:
        return scene_number in self._by_scene

    def character_presence(self) -> dict:
        """Map of base character name (uppercase, extension stripped) to the
        sorted scene numbers where they speak. Computed once and reused by the
        script map and by character-mention scene resolution."""
        if getattr(self, "_characters", None) is None:
            chars: dict[str, list[int]] = {}
            for s in self.data.get("scenes", []):
                num = s.get("scene_number")
                for el in s.get("elements", []):
                    if el.get("type") == "character":
                        name = (el.get("text") or "").strip().upper()
                        # keep the base name (strip extensions like (O.S.)/(CONT'D))
                        base = name.split("(")[0].strip()
                        if base:
                            chars.setdefault(base, [])
                            if num not in chars[base]:
                                chars[base].append(num)
            for scenes in chars.values():
                scenes.sort()
            self._characters = chars
        return self._characters

    def script_map(self, max_characters: int = 24, max_chars: int = 0) -> str:
        """A compact standing map of the script: scene headings plus which
        characters appear where. Cheap enough to ride in the system prompt
        every turn, and it lets the co-writer point at exact scenes even when
        the writer's question doesn't name a scene number (full scene text is
        still injected on demand when a scene is referenced).

        `max_chars` (0 = unbounded) is the prompt budget's lever. Over it, the
        character-presence section goes first — the scene list is what locates
        a scene — and if that is still not enough, scene lines are cut from the
        tail. Either way the cut is STATED, so the model knows the map is
        partial rather than believing the script ends where the list does."""
        scenes = self.data.get("scenes", [])
        if not scenes:
            return ""
        header = f"SCRIPT MAP — {len(scenes)} scenes:"
        scene_lines = []
        for s in scenes:
            num = s.get("scene_number")
            heading = s.get("heading_raw") or s.get("heading") or ""
            scene_lines.append(f"Scene {num}: {heading}")

        chars = self.character_presence()
        char_lines = []
        if chars:
            ordered = sorted(chars.items(), key=lambda kv: -len(kv[1]))[:max_characters]
            char_lines = ["CHARACTER PRESENCE (scene numbers where each appears):"]
            char_lines += [f"{name}: {', '.join(str(n) for n in nums)}" for name, nums in ordered]

        lines = [header] + scene_lines + char_lines
        if not max_chars or len("\n".join(lines)) <= max_chars:
            return "\n".join(lines)

        # over budget: drop the character section first, then cut scene lines
        lines = [header] + scene_lines
        if len("\n".join(lines)) <= max_chars:
            return "\n".join(lines) + "\n(Character presence omitted for space.)"

        kept = []
        for line in lines:
            if len("\n".join(kept + [line])) > max_chars:
                break
            kept.append(line)
        if len(kept) <= 1:  # not even the header fits — say so rather than emit a bare header
            return f"SCRIPT MAP — {len(scenes)} scenes (list omitted for space)."
        kept.append(f"(…{len(lines) - len(kept)} further line(s) omitted for space.)")
        return "\n".join(kept)


class ReportContext:
    """Thin wrapper over a Piece 2 findings.json dict."""

    def __init__(self, data: dict = None):
        self.data = data or {}

    @property
    def title(self):
        return self.data.get("title")

    @property
    def model_used(self):
        return self.data.get("model_used")

    # Severity ordering for the budget's findings trim. The KB curates the
    # severity, so it is the ranking the trim should respect.
    _SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}

    def compact_summary(self, max_findings: int = 0, drop_why: bool = False) -> str:
        """A dense but complete text form of coverage + all findings — this is
        what stays in the system prompt every turn.

        `max_findings` and `drop_why` (both off by default) are the prompt
        budget's last-resort levers. The findings are the point of the
        conversation, so they are trimmed only after every optional block has
        been dropped — and the trim keeps the highest-severity findings, then
        restores report order, so the survivors are still readable in sequence.
        The omission is stated rather than silently applied."""
        parts = []
        cov = self.data.get("coverage")
        if cov:
            parts.append(
                f"COVERAGE — Recommendation: {cov.get('recommendation', '?').upper()}\n"
                f"Logline: {cov.get('logline', '')}\n"
                f"Genre/Tone: {cov.get('genre', '')} / {cov.get('tone', '')}\n"
                f"Strengths: {'; '.join(cov.get('strengths', []))}\n"
                f"Weaknesses: {'; '.join(cov.get('weaknesses', []))}"
            )

        findings = self.data.get("findings", [])
        omitted = 0
        if findings and max_findings and len(findings) > max_findings:
            ranked = sorted(range(len(findings)),
                            key=lambda i: self._SEVERITY_RANK.get(
                                str(findings[i].get("severity") or "").lower(), 3))
            keep = sorted(ranked[:max_findings])
            omitted = len(findings) - len(keep)
            findings = [findings[i] for i in keep]

        if findings:
            parts.append("REPORT FINDINGS:")
            for f in findings:
                scene_str = ", ".join(f"Scene {n}" for n in f.get("scene_refs", [])) or "General"
                status = f.get("verification", {}).get("status", "")
                flag = " [UNVERIFIED QUOTE]" if status == "not_found" else ""
                issue = f.get('issue', f.get('finding', ''))  # fallback for older report.findings.json files
                why = "" if drop_why else f.get('why_it_matters', '')
                line = f"- ({f.get('category')}, {f.get('severity')}) {scene_str}: {issue}"
                if why:
                    line += f" — {why}"
                parts.append(f"{line}{flag}")
            if omitted:
                parts.append(f"({omitted} further finding(s) not listed here — for space.)")

        formatting = self.data.get("formatting_findings", [])
        if formatting:
            parts.append("FORMATTING NOTES:")
            for f in formatting:
                parts.append(f"- {f.get('message')}")

        return "\n\n".join(parts) if parts else "(No report loaded — discussing the raw script only.)"

    def craft_principles(self, max_rules: int = MAX_CRAFT_RULES,
                         max_chars: int = MAX_CRAFT_CHARS) -> str:
        """The named craft principles the findings actually rest on.

        Findings carry a `rule_id` when they were grounded in the knowledge
        base, but the summary above showed the co-writer only the finding's
        prose — so it could quote the doctor's verdict without being able to
        see the rule the verdict rests on, and its advice drifted to general
        impressions. This names the distinct rules in play (never the whole
        KB), deduped and capped.

        Returns "" when no finding cites a rule or the knowledge base isn't
        installed — the co-writer then behaves exactly as before, keeping its
        standalone guarantee (the import is lazy and guarded).
        """
        rule_ids: list[str] = []
        for f in self.data.get("findings") or []:
            rid = str(f.get("rule_id") or "").strip()
            if rid and rid not in rule_ids:
                rule_ids.append(rid)
        if not rule_ids:
            return ""
        try:
            from knowledge_base import KnowledgeBase
        except ImportError:
            return ""
        kb = KnowledgeBase()
        lines: list[str] = []
        used = 0
        unknown = 0
        for rid in rule_ids[:max_rules]:
            try:
                rule = kb.get(rid)
            except KeyError:
                # A rule id the KB does not know. Counted separately from the
                # space cap below — an unknown id is a dangling reference in
                # the report, not something this block chose to leave out.
                unknown += 1
                continue
            line = f"- **{rule.name}** ({rule.attribution}): {rule.definition}"
            if lines and used + len(line) > max_chars:
                break
            lines.append(line)
            used += len(line)
        if not lines:
            return ""
        block = (
            "CRAFT PRINCIPLES IN PLAY — the named rules behind the findings "
            "above, from the same knowledge base the analyzer used. Ground your "
            "advice in these rather than general impressions; where you go "
            "beyond them, say so:\n" + "\n".join(lines)
        )
        omitted = len(rule_ids) - len(lines) - unknown
        if omitted > 0:
            block += f"\n({omitted} further principle(s) not listed here.)"
        return block


# The idea page's free-form notes, capped so a long canvas can't blow the
# prompt; the tail is what the writer is currently shaping, which matters
# most for the conversation.
MAX_PAGE_CONTENT_CHARS = 6000


def _premise_block(card: dict | None) -> str:
    """The idea page as compact context: the shared, growing note the idea
    room keeps on the desk. The free-form page is the primary material;
    the structured card (logline/questions) rides behind it. Empty parts
    are dropped so a fresh page doesn't pad the prompt with blanks."""
    card = card or {}
    parts = []
    title = (card.get("title") or "").strip()
    logline = (card.get("logline") or "").strip()
    premise = (card.get("premise") or "").strip()
    questions = [str(q).strip() for q in (card.get("questions") or []) if str(q).strip()]
    if title:
        parts.append(f"Working title: {title}")
    content = (card.get("content") or "").strip()
    if content:
        if len(content) > MAX_PAGE_CONTENT_CHARS:
            content = "…(earlier notes cut for space)…\n" + content[-MAX_PAGE_CONTENT_CHARS:]
        parts.append("THE PAGE — the writer's free-form notes, as they stand:\n\n" + content)
    if logline:
        parts.append(f"Logline: {logline}")
    if premise:
        parts.append(f"Premise: {premise}")
    if questions:
        parts.append("Open questions: " + " | ".join(questions))
    return "\n".join(parts) if parts else "(The page is empty so far — you're shaping the idea together.)"


def _shed_ladder():
    """The prompt budget's shed steps, lowest value first and cumulative.

    What is never shed: the persona, the mode, the example dialogue, the voice
    and grounding rules, the findings' `issue` lines, and the writer's own
    relationship card / cold-start line — those are the conversation. What goes
    first is garnish (room state), then the writer's craft history, then the
    doctor's case file, then the writer's past work, then the craft principles,
    then detail inside the map and finally the findings' rationale. Each step
    keeps the previous one.

    Note the two similarly-named keys, which mean different things: `drop_craft`
    sheds the report's CRAFT PRINCIPLES (the rules the findings rest on), while
    `drop_craft_history` sheds the writer's own EDIT HISTORY (P2.8). They are
    shed at opposite ends of the ladder — history is reference material and goes
    second, principles are load-bearing for the findings and go fourth.
    """
    plan: dict = {}
    for key, value in (
        ("drop_mood", True),
        ("drop_craft_history", True),
        ("drop_case", True),
        ("drop_library", True),
        ("drop_craft", True),
        ("map_chars", 2000),
        ("map_chars", 800),
        ("report_why", False),
        ("map_chars", 400),
        ("report_max", 12),
    ):
        plan = {**plan, key: value}
        yield dict(plan)


PROMPT_SHED_LADDER = tuple(_shed_ladder())

PROMPT_TRIM_NOTE = (
    "CONTEXT TRIMMED — this turn's context was cut to fit the model's window, so "
    "some reference material above is missing. Do not assume it does not exist: "
    "if you need something that isn't here, say so and ask."
)


def build_system_prompt(script_ctx: ScriptContext, report_ctx: ReportContext, persona: str, mode: str,
                        relationship_card: str | None = None, cold_start_line: str | None = None,
                        premise: dict | None = None, writer_library_text: str | None = None,
                        mood_text: str | None = None, doctor_case_text: str | None = None,
                        craft_history_text: str | None = None,
                        budget: int | None = None) -> str:
    examples = persona_examples(persona)
    examples_block = f"\n\n{examples}" if examples else ""
    if premise is not None:
        # Idea room: no script, no report — the premise card is the material.
        # No shed ladder here: the only unbounded block is the page itself, and
        # _premise_block already caps it with a stated cut.
        idea_title = (premise.get("title") or "").strip() or "this idea"
        update_note = (premise.get("page_update") or "").strip()
        update_block = (
            f"\n\nPAGE UPDATE — a deterministic diff of the page since you last read it. "
            f"These changes are facts, not guesses; react to what's new naturally:\n{update_note}\n"
            if update_note else ""
        )
        prompt = (
            f"{persona_text(persona)}\n\n"
            f"{mode_text(mode)}\n\n"
            f"{examples_block}\n"
            f"You're developing the story idea \"{idea_title}\" with its writer. "
            f"There are no pages yet — the idea is the material.\n\n"
            f"PREMISE (the shared card, keeps growing as you talk):\n\n{_premise_block(premise)}\n"
            f"{update_block}\n"
            f"{IDEA_GROUNDING_INSTRUCTION}\n\n{LANGUAGE_META_INSTRUCTION}\n\n{PLAIN_TEXT_INSTRUCTION}"
        )
    else:
        title = script_ctx.title or report_ctx.title or "this screenplay"

        def render(*, drop_mood=False, drop_case=False, drop_library=False, drop_craft=False,
                   drop_craft_history=False, map_chars=0, report_max=0, report_why=True):
            script_map = script_ctx.script_map(max_chars=map_chars)
            map_block = f"\n\nHere is a map of the script itself:\n\n{script_map}" if script_map else ""
            # The rules the findings rest on, so advice is anchored to the craft
            # source rather than to the finding's prose alone. Empty when the
            # report cites no rule ids, so nothing changes for older reports.
            _craft = "" if drop_craft else report_ctx.craft_principles()
            craft_block = f"\n\n{_craft}" if _craft else ""
            body = (
                f"{persona_text(persona)}\n\n"
                f"{mode_text(mode)}\n\n"
                f"{examples_block}\n"
                f"You're discussing the screenplay \"{title}\" with its writer. Here is the "
                f"standing analysis report for reference:\n\n"
                f"{report_ctx.compact_summary(max_findings=report_max, drop_why=not report_why)}"
                f"{craft_block}{map_block}\n\n"
                f"When specific scene text is relevant to the current question, it will be "
                f"provided below as additional context for this turn. If it isn't provided "
                f"and you need exact wording to answer precisely, say so rather than guessing "
                f"at exact lines from memory.\n\n{GROUNDING_INSTRUCTION}\n\n{LANGUAGE_META_INSTRUCTION}\n\n{PLAIN_TEXT_INSTRUCTION}"
            )
            if mood_text and not drop_mood:
                # Deterministic room state (facts computed from real project data —
                # never model-improvised). Colors energy/patience; carries no facts
                # the persona could misquote as script content.
                body += f"\n\n{mood_text}"
            if doctor_case_text and persona == DOCTOR_PERSONA and not drop_case:
                # The doctor's case file on this writer — cross-project PATTERNS only,
                # never script content. Sameer never sees it; it's not his lens.
                body += f"\n\n{doctor_case_text}"
            if relationship_card:
                body += f"\n\n{relationship_card}"
            if craft_history_text and not drop_craft_history:
                # Sits AFTER the relationship card on purpose. The card forbids
                # quoting the memory; this block carves out exactly one
                # permitted class (the writer's own past edits on THIS script)
                # and restates the profile prohibition, so the carve-out has the
                # last word without widening what the card forbids. Put it
                # before the card and the card's blanket rule would swallow the
                # one reference the review asked us to permit (P2.8).
                body += f"\n\n{craft_history_text}"
            if cold_start_line:
                body += f"\n\n{cold_start_line}"
            if writer_library_text and not drop_library:
                # The writer's past work — a different shelf, with a grounding guard
                # baked into the block itself (never merged with the current script).
                body += f"\n\n{writer_library_text}"
            return body

        full = render()
        prompt = full
        limit = PROMPT_CHAR_BUDGET if budget is None else budget
        if limit and len(prompt) > limit:
            # The trim note has to be PAID FOR out of the budget. Fitting the
            # prompt and then appending the note pushes it back over the limit —
            # which then reports the budget as unreachable when it was not.
            reserve = len(PROMPT_TRIM_NOTE) + 2
            for plan in PROMPT_SHED_LADDER:
                prompt = render(**plan)
                if len(prompt) + reserve <= limit:
                    break
            # State the cut only when content actually changed: a ladder step
            # that had nothing to remove is not a trimmed turn.
            if prompt != full:
                prompt += "\n\n" + PROMPT_TRIM_NOTE
            if len(prompt) > limit:
                # The ladder has a floor: the persona, the mode, the example
                # dialogue, the guards and the findings are not shed, so a
                # budget below their sum is unreachable. Measured: a 22-scene
                # script with 17 findings floors at ~12k chars. Say so loudly —
                # otherwise the operator believes the cap is protecting them
                # while the server still truncates.
                warnings.warn(
                    f"Prompt budget {limit} chars is unreachable for this turn: the "
                    f"irreducible context (persona, guards, examples and findings) is "
                    f"~{len(prompt) // 1000}k chars. Raise SCREENPLAY_PROMPT_BUDGET or "
                    f"the model will truncate silently.",
                    RuntimeWarning,
                )
    return prompt


def extract_scene_refs(text: str) -> list:
    return sorted(set(int(n) for n in SCENE_REF_RE.findall(text)))[:MAX_SCENES_INJECTED_PER_TURN]


CHAR_MIN_LEN = 3  # ignore very short names ("AM", "JO") to avoid false-positive word matches
FUZZY_RATIO = 0.58  # nickname tier: 'siddhu' ~ 'SIDDHARTH' scores 0.67; 'ravi' ~ 'RAHUL' 0.44


def extract_character_refs(text: str, script_ctx: ScriptContext) -> list:
    """Base character names from the script that the text mentions. Writers
    ask about their script by naming people ('what's Rishi's deal in the
    hospital?'), often in shorthand (nicknames, plurals, truncated forms —
    'siddhu', 'the goons', 'doc'). Mentions resolve to the scenes where that
    character actually speaks, so the model gets real text to ground on.

    Four tiers, least to most permissive: whole-name match, name-token match
    (GOON_TWO -> 'goon'), prefix match both directions ('goons' -> GOON,
    'siddh' -> SIDDHARTH), then a fuzzy best-match for diminutives
    ('siddhu' -> SIDDHARTH). Only the single closest fuzzy candidate wins,
    which keeps accidental lookalikes out."""
    t = text or ""
    words = re.findall(r"[A-Za-z][A-Za-z']{2,}", t)  # user words, len >= 3
    presence = script_ctx.character_presence()
    found = []

    for name in presence:
        if len(name) < CHAR_MIN_LEN:
            continue
        # 1) whole-name, word-boundary, case-insensitive
        if re.search(rf"\b{re.escape(name)}\b", t, re.I):
            found.append(name)
            continue
        # 2) any name token as a whole word (GOON_TWO -> 'goon', 'senior')
        tokens = [tok for tok in re.split(r"[\s_]+", name) if len(tok) >= 4]
        if any(re.search(rf"\b{re.escape(tok)}\b", t, re.I) for tok in tokens):
            found.append(name)
            continue
        # 3) prefix match either direction against a user word ('doc' ->
        #    DOCTOR, 'goons' -> GOON, 'siddh' -> SIDDHARTH)
        if any(len(w) >= CHAR_MIN_LEN and (w.upper().startswith(name) or name.startswith(w.upper())) for w in words):
            found.append(name)
            continue
        # 4) fuzzy best-match across names (diminutives): only the closest
        #    candidate, and only when it clears the similarity bar
        best, best_r = None, 0.0
        for other in presence:
            if len(other) < 4:
                continue
            r = max(SequenceMatcher(None, other, w.upper()).ratio() for w in words if len(w) >= 4)
            if r > best_r:
                best, best_r = other, r
        if best and best_r >= FUZZY_RATIO and best not in found:
            found.append(best)
    return found


def resolve_referenced_scenes(text: str, script_ctx: ScriptContext,
                              max_n: int = MAX_SCENES_INJECTED_PER_TURN) -> list:
    """Scene numbers worth pulling into this turn's context: explicit
    'scene N' mentions plus every scene where a named character speaks.
    Character mentions are how writers actually refer to their script —
    without them the model answers from the map + report alone and fills the
    gaps by inventing. The cap keeps context growth bounded on long chats."""
    refs = extract_scene_refs(text)
    for name in extract_character_refs(text, script_ctx):
        for n in script_ctx.character_presence()[name]:
            if n not in refs:
                refs.append(n)
    return sorted(refs)[:max_n]


def build_scene_context_block(script_ctx: ScriptContext, scene_numbers: list):
    if not scene_numbers:
        return None
    blocks = []
    missing = []
    for n in scene_numbers:
        text = script_ctx.scene_text(n)
        if text:
            blocks.append(text)
        else:
            missing.append(n)
    if not blocks:
        return None
    out = "SCENE TEXT (for this turn only):\n\n" + "\n\n---\n\n".join(blocks)
    if missing:
        out += f"\n\n(Note: scene(s) {missing} were referenced but not found in the script data.)"
    return out
