"""Gap 24 — native-script speaker cues beyond Devanagari and Tamil.

Measured before the fix, on one synthetic Fountain scene:

    ఇంట. గది - పగలు          (INT. ROOM - DAY, Telugu)
    రాము కిటికీ దగ్గర ...      (action)
    రాము                      (cue)
    నేను వెళ్తున్నాను.         (dialogue)
    సీత                       (cue)
    సరే, జాగ్రత్త.             (dialogue)

parsed to **zero scenes**, and every line was ACTION. Two independent causes,
both fixed here:

1. `_script_share` counted only Devanagari and Tamil, so a Telugu line measured
   0 script characters and fell through to the all-caps test — which no caseless
   line can pass. The scene heading had the same shape of gap: the heading
   tokens for Telugu existed in no table at all.
2. With cues fixed, `రాము` was STILL action: its dialogue line is short, looked
   like a cue itself, and so disqualified the line above it. The lookahead could
   not tell a two-character name from a two-word line of dialogue. A cue does
   not end a sentence; that is now the discriminator.

The register warned "do not infer that all Telugu text will parse incorrectly",
and these tests keep that discipline: the fixtures are minimal, the assertions
are about the elements this parser is supposed to produce, and the languages that
already worked are pinned as controls so a widening of the script table cannot
quietly break them.
"""
import os

import pytest

from screenplay_parser.heuristics import (
    CASELESS_SCRIPTS,
    _script_share,
    looks_like_character_cue,
    looks_like_scene_heading,
    parse_scene_heading,
)
from screenplay_parser.text_parser import parse_fountain

TELUGU = (
    "Title: తెలుగు పరీక్ష\n\n"
    "ఇంట. గది - పగలు\n\n"
    "రాము కిటికీ దగ్గర నిలబడి ఉన్నాడు.\n\n"
    "రాము\n"
    "నేను వెళ్తున్నాను.\n\n"
    "సీత\n"
    "సరే, జాగ్రత్త.\n"
)

HINDI = (
    "Title: हिंदी परीक्षा\n\n"
    "इंट. कमरा - दिन\n\n"
    "रामू खिड़की के पास खड़ा है।\n\n"
    "रामू\n"
    "मैं जा रहा हूँ।\n\n"
    "सीता\n"
    "ठीक है, ध्यान रखना।\n"
)

TAMIL = (
    "Title: தமிழ் சோதனை\n\n"
    "உள். அறை - பகல்\n\n"
    "ராமு ஜன்னலருகே நிற்கிறான்.\n\n"
    "ராமு\n"
    "நான் செல்கிறேன்.\n\n"
    "சீதா\n"
    "சரி, கவனமாக இரு.\n"
)


