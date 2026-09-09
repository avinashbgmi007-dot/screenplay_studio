# Writer Relationship Memory — "Sam gets to know you" (v2)

**Status:** Approved design → spec. Implementation follows after user review + plan critique.
**Date:** 2026-08-12
**Companion spec:** `2026-08-12-feedback-cowrite-rooms-design.md` (the rooms + partner work this builds on).

---

## 1. Problem

The rooms work built Sam: one consistent writing partner with guardrails that keep him human —
never jumping on an idea, never dead-ending, one idea at a time, never volunteering the report.
But Sam is a *stranger every session*. Open a new project tomorrow and he behaves identically to
day one, regardless of how you've worked together since.

**Goal:** Sam *gets to know the writer* across sessions — tone and working style calibrate
gradually, exactly the way a real colleague learns what you expect, accept, and argue about.
The rooms spec explicitly deferred this to v2 ("writer-profile / tone calibration over sessions").
This is that v2.

## 2. Principles (non-negotiable)

1. **The writer stays the editor.** Everything Sam learns is visible and reversible. He never
   acts on a hidden black box.
2. **Memory informs tone, never content.** It tunes *how* Sam talks (length, directness, probing,
   pushback, where the conversation lives) — it never vetoes a story choice and is never quoted
   at the writer ("you always say…" is forbidden).
3. **Nothing much at the beginning.** Cold start is a human get-to-know-you, not a questionnaire.
   The profile starts empty and every calibration is *earned* with evidence and confidence.
4. **No flip-flopping.** A single comment never changes behavior. Contradictions accumulate on the
   opposite pole; only sustained evidence crosses the gate.
5. **The guardrails tune, never break.** The two-phase probe, dead-end check, and one-idea cap
   stay structurally intact; memory adjusts their *frequency and weight* only.

## 3. Locked decisions (from design Q&A)

| Decision | Choice |
|---|---|
| Scope | **Writer-level, across all projects** — one profile file next to `studio_projects/`, not inside any project |
| Memory source | **Auto-inferred (behavioral)** — Sam observes interaction patterns; no "remember that…" commands in v1 |
| Dimensions | All five: **detail level, directness/gentleness, probe appetite, pushback appetite, topic gravity** |
| Mechanism | **Hybrid** — cheap per-turn rule signals (the floor) + one LLM **session refresh** pass that reconciles scattered signals into stable observations |
| Cold start | **Human get-to-know-you** — Sam starts neutral; the fresh-session welcome includes one light, optional open question that doubles as the first honest signal |
| Surfacing | Visible, editable **"Sam's notes on you"** card in the Co-write room — view, "forget this", "refresh now" |

## 4. Architecture

```
studio_projects/
  writer_profile.json          <-- NEW: writer-level memory (spans all projects)
  <project>/
    sessions/<sid>.json        <-- unchanged, per-project as today
```

**New module:** `screenplay_cowriter/memory.py`

- **Pure functions** (unit-testable, no I/O): `extract_signals`, `apply_signals`,
  `dimension_gate`, `build_relationship_card`, `merge_refresh`, `parse_refresh_json`,
  `refresh_prompt`.
- **Thin wrapper:** `WriterMemory` — load/save (with lock), `observe()`, `refresh_due()`,
  `refresh_async()`, `suppress()`, `card_text()`, `cold_start_line()`.

**Touch points (minimal, backward-compatible):**

| File | Change |
|---|---|
| `screenplay_cowriter/memory.py` | new module (above) |
| `screenplay_cowriter/context.py` | `build_system_prompt(..., relationship_card: str | None = None, cold_start_line: str | None = None)` — both appended only when provided |
| `screenplay_cowriter/engine.py` | `CoWriterEngine` gains optional `memory=None`; `send_message` observes each turn and passes the card into both prompt paths (probe + full) |
| `screenplay_studio/webapp_server.py` | wires memory by default (path = `PROJECTS_DIR/writer_profile.json`); new endpoints |
| `screenplay_studio/webapp/app.js` + `index.html` + `style.css` | "Sam's notes on you" card panel in Co-write room |
| `screenplay_cowriter/server.py` / `cli.py` | optional `--memory-path` (default off) — existing CLI users see zero change |

## 5. Data model — `writer_profile.json`

