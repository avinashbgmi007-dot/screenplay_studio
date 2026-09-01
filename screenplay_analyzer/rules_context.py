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

# category name (as used throughout pipeline.py/prompts.py) -> which
# knowledge-base taxonomy level(s) that category should pull rules from.
CATEGORY_TO_TAXONOMY_LEVELS = {
    "theme": ["story_macro", "theme"],
    "character": ["character", "relationship", "psychology", "nonverbal"],
    "structure": ["structure_pacing"],
    "scene_function": ["scene"],
    "dialogue": ["dialogue"],
    "plot": ["plot_thread"],
    "continuity": ["continuity"],
    "pitch": ["pitch"],
    "revision": ["revision"],
}


class RulesContext:
    def __init__(self, kb=None):
        if kb is None:
            from knowledge_base import KnowledgeBase
            kb = KnowledgeBase()
        self.kb = kb

    def rules_for_category(self, category: str):
        levels = CATEGORY_TO_TAXONOMY_LEVELS.get(category, [])
        rules = []
        for level in levels:
            rules.extend(self.kb.for_taxonomy_level(level))
        return rules

    def prompt_fragment_for_category(self, category: str) -> str:
        rules = self.rules_for_category(category)
        if not rules:
            return ""
        header = (
            "Ground your analysis in these specific, named craft principles "
            "rather than generic impressions. Each includes what to look for "
            "and when NOT to flag something — both matter equally:\n\n"
        )
        return header + self.kb.render_for_prompt(rules)

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
        return header + self.kb.render_for_prompt(rules)

    def dialogue_rules_for_genre(self, genre: str) -> str:
        """Get dialogue rules scoped by genre: genre-specific dialogue rules
        + cross-genre dialogue rules from dialogue_advanced.json."""
        genre_rules = self.kb.for_genre(genre) if genre else []
        dialogue_rules = [r for r in genre_rules if r.taxonomy_level == "dialogue"]
        # Also include cross-genge dialogue_advanced rules
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
        return header + self.kb.render_for_prompt(unique)
