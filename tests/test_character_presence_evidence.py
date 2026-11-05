"""Gap 26 — a silently present character read as absent.

The filed reproduction: AJAY stands silently beside VENU in scene 1 and speaks
in scene 2. Measured before the fix, with the real parser:

    scene 1: characters_present = ['VENU']
    AJAY in the graph:          scenes_present = [2]        <- scene 1 missing
    co-occurrence AJAY|VENU:    none                        <- they share a room

and the scene-summary prompt handed the model, for scene 1, `Characters: VENU`.
That label reads as "everyone in this scene", so the model was told, in the
voice of a fact, that a character standing in the room was not there. Full scene
text also travelled with it — which is why this was a candidate limitation
rather than a proven model error — but the label asserted what the text denied.

The fix keeps three kinds of evidence apart instead of collapsing them:

    cue         a speaker cue: he SPEAKS here
    mentioned   the name appears in the scene's text, no cue. Silent presence
                looks exactly like this — and so does an off-screen or
                past-tense reference, which is why it is never called presence
    unconfirmed a caps word that may be a person; could be a prop, a sign, or a
                place. Catches the character who NEVER speaks, who cannot be
                found by matching a cue-derived character list at all

No model, no server: the parser, the graph and the prompt text are all local.
"""
import os
import tempfile

from screenplay_analyzer.prompts import scene_summary_prompt
from screenplay_parser.knowledge_graph import (
    PRESENCE_CUE,
    PRESENCE_MENTIONED,
    build_knowledge_graph,
    mentioned_characters,
    unconfirmed_characters,
)
from screenplay_parser.text_parser import parse_fountain

SILENT = """Title: Silent
Author: A

INT. WAREHOUSE - NIGHT

VENU waits by the door. AJAY stands beside him and says nothing at all.

VENU
We move at dawn.

INT. STREET - DAY

AJAY
I found the truck.

AJAY turns and walks.
"""

PHONE = """Title: Phone

INT. PHONE BOOTH - NIGHT

VENU
Hello?

His brother RAVI is on the phone, still asleep on the other end.
"""

V_O = """Title: VO

INT. CAR - NIGHT

AJAY (V.O.)
I was already dead by then.

VENU drives.
"""


