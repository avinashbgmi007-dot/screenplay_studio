"""
Watch-folder / batch processing.

Publish a screenplay into the watched directory and create a sibling
`<filename>.<extension>.ready` marker only after the producer has closed it.
The marker is the completion handshake; an unmarked file stays in the inbox.
After processing, the source is filed under <watch>/done/ or <watch>/failed/.

process_pending() is the testable one-shot worker; watch_loop() wraps it in
a polling loop for the `screenplay_studio watch` CLI command.

Gap 16 — the guarantee this module now keeps, because it did not:

* **A visible file is not assumed complete.** A producer must close and
  publish the source, then create `<filename>.<extension>.ready`. Unmarked
  sources remain untouched and are reported pending; a stable-size pause is not
  treated as proof that a slow upload has finished.
* **The claimed bytes stay the analyzed bytes.** The input is fingerprinted
  before work and again after analysis. If it changes despite the producer
  handshake, the partial project is removed and the complete source is filed
  under `failed/` for an explicit retry.
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

import hashlib
import os
import shutil
import stat
import time
import uuid

from .manifest import ProjectManifest
from .orchestrator import Orchestrator

SUPPORTED_EXTENSIONS = {".fdx", ".fountain", ".txt", ".md", ".pdf"}
READY_SUFFIX = ".ready"


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
            f.write(error + "\n\nThe source file is untouched and preserved next to this note. "
                    "After confirming it is complete, move it back into the watch "
                    "folder and recreate its .ready marker to retry.\n")
    except OSError:
        pass


def _ready_path(source_path: str) -> str:
    return source_path + READY_SUFFIX


def _is_linklike(path: str) -> bool:
    if os.path.islink(path):
        return True
    isjunction = getattr(os.path, "isjunction", None)
    if isjunction is not None:
        try:
            return bool(isjunction(path))
        except OSError:
            return True
    return False


def _ready_marker_state(source_path: str) -> tuple[bool, str | None]:
    """A marker must be a regular sibling file, never a symlink/reparse point."""
    marker = _ready_path(source_path)
    if _is_linklike(marker):
        return False, "completion marker is a symlink or junction; it was not followed"
    try:
        info = os.stat(marker, follow_symlinks=False)
    except FileNotFoundError:
        return False, "waiting for a .ready completion marker; source remains in the inbox"
    except OSError as e:
        return False, f"completion marker could not be checked: {e}"
    if not stat.S_ISREG(info.st_mode):
        return False, "completion marker must be a regular file"
    return True, None


def _source_fingerprint(path: str) -> tuple:
    """Hash a source while checking its identity and metadata stayed stable."""
    def signature(info):
        return (info.st_dev, info.st_ino, info.st_size,
                getattr(info, "st_mtime_ns", int(info.st_mtime * 1e9)),
                getattr(info, "st_ctime_ns", int(info.st_ctime * 1e9)))

    before = os.stat(path)
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    after = os.stat(path)
    before_sig, after_sig = signature(before), signature(after)
    if before_sig != after_sig:
        raise RuntimeError("source changed while its completion state was being verified")
    return (*after_sig, digest.hexdigest())


def _pending_result(filename: str, error: str) -> dict:
    return {"filename": filename, "ok": False, "pending": True,
            "project": None, "error": error, "filed": None}


def process_pending(watch_dir: str, projects_dir: str, server_url: str,
                    model: str = None, categories: tuple = None, report_language: str = "eng",
                    move_done: bool = True) -> list[dict]:
    """Process inputs explicitly published with a sibling `.ready` marker.

    Unmarked supported files are reported as pending and left byte-for-byte in
    the inbox. The producer creates the marker only after closing/publishing the
    source (prefer a same-filesystem atomic rename from a temporary suffix).
    Returns per-file results with `pending` distinguishing "not ready yet" from
    a processing failure.
    """
    os.makedirs(projects_dir, exist_ok=True)
    results = []
    for name in sorted(os.listdir(watch_dir)):
        path = os.path.join(watch_dir, name)
        if not _is_supported(name):
            continue
        if _is_linklike(path):
            results.append(_pending_result(name, "source is a symlink or junction; it was not followed"))
            continue
        if not os.path.isfile(path):
            continue

        ready, reason = _ready_marker_state(path)
        if not ready:
            results.append(_pending_result(name, reason or "completion marker unavailable"))
            continue

        # Claim source first, then claim its marker into the same private folder.
        # A racing worker can win only one source rename; a marker race restores
        # the source to the inbox instead of processing without producer consent.
        claimed, claim_dir, source_name = _claim(path, watch_dir)
        if claimed is None:
            # A competing worker may have won, or the OS may refuse to rename
            # a still-open producer file (notably on some Windows setups). Only
            # report pending if the source is still here; never double-report a
            # successful competing claim.
            if os.path.isfile(path):
                claim_reason = _ready_marker_state(path)[1]
                results.append(_pending_result(
                    name, claim_reason or
                    "source could not be claimed; it may still be open or another worker may own it"))
            continue
        marker_path = _ready_path(path)
        claimed_marker = _ready_path(claimed)
        try:
            os.replace(marker_path, claimed_marker)
            if _is_linklike(claimed_marker) or not os.path.isfile(claimed_marker):
                raise OSError("completion marker changed during claim; refusing to process")
        except OSError as e:
            # Do not os.replace the source back over a new file a producer may
            # have created at the inbox name. Keep this claim visible for manual
            # recovery; no parse or overwrite has occurred.
            results.append({"filename": name, "ok": False, "pending": False,
                            "project": None,
                            "error": f"could not claim completion marker: {e}; source remains in .processing/",
                            "filed": os.path.relpath(claimed, watch_dir)})
            continue

        result = {"filename": name, "ok": False, "pending": False,
                  "project": None, "error": None, "filed": None}
        project_dir = os.path.join(projects_dir, _safe_project_name(name))
        suffix = 1
        while os.path.exists(project_dir):
            suffix += 1
            project_dir = os.path.join(projects_dir, f"{_safe_project_name(name)}_{suffix}")

        created_project = False
        source_before = None
        try:
            source_before = _source_fingerprint(claimed)
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

        # Check even after parse/analyze errors: changed input is never kept as a
        # project that could look like an analysis of the final source.
        if source_before is not None:
            changed_reason = None
            try:
                if _source_fingerprint(claimed) != source_before:
                    changed_reason = "source changed after it was marked ready"
            except (OSError, RuntimeError) as e:
                changed_reason = f"source could not be verified after processing ({e})"
            if changed_reason:
                result["ok"] = False
                result["project"] = None
                result["error"] = ((result["error"] + "; ") if result["error"] else "") + \
                    changed_reason + "; no project was kept"
                if created_project:
                    try:
                        shutil.rmtree(project_dir)
                        created_project = False
                    except OSError as cleanup_error:
                        result["error"] += f"; could not remove partial project: {cleanup_error}"

        # ---- file the source, and never lie about why ----
        try:
            if not move_done:
                # The caller asked to keep the source. Its marker is consumed so
                # a future poll cannot silently run the same bytes again.
                back = _file_into(claimed, watch_dir, source_name)
                result["filed"] = os.path.relpath(back, watch_dir)
            elif result["ok"]:
                filed = _file_into(claimed, os.path.join(watch_dir, "done"), source_name)
                result["filed"] = os.path.relpath(filed, watch_dir)
            else:
                failed = _file_into(claimed, os.path.join(watch_dir, "failed"), source_name)
                _write_failure_note(failed, result["error"] or "unknown error")
                result["filed"] = os.path.relpath(failed, watch_dir)
        except Exception as e:      # noqa: BLE001 — filing is the last step, and must be reported
            result["error"] = (result["error"] + "; " if result["error"] else "") + \
                f"could not file the source: {e}"
            # The claim dir still holds source and marker; it is visible, never deleted.
            if os.path.isdir(claim_dir):
                result["filed"] = os.path.relpath(claimed, watch_dir)
            results.append(result)
            continue

        # The marker has served its purpose. Keep no stale signal beside the
        # filed source; a retry requires an explicit new .ready file.
        shutil.rmtree(claim_dir, ignore_errors=True)
        results.append(result)
    return results

def watch_loop(watch_dir: str, projects_dir: str, server_url: str,
               poll_interval: int = 5, model: str = None, categories: tuple = None,
               report_language: str = "eng") -> None:
    """Poll the watch dir forever, processing new screenplays as they appear."""
    os.makedirs(watch_dir, exist_ok=True)
    print(f"Watching {os.path.abspath(watch_dir)} for screenplays…")
    print(f"Projects → {os.path.abspath(projects_dir)}  (success → {watch_dir}/done/, failure → {watch_dir}/failed/)")
    print("A source is processed only after its sibling .ready marker is published.")
    print("Ctrl+C to stop.\n")
    announced_pending = set()
    while True:
        results = process_pending(watch_dir, projects_dir, server_url, model=model, categories=categories,
                                  report_language=report_language)
        current_pending = {r["filename"] for r in results if r.get("pending")}
        for r in results:
            if r.get("pending"):
                if r["filename"] not in announced_pending:
                    print(f"… {r['filename']} → {r['error']}")
                continue
            status = "✓" if r["ok"] else "✗"
            print(f"{status} {r['filename']} → {r['project'] or r['error']}")
        announced_pending = current_pending
        time.sleep(poll_interval)
