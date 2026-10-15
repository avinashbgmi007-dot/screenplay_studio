"""Post-trust hardening: the three edges the real-model probe + production
validation left on the table.

1. DEMO FALLBACK FALSE POSITIVE (RE-B4). The import-time reachability probe can
   only test the DEFAULT url -- `--server` is not parsed until main(). A desk
   launched with `--server http://127.0.0.1:8099` while the default :8080 is
   down used to silently run the demo craft model for the whole session. The
   fix: the auto-fallback marks itself (`_DEMO_FALLBACK_AUTO`), main() undoes
   it, applies the real --server, and re-runs the decision — an explicit demo
   choice (env/flag) is never second-guessed.

2. CHAR_READS HARDENING. One-shot chat_json call (client already retries JSON
   parses 2x; a generation that never ARRIVES is what failed) wrapped in one
   bounded retry pass, then re-raised so the existing failed_categories path
   records the reason in report.errors — instead of a 3-minute stall and a
   bare category failure.

3. SPA TRUST LINE (serve path). The dock's verificationReadout() reads
   report.verification_summary; the bundle's serve-time stamp in
   _sanitize_report guarantees the block on every served report, so the
   readout now renders for PRE-BUNDLE reports too. The unit pin lives in
   tests/e2e_browser_trust_line.py (real chain, browser); this file pins the
   SPA contract's server half plus the readout's leak guard: state.report is
   reset on project switch so a previous script's numbers can never surface
   on a new project that has no report yet.
"""
import json

import pytest

from conftest import MOCK_PORT
from screenplay_studio import webapp_server


# ---------------------------------------------------------------------------
# 1. demo-fallback false positive: the re-check state machine
# ---------------------------------------------------------------------------

@pytest.fixture
def clean_demo_state():
    """Whatever a test does to the demo globals, restore afterwards."""
    saved = (webapp_server._DEMO_MODEL_ACTIVE, webapp_server._DEMO_URL,
             webapp_server._DEMO_FALLBACK_AUTO)
    saved_cfg = dict(webapp_server.CONFIG.to_dict())
    yield
    (webapp_server._DEMO_MODEL_ACTIVE, webapp_server._DEMO_URL,
     webapp_server._DEMO_FALLBACK_AUTO) = saved
    for k, v in saved_cfg.items():
        webapp_server.CONFIG[k] = v


def test_recheck_stands_down_when_import_found_real_server(clean_demo_state):
    """Clean import (probe found the server): nothing to undo, no probe runs."""
    webapp_server._DEMO_MODEL_ACTIVE = False
    webapp_server._DEMO_URL = None
    webapp_server._DEMO_FALLBACK_AUTO = False
    called = []
    orig = webapp_server._server_reachable
    webapp_server._server_reachable = lambda url: called.append(url) or True
    try:
        webapp_server._recheck_fallback_after_args()
    finally:
        webapp_server._server_reachable = orig
    assert called == [], "must not probe when no auto-fallback is active"


def test_recheck_undoes_fallback_when_real_server_up(clean_demo_state):
    """The RE-B4 rescue: import fell back on the default url, --server points
    at a live server; the demo decision is undone and config restored."""
    webapp_server._use_demo_model(auto=True)
    assert webapp_server._DEMO_FALLBACK_AUTO is True
    real = "http://127.0.0.1:8099"
    webapp_server.CONFIG["real_server_url"] = real
    orig = webapp_server._server_reachable
    webapp_server._server_reachable = lambda url: url == real
    try:
        webapp_server.CONFIG["server_url"] = real  # what main() does with --server
        webapp_server._recheck_fallback_after_args()
    finally:
        webapp_server._server_reachable = orig
    assert webapp_server._DEMO_MODEL_ACTIVE is False
    assert webapp_server._DEMO_URL is None
    assert webapp_server._DEMO_FALLBACK_AUTO is False
    assert webapp_server.CONFIG["server_url"] == real, "--server url restored"


def test_recheck_keeps_demo_when_real_server_still_down(clean_demo_state):
    """--server is ALSO down: the fallback stands, desk stays usable."""
    webapp_server._use_demo_model(auto=True)
    orig = webapp_server._server_reachable
    webapp_server._server_reachable = lambda url: False
    try:
        webapp_server._recheck_fallback_after_args()
    finally:
        webapp_server._server_reachable = orig
    assert webapp_server._DEMO_MODEL_ACTIVE is True
    assert webapp_server._DEMO_FALLBACK_AUTO is True


