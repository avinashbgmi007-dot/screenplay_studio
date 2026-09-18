"""The co-writer's quotes are verified against the script (Wave 3 #4).

Sameer and the doctor quote the pages constantly — it is most of what makes them
feel like they have read the script. It is also the easiest thing for a small
local model to fake: an invented line that sounds like the writer's voice reads
exactly like a real one.

So a quoted span is checked against the script, and an unverifiable one is
flagged rather than deleted — the same "flag, don't silently drop" policy the
analyzer's verifier applies to findings.

The matcher is the analyzer's own (`verifier._normalize` + its fuzzy threshold),
deliberately NOT a second implementation. A naive substring test fails on a quote
that spans a line wrap, and on one typed with straight quotes where the script has
curly ones — which is precisely the defect that made the analyzer report an
entire dialogue category as "addressed" on a script nobody had edited. Several
tests below exist only to pin that the co-writer does not repeat it.

Precision matters more than recall here: a false flag tells the writer their
co-writer is lying when it isn't. Hence the word floor, the containment-first
order, and the fuzzy pass bounded to the scenes actually injected.
"""

import json
import sys

import pytest

from screenplay_cowriter.context import ScriptContext
from screenplay_cowriter.engine import CoWriterEngine
from screenplay_cowriter.models import Session
from screenplay_cowriter.reply_transforms import (
    MAX_QUOTED_SPANS, MIN_QUOTED_WORDS, _QUOTE_FLAG_MARK, verify_reply_quotes,
)


# Scene 1's dialogue is deliberately split across two wrapped elements and ends
# with a CURLY quote — the two properties that break a naive matcher.
SCRIPT = {
    "title": "T",
    "scenes": [
        {"scene_number": 1, "heading_raw": "INT. STAIRWELL - NIGHT",
         "elements": [
             {"type": "character", "text": "MARA"},
             {"type": "dialogue", "text": "You are the sum of all your"},
             {"type": "dialogue", "text": "choices”"},
             {"type": "action", "text": "She turns away."},
         ]},
        {"scene_number": 2, "heading_raw": "EXT. STREET - DAWN",
         "elements": [
             {"type": "character", "text": "DEV"},
             {"type": "dialogue", "text": "The gun is not the point"},
         ]},
    ],
}

WRAPPED = "You are the sum of all your choices"   # spans two elements + curly
SINGLE = "The gun is not the point"               # 6 words, one element


def _script(data=None):
    return ScriptContext(json.loads(json.dumps(data if data is not None else SCRIPT)))


def _flagged(reply, scene_numbers=None, data=None):
    out = verify_reply_quotes(reply, _script(data), scene_numbers)
    return out, out != reply


# --------------------------------------------------------------------------
# genuine quotes must never be flagged
# --------------------------------------------------------------------------

class TestGenuineQuotesPass:
    def test_a_plain_quote_from_the_script_is_untouched(self):
        reply = f'He says "{SINGLE}" and that is the whole scene.'
        assert verify_reply_quotes(reply, _script(), [2]) == reply

    def test_a_quote_spanning_a_line_wrap_is_untouched(self):
        """Scene text is stored line-wrapped, so this quote is not a substring of
        any single element. The verifier's normaliser joins across the wrap; a
        naive matcher would flag a perfectly correct quote."""
        reply = f'That line — "{WRAPPED}" — is the thesis.'
        assert verify_reply_quotes(reply, _script(), [1]) == reply

    def test_a_quote_with_straight_marks_against_a_curly_script_is_untouched(self):
        """The script closes with a curly quote; the model types a straight one.
        The normaliser strips punctuation, so both are the same string."""
        reply = f'"{WRAPPED}" lands because it is earned.'
        assert verify_reply_quotes(reply, _script(), [1]) == reply

    def test_a_quote_from_a_scene_not_injected_this_turn_is_untouched(self):
        """Containment runs against the WHOLE script, so a real line the model
        happens to remember from another scene is not accused."""
        reply = f'It echoes "{SINGLE}" from earlier.'
        assert verify_reply_quotes(reply, _script(), [1]) == reply

    def test_a_near_miss_of_an_injected_scene_is_untouched(self):
        """The fuzzy pass exists so a light paraphrase is not treated as an
        invention — the same generosity the verifier shows findings."""
        reply = 'He says "The gun is not really the point" here.'
        assert verify_reply_quotes(reply, _script(), [2]) == reply

    def test_no_quotes_at_all_is_untouched(self):
        reply = "The scene talks to itself instead of letting us watch."
        assert verify_reply_quotes(reply, _script(), [1]) == reply


