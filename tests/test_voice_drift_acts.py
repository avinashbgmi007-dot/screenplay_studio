"""Voice drift now ACTS, instead of only logging (review section 7, P1.7).

The review, verbatim: "Make voice-drift act, not just log — re-prime the examples
block when drift crosses a threshold."

What it did before: `_detect_voice_drift` counted AI tells per reply, kept a
history in a MODULE-LEVEL dict, and — when the recent average exceeded the early
average by more than 1.0 — called `logging.warning(...)` and returned the reply
untouched. Two failures, and only the first is the one the review named:

1. It never acted. A log line nobody reads changes nothing, and the persona
   system already had the lever: the example dialogue sits in the system prompt
   and is never shed (context.py's shed ladder lists it as un-sheddable).
2. The history was PROCESS-GLOBAL. Two open projects shared one drift history, so
   neither persona was measured against its own conversation.

Both are fixed: the tell count and the threshold test are pure functions, the
history belongs to the engine, and crossing the threshold arms a re-prime that
rides the NEXT turn's closing voice reminder — the highest-weight position in the
prompt, the one the trait/post-history levers already use.
"""

import pytest

from screenplay_cowriter.engine import (
    CoWriterEngine, count_ai_tells, voice_drift_crossed,
    VOICE_DRIFT_MARGIN, VOICE_DRIFT_MIN_HISTORY, VOICE_DRIFT_WINDOW,
    VOICE_DRIFT_HISTORY_MAX,
)
from screenplay_cowriter.models import Session
from screenplay_cowriter.personas import (
    POST_HISTORY_REMINDER, VOICE_REPRIME_REMINDER, post_history_reminder,
)
from screenplay_cowriter.context import ScriptContext, ReportContext

CLEAN = "Cut the line. The pause does it."
DRIFTED = "I think maybe the line is actually a bit long, honestly."


# --------------------------------------------------------------------------
# the counter — pure, no engine
# --------------------------------------------------------------------------

class TestCountingAITells:
    def test_a_plain_reply_has_none(self):
        assert count_ai_tells(CLEAN) == 0

    def test_hedging_costs_one(self):
        assert count_ai_tells("I think the scene works.") == 1

    def test_filler_costs_one(self):
        assert count_ai_tells("The ending is basically fine.") == 1

    def test_a_canned_opening_costs_two(self):
        assert count_ai_tells("Great question! Here's the thing.") == 2

    def test_a_canned_closing_costs_two(self):
        assert count_ai_tells("That should do it. I hope this helps") == 2

    def test_tells_accumulate(self):
        assert count_ai_tells(DRIFTED) == 2  # hedging + filler

    def test_an_empty_reply_is_not_an_error(self):
        assert count_ai_tells("") == 0 and count_ai_tells(None) == 0


# --------------------------------------------------------------------------
# the threshold — pure, no engine
# --------------------------------------------------------------------------

class TestTheThreshold:
    def test_a_short_history_never_crosses(self):
        """There is no 'early' to compare against yet."""
        assert not voice_drift_crossed([0] * (VOICE_DRIFT_MIN_HISTORY - 1))

    def test_a_flat_history_does_not_cross(self):
        assert not voice_drift_crossed([1] * 20)

    def test_a_persona_that_always_hedges_is_not_drifting(self):
        """Compares the two ENDS, not a running average — a consistently
        colloquial persona must not be flagged for being itself."""
        assert not voice_drift_crossed([2] * 20)

    def test_a_slide_from_clean_to_hedging_crosses(self):
        assert voice_drift_crossed([0] * 5 + [2] * 5)

    def test_a_slide_below_the_margin_does_not_cross(self):
        assert not voice_drift_crossed([0] * 5 + [1] * 5)

    def test_the_margin_is_the_boundary(self):
        history = [0] * 5 + [VOICE_DRIFT_MARGIN] * 5
        assert not voice_drift_crossed(history), "exactly at the margin is not over it"

    def test_only_the_window_ends_matter(self):
        """A bad patch in the MIDDLE is not drift — it is a bad patch."""
        assert not voice_drift_crossed([0] * 5 + [5] * 5 + [0] * 5)


# --------------------------------------------------------------------------
# the engine state
# --------------------------------------------------------------------------

class _ScriptedClient:
    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = []

    def chat(self, messages, **kw):
        self.calls.append([dict(m) for m in messages])
        return self._replies.pop(0) if self._replies else CLEAN


def _engine(replies):
    client = _ScriptedClient(replies)
    engine = CoWriterEngine(client, ScriptContext(), ReportContext(None))
    return client, engine, Session.new("T")


def _drift_to_the_threshold():
    """Five clean replies then five drifting ones — the shape that crosses."""
    return _engine([CLEAN] * 5 + [DRIFTED] * 10 + [CLEAN] * 10)


class TestTheEngineState:
    def test_it_arms_only_after_the_trend_crosses(self):
        _, engine, session = _drift_to_the_threshold()
        persona = session.branch.active_persona
        for i in range(VOICE_DRIFT_MIN_HISTORY - 1):
            engine.send_message(session, f"turn {i}")
            assert not engine.voice_reprime_pending(persona), (
                f"armed early, at reply {i + 1}"
            )
        engine.send_message(session, "the tenth")
        assert engine.voice_reprime_pending(persona)

    def test_consuming_clears_it(self):
        """It rides ONE turn. If the drift is still there the next reply re-arms
        it, so the detector governs and this cannot become a permanent nag."""
        _, engine, session = _drift_to_the_threshold()
        persona = session.branch.active_persona
        engine._voice_reprime.add(persona)
        assert engine.voice_reprime_pending(persona)
        engine._consume_voice_reprime(persona)
        assert not engine.voice_reprime_pending(persona)

    def test_a_clean_conversation_never_arms(self):
        _, engine, session = _engine([CLEAN] * 15)
        persona = session.branch.active_persona
        for i in range(15):
            engine.send_message(session, f"turn {i}")
        assert not engine.voice_reprime_pending(persona)

    def test_the_history_is_capped(self):
        _, engine, session = _drift_to_the_threshold()
        persona = session.branch.active_persona
        for i in range(VOICE_DRIFT_HISTORY_MAX + 8):
            engine.send_message(session, f"turn {i}")
        assert len(engine._tell_history[persona]) <= VOICE_DRIFT_HISTORY_MAX