def _doc(tmp_path, text, name="s.fountain"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return parse_fountain(str(p))


def _element_types(doc):
    return [(el.type.value if hasattr(el.type, "value") else str(el.type), el.text)
            for sc in doc.scenes for el in sc.elements]


# ---------------------------------------------------------------------------
# The reported case
# ---------------------------------------------------------------------------

def test_a_telugu_script_parses_to_a_scene_at_all(tmp_path):
    """Measured before the fix: zero scenes. The heading tokens were in no
    table, so nothing opened a scene and every line fell to front matter."""
    doc = _doc(tmp_path, TELUGU)
    assert doc.scene_count == 1, f"expected one scene, got {doc.scene_count}"


def test_telugu_speaker_cues_are_character_elements(tmp_path):
    doc = _doc(tmp_path, TELUGU)
    cues = [text for kind, text in _element_types(doc) if kind == "character"]
    assert cues == ["రాము", "సీత"], f"cue elements were {cues!r}"


def test_both_telugu_speakers_are_detected(tmp_path):
    """The reported symptom: "detected no speaker"."""
    doc = _doc(tmp_path, TELUGU)
    assert doc.all_characters == ["రాము", "సీత"]


def test_telugu_dialogue_is_attributed_to_its_speaker(tmp_path):
    """A cue that parses but whose dialogue is not attached would be a worse
    answer than the bug: the writer would lose who said what."""
    doc = _doc(tmp_path, TELUGU)
    scene = doc.scenes[0]
    attributed = [(el.text, el.character) for el in scene.elements if el.type.value == "dialogue"]
    assert ("నేను వెళ్తున్నాను.", "రాము") in attributed
    assert ("సరే, జాగ్రత్త.", "సీత") in attributed


def test_a_telugu_action_line_stays_action(tmp_path):
    """Widening the cue test must not turn action into speakers — that is the
    failure mode the register explicitly warned about."""
    doc = _doc(tmp_path, TELUGU)
    actions = [text for kind, text in _element_types(doc) if kind == "action"]
    assert "రాము కిటికీ దగ్గర నిలబడి ఉన్నాడు." in actions
    assert "రాము" not in actions, "the cue must not also appear as action"


def test_the_telugu_scene_heading_carries_its_int_ext_location_and_time(tmp_path):
    parsed = parse_scene_heading("ఇంట. గది - పగలు")
    assert parsed["int_ext"] == "INT"
    assert parsed["location"] == "గది"
    assert parsed["time_of_day"] == "పగలు"


@pytest.mark.parametrize("heading,expected", [
    ("ఇంట. గది - పగలు", "INT"),
    ("ఎక్సట. వీధి - రాత్రి", "EXT"),
    ("బయట. కాలేజీ - సాయంత్రం", "EXT"),
    ("లోపల. హాల్ - ఉదయం", "INT"),
])
def test_telugu_heading_variants(heading, expected):
    assert looks_like_scene_heading(heading) is True
    assert parse_scene_heading(heading)["int_ext"] == expected


# ---------------------------------------------------------------------------
# The second cause: a short line of dialogue is not a cue
# ---------------------------------------------------------------------------

def test_a_shorter_dialogue_line_does_not_disqualify_the_cue_above_it():
    """The measured asymmetry: `సీత` parsed correctly while `రాము` did not,
    purely because "సరే, జాగత్త." was longer than "నేను వెళ్తున్నాను.". Both are
    dialogue; neither should have looked like a cue."""
    # A name: no sentence-final punctuation.
    assert looks_like_character_cue("రాము", "నేను వెళ్తున్నాను.") is True
    assert looks_like_character_cue("సీత", "సరే, జాగర్త్త.") is True
    # Short dialogue IS a full sentence — it must not read as a name.
    assert looks_like_character_cue("నేను వెళ్తున్నాను.", "మరో మాట.") is False


def test_the_same_rule_holds_in_the_scripts_that_already_worked():
    """The fix is not Telugu-specific; the ambiguity is a property of caseless
    scripts, so Hindi and Tamil were exposed to the same asymmetry."""
    assert looks_like_character_cue("रामू", "मैं जा रहा हूँ।") is True
    assert looks_like_character_cue("मैं जा रहा हूँ।", "ठीक है।") is False
    assert looks_like_character_cue("ராமு", "நான் செல்கிறேன்.") is True
    assert looks_like_character_cue("நான் செல்கிறேன்.", "சரி.") is False


def test_the_forced_cue_syntax_is_the_escape_hatch_when_the_heuristic_says_no(tmp_path):
    """A writer whose name the heuristic cannot read (a one-word name, a name
    ending in a period) is not stuck: Fountain's `@` forces a cue.

    The name is normalized on the way in — `normalize_character_name` strips a
    trailing period — so the id is `రాము`, not `రాము.`. That is the documented
    behaviour of the existing code, not something this gap changed; my first
    version of this test asserted the un-normalized spelling and was wrong."""
    text = ("Title: t\n\nINT. ROOM - DAY\n\n"
            "Some action here.\n\n"
            "@రాము.\n"
            "ఒక మాట.\n")
    doc = _doc(tmp_path, text)
    assert doc.all_characters == ["రాము"], doc.all_characters
    kinds = [k for k, _t in _element_types(doc)]
    assert "character" in kinds and "dialogue" in kinds


# ---------------------------------------------------------------------------
# Controls: the languages that already worked must not regress
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected_cues", [
    (HINDI, ["रामू", "सीता"]),
    (TAMIL, ["ராமு", "சீதா"]),
])
def test_existing_languages_are_unchanged(tmp_path, text, expected_cues):
    doc = _doc(tmp_path, text)
    assert doc.scene_count == 1
    cues = [t for k, t in _element_types(doc) if k == "character"]
    assert cues == expected_cues, f"{cues!r} != {expected_cues!r}"
    assert doc.all_characters == sorted(expected_cues)


