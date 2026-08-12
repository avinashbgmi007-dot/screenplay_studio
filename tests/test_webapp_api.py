"""Tests for screenplay_studio.webapp_server — the HTTP API backing the web UI."""
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


def _upload(http_client, filename="script.fountain"):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), filename), "title": "API Test"},
        content_type="multipart/form-data",
    )


class TestStaticServing:
    def test_index_served(self, http_client):
        resp = http_client.get("/")
        assert resp.status_code == 200
        assert b"Script Doctor Studio" in resp.data

    def test_css_served(self, http_client):
        resp = http_client.get("/style.css")
        assert resp.status_code == 200

    def test_js_served(self, http_client):
        resp = http_client.get("/app.js")
        assert resp.status_code == 200


class TestConfig:
    def test_get_config(self, http_client):
        resp = http_client.get("/api/config")
        assert resp.status_code == 200
        assert "server_url" in resp.get_json()

    def test_set_config(self, http_client):
        resp = http_client.post("/api/config", json={"server_url": "http://localhost:9999"})
        assert resp.status_code == 200
        assert resp.get_json()["server_url"] == "http://localhost:9999"


class TestProjectLifecycle:
    def test_upload_creates_project_and_parses(self, http_client):
        resp = _upload(http_client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["stages"]["parse"] == "complete"
        assert data["stages"]["analyze"] == "pending"

    def test_upload_with_no_file_returns_400(self, http_client):
        resp = http_client.post("/api/projects", data={}, content_type="multipart/form-data")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_get_nonexistent_project_404(self, http_client):
        resp = http_client.get("/api/projects/nope")
        assert resp.status_code == 404

    def test_list_projects_after_upload(self, http_client):
        _upload(http_client)
        resp = http_client.get("/api/projects")
        assert resp.status_code == 200
        projects = resp.get_json()
        assert len(projects) == 1
        assert projects[0]["title"] == "API Test"

    def test_analyze_full_flow(self, http_client):
        upload_resp = _upload(http_client)
        project = upload_resp.get_json()["project"]

        resp = http_client.post(f"/api/projects/{project}/analyze")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["stages"]["analyze"] == "complete"

        report_resp = http_client.get(f"/api/projects/{project}/report")
        assert report_resp.status_code == 200
        assert "findings" in report_resp.get_json()

    def test_report_before_analyze_returns_400(self, http_client):
        upload_resp = _upload(http_client)
        project = upload_resp.get_json()["project"]
        resp = http_client.get(f"/api/projects/{project}/report")
        assert resp.status_code == 400

    def test_force_rerun_actually_reruns(self, http_client, tmp_path):
        upload_resp = _upload(http_client)
        project = upload_resp.get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        report_path = webapp_server._project_dir(project) + os.sep + "report.findings.json"
        import json
        first = json.load(open(report_path, encoding="utf-8"))

        # without force, a second call short-circuits (no re-analysis)
        http_client.post(f"/api/projects/{project}/analyze")
        assert json.load(open(report_path, encoding="utf-8")) == first

        # with force, the stage resets and the report is regenerated
        resp = http_client.post(f"/api/projects/{project}/analyze", json={"force": True})
        assert resp.status_code == 200
        assert resp.get_json()["stages"]["analyze"] == "complete"
        second = json.load(open(report_path, encoding="utf-8"))
        assert second == first  # same mock output, but it genuinely re-ran
        # prove the re-run happened: progress.json exists from the fresh run
        from screenplay_studio.manifest import ProjectManifest
        m = ProjectManifest.load(webapp_server._project_dir(project))
        assert os.path.exists(m.progress_path)


class TestChatFlow:
    def _setup_analyzed_project(self, http_client):
        upload_resp = _upload(http_client)
        project = upload_resp.get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        return project

    def test_start_chat(self, http_client):
        project = self._setup_analyzed_project(http_client)
        resp = http_client.post(f"/api/projects/{project}/chat/start")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["session_id"]
        assert data["branch"] == "main"

    def test_send_message_and_get_reply(self, http_client):
        project = self._setup_analyzed_project(http_client)
        sid = http_client.post(f"/api/projects/{project}/chat/start").get_json()["session_id"]

        resp = http_client.post(
            f"/api/projects/{project}/chat/sessions/{sid}/messages",
            json={"text": "What about the revolver?"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["reply"]
        assert len(data["messages"]) == 2

    def test_empty_message_rejected(self, http_client):
        project = self._setup_analyzed_project(http_client)
        sid = http_client.post(f"/api/projects/{project}/chat/start").get_json()["session_id"]
        resp = http_client.post(f"/api/projects/{project}/chat/sessions/{sid}/messages", json={"text": "  "})
        assert resp.status_code == 400

    def test_fork_and_isolation(self, http_client):
        project = self._setup_analyzed_project(http_client)
        sid = http_client.post(f"/api/projects/{project}/chat/start").get_json()["session_id"]
        http_client.post(f"/api/projects/{project}/chat/sessions/{sid}/messages", json={"text": "Setup message"})

        fork_resp = http_client.post(f"/api/projects/{project}/chat/sessions/{sid}/fork", json={"name": "alt"})
        assert fork_resp.status_code == 200
        assert set(fork_resp.get_json()["branches"]) == {"main", "alt"}

        http_client.post(f"/api/projects/{project}/chat/sessions/{sid}/messages", json={"text": "Fork-only message"})
        session_data = http_client.get(f"/api/projects/{project}/chat/sessions/{sid}").get_json()
        assert len(session_data["branches"]["alt"]["messages"]) == 4  # setup(2) + fork-only(2)
        assert len(session_data["branches"]["main"]["messages"]) == 2  # untouched
        # the served branch dict must expose the fork point so the UI can
        # badge each message with its true origin branch
        alt = session_data["branches"]["alt"]
        assert alt["parent_branch"] == "main"
        assert alt["forked_at_index"] == 2  # the split happened after setup(2)
        assert session_data["branches"]["main"]["forked_at_index"] is None

    def test_switch_branch(self, http_client):
        project = self._setup_analyzed_project(http_client)
        sid = http_client.post(f"/api/projects/{project}/chat/start").get_json()["session_id"]
        http_client.post(f"/api/projects/{project}/chat/sessions/{sid}/fork", json={"name": "alt"})

        resp = http_client.post(f"/api/projects/{project}/chat/sessions/{sid}/switch", json={"name": "main"})
        assert resp.status_code == 200
        assert resp.get_json()["current_branch"] == "main"

    def test_switch_to_nonexistent_branch_fails_cleanly(self, http_client):
        project = self._setup_analyzed_project(http_client)
        sid = http_client.post(f"/api/projects/{project}/chat/start").get_json()["session_id"]
        resp = http_client.post(f"/api/projects/{project}/chat/sessions/{sid}/switch", json={"name": "ghost"})
        assert resp.status_code == 400

    def test_update_persona_and_mode(self, http_client):
        project = self._setup_analyzed_project(http_client)
        sid = http_client.post(f"/api/projects/{project}/chat/start").get_json()["session_id"]
        resp = http_client.post(
            f"/api/projects/{project}/chat/sessions/{sid}/settings",
            json={"persona": "producer", "mode": "brainstorm"},
        )
        assert resp.status_code == 200
        assert resp.get_json() == {"active_persona": "producer", "active_mode": "brainstorm"}

    def test_invalid_persona_rejected(self, http_client):
        project = self._setup_analyzed_project(http_client)
        sid = http_client.post(f"/api/projects/{project}/chat/start").get_json()["session_id"]
        resp = http_client.post(
            f"/api/projects/{project}/chat/sessions/{sid}/settings", json={"persona": "not_real"}
        )
        assert resp.status_code == 400

    def test_chat_works_without_analysis(self, http_client):
        """Script-only mode — chat should still work if the user never ran analyze."""
        upload_resp = _upload(http_client)
        project = upload_resp.get_json()["project"]
        resp = http_client.post(f"/api/projects/{project}/chat/start")
        assert resp.status_code == 200

    def test_new_session_defaults_to_writing_partner(self, http_client):
        project = self._setup_analyzed_project(http_client)
        sid = http_client.post(f"/api/projects/{project}/chat/start").get_json()["session_id"]
        data = http_client.get(f"/api/projects/{project}/chat/sessions/{sid}").get_json()
        branch = next(iter(data["branches"].values()))
        assert branch["active_persona"] == "writing_partner"
        assert branch["active_mode"] == "peer"

    def test_settings_reset_to_partner(self, http_client):
        project = self._setup_analyzed_project(http_client)
        sid = http_client.post(f"/api/projects/{project}/chat/start").get_json()["session_id"]
        base = f"/api/projects/{project}/chat/sessions/{sid}/settings"
        http_client.post(base, json={"persona": "producer"})
        resp = http_client.post(base, json={"persona": "writing_partner", "mode": "peer"})
        assert resp.status_code == 200
        assert resp.get_json() == {"active_persona": "writing_partner", "active_mode": "peer"}

    def test_report_and_fixqueue_available_after_analysis(self, http_client):
        project = self._setup_analyzed_project(http_client)  # helper already analyzes
        assert http_client.get(f"/api/projects/{project}/report").status_code == 200
        fq = http_client.get(f"/api/projects/{project}/fixqueue").get_json()
        assert "items" in fq
        assert "acts" in fq


    def _reset_writer_memory(self):
        import os
        from screenplay_studio import webapp_server
        p = os.path.join(webapp_server.PROJECTS_DIR, "writer_profile.json")
        if os.path.exists(p):
            os.remove(p)

    def test_get_writer_memory(self, http_client):
        self._reset_writer_memory()
        resp = http_client.get("/api/writer-memory")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "profile" in data and "card" in data
        assert data["profile"]["meta"]["total_turns_observed"] == 0

    def test_suppress_observation_via_api(self, http_client):
        self._reset_writer_memory()
        project = self._setup_analyzed_project(http_client)
        sid = http_client.post(f"/api/projects/{project}/chat/start").get_json()["session_id"]
        for _ in range(3):
            http_client.post(f"/api/projects/{project}/chat/sessions/{sid}/messages",
                             json={"text": "just tell me straight, what's wrong with scene 1"})
        data = http_client.get("/api/writer-memory").get_json()
        obs = next(o for o in data["profile"]["observations"] if not o["suppressed"])
        resp = http_client.post(f"/api/writer-memory/observations/{obs['id']}/suppress")
        assert resp.status_code == 200
        data2 = http_client.get("/api/writer-memory").get_json()
        assert next(o for o in data2["profile"]["observations"] if o["id"] == obs["id"])["suppressed"] is True
        # the suppression-aware gate is exposed for the panel's chips — the
        # only learned belief was forgotten, so nothing steers Sam any more
        assert data2["gated"] == {}
        assert data2["card"] is None

    def test_suppress_unknown_observation_404(self, http_client):
        self._reset_writer_memory()
        resp = http_client.post("/api/writer-memory/observations/obs_nope/suppress")
        assert resp.status_code == 404

    def test_refresh_endpoint_merges_mock_proposal(self, http_client):
        self._reset_writer_memory()
        project = self._setup_analyzed_project(http_client)
        sid = http_client.post(f"/api/projects/{project}/chat/start").get_json()["session_id"]
        http_client.post(f"/api/projects/{project}/chat/sessions/{sid}/messages", json={"text": "hello"})
        resp = http_client.post("/api/writer-memory/refresh",
                                json={"project": project, "session_id": sid})
        assert resp.status_code == 200
        profile = resp.get_json()["profile"]
        assert profile["dimensions"]["detail_level"]["value"] == "deep"


class TestTimeoutConfig:
    """Proves the configurable timeout (added in response to a real slow-
    local-model bug report) actually reaches the manifest and persists,
    not just that the /api/config endpoint accepts the value."""

    def test_set_timeout_via_config(self, http_client):
        resp = http_client.post("/api/config", json={"timeout": 900})
        assert resp.status_code == 200
        assert resp.get_json()["timeout"] == 900

    def test_invalid_timeout_ignored_not_crashed(self, http_client):
        resp = http_client.post("/api/config", json={"timeout": "not_a_number"})
        assert resp.status_code == 200  # doesn't crash, just ignores the bad value

    def test_timeout_flows_into_new_project_manifest(self, http_client, tmp_path):
        http_client.post("/api/config", json={"timeout": 900})
        resp = _upload(http_client)
        project = resp.get_json()["project"]

        from screenplay_studio.manifest import ProjectManifest
        import screenplay_studio.webapp_server as webapp_server
        m = ProjectManifest.load(webapp_server._project_dir(project))
        assert m.timeout == 900

    def test_timeout_flows_into_analyze(self, http_client):
        http_client.post("/api/config", json={"timeout": 900})
        resp = _upload(http_client)
        project = resp.get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")

        import screenplay_studio.webapp_server as webapp_server
        from screenplay_studio.manifest import ProjectManifest
        m = ProjectManifest.load(webapp_server._project_dir(project))
        assert m.timeout == 900


class TestConnectionTest:
    """The 'Test Connection' feature in settings — added specifically so a
    user finds out a server is unreachable BEFORE trying to chat, not after,
    which is exactly the confusing failure mode from the real bug report."""

    def test_successful_connection(self, http_client, mock_server):
        resp = http_client.post("/api/test-connection", json={"server_url": mock_server})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "model loaded" in data["message"]

    def test_unreachable_server(self, http_client):
        resp = http_client.post("/api/test-connection", json={"server_url": "http://localhost:9999"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is False
        assert "message" in data

    def test_uses_configured_url_when_none_given(self, http_client, mock_server):
        http_client.post("/api/config", json={"server_url": mock_server})
        resp = http_client.post("/api/test-connection", json={})
        assert resp.get_json()["ok"] is True
