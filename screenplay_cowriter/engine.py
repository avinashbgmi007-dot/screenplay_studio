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


def _persona_register(reply: str, persona: str) -> str:
    """Deterministic register guard, per persona. The doctor's card forbids
    exclamation marks; a local model excited by a good beat can still emit one,
    so the register is enforced here — the character never breaks voice at the
    mechanical level, no matter what the model feels like. (Sameer keeps his
    natural register; HUMAN_VOICE_RULES already caps his exclamations.)"""
    if persona == "script_consultant":
        reply = reply.replace("!", ".")
    return reply


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
                 history_window: int = HISTORY_WINDOW, store=None, memory=None, premise: dict | None = None,
                 memory_scope: str | None = None, writer_library_text: str | None = None,
                 mood_text: str | None = None, doctor_case_text: str | None = None):
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
        # Memory scope this conversation belongs to ("project:X" / "idea:Y").
        # Global writer-behavior patterns always ride along; observations
        # tagged for a DIFFERENT scope never cross into this conversation.
        self.memory_scope = memory_scope
        # The writer's past work, as a compact digest block (see
        # writer_library.py). When present it rides in every turn so Sameer /
        # the doctor can draw on earlier scripts without confusing them with
        # the current one. None by default — CLI stays byte-identical.
        self.writer_library_text = writer_library_text
        # Deterministic room state (facts from real project data) and the
        # doctor's cross-project case file. Both optional; build_system_prompt
        # routes the case file to the script_consultant persona only. None by
        # default — CLI byte-identical.
        self.mood_text = mood_text
        self.doctor_case_text = doctor_case_text

    def _ground_reply_for_room(self, reply: str) -> str:
        """Reply-side hallucination guard, room-aware. In the idea room there
        IS no script, so any 'scene N' is hypothetical by definition — the
        guard must stay silent there or every premise discussion that mentions
        a speculative scene number gets falsely flagged as a hallucination."""
        if self.premise is not None:
            return reply
        return _ground_reply(reply, self.script_ctx)

    def _memory_entities(self) -> list:
        """Character names from the current script, used to classify refresh
        observations as project-scoped when they mention script content."""
        try:
            return list((self.script_ctx.character_presence() or {}).keys())
        except Exception:
            return []

    # Chat sampling: greedy/low-temperature generation is THE robotic-loop
    # culprit on local models. Chat turns get warm settings (analyzer keeps
    # its own conservative client config).
    CHAT_TEMPERATURE = 0.85
    CHAT_REPEAT_PENALTY = 1.15
    FEWSHOT_CHAR_BUDGET = 24000  # drop example blocks before starving history
    TRAIT_DEPTH = 6              # trait re-injection position from the end

    def _generate(self, messages, on_token=None):
        """One chat completion. With on_token, raw pieces stream to the caller
        as they arrive (the perceived-latency win for slow local models); the
        returned full RAW text feeds the exact same hygiene pipeline either
        way — streaming changes how a reply APPEARS, never what gets stored.
        Clients without chat_stream (test fakes, older callers) fall back to
        the blocking call."""
        if on_token is not None and hasattr(self.client, "chat_stream"):
            return self.client.chat_stream(messages, on_token=on_token, max_tokens=600,
                                           temperature=self.CHAT_TEMPERATURE,
                                           repeat_penalty=self.CHAT_REPEAT_PENALTY)
        return self.client.chat(messages, max_tokens=600,
                                temperature=self.CHAT_TEMPERATURE,
                                repeat_penalty=self.CHAT_REPEAT_PENALTY)

    def _assemble_messages(self, system_prompt, history, prompt_user, persona,
                           scene_block=None, quote_context=None):
        """Shared turn assembly for both probe and full paths. Order matters:
        system -> scene/quote context -> few-shot examples (budget-permitting)
        -> [history with trait reminder at fixed depth] -> user turn ->
        post-history voice reminder (last word before generation carries the
        most weight -- the SillyTavern post-history lever)."""
        from .personas import (post_history_reminder, trait_reminder,
                               persona_examples, FIRST_LINE_ANCHOR)
        messages = [{"role": "system", "content": system_prompt}]
        if scene_block:
            messages.append({"role": "system", "content": scene_block})
        if quote_context:
            messages.append({"role": "system", "content": quote_context})
        total = sum(len(m["content"]) for m in messages)
        examples = persona_examples(persona)
        if examples and total + len(examples) <= self.FEWSHOT_CHAR_BUDGET:
            messages.append({"role": "system", "content": examples})
            total += len(examples)
        hist = list(history)[-self.history_window:]
        msgs = [{"role": m.role, "content": m.content} for m in hist]
        if len(msgs) >= self.TRAIT_DEPTH:
            msgs.insert(-self.TRAIT_DEPTH + 1,
                        {"role": "system", "content": trait_reminder(persona)})
        messages.extend(msgs)
        messages.append({"role": "user", "content": prompt_user})
        anchor = ""
        if not hist:
            anchor = "\n\n" + FIRST_LINE_ANCHOR
        messages.append({"role": "system",
                         "content": post_history_reminder(persona) + anchor})
        return messages

    def send_message(self, session: Session, user_text: str, quote: dict | None = None,
                     on_token=None) -> str:
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
        # Answer-first contract: when the writer asked a DIRECT question, the
        # reply must open with the answer -- probing/redirecting first reads
        # as evasive. One short follow-up at most.
        answer_first = ""
        if turn_kind == "question":
            answer_first = (
                "\n\nANSWER FIRST: the writer asked a direct question. Open with "
                "the actual answer to THAT question -- no preamble, no redirect. "
                "After the answer, at most one short follow-up."
            )

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
        relationship_card = self.memory.card_text(scope=self.memory_scope) if self.memory is not None else None

        # Explicit 'scene N' mentions plus scenes where a named character
        # speaks — writers ask about their script by naming people, and the
        # model can only ground on text it's actually shown.
        scene_refs = resolve_referenced_scenes(user_text, self.script_ctx)
        if quote is not None and quote["scene_number"] is not None and quote["scene_number"] not in scene_refs:
            scene_refs.append(quote["scene_number"])

        quote_context = None
        if quote is not None:
            # wording follows the room: idea pages have no scenes
            source = ("their idea page" if self.premise is not None else "the script")
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
                    f"The writer selected this passage from {source} and is asking about it:\n\n"
                    f"\"{quote['text']}\"\n\n"
                    "Ground your answer in the exact words they highlighted. "
                    "You may quote it back only briefly; keep the reply plain prose."
                )

        # The passage also rides inside the user turn itself (not just a system
        # message) so no model can miss it — the question sits right under it.
        prompt_user = user_text
        if quote is not None:
            prompt_user = f'Passage from the script: \"{quote["text"]}\"\n\n{user_text}'

        # Language mirror: reply in the register the writer used (Telugu /
        # Hindi / Tenglish / Hinglish / English). Deterministic detection on
        # the CURRENT message -- writers switch mid-conversation.
        lang_note = ""
        try:
            from .language_mirror import mirror_instruction
            lang_note = mirror_instruction(user_text)
        except Exception:
            lang_note = ""  # mirroring is an enhancement, never a dependency

        if not was_pending and should_probe(user_text):
            # Phase 1: reflect + probe, no suggestions.
            system_prompt = build_system_prompt(
                self.script_ctx, self.report_ctx, branch.active_persona, branch.active_mode,
                relationship_card=relationship_card, cold_start_line=cold_start_line,
                premise=self.premise, writer_library_text=self.writer_library_text,
                mood_text=self.mood_text, doctor_case_text=self.doctor_case_text,
            ) + "\n\n" + PROBE_SYSTEM_PROMPT
            if lang_note:
                system_prompt += "\n\n" + lang_note
            # the probe path already redirects short ideas; a QUESTION that
            # reached the probe branch still deserves an answer-first note
            system_prompt += answer_first
            scene_block = build_scene_context_block(self.script_ctx, scene_refs)
            messages = self._assemble_messages(
                system_prompt, branch.messages, prompt_user, branch.active_persona,
                scene_block=scene_block, quote_context=quote_context)
            try:
                reply = clean_reply(self._generate(messages, on_token))
            except Exception:
                branch.awaiting_probe = False  # never strand the writer mid-probe
                raise
            reply = self._ground_reply_for_room(reply)
            branch.awaiting_probe = True
        else:
            system_prompt = build_system_prompt(
                self.script_ctx, self.report_ctx, branch.active_persona, branch.active_mode,
                relationship_card=relationship_card, cold_start_line=cold_start_line,
                premise=self.premise, writer_library_text=self.writer_library_text,
                mood_text=self.mood_text, doctor_case_text=self.doctor_case_text,
            )
            if lang_note:
                system_prompt += "\n\n" + lang_note
            system_prompt += answer_first
            scene_block = build_scene_context_block(self.script_ctx, scene_refs)
            messages = self._assemble_messages(
                system_prompt, branch.messages, prompt_user, branch.active_persona,
                scene_block=scene_block, quote_context=quote_context)
            reply = clean_reply(self._generate(messages, on_token))
            reply = self._ground_reply_for_room(reply)
            reply = cap_suggestions(reply)

        reply = _persona_register(reply, branch.active_persona)

        reply = ensure_forward_momentum(reply, turn_kind)

        branch.messages.append(Message(role="user", content=user_text, scene_refs=scene_refs, mode=branch.active_mode, quote=quote))
        branch.messages.append(Message(role="assistant", content=reply, mode=branch.active_mode))

        if self.store is not None:
            self.store.save(session)

        if self.memory is not None:
            recent = [m.to_dict() for m in branch.messages[-self.history_window:]]
            self.memory.maybe_refresh_async(self.client, recent, scope=self.memory_scope,
                                            entities=self._memory_entities())

        return reply
