"""
Project manifest — the thing that lets the orchestrator resume partway
through, skip stages that already succeeded, and retry just the stage that
failed instead of starting over.

Standard project directory layout:
    my_project/
      project.json          <- this manifest
      source.<ext>           <- copy of the original screenplay file
      parsed.json             <- Piece 1 output (ScriptDocument)
      parsed.kg.json           <- Piece 1 knowledge graph
      report.md                 <- Piece 2 human-readable report
      report.findings.json       <- Piece 2 structured findings
      sessions/                   <- Piece 3 session store
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field, asdict


@dataclass
class StageStatus:
    status: str = "pending"  # "pending" | "running" | "complete" | "failed" | "skipped"
    output_paths: dict = field(default_factory=dict)
    error: str = None
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "StageStatus":
        return StageStatus(
            status=d.get("status", "pending"),
            output_paths=d.get("output_paths", {}),
            error=d.get("error"),
            updated_at=d.get("updated_at", time.time()),
        )


@dataclass
class ProjectManifest:
    project_dir: str
    title: str
    source_filename: str
    source_format: str
    server_url: str = "http://localhost:8080"
    model_id: str = None
    timeout: int = 600
    stages: dict = field(default_factory=lambda: {
        "parse": StageStatus(), "analyze": StageStatus(), "chat": StageStatus(),
    })
    cowriter_session_id: str = None
    drafts: list = field(default_factory=list)  # [{name, source_filename, uploaded_at}] — uploaded drafts
    active_draft: str = None  # None => the original first upload is active
    report_language: str = "eng"  # language of the analysis report: eng | tenglish | hindi | tamil
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # ---- standard paths within the project directory ----
    @property
    def manifest_path(self) -> str:
        return os.path.join(self.project_dir, "project.json")

    @property
    def source_path(self) -> str:
        return os.path.join(self.project_dir, f"source{self.source_format_ext}")

    @property
    def source_format_ext(self) -> str:
        return self.source_format if self.source_format.startswith(".") else f".{self.source_format}"

    @property
    def parsed_path(self) -> str:
        return os.path.join(self.project_dir, "parsed.json")

    @property
    def kg_path(self) -> str:
        return os.path.join(self.project_dir, "parsed.kg.json")

    @property
    def report_md_path(self) -> str:
        return os.path.join(self.project_dir, "report.md")

    @property
    def report_findings_path(self) -> str:
        return os.path.join(self.project_dir, "report.findings.json")

    @property
    def sessions_dir(self) -> str:
        return os.path.join(self.project_dir, "sessions")

    @property
    def progress_path(self) -> str:
        """Live per-stage analysis progress (written by the analyzer's callback)."""
        return os.path.join(self.project_dir, "progress.json")

    def stage(self, name: str) -> StageStatus:
        if name not in self.stages:
            self.stages[name] = StageStatus()
        return self.stages[name]

    def mark_running(self, name: str):
        self.stages[name] = StageStatus(status="running")
        self.save()

    def mark_complete(self, name: str, output_paths: dict = None):
        self.stages[name] = StageStatus(status="complete", output_paths=output_paths or {})
        self.save()

    def mark_failed(self, name: str, error: str):
        self.stages[name] = StageStatus(status="failed", error=error)
        self.save()

    def mark_skipped(self, name: str):
        self.stages[name] = StageStatus(status="skipped")
        self.save()

    def to_dict(self) -> dict:
        return {
            "project_dir": self.project_dir,
            "title": self.title,
            "source_filename": self.source_filename,
            "source_format": self.source_format,
            "server_url": self.server_url,
            "model_id": self.model_id,
            "timeout": self.timeout,
            "stages": {k: v.to_dict() for k, v in self.stages.items()},
            "cowriter_session_id": self.cowriter_session_id,
            "drafts": self.drafts,
            "active_draft": self.active_draft,
            "report_language": self.report_language,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(d: dict) -> "ProjectManifest":
        m = ProjectManifest(
            project_dir=d["project_dir"], title=d["title"],
            source_filename=d["source_filename"], source_format=d["source_format"],
            server_url=d.get("server_url", "http://localhost:8080"),
            model_id=d.get("model_id"),
            timeout=d.get("timeout", 600),
            cowriter_session_id=d.get("cowriter_session_id"),
            drafts=d.get("drafts", []),
            active_draft=d.get("active_draft"),
            report_language=d.get("report_language", "eng"),
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at", time.time()),
            stages={},
        )
        m.stages = {k: StageStatus.from_dict(v) for k, v in d.get("stages", {}).items()}
        for name in ("parse", "analyze", "chat"):
            if name not in m.stages:
                m.stages[name] = StageStatus()
        return m

    def save(self) -> None:
        self.updated_at = time.time()
        os.makedirs(self.project_dir, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @staticmethod
    def load(project_dir: str) -> "ProjectManifest":
        path = os.path.join(project_dir, "project.json")
        if not os.path.exists(path):
            raise FileNotFoundError(f"No project found at '{project_dir}' (no project.json).")
        with open(path, "r", encoding="utf-8") as f:
            return ProjectManifest.from_dict(json.load(f))

    @staticmethod
    def create(project_dir: str, source_file: str, title: str = None) -> "ProjectManifest":
        os.makedirs(project_dir, exist_ok=True)
        ext = os.path.splitext(source_file)[1].lower()
        manifest = ProjectManifest(
            project_dir=project_dir,
            title=title or os.path.splitext(os.path.basename(source_file))[0],
            source_filename=os.path.basename(source_file),
            source_format=ext,
        )
        shutil.copy2(source_file, manifest.source_path)
        manifest.save()
        return manifest
