"""
The actual chat-turn logic. Session/branch bookkeeping (fork/switch/persona)
lives in models.py and is handled directly by the CLI/server since those are
free operations that don't need a model call — this module handles only the
"send a message, get a grounded reply" turn.
"""

from .models import Session, Message
from .llm_client import LlamaServerClient
from .context import (
    ScriptContext, ReportContext, build_system_prompt, build_scene_context_block,
    resolve_referenced_scenes, SCENE_REF_RE,
)
from .language_meta import (
    strip_language_meta, strip_json_wrap, strip_repetition_lines, strip_repeated_blocks,
)

# Generation budget for chat turns. Local models that fall into a repetition
# loop would otherwise burn the full budget on garbage (minutes of waiting);
# 600 tokens is comfortably above any reply this app has produced while
# capping the damage a loop can do. (The refresh path keeps the client's
# larger default — its JSON needs room.)

# llama.cpp's default repeat_penalty (1.1) lets this class of local model
# loop, re-answering the same point several times in one reply. 1.3 is
# high enough to break the loop without dulling genuine variety.
REPEAT_PENALTY = 1.3

HISTORY_WINDOW = 16  # most recent messages kept verbatim; older context relies on the standing report summary


def clean_reply(raw: str) -> str:
    """Reply hygiene pipeline, outermost-raw to innermost-clean:
    unwrap accidental JSON wrappers, drop separator/tag garbage, collapse
    semantic repetition blocks, then strip language meta-commentary."""
    return strip_language_meta(
        strip_repeated_blocks(strip_repetition_lines(strip_json_wrap(raw)))
    )


def _ground_reply(reply: str, script_ctx: ScriptContext) -> str:
    """Reply-side hallucination guard. If the reply references a scene number
    that doesn't exist in the script, own it honestly instead of letting the
    invented scene stand — a real co-writer caught reaching for a page they
    don't have would say so. Cheap and safe: only flags numbers outside the
    script's actual scene set, so genuine references pass untouched."""
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


def _normalize_quote(quote):
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


