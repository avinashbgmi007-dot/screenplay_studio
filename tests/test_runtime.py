"""
Per-scene runtime estimates — every scene's word count translated to
screen minutes (~1 page per minute), surfaced per-scene in the script view
and totaled in the stats report.
"""

import io
import os

import pytest

from screenplay_parser import stats
from screenplay_parser.text_parser import parse_fountain

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "pain_tenglish.fountain")


class TestSceneEstimates:
    def test_every_scene_has_an_estimate(self):
        doc = parse_fountain(FIXTURE)
        estimates = stats.scene_estimates(doc)
        assert set(estimates.keys()) == {s.scene_number for s in doc.scenes}
        for est in estimates.values():
            assert est["words"] > 0
            assert est["minutes"] > 0
            assert est["dialogue_lines"] >= 0

    def test_words_track_dialogue_plus_action(self):
        doc = parse_fountain(FIXTURE)
        estimates = stats.scene_estimates(doc)
        # scene 2 is dialogue-heavy — it must register dialogue lines
        assert estimates[2]["dialogue_lines"] >= 3
        # minutes scale with words: more words => >= minutes
        est1, est3 = estimates[1], estimates[3]
        if est1["words"] >= est3["words"]:
            assert est1["minutes"] >= est3["minutes"]

    def test_minutes_formula(self):
        doc = parse_fountain(FIXTURE)
        est = stats.scene_estimates(doc)[2]
        expected = round(max(est["words"] / stats.WORDS_PER_SCREEN_MINUTE, 0.1), 1)
        assert est["minutes"] == expected

    def test_total_runtime_in_stats(self):
        doc = parse_fountain(FIXTURE)
        report = stats.full_stats_report(doc)
        assert report["runtime_minutes"] > 0
        assert report["scene_estimates"][1]["minutes"] > 0

    def test_short_scene_has_floor(self):
        doc = parse_fountain(FIXTURE)
        # a near-empty scene must still get the 0.1 min floor, not 0
        est = stats.scene_estimates(doc)[1]
        assert est["minutes"] >= 0.1


class TestRuntimeAPI:
    @pytest.fixture
    def http_client(self, tmp_path, mock_server):
        import screenplay_studio.webapp_server as webapp_server
        webapp_server.PROJECTS_DIR = str(tmp_path / "runtime_projects")
        os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
        webapp_server.CONFIG["server_url"] = mock_server
        webapp_server.app.config["TESTING"] = True
        return webapp_server.app.test_client()

    def test_script_response_carries_estimates(self, http_client):
        resp = http_client.post(
            "/api/projects",
            data={"file": (io.BytesIO(open(FIXTURE, "rb").read()), "pain.fountain"), "title": "Pain"},
            content_type="multipart/form-data",
        )
        project = resp.get_json()["project"]
        script = http_client.get(f"/api/projects/{project}/script").get_json()
        assert script["runtime_minutes"] > 0
        with_est = [s for s in script["scenes"] if "page_estimate" in s]
        assert len(with_est) == len(script["scenes"])
        assert all(s["page_estimate"] > 0 for s in with_est)
        assert all(s["word_count"] > 0 for s in with_est)
