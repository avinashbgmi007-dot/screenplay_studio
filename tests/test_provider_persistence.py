"""Gap 131: a custom provider that survives a restart — and a token kept private.

The request was concrete: base URL, model, API key, connect check, connected
status, save the config. Everything but the last two already worked; those two
were the gap, and both were measured before the fix:

* **Save did not save.** `POST /api/config` wrote process memory. A writer
  configured `https://api.example.com/v1` + `gpt-4o-mini` + a token, was told
  "connected", restarted the studio — and got `http://127.0.0.1:8099`, no model,
  no token. Proven here across two separate OS processes, because an in-process
  reload would not show which layer carried the setting.
* **Connected status did not persist.** The check result lived in the browser
  tab, so it described the moment the page loaded. Nothing could answer "was
  this provider answering ten minutes ago", and a second tab started blank.

Three properties matter as much as the feature, and each is a test below:

1. the token file is **owner-only** (0600), because a secret is now on disk;
2. a settings file can **never** grant remote permission — the launch flag still
   owns that decision, or the guard would be writable by the thing it guards;
3. a remembered "connected" is reported **with its timestamp**, and never reused
   for a different endpoint.
"""

import json
import os
import stat
import subprocess
import sys

import pytest

import screenplay_studio.webapp_server as webapp_server

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = "sk-synthetic-provider-token"
URL = "https://provider.example.com/v1"


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(tmp_path / "projects"))
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    monkeypatch.setattr(webapp_server, "_ALLOW_REMOTE_SERVER", True)
    saved = webapp_server.CONFIG.to_dict()
    saved_origin = webapp_server.CONFIG.get("api_key_origin")
    webapp_server.CONFIG["server_url"] = "http://127.0.0.1:8080"
    webapp_server.CONFIG["api_key"] = None
    webapp_server.CONFIG["model"] = None
    webapp_server._LAST_CHECK.update({"checked_at": None, "ok": None, "detail": None,
                                      "destination": None, "model": None})
    yield
    for k, v in saved.items():
        webapp_server.CONFIG[k] = v
    webapp_server.CONFIG._data["api_key_origin"] = saved_origin


@pytest.fixture
def client():
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _configure(client, **over):
    body = {"connection_mode": "remote", "server_url": URL,
            "model": "model-x", "api_key": TOKEN}
    body.update(over)
    return client.post("/api/config", json=body)


# ---------------------------------------------------------------------------
# Save actually saves
# ---------------------------------------------------------------------------