def test_recheck_never_touches_explicit_demo(clean_demo_state):
    """--demo-model / env trigger: _DEMO_FALLBACK_AUTO stays False, the
    re-check must stand down even with a live server reachable."""
    webapp_server._use_demo_model()  # explicit (auto=False)
    assert webapp_server._DEMO_FALLBACK_AUTO is False
    called = []
    orig = webapp_server._server_reachable
    webapp_server._server_reachable = lambda url: called.append(url) or True
    try:
        webapp_server._recheck_fallback_after_args()
    finally:
        webapp_server._server_reachable = orig
    assert called == []
    assert webapp_server._DEMO_MODEL_ACTIVE is True


def test_use_demo_model_marks_auto_only_when_asked(clean_demo_state):
    webapp_server._use_demo_model(auto=True)
    assert webapp_server._DEMO_FALLBACK_AUTO is True
    webapp_server._undo_demo_fallback()
    assert webapp_server._DEMO_FALLBACK_AUTO is False
    webapp_server._use_demo_model()  # explicit
    assert webapp_server._DEMO_FALLBACK_AUTO is False


# ---------------------------------------------------------------------------
# 2. char_reads hardening: bounded retry, recorded failure
# ---------------------------------------------------------------------------

class _FlakyClient:
    """Fails `fail_times` times, then returns a good char_reads payload."""

    def __init__(self, fail_times, sleeps):
        self.fail_times = fail_times
        self.calls = 0
        self.sleeps = sleeps

    def chat_json(self, *a, **k):
        self.calls += 1
        if self.calls <= self.fail_times:
            from screenplay_analyzer.llm_client import LlamaServerError
            raise LlamaServerError("503 busy (server overloaded)")
        return {"reads": [{"character": "MARA", "how_reads": "steady",
                           "apparent_intent": "calm", "gap": "none",
                           "scene_refs": [1], "evidence_quote": None}]}