def test_english_parsing_is_untouched(tmp_path):
    text = ("Title: en\n\nINT. ROOM - DAY\n\nAction line here.\n\n"
            "MARA\nI'll tell you everything.\n\nDEREK\nJust don't.\n")
    doc = _doc(tmp_path, text)
    assert doc.all_characters == ["DEREK", "MARA"]
    assert doc.scene_count == 1


# ---------------------------------------------------------------------------
# The script table itself
# ---------------------------------------------------------------------------

def test_the_caseless_script_set_covers_the_major_indian_scripts():
    """The gap's root cause was a two-entry table. This pins the coverage so a
    future language cannot be added to the heading regexes but missing here."""
    for name, rng in (("devanagari", 0x0900), ("bengali", 0x0980), ("gurmukhi", 0x0A00),
                      ("gujarati", 0x0A80), ("oriya", 0x0B00), ("tamil", 0x0B80),
                      ("telugu", 0x0C00), ("kannada", 0x0C80), ("malayalam", 0x0D00),
                      ("sinhala", 0x0D80)):
        assert any(rng == r.start for r in CASELESS_SCRIPTS), f"{name} missing"


def test_script_share_reports_the_dominant_script_not_just_two():
    """`_script_share` is the function the whole cue test hangs on; it must
    measure whichever caseless script the line is written in.

    Note the letter count: Telugu vowel SIGNS (ా, ు) are combining marks and
    `str.isalpha()` is False for them, so a four-character name has two
    "letters". That asymmetry is exactly why the cue test compares
    `script_chars >= letters * 0.8` rather than to `len()` — and why the char
    count, not the letter count, is what proves the script was recognised."""
    assert _script_share("రాము") == (4, 2)      # Telugu
    assert _script_share("ರಾಮು") == (4, 2)      # Kannada
    assert _script_share("രാമു") == (4, 2)      # Malayalam
    assert _script_share("রামু") == (4, 2)      # Bengali
    # A mixed line is measured against the script it is mostly written in, and
    # the Latin extension counts toward the letters.
    dominant, letters = _script_share("రాము (V.O.)")
    assert dominant == 4 and letters == 4


def test_every_token_parse_scene_heading_accepts_is_a_heading():
    """The class of bug behind this gap, pinned as a property.

    The heading TEST used to come from a hand-written per-language regex while
    the TOKEN MAP was a separate table, so a token could be in one and not the
    other — which is how `లోపల. హాల్ - ఉదయం` failed to open a scene while
    `parse_scene_heading` happily resolved it to INT. Now the pattern is derived
    from the tables, so this holds for every token, in every language.
    """
    from screenplay_parser.heuristics import NATIVE_INT_EXT_MAPS

    checked = 0
    for table in NATIVE_INT_EXT_MAPS:
        for token, expected in table.items():
            if "/" in token:
                continue
            line = f"{token}. గది - పగలు"
            assert looks_like_scene_heading(line) is True, (
                f"token {token!r} is in a token table but is not recognised as a heading")
            assert parse_scene_heading(line)["int_ext"] == expected
            checked += 1
    assert checked >= 10, f"only {checked} tokens were exercised — the tables shrank?"
