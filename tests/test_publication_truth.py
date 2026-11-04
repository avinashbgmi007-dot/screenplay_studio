"""Gaps 2, 3 and 4 — the report must describe the script the writer is on.

Three measured failures, one shape:

* **2:** analysis loaded `parsed.json`, so a writer who fixed a line and re-ran
  analysis got findings about text that was no longer on their screen.
* **3:** a run that produced nothing usable still overwrote the previous good
  report, and `/report` then answered 400 while a valid reading was on disk.
* **4:** a run that read one draft still published after another draft became
  active, so one script's findings appeared in another script's report.

The fix is one mechanism: a run stages its whole artifact set as a generation,
and a single compare-and-publish step decides whether it may become the live
report — re-reading the live draft first and refusing if it moved.
"""
import io
import json
import os

import pytest

import screenplay_analyzer.pipeline as pipeline
import screenplay_studio.webapp_server as webapp_server
from screenplay_analyzer.pipeline import AnalysisResult
from screenplay_analyzer.report import document_digest
from screenplay_studio import report_generation
from screenplay_studio.manifest import ProjectManifest
from screenplay_studio.revision import load_working


SAMPLE = b"""Title: Truth Test

INT. STUDY - NIGHT

MARA unlocks a drawer.

MARA
The drawer was empty.
"""

EDITED_LINE = {"old": "The drawer was empty.", "new": "The drawer held a REVOLVER."}


@pytest.fixture
def client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _project(client, data=SAMPLE, filename="a.fountain"):
    resp = client.post("/api/projects",
                       data={"file": (io.BytesIO(data), filename), "title": "Truth"},
                       content_type="multipart/form-data")
    return resp.get_json()["project"]


def _manifest(project):
    return ProjectManifest.load(os.path.join(webapp_server.PROJECTS_DIR, project))


class TestAnalysisReadsWhatTheWriterSees:
    def test_the_run_reads_the_working_draft_not_the_base_parse(self, client, monkeypatch):
        project = _project(client)
        applied = client.post(f"/api/projects/{project}/edits/apply",
                              json={"scene_number": 1, "replacements": [EDITED_LINE]})
        assert applied.status_code == 200

        seen = {}
        real = pipeline.analyze

        def spy(doc, llm, **kw):
            seen["text"] = [e.text for s in doc.scenes for e in s.elements]
            return real(doc, llm, **kw)

        monkeypatch.setattr(pipeline, "analyze", spy)
        assert client.post(f"/api/projects/{project}/analyze", json={}).status_code == 200

        joined = " | ".join(seen["text"])
        assert "REVOLVER" in joined, "the analysis recomputed on text the writer had replaced"
        assert "drawer was empty" not in joined

    def test_the_published_report_names_the_script_it_read(self, client):
        project = _project(client)
        client.post(f"/api/projects/{project}/edits/apply",
                    json={"scene_number": 1, "replacements": [EDITED_LINE]})
        client.post(f"/api/projects/{project}/analyze", json={})

        report = client.get(f"/api/projects/{project}/report").get_json()
        stamp = report["snapshot"]
        live = document_digest(load_working(_manifest(project)))
        assert stamp["digest"] == live, (
            "the report's digest does not match the script on screen")
        # ...and the artifact on disk says the same thing, without the API.
        findings = json.load(open(os.path.join(
            webapp_server.PROJECTS_DIR, project, "report.findings.json"), encoding="utf-8"))
        assert findings["snapshot"]["digest"] == live

    def test_an_edit_during_the_run_refuses_publication(self, client, monkeypatch):
        """Gap 4: the draft moved between the read and the publish."""
        project = _project(client)
        real = pipeline.analyze

        def analyze_then_edit(doc, llm, **kw):
            result = real(doc, llm, **kw)
            client.post(f"/api/projects/{project}/edits/apply",
                        json={"scene_number": 1, "replacements": [EDITED_LINE]})
            return result

        monkeypatch.setattr(pipeline, "analyze", analyze_then_edit)
        resp = client.post(f"/api/projects/{project}/analyze", json={})
        assert resp.status_code == 502
        assert "draft changed" in resp.get_json()["error"].lower()
        assert client.get(f"/api/projects/{project}/report").status_code == 400, (
            "nothing was published, so there is no report — and no half-report")


