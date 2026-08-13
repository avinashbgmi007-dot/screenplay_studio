# Script Doctor & Co-Writer Studio

A local, privacy-first screenplay analysis system running entirely on your
own `llama-server` instance. This bundle contains everything: the four
components (Parser, Analyzer, Co-writer, Craft Knowledge Base) plus an
orchestrator that wires them together — while keeping every piece fully
usable on its own.

## What's in this bundle

```
screenplay_parser/      Piece 1 — no model dependency. Parses .fdx/.pdf/
                         .txt/.fountain into structured JSON + a knowledge
                         graph (character index, recurring-object candidates,
                         timeline, dialogue promises).
knowledge_base/          34 attributed screenwriting-craft rules (Aristotle,
                         McKee, Snyder, Field, Swain, Vogler, Chekhov) that
                         ground every analyzer judgment in a named, explicit
                         principle instead of an LLM's unaudited memory.
screenplay_analyzer/     Piece 2 — model-dependent. Runs the full analysis
                         pipeline (theme/character/structure/dialogue/scene-
                         function/plot-economy/coverage), grounded in the
                         knowledge base, with every quote verified against
                         the actual script text.
screenplay_cowriter/     Piece 3 — model-dependent. Persistent, forkable
                         chat about the analysis, with multi-persona reader
                         modes (producer/dev-exec/teacher/audience/genre
                         specialist).
screenplay_studio/       This orchestrator — runs the three above in
                         sequence, with a resumable project manifest so one
                         stage failing doesn't lose prior progress.
```

## Quick start

```bash
pip install -r requirements.txt

# start llama-server the way you already do
llama-server -m your-model.gguf --port 8080 --jinja

# full pipeline: parse -> analyze -> drop into interactive chat
python -m screenplay_studio run my_script.fdx --project ./my_project --server http://localhost:8080

# just parse + analyze, skip the interactive handoff
python -m screenplay_studio run my_script.fdx --project ./my_project --skip-chat

# resume later (only reruns stages that aren't already complete)
python -m screenplay_studio resume ./my_project --server http://localhost:8080

# check where a project stands
python -m screenplay_studio status ./my_project
```

## Project layout

Each run creates a self-contained project directory:

```
my_project/
  project.json               <- manifest: stage status, model used, session id
  source.fdx                  <- copy of your original screenplay file
  parsed.json                  <- Piece 1 output
  parsed.kg.json                 <- knowledge graph (recurring objects, timeline, etc.)
  report.md                       <- human-readable analysis report
  report.findings.json             <- structured findings (Piece 3 reads this)
  sessions/                          <- co-writer chat sessions (persistent memory)
```

## Using pieces independently

The orchestrator is a convenience layer, not a requirement — every piece
still works exactly as documented in its own README, using its own CLI
directly:

```bash
python -m screenplay_parser parse my_script.fdx -o parsed.json --kg
python -m screenplay_analyzer parsed.json --server http://localhost:8080 -o report.md
python -m screenplay_cowriter chat --new "My Script" --report report.findings.json --script parsed.json
```

This matters if you want to, say, re-run just the analyzer with different
categories without touching an existing chat session, or parse a script
without ever running the model-dependent stages.

## Failure isolation

