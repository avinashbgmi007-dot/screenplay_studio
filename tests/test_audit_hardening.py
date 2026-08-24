"""Hardening batch: traversal guards, atomic writes, flag-don't-drop, wiring.

Covers the audit fixes:
- C1  path-traversal ids/names answer 400 at every chokepoint (ideas AND
      projects), including the proven kill-shot DELETE /api/ideas/..
- H1  concurrent idea saves/renames never tear idea.json
- H2  a corrupt idea is flagged on the shelf (unreadable), not dropped
- C3  config personas exclude internal *_examples keys
- P4  /api/stt/languages stays the mic menu's source of truth
"""
import io
import io
import json
import os
import threading

import pytest

import screenplay_studio.webapp_server as webapp_server
from screenplay_studio.ideas import IdeaStore


@pytest.fixture
def client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "hard_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


# ---- C1: traversal probes are rejected everywhere ----

def test_idea_traversal_ids_are_400(client):
    for method, path in (("POST", "/api/ideas/../content"),
                         ("POST", "/api/ideas/../rename"),
                         ("POST", "/api/ideas/../card"),
                         ("DELETE", "/api/ideas/..")):
        r = client.open(path, method=method, json={"content": "x", "title": "x", "card": {}})
        assert r.status_code == 400, (method, path)
        assert "invalid" in r.get_json()["error"].lower()


def test_project_traversal_name_is_400_not_500(client):
    r = client.get("/api/projects/../report")
    assert r.status_code == 400


def test_delete_ideas_dotdot_cannot_nuke_projects_dir(client):
    # The kill-shot from the audit: gate file present, then DELETE /api/ideas/..
    gate = os.path.join(webapp_server.PROJECTS_DIR, "idea.json")
    with open(gate, "w") as f:
        f.write("{}")
    r = client.delete("/api/ideas/..")
    assert r.status_code == 400
    assert os.path.isdir(webapp_server.PROJECTS_DIR)
    assert os.path.exists(gate), "projects dir contents must survive"


def test_store_rejects_bad_ids_directly(tmp_path):
    store = IdeaStore(str(tmp_path / "ideas"))
    with pytest.raises(ValueError):
        store._dir("..")
    with pytest.raises(ValueError):
        store._dir("a/../b")
    with pytest.raises(ValueError):
        store._dir("")
    # legit ids still work
    meta = store.create("ok")
    assert store.load(meta["id"])["title"] == "ok"


# ---- H1: atomic writes survive a save/rename race ----

def test_save_rename_race_never_tears_json(client):
    meta = client.post("/api/ideas", json={"title": "race"}).get_json()
    iid = meta["id"]
    errors = []

    def save(i):
        try:
            r = client.post(f"/api/ideas/{iid}/content",
                            json={"content": f"line {i}\nsecond {i}"})
            assert r.status_code == 200
        except Exception as e:  # pragma: no cover
            errors.append(e)

    def rename(i):
        try:
            r = client.post(f"/api/ideas/{iid}/rename", json={"title": f"T{i}"})
            assert r.status_code == 200
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=save, args=(i,)) for i in range(10)]
    threads += [threading.Thread(target=rename, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors

    final = client.get(f"/api/ideas/{iid}").get_json()
    assert isinstance(final.get("content"), str) and final["content"]
    assert final["title"].startswith("T")
    # no tmp litter left behind
    leftovers = [f for f in os.listdir(os.path.join(webapp_server.PROJECTS_DIR,
                                                    "ideas", iid)) if f.endswith(".tmp")]
    assert leftovers == []


# ---- H2: corrupt ideas are flagged, never silently dropped ----

def test_corrupt_idea_is_flagged_on_shelf(client):
    made = client.post("/api/ideas", json={"title": "broken"}).get_json()
    iid = made["id"]
    path = os.path.join(webapp_server.PROJECTS_DIR, "ideas", iid, "idea.json")
    with open(path, "w") as f:
        f.write("{ this is not json")

    listing = client.get("/api/ideas").get_json()
    entry = next((m for m in listing if m["id"] == iid), None)
    assert entry is not None, "corrupt idea must stay on the shelf"
    assert entry.get("unreadable") is True

    # opening it answers a clean client error, not a raw traceback
    r = client.get(f"/api/ideas/{iid}")
    assert r.status_code in (400, 500)
    body = r.get_json()
    assert body and "error" in body


def test_healthy_ideas_are_not_flagged(client):
    client.post("/api/ideas", json={"title": "healthy"})
    listing = client.get("/api/ideas").get_json()
    assert all(not m.get("unreadable") for m in listing if m.get("id"))


# ---- C2/C3: persona list is clean for the dropdown ----

def test_config_personas_exclude_example_keys(client):
    cfg = client.get("/api/config").get_json()
    personas = cfg.get("personas") or []
    assert personas, "co-writer installed: real persona list expected"
    assert not [p for p in personas if p.endswith("_examples")]
    assert "writing_partner" in personas and "premise_doctor" in personas


# ---- P4b: stt languages endpoint remains the mic source of truth ----

def test_stt_languages_shape(client):
    r = client.get("/api/stt/languages")
    assert r.status_code == 200
    langs = r.get_json()["languages"]
    assert isinstance(langs, list) and "auto" in langs and "en" in langs


# ---- upload cap answers a clean 413 ----

def test_oversized_upload_answers_413_json(client):
    webapp_server.app.config["MAX_CONTENT_LENGTH"] = 1000  # shrink for the test
    try:
        big = b"x" * 2000
        r = client.post("/api/projects",
                        data={"file": (io.BytesIO(big), "big.fountain")},
                        content_type="multipart/form-data")
        assert r.status_code == 413
        assert "too large" in r.get_json()["error"].lower()
    finally:
        webapp_server.app.config["MAX_CONTENT_LENGTH"] = 256 * 1024 * 1024


# ---- faster-whisper is optional, not a hard dependency ----

def test_faster_whisper_is_not_a_hard_dependency():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "requirements.txt")) as f:
        lines = [ln.strip() for ln in f.readlines()]
    active = [ln for ln in lines if ln and not ln.startswith("#")]
    assert not any("faster-whisper" in ln for ln in active), \
        "STT is optional; it must stay out of the hard requirements"


