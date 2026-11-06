"""Gap 82 — one damage vocabulary for every shelf.

Filed defect: `GET /api/projects` flagged a damaged project with `{project, title,
unreadable, stages, sessions}` while `GET /api/ideas` flagged a damaged idea with
`{id, title, unreadable, created_at, updated_at}`. Measured: the two rows shared
exactly **two** keys — `title` and `unreadable` — and neither carried
`recoverable`, `detail` or `last_known`.

It was filed as low severity ("a prerequisite for gap 80's fix"). That framing was
wrong in an instructive way: gap 80 had already shipped a recovery panel, and the
panel could not answer for an idea at all — because it had no shared fields to read
and the idea shelf's own `recover`/`repair` routes (built in gap 70) were never
wired into the client. So an idea damaged on disk still showed a card that refused
every click. The inconsistency was not cosmetic; it was the reason half the
recovery surface did not exist.

These tests hold the contract: any shelf that reports damage reports the same
seven keys, with the same meanings, and the same recovery panel can drive it.
"""

import json
import os

import pytest

import screenplay_studio.ideas as ideas_mod
import screenplay_studio.webapp_server as ws
from screenplay_parser import parse_screenplay
from screenplay_studio.jsonio import DAMAGE_ENVELOPE_KEYS, damage_envelope, last_known_facts
from screenplay_studio.manifest import ProjectManifest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "pain_tenglish.fountain")


@pytest.fixture
def damaged_desk(tmp_path, monkeypatch):
    """One project and one idea, both damaged the same way."""
    projects = tmp_path / "root"
    projects.mkdir()
    ideas = tmp_path / "ideas"
    ideas.mkdir()

    src = tmp_path / "kept.fountain"
    src.write_bytes(open(FIXTURE, "rb").read())
    m = ProjectManifest.create(str(projects / "p1"), str(src), title="p1")
    parse_screenplay(str(m.source_path)).save(m.parsed_path)
    m.mark_complete("parse", {"parsed": m.parsed_path})
    with open(m.manifest_path, "w", encoding="utf-8") as f:
        f.write('{"title": "p1", "source_file')

    store = ideas_mod.IdeaStore(str(ideas))
    meta = store.create(title="My Idea")
    with open(os.path.join(store._dir(meta["id"]), "idea.json"), "w", encoding="utf-8") as f:
        f.write('{"id": "x", "tit')

    monkeypatch.setattr(ws, "PROJECTS_DIR", str(projects))
    monkeypatch.setattr(ws, "_ideas_dir", lambda: str(ideas))
    ws.app.config["TESTING"] = True
    return ws.app.test_client(), m, meta, projects, ideas


def _damaged(client, shelf):
    return [r for r in client.get(f"/api/{shelf}").get_json() if r.get("unreadable")][0]


# ---------- the envelope itself ----------

def test_the_envelope_has_exactly_the_documented_keys():
    env = damage_envelope("idea", "abc", detail="boom")
    for key in DAMAGE_ENVELOPE_KEYS:
        assert key in env, f"envelope lost {key}"
    assert env["unreadable"] is True
    assert env["id"] == "abc"
    assert env["detail"] == "boom"


def test_a_damaged_thing_is_never_blank_on_the_shelf():
    """An empty title renders an unclickable looking card. The identifier is a
    poor title but an honest one."""
    env = damage_envelope("project", "p9")
    assert env["title"] == "p9"


def test_recoverable_is_a_claim_not_a_mood():
    assert damage_envelope("idea", "a", recoverable=False)["recoverable"] is False
    assert damage_envelope("idea", "a")["recoverable"] is True


def test_last_known_facts_survive_a_missing_file(tmp_path):
    facts = last_known_facts(str(tmp_path / "gone.json"))
    assert facts["file"] == "gone.json"
    assert facts["size"] is None, "a missing file has no size — do not invent 0"


