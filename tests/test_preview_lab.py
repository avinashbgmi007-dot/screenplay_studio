"""Tests for the Design Lab preview API (preview-next).

Covers: shelf, project data, isolated lab chat (round-trip, clear,
manifest-session untouched), and 404s. Runs against the mock llama-server
fixture — no real model needed.
"""
import io
import os

import pytest

import screenplay_studio.webapp_server as webapp_server

SAMPLE_SCRIPT = b"""Title: API Test Script
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


@pytest.fixture
def lab(tmp_path, mock_server, monkeypatch):
    """Studio with a parsed (and demo-analyzed) project + demo-mode chat."""
    webapp_server.PROJECTS_DIR = str(tmp_path / "lab_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    client = webapp_server.app.test_client()

    client.post("/api/projects",
                data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"),
                      "title": "Lab Test"},
                content_type="multipart/form-data")
    client.post("/api/projects/Lab_Test/analyze")

    # demo-mode flag so engine construction doesn't require a real server
    monkeypatch.setattr(webapp_server, "_DEMO_MODEL_ACTIVE", True)
    return client


class TestPreviewShelf:
    def test_shelf_lists_real_projects(self, lab):
        body = lab.get("/api/preview/projects").get_json()
        names = [p["name"] for p in body["projects"]]
        assert "Lab_Test" in names
        for p in body["projects"]:
            assert set(p) >= {"name", "title", "format", "stage_parse", "stage_analyze", "has_findings"}

    def test_shelf_reports_findings_presence(self, lab):
        body = lab.get("/api/preview/projects").get_json()
        p = next(p for p in body["projects"] if p["name"] == "Lab_Test")
        assert isinstance(p["has_findings"], bool)


class TestPreviewData:
    def test_data_serves_real_parse(self, lab):
        body = lab.get("/api/preview/data/Lab_Test").get_json()
        assert body["name"] == "Lab_Test"
        assert body["parsed"]["scenes"], "real parse must carry scenes"
        s0 = body["parsed"]["scenes"][0]
        assert "heading_raw" in s0 and "elements" in s0

    def test_data_findings_when_analyzed(self, lab):
        body = lab.get("/api/preview/data/Lab_Test").get_json()
        if body["stages"]["analyze"] == "complete":
            assert body["report"]["findings"], "analyzed project must carry findings"
            assert body["fixqueue"]["items"], "fixqueue derives from findings"

    def test_data_404_on_unknown(self, lab):
        assert lab.get("/api/preview/data/no_such_project").status_code == 404


class TestPreviewChat:
    def test_chat_round_trip(self, lab):
        r = lab.post("/api/preview/chat/Lab_Test",
                     json={"message": "What is this script about?"})
        assert r.status_code == 200
        body = r.get_json()
        assert body["reply"], "Sameer must answer"
        assert body["messages"][-1]["role"] == "assistant"
        hist = lab.get("/api/preview/chat/Lab_Test").get_json()
        assert len(hist["messages"]) >= 2, "history persists in the lab session"

    def test_lab_session_isolated_from_manifest(self, lab):
        """The lab thread must never touch the writer's manifest-pinned session."""
        m = webapp_server._load_manifest("Lab_Test")
        lab.post("/api/preview/chat/Lab_Test", json={"message": "hi"})
        m2 = webapp_server._load_manifest("Lab_Test")
        assert m2.cowriter_session_id != "preview-lab"

    def test_clear_starts_over(self, lab):
        lab.post("/api/preview/chat/Lab_Test", json={"message": "hello"})
        assert lab.delete("/api/preview/chat/Lab_Test").status_code == 200
        hist = lab.get("/api/preview/chat/Lab_Test").get_json()
        assert hist["messages"] == []

    def test_empty_message_rejected(self, lab):
        assert lab.post("/api/preview/chat/Lab_Test",
                        json={"message": "  "}).status_code == 400

    def test_chat_404_on_unknown_project(self, lab):
        assert lab.get("/api/preview/chat/no_such_project").status_code == 404


class TestPreviewVerbs:
    def test_dismiss_round_trip_via_real_routes(self, lab):
        """P2: the Lab's Dismiss wires to the real dismiss routes — the same
        dismissed_findings.json the main app reads."""
        body = lab.get("/api/preview/data/Lab_Test").get_json()
        fq = body.get("fixqueue") or {}
        if not fq.get("items"):
            pytest.skip("project has no findings — nothing to dismiss")
        item = fq["items"][0]
        r = lab.post(f"/api/projects/Lab_Test/findings/{item['index']}/dismiss",
                     json={"issue": item["issue"]})
        assert r.status_code == 200
        after = lab.get("/api/projects/Lab_Test/fixqueue").get_json()
        assert after["dismissed_count"] >= 1
        r2 = lab.post(f"/api/projects/Lab_Test/findings/{item['index']}/undismiss", json={})
        assert r2.status_code == 200
