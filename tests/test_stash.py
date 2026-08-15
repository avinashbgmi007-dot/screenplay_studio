"""Tests for the Stash — per-project saved snippets."""

import os

import pytest

import screenplay_studio.webapp_server as webapp_server

from screenplay_studio.stash_store import load_stash, add_to_stash, remove_from_stash


def test_add_load_remove_roundtrip(tmp_path):
    d = str(tmp_path)
    e1 = add_to_stash(d, "A good line that got cut.", title="Scene 3 cut", scene_number=3)
    e2 = add_to_stash(d, "Another keeper.", scene_number=None)
    stash = load_stash(d)
    assert len(stash) == 2
    assert stash[0]["id"] == e2["id"]  # newest first
    assert e1["scene_number"] == 3
    assert e2["scene_number"] is None
    assert e1["title"] == "Scene 3 cut"

    assert remove_from_stash(d, e1["id"]) is True
    assert [e["id"] for e in load_stash(d)] == [e2["id"]]
    assert remove_from_stash(d, "missing") is False


def test_add_requires_text(tmp_path):
    with pytest.raises(ValueError):
        add_to_stash(str(tmp_path), "   ")


def test_load_tolerates_missing_or_bad_file(tmp_path):
    assert load_stash(str(tmp_path)) == []  # no file yet
    with open(os.path.join(str(tmp_path), "stash.json"), "w", encoding="utf-8") as f:
        f.write("not json")
    assert load_stash(str(tmp_path)) == []


@pytest.fixture
def http_client(tmp_path, sample_fountain):
    webapp_server.PROJECTS_DIR = str(tmp_path / "proj")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = "http://localhost:8196"
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    from screenplay_studio.manifest import ProjectManifest
    m = ProjectManifest.create(os.path.join(webapp_server.PROJECTS_DIR, "p1"), sample_fountain)
    m.save()
    return webapp_server.app.test_client()


def test_stash_routes(http_client):
    resp = http_client.get("/api/projects/p1/stash")
    assert resp.status_code == 200
    assert resp.get_json()["stash"] == []

    resp = http_client.post("/api/projects/p1/stash", json={"text": "Keep this line.", "scene_number": 2})
    assert resp.status_code == 201
    entry = resp.get_json()
    assert entry["text"] == "Keep this line."
    assert entry["scene_number"] == 2
    assert entry["id"]

    resp = http_client.post("/api/projects/p1/stash", json={"text": ""})
    assert resp.status_code == 400

    resp = http_client.get("/api/projects/p1/stash")
    assert len(resp.get_json()["stash"]) == 1

    resp = http_client.delete(f"/api/projects/p1/stash/{entry['id']}")
    assert resp.status_code == 200
    resp = http_client.delete(f"/api/projects/p1/stash/{entry['id']}")
    assert resp.status_code == 404
