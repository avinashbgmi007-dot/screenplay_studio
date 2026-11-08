"""Gap 49: creation claims new idea/chat identities without clobbering old data."""

from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from screenplay_cowriter.models import Message, Session
from screenplay_cowriter.store import SessionStore
from screenplay_studio.ideas import EMPTY_CARD, IdeaStore
from screenplay_studio.jsonio import atomic_create_json
import screenplay_cowriter.models as models_mod
import screenplay_studio.ideas as ideas_mod


FIRST_ID = uuid.UUID("deadbeef-1234-5678-9abc-def012345678").hex
SECOND_ID = uuid.UUID("cafebabe-1234-5678-9abc-def012345678").hex
WORKERS = 4


def _colliding_ids(collision: str, count: int):
    lock = threading.Lock()
    calls = 0

    def supply() -> str:
        nonlocal calls
        with lock:
            calls += 1
            current = calls
        if current <= count:
            return collision
        return uuid.UUID(int=current).hex

    return supply


def test_atomic_create_json_never_replaces_an_existing_document(tmp_path):
    path = tmp_path / "record.json"
    assert atomic_create_json(str(path), {"content": "original"}) is True
    assert atomic_create_json(str(path), {"content": "replacement"}) is False
    assert json.loads(path.read_text(encoding="utf-8")) == {"content": "original"}
    assert not list(tmp_path.glob("*.create.tmp"))


def test_idea_collision_retries_without_overwriting_and_survives_restart(
        tmp_path, monkeypatch):
    ideas_dir = tmp_path / "ideas"
    store = IdeaStore(str(ideas_dir))
    monkeypatch.setattr(ideas_mod, "_new_idea_id", lambda: FIRST_ID)
    original = store.create("First idea")
    store.save_content(original["id"], "Synthetic original content must survive.")

    candidates = iter((FIRST_ID, SECOND_ID))
    monkeypatch.setattr(ideas_mod, "_new_idea_id", lambda: next(candidates))
    second = store.create("Second idea")

    restarted = IdeaStore(str(ideas_dir))
    assert original["id"] == FIRST_ID
    assert second["id"] == SECOND_ID
    assert restarted.load(FIRST_ID)["content"] == "Synthetic original content must survive."
    assert restarted.load(FIRST_ID)["title"] == "Synthetic original content must survive."
    assert restarted.load(SECOND_ID)["title"] == "Second idea"
    assert {row["id"] for row in restarted.list()} == {FIRST_ID, SECOND_ID}


def test_idea_collision_exhaustion_fails_without_touching_existing_data(
        tmp_path, monkeypatch):
    store = IdeaStore(str(tmp_path / "ideas"))
    monkeypatch.setattr(ideas_mod, "_new_idea_id", lambda: FIRST_ID)
    store.create("First idea")
    store.save_content(FIRST_ID, "Keep this page.")

    with pytest.raises(RuntimeError, match="32 attempts"):
        store.create("Must not replace")
    assert store.load(FIRST_ID)["content"] == "Keep this page."
    assert store.load(FIRST_ID)["title"] == "Keep this page."


def test_restart_after_orphaned_idea_claim_retries_without_touching_it(
        tmp_path, monkeypatch):
    ideas_dir = tmp_path / "ideas"
    store = IdeaStore(str(ideas_dir))
    # Simulates a process stopping after mkdir claimed an id but before metadata
    # was published. The next creator must treat that directory as occupied.
    (ideas_dir / FIRST_ID).mkdir()
    candidates = iter((FIRST_ID, SECOND_ID))
    monkeypatch.setattr(ideas_mod, "_new_idea_id", lambda: next(candidates))

    created = store.create("After restart")

    assert created["id"] == SECOND_ID
    assert (ideas_dir / FIRST_ID).is_dir()
    assert store.load(SECOND_ID)["title"] == "After restart"


def test_parallel_idea_creators_claim_distinct_directories(tmp_path, monkeypatch):
    ideas_dir = tmp_path / "ideas"
    store = IdeaStore(str(ideas_dir))
    monkeypatch.setattr(ideas_mod, "_new_idea_id", _colliding_ids(FIRST_ID, WORKERS))

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        created = list(pool.map(lambda n: store.create(f"Idea {n}"), range(WORKERS)))

    ids = {row["id"] for row in created}
    restarted = IdeaStore(str(ideas_dir))
    assert len(ids) == WORKERS
    assert {row["id"] for row in restarted.list()} == ids
    assert {restarted.load(idea_id)["title"] for idea_id in ids} == {
        f"Idea {n}" for n in range(WORKERS)
    }


