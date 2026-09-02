# Screenplay Studio — Architecture Document

> A three-piece screenplay analysis and co-writing system with an orchestrator and web UI.

---

## 1. Project Directory Architecture

```
screenplay-studio_1/
├── docs/
│   ├── ARCHITECTURE.md         # this document — system architecture
│   ├── PROJECT_OVERVIEW.md     # high-level product overview
│   ├── CODEBASE_MAP.md         # symbol-level module index (read first)
│   ├── UI_UX_SPECIFICATION.md  # complete UI/UX spec — screens, components, states, interactions, API contracts, acceptance checklist (shareable)
│   ├── CLI_REFERENCE.md        # all CLI commands for the four packages
│   ├── DATA_FORMATS.md         # JSON bridge schemas (parsed/kg/report/manifest/session)
│   ├── DEVELOPMENT.md          # setup, conventions, how to extend
│   └── TESTING.md              # test suite & mock llama-server
├── screenplay_parser/          # Piece 1 — Deterministic parsing
│   ├── __init__.py             # Export: parse_screenplay(), build_knowledge_graph()
│   ├── models.py               # ScriptDocument, Scene, Element, ElementType
│   ├── text_parser.py          # Shared state machine for .txt/.fountain/.md
│   ├── fdx_parser.py           # .fdx XML parser
│   ├── pdf_parser.py           # PDF → text → Element stream (OCR fallback)
│   ├── export.py               # Re-export working copy to fountain/fdx/txt
│   ├── heuristics.py           # Shared classification functions
│   ├── knowledge_graph.py      # Candidate generator (not judgment engine)
│   ├── stats.py                # Character counts, dialogue ratios, scene stats
│   └── cli.py                  # CLI entry point
├── screenplay_analyzer/        # Piece 2 — LLM-powered analysis
│   ├── __init__.py / __main__.py
│   ├── cli.py                  # CLI entry point
│   ├── pipeline.py             # Multi-pass analysis pipeline
│   ├── llm_client.py           # llama-server HTTP client, GBNF-constrained JSON
│   ├── grammar.py              # Hand-written GBNF grammars
│   ├── verifier.py             # Fuzzy matching, sliding-window verification
│   ├── principles_engine.py    # Two-stage Chekhov's Gun detection
│   ├── setup_payoff.py         # End-of-pipeline setup/payoff ledger (whole-script audit)
│   ├── pacing.py               # Deterministic per-scene pace index (drag flagging, no model)
│   ├── dials.py                # Character dials: model-scored 1-10 trait poles per main character
│   ├── voice.py                # Deterministic voice-bleed, subtext & idiolect passes
│   ├── continuity.py           # Deterministic continuity pass (time flips, name variants)
│   ├── genre.py                # Genre-convention check
│   ├── feedback_filter.py      # Drops non-writing meta-commentary findings
│   ├── formatting_check.py     # Formatting rule checks
│   ├── rules_context.py        # Knowledge-base rules injection
│   ├── prompts.py              # Two-tier citation instructions
│   └── report.py               # Markdown report + JSON renderer
├── screenplay_cowriter/        # Piece 3 — Conversational co-writing
│   ├── __init__.py / __main__.py
│   ├── cli.py                  # CLI with REPL and slash commands
│   ├── server.py               # Standalone Flask API (port 8300)
│   ├── engine.py               # CoWriterEngine.send_message()
│   ├── context.py              # ScriptContext, ReportContext, scene injection
│   ├── language_meta.py        # Strips wrapper-language markers from replies
│   ├── personas.py             # 7 personas, 4 modes (default: writing_partner/peer)
│   ├── peer.py                 # guardrails: two-phase probe, forward-momentum, idea cap
│   ├── memory.py               # writer relationship memory: signals, confidence gate, card, refresh
│   ├── writer_library.py       # writer's library: deterministic digest of past projects (PAST WORK block)
│   ├── discovery.py            # Model selection (explicit > inherited > loaded)
│   ├── llm_client.py           # Lightweight chat client (free text)
│   ├── models.py               # Session, Branch, Message dataclasses
│   └── store.py                # File-based session store (one JSON per session)
├── screenplay_studio/          # Orchestrator + web UI
│   ├── __init__.py / __main__.py
│   ├── cli.py                  # Entry: run, resume, status, watch subcommands
│   ├── orchestrator.py         # Orchestrator class, full pipeline runner
│   ├── manifest.py             # ProjectManifest, StageStatus, resume-from-partial
│   ├── revision.py             # Working-copy rewrite / apply / export loop
│   ├── diff.py                 # Draft snapshots + cross-draft diffing
│   ├── beatboard.py            # Scene reordering / beat board
│   ├── notes.py                # Per-project notes store
│   ├── stash_store.py          # The Stash: per-project saved snippets (stash.json)
│   ├── character_track.py      # Per-character track layer (presence/traits/interactions/reads)
│   ├── watch.py                # Watch-folder auto-analysis
│   ├── sample.py               # Sample-script generator
│   ├── webapp_server.py        # Flask backend (port 8500)
│   └── webapp/                 # Static frontend (no build step)
│       ├── index.html          # Single-page app shell
│       ├── app.js              # Client-side JS (~2,200 lines)
│       └── style.css           # Dark ink-blue palette, serif fonts (~2,300 lines)
├── knowledge_base/             # 34 attributed screenwriting-craft rules
│   ├── knowledge_base.py       # KnowledgeBase, Rule dataclass
│   ├── rules/                  # Per-category rule JSON
│   └── schema.json
├── tests/                      # pytest suite (mock llama-server)
├── requirements.txt            # requests, flask, pdfplumber
├── AGENTS.md                   # AI-agent project context
└── NOTES.md                    # handoff log (Completed/Decisions/Open Questions/Next Steps)
```

