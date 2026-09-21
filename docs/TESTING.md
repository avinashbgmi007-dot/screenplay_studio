# Testing

The suite is pure pytest against an **in-process mock llama-server** — no real model or network needed. Run it with:

```bash
python -m pytest tests/ -v          # full suite
python -m pytest tests/test_diff.py # single file
python -m pytest tests/ -k "resume" # by keyword
```

## How the mock works

- `tests/conftest.py` starts a session-scoped Flask server (`tests/mock_unified_server.py`) on port **8196** in a background thread and hands the URL to tests via the `mock_server` fixture.
- The mock routes on distinctive phrases in the system prompt: `"Summarize each"` → scene summaries; `"on-the-nose dialogue"` → dialogue findings; `"professional script coverage"` → coverage; `"script doctor proposing a targeted revision"` → revision replacements; anything else → a chat echo reply that reports the detected persona, findings count, and injected scene numbers (so grounding can be verified end-to-end).
- Because Piece 2 and Piece 3 hit the *same* server in real use, one unified mock handles both request shapes — this is what lets the full parse→analyze→chat pipeline be tested genuinely end-to-end.
- `tests/fixtures/pain_tenglish.fountain` is a small Tenglish sample used by several tests. `tests/fixtures/Pain_FD_4_scenes.pdf` (+ `_recoverable.pdf`) are text-less PDFs that exercise the OCR path (skipped gracefully when no OCR engine is installed).
- `tests/js/` holds node tests for the DOM-free frontend helpers (`node --test tests/js/`).

## Test areas

| Area | Files |
|---|---|
| Full pipeline (positive/negative/edge/stress) | `test_positive.py`, `test_negative.py`, `test_neutral_edge.py`, `test_stress.py`, `test_runtime.py` |
| Parser | `test_structure.py`, `test_export.py`, `test_pdf_fixture.py`, `test_pdf_ocr.py`, `test_pdf_layout.py`, `test_bare_array_tolerance.py` |
| Analyzer | `test_genre.py`, `test_character_reads_logline.py`, `test_grammar_compat.py`, `test_voice_subtext.py`, `test_continuity_idiolect.py`, `test_setup_payoff.py`, `test_pacing_dials_track.py`, `test_feedback_filter.py`, `test_report_language.py`, `test_prompt_extensions.py`, `test_llm_client.py` |
| Co-writer | `test_chat_language_meta.py`, `test_indian_languages.py`, `test_peer_guardrails.py`, `test_writer_memory.py`, `test_writer_library.py`, `test_persona_humanization.py`, `test_humanization_v2.py` |
| Studio / revision loop | `test_revision.py`, `test_diff.py`, `test_compare.py`, `test_beatboard.py`, `test_notes.py`, `test_stash.py`, `test_undo_redo.py`, `test_fixqueue.py`, `test_webapp_revision.py`, `test_metrics.py` |
| Webapp API | `test_webapp_api.py`, `test_webapp_revision.py`, `test_ideas.py`, `test_idea_room_v2.py`, `test_idea_room_v3.py`, `test_preview_lab.py`, `test_selection_translate_sloppiness.py`, `test_sidebar_translate_stt.py`, `test_report_export_progress.py`, `test_language_and_human_levers.py`, `test_two_tier_watchdog.py` |
| Orchestrator / manifest | `test_delete_project.py`, `test_sample.py`, `test_watch.py`, `test_fix_batch.py`, `test_bugfix_batch.py`, `test_feature_batch.py`, `test_audit_hardening.py` |
| Browser e2e (Playwright) | `tests/e2e_browser_*.py` — smoke, selection/translate/mic, UI fixes, v3, wf (see `e2e_browser_common.py`) |
| Store fault injection | `test_store_fault_injection.py` — every writer-owned store against a crash-truncated / flipped-byte / zero-byte file (see below) |
| Packaging | `test_packaging_data_files.py` — builds a real wheel **and** sdist and asserts the craft-rule JSON, the SPA and the fonts are inside (see below) |
| SPA security | `test_spa_security_headers.py` — the `Content-Security-Policy` on the SPA document, and that it is *not* applied to the preview labs |
| XSS regression | `e2e_browser_xss_inert.py` — plants text- and attribute-context payloads into a real report and asserts they render inert (see below) |

