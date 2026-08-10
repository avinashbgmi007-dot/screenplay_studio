# screenplay_parser/models.py

## Purpose
Defines the core data types for the screenplay parser: element types, scene objects, and script documents. This is the foundation that all other modules consume.

## Key Types

### `ElementType` (Enum)
```python
class ElementType(Enum):
    TITLE = "title"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    SCENE_HEADING = "scene_heading"
    ACTION = "action"
    CHARACTER = "character"
    DIALOGUE = "dialogue"
    PARENTHETICAL = "parenthetical"
    TRANSITION = "transition"
    SECTION_HEADING = "section_heading"
    NOTE = "note"
    PAGE_BREAK = "page_break"
    UNKNOWN = "unknown"
```
Represents every recognized screenplay element type. Used throughout the pipeline to classify parsed text.

### `Scene`
```python
@dataclass
class Scene:
    location: str
    time_of_day: str
    elements: list[ElementType]
```
A parsed scene with its location, time-of-day, and list of element types. Used by the analyzer to build scene summaries.

### `ScriptDocument`
```python
@dataclass
class ScriptDocument:
    title: str
    author: str
    scenes: list[Scene]
    elements: list[Element]
    raw_text: str
```
The complete parsed screenplay. Bridges the parser to the analyzer and knowledge graph modules. High betweenness centrality (0.244) — it's the cross-community bridge connecting parser, knowledge graph, CLI, and formatting.

### `Element`
```python
@dataclass
class Element:
    element_type: ElementType
    text: str
    line_number: int
```
A single parsed element with its type, text content, and source line number.

## Dependencies
- `dataclasses` (stdlib)
- `enum` (stdlib)
- Consumed by: `screenplay_parser/stats.py`, `screenplay_analyzer/pipeline.py`, `screenplay_analyzer/verifier.py`

## Usage Example
```python
from screenplay_parser.models import ScriptDocument, Scene, ElementType

doc = ScriptDocument(
    title="My Script",
    author="Jane Doe",
    scenes=[Scene(location="INT. COFFEE SHOP", time_of_day="DAY", elements=[ElementType.ACTION, ElementType.DIALOGUE])],
    elements=[],
    raw_text="..."
)
```

## Graph Notes
- `ScriptDocument` has 39 edges in the knowledge graph (3rd most connected)
- 34 inferred edges need verification (model-reasoned connections)
- Connects `Parser & Knowledge Graph` to `CLI & Formatting` and `Evidence Verifier`
