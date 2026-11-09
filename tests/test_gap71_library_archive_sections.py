"""Gap 71: library archives name projects, ideas, and private writer memory."""

import io
import json
import os
import zipfile

import pytest

import screenplay_studio.webapp_server as webapp_server
from screenplay_studio.ideas import IdeaStore


SCRIPT = b"""Title: Archive round trip
Author: Test

INT. ROOM - DAY

MARA enters the room.

CUT TO:

EXT. STREET - NIGHT

MARA looks up.
"""


@pytest.fixture
def library(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(root))
    monkeypatch.setitem(webapp_server.CONFIG, "server_url", "http://127.0.0.1:1")
    monkeypatch.setitem(webapp_server.CONFIG, "model", None)
    monkeypatch.setitem(webapp_server.CONFIG, "fast_model", None)
    monkeypatch.setitem(webapp_server.app.config, "TESTING", True)
    client = webapp_server.app.test_client()

    upload = client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SCRIPT), "archive.fountain"),
              "title": "Archive Project"},
        content_type="multipart/form-data",
    )
    assert upload.status_code in (200, 201), upload.get_data(as_text=True)
    project_id = upload.get_json()["project"]

    ideas = IdeaStore(str(root / "ideas"))
    idea = ideas.create("Archive Idea")
    ideas.save_content(idea["id"], "An idea that must travel separately from scripts.")
    (root / "writer_profile.json").write_text(
        json.dumps({"observations": [{"text": "prefers candid feedback"}]}),
        encoding="utf-8",
    )
    return client, root, project_id, idea


def _archive(client, suffix=""):
    response = client.get("/api/library/backup" + suffix)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response, zipfile.ZipFile(io.BytesIO(response.data))


def test_manifest_names_ideas_separately_and_discloses_default_memory_exclusion(library):
    client, _root, project_id, idea = library
    response, archive = _archive(client)
    manifest = json.loads(archive.read("library-backup.json"))

    assert manifest["archive_version"] == 2
    assert {entry["project"] for entry in manifest["projects"]} == {project_id}
    assert manifest["ideas"] == [{"idea_id": idea["id"], "files": 1}]
    assert f"ideas/{idea['id']}/idea.json" in archive.namelist()
    assert not any(row["project"] == "ideas" for row in manifest["projects"])
    assert manifest["writer_memory"]["included"] is False
    assert "personal relationship memory" in manifest["writer_memory"]["reason"]
    assert "writer_profile.json" not in archive.namelist()
    assert response.headers["X-Backup-Writer-Memory"] == "withheld"
    assert manifest["restore"] == {
        "mode": "manual", "in_app_import": False,
        "target": "an empty projects directory",
    }


def test_writer_memory_requires_an_explicit_opt_in(library):
    client, _root, _project_id, _idea = library
    _response, archive = _archive(client, "?include_writer_memory=true")
    manifest = json.loads(archive.read("library-backup.json"))

    assert "writer_profile.json" in archive.namelist()
    assert manifest["writer_memory"] == {
        "included": True,
        "path": "writer_profile.json",
        "reason": "included at the writer's explicit request",
    }
    assert _response.headers["X-Backup-Writer-Memory"] == "included"


def test_manual_restore_to_empty_library_round_trips_project_and_idea(library, tmp_path,
                                                                        monkeypatch):
    client, _root, project_id, idea = library
    _response, archive = _archive(client)
    restored_root = tmp_path / "restored-empty-library"
    restored_root.mkdir()
    # This test deliberately restores only to a new empty directory. It does
    # not exercise or imply a merge/overwrite restore contract.
    archive.extractall(restored_root)
    monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(restored_root))

    projects = client.get("/api/projects")
    ideas = client.get("/api/ideas")
    restored_idea = client.get(f"/api/ideas/{idea['id']}")

    assert projects.status_code == 200
    assert [row["project"] for row in projects.get_json()] == [project_id]
    assert ideas.status_code == 200
    assert [row["id"] for row in ideas.get_json()] == [idea["id"]]
    assert restored_idea.status_code == 200
    assert restored_idea.get_json()["content"] == (
        "An idea that must travel separately from scripts.")
    assert not (restored_root / "writer_profile.json").exists()


def test_invalid_memory_opt_in_is_rejected(library):
    client, _root, _project_id, _idea = library
    response = client.get("/api/library/backup?include_writer_memory=maybe")
    assert response.status_code == 400
    assert "include_writer_memory" in response.get_json()["error"]


def test_memory_opt_in_requires_capability_token_when_server_has_one(library,
                                                                      monkeypatch):
    client, _root, _project_id, _idea = library
    monkeypatch.setattr(webapp_server, "_API_TOKEN", "secret-capability")

    refused = client.get("/api/library/backup?include_writer_memory=true")
    accepted = client.get(
        "/api/library/backup?include_writer_memory=true",
        headers={"X-Studio-Token": "secret-capability"},
    )

    assert refused.status_code == 403
    assert accepted.status_code == 200
    with zipfile.ZipFile(io.BytesIO(accepted.data)) as archive:
        manifest = json.loads(archive.read("library-backup.json"))
        assert manifest["writer_memory"]["included"] is True
