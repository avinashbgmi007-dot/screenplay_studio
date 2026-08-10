# screenplay_analyzer/pipeline.py

## Purpose
The main analysis pipeline. Orchestrates scene summaries, dialogue analysis, and finding generation. This is the core of the LLM-based analysis layer.

## Key Functions

### `analyze(doc: ScriptDocument, llm_client: LlamaServerClient) -> dict`
Main entry point. Runs the full analysis pipeline:
1. Builds scene summaries
2. Runs dialogue analysis
3. Generates findings
4. Verifies findings against source text

### `build_scene_summaries(doc: ScriptDocument, llm_client: LlamaServerClient) -> list[dict]`
Uses LLM to generate summaries for each scene. Uses GBNF grammar constraints for structured output.

### `run_dialogue_analysis(doc: ScriptDocument, llm_client: LlamaServerClient) -> dict`
Analyzes dialogue patterns:
- Character voice analysis
- Dialogue density per scene
- Subtext detection

### `generate_findings(doc: ScriptDocument, scene_summaries: list[dict], llm_client: LlamaServerClient) -> list[dict]`
Generates findings (issues, observations, recommendations) using LLM with grammar-constrained output.

## Dependencies
- `screenplay_parser.models` (ScriptDocument)
- `screenplay_analyzer.prompts` (prompt templates)
- `screenplay_analyzer.grammar` (GBNF grammars)
- `screenplay_analyzer.verifier` (finding verification)
- `screenplay_analyzer.rules_context` (rules context)
- `screenplay_analyzer.llm_client` (LlamaServerClient)
- `screenplay_analyzer.report` (report generation)

## Usage Example
```python
from screenplay_analyzer.pipeline import analyze
from screenplay_analyzer.llm_client import LlamaServerClient

client = LlamaServerClient(base_url="http://localhost:8080")
doc = parse_text("# INT. COFFEE SHOP...")
results = analyze(doc, client)
# results = {
#   "scene_summaries": [...],
#   "dialogue_analysis": {...},
#   "findings": [...]
# }
```

## Graph Notes
- `Orchestrator` (40 edges) is the 2nd most connected node — it wraps this pipeline
- `LlamaServerClient` (28 edges) is the 4th most connected node
- 33 inferred edges around `Orchestrator` need verification
