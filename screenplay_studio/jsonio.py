"""Atomic JSON persistence for the studio's file-backed stores.

Every store that the webapp writes (manifests, ideas, notes, stash, beat
board) must go through `atomic_write_json`: a crash mid-write then leaves a
`.tmp` behind instead of a torn JSON file, and a concurrent reader either sees
the old bytes or the new ones — never a half-written document.

Two writers can race on one store, and they need different locks:

* **Threads in one process** (threaded Flask request handling) — an RLock.
* **Separate processes** — the CLI and the webapp both write the same project
  directory, which AGENTS.md documents as a supported configuration. Nothing
  in-process can serialize those, so the write also takes an OS byte-range
  lock on a `<store>.lock` sidecar.

`lock_for` hands out ONE object carrying both layers, so a store can hold it
across a load-modify-write cycle while `atomic_write_json` re-enters it. Lock
files are created on demand and never deleted: removing one would let a
newcomer lock a fresh inode while an existing holder still owns the old one.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
import time
import uuid
import weakref

_LOCKS_GUARD = threading.Lock()
# Weak values (L1): a per-path lock is only worth keeping while somebody holds
# it. Any thread inside `with lock:` holds a strong reference for the duration,
# so an entry can never be collected under a waiter's feet; a path nobody is
# touching costs nothing. The previous plain dict kept a path string plus a lock
# for every file ever touched, for the life of the process.
_LOCKS = weakref.WeakValueDictionary()  # abspath -> _StoreLock

# How long to wait for ANOTHER process to release a store before giving up. A
# holder only ever holds it for the length of one write or one
# load-modify-write cycle, so this is generous; the point of the bound is that
# a holder killed mid-write can never hang the app forever. Both platforms
# release the lock when the holding process dies, so this should never fire.
LOCK_TIMEOUT_SECONDS = 10.0

# Poll interval while waiting. Short: contention here lasts milliseconds and
# the wait happens inside a request.
_LOCK_POLL_SECONDS = 0.01


class StoreLockTimeout(RuntimeError):
    """Another process held a store lock for longer than LOCK_TIMEOUT_SECONDS."""

    def __init__(self, path: str, timeout: float):
        self.path = path
        self.timeout = timeout
        secs = f"{timeout:.1f}".rstrip("0").rstrip(".")
        super().__init__(
            f"timed out after {secs}s waiting for another process to "
            f"release {os.path.basename(path)}")


# ---------------------------------------------------------------------------
# Composing lock budgets (BE-3 amplifier, round-4 audit 2026-09-25)
# ---------------------------------------------------------------------------
# LOCK_TIMEOUT_SECONDS bounds ONE acquisition. A cycle that takes the anchor
# lock and then leaf locks therefore gets the SUM of those budgets, and it holds
# the cycle lock for all of it — so one stuck file could keep every other
# request waiting past its own budget and have them all told the studio is
# broken. `reset_working` is the worst case: three leaves, so ~3x.
#
# `lock_deadline()` puts ONE deadline over a block, so nested acquisitions share
# it instead of each starting a fresh one.
#
# Deliberately opt-in and additive: nothing changes unless a caller wraps a
# block. `_StoreLock`'s own enter/exit bookkeeping — the thing standing between
# the writer and a lost edit — is deliberately NOT touched to make this
# automatic; a per-thread hold counter there would be more elegant and much
# riskier, and the amplifier is a latency problem in a case the audit measured
# as unreachable by load (it needs a ~50MB working copy, or a genuinely stuck
# process).
_deadline_local = threading.local()


@contextlib.contextmanager
def lock_deadline(seconds: float | None = None):
    """Cap the TOTAL wait of every lock acquired inside this block.

    `seconds=None` uses LOCK_TIMEOUT_SECONDS. Nested blocks take the tighter of
    the two, so an inner block can only ever shorten the budget — never extend
    an outer one.
    """
    if seconds is None:
        seconds = LOCK_TIMEOUT_SECONDS
    stack = getattr(_deadline_local, "stack", None)
    if stack is None:
        stack = _deadline_local.stack = []
    stack.append(time.monotonic() + seconds)
    try:
        yield
    finally:
        stack.pop()


def _lock_file_path(path: str) -> str:
    """Sidecar path holding a store's cross-process lock.

    Named `<store>.lock`, so the `*.json` globs that enumerate sessions and
    stores never see it. It is deliberately NOT a `.tmp`: those are per-write
    and cleaned up, whereas the lock file has to outlive every writer — deleting
    it would let two processes lock two different inodes and both believe they
    hold the store.
    """
    return path + ".lock"


def _acquire_os_lock(fd: int, path: str, timeout: float | None = None) -> None:
    """Take the exclusive byte-range lock on `fd`, waiting up to `timeout`.

    `timeout` defaults to LOCK_TIMEOUT_SECONDS, read at CALL time so the bound
    stays patchable (a default argument would freeze it at import).

    Non-blocking attempts in a loop rather than one blocking call: a blocking
    Windows lock carries its own hidden 10s budget and then raises, which is
    harder to reason about than our own deadline — and this keeps both
    platforms on one code path.
    """
    if timeout is None:
        timeout = LOCK_TIMEOUT_SECONDS
    started = time.monotonic()
    deadline = started + timeout
    # A surrounding `lock_deadline()` block wins when it is tighter. That is how
    # a cycle's leaf acquisitions share ONE budget instead of one each.
    stack = getattr(_deadline_local, "stack", None)
    if stack:
        deadline = min(deadline, stack[-1])
    while True:
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError:
            if time.monotonic() >= deadline:
                # Report the budget that ACTUALLY expired. `timeout` is the
                # per-acquisition default (10s); inside a `lock_deadline(0.4)`
                # block the wait ended at 0.4s, and a message that says "after
                # 10s" is wrong in the one place the writer reads to find out
                # how long the studio was busy.
                raise StoreLockTimeout(path, deadline - started) from None
            time.sleep(_LOCK_POLL_SECONDS)


def _release_os_lock(fd: int) -> None:
    """Unlock and close. Closing alone releases on both platforms; the explicit
    unlock is best-effort."""
    if fd < 0:
        return
    try:
        if os.name == "nt":
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


class RunLock:
    """One exclusive, cross-process claim on a project's analysis run.

    Gap 7 / gap 65. The webapp's `_analyze_lock` is a `threading.Lock`: it
    serialises two browser tabs and nothing else. A CLI `analyze` and the web UI
    on the same project each take their own private lock, both believe they are
    the only run, and both publish. Measured with two real OS processes: both
    entered the run.

    This is the same mechanism every store already uses — an advisory lock on a
    sidecar file — narrowed to one purpose: *whoever holds it is the only run for
    this project, in any process.* Deliberately NOT a `_StoreLock`: that type is
    reentrant, which is right for a store held across a read-modify-write and
    wrong here, because a second acquisition by the same process must be a
    refusal rather than a deeper nest.

    **It cannot go stale.** `flock`/`msvcrt` locks are released by the kernel
    when the holding descriptor closes, including when the process dies, so a
    crashed run leaves nothing to clean up and nothing to time out. That is why
    this is a lock and not a PID file: a PID file needs a liveness rule, and
    every liveness rule is wrong after a reboot or a PID reuse.

    Lock order: a run lock is the OUTERMOST lock a process takes, exactly like
    the analyze lock it complements. Nothing acquired under it reaches back for
    it, and it is never taken while a store lock is held.
    """

    def __init__(self, project_dir: str):
        # The DIRECTORY is what the existence check needs; `path` is only the
        # stem the sidecar is named after. Keeping both explicit is what stops
        # `isdir` being asked about a path that is never a directory.
        self.project_dir = os.path.abspath(project_dir)
        self.path = self.project_dir
        self._fd = -1

    def _lock_path(self) -> str:
        return os.path.join(self.project_dir, "analyze.run.lock")

    def try_acquire(self) -> bool:
        """True when this process now holds the run. Never waits, never raises.

        A project directory that does not exist yet cannot host a lock file, and
        there is also no run to collide with — so this reports the lock as taken
        and `held()` stays False. Reporting False instead would tell a caller
        "another analysis is running" about a directory nothing has created.
        """
        if not os.path.isdir(self.project_dir):
            return True
        try:
            fd = os.open(self._lock_path(), os.O_CREAT | os.O_RDWR, 0o600)
        except OSError:
            return True
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False
        self._fd = fd
        return True

    def release(self) -> None:
        fd, self._fd = self._fd, -1
        _release_os_lock(fd)

    def held(self) -> bool:
        return self._fd >= 0

    def __enter__(self) -> "RunLock":
        self.try_acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.release()
        return False


def run_lock(project_dir: str) -> RunLock:
    """The run lock for one project directory."""
    return RunLock(project_dir)


class _StoreLock:
    """Reentrant in-process AND cross-process lock for one store path.

    The in-process RLock is the OUTER gate, and that is what makes the
    reentrancy counter and the single file descriptor safe without a mutex of
    their own: only one thread is ever inside `__enter__`..`__exit__` for this
    path, so `_depth` can only be raised by a nested `with` on the same thread.
    The RLock is reentrant for exactly that case — a store holds the lock across
    a load-modify-write while `atomic_write_json` re-enters it.
    """

    # __weakref__ is required: _LOCKS is a WeakValueDictionary, and a slots
    # class without it cannot be weakly referenced at all.
    __slots__ = ("_path", "_rlock", "_fd", "_depth", "__weakref__")

    def __init__(self, path: str):
        self._path = path
        self._rlock = threading.RLock()
        self._fd = -1
        self._depth = 0

    def __enter__(self) -> "_StoreLock":
        self._rlock.acquire()
        try:
            if self._depth == 0:
                try:
                    fd = os.open(_lock_file_path(self._path),
                                 os.O_CREAT | os.O_RDWR, 0o600)
                except FileNotFoundError:
                    # No directory yet -> no store to guard and nothing to lock.
                    # Leave _fd at -1; the read/write below raises
                    # FileNotFoundError exactly as it did before this lock.
                    fd = -1
                else:
                    try:
                        _acquire_os_lock(fd, self._path)
                    except BaseException:
                        os.close(fd)
                        raise
                self._fd = fd
            self._depth += 1
        except BaseException:
            self._rlock.release()
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            self._depth -= 1
            if self._depth == 0:
                fd, self._fd = self._fd, -1
                _release_os_lock(fd)
        finally:
            self._rlock.release()
        return False


def _lock_for(path: str) -> "_StoreLock":
    key = os.path.abspath(path)
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = _StoreLock(key)
            _LOCKS[key] = lock
        return lock


def lock_for(path: str) -> "_StoreLock":
    """Public per-path lock for load-modify-write cycles: hold it across the
    load so a racing writer — in this process OR another one — can't clobber
    fields the writer didn't see.

    Hold at most ONE of these at a time. Two would put a nested wait-for edge
    into the lock graph, and two processes taking the same pair in opposite
    orders would deadlock. Every current caller locks a single path, and
    `atomic_write_json` re-enters the lock for the path it is already under
    rather than taking a second one.
    """
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


# Gap 82: the two shelves described the same damage in two different vocabularies —
# a damaged project said `{project, title, unreadable, stages, sessions}` and a
# damaged idea said `{id, title, unreadable, created_at, updated_at}`. The only
# shared words were `title` and `unreadable`, so the recovery UI built for one
# shelf (gap 80) could not read the other, and neither row said whether anything
# could be rescued, why the file failed, or what the file last looked like.
#
# Damage is the same event regardless of which store it happens to, so it gets
# one vocabulary here — the module that already owns `StoreUnreadable` — and every
# shelf is a superset of it. Shelf-specific keys stay (the project card still
# carries `stages`), they just no longer *are* the damage description.
DAMAGE_ENVELOPE_KEYS = ("kind", "id", "title", "unreadable",
                        "recoverable", "detail", "last_known")


def damage_envelope(kind: str, ident: str, *, title: str = None,
                    detail: str = None, recoverable: bool = True,
                    last_known: dict = None, **shelf_fields) -> dict:
    """"This thing is damaged", in the one shape every reader understands.

    `recoverable` is a claim about what the RECOVERY ROUTE would return, not a
    mood: True means there are bytes to hand back or a file to rebuild from.
    `detail` is the parser's own reason, kept verbatim so support tooling and the
    writer see the same sentence. `last_known` is what can be said about the file
    without reading it — size and mtime — because a destroyed file still has a
    past and guessing at its contents would invent one.
    """
    env = {
        "kind": kind,
        "id": ident,
        # A damaged thing keeps its identifier as its title until something
        # better survives; never blank, so no reader renders an empty card.
        "title": title or ident,
        "unreadable": True,
        "recoverable": bool(recoverable),
        "detail": detail,
        "last_known": last_known,
    }
    env.update(shelf_fields)
    return env


def last_known_facts(path: str) -> dict:
    """What is knowable about a damaged file without trusting its contents."""
    try:
        st = os.stat(path)
        return {"file": os.path.basename(path), "size": st.st_size,
                "modified": st.st_mtime}
    except OSError:
        return {"file": os.path.basename(path), "size": None, "modified": None}


class StoreUnreadable(RuntimeError):
    """A store file is there but cannot be read as its documented shape.

    Deliberately NOT folded into the caller's default. "The file is not there"
    and "the file is damaged" are different facts, and only one of them means
    the writer never had anything here: collapsing them (the shape A2/A3 were
    opened for) shows a damaged store as an empty one, and — because every
    mutator loads before it saves — the next mundane action then overwrites the
    only recoverable copy of it.
    """

    def __init__(self, path: str, detail: str = ""):
        self.path = path
        self.detail = detail
        super().__init__(
            f"{os.path.basename(path)} exists but is unreadable ({detail}); "
            "it is NOT being treated as empty")


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_json_store(path: str, default, assume_present: bool = False):
    """Read a JSON store. MISSING -> `default`; PRESENT-BUT-UNREADABLE -> raise.

    The one shared reader behind every writer-owned store, so the distinction
    (and the refusal to overwrite) is a property of the store layer instead of
    something each module re-decides. Shape checking stays with the caller:
    a list store handed a dict is just as damaged as a torn file.

    Read under the same lock as the write, and with the transient retry BE-H4
    was opened for. A concurrent writer used to surface to the writer as
    PERMANENT data damage — HTTP 503, "it is NOT being treated as empty" — for
    contention that clears in milliseconds (measured: 785 such escalations in
    one 4-process run). Contended is not damaged: only a read still failing
    after the retry budget is reported as unreadable.

    `assume_present` is for a load-modify-write cycle that ALREADY holds
    `lock_for(path)`. It settles the existence question inside that lock instead
    of by the unlocked pre-check below, because a peer that creates the file a
    microsecond earlier is otherwise answered "missing" — harmless for a plain
    read, but a merge reads "missing" as permission to write its whole stale
    snapshot over a file that now exists. Measured: that cost exactly one
    writer's turn in a 2-process race on `writer_profile.json`.
    """

    def _read():
        try:
            return retry_permission(lambda: _read_text(path))
        except FileNotFoundError:
            return None
        except OSError as e:
            raise StoreUnreadable(path, f"cannot read: {e}") from e

    # A read must not CREATE anything, so a missing store is answered without
    # taking the lock — no `.lock` sidecar for a file that isn't there. Nothing
    # is lost: a writer creating it lands atomically, and answering "missing"
    # for a file that appeared a microsecond ago is what a plain open() did
    # before this lock existed. A MERGE is the one caller that must not act on
    # that answer, which is what `assume_present` is for.
    try:
        present = os.path.exists(path)
    except OSError:
        present = False

    if present or assume_present:
        # Under the lock, so a concurrent writer's os.replace cannot land
        # between our open and our read.
        with _lock_for(path):
            raw = _read()
    else:
        raw = _read()

    if raw is None:
        return default
    if not raw.strip():
        raise StoreUnreadable(path, "zero-byte")
    try:
        return json.loads(raw)
    except ValueError as e:
        raise StoreUnreadable(path, f"invalid JSON: {e}") from e


def _fsync_dir(directory: str) -> None:
    """Persist a rename. Best-effort: Windows cannot fsync a directory handle
    and not every filesystem supports it. The DATA is already fsynced before
    the rename, so losing this only matters on a power cut."""
    if os.name == "nt":
        return
    try:
        dfd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dfd)
    except OSError:
        pass
    finally:
        try:
            os.close(dfd)
        except OSError:
            pass


def atomic_write_json(path: str, data) -> None:
    """Serialize `data` as JSON to `path` atomically (unique tmp + fsync + replace).

    The temp file name must be UNIQUE per writer. It used to be a fixed
    `path + ".tmp"`, and the per-path lock only serializes threads — so two
    processes wrote into the SAME temp file, interleaved their bytes, and the
    survivor was renamed into the store. Reproduced across 4 processes: 707
    unparseable reads, `edits.json` keeping 150 of 508 applied edits, and
    `finding_marks.json` left permanently torn at rest.

    `0o666` (umask-applied, exactly what `open()` used to give) rather than
    mkstemp's 0600, so adopting this does not quietly re-permission every store
    on disk. The fd is fsynced before the rename: a crash must not leave a
    directory entry pointing at bytes the filesystem has not committed.
    """
    with _lock_for(path):
        tmp = f"{path}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
        fd = os.open(tmp, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o666)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            retry_permission(lambda: os.replace(tmp, path))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        _fsync_dir(os.path.dirname(os.path.abspath(path)))


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
