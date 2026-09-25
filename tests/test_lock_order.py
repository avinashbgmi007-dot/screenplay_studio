"""Executable check of the edit-cycle lock-order invariant (P1-3, revision.py).

The rule AGENTS.md states as "one lock per store" is, since the P1-3
restructure, precisely this topology (see the comment block at the top of
`revision.py`): `working.json`'s lock is the SINGLE cycle lock for apply /
undo / redo / reset / ensure, and `edits.json` / `edits.redo.json` are only
ever taken as LEAF locks briefly inside it. Nesting of the SAME path is the
documented reentrancy (`_StoreLock._depth`) that `atomic_write_json` relies
on and must stay legal. What must NEVER happen is a different nesting
direction — the audit (plan_validation_2026-09-25 §7.1) specifically warns
against a fix that nests log -> working: two processes taking the same pair
in opposite orders deadlock, and an outer lock that is not the cycle anchor
re-opens the lost-update hole P1-3 closed (an undo clobbering a concurrent
apply's write to working.json).

So the invariant this test enforces, on every real `_lock_for` acquisition
made while it drives the actual writers, is:

  1. acquiring a DIFFERENT path while an outer lock is held is only legal as
     the one documented fan-out: working.json -> {edits.json, edits.redo.json};
  2. while such a leaf is held, nothing may acquire any other path (the leaf
     is terminal — no working -> edits -> redo chains, no leaf -> anchor);
  3. nested acquisition of the SAME path is always legal (reentrancy).

The guard is a wrapper around `jsonio._lock_for` — the single chokepoint
every acquisition (public `lock_for`, `atomic_write_json`, `load_json_store`)
resolves at call time — so it sees leaves and anchors alike, not only the
explicit ones. Deliberately stricter than the task's briefest phrasing ("no
two DIFFERENT paths at once"): the current design provably and correctly
holds working + one leaf simultaneously, so that literal rule would be red
on the fixed code; the direction/terminality rules are the real invariant.
"""

from __future__ import annotations

import os
import threading

import pytest

from screenplay_studio import jsonio
from screenplay_studio import revision

from test_undo_redo_lock_race import (  # reuse the established fixtures
    LINE_1_NEW,
    LINE_1_OLD,
    LINE_2_NEW,
    LINE_2_OLD,
    _apply,
    _make_project,
)


