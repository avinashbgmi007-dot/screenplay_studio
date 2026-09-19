"""
The actual chat-turn logic. Session/branch bookkeeping (fork/switch/persona)
lives in models.py and is handled directly by the CLI/server since those are
free operations that don't need a model call — this module handles only the
"send a message, get a grounded reply" turn.
"""

import re

from .models import Session, Message
from .llm_client import LlamaServerClient
from .personas import DOCTOR_PERSONA
from .context import (
    ScriptContext, ReportContext, build_system_prompt, build_scene_context_block,
    resolve_referenced_scenes,
)
from .reply_transforms import (
    clean_reply, ground_reply, persona_register, normalize_quote,
    verify_reply_quotes,
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


def _resolve_prompt_block(value):
    """A prompt block may be given as text or as a zero-arg callable.

    The callable form exists so the server can defer its cross-project shelf
    scan (the writer's past-work digest and the doctor's case file) to the
    moment a prompt is actually built — loading a session, switching a branch
    or deleting a chat never generates, so it must never pay for a digest it
    will not use. Resolving here, on the one path that builds a prompt, also
    means no caller can forget to pass one: a caller that omits it would
    otherwise silently strip the co-writer's memory of the writer's shelf.

    A provider that raises yields None. These blocks are context, never a
    dependency, and an unreadable shelf must not break the chat.
    """
    if value is None or isinstance(value, str):
        return value
    try:
        return value()
    except Exception:
        return None


def _resolve_prompt_budget(value):
    """The prompt budget for a turn: an int, or None to use the module default.

    Accepts a number or a zero-arg callable, for the same reason the context
    blocks do — the server derives the budget from the model's reported context
    window, and that probe must not run for a request that never builds a prompt
    (loading a session, switching a branch, deleting a chat).

    Degrades to None on a provider that raises or reports no window, so the
    caller falls back to PROMPT_CHAR_BUDGET rather than silently losing the
    budget altogether. An int is clamped at 0, which build_system_prompt reads
    as "unlimited".
    """
    if value is None:
        return None
    if callable(value):
        try:
            value = value()
        except Exception:
            return None
    if value is None:
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None

# ---------------------------------------------------------------------------
# Voice drift (review section 7, P1.7).
#
# The old detector counted AI tells, kept a PROCESS-GLOBAL history, and logged a
# warning. Two problems, and the second is the one the review named: it never
# ACTED — a log line nobody reads changes nothing — and the global meant two open
# projects shared one drift history, so neither was measured against its own
# conversation.
#
# Split into two pure functions plus per-engine state: the thresholds are now
# testable without constructing an engine, and the history belongs to the
# conversation that produced it.
# ---------------------------------------------------------------------------
VOICE_DRIFT_WINDOW = 5         # replies compared at each end of the history
VOICE_DRIFT_MIN_HISTORY = 10   # below this there is no "early" to compare against
VOICE_DRIFT_MARGIN = 1.0       # tells per reply the recent end must exceed
VOICE_DRIFT_HISTORY_MAX = 20   # replies remembered per persona

_AI_TELL_PATTERNS = (
    (1, re.compile(r"\b(?:I think|I feel|maybe|perhaps|it seems like)\b", re.IGNORECASE)),
    (1, re.compile(r"\b(?:actually|basically|honestly|frankly)\b", re.IGNORECASE)),
    (2, re.compile(r"^(?:Great question|Absolutely|I'?d be happy to)", re.IGNORECASE)),
    (2, re.compile(r"(?:let me know if you need anything else|I hope this helps)\s*$",
                   re.IGNORECASE)),
)


def count_ai_tells(reply: str) -> int:
    """How many AI tells this reply carries. Deterministic; no model call.

    Weighted: a canned opening or closing is worth two, because either is a whole
    register slip rather than a word choice.
    """
    return sum(weight for weight, pattern in _AI_TELL_PATTERNS
               if pattern.search(reply or ""))


def voice_drift_crossed(history) -> bool:
    """True when the recent replies carry materially more tells than the early
    ones — the slow slide the persona examples exist to prevent.

    Compares the two ENDS of the history rather than a running average: a persona
    that always hedges a little is not drifting, and one that starts clean and
    ends hedging is, even when the mean barely moves.
    """
    if len(history) < VOICE_DRIFT_MIN_HISTORY:
        return False
    recent = sum(history[-VOICE_DRIFT_WINDOW:]) / VOICE_DRIFT_WINDOW
    early = sum(history[:VOICE_DRIFT_WINDOW]) / VOICE_DRIFT_WINDOW
    return recent > early + VOICE_DRIFT_MARGIN


class CoWriterEngine:
    def __init__(self, client: LlamaServerClient, script_ctx: ScriptContext, report_ctx: ReportContext,
                 history_window: int = HISTORY_WINDOW, store=None, memory=None, premise: dict | None = None,
                 memory_scope: str | None = None, writer_library_text: str | None = None,
                 mood_text: str | None = None, doctor_case_text: str | None = None,
                 craft_history_text: str | None = None,
                 prompt_budget: int | None = None):
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
        # Accepts a string or a zero-arg provider (see _resolve_prompt_block);
        # the server passes a provider so the shelf scan is deferred.
        self.writer_library_text = writer_library_text
        # Deterministic room state (facts from real project data) and the
        # doctor's cross-project case file. Both optional; build_system_prompt
        # routes the case file to the script_consultant persona only. None by
        # default — CLI byte-identical. The case file likewise accepts a
        # provider; it is resolved only for the persona that reads it.
        self.mood_text = mood_text
        self.doctor_case_text = doctor_case_text
        # The writer's own edit history on THIS script (see craft_history.py).
        # The relationship card learns how the writer works but is forbidden to
        # quote itself; this is the one class of reference the review permits
        # (P2.8), and it is sourced from the revision log rather than from
        # memory. Also accepts a provider — the edit-log read is deferred to
        # the turn that actually builds a prompt.
        self.craft_history_text = craft_history_text
        # Global prompt budget (M1). None lets build_system_prompt apply its
        # own default; the server passes a provider that derives the budget
        # from the model's reported context window, so it is resolved on the
        # one path that builds a prompt. See _resolve_prompt_budget.
        self.prompt_budget = prompt_budget
        # Voice drift, per CONVERSATION (P1.7). These used to be a module-level
        # dict shared by every engine in the process, so two open projects fed one
        # history and neither was measured against its own replies.
        self._tell_history: dict = {}      # persona -> list of per-reply tell counts
        self._voice_reprime: set = set()   # personas whose next turn gets the re-prime

    # -- voice drift -------------------------------------------------------

    def voice_reprime_pending(self, persona: str) -> bool:
        """Whether the next turn for `persona` should carry the drift re-prime."""
        return persona in self._voice_reprime

    def _note_voice_tells(self, reply: str, persona: str) -> bool:
        """Record this reply's AI-tell count; arm a re-prime if the trend crossed.

        Returns whether it armed. This is where the detector ACTS: it used to log
        a warning and return the reply untouched (P1.7). The re-prime rides the
        turn AFTER the slide is visible, because the history is only complete once
        this reply is counted.
        """
        history = self._tell_history.setdefault(persona, [])
        history.append(count_ai_tells(reply))
        del history[:-VOICE_DRIFT_HISTORY_MAX]
        if voice_drift_crossed(history):
            self._voice_reprime.add(persona)
            return True
        return False

    def _consume_voice_reprime(self, persona: str) -> None:
        """Clear the armed re-prime once it has ridden a turn. If the drift is
        still there, the next reply re-arms it — the detector governs, so this
        cannot become a permanent nag on its own."""
        self._voice_reprime.discard(persona)

    def _ground_reply_for_room(self, reply: str) -> str:
        """Reply-side hallucination guard, room-aware. In the idea room there
        IS no script, so any 'scene N' is hypothetical by definition — the
        guard must stay silent there or every premise discussion that mentions
        a speculative scene number gets falsely flagged as a hallucination."""
        if self.premise is not None:
            return reply
        return ground_reply(reply, self.script_ctx)

    def _guard_reply(self, reply: str, scene_refs=None) -> str:
        """The reply-side honesty guards, applied to the MODEL's output only.

        Quote verification runs first so it never scans a note the scene-number
        guard appended, and vice versa — each guard judges the model, not the
        other guard. (Both filters are narrow enough that a cross-read would be
        harmless, but relying on that would be luck.)

        `scene_refs` is the material injected into this turn; quote verification
        bounds its fuzzy pass to those scenes. Quote verification needs no room
        check of its own: with no scenes it returns the reply untouched, which is
        exactly the idea-room behaviour.
        """
        return self._ground_reply_for_room(
            verify_reply_quotes(reply, self.script_ctx, scene_refs)
        )

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

    def _generate_mirrored(self, messages, user_text, on_token=None):
        """One generation, plus at most ONE soft re-ask when the reply dropped
        the writer's script register (P2.9).

        Bounded on every side, because each of these is a way the retry could
        cost more than it buys:

          * It fires only on the exact Unicode-block case (`register_mismatch`
            refuses the fuzzy Latin-mix half — see `language_mirror`).
          * The re-ask is NOT streamed. The writer's bubble is already showing
            the first reply's tokens; streaming a second reply would append it
            to the first and read as a glitch. The caller re-renders from the
            final stored messages, so the swap is clean.
          * The re-ask is accepted only when it ACTUALLY carries the register.
            A retry that does no better is discarded and the first reply kept —
            the retry can never cost the writer the answer they already had,
            and a model that will not mirror cannot make things worse by being
            asked twice.
          * A failed re-ask is swallowed for the same reason. The first
            generation's own exception still propagates untouched.
        """
        from .language_mirror import mirror_reask_instruction, register_mismatch

        reply = clean_reply(self._generate(messages, on_token))
        if register_mismatch(user_text, reply) is None:
            return reply
        note = mirror_reask_instruction(user_text)
        if not note:
            return reply
        try:
            retry = clean_reply(self._generate(messages + [{"role": "user", "content": note}]))
        except Exception:
            return reply
        if register_mismatch(user_text, retry) is not None:
            return reply
        return retry

    def _assemble_messages(self, system_prompt, history, prompt_user, persona,
                           scene_block=None, quote_context=None, reprime=False):
        """Shared turn assembly for both probe and full paths. Order matters:
        system -> scene/quote context -> few-shot examples (budget-permitting)
        -> [history with trait reminder at fixed depth] -> user turn ->
        post-history voice reminder (last word before generation carries the
        most weight -- the SillyTavern post-history lever).

        `reprime=True` swaps that closing reminder for the drift re-prime, which
        is how the voice-drift detector acts instead of only logging (P1.7).

        SINGLE-SYSTEM CONTRACT (H7a): some llama-server builds return HTTP 500
        on any payload carrying two or more `system` messages, and this build is
        one of them (verified live). The analyzer works because it sends exactly
        one system + one user. So the co-writer sends at most ONE system message:
        the persona system prompt. The scene block, quote context, and few-shot
        examples are folded INTO that system text; the mid-history trait reminder
        and the post-history voice reminder ride as USER-role bracketed notes
        (same position, same weight, no extra system role)."""
        from .personas import (post_history_reminder, trait_reminder,
                               persona_examples, FIRST_LINE_ANCHOR)
        # Fold every context block into the single system prompt's text.
        system_text = system_prompt
        if scene_block:
            system_text += "\n\n" + scene_block
        if quote_context:
            system_text += "\n\n" + quote_context
        total = len(system_text)
        examples = persona_examples(persona)
        if examples and total + len(examples) <= self.FEWSHOT_CHAR_BUDGET:
            system_text += "\n\n" + examples
            total += len(examples)
        messages = [{"role": "system", "content": system_text}]
        hist = list(history)[-self.history_window:]
        msgs = [{"role": m.role, "content": m.content} for m in hist]
        if len(msgs) >= self.TRAIT_DEPTH:
            # user-role so we never add a second system message
            msgs.insert(-self.TRAIT_DEPTH + 1,
                        {"role": "user", "content": trait_reminder(persona)})
        messages.extend(msgs)
        messages.append({"role": "user", "content": prompt_user})
        anchor = ""
        if not hist:
            anchor = "\n\n" + FIRST_LINE_ANCHOR
        # post-history voice reminder: last word before generation, as a user
        # note (was a second system message — the H7a 500 trigger).
        messages.append({"role": "user",
                         "content": post_history_reminder(persona, reprime=reprime) + anchor})
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
        # P1.7: armed by a previous reply's tell trend; rides exactly one turn.
        reprime_now = self.voice_reprime_pending(branch.active_persona)

        # Select-to-reply: the writer highlighted a passage of the script and
        # asked about it. Normalize the shape so callers can't inject junk, and
        # make sure the quoted scene is pulled into context even if the free
        # text doesn't mention it by number.
        quote = normalize_quote(quote)

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

        # Resolve the deferred shelf blocks once per turn — and only for the
        # persona that actually reads each one. The case file is the doctor's
        # lens alone, so building it for the other seven personas is a
        # cross-project scan whose output build_system_prompt would discard.
        writer_library_text = _resolve_prompt_block(self.writer_library_text)
        # Deferred for the same reason as the shelf blocks, and read once per
        # turn: the edit log is per-project and cannot go stale within a turn.
        craft_history_text = _resolve_prompt_block(self.craft_history_text)
        doctor_case_text = (
            _resolve_prompt_block(self.doctor_case_text)
            if branch.active_persona == DOCTOR_PERSONA else None
        )
        # The prompt budget, resolved once per turn. Deferred for the same
        # reason as the shelf blocks: the server derives it from the model's
        # reported context window, and a request that never builds a prompt
        # must not pay for that probe.
        prompt_budget = _resolve_prompt_budget(self.prompt_budget)

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
                premise=self.premise, writer_library_text=writer_library_text,
                mood_text=self.mood_text, doctor_case_text=doctor_case_text,
                craft_history_text=craft_history_text,
                budget=prompt_budget,
            ) + "\n\n" + PROBE_SYSTEM_PROMPT
            if lang_note:
                system_prompt += "\n\n" + lang_note
            # the probe path already redirects short ideas; a QUESTION that
            # reached the probe branch still deserves an answer-first note
            system_prompt += answer_first
            scene_block = build_scene_context_block(self.script_ctx, scene_refs)
            messages = self._assemble_messages(
                system_prompt, branch.messages, prompt_user, branch.active_persona,
                scene_block=scene_block, quote_context=quote_context, reprime=reprime_now)
            try:
                reply = self._generate_mirrored(messages, user_text, on_token)
            except Exception:
                branch.awaiting_probe = False  # never strand the writer mid-probe
                raise
            reply = self._guard_reply(reply, scene_refs)
            branch.awaiting_probe = True
        else:
            system_prompt = build_system_prompt(
                self.script_ctx, self.report_ctx, branch.active_persona, branch.active_mode,
                relationship_card=relationship_card, cold_start_line=cold_start_line,
                premise=self.premise, writer_library_text=writer_library_text,
                mood_text=self.mood_text, doctor_case_text=doctor_case_text,
                craft_history_text=craft_history_text,
                budget=prompt_budget,
            )
            if lang_note:
                system_prompt += "\n\n" + lang_note
            system_prompt += answer_first
            scene_block = build_scene_context_block(self.script_ctx, scene_refs)
            messages = self._assemble_messages(
                system_prompt, branch.messages, prompt_user, branch.active_persona,
                scene_block=scene_block, quote_context=quote_context, reprime=reprime_now)
            reply = self._generate_mirrored(messages, user_text, on_token)
            reply = self._guard_reply(reply, scene_refs)
            reply = cap_suggestions(reply)

        reply = persona_register(reply, branch.active_persona)
        # P1.7: consume the re-prime that just rode this turn, then count this
        # reply and arm the next one if the trend has crossed. Order matters: the
        # history is only complete once this reply is counted.
        self._consume_voice_reprime(branch.active_persona)
        self._note_voice_tells(reply, branch.active_persona)

        reply = ensure_forward_momentum(reply, turn_kind, branch.active_persona)

        branch.messages.append(Message(role="user", content=user_text, scene_refs=scene_refs, mode=branch.active_mode, quote=quote, partner=branch.active_persona))
        branch.messages.append(Message(role="assistant", content=reply, mode=branch.active_mode, partner=branch.active_persona))

        if self.store is not None:
            self.store.save(session)

        if self.memory is not None:
            recent = [m.to_dict() for m in branch.messages[-self.history_window:]]
            self.memory.maybe_refresh_async(self.client, recent, scope=self.memory_scope,
                                            entities=self._memory_entities())

        return reply
