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
import weakref

_LOCKS_GUARD = threading.Lock()
# Weak values (L1): a per-path lock is only worth keeping while somebody holds
# it. Any thread inside `with lock:` holds a strong reference for the duration,
# so an entry can never be collected under a waiter's feet; a path nobody is
# touching costs nothing. The previous plain dict kept a path string plus a lock
# for every file ever touched, for the life of the process.
_LOCKS: "weakref.WeakValueDictionary[str, threading.RLock]" = weakref.WeakValueDictionary()


def _lock_for(path: str) -> threading.RLock:
    # RLock (not Lock): stores hold this across a load-modify-write cycle and
    # atomic_write_json re-acquires it inside — reentrancy, same mutual
    # exclusion across threads.
    key = os.path.abspath(path)
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _LOCKS[key] = lock
        return lock


def lock_for(path: str) -> threading.RLock:
    """Public per-path lock for load-modify-write cycles: hold it across the
    load so a racing writer can't clobber fields the writer didn't see."""
    return _lock_for(path)


# A Windows sharing violation (another process has the file open) and a byte-range
# lock violation (an AV scanner or indexer holding a range) are both TRANSIENT:
# the holder lets go within milliseconds, so a bounded retry is the right answer.
# Decision (2026-09-20, user-approved): retry EVERY PermissionError, not only the
# winerror 32/33 set. The concurrent save/rename hammer surfaces
# PermissionError(13, "Access is denied") with NO winerror under full-suite
# antivirus/indexer pressure — a signature the winerror-only filter read as a
# genuine denial and (correctly) refused to retry, leaving the suite red. The
# accepted, documented risk: a GENUINE access denial (read-only disk, ACL block)
# is now also retried for the bounded window (~1s) before it raises — it still
# raises; it is just not fail-fast. That trade is intentional: a writer's store
# that transiently can't be reached must not lose the write; a truly denied write
# still errors loudly, just after the retry budget.
_TRANSIENT_WINERRORS = frozenset({32, 33})  # ERROR_SHARING_VIOLATION, ERROR_LOCK_VIOLATION


def _is_transient_lock_error(exc: PermissionError) -> bool:
    # Kept for the winerror path and for callers/tests that introspect the
    # transient set. retry_permission itself retries every PermissionError (see
    # the note above); this answers "is this the classic Windows sharing/lock
    # violation" for diagnostics.
    return getattr(exc, "winerror", None) in _TRANSIENT_WINERRORS


def retry_permission(fn, attempts: int = 6):
    """Run fn() with a bounded retry for transient PermissionErrors: a
    concurrent reader/writer (or AV/indexer) can briefly hold a file open —
    open/os.replace then raises PermissionError. The concurrent save/rename
    hammer shows 3 attempts can expire before the holder releases, so the
    default is wider and the sleep is jittered to de-synchronize competing
    writers. Per the 2026-09-20 decision, EVERY PermissionError is retried for
    the bounded window; the error always raises if it never clears (a genuine
    denial is delayed ~1s, not swallowed)."""
    import random
    for attempt in range(attempts):
        try:
            return fn()
        except PermissionError:
            if attempt == attempts - 1:
                raise
            # 50ms..600ms capped, equal-jittered so two writers do not collide
            # on the same cadence and re-contend on every retry.
            time.sleep(min(0.6, 0.05 * (attempt + 1)) * (0.5 + random.random() * 0.5))


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
    # Collisions between identical titles are resolved by the CALLER (the
    # project-create routes append a numeric suffix via suffixed_id below) —
    # nothing in here increments anything.
    return safe[:max_len]


def suffixed_id(base: str, suffix: int, max_len: int = 64) -> str:
    """`base` with a collision suffix that still satisfies the id contract.

    `safe_dir_name` may return exactly `max_len` characters and `check_safe_id`
    caps the whole name at 64, so appending "_2" to a 64-char base produced a
    66-char name that `check_safe_id` rejected — "create this title twice"
    became a 500 on the second create. Trim the base to make room.
    """
    if suffix <= 1:
        return base[:max_len]
    tail = f"_{suffix}"
    return base[: max_len - len(tail)] + tail
