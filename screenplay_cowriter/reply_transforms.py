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


def persona_register(reply: str, persona: str) -> str:
    """Deterministic register guard, per persona. The doctor's card forbids
    exclamation marks; a local model excited by a good beat can still emit one,
    so the register is enforced here — the character never breaks voice at the
    mechanical level, no matter what the model feels like. (Sameer keeps his
    natural register; HUMAN_VOICE_RULES already caps his exclamations.)

    The register is the only thing handled here. The banned phrases — shared
    AND persona-specific — live in `persona_specs` and are applied by the
    single `strip_banned_phrases` pass below. They used to be re-implemented
    here as well (HEDGE_DOCTOR / FILLER_DOCTOR / a local SAMEER_BANNED), so
    every persona-specific phrase was applied twice per reply and the two
    copies could drift apart.
    """
    if persona == "script_consultant":
        # A replacement, not a removal: deleting the marks would leave the
        # sentence without its terminator.
        reply = reply.replace("!", ".")
    elif persona == "writing_partner":
        # Sameer: max one exclamation per reply (already in HUMAN_VOICE_RULES,
        # but enforce mechanically — keep only the first)
        if reply.count("!") > 1:
            first = reply.index("!")
            reply = reply[:first + 1] + reply[first + 1:].replace("!", ".")
    return strip_banned_phrases(reply, persona)


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
