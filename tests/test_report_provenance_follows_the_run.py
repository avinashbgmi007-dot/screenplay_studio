"""Gap 59 — a historical report's disclosure followed CURRENT demo mode.

The filed reproduction: a project with an analysis-complete manifest and a
Markdown report identifying `demo-craft-model`, exported through the real HTML
route. The prominent stand-in banner appeared or vanished depending on whether
`_DEMO_MODEL_ACTIVE` happened to be true at export time — not on what produced
the report. The inverse (a real-model report labelled canned while demo mode was
on) was a source inference in the filing; it is reproduced here.

Gap 88 had already routed the KNOWN cases through the run's `model_used`. What
remained was the `None` branch, which fell back to the same live global and so
undid the fix for every report that does not record its model — including
legacy ones. The honest answer there is "unknown", which is now its own banner
rather than a guess in either direction.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_studio import webapp_server as ws


@pytest.fixture
def demo(monkeypatch):
    """Set the live flag for a test without leaking it."""
    def _set(active):
        monkeypatch.setattr(ws, "_DEMO_MODEL_ACTIVE", active)
    return _set


# ---------- the filed reproduction ----------

def test_a_demo_report_keeps_its_banner_after_the_writer_connects(demo):
    demo(False)
    assert ws._report_banner("demo-craft-model") == ws.DEMO_REPORT_BANNER


def test_a_real_report_is_not_labelled_canned_while_demo_is_on(demo):
    """The inverse the entry inferred from source — reproduced here."""
    demo(True)
    assert ws._report_banner("my-llama-7b") == ""


def test_the_banner_does_not_depend_on_the_current_setting(demo):
    """The whole gap in one assertion: for any given report, flipping the live
    flag must not change its disclosure."""
    for model_used in ("demo-craft-model", "my-llama-7b", None):
        demo(True)
        on = ws._report_banner(model_used)
        demo(False)
        off = ws._report_banner(model_used)
        assert on == off, f"disclosure for {model_used!r} followed the live flag"


# ---------- the `None` branch that undid gap 88 ----------

def test_an_unrecorded_origin_is_unknown_not_a_guess(demo):
    demo(True)
    assert ws._report_banner(None) == ws.UNKNOWN_ORIGIN_BANNER
    demo(False)
    assert ws._report_banner(None) == ws.UNKNOWN_ORIGIN_BANNER


def test_an_empty_model_id_is_treated_as_unrecorded(demo):
    demo(False)
    for blank in ("", "   ", None):
        assert ws._report_banner(blank) == ws.UNKNOWN_ORIGIN_BANNER


def test_the_unknown_banner_says_unknown_and_does_not_claim_either_way(demo):
    demo(False)
    banner = ws._report_banner(None).lower()
    assert "not recorded" in banner
    assert "unknown" in banner
    # it must not assert the report is canned, nor that it is real
    assert "canned, not a reading" not in banner
    assert "real review" not in banner


# ---------- the served report carries provenance ----------

def _project(tmp_path, model_used, findings=True):
    from screenplay_parser import parse_screenplay
    from screenplay_studio.manifest import ProjectManifest
    import shutil
    shutil.rmtree(tmp_path, ignore_errors=True)   # one fresh project per call
    os.makedirs(tmp_path, exist_ok=True)
    src = tmp_path / "s.fountain"
    src.write_text("Title: T\n\nINT. ROOM - DAY\n\nMIRA\nHello.\n", encoding="utf-8")
    m = ProjectManifest.create(str(tmp_path / "p1"), str(src), title="T")
    parse_screenplay(m.source_path).save(m.parsed_path)
    m.stage("analyze").status = "complete"
    m.save()
    payload = {"title": "T", "findings": [], "errors": [], "notices": [],
               "recoveries": [], "withdrawals": [], "stats": {}}
    if model_used is not None:
        payload["model_used"] = model_used
    with open(m.report_findings_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    with open(m.report_md_path, "w", encoding="utf-8") as f:
        f.write("# Report\n\nNothing much.\n")
    return m


def test_the_served_report_exposes_tri_state_provenance(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    for model_used, expected in (("demo-craft-model", True),
                                 ("my-llama-7b", False),
                                 (None, None)):
        m = _project(tmp_path, model_used)
        r = client.get(f"/api/projects/{os.path.basename(m.project_dir)}/report")
        assert r.status_code == 200, r.get_json()
        prov = r.get_json()["provenance"]
        assert prov["stand_in"] is expected, (model_used, prov)


def test_the_export_follows_the_report_not_the_flag(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    m = _project(tmp_path, "demo-craft-model")
    monkeypatch.setattr(ws, "_DEMO_MODEL_ACTIVE", False)
    html = client.get(f"/api/projects/{os.path.basename(m.project_dir)}/report/export").data.decode()
    assert "Built-in stand-in model" in html


def test_the_export_of_an_unrecorded_report_says_unknown(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    m = _project(tmp_path, None)
    monkeypatch.setattr(ws, "_DEMO_MODEL_ACTIVE", True)
    html = client.get(f"/api/projects/{os.path.basename(m.project_dir)}/report/export").data.decode()
    assert "Report origin not recorded" in html
    assert "Built-in stand-in model." not in html, "must not claim it is canned"


# ---------- the markdown artifact agrees ----------

def test_markdown_states_an_unrecorded_model():
    from screenplay_analyzer.pipeline import AnalysisResult
    from screenplay_analyzer.report import render_markdown
    from screenplay_parser import parse_fountain
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False,
                                     encoding="utf-8") as f:
        f.write("Title: T\n\nINT. ROOM - DAY\n\nMIRA\nHello.\n")
        path = f.name
    try:
        doc = parse_fountain(path)
    finally:
        os.unlink(path)
    r = AnalysisResult(doc=doc)
    r.model_used = None
    md = render_markdown(r)
    assert "not recorded" in md.lower()
    assert "unknown" in md.lower()


# ---------- the client keeps the two subjects apart ----------

def test_the_client_scopes_report_origin_separately_from_the_connection():
    """Source pin: the report's banner must not be driven by the live flag.

    The defect was one attribute claiming both subjects. Two attributes and two
    predicates is the structural half of the fix; the browser half is exercised
    by the e2e suite.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "screenplay_studio", "webapp", "app.js"),
              encoding="utf-8") as f:
        js = f.read()
    assert "function applyReportOrigin" in js
    start_at = js.index("function applyReportOrigin")
    end_at = js.index("function applyDemoDisclosure")
    body = js[start_at:end_at]
    assert "state.config" not in body, "report origin must not read the live config"
    assert "reportProvenance" in body, "it must read the report's own record"

    with open(os.path.join(root, "screenplay_studio", "webapp", "index.html"),
              encoding="utf-8") as f:
        html = f.read()
    assert 'data-report-origin="stand-in"' in html
    assert 'data-report-origin="unknown"' in html


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(tmp_path))
    ws.app.config["TESTING"] = True
    return ws.app.test_client()
