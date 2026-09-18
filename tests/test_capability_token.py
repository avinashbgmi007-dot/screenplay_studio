"""H1 — capability token on the loopback server (regression tests).

The Origin guard rejects foreign-`Origin` pages, but a no-`Origin` blind write
(curl / form POST / no-cors fetch) sails through. Fix: when the server issues a
capability token (set as a SameSite=Strict cookie on `/`), mutating requests must
echo it back in the X-Studio-Token header. A foreign page can't read the cookie
and can't set the header without triggering CORS, so blind writes are blocked.
When no token is configured (bare test-client fixtures), behavior is unchanged.
"""
from __future__ import annotations


def _make_client(monkeypatch, tmp_path):
    import screenplay_studio.webapp_server as ws
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(tmp_path))
    ws.app.config["TESTING"] = True
    return ws, ws.app.test_client()


def test_mutations_rejected_without_token_when_one_is_set(monkeypatch, tmp_path):
    ws, client = _make_client(monkeypatch, tmp_path)
    monkeypatch.setattr(ws, "_API_TOKEN", "secret-token-123")
    # a mutating request with no token header -> 403
    r = client.post("/api/projects/The_Late_Hour/analyze")
    assert r.status_code == 403


def test_mutations_allowed_with_token(monkeypatch, tmp_path):
    ws, client = _make_client(monkeypatch, tmp_path)
    monkeypatch.setattr(ws, "_API_TOKEN", "secret-token-123")
    # with the token echoed, the guard passes (the route itself may 404/400 on a
    # missing project, but it must NOT be a 403 from the token gate)
    r = client.post("/api/projects/The_Late_Hour/analyze",
                    headers={"X-Studio-Token": "secret-token-123"})
    assert r.status_code != 403


def test_get_requests_pass_without_token(monkeypatch, tmp_path):
    ws, client = _make_client(monkeypatch, tmp_path)
    monkeypatch.setattr(ws, "_API_TOKEN", "secret-token-123")
    assert client.get("/api/config").status_code == 200


def test_no_token_configured_means_guard_off(monkeypatch, tmp_path):
    ws, client = _make_client(monkeypatch, tmp_path)
    monkeypatch.setattr(ws, "_API_TOKEN", None)
    r = client.post("/api/projects/The_Late_Hour/analyze")
    assert r.status_code != 403  # not blocked by the token gate


def test_index_sets_token_cookie_when_configured(monkeypatch, tmp_path):
    ws, client = _make_client(monkeypatch, tmp_path)
    monkeypatch.setattr(ws, "_API_TOKEN", "secret-token-123")
    r = client.get("/")
    cookie = r.headers.get("Set-Cookie", "")
    assert "studio_token=secret-token-123" in cookie
    assert "SameSite=Strict" in cookie
