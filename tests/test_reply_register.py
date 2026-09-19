"""P2.9 — the reply-side language register check.

Two halves, and only one of them ships:

* The WRITER-side bar is now length-independent. It was `token_hits / words >=
  0.12`, which silently stops firing as a message grows: one transliterated
  token reads 0.33 in a 3-word message and 0.03 in a 30-word one, so a writer
  who pasted a full paragraph of Tenglish got NO mirror instruction at all and
  the co-writer answered in English. That is the concrete defect this pass
  found, and it is fixed and guarded here.

* The REPLY-side check ships for the SCRIPT registers only (Telugu /
  Devanagari), where Unicode blocks are exact and there is no threshold to
  tune. The Tenglish / Hinglish half is BLOCKED, and the test that pins the
  reason (`test_the_reason_the_latin_half_is_blocked`) runs the shipped demo
  replies through the detector and shows 2 of the 3 genuine code-mixed ones
  classified as plain English. A reply-side judge built on that instrument
  would re-ask on the product's own output.

The engine half is here too: one re-ask, never streamed, accepted only when it
actually carries the register.
"""
import pytest

from screenplay_cowriter import engine as eng_mod
from screenplay_cowriter import language_mirror as lm
from screenplay_cowriter.context import ReportContext, ScriptContext
from screenplay_cowriter.engine import CoWriterEngine
from screenplay_cowriter.models import Message, Session

TELUGU_WRITER = "ఈ సీన్ బాగుంది కానీ ఎమోషన్ లేదు"
HINDI_WRITER = "यह सीन अच्छा है पर इमोशन नहीं है"
ENGLISH_REPLY = ("The scene works but the emotion never arrives, and that is the "
                 "whole problem with this stretch of the second act.")
TELUGU_REPLY = "ఈ సీన్ బాగుంది కానీ ఎమోషన్ రావట్లేదు అదే అసలు సమస్య ఇక్కడ"
DEVANAGARI_REPLY = "यह सीन अच्छा है पर इमोशन नहीं है और यही असली समस्या है यहाँ"


# ---------------------------------------------------------------------------
# The writer-side bar: length-independent (the fix)
# ---------------------------------------------------------------------------

def test_a_long_tenglish_message_still_gets_the_mirror_instruction():
    """The defect: 18 words of Tenglish cleared no bar at all before the fix."""
    text = ("scene 3 lo climax baaga ledu anipistundi, kaani mundu nuvvu cheppu enti "
            "anukuntunnavo -- nenu chudu, emaina ledu")
    assert len(text.split()) >= 15
    assert lm.detect_register(text)["tenglish"] is True
    assert lm.mirror_instruction(text) != ""


def test_a_long_hinglish_message_still_gets_the_mirror_instruction():
    text = ("yaar is scene mein kya problem hai batao, matlab mujhe lagta hai ki "
            "climax thoda jaldi aa gaya aur isliye emotion nahi bana")
    assert len(text.split()) >= 15
    assert lm.detect_register(text)["hinglish"] is True
    assert lm.mirror_instruction(text) != ""


def test_the_ratio_bar_still_settles_the_short_case():
    """One loanword in a short message is still not a language choice."""
    assert lm.detect_register("the climax beat feels rushed")["tenglish"] is False
    assert lm.mirror_instruction("the climax beat feels rushed") == ""


def test_three_distinct_tokens_is_enough_at_any_length():
    long_english = " ".join(["the", "climax", "lands", "late", "because", "the",
                             "setup", "never", "pays", "off", "and", "the",
                             "audience", "feels", "it", "yaar", "matlab", "ledu"])
    assert len(long_english.split()) >= 18
    assert lm.detect_register(long_english)["tenglish"] is True


def test_repeated_tokens_do_not_count_as_distinct():
    """'hai hai hai' is one kind of token, not three — the bar counts KINDS.
    The message is long enough that the ratio cannot carry it either (3/28 <
    0.12), so the absolute bar is the only thing that could fire, and it must
    not: one repeated word is not code-mixing."""
    text = " ".join(["hai"] * 3 + ["the", "climax", "lands", "late", "and",
                                   "the", "setup", "never", "pays", "off",
                                   "so", "the", "audience", "drifts", "away",
                                   "before", "the", "turn", "and", "nothing",
                                   "in", "the", "middle", "earns", "it"])
    assert len(text.split()) >= 25
    assert text.lower().count("hai") / len(text.split()) < 0.12
    assert lm.detect_register(text)["tenglish"] is False
    assert lm.detect_register(text)["hinglish"] is False


