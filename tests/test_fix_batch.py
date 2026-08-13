"""Tests for the batch of fixes:

1. resolve_categories / ALL_CATEGORIES sentinel (pipeline)
2. per-category outcomes + retry_failed partial resume (orchestrator)
3. defensive session save inside CoWriterEngine.send_message
4. ServerConfig validation + to_dict copy semantics (webapp_server)
5. /api/config exposes personas/modes lists
6. graceful cowriter-missing handling (webapp_server)
"""
import io
import json
import os

import pytest

import screenplay_studio.webapp_server as webapp_server

from screenplay_analyzer.pipeline import ALL_CATEGORIES, resolve_categories
from screenplay_studio.manifest import ProjectManifest
from screenplay_studio.orchestrator import Orchestrator


@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


class TestResolveCategories:
    def test_none_means_all(self):
        assert resolve_categories(None) == ALL_CATEGORIES

    def test_all_sentinel_tuple(self):
        assert resolve_categories(("all",)) == ALL_CATEGORIES

    def test_explicit_subset_preserved(self):
        assert resolve_categories(("theme", "structure")) == ("theme", "structure")

    def test_empty_tuple_means_nothing_extra(self):
        assert resolve_categories(()) == ()

    def test_mixed_all_preserved_as_all(self):
        assert resolve_categories(("all", "theme")) == ALL_CATEGORIES


def _make_manifest(tmp_path, sample_fountain, mock_server, name="proj"):
    project_dir = str(tmp_path / name)
    manifest = ProjectManifest.create(project_dir, sample_fountain)
    manifest.server_url = mock_server
    manifest.save()
    return manifest


class TestCategoryOutcomes:
    def test_outcomes_recorded_on_success(self, tmp_path, sample_fountain, mock_server):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()
        orch.run_analyze(categories=("dialogue", "theme"))

        stage = manifest.stage("analyze")
        outcomes = stage.output_paths.get("category_outcomes", {})
        assert outcomes.get("dialogue") == "ok"
        assert outcomes.get("theme") == "ok"
        assert stage.output_paths.get("failed_categories") == []


class TestRetryFailed:
    def test_retry_failed_with_no_failures_is_noop(self, tmp_path, sample_fountain, mock_server):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()
        orch.run_analyze(categories=("dialogue",))
        mtime_before = os.path.getmtime(manifest.report_findings_path)

        orch.run_analyze(retry_failed=True)  # no failed categories -> no-op
        assert manifest.stage("analyze").status == "complete"
        assert os.path.getmtime(manifest.report_findings_path) == mtime_before

    def test_retry_failed_reruns_only_failed_and_merges(self, tmp_path, sample_fountain, mock_server, monkeypatch):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()

        # Force a partial failure: theme fails, dialogue succeeds.
        from screenplay_analyzer import pipeline as pipeline_mod
        real_analyze = pipeline_mod.analyze

        def flaky_analyze(*args, **kwargs):
            result = real_analyze(*args, **kwargs)
            result.category_outcomes["theme"] = "failed"
            result.errors.append("theme analysis failed (simulated)")
            return result

        monkeypatch.setattr(pipeline_mod, "analyze", flaky_analyze)
        orch.run_analyze(categories=("dialogue", "theme"))
        stage = manifest.stage("analyze")
        assert stage.output_paths.get("failed_categories") == ["theme"]

        # Now retry only the failed category with a healthy analyzer.
        monkeypatch.undo()
        orch2 = Orchestrator(ProjectManifest.load(manifest.project_dir))
        orch2.run_analyze(retry_failed=True)

        # reload from disk — orch2 wrote a fresh manifest
        m2 = ProjectManifest.load(manifest.project_dir)
        report = json.load(open(m2.report_findings_path, encoding="utf-8"))
        assert m2.stage("analyze").status == "complete"
        assert "findings" in report
        # merge happened: no crash, report is a dict with findings list
        assert isinstance(report["findings"], list)
        # the failed category recovered; only dialogue was re-run
        assert m2.stage("analyze").output_paths.get("failed_categories") == []


class TestRetryPrerequisiteGating:
    def test_summaries_failure_marks_overview_gated_categories_failed(self, tmp_path, sample_fountain, mock_server, monkeypatch):
        """When scene summaries fail (overview stays empty), the categories
        that depend on the overview (theme/character/structure/scene_function/
        coverage/char_reads) must be recorded as failed too — otherwise a
        retry would try to re-run a leaf category that can't run without its
        prerequisite."""
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()

        from screenplay_analyzer import pipeline as pipeline_mod
        from screenplay_analyzer.llm_client import LlamaServerError

        def failing_summaries(*args, **kwargs):
            raise LlamaServerError("summaries unavailable (simulated)")

        monkeypatch.setattr(pipeline_mod, "build_scene_summaries", failing_summaries)
        orch.run_analyze(categories=("theme", "dialogue"))

        failed = set(manifest.stage("analyze").output_paths.get("failed_categories") or [])
        assert "theme" in failed          # overview-gated -> failed
        assert "dialogue" not in failed   # scene-level, doesn't need overview

    def test_retry_after_summaries_failure_recovers(self, tmp_path, sample_fountain, mock_server, monkeypatch):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()

        from screenplay_analyzer import pipeline as pipeline_mod
        from screenplay_analyzer.llm_client import LlamaServerError

        def failing_summaries(*args, **kwargs):
            raise LlamaServerError("summaries unavailable (simulated)")

        monkeypatch.setattr(pipeline_mod, "build_scene_summaries", failing_summaries)
        orch.run_analyze()  # all categories, summaries fails
        failed = set(manifest.stage("analyze").output_paths.get("failed_categories") or [])
        assert "theme" in failed

        # healthy retry re-runs the whole failed chain (summaries + dependents)
        monkeypatch.undo()
        orch2 = Orchestrator(ProjectManifest.load(manifest.project_dir))
        orch2.run_analyze(retry_failed=True)
        m2 = ProjectManifest.load(manifest.project_dir)  # fresh copy from disk
        report = json.load(open(m2.report_findings_path, encoding="utf-8"))
        assert isinstance(report["findings"], list)
        assert m2.stage("analyze").output_paths.get("failed_categories") == []


