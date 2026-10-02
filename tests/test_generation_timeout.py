"""R4 (audit M1/M2): a logical model call is wall-clock bounded, and a
recovered retry is reported rather than swallowed.

M1: chat_json retries parse failures internally and _post_chat retries the
server's busy window — but nothing bounded the TOTAL. A hung generation with
timeout=600 could legally consume (retries+1) x 600s of dead air inside one
category. The wall-clock budget makes every HTTP attempt draw from one
deadline, shrinking each attempt's slice.

M2: the char_reads retry (attempts=2) succeeded on the real server more than
once — and the report never said so. A successful recovery now lands in
result.notices, rendered as a "Run Notes" section, distinct from warnings.
"""

import io
import os
import time
from unittest import mock

import pytest

from screenplay_analyzer import pipeline
from screenplay_analyzer.llm_client import LlamaServerClient, LlamaServerError
from screenplay_analyzer.llm_client_base import LlamaServerError as BaseLlamaServerError
from screenplay_analyzer.report import render_markdown
from screenplay_parser import parse_fountain

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "pain_tenglish.fountain")


# ---------------------------------------------------------------------------
# M1: wall-clock budget
# ---------------------------------------------------------------------------

def _json_response(payload):
    import json as _json
    r = mock.Mock()
    r.status_code = 200
    r.text = _json.dumps(payload)
    r.json.return_value = payload
    r.raise_for_status.side_effect = None
    return r


def _client(timeout=600):
    c = LlamaServerClient(base_url="http://127.0.0.1:9999", model="m", timeout=timeout)
    c._resolved_model = "m"
    return c


def test_wall_clock_budget_caps_per_attempt_timeout():
    """Each HTTP attempt draws from the SAME deadline: with a 5s budget and a
    600s configured timeout, the first request must be given ~5s — not 600s —
    so a hung generation can never outlive the logical call."""
    c = _client(timeout=600)
    seen = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        seen["timeout"] = timeout
        return _json_response({"choices": [{"message": {"content": "{\"ok\": 1}"}}]})

    with mock.patch("requests.post", side_effect=fake_post):
        out = c.chat_json("s", "u", wall_clock=5.0)
    assert out == {"ok": 1}
    assert seen["timeout"] <= 5.0, "the attempt must be bounded by the budget, not the 600s client timeout"


def test_wall_clock_budget_stops_second_attempt():
    """A hung first attempt consumes the whole budget; the parse-retry loop
    must not fire a second request that is born dead."""
    c = _client(timeout=600)

    def fake_post(url, json=None, timeout=None, headers=None):
        import requests as _r
        raise _r.exceptions.Timeout("hung")

    with mock.patch("requests.post", side_effect=fake_post), mock.patch("time.sleep"):
        t0 = time.monotonic()
        with pytest.raises(LlamaServerError):
            c.chat_json("s", "u", retries=2, wall_clock=3.0)
        elapsed = time.monotonic() - t0
    assert elapsed < 30, "the budget must stop the retry loop, not let 3 attempts stack"


def test_wall_clock_none_disables_budget():
    """wall_clock=None restores the old behavior: full configured timeout on
    every attempt, no deadline checks."""
    c = _client(timeout=600)
    seen = []

    def fake_post(url, json=None, timeout=None, headers=None):
        seen.append(timeout)
        return _json_response({"choices": [{"message": {"content": "{\"ok\": 1}"}}]})

    with mock.patch("requests.post", side_effect=fake_post):
        c.chat_json("s", "u", wall_clock=None)
    assert seen == [600]


def test_budget_error_message_reports_actual_attempts():
    """When the budget (not the retry count) ends the loop, the error must not
    claim the full retries+1 attempts happened. (The attempt counter counts
    requests SENT, including failed ones — a request that times out still
    happened.)

    The fake clock advances 2s per monotonic() read, simulating a hung
    request that consumes the budget while requests.post is blocked — the
    condition the mock can't produce by doing nothing."""
    c = _client(timeout=600)

    class FakeTime:
        t = 0.0

        @staticmethod
        def monotonic():
            FakeTime.t += 2.0
            return FakeTime.t

        @staticmethod
        def sleep(s):
            pass

    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None, headers=None):
        calls["n"] += 1
        import requests as _r
        raise _r.exceptions.Timeout("hung")

    with mock.patch("screenplay_analyzer.llm_client.time", FakeTime), \
            mock.patch("requests.post", side_effect=fake_post):
        with pytest.raises(LlamaServerError) as ei:
            c.chat_json("s", "u", retries=2, wall_clock=3.0)
    msg = str(ei.value)
    assert calls["n"] == 1, "attempt 2's remaining budget was non-positive — it must not fire"
    assert "1 attempt(s)" in msg, msg
    assert "wall-clock budget" in msg


