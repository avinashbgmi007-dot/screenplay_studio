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

import requests


class LlamaServerError(Exception):
    pass


class ModelNotFoundError(LlamaServerError):
    pass


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
    left to generate a response — this is the single most common real-world
    cause of "successful" requests that come back with nothing in them,
    and previously produced a generic, undiagnosable error message.
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


class LlamaServerClient:
    def __init__(self, base_url: str, model: str | None = None, timeout: int = 600, extra_headers: dict | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
        self._resolved_model: str | None = None

    def list_models(self) -> list[dict]:
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

    def resolve_model(self) -> str:
        if self._resolved_model:
            return self._resolved_model

        available = self.list_models()
        available_ids = [m.get("id") or m.get("name") for m in available]
        available_ids = [a for a in available_ids if a]

        if not available_ids:
            raise LlamaServerError(f"llama-server at {self.base_url} reports no loaded models.")

        if self.model:
            if self.model not in available_ids:
                raise ModelNotFoundError(
                    f"Requested model '{self.model}' is not loaded at {self.base_url}. "
                    f"Available: {available_ids}"
                )
            self._resolved_model = self.model
        else:
            # no explicit model requested — llama-server serves one model per
            # instance, so take whatever's running
            self._resolved_model = available_ids[0]

        return self._resolved_model

    def chat_json(
        self,
        system: str,
        user: str,
        grammar: str | None = None,
        max_tokens: int = 1500,
        temperature: float = 0.3,
        retries: int = 2,
    ):
        """
        Sends a chat completion request and returns parsed JSON. Uses the
        llama.cpp `grammar` extension field (GBNF) when provided, on top of
        response_format json_object as a fallback signal for servers/paths
        that honor that instead.
        """
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
            # Reasoning models split output into a free-form `reasoning_content`
            # phase followed by `content`. Under a grammar, the constrained
            # generation gets routed into the reasoning block and `content`
            # comes back empty or as unconstrained prose — so the schema
            # constraint never reaches what this client parses. Disabling
            # thinking for grammar-constrained calls makes the constrained
            # JSON land in `content` where it belongs. (Harmless no-op on
            # non-reasoning templates.)
            payload.setdefault("chat_template_kwargs", {})
            payload["chat_template_kwargs"]["enable_thinking"] = False

        last_error = None
        for attempt in range(retries + 1):
            try:
                resp = requests.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    timeout=self.timeout,
                    headers=self.extra_headers,
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.Timeout as e:
                raise LlamaServerError(
                    f"Request to {self.base_url} timed out after {self.timeout}s. "
                    f"For a large/slow local model, consider raising the client timeout."
                ) from e
            except requests.exceptions.ConnectionError as e:
                raise LlamaServerError(
                    f"Could not connect to llama-server at {self.base_url}."
                ) from e
            except requests.exceptions.HTTPError as e:
                raise LlamaServerError(f"llama-server request failed: {e}") from e
            except (ValueError, json.JSONDecodeError) as e:
                last_error = f"llama-server's response body wasn't valid JSON: {e}"
                if attempt < retries:
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
            f"Model output could not be parsed as JSON after {retries + 1} attempts. "
            f"Last error: {last_error}"
        )
