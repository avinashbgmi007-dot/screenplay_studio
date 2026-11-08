"""Gap 80 — a damaged project is a recovery state, not a dead card.

Filed defect: a project whose `project.json` was corrupted appeared on the shelf
flagged `unreadable: true` (correct), and then **every** route refused — open,
script, drafts, export, report, and even `/backup`, the one action whose entire
purpose is to copy the folder somewhere safe. There was no export, no repair and
no raw-copy path. The source file and the parse were both intact the whole time.

Measured before the fix on a truncated manifest: six routes, six 503s, while
`source.fountain` (4711 bytes) and `parsed.json` were both undamaged. The damage
was one small file; the lockout was the entire project.

The principle: keep the warning, remove the dead end. A writer whose manifest is
corrupt should be able to (a) get their writing out with no trust in the desk at
all, and (b) rebuild a working manifest from what is on disk — without the
damaged file being discarded, because it is the only record of what was there.

Same dead-end shape as gap 70 on the idea side, which is why this closes with the
same shape of answer: recover (read-only) + repair (writes, keeps the original).
"""

import io
import json
import os
import zipfile

import pytest

import screenplay_studio.webapp_server as ws
from screenplay_parser import parse_screenplay
from screenplay_studio.manifest import ProjectManifest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "pain_tenglish.fountain")

DAMAGED = '{"title": "p1", "source_file'


def _project(tmp_path, name="p1", corrupt=True):
    root = tmp_path / "root"
    root.mkdir()
    src = tmp_path / "kept.fountain"
    src.write_bytes(open(FIXTURE, "rb").read())
    m = ProjectManifest.create(str(root / name), str(src), title=name)
    parse_screenplay(str(m.source_path)).save(m.parsed_path)
    m.mark_complete("parse", {"parsed": m.parsed_path})
    if corrupt:
        with open(m.manifest_path, "w", encoding="utf-8") as f:
            f.write(DAMAGED)
    return root, m


@pytest.fixture
def desk(tmp_path, monkeypatch):
    root, m = _project(tmp_path)
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(root))
    ws.app.config["TESTING"] = True
    return ws.app.test_client(), m


# ---------- the defect: what used to be impossible ----------

def test_the_shelf_still_flags_the_project(desk):
    """The warning stays. Recovery must not soften the disclosure."""
    client, _ = desk
    rows = client.get("/api/projects").get_json()
    row = [r for r in rows if r.get("project") == "p1"][0]
    assert row["unreadable"] is True


def test_a_damaged_project_can_still_be_copied_out(desk):
    """`/backup` used to 503 here — locking the one route that saves the folder."""
    client, m = desk
    r = client.get("/api/projects/p1/backup")
    assert r.status_code == 200
    assert r.headers["X-Recovery-Archive"] == "true"
    names = zipfile.ZipFile(io.BytesIO(r.data)).namelist()
    assert "source.fountain" in names, "the writing must be in the archive"
    assert "project.json" in names, "the damaged file is evidence — copy it too"


def test_the_recovery_archive_says_it_did_not_interpret_anything(desk):
    client, _ = desk
    r = client.get("/api/projects/p1/recover/backup")
    zf = zipfile.ZipFile(io.BytesIO(r.data))
    manifest = json.loads(zf.read("recovery-manifest.json"))
    assert manifest["kind"] == "recovery"
    assert "without requiring a readable project manifest" in manifest["note"]
    assert "Known credentials are redacted" in manifest["note"]
    assert manifest["files"] >= 2
    assert manifest["complete"] is True


def test_recover_returns_the_raw_bytes_so_a_writer_can_read_them(desk):
    """Fidelity, not convenience: a re-serialised manifest would be a new file
    pretending to be the evidence."""
    client, _ = desk
    r = client.get("/api/projects/p1/recover")
    assert r.status_code == 200
    body = r.get_json()
    assert body["raw"] == DAMAGED
    assert body["readable"] is False
    assert "invalid JSON" in body["damage"]


def test_recover_says_the_writing_is_still_there(desk):
    client, _ = desk
    body = client.get("/api/projects/p1/recover").get_json()
    assert body["recoverable"] is True
    assert body["source_file"] == "source.fountain"
    assert body["source_bytes"] > 0
    assert body["parsed_present"] is True


def test_recover_lists_what_survived(desk):
    client, _ = desk
    files = client.get("/api/projects/p1/recover").get_json()["files"]
    assert "source.fountain" in files
    assert "parsed.json" in files


def test_repair_rebuilds_a_working_manifest(desk):
    client, m = desk
    r = client.post("/api/projects/p1/repair")
    assert r.status_code == 200
    assert r.get_json()["repaired"] is True
    # and the project opens again
    opened = client.get("/api/projects/p1")
    assert opened.status_code == 200
    assert opened.get_json()["source_file"] == "source.fountain"


