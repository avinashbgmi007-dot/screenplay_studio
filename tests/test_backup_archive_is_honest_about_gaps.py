"""Gap 72 — a successful archive could be incomplete without telling the writer.

Both backup routes wrapped `zf.write` in `except OSError: continue`, and the
per-project archive did not even keep a count. Measured: with one file faulted,
`GET /api/projects/<name>/backup` answered **200**, the file was absent from the
zip, there was **no manifest inside**, and no response header said anything.

This is a completeness-honesty defect, not a lost backup: the file is still on
disk. The fault is that a download which looks whole is not whole.
"""

import io
import json
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import screenplay_studio.webapp_server as ws
from screenplay_studio.manifest import ProjectManifest

SRC = "Title: T\n\nINT. ROOM - DAY\n\nMIRA\nHello.\n"


@pytest.fixture
def desk(monkeypatch, tmp_path):
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(tmp_path))
    src = tmp_path / "s.fountain"
    src.write_text(SRC, encoding="utf-8")
    m = ProjectManifest.create(str(tmp_path / "myproj"), str(src), title="T")
    (tmp_path / "myproj" / "draft_notes.md").write_text("notes\n", encoding="utf-8")
    ws.app.config["TESTING"] = True
    return ws.app.test_client(), m


@pytest.fixture
def flaky():
    """Fail the zip write for one named file, then restore it."""
    real = ws._zip_regular_file
    state = {"victim": None}

    def _write(zf, filename, arcname):
        victim = state["victim"]
        if victim and str(filename).endswith(victim):
            raise OSError(2, "No such file or directory")
        return real(zf, filename, arcname)

    ws._zip_regular_file = _write
    yield state
    ws._zip_regular_file = real


# ---------- the filed reproduction ----------

def test_a_complete_backup_says_so(desk):
    client, _ = desk
    r = client.get("/api/projects/myproj/backup")
    assert r.status_code == 200
    assert r.headers["X-Backup-Complete"] == "true"
    z = zipfile.ZipFile(io.BytesIO(r.data))
    man = json.loads(z.read("backup-manifest.json"))
    assert man["complete"] is True
    assert man["skipped"] == []


def test_an_incomplete_backup_is_not_silent(desk, flaky):
    """The filed case: the download looks whole and is not."""
    client, _ = desk
    flaky["victim"] = "draft_notes.md"
    r = client.get("/api/projects/myproj/backup")
    assert r.status_code == 200
    assert r.headers["X-Backup-Complete"] == "false"
    assert r.headers["X-Backup-Omitted"] == "1"


def test_the_omission_is_named_inside_the_archive(desk, flaky):
    """A header is lost with the browser session; the archive is the artifact."""
    client, _ = desk
    flaky["victim"] = "draft_notes.md"
    r = client.get("/api/projects/myproj/backup")
    z = zipfile.ZipFile(io.BytesIO(r.data))
    man = json.loads(z.read("backup-manifest.json"))
    assert man["complete"] is False
    assert [s["path"].split("/")[-1] for s in man["skipped"]] == ["draft_notes.md"]
    assert man["skipped"][0]["reason"], "the reason must be recorded, not just the fact"


def test_the_project_backup_now_keeps_a_count(desk, flaky):
    """The per-project route did not even count what it wrote."""
    client, _ = desk
    flaky["victim"] = "draft_notes.md"
    z = zipfile.ZipFile(io.BytesIO(client.get("/api/projects/myproj/backup").data))
    man = json.loads(z.read("backup-manifest.json"))
    assert man["files"] >= 2, man
    real_names = [n for n in z.namelist() if n != "backup-manifest.json"]
    assert man["files"] == len(real_names)


# ---------- the library archive ----------

def test_the_library_manifest_records_skipped_files(desk, flaky):
    client, _ = desk
    flaky["victim"] = "draft_notes.md"
    r = client.get("/api/library/backup")
    assert r.status_code == 200
    assert r.headers["X-Backup-Complete"] == "false"
    z = zipfile.ZipFile(io.BytesIO(r.data))
    man = json.loads(z.read("library-backup.json"))
    assert man["complete"] is False
    assert man["skipped"], "the library manifest counted inclusions but not omissions"
    assert any("draft_notes" in s["path"] for s in man["skipped"])


def test_the_library_manifest_counts_only_files_that_landed(desk, flaky):
    """`files: n` must mean 'in the archive', not 'we tried'."""
    client, _ = desk
    flaky["victim"] = "draft_notes.md"
    r = client.get("/api/library/backup")
    z = zipfile.ZipFile(io.BytesIO(r.data))
    man = json.loads(z.read("library-backup.json"))
    claimed = sum(p["files"] for p in man["projects"])
    actual = [n for n in z.namelist() if not n.endswith(".json") or "/" in n]
    actual = [n for n in actual if n != "backup-manifest.json"]
    assert claimed == len(actual), (claimed, actual)


def test_a_clean_library_backup_is_complete(desk):
    client, _ = desk
    r = client.get("/api/library/backup")
    assert r.headers["X-Backup-Complete"] == "true"


# ---------- plumbing is still excluded, and that is not an omission ----------

def test_lock_and_temp_files_are_excluded_without_being_reported(desk):
    """Excluding our own plumbing is not a gap in the writer's desk."""
    client, m = desk
    lock = os.path.join(m.project_dir, "working.json.lock")
    with open(lock, "w") as f:
        f.write("{}")
    r = client.get("/api/projects/myproj/backup")
    assert r.headers["X-Backup-Complete"] == "true"
    z = zipfile.ZipFile(io.BytesIO(r.data))
    assert not any(n.endswith(".lock") for n in z.namelist())
    man = json.loads(z.read("backup-manifest.json"))
    assert man["skipped"] == []


def test_every_skiplist_entry_is_a_real_reason(desk, flaky):
    """A skip record must be actionable: path AND why."""
    client, _ = desk
    flaky["victim"] = "draft_notes.md"
    z = zipfile.ZipFile(io.BytesIO(client.get("/api/projects/myproj/backup").data))
    for entry in json.loads(z.read("backup-manifest.json"))["skipped"]:
        assert entry["path"] and entry["reason"]
        # The SUBclass name is recorded, e.g. "FileNotFoundError: [Errno 2] ...",
        # which is more useful than the base class — so accept any OSError name.
        oserror_names = ("OSError", "FileNotFoundError", "PermissionError",
                         "IsADirectoryError", "NotADirectoryError", "IOError")
        assert any(n in entry["reason"] for n in oserror_names), entry["reason"]
