# screenplay_studio/manifest.py

## Purpose
Project manifest management. Tracks the state of a project through the pipeline stages (parse, analyze, chat).

## Key Types

### `StageStatus` (Enum)
```python
class StageStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
```
Status for each pipeline stage.

### `ProjectManifest`
```python
@dataclass
class ProjectManifest:
    path: str
    stages: dict[str, StageStatus]
    updated_at: str
    version: str
```
The manifest tracks which stages have been completed and their status.

## Key Functions

### `create(path: str) -> ProjectManifest`
Creates a new manifest for a project.

### `load(path: str) -> ProjectManifest`
Loads a manifest from disk.

### `save(manifest: ProjectManifest)`
Saves the manifest to disk.

## Dependencies
- `dataclasses` (stdlib)
- `datetime` (stdlib)
- `json` (stdlib)
- `pathlib` (stdlib)

## Usage Example
```python
from screenplay_studio.manifest import create, load, save

manifest = create("my_script.fountain")
save(manifest)
manifest = load("my_script.fountain")
```

## Graph Notes
- `ProjectManifest` is the most connected node (51 edges)
- Connects `Studio Manifest & Tests` to `Docstrings & Comments`, `E2E Tests`, `Web Tests`
- 41 inferred edges need verification (highest count)
