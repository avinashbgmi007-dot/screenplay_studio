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
│   ├── llm_client_base.py      # Shared base client + LlamaServerError/ModelNotFoundError
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
│   ├── personas.py             # 8 personas, 5 modes (default: writing_partner/peer)
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
│   │                           #   + GO 1/2: compute_finding_id (content-hash finding identity),
│   │                           #   finding_intents/set_finding_intent (finding_marks.json),
│   │                           #   last_pass_snapshot (last_pass.json diff)
│   ├── diff.py                 # Draft snapshots + cross-draft diffing
│   ├── beatboard.py            # Scene reordering / beat board
│   ├── notes.py                # Per-project notes store
│   ├── stash_store.py          # The Stash: per-project saved snippets (stash.json)
│   ├── character_track.py      # Per-character track layer (presence/traits/interactions/reads)
│   ├── watch.py                # Watch-folder auto-analysis
│   ├── sample.py               # Sample-script generator
│   ├── ideas.py                # Idea store (idea rooms, graduation, premise cards)
│   ├── stt.py                  # Local dictation (faster-whisper, optional)
│   ├── metrics.py              # Desk metrics store (reply timings, fix counts)
│   ├── jsonio.py               # atomic_write_json / lock_for / retry_permission (WinError-32 retry)
│   ├── demo_model.py           # Built-in demo craft model (fallback when no llama-server)
│   ├── webapp_server.py        # Flask backend (port 8500) + POST /findings/intent route
│   └── webapp/                 # Static frontend (no build step)
│       ├── index.html          # Single-page app shell (~770 lines)
│       ├── app.js              # Client-side JS (~8,530 lines; GO 1/2 evidence surfaces)
│       ├── core.js             # DOM-free pure helpers (unit-tested via node --test)
│       ├── style.css           # Base design system (~6,520 lines; Nocta token fallback)
│       ├── tungsten.css        # Frozen visual system override (night + dawn registers)
│       ├── fonts/               # Self-hosted .woff2 (Instrument Serif + DM Sans)
│       ├── preview-redesigns/  # Six visual-direction prototypes (+ screenshots)
│       ├── preview-next/       # Seven interaction-model prototypes (Design Lab)
│       └── preview-r4/         # Visual-direction mockups + probes (untracked design material)
├── knowledge_base/             # 263 attributed screenwriting-craft rules (26 rule files)
│   ├── knowledge_base.py       # KnowledgeBase, Rule dataclass
│   ├── rules/                  # Per-category rule JSON
│   └── schema.json
├── tests/                      # pytest suite (mock llama-server)
├── requirements.txt            # declared runtime deps (floors: requests, flask, pdfplumber)
├── requirements.lock.txt       # exact pins for the whole closure (CI installs with `-c`)
├── pyproject.toml              # build + package config, extras (dev/stt/ci), package-data
├── LICENSE                     # proprietary, all rights reserved (private project)
├── CHANGELOG.md                # notable changes
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
- **"Nocta Craft Precision."** Near-black ink palette with a violet Co-write lamp (`--lamp
  #7e6bff`) and cyan Feedback lamp (`--consult #53c7f0`), swapped by `body[data-room]`.
  The manuscript stays bright cream paper. Dawn (light, daylight-glass) theme via
  `body.dawn`. (Superseded the earlier amber/slate "warm room" theme.)
- **Two rooms, one script.** The workspace is a shared script pane (always visible) plus a
  right-hand **room drawer** summoned from the edge gutter tabs: **Co-write** (the writer's
  desk — Sameer) and **Feedback** (the consultant's desk — Dr. Sushruta's Report + Fix Queue
  tabs). For projects, the Feedback room toggle, the `f` shortcut and the Consultant gutter
  tab all open the **Context Dock** on its **Evidence lens** instead (arrival strip ·
  script mass strip · per-scene deep cards · severity filter · dawn meter); the drawer
  panel remains for idea-less contexts. The old full-screen **Feedback View**
  (`#feedback-view`, `state.view="fv"`) and the docked **Problem Board**
  (`#problem-board`) are the two surfaces that route there — the first is still in the DOM
  but unreachable, the second is gone (markup, CSS, palette command and scroll-sync).
  `body[data-room]` drives the room theming. Beat Board, Compare, and Revision are
  full-screen tools opened from the script-pane toolbar (keys `b`/`d`/`v`).
