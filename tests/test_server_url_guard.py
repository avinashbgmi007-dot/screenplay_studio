"""BE-H1 — the model-server URL is a trust boundary, not a free-text field.

`POST /api/config {"server_url": ...}` used to accept ANY URL and then write it
into every project manifest, so one request permanently redirected every
analysis and chat turn — the writer's full script included — to a host of the
attacker's choosing. `/api/test-connection` was a second unvalidated outbound
primitive: it GETs `{url}/v1/models` for any URL it is handed.

The product's one promise is that nothing leaves this machine, so the boundary
is loopback-only at every point the URL can enter (config setter, HTTP route,
manifest propagation) and every point it is used (the connection probe and the
two client factories).

Two deliberate design points, pinned below:

1. The opt-in is process-level (`--allow-remote-server` / env var), NOT
   reachable over HTTP. If an HTTP request could set it, the guard would be
   decorative: the same request that names the remote host could authorise it.
2. State poisoned *before* this guard existed still cannot exfiltrate. The
   manifest and session files on disk are writable by the app, so a
   project already pointing at a remote host must fail loudly at the client
   factory rather than quietly POSTing the script there.

Every "remote" host used here is non-routable by standard — TEST-NET-1
(RFC 5737) and the reserved `.example` TLD (RFC 2606). A regression therefore
fails on an assertion instead of reaching a real server.
"""

import json
import os
import sys

import pytest

import screenplay_studio.webapp_server as webapp_server
from screenplay_studio.net_guard import is_loopback_host, is_loopback_url

# Non-routable: TEST-NET-1 is reserved for documentation and never forwarded.
REMOTE_IP = "http://192.0.2.1:1"
# Reserved TLD — guaranteed never to resolve.
REMOTE_NAME = "http://inference.example:1"
# The two classic prefix-check bypasses: userinfo (the authority ends at the
# `@`) and a suffix that makes a remote host look like localhost.
USERINFO_BYPASS = "http://127.0.0.1@192.0.2.1:1"
SUFFIX_BYPASS = "http://localhost.inference.example:1"


@pytest.fixture(autouse=True)
def _isolate_module_globals():
    """Restore the process-wide settings this module deliberately mutates.

    `main()` assigns the opt-in global on purpose (it is a startup path), and
    the config/project globals are shared. Without this, the opt-in granted by
    one test silently authorises the next test's attack — which is exactly how
    the first draft of the env-var test passed without testing anything.
    """
    saved = (webapp_server._ALLOW_REMOTE_SERVER, webapp_server.PROJECTS_DIR,
             webapp_server._DEMO_MODEL_ACTIVE, webapp_server._DEMO_URL,
             webapp_server.CONFIG.to_dict())
    yield
    (webapp_server._ALLOW_REMOTE_SERVER, webapp_server.PROJECTS_DIR,
     webapp_server._DEMO_MODEL_ACTIVE, webapp_server._DEMO_URL,
     config) = saved
    for key, value in config.items():
        webapp_server.CONFIG[key] = value


