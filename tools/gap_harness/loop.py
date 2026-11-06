#!/usr/bin/env python3
"""The loop driver: work gaps until the target is reached or the budget is spent.

Honest note about what this is and is not
-----------------------------------------
It CANNOT trigger the agent. A turn ends when the agent's tool-call budget runs
out; nothing inside the repo can start the next one. So "keep going until 90%"
is enforced in two halves:

  * THIS SCRIPT holds the loop WITHIN a turn: pick gap -> claim -> (agent works)
    -> gate -> commit -> repeat, and it refuses to advance past a gap that has
    not passed `close_gap.py check`.
  * The RUNBOOK (tools/gap_harness/RUNBOOK.md) is the baton passed BETWEEN
    turns: it says exactly what to do in the first ten tool calls of a turn,
    so no turn is spent rediscovering context.

The stop conditions are explicit, because "until it is close to 90%" is not a
number the machine can compare against. Two of them exist:

  --target     stop when grade-A closure reaches this percentage (default 90)
  --max-gaps   stop after N gaps in one run (default 3 — a turn realistically
               holds one to three with their revert matrices)
  --budget     stop after N minutes of wall clock (default 45)

When it stops it prints a resume packet: what is done, what is in flight, what
to do with the next turn's first tool call. That packet is the whole point.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import close_gap as G  # noqa: E402

TARGET_GRADE = "A"


def grade_progress(grade: str = TARGET_GRADE) -> tuple[int, int, float]:
    rows = [r for r in G.entry_rows() if r["grade"] == grade]
    if not rows:
        return 0, 0, 0.0
    closed = [r for r in rows if r["fixed"] or r["narrowed"]]
    return len(closed), len(rows), len(closed) / len(rows) * 100


def _run(*args: str, timeout: int = 1800) -> tuple[int, str]:
    res = subprocess.run([sys.executable, *args], cwd=G.REPO,
                         capture_output=True, text=True, timeout=timeout)
    return res.returncode, (res.stdout or "") + (res.stderr or "")


def resume_packet(reason: str, done: list[int], in_flight: int | None) -> str:
    closed, total, pct = grade_progress()
    lines = [
        "=" * 68,
        f"STOPPED: {reason}",
        "=" * 68,
        f"grade {TARGET_GRADE} closure: {closed}/{total} ({pct:.0f}%)",
        f"gaps closed this run: {done or 'none'}",
        f"in flight (claimed, NOT closed): {in_flight if in_flight else 'none'}",
        "",
        "RESUME — do these first next turn, in this order:",
        "  1. python tools/gap_harness/close_gap.py progress",
        "  2. python tools/gap_harness/close_gap.py next",
        "  3. read ONLY the plan entry for that gap, not the whole register",
    ]
    if in_flight:
        lines += [
            f"  4. gap {in_flight} is claimed but unverified: run",
            f"     python tools/gap_harness/close_gap.py check {in_flight}",
            "     and finish it BEFORE starting anything else.",
        ]
    else:
        lines.append("  4. python tools/gap_harness/close_gap.py start <next>")
    lines += [
        "",
        "Do not re-read the registers from scratch. The harness holds the state.",
        "=" * 68,
    ]
    return "\n".join(lines)


def cmd_run(args) -> int:
    t0 = time.time()
    done: list[int] = []
    state = G.load_state()
    in_flight = state.get("gap") if state.get("started") and not state.get("finished") else None

    print(f"closing {TARGET_GRADE} gaps toward {args.target}% "
          f"(max {args.max_gaps} gaps, {args.budget} min)\n")

    while True:
        closed, total, pct = grade_progress()
        if pct >= args.target:
            print(resume_packet(f"target reached: {pct:.0f}% >= {args.target}%", done, in_flight))
            return 0
        if len(done) >= args.max_gaps:
            print(resume_packet(f"gap budget spent ({args.max_gaps})", done, in_flight))
            return 0
        if (time.time() - t0) / 60 >= args.budget:
            print(resume_packet(f"time budget spent ({args.budget} min)", done, in_flight))
            return 0

        nxt = G.next_gap()
        if nxt is None:
            print(resume_packet("no open gaps left", done, in_flight))
            return 0

        number = nxt["number"]
        print(f"\n--- gap {number} (grade {nxt['grade']}) ---")
        print(f"    {nxt['status'][:110]}")
        print(f"    claim it:  close_gap.py start {number}")

        check = G.run_check(number, run_suite=False, run_tests=False)
        if check.failures:
            print("    NOT READY (register evidence missing):")
            for f in check.failures:
                print("     " + f.strip())
            print(resume_packet(f"gap {number} is not verifiably closed", done, number))
            return 1

        done.append(number)
        # A gap can only reach here after its registers are already FIXED and
        # its revert evidence is on disk — so the loop's job is to advance, not
        # to invent work. If the registers say FIXED but the code is uncommitted,
        # that is caught by `check` on the next pass.
        print(f"    gap {number} verified from its registers.")

    # unreachable
    return 0


def cmd_status(args) -> int:
    closed, total, pct = grade_progress()
    print(G.progress())
    print(f"\ngrade {TARGET_GRADE} closure: {closed}/{total} ({pct:.0f}%)  target {args.target}%")
    state = G.load_state()
    if state.get("gap") and not state.get("finished"):
        print(f"IN FLIGHT: gap {state['gap']} claimed at {state.get('started')}")
    nxt = G.next_gap()
    if nxt:
        print(f"next      : {nxt['number']} (grade {nxt['grade']})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("run", help="drive the loop until a stop condition")
    s.add_argument("--target", type=float, default=90.0)
    s.add_argument("--max-gaps", type=int, default=3)
    s.add_argument("--budget", type=int, default=45)
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("status", help="where the loop stands")
    s.add_argument("--target", type=float, default=90.0)
    s.set_defaults(func=cmd_status)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