---

## 2. Frontend Inventory

> **Complete UI/UX specification:** `docs/UI_UX_SPECIFICATION.md` is the authoritative,
> shareable spec for rebuilding the frontend — every screen, component, state, interaction,
> keyboard shortcut, and API contract, with an acceptance checklist. This section is the
> architecture-level summary.

### Layout & Structure
- **Single-page app** — `screenplay_studio/webapp/index.html` serves as the SPA shell.
- **No build step** — vanilla JS, no framework, no bundler, zero external requests (fonts
  are self-hosted `.woff2`; the only HTTP the page makes is to the Flask API).
- **"A warm room at night."** Deep ink-blue void palette (`:root` CSS variables), the
  manuscript as bright cream paper under a lamp. The **room lighting is the signature**:
  Co-write is warm amber (`--lamp`), Feedback is cool slate (`--consult`), swapped by
  `body[data-room]`. Dawn (light) theme via `body.dawn`.
- **Two rooms, one script.** The workspace is a shared script pane (always visible) plus a
  right-hand **room drawer** summoned from the edge gutter tabs: **Co-write** (the writer's
  desk — Sameer) and **Feedback** (the consultant's desk — Dr. Sushruta's Report + Fix Queue
  tabs). `body[data-room]` drives the room theming. Beat Board, Compare, and Revision are
  full-screen tools opened from the script-pane toolbar (keys `b`/`d`/`v`).
- **Three-zone shell.** Collapsible left structural rail (`#struct-rail`) holds the scene
  outline (click → jump + flash), the **character track layer** (`#rail-characters` —
  presence strip, dials, trait chips, interactions, reads), the Stash, and margin notes
  (newest-first, pinned to scenes or lines). The script pane never shrinks below 50%. A thin
  status strip shows project · model · connection · loop metrics · sprint timer · desk
  elapsed · dawn toggle.
- **Mood & reading modes.** Focus mode (`✳`, typewriter scroll, dims everything but the live
  line), Reader mode (clean draft, print-friendly), River read (`≋`, dark-glass continuous
  flow with a current-dot nav), Spotlight (`z`, total chrome removal). All persisted prefs.
