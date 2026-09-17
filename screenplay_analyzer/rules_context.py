"""
Wires the craft knowledge base into analyzer prompts. This is the actual
fix for the problem flagged earlier: instead of a hand-written paraphrase
of a craft concept baked into each prompt string, every category now
retrieves its rules from the same versioned, attributed source every time,
regardless of which local model is loaded.

Depends on the `knowledge_base` package sitting alongside this one (same
composability convention as the screenplay_parser dependency — copy it
next to this package, or pip install -e it).
"""

from __future__ import annotations

import os
import warnings

# category name (as used throughout pipeline.py/prompts.py) -> which
# knowledge-base taxonomy level(s) that category should pull rules from.
#
# NOTE: the key MUST match the name the pipeline actually asks for. The
# finding category is "plot_thread" everywhere (grammar.py, report.py,
# pipeline.py, principles_engine.py, setup_payoff.py, app.js) — so the key
# here is "plot_thread". An earlier "plot" key made `.get("plot_thread")`
# return [] and silently left the Principles Engine and the setup/payoff
# ledger with ZERO grounding (no error, just an empty fragment).
CATEGORY_TO_TAXONOMY_LEVELS = {
    "theme": ["story_macro", "theme"],
    "character": ["character", "relationship", "psychology", "nonverbal"],
    "structure": ["structure_pacing"],
    "scene_function": ["scene"],
    "dialogue": ["dialogue"],
    "plot_thread": ["plot_thread"],
    "continuity": ["continuity"],
    "pitch": ["pitch"],
    "revision": ["revision"],
}

# Extra rule files to inject into specific pipeline passes.
# Key: pass name (as used in pipeline.py), Value: list of filenames.
# These may add rules no taxonomy level covers (scene_function's
# visual_storytelling.json); they must never re-add one a level already
# supplied — rules_for_pass() de-duplicates by id for exactly that reason.
PASS_EXTRAS = {
    "dialogue": ["dialogue_advanced.json"],
    "scene_function": ["visual_storytelling.json", "revision.json"],
    "character": ["psychology.json", "body_language.json"],
    "logline_test": ["pitch.json"],
}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        warnings.warn(f"{name}={raw!r} is not an integer; using {default}.",
                      RuntimeWarning, stacklevel=2)
        return default


# A single pass's rendered KB fragment can dwarf the pipeline's own scene
# budget (the character pass renders ~79k chars / ~20k tokens). Rather than
# let the model server truncate silently, the size is made visible:
#   * SCREENPLAY_KB_WARN   — soft ceiling; past it a RuntimeWarning names the pass.
#   * SCREENPLAY_KB_BUDGET — hard cap; past it, whole rules are kept by
#     confidence tier and the omission is stated in the prompt itself.
# The hard budget defaults to 0 (unlimited) so nothing changes unless opted in.
KB_FRAGMENT_CHAR_BUDGET = _env_int("SCREENPLAY_KB_BUDGET", 0)
KB_FRAGMENT_SOFT_WARN = _env_int("SCREENPLAY_KB_WARN", 40000)

_TIER_ORDER = {"high": 0, "medium": 1, "low": 2}


def is_genre_scoped(rule) -> bool:
    """True when a rule is tagged for one genre only.

    Such a rule is only meaningful once the script's genre is known. The
    generic passes (theme, character, structure, scene_function, dialogue,
    plot_thread) all run *before* the coverage pass reports a genre, so
    injecting these there hands every script the principles of all eight
    genres at once — a romance receiving horror's and thriller's rules.
    They are therefore excluded from the generic path and delivered instead
    by the genre-scoped fragment (prompt_fragment_for_genre), which runs
    after coverage and knows the genre.
    """
    return bool((getattr(rule, "genre", "") or "").strip())

# Labels already reported for exceeding the soft ceiling. This is a notice
# cache, not behaviour: pytest resets the stdlib warning registry per test, so
# without it one oversized pass turns into a hundred lines of summary noise.
_WARNED_FRAGMENTS: set = set()


