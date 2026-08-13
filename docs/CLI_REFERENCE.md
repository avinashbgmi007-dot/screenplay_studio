# CLI Reference

All four packages are runnable standalone via `python -m <package>`. Model-dependent stages (analyzer, co-writer) require a running `llama-server` (default `http://localhost:8080`).

## screenplay_studio — orchestrator + web UI

```bash
# Full pipeline: parse -> analyze -> drop into interactive chat REPL
python -m screenplay_studio run my_script.fdx --project ./proj --server http://localhost:8080

# Parse + analyze only (skip the interactive handoff)
python -m screenplay_studio run my_script.fdx --project ./proj --skip-chat

# Run a single stage
python -m screenplay_studio run my_script.fdx --project ./proj --only parse
python -m screenplay_studio run my_script.fdx --project ./proj --only analyze
python -m screenplay_studio run my_script.fdx --project ./proj --only chat

# Resume — reruns only stages that aren't complete
python -m screenplay_studio resume ./proj --server http://localhost:8080

# Show stage status
python -m screenplay_studio status ./proj

# Auto-analyze screenplays dropped into a folder (poll loop)
python -m screenplay_studio watch ./inbox --projects-dir ./watched_projects --poll 5
python -m screenplay_studio watch ./inbox --once    # process what's there and exit

# Web app (Flask, port 8500) — separate module, not a studio subcommand
python -m screenplay_studio.webapp_server --port 8500 --projects-dir ./studio_projects
```

| Command | Options | Notes |
|---|---|---|
| `run [source] --project DIR` | `--title`, `--server`, `--model`, `--categories`, `--only {parse,analyze,chat}`, `--skip-chat`, `--lang {eng,tenglish,hindi,tamil}` | `source` only needed for a new project; existing projects resume. |
| `resume DIR` | `--server`, `--model`, `--skip-chat`, `--lang` | Skips completed stages. |
| `status DIR` | — | Prints parse/analyze/chat status + errors. |
| `watch DIR` | `--projects-dir`, `--server`, `--model`, `--poll SECS`, `--once`, `--categories`, `--lang` | Detects supported extensions; creates one project per file. |
| `webapp_server` (module) | `--port` (default 8500), `--projects-dir` | Serves the SPA + JSON API. Run as `python -m screenplay_studio.webapp_server`. |

## screenplay_parser — Piece 1 (deterministic, no model)

```bash
python -m screenplay_parser parse script.fdx -o parsed.json
python -m screenplay_parser parse script.pdf -o parsed.json --stats --kg
python -m screenplay_parser stats parsed.json
```

| Command | Options | Notes |
|---|---|---|
| `parse INPUT` | `-o/--output` (default `<input>.json`), `--stats`, `--kg` | Input: `.fdx`, `.pdf`, `.txt`, `.fountain`, `.md`. Prints confidence, scene/character counts, warnings. `--kg` also writes `<output>.kg.json`. |
| `stats INPUT` | — | Prints deterministic analytics JSON for an already-parsed file. |

## screenplay_analyzer — Piece 2 (LLM, requires llama-server)

```bash
python -m screenplay_analyzer parsed.json --server http://localhost:8080 -o report.md
python -m screenplay_analyzer parsed.json --categories dialogue,theme,character
```

| Option | Default | Notes |
|---|---|---|
| `input` | — | ScriptDocument JSON (Piece 1 output). |
| `--server` | `http://localhost:8080` | llama-server base URL. |
| `--model` | loaded model | Explicit model id override. |
| `-o/--output` | `<input>.report.md` | Writes both `.md` and `<name>.findings.json`. |
| `--categories` | `dialogue,theme,character,structure,scene_function,coverage` | Comma-separated. |

## screenplay_cowriter — Piece 3 (LLM, requires llama-server)

```bash
# New session with full context (recommended)
python -m screenplay_cowriter chat --new "My Script" --report report.findings.json --script parsed.json

# New session from script only
python -m screenplay_cowriter chat --new "My Script" --script parsed.json

# Resume a saved session
python -m screenplay_cowriter chat --resume <session_id>

# List sessions
python -m screenplay_cowriter list

# Standalone Flask API (port 8300)
python -m screenplay_cowriter.server --port 8300
```

| Option | Notes |
|---|---|
| `--new TITLE` | Start a new session. |
| `--resume SESSION_ID` | Resume an existing session. |
| `--report`, `--script` | Paths to Piece 2 findings / Piece 1 parsed JSON. |
| `--server`, `--model` | llama-server URL / model override. |
| `--sessions-dir` | Default `./sessions`. |

**In-chat slash commands** (`screenplay_cowriter chat` REPL):

| Command | Purpose |
|---|---|
| `/fork <name>` | Branch off into a new named thread. |
| `/switch <name>` | Jump to another branch. |
| `/branches` | List branches on this session. |
| `/delete <branch>` | Discard a branch (can't delete `main`). |
| `/persona <name>` | Switch persona: `script_consultant`, `producer`, `dev_exec`, `teacher`, `audience`, `genre_specialist`. |
| `/mode <name>` | Switch mode: `evidence_discussion`, `brainstorm`, `character_interview`. |
| `/history [n]` | Show last n messages (default 10). |
| `/help` / `/quit` | Help / exit (session saved after every turn). |

## Direct module entry points

The canonical form for each package is `python -m <package>` (e.g. `python -m screenplay_studio run ...`), which invokes that package's `cli.main()` via `__main__.py`. The webapp server is the exception: it runs as `python -m screenplay_studio.webapp_server` (it has its own `main()`, not part of the studio CLI subcommands).
