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
import socket
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
    # A trailing dot is the DNS root label: `localhost.` and `127.0.0.1.` name the
    # same hosts as their undotted forms. Stripping dots can only ever REMOVE
    # characters, so it cannot turn a remote name into a loopback one
    # (`evil.com.` -> `evil.com` -> still refused). This also fixes the same false
    # rejection one layer over: `is_loopback_url("http://127.0.0.1.:8080")` used to
    # be refused, because `urlparse` hands back the dotted hostname. The Host guard
    # strips dots itself as well; that is now belt-and-braces rather than the only
    # place it happens.
    host = host.rstrip(".")
    if not host:
        return False
    if host.lower() in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        pass
    # BE-5 (round-3 audit 2026-09-25): `ipaddress` accepts only the canonical
    # textual forms, so the `inet_aton` spellings of loopback — `127.1`,
    # `2130706433`, `0x7f000001`, `0177.0.0.1` — were all REFUSED. They are
    # legitimate ways to write 127.0.0.1, and refusing one is a false rejection
    # with no workaround on an app whose whole promise is that it is local.
    #
    # `inet_aton` parses those forms into the same four bytes, so the range check
    # is unchanged and this cannot accept a remote host: a name raises OSError,
    # and a non-127 address fails `is_loopback` exactly as it does above
    # (`3232235777` is 192.168.1.1 and stays refused).
    #
    # No browser sends these in a Host header, which is why this is a
    # completeness fix rather than a defect — but the guard's job is to answer
    # "is this loopback?" correctly, and it now does so for every spelling.
    try:
        packed = socket.inet_aton(host)
    except OSError:
        return False
    return ipaddress.ip_address(packed).is_loopback


def is_loopback_url(url: str | None) -> bool:
    """True when `url` is an http(s) URL pointing at this machine."""
    parsed = urlparse(url or "")
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return False
    return is_loopback_host(parsed.hostname)
