"""Two applies racing each other must never lose one of them (BE-1).

The round-3 audit (2026-09-25) found `POST /edits/apply` doing its
read-modify-write in TWO critical sections: `load_working` (the cycle lock
acquired and released inside `ensure_working`) and then `save_working`
(acquired again). Two concurrent applies therefore each wrote back a document
that did not carry the other's change, so `edits.json` ended up holding a record
whose text was not in `working.json`. Measured with nothing slowed, before the
fix: **295/300 across two threads of one process, 126/300 across two OS
processes, and 40/40 through two real browser contexts.**

`tests/test_cycle_continuity.py` is the deterministic guard for the same
defect — it asserts the shape. This file is the behavioural one: it asserts the
OUTCOME, under real concurrency, and it is the only guard that would still catch
a future refactor that is one critical section but a *stale* one.

Two things this file does that the earlier probes learned the hard way:

1. **Every iteration is gated by a barrier**, so the two applies are provably in
   flight together. A concurrency test that reports "0 diverged" is worthless if
   the operations were serialised by the test itself — a first version of the
   browser probe did exactly that and reported a clean 0/40 while measuring
   nothing.
2. **There is a sequential control run.** It applies the same sequence
   single-threaded and requires every iteration to land, which is what
   distinguishes "the race lost an edit" from "the fixture never worked".

Each thread owns its own scene and moves it through a chain of unique values
(`T1-0 -> T1-1 -> ...`), so "did my last write survive?" is a direct question
about a value only that thread ever wrote.
"""

from __future__ import annotations

import os
import textwrap
import threading
import time

from screenplay_studio import revision
from screenplay_studio.manifest import ProjectManifest

from test_undo_redo_lock_race import (  # reuse the established fixtures
    LINE_1_NEW,
    LINE_1_OLD,
    LINE_2_NEW,
    LINE_2_OLD,
    _child_env,
    _make_project,
    _spawn,
)

ITERATIONS = 60          # per thread, in the in-process leg
PROC_ITERATIONS = 25     # per child, in the cross-process leg
_GATE_S = 3.0            # boot margin so both children cross the start gate together


def _scene_lines(m, scene_number: int) -> list[str]:
    """The scene's element texts — exact membership, not a substring test.

    `in` on a substring would let `T1-2` pass for a scene holding `T1-25`, which
    is exactly the stale value a lost update leaves behind.
    """
    return [el.text for s in revision.load_working(m).scenes
            if s.scene_number == scene_number for el in s.elements]


def _run_chain(m, scene_number: int, first_old: str, tag: str, n: int, gate=None):
    """Move one scene T-0 -> T-1 -> ... -> T-n, returning the per-step record.

    `gate` is called before each step (the barrier that makes the race real).
    """
    steps = []
    for i in range(1, n + 1):
        old = first_old if i == 1 else f"{tag}-{i - 1}"
        if gate is not None:
            gate.wait()
        t0 = time.perf_counter()
        res = revision.apply_edit(m, scene_number, [{"old": old, "new": f"{tag}-{i}"}])
        t1 = time.perf_counter()
        steps.append({"i": i, "applied": bool(res["applied"]), "start": t0, "end": t1})
    return steps


