# Backend halves the Ink Layer's refusal path depends on (NOT APPLIED)

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

## The one decision these documents are blocked on

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

## Status

* Not applied to `screenplay_studio/revision.py` or `screenplay_studio/webapp_server.py` by me.
  Applying them means editing a working copy under concurrent-write guards and re-running the pytest
  suite (`tests/test_apply_race.py`, `tests/test_cycle_continuity.py` and the route-coverage one at
  minimum), which is a product change and not mine to make unreviewed on a design branch.
* `webapp_apply_edits.py` block C (the `/rewrite` producer filter) is also a one-line change to the
  route above `/edits/apply` — same reasoning.
