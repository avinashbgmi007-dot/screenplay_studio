"""Idea room — scriptless story-development sessions.

An idea is a small sibling of a project: a directory under PROJECTS_DIR/ideas/
holding `idea.json` (the premise card) and `sessions/` (a SessionStore). No
parse, no analysis — the material is the conversation and the card.

Ideas graduate into real projects: upload the first pages, and the premise
card is copied into the project as `premise.json` while the idea's session
files are carried into the project's sessions dir, so the same Sam, the same
memory, and the same thread continue on the script desk.

This module stays independent of the cowriter package (which the webapp loads
lazily) — it only manages the card JSON; sessions are handled by the webapp
through the existing SessionStore, mirroring how projects work.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid

from .jsonio import atomic_write_json, check_safe_id, damage_envelope, last_known_facts, lock_for, retry_permission

EMPTY_CARD = {"title": "", "logline": "", "premise": "", "questions": []}

# The idea page is a blank canvas, not a form: free-form `content` is the
# primary material. The structured card stays for the (hidden) structure
# view and backward-compat; `auto_title` means the shelf title follows the
# page's first line until the writer renames it by hand.
MAX_AUTO_TITLE_LEN = 48
_ID_CREATE_ATTEMPTS = 32


def _new_idea_id() -> str:
    """A long UUID candidate; `create` still claims it exclusively."""
    return uuid.uuid4().hex


class IdeaStore:
    def __init__(self, ideas_dir: str):
        self.ideas_dir = ideas_dir
        os.makedirs(self.ideas_dir, exist_ok=True)

    # ---- paths ----

    def _dir(self, idea_id: str) -> str:
        check_safe_id(idea_id, "idea id")
        return os.path.join(self.ideas_dir, idea_id)

    def _meta_path(self, idea_id: str) -> str:
        return os.path.join(self._dir(idea_id), "idea.json")

    def sessions_dir(self, idea_id: str) -> str:
        d = os.path.join(self._dir(idea_id), "sessions")
        os.makedirs(d, exist_ok=True)
        return d

    # ---- CRUD ----

    def create(self, title: str = "Untitled idea") -> dict:
        for _ in range(_ID_CREATE_ATTEMPTS):
            idea_id = _new_idea_id()
            idea_dir = self._dir(idea_id)
            try:
                # mkdir without exist_ok is the atomic identity claim. A check
                # followed by makedirs(exist_ok=True) lets a collision write into
                # an existing writer-owned idea directory.
                os.mkdir(idea_dir)
            except FileExistsError:
                continue

            meta = {
                "id": idea_id,
                "title": title or "Untitled idea",
                "created_at": time.time(),
                "updated_at": time.time(),
                "card": dict(EMPTY_CARD),
                "content": "",
                "auto_title": True,
            }
            self._write(idea_id, meta)
            return meta
        raise RuntimeError(
            f"Could not allocate a unique idea id after {_ID_CREATE_ATTEMPTS} attempts.")

    def load(self, idea_id: str) -> dict:
        # reader-side bounded retry: a concurrent tmp+os.replace can make the
        # open raise a Windows sharing violation (WinError 32 ->
        # PermissionError) — GETs must outlast the writer, never 500.
        from .jsonio import retry_permission
        return retry_permission(lambda: self._read_meta_raw(idea_id))

    def _read_meta_raw(self, idea_id: str) -> dict:
        """Read idea.json through the shared store reader (gap 70).

        This used to be a bare `json.load`, so a truncated file surfaced as
        `JSONDecodeError` — a ValueError — which the app's error handling turned
        into **400 "Expecting ',' delimiter"**: the writer's own page reported as
        if their request were malformed. Every other writer-owned store answers
        damage as damage (503 `unreadable`), and the project side handles the
        same corruption that way, so this was the one store that told the writer
        their data was a bad request.

        `load_json_store` gives the contract the rest of the package already
        keeps: MISSING -> default (the caller turns that into 404), PRESENT-BUT-
        UNREADABLE -> `StoreUnreadable`, which the app's handler answers as 503
        with the byte-level reason. Shape is checked here, because a dict store
        handed a list is just as damaged as a torn file.
        """
        from .jsonio import StoreUnreadable, load_json_store

        meta = retry_permission(
            lambda: load_json_store(self._meta_path(idea_id), default=None))
        if meta is None:
            # Missing is missing: the routes already answer 404 for it, and
            # `list()` relies on the exception to flag a dir with no meta file.
            with open(self._meta_path(idea_id), "r", encoding="utf-8") as f:
                return json.load(f)
        if not isinstance(meta, dict):
            raise StoreUnreadable(
                self._meta_path(idea_id),
                f"expected a JSON object, found {type(meta).__name__}")
        return meta

    def raw_meta_text(self, idea_id: str) -> str:
        """The idea file exactly as it sits on disk, damage and all (gap 70).

        Recovery needs the BYTES, not a parsed view: the whole point is that the
        file cannot be parsed. Returned verbatim and never repaired here — the
        writer (or a support person) decides what to salvage, and this function
        must not become the thing that overwrites the only copy.
        """
        with open(self._meta_path(idea_id), "r", encoding="utf-8",
                  errors="replace") as f:
            return f.read()

    def repair_meta(self, idea_id: str, text: str) -> dict:
        """Replace a damaged file with text the writer chose, keeping the old one.

        The damaged original is moved aside first — `<idea>.json.damaged-<ts>` —
        so a repair is never the act that destroys the evidence. It is only
        allowed when the file really is unreadable: a readable idea is edited
        through the normal paths, and using this to overwrite one would be a
        silent bypass of every merge rule in this module.
        """
        from .jsonio import StoreUnreadable
        path = self._meta_path(idea_id)
        try:
            self._read_meta_raw(idea_id)
        except StoreUnreadable:
            pass
        else:
            raise ValueError(
                "This idea file is readable, so it does not need repairing. "
                "Edit it normally instead.")
        try:
            parsed = json.loads(text or "")
        except ValueError as e:
            raise ValueError(f"That text is not valid JSON yet: {e}")
        if not isinstance(parsed, dict):
            raise ValueError("An idea file has to be a JSON object.")
        kept = f"{path}.damaged-{int(time.time())}"
        retry_permission(lambda: shutil.move(path, kept))
        atomic_write_json(path, parsed)
        parsed["repaired_from"] = os.path.basename(kept)
        return parsed

    def _write(self, idea_id: str, meta: dict) -> None:
        meta["updated_at"] = time.time()
        atomic_write_json(self._meta_path(idea_id), meta)

    def _modify(self, idea_id: str, fn) -> dict:
        """Locked load-modify-write of idea.json. rename/save_card/save_content
        all merge into the STORED meta under the per-path lock, so a racing
        save can't clobber fields the writer didn't send (the lost-update the
        ideas race test asserts: rename loading stale content and writing it
        back over a just-saved page)."""
        with lock_for(self._meta_path(idea_id)):
            meta = self.load(idea_id)
            fn(meta)
            self._write(idea_id, meta)
        return meta

    @staticmethod
    def auto_title_from(content: str) -> str:
        """The working title grows out of the page: the first non-empty line,
        stripped of markdown decoration, truncated. Empty page -> Untitled."""
        for line in (content or "").splitlines():
            line = line.strip().lstrip("#*- ").strip()
            if line:
                return line[:MAX_AUTO_TITLE_LEN].rstrip() or "Untitled idea"
        return "Untitled idea"

    def save_content(self, idea_id: str, content: str) -> dict:
        """Save the free-form page. While the title is auto (the writer hasn't
        renamed by hand), the shelf title follows the page's first line and
        the card's working title stays in sync so the chat sees it."""
        def apply(meta):
            meta["content"] = content or ""
            if meta.get("auto_title", True):
                meta["title"] = self.auto_title_from(meta["content"])
                card = dict(meta.get("card") or EMPTY_CARD)
                card["title"] = meta["title"]
                meta["card"] = card
        return self._modify(idea_id, apply)

    def rename(self, idea_id: str, title: str) -> dict:
        """A deliberate rename — from here the title is the writer's, and the
        page's first line stops overriding it."""
        def apply(meta):
            meta["title"] = (title or "").strip() or "Untitled idea"
            meta["auto_title"] = False
            card = dict(meta.get("card") or EMPTY_CARD)
            card["title"] = meta["title"]
            meta["card"] = card
        return self._modify(idea_id, apply)

    def save_card(self, idea_id: str, card: dict) -> dict:
        """Merge the incoming card fields into the stored card (partial saves
        never wipe fields the client didn't send), and keep the shelf title in
        sync with the card's working title when one is set."""
        incoming = card or {}

        def apply(meta):
            stored = dict(meta.get("card") or EMPTY_CARD)
            for key in ("title", "logline", "premise", "questions"):
                if key in incoming:
                    stored[key] = incoming[key]
            stored["questions"] = [q for q in (stored.get("questions") or []) if str(q).strip()]
            meta["card"] = stored
            if (stored.get("title") or "").strip():
                meta["title"] = stored["title"].strip()

        return self._modify(idea_id, apply)

    def list(self) -> list[dict]:
        out = []
        if not os.path.isdir(self.ideas_dir):
            return out
        for name in sorted(os.listdir(self.ideas_dir)):
            try:
                out.append(self.load(name))
            except Exception as e:
                # Flag, don't drop: a corrupt/unreadable idea must still show
                # on the shelf so the writer knows it exists.
                #
                # Gap 82: through the SHARED damage envelope, so the shelf row says
                # whether the idea can be rescued, why it failed, and what the file
                # last looked like — the same three things the project shelf says.
                # `recoverable` is honest here: `recover_idea` hands back the raw
                # bytes of whatever is on disk, and `repair_idea` can rebuild from
                # a source-only folder, so a directory that exists is recoverable.
                meta_path = os.path.join(self._dir(name), "idea.json")
                out.append(damage_envelope(
                    "idea", name,
                    detail=f"{type(e).__name__}: {e}",
                    recoverable=os.path.isdir(self._dir(name)),
                    last_known=last_known_facts(meta_path),
                    created_at=0, updated_at=0,
                ))
        out.sort(key=lambda m: m.get("updated_at", 0), reverse=True)
        return out

    def delete(self, idea_id: str) -> None:
        # Same Windows race as the project shelf (see delete_project): an open
        # handle on any file inside makes os.unlink fail, and rmtree deletes as
        # it walks, so an unretried failure leaves the idea PARTLY removed.
        retry_permission(lambda: shutil.rmtree(self._dir(idea_id)))

    # ---- graduation ----

    def carry_into_project(self, idea_id: str, project_dir: str) -> None:
        """Copy the premise card and the idea's conversation into a real
        project so the thread survives the move to the script desk."""
        meta = self.load(idea_id)
        card = dict(meta.get("card") or EMPTY_CARD)
        # the blank page is the primary material — carry it too, so the script
        # desk keeps the notes the idea grew from
        card["content"] = meta.get("content") or ""
        # A3 (2026-09-20): atomic like every other writer-owned store — a torn
        # premise.json used to read back as "no card" and silently lose the
        # writer's logline/premise on graduation.
        atomic_write_json(os.path.join(project_dir, "premise.json"), card)
        src = self.sessions_dir(idea_id)
        dst = os.path.join(project_dir, "sessions")
        os.makedirs(dst, exist_ok=True)
        for fn in os.listdir(src):
            if fn.endswith(".json"):
                shutil.copy2(os.path.join(src, fn), os.path.join(dst, fn))
