"""Graduation keeps page readiness and idea-material transfer truthful.

These tests use the real Flask routes and file-backed stores with synthetic
ideas/uploads; they do not call a language model or interpret a screenplay.
"""

import io
import json
import os
from pathlib import Path

import pytest

import screenplay_studio.webapp_server as web
from screenplay_studio.ideas import IdeaStore
from screenplay_cowriter.store import SessionStore


SCRIPT = b"""Title: First Pages
Author: Test

INT. ROOM - DAY

MARA enters and looks around.
"""


@pytest.fixture
def http_client(tmp_path, mock_server, monkeypatch):
    projects = str(tmp_path / "projects")
    os.makedirs(projects, exist_ok=True)
    monkeypatch.setattr(web, "PROJECTS_DIR", projects)
    monkeypatch.setitem(web.CONFIG, "server_url", mock_server)
    monkeypatch.setitem(web.CONFIG, "model", None)
    monkeypatch.setitem(web.app.config, "TESTING", True)
    return web.app.test_client()


def _new_idea(title="Embers"):
    store = IdeaStore(web._ideas_dir())
    idea = store.create(title=title)
    store.save_card(idea["id"], {
        "title": title, "logline": "A logline kept with its pages.",
        "premise": "The premise must survive graduation.",
    })
    return store, idea


def _graduate(client, idea_id, payload=SCRIPT, filename="first-pages.fountain", title="Graduated"):
    return client.post(
        f"/api/ideas/{idea_id}/graduate",
        data={"file": (io.BytesIO(payload), filename), "title": title},
        content_type="multipart/form-data",
    )


def test_injected_transfer_failure_is_reported_and_source_idea_survives(
        http_client, monkeypatch):
    store, idea = _new_idea()

    def fail_transfer(self, idea_id, project_dir):
        raise OSError("injected carry failure")

    monkeypatch.setattr(IdeaStore, "carry_into_project", fail_transfer)
    response = _graduate(http_client, idea["id"])
    assert response.status_code == 201  # valid pages still made a project
    body = response.get_json()
    transfer = body["graduation"]
    assert transfer["complete"] is False
    assert transfer["retryable"] is True
    assert transfer["premise"]["status"] == "unknown"
    assert transfer["sessions"]["status"] == "unknown"

    project_dir = web._project_dir(body["project"])
    assert os.path.isdir(project_dir)
    assert not os.path.exists(os.path.join(project_dir, "premise.json"))
    assert os.path.isdir(store._dir(idea["id"]))
    assert store.load(idea["id"])["card"]["logline"] == "A logline kept with its pages."

    # The transfer outcome survives a later project read rather than disappearing
    # with the one response that created the project.
    reopened = http_client.get(f"/api/projects/{body['project']}").get_json()
    assert reopened["graduation"]["complete"] is False
    assert reopened["graduation"]["idea_id"] == idea["id"]

    js = (Path(web.__file__).parent / "webapp" / "app.js").read_text(encoding="utf-8")
    assert "The premise card and your conversation came with you" not in js
    assert "Retry transfer into this project" in js
    assert "Your original idea remains available." in js
    assert "Graduation is incomplete." in js
    assert "Graduation transfer complete." in js


def test_session_pin_failure_is_visible_and_retryable(http_client, monkeypatch):
    store, idea = _new_idea("Pin Retry")
    session_store = SessionStore(store.sessions_dir(idea["id"]))
    session = session_store.create("Keep this thread active")
    real_pin = web._pin_graduated_session
    calls = 0

    def fail_first_pin(manifest, project_dir, transfer):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"status": "failed", "reason": "injected manifest save failure"}
        return real_pin(manifest, project_dir, transfer)

    monkeypatch.setattr(web, "_pin_graduated_session", fail_first_pin)
    response = _graduate(http_client, idea["id"], title="Pin Retry Project")
    assert response.status_code == 201
    body = response.get_json()
    assert body["graduation"]["complete"] is False
    assert body["graduation"]["retryable"] is True
    assert body["graduation"]["sessions"]["status"] == "complete"
    assert body["graduation"]["session_pin"]["status"] == "failed"
    project_id = body["project"]
    assert web._load_manifest(project_id).cowriter_session_id is None

    retried = http_client.post(f"/api/projects/{project_id}/retry-graduation-transfer")
    assert retried.status_code == 200
    transfer = retried.get_json()["graduation"]
    assert transfer["complete"] is True
    assert transfer["session_pin"]["status"] == "pinned"
    assert web._load_manifest(project_id).cowriter_session_id == session.session_id