# --------------------------------------------------------------------------
# inventions must be flagged
# --------------------------------------------------------------------------

class TestInventionsAreFlagged:
    def test_an_invented_line_is_flagged(self):
        reply = 'He says "the gun is a promise you keep to yourself" at the end.'
        out, flagged = _flagged(reply, [1, 2])
        assert flagged
        assert _QUOTE_FLAG_MARK in out

    def test_the_flag_names_the_wording_it_could_not_find(self):
        reply = 'He says "the gun is a promise you keep to yourself" at the end.'
        out, _ = _flagged(reply, [1, 2])
        assert "the gun is a promise you keep to yourself" in out

    def test_the_flag_does_not_touch_the_reply_body(self):
        """Flag, don't rewrite: the model's words survive intact and the note is
        appended, so the writer can judge the claim themselves."""
        reply = 'He says "the gun is a promise you keep to yourself" at the end.'
        out, _ = _flagged(reply, [1, 2])
        assert out.startswith(reply)

    def test_two_inventions_get_one_flag_that_counts_them(self):
        reply = ('First "the gun is a promise you keep to yourself" then '
                 '"a river remembers every stone it has ever carried".')
        out, flagged = _flagged(reply, [1, 2])
        assert flagged
        assert out.count(_QUOTE_FLAG_MARK) == 1, "one flag per reply, not one per quote"
        assert "(and 1 more)" in out

    def test_a_long_quote_is_truncated_in_the_flag(self):
        # ~280 chars: past the 80-char display cap, inside the 400-char span cap
        # (a span longer than that is not a quote anyone typed, so it is not
        # matched at all — which is why this fixture stays under it).
        long_line = " ".join(f"invented{i}" for i in range(30))
        reply = f'He says "{long_line}" there.'
        out, flagged = _flagged(reply, [1, 2])
        assert flagged
        # The reply BODY keeps the full quote (flag, don't rewrite); it is the
        # appended note that must not re-paste it.
        flag = out[len(reply):]
        assert "…" in flag
        assert long_line not in flag, "the flag must not re-paste the whole quote"


# --------------------------------------------------------------------------
# precision: what must NOT be flagged
# --------------------------------------------------------------------------

class TestPrecision:
    def test_a_short_quoted_phrase_is_not_flagged(self):
        """Conversational quoting is not script quoting. The floor is measured:
        a craft term the real model used was 1 word, a genuine line was 4."""
        reply = 'The "act two" problem is really a "point of view" problem.'
        assert verify_reply_quotes(reply, _script(), [1]) == reply

    def test_a_craft_term_is_not_flagged(self):
        reply = 'The finding was flagged for "on-the-nose" exposition.'
        assert verify_reply_quotes(reply, _script(), [1]) == reply

    def test_the_word_floor_matches_the_measured_case(self):
        assert MIN_QUOTED_WORDS == 4
        reply = 'He said "Journalist ga inka unna" there.'   # 4 words, real case
        # 4 words clears the floor; it is absent from THIS fixture so it flags,
        # which is the point — the floor is inclusive.
        _, flagged = _flagged(reply, [1])
        assert flagged

    def test_the_scene_number_guards_own_note_is_not_treated_as_a_quote(self):
        """`ground_reply` appends `I said "scene 99"`. That is 2 words, so the
        quote floor keeps it out — the two guards do not feed each other."""
        from screenplay_cowriter.reply_transforms import ground_reply
        reply = "This scene 99 is the turn."
        grounded = ground_reply(reply, _script())
        assert '"scene 99"' in grounded
        assert verify_reply_quotes(grounded, _script(), [1]) == grounded


# --------------------------------------------------------------------------
# the fuzzy pass is bounded to the injected scenes
# --------------------------------------------------------------------------

class TestTheFuzzyPassIsBounded:
    def test_bounding_changes_the_outcome_for_a_paraphrase(self):
        """A near-miss of scene 2 passes when scene 2 was injected (the fuzzy
        pass sees it) and flags when nothing was injected (only containment
        runs). This is the behaviour the ~30x speed-up buys, stated explicitly
        rather than left implicit."""
        reply = 'He says "The gun is not really the point" here.'
        assert verify_reply_quotes(reply, _script(), [2]) == reply
        out, flagged = _flagged(reply, None)
        assert flagged, "with no injected scenes only exact containment can pass"

    def test_an_injection_of_an_unrelated_scene_does_not_help(self):
        reply = 'He says "The gun is not really the point" here.'
        out, flagged = _flagged(reply, [1])
        assert flagged, "scene 1 does not contain that line"


# --------------------------------------------------------------------------
# it stays silent when it cannot be sure
# --------------------------------------------------------------------------

