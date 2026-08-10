# screenplay_studio/orchestrator.py

## Purpose
The Orchestrator — the main entry point for the screenplay studio. Orchestrates the full pipeline: parse → analyze → chat.

## Key Types

### `Orchestrator`
```python
class Orchestrator:
    def __init__(self, path: str):
        self.path = path
        self.manifest = None
        self.doc = None
        self.results = None
```

### `OrchestratorError`
Error type for orchestrator failures (24 edges in graph).

## Key Methods

### `Orchestrator.run_parse()`
Runs the parsing step. Loads the screenplay and builds a ScriptDocument.

### `Orchestrator.run_analyze()`
Runs the analysis step. Calls the analysis pipeline.

### `Orchestrator.start_chat()`
Starts the interactive chat session.

### `Orchestrator.run_full()`
Runs the full pipeline: parse → analyze → chat.

## Dependencies
- `screenplay_parser` (parse_text, parse_fountain)
- `screenplay_analyzer.pipeline` (analyze)
- `screenplay_analyzer.llm_client` (LlamaServerClient)
- `screenplay_cowriter.engine` (CoWriterEngine)
- `screenplay_studio.manifest` (ProjectManifest)

## Usage Example
```python
from screenplay_studio.orchestrator import Orchestrator

orch = Orchestrator(path="my_script.fountain")
orch.run_parse()
orch.run_analyze()
orch.start_chat()
```

## Graph Notes
- `Orchestrator` is the 2nd most connected node (40 edges)
- `OrchestratorError` (24 edges) — error handling
- Connects `Docstrings & Comments` to `Parser & Knowledge Graph`, `E2E Tests`, `Studio Manifest & Tests`
- 33 inferred edges need verification
