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

from screenplay_cowriter.language_meta import (
    strip_language_meta, strip_json_wrap, strip_repetition_lines, strip_repeated_blocks,
)
from screenplay_cowriter.context import (
    build_system_prompt, ScriptContext, ReportContext,
    LANGUAGE_META_INSTRUCTION, PLAIN_TEXT_INSTRUCTION, GROUNDING_INSTRUCTION,
    resolve_referenced_scenes,
)
from screenplay_cowriter.engine import CoWriterEngine, clean_reply, _ground_reply, REPEAT_PENALTY
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

    def test_writing_partner_embeds_example_dialogue(self):
        # The character-card lever: example exchanges lock the voice better
        # than adjectives. Sam's examples must ride the writing_partner prompt.
        prompt = build_system_prompt(
            ScriptContext({"title": "T"}), ReportContext(None), "writing_partner", "peer"
        )
        assert "How Sam talks" in prompt
        assert "Bold call" in prompt
        assert "want my honest take" in prompt

    def test_other_personas_have_no_example_dialogue(self):
        prompt = build_system_prompt(
            ScriptContext({"title": "T"}), ReportContext(None), "script_consultant", "evidence_discussion"
        )
        assert "How Sam talks" not in prompt


class TestScriptMap:
    """Sam gets a compact standing map of the script (headings + character
    presence) so answers aren't vague for questions that don't name a scene."""

    def _script(self):
        return {"title": "T", "scenes": [
            {"scene_number": 1, "heading_raw": "EXT. ROAD - NIGHT", "elements": [
                {"type": "action", "text": "A car pulls up."},
                {"type": "character", "text": "DOCTOR (O.S.)"},
                {"type": "dialogue", "text": "We are late."},
            ]},
            {"scene_number": 2, "heading_raw": "INT. HALL - DAY", "elements": [
                {"type": "character", "text": "RISHI"},
                {"type": "dialogue", "text": "Where is he?"},
                {"type": "character", "text": "DOCTOR (CONT'D)"},
                {"type": "dialogue", "text": "Coming."},
            ]},
        ]}

    def test_map_lists_headings_and_character_presence(self):
        m = ScriptContext(self._script()).script_map()
        assert "Scene 1: EXT. ROAD - NIGHT" in m
        assert "Scene 2: INT. HALL - DAY" in m
        assert "DOCTOR: 1, 2" in m
        assert "RISHI: 2" in m

    def test_map_strips_extensions_from_character_names(self):
        m = ScriptContext(self._script()).script_map()
        assert "DOCTOR (O.S.)" not in m  # extensions normalized to the base name

    def test_map_empty_script_returns_empty(self):
        assert ScriptContext({"scenes": []}).script_map() == ""

    def test_build_system_prompt_embeds_map(self):
        prompt = build_system_prompt(ScriptContext(self._script()), ReportContext(None), "writing_partner", "peer")
        assert "SCRIPT MAP — 2 scenes" in prompt
        assert "CHARACTER PRESENCE" in prompt

    def test_build_system_prompt_without_scenes_has_no_map(self):
        prompt = build_system_prompt(ScriptContext({"title": "T"}), ReportContext(None), "writing_partner", "peer")
        assert "SCRIPT MAP" not in prompt


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


