"""Gap 38: old Unicode project folders remain reachable through safe IDs."""
from __future__ import annotations

import os

from screenplay_studio.jsonio import legacy_project_id, suffixed_id
from screenplay_studio.manifest import ProjectManifest


def _make_project(directory, title):
    os.makedirs(directory)
    source = os.path.join(directory, "seed.fountain")
    with open(source, "w", encoding="utf-8") as screenplay:
        screenplay.write("INT. ROOM - DAY\n\nA synthetic scene.\n")
    manifest = ProjectManifest.create(directory, source, title=title)
    manifest.save()


def test_legacy_unicode_project_uses_safe_shelf_and_route_id_without_rename(
    tmp_path, monkeypatch
):
    import screenplay_studio.webapp_server as ws

    projects = tmp_path / "projects"
    projects.mkdir()
    actual_name = "రాత్రి"
    actual_dir = projects / actual_name
    _make_project(str(actual_dir), actual_name)
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(projects))
    ws.app.config["TESTING"] = True
    client = ws.app.test_client()
    expected_id = legacy_project_id(actual_name)

    shelf = client.get("/api/projects")
    assert shelf.status_code == 200
    row = next(project for project in shelf.get_json() if project["title"] == actual_name)
    assert row["project"] == expected_id
    assert os.path.isdir(actual_dir), "legacy project was silently renamed or migrated"

    opened = client.get(f"/api/projects/{expected_id}")
    assert opened.status_code == 200, opened.get_json()
    assert opened.get_json()["project"] == expected_id
    assert opened.get_json()["title"] == actual_name


def test_legacy_mapping_does_not_shadow_an_existing_safe_project_id(
    tmp_path, monkeypatch
):
    import screenplay_studio.webapp_server as ws

    projects = tmp_path / "projects"
    projects.mkdir()
    actual_name = "पुराना"
    legacy_dir = projects / actual_name
    base = legacy_project_id(actual_name)
    safe_dir = projects / base
    _make_project(str(legacy_dir), "Old Unicode Project")
    _make_project(str(safe_dir), "Existing Safe Project")
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(projects))
    ws.app.config["TESTING"] = True
    client = ws.app.test_client()

    shelf = client.get("/api/projects").get_json()
    by_title = {row["title"]: row["project"] for row in shelf}
    legacy_safe_id = suffixed_id(base, 2)
    assert by_title["Existing Safe Project"] == base
    assert by_title["Old Unicode Project"] == legacy_safe_id

    legacy_response = client.get(f"/api/projects/{legacy_safe_id}")
    safe_response = client.get(f"/api/projects/{base}")
    assert legacy_response.status_code == safe_response.status_code == 200
    assert legacy_response.get_json()["title"] == "Old Unicode Project"
    assert safe_response.get_json()["title"] == "Existing Safe Project"
