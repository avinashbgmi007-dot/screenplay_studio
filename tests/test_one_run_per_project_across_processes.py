"""One analysis run per project — across OS processes, not just across threads.

Gap 7, filed grade B: "Two OS processes entered the same temporary project's
orchestrator concurrently", recommended fix "shared cross-process run/publish
coordination; reject duplicate active runs by default".

Gap 65 had already narrowed the same hazard from the other side: a draft switch
during a run is refused with 409. That refusal is a `threading.Lock`, so it is
true of two browser tabs and false of a CLI run and the web UI on one project —
each process takes its own private lock, both believe they are the only run, and
both publish. Measured with two real OS processes before the fix: both entered.

`jsonio` has carried a working cross-process lock for years (every store uses
one), so nothing new was needed mechanically — the run simply did not use it.
`jsonio.run_lock` is that same mechanism with one purpose.

Two properties this file is careful about:

1. **The cross-process leg uses real subprocesses.** A thread-based version of
   this test would pass against the broken code, because the threading lock it
   was testing is exactly what already worked in one process.
2. **Nothing waits on a timer.** Each child either reports the refusal or holds
   the lock for a fixed, short span; the assertions are about which of those
   happened, not about how long anything took.

What is deliberately NOT claimed: this makes a second run *refused*, not queued.
A writer who starts a run from the CLI while the UI is analysing gets a clear
refusal and can try again — no run is silently dropped, and no second run is
silently allowed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

import pytest

from screenplay_studio import jsonio

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _child_env() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [REPO_ROOT, os.path.join(REPO_ROOT, "tests"), env.get("PYTHONPATH", "")])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _spawn(source: str, *args) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", source, *[str(a) for a in args]],
        cwd=REPO_ROOT, env=_child_env(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


# ---------------------------------------------------------------------------
# the primitive
# ---------------------------------------------------------------------------

def test_a_second_acquire_in_one_process_is_refused(tmp_path):
    a = jsonio.run_lock(str(tmp_path))
    b = jsonio.run_lock(str(tmp_path))

    assert a.try_acquire() is True
    assert b.try_acquire() is False, "a second run claimed the same project"
    a.release()
    assert b.try_acquire() is True, "the lock did not become available on release"
    b.release()


def test_releasing_twice_is_safe(tmp_path):
    """A release in a `finally` after a failed acquire must not raise."""
    lock = jsonio.run_lock(str(tmp_path))
    lock.release()
    lock.release()
    assert lock.held() is False


def test_the_lock_survives_being_taken_through_a_context_manager(tmp_path):
    with jsonio.run_lock(str(tmp_path)) as held:
        assert held.held() is True
        assert jsonio.run_lock(str(tmp_path)).try_acquire() is False
    assert jsonio.run_lock(str(tmp_path)).try_acquire() is True


def test_the_sidecar_does_not_collide_with_stores(tmp_path):
    """The lock file must not look like a store, or it gets parsed as data."""
    jsonio.run_lock(str(tmp_path)).try_acquire()
    names = os.listdir(tmp_path)
    assert "analyze.run.lock" in names
    assert not [n for n in names if n.endswith(".json")], names


# ---------------------------------------------------------------------------
# the filed hazard: two OS processes
# ---------------------------------------------------------------------------

_HOLD = textwrap.dedent("""
    import sys, time, json, os
    from screenplay_studio import jsonio

    project_dir, hold_seconds, tag = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    lock = jsonio.run_lock(project_dir)
    got = lock.try_acquire()
    print(json.dumps({"tag": tag, "acquired": got}), flush=True)
    if got:
        time.sleep(hold_seconds)
        lock.release()
