# gap_harness

The loop that closes gaps in `GAP_REGISTER_AND_EXECUTION_PLAN.md` without
re-discovering the same context every turn.

```bash
python tools/gap_harness/loop.py status         # where we are
python tools/gap_harness/close_gap.py next      # the next gap to work
python tools/gap_harness/close_gap.py start 35  # claim it, print the checklist
python tools/gap_harness/close_gap.py check 35  # gate: is it actually done?
python tools/gap_harness/loop.py run --target 90
```

`RUNBOOK.md` is the baton passed between turns — read it first.

## What the gate actually enforces

A gap cannot be reported closed unless, on disk:

| Check | Catches |
|---|---|
| entry row says FIXED | the "I'll update the docs later" drift |
| plan entry carries a FIXED tail | one register updated, not three |
| critique has a section naming the gap | self-review skipped (a standing instruction) |
| revert counts stated, **all non-zero** | a test that passes with the fix reverted |
| exactly one plan entry for the gap | the duplicated-block edit that once added 336 lines |
| a test file changed | a fix with no test |
| ruff clean, gap tests pass, suite has no *unexpected* failure | regressions hidden in the three known readiness failures |
| diffstat proportionate, no `.md` with >400 changed lines | runaway edits |

It is deliberately killable: `--fast` skips the suite and the tests for a quick
look, and prints exactly what it skipped.

## What it cannot do

* It cannot trigger the next turn. Nothing in a repo can. It makes each turn
  cheap to resume instead.
* It cannot judge *whether the reproduction was the right one*, or whether the
  fix is at the root. That is the agent's job, described in `RUNBOOK.md`.