## What the key suites verify

- **Positive:** full parse→analyze→chat pipeline; manifest persistence and reload; resume does not redo completed work.
- **Negative:** analyze against a dead server doesn't lose parse progress; retry after "fixing" the server picks up correctly; out-of-order stage calls raise clear errors; corrupt manifest/parsed JSON fails cleanly; unsupported source formats fail at parse with a clear message.
- **Neutral/edge:** model discovered during analyze carries into chat; running only specific analyzer categories; re-running a completed project is a no-op; starting chat twice resumes the same session.
- **Stress:** a 50-scene script through the full pipeline with timing assertions; forked chat branches through the orchestrator (fork isolation).
- **Webapp API:** every endpoint exercised through the real Flask app (`test_webapp_api.py`), including the full revision loop (`test_webapp_revision.py`).

## Conventions for new tests

- Use the `mock_server` fixture (returns the base URL) for anything that needs the LLM; use `sample_fountain` (`tmp_path`) for a minimal parseable script.
- Prefer asserting on the real outcome (stage statuses, findings content, file presence) over mock internals.
- Every webapp test should exercise the JSON API through the real Flask app (see `test_webapp_api.py`), not a stubbed client.
- If you add a new analyzer pass, add a mock branch to `tests/mock_unified_server.py` matched by a distinctive system-prompt phrase.
- To run against a real llama-server instead of the mock, point `--server` at it — the same CLI tests then exercise the real pipeline (slow; use selectively).

## Store integrity (one contract, every store)

`test_store_fault_injection.py` is not a per-store test file: it is a registry
(`CASES`) plus generic injectors, so a store is described once and gets the same
four assertions — MISSING reads as its default, VALID reads as data, DAMAGED
**never** reads as the default, and a load-modify-write must not replace a damaged
file's bytes (the damaged copy is often the only recoverable evidence). Writers
whose loader reports damage rather than raising declare that with `error_marker` /
`damage_ok`; stores that are regenerable declare it in `EXEMPT` with a reason. The
suite ends with a discovery check that fails when a module calls
`atomic_write_json` without a registry entry, so the next store cannot ship
without fault coverage.

```bash
python -m pytest tests/test_store_fault_injection.py -q     # 65 checks
```

## Packaging (the wheel must contain the app, not just the code)

