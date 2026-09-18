"""The prompt budget is ON by default, and sized from the model (M1).

The budget mechanism (context.py, the shed ladder) shipped opt-in: it required
SCREENPLAY_PROMPT_BUDGET, which nobody sets, so the protection existed only on
paper and a feature-length prompt was still silently truncated. Two changes fix
that, and both are pinned here:

  1. **Default on** — an unset env var now yields a real budget rather than 0
     (unlimited). An explicit 0 still restores unlimited, because the CLI and
     the tests rely on being able to switch it off.
  2. **Derived per model** — the server sizes the budget from the context window
     the model reports (/props), because a fixed number is wrong in both
     directions: it over-trims a 90k-token model and still truncates a 4k one.
     The constant is only the fallback for a server that doesn't answer.

The derivation is best-effort by construction: a probe that fails, is missing,
or reports nonsense must hand the decision back to the constant rather than
break a chat turn or silently disable the budget.
"""

import os

import pytest

from screenplay_analyzer import llm_client_base
from screenplay_analyzer.llm_client_base import BaseLlamaClient
from screenplay_cowriter import context as ctx
from screenplay_cowriter.context import (
    PROMPT_TRIM_NOTE, ReportContext, ScriptContext, build_system_prompt,
    budget_for_context,
)
from screenplay_cowriter.engine import CoWriterEngine, _resolve_prompt_budget
from screenplay_cowriter.models import Session


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_probe_cache():
    """The context-window cache is module-level and keyed by base_url, so it
    outlives a test. Clear it on both sides or tests leak into each other."""
    with llm_client_base._CONTEXT_WINDOW_LOCK:
        llm_client_base._CONTEXT_WINDOW_CACHE.clear()
    yield
    with llm_client_base._CONTEXT_WINDOW_LOCK:
        llm_client_base._CONTEXT_WINDOW_CACHE.clear()


class _Resp:
    """Minimal stand-in for a requests.Response."""

    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise llm_client_base.requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _patch_props(monkeypatch, resp):
    """Patch /props. `resp` may be a _Resp, an Exception to raise, or a
    callable taking the url."""
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        if callable(resp):
            return resp(url)
        if isinstance(resp, Exception):
            raise resp
        return resp

    monkeypatch.setattr(llm_client_base.requests, "get", fake_get)
    return calls


class _Client:
    """Records the messages it was asked to complete, so a test can inspect the
    assembled prompt without a live model."""

    def __init__(self, reply="Noted.", **kw):
        self.reply = reply
        self.messages = None

    def _remember(self, messages):
        self.messages = messages
        return self.reply

    def chat(self, messages, **kw):
        return self._remember(messages)

    def chat_stream(self, messages, on_token=None, **kw):
        if on_token:
            on_token(self.reply)
        return self._remember(messages)


def _big_report(n=40):
    """A report large enough that a small budget has to shed something."""
    return ReportContext({
        "coverage": {"recommendation": "consider", "logline": "L", "genre": "G",
                     "tone": "T", "strengths": ["s"], "weaknesses": ["w"]},
        "findings": [
            {"category": "structure", "severity": ["high", "medium", "low"][i % 3],
             "issue": f"Issue number {i}", "why_it_matters": f"Rationale number {i}",
             "scene_refs": [i + 1]}
            for i in range(n)
        ],
    })


def _scenes(n=40):
    return ScriptContext({"title": "T", "scenes": [
        {"scene_number": i, "heading_raw": f"INT. PLACE {i} - NIGHT",
         "elements": [{"type": "character", "text": f"CHAR_{i % 6}"},
                      {"type": "action", "text": "action " * 8}]}
        for i in range(1, n + 1)
    ]})


MOOD = "MOODBLOCK " * 60


# --------------------------------------------------------------------------
# 1. the default is ON
# --------------------------------------------------------------------------