class LockOrderGuard:
    """Per-thread timeline over `jsonio._lock_for`, raising on forbidden nesting.

    `roles` maps an anchor path to the leaf paths it may fan out to; any
    first-level nesting of an unlisted pair is a violation. Same-path
    reentry never is. Every enter/exit is appended to `timeline` so a test
    can assert the guard actually SAW the nesting it certifies (an inert
    wrapper would pass vacuously).
    """

    def __init__(self, roles: dict):
        self.roles = {os.path.abspath(a): {os.path.abspath(p) for p in ps}
                      for a, ps in roles.items()}
        self.timeline = []
        self._held_by_thread = {}
        self._meta = threading.Lock()

    # -- stack bookkeeping (per thread; the guard is process-global) --------

    def _stack(self) -> list:
        return self._held_by_thread.setdefault(threading.get_ident(), [])

    def _distinct(self, stack: list) -> list:
        seen = []
        for p in stack:
            if not seen or seen[-1] != p:
                seen.append(p)
        return seen

    def _check(self, path: str) -> None:
        stack = self._stack()
        if not stack or stack[-1] == path:
            return
        if len(self._distinct(stack)) >= 2:
            raise AssertionError(
                f"lock-order violation: acquiring {os.path.basename(path)} "
                f"while already holding {self._describe(stack)} - a leaf lock "
                "must be terminal (nothing else is taken under it)")
        outer = stack[-1]
        allowed = self.roles.get(outer, set())
        if path not in allowed:
            raise AssertionError(
                f"lock-order violation: acquiring {os.path.basename(path)} "
                f"while holding {os.path.basename(outer)} - the only legal "
                "nesting is working.json -> edits.json/edits.redo.json; "
                f"log -> working would deadlock opposite-order processes")

    def _describe(self, stack: list) -> str:
        return ", ".join(os.path.basename(p) for p in self._distinct(stack))

    def enter(self, path: str) -> None:
        path = os.path.abspath(path)
        self._check(path)
        stack = self._stack()
        stack.append(path)
        with self._meta:
            self.timeline.append(
                ("enter", threading.get_ident(), path, len(stack)))

    def exit(self, path: str) -> None:
        path = os.path.abspath(path)
        stack = self._stack()
        assert stack and stack[-1] == path, (
            f"guard bookkeeping broken: exiting {path} from stack {stack}")
        stack.pop()
        with self._meta:
            self.timeline.append(
                ("exit", threading.get_ident(), path, len(stack)))

    # -- observations for assertions -----------------------------------------

    def nested_pairs(self) -> set:
        """{(outer, inner)} distinct-path nestings actually observed."""
        pairs = set()
        stacks = {}
        for event, tid, path, depth in self.timeline:
            st = stacks.setdefault(tid, [])
            if event == "enter":
                if st and st[-1] != path:
                    pairs.add((st[-1], path))
                st.append(path)
            else:
                st.pop()
        return pairs

    def max_same_path_depth(self, path: str) -> int:
        path = os.path.abspath(path)
        return max((depth for event, _, p, depth in self.timeline
                    if p == path and event == "enter"), default=0)

    def assert_released(self) -> None:
        leftovers = {tid: [os.path.basename(p) for p in st]
                     for tid, st in self._held_by_thread.items() if st}
        assert not leftovers, f"locks still held at the end: {leftovers}"


class _TracedLock:
    """Context-manager proxy: consults the guard, then delegates."""

    __slots__ = ("inner", "path", "guard")

    def __init__(self, inner, path, guard):
        self.inner = inner
        self.path = os.path.abspath(path)
        self.guard = guard

    def __enter__(self):
        self.guard.enter(self.path)
        try:
            return self.inner.__enter__()
        except BaseException:
            self.guard.exit(self.path)
            raise

    def __exit__(self, *exc):
        try:
            return self.inner.__exit__(*exc)
        finally:
            self.guard.exit(self.path)


@pytest.fixture
def guard_factory(monkeypatch):
    """Patch `jsonio._lock_for` — the one chokepoint `lock_for`,
    `atomic_write_json` and `load_json_store` all resolve at call time —
    so the guard sees explicit cycle locks AND jsonio's leaf locks."""
    real = jsonio._lock_for

    def install(roles: dict) -> LockOrderGuard:
        guard = LockOrderGuard(roles)

        def traced(path):
            return _TracedLock(real(path), path, guard)

        monkeypatch.setattr(jsonio, "_lock_for", traced)
        return guard

    return install


def _roles_for(m) -> dict:
    """The documented P1-3 topology for one concrete project."""
    return {
        revision.working_path(m): {revision.edits_log_path(m),
                                   revision.edits_redo_path(m)},
    }


def _real_edit_cycle(m):
    """Drive every revision.py writer that touches more than one store."""
    _apply(m, 1, LINE_1_OLD, LINE_1_NEW, "e1-order")   # save_working (record)
    revision.save_working(m, revision.load_working(m))  # record-less overwrite
    revision.undo_last_edit(m)
    revision.redo_last_edit(m)
    revision.clear_redo(m)
    revision.reset_working(m)
    revision.ensure_working(m)                          # lazy create again
    _apply(m, 2, LINE_2_OLD, LINE_2_NEW, "e2-order")   # cycle once more
    revision.undo_last_edit(m)


