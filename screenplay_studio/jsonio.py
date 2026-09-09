"""Atomic JSON persistence for the studio's file-backed stores.

Every store that the webapp writes (manifests, ideas, notes, stash, beat
board) must go through `atomic_write_json`: a crash mid-write then leaves a
`.tmp` behind instead of a torn JSON file, and a concurrent reader either sees
the old bytes or the new ones — never a half-written document. Writes to the
same path are serialized by a per-path lock (the same pattern the cowriter's
SessionStore uses), so threaded request handling can't interleave
load-modify-write cycles on one document.
"""

from __future__ import annotations

import json
import os
import threading

_LOCKS_GUARD = threading.Lock()
_LOCKS: dict[str, threading.Lock] = {}


def _lock_for(path: str) -> threading.Lock:
    key = os.path.abspath(path)
    with _LOCKS_GUARD:
        if key not in _LOCKS:
            _LOCKS[key] = threading.Lock()
        return _LOCKS[key]


def atomic_write_json(path: str, data) -> None:
    """Serialize `data` as JSON to `path` atomically (tmp + os.replace)."""
    lock = _lock_for(path)
    with lock:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


# IDs come from URL path segments; anything outside this charset is a probe,
# not a project. One shared contract for projects and ideas alike.
import re  # noqa: E402

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def check_safe_id(value: str, kind: str = "id") -> str:
    """Raise ValueError unless `value` is a plain filesystem-safe id.

    Blocks path traversal ('..', 'a/../b') at every store chokepoint so no
    route can escape its data directory, even before Flask routing would.
    """
    if not value or not SAFE_ID_RE.match(value):
        raise ValueError(f"invalid {kind}: {value!r}")
    return value
