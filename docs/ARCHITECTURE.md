# Screenplay Studio — Architecture Document

> A three-piece screenplay analysis and co-writing system with an orchestrator and web UI.

---

## 1. Project Directory Architecture

```
screenplay-studio_1/
├── docs/
│   └── ARCHITECTURE.md
├── screenplay_parser/          # Piece 1 — Deterministic parsing
│   ├── __init__.py             # Export: parse_file(), parse_text()
│   ├── models.py               # ScriptDocument, Scene, Element, ElementKind
│   ├── text_parser.py          # Shared state machine for .txt/.fountain
│   ├── pdf_parser.py           # PDF → text → Element stream
│   ├── heuristics.py           # Shared classification functions
│   ├── knowledge_graph.py      # Candidate generator (not judgment engine)
│   ├── stats.py                # Character counts, dialogue ratios, scene stats
│   └── cli.py                  # CLI entry point
├── screenplay_analyzer/        # Piece 2 — LLM-powered analysis
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                  # CLI entry point
│   ├── pipeline.py             # 6-stage analysis pipeline
│   ├── llm_client.py           # GBNF grammar-constrained JSON generation
│   ├── grammar.py              # Hand-written GBNF grammars
│   ├── verifier.py             # Fuzzy matching, sliding-window verification
│   ├── principles_engine.py    # Two-stage Chekhov's Gun detection
│   ├── formatting_check.py     # Formatting rule checks
│   ├── rules_context.py        # Knowledge-base rules injection
│   ├── prompts.py              # Two-tier citation instructions
│   └── report.py               # Markdown report + JSON renderer
├── screenplay_cowriter/        # Piece 3 — Conversational co-writing
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                  # CLI with REPL and slash commands
│   ├── engine.py               # CoWriterEngine.send_message()
│   ├── context.py              # ScriptContext, ReportContext, scene injection
│   ├── personas.py             # 6 personas, 3 modes
│   ├── discovery.py            # Model selection (explicit > inherited > loaded)
│   ├── llm_client.py           # Lightweight chat client (free text)
│   ├── models.py               # Session, Branch, Message dataclasses
│   └── store.py                # File-based session store (one JSON per session)
├── screenplay_studio/          # Orchestrator + web UI
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                  # Entry: run, resume, status subcommands
│   ├── orchestrator.py         # Orchestrator class, full pipeline runner
│   ├── manifest.py             # ProjectManifest, StageStatus, resume-from-partial
│   ├── webapp_server.py        # Flask backend (port 8500)
│   └── knowledge_base/
│       └── knowledge_base.py   # KnowledgeBase, Rule dataclass
├── webapp/                     # Static frontend (no build step)
│   ├── index.html              # Single-page app shell
│   ├── app.js                  # Client-side JS (~575 lines)
│   └── style.css               # Dark ink-blue palette, serif fonts (~688 lines)
└── pyproject.toml              # Project metadata, dependencies
```

---

## 2. Frontend Inventory

### Layout & Structure
- **Single-page app** — `webapp/index.html` serves as the SPA shell.
- **No build step** — vanilla JS, no framework, no bundler.
- **Dark ink-blue palette** with serif fonts throughout.

### Client-Side JavaScript (`webapp/app.js`)
- ~575 lines of vanilla JS handling all client logic.
- **Hardcoded persona list** (line ~396): `["script_consultant", "producer", "dev_exec", "teacher", "audience", "genre_specialist"]` — does not sync with server-side `PERSONAS` dict.
- AJAX calls to Flask API endpoints for: project management, analysis, chat (start/send/fork/switch/settings).
- Branch-based session management UI (fork, switch, delete conversations).
- Report rendering with verification badges.

### CSS (`webapp/style.css`)
- ~688 lines of custom CSS.
- Dark ink-blue color scheme.
- Serif typography for readability.
- Responsive layout for the analysis report and chat interface.

### HTML (`webapp/index.html`)
- ~133 lines. Minimal SPA shell that loads `app.js` and `style.css`.

---

## 3. Backend Control Engine

### Server Endpoints (Flask, port 8500)
`webapp_server.py` exposes these JSON API endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/config` | GET | Server configuration |
| `/api/projects` | GET | List all projects |
| `/api/projects` | POST | Create new project |
| `/api/projects/<id>` | GET | Project details |
| `/api/projects/<id>/analyze` | POST | Run analysis pipeline |
| `/api/projects/<id>/report` | GET | Get analysis report |
| `/api/projects/<id>/chat/start` | POST | Start chat session |
| `/api/projects/<id>/chat/send` | POST | Send message to co-writer |
| `/api/projects/<id>/chat/fork` | POST | Fork conversation branch |
| `/api/projects/<id>/chat/switch` | POST | Switch to different branch |
| `/api/projects/<id>/chat/settings` | POST | Update chat settings |

### Data Models

**Piece 1 — Parser (`models.py`)**
```
ScriptDocument
├── scenes: list[Scene]
├── characters: dict[str, CharacterInfo]
├── knowledge_graph: dict[str, list[KnowledgeNode]]

Scene
├── kind: ElementKind (scene_heading, action, character, dialogue, parenthetical, transition, shot)
├── text: str
├── location: str (for scene headings)
├── time_of_day: str (DAY/NIGHT/etc.)
├── characters: list[str]
└── elements: list[Element]
```

**Piece 3 — Co-writer (`models.py`)**
```
Session
├── id: str
├── project_id: str
├── branches: dict[str, Branch]
├── active_branch_id: str
├── active_persona: str
├── active_mode: str
└── updated_at: datetime

Branch
├── id: str
├── messages: list[Message]
├── active_persona: str
├── active_mode: str
└── name: str

