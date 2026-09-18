"""The co-writer's persona voices.

Two defects lived here, both silent because nothing asserted the pairing:

1. `POST_HISTORY_REMINDER` / `TRAIT_REMINDER` held only the two desk
   characters (`writing_partner`, `script_consultant`) and fell back to
   Sameer's entry — so the other six personas were addressed as "Sameer" in
   the highest-weight position of the prompt (after the history, closest to
   generation). The Producer was handed Sameer's voice and its own
   instructions lost the argument.
2. Nothing checked that a persona had a reminder at all, so adding a persona
   silently enrolled it in (1).

The voice check is the last thing the model reads before it writes, so
naming the wrong character there is worse than saying nothing about identity
— which is why the fallback is neutral now.
"""

from __future__ import annotations

import pytest

from screenplay_cowriter import personas as P
from screenplay_cowriter.context import ReportContext, ScriptContext
from screenplay_cowriter.engine import CoWriterEngine
from screenplay_cowriter.models import Session

# The two desk characters, and the name each one answers to. Only these may
# be named in a voice reminder.
_DESK = {"writing_partner": "Sameer", "script_consultant": "Doctor"}


def _persona_names():
    return sorted(k for k in P.PERSONAS if not k.endswith("_examples"))


class _CaptureClient:
    def __init__(self):
        self.messages = []

    def chat(self, messages, **kw):
        self.messages = [dict(m) for m in messages]
        return "A thought, plainly said."


def test_there_is_more_than_one_persona():
    """Guard the guard: every test below is vacuous if the list is empty."""
    assert len(_persona_names()) >= 8


def test_every_persona_has_its_own_voice_reminder():
    missing = [n for n in _persona_names()
               if n not in P.POST_HISTORY_REMINDER or n not in P.TRAIT_REMINDER]
    assert not missing, (
        f"personas with no voice reminder: {missing} — the fallback would "
        f"address them as somebody else"
    )


def test_no_two_personas_share_a_voice_reminder():
    """A shared reminder is exactly how the original bug looked: eight
    personas, two texts. If two genuinely should sound identical, that is a
    persona problem, not a reminder problem."""
    seen: dict = {}
    for name in _persona_names():
        text = P.post_history_reminder(name)
        assert text not in seen, f"{name} shares its reminder with {seen[text]}"
        seen[text] = name


def test_only_the_two_desk_characters_are_named():
    offenders = []
    for name in _persona_names():
        if name in _DESK:
            continue
        text = P.post_history_reminder(name)
        if any(label in text for label in _DESK.values()):
            offenders.append(name)
    assert not offenders, (
        f"personas addressed as a desk character in their own voice check: {offenders}"
    )


def test_unknown_persona_falls_back_to_a_neutral_reminder():
    text = P.post_history_reminder("no_such_persona")
    assert not any(label in text for label in _DESK.values()), (
        "an unknown persona is being addressed as a named character"
    )
    trait = P.trait_reminder("no_such_persona")
    assert not any(label in trait for label in _DESK.values())


def test_the_development_exec_is_not_the_doctor():
    """`premise_doctor` reads concepts, not pages — it is not Dr. Sushruta.
    It used to receive Sameer's reminder."""
    premise = P.post_history_reminder("premise_doctor")
    assert premise != P.post_history_reminder("script_consultant")
    assert premise != P.post_history_reminder("writing_partner")


@pytest.mark.parametrize("persona", _persona_names())
def test_engine_injects_the_matching_persona_reminder(persona):
    """End to end through the public turn path: the last message of the turn
    carries THIS persona's voice check."""
    client = _CaptureClient()
    engine = CoWriterEngine(client, ScriptContext(), ReportContext(None))
    session = Session.new("T")
    session.branches[session.current_branch].active_persona = persona
    engine.send_message(session, "what about scene 3?")
    assert client.messages, "the turn produced no prompt"
    last = client.messages[-1]
    assert last["role"] == "system"
    assert last["content"].startswith(P.post_history_reminder(persona))


@pytest.mark.parametrize("persona", _persona_names())
def test_trait_reminder_matches_the_persona(persona):
    assert P.trait_reminder(persona) == P.TRAIT_REMINDER[persona]


# ---------------- the forward nudge is a character decision ----------------

def test_every_persona_is_classified_for_the_forward_nudge():
    """`ensure_forward_momentum` used to append "Want me to run with this?" to
    every persona's short reply. It is now gated, so every persona must be on
    one side of the line — adding one without deciding fails here rather than
    silently inheriting a collaborator's move."""
    from screenplay_cowriter.peer import NUDGE_PERSONAS, NO_NUDGE_PERSONAS

    classified = set(NUDGE_PERSONAS) | set(NO_NUDGE_PERSONAS)
    assert not (set(NUDGE_PERSONAS) & set(NO_NUDGE_PERSONAS)), "a persona is on both sides"
    unclassified = sorted(set(_persona_names()) - classified)
    assert not unclassified, (
        f"personas with no forward-nudge decision: {unclassified} — add each to "
        f"NUDGE_PERSONAS (it offers to act) or NO_NUDGE_PERSONAS (it delivers a read)"
    )
    stale = sorted(classified - set(_persona_names()))
    assert not stale, f"nudge lists name personas that no longer exist: {stale}"


def test_the_doctor_is_not_a_nudger():
    """He diagnoses; Sameer fixes. The nudge offers to act."""
    from screenplay_cowriter.peer import NUDGE_PERSONAS

    assert "script_consultant" not in NUDGE_PERSONAS
    assert "writing_partner" in NUDGE_PERSONAS
