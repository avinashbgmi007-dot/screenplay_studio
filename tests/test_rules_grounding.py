"""Regression guards for knowledge-base grounding.

These exist because of a real, silent bug: ``CATEGORY_TO_TAXONOMY_LEVELS``
keyed the plot-thread level as ``"plot"`` while the pipeline asked for
``"plot_thread"``. ``.get("plot_thread", [])`` returned ``[]``, so the
Principles Engine (Chekhov's Gun) and the setup/payoff ledger ran with **zero**
named craft principles — no error, no warning, just an empty prompt fragment.

The lesson: empty grounding is invisible unless something asserts it is not
empty. That is all these tests do. They need no model server.
"""

from __future__ import annotations

import pathlib
import re
import warnings

import pytest

from screenplay_analyzer.rules_context import (
    CATEGORY_TO_TAXONOMY_LEVELS,
    PASS_EXTRAS,
    RulesContext,
)

ANALYZER_DIR = pathlib.Path(__file__).resolve().parent.parent / "screenplay_analyzer"


@pytest.fixture(scope="module")
def rc():
    return RulesContext()


# --------------------------------------------------------------------------
# The specific regression
# --------------------------------------------------------------------------

def test_plot_thread_grounding_is_not_empty(rc):
    """39 KB rules exist for plot_thread; the fragment must carry them."""
    assert rc.prompt_fragment_for_category("plot_thread").strip(), (
        "plot_thread grounding is EMPTY — the Principles Engine and the "
        "setup/payoff ledger would run ungrounded"
    )
    assert rc.fragment_for_pass("plot_thread").strip()


# --------------------------------------------------------------------------
# The general contract (any of these failing is the same silent-empty class)
# --------------------------------------------------------------------------

def test_every_mapped_category_yields_a_fragment(rc):
    empty = [c for c in CATEGORY_TO_TAXONOMY_LEVELS
             if not rc.prompt_fragment_for_category(c).strip()]
    assert not empty, f"mapped categories rendering an empty fragment: {empty}"


def test_every_mapped_taxonomy_level_exists_in_kb(rc):
    """A typo in a level name fails the same silent way as a typo in a key."""
    bad = {}
    for category, levels in CATEGORY_TO_TAXONOMY_LEVELS.items():
        missing = [lv for lv in levels if not rc.kb.for_taxonomy_level(lv)]
        if missing:
            bad[category] = missing
    assert not bad, f"mapping points at taxonomy levels with no rules: {bad}"


def test_literal_pass_names_used_by_the_analyzer_are_grounded(rc):
    """Scan the analyzer source for the grounding calls it makes *by literal*
    and assert each one actually produces a fragment.

    This is the test that would have caught the ``plot`` / ``plot_thread``
    mismatch — it fails the moment a pass asks for grounding it cannot get.
    It deliberately accepts either route (category mapping or PASS_EXTRAS),
    because `logline_test` is grounded by the latter alone.
    """
    scans = (
        ("fragment_for_pass", r'fragment_for_pass\(\s*"([^"]+)"', rc.fragment_for_pass),
        ("prompt_fragment_for_category",
         r'prompt_fragment_for_category\(\s*"([^"]+)"', rc.prompt_fragment_for_category),
    )
    calls: list[tuple[str, str, object]] = []
    for kind, pattern, fn in scans:
        for path in sorted(ANALYZER_DIR.glob("*.py")):
            for name in re.findall(pattern, path.read_text(encoding="utf-8")):
                calls.append((kind, name, fn))
    assert calls, "source scan found no literal grounding calls — the scan is broken"

    empty = sorted({f"{kind}({name!r})" for kind, name, fn in calls
                    if not fn(name).strip()})
    assert not empty, (
        "the analyzer asks for rule grounding it never receives (empty fragment) "
        f"— this is the silent-empty class of bug: {empty}"
    )


def test_script_level_category_loop_names_are_mapped():
    """The script-level loop passes a variable, so the literal scan above can't
    see its names — pin them explicitly."""
    expected = {"theme", "character", "structure", "scene_function"}
    assert expected <= set(CATEGORY_TO_TAXONOMY_LEVELS)


def test_pass_extras_files_all_exist(rc):
    missing = {p: [f for f in files if not rc.kb.for_file(f)]
               for p, files in PASS_EXTRAS.items()}
    missing = {p: f for p, f in missing.items() if f}
    assert not missing, f"PASS_EXTRAS names files with no rules: {missing}"


# --------------------------------------------------------------------------
# Fragment hygiene
# --------------------------------------------------------------------------

def test_no_rule_is_rendered_twice_in_a_pass(rc):
    offenders = {}
    for name in set(CATEGORY_TO_TAXONOMY_LEVELS) | set(PASS_EXTRAS):
        ids = [r.id for r in rc.rules_for_pass(name)]
        if len(ids) != len(set(ids)):
            offenders[name] = len(ids) - len(set(ids))
    assert not offenders, f"passes rendering duplicate rules: {offenders}"


