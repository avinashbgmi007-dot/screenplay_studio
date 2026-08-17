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

EMPTY_CARD = {"title": "", "logline": "", "premise": "", "questions": []}

# The idea page is a blank canvas, not a form: free-form `content` is the
# primary material. The structured card stays for the (hidden) structure
# view and backward-compat; `auto_title` means the shelf title follows the
# page's first line until the writer renames it by hand.
MAX_AUTO_TITLE_LEN = 48


class IdeaStore:
    def __init__(self, ideas_dir: str):
        self.ideas_dir = ideas_dir
        os.makedirs(self.ideas_dir, exist_ok=True)

    # ---- paths ----

    def _dir(self, idea_id: str) -> str:
        return os.path.join(self.ideas_dir, idea_id)

    def _meta_path(self, idea_id: str) -> str:
        return os.path.join(self._dir(idea_id), "idea.json")

    def sessions_dir(self, idea_id: str) -> str:
        d = os.path.join(self._dir(idea_id), "sessions")
        os.makedirs(d, exist_ok=True)
        return d

    # ---- CRUD ----

    def create(self, title: str = "Untitled idea") -> dict:
        idea_id = uuid.uuid4().hex[:8]
        os.makedirs(self._dir(idea_id), exist_ok=True)
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

    def load(self, idea_id: str) -> dict:
        with open(self._meta_path(idea_id), "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, idea_id: str, meta: dict) -> None:
        meta["updated_at"] = time.time()
        with open(self._meta_path(idea_id), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

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
        meta = self.load(idea_id)
        meta["content"] = content or ""
        if meta.get("auto_title", True):
            meta["title"] = self.auto_title_from(meta["content"])
            card = dict(meta.get("card") or EMPTY_CARD)
            card["title"] = meta["title"]
            meta["card"] = card
        self._write(idea_id, meta)
        return meta

    def rename(self, idea_id: str, title: str) -> dict:
        """A deliberate rename — from here the title is the writer's, and the
        page's first line stops overriding it."""
        meta = self.load(idea_id)
        meta["title"] = (title or "").strip() or "Untitled idea"
        meta["auto_title"] = False
        card = dict(meta.get("card") or EMPTY_CARD)
        card["title"] = meta["title"]
        meta["card"] = card
        self._write(idea_id, meta)
        return meta

    def save_card(self, idea_id: str, card: dict) -> dict:
        """Merge the incoming card fields into the stored card (partial saves
        never wipe fields the client didn't send), and keep the shelf title in
        sync with the card's working title when one is set."""
        meta = self.load(idea_id)
        card = card or {}
        stored = dict(meta.get("card") or EMPTY_CARD)
        for key in ("title", "logline", "premise", "questions"):
            if key in card:
                stored[key] = card[key]
        stored["questions"] = [q for q in (stored.get("questions") or []) if str(q).strip()]
        meta["card"] = stored
        if (stored.get("title") or "").strip():
            meta["title"] = stored["title"].strip()
        self._write(idea_id, meta)
        return meta

    def list(self) -> list[dict]:
        out = []
        if not os.path.isdir(self.ideas_dir):
            return out
        for name in sorted(os.listdir(self.ideas_dir)):
            try:
                out.append(self.load(name))
            except Exception:
                continue
        out.sort(key=lambda m: m.get("updated_at", 0), reverse=True)
        return out

    def delete(self, idea_id: str) -> None:
        shutil.rmtree(self._dir(idea_id), ignore_errors=True)

    # ---- graduation ----

    def carry_into_project(self, idea_id: str, project_dir: str) -> None:
        """Copy the premise card and the idea's conversation into a real
        project so the thread survives the move to the script desk."""
        meta = self.load(idea_id)
        card = dict(meta.get("card") or EMPTY_CARD)
        # the blank page is the primary material — carry it too, so the script
        # desk keeps the notes the idea grew from
        card["content"] = meta.get("content") or ""
        with open(os.path.join(project_dir, "premise.json"), "w", encoding="utf-8") as f:
            json.dump(card, f, ensure_ascii=False, indent=2)
        src = self.sessions_dir(idea_id)
        dst = os.path.join(project_dir, "sessions")
        os.makedirs(dst, exist_ok=True)
        for fn in os.listdir(src):
            if fn.endswith(".json"):
                shutil.copy2(os.path.join(src, fn), os.path.join(dst, fn))
