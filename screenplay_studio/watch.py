"""
Watch-folder / batch processing.

Drop a screenplay into the watched directory and it gets parsed, analyzed,
and reported automatically — no CLI invocation per file. The source file is
moved to <watch>/done/ once processed, so a drop is fire-and-forget.

process_pending() is the testable one-shot worker; watch_loop() wraps it in
a polling loop for the `screenplay_studio watch` CLI command.

Gap 16 — the guarantee this module now keeps, because it did not:

* **A drop is never destroyed.** Files are filed into `done/` under a
  COLLISION-SAFE name: a second `draft.fountain` becomes `draft_2.fountain`
  rather than replacing the first. The old code moved to the unchanged
  filename, so two different scripts with the same name left one file — the
  earlier one gone.
* **A failed drop is never called done.** The old code moved the source on
  `ok OR error`, so a script whose project copy failed (disk full, permission,
  a manifest that never became durable) was cleared from the inbox and filed
  under `done/` — marked complete while no project existed anywhere. Failures
  now go to `failed/`, beside a `<name>.error.txt` that says what happened.
  Nothing is retried automatically (a permanent error must not spin), and the
  way to retry is to move the file back into the inbox.
* **Only one worker can own a drop.** Each file is claimed by an atomic
  rename into `<watch>/.processing/<claim-id>/` before any work starts, so two
  watchers (or two polls racing a restart) cannot both process it, and a crash
  mid-run leaves the script in `.processing/` — visible, not lost.
"""

from __future__ import annotations

import os
import shutil
import time
import uuid

from .manifest import ProjectManifest
from .orchestrator import Orchestrator

SUPPORTED_EXTENSIONS = {".fdx", ".fountain", ".txt", ".md", ".pdf"}


def _is_supported(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in SUPPORTED_EXTENSIONS and not name.startswith(".")


def _safe_project_name(filename: str) -> str:
    stem = os.path.splitext(filename)[0]
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem) or "project"
    return safe


CLAIM_DIR = ".processing"


def _reserve(target_dir: str, name: str) -> str:
    """Reserve a free path for `name` inside `target_dir` and return it.

    The reservation is an `O_CREAT|O_EXCL` create, so two workers racing for the
    same name cannot both win it: the loser moves on to `stem_2.ext` instead of
    overwriting the winner's file. This is what makes filing a drop no-clobber —
    the old `shutil.move(path, os.path.join(done_dir, name))` reused the
    filename, so the second `draft.fountain` silently replaced the first.
    """
    os.makedirs(target_dir, exist_ok=True)
    stem, ext = os.path.splitext(name)
    candidate = os.path.join(target_dir, name)
    n = 1
    while True:
        try:
            fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            n += 1
            candidate = os.path.join(target_dir, f"{stem}_{n}{ext}")
            continue
        os.close(fd)
        return candidate


def _file_into(src: str, target_dir: str, name: str) -> str:
    """Move `src` into `target_dir` under a collision-safe name. Returns the path.

    If the move itself fails the reserved (empty) placeholder is removed, so a
    failed filing never leaves a zero-byte `done/` entry that looks like a
    processed script.
    """
    dest = _reserve(target_dir, name)
    try:
        shutil.move(src, dest)
    except Exception:
        try:
            os.unlink(dest)
        except OSError:
            pass
        raise
    return dest


def _claim(path: str, watch_dir: str):
    """Atomically take ownership of one inbox file.

    Returns `(claimed_path, claim_dir, source_name)` or `(None, None, None)` when
    another worker got there first. The rename is atomic on one filesystem, so
    exactly one worker can succeed; the loser sees FileNotFoundError and skips
    the file rather than processing it a second time.
    """
    claim_dir = os.path.join(watch_dir, CLAIM_DIR, uuid.uuid4().hex)
    os.makedirs(claim_dir, exist_ok=True)
    target = os.path.join(claim_dir, os.path.basename(path))
    try:
        os.replace(path, target)
    except OSError:
        shutil.rmtree(claim_dir, ignore_errors=True)
        return None, None, None
    return target, claim_dir, os.path.basename(path)


