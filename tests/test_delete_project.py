"""
Delete a screenplay from the shelf — the writer's own project directory is
removed, nothing outside the projects root is ever touched.

Also pins the Windows lock contract: deleting a directory tree on Windows fails
with a sharing violation while any handle to a file inside it is open, and
`shutil.rmtree` deletes as it walks — so an unretried failure left the project
PARTLY removed (`parsed.json` gone, `project.json` still there: the shelf kept
listing a script the library had silently dropped). The endpoint now retries the
transient case and reports the rest clearly instead of returning a raw 500.
"""

import io
import os
import shutil
import threading

import pytest

from screenplay_studio import jsonio

SAMPLE_SCRIPT = b"""Title: Delete Test
Author: Test

INT. ROOM - NIGHT

MARA enters slowly.

MARA
I can't stay.
"""


@pytest.fixture
def http_client(tmp_path, mock_server):
    import screenplay_studio.webapp_server as webapp_server
    webapp_server.PROJECTS_DIR = str(tmp_path / "delete_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _upload(http_client, title="Delete Test"):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"), "title": title},
        content_type="multipart/form-data",
    )


class TestDeleteProject:
    def test_delete_removes_project(self, http_client):
        project = _upload(http_client).get_json()["project"]
        assert http_client.get(f"/api/projects/{project}").status_code == 200

        resp = http_client.delete(f"/api/projects/{project}")
        assert resp.status_code == 200
        assert resp.get_json() == {"ok": True, "project": project}

        # gone from listing and 404 on direct access
        names = [p["project"] for p in http_client.get("/api/projects").get_json()]
        assert project not in names
        assert http_client.get(f"/api/projects/{project}").status_code == 404

    def test_delete_twice_404(self, http_client):
        project = _upload(http_client).get_json()["project"]
        assert http_client.delete(f"/api/projects/{project}").status_code == 200
        assert http_client.delete(f"/api/projects/{project}").status_code == 404

    def test_unknown_project_404(self, http_client):
        assert http_client.delete("/api/projects/ghost").status_code == 404

    def test_path_traversal_rejected(self, http_client):
        _upload(http_client)
        import screenplay_studio.webapp_server as webapp_server
        # ".." is a single URL segment but resolves outside the projects root
        resp = http_client.delete("/api/projects/..")
        assert resp.status_code == 400
        # multi-segment traversal never reaches the endpoint (405) and the
        # projects dir itself must survive either way
        resp2 = http_client.delete("/api/projects/..%2F..%2Foutside")
        assert resp2.status_code == 405
        assert os.path.isdir(webapp_server.PROJECTS_DIR)

    def test_other_projects_survive(self, http_client):
        a = _upload(http_client, title="Keep A").get_json()["project"]
        b = _upload(http_client, title="Delete B").get_json()["project"]
        http_client.delete(f"/api/projects/{b}")
        names = [p["project"] for p in http_client.get("/api/projects").get_json()]
        assert a in names and b not in names


class TestDeleteSurvivesAWindowsLock:
    """The retry, exercised through the endpoint that was actually failing."""

    @pytest.mark.skipif(os.name != "nt",
                        reason="POSIX unlinks open files; the race does not exist there")
    def test_a_handle_released_mid_flight_still_deletes(self, http_client):
        """A REAL open handle on a file inside the project, released shortly
        after the request starts.

        This is the measured condition rather than a mock: on Windows `open()`
        does not pass FILE_SHARE_DELETE, so the first `rmtree` attempt genuinely
        fails with WinError 32. Without the retry this answers 500 and the
        project survives, partly deleted; with it the delete lands.
        """
        import screenplay_studio.webapp_server as webapp_server

        project = _upload(http_client).get_json()["project"]
        project_dir = os.path.join(webapp_server.PROJECTS_DIR, project)

        files = [os.path.join(dp, f)
                 for dp, _, names in os.walk(project_dir) for f in names]
        assert files, "the upload should have written at least one file"
        # Prefer parsed.json: it is what the writer's library reads, and its
        # loss is what turned a shelf row into a broken project in the measured
        # failure. Any file blocks the delete, so the fallback is equivalent.
        target = next((f for f in files if f.endswith("parsed.json")), files[0])

        held = open(target, "rb")
        # Release well inside the retry window: retry_permission's six attempts
        # are jittered and total under a second, so a holder that lets go after
        # 200 ms is the ordinary case rather than a race against the budget.
        release = threading.Timer(0.2, held.close)
        release.start()
        try:
            resp = http_client.delete(f"/api/projects/{project}")
        finally:
            release.cancel()
            held.close()

        assert resp.status_code == 200, resp.get_data(as_text=True)
        assert not os.path.isdir(project_dir), "the retry should have finished the job"

    def test_a_lock_that_never_clears_is_reported_not_crashed(self, http_client, monkeypatch):
        """Once the retries are exhausted the writer gets JSON — not Flask's HTML
        traceback — and the message admits the tree may be partly removed,
        because that is what a mid-walk failure leaves behind."""
        project = _upload(http_client).get_json()["project"]
        calls = []

        def always_locked(path, *args, **kwargs):
            calls.append(path)
            raise PermissionError(
                13,
                "The process cannot access the file because it is being used by another process",
                None,
                32,  # ERROR_SHARING_VIOLATION
            )

        monkeypatch.setattr(shutil, "rmtree", always_locked)
        resp = http_client.delete(f"/api/projects/{project}")

        assert resp.status_code == 500
        body = resp.get_json()
        assert body and "error" in body, "the front-end reads `error` off the body"
        assert "partly removed" in body["error"]
        assert len(calls) == jsonio.retry_permission.__defaults__[0], (
            "it should have used its whole retry budget")