class TestStripRepetitionLines:
    def test_underscore_tail_removed(self):
        reply = "The scene lacks consequence.\n\n" + "\n".join(["_"] * 50)
        out = strip_repetition_lines(reply)
        assert out == "The scene lacks consequence."

    def test_mixed_separators_removed(self):
        reply = "A real point.\n___\n---\n=== \n" + "B real point."
        out = strip_repetition_lines(reply)
        assert "___" not in out and "---" not in out
        assert "A real point." in out and "B real point." in out

    def test_mixed_content_lines_untouched(self):
        reply = "It reads like a_b_c shorthand for the audience.\n12345\nStay as-is."
        assert strip_repetition_lines(reply) == reply

    def test_mid_reply_separator_removed_but_text_kept(self):
        reply = "Point one.\n___\nPoint two."
        out = strip_repetition_lines(reply)
        assert out == "Point one.\nPoint two."

    def test_blank_runs_collapsed(self):
        reply = "Line A.\n\n\n\n\nLine B."
        assert strip_repetition_lines(reply) == "Line A.\n\nLine B."

    def test_eot_tag_lines_removed(self):
        reply = "The scene lacks consequence.\n" + "\n".join(["<im_end|>"] * 30)
        out = strip_repetition_lines(reply)
        assert out == "The scene lacks consequence."

    def test_eot_tag_variants_removed(self):
        reply = "Real point.\n<im_end|>\n<im_im_end|>\n<|im_end|>\n<im_im_im_end|>"
        out = strip_repetition_lines(reply)
        assert out == "Real point."

    def test_tag_glued_to_end_peeled(self):
        reply = "So the answer is no.<|im_end|>"
        assert strip_repetition_lines(reply) == "So the answer is no."

    def test_tag_glued_mid_text_removed(self):
        reply = "So the answer is no.<|im_end|> More on that later."
        assert strip_repetition_lines(reply) == "So the answer is no. More on that later."

    def test_cutoff_tag_line_removed(self):
        reply = "The scene lacks consequence.\n<im_im_im_im_im_im_im_im_im"
        assert strip_repetition_lines(reply) == "The scene lacks consequence."

    def test_no_space_tag_token_removed(self):
        # no-space angle-bracket tokens are the EOT-loop signature, even mid-line
        reply = "Use the <beat> marker sparingly.\nGood luck."
        assert strip_repetition_lines(reply) == "Use the  marker sparingly.\nGood luck."

    def test_html_tag_with_attributes_removed(self):
        reply = 'Here is the note: <div class="card">The scene drags.<div class="card">'
        assert strip_repetition_lines(reply) == "Here is the note: The scene drags."

    def test_html_font_and_closing_tags_removed(self):
        reply = '<font color="#ff69b4" size="+2">Keep the monologue.</font></br />'
        assert strip_repetition_lines(reply) == "Keep the monologue."

    def test_html_tag_own_line_removed(self):
        reply = "The scene drags.\n<div class=\"card\">\nReally, it drags."
        out = strip_repetition_lines(reply)
        assert "<div" not in out
        assert out == "The scene drags.\n\nReally, it drags."

    def test_html_bold_tag_removed(self):
        reply = "*The question remains: visually interesting but dramatically empty.*"
        assert strip_repetition_lines(reply) == reply  # no tags here — untouched
        reply2 = "<b>*The question remains.*</b>"
        assert strip_repetition_lines(reply2) == "*The question remains.*"

    def test_prose_operators_untouched(self):
        # "a < b" / "<-" must survive — not tags (no letter after the bracket)
        reply = "Keep x < y and z > w. The arrow <- points left."
        assert strip_repetition_lines(reply) == reply

    def test_empty_passthrough(self):
        assert strip_repetition_lines("") == ""


class TestStripRepeatedBlocks:
    # The live failure: a model re-answers the same point 3-4 times in one
    # reply, each repetition restarting with the same opening sentence and
    # sometimes re-echoing the user's question first.
    _ANSWER = (
        "The first act has a real imbalance: the medical explanation is a data "
        "dump for the audience rather than having any dramatic purpose for the "
        "characters.\n\n"
        "The dialogue needs to test the characters' values, not just explain "
        "the situation.\n\n"
        "Do you want the doctor to be more deeply connected, or more clinical?"
    )

    def test_question_and_answer_loop_collapsed(self):
        reply = self._ANSWER + "\n\nHow does the dialogue in the first act feel?\n\n" + self._ANSWER
        out = strip_repeated_blocks(reply)
        assert out == self._ANSWER
        assert out.count("The first act has a real imbalance") == 1

    def test_multi_repeat_collapsed(self):
        blocks = "\n\nHow does the dialogue in the first act feel?\n\n".join([self._ANSWER] * 3)
        out = strip_repeated_blocks(self._ANSWER + "\n\n" + blocks)
        assert out == self._ANSWER

    def test_near_duplicate_opening_collapsed(self):
        # the loop rephrases a little, but the opening sentence window matches
        variant = self._ANSWER.replace(
            "The dialogue needs to test the characters' values, not just explain the situation.",
            "The dialogue needs to test the characters' values, not just explain. "
            "The characters' painlessness feels more like a medical condition than a moral challenge.",
        )
        out = strip_repeated_blocks(self._ANSWER + "\n\n" + variant)
        assert out == self._ANSWER

    def test_first_occurrence_always_kept(self):
        out = strip_repeated_blocks(self._ANSWER + "\n\n" + self._ANSWER)
        assert out == self._ANSWER

    def test_short_paragraphs_never_deduped(self):
        # question echoes / one-liners must survive
        text = "what about scene 4?\n\nYes.\n\nwhat about scene 4?"
        assert strip_repeated_blocks(text) == text

    def test_clean_text_untouched(self):
        text = "Point one stands on its own.\n\nA different, unrelated paragraph.\n\nA third one."
        assert strip_repeated_blocks(text) == text

    def test_single_paragraph_untouched(self):
        assert strip_repeated_blocks(self._ANSWER) == self._ANSWER

    def test_empty_passthrough(self):
        assert strip_repeated_blocks("") == ""


