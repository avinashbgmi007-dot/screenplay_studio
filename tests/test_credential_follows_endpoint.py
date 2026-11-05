"""Gap 57: a saved API token follows a changed endpoint to a different provider.

The studio holds ONE token, `CONFIG["api_key"]`, and before this the value had
no memory of where it came from. Two ordinary UI flows therefore sent provider
A's secret to provider B, with no trust decision by the writer:

1. **Test Connection.** The token box is blank whenever the writer is not
   retyping the token — the settings page says so, and `app.js` omits the field
   rather than sending `""`. `/api/test-connection` treated an omitted field as
   "use the saved one" and built a client against whatever `server_url` was in
   the form. Type provider B's URL, press Test, and the probe went out to B
   carrying A's `Authorization: Bearer …`.
2. **Save.** `POST /api/config {"server_url": B}` with no `api_key` kept the
   token, moved the URL, and from then on every analysis and chat turn went to
   B with A's credential — and `GET /api/config` still reported `api_key_set`.

The fix records the origin the token was entered for and refuses to send it
anywhere else. Three properties are pinned here, and the second and third matter
as much as the first:

* the token does NOT travel to a different provider;
* the refusal happens BEFORE any outbound call (asserted by counting requests at
  a real loopback server, not by trusting the code path);
* nothing that used to work breaks — a loopback desk with no token, a same-origin
  port change, saving a token together with its URL, and deliberately migrating
  by typing the new token all still succeed. A guard that also refuses those is
  not a fix, it is an outage.

Every remote host below is non-routable by standard (TEST-NET-1, RFC 5737; the
reserved `.example` TLD, RFC 2606), so a regression fails on an assertion
instead of reaching a real provider.
"""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import screenplay_studio.webapp_server as webapp_server

PROVIDER_A = "http://provider-a.example:1/v1"
PROVIDER_B = "http://provider-b.example:1/v1"
TOKEN_A = "sk-token-entered-for-provider-a"
TOKEN_B = "sk-token-entered-for-provider-b"


# ---------------------------------------------------------------------------
# A loopback endpoint that records every request it receives
# ---------------------------------------------------------------------------

class _Recorder(BaseHTTPRequestHandler):
    seen: list = []

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler's spelling
        _Recorder.seen.append(dict(self.headers))
        body = b'{"data": [{"id": "mock-model"}]}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep the test output clean
        pass


