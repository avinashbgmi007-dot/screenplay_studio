"""Gap 45 — the pacing pass reported creative verdicts from word counts.

Every test here fails on the pre-fix module and passes after it. The claims the
filed gap made, and how each would have been measured, are in the docstrings.

The pre-fix loop was:

    if el.type == ElementType.DIALOGUE:
        dialogue += words
    else:
        action += words          # <- cues, headings, transitions, parentheticals

so a dialogue-only scene was reported as having "action words", and
`pace_score` min-max normalised density and inverted action share across the
script, so the slowest scene was always ~100 and the fastest always 0.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_parser import parse_fountain
from screenplay_analyzer.pacing import (
    per_scene_pace, drag_findings, is_measurable, DRAG_THRESHOLD,
)


def _parse(text):
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False,
                                     encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        return parse_fountain(path)
    finally:
        os.unlink(path)


def _talk_scene(heading, lines=4, words=16):
    out = [heading, ""]
    for i in range(lines):
        out.append("DEV" if i % 2 else "MIRA")
        out.append(" ".join(["walk"] * words))
        out.append("")
    return "\n".join(out)


def _action_scene(heading, words=40):
    return f"{heading}\n\n" + " ".join(["run"] * words) + "\n"


# ---------- character cues are not action ----------

def test_a_scene_with_no_action_line_reports_no_action_words():
    """The filed claim, in its smallest form.

    Pre-fix this scene reports action_words=8 (four cues plus the slug line) on
    a scene that contains no action line at all.
    """
    doc = _parse(_talk_scene("INT. ROOM - NIGHT"))
    rows = per_scene_pace(doc)
    assert len(rows) == 1
    r = rows[0]
    assert r["action_words"] == 0
    assert r["action_share"] == 0.0
    # the words are still counted towards the scene's size
    assert r["words"] > 0
    assert r["dialogue_words"] > 0


def test_a_scene_that_is_only_action_reports_full_share():
    doc = _parse(_action_scene("INT. STREET - DAY"))
    r = per_scene_pace(doc)[0]
    assert r["action_words"] > 0
    assert r["dialogue_words"] == 0
    assert r["action_share"] == 1.0


def test_cues_do_not_change_the_action_share():
    """Adding dialogue beats adds sizes but must not add movement.

    A scene with 4 beats and a scene with 8 beats, both all-dialogue, are the
    same kind of scene; the share must not drift toward "action" just because
    there are more names on the page.
    """
    small = per_scene_pace(_parse(_talk_scene("INT. ROOM - NIGHT", lines=4)))[0]
    large = per_scene_pace(_parse(_talk_scene("INT. ROOM - NIGHT", lines=8)))[0]
    assert small["action_share"] == large["action_share"] == 0.0
    assert large["words"] > small["words"]


# ---------- identical scenes get identical numbers ----------

def test_identical_scenes_get_identical_scores():
    """The reproduction that started the gap.

    Three long all-dialogue scenes plus two short action scenes gave
    pace_score [100.0, 100.0, 100.0, 0.0, 0.0] — all three longs tied at
    exactly 100, which reads as "maximally draggy" but is just a rank edge.
    A tie is still a tie, but nothing may present it as an amount.
    """
    text = "Title: T\n\n" + "\n".join(
        _talk_scene(f"INT. ROOM {n} - NIGHT") for n in (1, 2, 3)
    ) + "\n" + "\n".join(_action_scene(f"EXT. STREET {n} - DAY") for n in (1, 2))
    rows = per_scene_pace(_parse(text))
    talk = [r for r in rows if r["dialogue_words"] and not r["action_words"]]
    assert len(talk) == 3
    assert len({r["pace_score"] for r in talk}) == 1, "identical scenes must score identically"
    # and the rank is exposed as a rank, with ties sharing a position
    assert all(r["pace_rank"] is not None for r in talk)
    assert len({r["pace_rank"] for r in talk}) == 1


def test_a_uniformly_slow_script_scores_slow_everywhere():
    """The rank had no absolute zero: a script of three identical long talky
    scenes scored 0.0 on all three, i.e. "fastest possible". Absolute terms
    make it score the same high number everywhere, which is the truth."""
    same = "Title: T\n\n" + "\n".join(
        _talk_scene(f"INT. ROOM {n} - NIGHT", lines=6, words=40) for n in (1, 2, 3)
    )
    rows = per_scene_pace(_parse(same))
    assert len({r["pace_score"] for r in rows}) == 1
    assert rows[0]["pace_score"] > 50, "a uniformly long talky script is not fast"
    assert all(r["pace_rank"] == 1 for r in rows), "ties share a rank"


def test_score_is_absolute_not_normalised_against_the_script():
    """The same scene must score the same in a fast script and a slow one."""
    alone = per_scene_pace(_parse("Title: T\n\n" + _talk_scene("INT. ROOM - NIGHT",
                                                                lines=6, words=40)))
    crowded = per_scene_pace(_parse(
        "Title: T\n\n" + _talk_scene("INT. ROOM - NIGHT", lines=6, words=40)
        + "\n" + _action_scene("EXT. STREET - DAY", words=200)
    ))
    assert alone[0]["pace_score"] == crowded[0]["pace_score"]


def test_a_long_action_paragraph_does_not_outrank_a_talky_scene():
    """The second defect: the old composite contradicted itself.

    Density was words per ELEMENT, so a 44-word action paragraph (one element,
    density 22) outranked a 106-word dialogue scene (thirteen elements, density
    8.2) on the 0.6 weight — while action_share ranked it the opposite way on
    0.4. The weights decided the verdict, and the all-action scene came out
    "draggier" than the talking heads. Pre-fix scores: action 60.0, dialogue
    40.0.
    """
    text = ("Title: T\n\nEXT. STREET - DAY\n\n" + " ".join(["run"] * 40)
            + "\n\nINT. ROOM - NIGHT\n\n"
            + "\n".join("MIRA\n" + " ".join(["walk"] * 16) + "\n" for _ in range(6)))
    rows = per_scene_pace(_parse(text))
    action, talk = rows[0], rows[1]
    assert talk["action_share"] == 0.0 and action["action_share"] == 1.0
    assert talk["pace_score"] > action["pace_score"], (
        f"a {talk['words']}-word all-dialogue scene scored {talk['pace_score']} but a "
        f"{action['words']}-word action paragraph scored {action['pace_score']}"
    )
    assert talk["pace_rank"] == 1 and action["pace_rank"] == 2


def test_one_scene_is_scored_but_never_flagged():
    """Absolute terms need no comparison to compute a score, so a lone scene
    can be scored — but the pass has no reason to file a note about it, and
    "the slowest scene" of one is not a finding."""
    rows = per_scene_pace(_parse(_talk_scene("INT. ROOM - NIGHT")))
    assert rows[0]["pace_score"] is not None
    assert rows[0]["pace_rank"] == 1
    assert drag_findings(rows) == [] or all(
        not f["scene_refs"] for f in drag_findings(rows)
    )


# ---------- a dialogue-driven climax is not a defect ----------

def test_a_dialogue_driven_climax_is_not_flagged_as_drag():
    """Long speeches, zero action, and it is the best scene in the script.

    Pre-fix this scored 0.0 and filed nothing only by luck of normalisation;
    the module's own wording would have called it "meanders where the story
    needs to move" had it ranked high. Nothing may call it a defect.
    """
    text = "Title: T\n\n" + _talk_scene("INT. ROOM - NIGHT", lines=6, words=40) + "\n" + _action_scene("EXT. STREET - DAY", words=200)
    doc = _parse(text)
    rows = per_scene_pace(doc)
    climax = rows[0]
    assert climax["action_share"] == 0.0
    for f in drag_findings(rows):
        if climax["scene_number"] in f.get("scene_refs", []):
            assert f["is_observation"] is True
            assert f["confidence"] == "observation"
            assert "meander" not in f["why_it_matters"].lower()
            assert "needs to move" not in f["why_it_matters"].lower()
            assert "real event" not in f["why_it_matters"].lower()


def test_drag_findings_state_a_measurement_not_a_diagnosis():
    """No finding may assert what a word count cannot establish."""
    text = "Title: T\n\n" + _talk_scene("INT. ROOM - NIGHT", lines=6, words=40) + "\n" + _action_scene("EXT. STREET - DAY", words=20)
    findings = drag_findings(per_scene_pace(_parse(text)))
    assert findings, "fixture must reproduce at least one slow scene"
    banned = ("meander", "needs to move", "real event", "runs long with little",
              "keeps its momentum", "talking heads")
    for f in findings:
        blob = (f["issue"] + " " + f["why_it_matters"]).lower()
        for word in banned:
            assert word not in blob, f"creative verdict in a count-based finding: {word!r}"
        # severity is not "medium": nothing here has established seriousness
        assert f["severity"] == "low"
        assert f["check_id"] == "pacing_drag"


def test_silence_is_not_a_pace_drag():
    """A scene of pure whitespace has no words and must not be scored."""
    text = "Title: T\n\nINT. ROOM - NIGHT\n\n   \n\nINT. HALL - DAY\n\nMIRA\nHello there.\n"
    rows = per_scene_pace(_parse(text))
    for r in rows:
        if r["words"] == 0:
            assert r["action_share"] is None
            assert r["drag"] is False


# ---------- action without movement ----------

def test_action_without_movement_is_still_only_action_share():
    """Forty words of running is not proof the story moves, and the finding
    must not say it is. It scores high action share — nothing more."""
    text = "Title: T\n\n" + _action_scene("EXT. STREET - DAY", words=200) + "\n" + _talk_scene("INT. ROOM - NIGHT", lines=6, words=40)
    rows = per_scene_pace(_parse(text))
    action = rows[0]
    assert action["action_share"] == 1.0
    findings = drag_findings(rows)
    # the pure-action scene is the least slow thing here; if it were flagged,
    # the finding still may not claim the action scenes "move the story"
    for f in findings:
        assert "story" not in f["why_it_matters"].lower()


# ---------- non-Latin text is not measurable ----------

def test_telugu_script_is_declared_unmeasurable():
    """Parses fine; the word-share arithmetic does not apply.

    The pass must say so rather than dividing one meaningless count by another.
    """
    text = ("Title: Tel\n\nINT. ROOM - NIGHT\n\nMIRA\n"
            + " ".join(["ఇల్లు"] * 20) + "\n")
    assert is_measurable(_parse(text)) is False


def test_latin_script_is_measurable():
    assert is_measurable(_parse(_talk_scene("INT. ROOM - NIGHT"))) is True
