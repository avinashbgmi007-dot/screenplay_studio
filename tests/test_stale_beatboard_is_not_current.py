"""
Gap 20: a saved beat-board order could look current when it was stale.

Reproduced at module level: with a saved order [2,1] and a script the board no
longer fits, `get_order` returned the NATURAL order while `has_board` still
returned True, and the old order stayed on disk. The desk was told `saved: true`
and drew a board -- so the one thing the writer could not see was that the board
they saved was no longer the board they were looking at.

Two failures, and the second is the one nobody had noticed:

1. The fallback was silent. A stale board and a current board produced the same
   `saved` flag.
2. A board can be "valid" and still WRONG. The stored form is a permutation of
   scene numbers, so a re-parse that keeps the count but changes what scene 3 is
   passes every check and gets drawn over different scenes. Numbers are not
   identity.

The fix keeps the writer's arrangement on disk (never rewritten on a failed
match), draws the natural order, and says why -- with `saved_order` and
`changed_scenes` so the writer can reconcile instead of being handed a silent
reset.
"""

import json
import os

import pytest

from screenplay_studio import beatboard
from screenplay_studio.manifest import ProjectManifest


SOURCE = """INT. STUDY - NIGHT

MARA unlocks a drawer.

INT. KITCHEN - DAY

Mara sits at the table.

INT. GARAGE - NIGHT

The car is gone.
"""


@pytest.fixture
def board(tmp_path, monkeypatch):
    """A parsed project whose working copy is the sample script."""
    import screenplay_studio.webapp_server as webapp_server

    d = tmp_path
    src = d / "s.fountain"
    src.write_text(SOURCE, encoding="utf-8")
    m = ProjectManifest.create(str(d / "p"), str(src))
    m.save()

    root = d / "projects"
    root.mkdir()
    monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(root))
    webapp_server.app.config["TESTING"] = True
    client = webapp_server.app.test_client()
    up = client.post("/api/projects",
                     data={"file": (open(str(src), "rb"), "s.fountain")},
                     content_type="multipart/form-data")
    assert up.status_code in (200, 201), up.get_data(as_text=True)
    name = up.get_json().get("project") or up.get_json().get("name")
    # drive the REAL parse stage through the same helper the app uses
    from screenplay_studio.revision import ensure_working
    from screenplay_studio.manifest import ProjectManifest as PM
    m = PM.load(os.path.join(str(root), name))
    m.mark_complete("parse", {"parsed": m.parsed_path})
    ensure_working(m)
    m.name = name
    return client, m


class TestAFittingBoardIsNotStale:

    def test_a_fresh_board_draws_itself_and_is_not_stale(self, board):
        client, m = board
        assert client.put("/api/projects/%s/beatboard" % m.name,
                          json={"order": [3, 1, 2]}).status_code == 200
        body = client.get("/api/projects/%s/beatboard" % m.name).get_json()
        assert body["order"] == [3, 1, 2]
        assert body["saved"] is True
        assert body["stale"] is False

    def test_the_saved_board_records_what_each_card_was(self, board):
        client, m = board
        client.put("/api/projects/%s/beatboard" % m.name, json={"order": [3, 1, 2]})
        stored = json.load(open(beatboard._path(m), encoding="utf-8"))
        assert stored["headings"]["3"] == "INT. GARAGE - NIGHT", (
            "the board stored positions but not identities, so a re-parse that "
            "keeps the count can quietly re-point every card")


class TestAStaleBoardSaysSo:

    def test_a_saved_order_that_no_longer_fits_is_reported_stale(self, board):
        client, m = board
        client.put("/api/projects/%s/beatboard" % m.name, json={"order": [3, 1, 2]})
        # a re-parse loses a scene: the saved permutation cannot fit
        beatboard._save(m, {**json.load(open(beatboard._path(m), encoding="utf-8")),
                            "order": [3, 1]})
        body = client.get("/api/projects/%s/beatboard" % m.name).get_json()
        assert body["stale"] is True, "a board that no longer fits reported itself current"
        assert body["saved"] is True, "the board stopped admitting it exists"
        assert body["order"] == [1, 2, 3], "a stale board was drawn over the script"
        assert body["saved_order"] == [3, 1], "the writer's arrangement was not preserved"
        assert body["stale_reason"], "staleness was reported without a reason"

    def test_the_writers_arrangement_is_never_rewritten_by_a_read(self, board):
        client, m = board
        beatboard._save(m, {"order": [3, 1], "saved_at": 1.0})
        before = open(beatboard._path(m), encoding="utf-8").read()
        client.get("/api/projects/%s/beatboard" % m.name)
        assert open(beatboard._path(m), encoding="utf-8").read() == before, (
            "reading a stale board overwrote what the writer saved")

    def test_a_same_number_different_scene_is_caught(self, board):
        # The failure a permutation check cannot see: three scenes still exist
        # and the count is unchanged, but scene 3 is now something else.
        client, m = board
        client.put("/api/projects/%s/beatboard" % m.name, json={"order": [3, 1, 2]})
        stored = json.load(open(beatboard._path(m), encoding="utf-8"))
        stored["headings"]["3"] = "INT. ROOFTOP - DAWN"   # what scene 3 used to be
        beatboard._save(m, stored)
        body = client.get("/api/projects/%s/beatboard" % m.name).get_json()
        assert body["stale"] is True, (
            "scene 3 became a different scene and the board still looked current")
        assert 3 in body["changed_scenes"]
        assert body["verified_by"] == "scenes"

    def test_a_legacy_board_without_headings_is_honest_about_its_limit(self, board):
        client, m = board
        # a board saved before gap 20: permutation only, no identity record
        beatboard._save(m, {"order": [2, 1, 3], "saved_at": 1.0})
        body = client.get("/api/projects/%s/beatboard" % m.name).get_json()
        assert body["stale"] is False
        assert body["verified_by"] == "numbers_only", (
            "an unverifiable board was presented as verified")

    def test_export_refuses_a_stale_board(self, board):
        client, m = board
        beatboard._save(m, {"order": [3, 1], "saved_at": 1.0})
        with pytest.raises(ValueError) as exc:
            beatboard.export_reordered(m)
        assert "no longer matches" in str(exc.value)
        assert "Re-save" in str(exc.value), (
            "the export error does not tell the writer what to do")