def test_partial_session_copy_retries_idempotently_without_overwriting_edits(
        http_client, monkeypatch):
    import screenplay_studio.ideas as ideas_module

    store, idea = _new_idea("Two Threads")
    source_sessions = SessionStore(store.sessions_dir(idea["id"]))
    first = source_sessions.create("First conversation")
    second = source_sessions.create("Second conversation")
    real_create = ideas_module.atomic_create_json

    def fail_second_session_once(path, value, *args, **kwargs):
        if (os.path.basename(path) == f"{second.session_id}.json"
                and os.path.basename(os.path.dirname(path)) == "sessions"):
            raise OSError("injected one-session write failure")
        return real_create(path, value, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(ideas_module, "atomic_create_json", fail_second_session_once)
        response = _graduate(http_client, idea["id"], title="Partial Carry")

    assert response.status_code == 201
    first_transfer = response.get_json()["graduation"]
    assert first_transfer["complete"] is False
    assert first_transfer["premise"]["status"] == "copied"
    assert first_transfer["sessions"]["status"] == "partial"
    assert first.session_id in first_transfer["sessions"]["copied"]
    assert [f["id"] for f in first_transfer["sessions"]["failed"]] == [second.session_id]
    assert first_transfer["session_pin"]["status"] == "deferred"
    assert store.load(idea["id"])["card"]["premise"] == "The premise must survive graduation."

    project_id = response.get_json()["project"]
    project_dir = web._project_dir(project_id)
    assert web._load_manifest(project_id).cowriter_session_id is None

    retried = http_client.post(f"/api/projects/{project_id}/retry-graduation-transfer")
    assert retried.status_code == 200
    transfer = retried.get_json()["graduation"]
    assert transfer["complete"] is True
    assert transfer["premise"]["status"] == "already_present"
    assert transfer["sessions"]["status"] == "complete"
    assert first.session_id in transfer["sessions"]["already_present"]
    assert second.session_id in transfer["sessions"]["copied"]
    assert transfer["session_pin"]["status"] == "pinned"
    assert web._load_manifest(project_id).cowriter_session_id in {
        first.session_id, second.session_id}

    # A second retry is idempotent. It recognizes equal JSON, and does not
    # replace a project-side edit made after the original transfer.
    again = http_client.post(f"/api/projects/{project_id}/retry-graduation-transfer")
    assert again.status_code == 200
    assert again.get_json()["graduation"]["complete"] is True
    assert again.get_json()["graduation"]["premise"]["status"] == "already_present"

    premise_path = os.path.join(project_dir, "premise.json")
    with open(premise_path, encoding="utf-8") as f:
        edited_premise = json.load(f)
    edited_premise["premise"] = "Writer's newer project-side version."
    with open(premise_path, "w", encoding="utf-8") as f:
        json.dump(edited_premise, f)
    conflicted = http_client.post(f"/api/projects/{project_id}/retry-graduation-transfer")
    assert conflicted.status_code == 200
    outcome = conflicted.get_json()["graduation"]
    assert outcome["complete"] is False
    assert outcome["premise"]["status"] == "conflict"
    with open(premise_path, encoding="utf-8") as f:
        assert json.load(f)["premise"] == "Writer's newer project-side version."


def test_scene_less_and_scanned_uploads_are_refused_by_both_routes(
        http_client, monkeypatch):
    from screenplay_parser import pdf_parser

    monkeypatch.setattr(pdf_parser, "_get_ocr_engine", lambda: None)
    scanned_pdf = (Path(__file__).parent / "fixtures" / "Pain_FD_4_scenes.pdf").read_bytes()
    ordinary = http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(scanned_pdf), "scan.pdf"), "title": "Ordinary Scan"},
        content_type="multipart/form-data",
    )
    assert ordinary.status_code == 400
    assert "no readable scenes" in ordinary.get_json()["error"].lower()

    store, idea = _new_idea("Scanned Idea")
    graduation = _graduate(http_client, idea["id"], scanned_pdf, "scan.pdf", "Graduated Scan")
    assert graduation.status_code == 400
    assert "no readable scenes" in graduation.get_json()["error"].lower()
    assert store.load(idea["id"])["card"]["logline"] == "A logline kept with its pages."
    assert http_client.get("/api/projects").get_json() == []

    # The Fountain prose case is the same post-parse state and must also leave
    # the original idea available while removing only the unusable new project.
    prose = b"A paragraph with no scene headings at all.\n"
    prose_result = _graduate(http_client, idea["id"], prose, "notes.fountain", "Graduated Prose")
    assert prose_result.status_code == 400
    assert store.load(idea["id"])["id"] == idea["id"]
    assert http_client.get("/api/projects").get_json() == []


def test_empty_graduation_upload_is_rejected_before_project_claim(http_client):
    store, idea = _new_idea("Empty Upload")
    response = _graduate(http_client, idea["id"], b"", "empty.fountain", "Empty Pages")
    assert response.status_code == 400
    assert "0 bytes" in response.get_json()["error"]
    assert store.load(idea["id"])["id"] == idea["id"]
    assert http_client.get("/api/projects").get_json() == []
