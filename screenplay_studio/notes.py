"""
Writer's own margin notes — the writer's pencil, distinct from the tool's
findings. Notes pin to a scene (or the script as a whole); a note can also
carry an ``anchor`` — the exact line text it is pinned to (Google-Docs-style
margin comments). Saved per project in a small JSON file. The parser/analyzer
never touch them, so re-analysis or re-parse never loses the writer's
thoughts.
"""

from __future__ import annotations

import os
import time
import uuid

NOTES_FILE = "notes.json"


def _path(m) -> str:
    return os.path.join(m.project_dir, NOTES_FILE)


def _load_raw(m) -> list[dict]:
    # A damaged notes.json must NOT read as "you have no margin notes" (and it
    # must not be overwritten by the next note either): see jsonio.StoreUnreadable.
    from .jsonio import StoreUnreadable, load_json_store
    data = load_json_store(_path(m), default=[])
    if not isinstance(data, list):
        raise StoreUnreadable(_path(m), f"expected a list, found {type(data).__name__}")
    return data


def _save(m, notes: list[dict]) -> None:
    from .jsonio import atomic_write_json
    atomic_write_json(_path(m), notes)


def load_notes(m) -> list[dict]:
    """All notes, newest first."""
    notes = _load_raw(m)
    notes.sort(key=lambda n: n.get("created_at", 0), reverse=True)
    return notes


def notes_for_scene(m, scene_number) -> list[dict]:
    return [n for n in load_notes(m) if n.get("scene_number") == scene_number]


def add_note(m, scene_number, text: str, anchor: str | None = None) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("Note text is required.")
    if scene_number is not None:
        try:
            scene_number = int(scene_number)
        except (TypeError, ValueError):
            raise ValueError("scene_number must be an integer or null.")
    anchor = (anchor or "").strip() or None
    now = time.time()
    note = {
        "id": uuid.uuid4().hex[:12],
        "scene_number": scene_number,
        "text": text,
        "anchor": anchor,
        "created_at": now,
        "updated_at": now,
    }
    notes = _load_raw(m)
    notes.append(note)
    _save(m, notes)
    return note


def update_note(m, note_id: str, text: str) -> dict | None:
    text = (text or "").strip()
    if not text:
        raise ValueError("Note text is required.")
    notes = _load_raw(m)
    for n in notes:
        if n.get("id") == note_id:
            n["text"] = text
            n["updated_at"] = time.time()
            _save(m, notes)
            return n
    return None


def delete_note(m, note_id: str) -> bool:
    notes = _load_raw(m)
    kept = [n for n in notes if n.get("id") != note_id]
    if len(kept) == len(notes):
        return False
    _save(m, kept)
    return True
