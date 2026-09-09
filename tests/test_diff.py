"""Tests for screenplay_studio.diff — draft snapshotting, activation, and
draft-to-draft diffing (structural + findings)."""

import io
import json
import os

import pytest

from screenplay_parser import parse_fountain
from screenplay_studio.manifest import ProjectManifest
from screenplay_studio.orchestrator import Orchestrator
from screenplay_studio import diff

import screenplay_studio.webapp_server as webapp_server


DRAFT2 = """Title: E2E Test Script
Author: Test

INT. STUDY - NIGHT

MARA unlocks a drawer and takes out an old REVOLVER, setting it on the desk.

MARA
Now I have to tell you the truth.

DEREK watches her, uneasy.

DEREK
Just don't do anything stupid.

CUT TO:

INT. KITCHEN - DAY

Mara sits at the table.

MARA
I promise I'll explain everything.

CUT TO:

INT. STUDY - NIGHT

The REVOLVER is still there, untouched.

MARA
Some things are better left alone.

CUT TO:

INT. GARAGE - DAY

Mara finds DEREK hiding behind the tool bench.

MARA
I thought you were gone.
"""


@pytest.fixture
def analyzed_manifest(tmp_path, sample_fountain, mock_server):
    m = ProjectManifest.create(str(tmp_path / "proj"), sample_fountain)
    m.server_url = mock_server
    m.save()
    orch = Orchestrator(m)
    orch.run_parse()
    orch.run_analyze()
    return m


def _write_draft2(tmp_path, name="draft2.fountain"):
    p = tmp_path / name
    p.write_text(DRAFT2, encoding="utf-8")
    return str(p)


class TestSnapshotAndUpload:
    def test_upload_new_draft_snapshots_and_reparses(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        src = _write_draft2(tmp_path)
        diff.upload_new_draft(m, src, "draft2.fountain")

        assert m.active_draft == "draft-1"
        assert m.drafts[0]["name"] == "draft-1"
        assert m.source_filename == "draft2.fountain"
        # original snapshot exists and holds the OLD script
        original_parsed = diff.draft_parsed_path(m, "original")
        assert os.path.exists(original_parsed)
        # parse stage was re-queued (needs re-run on the new source)
        assert m.stage("parse").status == "pending"

    def test_reparse_after_upload(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        Orchestrator(m).run_parse()
        doc = diff._baseline_doc(m, "active")
        assert doc.scene_count == 4  # draft 2 added a scene

    def test_activate_draft_restores_files(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        Orchestrator(m).run_parse()

        diff.activate_draft(m, "original")
        assert m.active_draft == "original"
        doc = diff._baseline_doc(m, "active")
        assert doc.scene_count == 3
        assert any("tell you everything" in e.text for s in doc.scenes for e in s.elements)

    def test_activate_unknown_draft_raises(self, analyzed_manifest):
        with pytest.raises(ValueError):
            diff.activate_draft(analyzed_manifest, "ghost")


class TestStructuralDiff:
    def test_scene_diff_detects_added_changed(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        Orchestrator(m).run_parse()

        result = diff.diff_drafts(m, "original", "active")
        scenes = result["scenes"]
        assert scenes["added_scenes"] == [4]
        # scene 1's dialogue changed -> listed as changed
        changed_nums = [c["scene_number"] for c in scenes["changed_scenes"]]
        assert 1 in changed_nums
        scene1 = next(c for c in scenes["changed_scenes"] if c["scene_number"] == 1)
        assert any("tell you" in (l["old"] or "") for l in scene1["changed_lines"])

    def test_findings_diff_marks_resolved(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        Orchestrator(m).run_parse()
        Orchestrator(m).run_analyze()  # re-analyze the new draft

        result = diff.diff_drafts(m, "original", "active")
        summary = result["findings"]["summary"]
        # the dialogue finding's quote was changed -> resolved
        assert summary["resolved"] >= 1
        # theme/character findings with identical issues carried over
        assert summary["carried"] >= 1


class TestManifestDraftsPersistence:
    def test_drafts_survive_reload(self, analyzed_manifest, tmp_path):
        m = analyzed_manifest
        diff.upload_new_draft(m, _write_draft2(tmp_path), "draft2.fountain")
        reloaded = ProjectManifest.load(m.project_dir)
        assert reloaded.active_draft == "draft-1"
        assert reloaded.drafts[0]["source_filename"] == "draft2.fountain"


# ---------- webapp API ----------

@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


SAMPLE_SCRIPT = b"""Title: Diff Test Script
Author: Test

INT. STUDY - NIGHT

MARA takes out an old REVOLVER, setting it on the desk.

MARA
I'll tell you everything when this is over.

CUT TO:

INT. KITCHEN - DAY

Mara sits at the table.

MARA
I promise I'll explain everything.
"""


def _upload(http_client, data, filename="script.fountain", title="Diff Test"):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(data), filename), "title": title},
        content_type="multipart/form-data",
    )


class TestDraftApi:
    def test_upload_draft_flow(self, http_client):
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")

        resp = http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(DRAFT2.encode()), "draft2.fountain")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active_draft"] == "draft-1"
        assert len(data["drafts"]) == 1
        # parse re-queued because the source changed
        assert data["stages"]["parse"] == "complete"  # run_parse ran inside the endpoint
        assert data["stages"]["analyze"] == "pending"

    def test_diff_endpoint_after_draft(self, http_client):
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(DRAFT2.encode()), "draft2.fountain")},
            content_type="multipart/form-data",
        )
        http_client.post(f"/api/projects/{project}/analyze")

        resp = http_client.get(f"/api/projects/{project}/diff?from=original&to=active")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["findings"]["summary"]["resolved"] >= 1
        assert data["scenes"]["added_scenes"] == [3, 4]  # SAMPLE_SCRIPT has 2 scenes; DRAFT2 has 4

    def test_activate_draft_api(self, http_client):
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(DRAFT2.encode()), "draft2.fountain")},
            content_type="multipart/form-data",
        )

        resp = http_client.post(f"/api/projects/{project}/drafts/activate", json={"name": "original"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active_draft"] == "original"

        script = http_client.get(f"/api/projects/{project}/script").get_json()
        texts = [e["text"] for s in script["scenes"] for e in s["elements"]]
        assert "I'll tell you everything when this is over." in texts

    def test_diff_requires_known_draft(self, http_client):
        project = _upload(http_client, SAMPLE_SCRIPT).get_json()["project"]
        resp = http_client.get(f"/api/projects/{project}/diff?from=ghost&to=active")
        assert resp.status_code == 400
