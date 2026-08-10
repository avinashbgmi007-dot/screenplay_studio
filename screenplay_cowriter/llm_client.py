"""
Client for llama-server chat completions. Unlike Piece 2's client, this
doesn't need grammar-constrained JSON output — co-writer replies are free
text. Kept as its own small module (not imported from Piece 2) so Piece 3
works standalone without Piece 2 installed, per the composability goal.
"""

from __future__ import annotations

import requests


class LlamaServerError(Exception):
    pass


class ModelNotFoundError(LlamaServerError):
    pass


class LlamaServerClient:
    def __init__(self, base_url: str, model: str | None = None, timeout: int = 600, extra_headers: dict | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
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
                raise ModelNotFoundError(
                    f"Requested model '{self.model}' is not loaded at {self.base_url}. Available: {available}"
                )
            self._resolved_model = self.model
        else:
            self._resolved_model = available[0]
        return self._resolved_model

    def chat(self, messages: list[dict], max_tokens: int = 900, temperature: float = 0.7) -> str:
        model = self.resolve_model()
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            resp = requests.post(f"{self.base_url}/v1/chat/completions", json=payload, timeout=self.timeout, headers=self.extra_headers)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError as e:
            raise LlamaServerError(f"Could not connect to llama-server at {self.base_url}.") from e
        except requests.exceptions.Timeout as e:
            raise LlamaServerError(
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
