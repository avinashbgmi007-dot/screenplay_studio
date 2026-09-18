"""Regression tests for the humanized persona voices (Sameer, Dr. Sushruta,
premise doctor) and the shared human-voice rules distilled from the
character-AI ecosystem playbook (RealChar / Soul-of-Waifu / humanizer)."""

from screenplay_cowriter.context import ScriptContext, ReportContext, build_system_prompt
from screenplay_cowriter.personas import PERSONAS, HUMAN_VOICE_RULES

ALL_PERSONAS = tuple(sorted(k for k in PERSONAS if not k.endswith("_examples")))


def _prompt(persona: str, mode: str = "peer", premise=None):
    return build_system_prompt(
        ScriptContext({"title": "T"}), ReportContext(None), persona, mode, premise=premise
    )


class TestSharedVoiceRules:
    def test_voice_rules_ride_every_persona(self):
        """EVERY persona, not a hand-picked subset.

        This test used to iterate a hardcoded tuple of exactly the three
        personas that already carried the rules — so it could never fail, and
        five personas (producer, dev_exec, teacher, audience, genre_specialist)
        shipped with no voice rules at all. Derive the list from PERSONAS so a
        newly added persona is covered automatically.
        """
        assert len(ALL_PERSONAS) >= 8, "persona list collapsed — the scan is broken"
        for persona in ALL_PERSONAS:
            p = _prompt(persona)
            assert "How a real person talks" in p, persona
            assert "Great question!" in p, persona  # the anti-pattern is named, so it can be avoided
            assert "Never say \"as an AI\"" in p, persona

    def test_voice_rules_appear_exactly_once(self):
        """Appending must not double the block for personas that embed it."""
        for persona in ALL_PERSONAS:
            p = _prompt(persona)
            assert p.count("How a real person talks") == 1, persona

    def test_no_persona_breaks_the_fiction(self):
        # The humanization playbook's hard rule: nobody at the desk admits to
        # being a model. Scan all persona + example texts, not just prompts.
        # (The prohibition itself is quoted/lowercase inside HUMAN_VOICE_RULES,
        # so only sentence-position usage counts as a real fiction break.)
        for key, text in PERSONAS.items():
            assert "As an AI" not in text, key
            assert "I'm an AI" not in text, key
            assert "I am an AI" not in text, key
            assert "As a language model" not in text, key
            assert "I'm a language model" not in text, key


class TestSameerVoice:
    def test_sam_keeps_his_examples_and_guards(self):
        p = _prompt("writing_partner")
        assert "How Sameer talks" in p
        assert "Bold call" in p
        assert "want my honest take" in p
        assert "Never invent the pages" in p

    def test_sam_humor_dimension(self):
        p = _prompt("writing_partner")
        assert "sarcasm is allowed" in p or "Sarcasm is allowed" in p
        assert "never at the writer" in p


class TestDoctorVoice:
    def test_script_consultant_has_voice_and_wit(self):
        p = _prompt("script_consultant", "evidence_discussion")
        assert "dry wit" in p
        assert "argue with the script, never with the writer" in p
        assert "How Dr. Sushruta talks" in p  # example dialogue embedded
        # still does not leak Sameer's examples
        assert "How Sameer talks" not in p

    def test_premise_doctor_has_voice_and_examples(self):
        p = _prompt("premise_doctor", "concept_validation", premise={"title": "Idea"})
        assert "affectionate wit" in p
        assert "How the doctor talks" in p
        assert "raised eyebrow" in p

    def test_doctor_personas_stay_in_role(self):
        # Humanized, not generic: the consultant still points at the report and
        # the premise doctor still refuses to pretend pages exist.
        p = _prompt("premise_doctor", "concept_validation", premise={"title": "Idea"})
        assert "never pretend pages exist" in p


class TestRuleBlock:
    def test_voice_rules_block_shape(self):
        assert "non-negotiable" in HUMAN_VOICE_RULES
        assert "canned openings" in HUMAN_VOICE_RULES
        assert "signposting" in HUMAN_VOICE_RULES
        assert "Match the writer" in HUMAN_VOICE_RULES
        assert "sparingly" in HUMAN_VOICE_RULES
