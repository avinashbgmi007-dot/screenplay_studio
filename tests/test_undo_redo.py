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


class TestDamagedHistoryStores:
    """BE-M1 / BE-M2 — the undo/redo stores are writer-owned, so they follow the
    store contract: MISSING -> empty, PRESENT-BUT-UNREADABLE -> an error.

    The redo stack used to collapse damage into `[]` (the A2/A3 shape), which is
    worse than it sounds: the writer was told "Nothing to redo" about a stack
    that was sitting right there, and `undo_last_edit`'s load-modify-write then
    appended to that phantom empty list and overwrote the only recoverable copy.
    """

    def test_damaged_redo_stack_is_reported_not_read_as_empty(self, tmp_path):
        from screenplay_studio.jsonio import StoreUnreadable
        m = _make_project(tmp_path)
        _seed_redo(m)
        _damage(revision.edits_redo_path(m))

        # the reader reports damage instead of answering "nothing here"
        with pytest.raises(StoreUnreadable):
            revision.redo_stack(m)

        # and redo says "damaged", never the false "Nothing to redo."
        with pytest.raises(StoreUnreadable):
            revision.redo_last_edit(m)

    def test_damaged_redo_stack_survives_an_undo(self, tmp_path):
        """The load-modify-write behind undo must not finalise the loss."""
        from screenplay_studio.jsonio import StoreUnreadable
        m = _make_project(tmp_path)
        _seed_one_edit(m)
        _seed_redo(m)
        path = revision.edits_redo_path(m)
        _damage(path)
        with open(path, encoding="utf-8") as f:
            damaged = f.read()

        with pytest.raises(StoreUnreadable):
            revision.undo_last_edit(m)

        with open(path, encoding="utf-8") as f:
            assert f.read() == damaged, "the damaged redo stack was overwritten"

    def test_damaged_redo_stack_refuses_before_consuming_the_undo(self, tmp_path):
        """A refusal must leave the writer exactly where they were. Reading the
        redo stack up front is what buys this: detect the damage, then decline —
        rather than rewriting the working copy and popping the edit log first."""
        from screenplay_studio.jsonio import StoreUnreadable
        m = _make_project(tmp_path)
        _seed_one_edit(m)
        _seed_redo(m)
        _damage(revision.edits_redo_path(m))

        with pytest.raises(StoreUnreadable):
            revision.undo_last_edit(m)

        assert len(revision.edits_log(m)) == 1, (
            "the undo was consumed by an operation that then failed — the writer "
            "lost an edit they never got to undo")

    def test_damaged_edit_log_is_reported_not_read_as_empty(self, tmp_path):
        """BE-M2: the sibling file. A damaged edits.json must not surface as a
        bare JSONDecodeError (which the webapp turns into a 400 'bad request'
        for what is really a damaged disk)."""
        from screenplay_studio.jsonio import StoreUnreadable
        m = _make_project(tmp_path)
        _seed_one_edit(m)
        _damage(revision.edits_log_path(m))

        with pytest.raises(StoreUnreadable):
            revision.edits_log(m)

    def test_damaged_edit_log_refuses_before_consuming_the_redo(self, tmp_path):
        """The mirror of the undo case: a damaged edits.json must not let the
        redo run half-way and then fail, consuming the redo record."""
        from screenplay_studio.jsonio import StoreUnreadable
        m = _make_project(tmp_path)
        _seed_redo(m)
        _seed_one_edit(m)
        _damage(revision.edits_log_path(m))

        with pytest.raises(StoreUnreadable):
            revision.redo_last_edit(m)

        assert len(revision.redo_stack(m)) == 1, (
            "the redo record was consumed by an operation that then failed")

    def test_missing_and_valid_stores_still_behave(self, tmp_path):
        """The distinction is the point — an absent store is NOT damage."""
        m = _make_project(tmp_path)
        assert revision.redo_stack(m) == []
        assert revision.edits_log(m) == []
        with pytest.raises(ValueError, match="Nothing to redo"):
            revision.redo_last_edit(m)

    def test_healthy_undo_redo_cycle_still_works(self, tmp_path):
        """Guard against over-correcting: the ordinary cycle is untouched."""
        m = _make_project(tmp_path)
        _seed_one_edit(m, scene_number=1, applied=[
            {"old": "MARA takes out an old REVOLVER, setting it on the desk.",
             "new": "MARA lays the REVOLVER on the desk."}])
        undone = revision.undo_last_edit(m)
        assert undone["undone"]["id"] == "aa11"
        assert len(revision.redo_stack(m)) == 1
        redone = revision.redo_last_edit(m)
        assert redone["redone"]["id"] == "aa11"
        assert revision.redo_stack(m) == []


def _damage(path: str) -> None:
    """Crash-truncate a store, written outside the store API (a crash/AV/disk
    fault, not something the store layer would ever produce)."""
    with open(path, encoding="utf-8") as f:
        good = f.read()
    assert good, f"{path} was empty — nothing to truncate"
    with open(path, "w", encoding="utf-8") as f:
        f.write(good[: max(1, len(good) // 2)])


def _seed_redo(m) -> None:
    """A valid redo stack on disk, written directly (no undo needed to get one)."""
    import json as _json
    with open(revision.edits_redo_path(m), "w", encoding="utf-8") as f:
        _json.dump([{"id": "bb22", "scene_number": 1,
                     "applied": [{"old": "a", "new": "b"}]}], f)


def _seed_one_edit(m, scene_number=1, applied=None) -> None:
    """Put the project in the state an undo expects: a working copy plus one
    applied edit in the log.

    Written directly rather than through `save_working`, because that calls
    `clear_redo()` — which would delete the very stack these tests damage.
    `_make_project` has already produced the working copy via `ensure_working`.
    """
    import json as _json
    with open(revision.edits_log_path(m), "w", encoding="utf-8") as f:
        _json.dump([{"id": "aa11", "scene_number": scene_number,
                     "applied": applied if applied is not None else [],
                     "skipped": [], "applied_at": 1}], f)


class TestDamagedHistoryAPI:
    """The damage has to reach the writer, not just the loader."""

    def test_damaged_redo_stack_answers_503_not_400(self, http_client):
        project = _upload(http_client).get_json()["project"]
        base = f"/api/projects/{project}"

        http_client.post(f"{base}/edits/apply", json={
            "scene_number": 1,
            "replacements": [{"old": "MARA takes out an old REVOLVER, setting it on the desk.",
                              "new": "MARA sets the REVOLVER down."}],
        })
        assert http_client.post(f"{base}/edits/undo").status_code == 200

        import screenplay_studio.webapp_server as webapp_server
        redo_path = os.path.join(webapp_server.PROJECTS_DIR, project, "edits.redo.json")
        assert os.path.exists(redo_path), "the undo should have left a redo stack"
        _damage(redo_path)
        with open(redo_path, encoding="utf-8") as f:
            damaged = f.read()

        resp = http_client.post(f"{base}/edits/redo")
        assert resp.status_code == 503, (
            f"a damaged redo stack answered {resp.status_code}: {resp.data[:200]}")
        body = resp.get_json()
        assert body.get("unreadable") is True
        assert "edits.redo.json" in body.get("error", ""), body

        with open(redo_path, encoding="utf-8") as f:
            assert f.read() == damaged, "the damaged redo stack was overwritten"


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
