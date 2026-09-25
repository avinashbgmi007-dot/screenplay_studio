"""The edit cycle's REAL invariant: one critical section per cycle (BE-1/E2E-1).

`tests/test_lock_order.py` enforces the *order* of acquisitions — that
`working.json` is the anchor and `edits.json` / `edits.redo.json` are terminal
leaves. It cannot see the defect that actually shipped, because
acquire -> release -> acquire is two individually legal acquisitions, not a
nesting violation. That is how BE-1 survived the guard written to prevent its
bug class (round-3 audit 2026-09-25): the route called `load_working` (the cycle
lock acquired and released inside `ensure_working`) and then `save_working`
(acquired again), so two concurrent applies each wrote back a document that did
not carry the other's change. Measured with nothing slowed: 295/300 across two
threads of one process, 126/300 across two OS processes, and 40/40 through two
real browser contexts.

The invariant enforced here is the one the topology note above
`ensure_working` states in words — "one cycle, one explicit acquisition,
covering the whole read-modify-write of the trio, never only the write":

  1. the document a recorded `save_working` persists must have been READ while
     the cycle lock was held, so the load and the write are one section;
  2. the cycle lock must still be held when that save runs; and
  3. one `apply_edit` call must be exactly ONE outermost acquisition of the
     cycle lock.

Why the record is the trigger: the record is what makes the divergence durable.
Without it the writer still has their text; with it `edits.json` claims an edit
`working.json` does not carry, so `undo` reports `failed` and the writer is
never told anything was lost.

How it observes, and why this way: the guard reads the lock's OWN state
(`_StoreLock._depth`, plus RLock ownership) rather than keeping a stack of
enter/exit events. That choice is deliberate — a first version of this file
tracked a per-thread enter/exit stack and it did not stay in sync in this suite,
so it was discarded rather than debugged into working. Asking the object that
owns the state cannot drift away from it. `_depth` is private, but it is this
repo's own attribute and the topology note already reasons about it by name.

Scope, stated rather than implied: the record-LESS
`save_working(m, load_working(m))` overwrite is deliberately NOT constrained.
`save_working`'s own comment documents that form as safe and no production path
calls it, so constraining it here would make the guard contradict a documented
contract — and a guard that contradicts the contract is the guard that is wrong.
The guard is single-threaded by design; the concurrent legs live in
`tests/test_apply_race.py`.
"""

from __future__ import annotations

import io
import os
import threading

import pytest

import screenplay_studio.webapp_server as webapp_server
from screenplay_studio import jsonio, revision
from screenplay_studio.manifest import ProjectManifest

from test_undo_redo_lock_race import (  # reuse the established fixture
    LINE_1_NEW,
    LINE_1_OLD,
    _make_project,
)

SAMPLE_SCRIPT = b"""Title: Continuity
Author: Test

INT. STUDY - NIGHT

MARA takes out an old REVOLVER, setting it on the desk.

CUT TO:

INT. KITCHEN - DAY

Mara sits at the table, staring at nothing.
"""


