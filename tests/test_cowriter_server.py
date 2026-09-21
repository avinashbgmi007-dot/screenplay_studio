"""screenplay_cowriter/server.py — the piece's standalone HTTP surface.

Found by a route-reach sweep (audit item T2b, "is the HTTP reach thin?"): this
module serves 7 routes and **nothing in the repo imports it** — no test, no other
module. It is nonetheless a documented entry point (`python -m
screenplay_cowriter.server`, and AGENTS.md's "each piece runs its own local
server" architecture), so a break in it would ship silently. It was the one
claim in that audit section that held up.

The routes read a module-level `store` global that `main()` assigns, so the
fixture assigns it directly rather than booting a server thread. The two routes
that need a model (`POST /sessions`, `POST /sessions/<id>/messages`) are driven
against the repo's shared mock llama-server, so no real model is required.
"""
import os

import pytest

from screenplay_cowriter import server as cow_server
from screenplay_cowriter.store import SessionStore


@pytest.fixture
def client(tmp_path):
    cow_server.store = SessionStore(str(tmp_path / "sessions"))
    cow_server.app.config["TESTING"] = True
    return cow_server.app.test_client()


@pytest.fixture
def session_id(client, mock_server):
    """A real session, created THROUGH the route so the whole path is exercised."""
    r = client.post("/sessions", json={"title": "Route Test", "server_url": mock_server})
    assert r.status_code == 201, r.data[:300]
    return r.get_json()["session_id"]


# ---- 1. health -------------------------------------------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


# ---- 2/3. list + create ----------------------------------------------------

def test_sessions_start_empty(client):
    assert client.get("/sessions").get_json() == []


def test_create_resolves_the_model_from_the_server(client, session_id):
    listed = client.get("/sessions").get_json()
    assert [s["session_id"] for s in listed] == [session_id]

    body = client.get(f"/sessions/{session_id}").get_json()
    assert body["session_id"] == session_id
    # resolved from the mock's /v1/models, not inherited from anywhere
    assert body["model_id"] == "mock-e2e-model.gguf"
    assert body["messages"] == []
    assert body["current_branch"] == "main"


def test_create_reports_a_dead_model_server_as_502(client):
    """A session that cannot reach a model must not be reported as created."""
    r = client.post("/sessions", json={"title": "x", "server_url": "http://127.0.0.1:1"})
    assert r.status_code == 502, r.data[:200]
    assert "error" in r.get_json()


# ---- 4. get ----------------------------------------------------------------

def test_get_unknown_session_is_404(client):
    r = client.get("/sessions/nope")
    assert r.status_code == 404
    assert r.get_json()["error"] == "not found"


# ---- 5. messages -----------------------------------------------------------

def test_send_message_round_trips_through_the_mock(client, session_id):
    r = client.post(f"/sessions/{session_id}/messages",
                    json={"text": "What do you make of the revolver?"})
    assert r.status_code == 200, r.data[:300]
    body = r.get_json()
    assert body["reply"]
    assert body["branch"] == "main"
    # persisted, not merely echoed back
    after = client.get(f"/sessions/{session_id}").get_json()
    assert len(after["messages"]) >= 2


def test_send_message_requires_text(client, session_id):
    r = client.post(f"/sessions/{session_id}/messages", json={"text": "   "})
    assert r.status_code == 400
    assert r.get_json()["error"] == "text is required"


def test_send_message_unknown_session_is_404(client):
    r = client.post("/sessions/nope/messages", json={"text": "hi"})
    assert r.status_code == 404


# ---- 6. fork ---------------------------------------------------------------

def test_fork_creates_a_named_branch(client, session_id):
    r = client.post(f"/sessions/{session_id}/fork", json={"name": "alt"})
    assert r.status_code == 200, r.data[:200]
    assert "alt" in r.get_json()["branches"]


def test_fork_requires_a_name(client, session_id):
    r = client.post(f"/sessions/{session_id}/fork", json={})
    assert r.status_code == 400
    assert r.get_json()["error"] == "name is required"


def test_fork_of_an_existing_branch_is_400_not_a_500(client, session_id):
    """Session.fork raises ValueError; the route must translate it, not leak it."""
    client.post(f"/sessions/{session_id}/fork", json={"name": "alt"})
    r = client.post(f"/sessions/{session_id}/fork", json={"name": "alt"})
    assert r.status_code == 400, r.data[:200]
    assert "already exists" in r.get_json()["error"]


def test_fork_unknown_session_is_404(client):
    assert client.post("/sessions/nope/fork", json={"name": "alt"}).status_code == 404


# ---- 7. switch -------------------------------------------------------------

def test_switch_moves_the_current_branch(client, session_id):
    client.post(f"/sessions/{session_id}/fork", json={"name": "alt"})
    r = client.post(f"/sessions/{session_id}/switch", json={"name": "alt"})
    assert r.status_code == 200, r.data[:200]
    assert r.get_json()["current_branch"] == "alt"


def test_switch_to_an_unknown_branch_is_400(client, session_id):
    r = client.post(f"/sessions/{session_id}/switch", json={"name": "no-such-branch"})
    assert r.status_code == 400
    assert "No such branch" in r.get_json()["error"]


def test_switch_unknown_session_is_404(client):
    assert client.post("/sessions/nope/switch", json={"name": "main"}).status_code == 404


# ---- 8. settings -----------------------------------------------------------

def test_settings_persists_the_persona(client, session_id):
    r = client.post(f"/sessions/{session_id}/settings", json={"persona": "premise_doctor"})
    assert r.status_code == 200, r.data[:200]
    # the summary does not echo the persona, so assert the STORE actually moved
    assert cow_server.store.load(session_id).branch.active_persona == "premise_doctor"


def test_settings_persists_the_mode(client, session_id):
    r = client.post(f"/sessions/{session_id}/settings", json={"mode": "brainstorm"})
    assert r.status_code == 200, r.data[:200]
    assert cow_server.store.load(session_id).branch.active_mode == "brainstorm"


def test_settings_rejects_an_unknown_persona(client, session_id):
    r = client.post(f"/sessions/{session_id}/settings", json={"persona": "nope"})
    assert r.status_code == 400
    assert "unknown persona" in r.get_json()["error"]


def test_settings_rejects_an_unknown_mode(client, session_id):
    r = client.post(f"/sessions/{session_id}/settings", json={"mode": "nope"})
    assert r.status_code == 400
    assert "unknown mode" in r.get_json()["error"]


def test_settings_unknown_session_is_404(client):
    assert client.post("/sessions/nope/settings", json={}).status_code == 404
