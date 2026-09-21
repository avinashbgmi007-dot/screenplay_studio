"""One canonical answer to "is this URL on this machine?"

Two separate features must refuse to talk to a remote host: the dictation
engine (``stt.py``) and the model server (``webapp_server.py``). Both used to
answer that question with their own string check, and the original answer was
wrong in the same way twice — a prefix match on the raw URL, which
``http://127.0.0.1@evil.com`` (the authority ends at the ``@``) and
``http://localhost.evil.com`` both satisfy while resolving to a remote host.

So the check lives here, once, and is parsed rather than pattern-matched.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

# Only the *name* needs listing: every literal loopback address (127.0.0.0/8
# and ::1) is decided by the ipaddress module, which knows the actual ranges.
_LOOPBACK_NAMES = frozenset({"localhost"})

# The schemes this desk will ever speak to a local service.
_ALLOWED_SCHEMES = frozenset({"http", "https"})


def is_loopback_host(host: str | None) -> bool:
    """True when `host` names this machine and nothing else.

    `localhost` is matched by name (it is defined by the host's own resolver);
    every address literal is matched by range, so `127.0.0.2` and `::1` are
    accepted while `127.0.0.1.evil.com` — which merely *starts* like an address
    — is not.
    """
    if not host:
        return False
    if host.lower() in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_loopback_url(url: str | None) -> bool:
    """True when `url` is an http(s) URL pointing at this machine."""
    parsed = urlparse(url or "")
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return False
    return is_loopback_host(parsed.hostname)
