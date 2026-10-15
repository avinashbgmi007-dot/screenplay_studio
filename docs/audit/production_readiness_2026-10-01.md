# Production-readiness audit — 2026-10-01

**Scope:** live verification of the writer-facing desk, the analyze pipeline, CI, and the
browser-suite fleet, on branch `feature/post-trust-hardening` (PR #4, at `f532166`).
Every finding below was reproduced against the running app or read directly from the code —
none comes from prior audit docs. Baseline measured during the audit: **pytest 1986 passed /
3 failed (pre-existing, unrelated), JS 23/23, browser fleet 60 suites — 59 pass / 0 fail /
1 skip (gun_pen_audit), 1,514 checks, known-broken list empty.**

Two corrections to the running notes from probing (kept honest here because an audit that
cannot correct itself is just a diary):

1. **aria-live DOES announce arrival.** An early probe reported silence because it sampled
   ~200 ms after the event; the live region announced on the next tick. The real gap is that
   the announcement is in a `.vh` (visually-hidden) element and the *visible* unread affordance
   (the dock tab lamp) hides inside the closed dock — so sighted writers looking at the desk
   see nothing.
2. **Empty uploads do NOT fail silently at analyze.** The analyze run returns a 502 with
   "Document has no parsed scenes", which reaches the desk. The failure is *loud but late and
   misattributed* — the project was accepted (201) and the writer first learns the import was
   bad minutes later, as an analysis error rather than an upload error.

## Findings and dispositions

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| H1 | high | First-analysis arrival signal invisible: the arrival peek is gated on `arrived = last_pass.computed_at changed`, but `state.lastPass` never populates on a project's FIRST pass — so the peek never fires for the moment it exists for; the visible unread dot lives on `#dock-tab-evidence`, which hides inside the closed dock; the aria-live announcement is screen-reader-only (`.vh`) | **Fixed (R1)** — peek now keyed on `analysisCompletedFor` (set by the progress poll, consumed by the load path, one-shot); unread mirrored onto `#right-edge-affordance` (always visible); CSS lamp + glow added |
| H2 | high | No way to cancel a running analysis: 91 routes, none cancel; a slow/hung model run holds the desk for its full timeout, and "Re-run" during a run 409s | **Fixed (R2)** — `AnalysisCancelled` through pipeline (stage-boundary + per-chunk checks), `/analyze/cancel` route + per-project event registry (popped when the run ends), orchestrator restores the pre-run stage (snapshot passed pre-reset by the webapp's force path — a genuine design bug found and fixed during implementation), heartbeat says "cancelled — the script is unchanged", UI Stop button with Stopping… state, poller reset branch |
| H3 | high | CI never runs the real-model path: `gun_pen_audit` (the only suite that POSTs a live `/analyze`) is skipped on every CI run; its assertions exist only on developer machines | **Fixed (R3)** — `test-live-model` job, gated on repository variable `STUDIO_LIVE_LLM_URL` (a variable, not a secret: a URL is not a credential, and `if:` can't see secrets); runs `run_browser_suites.py gun_pen_audit` against the operator's studio; unset ⇒ job skips visibly, green builds stop silently losing real-model coverage |
| M1 | medium | One logical model call is not wall-clock bounded: `chat_json` retries parse failures (2×) around `_post_chat`'s busy window (6 retries) with `timeout=600s` per HTTP read — worst case ≈ 3 × 600s + backoff of dead air inside ONE category | **Fixed (R4)** — `wall_clock` budget (default 600s) in `chat_json`: one monotonic deadline; each attempt's `timeout` is `min(remaining, configured)`, ceil'd so a healthy full-budget attempt keeps its exact configured timeout; non-positive remainder stops the loop; error names actual attempts; `None` opts out |
| M2 | medium | A successful retry is invisible: char_reads' bounded retry (added in PR #4) recovers on the real server, but the report never says so — a wobble-and-land looks identical to a clean pass | **Fixed (R4)** — `_with_retries(on_retry=…)` hook; analyze() emits a live "retrying" progress beat and appends a `notices` entry ("recovered on retry #N — no findings were lost"), rendered as a new "ℹ️ Run Notes" report section (markdown + findings JSON), distinct from ⚠️ Warnings |
| M3 | medium | Degenerate uploads accepted at creation: 0-byte and scene-less prose files parse "successfully" (0 scenes), get a 201, and the writer first hears about it later as an analyze 502 | **Fixed (R5)** — 0-byte rejected up front with the true reason; after `run_parse`, the parse output is re-read and a 0-scene project is refused with actionable guidance (what a valid upload looks like) and the claimed directory is REMOVED, so the shelf never lists an unanalyzable project |
| M4 | medium | CI browser fleet is Linux-only although Windows is the shipping platform (msvcrt locking, retry_permission, path shapes) | **Fixed (R6)** — `test-browser-windows` job (windows-latest, full fleet via `run_browser_suites.py`) |
| M5 | medium | No library-level backup: per-project backup existed; nothing saved the shelf | **Fixed (R7)** — `GET /api/library/backup`: every project as one zip with an embedded `library-backup.json` manifest (per-project file counts; damaged dirs archived + recorded, never fatal; `.lock`/`.tmp` and the co-writer profile store excluded); dashboard "⬇ Backup library" button (hidden on an empty shelf) served by a token-aware `downloadBackup()` helper — a bare `<a href>` cannot carry `X-Studio-Token` and would save the 403 page on a protected server |
| L1 | low | No upload size cap (a multi-GB drop is parsed in full) | Accepted for now: parse cost is the writer's own machine, and a cap that rejects a legitimate 500-page epic would be worse; revisit only if a real burden appears |
| L2 | low | `safe_dir_name` silently rewrites hostile names (`../evil` → `evil` inside PROJECTS_DIR) | Verified safe: containment holds, the sanitized name is used only for the directory, and the display title keeps the writer's words |
| L3 | low | Design-lab suites (`preview-next`, `preview-design`) ride the CI fleet | Accepted: they are few, cheap, and gate lab regressions the team actively iterates on |
| L4 | low | Stale audit docs overstate closed items | Corrected by this document; FIX_TRACKER updated in the same commit |

## Verification at this revision

- `tests/test_analyze_cancel.py` — 8/8 (cancel route 404/409/event, pipeline boundaries, per-chunk, orchestrator restore for pending AND previously-complete stages)
- `tests/test_generation_timeout.py` — 8/8 (budget caps per-attempt timeout, stops dead attempts, default-on, None opt-out, attempts-count message, notice + live beat through `analyze()`)
- `tests/test_upload_validation.py` — 5/5 (0-byte, scene-less, whitespace-only, directory removed, valid 201)
- `tests/test_library_backup.py` — 5/5 (all projects + manifest, plumbing excluded, damaged dir non-fatal, empty library, profile store excluded)
- Full suite, ruff, JS tests, and the browser fleet re-run at the branch tip (see FIX_TRACKER entry for the closing numbers).