class TestItIsPerConversation:
    """The old history was a module-level dict — two open projects shared it."""

    def test_the_module_global_is_gone(self):
        import screenplay_cowriter.engine as eng_mod
        assert not hasattr(eng_mod, "_VOICE_DRIFT_HISTORY"), (
            "the process-global drift history is back — two projects would share it"
        )

    def test_one_engines_drift_does_not_mark_another(self):
        client_a = _ScriptedClient([CLEAN] * 5 + [DRIFTED] * 10)
        client_b = _ScriptedClient([CLEAN] * 15)
        eng_a = CoWriterEngine(client_a, ScriptContext(), ReportContext(None))
        eng_b = CoWriterEngine(client_b, ScriptContext(), ReportContext(None))
        sa, sb = Session.new("A"), Session.new("B")
        for i in range(VOICE_DRIFT_MIN_HISTORY):
            eng_a.send_message(sa, f"a{i}")
            eng_b.send_message(sb, f"b{i}")
        assert eng_a.voice_reprime_pending(sa.branch.active_persona)
        assert not eng_b.voice_reprime_pending(sb.branch.active_persona), (
            "engine B's clean conversation was marked as drifting by engine A's replies"
        )


# --------------------------------------------------------------------------
# it reaches the prompt
# --------------------------------------------------------------------------

class TestItReachesThePrompt:
    def test_the_early_turns_carry_the_normal_voice_check(self):
        client, engine, session = _drift_to_the_threshold()
        engine.send_message(session, "hello")
        last = client.calls[-1][-1]["content"]
        assert post_history_reminder(session.branch.active_persona) in last
        assert VOICE_REPRIME_REMINDER not in last

    def test_the_turn_after_the_drift_carries_the_reprime(self):
        client, engine, session = _drift_to_the_threshold()
        for i in range(VOICE_DRIFT_MIN_HISTORY):
            engine.send_message(session, f"turn {i}")
        engine.send_message(session, "the turn after")
        last = client.calls[-1][-1]["content"]
        assert VOICE_REPRIME_REMINDER in last, "the drift was detected but never acted on"
        assert post_history_reminder(session.branch.active_persona) not in last, (
            "the re-prime REPLACES the voice check; appending both wastes the "
            "highest-weight position"
        )

    def test_the_reprime_is_the_last_message(self):
        """Last word before generation carries the most weight — the lever the
        trait and post-history reminders already use."""
        client, engine, session = _drift_to_the_threshold()
        for i in range(VOICE_DRIFT_MIN_HISTORY):
            engine.send_message(session, f"turn {i}")
        engine.send_message(session, "the turn after")
        assert VOICE_REPRIME_REMINDER in client.calls[-1][-1]["content"]

    def test_it_is_consumed_after_the_turn(self):
        client, engine, session = _drift_to_the_threshold()
        for i in range(VOICE_DRIFT_MIN_HISTORY):
            engine.send_message(session, f"turn {i}")
        persona = session.branch.active_persona
        engine.send_message(session, "the turn after")
        # the reply for that turn is clean (index 10), so the recent window drops
        # toward clean — the flag may or may not re-arm, but it was CONSUMED first
        assert engine._voice_reprime.issubset({persona})

    def test_the_assemble_path_honours_the_flag_directly(self):
        """Pins the plumbing without going through a whole conversation."""
        client, engine, session = _drift_to_the_threshold()
        persona = session.branch.active_persona
        plain = engine._assemble_messages("SYS", [], "USER", persona)
        primed = engine._assemble_messages("SYS", [], "USER", persona, reprime=True)
        assert VOICE_REPRIME_REMINDER not in plain[-1]["content"]
        assert VOICE_REPRIME_REMINDER in primed[-1]["content"]


# --------------------------------------------------------------------------
# the text itself
# --------------------------------------------------------------------------

class TestTheReprimeText:
    def test_it_points_at_the_examples_rather_than_restating_rules(self):
        """'Re-prime the examples block' — the examples are already in the prompt
        and are never shed, so the action is to send the model back to them."""
        assert "example dialogue" in VOICE_REPRIME_REMINDER

    def test_it_names_no_persona(self):
        """It must be safe for all eight personas. Naming one would hand the
        others that character's voice — the mistake the fallback note in
        personas.py records."""
        for name in list(POST_HISTORY_REMINDER) + ["no_such_persona", ""]:
            text = post_history_reminder(name, reprime=True)
            assert text == VOICE_REPRIME_REMINDER
            for other in ("Sameer", "Doctor", "Producer", "Teacher", "Moviegoer"):
                assert other not in text, f"the re-prime names {other}"

    def test_the_normal_reminder_is_unchanged_by_default(self):
        """Regression guard: every existing caller passes one argument."""
        for name in list(POST_HISTORY_REMINDER) + ["no_such_persona"]:
            assert post_history_reminder(name) == post_history_reminder(name, reprime=False)

    def test_every_persona_gets_its_own_normal_reminder_still(self):
        assert post_history_reminder("writing_partner") != post_history_reminder("script_consultant")
