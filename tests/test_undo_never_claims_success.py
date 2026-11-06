"""Gap 51 — undo could fail while the interface said it succeeded.

The filed reproduction, through the real Flask routes: MARA's unique
`First line.` replaced with `Second line.` while TOM already says that line.
Undo answered HTTP 200 with `restored: []` and one `failed` item, the text
stayed changed, and the edit record moved from undo to redo. The production UI
ignored those fields and unconditionally displayed "Undid the last applied
edit."

Three separate defects, each tested here:

  1. the record was consumed even though nothing was reversed — the writer's
     edit became unrecoverable while the undo stack said there was nothing left
     to undo;
  2. a group was applied partially, leaving a document matching neither the
     before nor the after state;
  3. the interface reported a specific outcome it had never checked.

The root cause of (1) in the filed fixtures is worth naming: the apply matched
a line by TEXT alone, so replacing MARA's line with text TOM already had left
two identical lines under two different speakers — and the reversal, also
text-only, could no longer tell which one it had changed. A line's identity
includes its speaker, so both directions now carry it.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_parser import parse_screenplay
from screenplay_studio import revision
from screenplay_studio.manifest import ProjectManifest

SRC = """Title: T

INT. ROOM - DAY

MARA
First line.

TOM
Second line.
"""


def _client(monkeypatch, tmp_path):
    import screenplay_studio.webapp_server as ws
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(tmp_path))
    ws.app.config["TESTING"] = True
    return ws.app.test_client()


def _project(tmp_path, text=SRC):
    """A real project on disk, parsed and with a working copy — as the desk has."""
    src = Path(tmp_path) / "s.fountain"
    src.write_text(text, encoding="utf-8")
    m = ProjectManifest.create(str(Path(tmp_path) / "proj"), str(src), title="T")
    parse_screenplay(m.source_path).save(m.parsed_path)
    m.save()
    revision.ensure_working(m)
    return m


def _dialogue(m):
    doc = revision.load_working(m)
    return [(e.text, e.character) for e in doc.scenes[0].elements
            if e.type.value == "dialogue"]


# ---------- the filed route-level reproduction ----------

def test_a_failed_undo_is_not_a_200(monkeypatch, tmp_path):
    """The filed case, through the real route."""
    client = _client(monkeypatch, tmp_path)
    m = _project(tmp_path)

    # a record whose reversal cannot be resolved: the line it names is gone
    revision.apply_edit(m, 1, [{"old": "First line.", "new": "Third line."}])
    doc = revision.load_working(m)
    el = [e for e in doc.scenes[0].elements if e.text == "Third line."][0]
    el.text = "Something else entirely"        # the line moved on
    revision.save_working(m, doc)

    r = client.post("/api/projects/proj/edits/undo")
    assert r.status_code == 409, r.get_json()
    body = r.get_json()
    assert body["ok"] is False
    assert body["error"], "the writer must be told why"
    assert body["can_undo"] is True, "an edit that could not be reversed is still undoable"


def test_a_successful_undo_says_ok(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    m = _project(tmp_path)
    revision.apply_edit(m, 1, [{"old": "First line.", "new": "Third line."}])
    r = client.post("/api/projects/proj/edits/undo")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["applied_count"] == 1
    assert ("First line.", "MARA") in _dialogue(m)


def test_a_failed_redo_is_not_a_200(monkeypatch, tmp_path):
    """The entry flagged redo as unproven; it is the same shape."""
    client = _client(monkeypatch, tmp_path)
    m = _project(tmp_path)
    revision.apply_edit(m, 1, [{"old": "First line.", "new": "Third line."}])
    revision.undo_last_edit(m)
    # after the undo the text is back to `First line.`; now change it, so the
    # redo cannot find what it is supposed to re-apply
    doc = revision.load_working(m)
    [e for e in doc.scenes[0].elements if e.text == "First line."][0].text = "Moved on"
    revision.save_working(m, doc)

    r = client.post("/api/projects/proj/edits/redo")
    assert r.status_code == 409, r.get_json()
    assert r.get_json()["ok"] is False
    assert r.get_json()["can_redo"] is True


# ---------- the record survives a refusal ----------

def test_a_refused_undo_keeps_the_edit_recoverable(tmp_path):
    """The core defect: the record left the undo log anyway."""
    m = _project(tmp_path)
    revision.apply_edit(m, 1, [{"old": "First line.", "new": "Third line."}])
    doc = revision.load_working(m)
    [e for e in doc.scenes[0].elements if e.text == "Third line."][0].text = "Moved on"
    revision.save_working(m, doc)

    before = len(revision.edits_log(m))
    u = revision.undo_last_edit(m)
    assert u["undone"] is None
    assert u["restored"] == []
    assert len(revision.edits_log(m)) == before, "the edit must not be consumed"
    assert revision.redo_stack(m) == [], "it must not move to the redo stack"
    assert u["can_undo"] is True


def test_the_refusal_names_the_line(tmp_path):
    m = _project(tmp_path)
    revision.apply_edit(m, 1, [{"old": "First line.", "new": "Third line."}])
    doc = revision.load_working(m)
    [e for e in doc.scenes[0].elements if e.text == "Third line."][0].text = "Moved on"
    revision.save_working(m, doc)
    u = revision.undo_last_edit(m)
    assert "Third line." in u["reason"]
    assert "still in place" in u["reason"]


def test_a_refused_undo_changes_nothing(tmp_path):
    m = _project(tmp_path)
    revision.apply_edit(m, 1, [{"old": "First line.", "new": "Third line."}])
    doc = revision.load_working(m)
    [e for e in doc.scenes[0].elements if e.text == "Third line."][0].text = "Moved on"
    revision.save_working(m, doc)
    before = _dialogue(m)
    revision.undo_last_edit(m)
    assert _dialogue(m) == before


# ---------- groups are all-or-nothing ----------

def test_a_group_does_not_half_reverse(tmp_path):
    """Applying part of a group leaves a document matching neither state."""
    m = _project(tmp_path, text=(
        "Title: T\n\nINT. ROOM - DAY\n\nMARA\nFirst line.\n\nMARA\nSecond thought.\n"
    ))
    revision.apply_edit(m, 1, [
        {"old": "First line.", "new": "One."},
        {"old": "Second thought.", "new": "Two."},
    ])
    doc = revision.load_working(m)
    # only one of the two lines moves on, so the group cannot be reversed whole
    [e for e in doc.scenes[0].elements if e.text == "Two."][0].text = "Changed again"
    revision.save_working(m, doc)

    before = _dialogue(m)
    u = revision.undo_last_edit(m)
    assert u["undone"] is None
    assert _dialogue(m) == before, "the reversible half must not be applied alone"


# ---------- identity: a line's speaker is part of the line ----------

def test_a_duplicate_created_by_the_edit_does_not_block_undo(tmp_path):
    """The filed fixture exactly: MARA's line becomes what TOM already says.

    Before: apply matched by text alone, so the record said
    ('Second line.' -> 'First line.') with two candidate lines and undo refused.
    """
    m = _project(tmp_path)
    r = revision.apply_edit(m, 1, [{"old": "First line.", "new": "Second line.",
                                    "character": "MARA"}])
    assert r["applied"], r
    assert [t for t, _ in _dialogue(m)] == ["Second line.", "Second line."]

    u = revision.undo_last_edit(m)
    assert u["undone"] is not None, u["reason"]
    assert _dialogue(m) == [("First line.", "MARA"), ("Second line.", "TOM")]


def test_the_applied_record_carries_the_speaker(tmp_path):
    m = _project(tmp_path)
    r = revision.apply_edit(m, 1, [{"old": "First line.", "new": "Third line."}])
    assert r["applied"][0]["character"] == "MARA"


def test_a_speaker_hint_resolves_a_line_two_characters_say(tmp_path):
    """Two characters saying the same words is not ambiguous when the batch is
    about one of them."""
    m = _project(tmp_path)
    # make MARA and TOM both say the same words
    doc = revision.load_working(m)
    d = [e for e in doc.scenes[0].elements if e.type.value == "dialogue"]
    d[0].text = "Second line."
    revision.save_working(m, doc)
    assert set(t for t, _ in _dialogue(m)) == {"Second line."}

    r = revision.apply_edit(m, 1, [{"old": "Second line.", "new": "Only TOM's.",
                                    "character": "TOM"}])
    assert r["applied"], r
    assert _dialogue(m) == [("Second line.", "MARA"), ("Only TOM's.", "TOM")]


def test_without_a_speaker_hint_an_ambiguous_line_is_still_refused(tmp_path):
    """The old safety must survive: no identity, no guess."""
    m = _project(tmp_path, text=(
        "Title: T\n\nINT. ROOM - DAY\n\nMARA\nSame words.\n\nTOM\nSame words.\n"
    ))
    r = revision.apply_edit(m, 1, [{"old": "Same words.", "new": "Different."}])
    assert not r["applied"]
    assert "identical" in r["skipped"][0]["reason"]


# ---------- the interface message ----------

def test_the_client_reads_the_payload_before_claiming_success():
    """Source-level: no path may announce "Undid" without checking `ok`.

    The route-level tests above prove the server answers honestly; this pins the
    client half, which was the part that turned an honest 200-with-failures into
    a false statement to the writer.
    """
    js = (Path(__file__).resolve().parent.parent
          / "screenplay_studio" / "webapp" / "app.js").read_text(encoding="utf-8")
    start = js.index("async function undoEdit()")
    end = js.index("async function resetEdits()")
    block = js[start:end]
    assert "ok === false" in block, "the payload must be checked"
    assert block.index("ok === false") < block.index('"Undid the last applied edit."'), (
        "the success claim must come after the check"
    )
    assert "could not be re-applied" in block or "could not be undone" in block
