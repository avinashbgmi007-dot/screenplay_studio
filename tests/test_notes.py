"""
Writer's margin notes — the writer's own pencil, pinned to scenes and saved
per project, independent of the tool's findings and untouched by re-parses.
"""

import io
import os

import pytest

from screenplay_studio import notes as notes_module
from screenplay_studio.manifest import ProjectManifest

SAMPLE_SCRIPT = b"""Title: Notes Test
Author: Test

INT. STUDY - NIGHT

MARA takes out an old REVOLVER, setting it on the desk.

MARA
I'll tell you everything when this is over.

CUT TO:

INT. KITCHEN - DAY

Mara sits at the table, staring at nothing.
"""


@pytest.fixture
def http_client(tmp_path, mock_server):
    import screenplay_studio.webapp_server as webapp_server
    webapp_server.PROJECTS_DIR = str(tmp_path / "notes_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _upload(http_client):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"), "title": "Notes Test"},
        content_type="multipart/form-data",
    )


def _make_project(tmp_path, name="p"):
    """Create a project with a real source file on disk (create() copies it)."""
    src = tmp_path / "x.fountain"
    src.write_text("Title: T\n\nINT. X - DAY\n\nLine.\n", encoding="utf-8")
    return ProjectManifest.create(str(tmp_path / name), str(src), title="T")


class TestNotesModule:
    def test_add_and_load(self, tmp_path):
        m = _make_project(tmp_path)
        notes_module.add_note(m, 1, "Slow down this scene.")
        notes_module.add_note(m, None, "Whole-script thought: too quiet.")
        notes = notes_module.load_notes(m)
        assert len(notes) == 2
        assert notes[0]["scene_number"] is None  # newest first
        assert notes[0]["text"] == "Whole-script thought: too quiet."
        # per-scene filter
        assert [n["text"] for n in notes_module.notes_for_scene(m, 1)] == ["Slow down this scene."]

    def test_update_and_delete(self, tmp_path):
        m = _make_project(tmp_path)
        note = notes_module.add_note(m, 2, "first draft")
        updated = notes_module.update_note(m, note["id"], "second draft")
        assert updated["text"] == "second draft"
        assert notes_module.load_notes(m)[0]["text"] == "second draft"
        assert notes_module.delete_note(m, note["id"]) is True
        assert notes_module.load_notes(m) == []
        assert notes_module.delete_note(m, note["id"]) is False

    def test_anchored_note(self, tmp_path):
        """P2: a note can pin to an exact line (Google-Docs-style margin comment)."""
        m = _make_project(tmp_path)
        note = notes_module.add_note(m, 1, "This line could open with a bang.", anchor="MARA takes out an old REVOLVER")
        assert note["anchor"] == "MARA takes out an old REVOLVER"
        # scene-level notes stay backward-compatible (no anchor key surprises)
        plain = notes_module.add_note(m, 1, "Just a scene thought.")
        assert plain["anchor"] is None
        loaded = [n for n in notes_module.load_notes(m) if n["id"] == note["id"]][0]
        assert loaded["anchor"] == "MARA takes out an old REVOLVER"

    def test_blank_text_rejected(self, tmp_path):
        m = _make_project(tmp_path)
        with pytest.raises(ValueError):
            notes_module.add_note(m, 1, "   ")

    def test_bad_scene_number_rejected(self, tmp_path):
        m = _make_project(tmp_path)
        with pytest.raises(ValueError):
            notes_module.add_note(m, "not-a-number", "x")

    def test_survives_reparse(self, tmp_path):
        """Notes live in their own file — re-parsing never touches them."""
        m = _make_project(tmp_path)
        notes_module.add_note(m, 1, "keep me")
        # simulate a re-parse by touching other project files only
        m.save()
        assert notes_module.load_notes(m)[0]["text"] == "keep me"


class TestNotesAPI:
    def test_crud_flow(self, http_client):
        project = _upload(http_client).get_json()["project"]

        # empty by default
        resp = http_client.get(f"/api/projects/{project}/notes")
        assert resp.get_json() == {"notes": []}

        # create
        resp = http_client.post(f"/api/projects/{project}/notes", json={"scene_number": 1, "text": "Cut the second beat."})
        assert resp.status_code == 201
        note = resp.get_json()
        assert note["scene_number"] == 1

        # update
        resp = http_client.patch(f"/api/projects/{project}/notes/{note['id']}", json={"text": "Cut both beats."})
        assert resp.status_code == 200
        assert resp.get_json()["text"] == "Cut both beats."

        # list reflects the update
        resp = http_client.get(f"/api/projects/{project}/notes")
        assert resp.get_json()["notes"][0]["text"] == "Cut both beats."

        # delete
        resp = http_client.delete(f"/api/projects/{project}/notes/{note['id']}")
        assert resp.status_code == 200
        assert http_client.get(f"/api/projects/{project}/notes").get_json() == {"notes": []}

    def test_anchored_note_via_api(self, http_client):
        """P2: POST /notes carries the anchor (the exact line) end-to-end."""
        project = _upload(http_client).get_json()["project"]
        resp = http_client.post(f"/api/projects/{project}/notes",
                                json={"scene_number": 1, "text": "pinned", "anchor": "MARA takes out an old REVOLVER"})
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["anchor"] == "MARA takes out an old REVOLVER"
        # it round-trips through GET
        got = http_client.get(f"/api/projects/{project}/notes").get_json()["notes"]
        assert got[0]["anchor"] == "MARA takes out an old REVOLVER"

    def test_missing_text_400(self, http_client):
        project = _upload(http_client).get_json()["project"]
        resp = http_client.post(f"/api/projects/{project}/notes", json={"scene_number": 1, "text": "  "})
        assert resp.status_code == 400

    def test_unknown_note_404(self, http_client):
        project = _upload(http_client).get_json()["project"]
        assert http_client.patch(f"/api/projects/{project}/notes/nope", json={"text": "x"}).status_code == 404
        assert http_client.delete(f"/api/projects/{project}/notes/nope").status_code == 404

    def test_unknown_project_404(self, http_client):
        assert http_client.get("/api/projects/ghost/notes").status_code == 404
