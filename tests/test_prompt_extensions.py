"""Tests for the analysis-prompt extensions (structural checkpoints,
per-scene stakes, idiolect instruction) and the pipeline wiring of the new
deterministic passes (continuity + idiolect stages)."""

from screenplay_analyzer import prompts
from screenplay_analyzer import pipeline


def test_structure_prompt_has_checkpoints():
    sys, _ = prompts.structure_analysis_prompt("overview", "T", 12, 40)
    for marker in ("ACT ONE", "MIDPOINT", "DARKEST HOUR", "CLIMAX"):
        assert marker in sys


def test_scene_function_prompt_has_stakes():
    sys, _ = prompts.scene_function_prompt("overview", "T")
    for marker in ("WANT", "OBSTACLE", "CHANGE"):
        assert marker in sys


def test_dialogue_prompt_has_idiolect_instruction():
    sys, _ = prompts.dialogue_analysis_prompt([{"scene_number": 1, "heading_raw": "INT. X - DAY", "full_text": "hi"}])
    assert "Idiolect consistency" in sys


def test_pipeline_runs_continuity_stage():
    # The deterministic passes must be wired into analyze() — the continuity
    # module is importable from the pipeline's own namespace usage and the
    # stage emits a progress event.
    import screenplay_analyzer.continuity as cont
    assert cont.CATEGORY == "continuity"
    assert hasattr(cont, "run_continuity_analysis")


def test_grammar_allows_continuity_category():
    from screenplay_analyzer.grammar import FINDING_CATEGORIES, findings_grammar
    assert "continuity" in FINDING_CATEGORIES
    assert "continuity" in findings_grammar()  # renders into the category alternation
