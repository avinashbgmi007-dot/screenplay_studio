"""Gap 40: an explicit model pin must not silently become another model."""
from __future__ import annotations

import json
import os

import pytest

from screenplay_studio.manifest import ProjectManifest


AVAILABLE = "available-only"
REQUESTED = "writer-selected-model"
PROVIDER = "http://127.0.0.1:8099"


def _project(tmp_path, *, model_id=REQUESTED):
    from screenplay_parser.text_parser import parse_fountain
    from screenplay_studio import revision

    root = tmp_path / "projects"
    project_dir = root / "script"
    root.mkdir(exist_ok=True)
    source = tmp_path / "input.fountain"
    source.write_text(
        "Title: Identity test\n\nINT. ROOM - DAY\n\nA synthetic scene.\n\nANA\nHello.\n",
        encoding="utf-8",
    )
    manifest = ProjectManifest.create(str(project_dir), str(source), title="Identity test")
    document = parse_fountain(str(source))
    document.save(manifest.parsed_path)
    document.save(revision.working_path(manifest))
    manifest.mark_complete("parse")
    manifest.server_url = PROVIDER
    manifest.model_id = model_id
    manifest.save()
    return root, manifest


def _only_other_model(monkeypatch):
    from screenplay_cowriter.llm_client import LlamaServerClient as CowriterClient
    from screenplay_analyzer.llm_client import LlamaServerClient as AnalyzerClient

    monkeypatch.setattr(CowriterClient, "list_models_raw",
                        lambda _self: [{"id": AVAILABLE}])
    monkeypatch.setattr(AnalyzerClient, "list_models",
                        lambda _self: [{"id": AVAILABLE}])


def test_project_chat_rejects_missing_explicit_model_before_creating_session(
    tmp_path, monkeypatch
):
    from screenplay_studio.orchestrator import Orchestrator, OrchestratorError

    _, manifest = _project(tmp_path)
    _only_other_model(monkeypatch)

    with pytest.raises(OrchestratorError, match=REQUESTED) as exc:
        Orchestrator(manifest).start_chat()

    assert AVAILABLE in str(exc.value)
    assert manifest.model_id == REQUESTED
    assert manifest.cowriter_session_id is None
    assert not os.listdir(manifest.sessions_dir), "failed model resolution left a chat session"


def test_chat_session_persists_and_api_returns_requested_actual_and_provider(
    tmp_path, monkeypatch
):
    import screenplay_studio.webapp_server as ws
    from screenplay_cowriter.llm_client import LlamaServerClient as CowriterClient
    from screenplay_studio.orchestrator import Orchestrator

    root, manifest = _project(tmp_path, model_id=AVAILABLE)
    monkeypatch.setattr(CowriterClient, "list_models_raw",
                        lambda _self: [{"id": AVAILABLE}])
    session, _, store = Orchestrator(manifest).start_chat()
    manifest.cowriter_session_id = session.session_id
    manifest.save()
    persisted = store.load(session.session_id)
    assert persisted.model_id == AVAILABLE
    assert persisted.requested_model_id == AVAILABLE
    assert persisted.model_request_recorded is True
    assert persisted.server_url == PROVIDER

    monkeypatch.setattr(ws, "PROJECTS_DIR", str(root))
    ws.app.config["TESTING"] = True
    response = ws.app.test_client().get(
        f"/api/projects/script/chat/sessions/{session.session_id}")
    assert response.status_code == 200, response.get_json()
    data = response.get_json()
    assert data["requested_model_id"] == AVAILABLE
    assert data["model_id"] == AVAILABLE
    assert data["server_url"] == PROVIDER


def test_standalone_cowriter_server_rejects_unavailable_model_without_session(
    tmp_path, monkeypatch
):
    import screenplay_cowriter.server as cowriter_server
    from screenplay_cowriter.llm_client import LlamaServerClient as CowriterClient
    from screenplay_cowriter.store import SessionStore

    sessions = tmp_path / "sessions"
    monkeypatch.setattr(cowriter_server, "store", SessionStore(str(sessions)))
    monkeypatch.setattr(CowriterClient, "list_models_raw",
                        lambda _self: [{"id": AVAILABLE}])

    response = cowriter_server.app.test_client().post("/sessions", json={
        "title": "Model identity", "server_url": PROVIDER, "model": REQUESTED,
    })

    assert response.status_code == 502
    assert REQUESTED in response.get_json()["error"]
    assert AVAILABLE in response.get_json()["error"]
    assert not list(sessions.glob("*.json"))


