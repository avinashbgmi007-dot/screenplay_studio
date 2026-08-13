# AGENTS.md — Screenplay Studio

Local, privacy-first screenplay analysis & co-writing suite. Parses `.fdx`/`.fountain`/`.txt`/`.md`/`.pdf` screenplays, runs LLM-powered analysis, and offers a conversational co-writer. All LLM calls go to a user-run `llama-server` over HTTP — no cloud APIs.

## Tech stack

- **Language:** Python 3 (no build step, stdlib-first)
- **Package manager:** pip — `requirements.txt` is the source of truth (no `pyproject.toml`)
- **Runtime deps:** `requests`, `flask`, `pdfplumber`
- **Optional:** `pytesseract`/`easyocr` (OCR fallback for text-less PDFs) + `pypdfium2` (lazy-imported PNG rendering for OCR); tesseract lang packs for tel/hin/tam
- **Frontend:** vanilla JS + CSS SPA in `screenplay_studio/webapp/` — no framework, no bundler, no node
- **External service:** `llama-server` (llama.cpp, `--jinja`), any GGUF model, default `http://localhost:8080`

## Commands

```bash
pip install -r requirements.txt

# Full pipeline: parse -> analyze -> interactive chat
python -m screenplay_studio run script.fountain --project ./proj --server http://localhost:8080
python -m screenplay_studio run script.pdf --project ./proj --skip-chat   # analyze only
python -m screenplay_studio resume ./proj --server http://localhost:8080  # resume partial
python -m screenplay_studio status ./proj

# Pieces standalone
python -m screenplay_parser parse script.fdx -o parsed.json --kg
python -m screenplay_analyzer parsed.json --server http://localhost:8080 -o report.md
python -m screenplay_cowriter chat --new "Name" --report report.findings.json --script parsed.json

# Web app (Flask, port 8500) — module, not a studio subcommand
python -m screenplay_studio.webapp_server --port 8500 --projects-dir ./studio_projects

# Tests (281 tests collected; mock llama-server, no model needed)
python -m pytest tests/
```

## Architecture

Four sibling packages + a knowledge base, wired by an orchestrator. Pieces are independently usable and communicate via **JSON files as plain dicts** (no cross-package imports at module load — imports are lazy inside methods).

```
screenplay_parser/    Piece 1 — deterministic parsing -> parsed.json + knowledge graph (no model)
knowledge_base/       34 attributed craft rules grounding analyzer judgments (no model)
screenplay_analyzer/  Piece 2 — 11-pass LLM pipeline, GBNF grammar-constrained JSON, quote verification
screenplay_cowriter/  Piece 3 — branch-based chat, 6 personas x 3 modes, file-based session store
screenplay_studio/    Orchestrator (manifest-driven resume) + Flask webapp server
```

Key flows:
- **Pipeline (11 passes, `pipeline.py:analyze()`):** formatting & stats → voice/subtext (deterministic) → scene summaries → dialogue analysis → script-level categories (theme/character/structure/scene_function) → principles engine (2-stage Chekhov's Gun) → character reads → verification (fuzzy match, threshold 0.72) → coverage → logline test & genre check → feedback filter
- **Resume semantics:** `project.json` manifest tracks each stage as `pending`/`complete`/`failed`. A *total* analyze failure is `failed` (raises); a *partial* failure (some categories OK) is `complete` with visible errors.
- **Model discovery:** explicit flag → model inherited from report → first available on llama-server.
- **Webapp:** Flask JSON API (port 8500), SPA frontend, projects stored under `studio_projects/`.

## Conventions

- **"Boring is good"** — no database, no threading, no framework. Sessions = one JSON file each; state = file-based.
- **Candidate generation ≠ judgment** — the knowledge graph proposes candidates; the LLM judges significance.
- **Diagnose/prescribe split** — analyzer diagnoses, co-writer prescribes.
- **Flag, don't drop** — unverifiable findings are flagged, never silently removed.
- **Evidence-first** — every analyzer quote is verified against the actual script text.
- **Fail loudly with actionable errors** — e.g. missing OCR engine returns a clear message, not an empty parse.
- **Tests** live in `tests/` and talk to `tests/mock_unified_server.py`; run against the real llama-server only if you have one.

## Docs index

- `docs/CODEBASE_MAP.md` — **read this first**: symbol-level index of every module and its public API (no full-repo scan needed)
- `docs/ARCHITECTURE.md` — system architecture (tree, API endpoints, pipeline, known issues)
- `docs/PROJECT_OVERVIEW.md` — product overview and design principles
- `docs/CLI_REFERENCE.md` — every CLI command across the four packages
- `docs/DATA_FORMATS.md` — JSON bridge schemas (parsed/kg/report/manifest/session/progress)
- `docs/DEVELOPMENT.md` — setup, conventions, how to extend (pipeline pass, rule, persona, endpoint)
- `docs/TESTING.md` — test suite layout and the mock llama-server
- `NOTES.md` — handoff log; read it first, update it as you work

## Efficient workflow (avoid re-scanning the repo)

1. Read `NOTES.md` → `AGENTS.md` → `docs/CODEBASE_MAP.md` (all small files).
2. Open only the modules the map points you to — never glob/read the whole tree first.
3. If you changed a public symbol, update `docs/CODEBASE_MAP.md` in the same edit.
4. If you finished meaningful work, update `NOTES.md` so the next session picks up without re-deriving state.

## Gotchas

- Analyzer/co-writer stages require a running llama-server; parser and KB do not.
- Hardcoded persona list in `screenplay_studio/webapp/app.js` (doesn't sync with server `PERSONAS`); default category tuple lives in `pipeline.py:analyze()`.
- OCR-parsed PDFs are best-effort (mark project as low-confidence).
- Project dirs (`studio_projects/`, `.freebuff/`) are git-ignored runtime data.
