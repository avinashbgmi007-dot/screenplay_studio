"""
Gap 11, first half: a filter that drops a note for mentioning subtitles is
distorting feedback, not cleaning it.

Filed: "Synthetic craft note mentioning subtitles was filtered." A writer who
writes a scene in Hindi will get notes about that scene. Some of those notes are
about *language as a subject* — "needs subtitles", "this is probably Telugu" —
and are noise. Others are *craft notes that happen to mention a subtitle card*,
and dropping one of those silently deletes a real note about a real scene. The
distinction is whether language is what the note is ABOUT or a detail inside a
note about staging, character or POV.

The rule used to ask only "does a subtitle pattern appear anywhere in the
claim", which answers the wrong question.
"""

from screenplay_analyzer.feedback_filter import is_non_writing_feedback


def _note(issue, why, observation=""):
    return {"category": "dialogue", "issue": issue, "why_it_matters": why,
            "observation": observation, "severity": "medium", "scene_refs": [1],
            "evidence_quote": None}


# A craft note whose whole subject is Dev's POV. The subtitle card is a detail
# inside it. Dropping this loses the note.
_CRAFT_WITH_SUBTITLE_DETAIL = _note(
    "The Hindi exchange between Ma and Rahul carries the scene's whole argument, "
    "but the scene never lets Dev react to it.",
    "Dev is your POV character and he is the one who cannot follow the words - a "
    "subtitle card would explain the line to the audience and explain nothing to "
    "him.",
    "Dev watches the two of them, says nothing, exits.")


class TestACraftNoteIsNotLanguageNoise:

    def test_a_craft_note_that_mentions_a_subtitle_card_is_kept(self):
        assert is_non_writing_feedback(_CRAFT_WITH_SUBTITLE_DETAIL) is False, (
            "a note about POV was dropped for containing the word 'subtitle'")

    def test_the_dropped_ones_are_still_dropped(self):
        # Every one of these is ABOUT the language. None should survive.
        assert is_non_writing_feedback(_note(
            "Needs subtitles for audiences that don't speak the language.",
            "Non-native speakers will miss the tone of the exchange.")) is True
        assert is_non_writing_feedback(_note(
            "The dialect reads as regional - probably Telugu or a South Indian "
            "language.",
            "It establishes character voice.")) is True
        assert is_non_writing_feedback(_note(
            "The code-switching between English and Telugu is frequent.",
            "x")) is True

    def test_the_observation_side_still_needs_its_incomprehension_claim(self):
        # A note that merely OBSERVES a subtitle would be dropped on the claim
        # side alone; here the claim is craft, so the observation alone must not
        # tip it - that gate is what stops the filter eating every note about a
        # non-English scene.
        f = _note("The argument stalls halfway through the exchange.",
                  "The scene repeats a beat it already landed.")
        f["observation"] = "The two argue in Hindi; a subtitle appears."
        assert is_non_writing_feedback(f) is False
