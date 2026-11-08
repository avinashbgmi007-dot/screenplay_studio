"""OpenAI-compatible base URLs may include a final /v1 path segment."""
from __future__ import annotations

from unittest.mock import Mock

import pytest

from screenplay_analyzer.llm_client_base import normalize_openai_base_url


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        ("http://provider.example", "http://provider.example"),
        ("http://provider.example/v1", "http://provider.example"),
        ("http://provider.example/v1/", "http://provider.example"),
        ("http://provider.example/gateway", "http://provider.example/gateway"),
        ("http://provider.example/gateway/v1", "http://provider.example/gateway"),
        ("http://provider.example/gateway/v1/", "http://provider.example/gateway"),
        ("http://provider.example/v1ish", "http://provider.example/v1ish"),
    ],
)
def test_normalize_openai_base_url_only_strips_a_final_v1_segment(base, expected):
    assert normalize_openai_base_url(base) == expected


def _response():
    response = Mock()
    response.status_code = 200
    response.text = ""
    response.headers = {}
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "choices": [{"message": {"content": "{}"}}],
    }
    response.encoding = None
    response.iter_lines.return_value = [
        'data: {"choices":[{"delta":{"content":"ok"}}]}',
        "data: [DONE]",
    ]
    response.close.return_value = None
    return response


def test_analyzer_primary_and_fast_chat_use_one_version_segment(monkeypatch):
    import screenplay_analyzer.llm_client_base as base_module
    from screenplay_analyzer.llm_client import LlamaServerClient

    client = LlamaServerClient(
        "http://provider.example/gateway/v1", model="primary-model", fast_model="fast-model",
        extra_headers={"Authorization": "Bearer synthetic-token"},
    )
    client.resolve_model = lambda: "primary-model"
    client.resolve_model_id = lambda model: model
    calls = []

    def post(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return _response()

    monkeypatch.setattr(base_module, "request_no_redirects", post)
    assert client.chat_json("system", "primary", fast=False) == {}
    assert client.chat_json("system", "fast", fast=True) == {}

    assert [call[1] for call in calls] == [
        "http://provider.example/gateway/v1/chat/completions",
        "http://provider.example/gateway/v1/chat/completions",
    ]
    assert [call[2]["json"]["model"] for call in calls] == ["primary-model", "fast-model"]
    assert all(call[2]["headers"]["Authorization"] == "Bearer synthetic-token" for call in calls)


def test_cowriter_chat_and_stream_use_one_version_segment(monkeypatch):
    import screenplay_cowriter.llm_client as coworker_module
    from screenplay_cowriter.llm_client import LlamaServerClient

    client = LlamaServerClient(
        "http://provider.example/gateway/v1", model="writer-model",
        extra_headers={"Authorization": "Bearer synthetic-token"},
    )
    client.resolve_model = lambda: "writer-model"
    calls = []

    def post(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return _response()

    monkeypatch.setattr(coworker_module, "request_no_redirects", post)
    messages = [{"role": "user", "content": "hello"}]
    assert client.chat(messages) == "{}"
    assert client.chat_stream(messages, lambda _piece: None) == "ok"

    expected = "http://provider.example/gateway/v1/chat/completions"
    assert [call[1] for call in calls] == [expected, expected]
    assert all(call[2]["headers"]["Authorization"] == "Bearer synthetic-token" for call in calls)
    assert calls[1][2]["stream"] is True
