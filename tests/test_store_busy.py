"""A BUSY store is 503 + Retry-After, never a 500 (BE-3, round-3 audit).

`jsonio.StoreLockTimeout` subclasses `RuntimeError` and had no
`@app.errorhandler`, so it fell through to `_unhandled` and the writer was shown

    {"error": "Unexpected error: timed out after 10s waiting for another
               process to release working.json"}

— a crash report for a transient condition, on the two routes that render their
script, with no retry hint and no way to tell it apart from a real fault.
Measured before the fix: `GET /script` and `GET /export` 500 after 10.018s,
`POST /edits/apply` the same.

The classification IS the finding. The store layer already distinguishes MISSING
from UNREADABLE and reports the latter as 503 (`_store_unreadable`); this is the
same standard one layer over, and `busy` is what keeps the two apart so a client
never retries a damaged store.

**Why the contention is a real child process.** In-process contention cannot
produce this timeout at all: the in-process `RLock` is acquired with no timeout,
so two threads simply serialize. The 500 needed a *separate process*, which is
also the documented CLI + webapp configuration — so that is what this drives.
"""

from __future__ import annotations

import io
import json
import os
import textwrap
import time

import pytest

import screenplay_studio.webapp_server as webapp_server
from screenplay_studio import jsonio, revision

from test_undo_redo_lock_race import _child_env, _spawn  # reuse the machinery

SAMPLE_SCRIPT = b"""Title: Busy
Author: Test

INT. STUDY - NIGHT

MARA takes out an old REVOLVER, setting it on the desk.

CUT TO:

INT. KITCHEN - DAY

Mara sits at the table, staring at nothing.
"""

LINE_1_OLD = "MARA takes out an old REVOLVER, setting it on the desk."
LINE_1_NEW = "MARA lays the REVOLVER on the desk."

# Short so the test is fast; the real default is 10s and the point is that the
# route maps the exception, not that the number is any particular value.
TEST_TIMEOUT_S = 0.3

_HOLDER_CHILD = textwrap.dedent(
    """
    import sys, time
    from screenplay_studio.jsonio import lock_for

    target, hold = sys.argv[1], float(sys.argv[2])
    with lock_for(target):
        print("HELD", flush=True)
        time.sleep(hold)
    """
)


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
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "s.fountain"), "title": "Busy"},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (200, 201), resp.get_data(as_text=True)
    return resp.get_json()["project"]


class _Held:
    """A child process holding one store's lock, for the duration of a `with`."""

    def __init__(self, target: str, hold_s: float = 30.0):
        self.target = target
        self.hold_s = hold_s
        self.proc = None

    def __enter__(self):
        self.proc = _spawn(_HOLDER_CHILD, self.target, self.hold_s)
        # Do not proceed until the child actually holds it, or the parent might
        # win the race and the test would pass without any contention at all.
        line = self.proc.stdout.readline().strip()
        assert line == "HELD", f"the holder never took the lock (got {line!r})"
        return self

    def __exit__(self, *exc):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
            try:
                self.proc.communicate(timeout=30)
            except Exception:
                pass


def _working_path(project: str) -> str:
    from screenplay_studio.manifest import ProjectManifest
    m = ProjectManifest.load(webapp_server._project_dir(project))
    return revision.working_path(m)


# ---------------------------------------------------------------------------
# The classification, on the routes that render the writer's script.
# ---------------------------------------------------------------------------

def test_a_busy_store_is_503_with_a_retry_hint_not_a_500(client, monkeypatch):
    """`GET /script` under cross-process contention.

    Asserts all four things that make this a classification fix rather than a
    cosmetic one: the STATUS, the `Retry-After` header, the `busy` flag that
    distinguishes it from damage, and a message a writer can act on.
    """
    project = _upload(client)
    client.get(f"/api/projects/{project}/script")   # materialise working.json
    monkeypatch.setattr(jsonio, "LOCK_TIMEOUT_SECONDS", TEST_TIMEOUT_S)

    with _Held(_working_path(project)):
        t0 = time.monotonic()
        resp = client.get(f"/api/projects/{project}/script")
        elapsed = time.monotonic() - t0

    body = resp.get_json()
    assert resp.status_code == 503, (
        f"a busy store must not read as a crash; got {resp.status_code} {body}")
    assert resp.headers.get("Retry-After") == "1", dict(resp.headers)
    assert body["busy"] is True, body
    assert "Unexpected error" not in body["error"], (
        f"the writer is being shown an internal crash string: {body['error']!r}")
    assert "try again" in body["error"].lower(), body["error"]
    assert elapsed < TEST_TIMEOUT_S * 4, (
        f"the request waited {elapsed:.2f}s — it did not honour the budget")


