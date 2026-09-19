"""P2.8 — let memory be felt, carefully.

Review section 7, item 8: *"permit exactly one class of reference:
craft-preference callbacks ('last time you cut the explainer line and it
worked'), scoped, gated, never about the writer as a person. Today a month of
learning is invisible."*

Two different invisibilities, and the tests pin both:

1. The relationship card learns HOW the writer works but its own rules forbid
   ever speaking it. That prohibition is correct, and
   `TestThePermissionIsCarvedOutAndTheProhibitionSurvives` asserts it is still
   there — this pass narrows nothing.
2. The revision log — every line edit the writer applied and did not undo — was
   read by nobody but undo/redo. It is the only honest source for the permitted
   class, because the memory refresh is forbidden to record script content by
   design. `TestWhatItCounts` pins what can be derived from it, and
   `TestTheWordingCannotBecomeAPersonalClaim` pins the boundary the review drew
   between the WORK and the writer as a person.

The prompt-quality half — whether the co-writer actually uses the callback well
— is BLOCKED, not tested: this repo has no live model to validate a prompt
change against (the same reason P1.5 is open). What ships is the half that can
be proven: the derivation, the gate, the scope, the wording discipline, the
placement, and the shed order.
"""

import os
import re

import pytest

from screenplay_studio import revision
from screenplay_studio.manifest import ProjectManifest

from screenplay_cowriter import memory as mem_mod
from screenplay_cowriter.context import (
    PROMPT_SHED_LADDER, ReportContext, ScriptContext, build_system_prompt,
)
from screenplay_cowriter.engine import CoWriterEngine
from screenplay_cowriter.models import Session

NOW = 1_760_000_000.0
DAY = 86400.0

# The permission text quotes the forbidden phrasings in order to forbid them,
# so a naive scan of the whole block flags the block's own guard. Every wording
# test below scans the FACT bullets only.
FACT_PREFIX = "- "


def _ch():
    """The module under test, reached through a call rather than a top-level
    import.

    `craft_history.py` is new in this pass, so a mutation check that removes it
    would otherwise kill the whole file at collection time and report one error
    instead of grading each test. Reached this way, every test fails on its own
    and says what the fix carries.
    """
    from screenplay_cowriter import craft_history
    return craft_history


def _group(scene, pairs, at):
    """One entry of edits.json, shaped exactly like revision.save_working writes."""
    return {
        "id": "rec", "scene_number": scene,
        "applied": [{"old": o, "new": n, "similarity": 1.0} for o, n in pairs],
        "skipped": [], "applied_at": at,
    }


TWO_SITTINGS = [
    _group(12, [("he walks slowly across the empty room", "he crosses the room"),
                ("and then he says nothing at all", "silence")], NOW - 2 * DAY),
    _group(4, [("the door opens wide", "the door opens")], NOW - DAY),
]


def _history(edits, now=NOW):
    return _ch().build_craft_history(edits, now=now)


def _text(edits, now=NOW):
    return _ch().craft_history_text(_history(edits, now=now))


def _facts(block):
    return [ln for ln in (block or "").splitlines() if ln.startswith(FACT_PREFIX)]


# ---------------------------------------------------------------------------
# the gate: two occasions, not two lines
# ---------------------------------------------------------------------------

class TestTheGateCountsOccasionsNotLines:

    def test_an_empty_log_says_nothing(self):
        assert _history([]) is None
        assert _text([]) == ""

    def test_none_says_nothing(self):
        assert _history(None) is None

    def test_a_single_sitting_says_nothing_even_when_it_is_five_edits(self):
        """The whole risk of this feature is overclaiming from thin evidence.
        Five replacements inside ONE edit group are one decision made once, so
        they must not add up to a pattern."""
        one = [_group(7, [("a b c d e", "a b"), ("f g h i", "f g"),
                          ("j k l m", "j k"), ("n o p q", "n o"),
                          ("r s t u", "r s")], NOW - DAY)]
        assert _history(one) is None

    def test_two_sittings_clear_the_gate(self):
        hist = _history(TWO_SITTINGS)
        assert hist is not None
        assert hist["occasions"] == 2

    def test_records_with_no_applied_lines_are_not_occasions(self):
        """revision.save_working only writes a record when something applied, so
        an empty `applied` list means a damaged or hand-edited log — it must not
        count toward the gate."""
        edits = [_group(1, [("a b", "a")], NOW - DAY), {"scene_number": 2, "applied": []}]
        assert _history(edits) is None

    def test_a_record_without_a_usable_scene_number_is_not_an_occasion(self):
        edits = [_group(1, [("a b", "a")], NOW - DAY),
                 {"scene_number": "x", "applied": [{"old": "a", "new": ""}]}]
        assert _history(edits) is None

    def test_the_gate_is_the_declared_constant(self):
        assert _ch().MIN_OCCASIONS == 2
        one = [_group(1, [("a b", "a")], NOW)]
        assert _history(one) is None
        assert _history(one + [_group(2, [("c d", "c")], NOW)]) is not None


