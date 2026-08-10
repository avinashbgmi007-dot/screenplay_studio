"""Negative E2E tests: the core promise here is failure isolation — one
stage failing shouldn't lose prior progress or corrupt the manifest."""
import json
import os

import pytest

from screenplay_studio.manifest import ProjectManifest
from screenplay_studio.orchestrator import Orchestrator, OrchestratorError


def _make_manifest(tmp_path, sample_fountain, server_url, name="proj"):
    project_dir = str(tmp_path / name)
    manifest = ProjectManifest.create(project_dir, sample_fountain)
    manifest.server_url = server_url
    manifest.save()
    return manifest


class TestAnalyzeFailureIsolation:
    def test_analyze_failure_does_not_lose_parse_progress(self, tmp_path, sample_fountain):
        """Point analyze at a dead server — parse should still be recorded
        complete, and analyze should be marked failed (not silently skipped
        or left pending), with parsed.json still on disk."""
        manifest = _make_manifest(tmp_path, sample_fountain, "http://localhost:9999")
        orch = Orchestrator(manifest)
        orch.run_parse()
        assert manifest.stage("parse").status == "complete"

        with pytest.raises(OrchestratorError):
            orch.run_analyze()

        assert manifest.stage("parse").status == "complete"  # untouched
        assert os.path.exists(manifest.parsed_path)  # file still there
        assert manifest.stage("analyze").status == "failed"
        assert manifest.stage("analyze").error is not None

    def test_can_retry_analyze_after_fixing_server(self, tmp_path, sample_fountain, mock_server):
        """Simulates the real recovery flow: analyze fails against a dead
        server, user starts their real server, reruns — should pick up
        from analyze, not redo parse."""
        manifest = _make_manifest(tmp_path, sample_fountain, "http://localhost:9999")
        orch = Orchestrator(manifest)
        orch.run_parse()
        with pytest.raises(OrchestratorError):
            orch.run_analyze()

        # "fix" the server and retry via a fresh manifest load (simulates a new run)
        reloaded = ProjectManifest.load(manifest.project_dir)
        reloaded.server_url = mock_server
        reloaded.save()
        orch2 = Orchestrator(reloaded)
        orch2.run_parse()  # no-op, already complete
        orch2.run_analyze()  # should now succeed
        assert reloaded.stage("analyze").status == "complete"


class TestOutOfOrderStages:
    def test_analyze_before_parse_raises_clear_error(self, tmp_path, sample_fountain, mock_server):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        with pytest.raises(OrchestratorError, match="parse stage hasn't completed"):
            orch.run_analyze()

    def test_chat_before_parse_raises_clear_error(self, tmp_path, sample_fountain, mock_server):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        with pytest.raises(OrchestratorError, match="parse stage hasn't completed"):
            orch.start_chat()

    def test_chat_works_even_if_analyze_never_ran(self, tmp_path, sample_fountain, mock_server):
        """Chat should work off just the parsed script if analyze was skipped
        entirely -- falls back to script-only discussion."""
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()
        session, engine, store = orch.start_chat()
        assert manifest.stage("chat").status == "complete"
        reply = engine.send_message(session, "Hello")
        assert "findings_seen=0" in reply  # no report loaded, correctly reflects that


class TestCorruptState:
    def test_load_nonexistent_project_raises_clear_error(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ProjectManifest.load(str(tmp_path / "does_not_exist"))

    def test_corrupt_manifest_json_raises_clear_error(self, tmp_path):
        project_dir = tmp_path / "corrupt_proj"
        project_dir.mkdir()
        (project_dir / "project.json").write_text("{not valid json")
        with pytest.raises(json.JSONDecodeError):
            ProjectManifest.load(str(project_dir))

    def test_missing_source_file_raises_clear_error(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ProjectManifest.create(str(tmp_path / "proj"), str(tmp_path / "does_not_exist.fdx"))

    def test_corrupt_parsed_json_causes_analyze_to_fail_cleanly(self, tmp_path, sample_fountain, mock_server):
        """If parsed.json somehow got corrupted between stages (manual edit,
        disk issue), analyze should fail with a clear error, not crash ugly."""
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()

        with open(manifest.parsed_path, "w") as f:
            f.write("{not valid json at all")

        with pytest.raises(OrchestratorError):
            orch.run_analyze()
        assert manifest.stage("analyze").status == "failed"


class TestUnsupportedSourceFormat:
    def test_unsupported_extension_fails_parse_cleanly(self, tmp_path, mock_server):
        bad_file = tmp_path / "script.docx"
        bad_file.write_text("not relevant")
        manifest = ProjectManifest.create(str(tmp_path / "proj"), str(bad_file))
        manifest.server_url = mock_server
        manifest.save()

        orch = Orchestrator(manifest)
        with pytest.raises(OrchestratorError):
            orch.run_parse()
        assert manifest.stage("parse").status == "failed"
        assert "unsupported" in manifest.stage("parse").error.lower() or "format" in manifest.stage("parse").error.lower()
