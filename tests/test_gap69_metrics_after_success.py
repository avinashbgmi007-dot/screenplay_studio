"""Gap 69: ancillary metrics must not undo a completed analysis response."""

import io
import os
from pathlib import Path

import pytest

import screenplay_studio.metrics as metrics
import screenplay_studio.webapp_server as webapp_server
from screenplay_studio.jsonio import StoreLockTimeout
from screenplay_studio.manifest import ProjectManifest


SCRIPT = b"""Title: Completed analysis
Author: Test

INT. ROOM - DAY

MARA enters and sets down a letter.

CUT TO:

EXT. STREET - NIGHT

MARA looks up at the sky.
"""
REPORT = "# Completed analysis\n\nThe report was written successfully.\n"


@pytest.fixture
def client(tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    projects.mkdir()
    monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(projects))
    monkeypatch.setitem(webapp_server.CONFIG, "server_url", "http://127.0.0.1:1")
    monkeypatch.setitem(webapp_server.CONFIG, "model", None)
    monkeypatch.setitem(webapp_server.CONFIG, "fast_model", None)
    monkeypatch.setitem(webapp_server.app.config, "TESTING", True)
    return webapp_server.app.test_client()


def _upload(client):
    response = client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SCRIPT), "gap69.fountain"), "title": "Gap69"},
        content_type="multipart/form-data",
    )
    assert response.status_code in (200, 201), response.get_data(as_text=True)
    project = response.get_json()["project"]
    return project, ProjectManifest.load(webapp_server._project_dir(project))


def _successful_analysis_stub(manifest_calls):
    def run(self, **_kwargs):
        manifest = self.manifest
        manifest_calls.append(manifest)
        stage = manifest.stage("analyze")
        stage.status = "complete"
        stage.output_paths = {"failed_categories": []}
        Path(manifest.report_md_path).write_text(REPORT, encoding="utf-8")
        Path(manifest.report_findings_path).write_text("[]", encoding="utf-8")
        manifest.save()

    return run


def test_metrics_timeout_after_success_returns_completed_report_not_busy(
    client, monkeypatch
):
    project, manifest = _upload(client)
    calls = []
    monkeypatch.setattr(
        webapp_server.Orchestrator, "run_analyze", _successful_analysis_stub(calls)
    )

    def busy_metrics(_manifest, _elapsed):
        raise StoreLockTimeout(os.path.join(manifest.project_dir, "metrics.json"), 0.05)

    monkeypatch.setattr(metrics, "record_analysis", busy_metrics)
    response = client.post(f"/api/projects/{project}/analyze")
    body = response.get_json()

    assert response.status_code == 200, body
    assert body["stages"]["analyze"] == "complete"
    assert body["analysis_metrics_recorded"] is False
    assert "analysis_metrics_warning" in body
    assert "no rerun is needed" in body["analysis_metrics_warning"].lower()
    assert not body.get("busy")
    assert len(calls) == 1
    persisted = ProjectManifest.load(manifest.project_dir)
    assert persisted.stage("analyze").status == "complete"
    assert Path(manifest.report_md_path).read_text(encoding="utf-8") == REPORT


def test_successful_metrics_write_is_reported_as_recorded(client, monkeypatch):
    project, manifest = _upload(client)
    calls = []
    monkeypatch.setattr(
        webapp_server.Orchestrator, "run_analyze", _successful_analysis_stub(calls)
    )
    metrics_calls = []
    monkeypatch.setattr(
        metrics, "record_analysis", lambda _manifest, elapsed: metrics_calls.append(elapsed)
    )

    response = client.post(f"/api/projects/{project}/analyze")
    body = response.get_json()

    assert response.status_code == 200, body
    assert body["analysis_metrics_recorded"] is True
    assert "analysis_metrics_warning" not in body
    assert len(metrics_calls) == 1
    assert len(calls) == 1


def test_busy_before_orchestration_still_returns_busy_and_does_not_start(
    client, monkeypatch
):
    project, _manifest = _upload(client)
    run_calls = []
    monkeypatch.setattr(
        webapp_server.Orchestrator,
        "run_analyze",
        lambda *_args, **_kwargs: run_calls.append("started"),
    )

    def fail_preflight(_manifest):
        raise StoreLockTimeout(os.path.join(_manifest.project_dir, "manifest.json"), 0.05)

    monkeypatch.setattr(webapp_server, "_adopt_connection", fail_preflight)
    response = client.post(f"/api/projects/{project}/analyze")
    body = response.get_json()

    assert response.status_code == 503, body
    assert body["busy"] is True
    assert not run_calls, "busy was reported only after orchestration had started"
    assert "metrics_recorded" not in body


def test_retry_metrics_timeout_also_preserves_the_completed_retry(client, monkeypatch):
    project, manifest = _upload(client)
    stage = manifest.stage("analyze")
    stage.status = "complete"
    stage.output_paths = {"failed_categories": ["dialogue"]}
    manifest.save()
    calls = []
    monkeypatch.setattr(
        webapp_server.Orchestrator, "run_analyze", _successful_analysis_stub(calls)
    )
    monkeypatch.setattr(
        metrics,
        "record_analysis",
        lambda *_args: (_ for _ in ()).throw(
            StoreLockTimeout(os.path.join(manifest.project_dir, "metrics.json"), 0.05)
        ),
    )

    response = client.post(f"/api/projects/{project}/analyze/retry-failed")
    body = response.get_json()

    assert response.status_code == 200, body
    assert body["stages"]["analyze"] == "complete"
    assert body["analysis_metrics_recorded"] is False
    assert "no rerun is needed" in body["analysis_metrics_warning"].lower()
    assert len(calls) == 1
    assert Path(manifest.report_md_path).read_text(encoding="utf-8") == REPORT
