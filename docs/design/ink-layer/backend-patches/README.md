# Backend halves the Ink Layer's refusal path depends on — APPLIED

**Applied on `feature/stale-proposal-guard`, 2026-10-03**, branched from the merged `main`
(`1e1131a`): `bb9ce92` (the guard, the route contract and the `/rewrite` producer filter) and
`b6c153d` (the client half the browser suite then proved was missing). The sections below are kept
as they were written — they are what the patch was cut from, and why. The outcome is recorded at the
end, including the live re-run of the probe in the last section.

These two files are **paste-ready patch documents, not modules**: each one opens with a
`WHERE THIS GOES` note naming the file and the exact anchor. They are here as a record of what the
prototype in `screenplay_studio/webapp/preview-ink-layer/` expects from the desk, and as the
verification of a claim I made about this repo.

Verified against `main` at `0fa814c` (2026-10-03):

* **`revision.py` — the guard is absent.** No `StaleProposalError`, no `_assert_proposal_is_fresh`,
  no `"Stale proposal:"` string anywhere in the tree. `apply_edit` today is already one critical
  section (BE-1) — that part is in — but nothing asserts that the `old` text a proposal was cut from
  is still what the working copy holds, so a stale proposal is applied to text that has moved.
* **`webapp_server.py` — the explicit-frames rule is present, with different copy.** The route does
  validate each item (`replacements[i] must have string 'old' and string 'new'.`, the L5 fix) and
  does not need `_require_explicit_frames` for shape. What it does *not* do is answer the staleness
  contract, because nothing raises it yet.

## What the prototype expects, and why

The Ink Layer's trap frame (contracts_UI §3.4) never writes during an audition, so a refusal is a
**state** it renders, not an error it unwinds: `row[data-cast="stale"]`, the refusal printed in the
fold and kept there until the writer answers it, and the writer's own text still on the page byte for
byte. That path reads two things off the response:

```json
400  { "error": "Stale proposal: the text was modified manually.", "stale": true }
400  { "error": "replacements require string fields 'old' and 'new'" }
```

`core.classifyApplyError` decides from `body.stale` — never by matching the sentence — so the flag is
the load-bearing part, not the wording.

## The one decision these documents were blocked on — resolved: apply, with `main`'s copy

The copy differs between what this prototype was specified against and what the route ships:

| Refusal | Specified to the UI | In `main` today |
|---|---|---|
| malformed frame | `replacements require string fields 'old' and 'new'` | `replacements[i] must be an object with 'old' and 'new', got str.` / `replacements[i] must have string 'old' and string 'new'.` |
| stale proposal | `{"error": "Stale proposal: the text was modified manually.", "stale": true}` | not implemented |

Both current messages are *better* than the specified one — they name the offending row, which the
specified message does not. The prototype does not need the specified wording (it reads `stale` and
whatever sentence arrives), so my recommendation is: **keep `main`'s messages, add the `stale: true`
flag and the guard, and treat the specified copy as superseded.** Until that is decided, the UI's
stale path cannot be exercised against a real server — only against the demo, which re-implements the
guard so the refusal can at least be seen and tested.

**Decided 2026-10-03: apply the patch, keep `main`'s per-row messages, add the `stale: true`
flag.** The specified copy stays superseded, exactly as recommended above — the flag is what the UI
reads, so the wording never had to agree. With that, the stale path IS exercisable against a real
server, and the last section records it being exercised.

## Status at the time these documents were written

* Not applied to `screenplay_studio/revision.py` or `screenplay_studio/webapp_server.py` by me.
  Applying them means editing a working copy under concurrent-write guards and re-running the pytest
  suite (`tests/test_apply_race.py`, `tests/test_cycle_continuity.py` and the route-coverage one at
  minimum), which is a product change and not mine to make unreviewed on a design branch.
* `webapp_apply_edits.py` block C (the `/rewrite` producer filter) is also a one-line change to the
  route above `/edits/apply` — same reasoning.

Both were applied on 2026-10-03, with the suite and the guards above re-run — see the end.

---

## Observed on a live desk BEFORE the guard (2026-10-03) — what happened instead

The claim above ("a stale proposal is applied to text that has moved") deserves the sharper version,
measured rather than reasoned. Against the running desk with the writer's own 28-page script:

```
POST /edits/apply  {scene_number: 6, replacements: [{old: "Comic books chaduthu, …", new: "…"}]}
  → 1st call: {applied: [{old, new, similarity}], skipped: []}
  → 2nd call, identical body, the line now moved:
       {applied: [], skipped: [{old, new, reason: "line not found in scene"}]}   ← HTTP 200
```

So the desk's actual behaviour is **not** a silent wrong write and **not** a refusal: the replacement
is *skipped*, with a reason, and the answer is a 200. That is honest, and the page already reads it —
`applyReport` says **"0 applied, 1 skipped — line not found in scene"**, and the caller no longer
claims "Line N changed" when nothing did (fixed in `ea8e1ca`).

