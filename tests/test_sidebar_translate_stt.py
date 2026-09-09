"""Sidebar flyouts (frontend, covered in the browser e2e), the translate
language picker, and local STT dictation.

- /translate accepts target_lang (en|te|hi|teng|hing); unknown -> 400;
  default stays English; demo model renders its own templates in every
  register (reverse twins).
- /api/stt: multipart audio in, text out -- fully local. Missing engine ->
  actionable 503; bad language -> 400.
- screenplay_studio.stt unit behavior: validation, localhost-only external
  override, lazy engine errors.
"""
import io

from test_idea_room_v2 import client  # noqa: F401 -- shared fixture (keep name)

PAGE = (
    "Rain Courier\n\n"
    "A courier discovers her bag swaps whatever is inside with an object "
    "from the recipient's greatest regret.\n"
)


def _make_reply(client):
    iid = client.post("/api/ideas", json={"title": "translate picker"}).get_json()["id"]
    client.post(f"/api/ideas/{iid}/content", json={"content": PAGE})
    sid = client.post(f"/api/ideas/{iid}/chat/start").get_json()["session_id"]
    resp = client.post(f"/api/ideas/{iid}/chat/sessions/{sid}/messages",
                       json={"text": "what do you think?"}).get_json()
    assert resp["reply"]
    return iid, sid


def test_translate_default_is_english(client):  # noqa: F811
    iid, sid = _make_reply(client)
    out = client.post(f"/api/ideas/{iid}/chat/sessions/{sid}/translate",
                      json={"index": 1}).get_json()
    assert "translation" in out


def test_translate_unknown_target_rejected(client):  # noqa: F811
    iid, sid = _make_reply(client)
    resp = client.post(f"/api/ideas/{iid}/chat/sessions/{sid}/translate",
                       json={"index": 1, "target_lang": "klingon"})
    assert resp.status_code == 400
    assert "Supported" in resp.get_json()["error"]


def test_translate_to_telugu_and_tenglish(client):  # noqa: F811
    """Demo replies come from our own template bank, so the reverse twins
    must land script-native Telugu and Tenglish respectively."""
    from screenplay_studio.demo_model import _demo_translate

    # a real English rendering of one of our own Tenglish templates
    english = ("Okay, the page caught my eye. The one thing that snags me is "
               "who is it for? When it happens, what should the audience feel?")
    te = _demo_translate(english, "te")
    assert any("\u0c00" <= ch <= "\u0c7f" for ch in te), te
    teng = _demo_translate(english, "teng")
    assert "page naa kallalo padindi" in teng or "Sare" in teng, teng
    hi = _demo_translate(english, "hi")
    assert any("\u0900" <= ch <= "\u097f" for ch in hi), hi


def test_translate_endpoint_forwards_target(client):  # noqa: F811
    iid, sid = _make_reply(client)
    # index 1 = assistant reply; whatever the demo said, the endpoint must
    # accept the target and return a translation field (not an error)
    for tgt in ("en", "te", "hi", "teng", "hing"):
        out = client.post(f"/api/ideas/{iid}/chat/sessions/{sid}/translate",
                          json={"index": 1, "target_lang": tgt})
        assert out.status_code == 200, (tgt, out.get_json())
        assert "translation" in out.get_json()


# ---------- STT ----------

def test_stt_requires_audio_part(client):  # noqa: F811
    resp = client.post("/api/stt", data={})
    assert resp.status_code == 400


def test_stt_bad_language_rejected(client):  # noqa: F811
    resp = client.post("/api/stt", data={"audio": (io.BytesIO(b"x"), "a.webm"),
                                         "language": "fr"})
    assert resp.status_code == 400
    assert "Supported" in resp.get_json()["error"]


def test_stt_engine_missing_actionable_503(client, monkeypatch):  # noqa: F811
    from screenplay_studio import stt as stt_mod
    monkeypatch.setattr(stt_mod, "_get_model",
                        lambda: (_ for _ in ()).throw(
                            stt_mod.STTUnavailableError("Local transcription needs the faster-whisper package.")))
    resp = client.post("/api/stt", data={"audio": (io.BytesIO(b"x"), "a.webm")})
    assert resp.status_code == 503
    assert "faster-whisper" in resp.get_json()["error"]