def test_auto_selection_records_actual_without_inventing_a_request(tmp_path, monkeypatch):
    from screenplay_cowriter.llm_client import LlamaServerClient as CowriterClient
    from screenplay_studio.orchestrator import Orchestrator

    _, manifest = _project(tmp_path, model_id=None)
    monkeypatch.setattr(CowriterClient, "list_models_raw",
                        lambda _self: [{"id": AVAILABLE}])

    session, _, _ = Orchestrator(manifest).start_chat()

    assert session.requested_model_id is None
    assert session.model_request_recorded is True
    assert session.model_id == AVAILABLE


def test_analysis_records_requested_model_actual_model_and_provider(
    tmp_path, monkeypatch
):
    import screenplay_analyzer.pipeline as pipeline
    from screenplay_analyzer.pipeline import AnalysisResult
    from screenplay_studio.orchestrator import Orchestrator

    _, manifest = _project(tmp_path)
    _only_other_model(monkeypatch)

    def resolve_without_substitution(doc, client, **_kwargs):
        assert client.fallback_to_loaded is False
        try:
            actual = client.resolve_model()
        except Exception as error:
            return AnalysisResult(
                doc=doc,
                errors=[str(error)],
                coverage={},
                model_requested=client.model,
                provider_used=client.base_url,
            )
        return AnalysisResult(
            doc=doc,
            coverage={},
            model_requested=client.model,
            model_used=actual,
            provider_used=client.base_url,
        )

    monkeypatch.setattr(pipeline, "analyze", resolve_without_substitution)
    Orchestrator(manifest).run_analyze()

    with open(manifest.report_findings_path, encoding="utf-8") as source:
        report = json.load(source)
    assert report["model_requested"] == REQUESTED
    assert report["model_used"] is None
    assert report["provider_used"] == PROVIDER
    assert manifest.model_id == REQUESTED, "the configured request was overwritten"
    markdown = open(manifest.report_md_path, encoding="utf-8").read()
    assert f"**Requested model:** `{REQUESTED}`" in markdown
    assert f"**Model provider:** `{PROVIDER}`" in markdown


def test_partial_analysis_merge_does_not_relabel_auto_selection_with_old_provenance(
    tmp_path,
):
    from screenplay_analyzer.pipeline import AnalysisResult
    from screenplay_parser.text_parser import parse_fountain

    source = tmp_path / "screenplay.fountain"
    source.write_text("Title: Merge\n\nINT. ROOM - DAY\n\nA line.\n", encoding="utf-8")
    doc = parse_fountain(str(source))
    previous_path = tmp_path / "previous.json"
    previous_path.write_text(json.dumps({
        "model_used": REQUESTED,
        "model_requested": REQUESTED,
        "provider_used": "http://old-provider",
        "model_requested_by_tier": {"primary": REQUESTED, "fast": AVAILABLE},
        "model_used_by_tier": {"primary": REQUESTED, "fast": AVAILABLE},
    }), encoding="utf-8")

    current = AnalysisResult(
        doc=doc, model_requested=None, model_used=AVAILABLE,
        provider_used=PROVIDER,
        model_requested_by_tier={"primary": None},
        model_used_by_tier={},
    )
    current.merge(str(previous_path))

    assert current.model_requested is None
    assert current.model_used == AVAILABLE
    assert current.provider_used == PROVIDER
    assert current.model_requested_by_tier == {"primary": None}
    assert current.model_used_by_tier == {}


def test_analyzer_fast_model_pin_is_strict_and_written_per_tier(tmp_path, monkeypatch):
    import screenplay_analyzer.pipeline as pipeline
    from screenplay_analyzer.llm_client_base import ModelNotFoundError
    from screenplay_analyzer.pipeline import AnalysisResult
    from screenplay_studio.orchestrator import Orchestrator

    _, manifest = _project(tmp_path, model_id=AVAILABLE)
    manifest.fast_model = REQUESTED
    manifest.save()
    _only_other_model(monkeypatch)

    def check_fast_model(doc, client, **_kwargs):
        assert client.fallback_to_loaded is False
        primary = client.resolve_model()
        with pytest.raises(ModelNotFoundError) as exc:
            client.resolve_model_id(client.fast_model)
        return AnalysisResult(
            doc=doc,
            errors=[str(exc.value)],
            coverage={},
            model_requested=client.model,
            model_used=primary,
            provider_used=client.base_url,
            model_requested_by_tier={"primary": client.model, "fast": client.fast_model},
            model_used_by_tier=dict(client.model_used_by_tier),
        )

    monkeypatch.setattr(pipeline, "analyze", check_fast_model)
    Orchestrator(manifest).run_analyze()

    with open(manifest.report_findings_path, encoding="utf-8") as source:
        report = json.load(source)
    assert report["model_requested_by_tier"] == {"primary": AVAILABLE, "fast": REQUESTED}
    assert report["model_used_by_tier"] == {"primary": AVAILABLE}
    assert "Fast-tier model" in open(manifest.report_md_path, encoding="utf-8").read()


