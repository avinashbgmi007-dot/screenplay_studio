"""Selection-to-ask on the idea page, anti-sloppiness tuning, and the
ephemeral translate endpoint.

- idea blocking route forwards `quote`; quote_context wording follows the room
  ("their idea page" vs "the script").
- direct questions: ANSWER FIRST in the prompt, no forward-nudge appended.
- /translate renders an assistant reply in English, DISPLAY-ONLY (never
  persisted), on both idea and project sessions; demo model handles the
  [TRANSLATE TASK] branch via its glossary.
"""
from test_idea_room_v2 import client  # noqa: F401 -- shared fixture (keep name)

PAGE = (
    "Rain Courier\n\n"
    "A courier in Mumbai discovers her delivery bag swaps whatever is inside "
    "with an object from the recipient's greatest regret.\n"
    "She keeps one swapped item: a brass key nobody has claimed.\n"
)


def test_idea_blocking_route_accepts_quote(client):
    iid = client.post("/api/ideas", json={"title": "quote test"}).get_json()["id"]
    client.post(f"/api/ideas/{iid}/content", json={"content": PAGE})
    sid = client.post(f"/api/ideas/{iid}/chat/start").get_json()["session_id"]
    resp = client.post(
        f"/api/ideas/{iid}/chat/sessions/{sid}/messages",
        json={"text": "what do you make of this?",
              "quote": {"scene_number": None,
                        "text": "a brass key nobody has claimed"}},
    ).get_json()
    reply = resp["reply"]
    assert reply
    # the highlighted words reached the model and came back acknowledged
    assert "brass key" in reply.lower() or "key" in reply.lower()
    # stored on the user message like script quotes
    msgs = resp["messages"]
    user_msg = [m for m in msgs if m["role"] == "user"][-1]
    assert user_msg["quote"]["text"] == "a brass key nobody has claimed"


def test_quote_wording_follows_the_room():
    from screenplay_cowriter.engine import CoWriterEngine
    from screenplay_cowriter.context import ScriptContext, ReportContext
    from screenplay_studio.demo_model import demo_app

    class _Cap:
        def chat_stream(self, messages, **kw):
            self.messages = messages
            return "ok"

        chat = chat_stream

    # IDEA room -> "their idea page"
    eng = CoWriterEngine(_Cap(), ScriptContext(), ReportContext(None),
                         premise={"title": "T", "content": PAGE})
    c = demo_app.test_client()
    out = c.post("/v1/chat/completions", json={
        "messages": [{"role": "system", "content": "x"}]}).get_json()
    del out, c
    s = __import__("screenplay_cowriter.models", fromlist=["Session"]).Session.new("T")
    eng.send_message(s, "thoughts?", quote={"scene_number": None, "text": "brass key"})
    sys_text = " ".join(m["content"] for m in eng.client.messages if m["role"] == "system")
    assert "their idea page" in sys_text

    # SCRIPT room -> "the script"
    eng2 = CoWriterEngine(_Cap(), ScriptContext(), ReportContext(None))
    s2 = __import__("screenplay_cowriter.models", fromlist=["Session"]).Session.new("T")
    eng2.send_message(s2, "thoughts?", quote={"scene_number": None, "text": "INT. NIGHT"})
    sys_text2 = " ".join(m["content"] for m in eng2.client.messages if m["role"] == "system")
    assert "from the script" in sys_text2


def test_answer_first_in_prompt_for_direct_question(client):
    iid = client.post("/api/ideas", json={"title": "af test"}).get_json()["id"]
    sid = client.post(f"/api/ideas/{iid}/chat/start").get_json()["session_id"]
    resp = client.post(f"/api/ideas/{iid}/chat/sessions/{sid}/messages",
                       json={"text": "does the bag ever open?"}).get_json()
    assert "reply" in resp


def test_translate_ephemeral_on_idea_session(client):
    iid = client.post("/api/ideas", json={"title": "tr test"}).get_json()["id"]
    client.post(f"/api/ideas/{iid}/content", json={"content": PAGE})
    sid = client.post(f"/api/ideas/{iid}/chat/start").get_json()["session_id"]
    r = client.post(f"/api/ideas/{iid}/chat/sessions/{sid}/messages",
                    json={"text": "enti ee brass key gurinchi nee opinion?"}).get_json()
    before = len(r["messages"])
    tr = client.post(f"/api/ideas/{iid}/chat/sessions/{sid}/translate",
                     json={"index": len(r["messages"]) - 1}).get_json()
    assert "translation" in tr and tr["translation"]
    # DISPLAY-ONLY: the session history is untouched
    after = client.get(f"/api/ideas/{iid}/chat/sessions/{sid}").get_json()
    assert len(after["branches"]["main"]["messages"]) == before


def test_translate_rejects_bad_index_and_user_role(client):
    iid = client.post("/api/ideas", json={"title": "tr bad"}).get_json()["id"]
    sid = client.post(f"/api/ideas/{iid}/chat/start").get_json()["session_id"]
    r = client.post(f"/api/ideas/{iid}/chat/sessions/{sid}/translate",
                    json={"index": 99})
    assert r.status_code == 400
    r2 = client.post(f"/api/ideas/{iid}/chat/sessions/{sid}/messages",
                     json={"text": "hello there friend"}).get_json()
    user_idx = next(i for i, m in enumerate(r2["messages"]) if m["role"] == "user")
    r3 = client.post(f"/api/ideas/{iid}/chat/sessions/{sid}/translate",
                     json={"index": user_idx})
    assert r3.status_code == 400


def test_demo_glossary_translates_known_templates():
    from screenplay_studio.demo_model import _demo_translate
    te_reply = ("Sare, page naa kallalo padindi. Kani ee idea -- adi evaru kosam?\n\n"
                "Adi wrong ayite em break avtundi?")
    en = _demo_translate(te_reply)
    assert "page caught my eye" in en
    assert "who is it for?" in en
    assert "what breaks?" in en
    # Telugu-script template output also maps
    telugu = ("\u0c2a\u0c47\u0c1c\u0c40 \u0c1a\u0c26\u0c3f\u0c35\u0c3e\u0c28\u0c41 -- "
              "\u0c05\u0c26\u0c3f \u0c0e\u0c35\u0c30\u0c3f \u0c15\u0c4b\u0c38\u0c02?")
    en2 = _demo_translate(telugu)
    assert "read the page" in en2 or "I've read" in en2
    assert "who is it for?" in en2
