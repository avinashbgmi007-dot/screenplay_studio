"""
Stash — the writer's scrapbook for cut material and good lines.

Per-project JSON file (`stash.json` in the project dir): a list of saved
snippets, each with an id, the text, an optional title, the scene it came
from (when selected from the script), and a created timestamp. Pure storage —
no model involvement. The Stash is the flow-preservation feature: writers
lose good lines to bad drafts; here they park them beside the script and
pull them back later.

Gap 19 — a snippet is never cut in silence. The store used to save
`text[:4000]` and return the truncated entry as an ordinary success, so the
writer read "Stashed ✓" beside a passage whose tail had just been deleted, and
the success record could not even say so. There is still a bound (it is spelled
here as `MAX_TEXT_CHARS`, not as a bare slice buried in a dict literal), but:

* the tail is never dropped: text over the bound is **refused**, with an error
  naming the length and the bound, so nothing is lost without the writer
  choosing it;
* `MAX_TEXT_CHARS` is served to the client (`/api/projects/<name>/stash` GET),
  so the UI can *preview* the same refusal before anything is sent;
* a legacy entry written by the old code is not rewritten: `entry_truncated()`
  reports the length/dropped counts from the evidence already on disk (entries
  saved before the fix carry exactly the bound, so their real length is
  unknown — that is stated as unknown rather than guessed).
"""

from __future__ import annotations

import os
import time
import uuid


# The Stash is a scrapbook for lines and short passages, not a second copy of
# the script: 4,000 characters is ~2-3 pages of screenplay, and it is the bound
# the store always had. It is a CONSTANT now so the refusal, the API and the UI
# all quote the same number.
MAX_TEXT_CHARS = 4000
MAX_TITLE_CHARS = 120


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
    # Refuse, never truncate (gap 19). Measured before this: a 4,004-character
    # selection saved exactly 4,000 and the last four characters were gone, with
    # a 201 and a "Stashed ✓" in the UI — the only copy of that passage was the
    # writer's clipboard, and nothing said so.
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(
            f"That passage is {len(text):,} characters; the Stash keeps up to "
            f"{MAX_TEXT_CHARS:,}. Nothing was saved and nothing was cut — "
            f"stash a shorter selection, or keep the long version elsewhere."
        )
    entry = {
        "id": uuid.uuid4().hex[:8],
        "text": text,
        "title": (title or "").strip()[:MAX_TITLE_CHARS],
        "scene_number": scene_number if scene_number is not None and isinstance(scene_number, int) else None,
        "created_at": time.time(),
    }
    with _locked(project_dir):
        stash = load_stash(project_dir)
        stash.insert(0, entry)  # newest first
        _save(project_dir, stash)
    return entry


def entry_truncated(entry: dict) -> dict | None:
    """Was this entry cut short by the OLD store, and by how much?

    Entries written before gap 19 were sliced to exactly 4,000 characters, so
    `len(text) == MAX_TEXT_CHARS` is the only evidence on disk — the original
    length is not recoverable, and this reports it as unknown rather than
    pretending to know. Returns None when there is nothing to say.
    """
    text = entry.get("text") or ""
    if len(text) < MAX_TEXT_CHARS:
        return None
    return {
        "length": len(text),
        "limit": MAX_TEXT_CHARS,
        "dropped": None,          # unknown: the old store never recorded it
        "note": ("This entry was saved by an older version that cut text at "
                 f"{MAX_TEXT_CHARS:,} characters without saying so — its tail may "
                 "be missing. The original length was not recorded."),
    }


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
