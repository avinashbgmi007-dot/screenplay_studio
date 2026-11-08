"""Conservative HTTP transport for model and local-STT payloads.

Requests follows redirects and reads proxy environment variables by default.
Both are hidden routing decisions for sensitive screenplay/audio requests. Callers
use this helper so requests go directly to the configured endpoint and any 3xx
is surfaced before a second request can carry the body or credentials elsewhere.
"""
from __future__ import annotations

import requests


class RedirectRefusedError(requests.exceptions.RequestException):
    """A configured inference endpoint tried to redirect a payload request."""


# Passing explicit None entries prevents requests.Session.merge_environment_settings
# from importing HTTP_PROXY / HTTPS_PROXY / ALL_PROXY into this request. This
# code intentionally has no ambient-proxy mode; a proxy is a separate, explicit
# routing/consent feature, not an environment side effect.
_NO_ENV_PROXIES = {"http": None, "https": None, "all": None}


def request_no_redirects(method: str, url: str, **kwargs):
    """Issue one direct HTTP request; never follow a Location header or env proxy.

    Redirects are rejected for all methods, not just POST: a 307/308 preserves a
    body, while 301/302/303 behavior varies by method/client. Requiring callers
    to configure the final endpoint makes that boundary deterministic.
    """
    kwargs["allow_redirects"] = False
    kwargs["proxies"] = dict(_NO_ENV_PROXIES)
    response = getattr(requests, method.lower())(url, **kwargs)
    status = int(getattr(response, "status_code", 200) or 200)
    if 300 <= status < 400:
        location = (getattr(response, "headers", {}) or {}).get("Location", "")
        try:
            response.close()
        except Exception:
            pass
        raise RedirectRefusedError(
            f"Refusing HTTP {status} redirect from {url}"
            + (f" to {location}" if location else "")
            + "; configure the final inference endpoint URL directly."
        )
    return response
