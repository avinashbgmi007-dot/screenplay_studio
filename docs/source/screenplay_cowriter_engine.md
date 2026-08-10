# screenplay_cowriter/engine.py

## Purpose
The CoWriter engine — the interactive writing assistant. Handles conversation management, context building, and LLM interaction for the cowriter feature.

## Key Types

### `CoWriterEngine`
```python
class CoWriterEngine:
    def __init__(self, llm_client: LlamaServerClient):
        self.llm_client = llm_client
        self.context = None

    def send_message(self, message: str, context: ScriptContext | ReportContext) -> str:
        """Send a message to the LLM and get a response."""
```

## Key Functions

### `CoWriterEngine.send_message(message: str, context: ScriptContext | ReportContext) -> str`
The main interaction method. Sends a user message with context and returns the LLM response.

## Dependencies
- `screenplay_analyzer.llm_client` (LlamaServerClient)
- `screenplay_cowriter.context` (ScriptContext, ReportContext)
- `screenplay_cowriter.personas` (PERSONAS, MODES)
- `screenplay_cowriter.models` (Session, Branch, Message)

## Usage Example
```python
from screenplay_cowriter.engine import CoWriterEngine
from screenplay_analyzer.llm_client import LlamaServerClient

client = LlamaServerClient(base_url="http://localhost:8080")
engine = CoWriterEngine(client)
response = engine.send_message("What do you think of this scene?", context)
```

## Graph Notes
- `CoWriterEngine` is the 10th most connected node (17 edges)
- Core of the interactive writing assistant
