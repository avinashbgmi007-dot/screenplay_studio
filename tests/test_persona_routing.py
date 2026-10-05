"""Regression tests for persona-aware probes and isolated lens histories."""

from screenplay_cowriter.context import ReportContext, ScriptContext
from screenplay_cowriter.engine import CoWriterEngine
from screenplay_cowriter.models import Message, Session
from screenplay_cowriter.peer import SAMEER_PROBE_SYSTEM_PROMPT
from screenplay_cowriter.personas import persona_examples


class CaptureClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append([dict(message) for message in messages])
        return self.replies.pop(0)


def _engine(client):
    return CoWriterEngine(client, ScriptContext({}), ReportContext(None))


def _joined(messages):
    return "\n".join(message.get("content", "") for message in messages)


def test_consultant_statement_does_not_receive_sameer_probe():
    client = CaptureClient(["The report points to a cost-free midpoint."])
    engine = _engine(client)
    session = Session.new("T")
    session.branch.active_persona = "script_consultant"
    session.branch.active_mode = "evidence_discussion"

    engine.send_message(session, "The middle is losing pressure.")

    system = client.calls[0][0]["content"]
    assert "The writer just shared an idea with you" not in system
    assert "You are Sameer" not in system
    assert session.branch.awaiting_probe is False


def test_pending_sameer_probe_is_abandoned_on_persona_switch():
    client = CaptureClient([
        "Mara's death sounds important to you. What is driving that choice?",
        "The report's concern is plausible, but I need the midpoint scene to test it.",
    ])
    engine = _engine(client)
    session = Session.new("T")

    engine.send_message(session, "Mara should die at the end")
    assert session.branch.awaiting_probe is True

    session.branch.active_persona = "script_consultant"
    session.branch.active_mode = "evidence_discussion"
    engine.send_message(session, "The middle is losing pressure.")

    second_prompt = _joined(client.calls[1])
    assert "The writer just shared an idea with you" not in second_prompt
    assert "Mara's death sounds important" not in second_prompt
    assert session.branch.awaiting_probe is False


def test_pending_probe_with_unknown_legacy_speaker_is_abandoned():
    client = CaptureClient(["What changes if the midpoint pressure is resolved earlier?"])
    engine = _engine(client)
    session = Session.new("T")
    session.branch.awaiting_probe = True
    session.branch.messages.extend([
        Message(role="user", content="legacy idea"),
        Message(role="assistant", content="legacy untagged probe"),
    ])

    engine.send_message(session, "The middle is losing pressure.")

    assert SAMEER_PROBE_SYSTEM_PROMPT in client.calls[0][0]["content"]
    assert session.branch.awaiting_probe is True


def test_other_personas_assistant_history_is_not_sent_to_current_lens():
    client = CaptureClient([
        "SAMEER_ONLY_REPLY: the opening needs a sharper choice.",
        "The report's scene 4 concern needs the actual passage.",
    ])
    engine = _engine(client)
    session = Session.new("T")
    engine.send_message(session, "What do you think about the opening?")

    session.branch.active_persona = "script_consultant"
    session.branch.active_mode = "evidence_discussion"
    engine.send_message(session, "Does the report's scene 4 concern hold?")

    prompt = _joined(client.calls[1])
    assert "SAMEER_ONLY_REPLY" not in prompt
    assert "What do you think about the opening?" not in prompt
    assert "Does the report's scene 4 concern hold?" in prompt
    # The combined session remains intact for persistence and the UI's partner filter.
    assert session.branch.messages[1].partner == "writing_partner"
    assert session.branch.messages[-1].partner == "script_consultant"


def test_legacy_history_keeps_user_context_but_not_unknown_assistant_voice():
    history = [
        Message(role="user", content="legacy writer context"),
        Message(role="assistant", content="unknown legacy assistant voice"),
        Message(role="user", content="sameer-only question", partner="writing_partner"),
        Message(role="assistant", content="sameer-only reply", partner="writing_partner"),
        Message(role="user", content="doctor question", partner="script_consultant"),
        Message(role="assistant", content="doctor answer", partner="script_consultant"),
    ]

    kept = CoWriterEngine._history_for_persona(history, "script_consultant")
    assert [message.content for message in kept] == [
        "legacy writer context", "doctor question", "doctor answer",
    ]


def test_base_prompt_examples_are_not_duplicated_in_assembled_messages():
    client = CaptureClient(["Start with the first irreversible choice."])
    engine = _engine(client)
    session = Session.new("T")

    engine.send_message(session, "What should I look at first?")

    system = client.calls[0][0]["content"]
    examples = persona_examples("writing_partner")
    assert examples
    assert system.count(examples) == 1
