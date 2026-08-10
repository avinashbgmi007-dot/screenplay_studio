# knowledge_base/__init__.py

## Purpose
Package initialization for knowledge_base. Exports the main public API.

## Exports
- `KnowledgeBase` — from `knowledge_base.knowledge_base`
- `Rule` — from `knowledge_base.knowledge_base`

## Usage Example
```python
from knowledge_base import KnowledgeBase, Rule

kb = KnowledgeBase()
kb.add_rule(Rule(id="1", taxonomy_level="pacing", title="Rule", description="...", content="..."))
```

## Dependencies
- `knowledge_base.knowledge_base`

## Graph Notes
- Package init — no direct graph edges (standard Python pattern)
