"""Gap 78: only tight, long-name typo candidates become questions."""

import os
import tempfile

from screenplay_analyzer.continuity import run_continuity_analysis
from screenplay_parser import parse_fountain


def _parse(text):
    with tempfile.NamedTemporaryFile(
        "w", suffix=".fountain", delete=False, encoding="utf-8"
    ) as stream:
        stream.write(text)
        path = stream.name
    try:
        return parse_fountain(path)
    finally:
        os.unlink(path)


def _pair_script(first, second):
    return f"""Title: Name pair
Author: Test

INT. ROOM - DAY

{first}
I heard a sound.

CUT TO:

EXT. STREET - NIGHT

{second}
It was only the wind.
"""


def _variant_findings(script):
    findings, errors = run_continuity_analysis(_parse(script))
    assert errors == []
    return [f for f in findings if f.get("check_id") == "character_name_variant"]


def test_two_edit_family_role_words_are_not_inferred_as_one_person():
    script = _pair_script("MOTHER", "BROTHER")
    doc = _parse(script)

    assert _variant_findings(script) == []
    names = {name for scene in doc.scenes for name in scene.characters_present}
    assert {"MOTHER", "BROTHER"}.issubset(names)


def test_role_name_and_plural_near_pair_is_not_flagged():
    assert _variant_findings(_pair_script("MOTHER", "MOTHERS")) == []


def test_short_name_similarity_is_not_enough_to_claim_an_alias():
    assert _variant_findings(_pair_script("JON", "JOHN")) == []


def test_tight_typo_still_surfaces_as_a_question_not_a_verdict():
    findings = _variant_findings(_pair_script("SIDDHARTH", "SIDDHART"))

    assert len(findings) == 1
    assert findings[0]["severity"] == "low"
    assert "Could they be one character" in findings[0]["issue"]
    assert "If these cues are intended" in findings[0]["why_it_matters"]
