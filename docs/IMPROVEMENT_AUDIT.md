# Improvement Audit — what we've built, and where to push next

Date: 2026-08-14 · Author: session review (grounded in NOTES.md history + codebase)

This is an honest look back at what the project holds today, what's genuinely
strong, and — sorted by value-to-effort for the **end-user writer on a local
model** — what would push it closest to "perfect". Nothing here is a promise;
each item is a candidate for the next batch, to be spec'd when chosen.

---

## 1. What we hold today (inventory)

### The core loop (all working, tested, live-verified)
- **Import & parse** — PDF/Fountain/TXT → typed screenplay elements. The PDF
  parser does layout-band classification (left/dialogue/center/right from
  relative x0), glyph-doubling collapse, page-number stripping, U+2019 cue
  normalization, multi-line transition merging. Verified to mirror the uploaded
  PDF in the browser.
- **Analysis pipeline** — 11-pass category report (formatting, voice, subtext,
  scene summaries, dialogue/action, theme, character arcs, structure, scene
  function, setups/payoffs, character reads) with per-category resume, retry-
  failed merge, live progress UI, language selection.
- **Feedback room (script doctor)** — the report IS the interface: report
  viewer, fix queue with scene-anchored findings, "Discuss" that attaches the
  finding's evidence to Sam, compare/drafts/export.
- **Co-write room (Sam)** — humanized persona (character-card craft: behaviors
  over adjectives, example dialogue, tone-reaction, concrete callbacks),
  guardrails (probe unreasoned ideas, forward-momentum nudges, one-idea cap),
  select-to-reply quoting, script map as standing context, on-demand scene
  injection.
- **Relationship memory** — Sam learns the writer's working style across
  sessions (evidence-gated dimensions, visible "Sam's notes on you" panel with
  forget/refresh, survives chat clears).
- **Revision loop** — working-copy self-heal, undo/redo, edits applied to the
  script pane.

### Reliability work already banked
- Reply hygiene (JSON-wrap stripping, repetition/loop suppression, tag
  cleaning) — a real local-model pain point.
- Model fallback (`fallback_to_loaded`) so a pinned-but-unloaded model never
  bricks a conversation.
- **NEW this batch:** busy-retry in the LLM client (bounded backoff for
  llama-server's single-occupancy 400/429/503) so chatting during analysis
  doesn't fail the turn.
- **NEW this batch:** "Clear chat" (end-user control; memory preserved).
- **NEW this batch:** contextual motion (message entrance, room-swap slide,
  typing dots, quote pop-in; reduced-motion safe).

### Honest weaknesses (not yet addressed)
1. **No automated end-to-end test against a real model.** Unit coverage is
   strong (450+), but the model-dependent paths are verified manually per
   change.
2. **The 90% productivity claim is unmeasured.** No instrumentation (time-to-
   answer, findings-per-fix-item, session length) to prove improvement.
3. **Continuity checks don't exist yet** — and they're the highest-trust-risk
   feature (a wrong "continuity error" destroys trust).
4. **One model, one server.** No support for a second local model for cheap
   tasks (summaries) vs expensive ones (deep analysis).

---

## 2. Pushed to near-perfect: what the writer feels next (priority order)

Each row: outcome for the writer · rough effort (S/M/L) · why it earns its place.

### Tier 1 — fix the weakest link of the current loop
| # | Improvement | Effort | Why it matters |
|---|---|---|---|
| 1.1 | **Anchor findings to rendered lines, clickable both ways** (finding → the exact line in the paper; line → related findings) | M | Today the report and the script are two worlds; joining them is the single biggest productivity unlock for a script doctor |
| 1.2 | **Change-mark "stars" in the script margin** (Arc Studio's most-praised feature) — applied edits leave a small star you can hover/jump to | S–M | Rewrites become visible; undo/redo stops being a mystery |
| 1.3 | **Instrument the loop** (time-to-reply, analysis duration, findings-per-fix, "discussed" count) surfaced quietly in the status bar | S | Turns the 90% claim into something we can actually steer |

### Tier 2 — Sam earns trust
| # | Improvement | Effort | Why it matters |
|---|---|---|---|
| 2.1 | **The Stash** — highlight a line, store it in a sidebar, drag it back into the script later (already specced in the redesign proposal) | M | The core "don't lose a good idea while rewriting" workflow |
| 2.2 | **Character dials** (ScreenplayIQ pattern) — "did you intend her to be devious? adjust the dial"; the report re-renders its findings for that character | M | Turns feedback from a verdict into a tool |
| 2.3 | **Pacing/act graph** — a thin strip under the script showing scene lengths and energy; hover to jump | M | Structure becomes visible without leaving the page |
| 2.4 | **Quiet continuity check** — ship AFTER dials, with a confidence threshold and "wrong — forget" (the relationship-memory pattern) | L | Highest risk of the set; only ship when trust machinery exists |

### Tier 3 — polish & robustness (local-model reality)
| # | Improvement | Effort | Why it matters |
|---|---|---|---|
| 3.1 | **Two-tier model routing** — cheap model for summaries/refresh, good model for analysis; auto-fallback when only one is loaded | M | Cuts the long-analysis wait meaningfully on a single box |
| 3.2 | **Generation watchdog** — hard per-turn cap with a "Sam is still working, keep waiting?" prompt instead of a silent 600s timeout | S | The one remaining dead-end a writer can hit |
| 3.3 | **Session export/import as a single JSON file** | S | Portability + backup for the relationship memory and threads |
| 3.4 | **Full-script re-parse from within the app** when the parser version changes | S | Removes the manual CLI step that bit us twice |

### Explicitly cut (YAGNI — don't build)
- Ambient music, real-time multi-cursor, pre-production tools, market insights,
  cast suggestions, multiplayer.

---

## 3. Critique of this audit (self-review)

- **Tier 1.1 is the honest highest-leverage item** — the report and the paper
  already exist and are both strong; connecting them is integration, not new
  invention, and it changes the feel of the whole Feedback room.
- **The 90% claim** is persuasion until 1.3 exists. Instrument first, then
  claim.
- **2.4 is deliberately deferred**, not cut — continuity is the feature
  writers ask for most, but shipped without trust machinery it backfires.
- **3.2 is nearly free** and removes the last "hung turn" failure mode;
  do it whenever a small batch is being cut.

---

## 4. This batch's delta (already landed)

- `llm_client.py`: bounded busy-retry (400/429/503, body-aware) — chatting
  during analysis no longer fails the turn. (+5 tests)
- "Clear chat" button in the partner card → DELETE session → fresh session;
  relationship memory deliberately kept.
- Motion pass: message entrance (latest only), room-swap slide, Sam's typing
  dots, quote-card/quote-float pop-in, send-button lift — all disabled under
  `prefers-reduced-motion`.