def test_two_threads_applying_concurrently_never_lose_an_edit(tmp_path):
    """Two applies in flight together — the two-browser-tabs case.

    `app.run(threaded=True)` makes two tabs two threads, so this is the shape a
    writer actually hits by opening their project twice.
    """
    m = _make_project(tmp_path)
    barrier = threading.Barrier(2, timeout=30)
    out, errors = {}, {}

    def worker(scene, first_old, tag):
        try:
            out[tag] = _run_chain(m, scene, first_old, tag, ITERATIONS, gate=barrier)
        except BaseException as exc:  # surfaced below, never swallowed
            errors[tag] = exc
            try:
                barrier.abort()
            except Exception:
                pass

    threads = [
        threading.Thread(target=worker, args=(1, LINE_1_OLD, "T1")),
        threading.Thread(target=worker, args=(2, LINE_2_OLD, "T2")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(120)
    assert not any(t.is_alive() for t in threads), "a worker never finished"
    assert not errors, f"a worker raised: {errors}"

    a, b = out["T1"], out["T2"]

    # The race must have been REAL: both applies were in flight together on
    # every step, not sequenced by the harness. Without this, a green below
    # could mean "nothing raced" rather than "nothing was lost".
    overlapped = sum(
        1 for x, y in zip(a, b)
        if min(x["end"], y["end"]) > max(x["start"], y["start"]))
    assert overlapped == ITERATIONS, (
        f"only {overlapped}/{ITERATIONS} steps overlapped — the two applies were "
        "not actually concurrent, so this run proves nothing")

    missed = [s["i"] for s in a + b if not s["applied"]]
    assert not missed, (
        f"an apply found its own previous text missing at step(s) {missed} — a "
        "concurrent apply's write was lost, so `edits.json` now claims an edit "
        "`working.json` does not carry")

    assert f"T1-{ITERATIONS}" in _scene_lines(m, 1), (
        "scene 1 does not hold the last value its own thread wrote — the other "
        "thread's stale whole-file write clobbered it: "
        f"{_scene_lines(m, 1)}")
    assert f"T2-{ITERATIONS}" in _scene_lines(m, 2), (
        "scene 2 does not hold the last value its own thread wrote: "
        f"{_scene_lines(m, 2)}")


def test_the_sequential_control_applies_every_iteration(tmp_path):
    """The control: the same chain, single-threaded, must land every step.

    This is what makes the test above meaningful. If the fixture or the chain
    were broken, the concurrency test would fail for a reason that has nothing
    to do with locking; this leg pins that the chain works when nothing races.
    """
    m = _make_project(tmp_path)
    steps = _run_chain(m, 1, LINE_1_OLD, "S1", ITERATIONS)
    assert all(s["applied"] for s in steps), (
        f"the chain does not even work sequentially: {[s['i'] for s in steps if not s['applied']]}")
    assert f"S1-{ITERATIONS}" in _scene_lines(m, 1)


# ---------------------------------------------------------------------------
# Cross-process leg: the documented CLI + webapp case, in two REAL processes.
# No in-process RLock can serialize these; only the OS byte-range lock can.
# ---------------------------------------------------------------------------

_CHILD = textwrap.dedent(
    """
    import sys, time
    from screenplay_studio import revision
    from screenplay_studio.manifest import ProjectManifest

    proj, start_at, scene, first_old, tag, n = (
        sys.argv[1], float(sys.argv[2]), int(sys.argv[3]), sys.argv[4],
        sys.argv[5], int(sys.argv[6]))
    m = ProjectManifest.load(proj)
    while time.time() < start_at:
        time.sleep(0.001)
    missed = []
    for i in range(1, n + 1):
        old = first_old if i == 1 else f"{tag}-{i - 1}"
        res = revision.apply_edit(m, scene, [{"old": old, "new": f"{tag}-{i}"}])
        if not res["applied"]:
            missed.append(i)
    print("RESULT " + repr((tag, missed, f"{tag}-{n}")))
    """
)


def _child_result(proc) -> tuple:
    out, err = proc.communicate(timeout=180)
    assert proc.returncode == 0, f"child exited {proc.returncode}: {err[-600:]}"
    for line in out.splitlines():
        if line.startswith("RESULT "):
            return eval(line[len("RESULT "):])  # noqa: S307 - our own child's tuple
    raise AssertionError(f"child printed no RESULT line: {out[-300:]!r}")


def test_two_processes_applying_concurrently_never_lose_an_edit(tmp_path):
    """The same race across two OS processes — AGENTS.md documents CLI + webapp
    over one project directory as supported, and that pair is exactly this."""
    m = _make_project(tmp_path)
    start_at = time.time() + _GATE_S
    a = _spawn(_CHILD, m.project_dir, start_at, 1, LINE_1_OLD, "P1", PROC_ITERATIONS)
    b = _spawn(_CHILD, m.project_dir, start_at, 2, LINE_2_OLD, "P2", PROC_ITERATIONS)
    try:
        tag_a, missed_a, final_a = _child_result(a)
        tag_b, missed_b, final_b = _child_result(b)
    finally:
        for p in (a, b):
            if p.poll() is None:
                p.kill()
                p.communicate(timeout=30)

    assert not missed_a, (
        f"child A's own text went missing at step(s) {missed_a} — a concurrent "
        "process's stale whole-file write was not blocked by the cycle lock")
    assert not missed_b, (
        f"child B's own text went missing at step(s) {missed_b}")

    assert f"P1-{PROC_ITERATIONS}" in _scene_lines(m, 1), (
        f"scene 1 does not hold child A's last write: {_scene_lines(m, 1)}")
    assert f"P2-{PROC_ITERATIONS}" in _scene_lines(m, 2), (
        f"scene 2 does not hold child B's last write: {_scene_lines(m, 2)}")


def test_the_cross_process_control_applies_every_iteration(tmp_path):
    """Control for the leg above: one child alone must land every step."""
    m = _make_project(tmp_path)
    start_at = time.time() + _GATE_S
    a = _spawn(_CHILD, m.project_dir, start_at, 1, LINE_1_OLD, "C1", PROC_ITERATIONS)
    try:
        tag, missed, final = _child_result(a)
    finally:
        if a.poll() is None:
            a.kill()
            a.communicate(timeout=30)
    assert not missed, f"the single child lost its own text at {missed}"
    assert f"C1-{PROC_ITERATIONS}" in _scene_lines(m, 1)