def test_edit_cycle_writers_never_nest_outside_working_to_leaves(
        tmp_path, guard_factory):
    """The whole real edit cycle runs with the guard armed: it never raises,
    and the guard actually witnessed the sanctioned working -> {edits, redo}
    fan-out (so a guard that silently intercepted nothing cannot pass)."""
    m = _make_project(tmp_path)
    guard = guard_factory(_roles_for(m))

    _real_edit_cycle(m)

    guard.assert_released()
    wp = os.path.abspath(revision.working_path(m))
    pairs = guard.nested_pairs()
    assert (wp, os.path.abspath(revision.edits_log_path(m))) in pairs, (
        f"save_working should nest the edits-log leaf; saw {pairs}")
    assert (wp, os.path.abspath(revision.edits_redo_path(m))) in pairs, (
        f"clear_redo/undo should nest the redo-stack leaf; saw {pairs}")


def test_same_path_reentrancy_stays_legal(tmp_path, guard_factory):
    """The `_depth` case jsonio documents: a store holds its lock across a
    load-modify-write while atomic_write_json / load_json_store re-enter it.
    This must NOT be reported as nesting two different stores."""
    store = tmp_path / "store.json"
    guard = guard_factory({str(store): set()})

    with jsonio.lock_for(str(store)):
        with jsonio.lock_for(str(store)):
            jsonio.atomic_write_json(str(store), {"a": 1})
            assert jsonio.load_json_store(str(store), None) == {"a": 1}
        with jsonio.lock_for(str(store)):
            jsonio.atomic_write_json(str(store), {"a": 2})

    assert jsonio.load_json_store(str(store), None) == {"a": 2}
    guard.assert_released()
    assert guard.nested_pairs() == set(), "same-path reentry counted as nesting"
    assert guard.max_same_path_depth(str(store)) >= 3, (
        "the guard never saw the nested reentry — it is not instrumented "
        "where it claims to be")


# ---------------------------------------------------------------------------
# Can-fail proof: the forbidden shapes must be caught red. Each scratch block
# is exactly a bug a future refactor could reintroduce; the last one is the
# log -> working direction audit §7.1 warns about by name.
# ---------------------------------------------------------------------------

def test_guard_turns_red_on_forbidden_nesting(tmp_path, guard_factory):
    """working -> (a store outside the trio) is not the documented fan-out."""
    m = _make_project(tmp_path)
    guard = guard_factory(_roles_for(m))
    wp = revision.working_path(m)
    other = revision.dismissed_path(m)

    with pytest.raises(AssertionError, match="lock-order violation"):
        with jsonio.lock_for(wp):
            with jsonio.lock_for(other):
                pass

    guard.assert_released()


def test_guard_turns_red_on_the_forbidden_log_to_working_direction(
        tmp_path, guard_factory):
    """The exact reversal the audit forbids: edits.json held while taking
    working.json — opposite orders across two processes deadlock."""
    m = _make_project(tmp_path)
    guard = guard_factory(_roles_for(m))
    wp = revision.working_path(m)
    log = revision.edits_log_path(m)

    with pytest.raises(AssertionError, match="lock-order violation"):
        with jsonio.lock_for(log):
            with jsonio.lock_for(wp):
                pass

    guard.assert_released()
    # and the guard is still armed afterwards: the sanctioned shape passes
    with jsonio.lock_for(wp):
        with jsonio.lock_for(log):
            pass
    guard.assert_released()


def test_guard_turns_red_on_a_third_distinct_lock_under_a_leaf(
        tmp_path, guard_factory):
    """working -> edits is legal, but continuing the chain into redo under
    the leaf makes the wait-for graph deeper than the fixed depth-2 fan-out."""
    m = _make_project(tmp_path)
    guard = guard_factory(_roles_for(m))
    wp = revision.working_path(m)
    log = revision.edits_log_path(m)
    redo = revision.edits_redo_path(m)

    with pytest.raises(AssertionError, match="leaf lock must be terminal"):
        with jsonio.lock_for(wp):
            with jsonio.lock_for(log):
                with jsonio.lock_for(redo):
                    pass

    guard.assert_released()