- **Three-zone shell.** The left structural rail (`#struct-rail`) is **retired** — it
  shipped `display:none` since Phase 13 and was removed with its markup, renderers,
  `r` shortcut, edge tab and CSS in the redesign's ring-fenced batch (spec §11). Its
  content lives in the Context Dock's **Stash & Notes** lens (Stash, margin notes
  newest-first, pinned to scenes or lines) and the **scene index** (click → jump);
  the character track layer's dials reach the page through the craft shelf and the
  Evidence lens. The script pane never shrinks below 50%. A thin
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
  (or focus it with `s` + arrows and press `Enter`)
  in place (rides the edits/apply path — undoable, change-starred).

### Client-Side JavaScript (`screenplay_studio/webapp/app.js` + `core.js`)
- `app.js` is ~8,530 lines of vanilla JS handling all client logic; `core.js` holds the
  DOM-free pure helpers (`fuzzyScore`, `formatMessageContent`, `truncate`, `formatElapsed`,
  `fmtDuration`, `shortModelId`) — unit-tested in `node --test tests/js/`.
- **GO 1/2 evidence surfaces** — `computeFindingId` (id twin of `revision.py`), the one
  counting contract `findingDisposition`/`findingOpen`/`findingStatusOf` (every surface
  reads it), the fold `openFeedbackView` (routes Feedback entry points to the workspace +
  dock Evidence lens; the `#feedback-view` clone is dormant/unreachable), ONE filter state
  (`state.findingFilter`) driving ink/board/loop/counts together, ink marks
  (`inkAnchorsFor`/`decorateLineWithInk`), the contextual keyboard fix loop
  (`startLoop`/`stepLoop`/`exitLoop`/`renderLoopBar`; n/p/esc when active, scene-stepping
  on exit), intent buttons (`setFindingIntent`), and the arrival strip (`buildArrivalStrip`:
  scoped pass line + a working-copy draft clause + trust + inline retry + ghosted marks).
  Full spec: `docs/PHASE_B_FV_FOLD_SPEC.md` + `docs/UI_UX_SPECIFICATION.md` §4.9.
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

### CSS (`screenplay_studio/webapp/style.css` + `tungsten.css`)
- ~6,520 lines of base CSS (design system + the NOCTA v4 layer: auto-hide chrome,
  cursor spotlight, level badge, Sameer slide-in mock panel) carrying the token fallback.
- `tungsten.css` is the **frozen visual system override** (loads after style.css; night +
  dawn registers): volumetric gold key, lit-from-top vellum, severity never color-alone,
  Sameer violet + Sushruta cyan re-pinned, reduced-motion collapses to instant. Both
  registers theme automatically from the token ladder — new components ride existing
  token classes.
- Full design-token system via CSS variables: void ink ramp, glass surfaces, paper,
  violet/cyan room accents, type scale (`--font-typewriter/script/serif/display/ui/mono/hand`),
  radius, motion curves.
- Room theming via `body[data-room]`; Dawn theme via `body.dawn`; river-read dark-glass
  block; focus/spotlight/reader mode overrides; print styles for the draft and beat cards.
- `prefers-reduced-motion` kill-switch, `:focus-visible` rings, accent `::selection`.

