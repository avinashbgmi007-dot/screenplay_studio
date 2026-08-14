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
import re
from difflib import SequenceMatcher

from .personas import persona_text, persona_examples, mode_text

SCENE_REF_RE = re.compile(r"[Ss]cene\s+(\d+)")

MAX_SCENES_INJECTED_PER_TURN = 4  # cap context growth if someone mentions ten scene numbers at once

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

    def script_map(self, max_characters: int = 24) -> str:
        """A compact standing map of the script: scene headings plus which
        characters appear where. Cheap enough to ride in the system prompt
        every turn, and it lets the co-writer point at exact scenes even when
        the writer's question doesn't name a scene number (full scene text is
        still injected on demand when a scene is referenced)."""
        scenes = self.data.get("scenes", [])
        if not scenes:
            return ""
        lines = [f"SCRIPT MAP — {len(scenes)} scenes:"]
        for s in scenes:
            num = s.get("scene_number")
            heading = s.get("heading_raw") or s.get("heading") or ""
            lines.append(f"Scene {num}: {heading}")

        chars = self.character_presence()
        if chars:
            ordered = sorted(chars.items(), key=lambda kv: -len(kv[1]))[:max_characters]
            lines.append("CHARACTER PRESENCE (scene numbers where each appears):")
            for name, nums in ordered:
                lines.append(f"{name}: {', '.join(str(n) for n in nums)}")
        return "\n".join(lines)


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

    def compact_summary(self) -> str:
        """A dense but complete text form of coverage + all findings — this is
        what stays in the system prompt every turn."""
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
        if findings:
            parts.append("REPORT FINDINGS:")
            for f in findings:
                scene_str = ", ".join(f"Scene {n}" for n in f.get("scene_refs", [])) or "General"
                status = f.get("verification", {}).get("status", "")
                flag = " [UNVERIFIED QUOTE]" if status == "not_found" else ""
                issue = f.get('issue', f.get('finding', ''))  # fallback for older report.findings.json files
                why = f.get('why_it_matters', '')
                line = f"- ({f.get('category')}, {f.get('severity')}) {scene_str}: {issue}"
                if why:
                    line += f" — {why}"
                parts.append(f"{line}{flag}")

        formatting = self.data.get("formatting_findings", [])
        if formatting:
            parts.append("FORMATTING NOTES:")
            for f in formatting:
                parts.append(f"- {f.get('message')}")

        return "\n\n".join(parts) if parts else "(No report loaded — discussing the raw script only.)"


def build_system_prompt(script_ctx: ScriptContext, report_ctx: ReportContext, persona: str, mode: str,
                        relationship_card: str | None = None, cold_start_line: str | None = None) -> str:
    title = script_ctx.title or report_ctx.title or "this screenplay"
    script_map = script_ctx.script_map()
    map_block = f"\n\nHere is a map of the script itself:\n\n{script_map}" if script_map else ""
    examples = persona_examples(persona)
    examples_block = f"\n\n{examples}" if examples else ""
    prompt = (
        f"{persona_text(persona)}\n\n"
        f"{mode_text(mode)}\n\n"
        f"{examples_block}\n"
        f"You're discussing the screenplay \"{title}\" with its writer. Here is the "
        f"standing analysis report for reference:\n\n{report_ctx.compact_summary()}{map_block}\n\n"
        f"When specific scene text is relevant to the current question, it will be "
        f"provided below as additional context for this turn. If it isn't provided "
        f"and you need exact wording to answer precisely, say so rather than guessing "
        f"at exact lines from memory.\n\n{GROUNDING_INSTRUCTION}\n\n{LANGUAGE_META_INSTRUCTION}\n\n{PLAIN_TEXT_INSTRUCTION}"
    )
    if relationship_card:
        prompt += f"\n\n{relationship_card}"
    if cold_start_line:
        prompt += f"\n\n{cold_start_line}"
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
