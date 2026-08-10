# screenplay_parser/text_parser.py

## Purpose
The main parsing entry point. Handles text normalization, format detection, and delegates to format-specific parsers (Fountain, plain text, Markdown).

## Key Functions

### `parse_text(text: str, format: str | None = None) -> ScriptDocument`
The primary parsing function. Auto-detects format if not specified.
- Normalizes text (converts to uppercase, handles various screenplay formats)
- Supports: Fountain (.fountain), plain text (.txt), Markdown (.md)
- Returns a `ScriptDocument`

### `parse_fountain(text: str) -> ScriptDocument`
Parses Fountain format (a Markdown variant for screenplays). Handles:
- Scene headings (`# Scene Heading`)
- Character names (centered text)
- Dialogue (text after character names)
- Parentheticals (in parentheses)
- Section headings (`## Section`)
- Page breaks (`---`)

### `parse_txt(text: str) -> ScriptDocument`
Parses plain text screenplay format. Uses heuristics to detect:
- Scene headings (ALL CAPS lines)
- Character names (centered, ALL CAPS)
- Dialogue (text following character names)
- Transitions (RIGHT: text)

### `parse_md(text: str) -> ScriptDocument`
Parses Markdown format with screenplay conventions.

## Dependencies
- `screenplay_parser.heuristics` (parse_scene_heading, looks_like_*)
- `screenplay_parser.models` (ScriptDocument, Scene, Element, ElementType)
- `re` (regex)
- `dataclasses` (stdlib)

## Usage Example
```python
from screenplay_parser import parse_text

# Auto-detect format
doc = parse_text("# INT. COFFEE SHOP\n\nJohn enters.")

# Specify format explicitly
doc = parse_text("# INT. COFFEE SHOP\n\nJohn enters.", format="fountain")
```

## Graph Notes
- Heavily connected to `ElementType` (23 edges)
- Core bridge between raw text and structured `ScriptDocument`