- **The idea room (scriptless development).** An idea is a small sibling of a project under
  `studio_projects/ideas/<id>/` (`screenplay_studio/ideas.py` — a free-form page in
  `idea.json` + a SessionStore `sessions/` dir). The welcome screen's "Talk to Sameer about
  an idea" door creates one; the shelf has a separate **Ideas** row. Inside, a **blank
  autosaving canvas** on the void (Spark Wall starfield ambience); Sameer is OPTIONAL via a
  floating pill (one idea = one session, lazy). The room toggle swaps the *lens* on one
  conversation: Co-write = Sameer (explore), Feedback = the **premise doctor**
  (`premise_doctor`/`concept_validation` — stress-tests the concept). **Graduation:** upload
  the first pages via `/api/ideas/<id>/graduate` — a real project is created, the premise
  card + idea conversation carry over so the same thread, Sam, and memory continue on the
  script desk. Strict isolation: the idea engine gets no past-scripts digest.
- **Selection interactions.** Select text in the manuscript/idea page → floating
  "Ask Sameer about this" (prefills a quote card), "Stash this" (saves to the Stash), and
  "Note this line" (inline margin note pinned to that line). Double-click any line to edit it
  in place (rides the edits/apply path — undoable, change-starred).

### Client-Side JavaScript (`screenplay_studio/webapp/app.js` + `core.js`)
- `app.js` is ~5,900 lines of vanilla JS handling all client logic; `core.js` holds the
  DOM-free pure helpers (`fuzzyScore`, `formatMessageContent`, `truncate`, `formatElapsed`,
  `fmtDuration`, `shortModelId`) — unit-tested in `node --test tests/js/`.
- **Rooms** — `setRoom("cowrite"|"feedback")` swaps panel + `body[data-room]` identity;
  `openRoomDrawer`/`closeRoomDrawer` manage the summoned partner drawer; legacy saved views
  (`chat`/`script`) map to the Co-write room on restore.
- **Server-driven persona list** — `app.js` reads `personas`/`modes` from `GET /api/config`
  (fallback constants kept in sync manually); personas are *conversational lenses* (no
  dropdowns) — a "back to Sameer" reset button restores the default.
- **Streaming chat (SSE)** — `streamChatTurn()` renders raw tokens into the pending bubble
  as they arrive; the final SSE event carries the cleaned, stored reply + history. Falls
  back to the blocking endpoint on 404. A 408 watchdog ("still working — keep waiting?")
  avoids silent hangs on slow local models.
- **Report + fix queue rendering** — `loadFeedbackPanels()` renders `/report` and
  `/fixqueue` into Report/Fix Queue tabs with an empty state; the same `renderFixQueuePanel`
  is reused in the manuscript's Craft shelf, the Feedback tab, and the Revision view.
- **Command palette** — `Ctrl/⌘ K`, fuzzy-ranked (commands · scenes · help), `?` shows all
  shortcuts.
- **Dawn meter** — a night→dawn fill in the fix-queue head driven by
  addressed/(open+addressed); the room literally warms as findings resolve.
- **Inline editing, margin notes, stash, selection floats, translate globe, dictation
  (mic chips), sprint timer, session/prefs restore, error banner** — see
  `docs/UI_UX_SPECIFICATION.md` §7 for the full interaction catalog.

### CSS (`screenplay_studio/webapp/style.css`)
- ~4,300 lines of custom CSS.
- Full design-token system via CSS variables: void ink ramp, paper, lamp/consult room
  accents, type scale (`--font-typewriter/script/serif/mono/hand`), radius, glow.
- Room theming via `body[data-room]`; Dawn theme via `body.dawn`; river-read dark-glass
  block; focus/spotlight/reader mode overrides; print styles for the draft and beat cards.
- `prefers-reduced-motion` kill-switch, `:focus-visible` rings, amber `::selection`.

### HTML (`screenplay_studio/webapp/index.html`)
- ~530 lines. SPA shell: sidebar (brand · new-page · Ideas/shelf/library flyouts · Dawn/
  Settings footer), welcome scene + dashboard, project bar, workspace (structural rail ·
  desk · gutter · room drawer), status strip, Beat Board / Compare / Revision full-screen
  views, premise pane + idea canvas, five modals (Settings, Rewrite, Palette, Fork, Sam's
  notes). References cache-busted `style.css`/`core.js`/`app.js` (`?v=<hash>`).

---

## 3. Backend Control Engine