Message
├── role: str ("user" | "assistant")
├── content: str
├── timestamp: datetime
└── scene_injected: bool
```

### Threading & Worker Protocols
- **No threading** — the orchestrator runs synchronously.
- **No database** — sessions stored as individual JSON files in a directory.
- **Model discovery** — `discovery.py` resolves which model to use by checking what the llama-server reports loaded, falling back through explicit flag → inherited model from report → first available.

### Analysis Pipeline (6 stages)
1. **Formatting checks** — missing INT/EXT, missing time-of-day, character capitalization, heavy parentheticals, long action blocks.
2. **Scene summaries** — LLM-generated summaries of each scene.
3. **Dialogue analysis** — per-scene dialogue analysis with verbatim quotes.
4. **Script-level categories** — high-level script analysis.
5. **Principles engine** — Two-stage Chekhov's Gun detection (deterministic candidate generation + model significance judgment).
6. **Verification** — Fuzzy matching (SequenceMatcher, threshold 0.72) and sliding-window comparison. Flags unverified findings.

---

## 4. Dependency Tracking

### Third-Party Dependencies
- **Flask** — web server framework.
- **llama-cpp-python** — GBNF grammar-constrained JSON generation.
- **pypdf** — PDF parsing.
- **lxml** — XML parsing for .fdx files.
- **chardet** — character encoding detection.
- **rich** — terminal formatting for CLI output.
- **pydantic** — data validation (for dataclasses).

### Internal Package Configurations
- **pyproject.toml** — project metadata, dependencies, entry points.
- **No virtual environment committed** — users create their own.
- **Model-agnostic** — works with any llama.cpp-compatible model.

### System Bridges
- **llama-server** — external process that serves the LLM. Pieces communicate with it via HTTP.
- **Knowledge base** — `KnowledgeBase` class with `Rule` dataclass, independent of any specific model.
- **JSON file bridges** — pieces read each other's JSON output as plain dicts, not by importing packages. This enables standalone usage.

---

## 5. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        screenplay_studio                        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  Orchestrator│    │   Manifest   │    │  Webapp Server   │  │
│  │  (pipeline)  │    │ (resume)     │    │  (Flask :8500)   │  │
│  └──────┬───────┘    └──────────────┘    └──────────────────┘  │
│         │                                                      │
│         ▼                                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Pieces (independently usable)          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │  Piece 1        │    │  Piece 2        │    │  Piece 3    │ │
│  │  Parser         │    │  Analyzer       │    │  Co-writer  │ │
│  │                 │    │                 │    │             │ │
│  │  • .fdx/.pdf/   │    │  • GBNF grammar │    │  • 6 personas│ │
│  │    .txt/.fountain│   │  • 6 stages     │    │  • 3 modes  │ │
│  │  • Knowledge    │    │  • Verification │    │  • Branches │ │
│  │    Graph (cand.)│    │  • Principles   │    │  • Sessions │ │
│  └────────┬────────┘    └────────┬────────┘    └─────────────┘ │
│           │                      │                            │
│           ▼                      ▼                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              JSON Output Bridge                           │  │
│  │  Pieces read each other's JSON as plain dicts            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              External: llama-server                       │  │
│  │  (HTTP API, model-agnostic)                               │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Known Issues

### 1. Hardcoded `"all"` category in orchestrator
`orchestrator.py:149` calls `self.run_analyze()` without passing `run_categories`, but `pipeline.py:180` defaults to a hardcoded tuple of six categories. The orchestrator's `run_analyze()` accepts a `categories` parameter but the default `run_full()` never passes it. This means `run_full()` and `run_categories=None` behave differently than expected.

### 2. Hardcoded persona list in frontend
`app.js:396` hardcodes `["script_consultant", "producer", "dev_exec", "teacher", "audience", "genre_specialist"]` rather than reading from the server or a shared list. If the cowriter's `PERSONAS` dict gains new entries, the UI won't know about them without a deploy.

### 3. No graceful session list failure
`webapp_server.py:60-61` does `from screenplay_cowriter.store import SessionStore` inside a method, but if `screenplay_cowriter` isn't installed (a valid standalone scenario per the code's own design), this import would fail and leak a traceback on the project list page.

### 4. Conversation history not persisted
`engine.py:41-42` appends messages to `branch.messages` in-memory but the `Session` model's `save()` needs to be called explicitly. If any error path skips `store.save(session)`, the conversation is lost.

---

## 7. Design Observations

### What's Good
- **Clean separation of concerns** — Pieces don't import each other at module load time; imports happen lazily inside methods. This is intentional and correct for the composability goal.
- **Diagnose/prescribe split** — Piece 2 diagnoses problems, Piece 3 prescribes solutions.
- **Flag don't drop** — Verification system flags unverified findings rather than silently dropping them.
- **Model-agnostic knowledge base** — Works independently of any specific model.
- **Composability** — Pieces read each other's JSON as plain dicts, not by importing packages.
- **Branch-based session management** — Fork/switch/delete for co-writer conversations.
- **Manifest-based resume** — Stages track complete/failed/pending status, allowing partial resume.
- **Chunk backoff pattern** — `_with_chunk_backoff()` retries with smaller context windows for context exhaustion.
- **Two-stage Chekhov's Gun** — Deterministic candidate generation + model significance judgment.
- **Graceful fallbacks** — `_NullRulesContext` when KB not installed.
- **Safe project naming** — suffix auto-increment for duplicates.
- **Proper error handling** — specific HTTP status codes (400, 404, 500, 502).

### Design Philosophy
- **Boring is good** — No database, no threading, no framework. Deliberately simple.
- **Candidate generation ≠ judgment** — The knowledge graph is explicitly a candidate generator, not a judgment engine.
- **Model-agnostic by design** — Any llama.cpp-compatible model works.

---

*Document generated by Principal Software Systems Architect analysis.*
