"""Gap 52 — an accepted edit left the document and its exports inconsistent.

Two filed reproductions, both measured through the real `apply_replacements`:

  * replacing heading `INT. ROOM - DAY` with `EXT. PARK - NIGHT` returned an
    applied record, but `scene.heading_raw` kept the old text and the Fountain
    export contained `INT. ROOM - DAY`. The exporters write `heading_raw`, the
    manuscript UI renders it, and continuity/scene-keys read the derived
    int_ext/location/time_of_day — all six were left describing the old slug.
  * renaming cue `MARA` to `TOM` changed the cue text but the dialogue beneath
    it kept `character: MARA`, so the knowledge graph, dials and per-character
    tracks still credited the old speaker — and the new name had no dialogue.

Plus the half the entry only gestures at ("either support structural changes
end-to-end or refuse them clearly"): an edit the parser will not read back the
same way was applied and acknowledged. Measured, a heading edited to prose made
the re-imported script lose the scene entirely (1 scene -> 0), and a lowercase
cue turned its dialogue block into action lines.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_parser import parse_fountain
from screenplay_parser.export import to_fountain
from screenplay_parser.knowledge_graph import build_knowledge_graph
from screenplay_studio.revision import apply_replacements

SRC = """Title: T

INT. ROOM - DAY

MARA
Hello there.

TOM
Fine.

EXT. STREET - NIGHT

MARA
Alone here.
"""


def _parse(text=SRC):
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False,
                                     encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        return parse_fountain(path)
    finally:
        os.unlink(path)


def _reparse(doc):
    """Fountain out, parse back in — what resume, export and reanalysis do."""
    return _parse(to_fountain(doc))


def _el(doc, scene, kind):
    return [e for e in doc.scenes[scene].elements if e.type.value == kind]


# ---------- heading edits propagate ----------

def test_heading_edit_updates_heading_raw_and_export():
    doc = _parse()
    r = apply_replacements(doc, 1, [{"old": "INT. ROOM - DAY",
                                     "new": "EXT. PARK - NIGHT"}])
    assert r["applied"], r
    assert doc.scenes[0].heading_raw == "EXT. PARK - NIGHT"
    out = to_fountain(doc)
    assert "EXT. PARK - NIGHT" in out
    assert "INT. ROOM - DAY" not in out


def test_heading_edit_updates_every_derived_field():
    """int_ext, location and time_of_day can all change in one edit — a patch
    that fixed only some of them would still leave the document lying."""
    doc = _parse()
    apply_replacements(doc, 1, [{"old": "INT. ROOM - DAY",
                                 "new": "EXT. PARK - NIGHT"}])
    sc = doc.scenes[0]
    assert (sc.int_ext, sc.location, sc.time_of_day) == ("EXT", "PARK", "NIGHT")


def test_heading_edit_survives_a_round_trip():
    doc = _parse()
    apply_replacements(doc, 1, [{"old": "INT. ROOM - DAY",
                                 "new": "EXT. PARK - NIGHT"}])
    back = _reparse(doc)
    assert len(back.scenes) == len(doc.scenes)
    assert back.scenes[0].heading_raw == "EXT. PARK - NIGHT"
    assert back.scenes[0].time_of_day == "NIGHT"


# ---------- cue renames carry to the dialogue ----------

def test_cue_rename_updates_the_dialogue_beneath_it():
    doc = _parse()
    r = apply_replacements(doc, 1, [{"old": "MARA", "new": "PRIYA"}])
    assert r["applied"], r
    dialogue = _el(doc, 0, "dialogue")
    assert [d.character for d in dialogue] == ["PRIYA", "TOM"]
    assert _el(doc, 0, "character")[0].character == "PRIYA"


def test_cue_rename_is_scoped_to_the_following_block():
    """Scene 2 has its own MARA; renaming scene 1's cue must not touch it."""
    doc = _parse()
    apply_replacements(doc, 1, [{"old": "MARA", "new": "PRIYA"}])
    assert doc.scenes[1].characters_present == ["MARA"]
    assert "MARA" in doc.all_characters, "a speaker in scene 2 must survive"


def test_cue_rename_updates_the_derived_character_lists():
    doc = _parse()
    apply_replacements(doc, 1, [{"old": "MARA", "new": "PRIYA"}])
    assert doc.scenes[0].characters_present == ["PRIYA", "TOM"]
    assert sorted(doc.all_characters) == ["MARA", "PRIYA", "TOM"]


def test_cue_rename_reaches_the_knowledge_graph():
    """The graph is what every downstream character read is built from."""
    doc = _parse()
    apply_replacements(doc, 1, [{"old": "MARA", "new": "PRIYA"}])
    names = set(build_knowledge_graph(doc).characters)
    assert "PRIYA" in names
    assert "MARA" in names, "scene 2's MARA is still a character"


