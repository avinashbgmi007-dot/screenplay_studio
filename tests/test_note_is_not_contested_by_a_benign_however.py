"""
Gap 11, second half: a benign "however" was marking a finding contested.

Filed: "benign 'however' was marked contested." `is_refuted` fires on the word
`\bhowever\b` anywhere in a finding's observation, then `demote_contested`
lowers its severity and flags it. "However" is one of the most ordinary words in
English prose and most of its uses are not rebuttals — "however brief the
exchange is on the page" qualifies a duration, it does not contradict anything.

The real pattern is adversative use: HOWEVER followed by a clause that negates
what the note said. The word alone is not evidence.
"""

from screenplay_analyzer.feedback_filter import demote_contested, is_refuted


def _note(issue, observation):
    return {"category": "pacing", "issue": issue,
            "why_it_matters": "x", "observation": observation,
            "severity": "medium", "scene_refs": [1], "evidence_quote": None}


class TestABenignHoweverDoesNotContestTheNote:

    def test_however_qualifying_a_duration_is_not_a_rebuttal(self):
        f = _note("The second beat lands early.",
                  "The scene runs four pages, however brief the exchange is on "
                  "the page - most of it is stage business.")
        assert is_refuted(f) is False, (
            "a note was marked contested for the word 'however' with nothing "
            "rebutted")

    def test_however_introducing_an_exception_is_not_a_rebuttal(self):
        f = _note("The mother never listens to her son.",
                  "She listens in the kitchen scene, however grudgingly.")
        assert is_refuted(f) is False

    def test_a_genuine_adversative_rebuttal_is_still_caught(self):
        # This is the case the guard exists for: the observation says the note
        # is wrong AND says what the script actually shows instead.
        f = _note("The note claims no motivation.",
                  "The note claims no motivation; however, the script explicitly "
                  "shows a direct confrontation.")
        assert is_refuted(f) is True

    def test_the_other_rebuttal_markers_are_untouched(self):
        assert is_refuted(_note("x", "The dialogue actually does not build "
                                      "toward anything.")) is True
        assert is_refuted(_note("x", "This contradicts the previous scene.")) is True
        assert is_refuted(_note("x", "There is no evidence of rising stakes.")) is True

    def test_a_contested_note_still_gets_demoted(self):
        f = _note("The note claims no motivation.",
                  "The note claims no motivation; however, the script explicitly "
                  "shows a direct confrontation.")
        assert is_refuted(f) is True
        demote_contested(f)
        assert f["severity"] == "low" and f["contested"] is True