class CoWriterEngine:
    def __init__(self, client: LlamaServerClient, script_ctx: ScriptContext, report_ctx: ReportContext,
                 history_window: int = HISTORY_WINDOW, store=None, memory=None, premise: dict | None = None):
        self.client = client
        self.script_ctx = script_ctx
        self.report_ctx = report_ctx
        self.history_window = history_window
        # Idea room: a premise card instead of a script. When present, the
        # system prompt switches to idea framing (no pages, no report) and the
        # card rides in every turn as the shared, growing material.
        self.premise = premise
        # Optional persistence hook. send_message saves the session itself
        # after a successful turn, so a caller can't forget to persist the
        # conversation on some error path. Callers may still save explicitly
        # (idempotent — same content, harmless double-write).
        self.store = store
        # Optional writer relationship memory. When present, send_message
        # observes each turn and injects the relationship card into the
        # system prompt (both probe and full-turn paths).
        self.memory = memory

    def send_message(self, session: Session, user_text: str, quote: dict | None = None) -> str:
        from .peer import (
            classify_turn, should_probe, PROBE_SYSTEM_PROMPT,
            ensure_forward_momentum, cap_suggestions,
        )
        branch = session.branch
        user_text = (user_text or "").strip()
        turn_kind = classify_turn(user_text)

        # Select-to-reply: the writer highlighted a passage of the script and
        # asked about it. Normalize the shape so callers can't inject junk, and
        # make sure the quoted scene is pulled into context even if the free
        # text doesn't mention it by number.
        quote = _normalize_quote(quote)

        # A pending probe is resolved by whatever comes next: an idea is the
        # answer to it, a question/directive is a topic change. Either way the
        # flag clears — and we must NOT re-probe the writer who just answered
        # (capturing was_pending BEFORE clearing prevents that loop).
        was_pending = branch.awaiting_probe
        if was_pending:
            branch.awaiting_probe = False

        if self.memory is not None:
            # Capture the cold-start line BEFORE observe(): observe bumps
            # total_turns_observed, which would otherwise kill it on turn 1.
            cold_start_line = self.memory.cold_start_line() if not branch.messages else None
            prev_reply = branch.messages[-1].content if (was_pending and branch.messages) else None
            self.memory.observe(user_text, turn_kind, was_pending, prev_reply)
        else:
            cold_start_line = None
        relationship_card = self.memory.card_text() if self.memory is not None else None

        # Explicit 'scene N' mentions plus scenes where a named character
        # speaks — writers ask about their script by naming people, and the
        # model can only ground on text it's actually shown.
        scene_refs = resolve_referenced_scenes(user_text, self.script_ctx)
        if quote is not None and quote["scene_number"] is not None and quote["scene_number"] not in scene_refs:
            scene_refs.append(quote["scene_number"])

        quote_context = None
        if quote is not None:
            if quote["scene_number"] is not None:
                quote_context = (
                    "The writer selected this passage from Scene "
                    f"{quote['scene_number']} and is asking about it:\n\n"
                    f"\"{quote['text']}\"\n\n"
                    "Ground your answer in the exact moment the passage describes. "
                    "You may quote it back only briefly; keep the reply plain prose."
                )
            else:
                quote_context = (
                    "The writer selected this passage from the script and is asking about it:\n\n"
                    f"\"{quote['text']}\"\n\n"
                    "Ground your answer in the exact passage. "
                    "You may quote it back only briefly; keep the reply plain prose."
                )

        # The passage also rides inside the user turn itself (not just a system
        # message) so no model can miss it — the question sits right under it.
        prompt_user = user_text
        if quote is not None:
            prompt_user = f'Passage from the script: \"{quote["text"]}\"\n\n{user_text}'

        if not was_pending and should_probe(user_text):
            # Phase 1: reflect + probe, no suggestions.
            system_prompt = build_system_prompt(
                self.script_ctx, self.report_ctx, branch.active_persona, branch.active_mode,
                relationship_card=relationship_card, cold_start_line=cold_start_line,
                premise=self.premise,
            ) + "\n\n" + PROBE_SYSTEM_PROMPT
            scene_block = build_scene_context_block(self.script_ctx, scene_refs)
            messages = [{"role": "system", "content": system_prompt}]
            if scene_block:
                messages.append({"role": "system", "content": scene_block})
            if quote_context:
                messages.append({"role": "system", "content": quote_context})
            for m in branch.messages[-self.history_window:]:
                messages.append({"role": m.role, "content": m.content})
            messages.append({"role": "user", "content": prompt_user})
            try:
                reply = clean_reply(self.client.chat(messages, max_tokens=600, repeat_penalty=REPEAT_PENALTY))
            except Exception:
                branch.awaiting_probe = False  # never strand the writer mid-probe
                raise
            reply = _ground_reply(reply, self.script_ctx)
            branch.awaiting_probe = True
        else:
            system_prompt = build_system_prompt(
                self.script_ctx, self.report_ctx, branch.active_persona, branch.active_mode,
                relationship_card=relationship_card, cold_start_line=cold_start_line,
                premise=self.premise,
            )
            scene_block = build_scene_context_block(self.script_ctx, scene_refs)
            messages = [{"role": "system", "content": system_prompt}]
            if scene_block:
                messages.append({"role": "system", "content": scene_block})
            if quote_context:
                messages.append({"role": "system", "content": quote_context})
            for m in branch.messages[-self.history_window:]:
                messages.append({"role": m.role, "content": m.content})
            messages.append({"role": "user", "content": prompt_user})
            reply = clean_reply(self.client.chat(messages, max_tokens=600, repeat_penalty=REPEAT_PENALTY))
            reply = _ground_reply(reply, self.script_ctx)
            reply = cap_suggestions(reply)

        reply = ensure_forward_momentum(reply, turn_kind)

        branch.messages.append(Message(role="user", content=user_text, scene_refs=scene_refs, mode=branch.active_mode, quote=quote))
        branch.messages.append(Message(role="assistant", content=reply, mode=branch.active_mode))

        if self.store is not None:
            self.store.save(session)

        if self.memory is not None:
            recent = [m.to_dict() for m in branch.messages[-self.history_window:]]
            self.memory.maybe_refresh_async(self.client, recent)

        return reply