""")


def _run_child(project_dir: str, hold: float, tag: str):
    p = _spawn(_HOLD, project_dir, hold, tag)
    out, err = p.communicate(timeout=90)
    assert p.returncode == 0, err[-800:]
    return json.loads(out.strip().splitlines()[-1])


def test_two_os_processes_cannot_both_hold_the_run(tmp_path):
    """The defect itself, driven the way it was found: two real processes.

    Process A holds the run for long enough that B is certainly inside its
    attempt window; B must come back refused. The hold is short (0.5s) so the
    test is cheap, and the assertion is on the OUTCOME — B was refused — rather
    than on any timing.
    """
    a = _spawn(_HOLD, str(tmp_path), 0.5, "A")
    # wait for A to report that it holds the lock, so B's attempt cannot win a
    # race it is not meant to be racing
    first = json.loads(a.stdout.readline().strip())
    assert first["acquired"] is True

    b_result = _run_child(str(tmp_path), 0.0, "B")
    a.wait(timeout=90)
    a_result = first

    assert b_result["acquired"] is False, (
        "a second OS process took the run lock while the first held it — this "
        "is the filed gap")
    assert a_result["acquired"] is True


def test_a_dead_process_releases_the_run(tmp_path):
    """A crashed run must not block the project forever.

    This is why the guard is an OS lock rather than a PID file: the kernel drops
    the lock when the descriptor closes, so there is no liveness rule to get
    wrong. Killing a child mid-run is the closest honest simulation of a crash.
    """
    p = _spawn(_HOLD, str(tmp_path), 30.0, "A")
    assert json.loads(p.stdout.readline().strip())["acquired"] is True
    assert jsonio.run_lock(str(tmp_path)).try_acquire() is False

    p.kill()
    p.wait(timeout=30)

    assert jsonio.run_lock(str(tmp_path)).try_acquire() is True, (
        "the run lock outlived the process that held it — a crashed run would "
        "block every later one")


def test_sequential_children_each_get_the_run(tmp_path):
    """Guard against a lock that is never released: the next run must proceed."""
    for tag in ("A", "B", "C"):
        assert _run_child(str(tmp_path), 0.0, tag)["acquired"] is True


# ---------------------------------------------------------------------------
# the routes and the CLI actually use it
# ---------------------------------------------------------------------------

@pytest.fixture()
def webapp_project(tmp_path, monkeypatch):
    """A real project the Flask test client can reach, with the app pointed at it."""
    from screenplay_parser import parse_screenplay
    from screenplay_studio import revision, webapp_server
    from screenplay_studio.manifest import ProjectManifest

    projects = tmp_path / "projects"
    projects.mkdir()
    monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(projects))

    src = tmp_path / "a.fountain"
    src.write_bytes(b"Title: T\nAuthor: A\n\nINT. ROOM - DAY\n\nMARA speaks.\n")
    m = ProjectManifest.create(str(projects / "one"), str(src), title="T")
    parse_screenplay(str(m.source_path)).save(m.parsed_path)
    revision.ensure_working(m)
    return m, webapp_server.app.test_client()


def test_a_draft_switch_is_refused_while_another_process_runs(webapp_project):
    """Gap 65's remaining hole, asserted at the route the writer actually uses.

    The threading lock cannot see a run in another process; the run lock can.
    This holds the run lock the way a CLI run would and then asks the web route
    to switch drafts.
    """
    m, client = webapp_project
    m.active_draft = "draft-b"     # so "original" is a real switch, not a no-op
    m.save()

    held = jsonio.run_lock(m.project_dir)
    assert held.try_acquire() is True
    try:
        response = client.post("/api/projects/one/drafts/activate",
                               json={"name": "original"})
    finally:
        held.release()

    assert response.status_code == 409, response.get_json()
    assert "another process" in response.get_json()["error"]


def test_a_draft_switch_proceeds_once_the_other_process_finished(webapp_project):
    """The guard must not become a wall: no run, no refusal."""
    m, client = webapp_project
    m.active_draft = "draft-b"
    m.save()
    held = jsonio.run_lock(m.project_dir)
    held.try_acquire()
    held.release()

    response = client.post("/api/projects/one/drafts/activate",
                           json={"name": "original"})
    # The switch now gets PAST the run guard, which is the claim: whatever else
    # the route decides about snapshots, it did not refuse for "another process".
    body = response.get_json() or {}
    assert "another process" not in str(body), body


def test_an_analyze_request_is_refused_while_another_process_runs(webapp_project):
    """Duplicate active runs are rejected by default, as the register asked."""
    m, client = webapp_project
    held = jsonio.run_lock(m.project_dir)
    assert held.try_acquire() is True
    try:
        response = client.post("/api/projects/one/analyze", json={})
    finally:
        held.release()

    assert response.status_code == 409, response.get_json()
    assert "another process" in response.get_json()["error"]


def test_the_cli_refuses_a_run_another_process_holds(tmp_path):
    """The CLI is the other process from the filed evidence.

    Driven as a real subprocess through the real entry point, because the claim
    is about a second PROCESS: calling `cmd_run` in-process would exercise the
    same code while proving nothing about the boundary.
    """
    from screenplay_parser import parse_screenplay
    from screenplay_studio import revision
    from screenplay_studio.manifest import ProjectManifest

    src = tmp_path / "a.fountain"
    src.write_bytes(b"Title: T\nAuthor: A\n\nINT. ROOM - DAY\n\nMARA speaks.\n")
    m = ProjectManifest.create(str(tmp_path / "p"), str(src), title="T")
    parse_screenplay(str(m.source_path)).save(m.parsed_path)
    revision.ensure_working(m)

    held = jsonio.run_lock(m.project_dir)
    assert held.try_acquire() is True
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "screenplay_studio.cli", "run",
             m.project_dir, "--only", "analyze"],
            cwd=REPO_ROOT, env=_child_env(), capture_output=True, text=True,
            timeout=120)
    finally:
        held.release()

    assert proc.returncode == 1, (
        f"the CLI started a run another process holds "
        f"(rc={proc.returncode}, out={proc.stdout[-300:]}, err={proc.stderr[-300:]})")
    assert "another process" in (proc.stderr + proc.stdout).lower(), proc.stderr[-400:]


def test_a_refused_cli_run_exits_non_zero(tmp_path):
    """A refusal that exits 0 is the gap-39 bug class, and it would be here.

    The first version of the guard RETURNED 1 from `cmd_run` and `main()`
    discarded the value, so the process exited 0 while printing the refusal.
    Automation would read that as success. Asserted as a subprocess because the
    claim is about the exit status of a real process.
    """
    from screenplay_parser import parse_screenplay
    from screenplay_studio import revision
    from screenplay_studio.manifest import ProjectManifest

    src = tmp_path / "a.fountain"
    src.write_bytes(b"Title: T\nAuthor: A\n\nINT. ROOM - DAY\n\nMARA speaks.\n")
    m = ProjectManifest.create(str(tmp_path / "p"), str(src), title="T")
    parse_screenplay(str(m.source_path)).save(m.parsed_path)
    revision.ensure_working(m)

    held = jsonio.run_lock(m.project_dir)
    assert held.try_acquire() is True
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "screenplay_studio.cli", "run",
             m.project_dir, "--only", "analyze"],
            cwd=REPO_ROOT, env=_child_env(), capture_output=True, text=True,
            timeout=120)
    finally:
        held.release()

    assert proc.returncode == 1, (
        f"a refused run exited {proc.returncode} — a caller cannot tell it "
        f"failed. stderr={proc.stderr[-300:]}")
