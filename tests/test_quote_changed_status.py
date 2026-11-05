"""Gap 129: a third status, so an edited line is not reported as untouched.

The desk asked one yes/no question — "is the quoted line still in the script?" —
and answered `still_present` or `addressed`. Measured on the real function, with
one real sentence (values printed from `quote_change`, not estimated):

    case                       ratio   old verdict      gap-129 verdict
    unchanged                  1.000   still present    unchanged
    comma only                 1.000   still present    unchanged   (normalised away)
    typo fixed                 0.992   still present    changed     <- the defect
    two-word deletion          0.950   still present    changed     <- the defect
    one-word swap              0.928   addressed        gone        (unchanged rule)
    polite reword              0.816   addressed        gone        (unchanged rule)

The defect is precise: anything in the fuzzy branch — not literally present, but
still matching at >= 0.95 — was reported as *still in the script*, i.e. as if the
writer had not touched it. A typo fix and a two-word repair both landed there.
The writer edited the line and the desk said they had not.

**A middle band does not work, and I measured that rather than assuming it.** My
first design used a band from 0.90 to 0.95. The ratios are not ordered the way
"cosmetic vs substantive" would need: a typo (0.992) scores higher than a
two-word deletion (0.950), which scores higher than a one-word swap (0.928) that
the code already calls resolved. So the ratio cannot rank the edits; what it does
tell us reliably is *"not literally there, yet still the same line"*, and that is
exactly the case where the old label lied.

So `changed` asserts only what was measured, and it stays OPEN. Only `gone` may
be reported as addressed. The writer's own `addressed` mark closes a `changed`
row, because "was this edit meant to answer the note?" is not a computation.

The counting contract does not move: `changed` is open, exactly as
`still_present` was. Every total, chip and metric stays where it was.
"""

import json
import pathlib

import pytest

import screenplay_studio.revision as revision
from screenplay_parser import quotematch
from screenplay_parser.models import Element, ElementType, Scene, ScriptDocument

BASE = "She was thinking, not feeling. That is the whole problem with her."
TYPO = "She was thinking, not feelling. That is the whole problem with her."
TWO_WORD = "She was thinking, not feeling. That is the problem with her."
ONE_WORD = BASE.replace("thinking", "feeling")
REWORD = "She was thinking, rather than feeling. That is her whole problem."


def _doc(lines, kind="dialogue"):
    """A one-scene document with the given dialogue lines.

    Built the way `test_quote_agreement.py` builds its documents — copied from
    the file that already exercises this function. (My first two attempts
    guessed `heading=` and a three-argument `ScriptDocument` and every test
    errored on the constructor: the fixture was wrong, not the code.)
    """
    etype = ElementType.DIALOGUE if kind == "dialogue" else ElementType.ACTION
    doc = ScriptDocument(title="T", author=None, source_format="fountain",
                         source_filename="x.fountain")
    scene = Scene(scene_number=1, heading_raw="INT. ROOM - NIGHT")
    for text in lines:
        scene.elements.append(Element(type=etype, text=text, character="GUY"))
    doc.scenes.append(scene)
    return doc


# ---------------------------------------------------------------------------
# The measurements the decision rests on
# ---------------------------------------------------------------------------

class TestTheOverlapIsReal:
    CASES = {
        "identical": (BASE, "unchanged"),
        "comma_only": (BASE.replace("feeling.", "feeling,"), "unchanged"),
        "typo_fixed": (TYPO, "changed"),
        "two_word_deleted": (TWO_WORD, "changed"),
        "one_word_swapped": (ONE_WORD, "gone"),
        "polite_reword": (REWORD, "gone"),
    }

    @pytest.mark.parametrize("name", sorted(CASES))
    def test_each_case_gets_its_answer(self, name):
        text, expected = self.CASES[name]
        assert revision.quote_change(_doc([text]), BASE) == expected

    def test_the_ratio_does_not_order_cosmetic_against_substantive(self):
        """Why a middle band cannot work: these three overlap and even invert."""
        from difflib import SequenceMatcher
        base = quotematch.normalize_text(BASE)

        def r(text):
            return SequenceMatcher(None, quotematch.normalize_text(text), base).ratio()
        assert r(TYPO) > r(TWO_WORD) > r(ONE_WORD), (
            "the typo fix scores HIGHER than a two-word repair, which scores "
            "higher than a one-word swap the code already calls resolved")
        # and all three sit on different sides of the 0.95 line in a way no
        # single cutoff can line up with 'did the writer change this'
        assert r(TYPO) >= revision.QUOTE_CHANGE_THRESHOLD
        assert r(ONE_WORD) < revision.QUOTE_CHANGE_THRESHOLD

    def test_changed_is_exactly_the_fuzzy_branch(self):
        """The definition, stated as a property: `changed` iff the quote is not
        literally present but still matches, which is the branch that used to
        lie."""
        for text, expected in self.CASES.values():
            doc = _doc([text])
            literally = revision.quote_present(doc, BASE) and expected == "unchanged"
            if expected == "changed":
                assert revision.quote_present(doc, BASE) is True
                assert not literally, "changed must not be reachable by containment"