@pytest.fixture
def recording_server():
    _Recorder.seen = []
    srv = HTTPServer(("127.0.0.1", 0), _Recorder)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{srv.server_port}", _Recorder
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _isolate_config():
    """CONFIG is process-wide and `_ALLOW_REMOTE_SERVER` is a launch global.

    The token's approved origin lives in the config holder itself, so restoring
    `api_key` restores the approval with it — that is exactly the coupling this
    file is about, and it makes the isolation here honest rather than hopeful.
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
    webapp_server.CONFIG._data["api_key_origin"] = None


@pytest.fixture
def client(tmp_path):
    webapp_server.PROJECTS_DIR = str(tmp_path / "projects")
    webapp_server.app.config["TESTING"] = True
    webapp_server._ALLOW_REMOTE_SERVER = True   # the operator opted in at launch
    webapp_server._DEMO_MODEL_ACTIVE = False
    webapp_server._DEMO_URL = None
    return webapp_server.app.test_client()


def _saved_at(origin_url, token):
    """Put the app in the state a writer reaches by saving this provider."""
    webapp_server.CONFIG["server_url"] = origin_url
    webapp_server.CONFIG["api_key"] = token
    webapp_server.CONFIG._data["api_key_origin"] = webapp_server._origin_of(origin_url)


# ---------------------------------------------------------------------------
# Flow 1 — Test Connection with the token box left blank
# ---------------------------------------------------------------------------

class TestTheProbeDoesNotCarryTheTokenToAnotherProvider:
    def test_a_blank_token_box_does_not_send_the_saved_token_elsewhere(self, client, recording_server):
        """The exact reported flow: a token saved for A, B's URL in the form,
        an empty token box, press Test."""
        base, recorder = recording_server
        _saved_at(PROVIDER_A, TOKEN_A)
        r = client.post("/api/test-connection", json={"server_url": base})
        assert r.status_code == 200
        assert r.get_json()["ok"] is False, (
            "the probe reported success against an endpoint it must not have called")
        assert not recorder.seen, (
            "the token for provider A was sent to a different endpoint: "
            f"{recorder.seen}")

    def test_the_refusal_names_the_provider_the_token_was_entered_for(self, client, recording_server):
        base, _ = recording_server
        _saved_at(PROVIDER_A, TOKEN_A)
        msg = client.post("/api/test-connection", json={"server_url": base}).get_json()["message"]
        assert webapp_server._origin_of(PROVIDER_A) in msg, (
            f"the writer cannot tell which endpoint the token belongs to: {msg}")
        assert webapp_server._origin_of(base) in msg
        assert TOKEN_A not in msg, "the refusal must not leak the secret it is protecting"

    def test_the_same_origin_still_gets_the_saved_token(self, client, recording_server):
        """A blank box at the endpoint the token was entered for must work, or
        'Test' reports 401 for a setup that is fine."""
        base, recorder = recording_server
        _saved_at(base, TOKEN_A)
        r = client.post("/api/test-connection", json={"server_url": base})
        assert r.status_code == 200
        assert r.get_json()["ok"] is True, r.get_data(as_text=True)
        assert recorder.seen[-1].get("Authorization") == f"Bearer {TOKEN_A}"

    def test_typing_the_new_provider_token_still_reaches_it(self, client, recording_server):
        """Deliberate migration stays one explicit action."""
        base, recorder = recording_server
        _saved_at(PROVIDER_A, TOKEN_A)
        r = client.post("/api/test-connection", json={"server_url": base, "api_key": TOKEN_B})
        assert r.status_code == 200
        assert r.get_json()["ok"] is True, r.get_data(as_text=True)
        assert recorder.seen[-1].get("Authorization") == f"Bearer {TOKEN_B}"

    def test_a_different_port_on_the_same_host_is_a_different_origin(self, client, recording_server):
        """Origin, not host: a token approved for :8080 is not approved for
        :9999, because that port can be a different program entirely."""
        base, recorder = recording_server
        _saved_at("http://127.0.0.1:1/v1", TOKEN_A)
        r = client.post("/api/test-connection", json={"server_url": base})
        assert r.get_json()["ok"] is False
        assert not recorder.seen

    def test_with_no_saved_token_the_probe_simply_runs(self, client, recording_server):
        """Nothing to protect, so nothing to refuse — the pre-existing behaviour
        of testing a fresh install must survive the guard."""
        base, recorder = recording_server
        webapp_server.CONFIG["server_url"] = base
        webapp_server.CONFIG["api_key"] = None
        r = client.post("/api/test-connection", json={"server_url": base})
        assert r.status_code == 200
        assert r.get_json()["ok"] is True, r.get_data(as_text=True)
        assert "Authorization" not in recorder.seen[-1], (
            "a token that is not set must not appear on the wire")


# ---------------------------------------------------------------------------
# Flow 2 — Save with a new URL and a blank token box
# ---------------------------------------------------------------------------

class TestTheSaveDoesNotMoveTheToken:
    def test_saving_a_new_endpoint_with_a_blank_box_is_refused(self, client):
        _saved_at(PROVIDER_A, TOKEN_A)
        r = client.post("/api/config", json={"server_url": PROVIDER_B})
        assert r.status_code == 400, r.get_data(as_text=True)
        assert webapp_server.CONFIG["server_url"] == PROVIDER_A, (
            "a refused save still moved the desk to the new provider")
        assert webapp_server.CONFIG["api_key"] == TOKEN_A

    def test_the_refusal_says_what_to_do(self, client):
        _saved_at(PROVIDER_A, TOKEN_A)
        msg = client.post("/api/config", json={"server_url": PROVIDER_B}).get_json()["error"]
        assert "Enter the token for this provider" in msg
        assert TOKEN_A not in msg

    def test_saving_the_token_with_its_url_is_allowed(self, client):
        _saved_at(PROVIDER_A, TOKEN_A)
        r = client.post("/api/config", json={"server_url": PROVIDER_B, "api_key": TOKEN_B})
        assert r.status_code == 200, r.get_data(as_text=True)
        assert webapp_server.CONFIG["server_url"] == PROVIDER_B
        assert webapp_server.CONFIG["api_key"] == TOKEN_B
        assert webapp_server.CONFIG.get("api_key_origin") == webapp_server._origin_of(PROVIDER_B)

    def test_clearing_the_token_and_moving_is_allowed(self, client):
        """`api_key: ""` is how the UI clears the field, and it approves nothing,
        so the move is safe."""
        _saved_at(PROVIDER_A, TOKEN_A)
        r = client.post("/api/config", json={"server_url": PROVIDER_B, "api_key": ""})
        assert r.status_code == 200, r.get_data(as_text=True)
        assert webapp_server.CONFIG["server_url"] == PROVIDER_B
        assert webapp_server.CONFIG["api_key"] is None
        assert webapp_server.CONFIG.get("api_key_origin") is None

    def test_a_new_path_on_the_same_origin_keeps_the_token(self, client):
        _saved_at("https://api.example.com/v1", TOKEN_A)
        r = client.post("/api/config", json={"server_url": "https://api.example.com/v2"})
        assert r.status_code == 200, r.get_data(as_text=True)
        assert webapp_server.CONFIG["api_key"] == TOKEN_A

    def test_with_no_saved_token_a_new_server_still_saves(self, client):
        webapp_server.CONFIG["server_url"] = PROVIDER_A
        webapp_server.CONFIG["api_key"] = None
        r = client.post("/api/config", json={"server_url": PROVIDER_B})
        assert r.status_code == 200, r.get_data(as_text=True)
        assert webapp_server.CONFIG["server_url"] == PROVIDER_B


# ---------------------------------------------------------------------------
# A token with no recorded provider is not silently trusted off-machine
# ---------------------------------------------------------------------------

class TestAnInheritedTokenIsNotTrustedEverywhere:
    """`--api-key` / `SCREENPLAY_STUDIO_API_KEY` set the token at launch, and a
    config written before this check existed has no origin recorded either.
    Refusing all of them would break every existing install, so they keep
    working where they cannot leak — a loopback endpoint, which never receives
    the token anyway — and are refused anywhere else."""

    def test_an_unrecorded_token_is_used_on_a_loopback_endpoint(self, client, recording_server):
        base, recorder = recording_server
        webapp_server.CONFIG["server_url"] = base
        webapp_server.CONFIG["api_key"] = TOKEN_A       # as a CLI flag would set it
        assert webapp_server.CONFIG.get("api_key_origin") is None, "precondition"
        r = client.post("/api/test-connection", json={"server_url": base})
        assert r.get_json()["ok"] is True, r.get_data(as_text=True)

    def test_an_unrecorded_token_is_refused_off_machine(self, client):
        """Asserted on the predicate and on the message, not on `ok: false`.

        A non-routable host makes `ok: false` true for the wrong reason (the
        connection fails anyway), so that assertion would pass with the guard
        removed — measured, not assumed: it did. The predicate and the refusal
        wording are only true when the guard is the thing doing the refusing.
        """
        webapp_server.CONFIG["server_url"] = "http://127.0.0.1:8080"
        webapp_server.CONFIG["api_key"] = TOKEN_A
        assert webapp_server._credential_is_sendable_to(PROVIDER_B) is False
        assert webapp_server._credential_is_sendable_to("http://127.0.0.1:8080") is True
        assert webapp_server._credential_refusal(PROVIDER_B) is not None

    def test_the_refusal_does_not_claim_to_know_where_it_came_from(self, client):
        """Honest wording: `None` is not a provider, and saying 'it was entered
        for None' would be a bug report of its own."""
        webapp_server.CONFIG["server_url"] = "http://127.0.0.1:8080"
        webapp_server.CONFIG["api_key"] = TOKEN_A
        msg = client.post("/api/test-connection",
                          json={"server_url": PROVIDER_B}).get_json()["message"]
        assert "None" not in msg
        assert "--api-key" in msg or "SCREENPLAY_STUDIO_API_KEY" in msg

    def test_an_unparseable_endpoint_never_receives_the_secret(self):
        webapp_server.CONFIG["api_key"] = TOKEN_A
        assert webapp_server._credential_is_sendable_to("not a url") is False

    def test_the_approval_cannot_outlive_the_token_it_describes(self, client):
        """Clearing the token must clear its origin: a later token typed
        elsewhere must not inherit an approval it never had."""
        _saved_at(PROVIDER_A, TOKEN_A)
        assert webapp_server.CONFIG.get("api_key_origin") is not None
        webapp_server.CONFIG["api_key"] = None
        assert webapp_server.CONFIG.get("api_key_origin") is None

    def test_assigning_a_fresh_token_clears_the_old_approval(self, monkeypatch):
        monkeypatch.setattr(webapp_server, "_ALLOW_REMOTE_SERVER", True)
        _saved_at(PROVIDER_A, TOKEN_A)
        webapp_server.CONFIG["api_key"] = TOKEN_B   # e.g. the CLI flag at startup
        assert webapp_server.CONFIG.get("api_key_origin") is None, (
            "a token nobody approved inherited provider A's approval")


