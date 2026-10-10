# The Verdict Channel — integration spec

**Date:** 2026-10-05 · **Status:** spec (not applied) · **Base:** must be applied on `origin/main`, not the audit worktree
**Why:** the product has no ground-truth channel. `finding_marks.json` records what the writer will **do**
(`addressed | deferred`); nothing records whether a finding is **true**. Until something does, "98.58 %
accurate" is unfalsifiable — there is no data from which to compute it.

---

## 1 · What already exists (do not rebuild)

| axis | question | store | values | status |
|---|---|---|---|---|
| **actionability** | what will I do with it? | `finding_marks.json` | `addressed · deferred` (+ triage `dismissed`) | **exists** (`revision.py:92-131`) |
| **verifiability** | can the pipeline check it? | derived | `verified · not_found · …` (`verifier.py`) | **exists** |
| **truth** | is it right? | — | — | **MISSING — this is the whole gap** |

So the verdict channel is **one new axis**, not a redesign. It mirrors the intent store exactly, because
that store already solved the hard problems: stable keying, lock-spanning-read, atomic write, and
refusing to overwrite a damaged file.

---

## 2 · The store

New file `finding_verdicts.json` in the project dir — **separate from** `finding_marks.json` so a damaged
verdict store can never cost the writer their intent marks (and vice versa). Same discipline verbatim:

```python
# screenplay_studio/revision.py — beside finding_intents (line 100)

def finding_verdicts_path(m) -> str:
    return os.path.join(m.project_dir, "finding_verdicts.json")

_VERDICTS = ("correct", "partial", "incorrect")

def finding_verdicts(m) -> dict:
    """{finding_id: "correct" | "partial" | "incorrect"} — the writer's judgment
    on whether the finding is TRUE. Orthogonal to intent (what they will do).
    Missing -> {} ; damaged -> StoreUnreadable."""
    from .jsonio import StoreUnreadable, load_json_store
    data = load_json_store(finding_verdicts_path(m), default={})
    if not isinstance(data, dict):
        raise StoreUnreadable(finding_verdicts_path(m), "expected an object")
    return {k: v for k, v in data.items() if v in _VERDICTS}

def set_finding_verdict(m, finding_id: str, verdict) -> None:
    from .jsonio import StoreUnreadable, load_json_store, lock_for, atomic_write_json
    path = finding_verdicts_path(m)
    with lock_for(path):                       # the lock spans the READ (revision.py:118-121)
        data = load_json_store(path, default={})
        if not isinstance(data, dict):
            raise StoreUnreadable(path, "expected an object")
        if verdict in _VERDICTS:
            data[finding_id] = verdict
        else:
            data.pop(finding_id, None)         # None clears
        atomic_write_json(path, data)
```

## 3 · The routes (mirror the intent routes exactly)

| route | mirrors | body |
|---|---|---|
| `POST /api/projects/<n>/findings/verdict` | `webapp_server.py:2639` | `{"finding_id": "...", "verdict": "correct\|partial\|incorrect\|null"}` |
| `POST /api/projects/<n>/findings/verdict/batch` | `webapp_server.py:2552` | `{"verdicts": {"<id>": "correct", ...}}` — one call, N marks |

Both carry the same guards as every other write route: `X-Studio-Token`, same-origin, loopback.

## 4 · The UI

In the finding's expanded row, **below** the disposition row and visually distinct from it:

```
  is it right?    ✓ Correct   ~ Partly   ✗ Wrong        ← the NEW truth axis
  what I'll do?   Addressed   Defer      Dismiss        ← the EXISTING intent axis
```

Two rows, two questions. Never one control. A writer must be able to say *"it's true but I won't act on
it"* — collapsing the axes is what produced the ambiguous "partial" in the first place.

Keyboard: `1` / `2` / `3` when the row has focus; **never** while a text field has focus (the shipped
`isTypingTarget` guard, `app.js:8890`).

## 5 · The metric — defined here, once

