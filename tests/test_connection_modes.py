"""One desk, two places a model can live — local llama-server, or a remote
OpenAI-compatible API reached with a URL, a token and a model name.

The desk shipped loopback-only, which is a *privacy* property worth keeping:
your script never leaves the machine. What it did not have was any way to talk
to a token-protected endpoint at all — no bearer header existed anywhere in the
codebase — so "use a hosted API" was not a supported setup, it was a setup that
half-worked and then 401'd in a way that looked like the model was broken.

Two things are pinned here, and they are deliberately in tension:

1. The **mode is not a permission**. `connection_mode: "remote"` over HTTP is
   refused while the process opt-in is off, because if a request could grant
   remote access then the request that names the remote host would authorise
   sending the script there, and the guard would be decorative. The opt-in stays
   a launch-time decision (`--allow-remote-server`).
2. Once the operator HAS opted in, the remote path must actually work — URL,
   token and model name in, a correct `Authorization: Bearer …` on the wire out.
   A guard that permits a connection nobody can authenticate is not a feature.

The transport proof is a real loopback HTTP server that records what it was
sent, not a mock of the client: a mocked `requests` would prove the call was
made and prove nothing about the header.
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import screenplay_studio.webapp_server as webapp_server
from screenplay_analyzer.llm_client_base import auth_headers

# Non-routable by standard: TEST-NET-1 (RFC 5737) is never forwarded, and the
# reserved `.example` TLD (RFC 2606) never resolves — so a regression fails on an
# assertion instead of reaching a real host.
REMOTE_URL = "http://192.0.2.1:1"
REMOTE_API = "http://inference.example:1/v1"
TOKEN = "sk-test-0123456789abcdef"


@pytest.fixture(autouse=True)
def _isolate_module_globals():
    """Restore the process-wide settings these tests deliberately mutate.

    `_ALLOW_REMOTE_SERVER` is a launch-time global and `CONFIG` is shared, so
    without this the opt-in granted by one test would silently authorise the
    next one's remote connection — and the "refused" assertions would pass
    without testing anything.
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
    """A client on a loopback project dir with every relevant global reset."""
    webapp_server.PROJECTS_DIR = str(tmp_path / "conn_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.CONFIG["fast_model"] = None
    webapp_server.CONFIG["api_key"] = None
    webapp_server._ALLOW_REMOTE_SERVER = False
    webapp_server._DEMO_MODEL_ACTIVE = False
    webapp_server._DEMO_URL = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


class _Recorder(BaseHTTPRequestHandler):
    """A minimal OpenAI-compatible endpoint that remembers its headers."""

    seen_headers = []
    seen_paths = []

    def do_GET(self):  # noqa: N802 — BaseHTTPRequestHandler's spelling
        type(self).seen_headers.append(dict(self.headers))
        type(self).seen_paths.append(self.path)
        body = json.dumps({"data": [{"id": "recorded-model"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence the per-request stderr line
        pass


@pytest.fixture
def recording_server():
    """A real loopback HTTP server. Yields (base_url, handler_class)."""
    _Recorder.seen_headers = []
    _Recorder.seen_paths = []
    httpd = HTTPServer(("127.0.0.1", 0), _Recorder)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", _Recorder
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# The header format itself
# ---------------------------------------------------------------------------

class TestAuthHeaders:
    """A local server authenticates nothing, and "no token" must mean NO header.

    `Authorization: Bearer ` (empty credential) is rejected outright by some
    gateways, so emitting it would turn "the writer cleared the token" into
    "every call 401s" on a server that never needed one.
    """

    @pytest.mark.parametrize("value", [None, "", "   ", "\t\n"])
    def test_no_token_means_no_header(self, value):
        assert auth_headers(value) == {}

    def test_a_token_becomes_a_bearer_header(self):
        assert auth_headers(TOKEN) == {"Authorization": f"Bearer {TOKEN}"}

    def test_surrounding_whitespace_is_trimmed(self):
        # A pasted token almost always carries a trailing newline from the
        # clipboard; sending that verbatim is a 401 nobody can see.
        assert auth_headers(f"  {TOKEN}\n") == {"Authorization": f"Bearer {TOKEN}"}


class TestConnectionMode:
    @pytest.mark.parametrize("url", [
        "http://localhost:8080", "http://127.0.0.1:8080", "http://[::1]:9",
    ])
    def test_loopback_is_local(self, url):
        assert webapp_server.connection_mode(url) == "local"

    @pytest.mark.parametrize("url", [REMOTE_URL, REMOTE_API,
                                     "https://api.openai.com/v1"])
    def test_anything_else_is_remote(self, url):
        assert webapp_server.connection_mode(url) == "remote"

    def test_the_default_desk_is_local(self, http_client):
        cfg = http_client.get("/api/config").get_json()
        assert cfg["connection_mode"] == "local"
        # the fixture points at the loopback mock server, so "local" is what
        # matters here — not the literal :8080 default.
        assert webapp_server.connection_mode(cfg["server_url"]) == "local"


# ---------------------------------------------------------------------------
# The token is a secret: it goes in, and it does not come back
# ---------------------------------------------------------------------------

class TestTokenNeverComesBack:
    def test_config_reports_only_whether_a_token_is_set(self, http_client):
        webapp_server.CONFIG["api_key"] = TOKEN
        r = http_client.get("/api/config")
        cfg = r.get_json()
        assert cfg["api_key_set"] is True
        assert "api_key" not in cfg, "the raw key must not be a response field"
        assert TOKEN not in r.get_data(as_text=True), (
            "the token must not appear anywhere in the response body")

    def test_an_unset_token_reads_as_unset(self, http_client):
        cfg = http_client.get("/api/config").get_json()
        assert cfg["api_key_set"] is False

    def test_saving_a_token_does_not_echo_it(self, http_client):
        webapp_server._ALLOW_REMOTE_SERVER = True
        r = http_client.post("/api/config", json={
            "connection_mode": "remote", "server_url": REMOTE_API, "api_key": TOKEN})
        assert r.status_code == 200, r.get_data(as_text=True)
        assert TOKEN not in r.get_data(as_text=True)
        assert r.get_json()["api_key_set"] is True

    def test_clearing_the_token_lands_as_none_not_an_empty_bearer(self, http_client):
        webapp_server.CONFIG["api_key"] = TOKEN
        r = http_client.post("/api/config", json={"api_key": ""})
        assert r.status_code == 200
        assert webapp_server.CONFIG.get("api_key") is None
        assert r.get_json()["api_key_set"] is False
        # and the clients then send no Authorization header at all
        assert webapp_server._auth_headers(webapp_server.CONFIG.get("api_key")) == {}


# ---------------------------------------------------------------------------
# The mode is NOT a permission — the opt-in stays a launch decision
# ---------------------------------------------------------------------------

class TestRemoteNeedsTheLaunchOptin:
    def test_asking_for_remote_over_http_is_refused(self, http_client):
        before = webapp_server.CONFIG["server_url"]
        r = http_client.post("/api/config", json={
            "connection_mode": "remote", "server_url": REMOTE_API})
        assert r.status_code == 400
        err = r.get_json()["error"]
        assert "--allow-remote-server" in err, "the refusal must name the opt-in"
        # and nothing was applied
        assert webapp_server.CONFIG["server_url"] == before

    def test_the_refusal_does_not_grant_what_it_refused(self, http_client):
        http_client.post("/api/config", json={
            "connection_mode": "remote", "server_url": REMOTE_API})
        assert webapp_server._ALLOW_REMOTE_SERVER is False, (
            "a refused request must not leave the opt-in set")
        assert webapp_server.connection_mode() == "local"

    def test_a_remote_url_is_still_refused_without_the_optin(self, http_client):
        # The original guard, unchanged — the mode work must not have opened it.
        r = http_client.post("/api/config", json={"server_url": REMOTE_URL})
        assert r.status_code == 400

    def test_remote_needs_a_base_url(self, http_client):
        webapp_server._ALLOW_REMOTE_SERVER = True
        r = http_client.post("/api/config", json={"connection_mode": "remote"})
        assert r.status_code == 400
        assert "base URL" in r.get_json()["error"]

    def test_an_unknown_mode_is_refused(self, http_client):
        r = http_client.post("/api/config", json={"connection_mode": "sideways"})
        assert r.status_code == 400
        assert "local" in r.get_json()["error"]

    def test_with_the_optin_the_same_request_succeeds(self, http_client):
        """The pairing that makes the refusals meaningful.

        Without this, "remote is refused" would also pass if the remote path
        were simply broken.
        """
        webapp_server._ALLOW_REMOTE_SERVER = True
        r = http_client.post("/api/config", json={
            "connection_mode": "remote", "server_url": REMOTE_API, "api_key": TOKEN})
        assert r.status_code == 200, r.get_data(as_text=True)
        cfg = r.get_json()
        assert cfg["connection_mode"] == "remote"
        assert cfg["allow_remote"] is True
        assert webapp_server.CONFIG["server_url"] == REMOTE_API
        assert webapp_server.CONFIG.get("api_key") == TOKEN


# ---------------------------------------------------------------------------
# Going back to local fills the local info in
# ---------------------------------------------------------------------------

class TestSwitchingBackToLocal:
    def test_local_resets_the_url_and_clears_the_token(self, http_client):
        webapp_server._ALLOW_REMOTE_SERVER = True
        http_client.post("/api/config", json={
            "connection_mode": "remote", "server_url": REMOTE_API, "api_key": TOKEN})
        r = http_client.post("/api/config", json={"connection_mode": "local"})
        assert r.status_code == 200, r.get_data(as_text=True)
        cfg = r.get_json()
        assert cfg["connection_mode"] == "local"
        assert cfg["server_url"] == "http://localhost:8080"
        assert cfg["api_key_set"] is False, (
            "a local llama-server needs no token, and leaving one set would send "
            "the remote API's credential to the localhost server")
        assert webapp_server.CONFIG.get("api_key") is None


# ---------------------------------------------------------------------------
# The token actually reaches the wire
# ---------------------------------------------------------------------------

class TestTokenReachesTheWire:
    def test_test_connection_sends_the_bearer_header(self, http_client, recording_server):
        base, recorder = recording_server
        r = http_client.post("/api/test-connection",
                             json={"server_url": base, "api_key": TOKEN})
        assert r.status_code == 200, r.get_data(as_text=True)
        assert r.get_json()["ok"] is True
        assert recorder.seen_headers, "the endpoint was never called"
        assert recorder.seen_headers[-1].get("Authorization") == f"Bearer {TOKEN}", (
            f"the probe reached the server without the token: {recorder.seen_headers[-1]}")

    def test_no_token_means_no_authorization_header(self, http_client, recording_server):
        base, recorder = recording_server
        r = http_client.post("/api/test-connection", json={"server_url": base})
        assert r.status_code == 200
        assert "Authorization" not in recorder.seen_headers[-1]

    def test_the_saved_token_is_used_when_none_is_typed(self, http_client, recording_server):
        """Test Connection must answer the question the form is asking.

        With a token already saved and none typed into the box, the probe has to
        use the saved one — otherwise "Test" reports 401 for a setup that works.
        """
        base, recorder = recording_server
        webapp_server.CONFIG["api_key"] = TOKEN
        r = http_client.post("/api/test-connection", json={"server_url": base})
        assert r.status_code == 200
        assert recorder.seen_headers[-1].get("Authorization") == f"Bearer {TOKEN}"

    def test_the_typed_token_wins_over_the_saved_one(self, http_client, recording_server):
        base, recorder = recording_server
        webapp_server.CONFIG["api_key"] = "sk-stale-saved-token"
        r = http_client.post("/api/test-connection",
                             json={"server_url": base, "api_key": TOKEN})
        assert r.status_code == 200
        assert recorder.seen_headers[-1].get("Authorization") == f"Bearer {TOKEN}", (
            "the form was testing the token the writer had already replaced")

    def test_the_analysis_client_is_built_with_the_token(self, http_client, tmp_path):
        """The analysis path, not just the probe.

        `_make_client` is what the analyzer actually runs on, and it reads the
        MANIFEST — so this also proves the token survives the manifest round
        trip, which is what makes a resumed project work.
        """
        from screenplay_studio.manifest import ProjectManifest
        webapp_server.CONFIG["api_key"] = TOKEN
        m = ProjectManifest(project_dir=str(tmp_path / "analysis"),
                            title="t", source_filename="s.fountain",
                            source_format=".fountain")
        webapp_server._adopt_connection(m)
        assert m.api_key == TOKEN
        client = webapp_server._make_client(m)
        assert client.extra_headers == {"Authorization": f"Bearer {TOKEN}"}


# ---------------------------------------------------------------------------
# Projects carry the connection, so resume/CLI can reach the same model
# ---------------------------------------------------------------------------

class TestProjectsCarryTheConnection:
    def _write_manifest(self, projects_dir, name, **kw):
        from screenplay_studio.manifest import ProjectManifest
        d = os.path.join(projects_dir, name)
        os.makedirs(d, exist_ok=True)
        m = ProjectManifest(project_dir=d, title=name, source_filename="s.fountain",
                            source_format=".fountain", **kw)
        m.save()
        return d

    def test_a_settings_change_propagates_the_token(self, http_client):
        d = self._write_manifest(webapp_server.PROJECTS_DIR, "Old_Project",
                                 server_url="http://localhost:8080", api_key=None)
        webapp_server._ALLOW_REMOTE_SERVER = True
        r = http_client.post("/api/config", json={
            "connection_mode": "remote", "server_url": REMOTE_API, "api_key": TOKEN})
        assert r.status_code == 200, r.get_data(as_text=True)
        from screenplay_studio.manifest import ProjectManifest
        m = ProjectManifest.load(d)
        assert m.server_url == REMOTE_API
        assert m.api_key == TOKEN, (
            "an existing project would otherwise keep 401ing after the writer "
            "switched to a token-protected endpoint")

    def test_clearing_the_token_propagates_too(self, http_client):
        d = self._write_manifest(webapp_server.PROJECTS_DIR, "Was_Remote",
                                 server_url="http://localhost:8080", api_key=TOKEN)
        r = http_client.post("/api/config", json={"api_key": ""})
        assert r.status_code == 200
        from screenplay_studio.manifest import ProjectManifest
        assert ProjectManifest.load(d).api_key is None

    def test_a_token_change_alone_still_syncs(self, http_client):
        """The sync used to hang off `server_url` being present.

        Saving ONLY a new token (same endpoint, rotated credential) would then
        leave every project holding the old one — the exact shape of a silent
        auth failure that looks like the endpoint went down.
        """
        d = self._write_manifest(webapp_server.PROJECTS_DIR, "Rotate_Me",
                                 server_url="http://localhost:8080", api_key="sk-old")
        r = http_client.post("/api/config", json={"api_key": TOKEN})
        assert r.status_code == 200
        from screenplay_studio.manifest import ProjectManifest
        assert ProjectManifest.load(d).api_key == TOKEN

    def test_the_manifest_round_trips_the_token(self, tmp_path):
        from screenplay_studio.manifest import ProjectManifest
        m = ProjectManifest(project_dir=str(tmp_path / "p"), title="t",
                            source_filename="s.fountain", source_format=".fountain",
                            api_key=TOKEN)
        m.save()
        assert ProjectManifest.load(str(tmp_path / "p")).api_key == TOKEN
        assert ProjectManifest.load(str(tmp_path / "p")).to_dict()["api_key"] == TOKEN

    def test_an_old_manifest_without_a_token_still_loads(self, tmp_path):
        """Every project on disk predates this field."""
        from screenplay_studio.manifest import ProjectManifest
        d = tmp_path / "legacy"
        d.mkdir()
        (d / "project.json").write_text(json.dumps({
            "project_dir": str(d), "title": "legacy", "source_filename": "s.fountain",
            "source_format": ".fountain", "server_url": "http://localhost:8080",
            "model_id": None, "timeout": 600,
        }), encoding="utf-8")
        m = ProjectManifest.load(str(d))
        assert m.api_key is None