class TestTheProviderIsWrittenToDisk:
    def test_a_successful_save_reports_that_it_is_durable(self, client):
        body = _configure(client).get_json()
        assert body["provider"]["saved_to_disk"] is True, (
            "the writer is told 'saved' by the UI; it has to be true")

    def test_the_file_carries_url_model_and_token(self, client):
        _configure(client)
        path = webapp_server._provider_store_path()
        data = json.load(open(path, encoding="utf-8"))
        assert data["server_url"] == URL
        assert data["model"] == "model-x"
        assert data["api_key"] == TOKEN

    def test_loading_restores_all_three(self, client):
        _configure(client)
        # simulate a restart: wipe the live config, then load from disk
        webapp_server.CONFIG["server_url"] = "http://127.0.0.1:8080"
        webapp_server.CONFIG["api_key"] = None
        webapp_server.CONFIG["model"] = None
        assert webapp_server.load_provider() is True
        assert webapp_server.CONFIG["server_url"] == URL
        assert webapp_server.CONFIG["model"] == "model-x"
        assert webapp_server.CONFIG["api_key"] == TOKEN

    def test_the_token_approval_survives_the_round_trip(self, client):
        """Gap 57's origin record must travel with the token, or a restart
        forgets which provider the secret was entered for."""
        _configure(client)
        assert webapp_server.CONFIG.get("api_key_origin") == "https://provider.example.com"
        webapp_server.CONFIG["server_url"] = "http://127.0.0.1:8080"
        webapp_server.CONFIG["api_key"] = None
        webapp_server.load_provider()
        assert webapp_server.CONFIG.get("api_key_origin") == "https://provider.example.com"

    def test_it_survives_a_real_second_process(self, tmp_path):
        """The proof that matters: a fresh interpreter, same directory."""
        projects = tmp_path / "restart"
        projects.mkdir()
        save = (
            "import sys; sys.path.insert(0, %r)\n"
            "import screenplay_studio.webapp_server as w\n"
            "w.PROJECTS_DIR = %r\n"
            "w._ALLOW_REMOTE_SERVER = True\n"
            "w.app.config['TESTING'] = True\n"
            "w.app.test_client().post('/api/config', json={'connection_mode':'remote',"
            "'server_url':%r,'model':'model-x','api_key':%r})\n"
        ) % (REPO, str(projects), URL, TOKEN)
        load = (
            "import sys; sys.path.insert(0, %r)\n"
            "import screenplay_studio.webapp_server as w\n"
            "w.PROJECTS_DIR = %r\n"
            "w._ALLOW_REMOTE_SERVER = True\n"
            "w.load_provider()\n"
            "print(w.CONFIG['server_url'], w.CONFIG['model'], bool(w.CONFIG.get('api_key')))\n"
        ) % (REPO, str(projects))
        env = {**os.environ, "SCREENPLAY_STUDIO_DEMO_MODEL": "0"}
        subprocess.run([sys.executable, "-c", save], check=True, env=env,
                       capture_output=True, text=True)
        out = subprocess.run([sys.executable, "-c", load], check=True, env=env,
                             capture_output=True, text=True).stdout.strip().splitlines()
        assert out[-1] == f"{URL} model-x True", (
            "the provider did not survive a fresh process: " + str(out))

    def test_a_cleared_token_stays_cleared(self, client):
        _configure(client)
        client.post("/api/config", json={"api_key": ""})
        webapp_server.CONFIG["api_key"] = "leftover"
        webapp_server.load_provider()
        assert webapp_server.CONFIG.get("api_key") is None, (
            "a cleared token came back after a restart")


# ---------------------------------------------------------------------------
# The secret is on disk now, so the file has to be private
# ---------------------------------------------------------------------------

class TestTheTokenFileIsPrivate:
    def test_the_file_is_owner_only(self, client):
        _configure(client)
        mode = stat.S_IMODE(os.stat(webapp_server._provider_store_path()).st_mode)
        assert mode & 0o077 == 0, (
            f"the token file is readable by other users: mode {oct(mode)}")
        assert mode & stat.S_IRUSR, "the owner must still be able to read it"

    def test_the_token_never_leaves_over_the_api(self, client):
        _configure(client)
        for route in ("/api/config", "/api/health"):
            raw = client.get(route).get_data(as_text=True)
            assert TOKEN not in raw, f"{route} leaked the provider token"
            assert "api_key\"" not in raw, f"{route} exposed the raw field"

    def test_the_check_file_carries_no_secret(self, client, monkeypatch):
        _configure(client)
        import screenplay_analyzer.llm_client as mod

        class _Fake:
            def __init__(self, **kw):
                pass

            def list_models(self):
                return [{"id": "model-x"}]

        monkeypatch.setattr(mod, "LlamaServerClient", _Fake)
        client.post("/api/test-connection", json={"server_url": URL})
        path = webapp_server._last_check_path()
        assert os.path.isfile(path)
        assert TOKEN not in open(path, encoding="utf-8").read()


# ---------------------------------------------------------------------------
# A settings file must never grant permission
# ---------------------------------------------------------------------------

