"""
Non-writing feedback filter — findings that comment on the script's LANGUAGE
itself (dialect identification, subtitle/accessibility meta-commentary) are
noise for the writer and are dropped. Regression for the live finding:
"The dialect/mixed language ("Em ra Rahul," "paisal anni," etc.) reads as
regional — probably Telugu or a South Indian language..."
"""

import io
import json
import os

import pytest

from screenplay_analyzer import feedback_filter
from screenplay_analyzer.feedback_filter import filter_findings, is_non_writing_feedback

DIALECT_FINDING = {
    "category": "dialogue",
    "issue": "The dialect/mixed language (\"Em ra Rahul,\" \"paisal anni,\" etc.) reads as regional — probably Telugu or a South Indian language.",
    "why_it_matters": "It's working to establish character voice, though it'll need either subtitles or context for non-native speakers.",
    "severity": "low",
    "scene_refs": [3],
    "evidence_quote": "Em ra Rahul",
}

CRAFT_FINDING = {
    "category": "dialogue",
    "issue": "The line is on-the-nose: Ravi says exactly what he feels.",
    "why_it_matters": "Dialogue that names the emotion flattens the subtext a restrained scene needs.",
    "severity": "medium",
    "scene_refs": [3],
    "evidence_quote": "Light banchey!",
}

VOICE_FINDING = {
    "category": "voice",
    "issue": "Two characters read as one voice.",
    "why_it_matters": "Their dialogue shares the same sentence rhythm and word choices, so the reader loses the distinction between them.",
    "severity": "medium",
    "scene_refs": [1, 4],
    "evidence_quote": None,
}


class TestFilterUnit:
    def test_dialect_identification_dropped(self):
        assert is_non_writing_feedback(DIALECT_FINDING) is True

    def test_subtitle_accessibility_dropped(self):
        f = dict(DIALECT_FINDING)
        f["issue"] = "Needs subtitles for audiences that don't speak the language."
        f["why_it_matters"] = "Non-native speakers will miss the tone of the exchange."
        assert is_non_writing_feedback(f) is True

    def test_code_switching_identification_dropped(self):
        f = dict(DIALECT_FINDING)
        f["issue"] = "The code-switching between English and Telugu is frequent."
        assert is_non_writing_feedback(f) is True

    def test_craft_finding_kept_even_with_dialect_quote(self):
        # Evidence quotes are verbatim script text and must never trigger.
        assert is_non_writing_feedback(CRAFT_FINDING) is False

    def test_voice_bleed_finding_kept(self):
        assert is_non_writing_feedback(VOICE_FINDING) is False

    def test_character_voice_praise_kept(self):
        f = {
            "issue": "The consistent dialect establishes a strong voice for this character.",
            "why_it_matters": "The character reads as specific and grounded even in short exchanges.",
        }
        assert is_non_writing_feedback(f) is False

    def test_language_barrier_as_story_element_kept(self):
        # A language gap BETWEEN characters is story craft, not meta-commentary.
        f = {
            "issue": "The language barrier between the two leads is never dramatized.",
            "why_it_matters": "They speak different languages but understand each other instantly — the audience won't buy it.",
        }
        assert is_non_writing_feedback(f) is False

    def test_filter_findings_drops_only_bad_ones(self):
        out = filter_findings([DIALECT_FINDING, CRAFT_FINDING, VOICE_FINDING])
        assert out == [CRAFT_FINDING, VOICE_FINDING]

    def test_filter_tolerates_garbage(self):
        assert filter_findings(None) == []
        assert filter_findings([None, "x", {}, {"issue": "reads as regional"}]) == [{}]

    def test_severity_missing_still_filtered(self):
        f = {"issue": "probably Telugu dialogue", "why_it_matters": "x"}
        assert is_non_writing_feedback(f) is True


SAMPLE_SCRIPT = b"""Title: Filter Test
Author: Test

INT. ROOM - NIGHT

MARA enters slowly.

MARA
Em ra Rahul, ippudu enduku vacchav?

DEREK
Paisal anni ayipoyayi.

CUT TO:

INT. HALL - DAY

MARA stands at the door.
"""