# ---------------------------------------------------------------------------
# what it counts — measured, never inferred
# ---------------------------------------------------------------------------

class TestWhatItCounts:

    def test_it_counts_lines_and_scenes(self):
        hist = _history(TWO_SITTINGS)
        assert hist["lines"] == 3
        assert hist["scenes"] == 2

    def test_direction_is_measured_in_words_not_characters(self):
        """The honest proxy for 'cut' and 'add'. Words, not characters: the
        first pair GAINS five characters while losing a word, and the count must
        follow the words — a character measure would call it an addition."""
        edits = [
            _group(1, [("a b", "aaaaaaaa")], NOW - DAY),
            _group(2, [("a", "a b c")], NOW - DAY),
        ]
        hist = _history(edits)
        assert hist["shorter"] == 1
        assert hist["longer"] == 1

    def test_a_line_that_kept_its_length_is_counted_separately(self):
        edits = [
            _group(1, [("a b c", "d e f")], NOW - DAY),
            _group(2, [("g h i", "g h")], NOW - DAY),
        ]
        hist = _history(edits)
        assert hist["same_length"] == 1
        assert hist["shorter"] == 1

    def test_scenes_are_ranked_by_how_much_work_went_into_them(self):
        edits = [
            _group(9, [("a b c", "a")], NOW - DAY),
            _group(9, [("d e f", "d")], NOW - DAY),
            _group(9, [("g h i", "g")], NOW - DAY),
            _group(2, [("j k l", "j")], NOW - DAY),
        ]
        hist = _history(edits)
        assert [s["scene_number"] for s in hist["top_scenes"]] == [9, 2]
        assert hist["top_scenes"][0]["lines"] == 3

    def test_ties_break_on_the_lower_scene_number(self):
        edits = [
            _group(8, [("a b", "a")], NOW - DAY),
            _group(3, [("c d", "c")], NOW - DAY),
        ]
        assert [s["scene_number"] for s in _history(edits)["top_scenes"]] == [3, 8]

    def test_the_named_scenes_are_capped_but_the_total_is_not(self):
        edits = [_group(n, [("a b c", "a")], NOW - n * 100) for n in range(1, 9)]
        hist = _history(edits)
        assert len(hist["top_scenes"]) == _ch().MAX_SCENES_NAMED
        assert hist["scenes"] == 8

    def test_recency_comes_from_the_newest_applied_at(self):
        assert _history(TWO_SITTINGS)["last_at"] == NOW - DAY

    def test_a_log_with_no_timestamps_still_produces_history(self):
        edits = [_group(1, [("a b", "a")], None), _group(2, [("c d", "c")], None)]
        hist = _history(edits)
        assert hist["last_at"] is None
        assert "revision log" in _text(edits)
        assert "most recent" not in _text(edits).lower()

    def test_a_damaged_log_cannot_break_a_chat_turn(self):
        """This feeds a prompt. Every shape below is one a hand-edited or
        truncated edits.json can actually take."""
        edits = [
            "not a record at all",
            None,
            42,
            {"scene_number": 1, "applied": "not a list"},
            {"scene_number": 1, "applied": ["junk", None, 7]},
            {"scene_number": 5, "applied": [{"old": "a b c", "new": "a"}], "applied_at": NOW - DAY},
            {"scene_number": 6, "applied": [{"old": "d e", "new": "d"}], "applied_at": NOW - DAY},
        ]
        hist = _history(edits)          # must not raise
        assert hist is not None
        assert hist["lines"] == 2
        assert _text(edits)


