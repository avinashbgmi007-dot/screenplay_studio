"""Tests for the idea room — scriptless story development.

Covers the IdeaStore (premise card + carry-into-project), the idea-mode
system prompt (premise framing + no-pages grounding), and the webapp API
lifecycle: create idea -> card -> chat (lens swap) -> delete, and
graduation (upload pages -> project carries the card and the conversation).
"""

import io
import json
import os

import pytest

import screenplay_studio.webapp_server as webapp_server
from screenplay_studio.ideas import IdeaStore
from screenplay_studio.manifest import ProjectManifest
from screenplay_cowriter.context import (
    build_system_prompt, ScriptContext, ReportContext, IDEA_GROUNDING_INSTRUCTION,
)


@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


SAMPLE_SCRIPT = b"""Title: Embers
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


def _upload_project(http_client):
    r = http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "t.fountain"), "title": "T"},
        content_type="multipart/form-data",
    )
    return r.get_json()["project"]


class TestIdeaStore:
    def test_create_list_save_card(self, tmp_path):
        store = IdeaStore(str(tmp_path / "ideas"))
        meta = store.create(title="Embers")
        assert meta["id"]
        assert meta["card"] == {"title": "", "logline": "", "premise": "", "questions": []}

        store.save_card(meta["id"], {
            "title": "Embers", "logline": "A firefighter inherits his brother's crew.",
            "questions": ["Is it a movie?"],
        })
        loaded = store.load(meta["id"])
        assert loaded["title"] == "Embers"  # shelf title follows the card
        assert loaded["card"]["logline"].startswith("A firefighter")
        assert loaded["card"]["questions"] == ["Is it a movie?"]

        # a partial save never wipes fields the client didn't send
        store.save_card(meta["id"], {"premise": "He takes over the job and the grief."})
        again = store.load(meta["id"])
        assert again["card"]["logline"]
        assert again["card"]["premise"]
        assert [m["id"] for m in store.list()] == [meta["id"]]

    def test_delete(self, tmp_path):
        store = IdeaStore(str(tmp_path / "ideas"))
        meta = store.create()
        store.delete(meta["id"])
        assert store.list() == []

    def test_carry_into_project(self, tmp_path):
        store = IdeaStore(str(tmp_path / "ideas"))
        meta = store.create(title="Embers")
        store.save_card(meta["id"], {"title": "Embers", "logline": "L"})
        session_dir = store.sessions_dir(meta["id"])
        with open(os.path.join(session_dir, "abc123.json"), "w", encoding="utf-8") as f:
            json.dump({"session_id": "abc123"}, f)

        project_dir = tmp_path / "proj"
        os.makedirs(project_dir, exist_ok=True)
        store.carry_into_project(meta["id"], str(project_dir))
        assert os.path.exists(os.path.join(project_dir, "premise.json"))
        assert os.path.exists(os.path.join(project_dir, "sessions", "abc123.json"))


class TestIdeaPrompt:
    def test_premise_framing(self):
        prompt = build_system_prompt(
            ScriptContext(None), ReportContext(None), "premise_doctor", "concept_validation",
            premise={"title": "Embers", "logline": "L", "premise": "P", "questions": ["Is it a movie?"]},
        )
        assert "no pages yet" in prompt
        assert "PREMISE (the shared card" in prompt
        assert "Working title: Embers" in prompt
        assert "Logline: L" in prompt
        assert "Open questions: Is it a movie?" in prompt
        assert IDEA_GROUNDING_INSTRUCTION in prompt
        assert "standing analysis report" not in prompt
        assert "SCRIPT MAP" not in prompt

    def test_script_prompt_unchanged_without_premise(self):
        prompt = build_system_prompt(
            ScriptContext({"title": "T"}), ReportContext(None), "writing_partner", "peer"
        )
        assert "standing analysis report" in prompt
        assert IDEA_GROUNDING_INSTRUCTION not in prompt

    def test_idea_persona_and_mode_exist(self):
        from screenplay_cowriter.personas import PERSONAS, MODES
        assert "premise_doctor" in PERSONAS
        assert "concept_validation" in MODES


class TestIdeaApi:
    def _create(self, http_client):
        r = http_client.post("/api/ideas", json={"title": "Embers"})
        assert r.status_code == 201
        return r.get_json()["id"]

    def test_lifecycle(self, http_client):
        idea_id = self._create(http_client)
        assert http_client.get("/api/ideas").get_json()[0]["id"] == idea_id

        r = http_client.post(f"/api/ideas/{idea_id}/card", json={
            "card": {"title": "Embers", "logline": "L", "questions": ["Is it a movie?"]},
        })
        assert r.status_code == 200
        meta = http_client.get(f"/api/ideas/{idea_id}").get_json()
        assert meta["card"]["logline"] == "L"
        assert meta["title"] == "Embers"

        s = http_client.post(f"/api/ideas/{idea_id}/chat/start").get_json()["session_id"]
        r = http_client.post(f"/api/ideas/{idea_id}/chat/sessions/{s}/settings",
                             json={"persona": "premise_doctor", "mode": "concept_validation"})
        assert r.status_code == 200
        assert r.get_json() == {"active_persona": "premise_doctor", "active_mode": "concept_validation"}

        # the scriptless engine answers through the mock model server
        r = http_client.post(f"/api/ideas/{idea_id}/chat/sessions/{s}/messages",
                             json={"text": "What do you think of the hook?"})
        assert r.status_code == 200
        assert r.get_json()["reply"]

        # the idea conversation serves with its lens
        sess = http_client.get(f"/api/ideas/{idea_id}/chat/sessions/{s}").get_json()
        assert sess["branches"]["main"]["active_persona"] == "premise_doctor"

        assert http_client.delete(f"/api/ideas/{idea_id}").status_code == 200
        assert http_client.get("/api/ideas").get_json() == []

    def test_unknown_idea_404s(self, http_client):
        assert http_client.get("/api/ideas/nope").status_code == 404
        assert http_client.post("/api/ideas/nope/card", json={"card": {}}).status_code == 404

    def test_graduate_idea(self, http_client):
        """Upload the first pages: a real project appears carrying the premise
        card and the idea conversation (pinned as the project's session)."""
        idea_id = self._create(http_client)
        http_client.post(f"/api/ideas/{idea_id}/card", json={
            "card": {"title": "Embers", "logline": "L", "premise": "P"},
        })
        s = http_client.post(f"/api/ideas/{idea_id}/chat/start").get_json()["session_id"]
        http_client.post(f"/api/ideas/{idea_id}/chat/sessions/{s}/messages",
                         json={"text": "testing the thread"})

        r = http_client.post(
            f"/api/ideas/{idea_id}/graduate",
            data={"file": (io.BytesIO(SAMPLE_SCRIPT), "embers.fountain"), "title": "Embers"},
            content_type="multipart/form-data",
        )
        assert r.status_code == 201
        project = r.get_json()["project"]

        m = ProjectManifest.load(webapp_server._project_dir(project))
        assert m.cowriter_session_id == s  # the thread continues on the script desk
        with open(os.path.join(m.project_dir, "premise.json"), encoding="utf-8") as f:
            card = json.load(f)
        assert card["logline"] == "L"

        # get_project surfaces the carried premise
        gp = http_client.get(f"/api/projects/{project}").get_json()
        assert gp["premise"]["premise"] == "P"

    def test_save_project_premise(self, http_client):
        project = _upload_project(http_client)
        r = http_client.post(f"/api/projects/{project}/premise", json={
            "card": {"title": "T", "logline": "L"},
        })
        assert r.status_code == 200
        gp = http_client.get(f"/api/projects/{project}").get_json()
        assert gp["premise"]["title"] == "T"
