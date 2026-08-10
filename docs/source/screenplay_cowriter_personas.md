# screenplay_cowriter/personas.py

## Purpose
Defines personas and modes for the CoWriter engine. Personas represent different writing styles/roles the LLM can adopt.

## Key Constants

### `PERSONAS`
Dictionary of persona definitions. Each persona has:
- Name
- Description
- System prompt template
- Tone/style guidelines

### `MODES`
Dictionary of mode definitions. Modes control the interaction style:
- `critique` — critical feedback
- `collaborate` — collaborative writing
- `explain` — explanation mode
- `rewrite` — rewrite mode

### `DEFAULT_PERSONA`
The default persona used when none is specified.

### `DEFAULT_MODE`
The default mode used when none is specified.

## Dependencies
- `screenplay_cowriter.context` (uses personas in system prompts)
- `screenplay_cowriter.engine` (uses personas for LLM interaction)

## Usage Example
```python
from screenplay_cowriter.personas import PERSONAS, MODES, DEFAULT_PERSONA, DEFAULT_MODE

# List available personas
for name, persona in PERSONAS.items():
    print(f"{name}: {persona['description']}")

# Use default
print(DEFAULT_PERSONA)  # Default persona name
print(DEFAULT_MODE)     # Default mode name
```

## Graph Notes
- Personas and modes are configuration for the CoWriter engine
- No direct graph edges (configuration constants)
