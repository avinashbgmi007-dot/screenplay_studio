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
