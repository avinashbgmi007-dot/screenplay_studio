"""Gaps 44 and 77 — a correctly formatted cut reported as a dropped transition.

Both gaps are one defect seen from two sides, and this file closes both.

Measured before the fix:

    INT. KITCHEN - DAY  ->  EXT. STREET - NIGHT
    finding: "Unmarked time flip: Scene 1 ends in DAY and Scene 2 opens in NIGHT
              with no transition marker (LATER / THE NEXT DAY / etc.)."
    evidence_quote: "EXT. STREET - NIGHT"

Gap 77's sharpest detail: the finding's own evidence quote is the second scene's
heading — the text that states the new time. A finding quoting its own
refutation.

The premise was wrong. In a screenplay the scene heading is *where time is
stated*. `INT. KITCHEN - DAY` followed by `EXT. STREET - NIGHT` is the ordinary,
correctly formatted way to move time; demanding a redundant LATER on top of it
reports the writer's correct formatting as a defect. The register called this a
"normal act/scene cut" and was right.

What survives is the one thing a heading cannot express: two scenes in the SAME
place at opposite times with nothing between them to account for the gap. That
is a question, and it is reported as one.
"""
from screenplay_analyzer.continuity import run_continuity_analysis
from screenplay_parser.models import Element, ElementType, Scene, ScriptDocument


def _doc(*scenes):
    d = ScriptDocument(title="T", author=None, source_format="fountain",
                       source_filename="t.fountain")
    d.scenes = list(scenes)
    return d


def _scene(num, heading, int_ext, location, tod, actions=()):
    sc = Scene(scene_number=num, heading_raw=heading, int_ext=int_ext,
               location=location, time_of_day=tod)
    sc.elements.append(Element(type=ElementType.SCENE_HEADING, text=heading))
    for a in actions:
        sc.elements.append(Element(type=ElementType.ACTION, text=a))
    sc.elements.append(Element(type=ElementType.CHARACTER, text="MIRA"))
    sc.elements.append(Element(type=ElementType.DIALOGUE, text="Okay."))
    return sc


def _flips(doc):
    findings, _ = run_continuity_analysis(doc)
    return [f for f in findings
            if "time flip" in f["issue"].lower() or "time jump" in f["issue"].lower()]


# ---------------------------------------------------------------------------
# 1. The two filed cases produce nothing at all
# ---------------------------------------------------------------------------

def test_gap_44_ordinary_day_to_night_cut_is_not_a_defect():
    doc = _doc(_scene(1, "INT. KITCHEN - DAY", "INT", "KITCHEN", "DAY", ["She cooks."]),
               _scene(2, "EXT. STREET - NIGHT", "EXT", "STREET", "NIGHT", ["Rain."]))
    assert _flips(doc) == [], "an ordinary DAY->NIGHT cut was reported as a defect"


def test_gap_77_day_to_night_under_an_action_heading_is_not_a_defect():
    doc = _doc(_scene(1, "INT. KITCHEN - DAY", "INT", "KITCHEN", "DAY", ["She cooks."]),
               _scene(2, "INT. GARAGE - NIGHT", "INT", "GARAGE", "NIGHT", ["He waits."]))
    assert _flips(doc) == []


def test_the_words_unmarked_time_flip_are_gone():
    """The phrase asserted a dropped transition. It must not survive anywhere in
    the output for a normal script."""
    doc = _doc(_scene(1, "INT. A - DAY", "INT", "A", "DAY"),
               _scene(2, "EXT. B - NIGHT", "EXT", "B", "NIGHT"))
    findings, _ = run_continuity_analysis(doc)
    for f in findings:
        assert "unmarked time flip" not in f["issue"].lower()


def test_a_heading_is_never_quoted_as_evidence_that_a_transition_is_missing():
    """Gap 77's core complaint. For an ordinary cut there is no finding to quote
    anything; for the surviving case the quote is BOTH headings, never one."""
    ordinary = _doc(_scene(1, "INT. A - DAY", "INT", "A", "DAY"),
                    _scene(2, "EXT. B - NIGHT", "EXT", "B", "NIGHT"))
    assert _flips(ordinary) == []

    same_place = _doc(_scene(1, "INT. A - DAY", "INT", "A", "DAY"),
                      _scene(2, "INT. A - NIGHT", "INT", "A", "NIGHT"))
    flip = _flips(same_place)[0]
    # The pair must be visible to the writer — but in the ISSUE, not the quote.
    # An evidence quote has to be a verbatim line or quote-verification fails it.
    assert "INT. A - DAY" in flip["issue"]
    assert "INT. A - NIGHT" in flip["issue"]
    assert flip["evidence_quote"] == "INT. A - NIGHT", (
        "the quote must be a verbatim heading, not a composite of two")
    assert flip["paired_heading"] == "INT. A - DAY"


