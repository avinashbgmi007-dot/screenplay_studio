"""Tests for the writer's library knowledge layer — the deterministic digest
of the writer's past projects that Sameer and Dr. Sushruta draw on."""

import json
import os

import pytest

import screenplay_studio.webapp_server as webapp_server

from screenplay_cowriter.writer_library import build_library, library_digest_text


def _make_project(root, name, title, characters, themes=None, scene_count=2):
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    parsed = {
        "title": title, "source_format": "fountain", "scene_count": scene_count,
        "all_characters": characters, "scenes": [],
    }
    with open(os.path.join(d, "parsed.json"), "w", encoding="utf-8") as f:
        json.dump(parsed, f)
    if themes is not None:
        with open(os.path.join(d, "report.findings.json"), "w", encoding="utf-8") as f:
            json.dump({"findings": [{"category": "theme", "issue": t} for t in themes]}, f)


def test_build_library_digests(tmp_path):
    _make_project(str(tmp_path), "Pain_3", "Pain", ["RISHI", "SIDDHARTH", "DOCTOR"],
                  themes=["The cost of saying no.", "Memory and guilt."])
    _make_project(str(tmp_path), "Late_Hour", "The Late Hour", ["MARA", "DEREK"], themes=None)
    os.makedirs(os.path.join(str(tmp_path), "ideas"), exist_ok=True)  # sibling store — must be skipped

    lib = build_library(str(tmp_path))
    assert len(lib) == 2
    by_name = {e["project"]: e for e in lib}
    assert by_name["Pain_3"]["scene_count"] == 2
    assert by_name["Pain_3"]["themes"] == ["The cost of saying no.", "Memory and guilt."]
    assert "MARA" in by_name["Late_Hour"]["characters"]
    # the ideas store is never a library entry
    assert "ideas" not in by_name


def test_build_library_excludes_current_project(tmp_path):
    _make_project(str(tmp_path), "Current", "Current Script", ["A"], themes=["x"])
    _make_project(str(tmp_path), "Other", "Other Script", ["B"], themes=None)
    lib = build_library(str(tmp_path), exclude="Current")
    assert [e["project"] for e in lib] == ["Other"]


def test_build_library_tolerates_unparsed(tmp_path):
    os.makedirs(os.path.join(str(tmp_path), "EmptyProj"), exist_ok=True)
    with open(os.path.join(str(tmp_path), "EmptyProj", "notes.txt"), "w") as f:
        f.write("no parsed.json here")
    assert build_library(str(tmp_path)) == []


def test_digest_text_has_guard_and_content(tmp_path):
    _make_project(str(tmp_path), "Pain_3", "Pain", ["RISHI"], themes=["The cost of saying no."])
    text = library_digest_text(build_library(str(tmp_path)))
    assert "PAST WORK" in text
    assert "Pain" in text
    assert "RISHI" in text
    assert "never invent details of past scripts" in text  # grounding guard
    assert library_digest_text([]) == ""


@pytest.fixture
def http_client(tmp_path):
    webapp_server.PROJECTS_DIR = str(tmp_path / "proj")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = "http://localhost:8196"
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def test_writer_library_route(http_client, tmp_path):
    _make_project(str(tmp_path / "proj"), "Pain_3", "Pain", ["RISHI"], themes=["The cost of saying no."])
    resp = http_client.get("/api/writer-library")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["projects"]) == 1
    assert data["projects"][0]["title"] == "Pain"
    assert data["projects"][0]["themes"] == ["The cost of saying no."]
