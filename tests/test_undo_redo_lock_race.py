"""The edit log's undo/redo path is a load-modify-write like any other store —
and it was the one writer-owned cycle with NO lock on it (H5, re-audit 2026-09-24).

At the time, `save_working` appended under `lock_for(edits_log_path)`, while
`undo_last_edit` and `redo_last_edit` read both stores, mutated in memory, and
wrote them back with no lock at all — and the webapp runs `threaded=True` while
AGENTS.md documents CLI + webapp over one project directory as supported. Two
writers therefore overlapped, and the loser's record disappeared: an edit whose
text IS in `working.json` could vanish from `edits.json`, so the writer could
never undo it and had no sign anything was lost. Measured live in the audit (a
0.4 s-slowed read + one concurrent apply): final `edits.json` had **0 records**
while the working copy carried the applied text.

These tests widen that exact window deterministically — the read is slowed and
the concurrent apply is driven at the moment the read has happened but the
write-back has not — because that is the only way to observe the defect: with
the lock restored, both writers serialize and nothing overlaps by accident.

P1-3 (2026-09 audit): the same race BETWEEN PROCESSES. The thread legs above
monkeypatch a slow read in one process, which can never exercise the OS
byte-range lock in `jsonio.lock_for` — and `working.json` was the one store
whose own lock was taken for neither the read nor the cycle: an independent
audit measured 200/200 divergence between `working.json` and `edits.json`
across two OS processes (200/200 again across two threads, since
`webapp_server.py` runs `app.run(threaded=True)`). The child-process legs at
the bottom of this file are the cross-process guard: an undo/redo cycle racing
a real apply must never leave a record in `edits.json` whose text is not in
`working.json` (the lost-update direction; the rename is atomic, so this is
never a torn file, and the pair is concurrency-safe, not transactional — a
crash between the text write and the log write is a known, accepted gap).
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import threading
import time

from screenplay_studio import revision
from screenplay_studio.manifest import ProjectManifest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SAMPLE_SCRIPT = b"""Title: Undo Race

INT. STUDY - NIGHT

MARA takes out an old REVOLVER, setting it on the desk.

CUT TO:

INT. KITCHEN - DAY

