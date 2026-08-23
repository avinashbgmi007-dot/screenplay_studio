"""Idea Room v3 — session resume, page-diff awareness, and the context card.

- chat/start RESUMES the idea's most recent session (reload no longer orphans
  the conversation); messages survive across starts.
- Each successful turn persists last_seen_content; the NEXT turn's prompt
  carries a deterministic PAGE UPDATE diff (added/removed lines).
- Failed turns keep the old baseline so a retry re-reports the same changes.
- The demo model reacts to the ADDED material by name (update-aware Sameer).
"""
import json

from test_idea_room_v2 import client  # noqa: F401 -- shared fixture

from screenplay_studio.webapp_server import app, _page_update_note


def _client():
    app.config["TESTING"] = True
    return app.test_client()


def _idea(client, content=None, title="Diff test idea"):
    meta = client.post("/api/ideas", json={"title": title}).get_json()
    if content is not None:
        client.post(f"/api/ideas/{meta['id']}/content", json={"content": content})
    return meta["id"]


PAGE_A = (
    "Rain Courier\n\n"
    "A courier in Mumbai discovers her delivery bag swaps whatever is inside "
    "with an object from the recipient's greatest regret.\n"
    "She keeps one swapped item: a brass key nobody has claimed.\n"
)


def test_start_resumes_latest_session(client):
    iid = _idea(client, PAGE_A)
    s1 = client.post(f"/api/ideas/{iid}/chat/start").get_json()["session_id"]
    # a turn, so the session has history worth resuming
    r = client.post(f"/api/ideas/{iid}/chat/sessions/{s1}/messages",
                    json={"text": "thoughts on the bag?"}).get_json()
    assert "reply" in r and r["reply"]
    # simulate a reload: start again -- must RESUME, not orphan
    s2 = client.post(f"/api/ideas/{iid}/chat/start").get_json()["session_id"]
    assert s1 == s2
    sess = client.get(f"/api/ideas/{iid}/chat/sessions/{s2}").get_json()
    msgs = sess["branches"]["main"]["messages"]
    assert len(msgs) >= 2  # user turn + reply survived the restart


def test_page_update_note_diffs_lines():
    base = "line one\nline two\nline three"
    new = "line one\nline two rewritten\nline three\nline four"
    note = _page_update_note(base, new)
    assert "ADDED" in note and "line four" in note
    assert "REMOVED" in note and "line two" in note
    # nothing changed -> empty note; no baseline -> empty note
    assert _page_update_note(new, new) == ""
    assert _page_update_note(None, new) == ""


def test_turn_persists_baseline_and_next_turn_gets_diff(client):
    iid = _idea(client, PAGE_A)
    sid = client.post(f"/api/ideas/{iid}/chat/start").get_json()["session_id"]
    client.post(f"/api/ideas/{iid}/chat/sessions/{sid}/messages",
                json={"text": "where do we start?"}).get_json()
    sess = client.get(f"/api/ideas/{iid}/chat/sessions/{sid}").get_json()
    assert sess.get("last_seen_content") == PAGE_A

    # writer adds two lines after the discussion
    updated = PAGE_A + "Her rule: never open the bag after midnight. Tonight she breaks it.\n"
    client.post(f"/api/ideas/{iid}/content", json={"content": updated})

    # next turn: the demo model must NOTICE the added line by quoting it
    resp = client.post(f"/api/ideas/{iid}/chat/sessions/{sid}/messages",
                       json={"text": "ok I'm back — anything new to you?"}).get_json()
    reply = resp["reply"]
    assert "never open the bag after midnight" in reply
    # baseline moved forward
    sess = client.get(f"/api/ideas/{iid}/chat/sessions/{sid}").get_json()
    assert sess.get("last_seen_content") == updated


def test_prompt_carries_update_block():
    from screenplay_cowriter.context import ScriptContext, ReportContext, build_system_prompt
    premise = {"title": "T", "content": PAGE_A,
               "page_update": 'ADDED since your last read:\n  - "a brass key nobody has claimed"'}
    sp = build_system_prompt(ScriptContext(None), ReportContext(None),
                             "writing_partner", "peer", premise=premise)
    assert "PAGE UPDATE" in sp and "brass key" in sp
    # without an update there is no block
    sp2 = build_system_prompt(ScriptContext(None), ReportContext(None),
                              "writing_partner", "peer",
                              premise={"title": "T", "content": PAGE_A})
    assert "PAGE UPDATE" not in sp2


def test_demo_reacts_to_added_line_not_generic_probe():
    from screenplay_studio.demo_model import demo_app
    c = demo_app.test_client()
    system = (
        "You are Sameer, the writer's co-writing partner.\n"
        "GROUNDING - There is no script yet.\n\n"
        "PREMISE (the shared card):\n\nRain Courier\nnotes here\n\n"
        "PAGE UPDATE - deterministic diff:\nADDED since your last read:\n"
        '  - "Her rule: never open the bag after midnight"\n\n'
        "IDEA GROUNDING - never pretend you've read pages."
    )
    out = c.post("/v1/chat/completions", json={
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": "I'm back"}]}).get_json()
    reply = out["choices"][0]["message"]["content"]
    assert "never open the bag after midnight" in reply
    assert "?" in reply  # still conversational, still probes
