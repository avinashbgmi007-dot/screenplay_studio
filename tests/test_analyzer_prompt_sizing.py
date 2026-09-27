"""R6-BE-1: the analyzer must size a craft-rule fragment against the model it is
actually talking to.

The finding was measured, not guessed. The `character` pass renders 65,226 chars
of craft rules from the 83 rules its pass selects; against a live
`qwen3.6-35b-a3b-pruned-v2` that is 15,510 prompt tokens (`POST /tokenize`, so
this is the real count and not the repo's chars/3 estimate) and the pass then asks
for a 4,000-token completion — a 19,510-token requirement. That fits the 50,176
this author's server reports and does NOT fit a 4k or 8k window, which is the
normal setting on an 8 GB card.

When it does not fit, llama.cpp answers HTTP 400. `chat_json` retries that three
times and raises; `pipeline.analyze()` records the category `failed`; and
`orchestrator.py:148` still stamps the stage `complete`, because the other passes
did produce findings. The writer loses the entire character analysis and the
manifest says the run succeeded.

What these tests pin:
  * a small window sheds WHOLE rules, highest-confidence tier first, and says so
    inside the prompt, so the model never cites a rule list it was not shown;
  * a window with room sheds NOTHING — how dense the craft grounding is stays the
    operator's call, which `SCREENPLAY_KB_BUDGET` has always been the only way to
    make, and the model's window may tighten that choice but never loosen it;
  * a window too small to carry the pass at all reports the window and the knob
    instead of overflowing quietly;
  * and every script-level prompt fits the model it is addressed to, which is the
    gate this round was missing. `TOKEN_BUDGET` could not be that gate: it is the
    chunker's ceiling on SCENE TEXT (see `pipeline.py:240` and
    `_chunk_by_budget`'s docstring), and no script-level pass has ever been under
    it — asserting it could only be satisfied by deleting the knowledge base.
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_analyzer import pipeline, prompts  # noqa: E402
from screenplay_analyzer.pipeline import (  # noqa: E402
    CHARS_PER_TOKEN, CONTEXT_SLACK_TOKENS, SCRIPT_LEVEL_MAX_TOKENS,
    TOKEN_BUDGET, fit_rules_fragment_to_model)
from screenplay_analyzer.rules_context import (  # noqa: E402
    KB_OMISSION_MARKER, RulesContext)
from screenplay_parser import parse_fountain  # noqa: E402

SAMPLE = """INT. WORKSHOP - NIGHT

MARA (30) stands at the bench, a broken loom in her hands.

MARA
Fix it or bury it. Those are the two.

RAVI
Then we bury it.

INT. WORKSHOP - LATER

MARA welds the frame shut. Sparks. She does not look up.
"""

# The four categories `pipeline.analyze()` runs through
# `run_script_level_category`, which is where the unsized 65k fragment goes.
SCRIPT_LEVEL_CATEGORIES = ("theme", "character", "structure", "scene_function")

OVERVIEW = "INT. WORKSHOP - NIGHT\nMARA welds the frame shut. Sparks."


class WindowClient:
    """Stands in for LlamaServerClient for a server that reports a window.

    `context_window()` is the only new surface the analyzer may use; `chat_json`
    records what was sent so a test can prove the sized fragment is on the wire
    and not merely available to the caller.
    """

    def __init__(self, n_ctx=None, items=None):
        self._n_ctx = n_ctx
        self.sent = []
        self._items = items if items is not None else {"findings": []}

    def context_window(self):
        return self._n_ctx

    def resolve_model(self, requested=None):
        return "stub-model"

    def chat_json(self, system, user, **kwargs):
        self.sent.append((system, user))
        return self._items


def _assemble(category, fragment):
    """Build the real prompt a script-level pass would send."""
    if category == "character":
        return prompts.character_analysis_prompt(OVERVIEW, "Loom", ["Mara", "Ravi"],
                                                 rules_fragment=fragment, language="eng")
    if category == "theme":
        return prompts.theme_analysis_prompt(OVERVIEW, "Loom",
                                             rules_fragment=fragment, language="eng")
    if category == "structure":
        return prompts.structure_analysis_prompt(OVERVIEW, "Loom", 2, 4.0,
                                                 rules_fragment=fragment, language="eng")
    if category == "scene_function":
        return prompts.scene_function_prompt(OVERVIEW, "Loom",
                                             rules_fragment=fragment, language="eng")
    raise AssertionError(f"unwired category {category!r}")


def _fit(client, category, fragment, rules_ctx):
    return fit_rules_fragment_to_model(
        client, fragment=fragment, max_tokens=SCRIPT_LEVEL_MAX_TOKENS,
        assemble=lambda f: _assemble(category, f),
        shrink=lambda chars: rules_ctx.fragment_for_pass(category, char_budget=chars))


def _prompt_tokens(parts):
    """The repo's own estimator, applied to the whole assembled prompt."""
    return sum(len(p) for p in parts) // CHARS_PER_TOKEN


