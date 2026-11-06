"""Gap 73 — an export must say which file it came from, and what it left behind.

Filed defect: a project with a leftover `source.pdf` beside the active
`source.fountain` exported the active working copy correctly with **no warning**,
and nothing in the UI explained that the extra file existed and was not part of
the active draft.

Measured before the fix, through the real routes: the project summary carried no
source filename at all, the export carried no provenance of any kind, and a stray
`source.pdf` was invisible on every surface. Nothing was corrupt — the active
draft exported correctly — which is exactly why it went unnoticed: the writer's
only way to learn that two scripts shared a folder was to open the folder.

The principle these tests hold: the desk may never leave the writer guessing
which file is the draft. It also may not guess FOR them — an unrecorded source
is reported as unrecorded, never smoothed into a plausible filename, and a stray
file is disclosed and left exactly where it is.
"""

import os
import re
import time

import pytest

import screenplay_studio.webapp_server as ws
from screenplay_studio.manifest import ProjectManifest
from screenplay_parser import parse_screenplay
from screenplay_studio.revision import ensure_working

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "pain_tenglish.fountain")


def _project(tmp_path, name="p1", strays=("source.pdf",)):
    """A real, parseable project — plus whatever leftovers the case needs."""
    root = tmp_path / "root"
    root.mkdir()
    src = tmp_path / "kept.fountain"
    src.write_bytes(open(FIXTURE, "rb").read())
    m = ProjectManifest.create(str(root / name), str(src), title=name)
    parse_screenplay(str(m.source_path)).save(m.parsed_path)
    ensure_working(m)
    for stray in strays:
        (root / name / stray).write_bytes(b"%PDF-1.4 leftover" if stray.endswith(".pdf")
                                          else b"an older attempt")
    return root, m


@pytest.fixture
def desk(tmp_path, monkeypatch):
    root, m = _project(tmp_path)
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(root))
    ws.app.config["TESTING"] = True
    return ws.app.test_client(), m, root


# ---------- the defect, on each surface that used to stay silent ----------

def test_the_project_summary_names_the_active_source(desk):
    client, m, _ = desk
    body = client.get("/api/projects/p1").get_json()
    assert body["source_file"] == "kept.fountain"
    assert body["source_format"] == ".fountain"
    assert body["source_recorded"] is True


def test_the_shelf_row_names_the_active_source(desk):
    """The format chip on the shelf used to be the only hint, and it rendered
    nothing when the field was absent — from a summary that never carried it."""
    client, _, _ = desk
    rows = client.get("/api/projects").get_json()
    row = [r for r in (rows if isinstance(rows, list) else rows.get("projects", []))
           if r.get("project") == "p1"]
    assert len(row) == 1
    assert row[0]["source_file"] == "kept.fountain"


def test_a_stray_source_file_is_disclosed_not_hidden(desk):
    client, _, _ = desk
    body = client.get("/api/projects/p1").get_json()
    names = [x["name"] for x in body["unattached_sources"]]
    assert names == ["source.pdf"]


def test_the_stray_file_is_never_touched(desk):
    """Disclosure, not housekeeping. It is real material the writer may want."""
    client, _, root = desk
    path = root / "p1" / "source.pdf"
    before = path.read_bytes()
    client.get("/api/projects/p1")
    client.get("/api/projects/p1/export?format=fountain")
    assert path.exists(), "the stray was deleted"
    assert path.read_bytes() == before, "the stray was rewritten"


def test_the_export_says_what_it_was_made_from(desk):
    client, _, _ = desk
    r = client.get("/api/projects/p1/export?format=fountain")
    assert r.status_code == 200
    assert r.headers["X-Source-File"] == "kept.fountain"
    assert r.headers["X-Source-Format"] == ".fountain"


def test_the_export_reports_the_stray_beside_it(desk):
    """The export is the artifact that leaves the machine. Filing the stray only
    in the UI means the collaborator receiving the file learns nothing."""
    client, _, _ = desk
    r = client.get("/api/projects/p1/export?format=fountain")
    assert r.headers["X-Unattached-Sources"] == "1"
    assert r.headers["X-Unattached-Names"] == "source.pdf"


