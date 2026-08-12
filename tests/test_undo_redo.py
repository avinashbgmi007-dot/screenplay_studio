"""
Per-edit undo/redo — the writer can reverse just the last change (and
re-apply it), instead of only having the all-or-nothing reset. Undo moves
the record to a redo stack; a fresh edit clears redo history; exact-match
only, never fuzzy-guessing on reversal.
"""

import io
import os

import pytest

from screenplay_studio import revision
from screenplay_studio.manifest import ProjectManifest

SAMPLE_SCRIPT = b"""Title: Undo Test
Author: Test

INT. STUDY - NIGHT

MARA takes out an old REVOLVER, setting it on the desk.

MARA
I'll tell you everything when this is over.

CUT TO:

INT. KITCHEN - DAY

Mara sits at the table, staring at nothing.
"""


def _make_project(tmp_path):
    src = tmp_path / "x.fountain"
    src.write_bytes(SAMPLE_SCRIPT)
    m = ProjectManifest.create(str(tmp_path / "p"), str(src), title="Undo Test")
    # create a parsed working copy via the parser, the same way the server does
    from screenplay_parser import parse_screenplay
    doc = parse_screenplay(str(m.source_path))
    doc.save(m.parsed_path)
    revision.ensure_working(m)
    return m


def _scene_text(m, scene_number):
    return "\n".join(el.text for s in revision.load_working(m).scenes if s.scene_number == scene_number for el in s.elements)


class TestUndoRedoModule:
    def test_undo_restores_and_redo_reapplies(self, tmp_path):
        m = _make_project(tmp_path)
        doc = revision.load_working(m)
        old_line = "MARA takes out an old REVOLVER, setting it on the desk."
        new_line = "MARA lays the REVOLVER on the desk."
        result = revision.apply_replacements(doc, 1, [{"old": old_line, "new": new_line}])
        assert result["applied"]
        revision.save_working(m, doc, record={"scene_number": 1, "applied": result["applied"], "skipped": [], "applied_at": 1})

        assert _scene_text(m, 1).count(new_line) == 1
        assert old_line not in _scene_text(m, 1)

        undone = revision.undo_last_edit(m)
        assert undone["restored"]
        assert old_line in _scene_text(m, 1)
        assert new_line not in _scene_text(m, 1)
        assert revision.edits_log(m) == []  # record moved to redo
        assert len(revision.redo_stack(m)) == 1

        redone = revision.redo_last_edit(m)
        assert redone["applied"]
        assert new_line in _scene_text(m, 1)
        assert old_line not in _scene_text(m, 1)
        assert len(revision.edits_log(m)) == 1
        assert revision.redo_stack(m) == []

    def test_undo_with_nothing_raises(self, tmp_path):
        m = _make_project(tmp_path)
        with pytest.raises(ValueError):
            revision.undo_last_edit(m)
        with pytest.raises(ValueError):
            revision.redo_last_edit(m)

    def test_fresh_edit_clears_redo(self, tmp_path):
        m = _make_project(tmp_path)
        doc = revision.load_working(m)
        r1 = revision.apply_replacements(doc, 1, [{"old": "MARA takes out an old REVOLVER, setting it on the desk.", "new": "MARA sets the REVOLVER down."}])
        revision.save_working(m, doc, record={"scene_number": 1, "applied": r1["applied"], "skipped": [], "applied_at": 1})
        revision.undo_last_edit(m)
        assert len(revision.redo_stack(m)) == 1

        # a new edit after undo must clear the redo stack
        r2 = revision.apply_replacements(doc, 2, [{"old": "Mara sits at the table, staring at nothing.", "new": "Mara stares out the window."}])
        revision.save_working(m, doc, record={"scene_number": 2, "applied": r2["applied"], "skipped": [], "applied_at": 2})
        assert revision.redo_stack(m) == []
        assert len(revision.edits_log(m)) == 1  # only the new edit

    def test_reset_clears_redo_stack(self, tmp_path):
        m = _make_project(tmp_path)
        doc = revision.load_working(m)
        r = revision.apply_replacements(doc, 1, [{"old": "MARA takes out an old REVOLVER, setting it on the desk.", "new": "MARA sets the REVOLVER down."}])
        revision.save_working(m, doc, record={"scene_number": 1, "applied": r["applied"], "skipped": [], "applied_at": 1})
        revision.undo_last_edit(m)
        assert len(revision.redo_stack(m)) == 1
        revision.reset_working(m)
        assert revision.redo_stack(m) == []
        assert revision.edits_log(m) == []

    def test_undo_record_has_id(self, tmp_path):
        m = _make_project(tmp_path)
        doc = revision.load_working(m)
        r = revision.apply_replacements(doc, 1, [{"old": "MARA takes out an old REVOLVER, setting it on the desk.", "new": "MARA sets the REVOLVER down."}])
        revision.save_working(m, doc, record={"scene_number": 1, "applied": r["applied"], "skipped": [], "applied_at": 1})
        assert revision.edits_log(m)[0]["id"]


@pytest.fixture
def http_client(tmp_path, mock_server):
    import screenplay_studio.webapp_server as webapp_server
    webapp_server.PROJECTS_DIR = str(tmp_path / "undo_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _upload(http_client):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"), "title": "Undo Test"},
        content_type="multipart/form-data",
    )


class TestUndoRedoAPI:
    def test_undo_redo_flow(self, http_client):
        project = _upload(http_client).get_json()["project"]
        base = f"/api/projects/{project}"

        # apply an edit
        resp = http_client.post(f"{base}/edits/apply", json={
            "scene_number": 1,
            "replacements": [{"old": "MARA takes out an old REVOLVER, setting it on the desk.", "new": "MARA sets the REVOLVER down."}],
        })
        assert resp.status_code == 200
        assert resp.get_json()["applied"]

        # verify the edit is in the working copy
        script = http_client.get(f"{base}/script").get_json()
        scene1 = next(s for s in script["scenes"] if s["scene_number"] == 1)
        texts = [e["text"] for e in scene1["elements"]]
        assert "MARA sets the REVOLVER down." in texts

        # undo
        resp = http_client.post(f"{base}/edits/undo")
        assert resp.status_code == 200
        assert resp.get_json()["undone"]["scene_number"] == 1
        script = http_client.get(f"{base}/script").get_json()
        scene1 = next(s for s in script["scenes"] if s["scene_number"] == 1)
        texts = [e["text"] for e in scene1["elements"]]
        assert "MARA takes out an old REVOLVER, setting it on the desk." in texts
        assert "MARA sets the REVOLVER down." not in texts

        # redo
        resp = http_client.post(f"{base}/edits/redo")
        assert resp.status_code == 200
        assert resp.get_json()["redone"]["scene_number"] == 1
        script = http_client.get(f"{base}/script").get_json()
        scene1 = next(s for s in script["scenes"] if s["scene_number"] == 1)
        texts = [e["text"] for e in scene1["elements"]]
        assert "MARA sets the REVOLVER down." in texts

    def test_undo_empty_returns_400(self, http_client):
        project = _upload(http_client).get_json()["project"]
        resp = http_client.post(f"/api/projects/{project}/edits/undo")
        assert resp.status_code == 400
        resp = http_client.post(f"/api/projects/{project}/edits/redo")
        assert resp.status_code == 400

    def test_unknown_project_404(self, http_client):
        assert http_client.post("/api/projects/ghost/edits/undo").status_code == 404
