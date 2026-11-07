"""A located quote is not a supported claim, and one word was doing both jobs.

Gap 10, filed grade B: a controlled `analyze()` retained a fabricated
contradictory observation carrying an exact, verified quote, and "approximate
quotes can also be marked verified".

The two halves are different mistakes and the code makes both:

1. **"verified" is used for two different findings.** `apply_verification` emits
   `status: "verified"` both for a byte-normalised exact hit (`confidence: 1.0`)
   and for a fuzzy match as loose as the 0.72 threshold, where the model
   *reworded* the line. A writer reading "verified" cannot tell those apart, and
   neither can the desk's "3 of 3 quotes verified" readout. The near-identical
   boundary (0.95) correctly refuses to certify a paraphrase that is *almost*
   the same words — but a coarser paraphrase sails through as verified.

2. **Nothing anywhere says the CLAIM was assessed.** "Quote verified" answers
   "is this text in the script?" — it says nothing about whether the conclusion
   drawn from it follows. A finding can quote a real line exactly and still
   invent the point it makes about it, which is precisely the filed defect. No
   argument-level verifier exists in this pipeline, so the honest statement is
   "we located the text; we did not assess the claim" — not a silent implication
   that a verified quote means a supported finding.

What this file pins:

  * a located-once-exactly quote says `exact`, not merely `verified`;
  * a reworded quote says `approximate` and carries its similarity, so the
    writer can see how loose it is;
  * the report states, in words, that claim assessment did not happen;
  * `verification_summary` counts the two kinds separately, so no reader can
    total them into a single "verified" number by accident;
  * gap 93's rate still divides by QUOTED findings, not by total, and now says
    which part of that is exact.

Not done, deliberately: no "claim supported" boolean is invented. Nothing reads
the argument, so any such field would be fabricated confidence — the same defect
this file is about, one level up.
"""

from __future__ import annotations

import pytest

from screenplay_analyzer.pipeline import AnalysisResult
from screenplay_analyzer.report import render_markdown
from screenplay_analyzer.verifier import (verification_rate, verification_summary,
                                          verify_findings)
from screenplay_parser.models import Element, ElementType, Scene, ScriptDocument

EXACT_LINE = "MARA: I never wanted the house."
PARAPHRASE = "MARA: I never wanted to own the house."


def _doc() -> ScriptDocument:
    doc = ScriptDocument(title="T", author="A", source_format="fountain",
                         source_filename="t.fountain")
    scene = Scene(scene_number=1, heading_raw="INT. HOUSE - DAY")
    scene.elements = [
        Element(type=ElementType.CHARACTER, text="MARA", character="MARA"),
        Element(type=ElementType.DIALOGUE, text="I never wanted the house.",
                character="MARA"),
    ]
    doc.scenes = [scene]
    return doc


def _finding(quote: str, issue: str = "Mara contradicts her stated motive.") -> dict:
    # The real field names: verification reads `evidence_quote` and `scene_refs`,
    # not the display fields the report renders from.
    return {"id": "f1", "category": "dialogue", "scene_refs": [1],
            "evidence_quote": quote, "issue": issue, "suggestion": "x"}


def _verified(quote: str) -> dict:
    return verify_findings([_finding(quote)], _doc())[0]


# ---------------------------------------------------------------------------
# 1. exact and approximate must not share one word
# ---------------------------------------------------------------------------

def test_an_exact_quote_says_exact():
    v = _verified(EXACT_LINE)["verification"]
    assert v["status"] == "verified", v          # the locating status is unchanged
    assert v["match"] == "exact", f"an exact hit did not say so: {v}"
    assert v["confidence"] == 1.0


def test_a_reworded_quote_says_approximate_and_how_loose():
    """The filed half: 'approximate quotes can also be marked verified'."""
    v = _verified(PARAPHRASE)["verification"]
    assert v["status"] == "verified", v
    assert v["match"] == "approximate", (
        f"a reworded quote was reported as if it were exact: {v}")
    assert 0 < v["confidence"] < 1.0, v