def test_last_known_facts_report_real_numbers(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("hello", encoding="utf-8")
    facts = last_known_facts(str(p))
    assert facts["size"] == 5
    assert facts["modified"] > 0


def test_shelf_specific_fields_ride_alongside_the_envelope():
    """A union, not a replacement: the project card keeps `stages` because the
    desk renders it, it just no longer *is* the damage description."""
    env = damage_envelope("project", "p1", stages={"parse": {}})
    assert env["stages"] == {"parse": {}}
    assert env["unreadable"] is True


# ---------- both shelves agree ----------

def test_the_two_shelves_share_the_whole_envelope(damaged_desk):
    client, *_ = damaged_desk
    proj = _damaged(client, "projects")
    idea = _damaged(client, "ideas")
    missing_proj = [k for k in DAMAGE_ENVELOPE_KEYS if k not in proj]
    missing_idea = [k for k in DAMAGE_ENVELOPE_KEYS if k not in idea]
    assert not missing_proj, f"project shelf is missing {missing_proj}"
    assert not missing_idea, f"idea shelf is missing {missing_idea}"


def test_each_shelf_names_its_own_kind(damaged_desk):
    client, *_ = damaged_desk
    assert _damaged(client, "projects")["kind"] == "project"
    assert _damaged(client, "ideas")["kind"] == "idea"


def test_both_shelves_explain_the_failure_in_words(damaged_desk):
    """`detail` is the parser's own sentence, kept verbatim so the writer and any
    support tool read the same reason."""
    client, *_ = damaged_desk
    for shelf in ("projects", "ideas"):
        detail = _damaged(client, shelf)["detail"]
        assert detail and "invalid JSON" in detail, f"{shelf} lost the reason"


def test_both_shelves_say_what_the_file_last_looked_like(damaged_desk):
    client, *_ = damaged_desk
    for shelf in ("projects", "ideas"):
        facts = _damaged(client, shelf)["last_known"]
        assert facts["file"] in ("project.json", "idea.json")
        assert facts["size"] and facts["size"] > 0
        assert facts["modified"] > 0


def test_both_shelves_claim_recoverable_only_when_recovery_exists(damaged_desk):
    client, *_ = damaged_desk
    for shelf in ("projects", "ideas"):
        row = _damaged(client, shelf)
        assert row["recoverable"] is True
        ident = row["id"]
        r = client.get(f"/api/{shelf}/{ident}/recover")
        assert r.status_code == 200, f"{shelf} said recoverable but /recover answered {r.status_code}"


def test_the_shelf_keeps_its_own_card_fields(damaged_desk):
    """The desk still needs these to render the row; the envelope did not eat them."""
    client, *_ = damaged_desk
    proj = _damaged(client, "projects")
    assert set(proj["stages"]) == {"parse", "analyze", "chat"}
    assert proj["project"] == "p1"
    idea = _damaged(client, "ideas")
    assert "created_at" in idea and "updated_at" in idea


# ---------- the recovery answers agree too ----------

def test_both_recover_routes_answer_in_one_shape(damaged_desk):
    """Gap 80 shipped `/projects/<n>/recover`; gap 70 shipped `/ideas/<id>/recover`.
    They described the same situation with different keys, which is the same defect
    one layer down."""
    client, *_ = damaged_desk
    proj = client.get("/api/projects/p1/recover").get_json()
    idea_id = _damaged(client, "ideas")["id"]
    idea = client.get(f"/api/ideas/{idea_id}/recover").get_json()
    for key in ("raw", "readable", "recoverable", "damage"):
        assert key in proj, f"project recover lost {key}"
        assert key in idea, f"idea recover lost {key}"
    assert proj["raw"] and idea["raw"], "raw bytes must be handed back on both"
    assert proj["readable"] is False and idea["readable"] is False


def test_both_recover_routes_agree_on_the_readability_header(damaged_desk):
    client, *_ = damaged_desk
    idea_id = _damaged(client, "ideas")["id"]
    for path in ("/api/projects/p1/recover", f"/api/ideas/{idea_id}/recover"):
        r = client.get(path)
        assert r.headers["X-Record-Readable"] == "false"


def test_the_idea_recover_still_says_whether_a_file_was_there(damaged_desk):
    """`had_file` is what the shared panel reads to decide between "here are your
    bytes" and "this folder is empty"."""
    client, *_ = damaged_desk
    idea_id = _damaged(client, "ideas")["id"]
    body = client.get(f"/api/ideas/{idea_id}/recover").get_json()
    assert body["had_file"] is True
    assert body["last_known"]["file"] == "idea.json"


# ---------- the client: one panel, and it reaches both shelves ----------

def test_the_client_has_one_recovery_panel_for_both_shelves():
    with open(os.path.join(ROOT, "screenplay_studio", "webapp", "app.js"), encoding="utf-8") as f:
        js = f.read()
    assert js.count("async function showRecovery") == 1, (
        "two panels would be two vocabularies again")
    body = js[js.index("async function showRecovery"):js.index("async function openProject")]
    # both shelves are routed through it, by parameter rather than by a copy
    assert 'kind === "idea"' in body
    assert "ideas" in body and "projects" in body


def test_the_idea_shelf_no_longer_refuses_its_own_recovery():
    """Gap 70 built /ideas/<id>/repair and nothing ever called it. That was the
    concrete cost of the two vocabularies."""
    with open(os.path.join(ROOT, "screenplay_studio", "webapp", "app.js"), encoding="utf-8") as f:
        js = f.read()
    assert "This idea's file is damaged on disk and can't be opened." not in js, (
        "the idea dead end is back")
    assert js.count('showRecovery(idea, "idea"); return; }') == 2, (
        "both idea entry points (Enter/Space and click) must offer recovery")


def test_the_panel_does_not_offer_an_idea_a_folder_copy_route():
    """An idea has no /recover/backup. Offering it would be a button that 404s."""
    with open(os.path.join(ROOT, "screenplay_studio", "webapp", "app.js"), encoding="utf-8") as f:
        js = f.read()
    body = js[js.index("async function showRecovery"):js.index("async function openProject")]
    assert "recover/backup" in body
    assert 'kind === "project"' in body, (
        "the folder-copy link must be gated on the shelf that actually has one")
