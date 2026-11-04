"""Gap 23: quote matching must not erase meaningful Indic vowel marks.

The verifier's normaliser stripped everything `\\w` did not match — which in
Python excludes combining marks (Unicode categories Mn and Mc). Telugu,
Devanagari and Tamil all write vowel length as a combining sign, so కాల
("time") and కల ("a pen") normalised to the same string and the verifier
reported a quote that is NOT in the script as `verified` at confidence 1.0.

Driven through the real `normalize_text`, the real `verify_finding` and the
studio's real `quote_present` — never a private copy of the logic.
"""

import unicodedata

import pytest

from screenplay_analyzer import verifier
from screenplay_parser.models import Element, ElementType, Scene, ScriptDocument
from screenplay_parser.quotematch import normalize_text


def _doc_with(text: str) -> ScriptDocument:
    d = ScriptDocument(title="T", author=None, source_format="fountain",
                       source_filename="x.fountain")
    d.scenes.append(Scene(
        scene_number=1, heading_raw="INT. ROOM - DAY",
        elements=[Element(type=ElementType.DIALOGUE, text=text)]))
    return d


def _verify(script_text: str, quote: str) -> dict:
    finding = {"id": "f1", "evidence_quote": quote, "scene_refs": [1]}
    return verifier.verify_finding(finding, _doc_with(script_text))["verification"]


# A short/long vowel pair per script. Each pair is two DIFFERENT words; the
# second member differs from the first only by one combining mark.
VOWEL_PAIRS = [
    pytest.param("కల", "కాల", id="telugu"),
    pytest.param("कल", "काल", id="devanagari"),
    pytest.param("கல", "கால", id="tamil"),
]


class TestCombiningMarksSurviveNormalisation:
    @pytest.mark.parametrize("short,long", VOWEL_PAIRS)
    def test_a_vowel_sign_is_not_deleted(self, short, long):
        assert normalize_text(short) != normalize_text(long), (
            "two different words normalise to the same string — a combining "
            "vowel sign was dropped")

    @pytest.mark.parametrize("short,long", VOWEL_PAIRS)
    def test_the_mark_is_still_there_after_normalising(self, short, long):
        """Stated on the characters themselves, so this cannot pass because
        both words were mangled into some other equal shape."""
        out = normalize_text(long)
        marks = [c for c in out if unicodedata.category(c).startswith("M")]
        assert marks, f"every combining mark was stripped from {long!r} -> {out!r}"

    def test_punctuation_is_still_removed(self):
        """The normaliser's original purpose must survive the fix."""
        assert normalize_text("“you are the\nsum of all your choices”") == (
            "you are the sum of all your choices")
        assert normalize_text('"You are  the SUM!"') == "you are the sum"

    def test_decomposed_and_composed_forms_still_match(self):
        """NFC folding is required: the same word typed two ways must compare
        equal, or a real quote gets rejected for how it was encoded.

        Tamil is used for the fixture because Telugu and Devanagari vowel signs
        are precomposed in Unicode (NFD is a no-op there), so they cannot
        express a decomposed input at all.
        """
        composed = unicodedata.normalize("NFC", "கோ")
        decomposed = unicodedata.normalize("NFD", composed)
        assert decomposed != composed, "fixture is not actually decomposed"
        assert normalize_text(decomposed) == normalize_text(composed)


class TestADifferentWordIsNotAVerifiedQuote:
    SCRIPT = "అతను కాలం గురించి మాట్లాడాడు"      # "he spoke about time"
    ABSENT = "అతను కలం గురించి మాట్లాడాడు"      # "he spoke about a pen"

    def test_the_exact_line_still_verifies(self):
        v = _verify(self.SCRIPT, self.SCRIPT)
        assert v["status"] == "verified" and v["confidence"] == 1.0

    def test_a_word_absent_from_the_script_is_not_verified(self):
        """The defect, end to end: this quote is not in the script."""
        v = _verify(self.SCRIPT, self.ABSENT)
        assert v["status"] != "verified", (
            f"a quote containing a different word was certified as present: {v}")
        assert v["status"] == "not_found"

    def test_an_exact_match_is_distinguishable_from_a_near_match(self):
        """The register asks for exact and approximate to be told apart. An
        exact quote answers 1.0; a one-mark miss must not also answer 1.0."""
        exact = _verify(self.SCRIPT, self.SCRIPT)["confidence"]
        near = _verify(self.SCRIPT, self.ABSENT)["confidence"]
        assert exact == 1.0
        assert near < exact, (
            f"a quote that differs from the script scored as high as the exact "
            f"line ({near} vs {exact})")

    def test_a_genuine_paraphrase_is_still_accepted(self):
        """The tolerance that exists for a small model rewording a real line
        must not be lost while fixing the collision."""
        v = _verify(self.SCRIPT, "అతను కాలం మీద మాట్లాడాడు")
        assert v["status"] == "verified", (
            "a real line, genuinely reworded, is now rejected — the fix "
            "overshot and will report real quotes as fabricated")
        assert v["confidence"] < 1.0


class TestTheWriterEditSignalIsUnchanged:
    """Both engines share the primitives but keep separate thresholds. Fixing
    the normaliser must not blur them: a reworded line is exactly what a
    writer's edit looks like, and it must still read as CHANGED."""

    def test_a_reworded_line_reads_as_changed(self):
        from screenplay_studio.revision import quote_present

        doc = _doc_with("అతను కాలం మీద మాట్లాడాడు")
        assert quote_present(doc, "అతను కాలం గురించి మాట్లాడాడు") is False

    def test_an_untouched_line_reads_as_present(self):
        from screenplay_studio.revision import quote_present

        doc = _doc_with("అతను కాలం గురించి మాట్లాడాడు")
        assert quote_present(doc, "అతను కాలం గురించి మాట్లాడాడు") is True

    def test_only_the_vowel_sign_changed_reads_as_still_present_RESIDUAL(self):
        """RESIDUAL, pinned deliberately so it is not mistaken for fixed.

        `quote_present` is a load-modify READER of change, and its own comment
        states the trade-off: a dropped character scores 0.979 and is treated as
        still present, because a near-identical difference inside one element is
        read as the parse mistyping rather than the writer editing. So an editor
        changing కాలం -> కలం sees that finding stay OPEN in the desk.

        I did NOT change that here. It is a separate, documented decision about
        the writer-fix signal, it would flip behaviour across the whole queue,
        and gap 23 is about the VERIFIER certifying a quote that is absent — which
        is fixed above. This test records the current behaviour so the residual
        stays visible instead of being assumed solved.
        """
        from screenplay_studio.revision import quote_present

        doc = _doc_with("అతను కలం గురించి మాట్లాడాడు")
        assert quote_present(doc, "అతను కాలం గురించి మాట్లాడాడు") is True, (
            "behaviour changed — if quote_present now reports this as edited, "
            "update critique §37 rather than silently keeping this assertion")
