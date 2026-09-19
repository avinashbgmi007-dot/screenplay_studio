"""GAP-6: the analyzer and the status engine must agree about a quote.

`verifier.verify_finding` said six of the gun_pen report's dialogue findings were
`verified` at confidence 1.0, while `revision.quote_present` called the same
quotes gone. On a script nobody had edited the desk therefore reported eight
findings "addressed by you", the board dropped its Dialogue section (the largest
category on a dialogue-heavy script) and the manuscript rendered no margin ink
at all. `findingPassesFilter` treats a non-open disposition as hidden, so one
disagreement emptied three surfaces at once.

Two independent situations broke the old matcher. Both values are captured from
`studio_projects/gun_pen_2/parsed.json`, scene 1:

    element[7]  'yudhame jarguthundi... “you are the'
    element[8]  'sum of all your choices”'
    finding     '"you are the sum of all your choices"'

The quote spans two line-wrapped elements, and the model wrote straight quotes
where the script has curly ones. The old code substring-matched the raw quote
against one element at a time, then fuzzy-compared the whole quote against that
same element (about 35 characters, so a two-character difference is a ~0.946
score against a 0.95 threshold).

THE CONTRACT THESE TESTS HOLD
    if the verifier accepted a quote as real, the status engine may not call it
    gone.

Both halves matter and they pull in opposite directions: verification must be
lenient (a model paraphrases a real line) while change detection must be strict
(a reworded line is what a writer's edit looks like). The shared code is the
normaliser and the haystack. The thresholds stay separate, and the last class
here fails if anyone ever "unifies" them.
"""

from __future__ import annotations

import inspect

import pytest

from screenplay_parser import quotematch
from screenplay_parser.models import Element, ElementType, Scene, ScriptDocument
from screenplay_analyzer.verifier import (
    FUZZY_MATCH_THRESHOLD,
    verify_findings,
)
from screenplay_studio import revision
from screenplay_studio.diff import diff_findings
from screenplay_studio.revision import quote_present

# The captured real-world pair. Straight quotes in the finding, curly in the
# script, and the line wrapped across two elements.
WRAP_EL_1 = "yudhame jarguthundi... \u201cyou are the"
WRAP_EL_2 = "sum of all your choices\u201d"
WRAP_QUOTE = '"you are the sum of all your choices"'
EXACT_LINE = "Evadraaa nuvvu, akkada em"


def _doc(elements, scene_number: int = 1) -> ScriptDocument:
    doc = ScriptDocument(
        title="T", author=None, source_format="fountain", source_filename="x.fountain",
    )
    scene = Scene(scene_number=scene_number, heading_raw="INT. ROOM - NIGHT")
    for etype, text, who in elements:
        scene.elements.append(Element(type=etype, text=text, character=who))
    doc.scenes.append(scene)
    return doc


D = ElementType.DIALOGUE
A = ElementType.ACTION


def wrapped_doc() -> ScriptDocument:
    """Scene 1 exactly as the real report saw it, quote split over two elements."""
    return _doc([
        (D, WRAP_EL_1, "GUN GUY"),
        (D, WRAP_EL_2, "GUN GUY"),
        (D, EXACT_LINE, "PEN GUY"),
        (A, "He checks his watch.", None),
    ])


# ---------------------------------------------------------------------------
# the two captured situations
# ---------------------------------------------------------------------------

class TestTheCapturedFailures:
    def test_a_quote_wrapped_across_two_elements_is_still_present(self):
        assert quote_present(wrapped_doc(), WRAP_QUOTE) is True

    def test_straight_quote_finding_against_curly_script_is_still_present(self):
        # One element, so the wrap is not the cause here: only the quote
        # characters differ. The old per-element fuzzy scored this ~0.946.
        doc = _doc([(D, "\u201cyou are the sum of all your choices\u201d", "GUN GUY")])
        assert quote_present(doc, WRAP_QUOTE) is True

    def test_the_line_wrapped_case_word_wrapped_too(self):
        # Same failure, no quote characters involved at all.
        doc = _doc([(D, "the sum of all", "GUN GUY"), (D, "your choices", "GUN GUY")])
        assert quote_present(doc, "the sum of all your choices") is True


# ---------------------------------------------------------------------------
# the contract: accepted by the verifier => not "gone" for the status engine
# ---------------------------------------------------------------------------

