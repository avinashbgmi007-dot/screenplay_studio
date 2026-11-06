"""Gap 79 — an export must say it was reconstructed, and a re-import must not care.

Filed defect: a script parsed from a PDF exported cleanly to Fountain and FDX, and
neither artifact recorded that it came from a parse, which file it came from, or
what a parse cannot promise. Handing that export to a collaborator, or opening it
in Final Draft, produced something indistinguishable from an original screenplay.

Measured before the fix: all three formats carried no provenance of any kind — the
word "provenance" did not appear in any of them, and neither did the source
filename. Nothing was broken; the artifact simply arrived with no memory.

The two rules these tests hold:
  1. where the format can carry a note without touching the screenplay, it must;
  2. where it cannot, it must not contaminate the script to try — and the absence
     is stated on the wire instead of being left to assumption.
"""

import os
import xml.etree.ElementTree as ET

import pytest

import screenplay_studio.webapp_server as ws
from screenplay_parser import parse_fdx, parse_screenplay
from screenplay_parser.export import (
    PROVENANCE_MARKER,
    build_provenance,
    export,
    to_fdx,
    to_fountain,
    to_txt,
)
from screenplay_studio.manifest import ProjectManifest
from screenplay_studio.revision import ensure_working

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOUNTAIN = os.path.join(ROOT, "tests", "fixtures", "pain_tenglish.fountain")


@pytest.fixture
def pdf_doc():
    """A real PDF through the real parser — the case the gap was filed about."""
    return parse_screenplay(os.path.join(ROOT, "tests", "fixtures", "Pain_FD_4_scenes.pdf"))


@pytest.fixture
def fountain_doc():
    return parse_screenplay(FOUNTAIN)


# ---------- the block exists, and says the true thing ----------

def test_a_pdf_export_is_marked_as_reconstructed(pdf_doc):
    prov = build_provenance(pdf_doc)
    assert prov["reconstructed"] is True
    assert prov["source_format"] == "pdf"
    assert prov["source_file"] == "Pain_FD_4_scenes.pdf"


def test_a_native_fountain_is_not_called_reconstructed(fountain_doc):
    """Over-claiming is the mirror defect: a writer's own file is not a
    reconstruction, and saying so would teach readers to distrust the flag."""
    prov = build_provenance(fountain_doc)
    assert prov["reconstructed"] is False


def test_fountain_carries_the_marker_in_a_boneyard(fountain_doc):
    text = to_fountain(fountain_doc)
    assert PROVENANCE_MARKER in text
    block = text[text.index("/*"):text.index("*/") + 2]
    assert "pain_tenglish.fountain" in block, "the block must name the source file"
    assert "screenplay-studio" in block


def test_fdx_carries_the_marker_in_a_comment(fountain_doc):
    text = to_fdx(fountain_doc)
    assert PROVENANCE_MARKER in text
    assert "<!--" in text


def test_the_marker_is_valid_xml_and_not_content(fountain_doc, tmp_path):
    """It must be a comment, not a paragraph: a paragraph would print on the
    writer's title page in Final Draft."""
    p = tmp_path / "x.fdx"
    p.write_text(to_fdx(fountain_doc), encoding="utf-8")
    root = ET.parse(str(p)).getroot()
    content = root.find("Content")
    assert [e.tag for e in content] == ["Paragraph"] * len(list(content))
    for para in content.iter("Paragraph"):
        assert PROVENANCE_MARKER not in "".join(t.text or "" for t in para.findall("Text"))


def test_the_machine_half_is_real_json():
    import json
    doc = parse_screenplay(FOUNTAIN)
    text = to_fountain(doc)
    block = text[text.index("/*") + 2:text.index("*/")]
    line = [l for l in block.splitlines() if l.strip().startswith("{")][0]
    parsed = json.loads(line)
    assert parsed["generator"] == "screenplay-studio"
    assert parsed["scenes"] == len(doc.scenes)


# ---------- re-import must not care ----------

def test_a_marked_fountain_re_imports_cleanly(fountain_doc, tmp_path):
    p = tmp_path / "back.fountain"
    p.write_text(to_fountain(fountain_doc), encoding="utf-8")
    back = parse_screenplay(str(p))
    assert back.scene_count == fountain_doc.scene_count
    assert PROVENANCE_MARKER not in "".join(
        e.text or "" for s in back.scenes for e in s.elements)


def test_a_marked_fdx_re_imports_cleanly(fountain_doc, tmp_path):
    p = tmp_path / "back.fdx"
    p.write_text(to_fdx(fountain_doc), encoding="utf-8")
    back = parse_fdx(str(p))
    assert back.scene_count == fountain_doc.scene_count
    assert back.title == fountain_doc.title
    assert PROVENANCE_MARKER not in "".join(
        e.text or "" for s in back.scenes for e in s.elements)


def test_a_re_marked_export_does_not_accumulate_blocks(fountain_doc, tmp_path):
    """Re-exporting an already-marked file must not stack blocks — a file that
    grows a marker per round trip is a file that cannot be diffed."""
    p = tmp_path / "twice.fountain"
    p.write_text(to_fountain(fountain_doc), encoding="utf-8")
    twice = to_fountain(parse_screenplay(str(p)))
    assert twice.count(PROVENANCE_MARKER) == 1


# ---------- the format that cannot carry it says so ----------

def test_txt_does_not_embed_the_block(fountain_doc):
    """A .txt has no comment syntax and no title-page phase, so an embedded note
    re-imports as ACTION in the writer's script. Refusing is the honest choice."""
    text = to_txt(fountain_doc)
    assert PROVENANCE_MARKER not in text