# ---------------------------------------------------------------------------
# What each answer may claim
# ---------------------------------------------------------------------------

class TestWhatEachAnswerClaims:
    def test_an_edited_line_is_never_called_a_fix(self):
        doc = _doc([TYPO])
        assert revision.quote_change(doc, BASE) == "changed"
        assert revision.quote_present(doc, BASE) is True, (
            "the old boolean still says present — that is why the label, not the "
            "boolean, had to change")

    def test_a_rewrite_is_still_a_fix(self):
        assert revision.quote_change(_doc(["She was overthinking it."]), BASE) == "gone"

    def test_an_untouched_line_is_unchanged(self):
        assert revision.quote_change(_doc([BASE]), BASE) == "unchanged"

    def test_a_removed_line_is_gone(self):
        assert revision.quote_change(_doc(["Something else entirely."]), BASE) == "gone"

    @pytest.mark.parametrize("blank", [None, "", "   "])
    def test_a_blank_quote_has_no_claim(self, blank):
        assert revision.quote_change(_doc([BASE]), blank) == "gone"

    def test_a_short_quote_never_gets_the_fuzzy_branch(self):
        """A ratio on three words is noise, so short quotes keep the
        containment-only rule — the old contract, untouched."""
        assert revision.quote_change(_doc(["akkada unnaru andaru"]), "akkada ledu") == "gone"

    def test_case_and_punctuation_are_not_an_edit(self):
        """The writer is not penning an edit by typing a capital letter."""
        assert revision.quote_change(_doc([BASE.upper()]), BASE) == "unchanged"


# ---------------------------------------------------------------------------
# The counting contract: nothing moves
# ---------------------------------------------------------------------------

class TestCountingDoesNotMove:
    def test_changed_counts_as_open(self):
        assert revision.open_status_count(
            {"addressed": 2, "still_present": 1, "changed": 3, "unknown": 4}) == 8

    def test_the_old_arithmetic_would_have_dropped_it(self):
        summary = {"addressed": 0, "still_present": 0, "changed": 5, "unknown": 0}
        assert revision.open_status_count(summary) == 5
        assert (summary["still_present"] + summary["unknown"]) == 0, (
            "the old expression is exactly how 5 edited findings would vanish")

    def test_the_empty_summary_carries_every_status(self):
        assert set(revision._EMPTY_STATUS_SUMMARY) == {
            "addressed", "still_present", "changed", "unknown"}

    def test_totals_are_preserved(self):
        summary = {"addressed": 1, "still_present": 2, "changed": 3, "unknown": 4}
        assert (summary["addressed"] + revision.open_status_count(summary)) == 10


# ---------------------------------------------------------------------------
# End to end, through the real ledger the app reads
# ---------------------------------------------------------------------------