# ---------------------------------------------------------------------------
# scope — structural, not tagged
# ---------------------------------------------------------------------------

class TestScopeIsStructural:

    def test_the_digest_is_a_pure_function_of_the_records_handed_in(self):
        """The edit log belongs to one project, so a callback about this script
        cannot surface in another. There is no cross-project read to guard
        against: the function only ever sees the list it is given."""
        a = _history(TWO_SITTINGS)
        b = _history(TWO_SITTINGS)
        assert a == b

    def test_it_names_only_scenes_that_are_in_the_log_it_was_given(self):
        block = _text(TWO_SITTINGS)
        named = set(re.findall(r"scene (\d+)", block))
        assert named == {"4", "12"}

    def test_it_never_hands_the_model_the_writers_old_line_text(self):
        """Quoting the OLD text would put lines that no longer exist into the
        prompt as if they were pages — the one way this block could actively
        mislead. The digest counts; it does not quote."""
        block = _text(TWO_SITTINGS)
        assert "he walks slowly across the empty room" not in block
        assert "the door opens wide" not in block


# ---------------------------------------------------------------------------
# the wording boundary: the work, never the person
# ---------------------------------------------------------------------------

class TestTheWordingCannotBecomeAPersonalClaim:

    DISPOSITION = re.compile(
        r"\byou (?:always|never|tend|usually|like|love|prefer|are|'re|seem|come across)\b",
        re.IGNORECASE,
    )

    def test_the_fact_lines_never_describe_the_writer_as_a_person(self):
        """The review's boundary: a craft callback is about the WORK. 'Four
        lines came out shorter' is a count; 'you tend to cut' is a claim about
        someone's taste, and the log cannot support it."""
        for edits in (TWO_SITTINGS, [_group(n, [("a b c", "a")], NOW) for n in (1, 2)]):
            for line in _facts(_text(edits)):
                assert not self.DISPOSITION.search(line), line

    def test_the_facts_are_all_bullets_so_they_read_as_counts(self):
        facts = _facts(_text(TWO_SITTINGS))
        assert len(facts) >= 3
        assert any("line edit(s) applied" in f for f in facts)

    def test_every_number_it_states_matches_the_log(self):
        """TWO_SITTINGS is three line edits in two sittings: 6 words -> 4,
        7 -> 1, and 4 -> 3. All three are cuts."""
        block = _text(TWO_SITTINGS)
        assert "3 line edit(s) applied across 2 scene(s) in 2 sitting(s)" in block
        assert "3 came out shorter" in block
        assert "scene 4 (1 line(s))" in block

    def test_a_single_scene_is_stated_as_such_rather_than_as_a_ranking(self):
        """'Busiest scenes: scene 4' is a lie by implication when there is only
        one — there is nothing to be busiest than."""
        edits = [_group(4, [("a b c", "a")], NOW - DAY),
                 _group(4, [("d e f", "d")], NOW - DAY)]
        block = _text(edits)
        assert "All of it is in scene 4." in block
        assert "Busiest" not in block

    def test_a_capped_scene_list_says_how_many_it_left_out(self):
        edits = [_group(n, [("a b c", "a")], NOW - n * 100) for n in range(1, 9)]
        block = _text(edits)
        assert "5 other scene(s)" in block

    def test_it_does_not_claim_the_edits_worked_only_that_they_were_kept(self):
        """The review's example says 'and it worked'. Nobody measured that. The
        log can prove the writer applied the edit and did not undo it, and the
        block says exactly that and no more."""
        block = _text(TWO_SITTINGS)
        assert "still in effect" in block
        assert "it worked" not in block


# ---------------------------------------------------------------------------
# the permission, and the prohibition it must not weaken
# ---------------------------------------------------------------------------