def test_character_extras_are_fully_covered_by_the_taxonomy_levels(rc):
    """psychology.json / body_language.json were 54/54 duplicates. The de-dupe
    must not *lose* a rule — assert every extra id is already present."""
    base = {r.id for r in rc.rules_for_category("character")}
    for fname in PASS_EXTRAS["character"]:
        for r in rc.kb.for_file(fname):
            assert r.id in base, (
                f"{r.id} from {fname} is NOT covered by the character taxonomy "
                f"levels — the de-dupe would drop it"
            )


# --------------------------------------------------------------------------
# Budget
# --------------------------------------------------------------------------

def test_hard_budget_caps_and_states_the_omission(monkeypatch):
    import screenplay_analyzer.rules_context as mod
    monkeypatch.setattr(mod, "KB_FRAGMENT_CHAR_BUDGET", 5000)
    frag = RulesContext().fragment_for_pass("character")
    assert len(frag) <= 6000, f"budget not enforced ({len(frag)} chars)"
    assert "omitted to fit the prompt budget" in frag, (
        "an omission must be stated in the prompt, never silent"
    )


def test_soft_warning_fires_for_an_oversized_fragment(monkeypatch):
    import screenplay_analyzer.rules_context as mod
    monkeypatch.setattr(mod, "KB_FRAGMENT_CHAR_BUDGET", 0)
    monkeypatch.setattr(mod, "KB_FRAGMENT_SOFT_WARN", 1000)
    monkeypatch.setattr(mod, "_WARNED_FRAGMENTS", set())
    with pytest.warns(RuntimeWarning):
        RulesContext().fragment_for_pass("character")


def test_soft_warning_fires_only_once_per_label(monkeypatch):
    """The notice is a signal, not spam — one oversized pass must not print a
    hundred times in a test summary."""
    import screenplay_analyzer.rules_context as mod
    monkeypatch.setattr(mod, "KB_FRAGMENT_CHAR_BUDGET", 0)
    monkeypatch.setattr(mod, "KB_FRAGMENT_SOFT_WARN", 1000)
    monkeypatch.setattr(mod, "_WARNED_FRAGMENTS", set())
    rc = RulesContext()
    with pytest.warns(RuntimeWarning):
        rc.fragment_for_pass("character")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        rc.fragment_for_pass("character")
    assert not caught, "the soft-ceiling notice repeated for the same label"


def test_budget_of_zero_means_unlimited(monkeypatch):
    import screenplay_analyzer.rules_context as mod
    monkeypatch.setattr(mod, "KB_FRAGMENT_CHAR_BUDGET", 0)
    monkeypatch.setattr(mod, "KB_FRAGMENT_SOFT_WARN", 0)
    frag = RulesContext().fragment_for_pass("character")
    assert "omitted" not in frag, "budget 0 must not truncate"


# --------------------------------------------------------------------------
# The no-KB fallback must stay shape-compatible (genre wiring depends on it)
# --------------------------------------------------------------------------

def test_null_rules_context_has_the_same_surface():
    from screenplay_analyzer.pipeline import _NullRulesContext
    null = _NullRulesContext()
    for name in ("prompt_fragment_for_category", "prompt_fragment_for_rule",
                 "fragment_for_pass", "prompt_fragment_for_genre"):
        assert hasattr(null, name), f"_NullRulesContext lacks {name}()"
        assert getattr(null, name)("anything") == ""


# --------------------------------------------------------------------------
# The wiring: a pass must actually RECEIVE its fragment, not merely be able to
# build one. Both paths below were dead — genre.py's guard never fired because
# no caller passed rules_ctx, and the logline test's PASS_EXTRAS entry was
# unreachable because run_logline_test accepted no fragment.
# --------------------------------------------------------------------------

class _RecordingClient:
    """Captures the prompts a pass sends; returns an empty finding set."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def chat_json(self, system, user, grammar=None, max_tokens=None, fast=False):
        self.calls.append((system, user))
        return {"findings": []}


def test_genre_pass_receives_its_rule_fragment(rc):
    from screenplay_analyzer.genre import run_genre_check
    client = _RecordingClient()
    run_genre_check({"genre": "romance"}, "overview", client, rules_ctx=rc)
    assert client.calls, "the genre check made no model call"
    assert "Genre-Specific Craft Principles" in client.calls[0][1], (
        "the genre pass ran without its knowledge-base rules"
    )


def test_logline_pass_receives_its_rule_fragment(rc):
    from screenplay_analyzer.pipeline import run_logline_test
    fragment = rc.fragment_for_pass("logline_test")
    assert fragment.strip(), "logline_test grounding is empty"
    client = _RecordingClient()
    run_logline_test("A thief must rob one last vault.", "overview", "T", client,
                     rules_fragment=fragment)
    assert client.calls, "the logline test made no model call"
    assert fragment.strip()[:30] in client.calls[0][1], (
        "the logline test ran without its pitch rules"
    )


def test_logline_test_still_accepts_the_old_positional_call():
    """`language` stays ahead of `rules_fragment` so existing callers survive."""
    from screenplay_analyzer.pipeline import run_logline_test
    client = _RecordingClient()
    run_logline_test("x", "y", "z", client, "eng")   # must not raise
    assert client.calls
