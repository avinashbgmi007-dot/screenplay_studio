"""GAP-4 regression — the consult turn carries per-finding context.

The audit found the Sushruta lens answered at project level: `sendFvMessage`
passed `quote = null`, so the doctor never saw the finding the writer was
looking at. Two halves are locked here:

1. the quote rides into the model prompt ("Passage from the script: ...")
   and is STORED on the user message (so the UI can show what a question
   was about);
2. every stored turn is tagged with the persona it was spoken with
   (`partner`), so the consult column can show the writer's own question
   without leaking co-write turns into the doctor's thread.

Legacy sessions (no `partner` key) must round-trip to None — the client
falls back to the old assistant-only view rather than hiding history.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_cowriter.context import ScriptContext, ReportContext
from screenplay_cowriter.engine import CoWriterEngine
from screenplay_cowriter.models import Session, Message


class _ChatClient:
    """Minimal fake — records the prompt it was handed, returns a reply."""

    def __init__(self, reply="Noted — the line lands flat because it states what the scene already shows."):
        self._reply = reply
        self.messages = []
        self.calls = 0

    def chat(self, messages, **kw):
        self.calls += 1
        self.messages = [dict(m) for m in messages]
        return self._reply


def _engine(client):
    return CoWriterEngine(client, ScriptContext(), ReportContext(None))


def _prompt_text(client):
    return "\n".join(str(m.get("content", "")) for m in client.messages)


class TestQuoteRidesIntoConsultTurn:
    def test_quote_reaches_the_model_prompt(self):
        client = _ChatClient()
        engine = _engine(client)
        session = Session.new("T")
        session.branch.active_persona = "script_consultant"
        engine.send_message(session, "Why was this flagged?",
                            quote={"scene_number": 1, "text": "RAVI: I'll tell you everything when this is over."})
        assert 'Passage from the script: "RAVI: I\'ll tell you everything when this is over."' in _prompt_text(client)

    def test_quote_is_stored_on_the_user_message(self):
        client = _ChatClient()
        engine = _engine(client)
        session = Session.new("T")
        session.branch.active_persona = "script_consultant"
        engine.send_message(session, "Why was this flagged?",
                            quote={"scene_number": 2, "text": "MARA: Then it stays between us."})
        user_msg = [m for m in session.branch.messages if m.role == "user"][-1]
        assert user_msg.quote == {"scene_number": 2, "text": "MARA: Then it stays between us."}

    def test_malformed_quote_is_dropped_not_crashed(self):
        client = _ChatClient()
        engine = _engine(client)
        session = Session.new("T")
        engine.send_message(session, "plain question", quote={"scene_number": "one", "text": ""})
        user_msg = [m for m in session.branch.messages if m.role == "user"][-1]
        assert user_msg.quote is None  # normalize_quote dropped it
        assert "Passage from the script" not in _prompt_text(client)


class TestPartnerTagging:
    def test_turns_tagged_with_active_persona(self):
        client = _ChatClient()
        engine = _engine(client)
        session = Session.new("T")
        session.branch.active_persona = "script_consultant"
        engine.send_message(session, "Why was this flagged?")
        assert session.branch.messages[-2].partner == "script_consultant"  # user
        assert session.branch.messages[-1].partner == "script_consultant"  # assistant

    def test_sameer_turns_tag_writing_partner(self):
        client = _ChatClient()
        engine = _engine(client)
        session = Session.new("T")  # default persona
        engine.send_message(session, "What should I do with scene 2?")
        assert session.branch.messages[-2].partner == "writing_partner"
        assert session.branch.messages[-1].partner == "writing_partner"

    def test_legacy_message_roundtrips_partner_none(self):
        legacy = {"role": "user", "content": "old turn", "timestamp": 1.0}
        msg = Message.from_dict(legacy)
        assert msg.partner is None
        assert msg.to_dict()["partner"] is None
