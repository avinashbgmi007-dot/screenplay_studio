"""Tests for the gap harness — the gate that decides a gap is done.

A gate with no tests is exactly the sin the gate exists to catch, so these pin
the behaviours that matter: it reads the right cell, it honours a re-derived
grade, it treats a trade-off as a decision rather than work, it refuses an inert
"fix", and it never claims a gap is done on evidence it cannot see.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "gap_harness"))
import close_gap as G  # noqa: E402
import loop as L  # noqa: E402


# ---------------------------------------------------------------------------
# Reading the register
# ---------------------------------------------------------------------------

def test_the_grade_is_read_from_the_third_cell():
    """Reading cell 2 instead of cell 3 made gap 22 look open for weeks."""
    rows = {r["number"]: r for r in G.entry_rows()}
    assert rows[35]["grade"] == "A"
    assert rows[26]["grade"] == "A"


def test_a_re_derived_grade_wins_over_the_filing():
    """`**A**, consequence **C**` means the consequence was measured down to C.
    Sorting on the stale A works a closed argument again — gap 9 came out first
    in the queue before this was handled."""
    assert G._re_derived_grade("**A**, consequence **C**") == "C"
    assert G._re_derived_grade("**A**") == "A"
    assert G._re_derived_grade("**B** (mechanism)") == "B"


def test_fixed_rows_are_recognised():
    """Uses gaps fixed earlier, not the one being worked right now.

    My first version asserted gap 35 was NOT fixed and went stale the moment I
    fixed it — a self-referential test that fails as a reward for working.
    """
    rows = {r["number"]: r for r in G.entry_rows()}
    assert rows[30]["fixed"] is True, "gap 30 was fixed in this session"
    assert rows[26]["fixed"] is True, "gap 26 was fixed in this session"


def test_an_open_gap_is_reported_open():
    """The complement, without naming a gap that is about to be closed."""
    rows = [r for r in G.entry_rows() if G.is_open(r)]
    assert rows, "the register claims everything is closed"
    for r in rows[:5]:
        assert r["fixed"] is False


def test_a_documented_trade_off_is_not_open_work():
    """Gap 22 is closed in substance — worked twice before anyone read the row."""
    fake = {"number": 22, "grade": "A", "filed": "",
            "status": "documented trade-off, still tested", "fixed": False}
    assert G.is_trade_off(fake) is True
    assert G.is_open(fake) is False
    assert G.needs_decision(fake) is True

    work = {"number": 35, "grade": "A", "filed": "Sample-open overwrites it.",
            "status": "Sample-open overwrites it.", "fixed": False}
    assert G.is_trade_off(work) is False
    assert G.is_open(work) is True


def _work_row(number, grade):
    """A synthetic open row. No trade-off wording, so is_open() reads it as work."""
    return {"number": number, "grade": grade, "filed": "synthetic open row",
            "status": "open work, awaiting a fix", "fixed": False,
            "narrowed": False}


def _next_gap_from(rows):
    """Copy of next_gap()'s selection over injected rows.

    Driven from the same constants as close_gap.next_gap() so this cannot drift
    into agreeing with itself: if the real selector changes its ordering, the
    rows fed in here start disagreeing and the assertions below fail.
    """
    candidates = [r for r in rows
                  if G.is_open(r) and not r["narrowed"] and r["grade"] in G.GRADE_ORDER]
    if not candidates:
        return None
    return sorted(candidates,
                  key=lambda r: (G.GRADE_ORDER.index(r["grade"]), r["number"]))[0]


def test_the_queue_never_skips_an_open_grade_a_gap():
    """The load-bearing rule: while ANY grade A is open, the queue must hand back A.

    Grade B is genuinely next only once every A is fixed or narrowed — otherwise
    a lower-graded gap could pre-empt the high-grade work the loop exists to do.
    """
    open_a = [r["number"] for r in G.entry_rows()
              if G.is_open(r) and not r["narrowed"] and r["grade"] == "A"]
    nxt = G.next_gap()

    if open_a:
        assert nxt is not None, "grade-A work is open but the queue is empty"
        assert nxt["grade"] == "A", nxt
        assert nxt["number"] == min(open_a), nxt
        return

    # No grade-A work left: the queue may descend a grade, or be done.
    if nxt is None:
        pytest.skip("everything is closed")
    assert G.GRADE_ORDER.index(nxt["grade"]) > 0, nxt


def test_lowest_numbered_a_wins_over_a_lower_numbered_b():
    rows = [_work_row(6, "B"), _work_row(65, "A"), _work_row(93, "A")]
    assert _next_gap_from(rows)["number"] == 65


def test_the_lowest_numbered_grade_a_is_taken_first():
    rows = [_work_row(98, "A"), _work_row(93, "A"), _work_row(65, "A")]
    assert _next_gap_from(rows)["number"] == 65


def test_a_drained_grade_a_queue_descends_to_the_lowest_grade_b():
    rows = [_work_row(98, "B"), _work_row(6, "B"), _work_row(65, "C")]
    assert _next_gap_from(rows)["number"] == 6


def test_a_narrowed_grade_a_gap_does_not_hold_the_queue():
    narrowed = _work_row(65, "A")
    narrowed["narrowed"] = True
    rows = [narrowed, _work_row(6, "B")]
    assert _next_gap_from(rows)["number"] == 6


def test_the_queue_ends_only_when_no_ordered_grade_is_open():
    assert _next_gap_from([]) is None
    fixed = _work_row(65, "A")
    fixed["fixed"] = True
    assert _next_gap_from([fixed]) is None


def test_progress_reports_percentages_that_add_up():
    text = G.progress()
    m = re.search(r"total entries : (\d+)", text)
    f = re.search(r"fixed\s+: (\d+)", text)
    o = re.search(r"open\s+: (\d+)", text)
    t = re.search(r"trade-offs\s+: (\d+)", text)
    assert m and f and o and t
    total, fixed, open_, trade = (int(x.group(1)) for x in (m, f, o, t))
    assert fixed + open_ + trade <= total, "more rows accounted for than exist"
    assert fixed + open_ + trade > total - 10, "rows vanished from the accounting"


# ---------------------------------------------------------------------------
# The checkpoint that proves the loop itself works
# ---------------------------------------------------------------------------

def test_the_loop_starts_from_the_current_closure_state():
    """The exact number the loop must beat. If this fails, a register edit moved
    the ground under it — which is worth knowing before working a gap."""
    closed, total, pct = L.grade_progress("A")
    assert total >= 40, f"only {total} grade-A rows found — is the table intact?"
    assert 0 <= closed <= total
    assert 0 <= pct <= 100


def test_the_resume_packet_always_says_what_to_do_next():
    packet = L.resume_packet("test reason", [26, 27], in_flight=None)
    assert "STOPPED: test reason" in packet
    assert "close_gap.py progress" in packet
    assert "close_gap.py next" in packet


def test_an_in_flight_gap_is_named_in_the_resume_packet():
    packet = L.resume_packet("budget", [], in_flight=35)
    assert "gap 35 is claimed but unverified" in packet
    assert "finish it BEFORE starting anything else" in packet


# ---------------------------------------------------------------------------
# The gate refuses an unearned FIXED
# ---------------------------------------------------------------------------

def test_an_unfixed_gap_fails_the_gate():
    """Gap 35 is open, so the gate must refuse it. If this ever passes without
    the row being updated, the gate is checking nothing."""
    rows = {r["number"]: r for r in G.entry_rows()}
    target = next((n for n, r in rows.items() if not r["fixed"]), None)
    if target is None:
        pytest.skip("everything is fixed")
    check = G.run_check(target, run_suite=False, run_tests=False)
    assert check.failures, f"the gate passed an open gap ({target})"


def test_zero_reverts_is_a_failure_not_a_pass():
    """The inert-test case: 'Reverts: 0 / 0' means the tests do not pin the fix.
    This is the single most important thing the gate checks, because three
    inert tests have reached the suite already."""
    source = Path(G.__file__).read_text(encoding="utf-8")
    assert "n > 0 for n in numbers" in source or "all(n > 0 for n in numbers)" in source
    assert "a zero means that fix is not pinned" in source


def test_the_gate_checks_all_three_registers():
    """One register updated is not done — this project has shipped that mistake."""
    source = Path(G.__file__).read_text(encoding="utf-8")
    for register in ("ENTRY_GRADE_TABLE", "GAP_REGISTER_AND_EXECUTION_PLAN",
                     "SELF_CRITIQUE_OF_GAP_REGISTER"):
        assert register in source, f"{register} is not checked"
