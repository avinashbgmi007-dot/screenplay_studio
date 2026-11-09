"""
Shared base for LLM clients (analyzer and cowriter). Handles model
discovery, resolution, and busy-retry against a local llama-server.

Each consumer subclasses BaseLlamaClient and adds its own chat method:
- AnalyzerClient adds chat_json() (grammar-constrained JSON)
- CowriterClient adds chat() and chat_stream() (free text + SSE)
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

import hashlib
import inspect
import random
import re
import threading
import time

import requests

from .http_transport import RedirectRefusedError, request_no_redirects

# Clients are request-scoped, so a short process cache avoids paying the /props
# round trip on every chat turn. Entries are model/auth scoped and expire: a
# server can be restarted or a model replaced without changing its URL.
_CONTEXT_WINDOW_CACHE: dict[tuple[str, str, str], tuple[int | None, float]] = {}
_CONTEXT_WINDOW_LOCK = threading.Lock()
_CONTEXT_WINDOW_TTL_SECONDS = 60.0
_CONTEXT_WINDOW_MISS_TTL_SECONDS = 10.0
_CONTEXT_WINDOW_CACHE_MAXSIZE = 256

_CONTEXT_WINDOW_REJECTION = re.compile(
    r"(?:context.{0,80}(?:length|window|limit|size|exceed|overflow)|"
    r"(?:maximum|max|too many).{0,80}(?:tokens|context)|"
    r"(?:tokens|prompt).{0,80}(?:exceed|over limit|too long)|n_ctx)",
    re.IGNORECASE | re.DOTALL,
)


def _context_cache_now() -> float:
    """Clock seam for deterministic expiry tests."""
    return time.monotonic()


class LlamaServerError(Exception):
    pass


class ModelNotFoundError(LlamaServerError):
    pass


class DeadlineExceededError(LlamaServerError):
    """The logical model call's monotonic budget expired before more work."""


def _call_with_deadline(method, *args, deadline: float | None):
    """Pass a deadline to deadline-aware overrides without breaking older hooks."""
    if deadline is None:
        return method(*args)
    try:
        parameters = inspect.signature(method).parameters.values()
    except (TypeError, ValueError):
        return method(*args, deadline=deadline)
    accepts_deadline = any(
        parameter.name == "deadline" or parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )
    return method(*args, deadline=deadline) if accepts_deadline else method(*args)


def normalize_openai_base_url(base_url: str) -> str:
    """Canonicalize an OpenAI-compatible API root for clients that append `/v1`.

    The public configuration has historically accepted both an origin/path
    prefix and the same URL ending in `/v1`. Keep the prefix but remove that
    one exact terminal version segment so every endpoint builder gets exactly
    one `/v1`. Do not treat substrings such as `/v1ish` as a version segment.
    Query/fragment forms keep their legacy behavior; the endpoint clients do
    not yet provide a separate URL builder for those components.
    """
    value = str(base_url or "").strip().rstrip("/")
    # Query and fragment endpoint semantics are a separate compatibility
    # contract. Preserve them byte-for-byte rather than rewriting a path while
    # the current clients still concatenate endpoint paths as strings.
    if "?" in value or "#" in value:
        return value
    parts = urlsplit(value)
    path = parts.path.rstrip("/")
    if path == "/v1":
        path = ""
    elif path.endswith("/v1"):
        path = path[:-3]
    return urlunsplit((parts.scheme, parts.netloc, path, "", "")).rstrip("/")


