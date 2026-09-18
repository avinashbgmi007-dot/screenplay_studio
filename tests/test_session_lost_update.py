"""H4 — chat lost-update race.

Two overlapping turns on the same session each load a fresh Session, append
their own user+assistant pair in memory, and save. The per-file lock in
SessionStore.save only serializes the WRITES — the load is outside the lock, so
the slower turn's base snapshot predates the faster turn's save, and its save
overwrites (loses) the faster turn's messages. The fix: inside the write lock,
re-read the on-disk session and re-apply this save's in-memory branch messages,
so a save never silently drops messages another turn already persisted.
"""
from __future__ import annotations

from screenplay_cowriter.models import Session, Message
from screenplay_cowriter.store import SessionStore


def _turn(session, text, reply):
    session.branch.messages.append(Message(role="user", content=text))
    session.branch.messages.append(Message(role="assistant", content=reply))


def test_save_does_not_lose_a_concurrently_saved_turn(tmp_path):
    store = SessionStore(str(tmp_path))
    base = store.create("T")
    sid = base.session_id

    # Turn A loads, appends, saves.
    a = store.load(sid)
    _turn(a, "alpha-q", "alpha-r")
    store.save(a)

    # Turn B had loaded from the ORIGINAL base (before A saved) — the stale read:
    # a fresh in-memory object holding only its own turn, none of A's messages.
    b2 = Session.new("T")
    b2.session_id = sid
    _turn(b2, "bravo-q", "bravo-r")
    store.save(b2)

    final = store.load(sid)
    users = [m.content for m in final.branch.messages if m.role == "user"]
    assert "alpha-q" in users and "bravo-q" in users, \
        f"a turn was lost; surviving user messages: {users}"
