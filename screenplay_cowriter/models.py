"""
Session data model. A Session is one screenplay's ongoing co-writer
conversation, persisted to disk as JSON (this is the "memory" — close the
terminal, come back tomorrow, `chat --resume <session_id>` picks up exactly
where you left off).

A Session holds multiple Branches (default: "main"). Forking copies the
current branch's message history into a new named branch and switches to
it — main stays untouched, and you can switch back or discard the fork.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict


@dataclass
class Message:
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    mode: str | None = None  # e.g. "evidence_discussion", "brainstorm", "persona:producer"
    scene_refs: list[int] = field(default_factory=list)  # scenes pulled into context for this turn
    quote: dict | None = None  # select-to-reply: {"scene_number": int, "text": str}

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Message":
        return Message(
            role=d["role"], content=d["content"], timestamp=d.get("timestamp", time.time()),
            mode=d.get("mode"), scene_refs=d.get("scene_refs", []),
            quote=d.get("quote"),
        )


@dataclass
class Branch:
    name: str
    messages: list[Message] = field(default_factory=list)
    parent_branch: str | None = None
    forked_at_index: int | None = None  # index into parent's messages at fork time
    active_persona: str = "writing_partner"
    active_mode: str = "peer"
    awaiting_probe: bool = False  # two-phase turn: writer is mid-probe (no suggestions yet)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "messages": [m.to_dict() for m in self.messages],
            "parent_branch": self.parent_branch,
            "forked_at_index": self.forked_at_index,
            "active_persona": self.active_persona,
            "active_mode": self.active_mode,
            "awaiting_probe": self.awaiting_probe,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(d: dict) -> "Branch":
        b = Branch(
            name=d["name"], parent_branch=d.get("parent_branch"),
            forked_at_index=d.get("forked_at_index"),
            active_persona=d.get("active_persona", "writing_partner"),
            active_mode=d.get("active_mode", "peer"),
            awaiting_probe=d.get("awaiting_probe", False),
            created_at=d.get("created_at", time.time()),
        )
        b.messages = [Message.from_dict(m) for m in d.get("messages", [])]
        return b


@dataclass
class Session:
    session_id: str
    title: str
    report_path: str | None = None      # Piece 2 output (findings.json) — optional
    script_path: str | None = None      # Piece 1 output (ScriptDocument json) — optional but recommended
    server_url: str | None = None
    model_id: str | None = None
    # Idea-room diff baseline: the page content as Sameer last READ it. Set
    # after each successful turn; the next turn's prompt carries a
    # deterministic ADDED/REMOVED note for anything the writer changed since.
    # None = he hasn't read a page yet (first summon).
    last_seen_content: str | None = None
    branches: dict[str, Branch] = field(default_factory=dict)
    current_branch: str = "main"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if "main" not in self.branches:
            self.branches["main"] = Branch(name="main")

    @property
    def branch(self) -> Branch:
        return self.branches[self.current_branch]

    def fork(self, new_name: str, from_branch: str | None = None) -> Branch:
        if new_name in self.branches:
            raise ValueError(f"Branch '{new_name}' already exists.")
        source = self.branches[from_branch or self.current_branch]
        new_branch = Branch(
            name=new_name,
            messages=[Message.from_dict(m.to_dict()) for m in source.messages],  # deep copy
            parent_branch=source.name,
            forked_at_index=len(source.messages),
            active_persona=source.active_persona,
            active_mode=source.active_mode,
        )
        self.branches[new_name] = new_branch
        self.current_branch = new_name
        return new_branch

    def switch(self, name: str) -> Branch:
        if name not in self.branches:
            raise ValueError(f"No such branch '{name}'. Known: {list(self.branches.keys())}")
        self.current_branch = name
        return self.branches[name]

    def delete_branch(self, name: str) -> None:
        if name == "main":
            raise ValueError("Can't delete the main branch.")
        if name not in self.branches:
            raise ValueError(f"No such branch '{name}'.")
        del self.branches[name]
        if self.current_branch == name:
            self.current_branch = "main"

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "report_path": self.report_path,
            "script_path": self.script_path,
            "server_url": self.server_url,
            "model_id": self.model_id,
            "last_seen_content": self.last_seen_content,
            "branches": {k: v.to_dict() for k, v in self.branches.items()},
            "current_branch": self.current_branch,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(d: dict) -> "Session":
        s = Session(
            session_id=d["session_id"], title=d.get("title", "Untitled"),
            report_path=d.get("report_path"), script_path=d.get("script_path"),
            server_url=d.get("server_url"), model_id=d.get("model_id"),
            last_seen_content=d.get("last_seen_content"),
            current_branch=d.get("current_branch", "main"),
            created_at=d.get("created_at", time.time()), updated_at=d.get("updated_at", time.time()),
            branches={},
        )
        s.branches = {k: Branch.from_dict(v) for k, v in d.get("branches", {}).items()}
        if "main" not in s.branches:
            s.branches["main"] = Branch(name="main")
        return s

    def save(self, path: str) -> None:
        self.updated_at = time.time()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @staticmethod
    def load(path: str) -> "Session":
        with open(path, "r", encoding="utf-8") as f:
            return Session.from_dict(json.load(f))

    @staticmethod
    def new(title: str, report_path: str | None = None, script_path: str | None = None) -> "Session":
        return Session(session_id=str(uuid.uuid4())[:8], title=title, report_path=report_path, script_path=script_path)
