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


# A quoted span is only worth verifying when it is long enough to be a script
# line rather than a conversational aside. Measured on the replies the gun_pen
# audit captured from a real model: the doctor's craft term "on-the-nose" is 1
# word (noise), while the genuine Telugu line it also quoted is 4. The analyzer's
# verifier uses <3 words as its floor for a DECLARED quote (a finding's
# evidence_quote field, which is always meant as script text); free prose needs a
# higher bar, because most quoted spans in a conversation are not script text at
# all. Missing a short genuine quote costs nothing — it is simply not verified.
MIN_QUOTED_WORDS = 4

# A reply that quotes a dozen things is not worth a dozen script scans. The
# first few are enough to make the point, and the guard only ever reports one.
MAX_QUOTED_SPANS = 8

# Curly or straight, closing quote required. Single quotes are deliberately NOT
# matched: apostrophes make them ambiguous in English prose.
_QUOTED_SPAN_RE = re.compile(r'[“"]([^”"]{2,400})[”"]')

# Opening of the flag this guard appends. Used to make the guard idempotent: the
# flag quotes the very wording it could not verify, so a second pass would find
# that quote, fail it again, and stack a second note on the first. The guard runs
# once per turn today, but a guard that corrupts its own output on re-entry is a
# trap for whoever adds a retry path later.
_QUOTE_FLAG_MARK = "(One honest flag: I quoted"


def _script_haystack(script_ctx, scene_numbers=None) -> str:
    """Element text of the script — all of it, or just the given scenes.

    Joined with a SPACE rather than a newline: scene text is stored
    line-wrapped (one element per wrapped line), so a quote that spans a wrap
    must still be findable.
    """
    scenes = script_ctx.data.get("scenes") or []
    if scene_numbers is not None:
        wanted = set(scene_numbers)
        scenes = [s for s in scenes if s.get("scene_number") in wanted]
    return " ".join(
        (el.get("text") or "") for s in scenes for el in (s.get("elements") or [])
    )


def verify_reply_quotes(reply: str, script_ctx, scene_numbers=None) -> str:
    """Reply-side quote guard: when the co-writer quotes the script, check that
    the wording is actually there, and say so if it isn't.

    Reuses the analyzer's verifier — its normaliser and its fuzzy threshold —
    rather than growing a second matcher of its own. That is the whole point.
    A naive substring test fails on a quote that spans a line wrap, and on one
    the model typed with straight quotes where the script has curly ones, which
    is exactly the defect that made the analyzer report an entire dialogue
    category as "addressed" on a script nobody had edited. One matcher, one
    answer.

    Two passes, because the cheap one is exact and the expensive one is not:

      * CONTAINMENT against the WHOLE script, under the verifier's normaliser.
        Linear, and it already absorbs the curly/straight and line-wrap
        differences, so it settles the overwhelming majority of genuine quotes
        wherever they come from in the script.
      * FUZZY, bounded to `scene_numbers` — the scenes actually injected into
        this turn, i.e. the material the model was shown. The verifier's sliding
        window is generous by design (it exists to avoid accusing the analyzer of
        hallucinating over a near-miss), but it is O(script): measured at ~900 ms
        for a 120-scene script and ~1.8 s for a 180-scene one. Bounding it to the
        injected scenes keeps that generosity where it can actually apply and
        costs tens of milliseconds instead.

    Flags, never rewrites: an unverifiable quote is stated, not deleted, and the
    reply body is untouched — the same "flag, don't silently drop" policy the
    verifier applies to findings.

    Stays silent when it cannot be sure: no script (the idea room has no pages,
    so every quote there is hypothetical by definition), no quoted span, or a
    verifier that will not import. A guard that cannot run must not guess.
    """
    if script_ctx is None:
        return reply
    if not (script_ctx.data.get("scenes") or []):
        return reply
    if _QUOTE_FLAG_MARK in reply:
        return reply  # already flagged this reply once — see _QUOTE_FLAG_MARK
    spans = _QUOTED_SPAN_RE.findall(reply)
    if not spans:
        return reply

    try:
        from screenplay_analyzer.verifier import (
            FUZZY_MATCH_THRESHOLD, _best_fuzzy_match, _normalize,
        )
    except Exception:
        return reply  # the guard is an enhancement, never a dependency

    whole = _normalize(_script_haystack(script_ctx))
    if not whole:
        return reply
    shown = _normalize(_script_haystack(script_ctx, scene_numbers)) if scene_numbers else ""

    unverified = []
    for span in spans[:MAX_QUOTED_SPANS]:
        quoted = _normalize(span)
        if len(quoted.split()) < MIN_QUOTED_WORDS:
            continue
        if quoted in whole:
            continue
        if shown and _best_fuzzy_match(quoted, shown) >= FUZZY_MATCH_THRESHOLD:
            continue
        unverified.append(span.strip())

    if not unverified:
        return reply

    first = unverified[0]
    shown_quote = first if len(first) <= 80 else first[:77].rstrip() + "…"
    others = "" if len(unverified) == 1 else f" (and {len(unverified) - 1} more)"
    return (
        f"{reply.rstrip()}\n\n(One honest flag: I quoted \"{shown_quote}\"{others} — I "
        "can't find that wording in the pages I'm holding. If it's a paraphrase, "
        "or it came from somewhere else, ignore me; if it should be in the "
        "script, point me at the scene.)"
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