def _headings(fragment):
    return [line[4:] for line in fragment.splitlines() if line.startswith("### ")]


# ---------------------------------------------------------------------------
# 1. the defect is real: unsized, this pass cannot fit a small model
# ---------------------------------------------------------------------------

def test_the_unsized_character_fragment_overflows_a_small_window():
    """Anchors the measurement this file exists for. If the KB ever shrinks on
    its own this fails — and the sizing here needs revisiting, which is the
    correct direction for it to fail in."""
    fragment = RulesContext().fragment_for_pass("character")
    assert len(fragment) > 60_000, (
        f"the character pass rendered {len(fragment)} chars of craft rules; "
        f"R6-BE-1 measured 65,226")
    assert _prompt_tokens([fragment]) + SCRIPT_LEVEL_MAX_TOKENS > 8192, (
        "the pass now fits an 8k window unaided — R6-BE-1 may be obsolete")


def test_token_budget_could_not_be_the_gate():
    """Why the gate below sizes to the model rather than to TOKEN_BUDGET: the
    script-level passes exceed TOKEN_BUDGET with their craft grounding by
    design, so that assertion could only be bought by deleting the KB."""
    for category in SCRIPT_LEVEL_CATEGORIES:
        fragment = RulesContext().fragment_for_pass(category)
        assert _prompt_tokens([fragment]) > TOKEN_BUDGET, (
            f"{category}'s fragment now fits inside TOKEN_BUDGET — re-check "
            f"whether TOKEN_BUDGET is the right ceiling to gate on")


# ---------------------------------------------------------------------------
# 2. a small window sheds whole rules, in confidence order, and says so
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("category", SCRIPT_LEVEL_CATEGORIES)
def test_a_small_window_sheds_rules_and_states_the_omission(category):
    rules_ctx = RulesContext()
    full = rules_ctx.fragment_for_pass(category)
    fitted, unreachable = _fit(WindowClient(8192), category, full, rules_ctx)
    assert len(fitted) <= len(full), "sizing made the prompt bigger than the KB"
    if unreachable is not None:
        # A category whose irreducible prompt cannot fit 8k must shed to the
        # floor AND report it; it may not pass silently.
        assert KB_OMISSION_MARKER in fitted or fitted == full
        return
    assert _prompt_tokens(_assemble(category, fitted)) + SCRIPT_LEVEL_MAX_TOKENS <= 8192
    if fitted != full:
        assert KB_OMISSION_MARKER in fitted, (
            "rules were dropped silently — the model must be told the list is "
            "partial so it cannot present a full-grounding read")


def test_shedding_keeps_whole_rules_in_confidence_order():
    """The trim's two promises, checked against the rules themselves rather than
    against the rendered text: a kept rule is present VERBATIM (a mid-rule cut
    would hand the model a truncated principle it could still cite as grounded),
    and the kept set is a PREFIX of confidence-tier order — so what a small
    context loses is always the least trusted principle, never the best one."""
    rules_ctx = RulesContext()
    full = rules_ctx.fragment_for_pass("character")
    fitted, _ = _fit(WindowClient(8192), "character", full, rules_ctx)
    tier_order = sorted(rules_ctx.rules_for_pass("character"),
                        key=lambda r: {"high": 0, "medium": 1, "low": 2}.get(
                            r.confidence_tier, 1))
    kept = [r for r in tier_order if r.to_prompt_fragment() in fitted]
    assert 0 < len(kept) < len(tier_order), (
        f"expected a partial keep out of {len(tier_order)} rules, got {len(kept)}")
    assert [r.id for r in kept] == [r.id for r in tier_order[:len(kept)]], (
        "the kept rules are not the first N in confidence-tier order")
    for r in kept:
        assert r.to_prompt_fragment() in full, (
            f"{r.id} was rewritten by the trim")


