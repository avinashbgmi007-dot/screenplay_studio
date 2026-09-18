"""M4 — dismiss route must validate the finding index.

`/api/projects/<name>/findings/<int:index>/dismiss` passed the index straight to
dismiss_finding without checking it against the report's findings list, so a
stale/out-of-range index was accepted (HTTP 200) and stored as a bogus entry.
Fix: validate against the current report; out-of-range -> 400, and nothing is
written. No report yet -> 400 (there is no index space to validate against).
"""
from __future__ import annotations

import io
import json
import os

import pytest

SAMPLE = ("Title: T\n\nINT. ROOM - DAY\n\nMARA crosses.\n\nMARA\nWe leave at dawn.\n")


@pytest.fixture
def client(tmp_path, monkeypatch):
    import screenplay_studio.webapp_server as ws
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(tmp_path / "proj"))
    ws.app.config["TESTING"] = True
    return ws.app.test_client()


def _upload(client):
    return client.post("/api/projects",
                       data={"file": (io.BytesIO(SAMPLE.encode()), "s.fountain"), "title": "M4"},
                       content_type="multipart/form-data").get_json()["project"]


def _write_report(client, n_findings):
    """Drop a report.findings.json with n_findings entries into the project."""
    import screenplay_studio.webapp_server as ws
    proj = _upload(client)
    pdir = os.path.join(ws.PROJECTS_DIR, proj)
    os.makedirs(pdir, exist_ok=True)
    with open(os.path.join(pdir, "report.findings.json"), "w", encoding="utf-8") as f:
        json.dump({"findings": [{"issue": f"issue {i}", "category": "dialogue",
                                 "severity": "medium", "scene_refs": [1]} for i in range(n_findings)]}, f)
    # mark analyze complete so the report is considered live
    import json as _json
    mpath = os.path.join(pdir, "project.json")
    with open(mpath, encoding="utf-8") as f:
        man = _json.load(f)
    man.setdefault("stages", {}).setdefault("analyze", {})["status"] = "complete"
    with open(mpath, "w", encoding="utf-8") as f:
        _json.dump(man, f)
    return proj


def test_in_range_index_dismisses(client):
    proj = _write_report(client, 2)
    r = client.post(f"/api/projects/{proj}/findings/1/dismiss", json={"issue": "issue 1"})
    assert r.status_code == 200


def test_out_of_range_index_rejected(client):
    proj = _write_report(client, 2)
    r = client.post(f"/api/projects/{proj}/findings/9999/dismiss", json={"issue": "made up"})
    assert r.status_code == 400
    # and nothing was stored
    import screenplay_studio.webapp_server as ws
    dpath = os.path.join(ws.PROJECTS_DIR, proj, "dismissed.json")
    stored = json.load(open(dpath)) if os.path.exists(dpath) else []
    assert not any(d.get("index") == 9999 for d in stored)
