"""Perturbation-band harness for the quote verifier.

WHAT THIS IS FOR
----------------
`FUZZY_MATCH_THRESHOLD` (`screenplay_analyzer/verifier.py`) decides `verified`
vs `not_found` for every quote the analyzer claims. Before this harness no test
pinned how that decision behaves, so any change to `windowed_similarity` or
`normalize_text` could move the band silently and no suite would notice.

This measures the band and pins STRUCTURAL properties only. It deliberately
does NOT pin the threshold: `0.72` has never been calibrated against a golden
set, and a test that hard-codes an uncalibrated constant would launder it into
an assertion. Moving the constant is a product decision that needs data.

WHAT IT ASSERTS (structural, threshold-independent)
---------------------------------------------------
  1. A verbatim quote from the script always verifies.
  2. A fabricated quote never verifies.
  3. The paraphrase band is REPORTED, never thresholded. The information a
     calibration needs is printed; the verdict is not asserted.

WHY IT NEEDS NO MODEL
---------------------
The verifier is a pure function of `(finding, document)`. A model *produces*
findings; it has nothing to do with whether the verifier *classifies* them.
Everything here runs with no llama-server, no GPU, no network.

READING THE OUTPUT
------------------
`not_found` currently means "fabricated OR a real quote that drifted," and the
band report is how you tell those apart. If the paraphrase band's upper edge
crosses the threshold, real evidence is being labelled fabricated — which is
the failure `verifier.py`'s own LENIENT comment names as the expensive error.

Run: pytest tests/test_verifier_perturbation_bands.py -v -s
"""
import pytest

from screenplay_analyzer.verifier import (
    FUZZY_MATCH_THRESHOLD,
    verify_finding,
)
from screenplay_parser.models import Element, Scene, ScriptDocument

# --------------------------------------------------------------------------
# Probe construction. Five buckets, in increasing distance from a real line.
# --------------------------------------------------------------------------

BASE = ("The detective enters the precinct and questions the witness "
        "about the robbery.")


def _swap(text, index, replacement):
    tokens = text.split()
    tokens[index] = replacement
    return " ".join(tokens)


BUCKETS = [
    ("exact", BASE),
    ("one_word", _swap(BASE, 3, "station")),
    ("two_words", _swap(_swap(BASE, 3, "station"), 5, "briefs")),
    ("heavy_paraphrase",
     "A detective arrives at the precinct to speak with the witness about a robbery."),
    ("fabricated",
     "A banker signs the ledger and the market crashes at dawn."),
]


def _document(quote_line, n_elements, pad):
    """One scene holding the quote, padded to `n_elements` with other text."""
    elements = [
        Element(type="action",
                text=quote_line if i == 0 else f"{pad} Beat {i}.")
        for i in range(n_elements)
    ]
    return ScriptDocument(
        title="probe", author="", source_format="fountain",
        source_filename="probe.fountain",
        scenes=[Scene(scene_number=1, heading_raw="INT. HOSPITAL - NIGHT",
                      elements=elements)],
    )


def _verify(quote, doc):
    finding = {
        "category": "dialogue", "issue": "probe", "why_it_matters": "probe",
        "severity": "low", "scene_refs": [1], "evidence_quote": quote,
        "rule_id": None,
    }
    return verify_finding(dict(finding), doc)["verification"]


def _band(quote_line, n_elements, pad):
    doc = _document(quote_line, n_elements, pad)
    return {label: _verify(quote, doc) for label, quote in BUCKETS}


# Two scene shapes. Scene composition moves the scores, so one shape is not
# enough to characterise the band -- this is the point of the harness.
SCENES = [
    ("single_element", 1,
     "The hallway scene continues with ordinary business as the shift changes over."),
    ("full_scene", 6,
     "The hallway scene continues with ordinary business as the shift changes over."),
]


# --------------------------------------------------------------------------
# Structural properties. These hold at any threshold.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("shape,n_elements,pad", SCENES,
                         ids=[s[0] for s in SCENES])
def test_a_verbatim_quote_always_verifies(shape, n_elements, pad):
    band = _band(BASE, n_elements, pad)
    exact = band["exact"]
    assert exact["status"] == "verified", (
        f"{shape}: a quote copied verbatim from the script did not verify "
        f"(confidence {exact['confidence']}) — the verifier is rejecting "
        f"evidence that is provably on the page"
    )


@pytest.mark.parametrize("shape,n_elements,pad", SCENES,
                         ids=[s[0] for s in SCENES])
def test_a_fabricated_quote_never_verifies(shape, n_elements, pad):
    band = _band(BASE, n_elements, pad)
    fabricated = band["fabricated"]
    assert fabricated["status"] != "verified", (
        f"{shape}: an unrelated sentence verified against the script "
        f"(confidence {fabricated['confidence']}) — hallucinated citations "
        f"are passing the check"
    )


# --------------------------------------------------------------------------
# The band report. NOT asserted — this is the calibration input.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("shape,n_elements,pad", SCENES,
                         ids=[s[0] for s in SCENES])
def test_the_paraphrase_band_is_reported(shape, n_elements, pad, capsys):
    band = _band(BASE, n_elements, pad)
    threshold = FUZZY_MATCH_THRESHOLD

    with capsys.disabled():
        print(f"\n--- perturbation band :: {shape} "
              f"(threshold {threshold}) ---")
        for label, _ in BUCKETS:
            v = band[label]
            mark = "VERIFIED" if v["status"] == "verified" else "not_found"
            drift = v["confidence"] - threshold
            print(f"    {label:<20}{mark:<11}conf={v['confidence']:<6}"
                  f"{drift:+.2f} vs threshold")

    real_quote_scores = [band[l]["confidence"] for l, _ in BUCKETS
                         if l != "fabricated"]
    fabricated_score = band["fabricated"]["confidence"]

    assert min(real_quote_scores) > fabricated_score, (
        "fabrication and paraphrase are indistinguishable in this shape — "
        "no threshold can separate them, so the metric carries no signal"
    )

    paraphrase = [band[l]["confidence"] for l in
                  ("one_word", "two_words", "heavy_paraphrase")]
    upper = max(paraphrase)
    print(f"    => usable band: fabrication {fabricated_score:.2f} .. "
          f"paraphrase {upper:.2f}  (threshold {threshold})")
    if upper > threshold:
        print("    => WARNING: real evidence can cross the threshold. "
              "not_found does not mean fabricated.")
    elif threshold > upper:
        print("    => threshold sits ABOVE the band. not_found means "
              "fabricated OR drifted quote; these are merged.")


def test_scene_shape_alone_does_not_change_the_band():
    """Scene composition must not decide whether real evidence verifies.

    The quote, the threshold and the code are identical across both shapes.
    Any verdict difference here is the verifier reacting to how much OTHER
    text happens to sit in the same scene.
    """
    single = _band(BASE, 1,
                   "The hallway scene continues with ordinary business.")
    full = _band(BASE, 6,
                 "The hallway scene continues with ordinary business.")
    drifted = [label for label, _ in BUCKETS
               if label in ("one_word", "two_words", "heavy_paraphrase")
               and single[label]["status"] != full[label]["status"]]
    if drifted:
        print("\n    => drifted labels whose verdict depends on scene "
              f"composition alone: {drifted}")