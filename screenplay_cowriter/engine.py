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
                 history_window: int = HISTORY_WINDOW):
        self.client = client
        self.script_ctx = script_ctx
        self.report_ctx = report_ctx
        self.history_window = history_window

    def send_message(self, session: Session, user_text: str) -> str:
        branch = session.branch

        scene_refs = extract_scene_refs(user_text)
        system_prompt = build_system_prompt(self.script_ctx, self.report_ctx, branch.active_persona, branch.active_mode)
        scene_block = build_scene_context_block(self.script_ctx, scene_refs)

        messages = [{"role": "system", "content": system_prompt}]
        if scene_block:
            messages.append({"role": "system", "content": scene_block})

        for m in branch.messages[-self.history_window:]:
            messages.append({"role": m.role, "content": m.content})

        messages.append({"role": "user", "content": user_text})

        reply = strip_language_meta(self.client.chat(messages))

        branch.messages.append(Message(role="user", content=user_text, scene_refs=scene_refs, mode=branch.active_mode))
        branch.messages.append(Message(role="assistant", content=reply, mode=branch.active_mode))

        return reply
