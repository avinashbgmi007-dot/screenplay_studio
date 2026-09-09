"""
File-based session store. One JSON file per session under `sessions_dir`.
This is deliberately boring — no database, just files — since a single user
running a local screenplay co-writer doesn't need more than that, and it
keeps the whole thing inspectable/hand-editable if something goes wrong.
"""

import glob
import os
import threading

from .models import Session

# One lock per session file path (process-wide). Streaming turns and the
# every-10-turns memory refresh can overlap a save from another request;
# without this, two concurrent saves of the SAME session file race and the
# last write wins — silently dropping a just-stored message.
_LOCKS_GUARD = threading.Lock()
_LOCKS: dict = {}


def _lock_for(path: str) -> threading.Lock:
    key = os.path.abspath(path)
    with _LOCKS_GUARD:
        if key not in _LOCKS:
            _LOCKS[key] = threading.Lock()
        return _LOCKS[key]


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
        return Session.load(path)

    def save(self, session: Session) -> None:
        # Serialize writes per session file: concurrent turns on the same
        # conversation (e.g. a retry racing a slow first attempt) must not
        # clobber each other's messages. The write also lands atomically
        # (temp file + os.replace) so a concurrent reader never sees a torn,
        # half-written JSON file.
        path = self._path(session.session_id)
        with _lock_for(path):
            tmp = path + ".tmp"
            session.save(tmp)
            os.replace(tmp, path)

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
