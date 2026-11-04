"""Gap 18 — a chat turn must not lose, resurrect or destroy a conversation.

Five measured defects in one store. Fixed here: (a) the merge identified messages
by (role, content), so a repeated "Yes" was dropped as a duplicate; (b) a save
after deletion recreated the session; (e) a failed `.bak` park saved anyway and
destroyed the only recoverable copy. Defect (c) — a stale save restoring a deleted
branch — is covered by the existing `deleted_branches` tombstone and (d) — a
stale save overwriting a newer message — by the identity merge below.
"""
import json
import os

import pytest

from screenplay_cowriter.models import Message
from screenplay_cowriter.store import (SessionDeletedError, SessionStore,
                                       SessionUnreadableError)


@pytest.fixture
def store(tmp_path):
    return SessionStore(str(tmp_path / "sessions"))


class TestRepeatedIdenticalMessagesSurvive:
    def test_a_stale_snapshot_cannot_drop_a_repeated_message(self, store):
        """The measured case, and it needs the right direction to reproduce.

        Turn 1 saves 'Yes'. A second window snapshots the session (it holds one
        'Yes'), then turn 2 saves another 'Yes' — two turns, same words. The
        stale snapshot then saves. A content-keyed merge sees the DISK's two
        'Yes' messages, matches them against the one it already holds, and
        concludes there is nothing new: one turn is silently gone.

        (My first two attempts at this test did not reproduce the bug — memory
        was a superset in the first, and in the second the stale snapshot
        already contained both copies. See critique §35.)
        """
        session = store.create("Chat")
        session.branches["main"].messages.append(Message(role="user", content="Yes"))
        store.save(session)                                   # turn 1

        stale = store.load(session.session_id)                # second window
        session.branches["main"].messages.append(Message(role="user", content="Yes"))
        store.save(session)                                   # turn 2, same words
        assert len(store.load(session.session_id).branches["main"].messages) == 2

        stale.branches["main"].messages.append(Message(role="assistant", content="ok"))
        store.save(stale)                                     # the stale turn saves last

        stored = [m.content for m in store.load(session.session_id).branches["main"].messages]
        assert stored.count("Yes") == 2, (
            f"a repeated turn was merged away as a duplicate: {stored}")
        assert "ok" in stored

    def test_a_message_id_survives_a_round_trip(self, store):
        session = store.create("Chat")
        m = Message(role="user", content="hello")
        session.branches["main"].messages.append(m)
        store.save(session)
        again = store.load(session.session_id).branches["main"].messages[0]
        assert again.message_id == m.message_id

    def test_a_legacy_file_without_ids_gets_stable_ones(self, store):
        """Old sessions must merge the way they always did: loading the same file
        twice cannot mint new identities, or the whole history would duplicate."""
        session = store.create("Chat")
        path = store._path(session.session_id)
        raw = json.load(open(path, encoding="utf-8"))
        raw["branches"]["main"]["messages"] = [
            {"role": "user", "content": "old turn", "timestamp": 1.0},
        ]
        json.dump(raw, open(path, "w", encoding="utf-8"))

        first = store.load(session.session_id).branches["main"].messages[0].message_id
        second = store.load(session.session_id).branches["main"].messages[0].message_id
        assert first == second
        assert first.startswith("legacy-")


class TestDeletedSessionsStayDeleted:
    def test_a_save_after_deletion_does_not_recreate_the_session(self, store):
        session = store.create("Temp")
        store.delete(session.session_id)
        assert store.is_deleted(session.session_id)

        with pytest.raises(SessionDeletedError):
            store.save(session)
        assert not os.path.exists(store._path(session.session_id)), (
            "the deleted conversation came back")

    def test_the_tombstone_outlives_the_process(self, tmp_path):
        """A second store instance is a second process's view: the deletion has
        to be on disk, not in memory."""
        session = SessionStore(str(tmp_path / "s")).create("Temp")
        SessionStore(str(tmp_path / "s")).delete(session.session_id)
        other = SessionStore(str(tmp_path / "s"))
        assert other.is_deleted(session.session_id)
        with pytest.raises(SessionDeletedError):
            other.save(session)


class TestDamageIsNeverOverwrittenBlindly:
    def test_an_unreadable_session_is_preserved_before_it_is_replaced(self, store, tmp_path):
        session = store.create("Chat")
        path = store._path(session.session_id)
        open(path, "w", encoding="utf-8").write("{torn")
        store.save(session)  # a healthy save parks the damaged bytes
        assert os.path.exists(path + ".bak")
        assert open(path + ".bak", encoding="utf-8").read() == "{torn"

    def test_a_failed_park_refuses_the_save(self, store, monkeypatch):
        """Defect (e): the park used to be best-effort and the save proceeded,
        destroying the only recoverable copy."""
        session = store.create("Chat")
        path = store._path(session.session_id)
        open(path, "w", encoding="utf-8").write("{torn")

        import screenplay_cowriter.store as store_mod
        monkeypatch.setattr(store_mod, "_park_damaged", lambda p: False)
        with pytest.raises(SessionUnreadableError):
            store.save(session)
        assert open(path, encoding="utf-8").read() == "{torn", (
            "the damaged conversation was overwritten with no backup")
