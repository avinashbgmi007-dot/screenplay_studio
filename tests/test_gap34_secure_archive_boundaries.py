"""Gap 34: keep credentials private; never let archive paths follow symlinks.

The project/library backups already redact `api_key` (gap 8). These tests cover
what remained: a project manifest was created with ordinary umask permissions,
the recovery archive bypassed redaction, and archive writes dereferenced links.
All payloads are synthetic and all external targets live under pytest's tmp_path.
"""
from __future__ import annotations

import io
import json
import os
import stat
import zipfile

import pytest

from screenplay_studio.manifest import ProjectManifest
import screenplay_studio.webapp_server as W

SECRET = "sk-live-GAP34-synthetic-only"
SCRIPT = "Title: Archive Safety\n\nINT. ROOM - DAY\n\nMARA\nHello.\n"


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(W, "PROJECTS_DIR", str(root))
    source = tmp_path / "script.fountain"
    source.write_text(SCRIPT, encoding="utf-8")
    manifest = ProjectManifest.create(str(root / "one"), str(source), title="One")
    manifest.api_key = SECRET
    manifest.save()
    W.app.config["TESTING"] = True
    return W.app.test_client(), root, manifest


def _symlink_or_skip(source, link, *, target_is_directory=False):
    try:
        os.symlink(source, link, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation is not permitted on this platform: {exc}")


def _zip(response):
    assert response.status_code == 200, response.get_data(as_text=True)[:500]
    return zipfile.ZipFile(io.BytesIO(response.data))


def _internal_manifest(zf, name):
    if name.endswith("/backup-manifest.json") or name.endswith("/library-backup.json"):
        return json.loads(zf.read(name))
    return json.loads(zf.read(name))


def _assert_symlink_is_named_omission(response, manifest_name, path_fragment):
    assert response.headers.get("X-Backup-Complete") == "false"
    zf = _zip(response)
    assert all(path_fragment not in name for name in zf.namelist()), zf.namelist()
    manifest = json.loads(zf.read(manifest_name))
    records = manifest.get("skipped") or []
    entry = next((r for r in records if path_fragment in r["path"]), None)
    assert entry, f"archive did not record omitted link: {records}"
    assert "symlink" in entry["reason"].lower()


class TestManifestPermissions:

    @pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits are the tested permission contract")
    def test_a_manifest_with_a_credential_is_created_owner_only(self, project):
        _client, _root, manifest = project
        mode = stat.S_IMODE(os.stat(manifest.manifest_path).st_mode)
        assert mode == 0o600, f"credential-bearing project.json mode was {mode:o}"

    @pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits are the tested permission contract")
    def test_loading_a_legacy_readable_credential_manifest_migrates_mode(self, project):
        _client, _root, manifest = project
        os.chmod(manifest.manifest_path, 0o644)
        ProjectManifest.load(manifest.project_dir)
        mode = stat.S_IMODE(os.stat(manifest.manifest_path).st_mode)
        assert mode == 0o600, f"legacy credential-bearing file was not tightened: {mode:o}"


class TestRecoveryBackupRedactsKnownCredentials:

    def test_recovery_archive_withholds_key_and_says_so(self, project):
        client, _root, manifest = project
        response = client.get("/api/projects/one/recover/backup")
        zf = _zip(response)
        assert SECRET.encode() not in b"".join(zf.read(n) for n in zf.namelist())
        assert response.headers.get("X-Backup-Credentials") == "withheld"
        archive_manifest = json.loads(zf.read("recovery-manifest.json"))
        assert archive_manifest["credentials_withheld"]
        restored = json.loads(zf.read("project.json"))
        assert restored["api_key"] is None
        assert restored["title"] == manifest.title

    def test_a_damaged_but_redactable_manifest_keeps_evidence_without_secret(self,
                                                                            project):
        client, _root, manifest = project
        raw = '{"title":"One","api_key":"' + SECRET + '", BROKEN'
        with open(manifest.manifest_path, "w", encoding="utf-8") as f:
            f.write(raw)
        zf = _zip(client.get("/api/projects/one/recover/backup"))
        recovered = zf.read("project.json").decode("utf-8")
        assert "BROKEN" in recovered, "the non-secret damaged evidence was discarded"
        assert SECRET not in recovered
        archive_manifest = json.loads(zf.read("recovery-manifest.json"))
        assert archive_manifest["credentials_withheld"]

    def test_an_unisolatable_secret_in_corrupt_manifest_is_named_as_omitted(self,
                                                                           project):
        client, _root, manifest = project
        raw = '{"title":"One","api_key":"' + SECRET
        with open(manifest.manifest_path, "w", encoding="utf-8") as f:
            f.write(raw)
        response = client.get("/api/projects/one/recover/backup")
        zf = _zip(response)
        assert "project.json" not in zf.namelist()
        assert SECRET.encode() not in b"".join(zf.read(n) for n in zf.namelist())
        assert response.headers.get("X-Backup-Complete") == "false"
        assert response.headers.get("X-Backup-Credentials") == "withheld"
        archive_manifest = json.loads(zf.read("recovery-manifest.json"))
        assert any("project.json" in s["path"] for s in archive_manifest["skipped"])
        assert archive_manifest["credentials_withheld"]


class TestSymlinksAreNeverDereferencedByAnyBackup:

    def test_project_backup_records_file_symlink(self, project, tmp_path):
        client, _root, manifest = project
        target = tmp_path / "outside.txt"
        target.write_text("OUTSIDE-SECRET-CONTENT", encoding="utf-8")
        _symlink_or_skip(target, os.path.join(manifest.project_dir, "outside-link.txt"))
        response = client.get("/api/projects/one/backup")
        _assert_symlink_is_named_omission(response, "backup-manifest.json", "outside-link.txt")
        zf = _zip(response)
        assert "OUTSIDE-SECRET-CONTENT" not in b"".join(zf.read(n) for n in zf.namelist()).decode("utf-8", "ignore")

    def test_library_backup_records_file_symlink(self, project, tmp_path):
        client, _root, manifest = project
        target = tmp_path / "library-outside.txt"
        target.write_text("LIBRARY-OUTSIDE-SECRET", encoding="utf-8")
        _symlink_or_skip(target, os.path.join(manifest.project_dir, "library-link.txt"))
        response = client.get("/api/library/backup")
        _assert_symlink_is_named_omission(response, "library-backup.json", "library-link.txt")
        zf = _zip(response)
        assert "LIBRARY-OUTSIDE-SECRET" not in b"".join(zf.read(n) for n in zf.namelist()).decode("utf-8", "ignore")

    def test_recovery_backup_records_file_symlink(self, project, tmp_path):
        client, _root, manifest = project
        target = tmp_path / "recovery-outside.txt"
        target.write_text("RECOVERY-OUTSIDE-SECRET", encoding="utf-8")
        _symlink_or_skip(target, os.path.join(manifest.project_dir, "recovery-link.txt"))
        response = client.get("/api/projects/one/recover/backup")
        _assert_symlink_is_named_omission(response, "recovery-manifest.json", "recovery-link.txt")
        zf = _zip(response)
        assert "RECOVERY-OUTSIDE-SECRET" not in b"".join(zf.read(n) for n in zf.namelist()).decode("utf-8", "ignore")

    def test_manifest_symlink_is_not_read_and_credential_status_is_unknown(self, project,
                                                                            tmp_path):
        client, _root, manifest = project
        target = tmp_path / "outside-project.json"
        target.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
        if os.name == "posix":
            os.chmod(target, 0o644)
        os.unlink(manifest.manifest_path)
        _symlink_or_skip(target, manifest.manifest_path)
        response = client.get("/api/projects/one/backup")
        zf = _zip(response)
        assert "project.json" not in zf.namelist()
        assert SECRET.encode() not in b"".join(zf.read(n) for n in zf.namelist())
        assert response.headers.get("X-Backup-Complete") == "false"
        assert response.headers.get("X-Backup-Credentials") == "withheld"
        archive_manifest = json.loads(zf.read("recovery-manifest.json"))
        assert any(item["path"] == "project.json" for item in archive_manifest["skipped"])
        assert any(item["cleared"] == ["unknown"]
                   for item in archive_manifest["credentials_withheld"])
        if os.name == "posix":
            assert stat.S_IMODE(os.stat(target).st_mode) == 0o644, "target file was unexpectedly read/migrated"

    def test_directory_symlink_is_recorded_and_not_walked(self, project, tmp_path):
        client, _root, manifest = project
        outside = tmp_path / "outside-dir"
        outside.mkdir()
        (outside / "hidden.txt").write_text("DO-NOT-ARCHIVE", encoding="utf-8")
        _symlink_or_skip(outside, os.path.join(manifest.project_dir, "dir-link"),
                         target_is_directory=True)
        response = client.get("/api/projects/one/backup")
        _assert_symlink_is_named_omission(response, "backup-manifest.json", "dir-link")
        zf = _zip(response)
        assert not any("hidden.txt" in n for n in zf.namelist())
        assert "DO-NOT-ARCHIVE" not in b"".join(zf.read(n) for n in zf.namelist()).decode("utf-8", "ignore")


class TestProjectRootCannotEscapeTheLibrary:

    def test_backup_and_recovery_refuse_a_project_root_symlink(self, tmp_path, monkeypatch):
        root = tmp_path / "projects"
        root.mkdir()
        outside = tmp_path / "outside-project"
        outside.mkdir()
        (outside / "project.json").write_text('{"title":"outside"}', encoding="utf-8")
        (outside / "private.txt").write_text("DO-NOT-ARCHIVE", encoding="utf-8")
        _symlink_or_skip(outside, root / "alias", target_is_directory=True)
        monkeypatch.setattr(W, "PROJECTS_DIR", str(root))
        W.app.config["TESTING"] = True
        client = W.app.test_client()
        assert client.get("/api/projects/alias/backup").status_code == 400
        assert client.get("/api/projects/alias/recover/backup").status_code == 400
        response = client.get("/api/library/backup")
        zf = _zip(response)
        assert "DO-NOT-ARCHIVE" not in b"".join(zf.read(n) for n in zf.namelist()).decode("utf-8", "ignore")
        manifest = json.loads(zf.read("library-backup.json"))
        assert any(f["project"] == "alias" for f in manifest["failed"])
