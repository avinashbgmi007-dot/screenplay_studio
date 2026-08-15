"""
Report-language support: the analysis report (findings + coverage) can be
produced in English (default), Tenglish (Telugu in the Latin alphabet), Hindi
(Devanagari), or Tamil — the languages the writer's scripts are in.

Covers three layers:
  1. prompts: the language instruction is appended to every category prompt,
     and English adds nothing (so default behavior is byte-identical).
  2. pipeline: report_language flows into every model call.
  3. webapp API: analyze accepts report_language and the manifest remembers it.
"""

import io
import os

import pytest

from screenplay_analyzer import prompts
from screenplay_analyzer.pipeline import build_scene_summaries, run_coverage
from screenplay_parser.models import ScriptDocument, Element, ElementType, Scene
from screenplay_parser import parse_fountain


# ---------------------------------------------------------------------------
# prompts layer
# ---------------------------------------------------------------------------

def test_english_adds_nothing():
    assert prompts.language_instruction("eng") == ""
    # a category prompt in English is byte-identical to the pre-language version
    system, _ = prompts.coverage_prompt("overview", "Title", "Author", language="eng")
    assert "Tenglish" not in system


@pytest.mark.parametrize("lang,fragment", [
    ("tenglish", "Tenglish"),
    ("hindi", "Devanagari"),
    ("tamil", "Tamil script"),
])
def test_language_instruction_present(lang, fragment):
    assert fragment in prompts.language_instruction(lang)


def test_dialogue_prompt_carries_language():
    system, _ = prompts.dialogue_analysis_prompt([], language="tenglish")
    assert "Tenglish" in system
    # quotes must stay verbatim so the verifier can still check them
    assert "evidence_quote" in system


def test_coverage_prompt_carries_language():
    system, _ = prompts.coverage_prompt("overview", "T", "A", language="hindi")
    assert "Devanagari" in system


def test_all_categories_accept_language():
    """Every prompt builder accepts the language kwarg without error."""
    overview = "Scene 1 [INT. HOUSE - DAY] (A): A enters."
    args = {
        prompts.scene_summary_prompt: ([{"scene_number": 1, "heading_raw": "INT. X - DAY", "characters_present": ["A"], "full_text": "text"}],),
        prompts.dialogue_analysis_prompt: ([],),
        prompts.theme_analysis_prompt: (overview, "T"),
        prompts.character_analysis_prompt: (overview, "T", ["A"]),
        prompts.structure_analysis_prompt: (overview, "T", 1, 5),
        prompts.scene_function_prompt: (overview, "T"),
        prompts.genre_check_prompt: ("drama", ["x"], overview),
        prompts.coverage_prompt: (overview, "T", "A"),
        prompts.logline_test_prompt: ("A logline.", overview, "T"),
        prompts.character_reads_prompt: (overview, "T", ["A"]),
    }
    for fn, a in args.items():
        system, user = fn(*a, language="tenglish")
        assert isinstance(system, str) and isinstance(user, str)
        assert "Tenglish" in system


# ---------------------------------------------------------------------------
# pipeline layer — the language reaches the actual model call
# ---------------------------------------------------------------------------

class RecordingClient:
    """Minimal stand-in for LlamaServerClient that records every system prompt."""

    def __init__(self, responses):
        self.responses = responses
        self.system_prompts = []

    def chat_json(self, system, user, grammar=None, max_tokens=None, **kw):
        self.system_prompts.append(system)
        return self.responses.pop(0)

    def resolve_model(self):
        return "test-model"


def _mini_doc():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "pain_tenglish.fountain")
    return parse_fountain(path)


def test_summaries_sent_in_report_language():
    doc = _mini_doc()
    # the fixture's 6 scenes now chunk into 2 calls under the tighter budget
    first = {"summaries": [{"scene_number": n, "summary": "s"} for n in (1, 2, 3)]}
    second = {"summaries": [{"scene_number": n, "summary": "s"} for n in (4, 5, 6)]}
    client = RecordingClient([first, second])
    summaries, errors = build_scene_summaries(doc, client, chunk_size=6, language="tenglish")
    assert not errors
    assert set(summaries) == {1, 2, 3, 4, 5, 6}
    assert any("Tenglish" in s for s in client.system_prompts)


def test_coverage_sent_in_report_language():
    doc = _mini_doc()
    client = RecordingClient([{"logline": "l", "genre": "drama", "synopsis": "s", "strengths": [], "weaknesses": [], "recommendation": "consider"}])
    result = run_coverage(doc, "overview", client, language="hindi")
    assert result["genre"] == "drama"
    assert any("Devanagari" in s for s in client.system_prompts)


# ---------------------------------------------------------------------------
# webapp API layer
# ---------------------------------------------------------------------------

SAMPLE_SCRIPT = b"""Title: Language Test
Author: Test

INT. STUDY - NIGHT

MARA takes out an old REVOLVER, setting it on the desk.

MARA
I'll tell you everything when this is over.
"""


@pytest.fixture
def http_client(tmp_path, mock_server):
    import screenplay_studio.webapp_server as webapp_server
    webapp_server.PROJECTS_DIR = str(tmp_path / "lang_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _upload(http_client):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"), "title": "Lang Test"},
        content_type="multipart/form-data",
    )


def test_analyze_accepts_report_language(http_client):
    project = _upload(http_client).get_json()["project"]
    resp = http_client.post(f"/api/projects/{project}/analyze", json={"report_language": "tenglish"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["stages"]["analyze"] == "complete"
    assert data["report_language"] == "tenglish"


def test_report_language_defaults_to_english(http_client):
    project = _upload(http_client).get_json()["project"]
    resp = http_client.get(f"/api/projects/{project}")
    assert resp.get_json()["report_language"] == "eng"


def test_report_language_persists_on_reanalyze(http_client):
    project = _upload(http_client).get_json()["project"]
    http_client.post(f"/api/projects/{project}/analyze", json={"report_language": "hindi"})
    # re-run with no language given — the stored one wins
    resp = http_client.post(f"/api/projects/{project}/analyze", json={"force": True})
    assert resp.get_json()["report_language"] == "hindi"


def test_report_language_in_project_summary(http_client):
    project = _upload(http_client).get_json()["project"]
    http_client.post(f"/api/projects/{project}/analyze", json={"report_language": "tamil"})
    listing = http_client.get("/api/projects").get_json()
    assert listing[0]["report_language"] == "tamil"