# ---------------------------------------------------------------------------
# The bookkeeping is internal state, not a setting
# ---------------------------------------------------------------------------

class TestTheOriginIsNotASetting:
    def test_it_is_absent_from_a_config_snapshot(self):
        assert "api_key_origin" not in webapp_server.CONFIG.to_dict()

    def test_it_is_absent_from_the_api(self, client):
        _saved_at(PROVIDER_A, TOKEN_A)
        for route in ("/api/config", "/api/health"):
            body = client.get(route).get_data(as_text=True)
            assert "api_key_origin" not in body, f"{route} exposes internal state"
            assert TOKEN_A not in body


# ---------------------------------------------------------------------------
# The written record must not contradict the code
# ---------------------------------------------------------------------------

def test_the_graded_table_does_not_still_call_gap_57_open():
    """The register is the deliverable, so a stale row is a wrong answer.

    Gap 57's row and gap 118's justification both described the token as
    un-bound; 118's `credentials_scope` was pinned to `"global"` *because* 57 was
    open. When 57 was fixed, both had to move in the same commit — this test is
    what makes forgetting one a failure instead of a quiet inconsistency.
    """
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    table = (root / "ENTRY_GRADE_TABLE.md").read_text(encoding="utf-8")
    row57 = next(ln for ln in table.splitlines() if ln.startswith("| 57 |"))
    assert "FIXED" in row57, "gap 57's row still reads as open"
    assert row57.count("|") == 6, "gap 57's row lost a column"

    row118 = next(ln for ln in table.splitlines() if ln.startswith("| 118 |"))
    assert "credentials_scope" in row118
    assert "gap 57 is FIXED" in row118, (
        "row 118 still explains its scope from the time gap 57 was open")

    critique = (root / "SELF_CRITIQUE_OF_GAP_REGISTER.md").read_text(encoding="utf-8")
    assert "## §44" in critique, "the fix has no written critique entry"
