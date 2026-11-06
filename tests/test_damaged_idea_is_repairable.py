"""Gap 70 — a damaged idea was shown but could not be repaired.

Filed: after corrupting a synthetic idea file, `GET /api/ideas` still listed it
(flagged, by design), `GET /api/ideas/<id>` and `POST .../content` both answered
**400** with the raw `JSONDecodeError` text, and the file was left untouched. The
project side handles the same damage as 503 `unreadable`; the idea store raised
the parser error instead, so the writer saw "Expecting property name…" as if
their request were malformed — and there was no in-app way to recover the page.

The data was never lost. There was simply no door to it.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import screenplay_studio.webapp_server as ws

RAW = '{"title": "Half a file", "content": "my page"'      # truncated on purpose


@pytest.fixture
def desk(monkeypatch, tmp_path):
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(tmp_path))
    ideas = tmp_path / "ideas"
    ideas.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ws, "_ideas_dir", lambda: str(ideas))
    ws.app.config["TESTING"] = True
    client = ws.app.test_client()

    def _make(idea_id="brokenidea", raw=RAW):
        d = ideas / idea_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "idea.json").write_text(raw, encoding="utf-8")
        return d / "idea.json"

    return client, _make


# ---------- the filed reproduction ----------

def test_a_damaged_idea_is_not_a_bad_request(desk):
    """400 means 'your request was malformed'. The request was fine."""
    client, make = desk
    make()
    r = client.get("/api/ideas/brokenidea")
    assert r.status_code == 503, r.get_json()
    assert r.status_code != 400


def test_the_damage_is_named_as_damage(desk):
    client, make = desk
    make()
    body = client.get("/api/ideas/brokenidea").get_json()
    assert body["unreadable"] is True
    assert "damaged" in body["error"].lower()
    assert "not touched" in body["error"].lower()


def test_saving_over_a_damaged_idea_is_refused_the_same_way(desk):
    """Every mutator loads first, so the save must refuse too — otherwise it
    finalises the loss over a file that could still be recovered by hand."""
    client, make = desk
    path = make()
    r = client.post("/api/ideas/brokenidea/content", json={"content": "new"})
    assert r.status_code == 503, r.get_json()
    assert path.read_text(encoding="utf-8") == RAW, "the file must be untouched"


def test_a_damaged_idea_still_appears_on_the_shelf(desk):
    """Flag, don't drop — that part was already right and must survive."""
    client, make = desk
    make()
    r = client.get("/api/ideas")
    assert r.status_code == 200
    assert any(i.get("unreadable") for i in r.get_json())


# ---------- the door: export the raw text ----------

def test_the_raw_file_can_be_read_out(desk):
    client, make = desk
    make()
    r = client.get("/api/ideas/brokenidea/recover")
    assert r.status_code == 200
    body = r.get_json()
    assert body["raw"] == RAW, "recovery needs the bytes, not a parsed view"
    assert body["readable"] is False


def test_recovery_does_not_modify_the_file(desk):
    client, make = desk
    path = make()
    client.get("/api/ideas/brokenidea/recover")
    assert path.read_text(encoding="utf-8") == RAW


def test_recovery_works_for_a_healthy_idea_too(desk):
    client, make = desk
    make("fineidea", json.dumps({"title": "Fine", "content": "ok"}))
    r = client.get("/api/ideas/fineidea/recover")
    assert r.status_code == 200
    assert r.get_json()["readable"] is True


def test_recovery_of_a_missing_idea_is_404(desk):
    client, _ = desk
    assert client.get("/api/ideas/nosuchidea/recover").status_code == 404


# ---------- the repair ----------

def test_a_damaged_idea_can_be_repaired(desk):
    client, make = desk
    make()
    good = json.dumps({"title": "Half a file (recovered)", "content": "my page"})
    r = client.post("/api/ideas/brokenidea/repair", json={"text": good})
    assert r.status_code == 200, r.get_json()
    assert client.get("/api/ideas/brokenidea").get_json()["title"] == \
        "Half a file (recovered)"


def test_repair_keeps_the_damaged_original(desk):
    """A repair must never be the act that destroys the evidence."""
    client, make = desk
    d = make().parent
    good = json.dumps({"title": "Recovered", "content": ""})
    client.post("/api/ideas/brokenidea/repair", json={"text": good})
    kept = [f for f in os.listdir(d) if ".damaged-" in f]
    assert kept, f"nothing was kept; dir={os.listdir(d)}"
    assert (d / kept[0]).read_text(encoding="utf-8") == RAW


def test_repair_with_invalid_json_is_refused(desk):
    client, make = desk
    path = make()
    r = client.post("/api/ideas/brokenidea/repair", json={"text": '{"title": "x"'})
    assert r.status_code == 400
    assert "not valid JSON" in r.get_json()["error"]
    assert path.read_text(encoding="utf-8") == RAW


def test_repair_of_a_readable_idea_is_refused(desk):
    """Otherwise 'repair' becomes a silent bypass of every merge rule."""
    client, make = desk
    make("fineidea", json.dumps({"title": "Fine", "content": "ok"}))
    r = client.post("/api/ideas/fineidea/repair", json={"text": '{"title": "HIJACKED"}'})
    assert r.status_code == 400
    assert client.get("/api/ideas/fineidea").get_json()["title"] == "Fine"


def test_repair_refuses_a_non_object(desk):
    client, make = desk
    make()
    r = client.post("/api/ideas/brokenidea/repair", json={"text": "[1, 2, 3]"})
    assert r.status_code == 400
    assert "JSON object" in r.get_json()["error"]


def test_the_desk_works_again_after_a_repair(desk):
    """The point of a repair is that the page is usable, not merely parseable."""
    client, make = desk
    make()
    good = json.dumps({"title": "Recovered", "content": "my page"})
    client.post("/api/ideas/brokenidea/repair", json={"text": good})
    r = client.post("/api/ideas/brokenidea/content", json={"content": "edited now"})
    assert r.status_code == 200, r.get_json()


# ---------- missing is still missing, not damage ----------

def test_a_missing_idea_is_404_not_503(desk):
    client, _ = desk
    assert client.get("/api/ideas/nosuchidea").status_code == 404
    assert client.post("/api/ideas/nosuchidea/content",
                       json={"content": "x"}).status_code == 404


def test_a_wrong_shape_file_is_damage_not_a_crash(desk):
    """A dict store handed a list is as damaged as a torn file."""
    client, make = desk
    make("listidea", '["not", "an", "object"]')
    r = client.get("/api/ideas/listidea")
    assert r.status_code == 503, r.get_json()
    assert r.get_json()["unreadable"] is True