@pytest.fixture
def http_client(tmp_path, mock_server):
    """A client on a loopback project dir, with all module globals reset.

    The guard's opt-in and the demo flags are process-wide, so a neighbouring
    test file could leave them set. Reset both here so these assertions measure
    this file's behaviour and nothing else.
    """
    webapp_server.PROJECTS_DIR = str(tmp_path / "urlguard_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server._ALLOW_REMOTE_SERVER = False
    webapp_server._DEMO_MODEL_ACTIVE = False
    webapp_server._DEMO_URL = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


# ---------------------------------------------------------------------------
# The predicate itself
# ---------------------------------------------------------------------------

class TestLoopbackPredicate:
    @pytest.mark.parametrize("url", [
        "http://localhost:8080",
        "http://LOCALHOST:8080",       # hostnames are case-insensitive
        "https://localhost",
        "http://127.0.0.1:8080",
        "http://127.0.0.2:8080",       # all of 127/8 is loopback (RFC 1122)
        "http://127.255.255.254:8080",
        "http://[::1]:8080",
        "http://[0:0:0:0:0:0:0:1]:8080",
    ])
    def test_loopback_forms_are_local(self, url):
        assert is_loopback_url(url), f"{url} is on this machine"

    @pytest.mark.parametrize("url", [
        REMOTE_IP,
        REMOTE_NAME,
        USERINFO_BYPASS,
        SUFFIX_BYPASS,
        "http://0.0.0.0:8080",          # "all interfaces", not loopback
        "http://127.0.0.1.evil.example:8080",   # the prefix trap, spelled out
        "file:///etc/passwd",           # not an http(s) URL at all
        "ftp://127.0.0.1/x",
        "not a url",
        "",
    ])
    def test_remote_or_malformed_forms_are_not_local(self, url):
        assert not is_loopback_url(url), f"{url} must not count as local"

    def test_missing_host_is_not_local(self):
        assert not is_loopback_host(None)
        assert not is_loopback_host("")
        assert not is_loopback_url("http://")


# ---------------------------------------------------------------------------
# Entry point 1 — POST /api/config
# ---------------------------------------------------------------------------

class TestConfigRouteRefusesRemote:
    def test_a_remote_url_is_refused(self, http_client):
        r = http_client.post("/api/config", json={"server_url": REMOTE_IP})
        assert r.status_code == 400, r.get_data(as_text=True)

    def test_a_refused_url_does_not_change_the_config(self, http_client):
        before = webapp_server.CONFIG["server_url"]
        http_client.post("/api/config", json={"server_url": REMOTE_IP})
        assert webapp_server.CONFIG["server_url"] == before, \
            "a rejected value must not land in the live config"

    @pytest.mark.parametrize("url", [REMOTE_IP, REMOTE_NAME, USERINFO_BYPASS, SUFFIX_BYPASS])
    def test_every_bypass_form_is_refused(self, http_client, url):
        r = http_client.post("/api/config", json={"server_url": url})
        assert r.status_code == 400, f"{url} was accepted"

    def test_the_refusal_is_actionable(self, http_client):
        """The writer must be told how to opt in, not just 'no'."""
        msg = http_client.post("/api/config", json={"server_url": REMOTE_NAME}).get_json()["error"]
        assert "local" in msg.lower()
        assert "--allow-remote-server" in msg, "the error must name the opt-in"

    @pytest.mark.parametrize("url", [
        "http://localhost:9999",
        "http://127.0.0.1:9999",
        "http://127.0.0.2:9999",
        "http://[::1]:9999",
    ])
    def test_loopback_urls_are_still_accepted(self, http_client, url):
        r = http_client.post("/api/config", json={"server_url": url})
        assert r.status_code == 200, r.get_data(as_text=True)
        assert webapp_server.CONFIG["server_url"] == url.rstrip("/")

    def test_a_refusal_leaves_the_desk_working(self, http_client, mock_server):
        """Rejecting the attack must not break the connection the writer had."""
        http_client.post("/api/config", json={"server_url": REMOTE_IP})
        assert webapp_server.CONFIG["server_url"] == mock_server
        r = http_client.post("/api/test-connection", json={})
        assert r.status_code == 200 and r.get_json()["ok"] is True


# ---------------------------------------------------------------------------
# Entry point 2 — manifest propagation
# ---------------------------------------------------------------------------

class TestNoPropagationToManifests:
    def test_a_remote_url_never_reaches_a_project_manifest(self, http_client):
        name = http_client.post("/api/sample").get_json()["project"]
        manifest_path = os.path.join(webapp_server.PROJECTS_DIR, name, "project.json")
        with open(manifest_path, encoding="utf-8") as fh:
            assert json.load(fh)["server_url"] == webapp_server.CONFIG["server_url"]

        http_client.post("/api/config", json={"server_url": REMOTE_IP})

        with open(manifest_path, encoding="utf-8") as fh:
            after = json.load(fh)["server_url"]
        assert after != REMOTE_IP, \
            "the settings save rewrote every manifest to the attacker's host"
        assert after == webapp_server.CONFIG["server_url"]

    def test_the_sync_helper_is_itself_a_choke_point(self, http_client):
        """Defense in depth: the propagator refuses a remote URL on its own."""
        http_client.post("/api/sample")
        with pytest.raises(ValueError):
            webapp_server._sync_server_url_to_projects(REMOTE_IP)


# ---------------------------------------------------------------------------
# Entry point 3 — the outbound probe
# ---------------------------------------------------------------------------

class TestConnectionProbe:
    @pytest.mark.parametrize("url", [REMOTE_IP, REMOTE_NAME, USERINFO_BYPASS, SUFFIX_BYPASS])
    def test_a_remote_probe_is_refused(self, http_client, url):
        r = http_client.post("/api/test-connection", json={"server_url": url})
        assert r.status_code == 400, f"{url} was probed"
        assert "local" in r.get_json()["error"].lower()

    def test_the_probe_still_works_on_a_loopback_server(self, http_client, mock_server):
        r = http_client.post("/api/test-connection", json={"server_url": mock_server})
        assert r.status_code == 200
        assert r.get_json()["ok"] is True, r.get_data(as_text=True)


# ---------------------------------------------------------------------------
# The opt-in — process-level only
# ---------------------------------------------------------------------------

class TestOptIn:
    def test_the_opt_in_defaults_to_off(self):
        assert webapp_server._ALLOW_REMOTE_SERVER is False

    def test_an_explicit_opt_in_permits_a_remote_server(self, http_client, monkeypatch):
        monkeypatch.setattr(webapp_server, "_ALLOW_REMOTE_SERVER", True)
        r = http_client.post("/api/config", json={"server_url": REMOTE_IP})
        assert r.status_code == 200, r.get_data(as_text=True)
        assert webapp_server.CONFIG["server_url"] == REMOTE_IP

    def test_the_http_api_cannot_grant_itself_the_opt_in(self, http_client):
        """The guard must not be authorisable by the same request it guards."""
        r = http_client.post("/api/config", json={
            "server_url": REMOTE_IP, "allow_remote_server": True})
        assert r.status_code == 400
        assert webapp_server._ALLOW_REMOTE_SERVER is False

    def test_the_cli_flag_permits_a_remote_server(self, tmp_path, monkeypatch):
        assert webapp_server._ALLOW_REMOTE_SERVER is False, "precondition: opt-in off"
        monkeypatch.setattr(webapp_server, "_API_TOKEN", None)
        monkeypatch.setattr(webapp_server, "_DEMO_MODEL_ACTIVE", False)
        monkeypatch.setattr(webapp_server.app, "run", lambda **kw: None)
        monkeypatch.setattr(sys, "argv", [
            "webapp_server", "--port", "8599", "--projects-dir", str(tmp_path),
            "--server", REMOTE_IP, "--allow-remote-server"])
        webapp_server.main()
        assert webapp_server.CONFIG["server_url"] == REMOTE_IP

    def test_the_env_var_permits_a_remote_server(self, tmp_path, monkeypatch):
        assert webapp_server._ALLOW_REMOTE_SERVER is False, "precondition: opt-in off"
        monkeypatch.setattr(webapp_server, "_API_TOKEN", None)
        monkeypatch.setattr(webapp_server, "_DEMO_MODEL_ACTIVE", False)
        monkeypatch.setattr(webapp_server.app, "run", lambda **kw: None)
        monkeypatch.setenv("SCREENPLAY_STUDIO_ALLOW_REMOTE_SERVER", "1")
        monkeypatch.setattr(sys, "argv", [
            "webapp_server", "--port", "8599", "--projects-dir", str(tmp_path),
            "--server", REMOTE_IP])
        webapp_server.main()
        assert webapp_server.CONFIG["server_url"] == REMOTE_IP

    def test_the_cli_without_the_flag_fails_loudly(self, tmp_path, monkeypatch):
        """Fail loudly with an actionable message — never silently downgrade."""
        assert webapp_server._ALLOW_REMOTE_SERVER is False, "precondition: opt-in off"
        monkeypatch.setattr(webapp_server, "_API_TOKEN", None)
        monkeypatch.setattr(webapp_server, "_DEMO_MODEL_ACTIVE", False)
        monkeypatch.setattr(webapp_server.app, "run", lambda **kw: None)
        monkeypatch.delenv("SCREENPLAY_STUDIO_ALLOW_REMOTE_SERVER", raising=False)
        monkeypatch.setattr(sys, "argv", [
            "webapp_server", "--port", "8599", "--projects-dir", str(tmp_path),
            "--server", REMOTE_IP])
        with pytest.raises(SystemExit) as exc:
            webapp_server.main()
        assert exc.value.code != 0


# ---------------------------------------------------------------------------
# Egress — state poisoned before this guard existed
# ---------------------------------------------------------------------------

class TestEgressGuard:
    """A project or session already pointing at a remote host (written before
    this fix landed) must fail loudly, not quietly POST the script there."""

    def _poisoned_manifest(self, http_client):
        name = http_client.post("/api/sample").get_json()["project"]
        from screenplay_studio.manifest import ProjectManifest
        path = os.path.join(webapp_server.PROJECTS_DIR, name)
        m = ProjectManifest.load(path)
        m.server_url = REMOTE_IP          # written straight to disk, bypassing config
        m.save()
        return ProjectManifest.load(path)

    def test_a_poisoned_manifest_cannot_build_a_client(self, http_client):
        m = self._poisoned_manifest(http_client)
        assert m.server_url == REMOTE_IP, "fixture must actually poison the manifest"
        with pytest.raises(ValueError):
            webapp_server._make_client(m)

    def test_a_poisoned_session_url_is_refused_at_the_chat_boundary(self, http_client):
        class PoisonedSession:
            server_url = REMOTE_IP
            model_id = None
        with pytest.raises(ValueError):
            webapp_server._engine_base_url(PoisonedSession())

    def test_a_loopback_session_still_resolves(self, http_client, mock_server):
        class LocalSession:
            server_url = mock_server
            model_id = None
        assert webapp_server._engine_base_url(LocalSession()) == mock_server

    def test_the_egress_refusal_is_actionable(self, http_client):
        m = self._poisoned_manifest(http_client)
        with pytest.raises(ValueError) as exc:
            webapp_server._make_client(m)
        assert "--allow-remote-server" in str(exc.value)
