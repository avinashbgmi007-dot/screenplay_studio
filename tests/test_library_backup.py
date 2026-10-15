"""R7 (audit M5): the whole library is one click away as a single .zip.

The per-project backup existed; nothing saved the SHELF. A library backup
zips every project directory (damaged ones recorded in an embedded manifest,
not fatal), excludes lock/tmp plumbing, and is served as an attachment. The
UI button rides the dashboard head and is hidden on an empty shelf.
"""
import io
import json
import os
import zipfile

import pytest

import screenplay_studio.webapp_server as webapp_server


@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "r7_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


SCRIPT = b"""Title: R7 One
Author: T

INT. ROOM - DAY

Action.

ANA
A line.
"""


def _upload(client, title):
    return client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SCRIPT), "script.fountain"), "title": title},
        content_type="multipart/form-data",
    )


def _zip_names(resp):
    zf = zipfile.ZipFile(io.BytesIO(resp.data))
    return zf, zf.namelist()


def test_library_backup_zips_every_project_with_manifest(http_client):
    assert _upload(http_client, "R7 One").status_code == 201
    assert _upload(http_client, "R7 Two").status_code == 201

    resp = http_client.get("/api/library/backup")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"].startswith("application/zip")
    assert "attachment" in resp.headers.get("Content-Disposition", "")

    zf, names = _zip_names(resp)
    assert any(n.startswith("R7_One/") for n in names), names
    assert any(n.startswith("R7_Two/") for n in names), names
    assert any(n.endswith("project.json") for n in names), "the manifests themselves are in the archive"
    manifest = json.loads(zf.read("library-backup.json"))
    assert manifest["kind"] == "script-doctor-library-backup"
    got = sorted(p["project"] for p in manifest["projects"])
    assert got == ["R7_One", "R7_Two"]
    assert manifest["failed"] == []


def test_backup_excludes_lock_and_tmp_plumbing(http_client):
    assert _upload(http_client, "R7 One").status_code == 201
    # plant plumbing the way jsonio / mid-flight writes leave it
    pdir = os.path.join(webapp_server.PROJECTS_DIR, "R7_One")
    open(os.path.join(pdir, "notes.lock"), "w").close()
    open(os.path.join(pdir, "report.tmp"), "w").close()

    resp = http_client.get("/api/library/backup")
    _, names = _zip_names(resp)
    assert not any(n.endswith(".lock") for n in names)
    assert not any(n.endswith(".tmp") for n in names)


def test_damaged_project_is_recorded_not_fatal(http_client):
    assert _upload(http_client, "R7 One").status_code == 201
    # a half-deleted / foreign directory: no manifest inside
    broken = os.path.join(webapp_server.PROJECTS_DIR, "half-deleted")
    os.makedirs(broken, exist_ok=True)
    open(os.path.join(broken, "junk.txt"), "w").close()

    resp = http_client.get("/api/library/backup")
    assert resp.status_code == 200, "one stray directory must not fail the backup"
    zf, names = _zip_names(resp)
    assert any(n.startswith("half-deleted/") for n in names), \
        "unreadable files are still the writer's files — they are archived, not dropped"
    manifest = json.loads(zf.read("library-backup.json"))
    assert {"project": "half-deleted", "files": 1} in manifest["projects"]
    assert manifest["failed"] == []


def test_empty_library_still_downloads_a_valid_zip(http_client):
    resp = http_client.get("/api/library/backup")
    assert resp.status_code == 200
    zf, names = _zip_names(resp)
    manifest = json.loads(zf.read("library-backup.json"))
    assert manifest["projects"] == []
    assert manifest["failed"] == []


def test_writer_profile_store_is_not_archived(http_client):
    assert _upload(http_client, "R7 One").status_code == 201
    open(os.path.join(webapp_server.PROJECTS_DIR, "writer_profile.json"), "w").close()
    open(os.path.join(webapp_server.PROJECTS_DIR, "writer_profile.json.lock"), "w").close()

    resp = http_client.get("/api/library/backup")
    _, names = _zip_names(resp)
    assert not any("writer_profile" in n for n in names), \
        "the co-writer's internal memory store is not a project"