def test_repair_keeps_the_damaged_file(desk):
    client, m = desk
    client.post("/api/projects/p1/repair")
    kept = [n for n in os.listdir(m.project_dir) if n.startswith("project.json.damaged-")]
    assert len(kept) == 1
    with open(os.path.join(m.project_dir, kept[0]), encoding="utf-8") as f:
        assert f.read() == DAMAGED, "the evidence must be byte-identical"


def test_repair_does_not_claim_the_project_was_parsed(desk):
    """A rebuild that lied about having parsed would make the desk show a script
    it never read. It says re-run the parse instead."""
    client, _ = desk
    body = client.post("/api/projects/p1/repair").get_json()
    assert body["needs_reparse"] is True
    assert body["parse_stage"] == "pending"


def test_repair_refuses_a_healthy_project(desk):
    """No damage, nothing to repair — and overwriting a good manifest would
    destroy the real record."""
    client, _ = desk
    assert client.post("/api/projects/p1/repair").status_code == 200
    again = client.post("/api/projects/p1/repair")
    assert again.status_code == 400
    assert "does not need repairing" in again.get_json()["error"]


def test_repair_refuses_when_there_is_nothing_to_rebuild_from(tmp_path, monkeypatch):
    """No screenplay on disk means no honest manifest. Do not invent an empty one."""
    root = tmp_path / "root"
    root.mkdir()
    pdir = root / "p2"
    pdir.mkdir()
    (pdir / "project.json").write_text(DAMAGED, encoding="utf-8")
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(root))
    ws.app.config["TESTING"] = True
    r = ws.app.test_client().post("/api/projects/p2/repair")
    assert r.status_code == 400
    assert "cannot be rebuilt" in r.get_json()["error"]
    # nothing was written over the evidence
    assert (pdir / "project.json").read_text(encoding="utf-8") == DAMAGED


def test_recovery_never_touches_the_original_bytes(desk):
    client, m = desk
    client.get("/api/projects/p1/recover")
    client.get("/api/projects/p1/recover/backup")
    client.get("/api/projects/p1/backup")
    with open(m.manifest_path, encoding="utf-8") as f:
        assert f.read() == DAMAGED


def test_a_missing_project_is_still_a_404(desk):
    client, _ = desk
    for path in ("/api/projects/nope/recover", "/api/projects/nope/recover/backup"):
        assert client.get(path).status_code == 404
    assert client.post("/api/projects/nope/repair").status_code == 404


def test_recovery_routes_refuse_path_traversal(desk):
    """These routes do not load a manifest — they cannot — so the name check is
    the only thing between the URL and the filesystem."""
    client, _ = desk
    for bad in ("..", "%2e%2e", "..%2f.."):
        r = client.get(f"/api/projects/{bad}/recover")
        assert r.status_code in (404, 400), f"{bad} was not refused ({r.status_code})"


# ---------- the healthy path must not regress ----------

def test_a_healthy_backup_is_unchanged(tmp_path, monkeypatch):
    """The recovery fallback must not hijack the normal archive, which builds a
    real manifest and reports completeness (gaps 72/73)."""
    root, m = _project(tmp_path, corrupt=False)
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(root))
    ws.app.config["TESTING"] = True
    r = ws.app.test_client().get("/api/projects/p1/backup")
    assert r.status_code == 200
    assert "X-Recovery-Archive" not in r.headers
    assert r.headers["X-Backup-Complete"] == "true"
    zf = zipfile.ZipFile(io.BytesIO(r.data))
    assert "backup-manifest.json" in zf.namelist()
    assert "export_provenance" in json.loads(zf.read("backup-manifest.json"))


def test_a_readable_project_reports_readable(tmp_path, monkeypatch):
    root, m = _project(tmp_path, corrupt=False)
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(root))
    ws.app.config["TESTING"] = True
    body = ws.app.test_client().get("/api/projects/p1/recover").get_json()
    assert body["readable"] is True
    assert body["damage"] is None


# ---------- the client half: the dead end is replaced, not softened ----------

def test_the_client_offers_recovery_instead_of_refusing():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "screenplay_studio", "webapp", "app.js"),
              encoding="utf-8") as f:
        js = f.read()
    assert "function showRecovery" in js
    # every project-card entry point must route to recovery, not to an error
    assert js.count("showRecovery(p); return; }") >= 3, (
        "each way into a damaged project (button, Enter/Space, card click) must "
        "offer recovery")
    assert js.count("renderSourceProvenance(") >= 2  # gap 73's pin still holds
    body = js[js.index("function showRecovery"):js.index("async function openProject")]
    assert "/recover/backup" in body, "the folder copy must be reachable"
    assert "/repair" in body, "rebuilding the manifest must be reachable"
    with open(os.path.join(root, "screenplay_studio", "webapp", "index.html"),
              encoding="utf-8") as f:
        assert 'id="recovery-panel"' in f.read()
