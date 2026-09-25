# AGENTS.md — Screenplay Studio

Local, privacy-first screenplay analysis & co-writing suite. Parses `.fdx`/`.fountain`/`.txt`/`.md`/`.pdf` screenplays, runs LLM-powered analysis, and offers a conversational co-writer. All LLM calls go to a user-run `llama-server` over HTTP — no cloud APIs.

## Tech stack

- **Language:** Python 3 (no build step, stdlib-first)
- **Packaging:** `pyproject.toml` is the source of truth for the build (setuptools; extras `dev` / `stt` / `ci`). `requirements.txt` is the convenience runtime list and the two agree — do not treat one as authoritative over the other. `requirements.lock.txt` pins exact versions for the whole declared closure and is applied as a **constraints** file (`-c`), never as a second requirements list — regenerate it from a real environment when a dependency changes rather than retyping pins. The app ships **non-`.py` assets** (26 craft-rule JSONs, the no-build-step SPA and its fonts), so `[tool.setuptools.package-data]` + `MANIFEST.in` are load-bearing: without them the wheel installs a silently-empty knowledge base and a 404 frontend. `tests/test_packaging_data_files.py` builds a wheel and an sdist and fails if either stops covering them.
- **Licence:** **private, proprietary** — see `LICENSE`. No rights are granted; this is not open-source software.
- **Runtime deps:** `requests`, `flask`, `pdfplumber` (dictation/STT is optional: pip install "faster-whisper>=1.0.0")
- **Optional:** `pytesseract`/`easyocr` (OCR fallback for text-less PDFs) + `pypdfium2` (lazy-imported PNG rendering for OCR); tesseract lang packs for tel/hin/tam
- **Frontend:** vanilla JS + CSS SPA in `screenplay_studio/webapp/` — no framework, no bundler, no node
- **External service:** `llama-server` (llama.cpp, `--jinja`), any GGUF model, default `http://localhost:8080`; a built-in demo craft model (`demo_model.py`) fills in when no llama-server is reachable

## Commands

```bash
pip install -r requirements.txt -c requirements.lock.txt   # runtime, at the locked versions
pip install ".[ci]" -c requirements.lock.txt               # + pytest / playwright / ruff / setuptools (what CI installs)

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

# Tests (700+ tests collected; mock llama-server, no model needed)
python -m pytest tests/
```

## Architecture

Four sibling packages + a knowledge base, wired by an orchestrator. Pieces are independently usable and communicate via **JSON files as plain dicts** (no cross-package imports at module load — imports are lazy inside methods).

```
screenplay_parser/    Piece 1 — deterministic parsing -> parsed.json + knowledge graph (no model)
knowledge_base/       263 attributed craft rules (26 rule files) grounding analyzer judgments (no model)
screenplay_analyzer/  Piece 2 — 12-pass LLM pipeline (incl. setup/payoff ledger), GBNF grammar-constrained JSON, quote verification
screenplay_cowriter/  Piece 3 — branch-based chat, 8 personas x 5 modes, file-based session store, writer relationship memory, writer library (past-work digest)
screenplay_studio/    Orchestrator (manifest-driven resume) + Flask webapp server + Stash store
.agents/skills/       Persona humanization playbooks (sameer-humanizer, script-doctor-humanizer)
```