def test_default_budget_applies_without_opt_in():
    """The default (600s) budget must be active on every chat_json call —
    M1 was the *default* configuration's exposure, not an opt-in one."""
    c = _client(timeout=600)
    seen = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        seen["timeout"] = timeout
        return _json_response({"choices": [{"message": {"content": "{\"ok\": 1}"}}]})

    with mock.patch("requests.post", side_effect=fake_post):
        c.chat_json("s", "u")
    # ceil on the remaining slice keeps a healthy generation's full window
    assert seen["timeout"] == 600, "a generous budget must not cut a healthy generation short"


# ---------------------------------------------------------------------------
# M2: recovered retry is reported
# ---------------------------------------------------------------------------

class FlakyThenOkClient:
    """Fails the FIRST chat_json call overall (the summaries stage's), succeeds
    from then on. Responses are shaped by max_tokens: summaries ask for 800,
    char_reads for 1200 — so one client can serve the whole analyze() run."""

    def __init__(self):
        self.calls = 0
        self.summary_calls = 0
        self.read_calls = 0

    def chat_json(self, system, user, grammar=None, max_tokens=None, **kw):
        self.calls += 1
        if max_tokens == 800:  # scene summaries (the cheap tier)
            self.summary_calls += 1
            return {"summaries": [{"scene_number": 1, "summary": "Rahul hesitates at the door."}]}
        if max_tokens == 1200:  # the char_reads call
            self.read_calls += 1
            if self.read_calls == 1:
                raise LlamaServerError("llama-server busy: no slot available")
            return {"reads": [{"character": "RAHUL", "how_reads": "withdrawn",
                               "apparent_intent": "brave", "gap": "the gap"}]}
        return {}

    def resolve_model(self):
        return "test-model"


def _mini_doc():
    return parse_fountain(FIXTURE)


def test_char_reads_recovery_lands_in_notices():
    doc = _mini_doc()
    client = FlakyThenOkClient()
    reads = pipeline.run_character_reads(doc, "overview", client, ["RAHUL"])
    assert client.calls == 2, "the retry happened"
    assert reads, "the recovered call still returns verified reads"


def test_recovered_retry_visible_in_report_not_warnings():
    """The M2 contract: a recovery is rendered as good news in its own section,
    never as an Analysis Warning against the script."""
    result = pipeline.AnalysisResult(doc=_mini_doc())
    result.character_reads = [{"character": "R", "how_reads": "x", "apparent_intent": "y", "gap": "z"}]
    result.notices.append("The character-perception read hit a model hiccup but recovered on retry #1 — no findings were lost.")
    md = render_markdown(result)
    assert "Run Notes" in md
    assert "recovered on retry #1" in md
    assert "Analysis Warnings" not in md
    # and an empty notices list adds no section
    result2 = pipeline.AnalysisResult(doc=result.doc)
    assert "Run Notes" not in render_markdown(result2)


def test_analyze_char_reads_emits_retry_progress_and_notice(monkeypatch):
    """End-to-end through analyze(): a recovering char_reads call emits a live
    progress beat AND lands the notice in result.notices."""
    from screenplay_analyzer.pipeline import analyze

    doc = _mini_doc()
    client = FlakyThenOkClient()
    events = []
    beats = []
    captured = {}

    real_reads = pipeline.run_character_reads

    def spy_reads(doc_, overview_, client_, chars, **kw):
        # capture the hook analyze() passed BEFORE overwriting it — reading
        # kw["on_retry"] inside wrap would recurse into wrap itself
        real_hook = kw.get("on_retry")
        captured["on_retry"] = real_hook

        def wrap(n, exc):
            beats.append((n, str(exc)))
            if real_hook:
                real_hook(n, exc)

        kw["on_retry"] = wrap
        return real_reads(doc_, overview_, client_, chars, **kw)

    monkeypatch.setattr(pipeline, "run_character_reads", spy_reads)
    result = analyze(doc, client, run_categories=("char_reads",),
                     progress_cb=lambda ev: events.append(ev))

    assert result.category_outcomes.get("char_reads") == "ok"
    assert client.read_calls == 2, "the char_reads call itself failed once, then recovered"
    assert client.summary_calls >= 1, "summaries ran first (they feed the overview)"
    assert captured["on_retry"] is not None, "analyze must thread an on_retry hook"
    assert beats, "the retry hook fired"
    assert any("retrying" in (ev.get("detail") or "") for ev in events), \
        "the live progress stream must mention the retry"
    assert any("recovered on retry" in n for n in result.notices), result.notices
    assert all("Character-perception" not in e for e in result.errors), \
        "a recovered retry must NOT be recorded as an error"