class RulesContext:
    def __init__(self, kb=None):
        if kb is None:
            from knowledge_base import KnowledgeBase
            kb = KnowledgeBase()
        self.kb = kb

    # ---- rule selection ---------------------------------------------------

    def rules_for_category(self, category: str, include_genre_rules: bool = False) -> list:
        """Rules for a finding category, de-duplicated by rule id (the same
        rule can sit under more than one taxonomy level).

        Genre-tagged rules are skipped unless `include_genre_rules` is set:
        see `is_genre_scoped` for why the generic path must stay genre-neutral."""
        rules: list = []
        seen: set = set()
        for level in CATEGORY_TO_TAXONOMY_LEVELS.get(category, []):
            for r in self.kb.for_taxonomy_level(level):
                if not include_genre_rules and is_genre_scoped(r):
                    continue
                if r.id not in seen:
                    seen.add(r.id)
                    rules.append(r)
        return rules

    def rules_for_pass(self, pass_name: str, include_genre_rules: bool = False) -> list:
        """Category rules + PASS_EXTRAS files, de-duplicated by rule id.

        An extra file may legitimately contribute rules no taxonomy level
        covers (scene_function's visual_storytelling.json); it must never
        re-add one a level already supplied (character's psychology.json /
        body_language.json were 54/54 duplicates before this de-dupe)."""
        rules = (self.rules_for_category(pass_name, include_genre_rules=include_genre_rules)
                 if pass_name in CATEGORY_TO_TAXONOMY_LEVELS else [])
        seen = {r.id for r in rules}
        for filename in PASS_EXTRAS.get(pass_name, []):
            if not hasattr(self.kb, "for_file"):
                continue
            for r in self.kb.for_file(filename):
                if not include_genre_rules and is_genre_scoped(r):
                    continue
                if r.id not in seen:
                    seen.add(r.id)
                    rules.append(r)
        return rules

    # ---- rendering --------------------------------------------------------

    def _render(self, rules: list, label: str) -> str:
        """Render rules for a prompt, never splitting a rule in half."""
        if not rules:
            return ""
        rendered = self.kb.render_for_prompt(rules)
        if KB_FRAGMENT_CHAR_BUDGET > 0 and len(rendered) > KB_FRAGMENT_CHAR_BUDGET:
            return self._render_budgeted(rules)
        if KB_FRAGMENT_CHAR_BUDGET <= 0 and KB_FRAGMENT_SOFT_WARN \
                and len(rendered) > KB_FRAGMENT_SOFT_WARN \
                and label not in _WARNED_FRAGMENTS:
            _WARNED_FRAGMENTS.add(label)
            warnings.warn(
                f"KB fragment for {label!r} is {len(rendered)} chars "
                f"(soft ceiling {KB_FRAGMENT_SOFT_WARN}). Set "
                f"SCREENPLAY_KB_BUDGET to cap it.", RuntimeWarning, stacklevel=1)
        return rendered

    def _render_budgeted(self, rules: list) -> str:
        """Keep whole rules, highest confidence tier first, until the budget is
        reached — then state the omission in the prompt (never drop silently)."""
        ordered = sorted(rules, key=lambda r: _TIER_ORDER.get(
            getattr(r, "confidence_tier", "medium"), 1))
        kept: list = []
        used = 0
        for r in ordered:
            piece = r.to_prompt_fragment()
            if kept and used + len(piece) > KB_FRAGMENT_CHAR_BUDGET:
                break
            kept.append(r)
            used += len(piece)
        text = self.kb.render_for_prompt(kept)
        omitted = len(rules) - len(kept)
        if omitted:
            text += (f"\n\n({omitted} further craft principles omitted to fit the "
                     f"prompt budget — the highest-confidence ones are kept.)")
        return text

    # ---- public fragment API ---------------------------------------------

    def prompt_fragment_for_category(self, category: str) -> str:
        rules = self.rules_for_category(category)
        if not rules:
            return ""
        header = (
            "Ground your analysis in these specific, named craft principles "
            "rather than generic impressions. Each includes what to look for "
            "and when NOT to flag something — both matter equally:\n\n"
        )
        return header + self._render(rules, category)

    def prompt_fragment_for_rule(self, rule_id: str) -> str:
        """Fetch a single rule's prompt fragment by id — for cases where a
        pass needs one specific principle injected (e.g. the single-scene
        Chekhov's Gun extension riding on the dialogue pass) rather than a
        whole category's worth of rules."""
        try:
            return self.kb.get(rule_id).to_prompt_fragment()
        except KeyError:
            return ""

    def rules_for_genre(self, genre: str) -> list:
        """Get rules specific to a genre from the knowledge base.
        Uses the new for_genre() API which queries by genre field first,
        then falls back to filename-based lookup."""
        return self.kb.for_genre(genre)

    def prompt_fragment_for_genre(self, genre: str) -> str:
        """Get a prompt fragment for genre-specific rules."""
        rules = self.rules_for_genre(genre)
        if not rules:
            return ""
        header = (
            "Genre-Specific Craft Principles:\n"
            "Apply these principles specific to the identified genre. "
            "Each includes what to look for and when NOT to flag:\n\n"
        )
        return header + self._render(rules, f"genre:{genre}")

    def dialogue_rules_for_genre(self, genre: str) -> str:
        """Get dialogue rules scoped by genre: genre-specific dialogue rules
        + cross-genre dialogue rules from dialogue_advanced.json."""
        genre_rules = self.kb.for_genre(genre) if genre else []
        dialogue_rules = [r for r in genre_rules if r.taxonomy_level == "dialogue"]
        # Also include cross-genre dialogue_advanced rules
        advanced_rules = self.kb.for_file("dialogue_advanced.json")
        dialogue_rules.extend(advanced_rules)
        # Deduplicate by id
        seen = set()
        unique = []
        for r in dialogue_rules:
            if r.id not in seen:
                seen.add(r.id)
                unique.append(r)
        if not unique:
            return ""
        header = (
            "Dialogue Craft Principles"
            + (f" (genre-aware for {genre})" if genre else "")
            + ":\n"
        )
        return header + self._render(unique, f"dialogue:{genre or 'any'}")

    def fragment_for_pass(self, pass_name: str) -> str:
        """Get the complete prompt fragment for a pipeline pass.
        Combines category rules with any extra files defined in PASS_EXTRAS,
        de-duplicated by rule id."""
        rules = self.rules_for_pass(pass_name)
        if not rules:
            return ""
        return self._render(rules, pass_name)
