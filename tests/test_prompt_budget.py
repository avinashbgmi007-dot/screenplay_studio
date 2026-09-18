"""The co-writer's prompt has a global budget (C7, M1).

Every block that rides into the system prompt is individually capped, but
nothing capped their SUM: a feature-length script with a heavily flagged report
assembles a prompt larger than a small local model's window, and llama.cpp
truncates it silently — the model then answers from a mangled context with no
sign anything was lost.

The budget is ON by default and sized from the model's reported context window
(see test_prompt_budget_default.py for the default and the derivation). An
explicit 0 still means unlimited. When the budget bites, whole blocks are shed
lowest-value-first and the cut is STATED in the prompt, so a degraded turn is
honest instead of silently wrong.

These tests pin: the shed order is the declared order and is cumulative; the
persona, the guards, the findings and the writer's own relationship card survive
every step; the trim note appears exactly when content actually changed; and a
prompt of ordinary size is left untouched by the default.
"""

import contextlib
import warnings

import pytest

from screenplay_cowriter.context import (
    PROMPT_SHED_LADDER, PROMPT_TRIM_NOTE, PLAIN_TEXT_INSTRUCTION,
    ReportContext, ScriptContext, build_system_prompt, persona_text,
)


@contextlib.contextmanager
def _below_the_floor():
    """These budgets are deliberately under the ladder's floor. That the warning
    fires is the subject of TestAnUnreachableBudgetIsReported, not of the tests
    that just need the ladder walked all the way down."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        yield

MOOD = "MOODBLOCK " * 60          # 600 chars
PAST = "PASTWORKBLOCK " * 20      # 280 chars
CASE = "CASEBLOCK " * 20          # 200 chars
RELATIONSHIP = "RELATIONSHIPCARD " * 10

# The trim note is appended AFTER the fit test, so it has to be paid for out of
# the budget: a budget the ladder can only satisfy by shedding a block smaller
# than the note is not actually satisfiable. These helpers express budgets in
# those terms rather than in magic numbers.
NOTE_COST = len(PROMPT_TRIM_NOTE) + 2


def _budget_after(full, *shed):
    """A budget the ladder reaches only after shedding `shed` (cumulatively)."""
    return len(full) - sum(len(s) for s in shed) + NOTE_COST + 1


def _script(n_scenes=40, n_chars=6):
    scenes = []
    for i in range(1, n_scenes + 1):
        scenes.append({
            "scene_number": i,
            "heading_raw": f"INT. PLACE {i} - NIGHT",
            "elements": [
                {"type": "character", "text": f"CHAR_{i % n_chars}"},
                {"type": "action", "text": "action " * 8},
            ],
        })
    return ScriptContext({"title": "T", "scenes": scenes})


def _report(n_findings=30):
    findings = []
    for i in range(n_findings):
        findings.append({
            "category": "structure",
            "severity": ["high", "medium", "low"][i % 3],
            "issue": f"Issue number {i}",
            "why_it_matters": f"Rationale number {i}",
            "scene_refs": [i + 1],
        })
    return ReportContext({
        "title": "T",
        "coverage": {"recommendation": "consider", "logline": "L", "genre": "G",
                     "tone": "T", "strengths": ["s"], "weaknesses": ["w"]},
        "findings": findings,
    })


def _prompt(**kw):
    kw.setdefault("mood_text", MOOD)
    return build_system_prompt(_script(), _report(), kw.pop("persona", "writing_partner"),
                               kw.pop("mode", "peer"), **kw)


# --------------------------------------------------------------------------
# the default leaves an ordinary prompt alone
# --------------------------------------------------------------------------

class TestTheDefaultLeavesOrdinaryPromptsAlone:
    """The module default is ON — see test_prompt_budget_default.py for that
    contract and for the derivation from the model's window. These pin the other
    half: being on by default must cost a normal prompt nothing. The fixture is
    a 40-scene script with 30 findings, larger than any project staged on disk,
    so anything it loses would be a real project losing it too."""

    def test_an_ordinary_prompt_keeps_every_block(self):
        prompt = _prompt(writer_library_text=PAST)
        assert MOOD in prompt and PAST in prompt
        assert "REPORT FINDINGS:" in prompt
        assert PROMPT_TRIM_NOTE not in prompt

    def test_zero_budget_means_unlimited(self):
        prompt = _prompt(writer_library_text=PAST, budget=0)
        assert MOOD in prompt and PAST in prompt
        assert PROMPT_TRIM_NOTE not in prompt

    def test_a_prompt_inside_the_budget_is_byte_identical(self):
        unbounded = _prompt(writer_library_text=PAST)
        bounded = _prompt(writer_library_text=PAST, budget=len(unbounded) + 1)
        assert bounded == unbounded


# --------------------------------------------------------------------------
# the shed order
# --------------------------------------------------------------------------

class TestShedOrder:
    def test_garnish_goes_before_reference_material(self):
        full = _prompt(writer_library_text=PAST)
        # enough pressure to force the room state out, not enough to reach the
        # past-work step
        trimmed = _prompt(writer_library_text=PAST, budget=_budget_after(full, MOOD))
        assert MOOD not in trimmed, "room state should be the first thing shed"
        assert PAST in trimmed, "past work should survive a one-step trim"
        assert "REPORT FINDINGS:" in trimmed
        assert PROMPT_TRIM_NOTE in trimmed

    def test_the_ladder_is_cumulative(self):
        full = _prompt(writer_library_text=PAST)
        # pressure past the past-work step, so the room state must already be gone
        trimmed = _prompt(writer_library_text=PAST, budget=_budget_after(full, MOOD, PAST))
        assert MOOD not in trimmed
        assert PAST not in trimmed, "past work should go once the pressure passes its step"

    def test_the_doctor_loses_his_case_file_before_past_work(self):
        full = _prompt(persona="script_consultant", mode="evidence_discussion",
                       writer_library_text=PAST, doctor_case_text=CASE)
        assert CASE in full
        trimmed = _prompt(persona="script_consultant", mode="evidence_discussion",
                          writer_library_text=PAST, doctor_case_text=CASE,
                          budget=_budget_after(full, MOOD, CASE))
        assert CASE not in trimmed, "the case file is garnish for the doctor, shed early"
        assert PAST in trimmed, "past work is the more valuable shelf, shed later"

    def test_the_persona_the_guards_and_the_findings_always_survive(self):
        # a budget small enough to walk the whole ladder
        with _below_the_floor():
            trimmed = _prompt(writer_library_text=PAST, budget=2500)
        assert persona_text("writing_partner") in trimmed, "the persona must never be shed"
        assert PLAIN_TEXT_INSTRUCTION in trimmed, "the reply-format guard must never be shed"
        assert "REPORT FINDINGS:" in trimmed, "the findings are the conversation"
        assert "Issue number" in trimmed
        assert PROMPT_TRIM_NOTE in trimmed

    def test_the_writers_relationship_card_is_never_shed(self):
        with _below_the_floor():
            trimmed = _prompt(writer_library_text=PAST, relationship_card=RELATIONSHIP, budget=2500)
        assert RELATIONSHIP in trimmed

    def test_the_ladder_only_moves_forward(self):
        """Each step must carry every earlier key forward — otherwise a later
        step could re-add a block an earlier one shed."""
        previous = {}
        for step in PROMPT_SHED_LADDER:
            for key, value in previous.items():
                if key == "map_chars":
                    assert step[key] <= value, f"the map cap must only tighten: {step}"
                else:
                    assert step.get(key) == value, f"{key} regressed at {step}"
            previous = step
        assert previous.get("report_max") == 12


# --------------------------------------------------------------------------
# the trim note is honest
# --------------------------------------------------------------------------

class TestTrimNoteIsHonest:
    def test_a_prompt_that_already_fits_is_untouched(self):
        unbounded = _prompt(writer_library_text=PAST)
        assert _prompt(writer_library_text=PAST, budget=len(unbounded)) == unbounded

    def test_the_note_is_absent_when_nothing_could_be_removed(self):
        """The ladder can only shed what is there. A prompt with no optional
        blocks, no map and no findings is already minimal — labelling it trimmed
        would tell the model context is missing when nothing was cut."""
        bare = build_system_prompt(ScriptContext({"title": "T"}), ReportContext(None),
                                   "writing_partner", "peer")
        over = build_system_prompt(ScriptContext({"title": "T"}), ReportContext(None),
                                   "writing_partner", "peer", budget=len(bare) - 1)
        assert over == bare, "nothing could be shed, so nothing should have changed"
        assert PROMPT_TRIM_NOTE not in over

    def test_the_note_appears_when_content_actually_changed(self):
        full = _prompt(writer_library_text=PAST)
        trimmed = _prompt(writer_library_text=PAST, budget=_budget_after(full, MOOD))
        assert trimmed != full
        assert PROMPT_TRIM_NOTE in trimmed
        assert trimmed.endswith(PROMPT_TRIM_NOTE), "the note must land last, closest to generation"

    def test_the_note_is_paid_for_out_of_the_budget(self):
        """A prompt that only fits BEFORE the note is appended does not fit: the
        note's own length has to come out of the same budget, or the trim pushes
        the turn back over the limit it was trimming to satisfy.

        The budget here sits in the gap where the two behaviours differ — high
        enough that shedding the room state alone would satisfy it, and low
        enough that the room state plus the note would not."""
        full = _prompt(writer_library_text=PAST)
        budget = len(full) - len(MOOD) + NOTE_COST - 100
        trimmed = _prompt(writer_library_text=PAST, budget=budget)
        assert len(trimmed) <= budget, (
            "the honesty note must not push the prompt back over the budget"
        )


class TestAnUnreachableBudgetIsReported:
    """The ladder has a floor: the persona, the guards, the examples and the
    findings are never shed, so a budget below their sum cannot be met. Silent
    failure there is exactly the defect C7 describes — the operator believes the
    cap is protecting them while the server still truncates."""

    def test_a_budget_below_the_floor_warns(self):
        with pytest.warns(RuntimeWarning, match="unreachable"):
            _prompt(writer_library_text=PAST, budget=1000)

    def test_a_reachable_budget_does_not_warn(self, recwarn):
        full = _prompt(writer_library_text=PAST)
        trimmed = _prompt(writer_library_text=PAST, budget=_budget_after(full, MOOD))
        assert len(trimmed) <= len(full) - len(MOOD) + NOTE_COST + 1
        assert not [w for w in recwarn.list if issubclass(w.category, RuntimeWarning)]

    def test_no_budget_never_warns(self, recwarn):
        _prompt(writer_library_text=PAST)
        _prompt(writer_library_text=PAST, budget=0)
        assert not [w for w in recwarn.list if issubclass(w.category, RuntimeWarning)]


# --------------------------------------------------------------------------
# the bounded renderers
# --------------------------------------------------------------------------

class TestFindingsTrim:
    def test_no_cap_keeps_every_finding(self):
        text = _report(30).compact_summary()
        assert "Issue number 29" in text
        assert "not listed here" not in text

    def test_the_cap_keeps_the_highest_severity_and_states_the_omission(self):
        report = ReportContext({"findings": [
            {"category": "c", "severity": "low", "issue": f"low {i}"} for i in range(5)
        ] + [
            {"category": "c", "severity": "high", "issue": f"high {i}"} for i in range(3)
        ]})
        text = report.compact_summary(max_findings=3)
        assert "high 0" in text and "high 2" in text
        assert "low 0" not in text
        assert "5 further finding(s) not listed here" in text

    def test_the_survivors_keep_report_order(self):
        report = ReportContext({"findings": [
            {"category": "c", "severity": "low", "issue": "first-low"},
            {"category": "c", "severity": "high", "issue": "second-high"},
            {"category": "c", "severity": "medium", "issue": "third-medium"},
        ]})
        text = report.compact_summary(max_findings=2)
        assert text.index("second-high") < text.index("third-medium")

    def test_drop_why_keeps_the_issue_and_loses_the_rationale(self):
        text = _report(3).compact_summary(drop_why=True)
        assert "Issue number 0" in text
        assert "Rationale number 0" not in text


class TestScriptMapTrim:
    def test_no_cap_is_unchanged(self):
        assert _script().script_map(max_chars=0) == _script().script_map()

    def test_character_presence_goes_first(self):
        full = _script().script_map()
        assert "CHARACTER PRESENCE" in full
        text = _script().script_map(max_chars=len(full) - 20)
        assert "CHARACTER PRESENCE" not in text
        assert "Scene 1:" in text
        assert "Character presence omitted for space." in text

    def test_scene_lines_are_cut_from_the_tail_with_a_note(self):
        text = _script().script_map(max_chars=300)
        assert "Scene 1:" in text
        assert "Scene 40:" not in text
        assert "omitted for space" in text

    def test_a_cap_too_small_for_the_header_says_so(self):
        text = _script().script_map(max_chars=10)
        assert "list omitted for space" in text

    def test_a_script_with_no_scenes_still_returns_empty(self):
        assert ScriptContext({"title": "T"}).script_map(max_chars=10) == ""
