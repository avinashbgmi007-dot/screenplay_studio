"""
Gap 11, third claim: "Default character fragment omitted 30 of 83 selected
rules."

I verified that number before designing anything, and it is real: the character
pass selects 83 rules, renders 65,226 chars, and the default 40,000-char budget
admits 53 of them. So 30 never reach the model.

What was NOT true is that the omission is silent. `_render_budgeted` has always
appended "(30 further craft principles omitted to fit the prompt budget)" to the
prompt, and `test_analyzer_prompt_sizing.py` protects that. The defect is
narrower and worse in a different way: **the model was told and the writer was
not.** The writer reads findings cited against named craft principles and has no
way to know that a third of the grounding was shed — and, critically, that the
shed ones are the LOWEST-tier principles, so a defect covered only by a
lower-tier principle was never looked for.

A caveat in the prompt is not a disclosure to the reader. These tests pin the
disclosure to the reader.
"""

from screenplay_analyzer.rules_context import RulesContext
from screenplay_analyzer.report import render_markdown
from screenplay_analyzer.pipeline import AnalysisResult
from screenplay_parser.models import Scene, ScriptDocument


def _ctx():
    return RulesContext()


def _doc():
    return ScriptDocument(title="T", author="A", source_format="fountain",
                          source_filename="t.fountain")


class TestTheOmissionIsRecorded:

    def test_a_capped_fragment_records_what_it_shed(self):
        ctx = _ctx()
        promoted = ctx.fragment_for_pass("character")
        assert promoted, "the character fragment rendered nothing at all"
        rec = ctx.grounding_records()
        assert rec, "a budgeted fragment shed rules and recorded nothing"
        assert rec["selected"] > rec["supplied"] > 0
        assert rec["omitted"] == rec["selected"] - rec["supplied"]

    def test_an_uncapped_fragment_records_nothing(self):
        # Nothing was shed, so there is nothing to disclose. A "12 of 12" line
        # on every report would train the writer to ignore the line that matters.
        ctx = _ctx()
        ctx.prompt_fragment_for_rule("chekhovs_gun")
        assert ctx.grounding_records() == {}

    def test_the_recorded_number_matches_the_prompt_it_describes(self):
        # The record must describe the SAME omission the prompt states, not a
        # re-derivation that could drift from it.
        ctx = _ctx()
        frag = ctx.fragment_for_pass("character")
        rec = ctx.grounding_records()
        assert f"{rec['omitted']} further craft principles" in frag, (
            "the prompt and the record disagree about how many rules were shed")

    def test_a_tighter_budget_sheds_more_and_says_so(self, monkeypatch):
        monkeypatch.setenv("SCREENPLAY_KB_BUDGET", "12000")
        from screenplay_analyzer import rules_context as R
        monkeypatch.setattr(R, "KB_FRAGMENT_CHAR_BUDGET", 12000)
        ctx = _ctx()
        ctx.fragment_for_pass("character")
        rec = ctx.grounding_records()
        assert rec["omitted"] > 30, (
            "a smaller budget dropped fewer rules than the 40k default")


class TestTheWriterIsTold:

    def _report(self, stats):
        r = AnalysisResult(doc=_doc(), findings=[])
        r.stats = stats
        return render_markdown(r)

    def test_the_report_states_the_omission_in_numbers(self):
        text = self._report({"kb_grounding": {
            "selected": 83, "supplied": 53, "omitted": 30, "pct_supplied": 63.9}})
        assert "83 craft principles" in text
        assert "53 reached the model" in text
        assert "30 were left out" in text

    def test_the_report_says_what_the_omission_CANNOT_mean(self):
        # The load-bearing sentence. A writer who reads "every note cites a named
        # principle" will otherwise treat a missing note as proof of a healthy
        # script, when the pass that would have filed it never saw its principle.
        text = self._report({"kb_grounding": {
            "selected": 83, "supplied": 53, "omitted": 30, "pct_supplied": 63.9}})
        assert "absence of a note is not proof" in text.lower(), (
            "the report gives the count but not its consequence")
        assert "low" in text.lower() and "tier" in text.lower(), (
            "the report does not say WHICH rules were shed")

    def test_a_full_supply_report_says_nothing_about_grounding(self):
        text = self._report({"kb_grounding": {
            "selected": 83, "supplied": 83, "omitted": 0, "pct_supplied": 100.0}})
        assert "Craft grounding" not in text

    def test_a_report_with_no_grounding_stats_is_unchanged(self):
        assert "Craft grounding" not in self._report({})
        assert "Craft grounding" not in self._report({"evidence_depth": {"total": 2}})