class CycleContinuityGuard:
    """The observations the assertions are made from.

    `lock_lookup` is the REAL `jsonio._lock_for`, handed in rather than looked
    up, because this fixture monkeypatches `jsonio._lock_for` to install the
    `_TracedLock` proxy. Reading through the patched name would have the guard
    introspect its own proxy, which carries no `_depth` and would report "never
    held" for every lock — a guard that passes by being blind.
    """

    def __init__(self, cycle_path: str, lock_lookup):
        self.cycle = os.path.abspath(cycle_path)
        self._real_lock = lock_lookup
        self.violations: list[str] = []
        self.reads = 0
        self.reads_under_lock = 0
        self.recorded_saves = 0
        self.outer_acquisitions = 0
        self._read_under_lock: dict[int, bool] = {}

    def _held(self) -> bool:
        """Is the cycle lock held BY THIS THREAD right now?

        Ground truth from the lock object itself: a non-zero `_depth` means
        someone is inside `__enter__`..`__exit__`, and the RLock ownership check
        (when available) pins that to this thread rather than to any other.
        """
        lock = self._real_lock(self.cycle)
        if getattr(lock, "_depth", 0) <= 0:
            return False
        is_owned = getattr(getattr(lock, "_rlock", None), "_is_owned", None)
        return bool(is_owned()) if is_owned is not None else True

    def note_read(self) -> None:
        self.reads += 1
        held = self._held()
        if held:
            self.reads_under_lock += 1
        self._read_under_lock[threading.get_ident()] = held

    def note_outer_acquisition(self) -> None:
        self.outer_acquisitions += 1

    def check_recorded_save(self, has_record: bool) -> None:
        if not has_record:
            return
        self.recorded_saves += 1
        if not self._read_under_lock.get(threading.get_ident()):
            self.violations.append(
                "a recorded save persisted a document that was read OUTSIDE the "
                "cycle lock (load-then-save is two critical sections, so a "
                "concurrent cycle's change is overwritten and its log record is "
                "orphaned)")
        elif not self._held():
            self.violations.append(
                "a recorded save ran after the cycle lock had been released")

    def assert_clean(self) -> None:
        assert not self.violations, (
            "cycle-continuity violation:\n  " + "\n  ".join(self.violations))


class _TracedLock:
    """Proxy that counts OUTERMOST acquisitions of the cycle lock, then delegates.

    The count is taken AFTER a successful `__enter__`: `_depth == 1` at that
    point means this acquisition was the outermost one for this path, which is
    exactly "one cycle, one explicit acquisition". No enter/exit stack is kept,
    so nothing can drift out of sync with the lock.
    """

    __slots__ = ("inner", "is_cycle", "guard")

    def __init__(self, inner, is_cycle: bool, guard):
        self.inner = inner
        self.is_cycle = is_cycle
        self.guard = guard

    def __enter__(self):
        result = self.inner.__enter__()
        if self.is_cycle and getattr(self.inner, "_depth", 0) == 1:
            self.guard.note_outer_acquisition()
        return result

    def __exit__(self, *exc):
        return self.inner.__exit__(*exc)


@pytest.fixture
def arm_guard(monkeypatch):
    """Patch `jsonio._lock_for` — the single chokepoint that `lock_for`,
    `atomic_write_json` and `load_json_store` all resolve at call time."""
    real_lock = jsonio._lock_for
    real_load = revision.load_working
    real_save = revision.save_working

    def install(cycle_path: str) -> CycleContinuityGuard:
        guard = CycleContinuityGuard(cycle_path, real_lock)
        cycle = os.path.abspath(cycle_path)

        monkeypatch.setattr(
            jsonio, "_lock_for",
            lambda path: _TracedLock(real_lock(path),
                                     os.path.abspath(path) == cycle, guard))

        def traced_load(m):
            doc = real_load(m)
            guard.note_read()
            return doc

        def traced_save(m, doc, record=None):
            guard.check_recorded_save(bool(record))
            return real_save(m, doc, record=record)

        monkeypatch.setattr(revision, "load_working", traced_load)
        monkeypatch.setattr(revision, "save_working", traced_save)
        return guard

    return install


@pytest.fixture
def client(tmp_path):
    webapp_server.PROJECTS_DIR = str(tmp_path / "projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = "http://127.0.0.1:1"
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _upload(client) -> str:
    resp = client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "s.fountain"), "title": "Continuity"},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (200, 201), resp.get_data(as_text=True)
    return resp.get_json()["project"]


# ---------------------------------------------------------------------------
# The real thing: the route the writer's browser calls, armed.
# ---------------------------------------------------------------------------

