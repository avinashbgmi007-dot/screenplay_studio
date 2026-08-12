# NOTES.md — Handoff Log

Work-in-progress log for the current session. Update as you go; keep entries short and dated.

## Completed

- **2026-08-12 — Live E2E verification (real local model) + forget-belief fix.** Ran the webapp against the real llama.cpp server (Qwen3.6-35B on :8080) and drove the full flow via HTTP: 6 chat turns grew `studio_projects/writer_profile.json` from zero (3 dims gated with auto-created observations; probe appetite correctly stayed ungated at 2 evidence), refresh-now merged a real LLM proposal (0.62→0.9, higher-confidence rule), forget/re-forget/unknown/400 error paths all behaved. Verification found one real gap: **"forget this" didn't fully forget** — the card's dimension phrases came from `dimension_gate()` (dimension state), so Sam kept acting on a forgotten belief. Fix: `_current_belief_rejected()` in `memory.py` — a dimension whose current-value template observation is suppressed drops out of the gate (keyed to the LATEST matching observation so contradiction auto-suppression of an old pole doesn't silence a re-gated belief, and re-learning restores it); card bullets are now filtered to the active gate too (a refresh note can't leak a rejected belief back in); `WriterMemory.gated_dimensions()`; webapp GET `/api/writer-memory` returns `gated` (single source of truth) and the panel chips render from it. +5 tests (suppressed-belief drops phrase+gate, contradiction keeps new pole, re-learning restores, refresh-note leak, wrapper gate). Full suite: **362 passed**.
  - Honest caveat from live run: the LLM refresh can misread (it attributed Sam's own "I can't answer" replies to the writer) — exactly the documented tier-2 risk; the panel's visible + forgettable design is the mitigation and it worked.
  - E2E scratch drivers kept at repo root: `_e2e_memory.py` (send chat turns + dump memory), `_e2e_panel.py` (refresh/suppress/error paths), log `_webapp_e2e.log`.

- **2026-08-12 — Writer relationship memory (v2).** Spec + plan in `docs/superpowers/specs/` + `docs/superpowers/plans/` (`2026-08-12-writer-relationship-memory-*`). New `screenplay_cowriter/memory.py`: per-turn rule micro-signals → pos/neg evidence with a 0.6 confidence gate + MIN_EVIDENCE=3 (nothing gates on one comment; flips only when the opposite pole wins), human-readable observations auto-created the moment a dimension gates, explicit-tone contradictions auto-suppress at 2+, relationship card + cold-start line, every-10-turns LLM refresh (fire-and-forget daemon thread, module-level file lock, lenient JSON parse, strict merge rules: only higher-confidence wins, novel observations only). `CoWriterEngine(memory=None)` + `build_system_prompt(relationship_card=, cold_start_line=)` — byte-identical when absent. Writer-level store at `studio_projects/writer_profile.json` (webapp wires by default; cowriter CLI/server get `--memory-path`, default off). Webapp endpoints: `GET /api/writer-memory`, `POST /api/writer-memory/observations/<id>/suppress`, `POST /api/writer-memory/refresh`. Frontend: "Sam's notes on you" modal in the partner card (reuses `openModal`/`closeModal` + `modal-label`; forget + refresh-now with loading state). Plan super-critique found 4 issues before execution (cold-start-after-observe bug, suppress idempotency, modal helpers, nonexistent CSS class) + review hardening fixed 3 more (refresh double-check under lock, broad exception swallow, pushback regex false positive). Full suite: **358 passed** (+26 memory +4 webapp).

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

## Working Agreements

- **Super-critique gate (user-mandated, standing):** after the planning is finalized (spec written → self-review → user review → implementation plan written), do a **super-critique** of the plan BEFORE executing — be a genuine critic, verify every assumption against the real code (helpers, field names, wiring, tautologies), fix real issues, commit the fixes, and only then proceed. This caught 6 real bugs in the rooms plan (`a751c85`). Same gate applies to the spec before user review.

## Current State

- Test suite: **358 tests passed** (328 + 26 writer-memory tests + 4 webapp memory endpoints), runs against in-process mock llama-server (port 8196) — no real model needed.
- All 6 known code issues fixed (previous batch) + **new rooms feature**: two-room webapp (Co-write/Feedback), shared script pane, writing-partner guardrails (two-phase probe, dead-end nudge, one-idea cap), `writing_partner`/`peer` defaults, conversational persona lenses, prefill-only "→ discuss with my partner" bridge, room theming via `body[data-room]`.
- **Writer relationship memory (v2) shipped**: `screenplay_cowriter/memory.py`, writer-level `studio_projects/writer_profile.json`, confidence-gated tone calibration, 10-turn LLM refresh, "Sam's notes on you" modal.
- Git: repo now has commits (spec, plan, backend batch, webapp batch). Remaining untracked: the pre-existing project files (sample data, `.freebuff/`, `studio_projects/`, PDFs) — recommend one initial commit of the baseline so future sessions can use `git diff`.
- Remaining non-code items: OCR best-effort limitation (by design), no per-category webapp UI for `--retry-failed` (CLI-only so far).

## Open Questions

- Should `--retry-failed` be exposed in the web UI as a "Retry failed categories" action (currently CLI-only)?
- Do we want a GitHub-style CHANGELOG.md, or is git history enough?

## Next Steps

- Initial `git commit` of the whole tree (so future sessions can read only changed files via `git diff`).
- Optionally surface `--retry-failed` in the web UI ("Retry failed categories" button on partial-failure projects).
- Optionally: add a smoke-test for the docs (link checker) and set up the graphify knowledge graph as a committed query artifact.