class TestPublicationIsOnePointerSwap:
    def test_a_failed_run_keeps_the_previous_reading(self, client, monkeypatch):
        project = _project(client)
        assert client.post(f"/api/projects/{project}/analyze", json={}).status_code == 200
        good = client.get(f"/api/projects/{project}/report").get_json()
        project_dir = os.path.join(webapp_server.PROJECTS_DIR, project)
        md_before = open(os.path.join(project_dir, "report.md"), encoding="utf-8").read()

        def total_failure(doc, llm, **kw):
            result = AnalysisResult(doc)
            result.errors = ["model unreachable for the whole run"]
            result.coverage = None
            return result

        monkeypatch.setattr(pipeline, "analyze", total_failure)
        assert client.post(f"/api/projects/{project}/analyze",
                           json={"force": True}).status_code == 502

        assert open(os.path.join(project_dir, "report.md"), encoding="utf-8").read() == md_before
        after = client.get(f"/api/projects/{project}/report")
        assert after.status_code == 200, "the last valid reading is still on the desk"
        body = after.get_json()
        assert body["published"]["is_stale"] is True, (
            "a reading that predates the failed attempt must say so")
        assert body["snapshot"]["digest"] == good["snapshot"]["digest"]

    def test_a_staged_generation_carries_its_own_manifest(self, client):
        project = _project(client)
        client.post(f"/api/projects/{project}/analyze", json={})
        m = _manifest(project)
        gen = client.get(f"/api/projects/{project}/report").get_json()["published"]["generation"]
        gen_dir = os.path.join(m.report_generations_dir, gen)
        man = report_generation.load_manifest(gen_dir)
        assert man["digest"] == document_digest(load_working(_manifest(project)))
        assert os.path.exists(os.path.join(gen_dir, man["markdown"]))
        assert os.path.exists(os.path.join(gen_dir, man["findings"]))
        assert os.path.exists(os.path.join(gen_dir, man["snapshot"])), (
            "the generation must carry the exact document it read")

    def test_an_incomplete_generation_cannot_be_published(self, client):
        """A directory with no manifest is not a reading. Publishing one would
        put a half-written report on the desk.

        REGRESSION GUARD, not evidence: it exercises a function that only exists
        with the fix, so it cannot fail against the pre-fix code. It is here to
        keep the refusal from being removed later, not to demonstrate the gap.
        """
        project = _project(client)
        m = _manifest(project)
        os.makedirs(os.path.join(m.report_generations_dir, "not-a-generation"), exist_ok=True)
        with pytest.raises(ValueError, match="no complete reading"):
            report_generation.publish_generation(
                m, os.path.join(m.report_generations_dir, "not-a-generation"))

    def test_publication_refuses_when_the_draft_has_moved(self, client):
        """The compare half of compare-and-publish, driven directly: a staged
        reading of an older script must not become the live report."""
        project = _project(client)
        client.post(f"/api/projects/{project}/analyze", json={})
        m = _manifest(project)
        gen = client.get(f"/api/projects/{project}/report").get_json()["published"]["generation"]

        client.post(f"/api/projects/{project}/edits/apply",
                    json={"scene_number": 1, "replacements": [EDITED_LINE]})
        with pytest.raises(ValueError, match="draft changed"):
            report_generation.publish_generation(
                m, os.path.join(m.report_generations_dir, gen))


class TestAReadingBelongsToItsDraft:
    BETA = b"""Title: Truth Test Beta

INT. VAULT - NIGHT

BETA STRANGER waits in the dark.
"""

    def test_switching_drafts_keeps_each_reading(self, client):
        """The provenance files are per-draft state (gap 63's bundle): switching
        back must restore the reading that belongs to that draft's text."""
        project = _project(client)
        assert client.post(f"/api/projects/{project}/analyze", json={}).status_code == 200
        client.post(f"/api/projects/{project}/drafts",
                    data={"file": (io.BytesIO(self.BETA), "beta.fountain")},
                    content_type="multipart/form-data")
        assert client.post(f"/api/projects/{project}/analyze", json={}).status_code == 200
        assert client.get(f"/api/projects/{project}/report").get_json()["snapshot"]["title"] \
            == "Truth Test Beta"

        client.post(f"/api/projects/{project}/drafts/activate", json={"name": "original"})
        back = client.get(f"/api/projects/{project}/report")
        assert back.status_code == 200, "the first draft's reading was lost on the way back"
        assert back.get_json()["snapshot"]["title"] == "Truth Test"

        client.post(f"/api/projects/{project}/drafts/activate", json={"name": "draft-1"})
        again = client.get(f"/api/projects/{project}/report")
        assert again.get_json()["snapshot"]["title"] == "Truth Test Beta"

    def test_a_reparse_hides_the_old_reading_rather_than_showing_it(self, client):
        """The pre-existing rule this change had to preserve: after a re-parse the
        previous reading describes text that may no longer exist, so the route
        must refuse it — a stale report shown as current is the same lie as a
        stale analysis."""
        project = _project(client)
        assert client.post(f"/api/projects/{project}/analyze", json={}).status_code == 200
        assert client.get(f"/api/projects/{project}/report").status_code == 200
        client.post(f"/api/projects/{project}/reparse")
        resp = client.get(f"/api/projects/{project}/report")
        assert resp.status_code == 400
        assert "hasn't completed" in resp.get_json()["error"].lower()
