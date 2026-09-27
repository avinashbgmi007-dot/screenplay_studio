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

import copy
import os
import shutil
import time
from dataclasses import dataclass, field, asdict


def _merge_manifest(baseline: dict, desired: dict, on_disk: dict) -> dict:
    """Fold what this writer changed into the document that is on disk now.

    `baseline` is the document this object was read from (or last wrote), so
    `desired` differs from it only where this writer made a change. Everything
    else is taken from disk — that is the whole point: an in-flight analyze must
    not be able to resurrect a setting or a stage a newer writer already moved.
    Stages merge per stage name so two runners stamping two different stages
    each keep their own.
    """
    out = dict(on_disk)
    disk_stages = on_disk.get("stages") or {}
    baseline_stages = baseline.get("stages") or {}
    stages = dict(disk_stages)
    for name, value in (desired.get("stages") or {}).items():
        if baseline_stages.get(name) != value or name not in disk_stages:
            stages[name] = value
    out["stages"] = stages
    for key, value in desired.items():
        if key == "stages":
            continue
        if baseline.get(key) != value:
            out[key] = value
    return out


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
    fast_model: str = None  # optional cheap tier: summaries/refresh route here
    timeout: int = 600
    # Bearer token for a remote OpenAI-compatible endpoint; None for a local
    # llama-server, which authenticates nothing. It rides in the manifest for
    # the same reason server_url does — so `resume` and the CLI can reach the
    # same model without the writer re-typing it — and it lives in the writer's
    # own project directory, the same trust boundary as the script itself.
    api_key: str = None
    stages: dict = field(default_factory=lambda: {
        "parse": StageStatus(), "analyze": StageStatus(), "chat": StageStatus(),
    })
    cowriter_session_id: str = None
    drafts: list = field(default_factory=list)  # [{name, source_filename, uploaded_at}] — uploaded drafts
    active_draft: str = None  # None => the original first upload is active
    report_language: str = "eng"  # language of the analysis report: eng | tenglish | hindi | telugu | tamil
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    # The document this object was read from (or last wrote), used by `save()` to
    # tell "a field I changed" from "a field I never looked at". Not persisted:
    # `to_dict()` is explicit about what a manifest is.
    _baseline: dict = field(default_factory=dict, repr=False, compare=False)

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

    def to_dict(self) -> dict:
        return {
            "project_dir": self.project_dir,
            "title": self.title,
            "source_filename": self.source_filename,
            "source_format": self.source_format,
            "server_url": self.server_url,
            "model_id": self.model_id,
            "fast_model": self.fast_model,
            "timeout": self.timeout,
            "api_key": self.api_key,
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
            fast_model=d.get("fast_model"),
            timeout=d.get("timeout", 600),
            api_key=d.get("api_key"),
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
        # Every path that reads a manifest from disk goes through here, so this
        # is where a writer learns what it is allowed to overwrite.
        m._baseline = copy.deepcopy(d)
        return m

    def save(self) -> None:
        """Write the manifest without reverting a field this writer never touched.

        A manifest is held for as long as the work it describes — an analyze run
        owns one for minutes — and `save()` used to write that whole in-memory
        copy back. So a run that started before a re-parse reset `parse`, or
        before the writer changed a setting in another window, stamped the newer
        value out of existence. Measured across four real processes: three of
        four writers' stage entries never reached the file.

        The fix is to merge, not to hold the lock longer. `lock_for` covers the
        read-modify-write, and the write is what changed since this object was
        read (per stage name, so two runners stamping two stages do not fight).
        Holding the lock across the analyze instead would block every status poll
        the desk makes for the length of a model run.

        `drafts` is merged as a whole list: two processes appending a draft in
        the same instant can still lose one. Upload is a short cycle and reloads
        per request, so it is the one field where that window is negligible.
        """
        from .jsonio import atomic_write_json, load_json_store, lock_for
        self.updated_at = time.time()
        os.makedirs(self.project_dir, exist_ok=True)
        desired = self.to_dict()
        with lock_for(self.manifest_path):
            out = desired
            if self._baseline:
                # `assume_present` for the same reason as WriterMemory.save: this
                # block holds the lock, and a peer that created project.json a
                # microsecond ago must not be answered "missing" — that reads
                # here as "nothing to merge into", i.e. write the stale snapshot.
                on_disk = load_json_store(self.manifest_path, None, assume_present=True)
                if isinstance(on_disk, dict):
                    out = _merge_manifest(self._baseline, desired, on_disk)
            atomic_write_json(self.manifest_path, out)
        # Whatever is now on disk is this object's reference point: a field we
        # did not own keeps the other writer's value without us "changing" it
        # back on the next save.
        self._baseline = copy.deepcopy(out)

    @staticmethod
    def load(project_dir: str) -> "ProjectManifest":
        from .jsonio import StoreUnreadable, load_json_store
        path = os.path.join(project_dir, "project.json")
        if not os.path.exists(path):
            raise FileNotFoundError(f"No project found at '{project_dir}' (no project.json).")
        # The shared store reader, so a damaged manifest is DAMAGE (StoreUnreadable
        # -> HTTP 503) rather than a JSONDecodeError riding the generic 400
        # handler — which told the writer their request was bad about a file they
        # never sent. It also reads under the store lock, with the transient
        # Windows sharing-violation retry, instead of through a bare `open`.
        data = load_json_store(path, None)
        if data is None:
            raise FileNotFoundError(f"No project found at '{project_dir}' (no project.json).")
        if not isinstance(data, dict):
            raise StoreUnreadable(path, f"expected an object, got {type(data).__name__}")
        m = ProjectManifest.from_dict(data)
        # The caller resolved `project_dir` for THIS launch (the CLI's `--project`,
        # or `_project_dir(name)` under the running server's `--projects-dir`); the
        # string inside project.json is a record of where the project was created,
        # which is not an instruction to a different process. Honoring it moved every
        # artifact path — and `save()`'s `os.makedirs` — out of the tree the operator
        # pointed at: an analyze run against a COPY of a project rewrote the original,
        # because the copy still said `"project_dir": "./studio_projects\\<name>"` and
        # that resolves against the launcher's CWD, not the server's projects dir.
        # 21 of 22 projects on disk store such a relative path, so this was the normal
        # case. `save()` then writes the resolved directory back, repairing the record.
        m.project_dir = project_dir
        return m

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
