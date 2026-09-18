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
import time

_LOCKS_GUARD = threading.Lock()
_LOCKS: dict[str, threading.RLock] = {}


def _lock_for(path: str) -> threading.RLock:
    # RLock (not Lock): stores hold this across a load-modify-write cycle and
    # atomic_write_json re-acquires it inside — reentrancy, same mutual
    # exclusion across threads.
    key = os.path.abspath(path)
    with _LOCKS_GUARD:
        if key not in _LOCKS:
            _LOCKS[key] = threading.RLock()
        return _LOCKS[key]


def lock_for(path: str) -> threading.RLock:
    """Public per-path lock for load-modify-write cycles: hold it across the
    load so a racing writer can't clobber fields the writer didn't see."""
    return _lock_for(path)


def retry_permission(fn, attempts: int = 3):
    """Run fn() with a short bounded retry for Windows sharing violations:
    a concurrent reader/writer (or AV/indexer) can briefly hold a file open —
    open/os.replace then raises PermissionError([WinError 32]). A real
    failure (attempts misses) still raises."""
    for attempt in range(attempts):
        try:
            return fn()
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.05 * (attempt + 1))


def atomic_write_json(path: str, data) -> None:
    """Serialize `data` as JSON to `path` atomically (tmp + os.replace)."""
    lock = _lock_for(path)
    with lock:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        retry_permission(lambda: os.replace(tmp, path))


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


def safe_dir_name(title: str, max_len: int = 64) -> str:
    """Fold a human-readable title into a filesystem-safe ASCII directory name,
    keeping the display title (in the manifest) untouched. H2: `str.isalnum` is
    Unicode-aware so a Telugu/Hindi title survived the per-char sanitizer into
    check_safe_id, which is ASCII-only and 400'd it. Here we NFKD-strip diacritics
    and keep only ASCII alnum/-/_; if nothing ASCII survives (pure Telugu/Hindi),
    fall back to a short stable hash so the dir is still safe and unique-ish.
    """
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", title or "")
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in ascii_only)
    safe = safe.strip("_")
    if not safe:
        import hashlib
        safe = hashlib.sha1((title or "untitled").encode("utf-8")).hexdigest()[:8]
    # suffix auto-increment handles collisions for identical titles
    return safe[:max_len]