class TestThroughTheRealLedger:
    def test_an_edited_finding_reads_changed_and_stays_open(self, tmp_path, monkeypatch):
        from screenplay_studio.manifest import ProjectManifest

        made = tmp_path / "p"
        made.mkdir()   # ProjectManifest does not create the directory itself
        m = ProjectManifest(project_dir=str(made), title="t",
                            source_filename="s.fountain", source_format=".fountain")
        report = {"findings": [{"category": "dialogue",
                                "issue": "the line explains too much",
                                "evidence_quote": BASE}]}
        with open(m.report_findings_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh)

        monkeypatch.setattr(revision, "load_working", lambda _m: _doc([TYPO]))
        monkeypatch.setattr(revision, "_load_baseline_doc", lambda _m: _doc([BASE]))

        statuses = revision.finding_statuses(m)
        assert statuses["findings"][0]["status"] == "changed", (
            "the writer fixed a typo and the desk reported the line untouched")
        assert statuses["summary"]["changed"] == 1
        assert statuses["summary"]["addressed"] == 0
        assert revision.open_status_count(statuses["summary"]) == 1

    def test_an_untouched_finding_still_reads_still_present(self, tmp_path, monkeypatch):
        from screenplay_studio.manifest import ProjectManifest

        made = tmp_path / "q"
        made.mkdir()
        m = ProjectManifest(project_dir=str(made), title="t",
                            source_filename="s.fountain", source_format=".fountain")
        with open(m.report_findings_path, "w", encoding="utf-8") as fh:
            json.dump({"findings": [{"category": "dialogue", "issue": "x",
                                     "evidence_quote": BASE}]}, fh)
        monkeypatch.setattr(revision, "load_working", lambda _m: _doc([BASE]))
        monkeypatch.setattr(revision, "_load_baseline_doc", lambda _m: _doc([BASE]))

        statuses = revision.finding_statuses(m)
        assert statuses["findings"][0]["status"] == "still_present"
        assert statuses["summary"]["changed"] == 0, (
            "a genuinely untouched line must not be relabelled as edited")


# ---------------------------------------------------------------------------
# Through the HTTP route, not just the function
# ---------------------------------------------------------------------------

class TestThroughTheApiRoute:
    """Reverting the engine's wiring left 22 of 23 tests passing, because most of
    this file calls `quote_change` directly — it proved the function and not the
    connection. These drive the route the SPA actually reads."""

    def _project_with_quote(self, tmp_path, working_line):
        import screenplay_studio.webapp_server as webapp_server
        from screenplay_studio.manifest import ProjectManifest, StageStatus

        webapp_server.PROJECTS_DIR = str(tmp_path / "projects")
        made = tmp_path / "projects" / "act-one"
        made.mkdir(parents=True)
        m = ProjectManifest(project_dir=str(made), title="t",
                            source_filename="s.fountain", source_format=".fountain")
        m.stages["analyze"] = StageStatus(status="complete")
        m.save()
        with open(m.report_findings_path, "w", encoding="utf-8") as fh:
            json.dump({"findings": [{"category": "dialogue", "issue": "explains too much",
                                     "evidence_quote": BASE}]}, fh)
        # the working copy the route's `finding_statuses` reads is patched in by
        # the caller; stashing it on the manifest keeps one helper for both tests
        m.__dict__["_test_working"] = _doc([working_line])
        return m

    def test_the_route_reports_changed(self, tmp_path, monkeypatch):
        import screenplay_studio.webapp_server as webapp_server
        m = self._project_with_quote(tmp_path, TYPO)
        monkeypatch.setattr(webapp_server, "_load_manifest", lambda name: m)
        monkeypatch.setattr(revision, "load_working", lambda _m: m._test_working)
        monkeypatch.setattr(revision, "_load_baseline_doc", lambda _m: _doc([BASE]))
        webapp_server.app.config["TESTING"] = True
        body = webapp_server.app.test_client().get("/api/projects/act-one/edits").get_json()

        summary = body["statuses"]["summary"] if "statuses" in body else body["findings_status"]["summary"]
        assert summary.get("changed") == 1, (
            f"the route did not surface the third status: {summary}")
        assert summary.get("addressed") == 0
        assert revision.open_status_count(summary) == 1

    def test_the_route_still_reports_a_real_fix_as_addressed(self, tmp_path, monkeypatch):
        import screenplay_studio.webapp_server as webapp_server
        m = self._project_with_quote(tmp_path, "She was overthinking it entirely.")
        monkeypatch.setattr(webapp_server, "_load_manifest", lambda name: m)
        monkeypatch.setattr(revision, "load_working", lambda _m: m._test_working)
        monkeypatch.setattr(revision, "_load_baseline_doc", lambda _m: _doc([BASE]))
        webapp_server.app.config["TESTING"] = True
        body = webapp_server.app.test_client().get("/api/projects/act-one/edits").get_json()
        summary = body["statuses"]["summary"] if "statuses" in body else body["findings_status"]["summary"]
        assert summary.get("addressed") == 1
        assert summary.get("changed") == 0