# ---- flag-don't-drop for projects (same contract as ideas) ----

def test_corrupt_manifest_stays_on_the_shelf(client):
    good = client.post(
        "/api/projects",
        data={"file": (io.BytesIO(b"Title: t\n\nINT. A - DAY\n"), "ok.fountain")},
        content_type="multipart/form-data",
    ).get_json()["project"]
    # a damaged neighbor
    bad_dir = os.path.join(webapp_server.PROJECTS_DIR, "Broken_Show")
    os.makedirs(bad_dir, exist_ok=True)
    with open(os.path.join(bad_dir, "project.json"), "w") as f:
        f.write("{ torn")

    listing = client.get("/api/projects").get_json()
    by_name = {p["project"]: p for p in listing}
    assert good in by_name and not by_name[good].get("unreadable")
    assert "Broken_Show" in by_name, "corrupt project must stay visible"
    assert by_name["Broken_Show"].get("unreadable") is True
    # empty stage dicts keep every frontend reader safe
    assert by_name["Broken_Show"]["stages"]["analyze"] == {}


def test_non_project_dirs_are_still_not_listed(client):
    client.post("/api/projects",
                data={"file": (io.BytesIO(b"Title: t\n\nINT. A - DAY\n"), "x.fountain")},
                content_type="multipart/form-data")
    listing = client.get("/api/projects").get_json()
    names = {p["project"] for p in listing}
    assert "ideas" not in names  # the ideas store is not a shelf project


def test_corrupt_parse_flagged_in_writer_library(client):
    made = client.post(
        "/api/projects",
        data={"file": (io.BytesIO(b"Title: t\n\nINT. A - DAY\n"), "torn.fountain")},
        content_type="multipart/form-data",
    ).get_json()["project"]
    with open(os.path.join(webapp_server.PROJECTS_DIR, made, "parsed.json"), "w") as f:
        f.write("{ torn")

    lib = client.get("/api/writer-library").get_json()["projects"]
    entry = next((e for e in lib if e.get("name") == made or e.get("project") == made), None)
    assert entry is not None, "corrupt parse must stay in past work"
    assert entry.get("unreadable") is True


# ---- demo honesty: config exposes it; switching back deactivates it ----

def test_config_exposes_demo_flag_and_switch_back(client):
    webapp_server._DEMO_MODEL_ACTIVE = True
    webapp_server._DEMO_URL = "http://127.0.0.1:59998"
    webapp_server.CONFIG["real_server_url"] = "http://127.0.0.1:59999"
    webapp_server.CONFIG["server_url"] = "http://127.0.0.1:59998"
    try:
        cfg = client.get("/api/config").get_json()
        assert cfg["demo_model"] is True
        assert cfg["real_server_url"] == "http://127.0.0.1:59999"

        r = client.post("/api/config", json={"server_url": "http://127.0.0.1:59999"})
        assert r.status_code == 200
        assert webapp_server._DEMO_MODEL_ACTIVE is False, \
            "pointing at a non-demo URL must deactivate the demo"
        cfg = client.get("/api/config").get_json()
        assert cfg["demo_model"] is False
        assert "real_server_url" not in cfg
    finally:
        webapp_server._DEMO_MODEL_ACTIVE = False
        webapp_server._DEMO_URL = None
        webapp_server.CONFIG["real_server_url"] = None


def test_engine_base_ignores_stale_demo_pin(client):
    webapp_server._DEMO_URL = "http://127.0.0.1:59998"
    webapp_server.CONFIG["server_url"] = "http://real:8080"
    try:
        class DemoPinned:
            server_url = "http://127.0.0.1:59998"
        assert webapp_server._engine_base_url(DemoPinned()) == "http://real:8080", \
            "sessions created during demo must not pin the dead demo port"

        class Other:
            server_url = "http://other:9999"
        assert webapp_server._engine_base_url(Other()) == "http://other:9999"
    finally:
        webapp_server._DEMO_URL = None


def test_real_server_check_reports_availability(client):
    webapp_server._DEMO_MODEL_ACTIVE = True
    webapp_server._DEMO_URL = "http://127.0.0.1:59998"
    webapp_server.CONFIG["real_server_url"] = "http://127.0.0.1:59999"  # nothing there
    try:
        body = client.get("/api/real-server-check").get_json()
        assert body["demo"] is True and body["available"] is False

        webapp_server._DEMO_MODEL_ACTIVE = False
        assert client.get("/api/real-server-check").get_json() == {"demo": False}
    finally:
        webapp_server._DEMO_MODEL_ACTIVE = False
        webapp_server._DEMO_URL = None
        webapp_server.CONFIG["real_server_url"] = None
