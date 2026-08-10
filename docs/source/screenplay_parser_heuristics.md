# screenplay_parser/heuristics.py

## Purpose
Heuristic functions for detecting screenplay elements in raw text. These are deterministic (no LLM calls) pattern-matching functions.

## Key Functions

### `looks_like_scene_heading(text: str) -> bool`
Detects if text looks like a scene heading (INT./EXT. followed by location).

### `looks_like_character_name(text: str) -> bool`
Detects if text looks like a character name (centered, ALL CAPS, short).

### `looks_like_dialogue(text: str) -> bool`
Detects if text looks like dialogue (follows a character name, not ALL CAPS).

### `looks_like_transition(text: str) -> bool`
Detects transitions (FADE TO:, CUT TO:, etc.).

### `looks_like_parenthetical(text: str) -> bool`
Detects parentheticals (text in parentheses following a character name).

### `looks_like_section_heading(text: str) -> bool`
Detects section headings (## or ### followed by text).

### `looks_like_page_break(text: str) -> bool`
Detects page breaks (--- or ***).

### `looks_like_note(text: str) -> bool`
Detects notes (text in square brackets).

### `parse_scene_heading(text: str) -> tuple[str, str]`
Parses a scene heading into (location, time_of_day).

### `normalize_character_name(name: str) -> str`
Normalizes character names for comparison (lowercase, strip whitespace).

## Dependencies
- `re` (regex)
- `screenplay_parser.models` (ElementType)

## Usage Example
```python
from screenplay_parser.heuristics import looks_like_scene_heading, parse_scene_heading

if looks_like_scene_heading("INT. COFFEE SHOP - DAY"):
    location, tod = parse_scene_heading("INT. COFFEE SHOP - DAY")
    # location = "COFFEE SHOP", tod = "DAY"
```

## Graph Notes
- `ElementType` has 23 edges — heavily connected across the codebase
- Core of the deterministic parsing layer (no model calls)
