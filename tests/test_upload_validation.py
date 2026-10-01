"""R5 (audit M3): degenerate uploads are rejected AT CREATION, not left on
the shelf to fail loudly minutes later at analyze.

The parser "succeeds" on a 0-byte file and on prose with no scene headings —
both produced a 201, and the writer first heard about it as an analyze 502
("Document has no parsed scenes") after leaving the desk believing the import
worked. Empty is refused up front with the true reason; scene-less is refused
after the parse with guidance, and the claimed project directory is REMOVED so
the shelf never lists a project that cannot be analyzed.
"""
import io
import os

import pytest

import screenplay_studio.webapp_server as webapp_server


@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "r5_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


SAMPLE = b"""Title: R5 Check
Author: T

INT. ROOM - DAY

Action line.

ANA
A line of dialogue.
"""


def _post(client, payload, name="script.fountain"):
    return client.post(
        "/api/projects",
        data={"file": (io.BytesIO(payload), name), "title": "R5 Case"},
        content_type="multipart/form-data",
    )


def test_zero_byte_upload_rejected_400_with_true_reason(http_client):
    resp = _post(http_client, b"")
    assert resp.status_code == 400
    assert "empty" in resp.get_json()["error"].lower()
    assert "0 bytes" in resp.get_json()["error"], "the writer is told it was a 0-byte drop, not a parse problem"


def test_sceneless_prose_rejected_400_and_not_added_to_shelf(http_client):
    prose = b"Title: notes\n\nJust some prose.\nNo slug lines here at all.\nAnother line.\n"
    resp = _post(http_client, prose, name="notes.txt")
    assert resp.status_code == 400
    body = resp.get_json()["error"]
    assert "no readable scenes" in body
    assert "Fountain" in body, "the error says what a valid upload looks like"
    # nothing added to the shelf
    listing = http_client.get("/api/projects").get_json()
    projects = listing if isinstance(listing, list) else listing.get("projects", [])
    assert projects == [], f"the shelf must stay empty, got: {projects}"


def test_sceneless_rejection_removes_the_claimed_directory(http_client, tmp_path):
    prose = b"Title: notes\n\nA paragraph without headings.\n"
    resp = _post(http_client, prose, name="notes.txt")
    assert resp.status_code == 400
    leftover = os.listdir(webapp_server.PROJECTS_DIR)
    assert leftover == [], f"no project directory may survive the rejection, got: {leftover}"


def test_valid_script_still_created_201(http_client):
    resp = _post(http_client, SAMPLE)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["stages"]["parse"] == "complete"
    # the stage dict is the summary's parse record; scene count rides GET /
    project = body["project"]
    assert project
    detail = http_client.get(f"/api/projects/{project}").get_json()
    assert detail["stages"]["parse"] == "complete"


def test_whitespace_only_upload_rejected(http_client):
    resp = _post(http_client, b"   \n\t\r\n  ")
    assert resp.status_code == 400, "whitespace is 0 useful bytes; parsed scenes would be 0"
    # either guard may catch it — the reason must be one of the two truths
    reason = resp.get_json()["error"].lower()
    assert ("empty" in reason) or ("no readable scenes" in reason)