def test_run_character_reads_recovers_on_transient_failure(monkeypatch):
    from screenplay_analyzer import pipeline
    from screenplay_parser.text_parser import parse_fountain
    import io
    import os
    import tempfile

    buf = io.StringIO(
        "Title: t\n\nINT. STUDY - NIGHT\n\nMARA sits.\n\nMARA\nLine one.\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False) as f:
        f.write(buf.getvalue())
        path = f.name
    try:
        doc = parse_fountain(path)
    finally:
        os.unlink(path)

    delays = []
    monkeypatch.setattr(pipeline.time, "sleep", delays.append)
    client = _FlakyClient(fail_times=1, sleeps=delays)
    reads = pipeline.run_character_reads(doc, "overview", client, ["MARA"])
    assert client.calls == 2, "one transient failure -> exactly one retry"
    assert delays, "retry backs off instead of hammering"
    assert [r["character"] for r in reads] == ["MARA"]


def test_run_character_reads_fails_recorded_after_retry(monkeypatch):
    from screenplay_analyzer import pipeline
    from screenplay_analyzer.llm_client import LlamaServerError
    from screenplay_parser.text_parser import parse_fountain
    import io
    import os
    import tempfile

    buf = io.StringIO(
        "Title: t\n\nINT. STUDY - NIGHT\n\nMARA sits.\n\nMARA\nLine one.\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False) as f:
        f.write(buf.getvalue())
        path = f.name
    try:
        doc = parse_fountain(path)
    finally:
        os.unlink(path)

    delays = []
    monkeypatch.setattr(pipeline.time, "sleep", delays.append)
    client = _FlakyClient(fail_times=99, sleeps=delays)
    with pytest.raises(LlamaServerError) as ei:
        pipeline.run_character_reads(doc, "overview", client, ["MARA"])
    assert client.calls == 2, "bounded: exactly one retry, never a second stall"
    assert "character-perception read failed after 1 retry" in str(ei.value)
    assert "503 busy" in str(ei.value), "original reason carried for report.errors"


# ---------------------------------------------------------------------------
# 3. SPA trust line: the SERVE half of the chain (browser half in e2e)
# ---------------------------------------------------------------------------

@pytest.fixture
def http_client(tmp_path, mock_server):
    """Same shape as test_webapp_api.py's fixture (fixtures there are not
    shared across modules): isolated PROJECTS_DIR, config pointed at the
    mock unified server, Flask test client."""
    import os

    from screenplay_studio import webapp_server

    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def test_served_report_stamps_summary_for_prebundle_report(http_client, tmp_path):
    """A stored report with findings but NO verification_summary block (old
    analysis) gains the recomputed block at SERVE time — the SPA readout's
    data guarantee for every old project on disk. tmp_path is unused here
    (the fixture owns PROJECTS_DIR); kept in the signature for parity."""
    import io
    import os

    from screenplay_parser.text_parser import parse_fountain
    from screenplay_studio import webapp_server
    from screenplay_studio.manifest import ProjectManifest

    base = webapp_server.PROJECTS_DIR
    buf = io.StringIO(
        "Title: Old Report\n\nINT. STUDY - NIGHT\n\nMARA unlocks the drawer.\n\n"
        "MARA\nI'll tell you everything when this is over.\n"
    )
    src = os.path.join(base, "old.fountain")
    with open(src, "w", encoding="utf-8", newline="") as f:
        f.write(buf.getvalue())
    pdir = os.path.join(base, "old_report_proj")
    m = ProjectManifest.create(pdir, source_file=src, title="Old Report")
    parse_fountain(src).save(m.parsed_path)
    # Pre-bundle shape: per-finding verification existed before the bundle,
    # the AGGREGATE block did not — so the findings carry `verification`
    # fields and the report carries no verification_summary key at all.
    report = {"findings": [{
        "issue": "The gun arrives without a payoff", "category": "plot_economy",
        "severity": "high", "status": "open", "scene_refs": [1],
        "evidence_quote": "I'll tell you everything when this is over.",
        "verification": {"status": "verified", "matched_scene": 1,
                         "confidence": 1.0},
    }], "stats": {"total_findings": 1}}
    with open(m.report_findings_path, "w", encoding="utf-8", newline="") as f:
        json.dump(report, f)
    m.mark_complete("parse")
    m.mark_complete("analyze")

    r = http_client.get("/api/projects/old_report_proj/report")
    assert r.status_code == 200
    body = r.get_json()
    vs = body.get("verification_summary")
    assert vs, "serve-time stamp must add the block to a pre-bundle report"
    assert vs["verified"] == 1 and vs["quote_bearing"] == 1
    assert vs["verified_pct_of_quoted"] == 100.0
    s = http_client.get("/api/projects/old_report_proj/findings/summary").get_json()
    assert s.get("verification", {}).get("verified_pct_of_quoted") == 100.0


def test_served_summary_is_recomputed_from_served_rows(http_client, tmp_path):
    """The stamped block counts the rows being SERVED (sanitized), not the
    rows on disk — the readout can never disagree with the board under it."""
    import io
    import os

    from screenplay_parser.text_parser import parse_fountain
    from screenplay_studio import webapp_server
    from screenplay_studio.manifest import ProjectManifest

    base = webapp_server.PROJECTS_DIR
    buf = io.StringIO(
        "Title: Filtered\n\nINT. STUDY - NIGHT\n\nMARA unlocks the drawer.\n\n"
        "MARA\nI'll tell you everything when this is over.\n\n"
        "DEREK\nJust don't do anything stupid.\n"
    )
    src = os.path.join(base, "f.fountain")
    with open(src, "w", encoding="utf-8", newline="") as f:
        f.write(buf.getvalue())
    pdir = os.path.join(base, "filtered_proj")
    m = ProjectManifest.create(pdir, source_file=src, title="Filtered")
    parse_fountain(src).save(m.parsed_path)
    mk = lambda q, c, s: {  # noqa: E731
        "issue": f"note {c}", "category": "dialogue", "severity": "high",
        "status": "open", "scene_refs": [1], "evidence_quote": q,
        "verification": {"status": s, "matched_scene": 1 if s == "verified" else None,
                         "confidence": 1.0 if s == "verified" else 0.3},
    }
    report = {"findings": [mk("I'll tell you everything when this is over.", "mara", "verified"),
                           mk("Just don't do anything stupid.", "derek", "not_found")],
              "stats": {"total_findings": 2}}
    with open(m.report_findings_path, "w", encoding="utf-8", newline="") as f:
        json.dump(report, f)
    m.mark_complete("parse")
    m.mark_complete("analyze")

    body = http_client.get("/api/projects/filtered_proj/report").get_json()
    served = body["findings"]
    vs = body["verification_summary"]
    assert vs["quote_bearing"] == len([f for f in served
                                       if (f.get("evidence_quote") or "").strip()]), \
        "summary counts served rows only"
    assert vs["verified"] + vs["not_found"] == vs["quote_bearing"]
