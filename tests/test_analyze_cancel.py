"""R2 (RE-B4 audit): the writer can stop a running analysis.

Three layers, each pinned:

- ROUTE: POST /api/projects/<name>/analyze/cancel — 404 unknown project,
  409 when nothing is running (double-click safety), and it SETS the
  per-project event the run is watching when one is live.
- PIPELINE: the co-operative hook — `analyze(should_cancel=...)` raises
  AnalysisCancelled at the first stage boundary, and the scene-summary loop
  (the longest stage on a real script) checks between chunks. The current
  category always finishes; a cancel never lands mid-write.
- ORCHESTRATOR: a cancelled run is not a failed run — the stage returns to
  its pre-run state (a first run back to pending, a retry-merge back to the
  stage it was merging into) and the heartbeat says "cancelled" so the desk
  poller resets instead of reporting a stall.
"""
import io
import json
import os
import threading

import pytest

from screenplay_analyzer.llm_client import LlamaServerClient  # noqa: F401  (import cost: none)
from screenplay_analyzer.pipeline import AnalysisCancelled, analyze, build_scene_summaries
from screenplay_parser.text_parser import parse_fountain


@pytest.fixture
def http_client(tmp_path, mock_server):
    """Same shape as test_webapp_api.py's fixture (fixtures are not shared
    across modules): isolated PROJECTS_DIR, config pointed at the mock
    unified server, Flask test client."""
    from screenplay_studio import webapp_server

    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _mk_project(client, name):
    r = client.post("/api/projects", content_type="multipart/form-data", data={
        "file": (io.BytesIO(b"Title: t\n\nINT. ROOM - DAY\n\nAction.\n\nANA\nLine.\n"),
                 f"{name}.fountain"),
        "title": name,
    })
    assert r.status_code == 201, r.get_data(as_text=True)[:200]
    return name


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

def test_cancel_unknown_project_is_404(http_client):
    r = http_client.post("/api/projects/nope_zz/analyze/cancel")
    assert r.status_code == 404
    assert "not found" in r.get_json()["error"].lower()


def test_cancel_with_nothing_running_is_409(http_client):
    name = _mk_project(http_client, "cancel_idle")
    r = http_client.post(f"/api/projects/{name}/analyze/cancel")
    assert r.status_code == 409
    assert "no analysis is running" in r.get_json()["error"].lower()


def test_cancel_sets_the_event_of_a_live_run(http_client):
    from screenplay_studio import webapp_server

    name = _mk_project(http_client, "cancel_live")
    ev = threading.Event()
    webapp_server._ANALYZE_CANCEL[name] = ev
    lock = webapp_server._analyze_lock(name)
    assert lock.acquire(blocking=False), "test holds the lock to simulate a live run"
    try:
        r = http_client.post(f"/api/projects/{name}/analyze/cancel")
        assert r.status_code == 200
        assert r.get_json()["cancel_requested"] is True
        assert ev.is_set(), "the run's cancel event must be set"
    finally:
        lock.release()
        webapp_server._ANALYZE_CANCEL.pop(name, None)


# ---------------------------------------------------------------------------
# Pipeline hook
# ---------------------------------------------------------------------------

def _tiny_doc(tmp_path):
    src = tmp_path / "t.fountain"
    src.write_text("Title: t\n\nINT. ROOM - DAY\n\nAction.\n\nANA\nLine one.\n",
                   encoding="utf-8")
    return parse_fountain(str(src))


def test_analyze_raises_cancelled_at_first_boundary(tmp_path):
    doc = _tiny_doc(tmp_path)
    with pytest.raises(AnalysisCancelled):
        analyze(doc, client=None, should_cancel=lambda: True)


