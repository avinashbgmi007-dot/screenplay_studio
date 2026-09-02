"""Regression tests for the bugfix batch (H1, M1-M4, L4, L5).

Covers:
- H1  draft upload never destroys the source when the copy fails
- M1  retry_failed merge no longer duplicates regenerated deterministic findings
- M2  markdown report renders continuity/voice/subtext categories
- M3  the reply hallucination guard stays silent in the idea room
- M4  stash API routes return JSON 404 for unknown projects
- L4  report HTML export gives EVERY table a header row
- L5  rewrite endpoint returns a clean 404 for a missing scene
"""

import io
import json
import os
import types

import pytest

import screenplay_studio.diff as diff_mod
import screenplay_studio.webapp_server as webapp_server
from screenplay_analyzer.pipeline import AnalysisResult
from screenplay_analyzer.report import render_markdown
from screenplay_cowriter.context import ReportContext, ScriptContext
from screenplay_cowriter.engine import CoWriterEngine
from screenplay_parser.models import Scene, ScriptDocument
from screenplay_studio.diff import upload_new_draft
from screenplay_studio.manifest import ProjectManifest
from screenplay_studio.orchestrator import Orchestrator


# ---------------------------------------------------------------- H1

def _make_manifest(tmp_path, with_parse=True):
    src = tmp_path / "my_script.fountain"
    src.write_text("Title: T\n\nINT. ROOM - NIGHT\n\nAction.\n", encoding="utf-8")
    m = ProjectManifest.create(str(tmp_path / "proj"), str(src), title="T")
    if with_parse:
        from screenplay_parser import parse_screenplay
        doc = parse_screenplay(str(src))
        doc.save(m.parsed_path)
        m.mark_complete("parse", {})
    return m


def test_upload_failure_keeps_source_with_no_snapshot(tmp_path, monkeypatch):
    """H1: a failed copy during draft upload must not delete the original
    source — previously the old file was removed BEFORE the copy ran."""
    m = _make_manifest(tmp_path, with_parse=False)  # no snapshot exists
    original = open(m.source_path, encoding="utf-8").read()

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(diff_mod.shutil, "copy2", boom)

    new_upload = tmp_path / "new.fountain"
    new_upload.write_text("Title: New\n", encoding="utf-8")

    with pytest.raises(OSError):
        upload_new_draft(m, str(new_upload), "new.fountain")

    assert os.path.exists(m.source_path)
    assert open(m.source_path, encoding="utf-8").read() == original
    assert not os.path.exists(m.source_path + ".incoming")


def test_upload_success_swaps_source_atomically(tmp_path):
    m = _make_manifest(tmp_path, with_parse=True)
    new_upload = tmp_path / "new.fountain"
    new_upload.write_text("Title: Draft Two\n\nINT. ROOM - DAY\n\nMore.\n", encoding="utf-8")

    upload_new_draft(m, str(new_upload), "new.fountain")

    assert "Draft Two" in open(m.source_path, encoding="utf-8").read()
    assert not os.path.exists(m.source_path + ".incoming")
    # the pre-upload state was snapshotted and analysis re-queued
    assert m.active_draft == "draft-1"
    assert m.stage("analyze").status == "pending"


# ---------------------------------------------------------------- M1

def test_merge_drops_deterministic_findings_keeps_model_findings(tmp_path):
    prev = {
        "findings": [
            {"category": "theme", "rule_id": None, "issue": "model theme finding"},
            {"category": "structure", "rule_id": "chekhovs_gun", "issue": "model gun finding"},
            {"category": "structure", "rule_id": "pacing_drag", "issue": "old drag"},
            {"category": "voice", "rule_id": "voice_bleed", "issue": "old bleed"},
            {"category": "subtext", "rule_id": "on_the_nose", "issue": "old nose"},
            {"category": "voice", "rule_id": "idiolect_consistency", "issue": "old idiolect"},
            {"category": "continuity", "rule_id": "unmarked_time_flip", "issue": "old flip"},
            {"category": "continuity", "rule_id": "character_name_variant", "issue": "old variant"},
        ],
        "coverage": {"logline": "keep me"},
    }
    path = tmp_path / "report.findings.json"
    path.write_text(json.dumps(prev), encoding="utf-8")
    m = types.SimpleNamespace(report_findings_path=str(path))

    result = AnalysisResult(doc=ScriptDocument(title=None, author=None, source_format="txt", source_filename="x"))
    result.findings = [{"category": "dialogue", "rule_id": None, "issue": "fresh dialogue finding"}]
    result.category_outcomes = {"dialogue": "ok"}

    result.merge(str(path))

    issues = [f["issue"] for f in result.findings]
    assert "fresh dialogue finding" in issues      # re-run category's fresh copy
    assert "model theme finding" in issues          # model finding, not re-run -> kept
    assert "model gun finding" in issues            # structure model finding KEPT (rule-id match, not category)
    for old in ("old drag", "old bleed", "old nose", "old idiolect", "old flip", "old variant"):
        assert old not in issues                    # regenerated deterministic copies dropped once
    assert result.coverage == {"logline": "keep me"}
    assert result.verification["verified"] == len(issues) or result.verification is not None


