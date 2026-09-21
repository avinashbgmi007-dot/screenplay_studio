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

import os
import time
import uuid


def stash_path(project_dir: str) -> str:
    return os.path.join(project_dir, "stash.json")


def load_stash(project_dir: str) -> list[dict]:
    # missing -> [] ; damaged -> StoreUnreadable (never [] — that read as "your
    # stash is empty" and the next add_to_stash then overwrote the damaged file)
    from .jsonio import StoreUnreadable, load_json_store
    path = stash_path(project_dir)
    data = load_json_store(path, default=[])
    if not isinstance(data, list):
        raise StoreUnreadable(path, f"expected a list, found {type(data).__name__}")
    return [e for e in data if isinstance(e, dict) and e.get("text")]


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
    with _locked(project_dir):
        stash = load_stash(project_dir)
        stash.insert(0, entry)  # newest first
        _save(project_dir, stash)
    return entry


def remove_from_stash(project_dir: str, entry_id: str) -> bool:
    with _locked(project_dir):
        stash = load_stash(project_dir)
        remaining = [e for e in stash if e.get("id") != entry_id]
        if len(remaining) == len(stash):
            return False
        _save(project_dir, remaining)
    return True


def _save(project_dir: str, stash: list[dict]) -> None:
    os.makedirs(project_dir, exist_ok=True)
    from .jsonio import atomic_write_json
    atomic_write_json(stash_path(project_dir), stash)


def _locked(project_dir: str):
    """The stash's load-modify-write lock: hold it across the READ so a racing
    save — in this process or another one — cannot clobber an entry it never
    saw. Measured before this: two concurrent adds left ONE entry, because the
    second loaded the pre-add list and wrote it back over the first.

    The makedirs mirrors `_save`'s: the lock sidecar lives beside the store, so
    the directory has to exist before there is anything to lock.
    """
    os.makedirs(project_dir, exist_ok=True)
    from .jsonio import lock_for
    return lock_for(stash_path(project_dir))
