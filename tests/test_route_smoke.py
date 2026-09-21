"""T2c -- the routes the rest of the suite never touched.

`tests/test_route_coverage.py` measured which routes the pytest suite actually
exercises (via a `before_request` recorder, not a source grep) and found seven
with zero pytest coverage. This file drives six of them at their real contracts;
the seventh is declared in that file's registry.

The split is deliberate. The **validation contracts** of the streaming and
translate routes -- empty text, unknown project, unknown session -- are cheap,
model-free and worth guarding, so they are asserted here. Their **happy paths**
need a live model and are covered by the browser suites
(`e2e_browser_smoke.py` waits on a real `POST .../messages/stream`;
`e2e_browser_selection_translate.py` clicks the translate button). Exercising the
rule here means the route is wired and its guards work -- it is not a claim that
the generation path is covered by pytest.
"""

import io
import os

import pytest

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "pain_tenglish.fountain")


@pytest.fixture
def client(tmp_path, mock_server):
    import screenplay_studio.webapp_server as webapp_server
    webapp_server.PROJECTS_DIR = str(tmp_path / "route_smoke_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _upload(client) -> str:
    with open(FIXTURE, "rb") as fh:
        data = fh.read()
    resp = client.post(
        "/api/projects",
        data={"file": (io.BytesIO(data), "pain.fountain"), "title": "Pain"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201, resp.data[:300]
    return resp.get_json()["project"]


# ---- GET /api/health ------------------------------------------------------
# Nothing in the SPA or the test tree called this. It is a documented operator
# liveness probe (docs/API_ROUTE_MAP.md), so it is exactly the kind of route that
# can rot unwatched.

class TestHealthRoute:
    def test_reports_ok_and_reflects_the_live_config(self, client, mock_server):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "ok"
        # the probe reports the CONFIGURED server, not a hardcoded default
        assert body["server_url"] == mock_server
        assert "demo_model" in body


# ---- GET /api/projects/<name>/metrics ------------------------------------
# The SPA's status strip reads this (app.js -> #status-metrics), but no pytest
# test drove it. The browser suites only touch the DOM node, not the endpoint.

class TestMetricsRoute:
    def test_unknown_project_is_404(self, client):
        resp = client.get("/api/projects/nope/metrics")
        assert resp.status_code == 404

    def test_summarizes_a_real_project(self, client):
        project = _upload(client)
        resp = client.get(f"/api/projects/{project}/metrics")
        assert resp.status_code == 200
        body = resp.get_json()
        assert isinstance(body, dict)
        # the compact view the status strip renders
        assert {"analysis_seconds", "discussed", "findings_total"} <= set(body)


# ---- POST /api/projects/<name>/findings/intent ---------------------------

class TestFindingIntentRoute:
    def test_missing_finding_id_is_400(self, client):
        project = _upload(client)
        resp = client.post(f"/api/projects/{project}/findings/intent", json={})
        assert resp.status_code == 400

    def test_intent_round_trips_and_clears(self, client):
        project = _upload(client)
        base = f"/api/projects/{project}/findings/intent"

        resp = client.post(base, json={"finding_id": "hash123", "intent": "deferred"})
        assert resp.status_code == 200
        assert resp.get_json()["intent"] == "deferred"

        # a null intent clears the mark (set_finding_intent pops anything not in
        # the two known intents)
        resp = client.post(base, json={"finding_id": "hash123", "intent": None})
        assert resp.status_code == 200
        assert resp.get_json()["intent"] is None


# ---- the two SSE streaming routes ----------------------------------------

class TestStreamingRoutesValidation:
    def test_project_stream_requires_text(self, client):
        project = _upload(client)
        resp = client.post(
            f"/api/projects/{project}/chat/sessions/s1/messages/stream", json={})
        assert resp.status_code == 400
        assert "text" in resp.get_json()["error"].lower()

    def test_project_stream_unknown_session_is_404(self, client):
        project = _upload(client)
        resp = client.post(
            f"/api/projects/{project}/chat/sessions/does-not-exist/messages/stream",
            json={"text": "hello"})
        assert resp.status_code == 404

    def test_idea_stream_requires_text(self, client):
        resp = client.post(
            "/api/ideas/nope/chat/sessions/s1/messages/stream", json={})
        assert resp.status_code == 400
        assert "text" in resp.get_json()["error"].lower()

    def test_idea_stream_unknown_session_is_404(self, client):
        resp = client.post(
            "/api/ideas/nope/chat/sessions/does-not-exist/messages/stream",
            json={"text": "hello"})
        assert resp.status_code == 404


# ---- POST /api/projects/<name>/chat/sessions/<sid>/translate --------------

class TestTranslateRouteValidation:
    def test_unknown_project_is_404(self, client):
        resp = client.post(
            "/api/projects/nope/chat/sessions/s1/translate", json={"index": 0})
        assert resp.status_code == 404

    def test_unknown_session_is_404(self, client):
        project = _upload(client)
        resp = client.post(
            f"/api/projects/{project}/chat/sessions/does-not-exist/translate",
            json={"index": 0})
        assert resp.status_code == 404
