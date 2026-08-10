# screenplay_parser/stats.py

## Purpose
Deterministic statistical analysis of parsed screenplays. No LLM calls — pure computation on `ScriptDocument` objects.

## Key Functions

### `character_stats(doc: ScriptDocument) -> dict[str, int]`
Counts dialogue lines per character. Returns `{character_name: line_count}`.

### `dialogue_action_ratio(doc: ScriptDocument) -> float`
Ratio of dialogue lines to action lines. High ratio = dialogue-heavy script.

### `location_usage(doc: ScriptDocument) -> dict[str, int]`
Counts scenes per location. Returns `{location: scene_count}`.

### `average_scene_length(doc: ScriptDocument) -> float`
Average number of elements per scene.

### `scene_length_distribution(doc: ScriptDocument) -> dict[str, int]`
Distribution of scene lengths (short/medium/long).

### `genre_signals(doc: ScriptDocument) -> dict[str, float]`
Heuristic genre detection based on:
- Location patterns (INT./EXT. ratios)
- Dialogue density
- Scene count
- Time-of-day patterns

### `page_count_estimate(doc: ScriptDocument) -> int`
Estimates page count from element count (roughly 1 page = 60 elements).

### `average_dialogue_length(doc: ScriptDocument) -> float`
Average number of words per dialogue line.

## Dependencies
- `screenplay_parser.models` (ScriptDocument)
- `collections` (stdlib)

## Usage Example
```python
from screenplay_parser import parse_text
from screenplay_parser.stats import character_stats, genre_signals

doc = parse_text("# INT. COFFEE SHOP\n\nJohn: Hello.\nJane: Hi.")
print(character_stats(doc))  # {'John': 1, 'Jane': 1}
print(genre_signals(doc))    # {'comedy': 0.3, 'drama': 0.7, ...}
```

## Graph Notes
- Pure deterministic analysis — no LLM dependencies
- Complements the LLM-based analyzer with fast, reliable stats
