"""Settings validation is all-or-nothing; project sync is explicit and honest.

Two defects, one seam. `POST /api/config` mutated as it parsed, so a request
rejected at the eleventh field had already changed the first ten — and the one
that landed was usually `server_url`, i.e. where the writer's script goes next.
The writer was told the save failed and the desk had moved anyway. A later gap
showed the other boundary: a valid global save could partially fail across
project manifests and still return success. Writes are atomic per project, not
across the set, so that result must be reported and retryable.

The second half is the same seam seen from the other side. `connection_mode()`
describes the GLOBAL setting, but every project carries its own `server_url` and
`api_key` in its manifest, and a project's client is built from the MANIFEST
(`_make_client`). So `{"connection_mode": "local"}` reset the desk while every
existing project kept the remote destination — and the status panel, reading the
mode, reported "local" over turns that were still leaving the machine.

What is pinned here:

* a rejected save changes nothing at all, field by field, and the desk keeps
  working afterwards;
* a "go local" reaches the projects, including clearing their credential, so the
  effective destination for an existing project is loopback;
* when a project somehow still disagrees (an unwritable manifest, a hand edit),
  the API SAYS so — a mismatch is reported, never silently smoothed over.

The long-standing forgiving contracts are pinned here too, because a refactor is
where they get lost: a non-numeric `timeout` is still ignored rather than fatal,
and `connection_mode: "remote"` with no URL is still refused.
"""

import json
import os

import pytest

import screenplay_studio.webapp_server as webapp_server
from screenplay_studio.manifest import ProjectManifest

REMOTE_API = "https://provider-b.example.com/v1"
TOKEN = "sk-synthetic-provider-b"


@pytest.fixture(autouse=True)
def _isolate_config():
    saved = (webapp_server._ALLOW_REMOTE_SERVER, webapp_server.PROJECTS_DIR,
             webapp_server._DEMO_MODEL_ACTIVE, webapp_server._DEMO_URL,
             webapp_server.CONFIG.to_dict())
    yield
    (webapp_server._ALLOW_REMOTE_SERVER, webapp_server.PROJECTS_DIR,
     webapp_server._DEMO_MODEL_ACTIVE, webapp_server._DEMO_URL,
     config) = saved
    for key, value in config.items():
        webapp_server.CONFIG[key] = value
    webapp_server.CONFIG._data["api_key_origin"] = None


