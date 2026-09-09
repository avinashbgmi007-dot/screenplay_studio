"""
Indian-language screenplay parsing.

Three scripts the parser must handle:

1. Tenglish — Telugu spoken-lines written in the Roman alphabet, with standard
   INT./EXT. headings. This is the dominant convention for Telugu/Tamil
   screenwriting and the language of the canonical fixture
   (tests/fixtures/pain_tenglish.fountain, transcribed from the user's
   Pain_FD_4_scenes.pdf).
2. Hindi — Devanagari script, caseless, with इंट./एक्सट. headings and no
   uppercase character cues.
3. Tamil — caseless script with உள்./வெளி. headings.

The parser must treat these the same as an English script: scene boundaries,
speaker attribution, dialogue, parentheticals — and never misread all-caps
time markers ("TWO MONTHS EARLIER") or long action lines as character cues.
"""

import os

from screenplay_parser.heuristics import (
    looks_like_character_cue,
    looks_like_scene_heading,
    parse_scene_heading,
)
from screenplay_parser.text_parser import parse_fountain, parse_text

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "pain_tenglish.fountain")


def _parse_string(content: str, fmt: str = "txt"):
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), f"script.{'fountain' if fmt == 'fountain' else 'txt'}")
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return parse_text(p, source_format=fmt)


# ---------------------------------------------------------------------------
# Tenglish fixture (the user's own script)
# ---------------------------------------------------------------------------

def test_tenglish_fixture_parses_all_scenes():
    doc = parse_fountain(FIXTURE)
    assert len(doc.scenes) == 6
    assert [s.int_ext for s in doc.scenes] == ["INT/EXT", "EXT", "EXT", "INT", "EXT", "INT"]


def test_tenglish_fixture_characters():
    doc = parse_fountain(FIXTURE)
    chars = {c for s in doc.scenes for c in s.characters_present}
    # GOON_ONE (underscore) and GOON ONE (space) must merge into one speaker
    assert "GOON ONE" in chars and "GOON TWO" in chars
    assert "RISHI" in chars and "DOCTOR" in chars and "SIDDHARTH" in chars
    assert "GOON_ONE" not in chars


def test_tenglish_time_markers_are_not_character_cues():
    doc = parse_fountain(FIXTURE)
    for s in doc.scenes:
        for e in s.elements:
            if e.type.value == "character":
                assert not e.text.upper().startswith(
                    ("2 MONTHS", "TWO MONTHS", "1 YEAR", "2 YEARS")
                ), f"time marker misparsed as character: {e.text!r}"


def test_tenglish_dialogue_is_attributed():
    doc = parse_fountain(FIXTURE)
    # "RISHI / Enti?" — Telugu dialogue attributed to the right speaker
    scene = doc.scenes[1]
    dial = [(e.character, e.text) for e in scene.elements if e.type.value == "dialogue"]
    assert ("RISHI", "Enti?") in dial
    assert ("DOCTOR", "Both Physically and Emotionally. Ante shaareerakanga, maanasikanga kuda--") in dial


# ---------------------------------------------------------------------------
# Hindi (Devanagari)
# ---------------------------------------------------------------------------

HINDI = """Title: प्रेम कहानी

इंट. राहुल का घर - रात

राहुल कमरे में अकेला बैठा है

राहुल
(धीरे से)
मुझे कुछ समझ नहीं आ रहा

एक्सट. बाज़ार - दिन

राहुल और पुलिस

पुलिस
रुको!
"""


def test_hindi_scene_headings():
    assert looks_like_scene_heading("इंट. राहुल का घर - रात")
    assert looks_like_scene_heading("एक्सट. बाज़ार - दिन")
    assert looks_like_scene_heading("इंट/एक्सट. गलियारा - सुबह")


def test_hindi_heading_int_ext_values():
    assert parse_scene_heading("इंट. राहुल का घर - रात")["int_ext"] == "INT"
    assert parse_scene_heading("एक्सट. बाज़ार - दिन")["int_ext"] == "EXT"
    assert parse_scene_heading("इंट/एक्सट. गलियारा - सुबह")["int_ext"] == "INT/EXT"


def test_hindi_full_parse():
    doc = _parse_string(HINDI)
    assert len(doc.scenes) == 2
    s1, s2 = doc.scenes
    assert s1.int_ext == "INT" and s2.int_ext == "EXT"
    # the long action beat must not become a character
    assert "राहुल कमरे में अकेला बैठा है" not in s1.characters_present
    # and the mid-scene action beat must not become a character either
    assert "राहुल और पुलिस" not in s2.characters_present
    assert "राहुल" in s1.characters_present and "पुलिस" in s2.characters_present
    # parenthetical + dialogue attribution
    parens = [(e.character, e.text) for e in s1.elements if e.type.value == "parenthetical"]
    dial = [(e.character, e.text) for e in s1.elements if e.type.value == "dialogue"]
    assert parens == [("राहुल", "(धीरे से)")]
    assert dial == [("राहुल", "मुझे कुछ समझ नहीं आ रहा")]


def test_hindi_cue_heuristics():
    # short caseless line followed by content -> cue
    assert looks_like_character_cue("राहुल", next_nonblank_line="मुझे कुछ समझ नहीं आ रहा")
    # followed by a parenthetical -> cue
    assert looks_like_character_cue("राहुल", next_nonblank_line="(धीरे से)")
    # long action line -> not a cue
    assert not looks_like_character_cue("राहुल कमरे में अकेला बैठा है")
    # multi-word action beat followed by another cue -> not a cue
    assert not looks_like_character_cue("राहुल और पुलिस", next_nonblank_line="पुलिस", second_next="रुको!")


# ---------------------------------------------------------------------------
# Tamil
# ---------------------------------------------------------------------------

TAMIL = """உள். குமரன் வீடு - இரவு

குமரன் தனியாக அமர்ந்திருக்கிறான்

குமரன்
(மெதுவாக)
எனக்கு ஒன்றும் புரியவில்லை

வெளி. சந்தை - பகல்

குமரன் மற்றும் போலீஸ்

போலீஸ்
நில்!
"""


def test_tamil_scene_headings():
    assert looks_like_scene_heading("உள். குமரன் வீடு - இரவு")
    assert looks_like_scene_heading("வெளி. சந்தை - பகல்")


def test_tamil_heading_int_ext_values():
    assert parse_scene_heading("உள். குமரன் வீடு - இரவு")["int_ext"] == "INT"
    assert parse_scene_heading("வெளி. சந்தை - பகல்")["int_ext"] == "EXT"


def test_tamil_full_parse():
    doc = _parse_string(TAMIL)
    assert len(doc.scenes) == 2
    s1, s2 = doc.scenes
    assert s1.int_ext == "INT" and s2.int_ext == "EXT"
    assert "குமரன்" in s1.characters_present
    assert "போலீஸ்" in s2.characters_present
    dial = [(e.character, e.text) for e in s2.elements if e.type.value == "dialogue"]
    assert ("போலீஸ்", "நில்!") in dial


# ---------------------------------------------------------------------------
# Mixed Tenglish + Roman conventions still hold
# ---------------------------------------------------------------------------

def test_roman_cue_rejects_underscore_time_marker():
    # GOON_ONE-style underscore names are cues; pure time markers are not
    assert looks_like_character_cue("GOON_ONE (CONT'D)")
    assert not looks_like_character_cue("2 MONTHS LATER")
    assert not looks_like_character_cue("TWO MONTHS EARLIER")
