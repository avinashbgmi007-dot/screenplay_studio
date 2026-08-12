"""Tests for the one-click sample page (POST /api/sample) and the built-in
sample screenplay module."""

import os

from screenplay_parser import parse_fountain
from screenplay_studio.sample import SAMPLE_SCRIPT, SAMPLE_TITLE
from screenplay_studio.manifest import ProjectManifest

import screenplay_studio.webapp_server as webapp_server


class TestSampleContent:
    def test_sample_parses_cleanly(self, tmp_path):
        src = tmp_path / "sample.fountain"
        src.write_text(SAMPLE_SCRIPT, encoding="utf-8")
        doc = parse_fountain(str(src))
        assert doc.scene_count == 3
        # no warnings: the sample must never hit the parser's error path
        assert not doc.warnings
        texts = [e.text for s in doc.scenes for e in s.elements]
        assert any("stops walking" in t for t in texts)
        assert any("MEERA" == e.text for s in doc.scenes for e in s.elements if e.type.value == "character")

    def test_sample_has_dialogue_and_actions(self, tmp_path):
        src = tmp_path / "sample.fountain"
        src.write_text(SAMPLE_SCRIPT, encoding="utf-8")
        doc = parse_fountain(str(src))
        kinds = {e.type.value for s in doc.scenes for e in s.elements}
        assert {"dialogue", "action", "character"} <= kinds


class TestSampleApi:
    def test_create_sample_project(self, tmp_path):
        webapp_server.PROJECTS_DIR = str(tmp_path / "projects")
        os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
        webapp_server.CONFIG["server_url"] = "http://localhost:8080"
        webapp_server.app.config["TESTING"] = True
        client = webapp_server.app.test_client()

        resp = client.post("/api/sample")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == SAMPLE_TITLE
        assert data["stages"]["parse"] == "complete"

        # the manifest really exists on disk with the sample source
        m = ProjectManifest.load(os.path.join(webapp_server.PROJECTS_DIR, "The_Late_Hour"))
        with open(m.source_path, encoding="utf-8") as f:
            assert "The Late Hour" in f.read()

    def test_sample_is_idempotent(self, tmp_path):
        webapp_server.PROJECTS_DIR = str(tmp_path / "projects")
        os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
        webapp_server.CONFIG["server_url"] = "http://localhost:8080"
        webapp_server.app.config["TESTING"] = True
        client = webapp_server.app.test_client()

        first = client.post("/api/sample")
        second = client.post("/api/sample")
        assert first.status_code == 201
        assert second.status_code == 200  # already on the shelf — same project
        assert first.get_json()["project"] == second.get_json()["project"]
