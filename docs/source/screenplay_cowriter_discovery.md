# screenplay_cowriter/discovery.py

## Purpose
Model discovery for the CoWriter. Resolves which LLM model to use with a priority chain: explicit > inherited > whatever's loaded.

## Key Functions

### `resolve_model(explicit_model: str | None = None, inherited_model: str | None = None, loaded_model: str | None = None) -> str`
Resolves the model name using priority:
1. Explicit model (user-specified)
2. Inherited model (from parent session)
3. Whatever's loaded (default model on the server)

## Dependencies
- `screenplay_analyzer.llm_client` (LlamaServerClient, resolve_model)
- `screenplay_cowriter.models` (Session)

## Usage Example
```python
from screenplay_cowriter.discovery import resolve_model

model = resolve_model(
    explicit_model="llama-3.1-70b",
    inherited_model=None,
    loaded_model=None
)
```

## Graph Notes
- Model resolution follows the same priority as `LlamaServerClient.resolve_model`
- Connects to `LlamaServerClient` (20 inferred edges)
