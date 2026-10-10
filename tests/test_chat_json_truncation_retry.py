"""A truncated reply must still be RETRIED, not failed fast.

The tempting optimisation is: `finish_reason == 'length'` means the reply was
cut off by `max_tokens`, so retrying the identical request will truncate again
— skip the ladder and raise immediately so `_with_chunk_backoff` splits sooner.
That optimisation is WRONG, and this file exists to stop it being made.

Measured on qwen3.6 / Pain_3 (I2 probe, `i2_report_run2.json` + `i2_report.json`),
counting every logical `chat_json` call that threw away a body:

| run | truncating calls | recovered by a later attempt | exhausted the ladder |
|---|---:|---:|---:|
| run 2 (old budgets) | 9 | **6** | 3 |
| run 3 (sized budgets) | 5 | **4** | 1 |
| pooled | 14 | **10 (71 %)** | 4 |

So the ladder is not paying three times for the same failure — it is the
mechanism that recovers it. Sampling at `temperature=0.3` draws a different,
usually shorter reply, and a degenerate token loop (which is what fills the cap)
is stochastic, so a resample escapes it most of the time.

Failing fast would convert those 10 recoveries into forced chunk splits — and a
split is measurably NOT equivalent: the same gun_pen dialogue input yielded
**8 findings unsplit vs 12 split** (`i2_split.py`). Prefer the resample; keep the
split as the fallback for the calls that exhaust the ladder.

What IS worth keeping, and is pinned below: the raised error names the cause
(`finish_reason='length'` + the token counts), so an exhausted truncation is
diagnosable rather than reported as a generic parse failure.
"""
import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_analyzer.llm_client import LlamaServerClient, LlamaServerError  # noqa: E402

TRUNCATED_JSON = '{"findings": [{"issue": "The scene opens on a held shot", "severity": "high'


def _truncated():
    """A reply cut off by the cap — unparseable, and the server says why."""
    return {
        "choices": [{"message": {"content": TRUNCATED_JSON}, "finish_reason": "length"}],
        "usage": {"prompt_tokens": 4100, "completion_tokens": 3000},
    }


def _complete(content='{"findings": []}'):
    return {
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 4100, "completion_tokens": 220},
    }


def _client(replies):
    """A client whose transport is a scripted list of replies."""
    client = LlamaServerClient(base_url="http://127.0.0.1:9", model="test-model")
    client._resolved_model = "test-model"  # skip the /v1/models probe
    seen = {"n": 0, "payloads": []}

    def fake_post(payload, *a, **kw):
        seen["n"] += 1
        seen["payloads"].append(payload)
        idx = min(seen["n"] - 1, len(replies) - 1)
        return replies[idx]

    client._post_chat = fake_post
    return client, seen


def test_a_truncated_reply_is_retried_at_the_same_budget_and_recovers():
    """The whole point: attempt 1 truncates, attempt 2 is a resample that fits."""
    client, seen = _client([_truncated(), _complete()])
    with mock.patch("time.sleep"):
        out = client.chat_json("sys", "user", max_tokens=3000, retries=2)
    assert out == {"findings": []}
    assert seen["n"] == 2, (
        "a truncated reply must be retried, not failed fast — the ladder recovered "
        "10 of 14 truncating calls in the measured runs")
    # the retry is a RESAMPLE of the same request, not a different one: that is
    # what makes it cheap (no prompt re-shaping, no chunk split)
    assert [p["max_tokens"] for p in seen["payloads"]] == [3000, 3000]


def test_truncation_does_not_shorten_the_ladder():
    """If a future edit special-cases `finish_reason == 'length'` to bail on
    attempt 1, this fails. All retries+1 attempts must be spent."""
    client, seen = _client([_truncated()])
    with mock.patch("time.sleep"):
        with pytest.raises(LlamaServerError):
            client.chat_json("sys", "user", max_tokens=3000, retries=2)
    assert seen["n"] == 3, "the full ladder (1 + 2 retries) must be spent on truncation"


def test_an_exhausted_truncation_names_the_cause_in_the_error():
    """The failure is handed to the writer through `result.errors`, so it must
    say the reply hit the output limit — not just 'could not be parsed'."""
    client, _ = _client([_truncated()])
    with mock.patch("time.sleep"):
        with pytest.raises(LlamaServerError) as exc:
            client.chat_json("sys", "user", max_tokens=3000, retries=1)
    msg = str(exc.value)
    assert "finish_reason='length'" in msg
    assert "completion_tokens=3000" in msg


def test_a_truncated_reply_that_still_parses_is_returned():
    """A grammar-constrained reply can close its JSON and still report 'length'
    (the model wanted to keep going). That output is complete — return it."""
    valid_but_capped = {
        "choices": [{"message": {"content": '{"findings": []}'}, "finish_reason": "length"}],
        "usage": {"prompt_tokens": 4100, "completion_tokens": 3000},
    }
    client, seen = _client([valid_but_capped])
    with mock.patch("time.sleep"):
        out = client.chat_json("sys", "user", max_tokens=3000, retries=2)
    assert out == {"findings": []}
    assert seen["n"] == 1, "a parseable reply must not be retried just because it hit the cap"
