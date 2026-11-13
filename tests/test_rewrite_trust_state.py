"""The `/rewrite` grounding block must carry the finding's trust state.

`compact_summary()` (the chat prompt) and this block are the desk's two
findings-to-model surfaces, and they failed the same way: a finding demoted by
the analyzer arrived looking confirmed. Here the stakes are higher — the text
drives replacement lines the writer applies — so an ungrounded note formatted
`[LOW] Scene 3: ...` reads as a settled defect at uppercase severity.

Every flag below is produced by the analyzer's own guard functions, written by
the production `save_report` path and read back from disk, so this test breaks
if a demotion stops recording itself.
"""

import io
import os
import types

import pytest

import screenplay_studio.webapp_server as webapp_server
from screenplay_studio.webapp_server import _rewrite_finding_text


@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "trust_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


class _Doc:
    """The attributes the report writer and the identity check read off a
    ScriptDocument. Scene 2 has no dialogue, so the identity check can run and
    cannot prove the equation either way."""

    title = "Rewrite Trust Test"
    source_filename = "rewrite_trust.txt"
    author = None
    source_format = "txt"
    scene_count = 1
    estimated_page_count = 1.0
    parse_confidence = "high"
    all_characters = ["RAJ", "PEN GUY"]
    scenes = [types.SimpleNamespace(
        scene_number=2, heading_raw="INT. FLAT - NIGHT", elements=[], characters_present=["RAJ"]
    )]


SAMPLE_SCRIPT = b"""Title: Rewrite Trust Script
Author: Test

INT. STUDY - NIGHT

MARA takes out an old REVOLVER, setting it on the desk.

MARA
I'll tell you everything when this is over.

CUT TO:

INT. STUDY - NIGHT

The REVOLVER is still there, untouched.

MARA
Some things are better left alone.
"""


def _real_analysis():
    """An AnalysisResult whose flags were set by the analyzer's own guards."""
    from screenplay_analyzer import pipeline as P
    from screenplay_analyzer.pipeline import AnalysisResult

    result = AnalysisResult(doc=_Doc())
    result.findings = [
        # No quote, no observation -> apply_evidence_floor flags it ungrounded
        # and pins severity low. This is the row that used to read `[LOW]`.
        {"category": "dialogue", "issue": "marker-a on-the-nose line.",
         "why_it_matters": "The subtext is spoken aloud.",
         "severity": "high", "scene_refs": [2], "evidence_quote": None,
         "observation": None, "verification": {"status": "no_quote"}},
        # A quote plus an observation that argues against the note itself.
        {"category": "character", "issue": "marker-b lacks motivation.",
         "why_it_matters": "We cannot read the want.",
         "severity": "high", "scene_refs": [2], "evidence_quote": "Who asked you?",
         "observation": "The note claims no motivation; however, the script "
                        "explicitly shows a direct confrontation."},
        # A clean, cited finding: nothing should mark it.
        {"category": "structure", "issue": "marker-c act two turns too late.",
         "why_it_matters": "The midpoint lands in act three.",
         "severity": "medium", "scene_refs": [2], "evidence_quote": "Who asked you?",
         "observation": "The turn happens after the midpoint.",
         "verification": {"status": "verified"}},
    ]
    P.apply_evidence_floor(result)
    P.apply_scene_quote_rule(result.findings)
    P.apply_identity_check(result.findings, _Doc())
    return result


def _real_report(tmp_path):
    """The report dict exactly as it comes off disk."""
    import json

    from screenplay_analyzer.report import save_report

    json_path = tmp_path / "report.findings.json"
    save_report(_real_analysis(), str(tmp_path / "report.md"), str(json_path))
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def _by_row(report, row):
    for f in report["findings"]:
        if row in (f.get("issue") or ""):
            return f
    raise AssertionError(f"{row} never reached the report at all")


class TestRewriteFindingText:
    """`_rewrite_finding_text` is the whole grounding block: if a marker is not
    in its output, the model never learns the note was demoted."""

    def test_ungrounded_note_arrives_marked_not_confirmed(self, tmp_path):
        text = _rewrite_finding_text(_by_row(_real_report(tmp_path), "marker-a"))

        # The old block, still present — the marker is added, nothing removed.
        assert text.startswith("[LOW] Scene 2: marker-a on-the-nose line.")
        assert "UNGROUNDED" in text
        assert "NO QUOTE" in text
        assert "TRUST STATE" in text

    def test_the_demotion_is_explained_not_just_labelled(self, tmp_path):
        text = _rewrite_finding_text(_by_row(_real_report(tmp_path), "marker-a"))

        # The same legend the chat prompt uses: 'low' here means unproven, not
        # minor. Without this the model still reads LOW as a severity verdict.
        assert "unproven, not minor" in text
        # And the instruction that keeps it from rewriting on an unproven note.
        assert "Do not rewrite the scene to satisfy this note" in text

    def test_contested_note_is_marked(self, tmp_path):
        text = _rewrite_finding_text(_by_row(_real_report(tmp_path), "marker-b"))

        assert "CONTESTED" in text
        assert "Do not rewrite the scene to satisfy this note" in text

    def test_clean_note_renders_exactly_as_before(self, tmp_path):
        """No marker, no legend, no new line: a grounded finding's block is
        byte-identical to what the route used to build inline."""
        finding = _by_row(_real_report(tmp_path), "marker-c")
        assert _rewrite_finding_text(finding) == (
            "[MEDIUM] Scene 2: marker-c act two turns too late. — "
            "The midpoint lands in act three. Evidence: \"Who asked you?\""
        )

    def test_the_route_hands_the_markers_to_the_rewriter(self, http_client, tmp_path, monkeypatch):
        """The end of the wire: not just the helper, but the string that
        actually reaches `rewrite_scene`."""
        from screenplay_analyzer.report import save_report
        from screenplay_studio import revision as revision_mod

        project = http_client.post(
            "/api/projects",
            data={"file": (io.BytesIO(SAMPLE_SCRIPT), "rewrite_trust.fountain"),
                  "title": "Rewrite Trust"},
            content_type="multipart/form-data",
        ).get_json()["project"]
        analyze = http_client.post(f"/api/projects/{project}/analyze")
        assert analyze.status_code == 200, analyze.get_data(as_text=True)

        # Overwrite whatever the pipeline produced with the real flagged report,
        # at the exact path the route reads.
        manifest = webapp_server._load_manifest(project)
        save_report(_real_analysis(), str(tmp_path / "report.md"),
                    manifest.report_findings_path)

        seen = []
        real_rewrite = revision_mod.rewrite_scene

        def spy_rewrite(client, doc, scene_number, finding_text="", instruction=""):
            seen.append(finding_text)
            return real_rewrite(client, doc, scene_number, finding_text, instruction)

        monkeypatch.setattr(revision_mod, "rewrite_scene", spy_rewrite)

        resp = http_client.post(f"/api/projects/{project}/rewrite",
                                json={"scene_number": 1, "finding_index": 0})
        assert resp.status_code == 200, resp.get_data(as_text=True)

        assert "marker-a on-the-nose line." in seen[-1], "the wrong row was grounded"
        assert "UNGROUNDED" in seen[-1], (
            f"an unproven note reached the rewriter unmarked: {seen[-1]!r}"
        )
        assert "Do not rewrite the scene to satisfy this note" in seen[-1]