@pytest.fixture
def http_client(tmp_path, mock_server):
    import screenplay_studio.webapp_server as webapp_server
    webapp_server.PROJECTS_DIR = str(tmp_path / "filter_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _upload(http_client):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"), "title": "Filter Test"},
        content_type="multipart/form-data",
    )


def _seed_report(tmp_path, http_client, project_name):
    """Force a stored report containing a dialect finding + a craft finding."""
    from screenplay_studio.manifest import ProjectManifest, StageStatus
    project_dir = os.path.join(webapp_dir_of(http_client), project_name)
    m = ProjectManifest.load(project_dir)
    m.stages["analyze"] = StageStatus(status="complete", output_paths={"report": "x"})
    report = {
        "title": "Filter Test",
        "findings": [DIALECT_FINDING, CRAFT_FINDING, VOICE_FINDING],
        "formatting_findings": [],
        "stats": {},
        "verification_summary": {},
        "errors": [],
    }
    with open(m.report_findings_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False)
    m.save()


def webapp_dir_of(http_client):
    import screenplay_studio.webapp_server as webapp_server
    return webapp_server.PROJECTS_DIR


class TestFilterAPI:
    def test_report_served_sanitized(self, tmp_path, http_client):
        project = _upload(http_client).get_json()["project"]
        _seed_report(tmp_path, http_client, project)
        resp = http_client.get(f"/api/projects/{project}/report")
        assert resp.status_code == 200
        findings = resp.get_json()["findings"]
        assert [f["issue"] for f in findings] == [CRAFT_FINDING["issue"], VOICE_FINDING["issue"]]

    def test_fixqueue_served_sanitized(self, tmp_path, http_client):
        project = _upload(http_client).get_json()["project"]
        _seed_report(tmp_path, http_client, project)
        resp = http_client.get(f"/api/projects/{project}/fixqueue")
        assert resp.status_code == 200
        issues = [i["issue"] for i in resp.get_json()["items"]]
        assert DIALECT_FINDING["issue"] not in issues
        assert CRAFT_FINDING["issue"] in issues
        # indices stay aligned with the sanitized list (rewrite resolution
        # consumes the same list, so clicks always hit the right finding)
        assert {i["index"] for i in resp.get_json()["items"]} == {0, 1}

    def test_stored_report_file_untouched(self, tmp_path, http_client):
        """Sanitization is display-time only — the stored JSON keeps the
        original findings, so a re-analysis or export isn't lossy."""
        project = _upload(http_client).get_json()["project"]
        _seed_report(tmp_path, http_client, project)
        http_client.get(f"/api/projects/{project}/report")
        import screenplay_studio.webapp_server as webapp_server
        with open(os.path.join(webapp_server.PROJECTS_DIR, project, "report.findings.json"), encoding="utf-8") as f:
            stored = json.load(f)
        assert len(stored["findings"]) == 3


class _StubClient:
    """Minimal LlamaServerClient stand-in: dialogue returns a dialect
    finding, everything else returns empty structures."""

    def __init__(self):
        self.calls = 0

    def resolve_model(self):
        return "stub-model"

    def chat_json(self, *args, **kwargs):
        self.calls += 1
        return {"findings": [DIALECT_FINDING, CRAFT_FINDING]}


class TestFilterInPipeline:
    def test_analyze_drops_language_meta_findings(self):
        import sys
        import tempfile
        from screenplay_parser import parse_fountain
        from screenplay_analyzer.pipeline import analyze

        with tempfile.NamedTemporaryFile("w", suffix=".fountain", delete=False, encoding="utf-8") as f:
            f.write(SAMPLE_SCRIPT.decode("utf-8"))
            path = f.name
        try:
            doc = parse_fountain(path)
        finally:
            os.unlink(path)

        client = _StubClient()
        result = analyze(
            doc, client,
            run_categories=("dialogue",),  # skip summaries/coverage/principles
        )
        issues = [f["issue"] for f in result.findings]
        assert DIALECT_FINDING["issue"] not in issues
        assert CRAFT_FINDING["issue"] in issues