class TestCleanReplyPipeline:
    def test_repetition_loop_tail_and_blocks_stripped(self):
        raw = "The scene lacks consequence.\n\n" + "\n".join(["_"] * 40)
        out = clean_reply(raw)
        assert out == "The scene lacks consequence."

    def test_glued_separator_at_end_stripped(self):
        # a leftover loop separator glued to the final word
        assert clean_reply("grounded?_") == "grounded?"

    def test_full_live_shapes_all_clean(self):
        # repeated answer + question echo + glued separator + leaked tags:
        # the loop's answer repeats collapse, the question echo (it precedes
        # an already-seen answer) is dropped too, and the trailing glue and
        # tag lines are gone.
        raw = (
            "The first act has a real imbalance.\n\n"
            "How does the dialogue feel?\n\n"
            "The first act has a real imbalance.\n\n"
            "grounded?_\n\n"
            + "\n".join(["<im_end|>"] * 5)
        )
        out = clean_reply(raw)
        assert out == "The first act has a real imbalance.\n\ngrounded?"


class _ChatClient:
    def __init__(self, reply):
        self._reply = reply
        self.calls = 0
        self.kwargs = None
        self.messages = []

    def chat(self, messages, **kw):
        self.calls += 1
        self.kwargs = kw
        self.messages = [dict(m) for m in messages]
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

    def test_repetition_loop_tail_stripped(self):
        garbage = "The scene lacks consequence.\n\n" + "\n".join(["_"] * 100)
        engine = CoWriterEngine(_ChatClient(garbage), ScriptContext(), ReportContext(None))
        session = Session.new("T")
        reply = engine.send_message(session, "What about scene 4?")
        assert reply.startswith("The scene lacks consequence.")
        assert not any(set(l.strip()) == {"_"} for l in reply.split("\n"))
        assert session.branch.messages[-1].content == reply

    def test_semantic_repetition_loop_collapsed(self):
        answer = (
            "The first act has a real imbalance: the medical explanation is a data "
            "dump for the audience rather than having any dramatic purpose for the "
            "characters.\n\n"
            "The dialogue needs to test the characters' values, not just explain "
            "the situation."
        )
        looping = answer + "\n\nHow does the dialogue feel?\n\n" + answer + "\n\n" + answer
        engine = CoWriterEngine(_ChatClient(looping), ScriptContext(), ReportContext(None))
        session = Session.new("T")
        reply = engine.send_message(session, "How does the dialogue in the first act feel?")
        assert reply.count("The first act has a real imbalance") == 1
        assert session.branch.messages[-1].content == reply

    def test_chat_turn_sends_repeat_penalty(self):
        client = _ChatClient(CRAFT_PARAGRAPH)
        engine = CoWriterEngine(client, ScriptContext(), ReportContext(None))
        engine.send_message(Session.new("T"), "What about scene 3?")
        assert client.kwargs["repeat_penalty"] == REPEAT_PENALTY
        assert client.kwargs["max_tokens"] == 600


