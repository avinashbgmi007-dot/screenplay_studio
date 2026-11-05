"""Gap 5 — one run-scoped cancellation lifecycle across analysis and retry.

The writer's Stop button makes one promise: *a stopped run publishes nothing.*
The register recorded three separate places where that promise was broken or
half-kept, and each one is pinned here:

1. **PUBLICATION** (`test_stop_*closing*`, `test_stop_between_*`). The pipeline
   checked `should_cancel()` at stage boundaries, and the last check stood
   before step 6b — 169 lines before `return result`. Everything after it
   (steps 7-8i: the observation pass, the evidence floor, the four
   demote-never-drop guards, the verification summary, the evidence depth) ran
   with no check at all, and the return is what lets the caller stage and
   publish a new generation. A stop landing in that window was silently
   discarded: the run answered `200` with no `cancelled` flag, the stage went to
   `complete`, and `report.md` was rewritten over the writer's last good
   analysis. Measured on the real route before the fix.
2. **THE ANSWER** (`test_analyze_route_*`, `test_retry_route_*`). `/analyze`
   and `/analyze/retry-failed` answer `{cancelled: true}` for a stopped run;
   the frontend ignored the body and announced "Analysis complete" / "the
   report has been merged and updated" either way. The wording now comes from
   one helper (`core.js:cancellationNote`) and is tested in
   `tests/js/core.test.js`; the routes' contract is pinned here.
3. **THE RETRY** (gap 66, already shipped — kept here so one file owns the
   whole lifecycle). A retry is an analysis: it registers a cancel event, the
   route answers 200, and a stop is honoured.

Every test drives real objects: the real Flask routes against a real in-process
model server, the real pipeline, the real orchestrator, real files on disk. No
test stubs the client or asserts on a mock's call count.
"""
import io
import json
import os
import threading

import pytest

from screenplay_analyzer.llm_client import LlamaServerClient
from screenplay_analyzer.pipeline import AnalysisCancelled, analyze
from screenplay_parser.text_parser import parse_fountain


SOURCE = ("Title: WINDOW\n\nINT. ROOM - DAY\n\nAction here, someone moves.\n\n"
          "ANA\nLine one of dialogue.\n\nEXT. STREET - NIGHT\n\nMore action, rain.\n\n"
          "BO\nLine two.\n")

# Every category, so the run reaches the closing passes that used to be
# unchecked (7 -> 8i are where the old code stopped looking).
ALL_CATS = ("theme", "character", "structure", "scene_function", "setup_payoff",
            "char_reads", "coverage", "genre", "logline_test")


@pytest.fixture
def doc(tmp_path):
    src = tmp_path / "window.fountain"
    src.write_text(SOURCE, encoding="utf-8")
    return parse_fountain(str(src))


@pytest.fixture
def client(mock_server):
    return LlamaServerClient(base_url=mock_server, timeout=60)


# ---------------------------------------------------------------------------
# 1. Publication — the property is "nothing is published past a stop"
# ---------------------------------------------------------------------------

def test_stop_before_the_closing_passes_raises(doc, client):
    """The baseline the rest of this section depends on: the hook works, and a
    cancel raised at a stage boundary arrives as AnalysisCancelled, not as a
    result the caller could go on to publish."""
    with pytest.raises(AnalysisCancelled):
        analyze(doc, client=client, run_categories=ALL_CATS,
                should_cancel=lambda: True)


def test_stop_during_the_closing_passes_publishes_nothing(doc, client, monkeypatch):
    """The stop lands INSIDE the closing window — after the last stage check,
    before `return result`.

    The window is entered for real (the evidence floor is one of the closing
    passes; it is slowed, never stubbed) and the stop is requested from inside
    it, exactly as a click would be: the flag flips while the pass is running.
    Before the fix the run returned a full `AnalysisResult` and the caller
    published it; now it must raise.
    """
    import screenplay_analyzer.pipeline as pipe

    real_floor = pipe.apply_evidence_floor
    stop = threading.Event()
    entered = threading.Event()

    def floor_then_stop(findings):
        entered.set()
        stop.set()          # the writer clicks Stop while this pass is running
        return real_floor(findings)

    monkeypatch.setattr(pipe, "apply_evidence_floor", floor_then_stop)

    with pytest.raises(AnalysisCancelled):
        analyze(doc, client=client, run_categories=ALL_CATS, should_cancel=stop.is_set)

    assert entered.is_set(), "the test must actually reach the closing window"


