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


# --------------------------------------------------------------------------
# Curated severity
# --------------------------------------------------------------------------

def test_every_rule_has_a_curated_severity():
    from knowledge_base import KnowledgeBase
    missing = [r.id for r in KnowledgeBase().all()
               if not (r.severity_default or "").strip()]
    assert not missing, f"rules with no severity_default: {missing}"


def test_rule_fragment_states_its_curated_severity():
    """`severity_default` was populated on all 263 rules and read by nothing,
    so the same defect could be graded differently depending on which pass
    found it. It now rides the prompt, guiding the model's choice."""
    from knowledge_base import KnowledgeBase
    for rule in KnowledgeBase().all():
        fragment = rule.to_prompt_fragment()
        assert "Severity if confirmed:" in fragment, f"{rule.id} omits its severity"
        assert rule.severity_default in fragment, (
            f"{rule.id} fragment does not carry '{rule.severity_default}'"
        )


# --------------------------------------------------------------------------
# Genre scoping — a second silent-empty bug, and the leak it hid behind
#
# The knowledge base tags 90 rules with a genre. Two things were wrong:
#   (a) `for_genre` matched the tag with `==` on a free-text field. The
#       coverage grammar does not constrain `genre`, so a model answering
#       "Romantic Comedy" or "Sci-Fi Thriller" got [] — genre grounding was
#       silently off for every real-world label.
#   (b) those 90 rules also sat inside the generic taxonomy levels, so every
#       *other* pass received all eight genres at once: a romance was handed
#       horror's and thriller's principles.
# --------------------------------------------------------------------------

# labels a model plausibly returns, none of which is a bare KB tag
_FREE_TEXT_GENRES = [
    "romance", "Romantic Comedy", "rom-com", "romantic",
    "sci-fi", "Science Fiction", "Sci-Fi Thriller", "scifi",
    "thriller", "psychological thriller", "suspense",
    "mystery", "whodunit", "crime", "detective",
    "horror", "supernatural", "drama", "comedy", "action",
]


def test_for_genre_resolves_free_text_labels(rc):
    unresolved = [g for g in _FREE_TEXT_GENRES if not rc.kb.for_genre(g)]
    assert not unresolved, (
        "these real-world genre labels resolve to NO rules — genre-scoped "
        f"grounding is silently off for them: {unresolved}"
    )


def test_for_genre_still_returns_nothing_for_an_unknown_genre(rc):
    """Tolerance must not become 'match anything'."""
    assert rc.kb.for_genre("interpretive dance documentary") == []
    assert rc.kb.for_genre("") == []
    assert rc.kb.for_genre(None) == []


def test_genre_scoped_fragment_is_never_empty_for_a_tagged_genre(rc):
    from knowledge_base import KnowledgeBase
    genres = {(r.genre or "").strip() for r in KnowledgeBase().all() if (r.genre or "").strip()}
    assert genres, "the KB carries no genre-tagged rules — this guard is vacuous"
    empty = sorted(g for g in genres if not rc.prompt_fragment_for_genre(g).strip())
    assert not empty, f"tagged genres rendering an empty fragment: {empty}"


def test_every_genre_tagged_rule_is_reachable_through_the_genre_path(rc):
    """The generic path no longer carries genre rules, so the genre path must
    be able to deliver every one of them — otherwise a rule becomes
    unreachable everywhere."""
    from knowledge_base import KnowledgeBase
    unreachable = []
    for rule in KnowledgeBase().all():
        tag = (rule.genre or "").strip()
        if tag and rule.id not in {r.id for r in rc.rules_for_genre(tag)}:
            unreachable.append(rule.id)
    assert not unreachable, f"genre-tagged rules no rule path can deliver: {unreachable}"


def test_no_genre_tagged_rule_leaks_into_a_generic_pass(rc):
    """The generic passes run BEFORE the genre is known, so they must stay
    genre-neutral. Otherwise a romance receives all eight genres' principles."""
    from screenplay_analyzer.rules_context import is_genre_scoped
    offenders = {}
    for name in set(CATEGORY_TO_TAXONOMY_LEVELS) | set(PASS_EXTRAS):
        leaked = [r.id for r in rc.rules_for_pass(name) if is_genre_scoped(r)]
        if leaked:
            offenders[name] = leaked
    assert not offenders, (
        "genre-specific rules are being injected into genre-blind passes "
        f"(the caller does not know the script's genre yet): {offenders}"
    )


