"""Gap 16 — watch mode must never destroy a source file.

The register framed this as "processing can overwrite source files", release
blocker for watch mode. Reproduced on a real filesystem with the real
`process_pending()`, it was three separate defects, each measured before the
fix:

A. **A same-named drop replaced the earlier one.** `shutil.move(path,
   done/<name>)` reused the filename, so two different scripts dropped as
   `draft.fountain` left ONE file in `done/` — the first gone. Measured: 1 file
   in `done/`, its content the second script.
B. **A failed drop was filed under `done/`.** The move was gated on
   `ok or error`, so a script whose project copy failed (ENOSPC) was cleared
   from the inbox and archived as if it had been processed — while no project
   copy existed anywhere.
C. **A drop whose manifest never became durable was cleared too** — the same
   `ok or error` gate, reached through `manifest.save()`.

The tests below assert the property rather than the implementation, so they do
not care where a drop is filed: **after any run, every dropped script's content
is still retrievable, and nothing that failed is presented as done.**
"""
import os
import threading

import pytest

from screenplay_studio.watch import process_pending


def _script(marker: str) -> str:
    return (f"Title: {marker}\n\nINT. ROOM - DAY\n\nAction for {marker}.\n\n"
            f"ANA\nLine one for {marker}.\n")


def _drop(watch_dir: str, name: str, marker: str) -> str:
    os.makedirs(watch_dir, exist_ok=True)
    path = os.path.join(watch_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(_script(marker))
    open(path + ".ready", "wb").close()
    return path


def _all_text_under(root: str) -> str:
    """Every readable text file under `root`, concatenated — the search space a
    writer would actually look in when a drop seems to have vanished."""
    chunks = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            try:
                with open(os.path.join(dirpath, name), encoding="utf-8") as f:
                    chunks.append(f.read())
            except (OSError, UnicodeDecodeError):
                continue
    return "\n".join(chunks)


def _dead_server():
    return "http://127.0.0.1:9"       # nothing listens; every run fails fast


# ---------------------------------------------------------------------------
# A. Two drops, one filename, both scripts survive
# ---------------------------------------------------------------------------

def test_two_same_named_drops_are_both_retrievable(tmp_path):
    """The measured defect: the second `draft.fountain` silently replaced the
    first. A writer who re-saved a file under the same name and dropped it again
    lost the earlier version with no message."""
    watch = str(tmp_path / "watch")
    projects = str(tmp_path / "projects")

    _drop(watch, "draft.fountain", "FIRST_VERSION")
    process_pending(watch, projects, _dead_server())
    _drop(watch, "draft.fountain", "SECOND_VERSION")
    process_pending(watch, projects, _dead_server())

    text = _all_text_under(watch)
    assert "FIRST_VERSION" in text, (
        "the first drop is nowhere under the watch folder — it was replaced by "
        "the second, same-named drop")
    assert "SECOND_VERSION" in text, "the second drop must be kept too"


def test_a_second_drop_gets_its_own_file_not_an_overwrite(tmp_path):
    """The same guarantee stated as countable files, so a fix that 'preserves'
    the first by writing both into one file cannot pass."""
    watch = str(tmp_path / "watch")
    projects = str(tmp_path / "projects")

    _drop(watch, "draft.fountain", "ALPHA")
    r1 = process_pending(watch, projects, _dead_server())
    _drop(watch, "draft.fountain", "BETA")
    r2 = process_pending(watch, projects, _dead_server())

    assert r1[0]["filed"] and r2[0]["filed"], "each drop must report where it went"
    assert r1[0]["filed"] != r2[0]["filed"], (
        "two distinct sources cannot share one path: "
        f"both went to {r1[0]['filed']!r}")
    for res, marker in ((r1[0], "ALPHA"), (r2[0], "BETA")):
        with open(os.path.join(watch, res["filed"]), encoding="utf-8") as f:
            assert marker in f.read(), f"{marker} is not in {res['filed']}"


# ---------------------------------------------------------------------------
# B. A failure is never filed as done
# ---------------------------------------------------------------------------

def test_a_failed_copy_is_not_filed_under_done(tmp_path, monkeypatch):
    """Measured: `ProjectManifest.create` raising ENOSPC still moved the source
    to `done/`, clearing the inbox for a script that was never processed."""
    from screenplay_studio import watch as watch_mod

    watch = str(tmp_path / "watch")
    projects = str(tmp_path / "projects")
    _drop(watch, "precious.fountain", "PRECIOUS")

    def boom(project_dir, source_file, title=None):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(watch_mod.ProjectManifest, "create", staticmethod(boom))
    res = process_pending(watch, projects, _dead_server())[0]

    assert res["ok"] is False
    assert not str(res["filed"] or "").startswith("done"), (
        f"a failed drop was archived as done: filed={res['filed']!r}")
    # And the source is still readable, byte for byte.
    with open(os.path.join(watch, res["filed"]), encoding="utf-8") as f:
        assert f.read() == _script("PRECIOUS")
    assert "PRECIOUS" in _all_text_under(watch)


def test_a_failed_drop_says_why_beside_the_file(tmp_path, monkeypatch):
    """The writer must be able to find out what happened without reading logs."""
    from screenplay_studio import watch as watch_mod

    watch = str(tmp_path / "watch")
    projects = str(tmp_path / "projects")
    _drop(watch, "note_me.fountain", "NOTE")

    def boom(project_dir, source_file, title=None):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(watch_mod.ProjectManifest, "create", staticmethod(boom))
    res = process_pending(watch, projects, _dead_server())[0]

    note = os.path.join(watch, res["filed"] + ".error.txt")
    assert os.path.exists(note), f"no failure note next to {res['filed']}"
    body = open(note, encoding="utf-8").read()
    assert "No space left on device" in body
    assert "untouched" in body, "the note must say the source is intact"


def test_a_drop_whose_manifest_never_became_durable_is_not_done(tmp_path, monkeypatch):
    """Measured defect C: the failure point is `manifest.save()`, after the copy."""
    from screenplay_studio import watch as watch_mod

    watch = str(tmp_path / "watch")
    projects = str(tmp_path / "projects")
    _drop(watch, "halfway.fountain", "HALFWAY")

    def boom(self):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(watch_mod.ProjectManifest, "save", boom)
    res = process_pending(watch, projects, _dead_server())[0]

    assert res["ok"] is False
    assert not str(res["filed"] or "").startswith("done")
    assert "HALFWAY" in _all_text_under(watch)


def test_a_failed_first_copy_leaves_no_phantom_project(tmp_path, monkeypatch):
    """A half-created project directory is a shelf entry the writer cannot open.
    With the source still in our hands nothing is lost by removing it."""
    from screenplay_studio import watch as watch_mod

    watch = str(tmp_path / "watch")
    projects = str(tmp_path / "projects")
    _drop(watch, "phantom.fountain", "PHANTOM")

    def boom(project_dir, source_file, title=None):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(watch_mod.ProjectManifest, "create", staticmethod(boom))
    process_pending(watch, projects, _dead_server())

    left = os.listdir(projects) if os.path.isdir(projects) else []
    assert left == [], f"a failed drop left phantom project dirs: {left}"


# ---------------------------------------------------------------------------
# C. The happy path is unchanged
# ---------------------------------------------------------------------------

def test_a_successful_drop_still_lands_in_done(tmp_path, mock_server):
    watch = str(tmp_path / "watch")
    projects = str(tmp_path / "projects")
    _drop(watch, "good.fountain", "GOOD")

    res = process_pending(watch, projects, mock_server)[0]

    assert res["ok"] is True, res["error"]
    assert res["filed"] == os.path.join("done", "good.fountain"), res["filed"]
    assert os.path.exists(os.path.join(watch, "done", "good.fountain"))
    assert not os.path.exists(os.path.join(watch, "good.fountain")), "the inbox must be clear"
    project_dir = os.path.join(projects, res["project"])
    assert os.path.exists(os.path.join(project_dir, "report.findings.json"))


def test_move_done_false_keeps_even_a_failed_drop_in_the_inbox(tmp_path, monkeypatch):
    from screenplay_studio import watch as watch_mod

    watch = str(tmp_path / "watch")
    projects = str(tmp_path / "projects")
    _drop(watch, "stay.fountain", "STAY")

    def boom(project_dir, source_file, title=None):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(watch_mod.ProjectManifest, "create", staticmethod(boom))
    res = process_pending(watch, projects, _dead_server(), move_done=False)[0]

    assert res["filed"] == "stay.fountain"
    assert os.path.exists(os.path.join(watch, "stay.fountain"))


# ---------------------------------------------------------------------------
# D. One owner per drop (cross-process claiming)
# ---------------------------------------------------------------------------

def test_a_drop_is_claimed_before_work_starts(tmp_path, monkeypatch):
    """Two watchers polling one folder must not both process a drop, and must
    not both file it. Claims are atomic renames, so exactly one wins."""
    from screenplay_studio import watch as watch_mod

    watch = str(tmp_path / "watch")
    projects = str(tmp_path / "projects")
    _drop(watch, "once.fountain", "ONCE")

    calls = []
    real_create = watch_mod.ProjectManifest.create

    def counting_create(project_dir, source_file, title=None):
        calls.append(source_file)
        return real_create(project_dir, source_file, title=title)

    monkeypatch.setattr(watch_mod.ProjectManifest, "create", staticmethod(counting_create))

    results = []
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait()
        results.append(process_pending(watch, projects, _dead_server()))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert len(calls) == 1, f"the drop was processed {len(calls)} times, not once"
    reported = [r for batch in results for r in batch]
    assert len(reported) == 1, f"both workers reported the same drop: {reported}"
    assert "ONCE" in _all_text_under(watch)


def test_no_claim_directory_is_left_behind_after_a_run(tmp_path, mock_server):
    """`.processing/` is plumbing, not an archive: a successful run must not
    leave claimed copies accumulating in it."""
    watch = str(tmp_path / "watch")
    projects = str(tmp_path / "projects")
    _drop(watch, "clean.fountain", "CLEAN")

    process_pending(watch, projects, mock_server)

    claim_root = os.path.join(watch, ".processing")
    leftovers = []
    for dirpath, _dirs, files in os.walk(claim_root):
        leftovers.extend(files)
    assert leftovers == [], f"claimed copies were left behind: {leftovers}"


def test_a_failed_drop_is_retryable_by_moving_it_back(tmp_path, monkeypatch):
    """The documented way out of `failed/`. Nothing is auto-retried (a permanent
    error must not spin), so this is the path the writer is told to take — and
    it must work."""
    from screenplay_studio import watch as watch_mod

    watch = str(tmp_path / "watch")
    projects = str(tmp_path / "projects")
    src = _drop(watch, "retry.fountain", "RETRY")

    def boom(project_dir, source_file, title=None):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(watch_mod.ProjectManifest, "create", staticmethod(boom))
    first = process_pending(watch, projects, _dead_server())[0]
    assert first["ok"] is False

    # The writer follows the note: move it back.
    os.replace(os.path.join(watch, first["filed"]), src)
    open(src + ".ready", "wb").close()
    os.unlink(src + ".error.txt") if os.path.exists(src + ".error.txt") else None

    monkeypatch.undo()
    second = process_pending(watch, projects, os.environ.get("_unused") or "http://127.0.0.1:9")[0]
    # No server here either, so it fails again — but it is processed AGAIN,
    # which is the property: a failed drop is never silently dropped.
    assert second["filename"] == "retry.fountain"
    assert "RETRY" in _all_text_under(watch)