def test_stop_after_the_last_pass_before_the_return_publishes_nothing(doc, client, monkeypatch):
    """The narrowest version of the same window: everything has run, every
    finding is final, and the ONLY thing left is the `return`.

    This is the one the register recorded as "zero cancel checks in the closing
    passes". A stop here still must not publish — the report on disk must stay
    the one the writer already had. `evidence_depth` is the last thing computed
    before the return, so the flag is flipped as it completes.
    """
    import screenplay_analyzer.pipeline as pipe

    stop = threading.Event()
    real_depth = pipe.evidence_depth

    def depth_then_stop(findings):
        out = real_depth(findings)
        stop.set()          # ... and now the run would have returned
        return out

    monkeypatch.setattr(pipe, "evidence_depth", depth_then_stop)

    with pytest.raises(AnalysisCancelled):
        analyze(doc, client=client, run_categories=ALL_CATS, should_cancel=stop.is_set)


def test_a_stop_before_the_observation_pass_costs_no_model_calls(doc, client, monkeypatch):
    """The closing window has a model call at its head — the observation pass.

    The register recorded that the last pipeline check stood before step 6b, so
    a stop during steps 7-8d was still followed by the observation pass: one
    model call per ungrounded finding (capped, but billable and slow). The check
    in front of that pass exists to make the stop land *before* the pass runs,
    never after it.

    Ordering is measured, not assumed: the pass is PROXIED (its real body still
    runs when it is reached) so the test can see whether the writer had already
    asked to stop at the moment the pass was entered. A stub would prove
    nothing here — the property is that the pass is never entered at all.
    """
    from screenplay_analyzer import observation_pass as op_mod

    # The suite switches the pass OFF globally (conftest.py) because it costs a
    # model call per ungrounded finding; production runs it by default. This is
    # the one test that needs it live, so it turns the product switch back on
    # for its own run — it does not stub the pass.
    monkeypatch.setenv("SCREENPLAY_STUDIO_OBSERVATION_PASS", "1")

    stop = threading.Event()
    entered = []
    real_run = op_mod.ObservationPass.run

    def run_when_entered(self, *a, **k):
        entered.append(stop.is_set())
        return real_run(self, *a, **k)

    monkeypatch.setattr(op_mod.ObservationPass, "run", run_when_entered)

    def cb(event):
        # `genre` is the LAST category pass on this fixture (measured: the emit
        # order ends ... coverage, logline_test, genre, then observation).
        # Anchoring one pass earlier would let an OLD check catch the stop and
        # the test would pass whether or not the new one exists — the mistake
        # this docstring's neighbour was written to avoid.
        if event["stage"] == "genre" and event["status"] == "complete":
            stop.set()

    with pytest.raises(AnalysisCancelled):
        analyze(doc, client=client, run_categories=ALL_CATS,
                progress_cb=cb, should_cancel=stop.is_set)

    assert stop.is_set(), "the run must reach the stage this test stops after"
    assert entered == [], (
        f"the observation pass was entered with the stop already requested "
        f"(entered={entered}) — a cancelled run paid for a model-backed pass")


@pytest.mark.parametrize("stop_at", ["after_coverage", "after_genre", "after_logline"])
def test_stop_between_each_pair_of_model_passes_is_honoured(doc, client, stop_at):
    """A stop must be honoured whichever model call it follows — including the
    two (genre, logline_test) whose results used to be added with no check in
    front of the next stage. Anchored on the progress events the desk reads."""
    seen = []
    stop = threading.Event()

    def cb(event):
        seen.append((event["stage"], event["status"]))
        if stop_at == "after_coverage" and event["stage"] == "coverage" and event["status"] == "complete":
            stop.set()
        if stop_at == "after_genre" and event["stage"] == "genre" and event["status"] == "complete":
            stop.set()
        if stop_at == "after_logline" and event["stage"] == "logline_test" and event["status"] == "complete":
            stop.set()

    with pytest.raises(AnalysisCancelled):
        analyze(doc, client=client, run_categories=ALL_CATS,
                progress_cb=cb, should_cancel=stop.is_set)

    assert seen, "the run must get far enough to report the stage being stopped at"


