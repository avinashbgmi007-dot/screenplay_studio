"""The analyze contract that the gun_pen audit's three converted checks assert.

UX-4 (round-3 audit 2026-09-25). Commit `25aacf8` replaced three
`check(name, True)` calls in `tests/e2e_browser_gun_pen_audit.py` with real
conditions — *"force re-analysis accepted"*, *"analysis completed"*, *"the new
pass wrote a fresh arrival snapshot"* — and that suite is the fleet's **one skip**
(it POSTs a live `/analyze` and needs a llama-server), so **they have never
executed**. The replacement is correct; its value was zero.

Those three GUARANTEES are not model-dependent — they are the server's contract —
so they live here now, where they run on every `pytest`. The gun_pen suite keeps
its own versions, because what it exists for is the real-model depth.

Guarantee 3's *arithmetic* is already covered in `test_revision.py`
(`last_pass_snapshot` seeds on the first pass, diffs distinct finding ids, and
refuses to manufacture progress out of duplicate rows). What is asserted here is
the **HTTP half**: that the snapshot actually arrives on `GET /edits` carrying the
fields the arrival strip reads by name, so a partial or backwards-dated snapshot
fails here rather than NPE-ing further down.
"""

from __future__ import annotations

import io
import os
import time

import pytest

import screenplay_studio.webapp_server as webapp_server

# The fields the arrival strip reads BY NAME. A snapshot missing any of them
# cannot be rendered.
REQUIRED_SNAPSHOT_FIELDS = ("computed_at", "last_total", "prev_total",
                            "still_live", "fixed", "new")

SAMPLE_SCRIPT = b"""Title: Analyze Contract
Author: Test

INT. STUDY - NIGHT

MARA takes out an old REVOLVER, setting it on the desk.

CUT TO:

INT. KITCHEN - DAY

Mara sits at the table, staring at nothing.
"""


@pytest.fixture
def client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _upload(client) -> str:
    resp = client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "s.fountain"), "title": "Analyze Contract"},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (200, 201), resp.get_data(as_text=True)
    return resp.get_json()["project"]


def _analyze(client, project):
    """POST a forced analyze and return (status, parsed-body-or-None)."""
    resp = client.post(f"/api/projects/{project}/analyze", json={"force": True})
    try:
        return resp.status_code, resp.get_json()
    except Exception:
        return resp.status_code, None


def _snapshot(client, project):
    resp = client.get(f"/api/projects/{project}/edits")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json().get("last_pass")


# ---------------------------------------------------------------------------
# Guarantee 1 — "force re-analysis accepted" is MEASURED, not inferred from the
# status-code branch it sits in. A 200 whose body is an error envelope, another
# project's summary, or non-JSON is the server NOT confirming the forced run.
# ---------------------------------------------------------------------------

def test_a_forced_analysis_is_accepted_with_this_projects_summary(client):
    project = _upload(client)
    status, ack = _analyze(client, project)

    assert status in (200, 201), f"HTTP {status}: {ack}"
    assert isinstance(ack, dict), (
        f"the accepted response must be this project's manifest summary, got "
        f"{type(ack).__name__}")
    assert ack.get("project") == project, (
        f"the ack names {ack.get('project')!r}, not {project!r} — the client "
        "cannot tell which project the run was accepted for")
    assert not ack.get("error"), (
        f"a 200 carrying an error envelope is NOT an accepted run: {ack.get('error')!r}")


# ---------------------------------------------------------------------------
# Guarantee 2 — a completed analysis must LEAVE a non-empty report behind. The
# heartbeat flipping is only half the promise; without this the arrival strip
# counts a pass that produced nothing.
# ---------------------------------------------------------------------------

def test_a_completed_analysis_leaves_a_non_empty_report(client):
    project = _upload(client)
    status, ack = _analyze(client, project)
    assert status in (200, 201) and not ack.get("error"), ack

    resp = client.get(f"/api/projects/{project}/report")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    findings = resp.get_json().get("findings") or []
    assert findings, (
        "the analysis was accepted and completed, but the live report carries "
        "zero findings — the desk would render a pass that produced nothing")


def test_an_unanalyzed_project_has_no_findings_yet(client):
    """The control for guarantee 2: "the report has findings" must be about the
    ANALYZE, not about the endpoint always returning a list. Without this, a
    `/report` that fabricated findings for every project would pass the test
    above."""
    project = _upload(client)
    resp = client.get(f"/api/projects/{project}/report")
    if resp.status_code == 200:
        assert not (resp.get_json().get("findings") or []), (
            "an unanalyzed project reported findings — the guarantee above is "
            "then not evidence of anything")
    else:
        assert resp.status_code in (400, 404), resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Guarantee 3 — the new pass writes a FRESH arrival snapshot: strictly newer, and
# carrying every field the strip reads by name.
# ---------------------------------------------------------------------------

def test_a_second_pass_writes_a_fresh_arrival_snapshot(client):
    project = _upload(client)

    seen = []
    for i in range(3):
        status, ack = _analyze(client, project)
        assert status in (200, 201) and not ack.get("error"), (i, status, ack)
        snap = _snapshot(client, project)
        if snap is not None:
            seen.append(snap)
        # `computed_at` is time.time(); make sure two passes cannot land on the
        # same stamp on a coarse clock.
        time.sleep(0.2)

    assert len(seen) >= 2, (
        f"only {len(seen)} snapshot(s) after three passes — the first pass seeds "
        "and later passes must write the arithmetic")
    a, b = seen[-2], seen[-1]
    assert b["computed_at"] > a["computed_at"], (
        f"the newest snapshot is not strictly newer ({a['computed_at']} -> "
        f"{b['computed_at']}) — the arrival strip would be compared against the "
        "previous pass")
    missing = [k for k in REQUIRED_SNAPSHOT_FIELDS if b.get(k) is None]
    assert not missing, (
        f"the snapshot is missing the field(s) {missing} that the arrival strip "
        f"reads by name: {sorted(b)}")
