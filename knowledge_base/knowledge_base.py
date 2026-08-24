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
        """The actual text injected into an analyzer prompt for this rule."""
        return (
            f"### {self.name} (source: {self.attribution})\n"
            f"Definition: {self.definition}\n"
            f"What to look for: {self.detection_signal}\n"
            f"Do NOT flag when: {self.counter_considerations}\n"
            f"[confidence_tier: {self.confidence_tier} — "
            f"{'treat findings as near-certain if detection_signal is met' if self.confidence_tier == 'high' else 'treat findings as a judgment call' if self.confidence_tier == 'medium' else 'frame findings as a discussion prompt, not a verdict'}]"
        )


class KnowledgeBase:
    def __init__(self, rules_dir: str = None):
        self.rules_dir = rules_dir or os.path.join(_KB_DIR, "rules")
        self._rules: dict[str, Rule] = {}
        self._load()

    def _load(self):
        for path in sorted(glob.glob(os.path.join(self.rules_dir, "*.json"))):
            with open(path, "r", encoding="utf-8") as f:
                entries = json.load(f)
            for e in entries:
                rule = Rule(**e)
                if rule.id in self._rules:
                    raise ValueError(f"Duplicate rule id '{rule.id}' found in {path}")
                self._rules[rule.id] = rule

    def get(self, rule_id: str) -> Rule:
        if rule_id not in self._rules:
            raise KeyError(f"No rule with id '{rule_id}'. Known ids: {sorted(self._rules.keys())}")
        return self._rules[rule_id]

    def all(self) -> list:
        return list(self._rules.values())

    def for_taxonomy_level(self, level: str) -> list:
        return [r for r in self._rules.values() if r.taxonomy_level == level]

    def for_category(self, category: str) -> list:
        """Public query API — reserved for per-category prompt building."""
        return [r for r in self._rules.values() if r.category == category]

    def requiring(self, capability: str) -> list:
        """Public query API — rules needing a capability, e.g. 'knowledge_graph'."""
        return [r for r in self._rules.values() if capability in r.requires]

    def by_confidence_tier(self, tier: str) -> list:
        return [r for r in self._rules.values() if r.confidence_tier == tier]

    def render_for_prompt(self, rules: list) -> str:
        """Concatenate rule fragments for inclusion in an analyzer system prompt."""
        return "\n\n".join(r.to_prompt_fragment() for r in rules)

    def stats(self) -> dict:
        from collections import Counter
        tiers = Counter(r.confidence_tier for r in self._rules.values())
        levels = Counter(r.taxonomy_level for r in self._rules.values())
        return {
            "total_rules": len(self._rules),
            "by_confidence_tier": dict(tiers),
            "by_taxonomy_level": dict(levels),
        }