def test_generic_path_can_opt_back_into_genre_rules(rc):
    """The exclusion is a default, not a wall — a caller that already knows the
    genre (e.g. the genre pass, or a future genre-aware reorder) can ask for
    the full set."""
    neutral = rc.rules_for_pass("theme")
    full = rc.rules_for_pass("theme", include_genre_rules=True)
    assert len(full) > len(neutral), "include_genre_rules=True changed nothing"
    assert all(not (r.genre or "").strip() for r in neutral)


# --------------------------------------------------------------------------
# Curated severity must reach the FINDING, not just the prompt
#
# T0.6 put `severity_default` in the rule fragment so the model is guided. But
# the deterministic passes that cite a rule id by hand still hardcoded a flat
# "medium" — so a "Promise never fulfilled" grounded in a rule the KB curates
# as **high** was filed as medium. The rule is the source of truth.
# --------------------------------------------------------------------------

def test_severity_for_reads_the_curated_rule(rc):
    assert rc.severity_for("chekhovs_gun") == "medium"
    assert rc.severity_for("martell_plants_and_payoffs") == "high"
    assert rc.severity_for("lyons_story_spine") == "high"


def test_severity_for_falls_back_for_an_unknown_id(rc):
    assert rc.severity_for("no_such_rule") == "medium"
    assert rc.severity_for("no_such_rule", "low") == "low"
    assert rc.severity_for("") == "medium"


def test_severity_for_tolerates_a_stub_or_missing_context():
    """Several tests pass an object exposing only `fragment_for_pass`."""
    from screenplay_analyzer.rules_context import severity_for
    assert severity_for(None, "martell_plants_and_payoffs") == "medium"
    assert severity_for(object(), "martell_plants_and_payoffs", "low") == "low"


def test_principles_finding_takes_the_cited_rules_severity(rc):
    from screenplay_analyzer.principles_engine import _finding_from_judgment
    judgment = {"significant": True, "paid_off": False, "reasoning": "never returns"}
    high = _finding_from_judgment("recurring_object", "the locket", [2], judgment,
                                  "martell_plants_and_payoffs",
                                  severity=rc.severity_for("martell_plants_and_payoffs"))
    assert high["severity"] == "high", (
        "a finding citing a rule the KB curates as high is still graded medium"
    )
    medium = _finding_from_judgment("recurring_object", "the locket", [2], judgment,
                                    "chekhovs_gun", severity=rc.severity_for("chekhovs_gun"))
    assert medium["severity"] == "medium"


def test_ledger_finding_takes_the_cited_rules_severity(rc):
    from screenplay_analyzer.setup_payoff import dangling_findings
    ledger = [{"status": "dangling", "setup": "the broken watch", "setup_scenes": [3], "note": ""}]
    assert dangling_findings(ledger, [], rules_ctx=rc)[0]["severity"] == \
        rc.severity_for("setup_payoff_general")
    # back-compat: no context still yields a valid severity
    assert dangling_findings(ledger, [])[0]["severity"] == "medium"


def test_the_two_plot_passes_agree_on_a_shared_rule(rc):
    """The whole point: one rule id, one severity, whichever pass reports it."""
    from screenplay_analyzer.principles_engine import _finding_from_judgment
    from screenplay_analyzer.setup_payoff import dangling_findings
    rule = "setup_payoff_general"
    judgment = {"significant": True, "paid_off": False, "reasoning": "x"}
    engine = _finding_from_judgment("dialogue_promise", "a promise", [1], judgment, rule,
                                    severity=rc.severity_for(rule))
    ledger = dangling_findings(
        [{"status": "abandoned", "setup": "a promise", "setup_scenes": [1], "note": ""}],
        [], rules_ctx=rc)
    assert engine["severity"] == ledger[0]["severity"] == rc.severity_for(rule)


