"""The desk must never silently analyze with stale code.

Measured 2026-10-13: a long-lived server analyzed with pre-fix modules and
nothing — progress, report, log — said so; only a withdrawn row proved
which code ran. The server stamps its boot revision, reports it on
/api/health, and every analyze answer carries the boot rev plus a
staleness warning (None when the tree matches boot).
"""
import io
import os

import screenplay_studio.webapp_server as webapp_server
from screenplay_studio.webapp_server import (
    _CODE_REV_AT_STARTUP, _code_revision, _stale_code_warning,
)

import pytest


@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()

SAMPLE_SCRIPT = b"""Title: Code Rev
Author: Test

INT. ROOM - NIGHT

MARA enters slowly.
"""


def test_code_revision_is_a_short_hash_in_repo():
    import subprocess
    expected = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=True, text=True, timeout=10, check=True,
    ).stdout.strip()
    assert _code_revision() in (expected, expected + "+dirty")
    assert _CODE_REV_AT_STARTUP == _code_revision()


def test_code_revision_unknown_outside_repo(tmp_path):
    assert _code_revision(str(tmp_path)) == "unknown"


def test_stale_warning_none_when_matching():
    assert _stale_code_warning("abc1234", "abc1234") is None
    assert _stale_code_warning("abc1234+dirty", "abc1234+dirty") is None


def test_stale_warning_fires_on_mismatch():
    msg = _stale_code_warning("abc1234", "def5678")
    assert msg is not None and "abc1234" in msg and "def5678" in msg


def test_stale_warning_fires_when_unknown():
    assert _stale_code_warning("unknown", "abc1234") is not None
    assert _stale_code_warning("abc1234", "unknown") is not None


def test_health_reports_boot_rev(http_client):
    body = http_client.get("/api/health").get_json()
    assert body["status"] == "ok"
    assert body["code_rev"] == _CODE_REV_AT_STARTUP


def test_analyze_answer_carries_code_rev_and_freshness(http_client):
    resp = http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "s.fountain"), "title": "Code Rev"},
        content_type="multipart/form-data",
    )
    project = resp.get_json()["project"]
    resp = http_client.post(f"/api/projects/{project}/analyze", json={"force": True})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["code_rev"] == _CODE_REV_AT_STARTUP
    # unmodified tree in the test run: fresh, so no warning
    assert body["stale_code"] is None
