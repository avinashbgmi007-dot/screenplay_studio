# screenplay_studio/cli.py

## Purpose
Command-line interface for the screenplay studio. Provides commands for running the full pipeline, resuming, and checking status.

## Key Commands

### `cmd_run(args)`
Runs the full pipeline: parse → analyze → chat.

### `cmd_resume(args)`
Resumes a previous run from where it left off.

### `cmd_status(args)`
Shows the current status of a project.

### `main()`
Entry point. Parses CLI arguments and dispatches to commands.

## CLI Usage
```bash
# Full pipeline: parse -> analyze -> drop
python -m screenplay_studio.cli run my_script.fountain

# Resume a previous run
python -m screenplay_studio.cli resume my_script.fountain

# Check status
python -m screenplay_studio.cli status my_script.fountain
```

## Dependencies
- `screenplay_studio.orchestrator` (Orchestrator)
- `screenplay_studio.manifest` (ProjectManifest)
- `argparse` (stdlib)
- `sys` (stdlib)

## Graph Notes
- CLI connects to `Orchestrator` and `ProjectManifest`
- "Hands off to the same interactive loop Piece 3's own CLI uses" — inferred connection
