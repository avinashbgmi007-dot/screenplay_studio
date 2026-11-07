"""Gap 98 — a writer who said what they want must not be interrogated.

Filed defect: `classify_turn` keyed on the first token and a trailing "?" only,
so two opposite failures came out of one rule:

* a stated INTENTION was classified `idea` and therefore **probed** —
  "Let the silence sit.", "I want the audience to feel compulsion.",
  "I cut the line.", "The ending should feel earned.";
* a modal first-person PROPOSAL was classified `question` —
  "Can we talk about the mother?", "Could I lose the last beat?".

The brief this project is graded against rules out both: Sameer must not
interrogate a writer who has already said what they want, or who has asked
something. Probing a stated decision reads as not having listened; answering a
proposal as a fact question reads as not having understood it.

The fix is classification, not another exception list. `should_probe` stays one
line — `idea` and no embedded reasoning — because `intent` and `request` are no
longer `idea`. Each new kind carries a BEHAVIOUR (an opening contract the engine
injects, and no forward nudge for a request), because a kind nothing reads is a
comment.

Two boundaries here are deliberate and worth stating, because the obvious wider
rule is wrong:

* "Mara should die at the end" stays a probeable **idea**. A plot decision is
  exactly what a co-writer should help think through. Only effect statements
  ("the ending should feel earned") are intentions.
* "Can the mother appear earlier?" stays a **question**. That is the writer
  asking for a judgment, not proposing a change to their own draft — the
  first-person modal is what separates the two.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from screenplay_cowriter.peer import (                    # noqa: E402
    PROBE_SYSTEM_PROMPT,
    classify_turn,
    ensure_forward_momentum,
    has_embedded_reasoning,
    opening_contract,
    should_probe,
)


# ---------- the filed table, in the writer's own phrasing ----------

@pytest.mark.parametrize("text", [
    "Let the silence sit.",
    "I want the audience to feel compulsion.",
    "I cut the line.",
    "The ending should feel earned.",
    "Keep the last beat.",
    "I'd like the audience to be uncomfortable.",
    "Allow the pause to breathe.",
    "I've decided the mother never appears.",
])
def test_a_stated_intention_is_not_a_bare_idea(text):
    assert classify_turn(text) == "intent"
    assert not should_probe(text), "a writer who said what they want must not be asked why"


@pytest.mark.parametrize("text", [
    "Can we talk about the mother?",
    "Could I lose the last beat?",
    "Would we lose too much if the father never spoke?",
    "Should we open on the empty room?",
])
def test_a_modal_first_person_proposal_is_a_request(text):
    assert classify_turn(text) == "request"
    assert not should_probe(text)


# ---------- the boundaries: the wider rule would be wrong ----------

@pytest.mark.parametrize("text", [
    "Mara should die at the end",
    "I think Mara should die at the end",
])
def test_a_plot_decision_stays_a_probeable_idea(text):
    """Effect-vs-event. How the work should FEEL is an intention; what should
    HAPPEN is an idea to develop. Two pre-existing tests pin this."""
    assert classify_turn(text) == "idea"
    assert should_probe(text)


@pytest.mark.parametrize("text", [
    "Can the mother appear earlier?",
    "Should the mother appear earlier?",
    "should Mara die?",
    "why does scene 14 feel flat",
    "Why does she leave?",
])
def test_a_third_person_or_fact_question_stays_a_question(text):
    """Without first person it is the writer asking for a judgment, which the
    answer-first contract already handles correctly."""
    assert classify_turn(text) == "question"
    assert not should_probe(text)


def test_lets_is_still_a_directive_not_an_intention():
    """"Let's cut the scene" is an instruction to US; "Let the silence sit" is a
    decision about the WORK. One apostrophe is the whole difference."""
    assert classify_turn("Let's cut the scene.") == "directive"
    assert classify_turn("Let us cut the scene.") == "directive"
    assert classify_turn("Let the silence sit.") == "intent"


def test_an_undeveloped_thought_is_still_probed():
    """The probe is not retired — it is narrowed. A real idea still gets asked
    about, because that is the co-writing move the probe exists for."""
    assert classify_turn("What if the mother is already dead?") in ("question", "idea")
    assert should_probe("The mother is already dead")
    assert should_probe("Maybe the last scene is a memory")
    assert not should_probe("The mother is already dead because the guilt is the point")


def test_embedded_reasoning_still_suppresses_the_probe():
    """The pre-existing carve-out is unchanged."""
    assert has_embedded_reasoning("I cut the line because it repeated itself")
    assert not should_probe("I cut the line because it repeated itself")


# ---------- every kind has a behaviour, or it is a comment ----------

@pytest.mark.parametrize("kind", ["question", "request", "intent"])
def test_each_new_kind_tells_the_model_what_to_do_first(kind):
    contract = opening_contract(kind)
    assert contract.strip(), f"{kind} has no opening contract — the label does nothing"
    assert "writer" in contract.lower()


def test_intent_forbids_the_interrogation_explicitly():
    contract = opening_contract("intent").lower()
    assert "already said" in contract
    assert "do not ask what is driving it" in contract


def test_request_is_not_treated_as_a_fact_question():
    contract = opening_contract("request").lower()
    assert "not treat it as a fact question" in contract


def test_idea_and_directive_add_no_contract():
    """An idea must be met with the probe, and a directive with doing it — a
    'lead with this' instruction on either would fight the existing behaviour."""
    assert opening_contract("idea") == ""
    assert opening_contract("directive") == ""


def test_the_engine_uses_the_shared_contract_not_an_inline_copy():
    with open(os.path.join(ROOT, "screenplay_cowriter", "engine.py"), encoding="utf-8") as f:
        engine = f.read()
    assert "opening_contract(turn_kind)" in engine
    assert "ANSWER FIRST: the writer asked a direct question" not in engine, (
        "the contract is duplicated inline again — one statement, in peer.py")


def test_a_request_gets_no_forward_nudge():
    """They asked us something; tacking "want me to run with this?" onto the
    answer reads as evasive. Same rule as a question."""
    reply = "Yes — losing the last beat costs you the reveal, but it buys a colder ending."
    padded = ensure_forward_momentum(reply, "request", "writing_partner")
    assert padded == reply
    # and the question rule it mirrors still holds
    assert ensure_forward_momentum(reply, "question", "writing_partner") == reply


def test_an_intent_reply_may_still_close_forward():
    """An intention is not a question — offering to act on it is the right move,
    so `intent` must NOT be swept into the no-nudge rule with `request`."""
    short = "Good — that changes the whole ending."
    padded = ensure_forward_momentum(short, "intent", "writing_partner")
    assert padded != short, "an intention should still be able to move forward"


# ---------- the probe prompt still asks, and only for ideas ----------

def test_the_probe_prompt_still_exists_and_asks_one_question():
    assert "ONE job" in PROBE_SYSTEM_PROMPT
    assert "One question" in PROBE_SYSTEM_PROMPT


def test_classification_is_total_and_idempotent():
    """Every input gets a kind, and asking twice gives the same answer — the
    engine calls `classify_turn` and `should_probe` separately on one turn."""
    for text in ("", "   ", "Silence.", "?", "Let", "Can we", "I want"):
        kind = classify_turn(text)
        assert kind in ("idea", "question", "directive", "intent", "request")
        assert classify_turn(text) == kind