If `analyze` fails (server down, model swapped mid-run, etc.), the project
manifest still has `parse` recorded as complete — rerunning `resume` picks
up from `analyze`, it doesn't redo `parse`. A *partial* analyze failure
(some categories succeeded, one didn't) is recorded as complete with the
partial errors visible in the report; a *total* failure (nothing could be
analyzed at all) is recorded as failed and must be retried.

## How this was tested before being shared

The original 25 end-to-end tests (the suite has since grown — 281 tests collected), run against a unified mock server that handles both
Piece 2's structured analysis calls and Piece 3's conversational calls
(since in real use it's the same `llama-server` the whole time):

- **Positive (7)**: full parse→analyze→chat pipeline, manifest persistence
  and reload, resume not re-doing completed work.
- **Negative (10)**: analyze failing against a dead server doesn't lose
  parse progress; retrying after "fixing" the server picks up correctly;
  out-of-order stage calls (analyze/chat before parse) raise clear errors;
  corrupt manifest/parsed-JSON fails cleanly rather than crashing ugly;
  unsupported source formats fail at the parse stage with a clear message.
- **Neutral/edge (6)**: the model discovered during `analyze` correctly
  carries into `chat` (the cross-piece model-inheritance behavior);
  running only specific analyzer categories; re-running a completed
  project twice is a no-op; starting chat twice resumes the same session
  rather than creating a duplicate.
- **Stress (2)**: a 50-scene script through the full pipeline with timing
  assertions; 10 forked chat branches reached through the orchestrator,
  confirming Piece 3's fork isolation still holds when driven through this
  layer rather than directly.

**One real bug this process caught**: Piece 2's `analyze()` treats a
totally unreachable model server as a *soft* failure — it returns an empty
result with errors listed rather than raising, by design, so that one
category failing doesn't crash the other five. The orchestrator's first
draft didn't distinguish that from a genuine partial failure (5/6
categories succeeding), so a completely-dead-server run was being marked
"complete" with errors noted, identical to a minor partial failure. Fixed
so a total failure (nothing usable produced) is now correctly marked
"failed" and raises, while a partial failure (something usable was
produced despite some errors) is still marked "complete" with the errors
visible — these are genuinely different situations and now behave
differently.

## Indian-language scripts (Tenglish / Hindi / Tamil)

The parser natively handles Indian-language screenplays alongside standard
English ones — the classification rules were made script-aware:

- **Tenglish** — Telugu spoken-lines written in the Roman alphabet with
  standard `INT.`/`EXT.` headings (the dominant Telugu/Tamil screenwriting
  convention). Handles `EXT/INT.` headings, all-caps beat markers like
  `TWO MONTHS EARLIER` (never misread as speakers), and underscore names
  like `GOON_ONE` (normalized to `GOON ONE`).
- **Hindi (Devanagari)** — caseless script: `इंट.`/`एक्सट.` scene headings
  and speaker cues are detected by content context since there's no
  uppercase. Same for **Tamil** (`உள்.`/`வெளி.` headings).

### PDFs without a text layer (scanned / some Final Draft exports)

Some PDFs — including `tests/fixtures/Pain_FD_4_scenes.pdf` — carry fonts
without a Unicode mapping, so no text extractor can read them. The parser
falls back to **built-in OCR**: it renders each page and reads it with
tesseract (or easyocr), auto-detected — no code changes needed:

```bash
# install once (recommended lang packs for Indian scripts)
pip install pytesseract
# + install tesseract itself with eng, tel, hin, tam language packs

# optional overrides (defaults: auto-detect, eng+tel+hin)
export SCRIPT_DOCTOR_OCR=tesseract        # or easyocr
python -m screenplay_studio run my_script.pdf --project ./p
```

If no OCR engine is installed, the parser returns a clear, actionable
error (re-export as .fdx/.fountain, or install tesseract) instead of a
silent empty parse.

### Report language (English / Tenglish / Hindi / Tamil)

The analysis report can be produced in the language the script is in:

```bash
python -m screenplay_studio run my_script.fountain --project ./p --lang tenglish
python -m screenplay_studio watch ./inbox --lang hindi
```

In the web app, pick "Report in" next to **Run Analysis**. Quotes in the
report stay verbatim from the script so verification still works.

## Known limitations

- The orchestrator assumes all four component packages sit as siblings
  (this bundle's layout) — if you move pieces around independently, update
  imports accordingly.
- `run_analyze`/`run_parse` re-run from scratch if a stage is marked
  `failed` (not `complete`) — there's no partial-category resume within a
  single analyze stage (e.g. 5/6 categories succeeding doesn't let you
  retry just the 6th without re-running all 6).
- OCR-read PDFs are best-effort: scene boundaries and speaker attribution
  come from OCR line breaks, so spot-check them (a warning marks the
  project's parse as low-confidence).
