"""The analyze pre-flight is the one part of the handler OUTSIDE its try block.

It does real work — rewrites the manifest, resets the progress heartbeat — and if
it raised, the exception escaped the handler entirely. A Flask dev server answers
a throwable it cannot convert by closing the connection with **no reply**, so the
caller saw a dead socket (`requests`: `RemoteDisconnected`) instead of a reason.
Measured on the E2E harness: the studio's own log carried
`[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] … progress.json`, the audit's
force-trigger recorded "not accepted", and the stage then waited its full 3600 s
budget for a run that had never started.

Two things are pinned here:

1. the heartbeat reset **writes** rather than **deletes**, so there is nothing
   for a handle race or an instrumented environment to refuse; and
2. anything else that fails in the pre-flight returns a clear JSON error, never
   a dropped connection.

Why writing is the right shape, not just a workaround: `progress.json` is a
heartbeat the pipeline's first event overwrites within seconds, so the delete was
never load-bearing. Replacing it with a `running` write gives the same guarantee
(no poller can read the old `done`) and removes the failure mode entirely.
"""

import io
import json
import os
from pathlib import Path

import pytest

from screenplay_studio import webapp_server
from screenplay_studio.jsonio import atomic_write_json
from screenplay_studio.manifest import ProjectManifest

SAMPLE_SCRIPT = b"""Title: Preflight Test
Author: Test

INT. ROOM - NIGHT

MARA enters slowly.

MARA
I can't stay.
"""


@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _manifest(tmp_path):
    return ProjectManifest(project_dir=str(tmp_path), title="t",
                           source_filename="s.fountain", source_format=".fountain")


def _heartbeat(m):
    return json.loads(Path(m.progress_path).read_text(encoding="utf-8"))


def _upload(http_client):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"), "title": "Preflight"},
        content_type="multipart/form-data",
    )


class TestTheHeartbeatIsResetByWritingNotDeleting:
    def test_a_stale_done_is_replaced_by_running(self, tmp_path):
        m = _manifest(tmp_path)
        atomic_write_json(m.progress_path, {"stage": "done", "status": "complete",
                                            "detail": "Analysis complete", "ts": 1.0})
        webapp_server._start_progress_heartbeat(m)
        data = _heartbeat(m)
        assert data["status"] == "running", data
        assert data["stage"] == "analyze", data
        assert data["ts"] > 1.0, (
            "the heartbeat must be NEWER — every poller keys on `ts`, so a "
            "same-or-older stamp would let the previous run's state pass for this one's")

    def test_the_file_is_written_not_removed(self, tmp_path):
        """The whole point of the change: no delete, so nothing to refuse."""
        m = _manifest(tmp_path)
        webapp_server._start_progress_heartbeat(m)
        assert os.path.exists(m.progress_path)

    def test_a_refused_delete_cannot_break_it(self, tmp_path, monkeypatch):
        """Pin the SHAPE, not just the behaviour.

        `os.remove` is made to raise, which is what a Windows handle race or an
        instrumented environment does. The reset must still work — this is the
        exact failure that dropped the connection and cost 20 minutes of silence
        on the harness.
        """
        m = _manifest(tmp_path)
        atomic_write_json(m.progress_path, {"stage": "done", "status": "complete", "ts": 1.0})

        def refuse(path, *a, **kw):
            raise PermissionError(13, "Access is denied")

        monkeypatch.setattr(os, "remove", refuse)
        webapp_server._start_progress_heartbeat(m)  # must not raise
        assert _heartbeat(m)["status"] == "running"


class TestPreflightFailsLoudly:
    def test_a_failing_manifest_save_returns_json_not_a_dead_socket(self, http_client, monkeypatch):
        """The guarantee the whole endpoint depends on.

        If this ever regresses the caller sees `RemoteDisconnected` — which is
        indistinguishable from a network fault, and is exactly how a missing
        error message became a 20-minute silence on the harness.
        """
        project = _upload(http_client).get_json()["project"]

        def refuse_to_save(self):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(ProjectManifest, "save", refuse_to_save)
        try:
            resp = http_client.post(f"/api/projects/{project}/analyze", json={"force": True})
        except OSError as e:
            # Converted to a NAMED failure on purpose: an escaping exception is
            # an ERROR in pytest, which reads like a broken test rather than a
            # broken product. This is what it means in production.
            pytest.fail(
                f"the pre-flight raised out of the handler ({e}) — Werkzeug answers that by "
                "closing the connection with no reply, so the client sees RemoteDisconnected "
                "instead of a reason")
        assert resp.status_code == 500, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body and "Could not start the analysis" in body.get("error", ""), body
