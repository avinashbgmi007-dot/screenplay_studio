# screenplay_analyzer/llm_client.py

## Purpose
LLM client for interacting with a local Llama server. Handles model selection, API calls, and error handling.

## Key Types

### `LlamaServerError`
Error type for LLM server failures (21 edges in graph).

### `LlamaServerClient`
```python
class LlamaServerClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def chat_json(self, messages: list[dict], grammar: str | None = None) -> dict:
        """Chat with the LLM, optionally with grammar constraints."""

    def list_models(self) -> list[str]:
        """List available models."""

    def resolve_model(self, model: str | None = None) -> str:
        """Resolve model name: explicit > inherited > whatever's loaded."""
```

## Key Functions

### `list_models(base_url: str) -> list[str]`
Lists available models on the Llama server.

### `resolve_model(model: str | None = None) -> str`
Resolves model name with priority: explicit > inherited > whatever's loaded.

### `chat_json(base_url: str, messages: list[dict], grammar: str | None = None) -> dict`
Makes a chat call to the LLM server, optionally with grammar constraints.

## Dependencies
- `requests` (HTTP client)
- `screenplay_analyzer.grammar` (grammar constraints)
- `screenplay_analyzer.prompts` (prompt templates)

## Usage Example
```python
from screenplay_analyzer.llm_client import LlamaServerClient

client = LlamaServerClient(base_url="http://localhost:8080")
result = client.chat_json([
    {"role": "user", "content": "Analyze this script."}
])
```

## Graph Notes
- `LlamaServerClient` is the 4th most connected node (28 edges)
- `LlamaServerError` (21 edges) — error handling for server failures
- Core dependency for all LLM-based analysis
