"""The anti-AI reply filter — the deterministic pass that runs on every
co-writer reply.

It had no tests at all, which is how a fragment-mangling defect survived: the
filter deleted canned phrases *in place*, so

    "Great question! Let me think about this. Your act two sags."
      -> "about this. Your act two sags."

The rule this file pins: **removing canned phrasing must never leave a
fragment.** Openers and closers go as whole sentences; hedges are rewritten.

Two modules used to run back-to-back (`reply_transforms.strip_anti_ai_tells`
then `persona_specs.strip_banned_phrases`), with the persona-specific phrases
also re-implemented inside `persona_register`. There is now exactly one filter,
and `test_one_filter_is_the_only_filter` keeps it that way.
"""

import pytest

from screenplay_cowriter.persona_specs import (
    SHARED_CLOSERS,
    SHARED_HEDGES,
    SHARED_OPENERS,
    SHARED_SELF_REFERENCE,
    get_banned_phrases,
    strip_banned_phrases,
)
from screenplay_cowriter.reply_transforms import persona_register

PERSONAS = ("writing_partner", "script_consultant", "premise_doctor",
            "producer", "dev_exec", "teacher", "audience", "genre_specialist")


class TestNoFragments:
    """The regression that motivated the rewrite."""

    @pytest.mark.parametrize("src,expected", [
        ("Great question! Let me think about this. Your act two sags.",
         "Your act two sags."),
        ("Absolutely! Let me help. The hook is thin.",
         "The hook is thin."),
        ("I'd be happy to help. Your dialogue sings.",
         "Your dialogue sings."),
        ("That's a really interesting point. In order to fix it, cut scene 4. "
         "Let me know if you need anything else",
         "To fix it, cut scene 4."),
    ])
    def test_canned_openers_do_not_leave_a_fragment(self, src, expected):
        assert persona_register(src, "writing_partner") == expected

    def test_no_reply_starts_with_lowercase_continuation(self):
        for src in ("Great question! Let me think about this. Act two sags.",
                    "Absolutely! Let me help. The hook is thin.",
                    "I'd be happy to help. Your dialogue sings."):
            out = persona_register(src, "writing_partner")
            assert out[:1].isupper(), f"{out!r} starts lowercase — a fragment survived"

    def test_no_dangling_punctuation(self):
        for src in ("Absolutely! Let me help. The hook is thin.",
                    "Great question! Your act two sags.",
                    "That's a great question. Cut scene 4."):
            out = persona_register(src, "writing_partner")
            assert not out.startswith((",", ".", "!", "?", ";", ":")), out
            assert " ." not in out and " ," not in out and " !" not in out, out


class TestRegisterStillHolds:
    """The pre-existing contract, which must survive the rewrite."""

    def test_doctor_never_exclaims(self):
        assert persona_register("This works! Really!", "script_consultant") == "This works. Really."

    def test_sameer_keeps_one_exclamation(self):
        assert persona_register("Bold call! I like it.", "writing_partner") == "Bold call! I like it."

    def test_sameer_caps_multiple_exclamations(self):
        assert persona_register("Yes! No! Maybe!", "writing_partner") == "Yes! No. Maybe."


class TestHedgesAreRewritten:
    @pytest.mark.parametrize("src,expected", [
        ("In order to fix it, cut scene 4.", "To fix it, cut scene 4."),
        ("Due to the fact that act two drags, we cut it.", "Because act two drags, we cut it."),
        ("It's worth noting that the hook is thin.", "The hook is thin."),
        ("At the end of the day, it works.", "It works."),
    ])
    def test_hedge_becomes_a_shorter_sentence_not_an_amputation(self, src, expected):
        assert persona_register(src, "writing_partner") == expected


class TestFictionRule:
    def test_self_reference_is_dropped_for_every_persona(self):
        for persona in PERSONAS:
            out = persona_register("As an AI, I think it works.", persona)
            assert "as an AI" not in out.lower(), f"{persona} kept the fiction break"

    def test_doctor_drops_hedging_sameer_keeps_his(self):
        # Sameer's card permits "I think"; the doctor's forbids it.
        assert "I think" in persona_register("I think it works.", "writing_partner")
        assert "I think" not in persona_register("I think it works.", "script_consultant")


class TestSafety:
    def test_a_reply_of_only_pleasantries_is_not_emptied(self):
        """Emitting an empty turn is worse than emitting the original."""
        assert persona_register("Great question!", "writing_partner") == "Great question!"

    @pytest.mark.parametrize("src", [
        "Your act two sags because nothing costs anyone anything until page 60.",
        "Cut the diner scene. It repeats what scene 3 already told us.",
        "Bold call, and I mean that. The ending earns it.",
    ])
    def test_a_clean_reply_passes_through_untouched(self, src):
        assert persona_register(src, "writing_partner") == src

    def test_a_lowercase_reply_is_not_force_capitalised(self):
        """Capitalisation exists to repair a lowercase *continuation* left by a
        stripped opener. Applying it unconditionally rewrites replies the filter
        never touched — it broke the plain-fallback engine test."""
        assert persona_register("plain reply", "writing_partner") == "plain reply"
        # ...but a genuine continuation IS repaired
        assert persona_register(
            "Great question! the act sags.", "writing_partner") == "The act sags."


class TestOneFilterIsTheOnlyFilter:
    """The duplication guard. Two filters used to run back-to-back and the
    persona lists were re-implemented in `persona_register` as well."""

    def test_the_duplicate_filter_is_gone(self):
        import screenplay_cowriter.reply_transforms as rt
        assert not hasattr(rt, "strip_anti_ai_tells"), (
            "strip_anti_ai_tells is back — it duplicated SHARED_BANNED_PHRASES"
        )

    def test_persona_register_delegates_rather_than_reimplements(self):
        import inspect
        import screenplay_cowriter.reply_transforms as rt
        src = inspect.getsource(rt.persona_register)
        # Keep only the code AFTER the docstring: the docstring *names* the
        # removed blocks to explain why they are gone, which would otherwise
        # trip this very check.
        body = src.split('"""')[-1]
        # The register is the only thing it may do itself.
        assert "strip_banned_phrases" in body, "persona_register stopped applying the filter"
        assert "HEDGE_DOCTOR" not in body and "FILLER_DOCTOR" not in body, (
            "persona_register re-implements the doctor's banned phrases"
        )

    def test_the_shared_groups_are_not_also_in_the_persona_lists(self):
        """A phrase must have exactly one home, or it gets applied twice."""
        import re
        shared = " ".join(SHARED_OPENERS + SHARED_CLOSERS
                          + [p for p, _ in SHARED_HEDGES] + SHARED_SELF_REFERENCE).lower()
        for persona in ("writing_partner", "script_consultant", "premise_doctor"):
            for pat in get_banned_phrases(persona):
                for token in re.findall(r"[a-z]{4,}", pat.lower()):
                    if token in ("happy", "language", "assistant", "regard", "respect"):
                        assert token not in shared, (
                            f"{persona}: {pat!r} duplicates a shared pattern"
                        )

    def test_every_persona_list_is_non_empty_or_deliberately_absent(self):
        # The three authored personas have their own rules; the reader personas
        # rely on the shared ones alone.
        for persona in ("writing_partner", "script_consultant", "premise_doctor"):
            assert get_banned_phrases(persona), persona
        for persona in ("producer", "audience", "genre_specialist", "teacher", "dev_exec"):
            assert get_banned_phrases(persona) == [], persona
