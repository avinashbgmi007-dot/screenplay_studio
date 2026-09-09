"""
Shared base for LLM clients (analyzer and cowriter). Handles model
discovery, resolution, and busy-retry against a local llama-server.

Each consumer subclasses BaseLlamaClient and adds its own chat method:
- AnalyzerClient adds chat_json() (grammar-constrained JSON)
- CowriterClient adds chat() and chat_stream() (free text + SSE)
"""

from __future__ import annotations

import re
import time

import requests


class LlamaServerError(Exception):
    pass


class ModelNotFoundError(LlamaServerError):
    pass


class BaseLlamaClient:
    def __init__(self, base_url: str, model: str | None = None, timeout: int = 600,
                 extra_headers: dict | None = None, fallback_to_loaded: bool = False):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
        self.fallback_to_loaded = fallback_to_loaded
        self._resolved_model: str | None = None
        self._available_ids: list[str] | None = None

    def list_models(self) -> list:
        """Override in subclass: return model ids in the expected format.
        Analyzer returns raw dicts; cowriter returns string ids."""
        return self.list_models_raw()

    def list_models_raw(self) -> list[dict]:
        """Raw /v1/models response dicts."""
        try:
            resp = requests.get(f"{self.base_url}/v1/models", timeout=15, headers=self.extra_headers)
            resp.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise LlamaServerError(
                f"Could not connect to llama-server at {self.base_url}. "
                f"Is it running? (launch with `llama-server -m <model.gguf> --port ...`)"
            ) from e
        except requests.exceptions.Timeout as e:
            raise LlamaServerError(f"Timed out connecting to {self.base_url}") from e
        except requests.exceptions.HTTPError as e:
            raise LlamaServerError(f"llama-server at {self.base_url} returned an error: {e}") from e
        data = resp.json()
        return data.get("data", []) or data.get("models", [])

    def _available(self) -> list[str]:
        """Loaded model ids, cached per client."""
        if self._available_ids is None:
            available = self.list_models()
            ids = [m.get("id") or m.get("name") for m in available]
            self._available_ids = [a for a in ids if a]
        return self._available_ids

    def resolve_model_id(self, model_id: str | None) -> str:
        """Resolve a specific model id against what's loaded, applying the
        fallback policy. Never mutates self.model."""
        available_ids = self._available()
        if not available_ids:
            raise LlamaServerError(f"llama-server at {self.base_url} reports no loaded models.")
        if model_id:
            if model_id in available_ids:
                return model_id
            if self.fallback_to_loaded:
                return available_ids[0]
            raise ModelNotFoundError(
                f"Requested model '{model_id}' is not loaded at {self.base_url}. "
                f"Available: {available_ids}"
            )
        return available_ids[0]

    def resolve_model(self) -> str:
        if not self._resolved_model:
            self._resolved_model = self.resolve_model_id(self.model)
        return self._resolved_model

    def is_reachable(self) -> bool:
        try:
            self.list_models()
            return True
        except LlamaServerError:
            return False

    def _check_busy(self, status: int, body: str) -> bool:
        """True if the response indicates the server is busy."""
        if status in (429, 503):
            return True
        if status == 400:
            return bool(re.search(r"(busy|in progress|already running|another request)", body or "", re.IGNORECASE))
        return False

    def _post_chat(self, payload: dict, busy_retries: int = 6) -> dict:
        """POST to /v1/chat/completions with busy-retry. Returns the parsed JSON data."""
        attempt = 0
        while True:
            try:
                resp = requests.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload, timeout=self.timeout, headers=self.extra_headers,
                )
                status = getattr(resp, "status_code", 200)
                if self._check_busy(status, getattr(resp, "text", "") or "") and attempt < busy_retries:
                    attempt += 1
                    time.sleep(1.5 * attempt)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.ConnectionError as e:
                raise LlamaServerError(f"Could not connect to llama-server at {self.base_url}.") from e
            except requests.exceptions.Timeout as e:
                raise LlamaServerError(
                    f"Request to {self.base_url} timed out after {self.timeout}s. "
                    f"For a large/slow local model, consider raising the client timeout."
                ) from e
            except requests.exceptions.HTTPError as e:
                raise LlamaServerError(f"llama-server request failed: {e}") from e
            except (ValueError, requests.exceptions.JSONDecodeError) as e:
                raise LlamaServerError(f"llama-server at {self.base_url} returned a non-JSON response: {e}") from e
