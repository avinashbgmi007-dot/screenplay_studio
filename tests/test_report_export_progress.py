"""Tests for the shareable report export (styled HTML) and the live
per-stage analysis progress endpoint."""

import io
import os

import pytest

import screenplay_studio.webapp_server as webapp_server


@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


SAMPLE_SCRIPT = b"""Title: Export Test
Author: Test

INT. STUDY - NIGHT

MARA takes out an old REVOLVER.

MARA
I'll tell you everything when this is over.

CUT TO:

INT. KITCHEN - DAY

Mara sits at the table.

MARA
I promise I'll explain everything.
"""


def _analyzed_project(http_client):
    resp = http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"), "title": "Export Test"},
        content_type="multipart/form-data",
    )
    project = resp.get_json()["project"]
    http_client.post(f"/api/projects/{project}/analyze")
    return project


class TestReportExport:
    def test_export_requires_analysis(self, http_client):
        resp = http_client.post(
            "/api/projects",
            data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"), "title": "Export Test"},
            content_type="multipart/form-data",
        )
        project = resp.get_json()["project"]
        r = http_client.get(f"/api/projects/{project}/report/export")
        assert r.status_code == 400

    def test_export_is_styled_html(self, http_client):
        project = _analyzed_project(http_client)
        resp = http_client.get(f"/api/projects/{project}/report/export")
        assert resp.status_code == 200
        assert "text/html" in resp.content_type
        body = resp.data.decode("utf-8")
        assert "<!DOCTYPE html>" in body
        assert "<h1>" in body            # report title rendered
        assert "Script Doctor Report" in body
        assert "Detailed Analysis" in body
        assert "<style>" in body         # self-contained styling


class TestProgress:
    def test_progress_idle_before_analysis(self, http_client):
        resp = http_client.post(
            "/api/projects",
            data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"), "title": "Export Test"},
            content_type="multipart/form-data",
        )
        project = resp.get_json()["project"]
        data = http_client.get(f"/api/projects/{project}/progress").get_json()
        assert data["status"] in ("idle", "complete")

    def test_progress_complete_after_analysis(self, http_client):
        project = _analyzed_project(http_client)
        data = http_client.get(f"/api/projects/{project}/progress").get_json()
        assert data["status"] == "complete"
        assert data["stage"] == "done"

    def test_progress_file_written(self, http_client):
        project = _analyzed_project(http_client)
        import screenplay_studio.webapp_server as ws
        from screenplay_studio.manifest import ProjectManifest
        m = ProjectManifest.load(ws._project_dir(project))
        assert os.path.exists(m.progress_path)
