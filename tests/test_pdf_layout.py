"""
Regression tests for the layout-aware PDF parsing fixes.

The PDF path reconstructs plain lines from positioned text and now attaches
each line's relative column band ('left' | 'dialogue' | 'center' | 'right')
so the shared classifier can tell action from dialogue, catch centered
character cues, and recognize right-aligned transitions — things pure
text heuristics cannot do once an open dialogue block has swallowed
everything after the first cue.

Also covers the extraction cleanup (glyph doubling, page-number footers,
unmapped-glyph normalization) and the shared-classifier rules that apply to
any format: time markers as transitions and multi-line parentheticals.
"""

import os

from screenplay_parser.pdf_parser import (
    _clean_line,
    _collapse_doubled,
    _layout_band,
    _normalize_unmapped,
    _PAGE_NUMBER_RE,
    parse_pdf,
)
from screenplay_parser.text_parser import _parse_lines
from screenplay_parser.heuristics import looks_like_character_cue

RECOVERABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "Pain_FD_4_scenes_recoverable.pdf")


def _parse(lines, layout=None):
    doc = _parse_lines(lines, "pdf", "test.pdf", line_layout=layout)
    return [(e.type.value, e.text, e.character) for s in doc.scenes for e in s.elements]


# ---------------------------------------------------------------------------
# Extraction cleanup
# ---------------------------------------------------------------------------

def test_collapse_doubled_line_handles_single_space():
    # the two interleaved halves differ only where the single space fell on
    # the odd positions — "DDOOCCTTOORR ((CCOONNTT''DD))" -> "DOCTOR (CONT'D)"
    assert _collapse_doubled("DDOOCCTTOORR ((CCOONNTT\u2019\u2019DD))") == "DOCTOR (CONT\u2019D)"
    assert _collapse_doubled("((MMOORREE))") == "(MORE)"
    assert _collapse_doubled("22..") == "2."
    # untouched
    assert _collapse_doubled("DOCTOR") == "DOCTOR"
    assert _collapse_doubled("Rishi, ippativarku Siddharth") == "Rishi, ippativarku Siddharth"


def test_page_number_footers_dropped():
    assert _PAGE_NUMBER_RE.match("2.")
    assert _PAGE_NUMBER_RE.match("3")
    # doubled footer collapses first, then matches
    assert _PAGE_NUMBER_RE.match(_collapse_doubled("22.."))
    # real content is never a bare page number
    assert not _PAGE_NUMBER_RE.match("EXT. ROAD-SIDE - NIGHT")


def test_unmapped_glyph_normalized_to_apostrophe():
    assert _normalize_unmapped("SIDDHU\ufffdS") == "SIDDHU'S"
    assert _clean_line("  GOON_ONE (CONT\ufffdD)  ") == "GOON_ONE (CONT'D)"


def test_layout_bands_relative_to_page_width():
    width = 612.0
    assert _layout_band(108.0, width) == "left"      # action / scene heading
    assert _layout_band(180.0, width) == "dialogue"  # dialogue indent
    assert _layout_band(252.0, width) == "center"    # character cue
    assert _layout_band(462.0, width) == "right"     # transition
    assert _layout_band(None, width) == "left"       # unknown -> conservative


# ---------------------------------------------------------------------------
# Layout-aware classification (shared state machine, layout hints)
# ---------------------------------------------------------------------------

def test_dialogue_closes_when_action_resumes_at_left_margin():
    lines = [
        "INT. ROOM - DAY",
        "DOCTOR",
        "How are you feeling?",
        "Siddhu looks away without answering.",
        "RISHI",
        "Fine.",
    ]
    layout = {1: "center", 2: "dialogue", 3: "left", 4: "center", 5: "dialogue"}
    els = _parse(lines, layout)
    assert ("character", "DOCTOR", "DOCTOR") in els
    assert ("dialogue", "How are you feeling?", "DOCTOR") in els
    assert ("action", "Siddhu looks away without answering.", None) in els
    assert ("character", "RISHI", "RISHI") in els
    assert ("dialogue", "Fine.", "RISHI") in els


def test_centered_cue_mid_dialogue_stream_becomes_new_character():
    lines = ["INT. ROOM - DAY", "DOCTOR", "line one", "RISHI", "line two"]
    layout = {1: "center", 2: "dialogue", 3: "center", 4: "dialogue"}
    els = _parse(lines, layout)
    assert ("character", "RISHI", "RISHI") in els
    assert ("dialogue", "line two", "RISHI") in els


def test_right_aligned_lines_become_transition_and_merge():
    lines = ["INT. ROOM - DAY", "Some action here.", "MATCH CUT", "TO:(EYES OF", "RAHUL)"]
    layout = {1: "left", 2: "right", 3: "right", 4: "right"}
    els = _parse(lines, layout)
    trans = [e for e in els if e[0] == "transition"]
    assert len(trans) == 1
    assert "MATCH CUT" in trans[0][1] and "TO:(EYES OF" in trans[0][1] and "RAHUL)" in trans[0][1]