def test_the_apply_route_runs_in_one_critical_section(client, arm_guard):
    """`POST /edits/apply` must read and write inside ONE cycle-lock section.

    This is the assertion that would have caught BE-1 before it shipped, and it
    is deterministic — no timing, no race, no iterations.
    """
    project = _upload(client)
    m = ProjectManifest.load(webapp_server._project_dir(project))
    guard = arm_guard(revision.working_path(m))

    resp = client.post(f"/api/projects/{project}/edits/apply", json={
        "scene_number": 1,
        "replacements": [{"old": LINE_1_OLD, "new": LINE_1_NEW}],
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["applied"], body
    assert LINE_1_NEW in body["scene_text_after"]

    guard.assert_clean()
    # Non-vacuity: a guard that observed nothing must not be able to pass.
    assert guard.reads >= 1, "the guard saw no document read — it is not wired"
    assert guard.reads_under_lock >= 1, (
        "no document read happened under the cycle lock — the guard is not "
        "observing the lock it certifies")
    assert guard.recorded_saves >= 1, (
        "the guard saw no recorded save — it is not wired where it claims to be")
    assert guard.outer_acquisitions == 1, (
        f"the apply route took the cycle lock {guard.outer_acquisitions} times; "
        "one cycle is one explicit acquisition")


def test_the_locked_primitive_is_exactly_one_acquisition(tmp_path, arm_guard):
    """`apply_edit` is one cycle: ONE outermost acquisition of the cycle lock.

    The topology note's words, made executable. Two outermost acquisitions is
    the load-then-save shape, whatever it is spelled as.
    """
    m = _make_project(tmp_path)
    guard = arm_guard(revision.working_path(m))

    out = revision.apply_edit(m, 1, [{"old": LINE_1_OLD, "new": LINE_1_NEW}])

    assert out["applied"], out
    assert out["scene_text_after"].count(LINE_1_NEW) == 1
    guard.assert_clean()
    assert guard.recorded_saves == 1, (
        f"expected exactly one recorded save, saw {guard.recorded_saves}")
    assert guard.outer_acquisitions == 1, (
        f"one cycle must be exactly one outermost acquisition, saw "
        f"{guard.outer_acquisitions} — the read and the write are in different "
        "sections")


# ---------------------------------------------------------------------------
# Can-fail proof: both reintroductions must go red, including the subtle one.
# ---------------------------------------------------------------------------

def test_the_guard_turns_red_on_the_shape_be1_was(tmp_path, arm_guard):
    """The exact route shape before the fix: load, mutate, save, with no lock
    held across the pair. The guard must not be able to pass it."""
    m = _make_project(tmp_path)
    guard = arm_guard(revision.working_path(m))

    doc = revision.load_working(m)                       # acquired and RELEASED
    result = revision.apply_replacements(
        doc, 1, [{"old": LINE_1_OLD, "new": LINE_1_NEW}])
    assert result["applied"]
    revision.save_working(m, doc, record={               # acquired AGAIN
        "scene_number": 1, "applied": result["applied"], "skipped": []})

    assert guard.recorded_saves == 1, "the can-fail leg did not exercise the guard"
    assert guard.reads_under_lock == 0, (
        "the can-fail leg is not reproducing the defect: the read WAS under the "
        "lock, so this is not the load-then-save shape")
    with pytest.raises(AssertionError, match="cycle-continuity violation"):
        guard.assert_clean()


def test_the_guard_turns_red_on_a_lock_around_only_the_write(tmp_path, arm_guard):
    """The subtle reintroduction: wrapping only the SAVE in `lock_for` satisfies
    a naive "is the lock held at write time" check, but the document was still
    read outside the section, so a concurrent cycle's change is still lost."""
    m = _make_project(tmp_path)
    guard = arm_guard(revision.working_path(m))

    doc = revision.load_working(m)
    result = revision.apply_replacements(
        doc, 1, [{"old": LINE_1_OLD, "new": LINE_1_NEW}])
    with jsonio.lock_for(revision.working_path(m)):
        revision.save_working(m, doc, record={
            "scene_number": 1, "applied": result["applied"], "skipped": []})

    assert guard.recorded_saves == 1, "the can-fail leg did not exercise the guard"
    with pytest.raises(AssertionError, match="cycle-continuity violation"):
        guard.assert_clean()
