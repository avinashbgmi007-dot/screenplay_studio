"""An ungrounded finding's wording must never reach a persona as script prose.

`discussFinding` / `discussWithDoctor` pin the finding under discussion to the
next turn. They used to pass `f.evidence_quote || f.issue`, and the engine
wrapped whatever arrived in "The writer selected this passage from Scene N …
Ground your answer in the exact words they highlighted." For a finding the
analyzer could not ground there is no `evidence_quote`, so the NOTE's own
sentence — a machine opinion — was handed to the persona as verbatim dialogue.

The quote now carries a `kind`: a real citation rides as a selection (the old
wording, byte-identical), a note rides as a note and is labelled as one.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_cowriter.context import ScriptContext, ReportContext
from screenplay_cowriter.engine import CoWriterEngine
from screenplay_cowriter.models import Session
from screenplay_cowriter.reply_transforms import normalize_quote


class _ChatClient:
    """Minimal fake — records the prompt it was handed, returns a reply."""

    def __init__(self, reply="The note is not backed by the pages, so treat it as a question."):
        self._reply = reply
        self.messages = []
        self.calls = 0

    def chat(self, messages, **kw):
        self.calls += 1
        self.messages = [dict(m) for m in messages]
        return self._reply


def _prompt_text(client):
    return "\n".join(str(m.get("content", "")) for m in client.messages)


SCRIPT = {"title": "Provenance Test", "scenes": [
    {"scene_number": 3, "heading_raw": "INT. STUDY - NIGHT", "elements": [
        {"type": "action", "text": "MARA sets the revolver down."},
        {"type": "character", "text": "MARA"},
        {"type": "dialogue", "text": "I am fine."},
    ]},
]}


def _send(quote, text="Why was this flagged?"):
    client = _ChatClient()
    engine = CoWriterEngine(client, ScriptContext(SCRIPT), ReportContext(None))
    session = Session.new("T")
    session.branch.active_persona = "script_consultant"
    engine.send_message(session, text, quote=quote)
    return _prompt_text(client)


NOTE = "marker-a on-the-nose line; the subtext is spoken aloud."


class TestNormalizeQuoteCarriesKind:
    def test_a_note_keeps_its_kind(self):
        assert normalize_quote({"scene_number": 3, "text": NOTE, "kind": "note"}) == {
            "scene_number": 3, "text": NOTE, "kind": "note"}

    def test_a_kindless_quote_is_a_selection(self):
        """Every caller older than this field meant a real highlighted passage."""
        assert normalize_quote({"scene_number": 1, "text": "RAVI: Go."}) == {
            "scene_number": 1, "text": "RAVI: Go.", "kind": "selection"}

    def test_an_unknown_kind_cannot_smuggle_in_new_wording(self):
        assert normalize_quote({"text": "X", "kind": "script"})["kind"] == "selection"


class TestAnUngroundedNoteIsNotScriptText:
    def test_the_note_is_not_called_a_passage(self):
        prompt = _send({"scene_number": 3, "text": NOTE, "kind": "note"})
        assert NOTE in prompt
        # The misattribution itself: neither the context block nor the user
        # turn may tell the model these words are script text.
        assert "selected this passage" not in prompt
        assert "Passage from the script" not in prompt
        assert 'The writer selected this passage from Scene 3' not in prompt

    def test_the_note_is_labelled_as_a_note_and_to_be_judged(self):
        prompt = _send({"scene_number": 3, "text": NOTE, "kind": "note"})
        assert "doctor's note on Scene 3" in prompt
        assert "the NOTE's words, not script text" in prompt
        assert "Judge the note itself against the pages" in prompt
        assert "Note under discussion" in prompt

    def test_the_scene_still_rides_as_real_script_text(self):
        """Not a licence to drop grounding: the note's scene is still pulled in,
        so the persona can check the claim against the pages."""
        prompt = _send({"scene_number": 3, "text": NOTE, "kind": "note"})
        assert "SCENE TEXT (for this turn only)" in prompt

    def test_a_real_quote_keeps_the_old_wording(self):
        """A citation IS script text; its framing is unchanged, byte for byte."""
        quote = {"scene_number": 1, "text": "RAVI: I'll tell you everything when this is over."}
        prompt = _send(quote)
        assert 'Passage from the script: "RAVI: I\'ll tell you everything when this is over."' in prompt
        assert "The writer selected this passage from Scene 1 and is asking about it" in prompt
        assert "the NOTE's words" not in prompt

    def test_the_stored_message_keeps_the_two_field_shape(self):
        """`kind` words one reply; the stored quote stays what the card and old
        sessions read. Adding a third key here would be a silent schema drift."""
        client = _ChatClient()
        engine = CoWriterEngine(client, ScriptContext(SCRIPT), ReportContext(None))
        session = Session.new("T")
        engine.send_message(session, "Why was this flagged?",
                            quote={"scene_number": 3, "text": NOTE, "kind": "note"})
        user_msg = [m for m in session.branch.messages if m.role == "user"][-1]
        assert user_msg.quote == {"scene_number": 3, "text": NOTE}

    def test_the_general_case_has_no_scene_number(self):
        prompt = _send({"scene_number": None, "text": NOTE, "kind": "note"})
        assert "doctor's note on this project" in prompt
        assert "not script text" in prompt