### HTML (`screenplay_studio/webapp/index.html`)
- ~770 lines. SPA shell: collapsible sidebar (brand · new-page · Ideas/shelf/library
  flyouts · Dawn/Settings footer), welcome scene + dashboard, project bar, workspace
  (desk · context dock · gutter · room drawer), status strip, Beat
  Board / Compare / Revision / Feedback-View full-screen views (the Feedback View is
  dormant — the fold routes its entry points to the workspace dock, §app.js GO 1/2),
  premise pane + idea canvas, NOCTA chrome (Sameer panel mock, level badge, cursor
  spotlight), five modals (Settings, Rewrite, Palette, Fork, Sam's notes). References
  cache-busted `style.css`/`core.js`/`app.js`/`tungsten.css` (`?v=<hash>`).

---

## 3. Backend Control Engine

### Server Endpoints (Flask, port 8500)
`webapp_server.py` exposes the JSON API (projects keyed by `<name>`). **The complete
enumerated route map (all 84 endpoints) is `docs/API_ROUTE_MAP.md`** — regenerate it
after changing any `@app.route`. **The authoritative request/response shapes, error
codes, and the SSE stream contract are in `docs/UI_UX_SPECIFICATION.md` §9.** The
state each endpoint reads/writes is cataloged in `docs/STATE_STORES.md`. Quick index:

| Area | Endpoint | Methods |
|------|----------|---------|
| Config/conn | `/api/config`, `/api/test-connection`, `/api/health`, `/api/real-server-check` | GET/POST |
| Projects | `/api/projects`, `/api/projects/<name>`, `/api/sample`, `/api/projects/<name>/backup`, `/api/projects/<name>/reparse` | GET/POST/DELETE |
| Analysis | `/api/projects/<name>/analyze`, `/analyze/retry-failed`, `/progress`, `/report`, `/report/export`, `/fixqueue`, `/findings/<index>/dismiss`, `/findings/<index>/undismiss`, `/passes` (the revision arc, spec 15.4), `/quickcheck` (deterministic lint of the working draft, answered without the model and labelled provisional, spec 15.3), `/characters` | GET/POST |
| Manuscript | `/script`, `/rewrite`, `/edits`, `/edits/apply`, `/edits/undo`, `/edits/redo`, `/edits/reset`, `/export`, `/metrics` | GET/POST |
| Notes/Stash | `/notes`, `/notes/<id>`, `/stash`, `/stash/<id>`, `/premise` | GET/POST/PATCH/DELETE |
| Beat board/Drafts | `/beatboard`, `/beatboard/reset`, `/beatboard/export`, `/drafts`, `/drafts/activate`, `/diff`, `/compare` | GET/POST/PUT |
| Chat (project) | `/chat/start`, `/chat/sessions/<sid>`, `/chat/sessions/<sid>/messages`, `/messages/stream` (SSE), `/fork`, `/switch`, `/settings`, `/translate` | GET/POST/DELETE |
| Ideas | `/ideas`, `/ideas/<id>`, `/ideas/<id>/content`, `/rename`, `/card`, `/graduate`, `/chat/start`, `/chat/sessions/<sid>` (+ messages/stream/settings/translate) | GET/POST/DELETE |
| Writer memory | `/writer-memory`, `/writer-memory/observations/<id>/suppress`, `/writer-memory/refresh`, `/writer-library` | GET/POST |
| Dictation | `/stt`, `/stt/languages` | GET/POST |
| Design Lab | `/preview/projects`, `/preview/data/<name>`, `/preview/chat/<name>` | GET/POST/DELETE |

#### Where the model lives: local, or remote with a token

Two setups, one Settings form. `connection_mode(url)` **derives** `"local"` (a llama-server on this
machine) or `"remote"` (any OpenAI-compatible endpoint) from the URL rather than storing it, so the
mode cannot drift from the thing it describes; `GET /api/config` reports it alongside
`api_key_set` and `allow_remote`. The same config keys serve both — `server_url`, `model`,
`fast_model`, `timeout` — with `api_key` simply empty in the local case.

- **Auth.** `auth_headers(api_key)` (`screenplay_analyzer/llm_client_base.py`) is the ONE
  construction of the credential and is threaded through the clients' `extra_headers` on every
  request (`/v1/models`, `/props`, `/v1/chat/completions`). It lives in the shared client base
  because both pieces already depend on that module — no new cross-package edge, no second copy.
- **The token never leaves the server.** `GET /api/config` reports `api_key_set`, never the value.
- **Remote is a launch-time decision, not a permission.** `_validate_server_url` stays
  loopback-only unless the operator passed `--allow-remote-server` / set
  `SCREENPLAY_STUDIO_ALLOW_REMOTE_SERVER=1`. `POST /api/config {"connection_mode": "remote"}` is
  **refused** while that is off, because a request that could grant the opt-in would be the same
  request that names the remote host — and the guard would be decorative.
- **Projects carry the connection** (`server_url`, `api_key`) via `_adopt_connection(m)`, so
  `resume` and the CLI reach the same endpoint without re-typing anything.
- **Every failure answers as JSON.** `_error(msg, status)` returns `{"error": …}` and is what each
  route's own failure path uses, because the SPA reads `error` off the body. `@app.errorhandler(Exception)`
  (`_unhandled`) is the floor beneath them: an unhandled error anywhere also answers as JSON rather than
  Flask's HTML 500, with `HTTPException` passed through untouched so 404/405/413 keep their codes and
  their own handlers. Measured: an `OSError` from an unguarded `os.remove` reached the client as an HTML
  page and the front-end told the writer nothing (`tests/test_destructive_paths.py`).
- **A raise from a `finally` is a different hazard.** Splitting destructive calls by blast radius (can
  this leave a PARTIAL result?) is right for judging state and wrong for judging reporting. Where a
  cleanup sits in a `finally`, a raise **replaces the in-flight exception** — measured in `upload_draft`,
  where a refused temp-file removal discarded a clear `"Could not connect to llama-server."` and the
  writer saw a generic 500. The operation fails loudly with a JSON error naming what failed; housekeeping
  is non-fatal and reports the refusal.

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
- **The orchestrator runs synchronously** (no threads); the webapp server itself runs
  `threaded=True` and the writer-memory refresh is a fire-and-forget daemon thread —
  "no threading" applies to the pieces' core design, not the Flask host.
- **No database** — sessions stored as individual JSON files in a directory.
- **Model discovery** — `discovery.py` resolves which model to use by checking what the llama-server reports loaded, falling back through explicit flag → inherited model from report → first available.

### Analysis Pipeline (`pipeline.py:analyze()`)

The pipeline runs **12 model categories** (`ALL_CATEGORIES`: dialogue, theme, character,
structure, scene_function, principles, setup_payoff, char_reads, character_dials, coverage,
genre, logline_test) plus deterministic passes. Actual order in `analyze()`:

1. **Formatting checks & stats** — deterministic, no model: missing INT/EXT, time-of-day, character capitalization, heavy parentheticals, long action blocks; character counts, dialogue ratios.
2. **Craft passes (deterministic)** — voice-bleed, on-the-nose subtext, and **idiolect** (characters speaking with one voice) — no model calls.
3. **Continuity pass** — deterministic: time flips, name variants (no model call).
4. **Pacing** — deterministic per-scene pace index (density × inverted action-share), drags flagged over a threshold, capped at 4. Also emits pace-drag findings (`check_id: pacing_drag` — a mechanical measure, so no `rule_id`: that field is reserved for ids that resolve in the knowledge base). No model call.
5. **Scene summaries** — LLM-generated per-scene summaries (chunked, token-budgeted).
6. **Dialogue analysis** — per-scene dialogue findings with verbatim quotes (chunked).
7. **Script-level categories** — theme, character, structure, scene-function (one model call each, over the scene-summary overview).
8. **Principles engine** — Two-stage Chekhov's Gun (knowledge-graph candidate generation + model significance judgment).
9. **Character-perception reads** — how each character comes across vs. apparent intent.
10. **Setup/payoff ledger** — the end-of-pipeline whole-script audit: one grammar-constrained call over the full scene overview + mechanically-flagged candidates, returns a ledger {setup, kind, setup_scenes, payoff_scenes, status: paid|dangling|abandoned|red_herring, note}; dangling/abandoned fold into plot_thread findings (deduped vs. the principles engine).
11. **Character dials** — one model call scoring the main cast (≤8, by scene+dialogue share) on 1-10 trait poles with scene_refs.
12. **Verification** — fuzzy matching (SequenceMatcher, threshold 0.72) and sliding-window comparison; flags unverified findings.
13. **Coverage** — logline / genre / synopsis / recommendation.
14. **Logline test & genre check** — premise lands in one sentence; genre conventions (uses coverage output).
15. **Feedback filter** — drops non-writing meta-commentary (dialect/subtitle noise) from the final set.

(Progress emits 20 stage keys; the webapp's `ANALYSIS_STAGES` map matches them.)

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
- **pyproject.toml** — the build's source of truth (setuptools; `dev` / `stt` / `ci` extras; `[tool.setuptools.package-data]` for the craft rules and the SPA).
- **requirements.txt** — the declared runtime list, by floor (`requests>=2.31.0`, …). It and `pyproject.toml` agree; neither is authoritative over the other.
- **requirements.lock.txt** — exact pins for the entire declared dependency closure, derived rather than hand-written. Applied as a **constraints** file (`pip install ".[ci]" -c requirements.lock.txt`), never as a second requirements list: `pyproject.toml` decides *which* packages exist, the lock decides *which versions*. Without it the `>=` floors let CI and a developer resolve different versions of the same dependency and disagree about a green build. `tests/test_production_readiness.py` enforces that every line is an exact pin, every declared dependency is pinned or on a documented exception list, no pin is older than the floor it must satisfy, and CI actually applies it.
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
│  │  • .fdx/.pdf/   │    │  • GBNF grammar │    │  • 8 personas│ │
│  │    .txt/.fountain│   │  • 12 categories│    │  • 5 modes  │ │
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
Tests: `tests/test_peer_guardrails.py` (27) + webapp room tests. (Suite snapshot at the time; the suite has since grown past 670 tests.)

### 0b. Writer relationship memory (added 2026-08-12)
`screenplay_cowriter/memory.py` gives Sam a writer-level memory (across all projects) at `studio_projects/writer_profile.json`:
- **Rule signals → evidence** — each turn feeds cheap deterministic signals (tone statements, probe engagement, pushback, topic keywords) into per-dimension pos/neg evidence. A dimension affects behavior only past a **0.6 confidence gate with ≥ 3 signals** (nothing gates on one comment); it flips only when the opposite pole wins, and re-flips only with sustained evidence.
- **Refresh** — every 10 observed turns, a fire-and-forget daemon thread asks the model to propose profile updates from the recent transcript (lenient JSON parse, merge only on higher confidence / novel observations; `force=True` for the webapp's user-initiated refresh).
- **Injection** — `CoWriterEngine(memory=None)` observes each turn and injects the relationship card into `build_system_prompt(relationship_card=, cold_start_line=)` on both prompt paths. `memory=None` is byte-identical to before; only the webapp wires memory by default (cowriter CLI/server opt in via `--memory-path`).
- **Writer stays the editor** — "Sam's notes on you" modal (Co-write partner card): view observations, "forget this" (suppresses permanently), "refresh now". The card text forbids quoting memory at the writer ("you always say…" is forbidden).
Tests: `tests/test_writer_memory.py` (26) + webapp endpoints. (Suite snapshot at the time; the suite has since grown past 670 tests.)

### 1. Named category sentinel (resolved)
`pipeline.py` now exports `ALL_CATEGORIES` and `resolve_categories()`: `None` and `("all",)` both expand to the full twelve-category tuple; any other tuple is passed through unchanged. `analyze()` normalizes via `resolve_categories`, and per-category outcomes (`category_outcomes`, `"ok"`/`"failed"`) are recorded so partial analyses can be resumed.

### 2. Personas are server-driven (resolved)
`GET /api/config` now includes `personas` and `modes` from `screenplay_cowriter.personas`; `app.js` reads them and falls back to built-in defaults only when the server doesn't supply them. New personas appear in the UI automatically.

### 3. Graceful cowriter-missing handling (resolved)
`webapp_server.py` wraps all lazy `screenplay_cowriter` imports in `_import_cowriter()` (raising a clean `CowriterUnavailableError`), and chat endpoints return a 503 with an actionable message instead of leaking a traceback. The project shelf keeps working without the co-writer installed.

### 4. Conversation history persisted defensively (resolved)
`CoWriterEngine.send_message()` now accepts an optional `store` and saves the session itself after a successful turn; all four construction sites (webapp, orchestrator, cowriter CLI, cowriter server) pass it. Callers may still save explicitly — the double-write is idempotent.

### 5. Partial-category resume (new)
`run_analyze(retry_failed=True)` re-runs only the categories recorded as `failed` in the manifest's `category_outcomes`, merging their fresh findings into the existing report (`AnalysisResult.merge`). CLI: `run`/`resume --retry-failed`. Retry semantics are hardened: `genre`/`logline_test` failures automatically re-run `coverage` too (their prerequisite — otherwise the fresh run's empty coverage gates them out and they'd be re-marked failed forever); a retry that itself fails (empty outcomes) fails loudly and **preserves the previous partial record** (`failed_categories` + report paths) instead of overwriting the report; and the retry path also resumes from `status="failed"` stages that carry a partial record.

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
- **Graceful fallbacks** — `_NullRulesContext` (defined in `pipeline.py`) when KB not installed.
- **Safe project naming** — suffix auto-increment for duplicates.
- **Proper error handling** — specific HTTP status codes (400, 404, 500, 502).

### Design Philosophy
- **Boring is good** — No database, no threading, no framework. Deliberately simple.
- **Candidate generation ≠ judgment** — The knowledge graph is explicitly a candidate generator, not a judgment engine.
- **Model-agnostic by design** — Any llama.cpp-compatible model works.

---

*Document generated by Principal Software Systems Architect analysis.*