### Server Endpoints (Flask, port 8500)
`webapp_server.py` exposes the JSON API (projects keyed by `<name>`). **The authoritative
reference — including every request/response shape, error code, and the SSE stream
contract — is `docs/UI_UX_SPECIFICATION.md` §9.** The table below is the route map:

| Area | Endpoint | Methods |
|------|----------|---------|
| Config/conn | `/api/config`, `/api/test-connection`, `/api/health`, `/api/real-server-check` | GET/POST |
| Projects | `/api/projects`, `/api/projects/<name>`, `/api/sample`, `/api/projects/<name>/backup`, `/api/projects/<name>/reparse` | GET/POST/DELETE |
| Analysis | `/api/projects/<name>/analyze`, `/analyze/retry-failed`, `/progress`, `/report`, `/report/export`, `/fixqueue`, `/findings/<index>/dismiss`, `/findings/<index>/undismiss`, `/characters` | GET/POST |
| Manuscript | `/script`, `/rewrite`, `/edits`, `/edits/apply`, `/edits/undo`, `/edits/redo`, `/edits/reset`, `/export`, `/metrics` | GET/POST |
| Notes/Stash | `/notes`, `/notes/<id>`, `/stash`, `/stash/<id>`, `/premise` | GET/POST/PATCH/DELETE |
| Beat board/Drafts | `/beatboard`, `/beatboard/reset`, `/beatboard/export`, `/drafts`, `/drafts/activate`, `/diff`, `/compare` | GET/POST/PUT |
| Chat (project) | `/chat/start`, `/chat/sessions/<sid>`, `/chat/sessions/<sid>/messages`, `/messages/stream` (SSE), `/fork`, `/switch`, `/settings`, `/translate` | GET/POST/DELETE |
| Ideas | `/ideas`, `/ideas/<id>`, `/ideas/<id>/content`, `/rename`, `/card`, `/graduate`, `/chat/start`, `/chat/sessions/<sid>` (+ messages/stream/settings/translate) | GET/POST/DELETE |
| Writer memory | `/writer-memory`, `/writer-memory/observations/<id>/suppress`, `/writer-memory/refresh`, `/writer-library` | GET/POST |
| Dictation | `/stt`, `/stt/languages` | GET/POST |
| Design Lab | `/preview/projects`, `/preview/data/<name>`, `/preview/chat/<name>` | GET/POST/DELETE |

### Data Models

**Piece 1 — Parser (`models.py`)**
```
ScriptDocument
├── title / author / source_format (fdx|pdf|txt|fountain|md)
├── parse_confidence: str (high|medium|low)
├── front_matter: list[Element]
├── scenes: list[Scene]
├── warnings: list[ParseWarning]
└── properties: all_characters, scene_count, estimated_page_count

Scene
├── scene_number: int
├── heading_raw: str (e.g. "INT. COFFEE SHOP - DAY")
├── int_ext: str (INT|EXT|INT/EXT)
├── location: str
├── time_of_day: str (DAY/NIGHT/etc.)
├── page_start / page_end: float
├── characters_present: list[str]
└── elements: list[Element]

Element
├── type: ElementType (scene_heading, action, character, dialogue,
│                    parenthetical, transition, shot, general)
├── text: str
├── character: str (for dialogue/parenthetical)
└── line_start: int (source line, when known)
```

**Piece 3 — Co-writer (`models.py`)**
```
Session
├── session_id: str
├── title: str
├── report_path / script_path: str (Piece 2 / Piece 1 outputs)
├── server_url / model_id: str
├── branches: dict[str, Branch]
├── current_branch: str ("main" by default)
└── created_at / updated_at: float

Branch
├── name: str
├── messages: list[Message]
├── parent_branch / forked_at_index: str, int (fork lineage)
├── active_persona: str
├── active_mode: str
└── created_at: float

Message
├── role: str ("user" | "assistant" | "system")
├── content: str
├── timestamp: float
├── mode: str ("evidence_discussion" | "brainstorm" | "persona:<name>")
└── scene_refs: list[int] (scenes pulled into context for this turn)
```

### Threading & Worker Protocols
- **No threading** — the orchestrator runs synchronously.
- **No database** — sessions stored as individual JSON files in a directory.
- **Model discovery** — `discovery.py` resolves which model to use by checking what the llama-server reports loaded, falling back through explicit flag → inherited model from report → first available.