class TestStaysSilent:
    def test_the_idea_room_has_no_script_so_nothing_is_flagged(self):
        """A premise discussion quotes hypothetical dialogue by definition."""
        reply = 'She says "we are not leaving this town alive" and it lands.'
        assert verify_reply_quotes(reply, _script({"title": "T", "scenes": []})) == reply

    def test_an_empty_script_is_safe(self):
        reply = 'He says "the gun is a promise you keep to yourself" there.'
        assert verify_reply_quotes(reply, ScriptContext({})) == reply

    def test_a_missing_script_context_is_safe(self):
        reply = 'He says "the gun is a promise you keep to yourself" there.'
        assert verify_reply_quotes(reply, None) == reply

    def test_an_unimportable_verifier_leaves_the_reply_alone(self, monkeypatch):
        """A guard that cannot run must not guess — and must not crash the turn."""
        monkeypatch.setitem(sys.modules, "screenplay_analyzer.verifier", None)
        reply = 'He says "the gun is a promise you keep to yourself" there.'
        assert verify_reply_quotes(reply, _script(), [1]) == reply

    def test_a_script_with_no_usable_text_is_safe(self):
        empty = {"title": "T", "scenes": [{"scene_number": 1, "elements": []}]}
        reply = 'He says "the gun is a promise you keep to yourself" there.'
        assert verify_reply_quotes(reply, _script(empty), [1]) == reply


# --------------------------------------------------------------------------
# re-entry
# --------------------------------------------------------------------------

class TestIdempotence:
    def test_running_the_guard_twice_does_not_stack_flags(self):
        """The flag quotes the wording it could not verify, so a second pass
        would find that quote and fail it again. A guard that corrupts its own
        output on re-entry is a trap for whoever adds a retry path."""
        reply = 'He says "the gun is a promise you keep to yourself" at the end.'
        once, _ = _flagged(reply, [1, 2])
        twice = verify_reply_quotes(once, _script(), [1, 2])
        assert twice == once
        assert twice.count(_QUOTE_FLAG_MARK) == 1


# --------------------------------------------------------------------------
# the span cap
# --------------------------------------------------------------------------

class TestSpanCap:
    def test_only_the_first_spans_are_examined(self):
        """Pins the trade the cap makes, and the only way to observe it: put the
        genuine quotes FIRST and an invention past the cap. Capped, the invention
        is never reached; uncapped, it is. The cost is real and stated — a reply
        that quotes more than MAX_QUOTED_SPANS things gets no verification beyond
        the cap — and it is bought deliberately, because the guard exists to
        catch a fabricated line, not to audit an essay."""
        genuine = " ".join(f'"{SINGLE}"' for _ in range(MAX_QUOTED_SPANS))
        reply = f'{genuine} and finally "a wholly invented line that is not there".'
        assert verify_reply_quotes(reply, _script(), [2]) == reply, (
            "the invention sits past the cap, so it must not be examined"
        )

    def test_the_cap_is_not_so_tight_that_an_ordinary_reply_is_skipped(self):
        assert MAX_QUOTED_SPANS >= 4


# --------------------------------------------------------------------------
# it reaches the persisted reply
# --------------------------------------------------------------------------

class _Client:
    """Records the messages it was asked to complete; returns a canned reply."""

    def __init__(self, reply="Noted.", **kw):
        self.reply = reply
        self.messages = None

    def _remember(self, messages):
        self.messages = messages
        return self.reply

    def chat(self, messages, **kw):
        return self._remember(messages)

    def chat_stream(self, messages, on_token=None, **kw):
        if on_token:
            on_token(self.reply)
        return self._remember(messages)


class TestTheEngineAppliesIt:
    def _run(self, reply, **engine_kw):
        from screenplay_cowriter.context import ReportContext
        client = _Client(reply)
        engine = CoWriterEngine(client, _script(), ReportContext(None), **engine_kw)
        session = Session.new(title="t")
        engine.send_message(session, "what do you make of the line about the gun?")
        return engine, session

    def test_an_invented_quote_is_flagged_in_the_persisted_reply(self):
        _, session = self._run('He says "the gun is a promise you keep to yourself" there.')
        contents = [m.content for m in session.branch.messages if m.role == "assistant"]
        assert contents, "no assistant turn was persisted"
        assert _QUOTE_FLAG_MARK in contents[-1]

    def test_a_genuine_quote_is_not_flagged(self):
        _, session = self._run(f'He says "{SINGLE}" and it works.')
        contents = [m.content for m in session.branch.messages if m.role == "assistant"]
        assert _QUOTE_FLAG_MARK not in contents[-1]
