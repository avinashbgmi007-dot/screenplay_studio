# screenplay_cowriter/context.py

## Purpose
Builds context objects for the CoWriter engine. Converts parsed screenplays and analysis reports into structured context for LLM interaction.

## Key Types

### `ScriptContext`
```python
@dataclass
class ScriptContext:
    title: str
    author: str
    scenes: list[Scene]
    raw_text: str
```
Context built from a parsed screenplay.

### `ReportContext`
```python
@dataclass
class ReportContext:
    scene_summaries: list[dict]
    findings: list[dict]
    dialogue_analysis: dict
```
Context built from analysis results.

## Key Functions

### `build_system_prompt(script_context: ScriptContext, report_context: ReportContext) -> str`
Builds the system prompt for the CoWriter LLM, combining script context and report context.

## Dependencies
- `screenplay_parser.models` (ScriptDocument, Scene)
- `screenplay_analyzer.pipeline` (analysis results)
- `screenplay_cowriter.personas` (PERSONAS, MODES)

## Usage Example
```python
from screenplay_cowriter.context import build_system_prompt, ScriptContext, ReportContext

system_prompt = build_system_prompt(
    ScriptContext(title="My Script", author="Jane", scenes=[], raw_text="..."),
    ReportContext(scene_summaries=[], findings=[], dialogue_analysis={})
)
```

## Graph Notes
- Context building bridges the parser/analyzer to the cowriter
- `build_system_prompt` is the key integration point