def test_time_marker_is_transition_not_action():
    lines = ["INT. ROOM - DAY", "2 MONTHS LATER", "INT. OTHER - NIGHT"]
    els = _parse(lines, None)
    assert ("transition", "2 MONTHS LATER", None) in els


def test_multi_line_parenthetical_stays_attributed():
    lines = [
        "INT. ROOM - DAY",
        "RISHI",
        "I don't know",
        "(as he takes a deep",
        "breath)",
        "Anyway.",
    ]
    layout = {1: "center", 2: "dialogue", 3: "center", 4: "dialogue", 5: "dialogue"}
    els = _parse(lines, layout)
    parens = [e for e in els if e[0] == "parenthetical"]
    assert [p[1] for p in parens] == ["(as he takes a deep", "breath)"]
    assert ("dialogue", "Anyway.", "RISHI") in els


def test_contd_cue_with_curly_apostrophe():
    # Final Draft PDFs emit (CONT'D) with U+2019 — must still be a valid cue
    assert looks_like_character_cue("GOON_ONE (CONT\u2019D)", "Betting la paisal anni", "(with a sarcastic smile)")


def test_nonstandard_cue_extension_is_still_a_cue():
    # (KID) isn't in the canonical extension list but is a real cue extension —
    # a centered short all-caps line followed by dialogue must be a cue
    assert looks_like_character_cue("RAHUL (KID)", "Emanna cheppinva ra nagurinchi?")
    assert looks_like_character_cue("RAHUL (PRESENT)", "line here")
    lines = ["INT. ROOM - DAY", "RAHUL (KID)", "Emanna cheppinva ra nagurinchi?"]
    layout = {1: "center", 2: "dialogue"}
    els = _parse(lines, layout)
    # cue text keeps the extension; the normalized character drops it
    assert ("character", "RAHUL (KID)", "RAHUL") in els
    assert ("dialogue", "Emanna cheppinva ra nagurinchi?", "RAHUL") in els


def test_cut_style_and_montage_markers_are_transitions():
    # left-aligned cut/time markers from this script's export — transitions, not action
    assert looks_like_character_cue("FLASHE CUTS:") is False
    for marker in ("FLASHE CUTS:", "PRESENT:", "MONTAGE:", "Montage:"):
        lines = ["INT. ROOM - DAY", "Some action.", marker]
        els = _parse(lines, None)
        assert ("transition", marker, None) in els, marker


def test_the_end_is_a_transition_not_a_character():
    assert looks_like_character_cue("THE END") is False
    lines = ["INT. ROOM - DAY", "Some action.", "THE END"]
    els = _parse(lines, None)
    assert ("transition", "THE END", None) in els
    assert ("character", "THE END", "THE END") not in els


# ---------------------------------------------------------------------------
# End-to-end on the real recoverable PDF
# ---------------------------------------------------------------------------

def test_recoverable_pdf_fixture_parses_correctly():
    doc = parse_pdf(RECOVERABLE)
    assert len(doc.scenes) == 6
    assert doc.parse_confidence == "low"  # PDF path is still best-effort

    # scene 2 (EXT. OPEN PARK): dialogue attributed to the right speakers and
    # the action lines that follow dialogue are NOT swallowed as dialogue
    s2 = doc.scenes[1]
    chars = [e.text for e in s2.elements if e.type.value == "character"]
    assert "RISHI" in chars
    assert "DOCTOR (CONT\u2019D)" in chars
    actions = [e.text for e in s2.elements if e.type.value == "action"]
    assert any("Siddhu alaa nilchoni" in a for a in actions)
    dial = [(e.character, e.text) for e in s2.elements if e.type.value == "dialogue"]
    assert ("RISHI", "Enti?") in dial
    assert ("DOCTOR", "Body ki emaina debhalu thagilina") in dial

    # multi-line custom transitions are merged into single transition elements
    s3 = doc.scenes[2]
    trans3 = [e.text for e in s3.elements if e.type.value == "transition"]
    assert any("MATCH CUT" in t and "EYES OF RAHUL" in t for t in trans3)
    s4 = doc.scenes[3]
    trans4 = [e.text for e in s4.elements if e.type.value == "transition"]
    assert any("DISSOLVE" in t and "SUN RISE" in t for t in trans4)

    # time markers are transitions
    all_trans = [e.text for s in doc.scenes for e in s.elements if e.type.value == "transition"]
    assert "2 MONTHS LATER" in all_trans
    assert "TWO MONTHS EARLIER" in all_trans

    # no page-number footers, no glyph doubling, no replacement chars
    all_text = " ".join(e.text for s in doc.scenes for e in s.elements)
    assert not any(tok.strip() in ("2.", "3.", "4.") for tok in all_text.split("\n"))
    assert "\ufffd" not in all_text
    assert "DDOOCCTTOORR" not in all_text and "((MMOORREE))" not in all_text
