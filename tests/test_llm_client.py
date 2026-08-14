"""LlamaServerClient — busy-retry behavior.

llama-server is single-occupancy: a request arriving while another generation
is in flight gets a busy error (400/429/503) instead of queueing. The client
retries with linear backoff so a chat turn that loses the race to a running
analysis still lands, instead of failing the user's message.
"""

from unittest import mock

import pytest

from screenplay_cowriter.llm_client import LlamaServerClient, LlamaServerError


def _resp(status=200, text="", json_body=None):
    r = mock.Mock()
    r.status_code = status
    r.text = text
    r.json.return_value = json_body if json_body is not None else {
        "choices": [{"message": {"content": "hello from the model"}}]
    }
    r.raise_for_status.side_effect = None if status < 400 else _http_error(status)
    return r


def _http_error(status):
    import requests

    def _raise():
        raise requests.exceptions.HTTPError(f"{status} Client Error")

    return _raise


def _client():
    client = LlamaServerClient(base_url="http://127.0.0.1:9999", model="test-model")
    # skip resolve_model's network probe — the tests exercise the chat path
    client._resolved_model = "test-model"
    return client


def test_busy_400_with_busy_body_retries_then_succeeds():
    client = _client()
    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return _resp(400, text="slot unavailable: task already in progress")
        return _resp(200)

    with mock.patch("requests.post", side_effect=fake_post), mock.patch("time.sleep") as sleep:
        out = client.chat([{"role": "user", "content": "hi"}], busy_retries=3)
    assert out == "hello from the model"
    assert calls["n"] == 2
    sleep.assert_called_once()


def test_503_retries():
    client = _client()
    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return _resp(503, text="no slot available")
        return _resp(200)

    with mock.patch("requests.post", side_effect=fake_post), mock.patch("time.sleep"):
        out = client.chat([{"role": "user", "content": "hi"}], busy_retries=3)
    assert out == "hello from the model"
    assert calls["n"] == 2


def test_400_without_busy_body_does_not_retry():
    """A plain 400 is a genuine bad request — never mask it as busy."""
    client = _client()
    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        return _resp(400, text="model does not support chat")

    with mock.patch("requests.post", side_effect=fake_post):
        with pytest.raises(LlamaServerError):
            client.chat([{"role": "user", "content": "hi"}], busy_retries=3)
    assert calls["n"] == 1


def test_exhausts_retries_raises():
    client = _client()
    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        return _resp(503, text="no slot available")

    with mock.patch("requests.post", side_effect=fake_post), mock.patch("time.sleep"):
        with pytest.raises(LlamaServerError):
            client.chat([{"role": "user", "content": "hi"}], busy_retries=2)
    assert calls["n"] == 3  # initial attempt + 2 retries, then the error surfaces


def test_resolve_model_fallback_to_loaded():
    client = _client()
    with mock.patch.object(client, "list_models", return_value=["loaded-a", "loaded-b"]):
        assert client.resolve_model() == "test-model"

    fallback = LlamaServerClient(base_url="http://127.0.0.1:9999", model="missing", fallback_to_loaded=True)
    with mock.patch.object(fallback, "list_models", return_value=["loaded-a"]):
        assert fallback.resolve_model() == "loaded-a"