def test_session_collision_retries_without_overwriting_and_survives_restart(
        tmp_path, monkeypatch):
    sessions_dir = tmp_path / "sessions"
    store = SessionStore(str(sessions_dir))
    monkeypatch.setattr(models_mod, "_new_session_id", lambda: FIRST_ID)
    original = store.create("First chat")
    original.branches["main"].messages.append(
        Message(role="user", content="Synthetic original message must survive."))
    store.save(original)

    candidates = iter((FIRST_ID, SECOND_ID))
    monkeypatch.setattr(models_mod, "_new_session_id", lambda: next(candidates))
    second = store.create("Second chat")

    restarted = SessionStore(str(sessions_dir))
    first_again = restarted.load(FIRST_ID)
    second_again = restarted.load(SECOND_ID)
    assert original.session_id == FIRST_ID
    assert second.session_id == SECOND_ID
    assert first_again.title == "First chat"
    assert [m.content for m in first_again.branches["main"].messages] == [
        "Synthetic original message must survive."
    ]
    assert second_again.title == "Second chat"
    assert {row["session_id"] for row in restarted.list()} == {FIRST_ID, SECOND_ID}


def test_session_collision_exhaustion_fails_without_touching_existing_chat(
        tmp_path, monkeypatch):
    store = SessionStore(str(tmp_path / "sessions"))
    monkeypatch.setattr(models_mod, "_new_session_id", lambda: FIRST_ID)
    original = store.create("First chat")
    original.branches["main"].messages.append(
        Message(role="user", content="Keep this conversation."))
    store.save(original)

    with pytest.raises(RuntimeError, match="32 attempts"):
        store.create("Must not replace")
    reread = store.load(FIRST_ID)
    assert reread.title == "First chat"
    assert [m.content for m in reread.branches["main"].messages] == [
        "Keep this conversation."
    ]
    assert len(store.list()) == 1


def test_restart_after_unpublished_session_temp_creates_a_complete_session(
        tmp_path, monkeypatch):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    # Simulates the temp left if a process dies before the atomic hard-link
    # publication. It is not a final .json and therefore cannot be resumed as a
    # partial chat or mistaken for an occupied session id.
    (sessions_dir / f"{FIRST_ID}.json.123.leftover.create.tmp").write_text(
        '{"partial":', encoding="utf-8")
    store = SessionStore(str(sessions_dir))
    monkeypatch.setattr(models_mod, "_new_session_id", lambda: FIRST_ID)

    created = store.create("After restart")

    restarted = SessionStore(str(sessions_dir))
    assert created.session_id == FIRST_ID
    assert restarted.load(FIRST_ID).title == "After restart"
    assert {row["session_id"] for row in restarted.list()} == {FIRST_ID}
    assert (sessions_dir / f"{FIRST_ID}.json.123.leftover.create.tmp").exists()


def test_parallel_session_creators_claim_distinct_files(tmp_path, monkeypatch):
    sessions_dir = tmp_path / "sessions"
    store = SessionStore(str(sessions_dir))
    monkeypatch.setattr(models_mod, "_new_session_id",
                        _colliding_ids(FIRST_ID, WORKERS))

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        created = list(pool.map(lambda n: store.create(f"Chat {n}"), range(WORKERS)))

    ids = {session.session_id for session in created}
    restarted = SessionStore(str(sessions_dir))
    assert len(ids) == WORKERS
    assert {row["session_id"] for row in restarted.list()} == ids
    assert {restarted.load(session_id).title for session_id in ids} == {
        f"Chat {n}" for n in range(WORKERS)
    }


def test_legacy_eight_character_ids_remain_loadable_after_full_ids_are_created(
        tmp_path):
    ideas_dir = tmp_path / "ideas"
    idea_store = IdeaStore(str(ideas_dir))
    legacy_idea_id = "deadbeef"
    (ideas_dir / legacy_idea_id).mkdir()
    legacy_meta = {
        "id": legacy_idea_id, "title": "Legacy idea", "created_at": 1,
        "updated_at": 1, "card": dict(EMPTY_CARD), "content": "Old page",
    }
    idea_store._write(legacy_idea_id, legacy_meta)
    new_idea = idea_store.create("New idea")
    assert len(new_idea["id"]) == 32
    assert idea_store.load(legacy_idea_id)["content"] == "Old page"

    sessions_dir = tmp_path / "sessions"
    session_store = SessionStore(str(sessions_dir))
    legacy_session_id = "cafebabe"
    legacy_session = Session(session_id=legacy_session_id, title="Legacy chat")
    legacy_session.save(session_store._path(legacy_session_id))
    new_session = session_store.create("New chat")
    assert len(new_session.session_id) == 32
    assert session_store.load(legacy_session_id).title == "Legacy chat"
