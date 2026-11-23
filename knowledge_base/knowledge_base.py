"""
Loader for the screenplay craft knowledge base.

This is the actual consumption mechanism described in README.md: instead
of hand-writing a paraphrase of a craft concept into each analyzer prompt,
a check retrieves the relevant rule(s) here and includes their definition
and detection_signal directly in what gets sent to the model. Same rule
text every time, regardless of which local model is loaded.

Usage:
    from knowledge_base import KnowledgeBase

    kb = KnowledgeBase()
    rules = kb.for_taxonomy_level("plot_thread")
    chekhov = kb.get("chekhovs_gun")
    prompt_fragment = kb.render_for_prompt(rules)
"""

from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass, field


_KB_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass
class Rule:
    id: str
    name: str
    taxonomy_level: str
    category: str
    source: dict
    definition: str
    detection_signal: str
    counter_considerations: str
    severity_default: str
    confidence_tier: str
    requires: list = field(default_factory=list)
    related_rules: list = field(default_factory=list)
    genre: str | None = None

    @property
    def attribution(self) -> str:
        """Short human-readable citation, e.g. 'Robert McKee, Story (1997)'."""
        src = self.source
        if src["type"] == "general_craft":
            return "widely-taught convention (no single originator)"
        parts = [src.get("originator") or "unknown"]
        if src.get("work"):
            parts.append(f'— {src["work"]}')
        return " ".join(parts)

    def to_prompt_fragment(self) -> str:
        """The actual text injected into an analyzer prompt for this rule.

        `severity_default` is the KB's curated severity for this rule. It was
        previously never read anywhere, so the same defect could be graded
        differently depending on which pass happened to find it. Stating it
        here lets the model grade against the curated value instead of
        guessing.
        """
        return (
            f"### {self.name} (source: {self.attribution})\n"
            f"Definition: {self.definition}\n"
            f"What to look for: {self.detection_signal}\n"
            f"Do NOT flag when: {self.counter_considerations}\n"
            f"Severity if confirmed: {self.severity_default}\n"
            f"[confidence_tier: {self.confidence_tier} — "
            f"{'treat findings as near-certain if detection_signal is met' if self.confidence_tier == 'high' else 'treat findings as a judgment call' if self.confidence_tier == 'medium' else 'frame findings as a discussion prompt, not a verdict'}]"
        )


