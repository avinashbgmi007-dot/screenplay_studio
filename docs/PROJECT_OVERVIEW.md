# Project Overview — screenplay-studio

## Purpose
A three-piece screenplay analysis and co-writing system for writers who want structured feedback and conversational assistance on their screenplays. Local, privacy-first: everything stays on the machine.

## What It Does
- **Parses** screenplays in multiple formats (Fountain .fdx, .fountain, plain text, .md, PDF with OCR fallback)
- **Analyzes** them across 12 model categories (dialogue, theme, character, structure, scene_function, principles, setup/payoff ledger, char_reads, character_dials, coverage, genre, logline_test) plus deterministic passes (voice/subtext/idiolect, continuity, pacing) using an LLM with grammar-constrained JSON output
- **Co-writes** with the screenplay via a conversational interface: 8 personas × 5 modes, branch-based sessions, writer relationship memory, and a writer library (PAST WORK digest of past projects)
- **Serves a webapp** (Flask, port 8500): a two-room studio shell — the writer's desk (Sameer, co-write) and the consultant's desk (Dr. Sushruta, feedback) around a shared script pane — plus a scriptless Ideas room (premise incubator with graduation into a real project), the Stash, margin notes, Beat Board, Compare, Revision view, Feedback View, dictation (STT), and reply translation

## Core Design Principles
- **Boring is good** — no database, no framework; state is file-based, sessions are JSON files
- **Pieces are independently usable** — each piece can be imported and run standalone
- **Diagnose/prescribe split** — analysis diagnoses, co-writer prescribes
- **Model-agnostic** — works with any llama.cpp-compatible model; a built-in demo craft model fills in when no llama-server is reachable (honestly marked amber in the UI)
- **Evidence-first** — findings are verified against actual text (fuzzy threshold 0.72); unverifiable ones are flagged, never silently dropped

## Three Pieces

| Piece | Name | Responsibility | Model Dependency |
|-------|------|----------------|------------------|
| 1 | Parser | Deterministic structural extraction + knowledge graph (candidate generator) | None |
| 2 | Analyzer | LLM-powered multi-category analysis with grammar-constrained output | Required (or demo model) |
| 3 | Co-writer | Conversational co-writing with persona/mode switching and branch-based sessions | Required (or demo model) |

## Orchestrator
A thin glue layer (`screenplay_studio`) that runs the three pieces in sequence, manages a manifest for resume/retry semantics (`--retry-failed` re-runs just the failed categories), and serves the Flask web UI on port 8500.

## Key Files
- `screenplay_studio/orchestrator.py` — pipeline runner (parse → analyze → chat)
- `screenplay_studio/manifest.py` — stage status + resume state
- `screenplay_studio/cli.py` — run / resume / status / watch
- `screenplay_studio/webapp_server.py` — web UI server (Flask, port 8500)
- `screenplay_studio/webapp/` — the SPA frontend (index.html, app.js, core.js, style.css)
- `screenplay_analyzer/pipeline.py` — full analysis pipeline
- `screenplay_cowriter/engine.py` — chat engine
- `knowledge_base/` — 263 attributed craft rules across 26 rule files

## Strengths
- Well-considered find-candidates → judge → suggest split
- Error isolation through manifest (partial failures are resumable per-category)
- Chunk+backoff for model calls; retry-failed resume
- Thorough evidence verification
- Server-driven personas with frontend fallback

## Known Issues
- **Persona fallback list** (`screenplay_studio/webapp/app.js`, `FALLBACK_PERSONAS`) is used
  only when `/api/config` doesn't answer — the server-driven list is the source of truth
  (new personas appear automatically). By-design graceful degradation, guarded by a small
  test asserting the fallback stays a subset of the server's personas.
- **The shipped visual register rides the Tungsten override** (`webapp/tungsten.css`, night
  + dawn); the violet/cyan token set in `style.css` is the fallback under it. Retire the
  fallback only together with the override (boring is good: the override layer is the
  freeze).