@pytest.fixture
def client(tmp_path):
    webapp_server.PROJECTS_DIR = str(tmp_path / "projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = "http://127.0.0.1:8080"
    webapp_server.CONFIG["api_key"] = None
    webapp_server.CONFIG["turn_timeout"] = 120
    webapp_server.CONFIG["timeout"] = 600
    webapp_server._ALLOW_REMOTE_SERVER = True
    webapp_server._DEMO_MODEL_ACTIVE = False
    webapp_server._DEMO_URL = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _project(client, name="p"):
    """A real project with a remote destination in its manifest."""
    made = client.post("/api/sample").get_json()["project"]
    m = ProjectManifest.load(webapp_server._project_dir(made))
    m.server_url = REMOTE_API
    m.api_key = TOKEN
    m.save()
    return made


def _snapshot():
    return {k: webapp_server.CONFIG.get(k)
            for k in ("server_url", "api_key", "model", "fast_model",
                      "turn_timeout", "timeout")}


# ---------------------------------------------------------------------------
# Half one — a rejected save applies nothing
# ---------------------------------------------------------------------------

class TestARejectedSaveChangesNothing:
    def test_a_bad_turn_timeout_does_not_move_the_endpoint(self, client):
        """The register's own reproduction: a valid new URL plus an invalid
        negative turn_timeout. The URL used to be applied before the 400."""
        before = _snapshot()
        r = client.post("/api/config", json={"server_url": "http://127.0.0.1:9999",
                                            "turn_timeout": -5})
        assert r.status_code == 400
        assert "turn_timeout" in r.get_json()["error"], "the message must name the field"
        assert _snapshot() == before, "a refused save changed the live config"

    @pytest.mark.parametrize("bad", [{"turn_timeout": 0}, {"turn_timeout": "soon"},
                                     {"turn_timeout": None}])
    def test_every_invalid_turn_timeout_is_refused_before_the_rest(self, client, bad):
        before = _snapshot()
        r = client.post("/api/config", json={"server_url": "http://127.0.0.1:9999", **bad})
        assert r.status_code == 400, r.get_data(as_text=True)
        assert _snapshot() == before

    def test_a_refused_save_leaves_every_other_field_alone_too(self, client):
        before = _snapshot()
        client.post("/api/config", json={"server_url": "http://127.0.0.1:9999",
                                         "model": "should-not-land",
                                         "timeout": 900,
                                         "turn_timeout": -1})
        assert _snapshot() == before

    def test_a_refused_save_does_not_rewrite_every_project(self, client):
        """`_sync_server_url_to_projects` is the sticky half: it touches every
        manifest on disk, so it must not run for a save that failed."""
        made = _project(client)
        r = client.post("/api/config", json={"server_url": "http://127.0.0.1:9999",
                                            "turn_timeout": -5})
        assert r.status_code == 400
        m = ProjectManifest.load(webapp_server._project_dir(made))
        assert m.server_url == REMOTE_API, "a failed save rewrote the project"

    def test_a_refused_save_leaves_the_desk_working(self, client, tmp_path):
        """Rejecting a client never calls. The desk must still open the project
        it had, and the manifest must still be loadable."""
        made = _project(client)
        client.post("/api/config", json={"turn_timeout": -1})
        assert client.get(f"/api/projects/{made}").status_code == 200
        m = ProjectManifest.load(webapp_server._project_dir(made))
        assert m.api_key == TOKEN

    def test_a_valid_save_still_applies_everything(self, client):
        """The pairing that makes the refusals meaningful: if every save were
        refused, "nothing changed" would pass without testing anything."""
        r = client.post("/api/config", json={"server_url": "http://127.0.0.1:9999",
                                            "turn_timeout": 300, "timeout": 900,
                                            "model": "m1"})
        assert r.status_code == 200, r.get_data(as_text=True)
        cfg = r.get_json()
        assert cfg["server_url"] == "http://127.0.0.1:9999"
        assert cfg["turn_timeout"] == 300
        assert cfg["timeout"] == 900
        assert cfg["model"] == "m1"

    def test_the_old_forgiving_timeout_contract_survives(self, client):
        """`timeout: "not_a_number"` was ignored, never fatal. A refactor is not
        a licence to turn a forgiving field into a 400."""
        r = client.post("/api/config", json={"timeout": "not_a_number"})
        assert r.status_code == 200, r.get_data(as_text=True)
        assert r.get_json()["timeout"] == 600

    def test_remote_mode_still_needs_a_url(self, client):
        r = client.post("/api/config", json={"connection_mode": "remote"})
        assert r.status_code == 400
        assert "base URL" in r.get_json()["error"]


# ---------------------------------------------------------------------------
# Half two — "Local" reaches the projects, credential included
# ---------------------------------------------------------------------------

class TestGoingLocalReachesTheProjects:
    def test_the_project_manifest_follows_the_switch(self, client):
        made = _project(client)
        r = client.post("/api/config", json={"connection_mode": "local"})
        assert r.status_code == 200, r.get_data(as_text=True)
        m = ProjectManifest.load(webapp_server._project_dir(made))
        assert m.server_url == "http://localhost:8080"
        assert m.api_key is None, (
            "the project kept the remote token after the desk went local")

    def test_the_effective_destination_for_a_project_is_loopback(self, client):
        """The property that matters: ask the client factory, not the config."""
        made = _project(client)
        client.post("/api/config", json={"connection_mode": "local"})
        m = ProjectManifest.load(webapp_server._project_dir(made))
        client_obj = webapp_server._make_client(m)
        assert webapp_server.connection_mode(client_obj.base_url) == "local"
        assert client_obj.extra_headers == {}, (
            "a local client must carry no credential")

    def test_the_api_reports_no_remote_projects_afterwards(self, client):
        _project(client)
        body = client.post("/api/config", json={"connection_mode": "local"}).get_json()
        assert body["destinations"]["mode"] == "local"
        assert body["destinations"]["remote_projects"] == []

    def test_going_remote_carries_the_url_and_token_to_the_projects(self, client):
        made = client.post("/api/sample").get_json()["project"]
        r = client.post("/api/config", json={"connection_mode": "remote",
                                            "server_url": REMOTE_API, "api_key": TOKEN})
        assert r.status_code == 200, r.get_data(as_text=True)
        m = ProjectManifest.load(webapp_server._project_dir(made))
        assert m.server_url == REMOTE_API
        assert m.api_key == TOKEN

    def test_clearing_the_token_alone_reaches_the_projects(self, client):
        """A clear is a settings change like any other; leaving the remote token
        in the manifests keeps it on the wire."""
        made = _project(client)
        r = client.post("/api/config", json={"api_key": ""})
        assert r.status_code == 200, r.get_data(as_text=True)
        assert ProjectManifest.load(webapp_server._project_dir(made)).api_key is None


# ---------------------------------------------------------------------------
# A disagreement that survives is REPORTED, never smoothed over
# ---------------------------------------------------------------------------

class TestAMismatchIsReported:
    def test_a_remote_project_is_named_in_the_config_response(self, client):
        made = _project(client)
        cfg = client.get("/api/config").get_json()
        d = cfg["destinations"]
        assert d["mode"] == "local", "precondition: the desk believes it is local"
        assert [r["project"] for r in d["remote_projects"]] == [made], (
            "the desk says local while a project still sends turns off-machine")
        assert d["remote_projects"][0]["has_credential"] is True

    def test_health_reports_it_too(self, client):
        _project(client)
        body = client.get("/api/health").get_json()
        assert body["destinations"]["remote_projects"], (
            "an operator scripting /api/health cannot see the mismatch")

    def test_it_is_reported_after_a_failed_sync_not_invented(self, client, monkeypatch):
        """A directory that cannot be written must produce a REPORT, not a crash
        and not a reassuring blank."""
        made = _project(client)
        monkeypatch.setattr(webapp_server, "_sync_server_url_to_projects",
                            lambda *a, **k: None)   # the sync silently does nothing
        body = client.post("/api/config", json={"connection_mode": "local"}).get_json()
        assert [r["project"] for r in body["destinations"]["remote_projects"]] == [made]

    def test_partial_manifest_write_is_explicit_and_saving_again_reconciles(
        self, client, monkeypatch
    ):
        made = _project(client)
        project_dir = os.path.realpath(webapp_server._project_dir(made))
        original_save = ProjectManifest.save

        def fail_this_project(self):
            if os.path.realpath(self.project_dir) == project_dir:
                raise OSError("synthetic disk-full failure")
            return original_save(self)

        monkeypatch.setattr(ProjectManifest, "save", fail_this_project)
        response = client.post("/api/config", json={"connection_mode": "local"})
        assert response.status_code == 409
        body = response.get_json()
        assert body["settings_saved"] is True
        assert made in body["error"]
        assert REMOTE_API in body["error"]
        assert "Save these settings again" in body["error"]
        assert webapp_server.CONFIG["server_url"] == "http://localhost:8080"
        assert body["project_sync"]["ok"] is False
        assert body["project_sync"]["failed"] == [{
            "project": made,
            "effective_server_url": REMOTE_API,
            "error": "Could not update this project's settings.",
        }]
        assert [r["project"] for r in body["destinations"]["remote_projects"]] == [made]
        unchanged = ProjectManifest.load(webapp_server._project_dir(made))
        assert unchanged.server_url == REMOTE_API
        assert unchanged.api_key == TOKEN

        # Retrying the same explicit settings save is the reconciliation path;
        # the old destination is not silently adopted or forgotten.
        monkeypatch.setattr(ProjectManifest, "save", original_save)
        retry = client.post("/api/config", json={"connection_mode": "local"})
        assert retry.status_code == 200
        assert retry.get_json()["project_sync"]["ok"] is True
        updated = ProjectManifest.load(webapp_server._project_dir(made))
        assert updated.server_url == "http://localhost:8080"
        assert updated.api_key is None

    def test_a_local_project_on_the_same_url_is_a_full_agreement(self, client):
        """A new project inherits the global URL, so it agrees on both counts.

        (My first version of this test asserted `projects_elsewhere >= 1` here,
        which was a wrong premise of mine, not a defect: identical URLs are not
        "elsewhere".)
        """
        client.post("/api/sample")
        d = client.get("/api/config").get_json()["destinations"]
        assert d["remote_projects"] == []
        assert d["projects_elsewhere"] == 0
        assert d["project_count"] == 1, "the count is how 'none at all' is distinguishable"

    def test_a_local_project_on_another_port_is_elsewhere_but_not_remote(self, client):
        """Loopback on a different URL is still local. The two counts are not
        the same question, which is why both are reported."""
        made = client.post("/api/sample").get_json()["project"]
        m = ProjectManifest.load(webapp_server._project_dir(made))
        m.server_url = "http://127.0.0.1:8123"
        m.save()
        d = client.get("/api/config").get_json()["destinations"]
        assert d["projects_elsewhere"] == 1
        assert d["remote_projects"] == [], "a loopback project is not remote"
        assert d["mismatched_projects"] == [{
            "project": made,
            "server_url": "http://127.0.0.1:8123",
            "mode": "local",
            "has_credential": False,
        }]

    def test_the_projects_list_never_carries_the_token(self, client):
        _project(client)
        for route in ("/api/config", "/api/health"):
            raw = client.get(route).get_data(as_text=True)
            assert TOKEN not in raw, f"{route} leaked a project credential"