`test_packaging_data_files.py` exists because `pip install .` once produced a
wheel of `.py` files only: no craft-rule JSON (so `KnowledgeBase()` loaded zero
rules and `_kb_rule_ids()` returned an empty set — every report silently lost
its "grounded in rule X" claim) and no `webapp/` at all (so `GET /` 404'd).
Neither failure raised; both degraded silently.

It asserts in three layers: the declared `package-data` globs must match every
shippable file on disk (a drift guard — add a new asset type and it fails until
the pattern list knows about it), and a real wheel and sdist must contain the
KB, the SPA and the fonts, and must *not* contain the 69 tracked evidence
screenshots or the orphaned `graph*.json` scratch.

Two traps this suite documents, both found by mutation-testing the guard itself:

- **Build artifacts mask regressions.** setuptools reuses `build/lib` and
  `egg-info/SOURCES.txt` between runs. Without purging them first, a reverted
  `package-data` still produces a complete wheel — staged by an earlier build —
  and the assertions pass for the wrong reason. The fixtures purge `build/` and
  `*.egg-info/` (never `dist/`, which may hold a real release artifact).
- **A guard that cannot fail is not a guard.** Verify any change to this file by
  reverting the packaging fix and confirming the suite goes red.

```bash
python -m pytest tests/test_packaging_data_files.py -q      # 8 checks, ~50s
```

## Route coverage (every route is exercised or declared)

`test_route_coverage.py` exists because a hand sweep for untested routes was
wrong in **both** directions. It reported
`/api/projects/<name>/beatboard/reset` as unreached when
`test_beatboard.py::test_reset_endpoint` drives it (the test composes the path as
`f"{base}/reset"`, so the literal never appears in the source), and it credited
`screenplay_cowriter/server.py` with the *webapp's* `/api/…/chat/sessions` paths —
making a module with **zero** coverage look 6/7 covered. That is how a whole HTTP
surface sat untested. A sweep is a snapshot; this is a gate.

**What it asserts.** Every route in each app's *authoritative* URL map
(`app.url_map`, not a regex over decorators) must be either

1. **exercised** by the pytest suite, or
2. **declared** in `UNEXERCISED` with a reason and a pointer to what does cover it.

An undeclared, unexercised route fails the build. So does a **stale** declaration:
if a declared route later becomes exercised, the entry must be deleted, or the
registry quietly stops describing reality. This mirrors the store registry's
discovery check and the browser runner's named-exclusion list — the same rule
three times: dead coverage must be visible.

**How "exercised" is measured.** `tests/route_recorder.py` attaches a
`before_request` hook to both module-level Flask apps. Every test drives those
same app objects, so the hook sees every request the session makes — no grepping
for path strings, which is the heuristic that failed above. A third test asserts
the hook is actually attached, so a detached recorder reports *itself* rather
than 85 phantom "undeclared" routes.

The tests are marked `route_coverage` and `conftest.py` moves them **last**, since
they report on the rest of the run.

> ⚠️ The gate is **run-scoped** by design: it asserts "every route was exercised by
> *this* session". Running only a subset of the suite fails it legitimately — it
> names the routes that subset never touched. It is green in CI, which runs the
> whole suite.

```bash
python -m pytest tests/test_route_coverage.py tests/test_route_smoke.py -q
```

`test_route_smoke.py` drives the six routes the rest of the suite never touched,
at their real contracts (a health probe that reflected nothing; the metrics view
behind the status strip; the finding-intent store; and the validation paths of the
two SSE routes and translate — empty text, unknown project, unknown session). Their
*generation* paths need a live model and stay browser-covered.

## CI gates (what actually runs automatically)

`ruff check .` → `pytest -q` → `node --test tests/js/*.test.js` → the browser suites.

The last one is new (2026-09-20). The `tests/e2e_browser_*.py` suites are standalone
Playwright scripts, **not** pytest tests — they do not match `test_*.py`, so pytest
never collected them and nothing ran them, while the shipped SPA (`app.js`, ~9k lines)
had no other behavioural coverage in CI beyond 7 assertions on `core.js`. They are now
driven by `tests/run_browser_suites.py`, which runs every suite, prints one summary,
and exits nonzero on any failure or crash:

```bash
python tests/run_browser_suites.py               # all runnable suites (~25)
python tests/run_browser_suites.py phase6 smoke  # by name substring
python tests/run_browser_suites.py --strict      # also chase the known-broken
E2E_BASE=http://127.0.0.1:8500 python tests/run_browser_suites.py
```

Two groups *can* be excluded — and the runner **prints both on every run** rather
than skipping them quietly, because dead coverage is worse than none (it looks like
safety). As of 2026-09-21 only one suite is actually excluded:

| Suite | Why it is not in the gate |
|---|---|
| `gun_pen_audit` | runs a real analyze, so it needs a llama-server; `E2E_BASE` must point at a studio that has one |

`KNOWN_BROKEN` is **empty**. `preview_next` and `preview_redesigns` were repaired
(both had been excluded as "crashes" — one of them had never exercised four of its
six worlds). `design_session` was **self-hosted**: its old entry said it needed a
studio on `:8500`, but that label was false — the console frames the SPA, and the SPA
sends `frame-ancestors 'none'`, so **no port would ever have made it pass**. It boots
its own studio now and pins the deliberate block as a check instead of working around
it.

Chromium is required: `python -m playwright install chromium` (CI adds `--with-deps`).

## Optional: run the real server

```bash
llama-server -m your-model.gguf --port 8080 --jinja
python -m screenplay_studio run sample.fountain --project ./demo --server http://localhost:8080 --skip-chat
```
