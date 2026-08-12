"""
Watch-folder / batch processing.

Drop a screenplay into the watched directory and it gets parsed, analyzed,
and reported automatically — no CLI invocation per file. The source file is
moved to <watch>/done/ once processed, so a drop is fire-and-forget.

process_pending() is the testable one-shot worker; watch_loop() wraps it in
a polling loop for the `screenplay_studio watch` CLI command.
"""

from __future__ import annotations

import os
import shutil
import time

from .manifest import ProjectManifest
from .orchestrator import Orchestrator, OrchestratorError

SUPPORTED_EXTENSIONS = {".fdx", ".fountain", ".txt", ".md", ".pdf"}


def _is_supported(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in SUPPORTED_EXTENSIONS and not name.startswith(".")


def _safe_project_name(filename: str) -> str:
    stem = os.path.splitext(filename)[0]
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem) or "project"
    return safe


def process_pending(watch_dir: str, projects_dir: str, server_url: str,
                    model: str = None, categories: tuple = None, report_language: str = "eng",
                    move_done: bool = True) -> list[dict]:
    """Process every unprocessed screenplay in watch_dir once.

    Returns a list of per-file results: {filename, ok, project, error}.
    """
    os.makedirs(projects_dir, exist_ok=True)
    results = []
    for name in sorted(os.listdir(watch_dir)):
        path = os.path.join(watch_dir, name)
        if not os.path.isfile(path) or not _is_supported(name):
            continue

        result = {"filename": name, "ok": False, "project": None, "error": None}
        project_dir = os.path.join(projects_dir, _safe_project_name(name))
        suffix = 1
        while os.path.exists(project_dir):
            suffix += 1
            project_dir = os.path.join(projects_dir, f"{_safe_project_name(name)}_{suffix}")

        try:
            manifest = ProjectManifest.create(project_dir, path, title=_safe_project_name(name))
            manifest.server_url = server_url
            manifest.model_id = model
            manifest.save()

            orch = Orchestrator(manifest)
            orch.run_parse()
            orch.run_analyze(categories=categories, report_language=report_language)
            result["ok"] = True
            result["project"] = os.path.basename(project_dir)
        except (OrchestratorError, Exception) as e:
            result["error"] = str(e)

        if move_done and (result["ok"] or result["error"]):
            done_dir = os.path.join(watch_dir, "done")
            os.makedirs(done_dir, exist_ok=True)
            shutil.move(path, os.path.join(done_dir, name))

        results.append(result)
    return results


def watch_loop(watch_dir: str, projects_dir: str, server_url: str,
               poll_interval: int = 5, model: str = None, categories: tuple = None,
               report_language: str = "eng") -> None:
    """Poll the watch dir forever, processing new screenplays as they appear."""
    os.makedirs(watch_dir, exist_ok=True)
    print(f"Watching {os.path.abspath(watch_dir)} for screenplays…")
    print(f"Projects → {os.path.abspath(projects_dir)}  (processed files move to {watch_dir}/done/)")
    print("Ctrl+C to stop.\n")
    while True:
        results = process_pending(watch_dir, projects_dir, server_url, model=model, categories=categories,
                                  report_language=report_language)
        for r in results:
            status = "✓" if r["ok"] else "✗"
            print(f"{status} {r['filename']} → {r['project'] or r['error']}")
        time.sleep(poll_interval)
