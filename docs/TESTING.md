# Testing

The suite is pure pytest against an **in-process mock llama-server** — no real model or network needed. Run it with:

```bash
python -m pytest tests/ -v          # full suite
python -m pytest tests/test_diff.py # single file
python -m pytest tests/ -k "resume" # by keyword
```

## How the mock works

- `tests/conftest.py` starts a session-scoped Flask server (`tests/mock_unified_server.py`) on port **8196** in a background thread and hands the URL to tests via the `mock_server` fixture.
- The mock routes on distinctive phrases in the system prompt: `"Summarize each"` → scene summaries; `"on-the-note dialogue"` → dialogue findings; `"professional script coverage"` → coverage; `"script doctor proposing a targeted revision"` → revision replacements; anything else → a chat echo reply that reports the detected persona, findings count, and injected scene numbers (so grounding can be verified end-to-end).
- Because Piece 2 and Piece 3 hit the *same* server in real use, one unified mock handles both request shapes — this is what lets the full parse→analyze→chat pipeline be tested genuinely end-to-end.
- `tests/fixtures/pain_tenglish.fountain` is a small Tenglish sample used by several tests. `tests/fixtures/Pain_FD_4_scenes.pdf` is a text-less PDF that exercises the OCR path (skipped gracefully when no OCR engine is installed).

## Test areas

| Area | Files |
|---|---|
| Full pipeline (positive/negative/edge/stress) | `test_positive.py`, `test_negative.py`, `test_neutral_edge.py`, `test_stress.py`, `test_runtime.py` |
| Parser | `test_structure.py`, `test_export.py`, `test_pdf_fixture.py`, `test_pdf_ocr.py`, `test_bare_array_tolerance.py` |
| Analyzer | `test_genre.py`, `test_character_reads_logline.py`, `test_grammar_compat.py`, `test_voice_subtext.py`, `test_feedback_filter.py`, `test_report_language.py` |
| Co-writer | `test_chat_language_meta.py`, `test_indian_languages.py` |
| Studio / revision loop | `test_revision.py`, `test_diff.py`, `test_compare.py`, `test_beatboard.py`, `test_notes.py`, `test_undo_redo.py`, `test_fixqueue.py`, `test_webapp_revision.py` |
| Webapp API | `test_webapp_api.py`, `test_webapp_revision.py` |
| Orchestrator / manifest | `test_delete_project.py`, `test_sample.py`, `test_watch.py` |

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

## Optional: run the real server

```bash
llama-server -m your-model.gguf --port 8080 --jinja
python -m screenplay_studio run sample.fountain --project ./demo --server http://localhost:8080 --skip-chat
```
