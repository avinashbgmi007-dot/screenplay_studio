"""Stateless reply transformation pipeline.

Extracted from engine.py to separate pure transformation logic from
the CoWriterEngine class. Every function here is stateless — no side
effects, no instance state, no module-level mutable state.
"""

from __future__ import annotations

import re

from .language_meta import (
    strip_language_meta, strip_json_wrap, strip_repetition_lines, strip_repeated_blocks,
)
from .persona_specs import strip_banned_phrases


def clean_reply(raw: str) -> str:
    """Reply hygiene pipeline, outermost-raw to innermost-clean:
    unwrap accidental JSON wrappers, drop separator/tag garbage, collapse
    semantic repetition blocks, then strip language meta-commentary."""
    return strip_language_meta(
        strip_repeated_blocks(strip_repetition_lines(strip_json_wrap(raw)))
    )


def ground_reply(reply: str, script_ctx) -> str:
    """Reply-side hallucination guard. If the reply references a scene number
    that doesn't exist in the script, own it honestly instead of letting the
    invented scene stand — a real co-writer caught reaching for a page they
    don't have would say so. Cheap and safe: only flags numbers outside the
    script's actual scene set, so genuine references pass untouched."""
    from .context import SCENE_REF_RE
    refs = sorted({int(n) for n in SCENE_REF_RE.findall(reply)})
    unknown = [n for n in refs if not script_ctx.has_scene(n)]
    if not unknown:
        return reply
    reply = reply.rstrip()
    return (
        f"{reply}\n\n(One honest flag: I said \"scene {unknown[0]}\" — I don't "
        "actually see that scene in the script I'm holding. Point me at the right "
        "one and I'll dig in properly.)"
    )


def strip_anti_ai_tells(reply: str) -> str:
    """Strip common AI tells that break the fiction of a human collaborator.
    Based on 2026 research into AI voice drift and anti-patterns. These are
    the phrases that immediately mark text as machine-written."""
    # Banned openings — the model loves to start with these
    OPENINGS = [
        r"^(?:Great question[!.]|Absolutely[!.]|I'?d be happy to|"
        r"That'?s a (?:really )?(?:good|great|excellent|interesting) point[!.]|"
        r"Let me (?:help|think|consider|address)|"
        r"I (?:appreciate|understand) (?:your|the)|"
        r"Thank you for (?:sharing|asking|bringing))\s*",
    ]
    for pat in OPENINGS:
        reply = re.sub(pat, "", reply, count=1, flags=re.IGNORECASE)
    # Banned hedging phrases — AI loves to hedge; humans commit
    HEDGE = [
        r"\b(?:it'?s (?:worth|important) (?:noting|mentioning|pointing out) that)\b",
        r"\b(?:in (?:order to|terms of))\b",
        r"\b(?:due to the fact that)\b",
        r"\b(?:with (?:regard to|respect to))\b",
        r"\b(?:at the (?:end of the day|end of the day))\b",
        r"\b(?:it goes without saying)\b",
        r"\b(?:needless to say)\b",
    ]
    for pat in HEDGE:
        reply = re.sub(pat, "", reply, flags=re.IGNORECASE)
    # Banned closings
    CLOSERS = [
        r"\s*(?:let me know if you need anything else|"
        r"I (?:hope|hope this) (?:helps|was helpful)|"
        r"don'?t hesitate to (?:reach out|ask)|"
        r"feel free to (?:ask|reach out|let me know))\.?\s*$",
    ]
    for pat in CLOSERS:
        reply = re.sub(pat, "", reply, flags=re.IGNORECASE)
    return reply.strip()


def persona_register(reply: str, persona: str) -> str:
    """Deterministic register guard, per persona. The doctor's card forbids
    exclamation marks; a local model excited by a good beat can still emit one,
    so the register is enforced here — the character never breaks voice at the
    mechanical level, no matter what the model feels like. (Sameer keeps his
    natural register; HUMAN_VOICE_RULES already caps his exclamations.)

    Also enforces persona-specific anti-AI patterns and voice consistency."""
    if persona == "script_consultant":
        reply = reply.replace("!", ".")
        # Doctor never hedges — verdict first, no softeners
        HEDGE_DOCTOR = [
            r"\b(?:I think|I feel|maybe|perhaps|it seems like|"
            r"it (?:appears|looks) (?:like|as if)|"
            r"this (?:might|could|may) be)\b",
        ]
        for pat in HEDGE_DOCTOR:
            reply = re.sub(pat, "", reply, flags=re.IGNORECASE)
        # Doctor never uses filler phrases
        FILLER_DOCTOR = [
            r"\b(?:actually|basically|honestly|frankly|to be honest)\b",
        ]
        for pat in FILLER_DOCTOR:
            reply = re.sub(pat, "", reply, flags=re.IGNORECASE)
    elif persona == "writing_partner":
        # Sameer: max one exclamation per reply (already in HUMAN_VOICE_RULES,
        # but enforce mechanically — keep only the first)
        excl_count = reply.count("!")
        if excl_count > 1:
            first = reply.index("!")
            reply = reply[:first+1] + reply[first+1:].replace("!", ".")
        # Sameer never uses AI assistant phrases
        SAMEER_BANNED = [
            r"\b(?:I'?d be happy to|Let me (?:help|assist)|"
            r"That'?s a (?:great|good|interesting) question|"
            r"I (?:understand|appreciate) your)\b",
        ]
        for pat in SAMEER_BANNED:
            reply = re.sub(pat, "", reply, flags=re.IGNORECASE)
    # Strip common AI tells from all personas
    reply = strip_anti_ai_tells(reply)
    # Apply persona-specific banned phrases
    reply = strip_banned_phrases(reply, persona)
    return reply


def normalize_quote(quote):
    """Select-to-reply passage from the webapp: {'scene_number': int|None, 'text': str}.
    scene_number None means "general" (e.g. a script-level finding with no scene
    ref). Callers (CLI, server) pass nothing — None stays None. Anything malformed
    is dropped rather than crashing the turn."""
    if not isinstance(quote, dict):
        return None
    scene_number = quote.get("scene_number")
    text = (quote.get("text") or "").strip()
    if not text:
        return None
    if scene_number is not None and not isinstance(scene_number, int):
        return None
    if scene_number is not None:
        scene_number = max(1, scene_number)
    text = text[:4000]  # a quoted passage is a snapshot; cap it defensively
    return {"scene_number": scene_number, "text": text}