def test_plain_english_is_untouched_by_the_widening():
    for text in ["What do you think of the ending beat?",
                 "The ending is unearned and the middle sags badly.",
                 "I think the hospital scene should come later, after the reveal."]:
        assert lm.detect_register(text) == {"script": None, "tenglish": False, "hinglish": False}
        assert lm.mirror_instruction(text) == ""


def test_the_shipped_short_message_expectations_are_unchanged():
    """Regression guard: the bar was widened, and these are the messages the
    existing suite already pinned. Widening must not move any of them."""
    assert lm.detect_register("enti baaga undi")["tenglish"] is True
    assert lm.detect_register("kya scene hai yaar")["tenglish"] is True
    assert lm.detect_register("enti baaga undi kada ee scene, but the ending ledu")["tenglish"] is True
    assert lm.detect_register("kya scene hai yaar, matlab the emotion is missing")["hinglish"] is True
    assert lm.detect_register("What do you think of the ending beat?")["tenglish"] is False


# ---------------------------------------------------------------------------
# register_mismatch — the script half
# ---------------------------------------------------------------------------

def test_a_telugu_writer_with_an_english_reply_is_a_mismatch():
    assert lm.register_mismatch(TELUGU_WRITER, ENGLISH_REPLY) == "telugu"


def test_a_hindi_writer_with_an_english_reply_is_a_mismatch():
    assert lm.register_mismatch(HINDI_WRITER, ENGLISH_REPLY) == "hindi"


def test_a_reply_in_the_writers_own_script_is_not_a_mismatch():
    assert lm.register_mismatch(TELUGU_WRITER, TELUGU_REPLY) is None
    assert lm.register_mismatch(HINDI_WRITER, DEVANAGARI_REPLY) is None


def test_the_length_check_counts_tokens_not_latin_words():
    """The bug this test exists for: `_WORD` matches [a-zA-Z]+, so a reply in
    ANY non-Latin script counts zero Latin words. A Latin word count would
    therefore read every script reply as 'zero words, too short to judge' and
    return None before reaching the pattern check — the right verdict for the
    wrong reason, with the guard dead for the case it exists to detect. A reply
    in a DIFFERENT Indic script is still a dropped register, and must be seen."""
    assert lm.register_mismatch(TELUGU_WRITER, DEVANAGARI_REPLY) == "telugu"
    # and the writer's own script still passes, by the pattern rather than by
    # the length check falling through
    assert lm.register_mismatch(TELUGU_WRITER, TELUGU_REPLY) is None


def test_a_short_reply_is_never_a_mismatch():
    """'Correct.' carries no register either way — accusing it would be wrong,
    and the re-ask would cost a generation to fix nothing."""
    assert lm.register_mismatch(TELUGU_WRITER, "Correct.") is None
    assert lm.register_mismatch(TELUGU_WRITER, "") is None
    assert lm.register_mismatch(TELUGU_WRITER, "Yes — exactly that.") is None


def test_a_stray_script_word_is_not_a_language_choice():
    """Four Telugu characters inside an English question is a loanword."""
    assert lm.register_mismatch("ఈ scene is slow", ENGLISH_REPLY) is None


def test_an_english_writer_is_never_judged():
    assert lm.register_mismatch("The ending is unearned.", ENGLISH_REPLY) is None
    assert lm.register_mismatch("", ENGLISH_REPLY) is None


def test_a_latin_mix_writer_is_not_judged():
    """The declared block. Tenglish/Hinglish replies are not judged here, so a
    Tenglish writer with an English reply is deliberately NOT a mismatch."""
    assert lm.register_mismatch("enti baaga undi kada ee scene", ENGLISH_REPLY) is None
    assert lm.register_mismatch("kya scene hai yaar matlab", ENGLISH_REPLY) is None