def test_analyzer_client_records_actual_model_for_each_tier(monkeypatch):
    from unittest.mock import Mock
    from screenplay_analyzer.llm_client import LlamaServerClient

    client = LlamaServerClient(
        PROVIDER, model=AVAILABLE, fast_model=REQUESTED, fallback_to_loaded=False)
    monkeypatch.setattr(client, "list_models", lambda: [{"id": AVAILABLE}, {"id": REQUESTED}])

    def answer(*_args, json=None, **_kwargs):
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": "{}"}}],
        }
        response.raise_for_status.return_value = None
        assert json["model"] in (AVAILABLE, REQUESTED)
        return response

    monkeypatch.setattr("screenplay_analyzer.llm_client_base.request_no_redirects", answer)
    client.chat_json("system", "fast pass", fast=True)
    client.chat_json("system", "primary pass", fast=False)

    assert client.model_used_by_tier == {"fast": REQUESTED, "primary": AVAILABLE}


def test_pipeline_records_requested_primary_fast_and_provider_on_resolution_failure(
    tmp_path
):
    from screenplay_analyzer.llm_client_base import ModelNotFoundError
    from screenplay_analyzer.pipeline import analyze
    from screenplay_parser.text_parser import parse_fountain

    source = tmp_path / "script.fountain"
    source.write_text(
        "Title: Identity test\n\nINT. ROOM - DAY\n\nA synthetic scene.\n",
        encoding="utf-8",
    )
    doc = parse_fountain(str(source))

    class StrictClient:
        model = REQUESTED
        fast_model = "writer-selected-fast-model"
        base_url = PROVIDER

        @staticmethod
        def resolve_model():
            raise ModelNotFoundError(
                f"Requested model '{REQUESTED}' is not loaded. Available: ['{AVAILABLE}']")

    result = analyze(doc, StrictClient(), run_categories=())

    assert result.model_requested == REQUESTED
    assert result.model_used is None
    assert result.provider_used == PROVIDER
    assert result.model_requested_by_tier == {
        "primary": REQUESTED, "fast": "writer-selected-fast-model"}
    assert result.model_used_by_tier == {}
    assert AVAILABLE in result.errors[0]


def test_idea_chat_returns_actionable_model_error_without_creating_session(
    tmp_path, monkeypatch
):
    import screenplay_studio.webapp_server as ws
    from screenplay_studio.ideas import IdeaStore

    projects = tmp_path / "projects"
    idea = IdeaStore(str(projects / "ideas")).create("Test idea")
    _only_other_model(monkeypatch)
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(projects))
    monkeypatch.setitem(ws.CONFIG, "server_url", PROVIDER)
    monkeypatch.setitem(ws.CONFIG, "model", REQUESTED)
    monkeypatch.setitem(ws.CONFIG, "timeout", 5)
    monkeypatch.setitem(ws.CONFIG, "api_key", None)
    ws.app.config["TESTING"] = True

    response = ws.app.test_client().post(f"/api/ideas/{idea['id']}/chat/start")

    assert response.status_code == 502
    assert REQUESTED in response.get_json()["error"]
    assert AVAILABLE in response.get_json()["error"]
    assert not os.path.exists(str(projects / "ideas" / idea["id"] / "sessions"))


def test_chat_model_badge_and_report_render_show_model_provenance():
    from pathlib import Path

    html = Path("screenplay_studio/webapp/index.html").read_text(encoding="utf-8")
    app_js = Path("screenplay_studio/webapp/app.js").read_text(encoding="utf-8")
    assert 'id="chat-model-provenance"' in html
    assert "requested_model_id" in app_js
    assert "model_request_recorded" in app_js
    assert "Provider: " in app_js