def test_a_quote_not_in_the_script_is_still_not_found():
    v = _verified("MARA: Something she never says at all, ever.")["verification"]
    assert v["status"] == "not_found", v


def test_the_corrected_scene_case_is_exact():
    """A quote found elsewhere is an exact hit at a corrected scene."""
    doc = _doc()
    second = Scene(scene_number=2, heading_raw="EXT. GARDEN - NIGHT")
    second.elements = [Element(type=ElementType.ACTION,
                               text="The house burns anyway.")]
    doc.scenes.append(second)
    finding = {"id": "f1", "category": "action", "scene_refs": [1],
               "evidence_quote": "The house burns anyway.",
               "issue": "x", "suggestion": "y"}
    v = verify_findings([finding], doc)[0]["verification"]
    assert v["status"] == "verified"
    assert v["match"] == "exact", v
    assert v["matched_scene"] == 2


# ---------------------------------------------------------------------------
# 2. the counts must not be summable into one comfortable number
# ---------------------------------------------------------------------------

def test_the_summary_separates_exact_from_approximate():
    findings = [_verified(EXACT_LINE)]
    findings.append(verify_findings([_finding(PARAPHRASE)], _doc())[0])

    summary = verification_summary(findings)
    assert summary["exact"] == 1, summary
    assert summary["approximate"] == 1, summary
    # The locating total is preserved so gap 93's arithmetic still works.
    assert summary["verified"] == 2, summary


def test_a_quote_less_finding_is_not_counted_as_either():
    summary = verification_summary(verify_findings([
        {"id": "f2", "category": "theme", "scene_refs": [1],
         "evidence_quote": None, "issue": "x", "suggestion": "y"}], _doc()))
    assert summary["exact"] == 0 and summary["approximate"] == 0, summary
    assert summary["no_quote"] == 1, summary


# ---------------------------------------------------------------------------
# 3. the report must say the claim was never assessed
# ---------------------------------------------------------------------------

def _report(findings) -> str:
    result = AnalysisResult(doc=_doc(), findings=findings)
    result.verification = verification_summary(findings)
    return render_markdown(result)


def test_the_report_says_the_claim_was_not_assessed():
    text = _report([_verified(EXACT_LINE)])
    low = text.lower()
    assert "claim" in low, "the report never mentions the claim at all"
    # The report's own words say it more strongly than "not assessed"; what is
    # asserted is the meaning, not one phrasing of it.
    assert ("does not mean the finding's claim is supported" in low
            or "not assessed" in low
            or "did not assess" in low), (
        "a verified quote still implies a supported finding; the report must say "
        "the claim itself was not assessed:\n" + text[-1400:])
    assert "judge the claim yourself" in low, (
        "the report disclaims the claim without telling the writer what to do "
        "instead:\n" + text[-1400:])


def test_the_report_names_approximate_matches_as_approximate():
    text = _report([verify_findings([_finding(PARAPHRASE)], _doc())[0]])
    low = text.lower()
    assert "reword" in low or "approximate" in low, (
        "a reworded quote is presented without saying it was reworded:\n"
        + text[-1400:])
    assert "not an exact quotation" in low, (
        "the per-finding note that marks a reworded quote is missing:\n"
        + text[-1400:])


def test_the_exact_rate_is_stated_over_quoted_findings():
    """Gap 93's denominator rule, preserved and now split exact/approximate."""
    findings = [_verified(EXACT_LINE),
                verify_findings([_finding(PARAPHRASE)], _doc())[0],
                verify_findings([{"id": "f3", "category": "theme",
                                  "scene_refs": [1], "evidence_quote": None,
                                  "issue": "x", "suggestion": "y"}], _doc())[0]]
    rate = verification_rate(verification_summary(findings))
    assert rate["quoted"] == 2, rate
    assert rate["exact_pct_of_quoted"] == 50.0, rate