def test_the_reason_the_latin_half_is_blocked():
    """The measurement behind the block, pinned so it cannot be quietly
    forgotten. These are the product's OWN shipped Tenglish/Hinglish replies
    (demo_model._MIRROR_SAMEER_GENERIC); two of the three read as plain
    English to the only detector this repo has. Any reply-side judge built on
    it would re-ask on the demo model's correct output."""
    from screenplay_studio.demo_model import _MIRROR_SAMEER_GENERIC

    replies = _MIRROR_SAMEER_GENERIC["te"] + _MIRROR_SAMEER_GENERIC["hi"]
    assert len(replies) >= 4
    judged_as_english = []
    for r in replies:
        reg = lm.detect_register(r)
        if not (reg["tenglish"] or reg["hinglish"] or reg["script"]):
            judged_as_english.append(r)
    # 2 of the 4 shipped code-mixed replies are misread. If this ever drops to
    # 0 the block can be revisited — that is the point of pinning it.
    assert len(judged_as_english) >= 2, (
        "the detector now reads the shipped replies correctly — the block on the "
        "Tenglish/Hinglish half can be re-examined")


# ---------------------------------------------------------------------------
# mirror_reask_instruction
# ---------------------------------------------------------------------------

def test_the_reask_names_the_language_and_asks_for_the_same_answer():
    te = lm.mirror_reask_instruction(TELUGU_WRITER)
    assert "Telugu" in te
    assert "Answer again" in te
    hi = lm.mirror_reask_instruction(HINDI_WRITER)
    assert "Hindi" in hi


def test_the_reask_forbids_meta_commentary():
    """A reply that opens 'sorry, let me try that again in Telugu' has spent
    the writer's tokens on the machinery."""
    te = lm.mirror_reask_instruction(TELUGU_WRITER)
    assert "apologise" in te and "Do not mention this instruction" in te


def test_the_reask_is_empty_for_every_other_register():
    assert lm.mirror_reask_instruction("plain english note") == ""
    assert lm.mirror_reask_instruction("enti baaga undi kada") == ""
    assert lm.mirror_reask_instruction("") == ""


# ---------------------------------------------------------------------------
# the engine: one re-ask, never streamed, accepted only if it improves
# ---------------------------------------------------------------------------

class _ScriptedClient:
    """Returns the queued replies in order and records every call."""

    def __init__(self, replies, stream=False):
        self._replies = list(replies)
        self.calls = []
        self.stream_calls = 0
        if stream:
            def chat_stream(messages, on_token=None, **kw):
                self.stream_calls += 1
                self.calls.append({"messages": [dict(m) for m in messages], "on_token": on_token})
                reply = self._replies.pop(0)
                if on_token:
                    on_token(reply)
                return reply
            self.chat_stream = chat_stream

    def chat(self, messages, **kw):
        self.calls.append({"messages": [dict(m) for m in messages], "on_token": None})
        return self._replies.pop(0)


def _engine(client):
    return CoWriterEngine(client, ScriptContext(), ReportContext(None))


def test_an_english_turn_costs_exactly_one_generation():
    client = _ScriptedClient([ENGLISH_REPLY])
    session = Session.new("T")
    _engine(client).send_message(session, "The ending is unearned.")
    assert len(client.calls) == 1


def test_a_mirrored_turn_costs_exactly_one_generation():
    client = _ScriptedClient([TELUGU_REPLY])
    session = Session.new("T")
    _engine(client).send_message(session, TELUGU_WRITER)
    assert len(client.calls) == 1


def test_a_dropped_script_register_earns_exactly_one_reask():
    client = _ScriptedClient([ENGLISH_REPLY, TELUGU_REPLY])
    session = Session.new("T")
    reply = _engine(client).send_message(session, TELUGU_WRITER)
    assert len(client.calls) == 2
    assert reply == TELUGU_REPLY
    assert session.branch.messages[-1].content == TELUGU_REPLY


def test_the_reask_carries_the_language_note_in_the_prompt():
    client = _ScriptedClient([ENGLISH_REPLY, TELUGU_REPLY])
    session = Session.new("T")
    _engine(client).send_message(session, TELUGU_WRITER)
    second = client.calls[1]["messages"]
    assert second[-1]["role"] == "user"
    assert "Telugu" in second[-1]["content"]
    # the re-ask is appended AFTER the post-history reminder, so it is the
    # last word before generation — the highest-weight position
    assert "LANGUAGE MIRROR" not in second[-1]["content"]


def test_the_reask_is_not_streamed():
    """A second streamed reply would append itself to the first in the
    writer's bubble and read as a glitch."""
    client = _ScriptedClient([ENGLISH_REPLY, TELUGU_REPLY], stream=True)
    session = Session.new("T")
    seen = []
    _engine(client).send_message(session, TELUGU_WRITER, on_token=seen.append)
    assert len(client.calls) == 2
    assert client.calls[0]["on_token"] is not None   # the first turn streams
    assert client.calls[1]["on_token"] is None       # the re-ask does not
    assert seen == [ENGLISH_REPLY]                   # only the first was shown