```json
{
  "version": 1,
  "dimensions": {
    "detail_level":      { "value": "balanced", "confidence": 0.62, "evidence": { "pos": 7, "neg": 2 }, "last_updated": 1754980000 },
    "directness":        { "value": "direct",   "confidence": 0.71, "evidence": { "pos": 6, "neg": 1 }, "last_updated": 1754980000 },
    "probe_appetite":    { "value": "medium",   "confidence": 0.55, "evidence": { "pos": 3, "neg": 2 }, "last_updated": 1754980000 },
    "pushback_appetite": { "value": "high",     "confidence": 0.68, "evidence": { "pos": 5, "neg": 1 }, "last_updated": 1754980000 }
  },
  "topic_gravity": { "character": 0.42, "structure": 0.31, "dialogue": 0.18, "craft": 0.09 },
  "observations": [
    { "id": "obs_1a2b3c", "text": "You tend to argue for lines I suggest cutting — you enjoy sparring over choices.",
      "dimension": "pushback_appetite", "confidence": 0.7, "source": "rules", "contradictions": 0,
      "suppressed": false, "created": 1754980000, "updated": 1754980000 }
  ],
  "meta": { "total_turns_observed": 214, "turns_at_last_refresh": 204, "last_refresh": null, "refresh_count": 0 }
}
```

**Confidence math (pole-accumulator with smoothing):** each dimension stores a `pos`/`neg`
evidence pair — `pos` evidence for the currently-set pole, `neg` evidence against it (so a
contradictory signal pushes `neg`, which re-flips the value only when it wins at confidence).
`confidence = (pos + 2) / (pos + neg + 4)` — 0 evidence ⇒ 0.5 with no *pole* set; a pole only
emerges as evidence accumulates. **The behavior gate is `confidence ≥ 0.6`** on a set pole.
Below the gate, Sam stays neutral ("nothing much at the beginning").

**Dimensions & poles:** `detail_level` (short/balanced/deep), `directness` (gentle/balanced/direct),
`probe_appetite` (low/medium/high), `pushback_appetite` (low/medium/high),
`topic_gravity` (normalized keyword distribution across character/structure/dialogue/craft).

**Missing/corrupt file:** treated as empty profile; first write creates it; a corrupt file is
backed up to `writer_profile.json.bak` and replaced with an empty profile — chat never crashes.

## 6. Inference — per-turn micro-signals (rules, zero model cost)

Called at the start of each `send_message` turn with data already in hand:
`memory.observe(user_text, turn_kind, was_pending, previous_reply)`.

| Signal | Source | Poles |
|---|---|---|
| **Detail level** | user_text length bucket + explicit asks ("keep it short", "go deeper", "more detail") | short / deep (balanced by default) |
| **Directness** | explicit tone statements: "just tell me straight", "don't soften it" → direct; "be gentle", "ease me in", "carefully" → gentle | direct / gentle |
| **Probe appetite** | was this turn answering a probe (`was_pending`)? Engaged = substantive reply (≥ 6 words, or reasoning keywords) ⇒ high; dismissed = ≤ 3 words, or a topic-change question ⇒ low | high / low |
| **Pushback appetite** | does the writer argue for a choice ("no, that doesn't work because…", "I disagree")? Arguing = engagement (high); reflexive acceptance = low | high / low |
| **Topic gravity** | keyword lexicon per category, counted from user turns | distribution |

**Contradiction rule:** an explicit tone statement pointing *against* a currently gated preference
adds evidence to the opposite pole (which re-flips only at confidence) and increments
`contradictions` on any conflicting observation; an observation auto-suppresses at 2+ contradictions.

## 7. Inference — session refresh (one LLM call)

- **Trigger:** when `total_turns_observed - turns_at_last_refresh ≥ 10` (checked on session open
  and on each send — cheap boolean). One refresh in flight at a time (cooldown flag).
- **Execution:** fire-and-forget daemon thread — the writer's reply is never blocked. Uses the
  current session's recent messages (last 16, matching `HISTORY_WINDOW`) as the transcript.
- **Prompt contract (`refresh_prompt`):** *"Read this conversation between a writer and their
  co-writer. Based ONLY on explicit evidence, what does this writer prefer? Output strict JSON:
  per-dimension `{value | "no_evidence", confidence 0-1}` plus 1–3 plain-language observations
  with a dimension tag. Do NOT invent. If unclear, say no_evidence."*
- **Lenient parse (`parse_refresh_json`):** extract JSON even if the model wraps it in prose —
  same tolerance the analyzer already applies to model output (`test_bare_array_tolerance`).
- **Merge rules (`merge_refresh`):** a dimension changes only if the refresh's confidence beats
  the current one; observations are added only if novel (no near-duplicate text); refresh never
  *lowers* evidence from a single pass; on refresh failure, log and leave the profile unchanged
  (retried at the next due check).

## 8. Behavior gating — how the memory actually speaks

`memory.card_text()` returns a paragraph only when ≥ 1 dimension is gated (confidence ≥ 0.6):