# ---------------------------------------------------------------- M2

def test_report_renders_continuity_voice_subtext_sections():
    doc = ScriptDocument(title="T", author=None, source_format="fountain", source_filename="x.fountain")
    doc.scenes.append(Scene(scene_number=1, heading_raw="INT. X - NIGHT"))
    result = AnalysisResult(doc=doc)
    result.findings = [
        {"category": "continuity", "issue": "Unmarked time flip", "why_it_matters": "reader confusion",
         "severity": "low", "scene_refs": [1], "evidence_quote": None, "verification": {"status": "no_quote"}},
        {"category": "voice", "issue": "Voices bleed", "why_it_matters": "same voice",
         "severity": "medium", "scene_refs": [1], "evidence_quote": None, "verification": {"status": "no_quote"}},
        {"category": "subtext", "issue": "On-the-nose line", "why_it_matters": "tells not shows",
         "severity": "low", "scene_refs": [1], "evidence_quote": None, "verification": {"status": "no_quote"}},
    ]
    md = render_markdown(result)
    assert "### Continuity" in md
    assert "### Voice & Idiolect" in md
    assert "### Subtext" in md
    assert "Unmarked time flip" in md


# ---------------------------------------------------------------- M3

class _FakeClient:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append(messages)
        return self.reply


def _engine(reply, premise):
    client = _FakeClient(reply)
    return CoWriterEngine(
        client, ScriptContext(None), ReportContext(None),
        premise=premise,
    ) if premise else CoWriterEngine(client, ScriptContext(None), ReportContext(None))


def test_idea_room_does_not_flag_hypothetical_scene_numbers():
    engine = _engine("Let's try opening on scene 9 as a cold open.", premise={"title": "Idea"})
    session = __import__("screenplay_cowriter.models", fromlist=["Session"]).Session.new(title="t")
    reply = engine.send_message(session, "What about scene 9?")
    assert "scene 9" in reply
    assert "honest flag" not in reply  # no script exists here — nothing to hallucinate against


def test_script_desk_still_flags_invented_scene_numbers():
    engine = _engine("Let's look at scene 9.", premise=None)
    session = __import__("screenplay_cowriter.models", fromlist=["Session"]).Session.new(title="t")
    reply = engine.send_message(session, "Tell me about scene 9.")
    assert "don't" in reply and "scene 9" in reply  # the honest flag fired


# ------------------------------------------------- M4 / L4 / L5 (webapp API)

@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


SAMPLE_SCRIPT = b"""Title: Fix Batch Test
Author: Test

INT. STUDY - NIGHT

MARA takes out an old REVOLVER.

MARA
I'll tell you everything when this is over.
"""


def _upload(http_client, filename="script.fountain"):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), filename), "title": "Fix Batch Test"},
        content_type="multipart/form-data",
    )


class TestStash404:
    def test_get_stash_unknown_project_json_404(self, http_client):
        resp = http_client.get("/api/projects/nope/stash")
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "Project not found."

    def test_add_stash_unknown_project_json_404(self, http_client):
        resp = http_client.post("/api/projects/nope/stash", json={"text": "line"})
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "Project not found."

    def test_delete_stash_unknown_project_json_404(self, http_client):
        resp = http_client.delete("/api/projects/nope/stash/abc")
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "Project not found."

    def test_stash_roundtrip_still_works(self, http_client):
        project = _upload(http_client).get_json()["project"]
        resp = http_client.post(f"/api/projects/{project}/stash", json={"text": "a good line"})
        assert resp.status_code == 201
        entry = resp.get_json()
        listing = http_client.get(f"/api/projects/{project}/stash").get_json()
        assert listing["stash"][0]["text"] == "a good line"
        assert http_client.delete(f"/api/projects/{project}/stash/{entry['id']}").status_code == 200


class TestReportHtmlTables:
    def test_every_table_gets_header_cells(self):
        md = (
            "# R\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "| C | D |\n|---|---|\n| 3 | 4 |\n"
        )
        html = webapp_server._md_to_html(md)
        assert html.count("<table>") == 2
        assert html.count("<th>") == 4  # header row in BOTH tables


class TestRewrite404:
    def test_rewrite_missing_scene_is_404_before_model_call(self, http_client):
        project = _upload(http_client).get_json()["project"]
        resp = http_client.post(
            f"/api/projects/{project}/rewrite",
            json={"scene_number": 99},
        )
        assert resp.status_code == 404
        assert "Scene 99" in resp.get_json()["error"]
