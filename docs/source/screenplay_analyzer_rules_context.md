# screenplay_analyzer/rules_context.py

## Purpose
Wires the craft knowledge base into analyzer prompts. This is the actual fix for integrating rules-based analysis with LLM prompts.

## Key Types

### `CATEGORY_TO_TAXONOMY_LEVELS`
Maps analysis categories to taxonomy levels in the knowledge base.

### `RulesContext`
```python
class RulesContext:
    def __init__(self, knowledge_base: KnowledgeBase):
        self.kb = knowledge_base

    def render_for_prompt(self, category: str) -> str:
        """Render rules for a given category as a prompt string."""
```
Renders rules for a specific category into a prompt string that can be included in LLM prompts.

## Dependencies
- `knowledge_base` (KnowledgeBase, Rule)
- `screenplay_analyzer.prompts` (integrates rules into prompts)

## Usage Example
```python
from screenplay_analyzer.rules_context import RulesContext
from knowledge_base import KnowledgeBase

kb = KnowledgeBase()
ctx = RulesContext(kb)
rules_text = ctx.render_for_prompt("pacing")
# Includes relevant rules in the prompt
```

## Graph Notes
- `Wires the craft knowledge base into analyzer prompts` — inferred connection to KnowledgeBase
- Core integration point between rules engine and LLM analysis