class KnowledgeBase:
    def __init__(self, rules_dir: str = None):
        self.rules_dir = rules_dir or os.path.join(_KB_DIR, "rules")
        self._rules: dict[str, Rule] = {}
        self._files: dict[str, list[str]] = {}  # filename -> list of rule ids
        self._load()

    def _load(self):
        for path in sorted(glob.glob(os.path.join(self.rules_dir, "*.json"))):
            fname = os.path.basename(path)
            rule_ids = []
            with open(path, "r", encoding="utf-8") as f:
                entries = json.load(f)
            for e in entries:
                rule = Rule(**e)
                if rule.id in self._rules:
                    raise ValueError(f"Duplicate rule id '{rule.id}' found in {path}")
                self._rules[rule.id] = rule
                rule_ids.append(rule.id)
            self._files[fname] = rule_ids

    def get(self, rule_id: str) -> Rule:
        if rule_id not in self._rules:
            raise KeyError(f"No rule with id '{rule_id}'. Known ids: {sorted(self._rules.keys())}")
        return self._rules[rule_id]

    def all(self) -> list:
        return list(self._rules.values())

    def for_taxonomy_level(self, level: str) -> list:
        return [r for r in self._rules.values() if r.taxonomy_level == level]

    # Common ways a model words a genre, mapped to canonical KB tags. A
    # hybrid label can intentionally resolve to more than one genre.
    _GENRE_ALIASES = {
        "sciencefiction": ("scifi",),
        "sf": ("scifi",),
        "scifi": ("scifi",),
        "romcom": ("comedy", "romance"),
        "romanticcomedy": ("comedy", "romance"),
        "romantic": ("romance",),
        "dramedy": ("comedy", "drama"),
        "noir": ("mystery", "thriller"),
        "spy": ("thriller",),
        "suspense": ("thriller",),
        "psychologicalthriller": ("thriller",),
        "crime": ("mystery",),
        "detective": ("mystery",),
        "whodunit": ("mystery",),
        "supernatural": ("horror",),
        "period": ("drama",),
    }
    _GENRE_PHRASES = {
        ("science", "fiction"): ("scifi",),
        ("sci", "fi"): ("scifi",),
        ("romantic", "comedy"): ("comedy", "romance"),
        ("psychological", "thriller"): ("thriller",),
        ("neo", "noir"): ("mystery", "thriller"),
    }
    _CANONICAL_GENRES = (
        "action", "comedy", "drama", "horror", "mystery", "romance",
        "scifi", "thriller", "western", "fantasy",
    )

    @staticmethod
    def _norm_genre(text: str) -> str:
        """Lowercase a genre label and drop punctuation, so "Sci-Fi" and the
        stored tag "scifi" normalise to the same key."""
        return re.sub(r"[^a-z0-9]", "", (text or "").lower())

    @classmethod
    def resolve_genres(cls, genre: str) -> tuple[str, ...]:
        """Resolve a free-text label to known canonical genres.

        Exact aliases preserve established mappings, while whole-token and
        explicit phrase matching supports hybrids without accidental
        substring matches. Unknown labels resolve to an empty tuple.
        """
        if not genre or not str(genre).strip():
            return ()
        text = str(genre).lower()
        want = cls._norm_genre(text)
        if not want:
            return ()
        if want in cls._GENRE_ALIASES:
            return cls._GENRE_ALIASES[want]

        tokens = re.findall(r"[a-z0-9]+", text)
        found = set()
        for token in tokens:
            if token in cls._CANONICAL_GENRES:
                found.add(token)
            if token in cls._GENRE_ALIASES:
                found.update(cls._GENRE_ALIASES[token])

        for phrase, mapped in cls._GENRE_PHRASES.items():
            width = len(phrase)
            if any(tuple(tokens[i:i + width]) == phrase
                   for i in range(len(tokens) - width + 1)):
                found.update(mapped)

        return tuple(tag for tag in cls._CANONICAL_GENRES if tag in found)

    def for_genre(self, genre: str) -> list:
        """Return rules for every recognized genre in a free-text label.

        Both aliases and compound labels use ``resolve_genres`` so the same
        routing decision can drive convention guidance and KB grounding.
        Unknown labels intentionally return no genre-scoped rules.
        """
        genres = set(self.resolve_genres(genre))
        if not genres:
            return []
        # The KB stores the science-fiction tag as "scifi"; all other
        # canonical genre names already match the stored tags.
        kb_tags = {"scifi" if tag == "scifi" else tag for tag in genres}
        return [r for r in self._rules.values()
                if self._norm_genre(getattr(r, "genre", "") or "") in kb_tags]

    def for_file(self, filename: str) -> list:
        """Return all rules from a specific JSON file."""
        rule_ids = self._files.get(filename, [])
        return [self._rules[rid] for rid in rule_ids if rid in self._rules]

    # ---- query API --------------------------------------------------------
    # The pipeline routes rules by `taxonomy_level` (+ PASS_EXTRAS files, and
    # `genre` for the genre-scoped pass) — see
    # screenplay_analyzer/rules_context.py. The three filters below cover the
    # KB's *other* declared axes. They are deliberately NOT wired into
    # grounding yet: which rules reach a prompt is a quality change that
    # cannot be measured without a live model, and a wrong guess silently
    # degrades every finding. They are exercised by tests/test_kb_schema.py so
    # they cannot rot, and the README states the same contract.

    # Every token a rule may declare in `requires`. Declared here (rather than
    # inferred from the JSON) so a typo is caught instead of silently
    # mis-gating a rule.
    CAPABILITIES = ("scene_text", "scene_summaries", "knowledge_graph", "page_estimates")

    def for_category(self, category: str) -> list:
        """Rules carrying this fine-grained `category` tag (e.g. "stakes",
        "subtext"). This is NOT the pipeline's finding category — the finding
        categories are the keys of CATEGORY_TO_TAXONOMY_LEVELS."""
        return [r for r in self._rules.values() if r.category == category]

    def requiring(self, capability: str) -> list:
        """Rules whose check needs `capability` — one of `CAPABILITIES`."""
        return [r for r in self._rules.values() if capability in r.requires]

    def by_confidence_tier(self, tier: str) -> list:
        """Rules at a `confidence_tier` — "high" | "medium" | "low"."""
        return [r for r in self._rules.values() if r.confidence_tier == tier]

    def render_for_prompt(self, rules: list) -> str:
        """Concatenate rule fragments for inclusion in an analyzer system prompt."""
        return "\n\n".join(r.to_prompt_fragment() for r in rules)

    def stats(self) -> dict:
        from collections import Counter
        levels = Counter(r.taxonomy_level for r in self._rules.values())
        # Built through the public filter rather than a second inline
        # comprehension, so the query API is exercised on every stats() call
        # instead of sitting unused beside a duplicate of itself (F9).
        tiers = {tier: len(self.by_confidence_tier(tier))
                 for tier in sorted({r.confidence_tier for r in self._rules.values()})}
        return {
            "total_rules": len(self._rules),
            "by_confidence_tier": tiers,
            "by_taxonomy_level": dict(levels),
        }
