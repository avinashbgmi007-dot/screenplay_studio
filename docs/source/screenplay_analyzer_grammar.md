# screenplay_analyzer/grammar.py

## Purpose
GBNF (Grammars for BNF) grammar definitions for constraining LLM output. Ensures the LLM produces structured, parseable output.

## Key Grammars

### `findings_grammar`
Grammar for findings output. Constrains the LLM to produce:
- Finding title
- Finding category
- Finding severity
- Finding description
- Source citation

### `scene_summary_grammar`
Grammar for scene summaries. Constrains the LLM to produce:
- Scene location
- Scene summary text
- Character list
- Props list
- Promise/payoff flags

### `dialogue_analysis_grammar`
Grammar for dialogue analysis output.

## Dependencies
- `screenplay_analyzer.prompts` (references grammar constraints)
- `screenplay_analyzer.llm_client` (uses grammar with LLM calls)

## Usage Example
```python
from screenplay_analyzer.grammar import findings_grammar, scene_summary_grammar

# Grammars are used internally by the LLM client
# when making constrained output calls
```

## Graph Notes
- `LlamaServerError` (21 edges) — error type for LLM server failures
- Grammars are the key mechanism for reliable structured output
