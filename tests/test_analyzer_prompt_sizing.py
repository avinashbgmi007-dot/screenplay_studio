"""The craft-grounding cap: `SCREENPLAY_KB_BUDGET` is the operator's decision
about how dense the KB grounding is, and it is the ONLY thing that trims a
fragment here.

What these tests pin:
  * with no cap set, a pass gets EVERY rule its selection asks for — nothing
    here shortens the grounding on its own;
  * when the cap bites, it sheds WHOLE rules, highest-confidence tier first, so
    what is lost is always the least trusted principle and a kept rule is never
    a truncated one;
  * the prompt says so, with the true count, so the model cannot present a
    full-grounding read of a partial rule list;
  * and the cap is on the path `analyze()` actually takes, not only on a helper.

There is deliberately no comparison against any model's context size. The
analyzer sends what the operator asked for; the server answers for the rest.
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_analyzer import dials, genre, pipeline  # noqa: E402
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
# `run_script_level_category`, which is where the densest fragments go.
SCRIPT_LEVEL_CATEGORIES = ("theme", "character", "structure", "scene_function")

# A cap small enough to bite on every script-level pass, generous enough that a
# handful of whole rules always survive it.
CAPPED = 8000


class RecordingClient:
    """Stands in for LlamaServerClient and records what went on the wire, so a
    test can prove the fragment reached the model and was not merely available
    to the caller."""

    def __init__(self, items=None):
        self.sent = []
        self._items = items if items is not None else {"findings": []}

    def resolve_model(self, requested=None):
        return "stub-model"

    def chat_json(self, system, user, **kwargs):
        self.sent.append((system, user))
        return self._items


def _fragment(monkeypatch, category, cap=0):
    """This pass's fragment, rendered under `cap` chars (0 = uncapped).

    The string is returned already rendered, so a later patch cannot retroactively
    change a fragment a test is holding.
    """
    import screenplay_analyzer.rules_context as rc
    monkeypatch.setattr(rc, "KB_FRAGMENT_CHAR_BUDGET", cap)
    rules_ctx = RulesContext()
    return rules_ctx, rules_ctx.fragment_for_pass(category)


def _headings(fragment):
    return [line[4:] for line in fragment.splitlines() if line.startswith("### ")]


# ---------------------------------------------------------------------------
# 1. no cap, no trimming
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("category", SCRIPT_LEVEL_CATEGORIES)
def test_an_uncapped_pass_receives_every_rule_it_selected(monkeypatch, category):
    rules_ctx, fragment = _fragment(monkeypatch, category)
    assert fragment, f"{category} selected no rules at all"
    assert KB_OMISSION_MARKER not in fragment, (
        f"{category} was trimmed with no SCREENPLAY_KB_BUDGET set")
    for rule in rules_ctx.rules_for_pass(category):
        assert rule.to_prompt_fragment() in fragment, (
            f"{category} lost {rule.id} without being asked to")


# ---------------------------------------------------------------------------
# 2. a cap sheds whole rules, in confidence order, and says so
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("category", SCRIPT_LEVEL_CATEGORIES)
def test_a_cap_sheds_rules_and_states_the_omission(monkeypatch, category):
    _, full = _fragment(monkeypatch, category)
    _, capped = _fragment(monkeypatch, category, cap=CAPPED)
    if len(full) <= CAPPED:
        # The cap is a ceiling, never a floor: a pass already under it is handed
        # every rule it selected, byte for byte. `test_the_cap_bites_somewhere_
        # and_not_everywhere` keeps this arm and the one below both live.
        assert capped == full, f"{category} was rewritten while under its cap"
        return
    assert len(capped) < len(full), f"{category} ignored the cap"
    assert len(capped) <= CAPPED + 400, (
        f"the {category} fragment came to {len(capped)} chars over a "
        f"{CAPPED}-char cap")
    assert KB_OMISSION_MARKER in capped, (
        "rules were dropped silently — the model must be told the list is "
        "partial so it cannot present a full-grounding read")


def test_the_cap_bites_somewhere_and_not_everywhere(monkeypatch):
    """Both arms of the test above are live on today's KB. If the dense passes
    ever shrink under the cap (or the light ones grow past it), one arm becomes
    dead code and the parametrized test starts proving less than it claims — so
    this says so out loud."""
    sizes = {c: len(_fragment(monkeypatch, c)[1]) for c in SCRIPT_LEVEL_CATEGORIES}
    assert any(s > CAPPED for s in sizes.values()), (
        f"no script-level pass is over the {CAPPED}-char cap any more: {sizes}")
    assert any(s <= CAPPED for s in sizes.values()), (
        f"every script-level pass is now over the cap, so the under-the-cap "
        f"arm never runs: {sizes}")


def test_shedding_keeps_whole_rules_in_confidence_order(monkeypatch):
    """The trim's two promises, checked against the rules themselves rather than
    against the rendered text: a kept rule is present VERBATIM (a mid-rule cut
    would hand the model a truncated principle it could still cite as grounded),
    and the kept set is a PREFIX of confidence-tier order — so what is lost is
    always the least trusted principle, never the best one."""
    rules_ctx, capped = _fragment(monkeypatch, "character", cap=CAPPED)
    _, full = _fragment(monkeypatch, "character")
    tier_order = sorted(rules_ctx.rules_for_pass("character"),
                        key=lambda r: {"high": 0, "medium": 1, "low": 2}.get(
                            r.confidence_tier, 1))
    kept = [r for r in tier_order if r.to_prompt_fragment() in capped]
    assert 0 < len(kept) < len(tier_order), (
        f"expected a partial keep out of {len(tier_order)} rules, got {len(kept)}")
    assert [r.id for r in kept] == [r.id for r in tier_order[:len(kept)]], (
        "the kept rules are not the first N in confidence-tier order")
    for rule in kept:
        assert rule.to_prompt_fragment() in full, (
            f"{rule.id} was rewritten by the trim")


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


def test_the_omission_count_is_the_rules_actually_dropped(monkeypatch):
    """The note is the model's only view of what it is missing. A wrong count is
    a wrong statement about the evidence it was given."""
    rules_ctx, capped = _fragment(monkeypatch, "character", cap=CAPPED)
    total = len(rules_ctx.rules_for_pass("character"))
    dropped = total - len(_headings(capped))
    assert f"({dropped} further craft principles omitted" in capped, (
        f"{dropped} rules were dropped but the prompt says otherwise")


# ---------------------------------------------------------------------------
# 3. wiring: the cap must apply on the path analyze() actually takes
# ---------------------------------------------------------------------------

def test_analyze_sends_the_capped_fragment(monkeypatch):
    """A cap no production path reads is a dead setting."""
    import screenplay_analyzer.rules_context as rc
    monkeypatch.setattr(rc, "KB_FRAGMENT_CHAR_BUDGET", CAPPED)
    rules_ctx = RulesContext()
    monkeypatch.setattr(pipeline, "RulesContext", lambda: rules_ctx)
    client = RecordingClient()
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
    assert any(KB_OMISSION_MARKER in system for system, _ in client.sent), (
        "the model was never told the rule list is partial")


# ---------------------------------------------------------------------------
# 4. completion budgets are sized against MEASURED reply length
# ---------------------------------------------------------------------------
#
# A completion cap is not a style preference: when the reply reaches it the
# body is cut mid-JSON, `_extract_json` cannot parse it, the body is discarded
# and the finding is lost (chat_json retries the same doomed call). Measured on
# qwen3.6-35b-a3b / Pain_3: every discarded body was finish_reason='length' with
# completion_tokens == the sent cap. So the budget for each long-output pass is
# pinned above the cap that was OBSERVED to truncate it.
TRUNCATED_AT = {
    # pass -> (the cap that truncated, the reply length being written when cut)
    "dialogue": (1200, 5208),
    "character_reads": (1200, 4690),
    "character_dials": (1800, 6339),
    "genre": (1200, 4870),
    "character": (4000, 17437),
}

BUDGETS = {
    "dialogue": pipeline.DIALOGUE_MAX_TOKENS,
    "character_reads": pipeline.CHARACTER_READS_MAX_TOKENS,
    "character": pipeline.SCRIPT_LEVEL_MAX_TOKENS,
    "character_dials": dials.DIALS_MAX_TOKENS,
    "genre": genre.GENRE_MAX_TOKENS,
}


@pytest.mark.parametrize("name", sorted(TRUNCATED_AT))
def test_every_budget_clears_the_cap_measured_to_truncate_it(name):
    cap, reply_chars = TRUNCATED_AT[name]
    assert BUDGETS[name] > cap, (
        f"{name}: budget {BUDGETS[name]} is at or below the {cap}-token cap that "
        f"was measured to cut a {reply_chars}-char reply mid-JSON — that is a "
        f"budget that loses the finding it was paying to write")


def test_the_truncation_table_is_consistent_with_the_replies_it_records():
    """Rot guard: a recorded reply must actually be long enough to have reached
    the cap it was cut by. This model emits ~4.3 chars/token, so anything under
    3.5 chars/token would mean the pair is a typo, not evidence."""
    for name, (cap, reply_chars) in TRUNCATED_AT.items():
        assert reply_chars >= cap * 3.5, (
            f"{name}: a {reply_chars}-char reply cannot have reached a {cap}-token "
            f"cap — the recorded pair is wrong")


# The dialogue pass, measured by running it ALONE at a deliberately generous
# 8000-token budget on Pain_3: 9 of 11 chunks finished on their own at 736-2,096
# tokens, while 2 filled the entire budget with ~32,000-character replies. Two
# populations, two different problems — the healthy ceiling is 2,096, and the
# outliers are DEGENERATION (a loop fills any cap, so a bigger cap is not a fix,
# it is a longer loop).
DIALOGUE_HEALTHY_MAX_TOKENS = 2096


def test_dialogue_budget_clears_the_healthy_reply_but_stays_near_it():
    """Both directions matter, and the second is the non-obvious one.

    Too low truncates real analysis (the defect being fixed: 1200 sat BELOW the
    healthy ceiling, so genuine replies were being cut). Too high buys nothing —
    a degenerate chunk fills whatever it is given — and multiplies the cost of
    the loop instead.
    """
    assert pipeline.DIALOGUE_MAX_TOKENS > DIALOGUE_HEALTHY_MAX_TOKENS, (
        f"the dialogue cap ({pipeline.DIALOGUE_MAX_TOKENS}) is at or below the largest "
        f"HEALTHY reply measured ({DIALOGUE_HEALTHY_MAX_TOKENS} tokens) — that truncates "
        f"real analysis, which is exactly what this budget was sized to stop")
    assert pipeline.DIALOGUE_MAX_TOKENS <= 2 * DIALOGUE_HEALTHY_MAX_TOKENS, (
        f"the dialogue cap ({pipeline.DIALOGUE_MAX_TOKENS}) has been raised far past the "
        f"healthy reply size ({DIALOGUE_HEALTHY_MAX_TOKENS} tokens). Measured: 2 of 11 chunks "
        f"degenerate and fill ANY cap, so a bigger budget buys no completed analysis — only a "
        f"longer loop. Re-measure before raising this.")
