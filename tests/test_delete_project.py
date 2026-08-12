"""
Delete a screenplay from the shelf — the writer's own project directory is
removed, nothing outside the projects root is ever touched.
"""

import io
import os

import pytest

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