Key flows:
- **Pipeline (12 passes, `pipeline.py:analyze()`):** formatting & stats → voice/subtext/idiolect (deterministic) → continuity (deterministic) → scene summaries → dialogue analysis → script-level categories (theme/character/structure/scene_function) → principles engine (2-stage Chekhov's Gun) → **setup/payoff ledger** (end-of-pipeline whole-script audit; dangling entries fold into Plot Economy findings) → character reads → verification (fuzzy match, threshold 0.72) → coverage → logline test & genre check → feedback filter
- **Cross-project memory:** the writer's library (`screenplay_cowriter/writer_library.py`) digests every parsed project (characters/themes/scenes, no model calls) into a PAST WORK block Sameer and Dr. Sushruta ride in every turn — never merged with the current script (grounding guard).
- **The Stash:** per-project saved snippets (`screenplay_studio/stash_store.py` + `stash.json`); select a passage → 📥 Stash this; the rail lists them.
- **Three-zone shell (Phase 0):** scene index + docked **Stash & Notes** lens (the left structural rail was retired 2026-09-23 — see `docs/REDESIGN_MASTER_PLAN.md` §6), script pane never <50%, docked right room panel, thin status strip (model · connection · dawn).
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
- **Ship the data files** — the product is a no-build-step SPA plus a JSON craft knowledge base, so packaging is correctness, not polish. If `package-data`/`MANIFEST.in` stop covering an asset the app needs, the install degrades *silently* (empty KB, 404 frontend) rather than erroring. `tests/test_packaging_data_files.py` builds a real wheel and sdist to prevent that.
- **Escape at the render boundary** — the SPA has one canonical `escapeHtml()` in `core.js`; every `innerHTML` sink that interpolates finding, script, chat or config text goes through it, and the SPA document carries a strict `script-src 'self'` CSP. Never build event handlers by string-concatenating data (`tests/e2e_browser_xss_inert.py`).
- **No hand-maintained asset versions** — the `?v=` tokens in `index.html` are placeholders. `webapp_server._stamp_asset_versions` rewrites each to its asset's own content hash as the document is served, so editing a JS/CSS file invalidates its URL with no manual bump and no build step. Never reintroduce a "remember to bump this" step (`tests/test_asset_cache_bust.py`).
- **Nothing leaves the machine** — the model server and the dictation engine must both point at loopback. One predicate decides it (`net_guard.is_loopback_url` — parsed, never prefix-matched); never hand-roll a third `_LOOPBACK_HOSTS`. Every URL that reaches an outbound request goes through `webapp_server._validate_server_url`, and the opt-in for a LAN model server is process-level (`--allow-remote-server` / `SCREENPLAY_STUDIO_ALLOW_REMOTE_SERVER=1`), never grantable over HTTP (`tests/test_server_url_guard.py`).
- **One lock per store, and it must cross processes** — every writer-owned store writes through `jsonio.atomic_write_json` and takes `jsonio.lock_for(path)`; a load-modify-write must hold that lock across the **read**, not only the write. It is an in-process RLock *and* an OS byte-range lock on a `<store>.lock` sidecar, because the CLI and the webapp write the same project directory. Never take a second store's lock *after* writing through it, and never hold two cycle locks while taking a third — that is how two processes deadlock each other. Where one write cycle genuinely spans two stores (`working.json` plus the edit log), the outer lock is the cycle lock and the others are taken **only as terminal leaves, in one fixed direction**: `working.json → {edits.json, edits.redo.json}`, never a leaf back into `working.json`. Temp files are unique per write and fsynced before the rename (`tests/test_store_concurrency.py` runs real child processes; `tests/test_lock_order.py` enforces the ordering so it cannot rot).
- **Tests** live in `tests/` and talk to `tests/mock_unified_server.py`; run against the real llama-server only if you have one.

## Docs index

- `CONTEXT.md` — **domain glossary**: the official names for core entities (Project, Idea, Draft, Finding, Room, Stash, …) — use these terms exactly
- `docs/CODEBASE_MAP.md` — **read this first**: symbol-level index of every module and its public API (no full-repo scan needed)
- `docs/ARCHITECTURE.md` — system architecture (tree, API endpoints, pipeline, known issues)
- `docs/PRD.md` — **product requirements**: features, user stories, acceptance criteria (epics 1–7)
- `docs/USER_PERSONAS.md` — user archetypes (aspiring screenwriter / working rewriter / idea-stage writer) + design rules they imply
- `docs/UI_UX_SPECIFICATION.md` — **shareable UI/UX build spec**: every screen, component, state, interaction, keyboard shortcut, API contract, and an acceptance checklist (what "built & integrated" means)
- `docs/PROJECT_OVERVIEW.md` — product overview and design principles
- `docs/CLI_REFERENCE.md` — every CLI command across the four packages
- `docs/DATA_FORMATS.md` — JSON bridge schemas (parsed/kg/report/manifest/session/progress + all project stores)
- `docs/DEVELOPMENT.md` — setup, conventions, how to extend (pipeline pass, rule, persona, endpoint)
- `docs/TESTING.md` — test suite layout and the mock llama-server
- `docs/debates/` — live Sameer-vs-Premise-Doctor debate transcripts (re-run with `_debate.py`)
- `NOTES.md` — handoff log; read it first, update it as you work

## Efficient workflow (avoid re-scanning the repo)

1. Read `NOTES.md` → `AGENTS.md` → `docs/CODEBASE_MAP.md` (all small files).
2. Open only the modules the map points you to — never glob/read the whole tree first.
3. If you changed a public symbol, update `docs/CODEBASE_MAP.md` in the same edit.
4. If you finished meaningful work, update `NOTES.md` so the next session picks up without re-deriving state.

## Gotchas

- Analyzer/co-writer stages require a running llama-server; parser and KB do not.
- The client's `FALLBACK_PERSONAS` (app.js) is a degradation fallback only — the server-driven list is the source of truth; a test in `tests/test_webapp_api.py` guards the subset. Default category tuple lives in `pipeline.py:analyze()`.
- OCR-parsed PDFs are best-effort (mark project as low-confidence).
- Project dirs (`studio_projects/`, `.freebuff/`) are git-ignored runtime data.