class TestTheEnginesCannotDisagree:
    def _findings(self):
        return [
            {"category": "dialogue", "scene_refs": [1], "evidence_quote": WRAP_QUOTE},
            {"category": "dialogue", "scene_refs": [1], "evidence_quote": EXACT_LINE},
            # the same wrap, quoted without the quote characters at all
            {"category": "dialogue", "scene_refs": [1],
             "evidence_quote": "you are the sum of all your choices"},
            {"category": "theme", "scene_refs": [1],
             "evidence_quote": "a line that is nowhere in this script at all"},
        ]

    def test_every_quote_the_verifier_accepted_survives_the_status_engine(self):
        doc = wrapped_doc()
        verified = [f for f in verify_findings(self._findings(), doc)
                    if f["verification"]["status"] == "verified"]
        # guard against a vacuous property: if nothing verified, this proves nothing
        assert len(verified) >= 3, [f["verification"] for f in self._findings()]

        for f in verified:
            if f["verification"]["confidence"] != 1.0:
                continue
            assert quote_present(doc, f["evidence_quote"]) is True, f["evidence_quote"]

    def test_the_property_is_real_the_unsupported_quote_is_not_verified(self):
        doc = wrapped_doc()
        out = {f["evidence_quote"]: f["verification"]["status"]
               for f in verify_findings(self._findings(), doc)}
        assert out["a line that is nowhere in this script at all"] == "not_found"


# ---------------------------------------------------------------------------
# the trap: change detection must stay STRICT
# ---------------------------------------------------------------------------

class TestWriterFixesStillRegister:
    """Sharing the verifier's lenient threshold here would kill the fix signal."""

    LINED = "I changed the line entirely now."
    EDITED = "I changed the line completely now."

    def test_untouched_line_is_still_present(self):
        assert quote_present(_doc([(D, self.LINED, "GUY")]), self.LINED) is True

    def test_a_one_word_edit_reads_as_addressed(self):
        assert quote_present(_doc([(D, self.LINED, "GUY")]), self.EDITED) is False

    def test_a_removed_line_reads_as_addressed(self):
        assert quote_present(_doc([(A, "Something else entirely.", None)]), self.LINED) is False

    def test_a_dropped_word_reads_as_addressed(self):
        assert quote_present(_doc([(D, self.LINED, "GUY")]), "I changed the line now.") is False

    def test_a_single_dropped_character_is_still_present(self):
        # Only pass B can catch this one, which is what keeps pass B honest:
        # after normalisation the quote is not a substring of the scene, and the
        # per-element ratio is 0.979 against 0.95.
        script = "Evadraaa nuvvu, akkada em"
        typo = "Evadraaa nuvvu, akkda em"
        assert quote_present(_doc([(D, script, "PEN GUY")]), typo) is True

    def test_the_strict_threshold_is_not_the_verifier_threshold(self):
        # The whole design: two questions, two thresholds. If someone unifies
        # these, a paraphrase stops reading as an edit.
        assert revision.QUOTE_CHANGE_THRESHOLD != FUZZY_MATCH_THRESHOLD
        assert revision.QUOTE_CHANGE_THRESHOLD > FUZZY_MATCH_THRESHOLD


# ---------------------------------------------------------------------------
# short quotes, and the unchanged contract
# ---------------------------------------------------------------------------

class TestShortQuotesAndContract:
    def test_a_short_quote_present_by_containment_is_present(self):
        assert quote_present(_doc([(D, EXACT_LINE, "PEN GUY")]), "akkada em") is True

    def test_a_short_quote_is_never_rescued_by_fuzzy(self):
        # Below the word floor a 0.95 fuzzy hit is noise, not evidence.
        doc = _doc([(D, "akkada unnaru andaru", "PEN GUY")])
        assert quote_present(doc, "akkada ledu") is False

    @pytest.mark.parametrize("blank", [None, "", "   ", "\n\t "])
    def test_blank_quotes_are_false_so_status_stays_unknown(self, blank):
        assert quote_present(wrapped_doc(), blank) is False


# ---------------------------------------------------------------------------
# the second caller of the same function (the revision ledger)
# ---------------------------------------------------------------------------

class TestTheRevisionLedgerAgrees:
    def test_a_wrapped_quote_is_not_reported_as_resolved(self):
        old_report = {"findings": [{
            "category": "dialogue", "issue": "on the nose", "evidence_quote": WRAP_QUOTE,
        }]}
        result = diff_findings(old_report, wrapped_doc(), {"findings": []})
        assert result["resolved"] == []
        assert len(result["still_present"]) == 1
        assert result["still_present"][0]["draft_status"] == "still_present"


# ---------------------------------------------------------------------------
# one implementation, not two that happen to agree today
# ---------------------------------------------------------------------------

class TestOneImplementation:
    def test_the_verifier_uses_the_shared_normaliser(self):
        from screenplay_analyzer import verifier
        assert verifier._normalize is quotematch.normalize_text

    def test_the_verifier_uses_the_shared_windowed_match(self):
        from screenplay_analyzer import verifier
        assert verifier._best_fuzzy_match is quotematch.windowed_similarity

    def test_the_verifier_uses_the_shared_scene_joiner(self):
        from screenplay_analyzer import verifier
        assert verifier._scene_full_text is quotematch.find_scene_text

    def test_the_status_engine_uses_the_shared_module(self):
        src = inspect.getsource(revision.quote_present)
        assert "quotematch" in src

    def test_the_punctuation_stripping_regex_has_one_home(self):
        # A second copy of this regex is how the two engines drifted apart.
        from screenplay_analyzer import verifier
        assert r"[^\w\s]" not in inspect.getsource(verifier)
