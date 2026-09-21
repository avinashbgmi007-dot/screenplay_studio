# State Stores — Screenplay Studio

> **Generated from source:** 2026-09-06. This is the consolidated "global vs local"
> state map the UI/UX strategy needs. The app is **file-based** — there is no
> database, no Redux/Zustand, no in-memory global store. Every persistent slice is a
> JSON file.
>
> **Atomicity — corrected 2026-09-20.** Writer-owned stores go through
> `jsonio.atomic_write_json` (tmp + `os.replace` + per-path lock). The earlier flat
> claim that *every* slice did was **false**, and it hid the highest-stakes stores:
> `working.json` / `parsed.json` / `edits.json` / `writer_profile.json` were raw
> writes until audit item A2, and `premise.json` + `metrics.json` until A3 in the
> same pass. Both are now closed. What is **deliberately still raw**:
> `knowledge_graph.save` (the KG is regenerable from the parsed document) and
> export output (new files, not rewritten state).
>
> **Reader side — added 2026-09-20.** Atomic writes only stop a torn file being
> *produced*; they say nothing about what a reader does with one. Every
> writer-owned store now reads through `jsonio.load_json_store`, which keeps two
> facts apart: **MISSING → the store's default**, **PRESENT-BUT-UNREADABLE →
> `StoreUnreadable`**. That distinction is what stops a damaged file presenting
> as "you never wrote anything", and — since every mutator loads before it saves —
> it is also what stops the next mundane action overwriting the one recoverable
> copy. A store that cannot be read answers the SPA with **503** (`{"unreadable":
> true, "store": ..., "error": ...}`) from the `StoreUnreadable` handler.
> `tests/test_store_fault_injection.py` enforces this per store (three injected
> faults + a "the write must not clobber the damaged bytes" check) and fails the
> build when a module writes a store without a fault entry. Deliberately
> fail-soft, with a reason: `progress.json` (transient telemetry) and
> `parsed.json` / `working.json` (regenerable; the unregenerable edit log is
> covered by A1).
>
> **Concurrency — added 2026-09-21.** A per-path lock used to be a
> `threading.RLock`, which cannot serialize two *processes* — and `AGENTS.md`
> documents the CLI and the webapp writing the same project directory as a
> supported configuration. `atomic_write_json` also wrote through a **fixed**
> `<store>.tmp` name that every process shared, so two writers interleaved their
> bytes into one buffer and the survivor was renamed into the store (reproduced
> across 4 processes: `edits.json` kept 150 of 508 applied edits, and
> `finding_marks.json` was left torn at rest). `jsonio.lock_for` now returns one
> object carrying both an in-process RLock and an OS byte-range lock
> (`msvcrt.locking` / `fcntl.flock`) on a `<store>.lock` sidecar, and the temp
> name is unique per write (`<store>.<pid>.<hex>.tmp`, fsynced before the
> rename). Stores that do a load-modify-write must hold `lock_for` across the
> **read** as well as the write — `notes`, `stash_store`, `metrics`, `ideas`,
> `revision` (marks / edit log / dismissals) and the cowriter's `SessionStore`
> all do. The sidecars are plumbing, not data: `*.json` globs skip them, the
> shelf scan requires a directory, and `/backup` excludes `.lock` / `.tmp`.
> **Never hold two `lock_for` locks at once** — that is the one way to deadlock
> them. `tests/test_store_concurrency.py` proves all of this with real child
> processes.
>
> Companion docs: `docs/API_ROUTE_MAP.md` (which endpoints touch which store),
> `docs/DATA_FORMATS.md` (full JSON schemas), `CONTEXT.md` (entity glossary).

## Scope model

Every store has one of three scopes (from `docs/DATA_FORMATS.md`):

- **`global`** — writer-level, shared across all projects/ideas (e.g. Writer Memory, Writer Library).
- **`project:<id>`** — per-project, lives beside that project's `project.json` manifest.
- **`idea:<id>`** — per-idea, lives under `studio_projects/ideas/<id>/`.

Project stores live in `<PROJECTS_DIR>/<name>/` (the project directory created on
upload/sample/graduation). Idea stores live in `<PROJECTS_DIR>/ideas/<idea_id>/`.

---

## Store inventory

