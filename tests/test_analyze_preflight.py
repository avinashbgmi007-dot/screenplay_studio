"""The analyze pre-flight is the one part of the handler OUTSIDE its try block.

It does real work — rewrites the manifest, clears the transient progress
heartbeat — and if it raised, the exception escaped the handler entirely. A Flask
dev server that raises before it can write a response closes the connection with
NO reply, so the caller saw a dead socket (`requests`: `RemoteDisconnected`)
instead of a reason.

That is not hypothetical. Measured on the E2E harness: a refused
`os.remove(progress.json)` in the pre-flight dropped the connection, the audit's
force-trigger recorded "not accepted", and the stage then waited its full
3600 s budget for a run that had never started — 20 minutes of silence that read
exactly like a slow 35B model. Two separate defects, both pinned here:

1. a failed heartbeat clear must not cost the writer an analysis at all
   (`progress.json` is a heartbeat, not their data; the pipeline's first event
   overwrites it within seconds), and
2. anything else that fails in the pre-flight must return a clear JSON error,
   never a dropped connection.
"""

import io
import os

import pytest

from screenplay_studio import webapp_server
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


def _upload(http_client):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"), "title": "Preflight"},
        content_type="multipart/form-data",
    )


class TestHeartbeatClearIsNeverFatal:
    def test_a_refused_delete_is_reported_and_survived(self, tmp_path, monkeypatch, capsys):
        """The clear exists so a poller can't read the PREVIOUS run's `done`.

        But it is a heartbeat, not the writer's data, and the pipeline's first
        event overwrites it within seconds — so a refusal must be reported and
        then shrugged off, never turned into a lost analysis. (Windows races an
        open handle; an instrumented or sandboxed environment can refuse
        outright. Both measured.)
        """
        m = _manifest(tmp_path)
        with open(m.progress_path, "w", encoding="utf-8") as f:
            f.write('{"stage": "done", "status": "complete", "ts": 1}')

        real_remove = os.remove

        def refuse_only_the_heartbeat(path, *a, **kw):
            if os.path.abspath(str(path)) == os.path.abspath(m.progress_path):
                raise PermissionError(13, "Access is denied")
            return real_remove(path, *a, **kw)

        monkeypatch.setattr(os, "remove", refuse_only_the_heartbeat)
        webapp_server._clear_progress(m)  # must not raise
        assert os.path.exists(m.progress_path), "it must not pretend the clear worked"
        assert "could not clear" in capsys.readouterr().out, (
            "a refusal must be visible in the log, not swallowed")

    def test_the_clear_still_happens_when_it_can(self, tmp_path):
        m = _manifest(tmp_path)
        with open(m.progress_path, "w", encoding="utf-8") as f:
            f.write("{}")
        webapp_server._clear_progress(m)
        assert not os.path.exists(m.progress_path)

    def test_an_absent_heartbeat_is_not_an_error(self, tmp_path, capsys):
        webapp_server._clear_progress(_manifest(tmp_path))
        assert capsys.readouterr().out == "", "nothing to clear is the normal case"


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
