"""
Gap 29: a direct question about subtitles got back an EMPTY reply.

Filed: a fake model answered "Subtitles can help the audience follow the scene"
to "Should I use subtitles?", and the engine returned an empty assistant message
— `clean_reply` removes any sentence containing "subtitle", and the session then
stored that empty string as the answer.

Two separate faults, and the second is the one that made it invisible:

1. The filter did not know what was asked. Removing UNSOLICITED language
   commentary is the job; deleting the answer to a direct question is the filter
   eating its own subject matter.
2. Even when the filter legitimately empties a reply, the ENGINE stored the
   empty string as an assistant message. A blank bubble is indistinguishable from
   a crash, and the writer is told nothing.

The filter's documented contract — a wholly-meta reply cleans to "" — is
preserved and still pinned by tests/test_chat_language_meta.py. The caller now
handles it instead.
"""

from screenplay_cowriter.language_meta import language_filter_notice, strip_language_meta
from screenplay_cowriter.reply_transforms import clean_reply

ANSWER = "Subtitles can help the audience follow the scene."


class TestAnAskedQuestionIsAnswered:

    def test_a_reply_to_should_i_use_subtitles_survives(self):
        out = clean_reply(ANSWER, user_text="Should I use subtitles?")
        assert out.strip(), "the answer to a direct question came back blank"
        assert "subtitles" in out.lower()

    def test_the_filter_still_removes_unsolicited_commentary(self):
        # The filter is not weakened for the general case: only an explicit ask
        # from the writer turns it off for that turn.
        assert strip_language_meta(
            "The script reads as a South Indian language.") == ""

    def test_an_unrelated_question_does_not_unlock_the_filter(self):
        assert strip_language_meta(
            "The dialogue reads as Telugu.", user_text="Is scene 3 slow?") == ""

    def test_a_translation_question_counts_as_asking(self):
        for ask in ("Should I translate the Hindi lines?",
                    "Would captions help here?",
                    "Is this accessible to non-native speakers?"):
            assert strip_language_meta(ANSWER, user_text=ask).strip(), ask


class TestAnEmptiedReplyIsNeverStoredAsBlank:

    def test_the_notice_names_what_happened(self):
        text = language_filter_notice()
        assert "subtitles" in text.lower()
        assert text.strip()

    def test_the_filter_alone_still_empties_a_wholly_meta_reply(self):
        # The documented contract, unchanged — this is why the fix belongs in the
        # caller rather than in the filter.
        assert strip_language_meta("This reads as a South Indian language.") == ""


class TestTheEngineNeverHandsBackABlankReply:
    """The caller-side half, driven through the real method.

    The filter emptying a wholly-meta reply is correct and unchanged. What was
    wrong is that the engine passed that "" straight out, so the session stored
    an empty assistant message and the writer saw a blank bubble. A revert that
    removed the recovery left every other test in this file green -- the filter
    tests cannot see the caller -- so this drives `_generate_mirrored` itself.
    """

    def _engine(self, raw):
        from screenplay_cowriter.engine import CoWriterEngine

        class _E(CoWriterEngine):
            def __init__(self):        # no client, no script, no report
                pass

            def _generate(self, messages, on_token=None):
                return raw

        return _E()

    def test_an_emptied_reply_is_recovered_rather_than_returned_blank(self):
        e = self._engine("This reads as a South Indian language.")
        out = e._generate_mirrored([{"role": "user", "content": "Is scene 3 slow?"}],
                                   "Is scene 3 slow?")
        assert out.strip(), "the engine handed back a blank reply"
        assert "South Indian" in out, (
            "the recovery dropped the model's actual text instead of keeping it")

    def test_the_recovery_says_what_happened(self):
        e = self._engine("This reads as a South Indian language.")
        out = e._generate_mirrored([{"role": "user", "content": "x"}], "x")
        assert "subtitles" in out.lower(), (
            "the writer gets their text back with no explanation for the "
            "appended sentence")

    def test_a_normal_reply_is_returned_unchanged(self):
        e = self._engine("Scene 3 is doing too much work for its length.")
        out = e._generate_mirrored([{"role": "user", "content": "x"}], "x")
        assert out == "Scene 3 is doing too much work for its length."