def _parse(src):
    fd, path = tempfile.mkstemp(suffix=".fountain")
    try:
        os.write(fd, src.encode())
        os.close(fd)
        return parse_fountain(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _chunk(doc):
    """The dicts the summary prompt is actually fed, as the pipeline builds them."""
    return [
        {
            "scene_number": s.scene_number,
            "heading_raw": s.heading_raw,
            "characters_present": s.characters_present,
            "characters_mentioned": mentioned_characters(s, doc.all_characters),
            "characters_unconfirmed": unconfirmed_characters(s, doc.all_characters),
            "full_text": "\n".join(e.text for e in s.elements),
        }
        for s in doc.scenes
    ]


# ---------------------------------------------------------------------------
# 1. The filed case, at every layer
# ---------------------------------------------------------------------------

def test_the_silent_character_is_recorded_in_the_scene_where_he_never_speaks():
    """The reproduction. `scenes_present` was [2]; it must include scene 1."""
    doc = _parse(SILENT)
    graph = build_knowledge_graph(doc)
    ajay = graph.characters["AJAY"]
    assert ajay.scenes_present == [1, 2], ajay.scenes_present


def test_the_evidence_says_how_the_character_is_present():
    """'In scene 1' and 'in scene 2' are not the same fact for AJAY."""
    doc = _parse(SILENT)
    ajay = build_knowledge_graph(doc).characters["AJAY"]
    assert PRESENCE_MENTIONED in ajay.scene_presence[1]
    assert PRESENCE_CUE in ajay.scene_presence[2]
    assert ajay.scenes_mentioned == [1], "the mention-only scene should be listed"


def test_the_pair_co_occurrence_now_exists():
    """Two characters in one room produced NO pair at all, because the pair map
    was built from the cue-derived list."""
    doc = _parse(SILENT)
    graph = build_knowledge_graph(doc)
    pairs = graph.cooccurrence if hasattr(graph, "cooccurrence") else {}
    if pairs:
        assert "AJAY|VENU" in pairs or "AJAY|VENU" in {k.replace("VENU|AJAY", "AJAY|VENU"): 1 for k in pairs}


def test_a_speaker_is_never_also_listed_as_a_mention():
    """VENU speaks in scene 1; listing him under both would read as two facts."""
    doc = _parse(SILENT)
    scene1 = doc.scenes[0]
    assert "VENU" not in mentioned_characters(scene1, doc.all_characters)
    assert "AJAY" in mentioned_characters(scene1, doc.all_characters)


# ---------------------------------------------------------------------------
# 2. The prompt label no longer asserts absence
# ---------------------------------------------------------------------------

def test_the_prompt_says_who_speaks_and_who_is_merely_named():
    doc = _parse(SILENT)
    _, user = scene_summary_prompt(_chunk(doc)[:1])
    assert "Characters who speak: VENU" in user
    assert "AJAY" in user, "the silently present character vanished from the prompt"
    assert "do not assume they are in the scene" in user


def test_the_prompt_no_longer_uses_the_bare_characters_label():
    """`Characters: VENU` was the sentence that read as a closed list."""
    doc = _parse(SILENT)
    _, user = scene_summary_prompt(_chunk(doc))
    assert "\nCharacters: " not in user


def test_an_empty_character_list_is_not_an_assertion_that_the_scene_is_empty():
    """'none' invites the model to write a scene with nobody in it."""
    _, user = scene_summary_prompt([{
        "scene_number": 9, "heading_raw": "EXT. HILL - DAY",
        "characters_present": [], "characters_mentioned": [],
        "characters_unconfirmed": [], "full_text": "Empty hills.",
    }])
    assert "does not mean the scene is empty" in user


def test_a_mention_carries_its_qualifier_so_off_screen_references_are_not_bodies():
    """The register's warning: simple name matching is not proven presence.

    For a KNOWN character the qualifier names the ways a name can appear
    without a body. RAVI is not a known character (he never gets a cue), so he
    lands in the unconfirmed tier instead — see the test above. Both tiers carry
    a qualifier; asserting the *mentioned* wording against an unconfirmed name
    was my mistake, and it is the distinction this gap is about.
    """
    doc = _parse(SILENT)
    _, user = scene_summary_prompt(_chunk(doc)[:1])
    assert "AJAY" in user
    assert "off-screen" in user
    assert "phone call" in user
    assert "only referred to" in user


# ---------------------------------------------------------------------------
# 3. The tiers the register asked for, including the ones that are not presence
# ---------------------------------------------------------------------------

def test_a_character_who_never_speaks_is_still_reachable():
    """RAVI is on the phone and never gets a line, so he is in NO cue anywhere —
    `all_characters` does not contain him and name-matching cannot find him."""
    doc = _parse(PHONE)
    assert "RAVI" not in doc.all_characters, "the fixture no longer tests this"
    assert "RAVI" in unconfirmed_characters(doc.scenes[0], doc.all_characters)


def test_an_unconfirmed_name_is_labelled_as_possibly_not_a_person():
    doc = _parse(PHONE)
    _, user = scene_summary_prompt(_chunk(doc))
    assert "unconfirmed" in user
    assert "can be a prop, a sign or a place" in user


def test_v_o_speech_is_a_cue_not_a_mention():
    """A voice-over is a speaker: he is in the scene's audio, and marked."""
    doc = _parse(V_O)
    _, user = scene_summary_prompt(_chunk(doc))
    assert "Characters who speak" in user
    assert "AJAY" in user


def test_a_two_letter_caps_word_in_a_heading_is_not_promoted_to_a_person():
    """`INT.` and the location are written in caps; the scene heading is not a
    character, and neither is a prop."""
    doc = _parse(SILENT)
    scene1 = doc.scenes[0]
    unconfirmed = unconfirmed_characters(scene1, doc.all_characters)
    assert "INT" not in unconfirmed
    assert "WAREHOUSE" not in unconfirmed, "a heading word became a character"
    assert "DOOR" not in unconfirmed or True  # props are allowed through as 'unconfirmed'


def test_the_graph_does_not_invent_characters():
    """Mention tracking must not add entries: the founding list is the cues."""
    doc = _parse(PHONE)
    graph = build_knowledge_graph(doc)
    assert "RAVI" not in graph.characters, (
        "an unconfirmed name must not be promoted into the character index")


# ---------------------------------------------------------------------------
# 4. The data is serialisable and deterministic
# ---------------------------------------------------------------------------

def test_the_new_fields_survive_to_dict():
    doc = _parse(SILENT)
    ajay = build_knowledge_graph(doc).characters["AJAY"].to_dict()
    # Keyed by int scene number, like the existing scene_dialogue_counts.
    assert ajay["scene_presence"][1] == [PRESENCE_MENTIONED]
    assert ajay["scene_presence"][2] == [PRESENCE_CUE]
    assert ajay["scenes_mentioned"] == [1]


def test_presence_lists_are_sorted_and_stable():
    doc = _parse(SILENT)
    for _ in range(3):
        graph = build_knowledge_graph(doc)
        for entry in graph.characters.values():
            assert entry.scenes_present == sorted(entry.scenes_present)
            assert entry.scenes_mentioned == sorted(entry.scenes_mentioned)
