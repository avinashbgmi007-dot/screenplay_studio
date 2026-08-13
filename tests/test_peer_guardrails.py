# Tests for screenplay_cowriter/peer.py guardrails and engine two-phase turn.
# No real model needed — FakeClient simulates the llama server.

import pytest
from screenplay_cowriter.peer import classify_turn, has_embedded_reasoning, should_probe, PROBE_SYSTEM_PROMPT


def test_classify_question_by_question_mark():
    assert classify_turn("should Mara forgive him?") == "question"


def test_classify_question_by_start_word():
    assert classify_turn("why does scene 14 feel flat") == "question"


def test_classify_directive():
    assert classify_turn("rewrite scene 14 dialogue") == "directive"


def test_classify_plain_statement_as_idea():
    assert classify_turn("I think Mara should die at the end") == "idea"


def test_embedded_reasoning_detected():
    assert has_embedded_reasoning("I think Mara should die because the guilt is eating her")
    assert not has_embedded_reasoning("Mara should die at the end")


def test_should_probe_only_when_reasoning_absent():
    assert should_probe("Mara should die at the end")
    assert not should_probe("Mara should die because the guilt is eating her")
    assert not should_probe("should Mara die?")


def test_probe_prompt_forbids_suggestions():
    assert "do not offer suggestions" in PROBE_SYSTEM_PROMPT.lower()
    assert "one question" in PROBE_SYSTEM_PROMPT.lower()


def test_forward_reply_left_untouched():
    from screenplay_cowriter.peer import ensure_forward_momentum
    assert ensure_forward_momentum("What do you think?", "idea") == "What do you think?"


def test_stranded_reply_gets_nudge_for_idea_turn():
    from screenplay_cowriter.peer import ensure_forward_momentum
    out = ensure_forward_momentum("That could work.", "idea")
    assert out.startswith("That could work.")
    assert out != "That could work."
    assert out.rstrip().endswith("?")  # every nudge template ends with a question


def test_no_nudge_for_factual_answer():
    from screenplay_cowriter.peer import ensure_forward_momentum
    # >200 chars so the light-touch rule treats it as a substantial factual answer
    long_factual = "In act two, Mara confronts her brother at the warehouse, and the " \
                   "situation escalates into a confrontation that changes everything. " * 4
    assert len(long_factual) > 200
    assert ensure_forward_momentum(long_factual, "question") == long_factual


def test_short_factual_turn_still_gets_nudge():
    from screenplay_cowriter.peer import ensure_forward_momentum
    assert ensure_forward_momentum("Act two.", "question") != "Act two."


def test_nudges_rotate_no_repeat_back_to_back():
    from screenplay_cowriter.peer import ensure_forward_momentum, FORWARD_NUDGES
    a = ensure_forward_momentum("Yes.", "idea")
    b = ensure_forward_momentum("Yes.", "idea")
    assert a != b


def test_cap_leaves_single_suggestion_alone():
    from screenplay_cowriter.peer import cap_suggestions
    reply = "Here's one thought:\n- Try cutting the opening monologue."
    assert cap_suggestions(reply) == reply


def test_cap_trims_overflow_and_offers_choice():
    from screenplay_cowriter.peer import cap_suggestions
    reply = "Options:\n- Cut the monologue\n- Move it to act two\n- Give it to Mara's brother"
    out = cap_suggestions(reply)
    assert out.count("- ") == 1
    assert "one at a time" in out.lower()


def test_cap_no_bullets_untouched():
    from screenplay_cowriter.peer import cap_suggestions
    prose = "I think cutting the monologue works, and I'd move the key reveal to act two."
    assert cap_suggestions(prose) == prose


def test_writing_partner_persona_exists_and_is_default():
    from screenplay_cowriter.personas import PERSONAS, DEFAULT_PERSONA, persona_text
    assert "writing_partner" in PERSONAS
    assert DEFAULT_PERSONA == "writing_partner"
    text = persona_text("writing_partner")
    assert "co-writer" in text.lower() or "partner" in text.lower()