def test_a_vocal_extension_survives_the_rename():
    """(V.O.) lives in the cue text; `character` holds the bare name."""
    text = SRC.replace("MARA\nHello there.", "MARA (V.O.)\nHello there.")
    doc = _parse(text)
    r = apply_replacements(doc, 1, [{"old": "MARA (V.O.)", "new": "PRIYA (V.O.)"}])
    assert r["applied"], r
    cue = _el(doc, 0, "character")[0]
    assert cue.text == "PRIYA (V.O.)"
    assert cue.character == "PRIYA", "the bare name, not the whole cue"
    assert _el(doc, 0, "dialogue")[0].character == "PRIYA"


def test_cue_rename_does_not_rewrite_prose():
    """A name in action text is prose. Rewriting it would be the editor
    guessing at intent — the failure this whole gap is about."""
    text = """Title: T

INT. ROOM - DAY

MARA sits alone.

MARA
Hello.
"""
    doc = _parse(text)
    apply_replacements(doc, 1, [{"old": "MARA", "new": "PRIYA"}])
    assert _el(doc, 0, "action")[0].text == "MARA sits alone."


# ---------- structural edits are refused, not silently restructured ----------

def test_a_heading_edited_to_prose_is_refused():
    """Measured before the fix: applied, and the re-parsed script had 0 scenes."""
    doc = _parse()
    r = apply_replacements(doc, 1, [{"old": "INT. ROOM - DAY", "new": "Hello there."}])
    assert not r["applied"], "a heading that stops being a heading must be refused"
    assert r["skipped"] and "refused" in r["skipped"][0]["reason"]
    assert doc.scenes[0].heading_raw == "INT. ROOM - DAY"
    assert len(_reparse(doc).scenes) == len(doc.scenes)


def test_a_lowercase_cue_is_refused():
    """Measured before the fix: applied, and the dialogue block became action."""
    doc = _parse()
    r = apply_replacements(doc, 1, [{"old": "MARA", "new": "priya"}])
    assert not r["applied"]
    assert "refused" in r["skipped"][0]["reason"]
    back = _reparse(doc)
    assert any(e.type.value == "dialogue" for e in back.scenes[0].elements)


def test_the_refusal_says_what_breaks():
    """'Refused' alone leaves the writer guessing what to type instead."""
    doc = _parse()
    r = apply_replacements(doc, 1, [{"old": "MARA", "new": "priya"}])
    reason = r["skipped"][0]["reason"]
    assert "uppercase" in reason.lower()
    assert "dialogue" in reason.lower()


def test_a_valid_heading_edit_is_not_refused():
    """The guard must not block ordinary scene changes."""
    doc = _parse()
    for new in ("INT. KITCHEN - NIGHT", "EXT. PARK - CONTINUOUS",
                "INT/EXT. CAR - DAY"):
        d = _parse()
        r = apply_replacements(d, 1, [{"old": "INT. ROOM - DAY", "new": new}])
        assert r["applied"], (new, r)


def test_a_valid_cue_rename_is_not_refused():
    doc = _parse()
    for new in ("PRIYA", "DETECTIVE RAO", "MARA (CONT'D)"):
        d = _parse()
        r = apply_replacements(d, 1, [{"old": "MARA", "new": new}])
        assert r["applied"], (new, r)


def test_prose_that_looks_like_a_heading_is_still_editable():
    """The guard keys on the element's type, not on the text, so an action line
    mentioning INT. can be edited freely."""
    doc = _parse()
    r = apply_replacements(doc, 1, [{"old": "Hello there.", "new": "INT. whatever"}])
    assert r["applied"], r


# ---------- nothing moves when nothing is applied ----------

def test_a_refused_edit_changes_nothing():
    doc = _parse()
    before = [(e.type.value, e.text, e.character) for e in doc.scenes[0].elements]
    apply_replacements(doc, 1, [{"old": "INT. ROOM - DAY", "new": "nope"}])
    after = [(e.type.value, e.text, e.character) for e in doc.scenes[0].elements]
    assert before == after


def test_a_mixed_batch_applies_the_safe_edit_and_refuses_the_rest():
    doc = _parse()
    r = apply_replacements(doc, 1, [
        {"old": "Hello there.", "new": "Hello, finally."},
        {"old": "INT. ROOM - DAY", "new": "prose"},
    ])
    assert [a["new"] for a in r["applied"]] == ["Hello, finally."]
    assert len(r["skipped"]) == 1
    assert doc.scenes[0].heading_raw == "INT. ROOM - DAY"
