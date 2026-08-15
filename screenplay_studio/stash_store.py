"""
Stash — the writer's scrapbook for cut material and good lines.

Per-project JSON file (`stash.json` in the project dir): a list of saved
snippets, each with an id, the text, an optional title, the scene it came
from (when selected from the script), and a created timestamp. Pure storage —
no model involvement. The Stash is the flow-preservation feature: writers
lose good lines to bad drafts; here they park them beside the script and
pull them back later.
"""

from __future__ import annotations

import json
import os
import time
import uuid


def stash_path(project_dir: str) -> str:
    return os.path.join(project_dir, "stash.json")


def load_stash(project_dir: str) -> list[dict]:
    try:
        with open(stash_path(project_dir), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [e for e in data if isinstance(e, dict) and e.get("text")]
    except (OSError, ValueError):
        pass
    return []


def add_to_stash(project_dir: str, text: str, title: str = "", scene_number: int | None = None) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("Stash entry needs text.")
    entry = {
        "id": uuid.uuid4().hex[:8],
        "text": text[:4000],
        "title": (title or "").strip()[:120],
        "scene_number": scene_number if scene_number is not None and isinstance(scene_number, int) else None,
        "created_at": time.time(),
    }
    stash = load_stash(project_dir)
    stash.insert(0, entry)  # newest first
    _save(project_dir, stash)
    return entry


def remove_from_stash(project_dir: str, entry_id: str) -> bool:
    stash = load_stash(project_dir)
    remaining = [e for e in stash if e.get("id") != entry_id]
    if len(remaining) == len(stash):
        return False
    _save(project_dir, remaining)
    return True


def _save(project_dir: str, stash: list[dict]) -> None:
    os.makedirs(project_dir, exist_ok=True)
    with open(stash_path(project_dir), "w", encoding="utf-8") as f:
        json.dump(stash, f, ensure_ascii=False, indent=2)
