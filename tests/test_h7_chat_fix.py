"""Regression tests for H7 â€” chat must work against a real llama-server.

H7a. `_assemble_messages` emits up to FIVE `system` messages (system prompt +
scene block + quote context + few-shot examples + post-history voice reminder).
This llama-server build returns HTTP 500 on any payload with 2+ system messages.
The co-writer must send at most ONE system message.

H7b. The co-writer's chat client never sets `chat_template_kwargs.enable_thinking`
and reads only `message.content`. A reasoning model returns `content: ""` with the
reply in `reasoning_content`. The co-writer must set enable_thinking=False and fall
back to `reasoning_content` when `content` is empty.
"""
from __future__ import annotations

import json

from screenplay_cowriter import engine as engine_mod
from screenplay_cowriter.models import Session


# --------------------------------------------------------------------------
# H7a â€” single-system assembly
# --------------------------------------------------------------------------

def _make_engine():
    class StubClient:
        def __init__(self):
            self.messages = None

        def chat(self, messages, **kw):
            self.messages = messages
            return "ok"

    eng = engine_mod.CoWriterEngine.__new__(engine_mod.CoWriterEngine)
    eng.client = StubClient()
    eng.history_window = 16
    eng.script_ctx = None
    eng.report_ctx = None
    eng.premise = None
    eng.mood_text = None
    eng.memory = None
    eng.memory_scope = None
    eng.store = None
    eng._relationship_card = None
    eng._writer_library_text = None
    eng._doctor_case_text = None
    return eng


def test_assembled_messages_have_at_most_one_system_role():
    eng = _make_engine()
    session = Session.new("Test")
    branch = session.branch
    for i in range(6):
        branch.messages.append(
            engine_mod.Message(role="user" if i % 2 == 0 else "assistant",
                               content=f"turn {i}", mode="peer", partner="writing_partner"))
    messages = eng._assemble_messages(
        "SYSTEM PROMPT", branch.messages, "my question", "writing_partner",
        scene_block="SCENE TEXT HERE", quote_context="QUOTE CONTEXT HERE")
    roles = [m["role"] for m in messages]
    assert roles.count("system") <= 1, f"expected <=1 system message, got roles {roles}"
    from screenplay_cowriter.personas import post_history_reminder
    reminder = post_history_reminder("writing_partner")
    joined = "\n".join(m["content"] for m in messages)
    assert reminder in joined, "post-history voice reminder was dropped instead of folded"


def test_first_turn_has_single_system_message():
    eng = _make_engine()
    session = Session.new("Test")
    branch = session.branch
    messages = eng._assemble_messages(
        "SYSTEM PROMPT", branch.messages, "hello", "writing_partner",
        scene_block="SCENE", quote_context="QUOTE")
    assert [m["role"] for m in messages].count("system") <= 1



# --------------------------------------------------------------------------
# H7b — thinking disabled + reasoning_content fallback
# --------------------------------------------------------------------------

def _client_with_response(monkeypatch, response_payload):
    from screenplay_cowriter.llm_client import LlamaServerClient
    captured = {}

    class FakeResp:
        status_code = 200
        text = json.dumps(response_payload)

        def raise_for_status(self):
            return None

        def json(self):
            return response_payload

    def fake_post(url, json=None, timeout=None, headers=None, **kw):
        captured["payload"] = json
        return FakeResp()

    monkeypatch.setattr("requests.post", fake_post)
    c = LlamaServerClient("http://x", model="m")
    c._resolved_model = "m"
    return c, captured


def test_chat_sets_enable_thinking_false(monkeypatch):
    c, captured = _client_with_response(monkeypatch, {
        "choices": [{"message": {"role": "assistant", "content": "hi"}}]})
    c.chat([{"role": "user", "content": "hi"}])
    assert captured["payload"]["chat_template_kwargs"]["enable_thinking"] is False


def test_chat_falls_back_to_reasoning_content_when_content_empty(monkeypatch):
    c, _ = _client_with_response(monkeypatch, {
        "choices": [{"finish_reason": "length",
                     "message": {"role": "assistant", "content": "",
                                 "reasoning_content": "the real reply"}}]})
    out = c.chat([{"role": "user", "content": "hi"}])
    assert out == "the real reply"


def test_chat_stream_sets_enable_thinking_false(monkeypatch):
    from screenplay_cowriter.llm_client import LlamaServerClient
    captured = {}

    class FakeStream:
        status_code = 200
        encoding = "utf-8"

        def raise_for_status(self):
            return None

        def iter_lines(self, decode_unicode=True):
            yield 'data: {"choices":[{"delta":{"content":"hi"}}]}'
            yield "data: [DONE]"

        def close(self):
            return None

    def fake_post(url, json=None, timeout=None, headers=None, stream=False, **kw):
        captured["payload"] = json
        return FakeStream()

    monkeypatch.setattr("requests.post", fake_post)
    c = LlamaServerClient("http://x", model="m")
    c._resolved_model = "m"
    out = c.chat_stream([{"role": "user", "content": "hi"}], lambda t: None)
    assert captured["payload"]["chat_template_kwargs"]["enable_thinking"] is False
    assert out == "hi"
