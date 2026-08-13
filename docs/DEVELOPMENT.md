# Development Guide

How to set up, work on, and extend Screenplay Studio. Read [ARCHITECTURE.md](ARCHITECTURE.md) first for the big picture, and [AGENTS.md](../AGENTS.md) for a compact orientation.

## Setup

```bash
pip install -r requirements.txt          # requests, flask, pdfplumber
python -m pytest tests/                  # full suite (uses an in-process mock llama-server, no model needed)
```

Optional, for OCR of scanned/text-less PDFs:

```bash
pip install pytesseract pypdfium2        # pypdfium2 is lazy-imported when OCR is needed
# + install tesseract itself with eng, tel, hin, tam language packs
export SCRIPT_DOCTOR_OCR=tesseract       # or easyocr; default: auto-detect
```

There is no `pyproject.toml` — `requirements.txt` is the source of truth. No virtual environment is committed; create your own.

## Repository layout

```
screenplay_parser/        Piece 1 — deterministic: parse .fdx/.pdf/.txt/.fountain/.md -> ScriptDocument + knowledge graph
screenplay_analyzer/      Piece 2 — LLM pipeline: 11 passes, GBNF-constrained JSON, quote verification
screenplay_cowriter/      Piece 3 — branch-based chat: personas, modes, file-backed session store
screenplay_studio/        Orchestrator (manifest resume) + Flask webapp (port 8500) + revision/beatboard/watch/sample
knowledge_base/           34 attributed screenwriting-craft rules that ground analyzer prompts
tests/                    pytest suite against tests/mock_unified_server.py
```

## Conventions

- **"Boring is good"** — no database, no threading, no ORM, no frontend framework. State lives in JSON files; the orchestrator runs synchronously.
- **Pieces stay independent** — cross-package imports happen lazily inside methods (see `orchestrator.py`). Don't add module-level cross-package imports.
- **JSON file bridge** — pieces exchange data as plain dicts via JSON files (`parsed.json`, `report.findings.json`). Don't make a piece import another piece's package to share data.
- **Candidate generation ≠ judgment** — `knowledge_graph.py` proposes candidates (props, promises, characters); the LLM judges significance. Keep deterministic layers model-free.
- **Evidence-first** — every model-produced finding with an `evidence_quote` is verified against the parsed scene text (fuzzy match, threshold 0.72). Don't drop unverified findings — flag them (`verification.status = "not_found"`).
- **Fail loudly with actionable errors** — e.g. a text-less PDF with no OCR engine installed must raise a clear, actionable error, never silently return an empty parse.
- **All LLM calls go over HTTP** to a user-run `llama-server`. Grammar-constrained JSON via GBNF for structured passes; free text for chat. Model-agnostic — don't hardcode a model family.
- **Docstrings carry usage** — each `cli.py` module docstring shows the real command examples. Update the docstring when you change the CLI, and keep [CLI_REFERENCE.md](CLI_REFERENCE.md) in sync.
- **Keep [CODEBASE_MAP.md](CODEBASE_MAP.md) current** — when you add/rename/remove a public function or class, update its row (or regenerate the symbol lists with `grep -nE "^(def|class) " <pkg>/*.py`).

## How to extend

### Add an analysis pass to the pipeline

1. Write the pass in `screenplay_analyzer/` (e.g. `voice.py` — deterministic, no model) or add a model pass in `pipeline.py`.
2. Deterministic passes feed `all_findings` directly. Model passes follow the existing pattern: build prompts in `prompts.py`, constrain output with a GBNF grammar in `grammar.py`, chunk with `_chunk_by_budget`, retry with `_with_chunk_backoff`.
3. Add the category to `analyze()`'s `run_categories` default tuple if it should run by default.
4. Emit `progress_cb` stage events so the web UI shows progress.
5. Add a `CATEGORY_TITLES` entry in `report.py` if findings carry a new category.
6. Add a mock branch in `tests/mock_unified_server.py` (match on a distinctive system-prompt phrase) and a test.

### Add a craft rule to the knowledge base

1. Add a JSON entry in `knowledge_base/rules/<taxonomy_level>.json` following the schema in `knowledge_base/README.md` (id, name, taxonomy_level, category, source, definition, detection_signal, counter_considerations, severity_default, confidence_tier, requires, related_rules).
2. No code changes needed — `rules_context.py` injects rules by `taxonomy_level`/`category` at prompt time.

### Add a co-writer persona or mode

1. Add to `PERSONAS` / `MODES` in `screenplay_cowriter/personas.py`.
2. The web UI has a **hardcoded** persona list (`screenplay_studio/webapp/app.js:799`) — update it too, or new personas won't appear in the UI (known issue).

### Add a webapp endpoint

1. Add an `@app.route` in `screenplay_studio/webapp_server.py` (projects keyed by `<name>`).
2. Use proper status codes (400/404/500/502); keep failure isolation — never let a missing optional piece crash the project list.
3. Update the endpoint table in [ARCHITECTURE.md](ARCHITECTURE.md).

### Add a project stage

1. Extend `ProjectManifest` in `screenplay_studio/manifest.py` (stage status enum, default stages dict).
2. Add an `Orchestrator.run_<stage>()` method that marks `running` → `complete`/`failed`.
3. Wire into `run_full()` and the `run`/`resume` CLI commands in `screenplay_studio/cli.py`.

## Reporting & verification

- `report.py` renders both `report.md` (human) and `report.findings.json` (machine, consumed by Piece 3) from the same `AnalysisResult`.
- Verification statuses: `verified`, `not_found` (quote not confirmed), `no_quote` (scene-number-only citation — normal for summary-level categories), `scene_not_found`.

## Resolved issues & regressions

The four known issues in [ARCHITECTURE.md](ARCHITECTURE.md) (category sentinel, server-driven personas, graceful cowriter-missing handling, defensive session save) are fixed, plus partial-category resume (`run_analyze(retry_failed=True)`, CLI `--retry-failed`) and a validated `ServerConfig` holder. Regression coverage lives in `tests/test_fix_batch.py` — keep it green when touching those areas.