class TestASavedFileCannotGrantRemote:
    def test_a_remembered_remote_url_is_refused_without_the_launch_optin(self, monkeypatch):
        monkeypatch.setattr(webapp_server, "_ALLOW_REMOTE_SERVER", False)
        path = webapp_server._provider_store_path()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"server_url": URL, "api_key": TOKEN}, fh)
        webapp_server.load_provider()
        assert webapp_server.CONFIG["server_url"] != URL, (
            "a file on disk granted the permission the launch flag exists to hold")

    def test_the_refusal_does_not_crash_and_keeps_local_working(self, monkeypatch):
        monkeypatch.setattr(webapp_server, "_ALLOW_REMOTE_SERVER", False)
        with open(webapp_server._provider_store_path(), "w", encoding="utf-8") as fh:
            json.dump({"server_url": URL, "model": "m"}, fh)
        webapp_server.load_provider()          # must not raise
        assert webapp_server.connection_mode() == "local"

    def test_a_corrupt_file_is_ignored_rather_than_fatal(self):
        with open(webapp_server._provider_store_path(), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        assert webapp_server.load_provider() is False
        assert webapp_server.connection_mode() == "local"


# ---------------------------------------------------------------------------
# Connected status, remembered and timestamped
# ---------------------------------------------------------------------------

class TestTheCheckIsRemembered:
    def test_a_successful_probe_is_recorded_with_its_time_and_model(self, client, monkeypatch):
        import screenplay_analyzer.llm_client as mod

        class _Fake:
            def __init__(self, **kw):
                pass

            def list_models(self):
                return [{"id": "model-x"}]

        monkeypatch.setattr(mod, "LlamaServerClient", _Fake)
        _configure(client)
        r = client.post("/api/test-connection", json={"server_url": URL})
        assert r.get_json()["ok"] is True
        last = webapp_server.connection_report()["last_check"]
        assert last["ok"] is True
        assert last["model"] == "model-x"
        assert last["checked_at"] is not None
        assert last["stale"] is False

    def test_a_failed_probe_is_remembered_too(self, client):
        """The failure must be recorded against the endpoint that was probed.

        Note the question being asked: `connection_report` only reuses a record
        whose destination matches the CONFIGURED endpoint, so this test points
        the config at the probe target first. A failure for an endpoint nobody is
        using is correctly reported as stale, not as the current status.
        """
        dead = "http://127.0.0.1:1"
        webapp_server.CONFIG["server_url"] = dead
        r = client.post("/api/test-connection", json={"server_url": dead})
        assert r.get_json()["ok"] is False
        last = webapp_server.connection_report()["last_check"]
        assert last["ok"] is False
        assert last["detail"], "a failure with no reason is not actionable"

    def test_the_record_survives_a_restart(self, client, monkeypatch):
        # The configured endpoint must BE the one that was checked, or
        # `connection_report` correctly calls the record stale. My first version
        # of this test recorded a check for URL while the fixture still pointed at
        # loopback and asserted `ok is True` — the code was right, the test was
        # wrong, and it is exactly the property the next test pins.
        monkeypatch.setitem(webapp_server.CONFIG, "server_url", URL)
        webapp_server.record_last_check(True, "Connected", URL, "model-x")
        webapp_server._LAST_CHECK.update({"checked_at": None, "ok": None})
        webapp_server._load_last_check()
        assert webapp_server.connection_report()["last_check"]["ok"] is True

    def test_a_check_against_another_endpoint_reads_as_stale(self):
        """A remembered green must not describe a provider it never tested."""
        webapp_server.CONFIG["server_url"] = URL
        webapp_server.record_last_check(True, "Connected", URL, "model-x")
        assert webapp_server.connection_report()["last_check"]["ok"] is True
        webapp_server.CONFIG["server_url"] = "https://other.example.com/v1"
        last = webapp_server.connection_report()["last_check"]
        assert last["ok"] is None, "the old verdict was reused for a new endpoint"
        assert last["stale"] is True

    def test_config_and_health_agree(self, client):
        _configure(client)
        cfg = client.get("/api/config").get_json()["provider"]
        health = client.get("/api/health").get_json()["provider"]
        assert cfg == health, "two surfaces, two answers about the same provider"


# ---------------------------------------------------------------------------
# Local and remote both work — the point of a custom provider
# ---------------------------------------------------------------------------

class TestLocalAndRemoteBothWork:
    def test_the_local_desk_needs_no_provider_at_all(self, client):
        body = client.post("/api/config", json={"connection_mode": "local"}).get_json()
        assert body["provider"]["mode"] == "local"
        assert body["provider"]["api_key_set"] is False

    def test_switching_between_them_round_trips(self, client):
        _configure(client)
        assert client.get("/api/config").get_json()["provider"]["mode"] == "remote"
        client.post("/api/config", json={"connection_mode": "local"})
        assert client.get("/api/config").get_json()["provider"]["mode"] == "local"
        _configure(client)
        assert client.get("/api/config").get_json()["provider"]["mode"] == "remote"

    def test_the_configured_model_is_reported_back(self, client):
        _configure(client, model="model-y")
        assert client.get("/api/config").get_json()["provider"]["model"] == "model-y"
