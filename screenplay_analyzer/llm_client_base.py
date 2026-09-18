"""
Shared base for LLM clients (analyzer and cowriter). Handles model
discovery, resolution, and busy-retry against a local llama-server.

Each consumer subclasses BaseLlamaClient and adds its own chat method:
- AnalyzerClient adds chat_json() (grammar-constrained JSON)
- CowriterClient adds chat() and chat_stream() (free text + SSE)
"""

from __future__ import annotations

import re
import threading
import time

import requests

# The context window a server reports changes only when the server restarts, and
# a client is constructed per web request — so the probe result is cached by
# base_url rather than per client. None is cached too: a build without /props
# must not be re-probed on every turn.
_CONTEXT_WINDOW_CACHE: dict[str, int | None] = {}
_CONTEXT_WINDOW_LOCK = threading.Lock()


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

    def context_window(self) -> int | None:
        """The context window this server reports, in TOKENS — or None.

        Exists so a caller can size its own prompt against the model it is
        actually talking to instead of guessing a constant. The co-writer uses
        it for its prompt budget: a model reporting a small window gets a small
        budget (and the prompt sheds garnish rather than being silently
        truncated), while a model with room is left alone.

        Best-effort by design. `/props` is a llama.cpp endpoint that some builds
        don't expose, and a capability probe must never fail a chat turn — so
        every failure path returns None and the caller falls back to a constant.
        """
        key = self.base_url
        with _CONTEXT_WINDOW_LOCK:
            if key in _CONTEXT_WINDOW_CACHE:
                return _CONTEXT_WINDOW_CACHE[key]
        n_ctx = self._probe_context_window()
        with _CONTEXT_WINDOW_LOCK:
            _CONTEXT_WINDOW_CACHE[key] = n_ctx
        return n_ctx

    def _probe_context_window(self) -> int | None:
        """One GET /props, read for the per-slot context size.

        llama.cpp reports it under `default_generation_settings.n_ctx` (already
        divided across `total_slots`, so it is the window this client actually
        gets); the bare top-level `n_ctx` is accepted as a fallback for builds
        that report it differently.
        """
        try:
            resp = requests.get(f"{self.base_url}/props", timeout=3, headers=self.extra_headers)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        gen = data.get("default_generation_settings")
        gen = gen if isinstance(gen, dict) else {}
        params = gen.get("params")
        params = params if isinstance(params, dict) else {}
        for candidate in (gen.get("n_ctx"), data.get("n_ctx"), params.get("n_ctx")):
            try:
                value = int(candidate)
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value
        return None

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
