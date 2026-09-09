"""
Beat board — a proposed scene order on the writer's corkboard. Validated
permutation storage, plus export of the working copy reordered (scenes
renumbered 1..N) without touching the actual draft.
"""

import io
import os

import pytest

from screenplay_studio import beatboard
from screenplay_studio.manifest import ProjectManifest

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "pain_tenglish.fountain")


def _make_project(tmp_path):
    src = tmp_path / "pain.fountain"
    src.write_bytes(open(FIXTURE, "rb").read())
    m = ProjectManifest.create(str(tmp_path / "p"), str(src), title="Pain")
    from screenplay_parser import parse_screenplay
    doc = parse_screenplay(str(m.source_path))
    doc.save(m.parsed_path)
    from screenplay_studio.revision import ensure_working
    ensure_working(m)
    return m


class TestBeatBoardModule:
    def test_natural_order_when_unset(self, tmp_path):
        m = _make_project(tmp_path)
        order = beatboard.get_order(m)
        assert order == [1, 2, 3, 4, 5, 6]
        assert beatboard.has_board(m) is False

    def test_set_and_get_order(self, tmp_path):
        m = _make_project(tmp_path)
        new_order = [6, 5, 4, 3, 2, 1]
        board = beatboard.set_order(m, new_order)
        assert board["order"] == new_order
        assert beatboard.get_order(m) == new_order
        assert beatboard.has_board(m) is True

    def test_invalid_order_rejected(self, tmp_path):
        m = _make_project(tmp_path)
        with pytest.raises(ValueError):
            beatboard.set_order(m, [1, 2, 3])  # missing scenes
        with pytest.raises(ValueError):
            beatboard.set_order(m, [1, 2, 3, 4, 5, 7])  # wrong number
        with pytest.raises(ValueError):
            beatboard.set_order(m, "nope")

    def test_stale_board_falls_back_to_natural(self, tmp_path):
        m = _make_project(tmp_path)
        beatboard.set_order(m, [1, 2, 3, 4, 5, 6])
        # a board referencing scenes that no longer exist must not crash
        import json
        with open(beatboard._path(m), "w", encoding="utf-8") as f:
            json.dump({"order": [1, 2, 9, 99, 5, 6]}, f)
        assert beatboard.get_order(m) == [1, 2, 3, 4, 5, 6]

    def test_reset_restores_natural(self, tmp_path):
        m = _make_project(tmp_path)
        beatboard.set_order(m, [6, 5, 4, 3, 2, 1])
        beatboard.reset_order(m)
        assert beatboard.get_order(m) == [1, 2, 3, 4, 5, 6]
        assert beatboard.has_board(m) is False

    def test_export_reordered_sequence(self, tmp_path):
        m = _make_project(tmp_path)
        new_order = [3, 1, 2, 4, 5, 6]
        beatboard.set_order(m, new_order)
        text = beatboard.export_reordered(m, "fountain")
        # parse the exported text — scenes must appear in the new order
        from screenplay_parser.text_parser import parse_text
        import tempfile
        out = os.path.join(tempfile.mkdtemp(), "reordered.fountain")
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        re = parse_text(out, source_format="fountain")
        headings = [s.heading_raw for s in re.scenes]
        from screenplay_studio.revision import load_working
        orig = {s.scene_number: s.heading_raw for s in load_working(m).scenes}
        assert headings == [orig[n] for n in new_order]

    def test_export_reordered_does_not_touch_working_copy(self, tmp_path):
        from screenplay_studio.revision import load_working
        m = _make_project(tmp_path)
        before = [s.heading_raw for s in load_working(m).scenes]
        beatboard.set_order(m, [6, 5, 4, 3, 2, 1])
        beatboard.export_reordered(m, "fountain")
        after = [s.heading_raw for s in load_working(m).scenes]
        assert after == before  # the draft itself is untouched

    def test_board_view_cards(self, tmp_path):
        m = _make_project(tmp_path)
        view = beatboard.board_view(m)
        assert [c["scene_number"] for c in view["cards"]] == [1, 2, 3, 4, 5, 6]
        card = view["cards"][1]
        assert card["heading_raw"]
        assert card["page_estimate"] > 0
        assert "your_notes" in card


@pytest.fixture
def http_client(tmp_path, mock_server):
    import screenplay_studio.webapp_server as webapp_server
    webapp_server.PROJECTS_DIR = str(tmp_path / "bb_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _upload(http_client):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(open(FIXTURE, "rb").read()), "pain.fountain"), "title": "Pain"},
        content_type="multipart/form-data",
    )


class TestBeatBoardAPI:
    def test_get_put_flow(self, http_client):
        project = _upload(http_client).get_json()["project"]
        base = f"/api/projects/{project}/beatboard"

        view = http_client.get(base).get_json()
        assert view["order"] == [1, 2, 3, 4, 5, 6]
        assert view["saved"] is False

        new_order = [6, 5, 4, 3, 2, 1]
        resp = http_client.put(base, json={"order": new_order})
        assert resp.status_code == 200
        assert http_client.get(base).get_json()["order"] == new_order

    def test_invalid_order_400(self, http_client):
        project = _upload(http_client).get_json()["project"]
        resp = http_client.put(f"/api/projects/{project}/beatboard", json={"order": [1, 2]})
        assert resp.status_code == 400

    def test_reset_endpoint(self, http_client):
        project = _upload(http_client).get_json()["project"]
        base = f"/api/projects/{project}/beatboard"
        http_client.put(base, json={"order": [6, 5, 4, 3, 2, 1]})
        resp = http_client.post(f"{base}/reset")
        assert resp.status_code == 200
        assert http_client.get(base).get_json()["order"] == [1, 2, 3, 4, 5, 6]

    def test_export_endpoint(self, http_client):
        project = _upload(http_client).get_json()["project"]
        base = f"/api/projects/{project}/beatboard"
        http_client.put(base, json={"order": [3, 1, 2, 4, 5, 6]})
        resp = http_client.get(f"{base}/export?format=fountain")
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        # scene 3's heading must come before scene 1's heading in the export
        assert text.index("ROAD-SIDE") < text.index("HOSPITAL")
