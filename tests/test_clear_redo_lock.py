"""P1-4 — `revision.clear_redo` was an unlocked bare `os.remove`.

Three measured failures of the old shape (`if exists: os.remove`):

* while another process held `lock_for(edits.redo.json)` for 3 s, `clear_redo`
  returned in 0.11 ms and deleted the file anyway — the store lock was advisory
  only because this one writer never took it;
* two concurrent `clear_redo` calls raised `FileNotFoundError` in 3996/20000
  runs (20%) from the exists->remove TOCTOU;
* `undo_last_edit` ∥ `clear_redo` left an undone record in NEITHER log 49 times
  out of 200 — permanently unrecoverable.

The fix takes `lock_for(redo_path)` (the working-cycle callers hold
`lock_for(working)` outside it, a fixed working->redo order, so this is a leaf
lock and can never deadlock) and goes through the repo's transient-PermissionError
retry (Windows raises `PermissionError` on a sharing violation — today it
surfaces as a 500 *after* the edit saved). "Already gone" is success.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time
from types import SimpleNamespace

import pytest

from screenplay_studio import jsonio, revision

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_HOLD_REDO = textwrap.dedent(
    """
    import sys, time
    from screenplay_studio import jsonio

    path, hold, flag = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    with jsonio.lock_for(path):
        with open(flag, "w", encoding="utf-8") as f:
            f.write("locked")
        time.sleep(hold)
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


def _redo_store(tmp_path) -> SimpleNamespace:
    """A minimal manifest-shaped object: clear_redo only needs project_dir."""
    m = SimpleNamespace(project_dir=str(tmp_path))
    jsonio.atomic_write_json(
        revision.edits_redo_path(m),
        [{"id": "keep-me", "scene_number": 1, "applied": []}])
    return m


def test_clear_redo_blocks_while_another_process_holds_the_redo_lock(tmp_path, monkeypatch):
    """A CHILD process holding lock_for(edits.redo.json) must stop clear_redo.

    Threads cannot prove this — the failure mode is precisely that the OS
    byte-range lock was never consulted. Broken: clear_redo returned in ~0.1 ms
    and deleted the file under the holder's feet.
    """
    m = _redo_store(tmp_path)
    flag = str(tmp_path / "redo.flag")
    redo_path = revision.edits_redo_path(m)

    proc = subprocess.Popen(
        [sys.executable, "-c", _HOLD_REDO, redo_path, "20", flag],
        cwd=REPO_ROOT, env=_child_env(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.monotonic() + 30
        while not os.path.exists(flag):
            assert proc.poll() is None, f"child died before locking: {proc.communicate()[1]}"
            assert time.monotonic() < deadline, "child never took the lock"
            time.sleep(0.02)

        monkeypatch.setattr(jsonio, "LOCK_TIMEOUT_SECONDS", 0.5)
        started = time.monotonic()
        with pytest.raises(jsonio.StoreLockTimeout):
            revision.clear_redo(m)
        waited = time.monotonic() - started
        assert waited >= 0.4, (
            f"clear_redo gave up after {waited:.3f}s — it never waited for the "
            "child's lock at all (the bare os.remove shape returned instantly)"
        )
        assert os.path.exists(redo_path), (
            "clear_redo DELETED the redo stack out from under a process that "
            "held its lock mid-move — the undone record became unrecoverable"
        )
    finally:
        proc.kill()
        proc.communicate(timeout=30)


def test_clear_redo_on_a_missing_stack_is_not_an_error(tmp_path):
    """exists->remove TOCTOU: two racing clear_redo calls, the loser must be
    silent (already gone == success), not a FileNotFoundError 500."""
    m = SimpleNamespace(project_dir=str(tmp_path))
    assert not os.path.exists(revision.edits_redo_path(m))
    revision.clear_redo(m)          # must not raise
    revision.clear_redo(m)          # twice, for good measure


def test_clear_redo_retries_a_transient_windows_sharing_violation(tmp_path, monkeypatch):
    """On Windows a concurrent reader briefly holds the file open and
    os.remove raises PermissionError (WinError 32). jsonio.retry_permission is
    the repo's bounded-retry helper for exactly that — clear_redo must use it
    instead of surfacing the 500 after the edit already saved."""
    m = _redo_store(tmp_path)
    redo_path = revision.edits_redo_path(m)
    real_remove = os.remove
    calls = {"n": 0}

    def flaky_remove(path):
        calls["n"] += 1
        if calls["n"] == 1:
            raise PermissionError(13, "The process cannot access the file "
                                      "because it is being used by another process")
        real_remove(path)

    monkeypatch.setattr(os, "remove", flaky_remove)
    revision.clear_redo(m)
    monkeypatch.setattr(os, "remove", real_remove)
    assert calls["n"] >= 2, "the sharing violation was not retried"
    assert not os.path.exists(redo_path), "clear_redo did not complete after the transient error"
