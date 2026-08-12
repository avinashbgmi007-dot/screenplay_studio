"""
Co-writer replies must stay free of non-writing feedback: the standing
system prompt forbids language/dialect identification and subtitle meta-
commentary, and strip_language_meta() backs that up on the reply side.
Regression for a live chat reply that told the writer their Tenglish
dialect "reads as regional — probably Telugu" and would "need either
subtitles or context for non-native speakers".
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_cowriter.language_meta import strip_language_meta
from screenplay_cowriter.context import build_system_prompt, ScriptContext, ReportContext, LANGUAGE_META_INSTRUCTION
from screenplay_cowriter.engine import CoWriterEngine
from screenplay_cowriter.models import Session, Message

META_PARAGRAPH = (
    "The dialect/mixed language (\"Em ra Rahul,\" \"paisal anni,\" etc.) reads as "
    "regional — probably Telugu or a South Indian language. It's working to "
    "establish character voice, though it'll need either subtitles or context for "
    "non-native speakers."
)

CRAFT_PARAGRAPH = (
    "The scene has a clear function — it establishes Rahul as a character in "
    "trouble and sets up the match cut to his eyes. That's not empty padding."
)


class TestStripLanguageMeta:
    def test_meta_sentences_removed(self):
        text = META_PARAGRAPH + "\n\n" + CRAFT_PARAGRAPH
        out = strip_language_meta(text)
        assert "reads as regional" not in out
        assert "probably Telugu" not in out
        assert "subtitles" not in out
        assert "non-native speakers" not in out
        assert "establishes Rahul as a character in trouble" in out

    def test_entirely_meta_line_dropped(self):
        assert strip_language_meta("This reads as a South Indian language.").strip() == ""

    def test_clean_text_untouched(self):
        text = "A couple of craft notes:\n\n" + CRAFT_PARAGRAPH
        assert strip_language_meta(text) == text

    def test_bullet_meta_dropped_but_neighbors_kept(self):
        text = "- One note on the language: probably Telugu.\n- The pacing is tight.\n- Subtitle needs are a concern for non-native viewers."
        out = strip_language_meta(text)
        assert "- One note on the language: probably Telugu." not in out
        assert "- Subtitle needs are a concern" not in out
        assert "- The pacing is tight." in out

    def test_blank_runs_collapsed(self):
        out = strip_language_meta("Line A.\n\n\n\nLine B.\n\n" + META_PARAGRAPH)
        assert "\n\n\n" not in out
        assert "Line A." in out and "Line B." in out


class TestPromptRule:
    def test_system_prompt_contains_language_rule(self):
        prompt = build_system_prompt(
            ScriptContext({"title": "T"}), ReportContext(None), "script_consultant", "evidence_discussion"
        )
        assert LANGUAGE_META_INSTRUCTION in prompt
        assert "Never comment on the script's LANGUAGE itself" in prompt

    def test_rule_applies_to_all_personas(self):
        for persona in ("script_consultant", "producer", "dev_exec", "teacher", "audience", "genre_specialist"):
            prompt = build_system_prompt(ScriptContext({"title": "T"}), ReportContext(None), persona, "brainstorm")
            assert "Never comment on the script's LANGUAGE itself" in prompt


class _ChatClient:
    def __init__(self, reply):
        self._reply = reply
        self.calls = 0

    def chat(self, messages):
        self.calls += 1
        return self._reply


class TestEngineAppliesFilter:
    def test_reply_stripped_before_stored(self):
        engine = CoWriterEngine(_ChatClient(META_PARAGRAPH + "\n\n" + CRAFT_PARAGRAPH), ScriptContext(), ReportContext(None))
        session = Session.new("T")
        reply = engine.send_message(session, "What about scene 3?")
        assert "reads as regional" not in reply
        assert "probably Telugu" not in reply
        assert "establishes Rahul as a character in trouble" in reply
        # the stored assistant message matches the returned (stripped) reply
        stored = session.branch.messages[-1]
        assert stored.role == "assistant" and stored.content == reply

    def test_clean_reply_passthrough(self):
        engine = CoWriterEngine(_ChatClient(CRAFT_PARAGRAPH), ScriptContext(), ReportContext(None))
        session = Session.new("T")
        reply = engine.send_message(session, "hello")
        assert reply == CRAFT_PARAGRAPH
        assert engine.client.calls == 1