class TestTheDefaultIsOn:
    def test_the_default_budget_is_not_off(self):
        """The whole point of M1: an operator who sets nothing must still be
        protected. 0 means unlimited, so the default must not be 0."""
        assert ctx.DEFAULT_PROMPT_CHAR_BUDGET > 0

    def test_the_module_constant_uses_the_default_when_the_env_is_unset(self):
        if "SCREENPLAY_PROMPT_BUDGET" in os.environ:
            pytest.skip("the operator has set the budget explicitly")
        assert ctx.PROMPT_CHAR_BUDGET == ctx.DEFAULT_PROMPT_CHAR_BUDGET

    def test_an_oversized_prompt_is_actually_trimmed_by_the_default(self):
        """Proof the default bites: a prompt past the default budget loses a
        block and says so. Before M1 this prompt was sent whole."""
        huge = "PASTWORK " * (ctx.DEFAULT_PROMPT_CHAR_BUDGET // 8)
        full = build_system_prompt(_scenes(), _big_report(), "writing_partner", "peer",
                                   mood_text=MOOD, writer_library_text=huge, budget=0)
        assert len(full) > ctx.DEFAULT_PROMPT_CHAR_BUDGET
        trimmed = build_system_prompt(_scenes(), _big_report(), "writing_partner", "peer",
                                      mood_text=MOOD, writer_library_text=huge)
        assert len(trimmed) < len(full), "the default budget did not bite"
        assert PROMPT_TRIM_NOTE in trimmed

    def test_an_ordinary_prompt_is_untouched_by_the_default(self):
        """A realistic project must not be trimmed: the default exists to bound
        runaway growth, not to shave normal use."""
        prompt = build_system_prompt(_scenes(), _big_report(20), "writing_partner", "peer",
                                     mood_text=MOOD)
        assert len(prompt) < ctx.DEFAULT_PROMPT_CHAR_BUDGET
        assert PROMPT_TRIM_NOTE not in prompt
        assert MOOD in prompt

    def test_zero_still_means_unlimited(self):
        huge = "PASTWORK " * (ctx.DEFAULT_PROMPT_CHAR_BUDGET // 8)
        prompt = build_system_prompt(_scenes(), _big_report(), "writing_partner", "peer",
                                     mood_text=MOOD, writer_library_text=huge, budget=0)
        assert PROMPT_TRIM_NOTE not in prompt
        assert MOOD in prompt


# --------------------------------------------------------------------------
# 2. the env var
# --------------------------------------------------------------------------

class TestEnvOverride:
    """SCREENPLAY_PROMPT_BUDGET is read by _budget_from_env, which is what the
    module constant is built from — so these drive the real function through the
    real environment rather than re-implementing its parsing."""

    @pytest.mark.parametrize("raw,expected", [
        (None, 48000),     # unset        -> the default
        ("", 48000),       # blank        -> the default
        ("   ", 48000),    # whitespace   -> the default
        ("abc", 48000),    # typo         -> the default, NOT 0
        ("0", 0),          # explicit     -> unlimited
        ("-10", 0),        # negative     -> clamped to unlimited
        ("12345", 12345),  # a real value
    ])
    def test_values(self, monkeypatch, raw, expected):
        if raw is None:
            monkeypatch.delenv("SCREENPLAY_PROMPT_BUDGET", raising=False)
        else:
            monkeypatch.setenv("SCREENPLAY_PROMPT_BUDGET", raw)
        assert ctx._budget_from_env(48000) == expected

    def test_a_typo_does_not_silently_disable_the_protection(self, monkeypatch):
        """Falling back to 0 would turn a typo into 'no protection at all' —
        the exact silent failure M1 is about."""
        monkeypatch.setenv("SCREENPLAY_PROMPT_BUDGET", "48_000 chars please")
        assert ctx._budget_from_env(48000) == 48000

    def test_zero_is_still_an_explicit_opt_out(self, monkeypatch):
        monkeypatch.setenv("SCREENPLAY_PROMPT_BUDGET", "0")
        assert ctx._budget_from_env(48000) == 0


# --------------------------------------------------------------------------
# 3. the derivation
# --------------------------------------------------------------------------

class TestBudgetForContext:
    @pytest.mark.parametrize("n_ctx", [None, 0, -1, -4096])
    def test_an_unknown_or_nonsensical_window_yields_none(self, n_ctx):
        """None is the signal for 'use the constant' — so a garbage window must
        not be turned into a garbage budget."""
        assert budget_for_context(n_ctx) is None

    @pytest.mark.parametrize("n_ctx", [4096, 8192, 32768, 90112])
    def test_a_real_window_yields_a_positive_budget(self, n_ctx):
        budget = budget_for_context(n_ctx)
        assert isinstance(budget, int) and budget > 0

    def test_the_budget_grows_with_the_window(self):
        assert budget_for_context(4096) < budget_for_context(32768) < budget_for_context(90112)

    def test_the_documented_relationship_holds(self):
        """The two factors are named separately so either can move; at their
        current settings their product is 1.0. Pin that, so a change to either
        is a deliberate act rather than a silent drift."""
        assert (ctx.PROMPT_BUDGET_CONTEXT_FRACTION * ctx.PROMPT_BUDGET_CHARS_PER_TOKEN) == 1.0
        assert budget_for_context(10000) == 10000

    def test_the_derived_budget_is_below_the_window_it_came_from(self):
        """Conservative by construction: the prompt may claim only a fraction of
        the window, because the reply, the history and the injected scenes need
        the rest."""
        for n_ctx in (4096, 8192, 32768, 90112):
            assert budget_for_context(n_ctx) <= n_ctx


# --------------------------------------------------------------------------
# 4. the probe
# --------------------------------------------------------------------------

class TestContextWindowProbe:
    def test_reads_the_per_slot_window_from_default_generation_settings(self, monkeypatch):
        _patch_props(monkeypatch, _Resp({"default_generation_settings": {"n_ctx": 90112}}))
        assert BaseLlamaClient("http://x").context_window() == 90112

    def test_falls_back_to_a_top_level_n_ctx(self, monkeypatch):
        _patch_props(monkeypatch, _Resp({"n_ctx": 4096}))
        assert BaseLlamaClient("http://x").context_window() == 4096

    def test_returns_none_when_the_build_reports_no_window(self, monkeypatch):
        _patch_props(monkeypatch, _Resp({"model_path": "x.gguf", "total_slots": 1}))
        assert BaseLlamaClient("http://x").context_window() is None

    def test_returns_none_when_props_is_unreachable(self, monkeypatch):
        _patch_props(monkeypatch, llm_client_base.requests.ConnectionError("refused"))
        assert BaseLlamaClient("http://x").context_window() is None

    def test_returns_none_on_a_non_json_body(self, monkeypatch):
        _patch_props(monkeypatch, _Resp(ValueError("not json")))
        assert BaseLlamaClient("http://x").context_window() is None

    def test_returns_none_on_a_json_body_that_is_not_an_object(self, monkeypatch):
        _patch_props(monkeypatch, _Resp([1, 2, 3]))
        assert BaseLlamaClient("http://x").context_window() is None

    def test_returns_none_on_an_http_error(self, monkeypatch):
        _patch_props(monkeypatch, _Resp({}, status=404))
        assert BaseLlamaClient("http://x").context_window() is None

    @pytest.mark.parametrize("bad", ["lots", None, 0, -1, {}, []])
    def test_ignores_a_nonsensical_window(self, monkeypatch, bad):
        _patch_props(monkeypatch, _Resp({"default_generation_settings": {"n_ctx": bad}}))
        assert BaseLlamaClient("http://x").context_window() is None

    def test_the_probe_is_cached(self, monkeypatch):
        calls = _patch_props(monkeypatch, _Resp({"default_generation_settings": {"n_ctx": 8192}}))
        client = BaseLlamaClient("http://x")
        assert client.context_window() == 8192
        assert client.context_window() == 8192
        assert BaseLlamaClient("http://x").context_window() == 8192
        assert len(calls) == 1, "the window was re-probed for a fresh client on the same url"

    def test_a_missing_window_is_cached_too(self, monkeypatch):
        """Otherwise every turn on a build without /props pays a 3s timeout."""
        calls = _patch_props(monkeypatch, llm_client_base.requests.ConnectionError("refused"))
        assert BaseLlamaClient("http://x").context_window() is None
        assert BaseLlamaClient("http://x").context_window() is None
        assert len(calls) == 1

    def test_the_cache_is_keyed_by_url(self, monkeypatch):
        def by_url(url):
            return _Resp({"default_generation_settings": {"n_ctx": 4096 if "a" in url else 32768}})

        _patch_props(monkeypatch, by_url)
        assert BaseLlamaClient("http://a").context_window() == 4096
        assert BaseLlamaClient("http://b").context_window() == 32768


# --------------------------------------------------------------------------
# 5. resolving the engine's budget
# --------------------------------------------------------------------------

class TestResolvePromptBudget:
    def test_none_stays_none(self):
        """None means 'let build_system_prompt apply its own default'."""
        assert _resolve_prompt_budget(None) is None

    def test_an_int_passes_through(self):
        assert _resolve_prompt_budget(1234) == 1234

    def test_a_callable_is_invoked(self):
        assert _resolve_prompt_budget(lambda: 4321) == 4321

    def test_a_callable_returning_none_yields_none(self):
        assert _resolve_prompt_budget(lambda: None) is None

    def test_a_raising_callable_yields_none(self):
        """A probe that fails must fall back to the constant, not crash a turn."""
        def boom():
            raise RuntimeError("server went away")
        assert _resolve_prompt_budget(boom) is None

    def test_garbage_yields_none(self):
        assert _resolve_prompt_budget("lots") is None
        assert _resolve_prompt_budget(object()) is None

    def test_a_negative_value_clamps_to_unlimited(self):
        assert _resolve_prompt_budget(-5) == 0


class TestTheEngineDefersTheBudget:
    def test_constructing_the_engine_does_not_resolve_the_budget(self):
        """Same contract as the shelf blocks (C10): the probe must not run for a
        request that never builds a prompt."""
        calls = []
        engine = CoWriterEngine(_Client(), _scenes(), _big_report(),
                                prompt_budget=lambda: calls.append(1) or 99999)
        assert calls == [], "the budget provider ran at construction time"
        assert engine.prompt_budget is not None  # it is still wired up

    def test_a_turn_resolves_the_budget_and_uses_it(self, monkeypatch):
        """Plumbing only: the resolved number must reach build_system_prompt.
        The budget is deliberately generous so this test doesn't also trip the
        unreachable-budget warning — the trimming itself is the next test."""
        seen = {}
        real = build_system_prompt

        def spy(*a, **kw):
            seen.update(kw)
            return real(*a, **kw)

        monkeypatch.setattr("screenplay_cowriter.engine.build_system_prompt", spy)
        engine = CoWriterEngine(_Client(), _scenes(), _big_report(),
                                mood_text=MOOD, prompt_budget=lambda: 40000)
        engine.send_message(Session.new(title="t"), "hello")
        assert seen.get("budget") == 40000

    def test_the_resolved_budget_actually_trims_the_prompt(self):
        """End to end: a budget from the provider reaches the ladder and sheds a
        block. Sized off the measured prompt so it lands inside the reachable
        band (above the irreducible floor, below the untrimmed prompt) rather
        than under the floor, where the warning — not the trim — is the story."""
        sc, rep = _scenes(), _big_report()
        full = build_system_prompt(sc, rep, "writing_partner", "peer", mood_text=MOOD, budget=0)
        budget = len(full) - len(MOOD) + len(PROMPT_TRIM_NOTE) + 2
        engine = CoWriterEngine(_Client(), sc, rep, mood_text=MOOD,
                                prompt_budget=lambda: budget)
        engine.send_message(Session.new(title="t"), "hello")
        system = [m for m in engine.client.messages if m["role"] == "system"][0]["content"]
        assert PROMPT_TRIM_NOTE in system, "the provider's budget never reached the ladder"
        assert MOOD not in system, "the first ladder step should have shed the room state"

    def test_no_provider_leaves_the_prompt_alone(self):
        """The CLI passes nothing, so its turns must be byte-identical to before
        the budget existed — well under the default, so nothing is shed."""
        engine = CoWriterEngine(_Client(), _scenes(), _big_report(), mood_text=MOOD)
        engine.send_message(Session.new(title="t"), "hello")
        system = [m for m in engine.client.messages if m["role"] == "system"][0]["content"]
        assert PROMPT_TRIM_NOTE not in system
        assert MOOD in system

    def test_a_raising_provider_falls_back_instead_of_breaking_the_turn(self):
        def boom():
            raise RuntimeError("no server")
        engine = CoWriterEngine(_Client(), _scenes(), _big_report(),
                                mood_text=MOOD, prompt_budget=boom)
        engine.send_message(Session.new(title="t"), "hello")
        system = [m for m in engine.client.messages if m["role"] == "system"][0]["content"]
        assert MOOD in system  # the default budget is generous, so nothing shed


# --------------------------------------------------------------------------
# 6. the server's provider
# --------------------------------------------------------------------------

class TestServerProvider:
    def test_it_derives_the_budget_from_the_reported_window(self, monkeypatch):
        """Pinned with a sentinel rather than a number: at the current factor
        settings budget_for_context(n) == n, so a value assertion could not tell
        'derived through the documented conversion' from 'handed the raw window
        straight through'. The sentinel makes the difference visible."""
        import screenplay_cowriter.context as cctx
        import screenplay_studio.webapp_server as ws
        monkeypatch.setattr(cctx, "budget_for_context", lambda n: ("derived", n))
        _patch_props(monkeypatch, _Resp({"default_generation_settings": {"n_ctx": 8192}}))
        provider = ws._prompt_budget_provider(BaseLlamaClient("http://x"))
        assert provider() == ("derived", 8192)

    def test_it_sizes_a_real_window_through_the_documented_conversion(self, monkeypatch):
        import screenplay_studio.webapp_server as ws
        _patch_props(monkeypatch, _Resp({"default_generation_settings": {"n_ctx": 8192}}))
        provider = ws._prompt_budget_provider(BaseLlamaClient("http://x"))
        assert provider() == budget_for_context(8192)

    def test_it_returns_none_when_the_window_is_unknown(self, monkeypatch):
        import screenplay_studio.webapp_server as ws
        _patch_props(monkeypatch, _Resp({"model_path": "x.gguf"}))
        provider = ws._prompt_budget_provider(BaseLlamaClient("http://x"))
        assert provider() is None, "unknown window must fall back to the constant"

    def test_a_client_that_raises_returns_none(self, monkeypatch):
        import screenplay_studio.webapp_server as ws

        class Bad:
            def context_window(self):
                raise RuntimeError("boom")

        assert ws._prompt_budget_provider(Bad())() is None

    def test_the_provider_is_deferred(self, monkeypatch):
        import screenplay_studio.webapp_server as ws
        calls = _patch_props(monkeypatch, _Resp({"default_generation_settings": {"n_ctx": 4096}}))
        provider = ws._prompt_budget_provider(BaseLlamaClient("http://x"))
        assert calls == [], "building the provider probed the server"
        provider()
        assert len(calls) == 1
