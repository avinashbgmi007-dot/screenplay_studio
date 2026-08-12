"""
Regression tests for the grammar-build compatibility fix.

The PEG-era llama.cpp grammar parser (turboquant / "peg-native" builds)
rejects two things the app's older grammars relied on:

  1. Multi-line rule bodies — a rule body spanning several lines makes the
     parser report "expecting name" at the first token of the continuation
     line. The server then silently drops the grammar and runs unconstrained,
     so the schema guarantee vanishes without any visible error.
  2. `\x00-\x1f` hex ranges and backslash escapes inside character classes.

These tests pin the invariants so a future edit can't silently reintroduce
either pattern, and pin the client-side half of the fix: grammar-constrained
calls disable thinking so the constrained JSON lands in `content` (which the
client parses) instead of `reasoning_content`.
"""

import json

import pytest

from screenplay_analyzer import grammar as grammar_mod
from screenplay_analyzer.llm_client import LlamaServerClient

# Every rule body must be a single line. A multi-line body (continuation
# lines) is what the PEG parser rejects with "expecting name".
ALL_GRAMMARS = [
    grammar_mod.findings_grammar,
    grammar_mod.scene_summary_grammar,
    grammar_mod.principle_judgment_grammar,
    grammar_mod.replacements_grammar,
    grammar_mod.logline_test_grammar,
    grammar_mod.character_reads_grammar,
    grammar_mod.coverage_grammar,
]


@pytest.mark.parametrize("build", ALL_GRAMMARS, ids=lambda f: f.__name__)
def test_every_rule_is_single_line(build):
    g = build()
    for line in g.splitlines():
        if not line.strip():
            continue
        # A rule definition ends at the newline; continuation content on a
        # later line would mean the rule body was split across lines.
        assert line.count("::=") == 1, (
            f"rule split across lines (PEG parser rejects this): {line!r}"
        )


@pytest.mark.parametrize("build", ALL_GRAMMARS, ids=lambda f: f.__name__)
def test_char_class_uses_compatible_form(build):
    g = build()
    # The rejected constructs: hex control ranges and backslash escapes
    # inside [ ... ].
    assert "\\x00-" not in g
    assert "\\x01-" not in g
    assert "[\\x1f" not in g
    assert "[^\"\\\\" not in g  # negated class containing an escaped backslash
    assert "[\\\\/bfnrt]" not in g
    # The compatible form must be present in every grammar that has strings.
    if "string ::" in g:
        assert "[\\x20-\\x21] | [\\x23-\\x5B] | [\\x5E-\\x7E] | [\\x80-\\u10FFFF]" in g
        # The PEG parser rejects these escape literals outright; they must not
        # appear in any string rule.
        assert "\\\"" in g  # the \" escape literal IS allowed and present
        assert "\\\\" in g
        assert "\\/" not in g
        assert "\\b" not in g
        assert "\\f" not in g


def test_payload_disables_thinking_when_grammar_present(monkeypatch):
    """Grammar-constrained calls must disable reasoning so the constrained
    JSON lands in `content` rather than `reasoning_content`."""
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [{
                    "message": {"content": '{"ok": true}'},
                    "finish_reason": "stop",
                }],
                "usage": {},
            }

    def fake_post(url, json=None, timeout=None, headers=None):
        captured["payload"] = json
        return FakeResp()

    import requests
    monkeypatch.setattr(requests, "post", fake_post)

    client = LlamaServerClient("http://localhost:8080")
    client._resolved_model = "test-model"

    out = client.chat_json("sys", "usr", grammar="root ::= \"a\"")
    assert out == {"ok": True}
    payload = captured["payload"]
    assert payload["grammar"] == 'root ::= "a"'
    assert payload.get("chat_template_kwargs") == {"enable_thinking": False}


def test_payload_keeps_thinking_when_no_grammar(monkeypatch):
    """Conversational calls (no grammar) should not force thinking off."""
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}], "usage": {}}

    def fake_post(url, json=None, timeout=None, headers=None):
        captured["payload"] = json
        return FakeResp()

    import requests
    monkeypatch.setattr(requests, "post", fake_post)

    client = LlamaServerClient("http://localhost:8080")
    client._resolved_model = "test-model"

    client.chat_json("sys", "usr")
    assert "chat_template_kwargs" not in captured["payload"]
