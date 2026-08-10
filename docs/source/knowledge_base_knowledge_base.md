# knowledge_base/knowledge_base.py

## Purpose
The knowledge base module. Stores and manages craft knowledge (rules, principles, guidelines) for screenwriting.

## Key Types

### `Rule`
```python
@dataclass
class Rule:
    id: str
    taxonomy_level: str
    title: str
    description: str
    content: str
```
A single rule in the knowledge base.

### `KnowledgeBase`
```python
class KnowledgeBase:
    def __init__(self):
        self.rules = []

    def add_rule(self, rule: Rule):
        """Add a rule to the knowledge base."""

    def for_taxonomy_level(self, level: str) -> list[Rule]:
        """Get all rules for a given taxonomy level."""

    def render_for_prompt(self, level: str) -> str:
        """Render rules as a prompt string."""
```

## Key Functions

### `for_taxonomy_level(level: str) -> list[Rule]`
Returns all rules for a given taxonomy level.

### `render_for_prompt(level: str) -> str`
Renders rules for a given level as a prompt string.

## Dependencies
- `dataclasses` (stdlib)
- `screenplay_analyzer.rules_context` (RulesContext)

## Usage Example
```python
from knowledge_base import KnowledgeBase

kb = KnowledgeBase()
kb.add_rule(Rule(id="1", taxonomy_level="pacing", title="Pacing Rule", description="...", content="..."))
rules = kb.for_taxonomy_level("pacing")
prompt = kb.render_for_prompt("pacing")
```

## Graph Notes
- `KnowledgeBase` is connected to `RulesContext` (inferred edge)
- Core of the rules-based analysis system