def test_a_marked_txt_would_have_printed_on_the_page(fountain_doc, tmp_path):
    """The reason for the refusal, MEASURED — and narrower than I first wrote it.

    My first version of this test asserted the block becomes dialogue and
    corrupts the script. It reproduces no such thing: the scene count is
    unchanged and the marker never reaches scene text. What actually happens is
    that every note line lands in `front_matter` as ACTION, so it prints as four
    bogus action paragraphs at the top of the screenplay. That is the real cost,
    and the limit is justified on that, not on an imagined one.
    """
    q = tmp_path / "clean.txt"
    q.write_text(to_txt(fountain_doc), encoding="utf-8")
    clean = parse_screenplay(str(q))

    polluted = ("/* " + PROVENANCE_MARKER + "\nExported by screenplay-studio.\n"
                "{\"generator\": \"screenplay-studio\"}\n*/\n\n" + to_txt(fountain_doc))
    p = tmp_path / "polluted.txt"
    p.write_text(polluted, encoding="utf-8")
    back = parse_screenplay(str(p))

    # structure survives — so "it corrupts the script" would have been a false claim
    assert back.scene_count == clean.scene_count
    assert PROVENANCE_MARKER not in " ".join(
        e.text or "" for s in back.scenes for e in s.elements)
    # but the page does not
    # measured as a DELTA: a plain .txt already carries 2 action lines in
    # front_matter (its Title:/Author: lines, since .txt has no title-page phase)
    before = len([e for e in clean.front_matter if e.type.value == "action"])
    after = [e for e in back.front_matter if e.type.value == "action"]
    assert len(after) - before == 4, (
        f"expected the note to add 4 printed action lines, added {len(after) - before}")
    assert any(PROVENANCE_MARKER in (e.text or "") for e in after)


# ---------- the route: real project, real export ----------

def _project(tmp_path, name="p1", fixture=FOUNTAIN):
    root = tmp_path / "root"
    root.mkdir()
    # The extension is what makes it a PDF project — naming a PDF copy
    # "kept.fountain" silently built a Fountain project (second fixture bug,
    # caught by the archive test asserting reconstructed == True).
    src = tmp_path / ("kept" + os.path.splitext(fixture)[1])
    src.write_bytes(open(fixture, "rb").read())
    m = ProjectManifest.create(str(root / name), str(src), title=name)
    # The parse stage is a MANIFEST fact, not a side effect of having written
    # parsed.json: /backup reads m.stage("parse"), so a fixture that only saves
    # the parse tests the wrong thing. (My first fixture did exactly that and
    # reported the product as pending.)
    parse_screenplay(str(m.source_path)).save(m.parsed_path)
    ensure_working(m)
    m.mark_complete("parse", {"parsed": m.parsed_path})
    return root, m


@pytest.fixture
def desk(tmp_path, monkeypatch):
    root, m = _project(tmp_path)
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(root))
    ws.app.config["TESTING"] = True
    return ws.app.test_client(), m


def test_the_route_embeds_the_block_with_the_project_facts(desk):
    client, m = desk
    r = client.get("/api/projects/p1/export?format=fountain")
    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert PROVENANCE_MARKER in body
    assert "kept.fountain" in body          # the document's own memory
    assert '"project": "p1"' in body        # only the manifest knows this
    assert r.headers["X-Provenance-Embedded"] == "boneyard"


def test_the_route_says_when_it_could_not_embed(desk):
    client, _ = desk
    r = client.get("/api/projects/p1/export?format=txt")
    assert r.headers["X-Provenance-Embedded"] == "none"
    assert PROVENANCE_MARKER not in r.data.decode("utf-8")


def test_the_fdx_route_embeds_a_comment(desk):
    client, _ = desk
    r = client.get("/api/projects/p1/export?format=fdx")
    assert r.headers["X-Provenance-Embedded"] == "xml-comment"
    assert "<!--" in r.data.decode("utf-8")


def test_the_backup_manifest_records_export_provenance(desk, tmp_path):
    """The recommendation asks for it in the backup manifest too: the archive is
    what answers "original or reconstructed" after the manifest is gone."""
    import io
    import json
    import zipfile

    client, m = desk
    r = client.get("/api/projects/p1/backup")
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.data))
    manifest = json.loads(zf.read("backup-manifest.json"))
    prov = manifest["export_provenance"]
    assert prov["source_file"] == "kept.fountain"
    assert prov["reconstructed"] is False
    assert prov["parse_status"] == "complete"


def test_a_pdf_project_is_recorded_as_reconstructed_in_the_archive(tmp_path, monkeypatch):
    import io
    import json
    import zipfile

    root, m = _project(tmp_path, fixture=os.path.join(ROOT, "tests", "fixtures",
                                                      "Pain_FD_4_scenes.pdf"))
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(root))
    ws.app.config["TESTING"] = True
    r = ws.app.test_client().get("/api/projects/p1/backup")
    manifest = json.loads(zipfile.ZipFile(io.BytesIO(r.data)).read("backup-manifest.json"))
    assert manifest["export_provenance"]["reconstructed"] is True


def test_suppressing_the_block_is_opt_in_and_not_the_default(fountain_doc):
    """Formats conformance tests may need a bare file; nothing user-facing may
    reach it by accident."""
    assert PROVENANCE_MARKER not in to_fountain(fountain_doc, provenance=False)
    assert PROVENANCE_MARKER in to_fountain(fountain_doc)
    blank = parse_screenplay(FOUNTAIN)
    blank.source_filename = None
    prov = build_provenance(blank)
    assert prov["source_file"] is None, "an unrecorded source is null, not an empty string"