Mara sits at the table, staring at nothing.
"""

LINE_1_OLD = "MARA takes out an old REVOLVER, setting it on the desk."
LINE_1_NEW = "MARA lays the REVOLVER on the desk."
LINE_2_OLD = "Mara sits at the table, staring at nothing."
LINE_2_NEW = "Mara stares at the table, saying nothing."

# Long enough that the concurrent writer lands inside the window on any machine
# this suite runs on, matching the 0.4 s the audit used to prove the defect. The
# probe only proves anything if the apply's append completes BEFORE the stale
# write-back, so the window has to outlast the concurrent apply's own work too.
WINDOW_S = 1.5


def _make_project(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "x.fountain"
    src.write_bytes(SAMPLE_SCRIPT)
    m = ProjectManifest.create(str(tmp_path / "p"), str(src), title="Undo Race")
    from screenplay_parser import parse_screenplay
    doc = parse_screenplay(str(m.source_path))
    doc.save(m.parsed_path)
    revision.ensure_working(m)
    return m


def _apply(m, scene_number, old_line, new_line, record_id):
    """One real apply through the locked path — the same call the webapp makes.

    BE-1 (round-3 audit 2026-09-25): this used to spell out the load-then-save
    pair by hand, which is the very shape that lost updates. It now calls
    `revision.apply_edit`, so every guard in this file and in
    `test_lock_order.py` drives the primitive the route drives, not a
    hand-rolled imitation of it.

    The record id is supplied rather than read back afterwards: re-reading the log
    here would sample a different moment than the append did, and this probe has
    to name the record it is looking for, not whichever one is on disk when it
    looks (`save_working` only mints an id when the record has none).
    """
    result = revision.apply_edit(
        m, scene_number, [{"old": old_line, "new": new_line}],
        record={"id": record_id})
    assert result["applied"], f"the fixture line was not found: {result}"
    return record_id


def _slowed(real_read, started: threading.Event, window_s: float = WINDOW_S):
    """Wrap a store read: complete it, announce it, then hold the window open."""
    def read(m):
        data = real_read(m)
        started.set()
        time.sleep(window_s)
        return data
    return read


def _run_with_concurrent_apply(m, monkeypatch, slow_name, op, record_id):
    """Run `op` on a thread whose store read is slowed; land one apply inside."""
    real_read = getattr(revision, slow_name)
    started = threading.Event()
    monkeypatch.setattr(revision, slow_name, _slowed(real_read, started))

    box = {}

    def run():
        try:
            box["result"] = op()
        except Exception as exc:  # surfaced below, never swallowed
            box["error"] = exc

    thread = threading.Thread(target=run)
    thread.start()
    assert started.wait(10), "the slowed read never ran — the probe is not measuring what it claims"
    # the concurrent writer: a real, locked apply on ANOTHER scene, so neither
    # operation depends on the other's text
    e2 = _apply(m, 2, LINE_2_OLD, LINE_2_NEW, record_id)
    thread.join(30)
    monkeypatch.setattr(revision, slow_name, real_read)
    assert not thread.is_alive(), f"{slow_name} never finished"
    assert "error" not in box, f"{slow_name} raised: {box.get('error')!r}"
    return box["result"], e2


def test_undo_does_not_drop_an_apply_that_lands_mid_flight(tmp_path, monkeypatch):
    """An edit applied while an undo is in flight keeps its log record.

    Broken: the undo writes back the list it read BEFORE the apply, so the
    apply's record is erased — the text stays in working.json, the record does
    not, and `can_undo` says there is nothing there.
    """
    m = _make_project(tmp_path)
    e1 = _apply(m, 1, LINE_1_OLD, LINE_1_NEW, "e1-race")

    undone, e2 = _run_with_concurrent_apply(
        m, monkeypatch, "edits_log", lambda: revision.undo_last_edit(m), "e2-race")

    assert undone["undone"]["id"] == e1
    ids = [rec.get("id") for rec in revision.edits_log(m)]
    assert e2 in ids, (
        "the concurrently applied edit lost its record: the log is a "
        f"load-modify-write that does not hold lock_for(edits.json) — ids={ids}"
    )
    # and the working copy still holds that edit's text: the two stores agree
    text = "\n".join(el.text for s in revision.load_working(m).scenes
                     if s.scene_number == 2 for el in s.elements)
    assert LINE_2_NEW in text


def test_redo_does_not_drop_an_apply_that_lands_mid_flight(tmp_path, monkeypatch):
    """The redo mirror: re-applying an undone edit must not erase a newer one.

    Same defect, other direction — and the window has to sit on the LOG read,
    because that is the write-back that clobbers: redo loads the log, a locked
    apply appends to it, and redo then writes its own stale list over the
    append. The redo stack's own read is not where the loss happens.
    """
    m = _make_project(tmp_path)
    _apply(m, 1, LINE_1_OLD, LINE_1_NEW, "e1-race")
    revision.undo_last_edit(m)          # E1 now sits on the redo stack

    redone, e2 = _run_with_concurrent_apply(
        m, monkeypatch, "edits_log", lambda: revision.redo_last_edit(m), "e2-race")

    assert redone["redone"]["scene_number"] == 1
    ids = [rec.get("id") for rec in revision.edits_log(m)]
    assert e2 in ids, (
        "redo appended to a log it read before the concurrent apply landed, and "
        f"overwrote the apply's record — ids={ids}"
    )
    # and the working copy still holds that edit's text too — the mirror of the
    # undo leg's assertion above (the redo leg used to check only the log).
    text = "\n".join(el.text for s in revision.load_working(m).scenes
                     if s.scene_number == 2 for el in s.elements)
    assert LINE_2_NEW in text


# ---------------------------------------------------------------------------
# P1-3, the cross-process legs: REAL child processes, because the defect is
# that `save_working` wrote working.json with no lock of its own, and no
# in-process monkeypatch can prove the OS byte-range lock serializes cycles
# between processes (tests/test_store_concurrency.py documents the same rule).
# The racer child slows ITS OWN working-read inside the cycle — that only
# widens the read->write window; the discriminating part is that the apply
# child is a separate OS process whose working write either lands inside the
# window (broken: no working lock to block it) or waits for the cycle lock
# (fixed). The assertion pins the direction that must never occur under ANY
# interleaving of serialized cycles — a record in edits.json whose new text
# is absent from working.json. (The reverse direction — an apply whose stale
# whole-file write resurrects already-undone text — is a caller-level
# load-then-save hazard this fix does not claim to close.)
# ---------------------------------------------------------------------------

# How long the racer holds its read->write window open, and how long the apply
# child waits after the shared start gate before it writes. The apply's whole
# operation (~0.2s of JSON round-trips) lands deep inside the window on the
# broken code and is forced past the window's end on the fixed one.
_RACE_WINDOW_S = 2.0
_APPLY_DELAY_S = 0.3
_GATE_S = 3.0   # boot margin so both children cross the start gate together

_RACER_CHILD = textwrap.dedent(
    """
    import json, sys, time
    from screenplay_studio import revision
    from screenplay_studio.manifest import ProjectManifest

    proj, op, start_at, window = (sys.argv[1], sys.argv[2], float(sys.argv[3]),
                                  float(sys.argv[4]))
    m = ProjectManifest.load(proj)
    real_load = revision.load_working

    def slow_load(mm):
        # widen the working read->write window INSIDE the cycle: this is the
        # exact span that must be atomic across processes.
        doc = real_load(mm)
        time.sleep(window)
        return doc

    revision.load_working = slow_load
    while time.time() < start_at:
        time.sleep(0.001)
    gate = time.monotonic()
    fn = revision.undo_last_edit if op == "undo" else revision.redo_last_edit
    try:
        fn(m)
    except ValueError:
        pass  # empty log/stack: seeded state was consumed by the other child
    print("ELAPSED " + repr(time.monotonic() - gate))
    """
)

_APPLY_CHILD = textwrap.dedent(
    """
    import sys, time
    from screenplay_studio import revision
    from screenplay_studio.manifest import ProjectManifest

    proj, start_at, delay, old_line, new_line = (
        sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4], sys.argv[5])
    m = ProjectManifest.load(proj)
    while time.time() < start_at:
        time.sleep(0.001)
    gate = time.monotonic()
    time.sleep(delay)
    # BE-1: the production primitive — one critical section across load + write,
    # so this child contends for the cycle lock the way the webapp does.
    result = revision.apply_edit(
        m, 2, [{"old": old_line, "new": new_line}], record={"id": "e2-race"})
    assert result["applied"], f"fixture line not found: {result}"
    print("ELAPSED " + repr(time.monotonic() - gate))
    """
)


def _child_env() -> dict:
    env = dict(os.environ)
    parts = [REPO_ROOT] + [p for p in sys.path if p]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _spawn(source: str, *args) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", source, *[str(a) for a in args]],
        cwd=REPO_ROOT, env=_child_env(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


def _child_elapsed(proc: subprocess.Popen) -> float:
    out, err = proc.communicate(timeout=120)
    assert proc.returncode == 0, f"child exited {proc.returncode}: {err[-600:]}"
    for line in out.splitlines():
        if line.startswith("ELAPSED "):
            return float(line.split()[1])
    raise AssertionError(f"child printed no ELAPSED line: {out[-300:]!r}")


def _run_cross_process_race(tmp_path, racer_op):
    """Seed E1 (and undo it for the redo leg), then race one cycle against a
    real apply in two OS processes started behind one gate."""
    m = _make_project(tmp_path / racer_op)
    _apply(m, 1, LINE_1_OLD, LINE_1_NEW, "e1-race")
    if racer_op == "redo":
        revision.undo_last_edit(m)   # E1 now lives on the redo stack
    else:
        assert revision.redo_stack(m) == []

    start_at = time.time() + _GATE_S
    racer = _spawn(_RACER_CHILD, m.project_dir, racer_op, start_at, _RACE_WINDOW_S)
    applier = _spawn(_APPLY_CHILD, m.project_dir, start_at, _APPLY_DELAY_S,
                     LINE_2_OLD, LINE_2_NEW)
    try:
        racer_elapsed = _child_elapsed(racer)
        apply_elapsed = _child_elapsed(applier)
    finally:
        for p in (racer, applier):
            if p.poll() is None:
                p.kill()
                p.communicate(timeout=30)

    # The race must have been REAL: the apply had to sit inside the racer's
    # window. On the fixed code the apply's cycle waits for the working lock,
    # so its elapsed time necessarily exceeds the window; on the broken code
    # it never waits, and the assertion below catches the divergence instead.
    assert racer_elapsed >= _RACE_WINDOW_S, "the racer's window never opened"
    assert apply_elapsed >= _RACE_WINDOW_S, (
        f"the concurrent apply finished in {apply_elapsed:.2f}s without waiting "
        f"for the racer's {_RACE_WINDOW_S:.1f}s cycle — the cycle locks do not "
        "cross processes"
    )

    ids = [rec.get("id") for rec in revision.edits_log(m)]
    if "e2-race" in ids:
        text = "\n".join(el.text for s in revision.load_working(m).scenes
                         if s.scene_number == 2 for el in s.elements)
        assert LINE_2_NEW in text, (
            "working.json diverged from edits.json: the applied edit's record is "
            "in the log but its text was clobbered by an unlocked read-modify-"
            f"write on working.json (undo/redo wrote a document it read before "
            f"the apply landed) — ids={ids}"
        )
    # the log itself must never carry the same record twice from one cycle
    assert len(ids) == len(set(ids)), f"a cycle duplicated a log entry: {ids}"


def test_undo_vs_apply_across_processes_never_diverges_working_from_edits(tmp_path):
    """Undo cycle racing a real apply in two OS processes (P1-3, undo leg)."""
    _run_cross_process_race(tmp_path, "undo")


def test_redo_vs_apply_across_processes_never_diverges_working_from_edits(tmp_path):
    """The redo mirror (P1-3, redo leg)."""
    _run_cross_process_race(tmp_path, "redo")
