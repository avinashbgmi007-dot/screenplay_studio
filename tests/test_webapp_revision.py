"""Webapp API tests for the revision loop: script viewer, rewrite, apply,
reset, and export endpoints."""

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


SAMPLE_SCRIPT = b"""Title: Revision Test Script
Author: Test

INT. STUDY - NIGHT

MARA takes out an old REVOLVER, setting it on the desk.

MARA
I'll tell you everything when this is over.

CUT TO:

INT. STUDY - NIGHT

The REVOLVER is still there, untouched.

MARA
Some things are better left alone.
"""


def _upload(http_client, filename="script.fountain"):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), filename), "title": "Revision Test"},
        content_type="multipart/form-data",
    )


class TestScriptViewer:
    def test_script_endpoint_returns_working_copy(self, http_client):
        project = _upload(http_client).get_json()["project"]
        resp = http_client.get(f"/api/projects/{project}/script")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["scene_count"] == 2
        assert data["scenes"][0]["heading_raw"].startswith("INT.")

    def test_script_endpoint_404(self, http_client):
        resp = http_client.get("/api/projects/nope/script")
        assert resp.status_code == 404

    def test_edits_endpoint_empty_before_any_edit(self, http_client):
        project = _upload(http_client).get_json()["project"]
        resp = http_client.get(f"/api/projects/{project}/edits")
        assert resp.status_code == 200
        assert resp.get_json()["edits"] == []


class TestRewriteFlow:
    def _analyzed_project(self, http_client):
        project = _upload(http_client).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        return project

    def test_rewrite_proposes_candidates_without_applying(self, http_client):
        project = self._analyzed_project(http_client)
        resp = http_client.post(f"/api/projects/{project}/rewrite", json={
            "scene_number": 1,
            "finding_index": 0,
            "instruction": "Make it less on the nose.",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["replacements"]
        assert data["scene_text"]
        assert "I'll tell you everything when this is over." in data["scene_text"]

    def test_rewrite_missing_scene_404(self, http_client):
        project = self._analyzed_project(http_client)
        resp = http_client.post(f"/api/projects/{project}/rewrite", json={"scene_number": 99})
        assert resp.status_code == 404

    def test_rewrite_requires_scene_number(self, http_client):
        project = self._analyzed_project(http_client)
        resp = http_client.post(f"/api/projects/{project}/rewrite", json={})
        assert resp.status_code == 400

    def test_apply_changes_working_copy_and_marks_finding_addressed(self, http_client):
        project = self._analyzed_project(http_client)
        resp = http_client.post(f"/api/projects/{project}/rewrite", json={"scene_number": 1, "finding_index": 0})
        candidates = resp.get_json()["replacements"]

        apply_resp = http_client.post(f"/api/projects/{project}/edits/apply", json={
            "scene_number": 1,
            "replacements": candidates,
        })
        assert apply_resp.status_code == 200
        data = apply_resp.get_json()
        assert len(data["applied"]) == len(candidates)
        assert data["findings_status"]["summary"]["addressed"] >= 1
        assert "[fixed]" in data["scene_text_after"]

        script = http_client.get(f"/api/projects/{project}/script").get_json()
        scene1_texts = [e["text"] for e in script["scenes"][0]["elements"]]
        assert any("[fixed]" in t for t in scene1_texts)
        assert "I'll tell you everything when this is over." not in scene1_texts

    def test_edits_log_records_applied_edits(self, http_client):
        project = self._analyzed_project(http_client)
        http_client.post(f"/api/projects/{project}/rewrite", json={"scene_number": 1, "finding_index": 0})
        candidates = http_client.post(
            f"/api/projects/{project}/rewrite", json={"scene_number": 1, "finding_index": 0}
        ).get_json()["replacements"]
        http_client.post(f"/api/projects/{project}/edits/apply", json={"scene_number": 1, "replacements": candidates})

        edits = http_client.get(f"/api/projects/{project}/edits").get_json()
        assert len(edits["edits"]) == 1
        assert edits["edits"][0]["scene_number"] == 1

    def test_reset_discards_edits(self, http_client):
        project = self._analyzed_project(http_client)
        candidates = http_client.post(
            f"/api/projects/{project}/rewrite", json={"scene_number": 1, "finding_index": 0}
        ).get_json()["replacements"]
        http_client.post(f"/api/projects/{project}/edits/apply", json={"scene_number": 1, "replacements": candidates})

        resp = http_client.post(f"/api/projects/{project}/edits/reset")
        assert resp.status_code == 200
        script = http_client.get(f"/api/projects/{project}/script").get_json()
        scene1_texts = [e["text"] for e in script["scenes"][0]["elements"]]
        assert "I'll tell you everything when this is over." in scene1_texts
        assert not any("[fixed]" in t for t in scene1_texts)


class TestExport:
    @pytest.mark.parametrize("fmt,mime,needle", [
        ("fountain", "text/plain", b"Title: Revision Test Script"),
        ("fdx", "application/xml", b"<FinalDraft"),
        ("txt", "text/plain", b"INT. STUDY - NIGHT"),
    ])
    def test_export_formats(self, http_client, fmt, mime, needle):
        project = _upload(http_client).get_json()["project"]
        resp = http_client.get(f"/api/projects/{project}/export?format={fmt}")
        assert resp.status_code == 200
        assert mime in resp.content_type
        assert needle in resp.data

    def test_export_includes_edits(self, http_client):
        project = _upload(http_client).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        candidates = http_client.post(
            f"/api/projects/{project}/rewrite", json={"scene_number": 1, "finding_index": 0}
        ).get_json()["replacements"]
        http_client.post(f"/api/projects/{project}/edits/apply", json={"scene_number": 1, "replacements": candidates})

        resp = http_client.get(f"/api/projects/{project}/export?format=fountain")
        assert b"[fixed]" in resp.data
        assert b"I'll tell you everything when this is over." not in resp.data

    def test_bad_format_rejected(self, http_client):
        project = _upload(http_client).get_json()["project"]
        resp = http_client.get(f"/api/projects/{project}/export?format=docx")
        assert resp.status_code == 400

    def test_exported_fdx_reparses_to_same_structure(self, http_client, tmp_path):
        project = _upload(http_client).get_json()["project"]
        resp = http_client.get(f"/api/projects/{project}/export?format=fdx")
        p = tmp_path / "out.fdx"
        p.write_bytes(resp.data)
        from screenplay_parser import parse_fdx
        doc = parse_fdx(str(p))
        assert doc.scene_count == 2
        assert doc.title == "Revision Test Script"