| # | Slice (what it holds) | Module | On-disk path | Scope | Read/Write endpoints |
|---|------------------------|--------|--------------|-------|----------------------|
| 1 | **Manifest** — stage statuses, drafts, active draft, report language, failed categories | `screenplay_studio/manifest.py` (`ProjectManifest`) | `<name>/project.json` | project | `get_project`, `analyze*`, `reparse`, `drafts/activate` |
| 2 | **Chat Session** — messages, branches, `current_branch`, `last_seen_content`, created/updated ts | `screenplay_cowriter/store.py` (`SessionStore`) | `<name>/sessions/<sid>.json` (and `ideas/<id>/sessions/`) | project / idea | all `/chat/sessions/*` and `/ideas/.../chat/sessions/*` |
| 3 | **Idea** — `{id,title,card,content,auto_title}` + premise card | `screenplay_cowriter/ideas.py` (`IdeaStore`) | `ideas/<id>/idea.json`, `ideas/<id>/sessions/<sid>.json` | idea | all `/api/ideas*` |
| 4 | **Stash** — saved snippets `[{id,text,title,scene_number,created_at}]` | `screenplay_studio/stash_store.py` | `<name>/stash.json` | project | `/stash`, `/stash/<id>` |
| 5 | **Margin Notes** — `[{id,scene_number,text,anchor,created_at,updated_at}]` | `screenplay_studio/notes.py` | `<name>/notes.json` | project | `/notes`, `/notes/<id>` |
| 6 | **Beat Board** — `{"order":[scene numbers],"saved_at":ts}` | `screenplay_studio/beatboard.py` | `<name>/beatboard.json` | project | `/beatboard*` |
| 7 | **Metrics** — `{analysis_seconds,last_analysis_ts,reply_seconds,discussed,findings_open,findings_total}` | `screenplay_studio/metrics.py` | `<name>/metrics.json` | project | `/metrics` |
| 8 | **Working Copy** — full `ScriptDocument` (editable; source untouched until export) | `screenplay_studio/revision.py` | `<name>/working.json` | project | `/script`, `/rewrite`, `/edits/apply`, `/edits/undo|redo|reset`, `/export` |
| 9 | **Edit Log** — undo/redo records `[{id,scene_number,applied[],skipped[],applied_at}]` | `screenplay_studio/revision.py` | `<name>/edits.json`, `<name>/edits.redo.json` | project | `/edits`, `/edits/apply|undo|redo|reset` |
| 10 | **Dismissed Findings** — triage `[{index,issue}]` (fix queue is computed, not stored) | `webapp_server.py` | `<name>/dismissed_findings.json` | project | `/findings/<i>/dismiss`, `/undismiss`, `/fixqueue` |
| 11 | **Premise Card** — `{title,logline,premise,questions,content}` (carried on graduation) | `webapp_server.py` + `ideas.py` | `<name>/premise.json` | project | `/premise`, `/ideas/<id>/card`, `graduate` |
| 12 | **Writer Memory** — 8 confidence-gated dimensions + scoped observations + relationship card | `screenplay_cowriter/memory.py` (`WriterMemory`) | `<PROJECTS_DIR>/writer_profile.json` | global (per-entity scope) | `/writer-memory*` |
| 13 | **Writer Library** — deterministic digest of every parsed project (`{characters,themes,scenes}`), injected as PAST WORK | `screenplay_cowriter/writer_library.py` (`build_library`) | computed at request (no persisted file) | global | `/writer-library` |
| 14 | **Knowledge Graph** — character index, recurring props, timeline, promises, co-occurrence (candidate generator) | `screenplay_parser` (KG builder) | `<name>/parsed.kg.json` | project | generated on parse; read by `/characters`, character tracks |
| 15 | **Report** — findings, pacing, character_dials, setup_payoff ledger, character_reads, coverage | `screenplay_analyzer` (pipeline) | `<name>/report.findings.json` (+ coverage) | project | `/report`, `/report/export`, `/characters`, `/fixqueue` |
| 16 | **Drafts** — named snapshot of source + parsed + report | `screenplay_studio/diff.py` | `<name>/drafts/<draft_name>/` | project | `/drafts*`, `/drafts/activate`, `/diff`, `/compare` |

---

## Notes for the UX strategy

- **The "global state" is tiny by design.** Only two slices are truly cross-project:
  Writer Memory (#12) and Writer Library (#13). Everything else is scoped to a single
  Project or Idea. There is no app-wide store to "lift state into."
- **Transient UI state is client-side only.** The SPA (`webapp/app.js`) keeps
  view/room/selection in memory + `localStorage` (`screenplay_studio.session.v1`,
  `screenplay_studio.sprint.v1`); it never round-trips to a server store except via the
  endpoints above. Plan the Inspector / List views against the JSON shapes in
  `docs/DATA_FORMATS.md`, not against any client store.
- **Computed, not stored:** the Fix Queue (#10 joined at request), Character Track
  (#14 + #15 assembled at serve time), and Writer Library (#13) are derived on demand.
  Don't design a panel that expects them as persisted files.
- **Scope mismatches to watch:** an Idea (#3) has no analysis/report/KG until it
  **graduates** (#11, #1) into a Project. The chat UX must branch on entity type
  (project vs idea) — see the mirrored `/chat/sessions/*` vs `/ideas/.../chat/sessions/*`
  routes in `docs/API_ROUTE_MAP.md`.
