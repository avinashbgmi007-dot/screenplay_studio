#!/usr/bin/env python3
"""The gap-closing gate.

This exists because the loop I was running by hand had no memory and no
gate: each turn began by re-reading the registers, and a gap could be
declared fixed on the strength of being *probably* fixed. Both are expensive
and one of them is dishonest.

What it does
------------
    close_gap.py start 35      claim a gap: refuse if it is not open, print the
                              definition of done, record the claim on disk
    close_gap.py check 35      verify EVERY step: tests pass, they fail when the
                              fix is reverted (counts stated and non-zero), the
                              three registers say FIXED, the diff is sane
    close_gap.py progress      how far along the register is, by grade
    close_gap.py next          the next gap to work, in grade-A-first order

It cannot make me work, and it cannot verify a revert matrix on its own — that
needs a human-or-agent judgement about WHICH line to revert. What it can do is
refuse to let a gap be marked closed without the evidence being on disk and
well-formed, and it can catch the specific mistakes this project has actually
made:

  * a test that cannot fail (the check requires a stated revert count, and
    rejects zero, because "the revert changed nothing" means the test is inert)
  * a register edit that duplicates 336 lines (duplicate-entry check)
  * a FIXED claim with no critique entry (the user's standing instruction)
  * an absurd diffstat (a one-row register edit cannot add 338 lines)

Exit code is 0 only when every step passes, so it can gate a commit.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STATE = REPO / ".agent_state.json"
ENTRY_TABLE = REPO / "ENTRY_GRADE_TABLE.md"
PLAN = REPO / "GAP_REGISTER_AND_EXECUTION_PLAN.md"
CRITIQUE = REPO / "SELF_CRITIQUE_OF_GAP_REGISTER.md"

GRADE_ORDER = ["A", "B", "C", "D", "W"]


# ---------------------------------------------------------------------------
# register parsing
# ---------------------------------------------------------------------------

def _re_derived_grade(cell: str) -> str:
    """The grade the entry now claims, honouring a documented re-derivation.

    Some rows read `**A**, consequence **C**`: the filing was A, but measuring it
    downgraded the consequence to C. Sorting by the stale A works a closed
    argument again — that is how gap 9 came out first in my own queue. The LAST
    documented grade wins, because entries are re-derived in place.
    """
    found = re.findall(r"\*\*([ABCDW])\*\*", cell)
    return found[-1] if found else cell.strip("* ").split("**")[0].strip()


def entry_rows() -> list[dict]:
    """Every numbered row of ENTRY_GRADE_TABLE.md.

    The grade is the THIRD markdown cell. Reading the second cell instead is
    what made gap 22 look open for weeks.
    """
    rows = []
    if not ENTRY_TABLE.exists():
        return rows
    for line in ENTRY_TABLE.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 6:
            continue
        num = cells[1].strip()
        if not num.isdigit():
            continue
        status = cells[4]
        rows.append({
            "number": int(num),
            "grade": _re_derived_grade(cells[2]),
            "filed": cells[3],
            "status": status,
            "fixed": "FIXED" in status,
            "narrowed": "NARROWED" in status,
        })
    return rows


# A row can be closed in substance without carrying the word FIXED: the
# trade-offs, where the defect is real and the decision is to keep it. Gap 22 is
# the case that taught the register this — it was worked twice before anyone
# noticed the row already said "known trade-off, still tested".
TRADE_OFF_MARKERS = ("known trade-off", "documented trade-off", "trade-off,",
                     "by design", "wontfix", "won't fix")


def is_trade_off(row: dict) -> bool:
    blob = (row["status"] + " " + row["filed"]).lower()
    return any(m in blob for m in TRADE_OFF_MARKERS)


def is_open(row: dict) -> bool:
    """Open for WORK. A trade-off is not work — it is a decision to re-verify."""
    return not row["fixed"] and not is_trade_off(row)


def needs_decision(row: dict) -> bool:
    """Closed in substance, but the register has not recorded that yet."""
    return is_trade_off(row) and not row["fixed"]


def progress() -> str:
    rows = entry_rows()
    if not rows:
        return "no entries found"
    fixed = [r for r in rows if r["fixed"]]
    narrowed = [r for r in rows if r["narrowed"] and not r["fixed"]]
    open_rows = [r for r in rows if is_open(r) and not r["narrowed"]]
    trade_offs = [r for r in rows if needs_decision(r)]
    out = [f"total entries : {len(rows)}",
           f"fixed         : {len(fixed)}  ({len(fixed) / len(rows) * 100:.1f}%)",
           f"narrowed      : {len(narrowed)}",
           f"open          : {len(open_rows)}",
           f"trade-offs    : {len(trade_offs)}"
           + (f"  (rows {[r['number'] for r in trade_offs]})" if trade_offs else ""),
           ""]
    by_grade = Counter(r["grade"] for r in rows)
    fixed_by = Counter(r["grade"] for r in fixed)
    for g in GRADE_ORDER:
        if not by_grade[g]:
            continue
        pct = fixed_by[g] / by_grade[g] * 100
        out.append(f"  grade {g}: {fixed_by[g]:2d}/{by_grade[g]:2d} closed ({pct:4.0f}%)")
    return "\n".join(out)


def next_gap() -> dict | None:
    """The next open gap, grade-A first, then by number (register order)."""
    rows = [r for r in entry_rows()
            if is_open(r) and not r["narrowed"] and r["grade"] in GRADE_ORDER]
    if not rows:
        return None

    def key(r):
        return (GRADE_ORDER.index(r["grade"]), r["number"])
    return sorted(rows, key=key)[0]


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# the definition of done, in the order that prevents rework
# ---------------------------------------------------------------------------

DEFINITION_OF_DONE = """\
1. REPRODUCE   a runnable measurement of the filed defect, before touching code.
               If it does not reproduce, say so and re-derive the severity —
               the filed shape has been wrong before (gaps 5, 16, 19, 22, 30).