### Analysis Pipeline (multi-pass, `pipeline.py:analyze()`)
1. **Formatting checks & stats** — deterministic, no model: missing INT/EXT, time-of-day, character capitalization, heavy parentheticals, long action blocks; character counts, dialogue ratios.
2. **Craft passes** — deterministic: voice-bleed and on-the-nose subtext detection (no model call).
3. **Scene summaries** — LLM-generated per-scene summaries (chunked, token-budgeted).
4. **Dialogue analysis** — per-scene dialogue findings with verbatim quotes (chunked).
5. **Script-level categories** — theme, character, structure, scene-function (one model call each, over the scene-summary overview).
6. **Principles engine** — Two-stage Chekhov's Gun (knowledge-graph candidate generation + model significance judgment).
7. **Character-perception reads** — how each character comes across vs. apparent intent.
8. **Pacing** — deterministic per-scene pace index (density × inverted action-share), drags flagged over a threshold, capped at 4. Also emits `pacing_drag` findings. No model call.
9. **Setup/payoff ledger** — the FINAL whole-script audit: one grammar-constrained call over the full scene overview + mechanically-flagged candidates, returns a ledger {setup, kind, setup_scenes, payoff_scenes, status: paid|dangling|abandoned|red_herring, note}; dangling/abandoned fold into plot_thread findings (deduped vs. the principles engine).
10. **Character dials** — one model call scoring the main cast (≤8, by scene+dialogue share) on five 1-10 trait poles with scene_refs.
11. **Verification** — fuzzy matching (SequenceMatcher, threshold 0.72) and sliding-window comparison; flags unverified findings.
12. **Coverage** — logline / genre / synopsis / recommendation.
13. **Logline test & genre check** — premise lands in one sentence; genre conventions (uses coverage output).
14. **Feedback filter** — drops non-writing meta-commentary (dialect/subtitle noise) from the final set.

**Report surface (`report.findings.json`)** carries `pacing` (per-scene pace rows), `character_dials` (trait scores), `setup_payoff` (ledger) and `character_reads` alongside `findings` — the webapp's character-track layer (`GET /api/projects/<p>/characters`, `character_track.py`) assembles per-character presence/traits/interactions/reads from the on-disk KG + report at serve time (no model calls).

---

## 4. Dependency Tracking

### Third-Party Dependencies (`requirements.txt`)
- **requests** — HTTP client for llama-server calls (analyzer + co-writer).
- **flask** — web server framework (studio webapp + co-writer standalone API).
- **pdfplumber** — PDF text extraction (parser).

### Optional / Runtime-Discovered
- **pypdfium2** — PDF page → PNG rendering for the OCR fallback (lazy import in `pdf_parser.py`).
- **pytesseract / easyocr** — OCR engines for scanned/text-less PDFs (auto-detected; `SCRIPT_DOCTOR_OCR` env override).
- **llama-server** — external process; no Python binding required. All LLM calls go over HTTP.

### Internal Package Configurations
- **requirements.txt** — project dependencies (no `pyproject.toml`).
- **No virtual environment committed** — users create their own.
- **Model-agnostic** — works with any llama.cpp-compatible model served by llama-server.

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
│  │  • .fdx/.pdf/   │    │  • GBNF grammar │    │  • 7 personas│ │
│  │    .txt/.fountain│   │  • 11 passes    │    │  • 4 modes  │ │
│  │  • Knowledge    │    │  • Verification │    │  • Branches │ │
│  │    Graph (cand.)│    │  • Principles   │    │  • Sessions │ │
│  │                 │    │                 │    │  • Guardrails│ │
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

## 6. Resolved Issues

All four previously-known issues are fixed (2026-08-12), with regression tests in `tests/test_fix_batch.py`.

