"""Regression edges for the writer-facing turn intent heuristics (Gap 101)."""

import pytest

from screenplay_cowriter.peer import (
    classify_turn,
    has_embedded_reasoning,
    opening_contract,
    should_probe,
)


def test_temporal_since_does_not_count_as_a_reason_for_a_later_idea():
    text = (
        "Since the funeral, he walks alone. "
        "Maybe the last image is the empty house."
    )
    assert classify_turn(text) == "idea"
    assert not has_embedded_reasoning(text)
    assert should_probe(text)


def test_temporal_since_prefix_does_not_hide_a_later_actual_reason():
    text = (
        "Since the funeral, he walks alone. "
        "Maybe the last image is the empty house because guilt is all he has left."
    )
    assert has_embedded_reasoning(text)
    assert not should_probe(text)


@pytest.mark.parametrize("text", [
    "Could you tighten this?",
    "Would you try a version without the flashback?",
])
def test_polite_edit_instructions_use_the_directive_path(text):
    assert classify_turn(text) == "directive"
    assert opening_contract("directive") == ""
    assert not should_probe(text)


def test_polite_information_request_is_still_a_question():
    assert classify_turn("Could you explain why the mother leaves?") == "question"
    assert opening_contract("question").strip()


def test_exploratory_first_person_proposal_keeps_the_request_contract():
    text = "Could we lose the last beat?"
    assert classify_turn(text) == "request"
    assert "proposal" in opening_contract("request").lower()
    assert not should_probe(text)


def test_third_person_plot_question_and_plot_idea_keep_gap_98_boundary():
    assert classify_turn("Could the mother appear earlier?") == "question"
    assert classify_turn("Mara should die at the end.") == "idea"
    assert should_probe("Mara should die at the end.")