def test_the_evidence_quote_is_a_verbatim_script_line():
    """This module promises every evidence quote survives quote-verification.
    Writing a composite `prev -> cur` broke that promise and broke a downstream
    revision test, which is how I found it."""
    doc = _doc(_scene(1, "INT. A - DAY", "INT", "A", "DAY"),
               _scene(2, "INT. A - NIGHT", "INT", "A", "NIGHT"))
    flip = _flips(doc)[0]
    lines = {e.text for sc in doc.scenes for e in sc.elements}
    assert flip["evidence_quote"] in lines, (
        "the evidence quote does not exist anywhere in the script")


# ---------------------------------------------------------------------------
# 2. The one case a heading cannot express
# ---------------------------------------------------------------------------

def test_same_place_opposite_time_is_raised_as_a_question():
    doc = _doc(_scene(1, "INT. KITCHEN - DAY", "INT", "KITCHEN", "DAY", ["Breakfast."]),
               _scene(2, "INT. KITCHEN - NIGHT", "INT", "KITCHEN", "NIGHT", ["Dark."]))
    flips = _flips(doc)
    assert len(flips) == 1
    issue = flips[0]["issue"]
    assert issue.startswith("Possible"), "it must not be stated as a fact"
    assert "same place" in issue.lower()


def test_the_surviving_finding_is_marked_an_observation():
    doc = _doc(_scene(1, "INT. KITCHEN - DAY", "INT", "KITCHEN", "DAY"),
               _scene(2, "INT. KITCHEN - NIGHT", "INT", "KITCHEN", "NIGHT"))
    flip = _flips(doc)[0]
    assert flip["is_observation"] is True
    assert flip["confidence"] == "observation"
    assert "nothing to fix" in flip["why_it_matters"].lower(), (
        "the writer must be told an ellipsis may be exactly what they intend")


def test_a_stated_marker_silences_even_the_same_place_case():
    doc = _doc(_scene(1, "INT. KITCHEN - DAY", "INT", "KITCHEN", "DAY"),
               _scene(2, "INT. KITCHEN - NIGHT", "INT", "KITCHEN", "NIGHT",
                      ["LATER. The same room, dark."]))
    assert _flips(doc) == []


# ---------------------------------------------------------------------------
# 3. The cases the register asked for
# ---------------------------------------------------------------------------

def test_morning_to_evening_is_normal_pacing():
    doc = _doc(_scene(1, "INT. A - MORNING", "INT", "A", "MORNING"),
               _scene(2, "INT. B - EVENING", "INT", "B", "EVENING"))
    assert _flips(doc) == []


def test_continuous_is_not_a_flip():
    doc = _doc(_scene(1, "INT. A - DAY", "INT", "A", "DAY"),
               _scene(2, "INT. A - CONTINUOUS", "INT", "A", "CONTINUOUS"))
    assert _flips(doc) == []


def test_a_flashback_does_not_become_a_continuity_defect():
    """The register's flashback case: a deliberate chronology move."""
    doc = _doc(_scene(1, "INT. A - DAY", "INT", "A", "DAY"),
               _scene(2, "INT. A - NIGHT", "INT", "A", "NIGHT",
                      ["FLASHBACK. Twelve years ago, this same room."]))
    assert _flips(doc) == [], "a flashback was read as a dropped transition"


def test_a_concrete_year_marker_silences_it():
    doc = _doc(_scene(1, "INT. A - DAY", "INT", "A", "DAY"),
               _scene(2, "INT. A - NIGHT", "INT", "A", "NIGHT", ["1998. The same room."]))
    assert _flips(doc) == []


def test_three_scenes_of_ordinary_cuts_produce_nothing():
    """The parsed Pain 3 script fired this on 5->6, 13->14 and 17->18, each a
    normal act/scene cut."""
    doc = _doc(*[_scene(i, f"{'INT' if i % 2 else 'EXT'}. PLACE {i} - "
                          f"{'DAY' if i % 2 else 'NIGHT'}",
                       "INT" if i % 2 else "EXT", f"PLACE {i}",
                       "DAY" if i % 2 else "NIGHT")
                  for i in range(1, 8)])
    assert _flips(doc) == []


def test_an_unparsed_time_on_either_side_is_left_alone():
    """No time parsed is not evidence of a jump."""
    a = _scene(1, "INT. A - DAY", "INT", "A", "DAY")
    b = _scene(2, "INT. B", "INT", "B", None)
    assert _flips(_doc(a, b)) == []
