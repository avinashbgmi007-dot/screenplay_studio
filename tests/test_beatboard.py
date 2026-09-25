"""
Beat board — a proposed scene order on the writer's corkboard. Validated
permutation storage, plus export of the working copy reordered (scenes
renumbered 1..N) without touching the actual draft.
"""

import io
import os

import pytest

import screenplay_studio.webapp_server as webapp_server
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


def _make_three_scene_project(tmp_path, sample_fountain, name="p3"):
    """A 3-scene project — the shape L6 needs, because a string order only
    survives the permutation check when its digits happen to be a valid
    permutation (a 3-scene script turns '312' into [3, 1, 2])."""
    m = ProjectManifest.create(str(tmp_path / name), sample_fountain, title="Three")
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

    def test_a_string_order_is_rejected_not_read_as_digits(self, tmp_path, sample_fountain):
        """L6 (re-audit 2026-09-24): {'order': '312'} used to iterate the string,
        coerce each character and SAVE [3, 1, 2] — a valid permutation of a
        3-scene script, so nothing failed and the board silently changed."""
        m = _make_three_scene_project(tmp_path, sample_fountain)
        assert beatboard.scene_numbers(m) == [1, 2, 3]

        with pytest.raises(ValueError, match="list"):
            beatboard.set_order(m, "312")

        assert beatboard.get_order(m) == [1, 2, 3]  # still the natural order
        assert beatboard.has_board(m) is False  # AND nothing was persisted

    def test_order_items_must_be_integers_not_bools_or_strings(self, tmp_path, sample_fountain):
        """L6 (re-audit 2026-09-24): int() coerces bools/float-strings too, so
        [True, 2, 3] persisted as [1, 2, 3] — same silent drift, one layer in."""
        m = _make_three_scene_project(tmp_path, sample_fountain)
        for bogus in ([True, 2, 3], ["1", 2, 3], [1.0, 2, 3]):
            with pytest.raises(ValueError):
                beatboard.set_order(m, bogus)
        assert beatboard.has_board(m) is False


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

    def test_string_order_is_rejected_at_http_boundary(self, http_client):
        """L6 (re-audit 2026-09-24): the SPA sends an array, but a string must
        fail loudly with the module's existing 400 rather than be iterated."""
        project = _upload(http_client).get_json()["project"]
        base = f"/api/projects/{project}/beatboard"
        resp = http_client.put(base, json={"order": "312"})
        assert resp.status_code == 400
        assert "list" in resp.get_json()["error"]
        assert http_client.get(base).get_json()["saved"] is False


def _upload_unparsed(http_client):
    """A project whose upload parse FAILED.

    /api/projects persists the manifest before it parses, so a parse failure (an
    unsupported .docx here) leaves a project on disk with parse != complete and
    no parsed.json at all — the state L3 was reproduced in.
    """
    resp = http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(b"not a screenplay"), "script.docx"), "title": "Unparsed"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 500, resp.get_data(as_text=True)
    projects = http_client.get("/api/projects").get_json()
    assert len(projects) == 1, projects
    name = projects[0]["project"]

    m = ProjectManifest.load(os.path.join(webapp_server.PROJECTS_DIR, name))
    assert m.stage("parse").status != "complete", "precondition: the parse stage never completed"
    assert not os.path.exists(m.parsed_path), "precondition: there is no parsed script on disk"
    return name


class TestBeatBoardBeforeParse:
    """L3 (re-audit 2026-09-24): every beatboard route must answer the same 400
    its siblings (/script, /rewrite, /quickcheck) answer when the parse stage
    never completed — not a 500 whose message also carries a filesystem path."""

    @pytest.mark.parametrize("method,path,body", [
        ("GET", "", None),
        ("PUT", "", {"order": [1, 2, 3, 4, 5, 6]}),
        ("POST", "/reset", None),
        ("GET", "/export?format=fountain", None),
    ])
    def test_each_beatboard_route_400s_before_parse(self, http_client, method, path, body):
        project = _upload_unparsed(http_client)
        url = f"/api/projects/{project}/beatboard{path}"
        call = getattr(http_client, method.lower())
        resp = call(url, json=body) if body is not None else call(url)

        assert resp.status_code == 400, f"{method} {url} -> {resp.status_code} {resp.get_data(as_text=True)}"
        # the message names the state, and leaks no filesystem path
        assert resp.get_json()["error"] == "Project hasn't been parsed yet."