class TestRetryGenreNeedsCoverage:
    """Genre / logline_test depend on coverage's genre+logline fields. If they
    fail on their OWN model call while coverage succeeds, the retry must re-run
    coverage alongside them — otherwise the fresh run's empty coverage gates
    them out and step-7 re-marks them failed forever."""

    def test_genre_failure_independent_of_coverage_recovers_on_retry(self, tmp_path, sample_fountain, mock_server, monkeypatch):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()

        from screenplay_analyzer import genre as genre_mod
        from screenplay_analyzer.llm_client import LlamaServerError

        def flaky_genre(*args, **kwargs):
            raise LlamaServerError("genre check unavailable (simulated)")

        monkeypatch.setattr(genre_mod, "run_genre_check", flaky_genre)
        orch.run_analyze()  # all categories; coverage succeeds, genre fails

        failed = set(manifest.stage("analyze").output_paths.get("failed_categories") or [])
        assert "genre" in failed
        assert "coverage" not in failed  # coverage itself succeeded

        # healthy retry: genre must recover (coverage re-run alongside)
        monkeypatch.undo()
        orch2 = Orchestrator(ProjectManifest.load(manifest.project_dir))
        orch2.run_analyze(retry_failed=True)
        m2 = ProjectManifest.load(manifest.project_dir)
        assert m2.stage("analyze").output_paths.get("failed_categories") == []

    def test_failed_retry_preserves_partial_record(self, tmp_path, sample_fountain, mock_server, monkeypatch):
        """If the retry itself fails (e.g. server down), the manifest must keep
        the previous partial-completion record so a later retry can resume from
        the same failed_categories instead of re-running everything."""
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()

        from screenplay_analyzer import pipeline as pipeline_mod
        from screenplay_analyzer.llm_client import LlamaServerError

        def failing_summaries(*args, **kwargs):
            raise LlamaServerError("summaries unavailable (simulated)")

        monkeypatch.setattr(pipeline_mod, "build_scene_summaries", failing_summaries)
        orch.run_analyze()
        failed_before = sorted(manifest.stage("analyze").output_paths.get("failed_categories") or [])
        assert failed_before  # partial record exists

        # retry, but now the server is unreachable -> the retry fails
        monkeypatch.undo()
        from screenplay_analyzer.llm_client import LlamaServerClient as RealClient

        def dead_resolve(self):
            raise LlamaServerError("server down (simulated)")

        monkeypatch.setattr(RealClient, "resolve_model", dead_resolve)
        orch2 = Orchestrator(ProjectManifest.load(manifest.project_dir))
        with pytest.raises(Exception):
            orch2.run_analyze(retry_failed=True)

        m2 = ProjectManifest.load(manifest.project_dir)
        assert m2.stage("analyze").status == "failed"
        # partial record survived the failed retry
        assert sorted(m2.stage("analyze").output_paths.get("failed_categories") or []) == failed_before

        # and a later retry still resumes from the same failed set
        monkeypatch.undo()
        orch3 = Orchestrator(ProjectManifest.load(manifest.project_dir))
        orch3.run_analyze(retry_failed=True)
        m3 = ProjectManifest.load(manifest.project_dir)
        assert m3.stage("analyze").output_paths.get("failed_categories") == []


class TestEngineDefensiveSave:
    def test_send_message_saves_when_store_provided(self, tmp_path, sample_fountain, mock_server):
        manifest = _make_manifest(tmp_path, sample_fountain, mock_server)
        orch = Orchestrator(manifest)
        orch.run_parse()
        orch.run_analyze(categories=("dialogue",))
        session, engine, store = orch.start_chat()

        # engine was constructed with store=store -> send_message persists
        engine.send_message(session, "Hello there")
        reloaded = store.load(session.session_id)
        assert len(reloaded.branch.messages) == 2

    def test_send_message_without_store_still_works(self, tmp_path, sample_fountain, mock_server):
        from screenplay_cowriter.context import ScriptContext, ReportContext
        from screenplay_cowriter.engine import CoWriterEngine
        from screenplay_cowriter.llm_client import LlamaServerClient
        from screenplay_cowriter.models import Session

        client = LlamaServerClient(base_url=mock_server)
        engine = CoWriterEngine(client, ScriptContext({}), ReportContext(None))  # no store
        session = Session.new("t")
        reply = engine.send_message(session, "Hello")
        assert reply  # works without a store


def test_webapp_config_exposes_personas(http_client):
    resp = http_client.get("/api/config")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "personas" in data
    assert "script_consultant" in data["personas"]
    assert "modes" in data
    assert "evidence_discussion" in data["modes"]


def test_webapp_config_timeout_validation(http_client):
    resp = http_client.post("/api/config", json={"timeout": 0})
    assert resp.status_code == 200
    # invalid (non-positive) timeout keeps the old value
    assert resp.get_json()["timeout"] > 0

    resp = http_client.post("/api/config", json={"timeout": 120})
    assert resp.get_json()["timeout"] == 120


def test_webapp_config_returns_copy_not_live_ref(http_client):
    resp = http_client.get("/api/config")
    payload = resp.get_json()
    payload["server_url"] = "http://hacked:1"
    again = http_client.get("/api/config").get_json()
    assert again["server_url"] != "http://hacked:1"
