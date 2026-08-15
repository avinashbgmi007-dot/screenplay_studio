"""Audit items 3.1 + 3.2 — two-tier model routing and the generation watchdog.

Two-tier routing: the analyzer client can send cheap calls (scene summaries,
quick reads, the logline test) to an optional fast model, auto-falling back
to whatever is loaded when only one model exists. The watchdog: a chat turn
that exceeds its per-turn cap surfaces a distinguishable 408 (still_working)
instead of a silent multi-minute hang, and the retry is safe because the user
message is only stored after the model call succeeds.
"""

import io
import os
from unittest import mock

import pytest

from screenplay_analyzer.llm_client import LlamaServerClient, LlamaServerError
from screenplay_analyzer import pipeline
from screenplay_cowriter.llm_client import (
    LlamaServerClient as CowriterClient,
    LlamaServerError as CowriterError,
    WatchdogTimeoutError,
)

import screenplay_studio.webapp_server as webapp_server


# ---------------------------------------------------------------------------
# analyzer client — fast tier routing
# ---------------------------------------------------------------------------


def _analyzer_resp(json_body=None):
    r = mock.Mock()
    r.status_code = 200
    r.text = ""
    r.json.return_value = json_body if json_body is not None else {"choices": [{"message": {"content": "{}"}}]}
    r.raise_for_status.side_effect = None
    return r


def test_fast_tier_routes_to_fast_model():
    client = LlamaServerClient(base_url="http://127.0.0.1:9999", model="good-model",
                               fast_model="fast-model", fallback_to_loaded=True)
    seen = {}

    def fake_post(url, json=None, **kw):
        seen["model"] = json.get("model")
        return _analyzer_resp()

    with mock.patch("requests.post", side_effect=fake_post), \
         mock.patch.object(client, "list_models", return_value=[{"id": "good-model"}, {"id": "fast-model"}]):
        client.chat_json("sys", "usr", fast=True)
    assert seen["model"] == "fast-model"


def test_fast_tier_defaults_to_main_model_without_fast_model():
    """One-model box: fast=True must use the same model — never fail."""
    client = LlamaServerClient(base_url="http://127.0.0.1:9999", model="only-model",
                               fallback_to_loaded=True)
    seen = {}

    def fake_post(url, json=None, **kw):
        seen["model"] = json.get("model")
        return _analyzer_resp()

    with mock.patch("requests.post", side_effect=fake_post), \
         mock.patch.object(client, "list_models", return_value=[{"id": "only-model"}]):
        client.chat_json("sys", "usr", fast=True)
    assert seen["model"] == "only-model"


def test_fast_tier_unloaded_fast_model_falls_back():
    """fast_model pinned but not loaded: fall back to the loaded model."""
    client = LlamaServerClient(base_url="http://127.0.0.1:9999", model="good-model",
                               fast_model="fast-model", fallback_to_loaded=True)
    seen = {}

    def fake_post(url, json=None, **kw):
        seen["model"] = json.get("model")
        return _analyzer_resp()

    with mock.patch("requests.post", side_effect=fake_post), \
         mock.patch.object(client, "list_models", return_value=[{"id": "good-model"}]):
        client.chat_json("sys", "usr", fast=True)
    assert seen["model"] == "good-model"


def test_fast_tier_strict_raises_when_fast_model_missing():
    """Without fallback_to_loaded, an unloaded fast model is an error — the
    CLI keeps the strict contract (explicit model must be loaded)."""
    client = LlamaServerClient(base_url="http://127.0.0.1:9999", model="good-model",
                               fast_model="fast-model", fallback_to_loaded=False)
    with mock.patch.object(client, "list_models", return_value=[{"id": "good-model"}]):
        with pytest.raises(LlamaServerError):
            client.chat_json("sys", "usr", fast=True)


# ---------------------------------------------------------------------------
# pipeline — cheap stages carry fast=True
# ---------------------------------------------------------------------------


class _RecordingClient:
    """Records every chat_json call's kwargs; returns valid-ish shapes."""

    def __init__(self):
        self.calls = []
        self._model = "main"

    def resolve_model(self):
        return self._model

    def chat_json(self, system, user, grammar=None, max_tokens=0, temperature=0.0, fast=False):
        self.calls.append({"fast": fast, "max_tokens": max_tokens})
        return {"summaries": [], "reads": [], "logline_test": {}, "findings": []}


