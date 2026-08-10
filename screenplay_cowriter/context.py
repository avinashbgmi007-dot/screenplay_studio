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

from .personas import persona_text, mode_text

SCENE_REF_RE = re.compile(r"[Ss]cene\s+(\d+)")

MAX_SCENES_INJECTED_PER_TURN = 4  # cap context growth if someone mentions ten scene numbers at once


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


def build_system_prompt(script_ctx: ScriptContext, report_ctx: ReportContext, persona: str, mode: str) -> str:
    title = script_ctx.title or report_ctx.title or "this screenplay"
    return (
        f"{persona_text(persona)}\n\n"
        f"{mode_text(mode)}\n\n"
        f"You're discussing the screenplay \"{title}\" with its writer. Here is the "
        f"standing analysis report for reference:\n\n{report_ctx.compact_summary()}\n\n"
        f"When specific scene text is relevant to the current question, it will be "
        f"provided below as additional context for this turn. If it isn't provided "
        f"and you need exact wording to answer precisely, say so rather than guessing "
        f"at exact lines from memory."
    )


def extract_scene_refs(text: str) -> list:
    return sorted(set(int(n) for n in SCENE_REF_RE.findall(text)))[:MAX_SCENES_INJECTED_PER_TURN]


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