@pytest.mark.parametrize("fmt", ["fountain", "fdx", "txt"])
def test_every_export_format_discloses_provenance(desk, fmt):
    client, _, _ = desk
    r = client.get(f"/api/projects/p1/export?format={fmt}")
    assert r.status_code == 200
    assert r.headers["X-Source-File"] == "kept.fountain"


# ---------- guessing is the other way to get this wrong ----------

def test_an_unrecorded_source_is_reported_as_unrecorded(tmp_path, monkeypatch):
    """Legacy manifests may lack `source_filename`. Report the hole; do not fill
    it with the file that happens to be there."""
    root, m = _project(tmp_path)
    m.source_filename = None
    m.save()
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(root))
    ws.app.config["TESTING"] = True
    client = ws.app.test_client()

    body = client.get("/api/projects/p1").get_json()
    assert body["source_recorded"] is False
    assert not body["source_file"]
    r = client.get("/api/projects/p1/export?format=fountain")
    assert r.status_code == 200
    assert r.headers["X-Source-File"] == "not-recorded"


def test_the_desks_own_artifacts_are_not_called_strays(desk):
    """`report.md` and `draft_notes.md` carry script extensions but are this
    desk's own output. Flagging them on every project would train the writer to
    ignore the warning that matters."""
    client, m, root = desk
    (root / "p1" / "source.pdf").unlink()  # isolate the two desk artifacts
    (root / "p1" / "report.md").write_text("# report\n")
    (root / "p1" / "draft_notes.md").write_text("notes\n")
    body = client.get("/api/projects/p1").get_json()
    assert body["unattached_sources"] == []


def test_the_active_source_is_never_listed_as_a_stray(desk):
    client, m, _ = desk
    names = [x["name"] for x in client.get("/api/projects/p1").get_json()["unattached_sources"]]
    assert os.path.basename(m.source_path) not in names


def test_a_clean_project_says_nothing_alarming(desk):
    client, m, root = desk
    (root / "p1" / "source.pdf").unlink()
    body = client.get("/api/projects/p1").get_json()
    assert body["unattached_sources"] == []
    r = client.get("/api/projects/p1/export?format=fountain")
    assert r.headers["X-Unattached-Sources"] == "0"
    assert "X-Unattached-Names" not in r.headers


def test_the_stray_survives_a_second_upload_being_refused(tmp_path):
    """A stray source file makes the directory non-empty, and `create` refuses an
    occupied destination (gap 50). Both rules must hold at once: refuse to
    clobber, and keep disclosing the file that caused the refusal."""
    root, m = _project(tmp_path)
    other = tmp_path / "other.fountain"
    other.write_bytes(b"Title: Other\n\nINT. X - DAY\n\nNothing.\n")
    with pytest.raises(ValueError):
        ProjectManifest.create(str(root / "p1"), str(other), title="clobber")
    assert (root / "p1" / "source.pdf").exists()
    assert m.unattached_sources()[0]["name"] == "source.pdf"


# ---------- the client half, pinned at source ----------

def test_the_client_names_the_file_and_the_strays():
    with open(os.path.join(ROOT, "screenplay_studio", "webapp", "app.js"),
              encoding="utf-8") as f:
        js = f.read()
    start = js.index("function renderSourceProvenance")
    end = js.index("async function openProject")
    body = js[start:end]
    assert "unattached_sources" in body
    assert "source_file" in body
    # the unrecorded case must be spoken, not skipped
    assert re.search(r"not recorded", body, re.I), "an unrecorded source must say so"
    # And it must be WIRED INTO the project open, or it never runs. Asserting on
    # the bare call text is not enough: the definition ("function
    # renderSourceProvenance(project)") contains it, so an unwired helper would
    # still pass. Count call sites outside the definition instead.
    assert js.count("renderSourceProvenance(") >= 2, (
        "renderSourceProvenance is defined but never called — the banner never runs")
    open_at = js.index("async function openProject(name)")
    assert "renderSourceProvenance(project)" in js[open_at:], (
        "the project open must call it, or opening a project says nothing")

    with open(os.path.join(ROOT, "screenplay_studio", "webapp", "index.html"),
              encoding="utf-8") as f:
        html = f.read()
    assert 'id="project-source"' in html