def test_no_stop_still_returns_a_complete_result(doc, client):
    """The guard must be invisible to a run nobody stopped — the last thing a
    cancellation fix may do is refuse a normal completion. Pins that the
    closing passes really do run (evidence depth is computed and counted)."""
    result = analyze(doc, client=client, run_categories=ALL_CATS)
    assert result is not None and result.doc is doc
    assert result.stats.get("evidence_depth") is not None
    assert result.stats["evidence_depth"]["total"] == len(result.findings)


# ---------------------------------------------------------------------------
# 2. The routes' contract — the frontend's "was this a stop?" signal
# ---------------------------------------------------------------------------

@pytest.fixture
def http_client(tmp_path, mock_server):
    from screenplay_studio import webapp_server

    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.CONFIG["timeout"] = 60
    webapp_server.app.config["TESTING"] = True
    yield webapp_server.app.test_client()
    # Never leak a cancel event between tests: a stale one is set, and every
    # subsequent run in this process would cancel on arrival.
    webapp_server._ANALYZE_CANCEL.clear()


def _mk_project(client, name):
    r = client.post("/api/projects", content_type="multipart/form-data", data={
        "file": (io.BytesIO(SOURCE.encode()), f"{name}.fountain"),
        "title": name,
    })
    assert r.status_code == 201, r.get_data(as_text=True)[:300]
    return name


def _project_dir(name):
    from screenplay_studio import webapp_server
    return os.path.join(webapp_server.PROJECTS_DIR, name)


def test_analyze_route_answers_cancelled_and_publishes_nothing(http_client, name="route_cancel"):
    """The whole promise, on the real route: stop in the closing passes →
    `cancelled: true`, stage restored, and the report from the previous run is
    still the report on disk, byte for byte."""
    from screenplay_studio import webapp_server

    name = _mk_project(http_client, name)

    # A first, complete run: this is the report the writer must not lose.
    r = http_client.post(f"/api/projects/{name}/analyze", json={"force": True, "report_language": "eng"})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    assert not r.get_json().get("cancelled")
    report_path = os.path.join(_project_dir(name), "report.md")
    assert os.path.exists(report_path), "the first run produced no report"
    before = open(report_path, "rb").read()

    # Now re-run, and stop inside the closing window.
    #
    # The click must set the event THE RUN is watching, not a fresh one: the
    # route registers `_ANALYZE_CANCEL[name]` and hands its `is_set` to the
    # pipeline. (Getting this wrong is how a test can "prove" a guard is
    # missing when the guard is fine — the first draft of this file did exactly
    # that.)
    import screenplay_analyzer.pipeline as pipe

    real_floor = pipe.apply_evidence_floor

    def floor_then_stop(findings):
        ev = webapp_server._ANALYZE_CANCEL.get(name)
        assert ev is not None, "the run must register a cancel event before it starts"
        ev.set()
        return real_floor(findings)

    pipe.apply_evidence_floor = floor_then_stop
    try:
        r2 = http_client.post(f"/api/projects/{name}/analyze",
                              json={"force": True, "report_language": "eng"})
    finally:
        pipe.apply_evidence_floor = real_floor

    assert r2.status_code == 200, r2.get_data(as_text=True)[:300]
    body = r2.get_json()
    assert body.get("cancelled") is True, f"a stopped run must say so: {body}"
    assert body["stages"]["analyze"] == "complete", (
        "the stage returns to the pre-run state — this was a re-run of a "
        "complete project, so 'complete' with the OLD report is correct")

    # The report must be the one from the first run, untouched.
    assert open(report_path, "rb").read() == before, "a stopped run rewrote the report"

    # And the heartbeat the desk polls says cancelled, not done.
    hb = json.load(open(os.path.join(_project_dir(name), "progress.json"), encoding="utf-8"))
    assert hb["status"] == "cancelled"
    assert hb["stage"] != "done", "a stopped run must never leave 'done' for the poller"