class TestThePermissionIsCarvedOutAndTheProhibitionSurvives:

    def test_the_permission_names_the_boundary_explicitly(self):
        permission = _ch().CRAFT_HISTORY_PERMISSION
        assert "never about the writer as a person" in permission
        assert "you always" in permission          # named as forbidden
        assert "never as an opener" in permission

    def test_the_permission_restates_that_the_profile_is_still_off_limits(self):
        """The risk of widening a prohibition is that the model hears the
        widening as 'quoting is fine now'. The carve-out has to say what it does
        NOT permit."""
        permission = _ch().CRAFT_HISTORY_PERMISSION
        assert "NOT the memory profile" in permission
        assert "still never quoted" in permission

    def test_the_relationship_card_still_forbids_quoting_the_memory(self):
        """This pass narrows nothing. The card's own rule is untouched — the
        permitted class lives in a different block, sourced from a different
        place."""
        assert "Never quote the memory" in mem_mod.CARD_RULES
        assert "you always say" in mem_mod.CARD_RULES

    def test_the_block_carries_the_permission(self):
        assert _ch().CRAFT_HISTORY_PERMISSION in _text(TWO_SITTINGS)

    def test_the_block_names_the_log_as_its_source(self):
        assert "revision log" in _text(TWO_SITTINGS)


# ---------------------------------------------------------------------------
# it reaches the prompt
# ---------------------------------------------------------------------------

def _script(n_scenes=6):
    return ScriptContext({"title": "T", "scenes": [
        {"scene_number": i, "heading_raw": f"INT. PLACE {i} - NIGHT",
         "elements": [{"type": "action", "text": "action " * 8}]}
        for i in range(1, n_scenes + 1)
    ]})


CARD = "RELATIONSHIPCARD " * 6
MOOD = "MOODBLOCK " * 30


def _prompt(**kw):
    kw.setdefault("relationship_card", CARD)
    kw.setdefault("mood_text", MOOD)
    return build_system_prompt(_script(), ReportContext(None), "writing_partner", "peer", **kw)


class TestItReachesThePrompt:

    def test_the_block_rides_in_the_system_prompt(self):
        block = _text(TWO_SITTINGS)
        assert block in _prompt(craft_history_text=block)

    def test_a_prompt_without_it_is_unchanged(self):
        """None by default: the CLI and every existing caller stay
        byte-identical."""
        assert "revision log" not in _prompt()
        assert _prompt() == _prompt(craft_history_text=None)

    def test_an_empty_block_adds_nothing(self):
        """build_craft_history returns None below the gate and the renderer
        returns '' — the prompt must not gain a blank block for either."""
        assert _prompt(craft_history_text="") == _prompt()
        assert _prompt(craft_history_text=_text([])) == _prompt()

    def test_it_sits_after_the_relationship_card(self):
        """Order is the carve-out. The card forbids quoting the memory; the
        block permits exactly one class and restates the prohibition, so the
        carve-out has to be the last of the two or the card's blanket rule
        swallows the one reference the review asked for."""
        block = _text(TWO_SITTINGS)
        prompt = _prompt(craft_history_text=block)
        assert prompt.index(CARD) < prompt.index(block)

    def test_the_idea_room_never_carries_it(self):
        """An idea page has no scenes and no revision log, so the block has
        nothing to describe. It must not be bolted onto the idea framing."""
        prompt = build_system_prompt(
            _script(), ReportContext(None), "writing_partner", "peer",
            premise={"title": "Idea", "content": "A page."},
            craft_history_text=_text(TWO_SITTINGS),
        )
        assert "revision log" not in prompt


# ---------------------------------------------------------------------------
# the budget sheds it, and the card survives
# ---------------------------------------------------------------------------

class TestTheLadderShedsItBeforeTheCard:

    def test_the_shed_key_exists(self):
        assert any("drop_craft_history" in step for step in PROMPT_SHED_LADDER)

    def test_it_is_shed_second_after_the_room_state(self):
        """Reference material, not conversation: it goes early. It is shed
        before the doctor's case file, the writer's past work and the craft
        principles because it is the most optional of them."""
        first = PROMPT_SHED_LADDER[0]
        assert "drop_mood" in first
        assert "drop_craft_history" in PROMPT_SHED_LADDER[1]
        assert "drop_craft_history" not in first

    def test_the_ladder_still_only_moves_forward_with_the_new_step(self):
        previous = {}
        for step in PROMPT_SHED_LADDER:
            for key, value in previous.items():
                if key == "map_chars":
                    assert step[key] <= value
                else:
                    assert step.get(key) == value, f"{key} regressed at {step}"
            previous = step

    def test_a_tight_budget_sheds_the_history_and_keeps_the_card(self):
        import warnings

        block = _text(TWO_SITTINGS)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            trimmed = _prompt(craft_history_text=block, budget=2500)
        assert block not in trimmed
        assert CARD in trimmed

    def test_the_two_craft_keys_are_not_the_same_key(self):
        """`drop_craft` sheds the report's craft PRINCIPLES; the new key sheds
        the writer's EDIT HISTORY. Same prefix, different block — pinned so a
        later edit cannot collapse them."""
        assert "drop_craft" in PROMPT_SHED_LADDER[-1]
        assert "drop_craft_history" in PROMPT_SHED_LADDER[-1]
        assert PROMPT_SHED_LADDER[-1]["drop_craft_history"] is True


