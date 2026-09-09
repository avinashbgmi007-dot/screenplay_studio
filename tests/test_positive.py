"""Positive E2E tests for the orchestrator."""
import os

from screenplay_studio.manifest import ProjectManifest
from screenplay_studio.orchestrator import Orchestrator


def _make_manifest(tmp_path, sample_fountain, mock_server, name="proj"):
    project_dir = str(tmp_path / name)
    manifest = ProjectManifest.create(project_dir, sample_fountain)
    manifest.server_url = mock_server
    manifest.save()
    return manifest


class TestFullPipeline:
    def test_parse_stage_produces_expected_files(self, tmp_path, sample_fountain, mock_server):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()

        assert manifest.stage("parse").status == "complete"
        assert os.path.exists(manifest.parsed_path)
        assert os.path.exists(manifest.kg_path)

        import json
        parsed = json.load(open(manifest.parsed_path))
        assert parsed["scene_count"] == 3
        kg = json.load(open(manifest.kg_path))
        assert any(p["name"] == "REVOLVER" for p in kg["prop_candidates"])

    def test_analyze_stage_produces_report(self, tmp_path, sample_fountain, mock_server):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()
        orch.run_analyze()

        assert manifest.stage("analyze").status == "complete"
        assert os.path.exists(manifest.report_md_path)
        assert os.path.exists(manifest.report_findings_path)

        import json
        findings = json.load(open(manifest.report_findings_path))
        assert findings["coverage"] is not None
        categories = {f["category"] for f in findings["findings"]}
        assert "plot_thread" in categories

    def test_chat_stage_grounds_in_report(self, tmp_path, sample_fountain, mock_server):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()
        orch.run_analyze()
        session, engine, store = orch.start_chat()

        assert manifest.stage("chat").status == "complete"
        reply = engine.send_message(session, "What's the overall read?")
        assert "findings_seen=" in reply
        import re
        count = int(re.search(r"findings_seen=(\d+)", reply).group(1))
        assert count > 0

    def test_run_full_convenience_method(self, tmp_path, sample_fountain, mock_server):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_full(skip_chat=True)
        assert manifest.stage("parse").status == "complete"
        assert manifest.stage("analyze").status == "complete"
        assert manifest.stage("chat").status == "pending"

    def test_run_full_with_chat(self, tmp_path, sample_fountain, mock_server):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        result = orch.run_full(skip_chat=False)
        assert result is not None
        session, engine, store = result
        assert manifest.stage("chat").status == "complete"


class TestManifestPersistence:
    def test_manifest_reload_preserves_all_stage_status(self, tmp_path, sample_fountain, mock_server):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()
        orch.run_analyze()

        reloaded = ProjectManifest.load(manifest.project_dir)
        assert reloaded.stage("parse").status == "complete"
        assert reloaded.stage("analyze").status == "complete"
        assert reloaded.model_id == manifest.model_id

    def test_resume_skips_already_complete_stages(self, tmp_path, sample_fountain, mock_server):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()

        parsed_mtime_before = os.path.getmtime(manifest.parsed_path)

        reloaded = ProjectManifest.load(manifest.project_dir)
        orch2 = Orchestrator(reloaded)
        orch2.run_parse()

        parsed_mtime_after = os.path.getmtime(manifest.parsed_path)
        assert parsed_mtime_before == parsed_mtime_after
