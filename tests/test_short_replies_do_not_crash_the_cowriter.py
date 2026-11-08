"""
Gap 28: a one-word reply could crash the co-writer BEFORE a model was called.

Filed: with a parsed script containing AJAY, `extract_character_refs` raised
`ValueError: max() arg is an empty sequence` for "Hi", "Yes" and a Telugu-script
input. The fuzzy tier computed `max(... for w in words if len(w) >= 4)` with no
guard: when the text holds no Latin word of four or more characters the
generator is empty, and `max()` on empty raises.

"Hi" is not an edge case. It is most of what a writer types.
"""

import pytest

from screenplay_cowriter.context import extract_character_refs


class _Ctx:
    def __init__(self, names):
        self._names = names

    def character_presence(self):
        return {n: [1] for n in self._names}


@pytest.fixture
def ctx():
    return _Ctx(["AJAY", "SIDDHARTH"])


class TestAShortReplyReturnsNoMatchInsteadOfRaising:

    @pytest.mark.parametrize("text", ["Hi", "Yes", "No", "ok", "?", "...", "", "   "])
    def test_short_and_empty_input_returns_empty(self, ctx, text):
        assert extract_character_refs(text, ctx) == []

    def test_native_script_input_does_not_raise(self, ctx):
        # The filed case: a Telugu utterance has no Latin words at all, so the
        # fuzzy tier had nothing to compare and crashed.
        assert extract_character_refs("నమస్కారం", ctx) == []

    def test_punctuation_only_does_not_raise(self, ctx):
        assert extract_character_refs("!!! ... ---", ctx) == []


class TestRealReferencesStillResolve:

    def test_a_whole_name_is_found(self, ctx):
        assert extract_character_refs("What's Ajay doing in this scene?", ctx) == ["AJAY"]

    def test_a_diminutive_still_fuzzy_matches(self, ctx):
        assert extract_character_refs("siddhu's whole deal here", ctx) == ["SIDDHARTH"]

    def test_a_short_input_with_one_long_word_still_matches(self, ctx):
        # "Hi" alone has no candidate, but this must not disable matching when a
        # candidate DOES exist — the guard is a filter, not a feature removal.
        assert "AJAY" in extract_character_refs("hi ajay", ctx)
