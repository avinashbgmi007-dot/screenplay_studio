"""Cross-process store safety — BE-H2 (torn/lost writes) and BE-H4 (contended
reads reported as permanent damage).

The CLI and the webapp both write the same project directory; AGENTS.md
documents that as a supported configuration. Every lock in this codebase used to
be process-local (`threading.RLock` / `Lock`), which cannot serialize two
processes at all, and `atomic_write_json` wrote through a FIXED `<store>.tmp`
name that every process shared — so two writers interleaved their bytes into one
buffer and the survivor was renamed into the store.

These tests spawn REAL child processes, because that is the only way to observe
the defect: an in-process test passes on the broken code. Verified by mutation —
dropping the OS lock (leaving only the RLock) turns the first two red.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import threading
import time
from types import SimpleNamespace

import pytest

from screenplay_studio import jsonio, notes, stash_store

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHILD_TIMEOUT = 240


def _child_env() -> dict:
    """Give a child this process's import path, so it finds the repo AND the
    test dependencies however pytest happened to be launched."""
    env = dict(os.environ)
    parts = [REPO_ROOT] + [p for p in sys.path if p]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _spawn(source: str, *args) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", source, *args],
        cwd=REPO_ROOT, env=_child_env(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


# ---------------------------------------------------------------------------
# 1. The defect itself: concurrent writers on ONE store, from separate processes
# ---------------------------------------------------------------------------

_ACCUMULATE = textwrap.dedent(
    """
    import sys, time
    from screenplay_studio import jsonio

    path, worker, rounds, start_at = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4])
    # start-gate: every child begins hammering at the same instant, so the
    # windows genuinely overlap instead of the children politely queueing up.
    while time.time() < start_at:
        time.sleep(0.001)
    for k in range(rounds):
        with jsonio.lock_for(path):
            data = jsonio.load_json_store(path, {})
            data[worker] = k
            jsonio.atomic_write_json(path, data)
    """
)


def test_concurrent_processes_lose_no_update_and_never_tear_the_store(tmp_path):
    """4 processes x 40 locked load-modify-write cycles on one store.

    Keys only ever accumulate, so a correct serialization must leave every
    worker's key in the final file. Before the fix this lost updates and/or left
    the store unparseable, and the child raised on the torn read.
    """
    path = str(tmp_path / "shared.json")
    workers, rounds = 4, 40
    start_at = time.time() + 1.5

    procs = [
        _spawn(_ACCUMULATE, path, f"w{i}", str(rounds), repr(start_at))
        for i in range(workers)
    ]
    failures = []
    for i, proc in enumerate(procs):
        _out, err = proc.communicate(timeout=CHILD_TIMEOUT)
        if proc.returncode != 0:
            failures.append(f"worker {i} exited {proc.returncode}: {err.strip()[-400:]}")

    assert not failures, "child processes failed:\n" + "\n".join(failures)
    assert set(jsonio.load_json_store(path, {})) == {f"w{i}" for i in range(workers)}, (
        "lost updates: every worker's key must survive"
    )
    assert [f for f in os.listdir(tmp_path) if f.endswith(".tmp")] == [], (
        "a temp file was left behind"
    )


# ---------------------------------------------------------------------------
# 2. The lock is genuinely cross-PROCESS (the entire point of BE-H2)
# ---------------------------------------------------------------------------

_HOLD = textwrap.dedent(
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


def test_the_lock_is_actually_cross_process(tmp_path, monkeypatch):
    """A lock held by ANOTHER process must block us, and the wait must be
    bounded. An in-process RLock cannot do this — which was the whole defect —
    so the proof has to come from a second process rather than a thread."""
    path = str(tmp_path / "held.json")
    flag = str(tmp_path / "held.flag")
    jsonio.atomic_write_json(path, {"seed": 1})   # creates the lock sidecar

    proc = _spawn(_HOLD, path, "20", flag)
    try:
        deadline = time.monotonic() + 30
        while not os.path.exists(flag):
            assert proc.poll() is None, f"child died before locking: {proc.communicate()[1]}"
            assert time.monotonic() < deadline, "child never took the lock"
            time.sleep(0.02)

        monkeypatch.setattr(jsonio, "LOCK_TIMEOUT_SECONDS", 0.5)
        started = time.monotonic()
        with pytest.raises(jsonio.StoreLockTimeout):
            with jsonio.lock_for(path):
                pytest.fail("acquired a lock another process was holding")
        waited = time.monotonic() - started
        assert waited < 10, f"gave up after {waited:.1f}s — the wait must be bounded"
    finally:
        proc.kill()
        proc.communicate(timeout=30)


# ---------------------------------------------------------------------------
# 3. BE-H4: contended is not damaged
# ---------------------------------------------------------------------------


def test_transient_read_contention_is_retried_not_reported_as_damage(tmp_path, monkeypatch):
    """A read that fails only because a writer briefly holds the file open must
    be RETRIED, not escalated to StoreUnreadable ("this store is damaged",
    HTTP 503). Measured before this: 785 such escalations in one 4-process run.
    """
    path = str(tmp_path / "store.json")
    jsonio.atomic_write_json(path, {"kept": True})

    real_read = jsonio._read_text
    calls = {"n": 0}

    def flaky(p):
        calls["n"] += 1
        if calls["n"] == 1:
            raise PermissionError(13, "Access is denied")   # sharing violation
        return real_read(p)

    monkeypatch.setattr(jsonio, "_read_text", flaky)
    assert jsonio.load_json_store(path, None) == {"kept": True}
    assert calls["n"] == 2, "the read was not retried"


def test_a_genuinely_unreadable_store_still_raises(tmp_path, monkeypatch):
    """The retry must not swallow a real failure — flag, don't drop."""
    path = str(tmp_path / "store.json")
    jsonio.atomic_write_json(path, {"kept": True})

    def always_denied(_p):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(jsonio, "_read_text", always_denied)
    with pytest.raises(jsonio.StoreUnreadable):
        jsonio.load_json_store(path, None)