def test_stt_happy_path_with_fake_model(client, monkeypatch):  # noqa: F811
    from screenplay_studio import stt as stt_mod

    class _FakeSeg:
        text = " brass key "

    class _FakeModel:
        def transcribe(self, path, language=None, beam_size=1):
            assert language == "en"
            return iter([_FakeSeg()]), type("Info", (), {"language": "en"})()

    monkeypatch.setattr(stt_mod, "_get_model", lambda: _FakeModel())
    resp = client.post("/api/stt", data={"audio": (io.BytesIO(b"fake-bytes"), "speech.webm"),
                                         "language": "en"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["text"] == "brass key"
    assert body["engine"].startswith("faster-whisper")


def test_stt_empty_forced_language_retries_auto(client, monkeypatch):  # noqa: F811
    """Forcing a language can mis-decode foreign audio into an EMPTY transcript;
    the engine must retry once with auto-detect instead of returning nothing."""
    from screenplay_studio import stt as stt_mod

    calls = []

    class _FakeModel:
        def transcribe(self, path, language=None, beam_size=1):
            calls.append(language)
            if language == "hi":          # forced decode finds nothing
                return iter([]), type("Info", (), {"language": "hi"})()
            return iter([type("S", (), {"text": " the rain "})()]), \
                type("Info", (), {"language": "en"})()

    monkeypatch.setattr(stt_mod, "_get_model", lambda: _FakeModel())
    resp = client.post("/api/stt", data={"audio": (io.BytesIO(b"fake"), "s.webm"),
                                         "language": "hi"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["text"] == "the rain"
    assert calls == ["hi", None]          # forced first, auto-detect rescue second


def test_stt_genuinely_silent_audio_stays_empty(client, monkeypatch):  # noqa: F811
    """No rescue loop beyond ONE retry -- true silence returns an empty text."""
    from screenplay_studio import stt as stt_mod

    calls = []

    class _FakeModel:
        def transcribe(self, path, language=None, beam_size=1):
            calls.append(language)
            return iter([]), type("Info", (), {"language": language or "en"})()

    monkeypatch.setattr(stt_mod, "_get_model", lambda: _FakeModel())
    resp = client.post("/api/stt", data={"audio": (io.BytesIO(b"silence"), "s.webm"),
                                         "language": "auto"})
    assert resp.status_code == 200
    assert resp.get_json()["text"] == ""
    assert len(calls) == 1


def test_stt_languages_listing(client):  # noqa: F811
    langs = client.get("/api/stt/languages").get_json()["languages"]
    assert set(langs) >= {"auto", "en", "hi", "te"}


def test_external_whisper_url_must_be_local(monkeypatch):
    from screenplay_studio import stt as stt_mod
    monkeypatch.setattr(stt_mod, "EXTERNAL_WHISPER_URL", "https://evil.example.com")
    try:
        stt_mod.transcribe(b"bytes", "a.webm", "auto")
        raise AssertionError("non-local whisper URL must be refused")
    except stt_mod.STTUnavailableError as e:
        assert "LOCAL" in str(e)


def test_transcribe_validates_input():
    from screenplay_studio import stt as stt_mod
    try:
        stt_mod.transcribe(b"", "a.webm", "auto")
        raise AssertionError("empty audio should raise")
    except ValueError:
        pass


# ---------- startup flag/env parity ----------


def test_env_demo_model_survives_module_launch(tmp_path, monkeypatch):
    """Regression: SCREENPLAY_STUDIO_DEMO_MODEL=1 activates the demo at import,
    but webapp_server.main() used to reset CONFIG back to --server (:8080)
    afterwards -- silently killing demo chat when launched via the module.
    The demo URL chosen at import must survive main()."""
    import sys
    from screenplay_studio import webapp_server as ws
    monkeypatch.setattr(ws, "_DEMO_MODEL_ACTIVE", True)
    monkeypatch.setitem(ws.CONFIG, "server_url", "http://127.0.0.1:9091")  # demo url
    monkeypatch.setattr(ws.app, "run", lambda **kw: None)
    monkeypatch.setattr(sys, "argv",
                        ["webapp_server", "--port", "8599", "--projects-dir", str(tmp_path)])
    ws.main()
    assert ws.CONFIG["server_url"] == "http://127.0.0.1:9091"


def test_plain_module_launch_keeps_server_arg(tmp_path, monkeypatch):
    """Without any demo trigger, --server must still win (default flow intact)."""
    import sys
    from screenplay_studio import webapp_server as ws
    monkeypatch.setattr(ws, "_DEMO_MODEL_ACTIVE", False)
    monkeypatch.setitem(ws.CONFIG, "server_url", "http://stale.example:1")
    monkeypatch.setattr(ws.app, "run", lambda **kw: None)
    monkeypatch.setattr(sys, "argv",
                        ["webapp_server", "--port", "8599", "--projects-dir", str(tmp_path),
                         "--server", "http://localhost:1234"])
    ws.main()
    assert ws.CONFIG["server_url"] == "http://localhost:1234"
