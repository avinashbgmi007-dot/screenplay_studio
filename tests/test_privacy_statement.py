"""Gap 118: consent scope must be machine-readable, and must describe reality.

`/api/config` used to answer `allow_remote` and `connection_mode` as bare
booleans, with the privacy consequence explained only in the settings UI's
prose. A scripted client could enable remote use and learn nothing about what
leaves the machine.

The other half of this file matters as much: the statement must not promise more
than the code does. Since gap 57 a token is bound to the origin it was entered
for, so `credentials_scope` says `"origin"` — but ONLY when an origin is actually
recorded. A token inherited from `--api-key` / `SCREENPLAY_STUDIO_API_KEY` or
from a config written before that bookkeeping existed is refused off-machine
rather than origin-bound, and the statement reports `"unrecorded"` for it.
"""

import pytest

import screenplay_studio.webapp_server as webapp_server


@pytest.fixture
def client(tmp_path, monkeypatch):
    webapp_server.PROJECTS_DIR = str(tmp_path / "projects")
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


@pytest.fixture
def config(monkeypatch):
    """Set the connection the way the app holds it, restored afterwards."""
    def _set(url, api_key=None, allow_remote=False):
        monkeypatch.setattr(webapp_server, "_ALLOW_REMOTE_SERVER", allow_remote)
        monkeypatch.setitem(webapp_server.CONFIG, "server_url", url)
        monkeypatch.setitem(webapp_server.CONFIG, "api_key", api_key)
    return _set


class TestTheStatementIsMachineReadable:
    def test_a_local_configuration_says_nothing_leaves(self, client, config):
        config("http://127.0.0.1:8080")
        p = client.get("/api/config").get_json()["privacy"]
        assert p["sends_script_off_machine"] is False
        assert p["destination"] is None
        assert p["credentials_in_use"] is False

    def test_a_remote_configuration_names_the_origin(self, client, config):
        config("https://api.example.com/v1", "sk-synthetic", allow_remote=True)
        p = client.get("/api/config").get_json()["privacy"]
        assert p["sends_script_off_machine"] is True
        assert p["destination"] == "https://api.example.com", (
            "the destination is the origin, not the provider's API path")
        assert p["credentials_in_use"] is True
        assert p["remote_permitted"] is True

    def test_the_origin_keeps_a_non_default_port(self, client, config):
        config("https://api.example.com:8443/v1", allow_remote=True)
        p = client.get("/api/config").get_json()["privacy"]
        assert p["destination"] == "https://api.example.com:8443"

    def test_a_loopback_server_needs_no_credential_even_if_one_is_set(self, client, config):
        """`_auth_headers` short-circuits for local, so 'in use' must be false —
        otherwise the statement overstates what is sent."""
        config("http://127.0.0.1:8080", "sk-synthetic")
        p = client.get("/api/config").get_json()["privacy"]
        assert p["credentials_in_use"] is False
        assert p["sends_script_off_machine"] is False


class TestItDoesNotOverstate:
    def test_it_claims_origin_scope_only_when_an_origin_is_recorded(self, client, config):
        """Gap 57 is FIXED: a saved token is only used at the origin it was
        entered for, so `origin` is now a promise the code keeps. A token with
        no recorded origin (CLI flag, env var, an older config) is NOT
        origin-bound — it is refused off-machine — and the statement must not
        round that up to `origin` either.
        """
        config("https://api.example.com/v1", None, allow_remote=True)
        webapp_server.CONFIG["api_key"] = "sk-synthetic"   # no recorded origin
        p = client.get("/api/config").get_json()["privacy"]
        assert p["credentials_scope"] == "unrecorded"

        webapp_server._approve_credential_for("https://api.example.com/v1")
        p = client.get("/api/config").get_json()["privacy"]
        assert p["credentials_scope"] == "origin"

    def test_no_key_means_no_scope_claim(self, client, config):
        config("https://api.example.com/v1", None, allow_remote=True)
        p = client.get("/api/config").get_json()["privacy"]
        assert p["credentials_scope"] is None
        assert p["credentials_in_use"] is False

    def test_an_unparseable_url_is_reported_as_remote_with_no_destination(self, client, config):
        """Honest rather than convenient: it is NOT loopback, so it is treated
        as off-machine, and the destination is unknown rather than invented."""
        config("not a url", allow_remote=True)
        p = client.get("/api/config").get_json()["privacy"]
        assert p["sends_script_off_machine"] is True
        assert p["destination"] is None


class TestTheSecretStillNeverLeaves:
    def test_neither_surface_carries_the_token(self, client, config):
        secret = "sk-this-must-never-appear"
        config("https://api.example.com/v1", secret, allow_remote=True)
        for route in ("/api/config", "/api/health"):
            body = str(client.get(route).get_json())
            assert secret not in body, f"{route} leaked the api key"


class TestEverySurfaceAgrees:
    def test_health_carries_the_same_statement(self, client, config):
        config("https://api.example.com/v1", "sk-synthetic", allow_remote=True)
        cfg = client.get("/api/config").get_json()["privacy"]
        health = client.get("/api/health").get_json()["privacy"]
        assert cfg == health, (
            "a health-only client and a config client disagree about what "
            "leaves the machine")

    def test_the_post_response_carries_it_too(self, client, config):
        """POST /api/config answers with the same shape as GET (gap 56). A
        client that has just changed the setting must not have to re-read."""
        # the process opt-in must be on, or the guard correctly refuses the switch
        # — that refusal is its own contract, pinned in test_connection_modes.
        config("http://127.0.0.1:8080", allow_remote=True)
        posted = client.post("/api/config", json={"connection_mode": "remote",
                                                  "server_url": "https://api.example.com/v1"})
        assert posted.status_code == 200, posted.get_json()
        p = posted.get_json().get("privacy")
        assert p is not None, "the write response lost the consent statement"
        assert p["sends_script_off_machine"] is True