# ---------------------------------------------------------------------------
# 4. BE-H3: the writer's own stores must not lose a concurrent entry
# ---------------------------------------------------------------------------


def _in_parallel(fn, args, values) -> None:
    """Run `fn(*args, value)` once per value, all starting together."""
    barrier = threading.Barrier(len(values))
    errors: list[str] = []

    def run(value):
        try:
            barrier.wait(timeout=30)
            fn(*args, value)
        except Exception as e:                      # noqa: BLE001 — reported below
            errors.append(repr(e))

    threads = [threading.Thread(target=run, args=(v,)) for v in values]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, errors


def test_two_concurrent_note_adds_both_survive(tmp_path, monkeypatch):
    """The writer's margin notes. Measured before this: two adds left ONE note,
    because the second loaded the pre-add list and wrote it back over the first.
    """
    d = tmp_path / "proj"
    d.mkdir()
    m = SimpleNamespace(project_dir=str(d))

    real_load = notes._load_raw

    def slow_load(mm):
        data = real_load(mm)
        time.sleep(0.2)          # widen the read -> write window
        return data

    monkeypatch.setattr(notes, "_load_raw", slow_load)
    _in_parallel(notes.add_note, (m, 1), ["note A", "note B"])

    assert len(notes.load_notes(m)) == 2


def test_two_concurrent_stash_adds_both_survive(tmp_path, monkeypatch):
    """The Stash — same shape, same defect, same fix."""
    d = tmp_path / "proj"
    d.mkdir()

    real_load = stash_store.load_stash

    def slow_load(project_dir):
        data = real_load(project_dir)
        time.sleep(0.2)
        return data

    monkeypatch.setattr(stash_store, "load_stash", slow_load)
    _in_parallel(stash_store.add_to_stash, (str(d),), ["line A", "line B"])

    assert len(stash_store.load_stash(str(d))) == 2


# ---------------------------------------------------------------------------
# 5. The lock sidecar must stay invisible to the product
# ---------------------------------------------------------------------------


def test_a_lock_sidecar_never_becomes_a_shelf_card(tmp_path, monkeypatch):
    """jsonio drops `<store>.lock` beside every store it writes, and one of them
    (writer_profile.json.lock) lands directly in PROJECTS_DIR. It is a FILE, so
    it must never reach ProjectManifest.load -> check_safe_id, whose ValueError
    the shelf route's `except Exception` would render as a phantom "unreadable"
    project on the writer's shelf."""
    import screenplay_studio.webapp_server as webapp_server

    monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(tmp_path))
    client = webapp_server.app.test_client()
    # 201 on first create, 200 when the deduplicated sample already exists
    assert client.post("/api/sample").status_code < 300   # one REAL project

    # exactly what a store write in PROJECTS_DIR leaves behind
    jsonio.atomic_write_json(str(tmp_path / "writer_profile.json"), {})

    cards = client.get("/api/projects").get_json()
    names = [c["project"] for c in cards]
    assert "writer_profile.json.lock" not in names, "a lock sidecar became a shelf card"
    assert not any(c.get("unreadable") for c in cards), cards
    assert names, "the real project vanished from the shelf"


def test_the_backup_archive_excludes_lock_sidecars(tmp_path, monkeypatch):
    """A backup is the writer's desk, not our plumbing."""
    import io
    import zipfile

    import screenplay_studio.webapp_server as webapp_server

    monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(tmp_path))
    client = webapp_server.app.test_client()
    client.post("/api/sample")
    name = client.get("/api/projects").get_json()[0]["project"]

    resp = client.get(f"/api/projects/{name}/backup")
    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
        assert [n for n in zf.namelist() if n.endswith(".lock")] == []


# ---------------------------------------------------------------------------
# 6. The primitive's own contract
# ---------------------------------------------------------------------------


def test_the_lock_is_reentrant_and_leaves_no_temp_files(tmp_path):
    """A store holds the lock across its load-modify-write while
    atomic_write_json re-enters it — that nesting must not deadlock."""
    path = str(tmp_path / "store.json")
    with jsonio.lock_for(path):
        with jsonio.lock_for(path):
            jsonio.atomic_write_json(path, {"nested": True})
            assert jsonio.load_json_store(path, None) == {"nested": True}
    assert jsonio.load_json_store(path, None) == {"nested": True}
    assert [f for f in os.listdir(tmp_path) if f.endswith(".tmp")] == []


def test_a_failed_write_leaves_no_temp_file(tmp_path):
    """`object()` cannot be serialized, so json.dump raises part-way through."""
    path = str(tmp_path / "store.json")
    with pytest.raises(TypeError):
        jsonio.atomic_write_json(path, {"bad": object()})
    assert [f for f in os.listdir(tmp_path) if f.endswith(".tmp")] == []


def test_reading_a_missing_store_creates_nothing(tmp_path):
    """A read must not mutate the directory — not even a lock sidecar."""
    assert jsonio.load_json_store(str(tmp_path / "absent.json"), "DEFAULT") == "DEFAULT"
    assert os.listdir(tmp_path) == []


def test_the_lock_sidecar_sits_beside_its_store(tmp_path):
    path = str(tmp_path / "store.json")
    jsonio.atomic_write_json(path, {"a": 1})
    assert sorted(os.listdir(tmp_path)) == ["store.json", "store.json.lock"]