2. FIX         at the ROOT, not at the symptom. Write down what the actual
               cause was, because it is often not the filed cause.
3. PIN         tests that FAIL when the fix is reverted. Verify by reverting:
               batch the reverts, count the failures per revert, restore.
               A revert that changes nothing means the test is inert.
4. SUITE       ruff clean + full suite green (3 known readiness failures are
               pre-existing and unrelated: CI timeout declarations).
5. REGISTERS   ENTRY_GRADE_TABLE row -> FIXED with the measurement and reverts;
               GAP_REGISTER plan entry -> FIXED tail; critique -> one new §.
6. REVIEW      `close_gap.py check N` must pass, self-review section written.
7. COMMIT      one commit per gap, message says what was MEASURED, what was
               actually wrong, and what I got wrong on the way.
"""


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

class Check:
    def __init__(self):
        self.failures: list[str] = []
        self.notes: list[str] = []

    def ok(self, label: str, detail: str = ""):
        self.notes.append(f"  PASS  {label}" + (f" — {detail}" if detail else ""))

    def fail(self, label: str, detail: str = ""):
        self.failures.append(f"  FAIL  {label}" + (f" — {detail}" if detail else ""))

    def require(self, cond: bool, label: str, detail: str = ""):
        (self.ok if cond else self.fail)(label, detail)
        return cond


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                              text=True, timeout=120).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _changed_files(number: int | None = None) -> list[str]:
    """Files touched since the last commit, plus untracked ones.

    The working tree is the normal case, but a gap can also already be
    COMMITTED when the gate runs — and then this returned nothing, so the gate
    reported "nothing under tests/ has changed" for a fully finished gap. That
    happened for gap 54, which was committed first on purpose: an earlier
    sandbox reset had thrown away an uncommitted gap, so committing early was
    the safer order. A checker that punishes the safe order is a broken checker.

    So HEAD is included too — but ONLY when HEAD's own commit is this gap
    (its subject names the gap number). Otherwise the previous gap's files
    would satisfy this gap's checks, which is the false pass this gate exists
    to prevent.
    """
    out = _git("status", "--porcelain")
    files = []
    for line in out.splitlines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ")[-1]
        if path:
            files.append(path)
    if number is not None:
        # Look back a few commits, not just HEAD: a gap's work legitimately
        # spans more than one (the fix, then its measured revert counts), and
        # keying only on HEAD failed gap 59 after exactly that second commit.
        # Still scoped — a commit only counts if its subject names THIS gap
        # number, so the previous gap's tests cannot satisfy this gap's checks.
        recent = _git("log", "-8", "--pretty=%s%x00%H")
        for row in (recent or "").splitlines():
            if "\x00" not in row:
                continue
            subject, sha = row.split("\x00", 1)
            if re.search(rf"\b[Gg]aps?\b.*\b{number}\b", subject):
                committed = _git("show", "--pretty=format:", "--name-only", sha.strip())
                files += [ln.strip() for ln in committed.splitlines() if ln.strip()]
    return list(dict.fromkeys(files))


def _critique_section(number: int) -> str:
    """The critique section that discusses this gap, by number."""
    if not CRITIQUE.exists():
        return ""
    text = CRITIQUE.read_text(encoding="utf-8")
    sections = re.split(r"\n## §", text)
    # Prefer a section whose HEADING names this gap. Falling straight to "any
    # mention" picked a much older section that merely talked about gap 6 in
    # passing, so the revert counts and the reasoning in the real section were
    # invisible to the gate. Most recent heading wins.
    head = [sec for sec in sections
            if re.match(rf"\d+\s*—\s*Gaps?\s+.*\b{number}\b", sec)]
    if head:
        return head[-1]
    for sec in sections:
        # "Gap 44" or "Gaps 44 + 77": a combined section covers both numbers.
        if re.search(rf"Gaps?\s+.*\b{number}\b", sec):
            return sec
    return ""


def _plan_entry(number: int) -> str:
    if not PLAN.exists():
        return ""
    text = PLAN.read_text(encoding="utf-8")
    # Two shapes, both real: 15+ are `**N. paragraph**`, 1-14 are table rows.
    # Reading only the paragraph form left `plan_entry` empty for the table, so
    # the FIXED-tail check failed a gap whose tail was right there in the row.
    m = re.search(rf"^\*\*{number}\. .*$", text, re.M)
    if m:
        return m.group(0)
    # Table rows come in two weights: the bolded `| **6** |` summary table and
    # the plain `| 22 |` trade-off table further up the file.
    for pattern in (rf"^\| \*\*{number}\*\* \|.*$", rf"^\| {number} \|.*$"):
        m = re.search(pattern, text, re.M)
        if m:
            return m.group(0)
    return ""


def run_check(number: int, run_suite: bool = True, run_tests: bool = True) -> Check:
    c = Check()
    rows = {r["number"]: r for r in entry_rows()}
    row = rows.get(number)
    c.require(row is not None, f"entry {number} exists in ENTRY_GRADE_TABLE")
    if row is None:
        return c

    # --- 5. registers -----------------------------------------------------
    c.require(row["fixed"], f"entry table row {number} says FIXED",
              "status: " + row["status"][:70])

    plan_entry = _plan_entry(number)
    c.require("FIXED" in plan_entry, f"plan entry {number} carries a FIXED tail")

    section = _critique_section(number)
    c.require(bool(section), f"critique has a section about gap {number}",
              "the standing instruction is that self-critique is recorded, not glossed")

    # Revert evidence: stated and non-zero. This is the honesty gate — a zero
    # means the "pin" does not actually pin anything.
    # Match "Reverts: 5 / 4 / 1", "reverts 5, 4 and 1", "Reverts: **5 / 4**".
    # My first pattern stopped at the first asterisk, so a bolded count was
    # invisible and the gate failed a gap that had stated its reverts.
    blob = (section or "") + " " + (plan_entry or "")
    reverts = re.findall(r"[Rr]everts?\s*:?[\s*]*([0-9][0-9\s/*\u2013,-]*)", blob)
    numbers: list[int] = []
    for blob in reverts:
        numbers.extend(int(n) for n in re.findall(r"\d+", blob))
    c.require(bool(numbers), f"gap {number} states its revert counts",
              "no 'Reverts: a / b / c' line found in the critique or plan")
    if numbers:
        c.require(all(n > 0 for n in numbers),
                  f"gap {number} revert counts are all non-zero",
                  f"counts {numbers} — a zero means that fix is not pinned by any test")

    # Duplicate plan entries — the bug that once added 336 lines.
    if PLAN.exists():
        plan_text = PLAN.read_text(encoding="utf-8")
        # Entries 1-14 are table rows (`| **6** | ... |`); 15+ are `**N. ...**`
        # paragraphs. Counting only the paragraph form reported "found 0" for a
        # gap that is right there in the table, so both forms are counted and a
        # plan holding one of either is a single entry.
        count = max(
            len(re.findall(rf"^\*\*{number}\. ", plan_text, re.M)),
            len(re.findall(rf"^\| \*\*{number}\*\* \|", plan_text, re.M)),
            len(re.findall(rf"^\| {number} \|", plan_text, re.M)))
        c.require(count == 1, f"plan has exactly one entry {number}", f"found {count}")

    # --- 3. tests that exist ---------------------------------------------
    changed = _changed_files(number)
    test_files = [f for f in changed
                  if f.startswith("tests/") and f.endswith(".py")
                  and os.path.basename(f).startswith("test_")]
    c.require(bool(test_files), "a test file was added or changed",
              ", ".join(test_files) if test_files else "nothing under tests/ has changed")

    # --- 4. ruff + suite --------------------------------------------------
    ruff = subprocess.run([sys.executable, "-m", "ruff", "check", "."],
                          cwd=REPO, capture_output=True, text=True, timeout=600)
    c.require(ruff.returncode == 0, "ruff clean",
              (ruff.stdout or "").strip().splitlines()[-1] if ruff.stdout.strip() else "")

    if run_tests and test_files:
        cmd = [sys.executable, "-B", "-m", "pytest", *test_files,
               "-q", "-p", "no:logging", "--tb=no"]
        res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=1800)
        tail = (res.stdout or "").strip().splitlines()[-1] if res.stdout.strip() else ""
        c.require(res.returncode == 0, "the gap's own tests pass", tail)

    if run_suite:
        cmd = [sys.executable, "-B", "-m", "pytest", "tests/", "-q",
               "-p", "no:logging", "--tb=no", "-rf"]
        res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=1800)
        tail = (res.stdout or "").strip().splitlines()[-1] if res.stdout.strip() else ""
        # The three readiness failures are pre-existing and unrelated.
        known = {"test_every_ci_job_declares_a_timeout",
                 "test_unbounded_network_steps_declare_a_timeout",
                 "test_the_timeout_guards_reject_an_inert_declaration"}
        got = set(re.findall(r"FAILED [^:]+::(\w+)", res.stdout or ""))
        unexpected = got - known
        # Guard against the detector itself going inert: if the summary says
        # failures happened but no names were parsed, the sets are both empty
        # and "no unexpected failures" would be vacuously true. That is exactly
        # the class of bug this harness exists to catch, so it is checked here.
        n_failed = int((re.search(r"(\d+) failed", tail) or [0, 0])[1]) \
            if re.search(r"(\d+) failed", tail) else 0
        names_parsed = len(got)
        c.require(names_parsed >= n_failed,
                  "the failure names were actually parsed",
                  f"summary says {n_failed} failed, parsed {names_parsed}")
        c.require(not unexpected, "full suite has no unexpected failures",
                  (tail or "no summary")
                  + (f" ; unexpected: {sorted(unexpected)}" if unexpected else ""))

    # --- diffstat sanity --------------------------------------------------
    stat = _git("diff", "--cached", "--stat")
    if not stat.strip():
        stat = _git("diff", "--stat")
    total = 0
    for m in re.finditer(r"\|\s+(\d+) [+-]+", stat):
        total += int(m.group(1))
    if total:
        c.require(total < 2500, "diffstat is proportionate", f"{total} changed lines")
        for m in re.finditer(r"(\S+)\s+\|\s+(\d+)", stat):
            path, n = m.group(1), int(m.group(2))
            if path.endswith(".md") and n > 400:
                c.fail("register edit is not absurdly large",
                       f"{path} shows {n} changed lines — check for a duplicated block")

    return c


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_start(args) -> int:
    rows = {r["number"]: r for r in entry_rows()}
    row = rows.get(args.gap)
    if row is None:
        print(f"no entry {args.gap} in {ENTRY_TABLE.name}")
        return 2
    if row["fixed"]:
        print(f"gap {args.gap} is already FIXED — check the next one:")
        nxt = next_gap()
        print(f"  next: {nxt['number']} (grade {nxt['grade']})" if nxt else "  none left")
        return 2

    state = load_state()
    state["gap"] = args.gap
    state["started"] = _now()
    state["finished"] = None
    state["grade"] = row["grade"]
    save_state(state)

    print(f"GAP {args.gap}  (grade {row['grade']})")
    print(f"  filed: {row['filed']}")
    print(f"  says : {row['status'][:200]}")
    print()
    print(DEFINITION_OF_DONE)
    print(f"when done:  python tools/gap_harness/close_gap.py check {args.gap}")
    return 0


def cmd_check(args) -> int:
    number = args.gap or load_state().get("gap")
    if not number:
        print("no gap given and none claimed — run `start N` first")
        return 2
    print(f"checking gap {number}\n")
    c = run_check(int(number), run_suite=not args.fast, run_tests=not args.fast)
    print("\n".join(c.notes))
    if c.failures:
        print()
        print("\n".join(c.failures))
        print(f"\n{len(c.failures)} check(s) failed — the gap is not done.")
        return 1
    state = load_state()
    if int(state.get("gap") or 0) == int(number):
        state["finished"] = _now()
        save_state(state)
    print(f"\nall checks passed for gap {number}. Commit it.")
    return 0


def cmd_progress(args) -> int:
    print(progress())
    nxt = next_gap()
    if nxt:
        print(f"\nnext: {nxt['number']} (grade {nxt['grade']}) — {nxt['status'][:90]}")
    return 0


def cmd_next(args) -> int:
    nxt = next_gap()
    if not nxt:
        print("nothing open")
        return 0
    print(f"{nxt['number']}\t{nxt['grade']}\t{nxt['status'][:140]}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start", help="claim a gap and print the definition of done")
    s.add_argument("gap", type=int)
    s.set_defaults(func=cmd_start)

    s = sub.add_parser("check", help="verify every step for a gap")
    s.add_argument("gap", type=int, nargs="?")
    s.add_argument("--fast", action="store_true", help="skip the suite and the tests")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("progress", help="closing percentage by grade")
    s.set_defaults(func=cmd_progress)

    s = sub.add_parser("next", help="the next gap to work")
    s.set_defaults(func=cmd_next)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
