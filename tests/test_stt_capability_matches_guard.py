"""Gap 125: the dictation capability endpoint must not advertise an engine the
transcribe endpoint refuses.

Reproduced on one client with `SCREENPLAY_STUDIO_WHISPER_URL=http://speech.example.com:9000`:
`GET /api/stt/languages` answered 200 `engine: whisper-server` while
`POST /api/stt` answered 503 "must point at a LOCAL whisper server". The writer
was told dictation was configured, recorded a paragraph, and only then learned it
was not.

The guard itself was and is correct — what was missing is that the label never
ran it. These tests pin the two answers to each other rather than to a string.
"""

import io

import pytest

import screenplay_studio.webapp_server as webapp_server
from screenplay_studio import stt as stt_mod


@pytest.fixture
def client(tmp_path, monkeypatch):
    webapp_server.PROJECTS_DIR = str(tmp_path / "projects")
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


@pytest.fixture
def whisper_url(monkeypatch):
    def _set(url):
        monkeypatch.setattr(stt_mod, "EXTERNAL_WHISPER_URL", url)
        return url
    return _set


def _post_audio(client):
    return client.post("/api/stt", data={
        "audio": (io.BytesIO(b"\x00" * 512), "a.webm"), "language": "auto"})


class TestTheCapabilityAnswerMatchesTheGuard:
    def test_a_remote_url_is_not_advertised_as_a_whisper_server(self, client, whisper_url):
        whisper_url("http://speech.example.com:9000")
        body = client.get("/api/stt/languages").get_json()
        assert body["engine"] != "whisper-server", (
            "the capability endpoint promised an engine the transcribe route "
            "will refuse")
        assert body["engine"] == "faster-whisper"

    def test_the_refusal_is_reported_with_its_reason(self, client, whisper_url):
        whisper_url("http://speech.example.com:9000")
        body = client.get("/api/stt/languages").get_json()
        assert body.get("misconfigured") == "whisper-server"
        assert "LOCAL" in body.get("reason", ""), (
            "the writer gets no explanation until after they have recorded")

    def test_the_two_endpoints_are_consistent_for_every_configuration(
            self, client, whisper_url):
        """The whole point: whichever way it is configured, the label and the
        route must agree. This is the assertion that would have caught it.

        Two honest shapes, and the test allows both: either the endpoint
        advertises `whisper-server` and the route accepts it, or it does NOT
        advertise it and — when a URL was configured that the guard refuses —
        says why. No configuration may name an engine the route will refuse.
        """
        for url in ("", "http://127.0.0.1:8090", "http://localhost:8090",
                    "http://speech.example.com:9000", "http://127.0.0.1@evil.com"):
            whisper_url(url)
            body = client.get("/api/stt/languages").get_json()
            resp = _post_audio(client)
            # A 503 is not automatically the guard: a LOCAL server that simply
            # is not running also answers 503 ("could not be reached"), and
            # advertising whisper-server for that is honest — the configuration
            # is permitted, the machine just is not up. What must never happen is
            # the GUARD refusing after the label promised the engine.
            guard_refused = (resp.status_code == 503
                             and "never sends audio off the machine"
                             in str(resp.get_json()))
            if body["engine"] == "whisper-server":
                assert not guard_refused, (
                    f"{url!r}: advertised whisper-server but the guard refused it")
            elif url:
                # a URL WAS configured and the guard will not use it -> explained
                assert body.get("reason") and guard_refused, (
                    f"{url!r}: not advertised, but the writer is not told why")

class TestTheGuardStillDecides:
    def test_a_local_server_is_advertised_and_not_flagged(self, client, whisper_url):
        whisper_url("http://127.0.0.1:8090")
        body = client.get("/api/stt/languages").get_json()
        assert body["engine"] == "whisper-server"
        assert "misconfigured" not in body and "reason" not in body

    def test_not_configured_uses_the_in_process_engine(self, client, whisper_url):
        whisper_url("")
        body = client.get("/api/stt/languages").get_json()
        assert body["engine"] == "faster-whisper"
        assert "misconfigured" not in body

    def test_a_url_that_only_looks_local_is_still_refused(self, client, whisper_url):
        """`http://127.0.0.1@evil.com` is evil.com with a userinfo prefix — the
        old prefix check would have allowed it. The label must follow the guard
        here too, or this endpoint becomes the way around it."""
        whisper_url("http://127.0.0.1@evil.com")
        body = client.get("/api/stt/languages").get_json()
        assert body["engine"] == "faster-whisper"
        assert body.get("misconfigured") == "whisper-server"

    def test_the_label_runs_the_real_guard_rather_than_a_copy(self):
        """A second loopback test is how these two drift apart again."""
        import inspect
        src = inspect.getsource(stt_mod.engine_status)
        assert "_assert_local_whisper" in src, (
            "engine_status re-implements the check instead of calling the guard "
            "the route enforces")
