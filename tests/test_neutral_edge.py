"""Neutral/edge-case E2E tests."""
import json
import os

from screenplay_studio.manifest import ProjectManifest
from screenplay_studio.orchestrator import Orchestrator


def _make_manifest(tmp_path, sample_fountain, mock_server, name="proj"):
    project_dir = str(tmp_path / name)
    manifest = ProjectManifest.create(project_dir, sample_fountain)
    manifest.server_url = mock_server
    manifest.save()
    return manifest


class TestModelInheritanceAcrossStages:
    def test_chat_inherits_model_analyze_used(self, tmp_path, sample_fountain, mock_server):
        """The model discovered during analyze should carry into the manifest
        and be what chat resolves to as well -- this is the cross-piece
        'inherit the prior stage's model' behavior explicitly requested early on."""
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()
        orch.run_analyze()
        model_after_analyze = manifest.model_id
        assert model_after_analyze is not None

        session, engine, store = orch.start_chat()
        assert session.model_id == model_after_analyze


class TestPartialCategorySelection:
    def test_only_run_specific_categories(self, tmp_path, sample_fountain, mock_server):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()
        orch.run_analyze(categories=("coverage",))

        findings = json.load(open(manifest.report_findings_path))
        assert findings["findings"] == []  # no analysis categories ran
        assert findings["coverage"] is not None  # coverage still ran


class TestReRunningCompletedProject:
    def test_run_full_twice_is_idempotent(self, tmp_path, sample_fountain, mock_server):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_full(skip_chat=True)

        report_mtime_1 = os.path.getmtime(manifest.report_findings_path)

        # running again should no-op both stages since they're already complete
        orch.run_full(skip_chat=True)
        report_mtime_2 = os.path.getmtime(manifest.report_findings_path)
        assert report_mtime_1 == report_mtime_2


class TestChatSessionReuse:
    def test_starting_chat_twice_reuses_same_session(self, tmp_path, sample_fountain, mock_server):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()
        orch.run_analyze()
        session1, engine1, store1 = orch.start_chat()
        engine1.send_message(session1, "First message")
        store1.save(session1)

        # reload manifest fresh (simulates restarting the CLI) and start chat again
        reloaded = ProjectManifest.load(manifest.project_dir)
        orch2 = Orchestrator(reloaded)
        session2, engine2, store2 = orch2.start_chat()

        assert session2.session_id == session1.session_id
        assert len(session2.branch.messages) == 2  # the prior message is still there


class TestTitleHandling:
    def test_default_title_derived_from_filename(self, tmp_path, sample_fountain):
        manifest = ProjectManifest.create(str(tmp_path / "proj"), sample_fountain)
        assert manifest.title == "sample"  # from sample_fountain fixture filename

    def test_explicit_title_overrides_default(self, tmp_path, sample_fountain):
        manifest = ProjectManifest.create(str(tmp_path / "proj"), sample_fountain, title="My Custom Title")
        assert manifest.title == "My Custom Title"
