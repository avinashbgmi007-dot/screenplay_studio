"""Tests for screenplay_studio.diff.compare_drafts — the side-by-side compare
material: aligned rows per common scene between two drafts."""

import io

import pytest

from screenplay_studio.orchestrator import Orchestrator
from screenplay_studio import diff

from tests.test_diff import (
    DRAFT2,
    SAMPLE_SCRIPT,
    _upload,
    _write_draft2,
    analyzed_manifest,  # pytest fixture
    http_client,  # pytest fixture
)


class TestCompareModule:
    def test_compare_drafts_aligned_rows(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        Orchestrator(m).run_parse()

        result = diff.compare_drafts(m, "original", "active")
        assert result["from"] == "original"
        assert result["to"] == "active"
        assert result["common_scene_count"] >= 2

        scene1 = next(s for s in result["scenes"] if s["scene_number"] == 1)
        # the dialogue line that changed appears as a 'changed' row
        changed_rows = [r for r in scene1["rows"] if r["kind"] == "changed"]
        assert any(
            ("tell you" in (r["left"] or "")) or ("tell you" in (r["right"] or ""))
            for r in changed_rows
        )
        # unchanged lines are 'same' rows with both sides populated
        same_rows = [r for r in scene1["rows"] if r["kind"] == "same"]
        assert same_rows
        assert all(r["left"] and r["right"] for r in same_rows)

    def test_compare_kind_tags_cover_all_states(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        Orchestrator(m).run_parse()

        result = diff.compare_drafts(m, "original", "active")
        kinds = {r["kind"] for s in result["scenes"] for r in s["rows"]}
        # DRAFT2 changes scene 1 dialogue (replace); at minimum 'same' +
        # 'changed' must appear, and every tag must be a known one.
        assert {"same", "changed"} <= kinds
        for s in result["scenes"]:
            for r in s["rows"]:
                assert r["kind"] in ("same", "changed", "added", "removed")
                assert r["type"]  # element type present on every row

    def test_compare_unknown_draft_raises(self, analyzed_manifest):
        with pytest.raises(ValueError):
            diff.compare_drafts(analyzed_manifest, "ghost", "active")


class TestCompareApi:
    def test_compare_endpoint(self, http_client):
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(DRAFT2.encode()), "draft2.fountain")},
            content_type="multipart/form-data",
        )

        resp = http_client.get(f"/api/projects/{project}/compare?from=original&to=active")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["from"] == "original"
        assert data["to"] == "active"
        assert data["common_scene_count"] >= 2
        rows = [r for s in data["scenes"] for r in s["rows"]]
        assert any(r["kind"] == "changed" for r in rows)

    def test_compare_unknown_draft_400(self, http_client):
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        resp = http_client.get(f"/api/projects/{project}/compare?from=ghost&to=active")
        assert resp.status_code == 400

    def test_compare_defaults_to_previous_draft(self, http_client):
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(DRAFT2.encode()), "draft2.fountain")},
            content_type="multipart/form-data",
        )

        resp = http_client.get(f"/api/projects/{project}/compare")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["from"] == "original"  # default: previous draft
        assert data["to"] == "active"
