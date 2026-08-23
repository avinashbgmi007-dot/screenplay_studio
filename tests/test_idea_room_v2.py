"""Idea-room v2 — /sameer anywhere on the page, fresh-context summon,
Sameer's probing posture, and idea deletion.

- The engine's idea context is the CURRENT page content (fresh every turn),
  per-idea isolated, with no writer-library bleed.
- The premise-branch system prompt forbids reciting the page and demands
  probing questions.
- Idea delete: backend removes the directory; unknown idea 404s; the API
  mirrors exactly what the shelf's new delete button calls.
- Demo model: idea-room replies PROBE (question mark, references a detail)
  instead of reciting the page back.
"""

import json
import os

import pytest

import screenplay_studio.webapp_server as webapp_server


@pytest.fixture
def client(tmp_path):
    webapp_server.PROJECTS_DIR = str(tmp_path / "shelf")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = "http://127.0.0.1:1"  # unused: demo model is in-process
    from screenplay_studio.demo_model import start_demo_server
    webapp_server.CONFIG["server_url"] = start_demo_server()
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


PAGE = (
    "Rain Courier\n\n"
    "A courier in Mumbai discovers her delivery bag swaps whatever is inside "
    "with an object from the recipient's greatest regret.\n"
    "She keeps one swapped item: a brass key nobody has claimed.\n"
    'Her rule: never open the bag after midnight. Tonight she breaks it.\n'
)


def _create_idea(client, content=None, title="New idea"):
    meta = client.post("/api/ideas", json={"title": title}).get_json()
    if content is not None:
        client.post(f"/api/ideas/{meta['id']}/content", json={"content": content})
    return meta["id"]


def test_idea_context_is_current_page_and_isolated(client):
    idea_a = _create_idea(client, PAGE)
    idea_b = _create_idea(client, "Completely different story about a lighthouse keeper.")

    sid_a = client.post(f"/api/ideas/{idea_a}/chat/start").get_json()["session_id"]
    resp = client.post(f"/api/ideas/{idea_a}/chat/sessions/{sid_a}/messages",
                       json={"text": "I just added the midnight rule — thoughts?"}).get_json()
    reply = resp["reply"]
    # Sameer read THIS idea's page (the key detail) ...
    assert "brass key" in reply or "midnight" in reply
    # ... and asks rather than recites
    assert "?" in reply

    # isolation: idea B's chat must not know A's material
    sid_b = client.post(f"/api/ideas/{idea_b}/chat/start").get_json()["session_id"]
    reply_b = client.post(f"/api/ideas/{idea_b}/chat/sessions/{sid_b}/messages",
                          json={"text": "where do we start?"}).get_json()["reply"]
    assert "brass key" not in reply_b and "courier" not in reply_b.lower()


def test_idea_prompt_forbids_recitation():
    from screenplay_cowriter.context import ScriptContext, ReportContext, build_system_prompt
    premise = {"title": "Rain Courier", "content": PAGE}
    sp = build_system_prompt(ScriptContext(None), ReportContext(None),
                             "writing_partner", "peer",
                             premise=premise)
    assert "never recite it back" in sp
    assert "probe" in sp.lower()


def test_demo_idea_reply_probes_instead_of_parroting():
    from screenplay_studio.demo_model import demo_app
    c = demo_app.test_client()
    system = (
        "You are Sameer, the writer's co-writing partner.\n"
        "GROUNDING - There is no script yet: the idea and the premise card are the "
        "only material.\n\n"
        "PREMISE (the shared card, keeps growing as you talk):\n\n"
        + PAGE +
        "\n\nIDEA GROUNDING - never pretend you've read pages."
    )
    out = c.post("/v1/chat/completions", json={
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": "thoughts on where this goes?"}]}).get_json()
    reply = out["choices"][0]["message"]["content"]
    assert "demo craft model" not in reply               # no robot tags
    assert "?" in reply                                   # he probes
    assert reply.count("Rain Courier") == 0               # never parrots the title
    # he engages a CONCRETE element from the page, not generic filler
    assert any(k in reply for k in ("brass key", "midnight", "courier", "swaps"))


class TestIdeaDeletion:
    def test_delete_removes_idea_and_sessions(self, client):
        idea = _create_idea(client, PAGE)
        client.post(f"/api/ideas/{idea}/chat/start")
        sessions_dir = webapp_server.IdeaStore(
            os.path.join(webapp_server.PROJECTS_DIR, "ideas")).sessions_dir(idea)
        assert os.path.exists(os.path.join(sessions_dir, ".."))

        assert client.delete(f"/api/ideas/{idea}").status_code == 200
        assert client.get(f"/api/ideas/{idea}").status_code == 404
        assert not os.path.exists(sessions_dir)

        # the shelf no longer lists it
        assert all(i["id"] != idea for i in client.get("/api/ideas").get_json())

    def test_delete_unknown_idea_is_404(self, client):
        assert client.delete("/api/ideas/nope123").status_code == 404

    def test_survivor_ideas_keep_their_chats(self, client):
        a = _create_idea(client, PAGE)
        b = _create_idea(client, "Another seed.")
        sid = client.post(f"/api/ideas/{a}/chat/start").get_json()["session_id"]

        assert client.delete(f"/api/ideas/{b}").status_code == 200

        # deleting B must not touch A's conversation
        data = client.get(f"/api/ideas/{a}/chat/sessions/{sid}").get_json()
        assert data["session_id"] == sid