def auth_headers(api_key: str | None) -> dict:
    """Bearer header for a token-protected endpoint; ``{}`` for a local server.

    A llama-server on this machine authenticates nothing; a remote
    OpenAI-compatible endpoint (a hosted API, a LAN box, a gateway) usually
    wants a bearer token. Both clients here thread `extra_headers` through every
    request they make — /v1/models, /props, /v1/chat/completions — so this is the
    whole plumbing.

    It lives in the shared base rather than in either consumer for the same
    reason ``net_guard.py`` exists in the studio: two independent constructions
    of one wire format drift, and they drift *silently*, because a malformed
    auth header is indistinguishable from a wrong token.

    An empty/whitespace/absent token yields NO header rather than
    ``Authorization: Bearer `` — some gateways reject a malformed credential
    outright, which would turn "the writer cleared the token" into "every call
    401s" on a server that never needed one.
    """
    key = (api_key or "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}


def busy_retry_delay(attempt: int, base: float = 1.5) -> float:
    """Equal jitter for the busy-retry backoff (L3).

    llama-server is single-occupancy, so several clients that all saw the same
    "busy" used to sleep exactly 1.5s, 3.0s, 4.5s... and retry in lockstep: the
    backoff grew, but it separated nobody, and the herd collided again on every
    round. Half the wait stays fixed (so the backoff still grows), half is
    random (so the herd spreads across the window). One implementation, shared
    by both clients — the analyzer's and the co-writer's chat path.
    """
    half = base * attempt / 2
    return half + random.uniform(0, half)


class BaseLlamaClient:
    def __init__(self, base_url: str, model: str | None = None, timeout: int = 600,
                 extra_headers: dict | None = None, fallback_to_loaded: bool = False):
        self.base_url = normalize_openai_base_url(base_url)
        self.model = model
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
        self.fallback_to_loaded = fallback_to_loaded
        self._resolved_model: str | None = None
        self._available_ids: list[str] | None = None

    def list_models(self, deadline: float | None = None) -> list:
        """Override in subclass: return model ids in the expected format.
        Analyzer returns raw dicts; cowriter returns string ids."""
        return _call_with_deadline(self.list_models_raw, deadline=deadline)

    def list_models_raw(self, deadline: float | None = None) -> list[dict]:
        """Raw /v1/models response dicts; optionally budget discovery too."""
        timeout = 15.0
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DeadlineExceededError("The logical call deadline expired before model discovery.")
            timeout = min(timeout, remaining)
        try:
            resp = request_no_redirects("get", f"{self.base_url}/v1/models",
                                        timeout=timeout, headers=self.extra_headers)
            if deadline is not None and time.monotonic() >= deadline:
                raise DeadlineExceededError(
                    "The logical call deadline expired during model discovery.")
            resp.raise_for_status()
        except RedirectRefusedError as e:
            raise LlamaServerError(str(e)) from e
        except requests.exceptions.ConnectionError as e:
            raise LlamaServerError(
                f"Could not connect to llama-server at {self.base_url}. "
                f"Is it running? (launch with `llama-server -m <model.gguf> --port ...`)"
            ) from e
        except requests.exceptions.Timeout as e:
            if deadline is not None and time.monotonic() >= deadline:
                raise DeadlineExceededError(
                    "The logical call deadline expired while discovering the loaded model.") from e
            raise LlamaServerError(f"Timed out connecting to {self.base_url}") from e
        except requests.exceptions.HTTPError as e:
            raise LlamaServerError(f"llama-server at {self.base_url} returned an error: {e}") from e
        data = resp.json()
        return data.get("data", []) or data.get("models", [])

    def _available(self, deadline: float | None = None) -> list[str]:
        """Loaded model ids, cached per client; discovery can share a deadline."""
        if self._available_ids is None:
            # Preserve third-party/subclass overrides that predate deadline-aware
            # discovery while passing the budget wherever the hook supports it.
            available = _call_with_deadline(self.list_models, deadline=deadline)
            ids = [m.get("id") or m.get("name") for m in available]
            self._available_ids = [a for a in ids if a]
        return self._available_ids

    def resolve_model_id(self, model_id: str | None, deadline: float | None = None) -> str:
        """Resolve a model id against loaded models under the optional deadline.

        Never mutates self.model.
        """
        available_ids = self._available(deadline=deadline)
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

    def resolve_model(self, deadline: float | None = None) -> str:
        if not self._resolved_model:
            self._resolved_model = _call_with_deadline(
                self.resolve_model_id, self.model, deadline=deadline)
        return self._resolved_model

    def is_reachable(self) -> bool:
        try:
            self.list_models()
            return True
        except LlamaServerError:
            return False

    def _context_window_cache_key(self) -> tuple[str, str, str]:
        """Partition capabilities without retaining credential values in keys."""
        headers = tuple(sorted((str(key).lower(), str(value))
                               for key, value in self.extra_headers.items()))
        header_digest = hashlib.sha256(repr(headers).encode("utf-8")).hexdigest() if headers else ""
        return self.base_url, self.model or "", header_digest

    def invalidate_context_window(self) -> None:
        """Forget this endpoint/auth context after a server rejection.

        A model may have been resolved from a fallback after its initial probe,
        so clear every model entry for this endpoint and header identity. A
        redundant probe is safer than leaving another model alias stale.
        """
        key = self._context_window_cache_key()
        with _CONTEXT_WINDOW_LOCK:
            for cached_key in list(_CONTEXT_WINDOW_CACHE):
                if cached_key[0] == key[0] and cached_key[2] == key[2]:
                    _CONTEXT_WINDOW_CACHE.pop(cached_key, None)

    def _invalidate_context_window_on_rejection(self, response) -> bool:
        """Drop a stale estimate when the server explicitly rejects context size."""
        status = getattr(response, "status_code", 200)
        rejected = (status == 413 or (status == 400 and _CONTEXT_WINDOW_REJECTION.search(
            getattr(response, "text", "") or "")))
        if rejected:
            self.invalidate_context_window()
        return bool(rejected)

    def context_window(self) -> int | None:
        """The context window this server reports, in TOKENS — or None.

        Results are scoped to endpoint, selected model and a one-way digest of
        request headers. Positive results expire after 60 seconds; unavailable
        or unsupported probes expire after 10 seconds. This preserves reuse
        across ordinary turns while bounding stale data after a restart or model
        swap at the same URL. A recognized context-length rejection also clears
        the entry so the next turn probes immediately.

        Best-effort by design. `/props` is a llama.cpp endpoint that some builds
        don't expose, and a capability probe must never fail a chat turn — so
        every failure path returns None and the caller falls back to a constant.
        """
        key = self._context_window_cache_key()
        now = _context_cache_now()
        with _CONTEXT_WINDOW_LOCK:
            cached = _CONTEXT_WINDOW_CACHE.get(key)
            if cached is not None:
                value, expires_at = cached
                if expires_at > now:
                    return value
                _CONTEXT_WINDOW_CACHE.pop(key, None)

        n_ctx = self._probe_context_window()
        now = _context_cache_now()
        ttl = _CONTEXT_WINDOW_TTL_SECONDS if n_ctx is not None else _CONTEXT_WINDOW_MISS_TTL_SECONDS
        with _CONTEXT_WINDOW_LOCK:
            # Expiry is also the natural cleanup path for endpoints no longer in
            # use. Bound memory if a process talks to many models/tenants.
            for stale_key, (_value, expiry) in list(_CONTEXT_WINDOW_CACHE.items()):
                if expiry <= now:
                    _CONTEXT_WINDOW_CACHE.pop(stale_key, None)
            if len(_CONTEXT_WINDOW_CACHE) >= _CONTEXT_WINDOW_CACHE_MAXSIZE:
                _CONTEXT_WINDOW_CACHE.pop(next(iter(_CONTEXT_WINDOW_CACHE)))
            _CONTEXT_WINDOW_CACHE[key] = (n_ctx, now + ttl)
        return n_ctx

    def _probe_context_window(self) -> int | None:
        """One GET /props, read for the per-slot context size.

        llama.cpp reports it under `default_generation_settings.n_ctx` (already
        divided across `total_slots`, so it is the window this client actually
        gets); the bare top-level `n_ctx` is accepted as a fallback for builds
        that report it differently.
        """
        try:
            resp = request_no_redirects("get", f"{self.base_url}/props",
                                        timeout=3, headers=self.extra_headers)
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

    def _post_chat(self, payload: dict, busy_retries: int = 6, timeout: float | None = None,
                   deadline: float | None = None, on_attempt=None) -> dict:
        """POST to chat completions with bounded busy retries.

        `timeout` overrides self.timeout for this request. When supplied, the
        absolute monotonic `deadline` also bounds retry scheduling and each
        attempt's timeout slice. It cannot cancel work already accepted by a
        provider, and Requests' timeout is not a hard total-duration guarantee.
        """
        eff_timeout = self.timeout if timeout is None else timeout
        attempt = 0
        while True:
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise DeadlineExceededError("The logical call deadline expired before the next chat attempt.")
                eff_timeout = min(eff_timeout, remaining)
            try:
                if on_attempt is not None:
                    on_attempt()
                resp = request_no_redirects(
                    "post", f"{self.base_url}/v1/chat/completions",
                    json=payload, timeout=eff_timeout, headers=self.extra_headers,
                )
                if deadline is not None and time.monotonic() >= deadline:
                    raise DeadlineExceededError("The logical call deadline expired during a chat attempt.")
                status = getattr(resp, "status_code", 200)
                if self._check_busy(status, getattr(resp, "text", "") or "") and attempt < busy_retries:
                    attempt += 1
                    delay = busy_retry_delay(attempt)
                    if deadline is not None:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise DeadlineExceededError("The logical call deadline expired after a busy response.")
                        delay = min(delay, remaining)
                    time.sleep(delay)
                    if deadline is not None and time.monotonic() >= deadline:
                        raise DeadlineExceededError("The logical call deadline expired during busy backoff.")
                    continue
                if self._invalidate_context_window_on_rejection(resp):
                    raise LlamaServerError(
                        "llama-server rejected the request as too large. The cached context estimate "
                        "was cleared; retry to rebuild the prompt, and reduce it if the error repeats."
                    )
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.ConnectionError as e:
                raise LlamaServerError(f"Could not connect to llama-server at {self.base_url}.") from e
            except requests.exceptions.Timeout as e:
                if deadline is not None and time.monotonic() >= deadline:
                    raise DeadlineExceededError(
                        "The logical call deadline expired during a chat attempt.") from e
                raise LlamaServerError(
                    f"Request to {self.base_url} timed out after {eff_timeout}s. "
                    f"For a large/slow local model, consider raising the client timeout."
                ) from e
            except requests.exceptions.HTTPError as e:
                raise LlamaServerError(f"llama-server request failed: {e}") from e
            except requests.exceptions.RequestException as e:
                raise LlamaServerError(f"llama-server transport refused the request: {e}") from e
            except (ValueError, requests.exceptions.JSONDecodeError) as e:
                raise LlamaServerError(f"llama-server at {self.base_url} returned a non-JSON response: {e}") from e
