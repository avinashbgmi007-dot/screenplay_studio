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

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_cowriter.language_meta import strip_language_meta, strip_json_wrap
from screenplay_cowriter.context import build_system_prompt, ScriptContext, ReportContext, LANGUAGE_META_INSTRUCTION, PLAIN_TEXT_INSTRUCTION
from screenplay_cowriter.engine import CoWriterEngine
from screenplay_cowriter.llm_client import LlamaServerClient, ModelNotFoundError
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

    def test_system_prompt_forbids_json(self):
        prompt = build_system_prompt(
            ScriptContext({"title": "T"}), ReportContext(None), "writing_partner", "peer"
        )
        assert PLAIN_TEXT_INSTRUCTION in prompt
        assert "Never emit JSON" in prompt

    def test_rule_applies_to_all_personas(self):
        for persona in ("script_consultant", "producer", "dev_exec", "teacher", "audience", "genre_specialist"):
            prompt = build_system_prompt(ScriptContext({"title": "T"}), ReportContext(None), persona, "brainstorm")
            assert "Never comment on the script's LANGUAGE itself" in prompt


class TestStripJsonWrap:
    def test_fenced_json_with_content_key(self):
        reply = '```json\n{"content": "The ending lands hard because of the setup."}\n```'
        assert strip_json_wrap(reply) == "The ending lands hard because of the setup."

    def test_raw_json_with_answer_key(self):
        assert strip_json_wrap('{"answer": "Scene 4 is too long."}') == "Scene 4 is too long."

    def test_single_key_dict_unwrapped(self):
        assert strip_json_wrap('{"response": "Keep the monologue."}') == "Keep the monologue."

    def test_plain_prose_passthrough(self):
        text = "The ending works. The setup pays off in scene 12."
        assert strip_json_wrap(text) == text

    def test_prose_starting_with_brace_not_parsed(self):
        # looks like JSON, isn't — never mangle a genuine reply
        text = "{Honestly, the first act drags.}"
        assert strip_json_wrap(text) == text

    def test_json_array_passthrough(self):
        reply = '[{"content": "One"}, {"content": "Two"}]'
        assert strip_json_wrap(reply) == reply

    def test_fenced_prose_passthrough(self):
        reply = '```json\nSome plain words that are not JSON.\n```'
        assert strip_json_wrap(reply) == reply

    def test_fenced_json_with_preamble(self):
        reply = 'Here is my note: ```json\n{"content": "Cut the voiceover."}\n```'
        assert strip_json_wrap(reply) == "Cut the voiceover."

    def test_empty_passthrough(self):
        assert strip_json_wrap("") == ""


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
        # a question takes the full-turn path (a bare "hello" would be treated as
        # an unreasoned idea and probed first — see peer.py two-phase logic)
        reply = engine.send_message(session, "What about scene 3?")
        assert reply == CRAFT_PARAGRAPH
        assert engine.client.calls == 1

    def test_json_wrapped_reply_unwrapped(self):
        engine = CoWriterEngine(_ChatClient('{"content": "The antagonist needs a clearer want."}'), ScriptContext(), ReportContext(None))
        session = Session.new("T")
        reply = engine.send_message(session, "What about the antagonist?")
        # the JSON wrapper is gone (the engine's own tone guards may still
        # append a forward nudge to a short reply — that's not what we test)
        assert reply.startswith("The antagonist needs a clearer want.")
        assert "{" not in reply and "}" not in reply
        assert session.branch.messages[-1].content == reply

    def test_fenced_json_reply_unwrapped(self):
        engine = CoWriterEngine(_ChatClient('```json\n{"answer": "Cut the voiceover."}\n```'), ScriptContext(), ReportContext(None))
        session = Session.new("T")
        reply = engine.send_message(session, "What about the voiceover?")
        assert reply.startswith("Cut the voiceover.")
        assert "```" not in reply and "{" not in reply


class TestModelFallback:
    def test_pinned_model_missing_raises_by_default(self, mock_server):
        client = LlamaServerClient(mock_server, model="ghost-model.gguf")
        with pytest.raises(ModelNotFoundError):
            client.chat([{"role": "user", "content": "hi"}])

    def test_pinned_model_missing_falls_back_to_loaded(self, mock_server):
        client = LlamaServerClient(mock_server, model="ghost-model.gguf", fallback_to_loaded=True)
        reply = client.chat([{"role": "user", "content": "hi"}])
        assert "[mock chat reply]" in reply  # the mock's loaded model answered