def test_cancelled_run_restores_a_pending_first_run(http_client):
    """A stop on a FIRST run returns the stage to pending — it must not leave a
    project looking analysed when nothing was ever written."""
    from screenplay_studio import webapp_server

    name = _mk_project(http_client, "route_cancel_first")
    # Simulate the writer pressing Stop as the run starts: pre-set the event so
    # the very first check fires. (The run registers its event, then the
    # pipeline's first `_cp()` sees a set event.)
    ev = threading.Event()
    ev.set()
    webapp_server._ANALYZE_CANCEL[name] = ev

    r = http_client.post(f"/api/projects/{name}/analyze",
                         json={"force": True, "report_language": "eng"})
    assert r.status_code == 200
    assert r.get_json().get("cancelled") is True
    assert r.get_json()["stages"]["analyze"] == "pending"
    assert not os.path.exists(os.path.join(_project_dir(name), "report.md"))


def test_retry_route_is_cancellable_and_says_so(http_client):
    """The retry path (gap 66, still one lifecycle): a stopped retry answers
    `cancelled: true` and leaves the partial record — and the report — alone.
    Without the fix this answered a 502 describing a deliberate stop as a
    fault, with the stage marked `failed`."""
    from screenplay_studio import webapp_server

    name = _mk_project(http_client, "route_retry_cancel")

    # Give the project a partial record so the retry route will accept it.
    pdir = _project_dir(name)
    m = webapp_server._load_manifest(name)
    m.mark_complete("analyze", {
        "report_md": m.report_md_path,
        "report_findings": m.report_findings_path,
        "failed_categories": ["genre"],
    })
    m.save()
    webapp_server.atomic_write_json(m.report_findings_path,
                                    {"findings": [], "meta": {"title": m.title}})
    with open(m.report_md_path, "w", encoding="utf-8") as f:
        f.write("# previous report\n")
    before = open(m.report_md_path, "rb").read()

    ev = threading.Event()
    ev.set()
    webapp_server._ANALYZE_CANCEL[name] = ev

    r = http_client.post(f"/api/projects/{name}/analyze/retry-failed", json={})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    body = r.get_json()
    assert body.get("cancelled") is True
    assert open(m.report_md_path, "rb").read() == before, "a stopped retry rewrote the report"
    hb = json.load(open(os.path.join(pdir, "progress.json"), encoding="utf-8"))
    assert hb["status"] == "cancelled"


def test_a_finished_run_leaves_no_cancel_event_behind(http_client):
    """The lifecycle is run-scoped: the event dies with the run, or the NEXT run
    would cancel the moment it started. Both routes clear it (and so does a
    raise out of the retry path — that one leaked)."""
    from screenplay_studio import webapp_server

    name = _mk_project(http_client, "route_no_leak")
    r = http_client.post(f"/api/projects/{name}/analyze", json={"force": True, "report_language": "eng"})
    assert r.status_code == 200 and not r.get_json().get("cancelled")
    assert name not in webapp_server._ANALYZE_CANCEL, "a completed run leaked its cancel event"

    # And a retry that raises terminally must not leak either.
    m = webapp_server._load_manifest(name)
    m.stages["analyze"].status = "failed"
    m.stages["analyze"].output_paths = {"failed_categories": ["genre"]}
    m.save()
    r2 = http_client.post(f"/api/projects/{name}/analyze/retry-failed", json={})
    assert name not in webapp_server._ANALYZE_CANCEL, "a failed retry leaked its cancel event"
    assert r2.status_code in (200, 502)


def test_cancel_route_reports_the_run_that_is_actually_live(http_client):
    """The stop endpoint is run-scoped too: 409 when nothing is running, 200
    with `cancel_requested` when one is. (Pinned for the lifecycle as a whole —
    the desk must never be able to "stop" a run that does not exist and believe
    it worked.)"""
    from screenplay_studio import webapp_server

    name = _mk_project(http_client, "route_stop_scope")
    assert http_client.post(f"/api/projects/{name}/analyze/cancel").status_code == 409

    ev = threading.Event()
    webapp_server._ANALYZE_CANCEL[name] = ev
    lock = webapp_server._analyze_lock(name)
    assert lock.acquire(blocking=False)
    try:
        r = http_client.post(f"/api/projects/{name}/analyze/cancel")
        assert r.status_code == 200 and r.get_json()["cancel_requested"] is True
        assert ev.is_set()
    finally:
        lock.release()
        webapp_server._ANALYZE_CANCEL.pop(name, None)
