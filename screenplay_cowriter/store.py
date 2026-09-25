"""
File-based session store. One JSON file per session under `sessions_dir`.
This is deliberately boring — no database, just files — since a single user
running a local screenplay co-writer doesn't need more than that, and it
keeps the whole thing inspectable/hand-editable if something goes wrong.
"""

import glob
import os

from .models import Session

# Sessions are serialized by `screenplay_studio.jsonio.lock_for`, which carries
# BOTH an in-process RLock and an OS-level byte-range lock. The local
# `threading.Lock` that used to live here only covered threads inside one
# process, while the CLI and the webapp both write the same project directory
# (AGENTS.md documents that as a supported configuration).


def _park_damaged(path: str) -> None:
    """Move an unreadable session file aside as `<path>.bak` before it is
    overwritten.

    A chat turn must never break, so a damaged base does not block the save —
    but silently replacing the writer's conversation is not an acceptable way to
    achieve that. Parking the bytes keeps the one recoverable copy. Same shape
    as WriterMemory's `.bak` (screenplay_cowriter/memory.py).
    """
    from screenplay_studio.jsonio import retry_permission
    try:
        retry_permission(lambda: os.replace(path, path + ".bak"))
    except OSError:
        pass  # if it cannot be parked, the save still proceeds


class SessionStore:
    def __init__(self, sessions_dir: str = "./sessions"):
        self.sessions_dir = sessions_dir
        os.makedirs(sessions_dir, exist_ok=True)

    def _path(self, session_id: str) -> str:
        # B1 (audit 2026-09-20): session ids are user-controlled (webapp <sid>
        # route param) and the Flask converter delivers backslashes on Windows —
        # without this guard "../../x" escapes sessions_dir. Lazy import keeps
        # the composability contract (cowriter must not import studio at load).
        from screenplay_studio.jsonio import check_safe_id
        check_safe_id(session_id, "session id")
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

    def save(self, session: Session, *, owns_selection: bool = False) -> None:
        # Serialize writes per session file AND merge across concurrent turns.
        # The lock alone only serializes the writes; the load that produced
        # `session` happened OUTSIDE it, so a stale in-memory snapshot would
        # overwrite (lose) messages a faster turn already saved (H4). Inside the
        # lock, re-read the on-disk session and union any branch messages this
        # in-memory snapshot is missing, keyed by content, so no persisted turn
        # is silently dropped.
        #
        # BE-6 (round-3 audit 2026-09-25): the merge covered branch MESSAGES and
        # nothing else, so the writer's SELECTION — `current_branch` and each
        # branch's active persona/mode — stayed last-writer-wins. A chat turn
        # holds a snapshot taken before the writer switched branches, so its save
        # wrote the OLD branch back and silently undid the switch. Only the routes
        # that exist to change the selection pass `owns_selection=True`; every
        # message-only save now leaves disk's selection alone.
        #
        # Deliberately scoped to those three fields, and the exclusions are
        # choices rather than oversights: `server_url` / `model_id` / `title` are
        # written when a session is created or resumed, where the snapshot IS the
        # source of truth, and `awaiting_probe` is turn state the engine has just
        # set — preserving disk's would break the probe.
        #
        # The write itself is `Session.save`, which is atomic (unique tmp +
        # fsync + os.replace). This method used to hand-roll that with a FIXED
        # `path + ".tmp"` — the same name in every process, so two writers'
        # bytes interleaved in one buffer and the survivor was renamed into the
        # session file.
        path = self._path(session.session_id)
        from screenplay_studio.jsonio import lock_for
        with lock_for(path):
            if os.path.exists(path):
                try:
                    disk = Session.load(path)
                    self._merge_missing_messages(disk, session, owns_selection)
                except OSError:
                    # Transient read contention (a sharing violation), NOT
                    # damage — park nothing, and still land this save.
                    pass
                except Exception:
                    # Genuinely unreadable (torn or wrong-shape JSON). The save
                    # must still happen — a chat turn may never break — but the
                    # unreadable bytes are parked first, so this save is not the
                    # thing that destroys the only recoverable copy.
                    _park_damaged(path)
            session.save(path)

    @staticmethod
    def _merge_missing_messages(disk: Session, session: Session,
                                owns_selection: bool = True) -> None:
        """Append onto `session` any branch messages present on `disk` (the
        already-saved state) that this in-memory snapshot lacks. Keyed on
        (branch, role, content) so the two halves of one turn never collide and
        a repeated phrase on a different turn is still its own message.

        `owns_selection=False` additionally takes the writer's SELECTION from
        `disk`: `current_branch` and each branch's active persona/mode. That is
        BE-6 — see `save` for why those three and not the rest.

        `owns_selection` defaults to True so the method keeps its old behaviour
        for any direct caller; `save` is what passes the real value through.
        """
        for bname, dbranch in disk.branches.items():
            sbranch = session.branches.get(bname)
            if sbranch is None:
                # A branch on disk that this snapshot does not have is usually a
                # concurrent fork, and losing it would lose its messages — so the
                # union copies it. But it is also what a DELIBERATE deletion
                # looks like from here, which is why `Session.delete_branch`
                # leaves a tombstone and this respects it. Without that check the
                # union silently undid every `/delete` (DEL-1).
                if bname in session.deleted_branches:
                    continue
                session.branches[bname] = dbranch  # whole branch is new to us
                continue
            have = {(m.role, m.content) for m in sbranch.messages}
            for m in dbranch.messages:
                if (m.role, m.content) not in have:
                    sbranch.messages.append(m)
                    have.add((m.role, m.content))
        if not owns_selection:
            # A snapshot that predates the writer's last switch must not write
            # the old branch back. `disk` is the newer truth for a field this
            # save was never about.
            #
            # Only adopt it if it names a branch we actually hold. The union
            # loop above guarantees that for any session this app wrote, but a
            # hand-edited or torn file can carry a dangling `current_branch`,
            # and assigning it would turn a healthy in-memory session into a
            # `KeyError` on the next `session.branch` — a 500 on the next turn,
            # from a save that was only ever meant to add a message.
            if disk.current_branch in session.branches:
                session.current_branch = disk.current_branch
            for bname, dbranch in disk.branches.items():
                sbranch = session.branches.get(bname)
                if sbranch is not None:
                    sbranch.active_persona = dbranch.active_persona
                    sbranch.active_mode = dbranch.active_mode

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
            except Exception as e:
                # Skip it — one damaged file must not break the whole list — but
                # never SILENTLY. Otherwise the writer's session list is simply
                # missing a conversation and they cannot tell that from never
                # having had one; "missing is a legitimate empty; damage is
                # reported" is the rule the writer's stores already follow. The
                # file is left untouched, so a hand-recovery stays possible.
                print(f"[sessions] skipping unreadable session "
                      f"{os.path.basename(path)}: {e}")
                continue
        return sorted(out, key=lambda x: -x["updated_at"])

    def delete(self, session_id: str) -> None:
        path = self._path(session_id)
        if os.path.exists(path):
            os.remove(path)
