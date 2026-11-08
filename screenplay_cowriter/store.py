"""
File-based session store. One JSON file per session under `sessions_dir`.
This is deliberately boring — no database, just files — since a single user
running a local screenplay co-writer doesn't need more than that, and it
keeps the whole thing inspectable/hand-editable if something goes wrong.
"""

import glob
import json
import os
import time

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
        return True
    except OSError:
        # Gap 18(e): this used to return None and the caller saved anyway, so a
        # failed park meant the save overwrote the damaged original with no
        # backup. The caller now fails closed on False.
        return False


class SessionDeletedError(Exception):
    """A save arrived for a session that was deleted while the turn was in flight.

    Gap 18(b): the store used to recreate the session, resurrecting a
    conversation the writer had deliberately removed.
    """


class SessionUnreadableError(Exception):
    """A session file is damaged AND could not be preserved as `.bak`.

    Gap 18(e): the save used to proceed regardless, destroying the only
    recoverable copy of the conversation.
    """


_SESSION_CREATE_ATTEMPTS = 32


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
        from screenplay_studio.jsonio import atomic_create_json

        for _ in range(_SESSION_CREATE_ATTEMPTS):
            session = Session.new(title=title, report_path=report_path,
                                  script_path=script_path)
            # Creation must claim the filename without replacing it. `save`
            # intentionally has replace semantics for later updates; using it
            # here let an ID collision destroy the existing conversation.
            if atomic_create_json(self._path(session.session_id), session.to_dict()):
                return session
        raise RuntimeError(
            "Could not allocate a unique session id after "
            f"{_SESSION_CREATE_ATTEMPTS} attempts.")

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
        # (see the tombstone check inside the lock below)
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
            # Gap 18(b): a stale snapshot must never bring a deleted
            # conversation back. Refuse loudly — silently dropping the turn
            # would be the same class of lie in the other direction.
            if self._superseded_by_delete(path, session):
                raise SessionDeletedError(
                    f"Session '{session.session_id}' was deleted while this turn "
                    "was in flight; the turn was not saved.")
            if os.path.exists(path):
                try:
                    disk = Session.load(path)
                    self._merge_missing_messages(disk, session, owns_selection)
                except OSError:
                    # Transient read contention (a sharing violation), NOT
                    # damage — park nothing, and still land this save.
                    pass
                except Exception as e:
                    # Genuinely unreadable (torn or wrong-shape JSON). Gap 18(e):
                    # this used to park best-effort and save regardless, so when
                    # the rename failed the save destroyed the only recoverable
                    # copy. FAIL CLOSED instead: if the damaged bytes cannot be
                    # preserved, refuse the write and say why. A refused save is
                    # recoverable; an overwritten conversation is not.
                    if not _park_damaged(path):
                        raise SessionUnreadableError(
                            f"Session '{session.session_id}' is unreadable and "
                            f"could not be preserved as '{os.path.basename(path)}.bak' "
                            f"({e}); refusing to overwrite it.") from e
            session.save(path)

    def _superseded_by_delete(self, path, session: Session) -> bool:
        """Was this in-memory session deleted out from under us?

        A tombstone's mere EXISTENCE is the wrong test, and getting that wrong
        broke a real feature: the Design Lab thread lives at a FIXED id
        (`preview-lab`), "clear this chat" deletes it, and the next request
        legitimately re-creates it at that same id. Blocking on the tombstone
        made every request after a clear fail with `SessionDeletedError` — the
        whole lab 500'd (caught by `tests/test_preview_lab.py`).

        The defect is a STALE save, so test for staleness: the session came into
        being (`Session.created_at`) BEFORE the deletion was recorded. A
        conversation deleted underneath a stale snapshot is always older than
        the deletion; a session built after the clear is a new conversation at a
        reused id and is allowed.

        Strict `<` on purpose: equal timestamps mean the ordering is unknown, so
        let the save through rather than break clear-and-start-over.
        """
        if os.path.exists(path):
            return False  # live file — the normal merge applies
        tomb = self._tombstone_path(session.session_id)
        if not os.path.exists(tomb):
            return False  # never deleted
        try:
            with open(tomb, encoding="utf-8") as f:
                deleted_at = float(json.load(f)["deleted_at"])
        except (OSError, ValueError, KeyError, TypeError):
            # Damaged tombstone: cannot prove this save is fresh. Fail
            # conservative and refuse — a resurrected conversation is
            # unrecoverable; a refused save is retriable and says why.
            return True
        return session.created_at < deleted_at

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
            # Gap 18(a): identity, not text. Keying on (role, content) meant a
            # writer who said "Yes" twice had the second message dropped as a
            # duplicate of the first — the merge could not tell two turns
            # apart. `message_id` is the primary key now; (role, content) is
            # kept ONLY as the fallback for legacy messages whose id was derived
            # deterministically, so old sessions still merge the way they did.
            have_ids = {m.message_id for m in sbranch.messages}
            for m in dbranch.messages:
                if m.message_id in have_ids:
                    continue
                if m.message_id.startswith("legacy-") and \
                        any(x.role == m.role and x.content == m.content
                            for x in sbranch.messages):
                    continue  # legacy fallback: same text, same turn
                sbranch.messages.append(m)
                have_ids.add(m.message_id)
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
        # Gap 18(b): deleting the file was not enough. An in-flight chat holds a
        # stale snapshot and its next `save` recreates the session — the writer
        # deleted a conversation and it came back. A durable tombstone (kept
        # after the file is gone) is what lets `save` tell "deleted" from "new",
        # and it outlives the process, because the writer's other window may be
        # a different one.
        from screenplay_studio.jsonio import atomic_write_json, lock_for
        with lock_for(path):
            if os.path.exists(path):
                os.remove(path)
            atomic_write_json(self._tombstone_path(session_id), {
                "session_id": session_id,
                "deleted_at": time.time(),
            })

    def _tombstone_path(self, session_id: str) -> str:
        return os.path.join(self.sessions_dir, f"{session_id}.deleted.json")

    def is_deleted(self, session_id: str) -> bool:
        """Did the writer delete this conversation?

        A present-but-unparseable tombstone answers YES — the conservative side.
        The session file is already gone, so a damaged record cannot prove no
        deletion happened, and guessing "no" would report a deleted
        conversation as live. `delete()` writes the tombstone atomically, so an
        unreadable one means outside damage. Bookkeeping only: `save` decides
        from timestamps (`_superseded_by_delete`), never from this, so failing
        conservative here does not lock an id against an explicit re-create.
        """
        tomb = self._tombstone_path(session_id)
        if not os.path.exists(tomb):
            return False
        try:
            with open(tomb, encoding="utf-8") as f:
                json.load(f)
        except (OSError, ValueError):
            return True  # damaged: cannot prove it was not a deletion
        return True