# ---------------------------------------------------------------------------
# the engine resolves it, per turn, both paths
# ---------------------------------------------------------------------------

class _ScriptedClient:
    """Returns the queued replies in order and records every call."""

    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = []

    def chat(self, messages, **kw):
        self.calls.append({"messages": [dict(m) for m in messages]})
        return self._replies.pop(0)


REPLY = ("The scene works, but the emotion never arrives. That is the whole "
         "problem with this stretch of the second act.")


def _system_prompt(client):
    return client.calls[0]["messages"][0]["content"]


class TestTheEngineResolvesIt:

    def test_a_provider_is_resolved_and_reaches_the_prompt(self):
        """The webapp passes a zero-arg provider so the edit-log read is
        deferred to the turn that actually builds a prompt."""
        block = _text(TWO_SITTINGS)
        calls = []

        def provider():
            calls.append(1)
            return block

        client = _ScriptedClient([REPLY])
        CoWriterEngine(client, ScriptContext(), ReportContext(None),
                       craft_history_text=provider).send_message(Session.new("T"), "hi")
        assert calls == [1]
        assert block in _system_prompt(client)

    def test_a_provider_that_raises_costs_the_block_and_nothing_else(self):
        def broken():
            raise OSError("edits.json went away")

        client = _ScriptedClient([REPLY])
        engine = CoWriterEngine(client, ScriptContext(), ReportContext(None),
                                craft_history_text=broken)
        reply = engine.send_message(Session.new("T"), "The ending is unearned.")
        # The reply may gain the engine's own forward nudge; what matters is
        # that the writer still got an answer and lost only the block.
        assert REPLY in reply
        assert "revision log" not in _system_prompt(client)

    def test_plain_text_is_accepted_as_well_as_a_provider(self):
        block = _text(TWO_SITTINGS)
        client = _ScriptedClient([REPLY])
        CoWriterEngine(client, ScriptContext(), ReportContext(None),
                       craft_history_text=block).send_message(Session.new("T"), "hi")
        assert block in _system_prompt(client)

    def test_the_probe_path_carries_it_too(self):
        """A bare idea takes the probe branch. If only the full path carried the
        block, the writer's most casual turns — the ones where a callback lands
        best — would never see it."""
        block = _text(TWO_SITTINGS)
        client = _ScriptedClient([REPLY])
        CoWriterEngine(client, ScriptContext(), ReportContext(None),
                       craft_history_text=block).send_message(Session.new("T"), "Rishi waits.")
        assert block in _system_prompt(client)


# ---------------------------------------------------------------------------
# the webapp provider: real files, and a damaged one
# ---------------------------------------------------------------------------