def _write_failure_note(failed_path: str, error: str) -> None:
    """Record WHY a drop failed, beside it. Best-effort: the source matters more."""
    try:
        with open(failed_path + ".error.txt", "w", encoding="utf-8") as f:
            f.write(error + "\n\nThe source file is untouched next to this note. "
                    "Move it back into the watch folder to retry.\n")
    except OSError:
        pass


def process_pending(watch_dir: str, projects_dir: str, server_url: str,
                    model: str = None, categories: tuple = None, report_language: str = "eng",
                    move_done: bool = True) -> list[dict]:
    """Process every unprocessed screenplay in watch_dir once.

    Returns a list of per-file results:
    {filename, ok, project, error, filed} — `filed` is where the source ended up
    (None when it stayed in the inbox), so a caller can report the truth instead
    of assuming every drop was archived.
    """
    os.makedirs(projects_dir, exist_ok=True)
    results = []
    for name in sorted(os.listdir(watch_dir)):
        path = os.path.join(watch_dir, name)
        if not os.path.isfile(path) or not _is_supported(name):
            continue

        # Claim before doing anything: from here on this file is ours, and a
        # second worker polling the same folder cannot start a parallel run.
        claimed, claim_dir, source_name = _claim(path, watch_dir)
        if claimed is None:
            continue        # another worker owns it — not our result to report

        result = {"filename": name, "ok": False, "project": None, "error": None, "filed": None}
        project_dir = os.path.join(projects_dir, _safe_project_name(name))
        suffix = 1
        while os.path.exists(project_dir):
            suffix += 1
            project_dir = os.path.join(projects_dir, f"{_safe_project_name(name)}_{suffix}")

        created_project = False
        try:
            manifest = ProjectManifest.create(project_dir, claimed, title=_safe_project_name(name))
            created_project = True
            manifest.server_url = server_url
            manifest.model_id = model
            manifest.save()

            orch = Orchestrator(manifest)
            orch.run_parse()
            orch.run_analyze(categories=categories, report_language=report_language)
            result["ok"] = True
            result["project"] = os.path.basename(project_dir)
        except Exception as e:      # noqa: BLE001 — one bad drop must not stop the batch
            result["error"] = str(e)
            # A project directory that never became usable is a phantom on the
            # shelf, not a copy the writer can open. The source is still in our
            # claim, so removing the partial copy loses nothing.
            if not created_project:
                shutil.rmtree(project_dir, ignore_errors=True)

        # ---- file the source, and never lie about why ----
        try:
            if not move_done:
                # The caller asked to leave drops where they are. Checked FIRST:
                # this is the "process in place" contract, and it applies to a
                # successful drop as much as a failed one. (Putting the success
                # branch first filed a `move_done=False` success into done/ and
                # the existing test caught it — the gate belongs at the top.)
                back = _file_into(claimed, watch_dir, source_name)
                result["filed"] = os.path.relpath(back, watch_dir)
            elif result["ok"]:
                filed = _file_into(claimed, os.path.join(watch_dir, "done"), source_name)
                result["filed"] = os.path.relpath(filed, watch_dir)
            else:
                # FAILED: preserved, never filed under done/.
                failed = _file_into(claimed, os.path.join(watch_dir, "failed"), source_name)
                _write_failure_note(failed, result["error"] or "unknown error")
                result["filed"] = os.path.relpath(failed, watch_dir)
        except Exception as e:      # noqa: BLE001 — filing is the last step, and must be reported
            result["error"] = (result["error"] + "; " if result["error"] else "") + \
                f"could not file the source: {e}"
            # The claim dir still holds the file — leave it there. It is in
            # .processing/, never deleted, and the message says where.
            if os.path.isdir(claim_dir):
                result["filed"] = os.path.relpath(claimed, watch_dir)
            results.append(result)
            continue

        shutil.rmtree(claim_dir, ignore_errors=True)
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