def _mini_doc():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "pain_tenglish.fountain")
    from screenplay_parser import parse_fountain
    return parse_fountain(path)


def test_summaries_route_to_fast_tier():
    client = _RecordingClient()
    pipeline.build_scene_summaries(_mini_doc(), client, chunk_size=99)
    assert client.calls, "summaries should have made model calls"
    assert all(c["fast"] for c in client.calls)


def test_logline_test_routes_to_fast_tier():
    client = _RecordingClient()
    pipeline.run_logline_test("A logline.", "overview", "T", client)
    assert client.calls and client.calls[-1]["fast"]


def test_character_reads_route_to_fast_tier():
    client = _RecordingClient()
    pipeline.run_character_reads(_mini_doc(), "overview", client, ["MARA", "RAJ"])
    assert client.calls and client.calls[-1]["fast"]


def test_deep_stages_do_not_use_fast_tier():
    """Dialogue analysis and script-level categories stay on the good model."""
    client = _RecordingClient()
    doc = _mini_doc()
    from screenplay_analyzer.rules_context import RulesContext
    pipeline.run_dialogue_analysis(doc, client, RulesContext(), chunk_size=99)
    assert client.calls, "dialogue should have made model calls"
    assert not any(c["fast"] for c in client.calls)


# ---------------------------------------------------------------------------
# watchdog — cowriter client raises a distinguishable timeout
# ---------------------------------------------------------------------------


def _cowriter_resp():
    r = mock.Mock()
    r.status_code = 200
    r.text = ""
    r.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    r.raise_for_status.side_effect = None
    return r


def test_chat_timeout_raises_watchdog_timeout_error():
    client = CowriterClient(base_url="http://127.0.0.1:9999", model="m", timeout=30)
    client._resolved_model = "m"
    import requests
    with mock.patch("requests.post", side_effect=requests.exceptions.Timeout("slow")):
        with pytest.raises(WatchdogTimeoutError):
            client.chat([{"role": "user", "content": "hi"}])


def test_watchdog_timeout_error_is_a_llama_server_error():
    assert issubclass(WatchdogTimeoutError, CowriterError)


# ---------------------------------------------------------------------------
# watchdog — webapp chat routes return the distinguishable 408
# ---------------------------------------------------------------------------


@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.CONFIG["fast_model"] = None
    webapp_server.CONFIG["turn_timeout"] = 120
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


SAMPLE_SCRIPT = b"""Title: Two Tier
Author: Test

INT. STUDY - NIGHT

MARA takes out an old REVOLVER.

MARA
I'll tell you everything when this is over.
"""


def _upload(http_client):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"), "title": "Two Tier"},
        content_type="multipart/form-data",
    )


def test_config_roundtrips_fast_model_and_turn_timeout(http_client):
    resp = http_client.post("/api/config", json={"fast_model": "fast-model", "turn_timeout": 45})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["fast_model"] == "fast-model"
    assert body["turn_timeout"] == 45

    resp = http_client.post("/api/config", json={"fast_model": ""})
    assert resp.get_json()["fast_model"] is None


def test_chat_route_408_on_watchdog_timeout(http_client):
    _upload(http_client)
    # get the project's first session via the chat start route
    resp = http_client.post("/api/projects/Two_Tier/chat/start")
    assert resp.status_code == 200
    sid = resp.get_json()["session_id"]

    import screenplay_cowriter.engine as engine_mod

    with mock.patch.object(engine_mod.CoWriterEngine, "send_message",
                          side_effect=WatchdogTimeoutError("The model didn't respond within 120s.")):
        resp = http_client.post(f"/api/projects/Two_Tier/chat/sessions/{sid}/messages",
                                json={"text": "hello"})
    assert resp.status_code == 408
    assert resp.get_json()["still_working"] is True


def test_chat_route_still_502_on_other_errors(http_client):
    _upload(http_client)
    resp = http_client.post("/api/projects/Two_Tier/chat/start")
    sid = resp.get_json()["session_id"]

    import screenplay_cowriter.engine as engine_mod

    with mock.patch.object(engine_mod.CoWriterEngine, "send_message",
                          side_effect=CowriterError("server unreachable")):
        resp = http_client.post(f"/api/projects/Two_Tier/chat/sessions/{sid}/messages",
                                json={"text": "hello"})
    assert resp.status_code == 502
    assert not resp.get_json().get("still_working")
