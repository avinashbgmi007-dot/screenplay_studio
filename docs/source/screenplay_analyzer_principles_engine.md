# screenplay_analyzer/principles_engine.py

## Purpose
Implements the Principles Engine — a system for detecting and evaluating writing principles like Chekhov's Gun, promise/payoff, and other craft principles.

## Key Functions

### `_judge_candidate(candidate: dict, doc: ScriptDocument) -> dict`
Judges whether a candidate finding is a real issue. Uses principles-based reasoning.

### `_finding_from_judgment(judgment: dict) -> dict`
Converts a judgment into a structured finding.

## Principles Implemented
- **Chekhov's Gun**: If a prop is introduced, it should be used
- **Promise/Payoff**: Setup elements should have payoff elements
- **Show Don't Tell**: Action should be shown, not told
- **Character Consistency**: Characters should act consistently

## Dependencies
- `screenplay_parser.models` (ScriptDocument)
- `screenplay_analyzer.prompts` (principle prompts)
- `screenplay_analyzer.grammar` (grammar constraints)

## Usage Example
```python
from screenplay_analyzer.principles_engine import _judge_candidate

candidate = {"promise_type": "chekhov_gun", "setup": "gun on wall", ...}
judgment = _judge_candidate(candidate, doc)
```

## Graph Notes
- Connects to `ScriptDocument` (34 inferred edges)
- Core of the principles-based analysis layer
