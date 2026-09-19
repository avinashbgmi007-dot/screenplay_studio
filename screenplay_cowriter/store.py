"""
File-based session store. One JSON file per session under `sessions_dir`.
This is deliberately boring — no database, just files — since a single user
running a local screenplay co-writer doesn't need more than that, and it
keeps the whole thing inspectable/hand-editable if something goes wrong.
"""

import glob
import os
import threading
import weakref

from .models import Session

# One lock per session file path (process-wide). Streaming turns and the
# every-10-turns memory refresh can overlap a save from another request;
# without this, two concurrent saves of the SAME session file race and the
# last write wins — silently dropping a just-stored message.
#
# Weak values (L1), the same shape as jsonio's registry: a holder keeps a strong
# reference for the duration of `with lock:`, so the entry cannot vanish under a
# waiter's feet, and a session nobody is saving costs nothing. The plain dict
# kept one entry per session file for the life of the process.
_LOCKS_GUARD = threading.Lock()
_LOCKS: "weakref.WeakValueDictionary[str, threading.Lock]" = weakref.WeakValueDictionary()


def _lock_for(path: str) -> threading.Lock:
    key = os.path.abspath(path)
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[key] = lock
        return lock


class SessionStore:
    def __init__(self, sessions_dir: str = "./sessions"):
        self.sessions_dir = sessions_dir
        os.makedirs(sessions_dir, exist_ok=True)

    def _path(self, session_id: str) -> str:
        return os.path.join(self.sessions_dir, f"{session_id}.json")

    def create(self, title: str, report_path: str = None, script_path: str = None) -> Session:
        session = Session.new(title=title, report_path=report_path, script_path=script_path)
        session.save(self._path(session.session_id))
        return session

    def load(self, session_id: str) -> Session:
        path = self._path(session_id)
        if not os.path.exists(path):
            raise FileNotFoundError(f"No session '{session_id}' found in {self.sessions_dir}")
        # reader-side bounded retry: the writer's tmp+os.replace can make a
        # concurrent open raise a Windows sharing violation (WinError 32 ->
        # PermissionError) — the hammer contract is that load always parses.
        from screenplay_studio.jsonio import retry_permission
        return retry_permission(lambda: Session.load(path))

    def save(self, session: Session) -> None:
        # Serialize writes per session file AND merge across concurrent turns.
        # The lock alone only serializes the writes; the load that produced
        # `session` happened OUTSIDE it, so a stale in-memory snapshot would
        # overwrite (lose) messages a faster turn already saved (H4). Inside the
        # lock, re-read the on-disk session and union any branch messages this
        # in-memory snapshot is missing, keyed by content, so no persisted turn
        # is silently dropped. The write also lands atomically (temp file +
        # os.replace) so a concurrent reader never sees a torn JSON file.
        path = self._path(session.session_id)
        with _lock_for(path):
            if os.path.exists(path):
                try:
                    disk = Session.load(path)
                    self._merge_missing_messages(disk, session)
                except Exception:
                    pass  # a corrupt/unreadable base must not block the save
            tmp = path + ".tmp"
            session.save(tmp)
            from screenplay_studio.jsonio import retry_permission
            retry_permission(lambda: os.replace(tmp, path))

    @staticmethod
    def _merge_missing_messages(disk: Session, session: Session) -> None:
        """Append onto `session` any branch messages present on `disk` (the
        already-saved state) that this in-memory snapshot lacks. Keyed on
        (branch, role, content) so the two halves of one turn never collide and
        a repeated phrase on a different turn is still its own message."""
        for bname, dbranch in disk.branches.items():
            sbranch = session.branches.get(bname)
            if sbranch is None:
                session.branches[bname] = dbranch  # whole branch is new to us
                continue
            have = {(m.role, m.content) for m in sbranch.messages}
            for m in dbranch.messages:
                if (m.role, m.content) not in have:
                    sbranch.messages.append(m)
                    have.add((m.role, m.content))

    def list(self) -> list[dict]:
        """Lightweight listing (id, title, branch count, last updated) without full deserialization cost."""
        out = []
        for path in sorted(glob.glob(os.path.join(self.sessions_dir, "*.json"))):
            try:
                s = Session.load(path)
                out.append({
                    "session_id": s.session_id,
                    "title": s.title,
                    "branches": list(s.branches.keys()),
                    "current_branch": s.current_branch,
                    "updated_at": s.updated_at,
                })
            except Exception:
                continue
        return sorted(out, key=lambda x: -x["updated_at"])

    def delete(self, session_id: str) -> None:
        path = self._path(session_id)
        if os.path.exists(path):
            os.remove(path)
