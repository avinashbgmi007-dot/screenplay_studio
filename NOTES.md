# NOTES.md — Handoff Log

Work-in-progress log for the current session. Update as you go; keep entries short and dated.

## Completed

- **2026-08-12 — Two-room webapp + writing-partner guardrails.** Spec + plan in `docs/superpowers/specs/` + `docs/superpowers/plans/`. The webapp is now two rooms with a shared script pane: **Co-write** (the writer's desk — one consistent partner "Sam", warm amber identity) and **Feedback** (the consultant's desk — Report + Fix Queue tabs, cool slate identity), switchable via the top-bar room toggle; Beat Board/Compare moved to script-pane toolbar icons. New `screenplay_cowriter/peer.py` with pure guardrails: two-phase turn (probes unreasoned ideas, abandons on topic change), forward-momentum nudge (light-touch: only short stranded replies, never factual answers), one-idea-at-a-time cap. `writing_partner` persona + `peer` mode are the new defaults; `Branch.awaiting_probe` flag (per-branch, fork-safe); personas are now conversational lenses (no dropdowns). Full suite: **328 passed**. Code review caught + fixed: blank Feedback pane (both panes started hidden — `switchFeedbackTab("report")` now called), dead scene-restore guard (`state.view === "script"` → room values).

- **2026-08-12 — Bug-fix batch (all 6 items) + retry hardening.** Fixed: named `ALL_CATEGORIES` sentinel + per-category `category_outcomes`; partial-category resume via `run_analyze(retry_failed=True)` / CLI `--retry-failed` (merges into existing report); server-driven personas in `/api/config` + `app.js` fallback; graceful `_import_cowriter()`/`CowriterUnavailableError` (503) in webapp; defensive session save inside `CoWriterEngine.send_message` (all 4 call sites pass `store`); `ServerConfig` validated holder replacing bare dict. Added `tests/test_fix_batch.py` (17 tests). Full suite: **298 passed**. Updated ARCHITECTURE.md ("Known Issues" → "Resolved Issues") and DEVELOPMENT.md.
  - Retry hardening (from code review): (a) `genre`/`logline_test` that fail independently of coverage now auto-add `coverage` to the retry set — otherwise the fresh run's empty coverage gates them out and step-7 re-marks them failed forever; (b) a retry that itself fails (empty `category_outcomes`) now fails loudly and preserves the previous partial record (`failed_categories` + report paths) via `prev_outputs` restore, instead of merging an empty run and overwriting the report; (c) retry path also resumes from `status="failed"` stages that carry a partial record.

- **2026-08-12 — Docs overhaul.**
  - Fixed stale references in `docs/ARCHITECTURE.md`: pyproject → requirements.txt, webapp/ moved under `screenplay_studio/`, knowledge_base/ moved to repo root, corrected dependency list, endpoint table (40+ routes), ElementType model, 11-pass pipeline, known-issue line numbers.
  - Deleted stale artifacts: `docs/source/` (31 auto-generated per-file docs from an old graph-analysis run, wrong signatures, no regenerator), plus root `god_nodes.md`, `suggested_questions.md`, `surprising_connections.md`.
  - Created: `docs/CLI_REFERENCE.md`, `docs/DATA_FORMATS.md`, `docs/DEVELOPMENT.md`, `docs/TESTING.md`, `docs/CODEBASE_MAP.md` (symbol-level index).
  - Updated `AGENTS.md` (fixed pipeline/test-count claims, added efficient-read-order workflow, docs index) and `docs/ARCHITECTURE.md` (tree now lists all docs) as session-entry points.

## Decisions

- `docs/source/` is **not** coming back — per-file auto-generated docs went stale and were removed by user approval; the curated `docs/` set (ARCHITECTURE, CLI, DATA_FORMATS, DEVELOPMENT, TESTING, CODEBASE_MAP) replaces it.
- `requirements.txt` is the source of truth for dependencies (there is no `pyproject.toml`).
- `docs/CODEBASE_MAP.md` is the designated answer to "where is X" — keep it updated when public APIs change.

## Current State

- Test suite: **328 tests passed** (298 + 27 peer/engine guardrail tests + 3 webapp room tests), runs against in-process mock llama-server (port 8196) — no real model needed.
- All 6 known code issues fixed (previous batch) + **new rooms feature**: two-room webapp (Co-write/Feedback), shared script pane, writing-partner guardrails (two-phase probe, dead-end nudge, one-idea cap), `writing_partner`/`peer` defaults, conversational persona lenses, prefill-only "→ discuss with my partner" bridge, room theming via `body[data-room]`.
- Git: repo now has commits (spec, plan, backend batch, webapp batch). Remaining untracked: the pre-existing project files (sample data, `.freebuff/`, `studio_projects/`, PDFs) — recommend one initial commit of the baseline so future sessions can use `git diff`.
- Remaining non-code items: OCR best-effort limitation (by design), no per-category webapp UI for `--retry-failed` (CLI-only so far).
- Deferred (v2): relationship memory (writer-profile / tone calibration) — the design leaves room for it on top of the guardrails.

## Open Questions

- Should `--retry-failed` be exposed in the web UI as a "Retry failed categories" action (currently CLI-only)?
- Do we want a GitHub-style CHANGELOG.md, or is git history enough?

## Next Steps

- Initial `git commit` of the whole tree (so future sessions can read only changed files via `git diff`).
- Optionally surface `--retry-failed` in the web UI ("Retry failed categories" button on partial-failure projects).
- Optionally: add a smoke-test for the docs (link checker) and set up the graphify knowledge graph as a committed query artifact.
