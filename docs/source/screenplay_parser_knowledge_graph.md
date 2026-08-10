# screenplay_parser/knowledge_graph.py

## Purpose
Builds a knowledge graph from a parsed screenplay. Extracts characters, locations, props, promises, and relationships between entities.

## Key Types

### `PropCandidate`
```python
@dataclass
class PropCandidate:
    prop_name: str
    context: str
    scene: str
```
A potential prop mentioned in the screenplay.

### `PromiseCandidate`
```python
@dataclass
class PromiseCandidate:
    promise_type: str  # e.g., "chekhov_gun", "setup_payoff"
    setup_element: str
    payoff_element: str
    confidence: float
```
A potential promise/payoff pair (Chekhov's Gun detection).

## Key Functions

### `build_knowledge_graph(doc: ScriptDocument) -> dict`
Builds the full knowledge graph:
- Extracts characters, locations, props
- Detects promise/payoff relationships
- Builds entity relationships
- Returns a dict with nodes, edges, communities

### `extract_characters(doc: ScriptDocument) -> list[str]`
Extracts unique character names from dialogue.

### `extract_locations(doc: ScriptDocument) -> list[str]`
Extracts unique locations from scene headings.

### `extract_props(doc: ScriptDocument) -> list[PropCandidate]`
Extracts props mentioned in action lines.

### `detect_promises(doc: ScriptDocument) -> list[PromiseCandidate]`
Detects Chekhov's Gun and other promise/payoff patterns.

## Dependencies
- `screenplay_parser.models` (ScriptDocument, Element, ElementType)
- `screenplay_parser.heuristics`
- `networkx` (graph library)
- `community` (community detection)

## Usage Example
```python
from screenplay_parser import parse_text
from screenplay_parser.knowledge_graph import build_knowledge_graph

doc = parse_text("# INT. COFFEE SHOP\n\nJohn enters with a gun.")
graph = build_knowledge_graph(doc)
print(graph["nodes"])  # List of nodes
print(graph["edges"])  # List of edges
```

## Graph Notes
- 556 nodes, 1325 edges extracted from 49 code + 5 doc files
- 22 communities detected and labeled
- God nodes: `ScriptDocument` (39 edges), `ElementType` (23 edges)
- `ProjectManifest` has 41 inferred edges needing verification
