# screenplay_cowriter/cli.py

## Purpose
Command-line interface for the CoWriter. Provides an interactive REPL for conversing with the LLM about screenplays.

## Key Functions

### `cmd_chat(args: argparse.Namespace)`
Main entry point for the chat command. Parses arguments and starts the REPL.

### `run_repl(engine: CoWriterEngine, session: Session)`
Runs the interactive REPL loop. Handles:
- User input
- Slash commands (/new, /fork, /switch, /delete, /quit)
- Session management
- Persona/mode switching

## Slash Commands
- `/new` — Create a new session
- `/fork <name>` — Fork current session
- `/switch <name>` — Switch to a branch
- `/delete <name>` — Delete a branch
- `/persona <name>` — Change persona
- `/mode <name>` — Change mode
- `/quit` — Exit

## Dependencies
- `screenplay_cowriter.engine` (CoWriterEngine)
- `screenplay_cowriter.models` (Session)
- `screenplay_cowriter.store` (SessionStore)
- `argparse` (stdlib)

## Usage Example
```bash
# Start a chat session
python -m screenplay_cowriter.cli --script my_script.fountain

# Interactive REPL starts
> Hello, I'm working on a scene...
> What do you think?
```

## Graph Notes
- CLI is the user-facing interface for the cowriter
- Connects to `Orchestrator` (hands off to the same interactive loop)