**What this costs:** the prototype's dedicated refusal state — `row[data-cast="stale"]`, the sentence
kept in the fold until the writer answers it, `refuseStale()` — is **unreachable against the real
desk**, because it is wired to an error the desk does not raise. It fires in the offline build only
(the `#drift` seam simulates it). So today the writer gets a *skip message* where the design promised
a *refusal*: same information, weaker placement, and nothing persisted until they act.

Either resolution is defensible and both are one change:

1. **Apply this patch** — the refusal becomes a first-class state, the trap frame's whole reason for
   existing holds, and `refuseStale()` stops being dead code in production. This is what the
   prototype was designed against.
2. **Or retire the stale state** in the page and keep the skip message, which is honest as-is — and
   delete `refuseStale()` rather than leaving a path that can never run.

What is **not** acceptable is the current arrangement: a UI state that exists, is tested offline, and
cannot happen in the product. That is the same defect class as the 0 px mark and the hollow quotes —
a claim in the interface that no data backs.

---

## Applied (2026-10-03) — what changed, and the same probe re-run

**The guard.** `revision.py` gains `STALE_PROPOSAL_MESSAGE`, `StaleProposalError`, `_still_holds`,
`_assert_proposal_is_fresh` and `proposal_is_landable`. `apply_edit` verifies every frame **inside**
the same `lock_for('working.json')` section that mutates it — a pre-check in the route would read
outside the lock and race the very write it protects (BE-1) — and raises before anything moves.

**Whole-value equality at every granularity, never containment.** A writer who types `!` onto the
proposed line leaves the old text as an exact substring; a substring test passes there, and the frame
commits over a line the writer had just changed. No strip, no case-fold, no normalisation anywhere: a
whitespace difference IS the manual edit this exists to catch. The run window covers only proposals
the model copied across a line break.

**The route** answers `400 {"error": …, "stale": true}` per the contract above, and **the producer**
shows only the candidates `proposal_is_landable` accepts. Both halves answer from `_still_holds`, so
the desk can neither offer a proposal the apply path refuses nor accept one the writer has outrun.

**The client half, which the browser suite found.** Turning a silent skip into a refusal exposed
that `applyOneRewrite`'s catch only wrote the status line: a refused row kept a live, checked
checkbox and rode the next bulk Apply (`cb.checked && !cb.disabled`), so the desk went on offering an
Apply that could never land. `tests/e2e_browser_rewrite_loop.py` caught it — its crafted
`ZZZ-NO-SUCH-LINE-*` frames are absent from the fixture by design, so every individual apply there is
a refusal — 40/43 on the guard commit, 43/43 once fixed, with the three failing checks watched
failing. `app.js` now carries `stale` on the api error beside `stillWorking` (the caller decides from
the flag, never by matching the sentence), marks the refused row `rewrite-candidate-stale` and removes
its actions; the sentence stays on screen unprefixed by a generic "Apply failed:".

**Tests and gates.** `tests/test_stale_proposal_guard.py` — 12 tests over the predicate, the route
contract and the producer filter. Full pytest `1987 passed / 4 skipped`; the one intermittent failure
is `tests/test_apply_race.py`'s overlap assertion, measured **pre-existing at the same rate on the
parent commit** (5/20 vs 5/20 failed, 20 interleaved runs each way on a 2-core box), so it is not a
consequence of this change. Browser suites: rewrite_loop 43/43, phase14 47/47, desk_controls 41/41,
two_contexts 8/8; `node --test tests/js/core.test.js` 16/16; ruff clean.

### The same probe, re-run against the running desk

Same project, same route, capability token sent. The before-state is the section above:

```
POST /api/projects/Pain_3/edits/apply
  {"scene_number": 6, "replacements": [{old: "akkada kindha godaki lean iyyi untaadu eyes half close open",
                                        new: "… open [probe]"}]}

  1st          → 200  {"applied": [{…, "similarity": 1.0}], "skipped": []}
  2nd, the SAME body, the line now holding its own new text
               → 400  {"error": "Stale proposal: the text was modified manually.", "stale": true}
```

where the recorded behaviour was `200 {"applied": [], "skipped": [{reason: "line not found in
scene"}]}`.

Two things that probe pins beyond the status code:

* **The old text is still a SUBSTRING of the new line** — the new value is the old one plus ` [probe]`
  — and the frame is refused anyway. The containment trap, measured rather than reasoned.
* **The refusal is whole.** A call carrying one fresh frame and one stale frame answers 400 and writes
  nothing: the fresh frame's line is unchanged and `working.json`'s digest is identical before and
  after.

### Still open

* **A bulk refusal cannot name the row.** The guard refuses the transaction and answers with one
  sentence for every frame, so a bulk Apply that refuses cannot say WHICH row went stale. Per-row
  marking on that path needs the frame in the error body — a contract change, deliberately not made
  here.
* **The prototype's own trap frame has not been re-observed in a browser.** The desk now answers the
  contract `refuseStale()` is wired to, so the state is reachable in production; this pass verified
  the desk's half (above) and the product modal's half (the suite), not the prototype's frame.