class TestTheWebappProvider:

    def _manifest(self, tmp_path):
        src = tmp_path / "pages.fountain"
        src.write_text("INT. ROOM - NIGHT\n\nSomeone waits.\n", encoding="utf-8")
        return ProjectManifest.create(str(tmp_path / "proj"), str(src), title="T")

    def test_it_derives_the_block_from_the_projects_edit_log(self, tmp_path):
        import screenplay_studio.webapp_server as webapp_server

        m = self._manifest(tmp_path)
        with open(os.path.join(m.project_dir, "edits.json"), "w", encoding="utf-8") as f:
            import json
            json.dump(TWO_SITTINGS, f)
        block = webapp_server._craft_history_provider(m)()
        assert "revision log" in block
        assert "scene 12" in block

    def test_no_edits_yet_yields_none_rather_than_an_empty_block(self, tmp_path):
        import screenplay_studio.webapp_server as webapp_server

        m = self._manifest(tmp_path)
        assert webapp_server._craft_history_provider(m)() is None

    def test_a_corrupt_log_yields_none_and_does_not_raise(self, tmp_path):
        """A damaged edits.json must not be able to break a chat turn."""
        import screenplay_studio.webapp_server as webapp_server

        m = self._manifest(tmp_path)
        with open(os.path.join(m.project_dir, "edits.json"), "w", encoding="utf-8") as f:
            f.write("{ this is not json")
        assert webapp_server._craft_history_provider(m)() is None

    def test_one_sitting_is_below_the_gate_through_the_real_file(self, tmp_path):
        import screenplay_studio.webapp_server as webapp_server

        m = self._manifest(tmp_path)
        with open(os.path.join(m.project_dir, "edits.json"), "w", encoding="utf-8") as f:
            import json
            json.dump([_group(3, [("a b c", "a")], NOW - DAY)], f)
        assert webapp_server._craft_history_provider(m)() is None


# ---------------------------------------------------------------------------
# the record shape it reads is the one revision.py actually writes
# ---------------------------------------------------------------------------

class TestItReadsTheShapeRevisionActuallyWrites:
    """The digest is only as honest as its reader, so these drive the REAL
    parse -> apply -> save path and read back through revision.edits_log. The
    record shape is exercised rather than assumed."""

    def _project_with_pages(self, tmp_path, text):
        from screenplay_parser import parse_screenplay

        src = tmp_path / "pages.fountain"
        src.write_text(text, encoding="utf-8")
        m = ProjectManifest.create(str(tmp_path / "proj"), str(src), title="T")
        parse_screenplay(m.source_path).save(m.parsed_path)
        m.save()
        revision.ensure_working(m)
        return m

    def test_a_real_applied_edit_round_trips_through_the_digest(self, tmp_path):
        from screenplay_studio import revision

        m = self._project_with_pages(
            tmp_path,
            "INT. ROOM - NIGHT\n\nThe door opens wide and nobody comes in.\n",
        )
        doc = revision.load_working(m)
        scene = doc.scenes[0].scene_number
        result = revision.apply_replacements(doc, scene, [
            {"old": "The door opens wide and nobody comes in.", "new": "The door opens."},
        ])
        assert result["applied"], result["skipped"]
        revision.save_working(m, doc, record={
            "scene_number": scene, "applied": result["applied"],
            "skipped": result["skipped"], "applied_at": NOW - DAY,
        })
        # a second sitting, so the real log clears the gate
        revision.save_working(m, doc, record={
            "scene_number": scene,
            "applied": [{"old": "The door opens.", "new": "The door opens slowly."}],
            "skipped": [], "applied_at": NOW,
        })

        hist = _ch().build_craft_history(revision.edits_log(m), now=NOW)
        assert hist is not None
        assert hist["occasions"] == 2
        assert hist["lines"] == 2
        assert hist["shorter"] == 1     # 8 words -> 3
        assert hist["longer"] == 1      # 3 words -> 4
        assert "revision log" in _ch().craft_history_text(hist)

    def test_an_undone_edit_leaves_the_log_and_so_leaves_the_digest(self, tmp_path):
        """The claim 'the log holds only edits still in effect' is what makes
        'decisions they kept' true. undo_last_edit pops the record — pin it, or
        the wording becomes a lie the day undo changes."""
        from screenplay_studio import revision

        m = self._project_with_pages(
            tmp_path,
            "INT. ROOM - NIGHT\n\nLine one here.\n\nLine two here.\n",
        )
        doc = revision.load_working(m)
        scene = doc.scenes[0].scene_number

        for old, new in (("Line one here.", "Line one."), ("Line two here.", "Line two.")):
            res = revision.apply_replacements(doc, scene, [{"old": old, "new": new}])
            assert res["applied"], res["skipped"]
            revision.save_working(m, doc, record={
                "scene_number": scene, "applied": res["applied"],
                "skipped": res["skipped"], "applied_at": NOW,
            })
        assert len(revision.edits_log(m)) == 2
        revision.undo_last_edit(m)
        assert len(revision.edits_log(m)) == 1
        # back below the gate, so the block retires itself with the decision
        assert _ch().build_craft_history(revision.edits_log(m), now=NOW) is None
