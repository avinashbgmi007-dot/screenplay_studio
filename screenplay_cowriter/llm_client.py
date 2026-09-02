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

from screenplay_analyzer.llm_client_base import BaseLlamaClient, LlamaServerError, ModelNotFoundError


class WatchdogTimeoutError(LlamaServerError):
    """A chat turn exceeded the per-turn generation cap. Distinct from other
    LlamaServerErrors so the webapp can offer a "keep waiting?" retry instead
    of failing the turn — a slow local model is not the same failure as a
    dead server, and the writer shouldn't have to retype a long message."""
    pass


class LlamaServerClient(BaseLlamaClient):
    def __init__(self, base_url: str, model: str | None = None, timeout: int = 600, extra_headers: dict | None = None,
                 fallback_to_loaded: bool = False):
        super().__init__(base_url, model=model, timeout=timeout, extra_headers=extra_headers,
                         fallback_to_loaded=fallback_to_loaded)

    def list_models(self) -> list[str]:
        entries = self.list_models_raw()
        ids = [e.get("id") or e.get("name") for e in entries]
        return [i for i in ids if i]

    def _resolve_model_local(self) -> str:
        """Cowriter-specific resolve that mutates self.model on fallback (preserves legacy behavior)."""
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

    def resolve_model(self) -> str:
        return self._resolve_model_local()

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
        if repeat_penalty is not None:
            payload["repeat_penalty"] = repeat_penalty
        if presence_penalty is not None:
            payload["presence_penalty"] = presence_penalty
        if frequency_penalty is not None:
            payload["frequency_penalty"] = frequency_penalty

        attempt = 0
        while True:
            try:
                resp = requests.post(f"{self.base_url}/v1/chat/completions", json=payload, timeout=self.timeout, headers=self.extra_headers)
                status = getattr(resp, "status_code", 200)
                if self._check_busy(status, getattr(resp, "text", "") or "") and attempt < busy_retries:
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

        No busy-retry loop here (a stream that starts has committed — a busy
        server fails fast and the caller can retry the turn)."""
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

        # SSE has no charset by default; requests then decodes with ISO-8859-1,
        # turning every em dash into mojibake and Telugu into mush.
        # llama-server speaks UTF-8, always. Pin it.
        resp.encoding = "utf-8"

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