def test_peer_mode_is_default_and_informed_partner_locked():
    from screenplay_cowriter.personas import MODES, DEFAULT_MODE, mode_text
    assert "peer" in MODES
    assert DEFAULT_MODE == "peer"
    text = mode_text("peer")
    assert "never volunteer" in text.lower()
    assert "one idea" in text.lower()


def test_legacy_personas_still_present():
    from screenplay_cowriter.personas import PERSONAS
    for name in ("producer", "dev_exec", "teacher", "audience", "genre_specialist", "script_consultant"):
        assert name in PERSONAS


def test_branch_awaiting_probe_default_false():
    from screenplay_cowriter.models import Branch
    assert Branch(name="main").awaiting_probe is False


def test_awaiting_probe_round_trips_through_dict():
    from screenplay_cowriter.models import Branch
    b = Branch(name="main")
    b.awaiting_probe = True
    restored = Branch.from_dict(b.to_dict())
    assert restored.awaiting_probe is True


def test_new_branch_defaults_to_writing_partner_peer():
    from screenplay_cowriter.models import Branch
    b = Branch(name="main")
    assert b.active_persona == "writing_partner"
    assert b.active_mode == "peer"


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
    def chat(self, messages, **kw):
        self.calls.append(messages)
        return self.replies.pop(0)


def _make_session():
    from screenplay_cowriter.models import Session
    return Session.new(title="t")


def _make_engine(client):
    from screenplay_cowriter.engine import CoWriterEngine
    from screenplay_cowriter.context import ScriptContext, ReportContext
    return CoWriterEngine(client, ScriptContext({}), ReportContext(None))


def test_idea_without_reasoning_probes_first_and_defers_suggestions():
    client = FakeClient(["So the idea is Mara dies at the end. What's pulling you toward that?"])
    engine = _make_engine(client)
    s = _make_session()
    reply = engine.send_message(s, "Mara should die at the end")
    assert "?" in reply
    assert s.branch.awaiting_probe is True
    assert "ONE job" in client.calls[0][0]["content"]
    assert len(s.branch.messages) == 2  # user + assistant, no suggestions offered


def test_idea_with_reasoning_gets_full_turn():
    client = FakeClient(["That reasoning lands. Want to explore the guilt angle?"])
    engine = _make_engine(client)
    s = _make_session()
    reply = engine.send_message(s, "Mara should die because the guilt is eating her")
    assert s.branch.awaiting_probe is False
    assert reply == "That reasoning lands. Want to explore the guilt angle?"


def test_probe_abandoned_on_topic_change():
    client = FakeClient([
        "So the idea is Mara dies at the end. What's pulling you toward that?",  # probe reply
        "Sure, scene 14. What's bugging you about it?",                          # full-turn reply
    ])
    engine = _make_engine(client)
    s = _make_session()
    engine.send_message(s, "Mara should die at the end")  # probes
    assert s.branch.awaiting_probe is True
    reply = engine.send_message(s, "what about scene 14?")  # question -> abandon
    assert s.branch.awaiting_probe is False
    assert reply == "Sure, scene 14. What's bugging you about it?"


def test_probe_continuation_clears_flag_and_answers():
    client = FakeClient(["Because she's the only one who knows the truth.", "Then let's lean into that."])
    engine = _make_engine(client)
    s = _make_session()
    engine.send_message(s, "Mara should die at the end")
    assert s.branch.awaiting_probe is True
    engine.send_message(s, "because the guilt is eating her")  # continuation idea
    assert s.branch.awaiting_probe is False


def test_suggestion_cap_applied_to_full_turn():
    client = FakeClient(["Options:\n- Cut it\n- Move it\n- Rewrite it"])
    engine = _make_engine(client)
    s = _make_session()
    reply = engine.send_message(s, "what should I do with the monologue?")
    assert reply.count("- ") == 1


def test_dead_end_nudge_applied_when_needed():
    client = FakeClient(["That could work."])
    engine = _make_engine(client)
    s = _make_session()
    reply = engine.send_message(s, "what do you think about cutting the monologue?")
    assert "one at a time" not in reply  # no bullets, so no cap
    assert reply.rstrip().endswith("?")  # nudge appended to the stranded reply
