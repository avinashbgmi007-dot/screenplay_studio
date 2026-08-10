# screenplay_studio/__init__.py

## Purpose
Package initialization for screenplay_studio. Exports the main public API.

## Exports
- `ProjectManifest` — from `screenplay_studio.manifest`
- `StageStatus` — from `screenplay_studio.manifest`
- `Orchestrator` — from `screenplay_studio.orchestrator`
- `OrchestratorError` — from `screenplay_studio.orchestrator`

## Usage Example
```python
from screenplay_studio import Orchestrator, ProjectManifest, StageStatus

orch = Orchestrator(path="my_script.fountain")
orch.run_parse()
```

## Dependencies
- `screenplay_studio.manifest`
- `screenplay_studio.orchestrator`

## Graph Notes
- Package init — no direct graph edges (standard Python pattern)