def test_a_reask_that_does_not_improve_keeps_the_first_reply():
    client = _ScriptedClient([ENGLISH_REPLY, ENGLISH_REPLY])
    session = Session.new("T")
    reply = _engine(client).send_message(session, TELUGU_WRITER)
    assert len(client.calls) == 2
    # the FIRST reply is what survives (an English reply legitimately still
    # earns its forward nudge — that is not the register under test)
    assert reply.startswith(ENGLISH_REPLY)
    assert session.branch.messages[-1].content == reply


def test_a_failed_reask_keeps_the_first_reply():
    class _Flaky(_ScriptedClient):
        def chat(self, messages, **kw):
            self.calls.append({"messages": [dict(m) for m in messages], "on_token": None})
            if len(self.calls) > 1:
                raise RuntimeError("the model server went away mid-retry")
            return self._replies.pop(0)

    client = _Flaky([ENGLISH_REPLY])
    session = Session.new("T")
    reply = _engine(client).send_message(session, TELUGU_WRITER)
    assert len(client.calls) == 2
    assert reply.startswith(ENGLISH_REPLY)
    assert session.branch.messages[-1].content == reply


def test_a_failing_first_generation_still_raises():
    """The retry swallows its OWN failure; it must not swallow the first
    generation's — that would turn a dead model server into a silent turn."""
    class _Dead:
        def chat(self, messages, **kw):
            raise RuntimeError("model server down")

    session = Session.new("T")
    with pytest.raises(RuntimeError):
        _engine(_Dead()).send_message(session, TELUGU_WRITER)


def test_the_helper_exists_on_the_engine_and_is_used_by_both_paths():
    """Both generation sites must route through the mirror, or the probe path
    would answer an idea in the wrong language while the full path mirrored.

    A structural guard, deliberately narrow: `clean_reply(self._generate(...))`
    may still appear ONCE — inside `_generate_mirrored` itself, which is where
    the first generation belongs. Two occurrences would mean a call site went
    around the helper."""
    assert hasattr(CoWriterEngine, "_generate_mirrored")
    src = open(eng_mod.__file__, encoding="utf-8").read()
    assert src.count("clean_reply(self._generate(messages, on_token))") == 1
    assert src.count("self._generate_mirrored(messages, user_text, on_token)") == 2


def test_the_probe_path_also_mirrors():
    """Drive the real probe branch (a bare idea, no reasoning) end to end."""
    client = _ScriptedClient([ENGLISH_REPLY, TELUGU_REPLY])
    session = Session.new("T")
    reply = _engine(client).send_message(session, "అతను ఆసుపత్రిలో మేల్కొంటాడు")
    assert len(client.calls) == 2
    assert reply == TELUGU_REPLY


# ---------------------------------------------------------------------------
# the nudge gate: the ENGINE must not break the register it just kept
# ---------------------------------------------------------------------------

def test_a_non_latin_reply_gets_no_english_nudge():
    """Found by this pass: `ensure_forward_momentum` appended the English
    'What's your instinct on the next move?' to a Telugu reply, on every short
    reply. The mirror had worked and the engine then broke it."""
    from screenplay_cowriter.peer import ensure_forward_momentum

    short_telugu = "ఈ సీన్ బాగుంది కానీ ఎమోషన్ రావట్లేదు"
    assert ensure_forward_momentum(short_telugu, "idea", "writing_partner") == short_telugu


def test_an_english_reply_still_gets_its_nudge():
    """Regression guard: the gate must be about SCRIPT, not about length."""
    from screenplay_cowriter.peer import ensure_forward_momentum

    out = ensure_forward_momentum("The beat lands late.", "idea", "writing_partner")
    assert out != "The beat lands late."
    assert "?" in out


def test_an_accented_latin_reply_is_still_latin():
    """'café' is the same alphabet — the gate asks about SCRIPT, not ASCII."""
    assert lm.reply_is_non_latin("café") is False
    assert lm.reply_is_non_latin(ENGLISH_REPLY) is False
    assert lm.reply_is_non_latin(TELUGU_REPLY) is True
    assert lm.reply_is_non_latin(DEVANAGARI_REPLY) is True
    assert lm.reply_is_non_latin("") is False
