"""Gap 60: one logical analyzer call deadline includes nested busy retries."""

from unittest import mock

import pytest

from screenplay_analyzer import llm_client as analyzer_client
from screenplay_analyzer import llm_client_base as base_client
from screenplay_analyzer.llm_client import LlamaServerClient
from screenplay_analyzer.llm_client_base import DeadlineExceededError


class FakeTime:
    now = 0.0

    @classmethod
    def monotonic(cls):
        return cls.now

    @classmethod
    def sleep(cls, seconds):
        cls.now += seconds


@pytest.fixture(autouse=True)
def reset_fake_clock():
    FakeTime.now = 0.0


class Response:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self.text = "busy" if status in (429, 503) else ""
        self.payload = payload or {"choices": [{"message": {"content": '{"ok": true}'}}]}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise base_client.requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


def _client(resolved=True):
    client = LlamaServerClient("http://127.0.0.1:9999", model="m", timeout=600)
    if resolved:
        client._resolved_model = "m"
    return client


def _clock_patches():
    return (
        mock.patch.object(analyzer_client, "time", FakeTime),
        mock.patch.object(base_client, "time", FakeTime),
    )


def test_busy_retry_stops_at_deadline_without_outer_retry_or_late_request():
    client = _client()
    sent_at = []
    responses = iter([Response(503) for _ in range(6)] + [Response()])

    def request(_method, _url, **kwargs):
        sent_at.append((FakeTime.now, kwargs["timeout"]))
        return next(responses)

    with _clock_patches()[0], _clock_patches()[1], \
            mock.patch.object(base_client, "request_no_redirects", side_effect=request), \
            mock.patch.object(base_client, "busy_retry_delay", return_value=0.5):
        with pytest.raises(DeadlineExceededError, match="deadline") as exc:
            client.chat_json("system", "user", retries=2, wall_clock=1.0)

    assert "2 attempt(s)" in str(exc.value)  # count actual HTTP sends, not the refused retry
    assert [when for when, _timeout in sent_at] == [0.0, 0.5]
    assert FakeTime.now == 1.0  # the last busy wait consumes only the remaining budget


def test_busy_retry_can_still_recover_before_deadline():
    client = _client()
    sent_at = []
    responses = iter([Response(503), Response()])

    def request(_method, _url, **kwargs):
        sent_at.append((FakeTime.now, kwargs["timeout"]))
        return next(responses)

    with _clock_patches()[0], _clock_patches()[1], \
            mock.patch.object(base_client, "request_no_redirects", side_effect=request), \
            mock.patch.object(base_client, "busy_retry_delay", return_value=0.25):
        assert client.chat_json("system", "user", wall_clock=1.0) == {"ok": True}

    assert [when for when, _timeout in sent_at] == [0.0, 0.25]
    assert FakeTime.now == 0.25


def test_none_keeps_ordinary_busy_retry_behavior():
    client = _client()
    sent_at = []
    responses = iter([Response(503) for _ in range(6)] + [Response()])

    def request(_method, _url, **kwargs):
        sent_at.append(FakeTime.now)
        return next(responses)

    with _clock_patches()[0], _clock_patches()[1], \
            mock.patch.object(base_client, "request_no_redirects", side_effect=request), \
            mock.patch.object(base_client, "busy_retry_delay", return_value=0.5):
        assert client.chat_json("system", "user", wall_clock=None) == {"ok": True}

    assert len(sent_at) == 7
    assert FakeTime.now == 3.0


def test_zero_budget_expires_immediately_without_a_request():
    client = _client()
    with _clock_patches()[0], _clock_patches()[1], \
            mock.patch.object(base_client, "request_no_redirects") as request:
        with pytest.raises(DeadlineExceededError, match="before model selection"):
            client.chat_json("system", "user", wall_clock=0)
    request.assert_not_called()


def test_outer_parse_retry_sleep_is_also_limited_by_the_same_deadline():
    client = _client()
    sent_at = []
    invalid = Response(payload={"choices": [{"message": {"content": "not JSON"}}]})

    def request(_method, _url, **kwargs):
        sent_at.append(FakeTime.now)
        return invalid

    with _clock_patches()[0], _clock_patches()[1], \
            mock.patch.object(base_client, "request_no_redirects", side_effect=request):
        with pytest.raises(DeadlineExceededError):
            client.chat_json("system", "user", retries=2, wall_clock=0.5)

    assert sent_at == [0.0]
    assert FakeTime.now == 0.5


def test_model_discovery_and_generation_share_the_deadline():
    client = _client(resolved=False)
    sent = []

    def request(method, url, **kwargs):
        sent.append((method, FakeTime.now, kwargs["timeout"]))
        if url.endswith("/v1/models"):
            FakeTime.now += 0.75
            return Response(payload={"data": [{"id": "m"}]})
        return Response(503)

    with _clock_patches()[0], _clock_patches()[1], \
            mock.patch.object(base_client, "request_no_redirects", side_effect=request), \
            mock.patch.object(base_client, "busy_retry_delay", return_value=0.5):
        with pytest.raises(DeadlineExceededError):
            client.chat_json("system", "user", wall_clock=1.0)

    assert [row[0] for row in sent] == ["get", "post"]
    assert sent[0][2] <= 1.0
    assert sent[1][1] == 0.75
    assert sent[1][2] <= 0.25
    assert FakeTime.now == 1.0