class TestRepeatPenaltyPayload:
    def _client(self):
        # bypass list_models (which would do a real GET) by pre-resolving
        client = LlamaServerClient("http://mock", model="m.gguf", fallback_to_loaded=True)
        client._resolved_model = "m.gguf"
        return client

    def test_repeat_penalty_sent_when_set(self, monkeypatch):
        captured = {}
        def fake_post(url, json=None, timeout=None, headers=None, **kw):
            captured["payload"] = json
            class _Resp:
                def raise_for_status(self):
                    pass
                def json(self):
                    return {"choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}}]}
            return _Resp()
        monkeypatch.setattr("screenplay_cowriter.llm_client.requests.post", fake_post)
        self._client().chat([{"role": "user", "content": "hi"}], repeat_penalty=1.3)
        assert captured["payload"]["repeat_penalty"] == 1.3

    def test_repeat_penalty_omitted_by_default(self, monkeypatch):
        captured = {}
        def fake_post(url, json=None, timeout=None, headers=None, **kw):
            captured["payload"] = json
            class _Resp:
                def raise_for_status(self):
                    pass
                def json(self):
                    return {"choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}}]}
            return _Resp()
        monkeypatch.setattr("screenplay_cowriter.llm_client.requests.post", fake_post)
        self._client().chat([{"role": "user", "content": "hi"}])
        assert "repeat_penalty" not in captured["payload"]
        # the refresh path keeps the server default — its JSON output is untouched




class TestMessageQuote:
    def test_quote_round_trip(self):
        m = Message(role="user", content="hi", quote={"scene_number": 2, "text": "the line"})
        d = m.to_dict()
        assert d["quote"] == {"scene_number": 2, "text": "the line"}
        restored = Message.from_dict(d)
        assert restored.quote == {"scene_number": 2, "text": "the line"}

    def test_old_sessions_without_quote_load_as_none(self):
        # persisted before the quote field existed
        restored = Message.from_dict({"role": "user", "content": "hi", "timestamp": 1.0})
        assert restored.quote is None

    def test_quote_none_serializes(self):
        m = Message(role="assistant", content="ok")
        assert m.to_dict()["quote"] is None


class TestEngineQuoteContext:
    def test_quote_grounds_context_and_stores_on_message(self):
        client = _ChatClient("The line works — it's earned.")
        engine = CoWriterEngine(client, ScriptContext(), ReportContext(None))
        session = Session.new("T")
        reply = engine.send_message(
            session, "What do you make of this?",
            quote={"scene_number": 2, "text": "Just don't do anything stupid."},
        )
        assert reply
        # the quoted passage reached the model as context
        all_text = " ".join(m["content"] for m in client.messages)
        assert "Just don't do anything stupid." in all_text
        assert "Scene 2" in all_text
        # the passage also rides inside the user turn itself (adjacent to the
        # question), not just in a system message
        assert "Just don't do anything stupid." in client.messages[-1]["content"]
        # stored on the user message
        user_msg = [m for m in session.branch.messages if m.role == "user"][-1]
        assert user_msg.quote == {"scene_number": 2, "text": "Just don't do anything stupid."}
        assert 2 in user_msg.scene_refs

    def test_malformed_quote_dropped(self):
        client = _ChatClient("ok")
        engine = CoWriterEngine(client, ScriptContext(), ReportContext(None))
        session = Session.new("T")
        engine.send_message(session, "hi", quote={"scene_number": "nope", "text": ""})
        assert session.branch.messages[-2].quote is None

    def test_no_quote_no_context(self):
        client = _ChatClient("ok")
        engine = CoWriterEngine(client, ScriptContext(), ReportContext(None))
        session = Session.new("T")
        engine.send_message(session, "hi")
        all_text = " ".join(m["content"] for m in client.messages)
        assert "selected this passage" not in all_text

    def test_general_quote_without_scene_number(self):
        # script-level finding: no scene ref — the passage is still grounded
        client = _ChatClient("ok")
        engine = CoWriterEngine(client, ScriptContext(), ReportContext(None))
        session = Session.new("T")
        engine.send_message(session, "what about this?", quote={"scene_number": None, "text": "The whole theme of ash."})
        all_text = " ".join(m["content"] for m in client.messages)
        assert "The whole theme of ash." in all_text
        assert "from the script and is asking about it" in all_text
        user_msg = [m for m in session.branch.messages if m.role == "user"][-1]
        assert user_msg.quote == {"scene_number": None, "text": "The whole theme of ash."}
        assert user_msg.scene_refs == []  # no phantom scene pulled in

class TestModelFallback:
    def test_pinned_model_missing_raises_by_default(self, mock_server):
        client = LlamaServerClient(mock_server, model="ghost-model.gguf")
        with pytest.raises(ModelNotFoundError):
            client.chat([{"role": "user", "content": "hi"}])

    def test_pinned_model_missing_falls_back_to_loaded(self, mock_server):
        client = LlamaServerClient(mock_server, model="ghost-model.gguf", fallback_to_loaded=True)
        reply = client.chat([{"role": "user", "content": "hi"}])
        assert "[mock chat reply]" in reply  # the mock's loaded model answered


class TestGrounding:
    """The knowledge boundary: never invent script content that isn't in the
    provided material — the hallucination guard, stated in the prompt."""

    def _prompt(self, persona="writing_partner"):
        return build_system_prompt(
            ScriptContext({"title": "T"}), ReportContext(None), persona, "peer"
        )

    def test_system_prompt_contains_grounding_rule(self):
        assert GROUNDING_INSTRUCTION in self._prompt()
        assert "Never invent a scene" in self._prompt()

    def test_grounding_applies_to_all_personas(self):
        for persona in ("writing_partner", "script_consultant", "producer", "dev_exec", "teacher", "audience", "genre_specialist"):
            assert "Never invent a scene" in self._prompt(persona)


class TestCharacterSceneResolution:
    """Writers ask about their script by naming people ('what's Rishi's deal?').
    Those mentions must resolve to the scenes where the character actually
    speaks, so the model gets real text to ground on instead of inventing."""

    def _script(self):
        return ScriptContext({"title": "T", "scenes": [
            {"scene_number": 1, "heading_raw": "EXT. ROAD - NIGHT", "elements": [
                {"type": "character", "text": "DOCTOR (O.S.)"},
                {"type": "dialogue", "text": "We are late."},
            ]},
            {"scene_number": 2, "heading_raw": "INT. HALL - DAY", "elements": [
                {"type": "character", "text": "RISHI"},
                {"type": "dialogue", "text": "Where is he?"},
                {"type": "character", "text": "DOCTOR (CONT'D)"},
                {"type": "dialogue", "text": "Coming."},
            ]},
            {"scene_number": 3, "heading_raw": "INT. CAR - NIGHT", "elements": [
                {"type": "character", "text": "RISHI"},
                {"type": "dialogue", "text": "Not a word of this."},
            ]},
            {"scene_number": 4, "heading_raw": "INT. HOSPITAL - NIGHT", "elements": [
                {"type": "character", "text": "SIDDHARTH"},
                {"type": "dialogue", "text": "He can't know."},
            ]},
            {"scene_number": 5, "heading_raw": "EXT. ALLEY - NIGHT", "elements": [
                {"type": "character", "text": "GOON_TWO"},
                {"type": "dialogue", "text": "Move."},
            ]},
        ]})

    def test_character_mention_resolves_to_their_scenes(self):
        assert resolve_referenced_scenes("what's Rishi's deal in the hall?", self._script()) == [2, 3]

    def test_case_insensitive_mention(self):
        assert resolve_referenced_scenes("the doctor is interesting", self._script()) == [1, 2]

    def test_extension_stripped_base_name_matches(self):
        # 'DOCTOR (O.S.)' in the script must match a plain 'doctor' mention
        assert 1 in resolve_referenced_scenes("Doctor arrives late", self._script())

    def test_explicit_scene_and_character_union(self):
        assert resolve_referenced_scenes("scene 1, and what about Rishi", self._script()) == [1, 2, 3]

    def test_no_mention_no_injection(self):
        assert resolve_referenced_scenes("the pacing feels slow", self._script()) == []

    def test_character_name_not_a_common_word_substring(self):
        # 'AM' is below CHAR_MIN_LEN — 'I am writing' must not resolve anything
        assert resolve_referenced_scenes("I am writing a new draft", self._script()) == []

    def test_nickname_resolves_to_full_name(self):
        # 'siddhu' ~ SIDDHARTH — the writer's everyday name for the character
        assert resolve_referenced_scenes("tell me about siddhu", self._script()) == [4]

    def test_plural_prefix_matches_underscore_name(self):
        # 'the goons' -> GOON (first token of GOON_TWO)
        assert resolve_referenced_scenes("the goons show up", self._script()) == [5]

    def test_short_prefix_matches_name(self):
        # 'doc' -> DOCTOR via prefix (word >= CHAR_MIN_LEN)
        assert resolve_referenced_scenes("doc is interesting", self._script()) == [1, 2]

    def test_unrelated_word_does_not_fuzzy_match(self):
        # 'ravi' vs RAHUL scores well below the bar — must not resolve
        assert resolve_referenced_scenes("ravi is the hero", self._script()) == []


class TestGroundReply:
    """Reply-side hallucination guard: a scene number the model invents that
    doesn't exist in the script gets owned honestly instead of left standing."""

    def _script(self):
        return ScriptContext({"title": "T", "scenes": [
            {"scene_number": 1, "heading_raw": "EXT. ROAD - NIGHT", "elements": []},
            {"scene_number": 2, "heading_raw": "INT. HALL - DAY", "elements": []},
        ]})

    def test_unknown_scene_flagged(self):
        out = _ground_reply("The scene 27 reveal lands hard.", self._script())
        assert "scene 27" in out
        assert "One honest flag" in out

    def test_valid_scene_reference_untouched(self):
        reply = "Scene 2 sets up the pay-off well."
        assert _ground_reply(reply, self._script()) == reply

    def test_no_scene_reference_untouched(self):
        reply = "The pacing drags in act two."
        assert _ground_reply(reply, self._script()) == reply
