# screenplay_analyzer/prompts.py

## Purpose
Prompt templates for the LLM-based analysis. Defines the instructions given to the LLM for scene summaries, findings generation, and dialogue analysis.

## Key Constants

### `CITATION_INSTRUCTION`
Instructions for how the LLM should cite source text when generating findings. Ensures findings include verifiable quotes.

### `scene_summary_prompt`
Prompt template for generating scene summaries. Instructs the LLM to:
- Summarize the scene's action
- Identify key characters
- Note important props
- Flag promise/payoff setups

### `findings_prompt`
Prompt template for generating findings. Instructs the LLM to:
- Identify structural issues
- Flag inconsistencies
- Note pacing problems
- Suggest improvements

### `dialogue_analysis_prompt`
Prompt template for dialogue analysis. Instructs the LLM to:
- Analyze character voices
- Detect subtext
- Flag exposition-heavy dialogue

## Dependencies
- `screenplay_analyzer.grammar` (references grammar constraints)
- `screenplay_analyzer.rules_context` (references rules context)

## Usage Example
```python
from screenplay_analyzer.prompts import scene_summary_prompt, CITATION_INSTRUCTION

# The prompts are used internally by pipeline.py
# No direct user-facing API
```

## Graph Notes
- `CITATION_INSTRUCTION` connects to `ScriptDocument` (evidence verification)
- Prompts are the bridge between raw text and structured analysis
