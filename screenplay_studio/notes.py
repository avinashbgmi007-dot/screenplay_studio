"""
Writer's own margin notes — the writer's pencil, distinct from the tool's
findings. Notes pin to a scene (or the script as a whole); a note can also
carry an ``anchor`` — the exact line text it is pinned to (Google-Docs-style
margin comments). Saved per project in a small JSON file. The parser/analyzer
never touch them, so re-analysis or re-parse never loses the writer's
thoughts.
"""

from __future__ import annotations

import json
import os
import time
import uuid

NOTES_FILE = "notes.json"


def _path(m) -> str:
    return os.path.join(m.project_dir, NOTES_FILE)


def _load_raw(m) -> list[dict]:
    path = _path(m)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(m, notes: list[dict]) -> None:
    with open(_path(m), "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2, ensure_ascii=False)


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
