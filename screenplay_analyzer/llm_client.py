"""
Client for talking to a local llama-server (or any OpenAI-compatible)
instance. Handles model discovery, grammar/schema-constrained JSON
generation, and defensive parsing of whatever comes back (local models
occasionally wrap JSON in prose or stray whitespace even under a grammar,
depending on server version — this client doesn't trust the wrapper).
"""

from __future__ import annotations

import json
import re
import time

from .llm_client_base import (  # noqa: F401 — ModelNotFoundError is re-exported via screenplay_analyzer/__init__
    BaseLlamaClient,
    LlamaServerError,
    ModelNotFoundError,
)


def _extract_json(text: str):
    """
    Best-effort JSON extraction. Tries a straight parse first; if that
    fails (model added stray prose despite grammar/response_format),
    finds the first balanced {...} or [...] span and parses that instead.
    """
    text = text.strip()
    if not text:
        raise ValueError("Model returned completely empty content (0 characters).")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # find first balanced JSON object or array by bracket counting
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break  # fall through to try the other bracket type
    raise ValueError(f"Could not extract valid JSON from model output ({len(text)} chars):\n{text[:500]}")


def _diagnose_parse_failure(error: Exception, choice: dict, data: dict, content: str) -> str:
    """
    Turns a bare parse failure into an actionable message by pulling in
    whatever the server told us alongside the content: finish_reason and
    token usage, if present. completion_tokens == 0 (or finish_reason ==
    'length' with empty content) is the specific signature of a prompt
    that filled or exceeded the server's context window, leaving no room
    left to generate a response.
    """
    parts = [str(error)]
    finish_reason = choice.get("finish_reason")
    usage = data.get("usage") or {}
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")

    if not content.strip():
        hint = "The model returned completely empty content."
        if completion_tokens == 0 or finish_reason == "length":
            hint += (
                " This combination (no completion tokens generated / finish_reason=\"length\") "
                "strongly suggests the prompt filled or exceeded your llama-server's context "
                "window, leaving no budget left to generate a response. Try launching "
                "llama-server with a larger --ctx-size (-c), or this particular call is sending "
                "too much text at once for your current context size (a long script's scene-"
                "summary or dialogue-analysis passes send several full scenes per call)."
            )
        parts.append(hint)

    if finish_reason:
        parts.append(f"finish_reason='{finish_reason}'")
    if prompt_tokens is not None:
        parts.append(f"prompt_tokens={prompt_tokens}")
    if completion_tokens is not None:
        parts.append(f"completion_tokens={completion_tokens}")

    return " ".join(parts)


class LlamaServerClient(BaseLlamaClient):
    def __init__(self, base_url: str, model: str | None = None, timeout: int = 600, extra_headers: dict | None = None,
                 fallback_to_loaded: bool = False, fast_model: str | None = None):
        super().__init__(base_url, model=model, timeout=timeout, extra_headers=extra_headers,
                         fallback_to_loaded=fallback_to_loaded)
        self.fast_model = fast_model or None

    def list_models(self) -> list[dict]:
        return self.list_models_raw()

    def chat_json(
        self,
        system: str,
        user: str,
        grammar: str | None = None,
        max_tokens: int = 1500,
        temperature: float = 0.3,
        retries: int = 2,
        fast: bool = False,
        wall_clock: float | None = 600.0,
    ):
        """
        Sends a chat completion request and returns parsed JSON. Uses the
        llama.cpp `grammar` extension field (GBNF) when provided, on top of
        response_format json_object as a fallback signal for servers/paths
        that honor that instead.

        fast=True routes the call to the optional cheap tier (fast_model):
        summaries/refresh-style calls where a lighter model is fine.

        wall_clock: a total budget (seconds) for this LOGICAL call — every
        HTTP attempt inside it, including the internal parse-failure retries
        and the server's busy window, must fit inside it. Without it, one
        logical call could legally take (retries+1) x timeout plus busy
        backoff — minutes of dead air in an analysis run (audit M1). The
        budget degrades gracefully: if a budget slice shrinks below the
        configured timeout, the slice wins; if it would go non-positive,
        the call stops attempting. None disables the budget (old behavior).
        """
        if fast and self.fast_model:
            model = self.resolve_model_id(self.fast_model)
        else:
            model = self.resolve_model()
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        if grammar:
            payload["grammar"] = grammar
            payload.setdefault("chat_template_kwargs", {})
            payload["chat_template_kwargs"]["enable_thinking"] = False
            # Grammar-constrained calls degenerate into token loops ('",",",')
            # when repetition is unsuppressed — llama-server ships with
            # repeat_penalty 1.0 (off). A light penalty breaks the loop
            # without distorting normal prose.
            payload["repeat_penalty"] = 1.1
            payload["presence_penalty"] = 0.3

        last_error = None
        attempts_made = 0
        deadline = (time.monotonic() + wall_clock) if wall_clock else None
        for attempt in range(retries + 1):
            # Per-attempt timeout: this attempt's slice of the remaining
            # budget, capped at the configured timeout — a slow-but-healthy
            # generation gets its full configured window, but attempts can
            # never pile up to (retries+1) x timeout of dead air (audit M1).
            # A non-positive remainder (earlier attempts ate the budget)
            # stops the loop rather than firing one more request that is
            # born dead.
            slice_ = None
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                # ceil so a fresh full-budget attempt keeps its exact
                # configured timeout (599.9999 would otherwise be reported —
                # and behave — as a hair under what the caller configured).
                import math as _math
                slice_ = min(_math.ceil(remaining), float(self.timeout))
            attempts_made += 1  # a request is being SENT (success or not)
            try:
                data = self._post_chat(payload, busy_retries=6, timeout=slice_)
            except LlamaServerError as e:
                last_error = str(e)
                if attempt < retries:
                    # The 1s settle is NOT deducted from the budget; the
                    # budget measures generation time. Worst-case drift is
                    # ~1s per attempt against a 600s budget — acceptable.
                    time.sleep(1)
                    continue
                break

            try:
                choice = data["choices"][0]
                content = choice["message"]["content"]
            except (KeyError, IndexError) as e:
                last_error = f"Unexpected response shape from llama-server (missing choices/message/content): {e}"
                if attempt < retries:
                    time.sleep(1)
                    continue
                break

            try:
                return _extract_json(content)
            except ValueError as e:
                last_error = _diagnose_parse_failure(e, choice, data, content)
                if attempt < retries:
                    time.sleep(1)
                    continue
                break

        raise LlamaServerError(
            f"Model output could not be parsed as JSON after {attempts_made} attempt(s)"
            + (f" within the {wall_clock:.0f}s wall-clock budget" if wall_clock else "")
            + f". Last error: {last_error}"
        )
