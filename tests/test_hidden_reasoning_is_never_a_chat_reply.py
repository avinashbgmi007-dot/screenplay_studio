"""
Gap 32: hidden reasoning was streamed and used as an answer.

Filed with a synthetic SSE response, not a real provider incident. The old
client used `reasoning_content` as a fallback in both streaming and blocking
paths; the browser displayed stream tokens before the server's cleaning and
verification pipeline ran. These tests pin the boundary at the transport and
its user-visible provisional state.
"""

import json

import pytest

from screenplay_cowriter.llm_client import LlamaServerClient, LlamaServerError


class _Response:
    status_code = 200
    encoding = None

    def __init__(self, lines):
        self.lines = lines
        self.closed = False

    def raise_for_status(self):
        pass

    def iter_lines(self, decode_unicode=True):
        return iter(self.lines)

    def json(self):
        return self.payload

    def close(self):
        self.closed = True


def _client():
    client = LlamaServerClient("http://model.invalid", model="test")
    client._resolved_model = "test"
    return client


def _sse(**deltas):
    lines = []
    for delta in deltas["frames"]:
        lines.append("data: " + json.dumps({"choices": [{"delta": delta}]}))
    lines.append("data: [DONE]")
    return lines


class TestStreamingOnlyDeliversFinalContent:

    def test_reasoning_chunk_is_never_delivered_to_token_callback(self, monkeypatch):
        resp = _Response(_sse(frames=[
            {"reasoning_content": "private thought"},
            {"content": "The answer."},
        ]))
        monkeypatch.setattr("requests.post", lambda *a, **kw: resp)
        got = []
        answer = _client().chat_stream([], on_token=got.append)
        assert got == ["The answer."]
        assert answer == "The answer."
        assert resp.closed

    def test_reasoning_and_final_content_in_the_same_delta_only_show_content(self, monkeypatch):
        resp = _Response(_sse(frames=[{
            "reasoning_content": "private thought", "content": "Final."}]))
        monkeypatch.setattr("requests.post", lambda *a, **kw: resp)
        got = []
        assert _client().chat_stream([], on_token=got.append) == "Final."
        assert got == ["Final."]

    def test_stream_with_no_final_content_fails_instead_of_succeeding_empty(self, monkeypatch):
        resp = _Response(_sse(frames=[{"reasoning_content": "private thought"}]))
        monkeypatch.setattr("requests.post", lambda *a, **kw: resp)
        got = []
        with pytest.raises(LlamaServerError, match="no final answer"):
            _client().chat_stream([], on_token=got.append)
        assert got == []
        assert resp.closed


class TestBlockingOnlyAcceptsFinalContent:

    def test_reasoning_only_response_is_an_explicit_error(self, monkeypatch):
        resp = _Response([])
        resp.payload = {"choices": [{"message": {
            "content": "", "reasoning_content": "private thought"}}]}
        monkeypatch.setattr("requests.post", lambda *a, **kw: resp)
        with pytest.raises(LlamaServerError, match="no final answer"):
            _client().chat([])

    def test_whitespace_only_content_is_not_a_final_answer(self, monkeypatch):
        resp = _Response([])
        resp.payload = {"choices": [{"message": {"content": "  "}}]}
        monkeypatch.setattr("requests.post", lambda *a, **kw: resp)
        with pytest.raises(LlamaServerError, match="no final answer"):
            _client().chat([])

    def test_final_content_wins_but_reasoning_is_never_returned(self, monkeypatch):
        resp = _Response([])
        resp.payload = {"choices": [{"message": {
            "content": "Writer-facing answer.", "reasoning_content": "private thought"}}]}
        monkeypatch.setattr("requests.post", lambda *a, **kw: resp)
        assert _client().chat([]) == "Writer-facing answer."


class TestTheBrowserLabelsUnverifiedStreamingAsProvisional:

    def test_stream_ui_explicitly_calls_tokens_a_draft_until_final_history_arrives(self):
        from pathlib import Path
        app = Path("screenplay_studio/webapp/app.js").read_text(encoding="utf-8")
        assert "Streaming draft" in app
        assert "final reply replaces this" in app
        # The `done` event is the authoritative cleaned/stored history; the UI
        # caller paints `res.messages`, never treats the raw stream as history.
        assert "state.branches[sentFrom] =" in app
        assert "messages: res.messages" in app