def test_a_tier_order_tie_keeps_file_order():
    """`sorted` is stable, and that is load-bearing here: rules of the same tier
    must still arrive in the KB's own curated order, or a trim would reshuffle
    the grounding pass to pass to pass."""
    rules_ctx = RulesContext()
    ordered = rules_ctx.rules_for_pass("character")
    high = [r.id for r in ordered if r.confidence_tier == "high"]
    tier_sorted = sorted(ordered, key=lambda r: {"high": 0, "medium": 1, "low": 2}.get(
        r.confidence_tier, 1))
    assert [r.id for r in tier_sorted if r.confidence_tier == "high"] == high, (
        "tier sorting reordered within the high tier")


def test_the_omission_count_is_the_rules_actually_dropped():
    """The note is the model's only view of what it is missing. A wrong count is
    a wrong statement about the evidence it was given."""
    rules_ctx = RulesContext()
    full = rules_ctx.fragment_for_pass("character")
    fitted, _ = _fit(WindowClient(8192), "character", full, rules_ctx)
    total = len(rules_ctx.rules_for_pass("character"))
    dropped = total - len(_headings(fitted))
    assert f"({dropped} further craft principles omitted" in fitted, (
        f"{dropped} rules were dropped but the prompt says otherwise")


# ---------------------------------------------------------------------------
# 3. a window with room must shed NOTHING
# ---------------------------------------------------------------------------

def test_a_window_with_room_keeps_every_rule():
    """50,176 is the window the author's server reports. Auto-shedding here would
    silently lower grounding density, which is the decision the 2026-09-24 round
    deliberately left to the operator."""
    rules_ctx = RulesContext()
    full = rules_ctx.fragment_for_pass("character")
    fitted, unreachable = _fit(WindowClient(50176), "character", full, rules_ctx)
    assert fitted == full, "the model had room and rules were still dropped"
    assert unreachable is None
    assert KB_OMISSION_MARKER not in fitted


def test_an_unreported_window_changes_nothing():
    """/props is a llama.cpp endpoint some builds do not expose, and the whole
    browser fleet's mock server has no /props at all. A failed probe must fall
    back to today's behaviour — a guessed cap would be worse than none."""
    rules_ctx = RulesContext()
    full = rules_ctx.fragment_for_pass("character")
    fitted, unreachable = _fit(WindowClient(None), "character", full, rules_ctx)
    assert fitted == full
    assert unreachable is None


def test_an_explicit_env_budget_still_wins(monkeypatch):
    """SCREENPLAY_KB_BUDGET is the operator choosing craft density. A generous
    model must never hand back what the operator capped away."""
    import screenplay_analyzer.rules_context as rc
    monkeypatch.setattr(rc, "KB_FRAGMENT_CHAR_BUDGET", 8000)
    rules_ctx = RulesContext()
    full = rules_ctx.fragment_for_pass("character", char_budget=10 ** 9)
    assert KB_OMISSION_MARKER in full, "the env cap stopped biting"
    assert len(full) <= 8000 + 400, (
        f"an env cap of 8,000 chars produced {len(full)}")


def test_a_smaller_env_budget_is_not_loosened_by_a_big_window(monkeypatch):
    """The cap is min(env, model), in that direction only."""
    import screenplay_analyzer.rules_context as rc
    monkeypatch.setattr(rc, "KB_FRAGMENT_CHAR_BUDGET", 8000)
    rules_ctx = RulesContext()
    capped = rules_ctx.fragment_for_pass("character")
    fitted, _ = _fit(WindowClient(131072), "character", capped, rules_ctx)
    assert len(fitted) <= len(capped), (
        "the model's window overrode an explicit SCREENPLAY_KB_BUDGET")


