"""
Client for llama-server chat completions. Unlike Piece 2's client, this
doesn't need grammar-constrained JSON output — co-writer replies are free
text. Kept as its own small module (not imported from Piece 2) so Piece 3
works standalone without Piece 2 installed, per the composability goal.
"""

from __future__ import annotations

import json
import re
import time

import requests


class LlamaServerError(Exception):
    pass


class ModelNotFoundError(LlamaServerError):
    pass


class WatchdogTimeoutError(LlamaServerError):
    """A chat turn exceeded the per-turn generation cap. Distinct from other
    LlamaServerErrors so the webapp can offer a "keep waiting?" retry instead
    of failing the turn — a slow local model is not the same failure as a
    dead server, and the writer shouldn't have to retype a long message."""
    pass


class LlamaServerClient:
    def __init__(self, base_url: str, model: str | None = None, timeout: int = 600, extra_headers: dict | None = None,
                 fallback_to_loaded: bool = False):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
        # When True, a model id that isn't currently loaded falls back to
        # whatever the server has loaded instead of raising. Used where the
        # model id is a *remembered preference* (session/manifest pins in the
        # webapp) rather than an explicit user choice — swapping the loaded
        # model must not brick existing conversations. The cowriter CLI keeps
        # the strict default: an explicit --model must be loaded.
        self.fallback_to_loaded = fallback_to_loaded
        self._resolved_model: str | None = None

    def list_models(self) -> list[str]:
        try:
            resp = requests.get(f"{self.base_url}/v1/models", timeout=15, headers=self.extra_headers)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError as e:
            raise LlamaServerError(
                f"Could not connect to llama-server at {self.base_url}. Is it running?"
            ) from e
        except requests.exceptions.Timeout as e:
            raise LlamaServerError(f"Timed out connecting to {self.base_url}") from e
        except requests.exceptions.HTTPError as e:
            raise LlamaServerError(f"llama-server at {self.base_url} returned an error: {e}") from e
        except (ValueError, requests.exceptions.JSONDecodeError) as e:
            raise LlamaServerError(f"llama-server at {self.base_url} returned a non-JSON response: {e}") from e

        entries = data.get("data", []) or data.get("models", [])
        ids = [e.get("id") or e.get("name") for e in entries]
        return [i for i in ids if i]

    def is_reachable(self) -> bool:
        try:
            self.list_models()
            return True
        except LlamaServerError:
            return False

    def resolve_model(self) -> str:
        if self._resolved_model:
            return self._resolved_model
        available = self.list_models()
        if not available:
            raise LlamaServerError(f"llama-server at {self.base_url} reports no loaded models.")
        if self.model:
            if self.model not in available:
                if self.fallback_to_loaded:
                    self.model = available[0]
                else:
                    raise ModelNotFoundError(
                        f"Requested model '{self.model}' is not loaded at {self.base_url}. Available: {available}"
                    )
            self._resolved_model = self.model
        else:
            self._resolved_model = available[0]
        return self._resolved_model

    def chat(self, messages: list[dict], max_tokens: int = 900, temperature: float = 0.7,
             repeat_penalty: float | None = None, busy_retries: int = 6,
             presence_penalty: float | None = None, frequency_penalty: float | None = None) -> str:
        model = self.resolve_model()
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # llama.cpp's default repeat_penalty is 1.1, which some local models
        # ("experts"/reasoning quants especially) find too lax — they loop,
        # re-answering the same point several times in one reply. Pass an
        # explicit penalty where the caller wants loop suppression; None keeps
        # the server default (used by paths that must not change sampling,
        # like the memory refresh).
        if repeat_penalty is not None:
            payload["repeat_penalty"] = repeat_penalty
        # Presence/frequency penalties (OpenAI-compat, supported by llama-server)
        # fight the runaway-synonym cascade some reasoning quants fall into (a
        # chain of "enduringness perpetuity immortality..."): presence_penalty
        # discourages re-using any token already emitted, frequency_penalty
        # damps repeated tokens harder the more often they appear. Default None
        # keeps every existing caller's sampling untouched.
        if presence_penalty is not None:
            payload["presence_penalty"] = presence_penalty
        if frequency_penalty is not None:
            payload["frequency_penalty"] = frequency_penalty
        # llama-server is single-occupancy: a request that arrives while another
        # generation is in flight (e.g. the user chats while a long analysis is
        # grinding) gets a busy error instead of queueing. A bounded retry with
        # linear backoff smooths that overlap out — the losing request waits a
        # few seconds and goes again instead of failing the user's turn.
        _BUSY_STATUS = (400, 429, 503)
        _BUSY_BODY = re.compile(r"(busy|in progress|already running|another request)", re.IGNORECASE)
        attempt = 0
        while True:
            try:
                resp = requests.post(f"{self.base_url}/v1/chat/completions", json=payload, timeout=self.timeout, headers=self.extra_headers)
                status = getattr(resp, "status_code", 200)
                if status in _BUSY_STATUS and attempt < busy_retries:
                    # 400 is also used for genuinely bad requests, so only retry
                    # when the body actually sounds busy. 429/503 are busy by
                    # definition.
                    if status in (429, 503) or _BUSY_BODY.search(getattr(resp, "text", "") or ""):
                        attempt += 1
                        time.sleep(1.5 * attempt)
                        continue
                resp.raise_for_status()
                data = resp.json()
                break
            except requests.exceptions.ConnectionError as e:
                raise LlamaServerError(f"Could not connect to llama-server at {self.base_url}.") from e
            except requests.exceptions.Timeout as e:
                raise WatchdogTimeoutError(
                    f"The model didn't respond within {self.timeout}s. For a large local model "
                    f"(especially with CPU-offloaded MoE experts, quantized KV cache, or a large "
                    f"context window), a single reply can genuinely take a while — this isn't "
                    f"necessarily a problem, just slow. If this keeps happening, either wait it out "
                    f"or reduce how much context is being sent per turn."
                ) from e
            except requests.exceptions.HTTPError as e:
                raise LlamaServerError(f"llama-server request failed: {e}") from e
            except (ValueError, requests.exceptions.JSONDecodeError) as e:
                raise LlamaServerError(f"llama-server at {self.base_url} returned a non-JSON response: {e}") from e

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LlamaServerError(f"Unexpected response shape from llama-server: {data}") from e

    def chat_stream(self, messages: list[dict], on_token, max_tokens: int = 900, temperature: float = 0.7,
                    repeat_penalty: float | None = None) -> str:
        """Streaming variant of chat(): calls `on_token(piece)` for each text
        chunk as it arrives (SSE from llama-server's OpenAI-compat endpoint)
        and returns the FULL raw text once the stream completes.

        The streamed pieces are RAW model output — the caller's reply-hygiene
        pipeline still runs on the returned full text before anything is
        stored. Sampling matches chat() exactly; no busy-retry loop here (a
        stream that starts has committed — a busy server fails fast and the
        caller can retry the turn)."""
        model = self.resolve_model()
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if repeat_penalty is not None:
            payload["repeat_penalty"] = repeat_penalty
        try:
            resp = requests.post(f"{self.base_url}/v1/chat/completions", json=payload,
                                 timeout=self.timeout, headers=self.extra_headers, stream=True)
            if resp.status_code in (429, 503):
                raise LlamaServerError("llama-server is busy with another request. Try again in a moment.")
            resp.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise LlamaServerError(f"Could not connect to llama-server at {self.base_url}.") from e
        except requests.exceptions.Timeout as e:
            raise WatchdogTimeoutError(
                f"The model didn't respond within {self.timeout}s. This isn't necessarily a "
                f"problem, just slow — retry the turn."
            ) from e
        except requests.exceptions.HTTPError as e:
            raise LlamaServerError(f"llama-server request failed: {e}") from e

        parts: list[str] = []
        try:
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    break
                try:
                    obj = json.loads(data_str)
                except ValueError:
                    continue  # keep-alive comment or partial frame — skip
                choices = obj.get("choices") or [{}]
                delta = choices[0].get("delta") or {}
                piece = delta.get("content")
                if piece:
                    parts.append(piece)
                    on_token(piece)
        finally:
            resp.close()
        return "".join(parts)
