"""
The actual chat-turn logic. Session/branch bookkeeping (fork/switch/persona)
lives in models.py and is handled directly by the CLI/server since those are
free operations that don't need a model call — this module handles only the
"send a message, get a grounded reply" turn.
"""

from .models import Session, Message
from .llm_client import LlamaServerClient
from .context import ScriptContext, ReportContext, build_system_prompt, build_scene_context_block, extract_scene_refs
from .language_meta import strip_language_meta

HISTORY_WINDOW = 16  # most recent messages kept verbatim; older context relies on the standing report summary


class CoWriterEngine:
    def __init__(self, client: LlamaServerClient, script_ctx: ScriptContext, report_ctx: ReportContext,
                 history_window: int = HISTORY_WINDOW, store=None):
        self.client = client
        self.script_ctx = script_ctx
        self.report_ctx = report_ctx
        self.history_window = history_window
        # Optional persistence hook. send_message saves the session itself
        # after a successful turn, so a caller can't forget to persist the
        # conversation on some error path. Callers may still save explicitly
        # (idempotent — same content, harmless double-write).
        self.store = store

    def send_message(self, session: Session, user_text: str) -> str:
        from .peer import (
            classify_turn, should_probe, PROBE_SYSTEM_PROMPT,
            ensure_forward_momentum, cap_suggestions,
        )
        branch = session.branch
        user_text = (user_text or "").strip()
        turn_kind = classify_turn(user_text)

        # A pending probe is resolved by whatever comes next: an idea is the
        # answer to it, a question/directive is a topic change. Either way the
        # flag clears — and we must NOT re-probe the writer who just answered
        # (capturing was_pending BEFORE clearing prevents that loop).
        was_pending = branch.awaiting_probe
        if was_pending:
            branch.awaiting_probe = False

        scene_refs = extract_scene_refs(user_text)

        if not was_pending and should_probe(user_text):
            # Phase 1: reflect + probe, no suggestions.
            system_prompt = build_system_prompt(
                self.script_ctx, self.report_ctx, branch.active_persona, branch.active_mode
            ) + "\n\n" + PROBE_SYSTEM_PROMPT
            scene_block = build_scene_context_block(self.script_ctx, scene_refs)
            messages = [{"role": "system", "content": system_prompt}]
            if scene_block:
                messages.append({"role": "system", "content": scene_block})
            for m in branch.messages[-self.history_window:]:
                messages.append({"role": m.role, "content": m.content})
            messages.append({"role": "user", "content": user_text})
            try:
                reply = strip_language_meta(self.client.chat(messages))
            except Exception:
                branch.awaiting_probe = False  # never strand the writer mid-probe
                raise
            branch.awaiting_probe = True
        else:
            system_prompt = build_system_prompt(
                self.script_ctx, self.report_ctx, branch.active_persona, branch.active_mode
            )
            scene_block = build_scene_context_block(self.script_ctx, scene_refs)
            messages = [{"role": "system", "content": system_prompt}]
            if scene_block:
                messages.append({"role": "system", "content": scene_block})
            for m in branch.messages[-self.history_window:]:
                messages.append({"role": m.role, "content": m.content})
            messages.append({"role": "user", "content": user_text})
            reply = strip_language_meta(self.client.chat(messages))
            reply = cap_suggestions(reply)

        reply = ensure_forward_momentum(reply, turn_kind)

        branch.messages.append(Message(role="user", content=user_text, scene_refs=scene_refs, mode=branch.active_mode))
        branch.messages.append(Message(role="assistant", content=reply, mode=branch.active_mode))

        if self.store is not None:
            self.store.save(session)

        return reply