def test_a_busy_store_is_503_on_a_write_too(client, monkeypatch):
    """The write path, which is the one a lost edit would come from."""
    project = _upload(client)
    client.get(f"/api/projects/{project}/script")
    monkeypatch.setattr(jsonio, "LOCK_TIMEOUT_SECONDS", TEST_TIMEOUT_S)

    with _Held(_working_path(project)):
        resp = client.post(f"/api/projects/{project}/edits/apply", json={
            "scene_number": 1,
            "replacements": [{"old": LINE_1_OLD, "new": LINE_1_NEW}],
        })

    assert resp.status_code == 503, resp.get_data(as_text=True)
    assert resp.headers.get("Retry-After") == "1"
    assert resp.get_json()["busy"] is True


def test_an_uncontended_read_still_answers_200(client, monkeypatch):
    """The control: the 503 must be about contention, not about the handler
    swallowing every read. Without this, a blanket-503 regression would pass."""
    project = _upload(client)
    monkeypatch.setattr(jsonio, "LOCK_TIMEOUT_SECONDS", TEST_TIMEOUT_S)
    resp = client.get(f"/api/projects/{project}/script")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["scenes"], "the script came back empty"


def test_a_damaged_store_is_still_503_but_is_not_busy(client):
    """Damage also answers 503, so `busy` is what stops a client retrying it.

    Without this the SPA's 503 retry would hammer a store that can never
    recover, and the writer would wait a second per attempt for nothing.
    """
    project = _upload(client)
    project_dir = webapp_server._project_dir(project)
    with open(os.path.join(project_dir, "edits.json"), "w", encoding="utf-8") as f:
        f.write("{ this is not json")

    resp = client.get(f"/api/projects/{project}/edits")
    body = resp.get_json()
    assert resp.status_code == 503, resp.get_data(as_text=True)
    assert body.get("unreadable") is True, body
    assert not body.get("busy"), (
        "a damaged store reported itself as busy — a client would retry forever")


# ---------------------------------------------------------------------------
# The amplifier: budgets compose instead of multiplying.
# ---------------------------------------------------------------------------

def test_lock_deadline_caps_a_nested_acquisition(tmp_path):
    """A block's deadline wins over the per-acquisition default.

    This is the BE-3 amplifier: `reset_working` takes three leaf locks while
    holding the cycle lock, and each used to start a FRESH
    `LOCK_TIMEOUT_SECONDS` — so one stuck file held the cycle lock for ~3x the
    budget while every other request expired its own. `LOCK_TIMEOUT_SECONDS` is
    deliberately left at its real 10s default here, so the assertion below is
    about the block's budget and not about a patched number.
    """
    target = str(tmp_path / "leaf.json")
    open(target, "w", encoding="utf-8").write("[]")

    with _Held(target):
        t0 = time.monotonic()
        with pytest.raises(jsonio.StoreLockTimeout):
            with jsonio.lock_deadline(0.4):
                with jsonio.lock_for(target):
                    pass
        elapsed = time.monotonic() - t0

    assert elapsed < 3.0, (
        f"the block's 0.4s deadline did not apply — the acquisition waited "
        f"{elapsed:.2f}s, i.e. it started a fresh {jsonio.LOCK_TIMEOUT_SECONDS}s "
        "budget instead of sharing the block's")


def test_lock_deadline_does_not_leak_past_its_block(tmp_path):
    """After the block, an uncontended acquisition must behave normally —
    otherwise the deadline would silently shorten every later lock in the
    thread, and a slow-but-healthy write would start failing."""
    target = str(tmp_path / "leaf.json")
    with jsonio.lock_deadline(0.05):
        pass
    with jsonio.lock_for(target):
        jsonio.atomic_write_json(target, {"ok": True})
    assert json.loads(open(target, encoding="utf-8").read()) == {"ok": True}
    assert not getattr(jsonio._deadline_local, "stack", []), (
        "the deadline stack was not unwound")


def test_reset_working_still_resets_under_one_budget(tmp_path):
    """The call site that uses it still does its job."""
    from test_undo_redo_lock_race import LINE_1_OLD as OLD, _apply, _make_project

    m = _make_project(tmp_path)
    _apply(m, 1, OLD, LINE_1_NEW, "e1-busy")
    assert revision.edits_log(m), "the fixture did not seed an edit"

    revision.reset_working(m)

    assert not os.path.exists(revision.working_path(m))
    assert not os.path.exists(revision.edits_log_path(m))
    assert not os.path.exists(revision.edits_redo_path(m))