# ---------------------------------------------------------------------------
# 4. an unreachable floor must be reported, not overflowed
# ---------------------------------------------------------------------------

def test_a_window_too_small_for_the_pass_reports_itself():
    """Shed to the floor and it is still ~2.4k prompt tokens plus a 4k
    completion, over 4096. The honest answer names the window and the knob."""
    rules_ctx = RulesContext()
    full = rules_ctx.fragment_for_pass("character")
    fitted, unreachable = _fit(WindowClient(4096), "character", full, rules_ctx)
    assert unreachable is not None, (
        "this pass still overflows a 4096 window and nothing was reported")
    assert "4096" in unreachable, f"the message must name the window: {unreachable!r}"
    assert "--ctx-size" in unreachable, (
        f"the message must name the thing to raise: {unreachable!r}")
    assert len(fitted) < len(full), "it should still have shed what it could"


@pytest.mark.parametrize("n_ctx", (8192, 16384, 32768, 50176, 131072))
def test_a_reachable_floor_reports_nothing_and_fits(n_ctx):
    rules_ctx = RulesContext()
    full = rules_ctx.fragment_for_pass("character")
    fitted, unreachable = _fit(WindowClient(n_ctx), "character", full, rules_ctx)
    assert unreachable is None, f"{n_ctx} can hold this pass: {unreachable}"
    budget = (n_ctx - SCRIPT_LEVEL_MAX_TOKENS - CONTEXT_SLACK_TOKENS) * CHARS_PER_TOKEN
    assert len(fitted) <= budget + 400, (
        f"{n_ctx}: {len(fitted)} chars of rules into a window that cannot hold "
        f"prompt+completion")


# ---------------------------------------------------------------------------
# 5. the gate: no script-level prompt may overflow its model
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n_ctx", (8192, 16384, 50176))
@pytest.mark.parametrize("category", SCRIPT_LEVEL_CATEGORIES)
def test_every_script_level_prompt_fits_the_model_it_is_addressed(category, n_ctx):
    """The permanent fence. For each category at each window, exactly one of two
    outcomes is allowed: the prompt the pipeline sends fits, or the pass reports
    the floor unreachable. A silent overflow is not available."""
    rules_ctx = RulesContext()
    fragment = rules_ctx.fragment_for_pass(category)
    fitted, unreachable = _fit(WindowClient(n_ctx), category, fragment, rules_ctx)
    if unreachable is not None:
        assert len(fitted) <= len(fragment)
        return
    required = _prompt_tokens(_assemble(category, fitted)) + SCRIPT_LEVEL_MAX_TOKENS
    assert required <= n_ctx, (
        f"{category} would send {required} tokens to a {n_ctx} window; llama.cpp "
        f"answers 400, the retries burn, and the category is recorded failed")


# ---------------------------------------------------------------------------
# 6. wiring: the sizing must be on the path analyze() actually takes
# ---------------------------------------------------------------------------

def test_analyze_sizes_the_prompt_it_sends_not_only_the_one_tests_call(monkeypatch):
    """A helper no production path calls is dead code. This drives analyze()
    against an 8k client and inspects what reached the model."""
    rules_ctx = RulesContext()
    monkeypatch.setattr(pipeline, "RulesContext", lambda: rules_ctx)
    client = WindowClient(8192)
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False,
                                     encoding="utf-8") as f:
        f.write(SAMPLE)
        path = f.name
    try:
        doc = parse_fountain(path)
    finally:
        os.unlink(path)
    pipeline.analyze(doc, client, run_categories=("character",), progress_cb=None)
    assert client.sent, "analyze() made no model call, so this proved nothing"
    overflowing = [(i, _prompt_tokens(parts) + SCRIPT_LEVEL_MAX_TOKENS)
                   for i, parts in enumerate(client.sent)
                   if _prompt_tokens(parts) + SCRIPT_LEVEL_MAX_TOKENS > 8192]
    assert not overflowing, (
        f"calls {overflowing} overflowed the 8192 window the server reported")
    assert any(KB_OMISSION_MARKER in system for system, _ in client.sent), (
        "the model was never told the rule list is partial")
