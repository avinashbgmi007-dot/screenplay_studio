"""Gap 36: the context estimate is short-lived and refreshed on rejection.

All endpoints are synthetic request fakes. No model server or external data is
used; the fake monotonic clock makes expiry behavior deterministic.
"""
from __future__ import annotations

import pytest
import requests

from screenplay_analyzer import llm_client_base as base
from screenplay_analyzer.llm_client_base import BaseLlamaClient, LlamaServerError
from screenplay_cowriter import llm_client as cowriter


class _Response:
    def __init__(self, payload=None, *, status=200, text=""):
        self.payload = payload
        self.status_code = status
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        return self.payload


@pytest.fixture(autouse=True)
def _empty_cache(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(base, "_context_cache_now", lambda: now[0])
    with base._CONTEXT_WINDOW_LOCK:
        base._CONTEXT_WINDOW_CACHE.clear()
    yield now
    with base._CONTEXT_WINDOW_LOCK:
        base._CONTEXT_WINDOW_CACHE.clear()


def _props(n_ctx):
    return _Response({"default_generation_settings": {"n_ctx": n_ctx}})


def test_same_url_same_model_reprobes_after_positive_ttl(monkeypatch, _empty_cache):
    clock = _empty_cache
    answers = iter((_props(8192), _props(2048)))
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append(url)
        return next(answers)

    monkeypatch.setattr(base, "request_no_redirects", fake_request)
    client = BaseLlamaClient("http://model.local/", model="alias")
    assert client.context_window() == 8192
    assert client.context_window() == 8192
    assert len(calls) == 1
    clock[0] += 60.1
    assert client.context_window() == 2048
    assert len(calls) == 2


def test_model_ids_at_one_endpoint_have_independent_entries(monkeypatch):
    answers = iter((_props(8192), _props(4096)))
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append(url)
        return next(answers)

    monkeypatch.setattr(base, "request_no_redirects", fake_request)
    assert BaseLlamaClient("http://same.local", model="model-a").context_window() == 8192
    assert BaseLlamaClient("http://same.local", model="model-b").context_window() == 4096
    assert len(calls) == 2


def test_auth_contexts_are_separate_without_retaining_tokens(monkeypatch):
    answers = iter((_props(8192), _props(2048)))
    monkeypatch.setattr(base, "request_no_redirects",
                        lambda method, url, **kwargs: next(answers))
    a = BaseLlamaClient("http://tenant.local", model="shared", extra_headers={
        "Authorization": "Bearer synthetic-alpha",
    })
    b = BaseLlamaClient("http://tenant.local", model="shared", extra_headers={
        "Authorization": "Bearer synthetic-beta",
    })
    assert a.context_window() == 8192
    assert b.context_window() == 2048
    assert "synthetic-alpha" not in repr(base._CONTEXT_WINDOW_CACHE)
    assert "synthetic-beta" not in repr(base._CONTEXT_WINDOW_CACHE)


def test_unavailable_probe_uses_short_negative_ttl(monkeypatch, _empty_cache):
    clock = _empty_cache
    responses = [requests.ConnectionError("offline"), _props(4096)]
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append(url)
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(base, "request_no_redirects", fake_request)
    client = BaseLlamaClient("http://recovering.local", model="m")
    assert client.context_window() is None
    assert client.context_window() is None
    assert len(calls) == 1
    clock[0] += 10.1
    assert client.context_window() == 4096
    assert len(calls) == 2


@pytest.mark.parametrize("path", ["analyzer", "cowriter-sync", "cowriter-stream"])
def test_context_rejection_invalidates_cache_for_next_turn(monkeypatch, _empty_cache, path):
    props = iter((_props(8192), _props(2048)))
    props_calls = []

    def fake_props(method, url, **kwargs):
        props_calls.append(url)
        return next(props)

    rejection = _Response(status=400, text="prompt exceeds the maximum context length")

    def fake_chat(method, url, **kwargs):
        return rejection

    monkeypatch.setattr(base, "request_no_redirects", fake_props)
    if path == "analyzer":
        client = BaseLlamaClient("http://model.local", model="m")
        monkeypatch.setattr(base, "request_no_redirects",
                            lambda method, url, **kwargs: fake_props(method, url, **kwargs)
                            if url.endswith("/props") else fake_chat(method, url, **kwargs))
        assert client.context_window() == 8192
        with pytest.raises(LlamaServerError, match="cached context estimate was cleared"):
            client._post_chat({"model": "m", "messages": []})
    else:
        client = cowriter.LlamaServerClient("http://model.local", model="m")
        client._resolved_model = "m"
        monkeypatch.setattr(cowriter, "request_no_redirects",
                            lambda method, url, **kwargs: fake_chat(method, url, **kwargs))
        assert client.context_window() == 8192
        if path == "cowriter-sync":
            with pytest.raises(LlamaServerError, match="cached context estimate was cleared"):
                client.chat([], busy_retries=0)
        else:
            with pytest.raises(LlamaServerError, match="cached context estimate was cleared"):
                client.chat_stream([], lambda _piece: None)

    assert client.context_window() == 2048
    assert len(props_calls) == 2


def test_invalidation_after_fallback_clears_old_model_alias_too(monkeypatch):
    answers = iter((_props(8192), _props(2048)))
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append(url)
        return next(answers)

    monkeypatch.setattr(base, "request_no_redirects", fake_request)
    original = BaseLlamaClient("http://fallback.local", model="requested")
    assert original.context_window() == 8192
    # A co-writer may mutate its model to a loaded fallback after the probe.
    original.model = "loaded-fallback"
    original.invalidate_context_window()
    fresh_request = BaseLlamaClient("http://fallback.local", model="requested")
    assert fresh_request.context_window() == 2048
    assert len(calls) == 2


def test_cache_is_bounded_when_many_model_ids_are_seen():
    for index in range(base._CONTEXT_WINDOW_CACHE_MAXSIZE + 1):
        client = BaseLlamaClient("http://many-models.local", model=f"m-{index}")
        client._probe_context_window = lambda: 4096
        assert client.context_window() == 4096
    assert len(base._CONTEXT_WINDOW_CACHE) <= base._CONTEXT_WINDOW_CACHE_MAXSIZE