The choice of denominator is the whole game. Three readings of one tally, measured on the two real
payloads (`accuracy_report.py`, this folder):

| reading | formula | Pain_3 | gun_pen | means |
|---|---|---|---|---|
| **accuracy (headline)** | `(correct + partial) / all` | **96.8 %** | **93.8 %** | a finding is *inaccurate* only if the writer calls it **wrong** |
| strict agreement | `correct / all` | 35.5 % | 37.5 % | every non-endorsed finding counts against |
| excl-partial **(do not use)** | `correct / (correct + incorrect)` | 91.7 % | 85.7 % | ignores the middle — gameable |

**The headline is the accuracy reading, and here is the rationale:** the harm this product must avoid is a
writer *acting on a false finding*. A true-but-unsupported finding costs nothing — the writer judges it.
So the bar belongs on `incorrect`, and the job of raising it is **verifiability** (Metric B), not a
stricter truth bar.

**`partial` is therefore not a failure — it is a *verifiability* debt**, and it is what gate 11 pays down.

### The two metrics, and why both

| | population | source | target |
|---|---|---|---|
| **A · accuracy** | every delivered item | writer verdicts | 98.58 % not-wrong |
| **B · verifiability** | the asserted tier | the pipeline (`verifier.py` + grounding) | 98.58 % grounded |

A perfect observation the writer ignores scores 100 % on B and 0 % on A; an agreeable opinion scores high
on A and is unmeasurable on B. **Only A proves the writer trusts the output; only B proves it is checkable.**

### Where the numbers are today (measured, real model, `gemma_vn26b`)

| | Pain_3 | gun_pen |
|---|---|---|
| A · accuracy (after the integrity gate) | **96.8 %** | **93.8 %** |
| — gap to 98.58 % | **1.8 pts** | **4.8 pts** |
| — residual wrong findings | 1 | 1 |
| B · verifiability (asserted tier) | 68.8 % | 83.3 % |
| coverage delivered | 79.5 % | 72.7 % |

**The gap to 98.58 % on A is a handful of wrong findings, not a redesign.** On these two payloads the
whole shortfall is 2 findings across 47 delivered items.

## 6 · Integration points (file:line, against `origin/main`)

| what | where | change |
|---|---|---|
| store | `screenplay_studio/revision.py:92-131` | add the three functions above |
| single route | `screenplay_studio/webapp_server.py:2639` | add, mirroring `set_finding_intent_route` |
| batch route | `screenplay_studio/webapp_server.py:2552` | add, mirroring `set_finding_intents_batch` |
| load into state | `screenplay_studio/webapp/app.js:4157` (`state.report = …`) | also fetch `/findings/verdicts` |
| render | the finding row, beside `data.gated` (`app.js:3753`) | two-axis row |
| meter | Coverage screen | read the verdicts, print A and B |

## 7 · Tests to add (the repo guards behaviour with tests — match it)

1. `test_verdict_store_survives_damage` — a torn `finding_verdicts.json` raises `StoreUnreadable` and is
   **not** overwritten by the next mark (mirrors the existing intent-store test).
2. `test_verdict_and_intent_are_independent` — setting a verdict leaves `finding_marks.json` byte-identical
   and vice versa.
3. `test_verdict_batch_is_one_call` — N verdicts in one POST, N persisted.
4. `test_verdict_survives_reanalysis` — **the gate-3 question**: mark findings, force a re-analysis, count
   survivors. (Expected to be poor today — `DECISION_RECORD.md:43` accepts that ids do not survive
   unconditionally. This test *documents* the rate rather than asserting a value.)

## 8 · What must happen before this is applied

**Apply on `origin/main`, not on the audit worktree.** The worktree is 9 commits behind, and it predates
`6b99fe0` — the commit that made a finding's id name its scene. The verdict store keys on that id; building
it on the pre-fix base would persist verdicts against colliding ids (measured: 73 findings → 34 unique ids,
one group of 40 sharing a single id). **The id fix is a hard prerequisite, not a nicety.**