> ABOUT HOW YOU TWO WORK TOGETHER — what you've noticed about how this writer likes to work:
> they prefer short, direct answers and enjoy sparring over choices. Adapt your tone accordingly.
> Rules: this informs TONE, never content. Never quote the memory to the writer ("you always say…"
> is forbidden). If the writer contradicts a remembered preference this turn, the current turn wins.

Injected into `build_system_prompt` on **both** prompt paths (probe + full turn).

**Guardrail tuning (frequency, never structure):**

| Gated dimension | Effect |
|---|---|
| `probe_appetite: low` | Sam still reflects first, but the probe folds in lightly and probe-turns are rarer |
| `probe_appetite: high` | probes a bit more readily — the writer engages with "why do you think so?" |
| `directness: direct` | after the reflect-first phase, notes land more plainly |
| `pushback_appetite: high` | Sam may argue a point after offering it |
| `detail_level` | reply length guidance in the system prompt |
| `topic_gravity` | no structural effect — it lets the card name where the writer keeps returning |

The two-phase structure ("never jumped on"), dead-end check, and one-idea cap remain intact in
every case.

## 9. Cold start

- The profile starts empty ⇒ no card, neutral behavior — **Sam is a polite stranger on day one**.
- `memory.cold_start_line()` returns a single light, optional question ("What's the one thing
  you're trying to fix in this draft?") appended only to the **very first turn** of a fresh
  session (`branch.messages` empty) when the profile has zero evidence. It is a prompt-level
  nudge, never a forced questionnaire; the writer's answer feeds topic gravity + detail as
  ordinary signals.

## 10. Surfacing — "Sam's notes on you" (writer stays the editor)

- **Co-write room partner card** gains a small affordance (an icon + "Sam's notes on you").
- Opens a panel listing: gated dimensions + observations with confidence.
- Each observation has **"forget this"** → `suppressed: true` (permanent; explicit override
  outranks inference) and a **"refresh now"** button (runs the same background refresh path).
- Backend: `GET /api/writer-memory` (profile + current card text) and
  `POST /api/writer-memory/observations/<id>/suppress`.

## 11. Data flow

```
send_message (engine)                     webapp_server
   │  observe(user_text, turn_kind,          │  GET /api/writer-memory
   │    was_pending, prev_reply) ──rules──▶  │  POST .../suppress
   │  refresh_due()? ──▶ refresh_async()     │     (writes profile, lock)
   │  card_text()/cold_start_line() ──▶      │
   ▼                                        ▼
build_system_prompt(+relationship_card)   writer_profile.json
   ▶ client.chat(messages)                 (spans all projects)
```

## 12. Backward compatibility

- `build_system_prompt` gains optional params defaulting to `None` — all existing callers
  (webapp, orchestrator, cowriter CLI/server, tests) unchanged.
- `CoWriterEngine(memory=None)` default — all four construction sites unchanged unless wired.
- Webapp wires memory by default; cowriter CLI/server expose `--memory-path` (default off).
- Existing sessions, branches, and profiles never block chat — memory is strictly additive.

## 13. Error handling

| Failure | Behavior |
|---|---|
| Model refresh fails | log; profile unchanged; retried at next due check |
| Profile JSON corrupt | backed up to `.bak`; empty profile used; chat unaffected |
| Concurrent writes | `threading.Lock` around save in `WriterMemory` |
| LLM refresh returns garbage | lenient parse fails ⇒ no merge; cooldown respected |

## 14. Testing plan

1. **Pure functions** (`tests/test_writer_memory.py`): signal extraction from canned user texts
   (tone statements, probe engagement, pushback, topic keywords); confidence/gating math
   (crosses 0.6 only with real evidence; no flip on one comment); card text (gated only,
   suppressed excluded); contradiction handling; merge rules (novelty, confidence-beat,
   no-lowering); lenient JSON parse; refresh prompt shape.
2. **Engine integration:** `memory=None` ⇒ system prompt byte-identical to today (regression);
   gated dimension ⇒ card appears in the system prompt (captured via mock client);
   `observe()` called every turn; cold-start line only on the first turn of a fresh session.
3. **Webapp:** `GET /api/writer-memory` returns profile + card; suppress endpoint marks the
   observation; due-check/cooldown logic unit-tested.
4. **Full suite stays green** (328 existing + new).

## 15. Out of scope (v2.x)

- Explicit "remember that…" commands and free-text preferences.
- Multi-writer/user profiles and per-writer identity.
- Cross-device sync or any network storage (memory is a local file, like everything else).
- Editing observation text in the UI (suppress only).