def test_analyze_runs_clean_when_cancel_never_fires(tmp_path, mock_server):
    """should_cancel=None (the default for every existing caller) must behave
    exactly as before — the hook is invisible unless a cancel is requested."""
    from tests.mock_unified_server import app as mock_app  # noqa: F401
    doc = _tiny_doc(tmp_path)
    from screenplay_analyzer.llm_client import LlamaServerClient
    client = LlamaServerClient(base_url=mock_server, timeout=30)
    result = analyze(doc, client=client, run_categories=())
    assert result is not None and result.doc is doc


def test_scene_summary_loop_checks_between_chunks(tmp_path):
    """The loop checks per chunk: a cancel that fires from the first boundary
    stops the run before ANY model call — the finest honest granularity (the
    chunk in flight always finishes, the next one never starts)."""
    doc = _tiny_doc(tmp_path)

    class NeverClient:
        def chat_json(self, *a, **k):
            raise AssertionError("cancel must fire before the chunk's model call")

    with pytest.raises(AnalysisCancelled):
        build_scene_summaries(doc, NeverClient(), chunk_size=1,
                              should_cancel=lambda: True)


# ---------------------------------------------------------------------------
# Orchestrator restore
# ---------------------------------------------------------------------------

def _seeded_project(tmp_path):
    from screenplay_studio import revision
    from screenplay_studio.manifest import ProjectManifest

    pdir = os.path.join(str(tmp_path), "cancel_restore")
    os.makedirs(pdir, exist_ok=True)
    src = os.path.join(str(tmp_path), "cancel_restore.fountain")
    with open(src, "w", encoding="utf-8", newline="") as f:
        f.write("Title: CR\n\nINT. ROOM - DAY\n\nAction.\n\nANA\nLine one.\n")
    doc = parse_fountain(src)
    m = ProjectManifest.create(pdir, source_file=src, title="CR")
    doc.save(m.parsed_path)
    doc.save(revision.working_path(m))
    m.mark_complete("parse")
    return m


def test_cancelled_run_restores_pending_stage_and_writes_heartbeat(tmp_path):
    from screenplay_studio.orchestrator import Orchestrator

    m = _seeded_project(tmp_path)
    assert m.stage("analyze").status == "pending"
    orch = Orchestrator(m)
    with pytest.raises(AnalysisCancelled):
        orch.run_analyze(should_cancel=lambda: True)
    assert m.stage("analyze").status == "pending", "a first run returns to pending"
    hb = json.load(open(m.progress_path, encoding="utf-8"))
    assert hb["status"] == "cancelled"
    assert "unchanged" in hb["detail"]


def test_cancelled_run_restores_completed_stage_after_rerun(tmp_path):
    """A cancel during a RE-run must not destroy the previous complete stage
    (its report paths and partial record survive — the writer keeps the last
    good analysis)."""
    from screenplay_studio.orchestrator import Orchestrator
    from screenplay_studio.manifest import StageStatus

    m = _seeded_project(tmp_path)
    m.mark_complete("analyze", {"report_md": "r.md", "report_findings": "r.json",
                                "failed_categories": []})
    before = dict(m.stage("analyze").output_paths or {})
    orch = Orchestrator(m)
    # Mirror the webapp's `force` path exactly: snapshot the complete stage
    # BEFORE the reset (that snapshot is what a cancel must restore), then
    # reset to pending so the orchestrator actually re-runs. Calling
    # run_analyze without the reset would hit its by-design short-circuit
    # (resume never redoes finished work) and no cancel could ever fire.
    prev_stage = {"status": m.stage("analyze").status,
                  "output_paths": dict(m.stage("analyze").output_paths)}
    from screenplay_studio.manifest import StageStatus as _SS
    m.stages["analyze"] = _SS()
    with pytest.raises(AnalysisCancelled):
        orch.run_analyze(should_cancel=lambda: True, prev_stage=prev_stage)
    assert m.stage("analyze").status == "complete"
    assert dict(m.stage("analyze").output_paths or {}) == before
    hb = json.load(open(m.progress_path, encoding="utf-8"))
    assert hb["status"] == "cancelled"