### 0. Two-room webapp + writing-partner guardrails (added 2026-08-12)
The webapp is now two rooms with a shared script pane (see §2). `screenplay_cowriter/peer.py` adds structural guardrails so the co-writer behaves like a peer, not a lecturer:
- **Two-phase turn** — an idea shared without embedded reasoning triggers a reflect-and-probe reply (no suggestions); the flag is per-branch (`Branch.awaiting_probe`), abandoned when the writer changes topic, and never re-probes a writer mid-answer.
- **Forward momentum** — `ensure_forward_momentum` appends a forward nudge only to *short stranded* replies (never substantial answers), from a rotating template pool.
- **One idea at a time** — `cap_suggestions` structurally caps bulleted suggestions per turn.
- **Informed partner** — the `peer` mode locks in "never volunteer the report"; the Feedback→Co-write bridge *prefills the composer* (never auto-sends).
Tests: `tests/test_peer_guardrails.py` (27) + webapp room tests. Full suite: **328 passed**.

### 0b. Writer relationship memory (added 2026-08-12)
`screenplay_cowriter/memory.py` gives Sam a writer-level memory (across all projects) at `studio_projects/writer_profile.json`:
- **Rule signals → evidence** — each turn feeds cheap deterministic signals (tone statements, probe engagement, pushback, topic keywords) into per-dimension pos/neg evidence. A dimension affects behavior only past a **0.6 confidence gate with ≥ 3 signals** (nothing gates on one comment); it flips only when the opposite pole wins, and re-flips only with sustained evidence.
- **Refresh** — every 10 observed turns, a fire-and-forget daemon thread asks the model to propose profile updates from the recent transcript (lenient JSON parse, merge only on higher confidence / novel observations; `force=True` for the webapp's user-initiated refresh).
- **Injection** — `CoWriterEngine(memory=None)` observes each turn and injects the relationship card into `build_system_prompt(relationship_card=, cold_start_line=)` on both prompt paths. `memory=None` is byte-identical to before; only the webapp wires memory by default (cowriter CLI/server opt in via `--memory-path`).
- **Writer stays the editor** — "Sam's notes on you" modal (Co-write partner card): view observations, "forget this" (suppresses permanently), "refresh now". The card text forbids quoting memory at the writer ("you always say…" is forbidden).
Tests: `tests/test_writer_memory.py` (26) + webapp endpoints. Full suite: **358 passed**.

### 1. Named category sentinel (resolved)
`pipeline.py` now exports `ALL_CATEGORIES` and `resolve_categories()`: `None` and `("all",)` both expand to the full ten-category tuple; any other tuple is passed through unchanged. `analyze()` normalizes via `resolve_categories`, and per-category outcomes (`category_outcomes`, `"ok"`/`"failed"`) are recorded so partial analyses can be resumed.

### 2. Personas are server-driven (resolved)
`GET /api/config` now includes `personas` and `modes` from `screenplay_cowriter.personas`; `app.js` reads them and falls back to built-in defaults only when the server doesn't supply them. New personas appear in the UI automatically.

### 3. Graceful cowriter-missing handling (resolved)
`webapp_server.py` wraps all lazy `screenplay_cowriter` imports in `_import_cowriter()` (raising a clean `CowriterUnavailableError`), and chat endpoints return a 503 with an actionable message instead of leaking a traceback. The project shelf keeps working without the co-writer installed.

### 4. Conversation history persisted defensively (resolved)
`CoWriterEngine.send_message()` now accepts an optional `store` and saves the session itself after a successful turn; all four construction sites (webapp, orchestrator, cowriter CLI, cowriter server) pass it. Callers may still save explicitly — the double-write is idempotent.

### 5. Partial-category resume (new)
`run_analyze(retry_failed=True)` re-runs only the categories recorded as `failed` in the manifest's `category_outcomes`, merging their fresh findings into the existing report (`_merge_analysis`). CLI: `run`/`resume --retry-failed`. Retry semantics are hardened: `genre`/`logline_test` failures automatically re-run `coverage` too (their prerequisite — otherwise the fresh run's empty coverage gates them out and they'd be re-marked failed forever); a retry that itself fails (empty outcomes) fails loudly and **preserves the previous partial record** (`failed_categories` + report paths) instead of overwriting the report; and the retry path also resumes from `status="failed"` stages that carry a partial record.

### 6. Config holder (new)
Module-level `CONFIG` is a `ServerConfig` instance: validated writes (positive int timeout), and `to_dict()` returns a copy so responses can't mutate live config by reference.

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
