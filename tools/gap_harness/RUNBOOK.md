# RUNBOOK — the baton passed between turns

This file is the instruction I hand my next self. It exists because each turn
was starting with a five-to-ten-call survey of the registers, and because I have
twice declared a fix verified on weaker evidence than I claimed.

The machine half lives in `tools/gap_harness/close_gap.py`. The judgement half
is below, and it cannot be automated: reproducing the right thing, picking the
root cause, and knowing which line to revert.

---

## Turn budget, honestly

I cannot trigger myself. A turn ends when my tool-call budget runs out, and only
the user can start the next one. What I *can* do is make each turn cheap to
resume and dense with work:

* **Reality: one turn ≈ one to three gaps**, if each gap is small. Gap 30 took a
  whole turn because the fix turned out to be structural. Most are like 26/27.
* **Never spend more than ~4 calls rediscovering state.** The harness holds it.

## First four calls of a turn — always these, in this order

```bash
python tools/gap_harness/loop.py status          # where we are, what's in flight
python tools/gap_harness/close_gap.py next       # the gap to work
python tools/gap_harness/close_gap.py start N    # claim it, print the checklist
# then ONE batched call to read only what gap N needs
```

If `status` says something is **IN FLIGHT**, finish that before starting
anything new. An unverified claim left behind is worse than never claiming.

## Per gap

1. **Reproduce.** Write a throwaway probe to `/tmp/probe_<n>.py`, run it, and
   paste the actual numbers into the commit message later. If it does not
   reproduce, stop and re-derive the severity — the filed shape has been wrong
   for gaps 5, 16, 19 and 30, and better-than-filed for 19.
2. **Fix at the root.** Write down what the real cause was. For gap 30 the
   filed cause ("not a hard bound") was wrong and the real one ("bounded one
   function of six") changed the fix.
3. **Pin.** Tests must fail when the fix is reverted. Verify by reverting:
   * batch all reverts into ONE call
   * verify each patch actually applied (`grep -c` the marker) — a silent
     no-op replacement once made me report "0 failures" three times
   * read the real pytest summary line, never `grep -c FAILED` (a collection
     error produces no FAILED line and reads as a clean zero)
   * restore, then confirm the tests pass again
4. **Suite.** `ruff check .` then the full suite with `-B`. Expect exactly the
   three readiness failures; anything else is mine.
5. **Registers.** Three files, one call: entry row → FIXED (with the measurement
   and the revert counts), plan entry → FIXED tail, critique → one new §. The
   critique section must include what *I* got wrong, not just what the code did.
6. **Gate.** `close_gap.py check N` must exit 0.
7. **Commit and push** — one gap, one commit.

## Traps this project has actually sprung

* **A stale `__pycache__` made a revert lie.** Always `pytest -B`.
* **`/tmp/struct.py` shadowed the stdlib `struct`** because the script's own
  directory is on `sys.path`. Never name a temp file after a stdlib module.
* **Register edits that duplicate blocks.** One stray write appended entries
  25–32 and I committed it. Check `git show --stat` for absurd shape and
  `grep -c "^\*\*N\. "` for duplicate entries. `close_gap.py` checks this now.
* **`PromptBudgetUnreachable` semantics:** a budget of `0` means *unlimited*.
  Any helper that can return 0 has reintroduced the bug it was built to fix.
* **A test that passes with the fix reverted is inert.** Three of these have
  reached the suite; the revert matrix is the only thing that catches them.
* **Grade is the THIRD cell** of `ENTRY_GRADE_TABLE.md`, and rows can carry a
  re-derived grade (`**A**, consequence **C**`). Reading cell 2 made gap 22
  look open for weeks.
* **Trade-offs are not work.** `is_trade_off` rows need a decision recorded, not
  another investigation.

## Stop conditions

Do not stop to ask for confirmation between gaps — the user has said so
explicitly. Stop, and say so plainly, only when:

1. **grade-A closure ≥ 90%**, or
2. **a gap needs a product decision** (which trade-off to take, which behaviour
   a writer should see) — that is the user's call, not mine, or
3. **a fix would change user-visible behaviour** in a way the register does not
   settle, or
4. the turn budget is nearly gone: then commit what is finished, and leave the
   resume packet from `loop.py run` as the last thing I say.

## What "done" is not

Done is not "the tests pass". Done is: reproduced, fixed at the root, pinned by
tests that fail without the fix, registers honest, and the self-critique records
the mistakes. Everything else is a draft.
