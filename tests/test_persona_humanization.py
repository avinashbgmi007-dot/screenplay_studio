"""Regression tests for the humanized persona voices (Sam, script consultant,
premise doctor) and the shared human-voice rules distilled from the
character-AI ecosystem playbook (RealChar / Soul-of-Waifu / humanizer)."""

from screenplay_cowriter.context import ScriptContext, ReportContext, build_system_prompt
from screenplay_cowriter.personas import PERSONAS, HUMAN_VOICE_RULES

HUMAN_PERSONAS = ("writing_partner", "script_consultant", "premise_doctor")


def _prompt(persona: str, mode: str = "peer", premise=None):
    return build_system_prompt(
        ScriptContext({"title": "T"}), ReportContext(None), persona, mode, premise=premise
    )


class TestSharedVoiceRules:
    def test_voice_rules_ride_every_human_persona(self):
        for persona in HUMAN_PERSONAS:
            p = _prompt(persona)
            assert "How a real person talks" in p, persona
            assert "Great question!" in p, persona  # the anti-pattern is named, so it can be avoided
            assert "Never say \"as an AI\"" in p, persona

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


class TestSamVoice:
    def test_sam_keeps_his_examples_and_guards(self):
        p = _prompt("writing_partner")
        assert "How Sam talks" in p
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
        assert "How this consultant talks" in p  # example dialogue embedded
        # still does not leak Sam's examples
        assert "How Sam talks" not in p

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
