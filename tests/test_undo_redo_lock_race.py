"""The edit log's undo/redo path is a load-modify-write like any other store —
and it was the one writer-owned cycle with NO lock on it (H5, re-audit 2026-09-24).

`save_working` appends under `lock_for(edits_log_path)`. `undo_last_edit` and
`redo_last_edit` read both stores, mutate in memory, and write them back with no
lock at all — while the webapp runs `threaded=True` and AGENTS.md documents
CLI + webapp over one project directory as supported. Two writers therefore
overlap, and the loser's record disappears: an edit whose text IS in
working.json can vanish from edits.json, so the writer can never undo it and
has no sign anything was lost. Measured live in the audit (a 0.4 s-slowed read
+ one concurrent apply): final `edits.json` had **0 records** while the working
copy carried the applied text.

These tests widen that exact window deterministically — the read is slowed and
the concurrent apply is driven at the moment the read has happened but the
write-back has not — because that is the only way to observe the defect: with
the lock restored, both writers serialize and nothing overlaps by accident.
"""

from __future__ import annotations

import threading
import time

from screenplay_studio import revision
from screenplay_studio.manifest import ProjectManifest

SAMPLE_SCRIPT = b"""Title: Undo Race

INT. STUDY - NIGHT

MARA takes out an old REVOLVER, setting it on the desk.

CUT TO:

INT. KITCHEN - DAY

Mara sits at the table, staring at nothing.
"""

LINE_1_OLD = "MARA takes out an old REVOLVER, setting it on the desk."
LINE_1_NEW = "MARA lays the REVOLVER on the desk."
LINE_2_OLD = "Mara sits at the table, staring at nothing."
LINE_2_NEW = "Mara stares at the table, saying nothing."

# Long enough that the concurrent writer lands inside the window on any machine
# this suite runs on, matching the 0.4 s the audit used to prove the defect. The
# probe only proves anything if the apply's append completes BEFORE the stale
# write-back, so the window has to outlast the concurrent apply's own work too.
WINDOW_S = 1.5


def _make_project(tmp_path):
    src = tmp_path / "x.fountain"
    src.write_bytes(SAMPLE_SCRIPT)
    m = ProjectManifest.create(str(tmp_path / "p"), str(src), title="Undo Race")
    from screenplay_parser import parse_screenplay
    doc = parse_screenplay(str(m.source_path))
    doc.save(m.parsed_path)
    revision.ensure_working(m)
    return m


def _apply(m, scene_number, old_line, new_line, record_id):
    """One real apply through the locked path — the same call the webapp makes.

    The record id is supplied rather than read back afterwards: re-reading the log
    here would sample a different moment than the append did, and this probe has
    to name the record it is looking for, not whichever one is on disk when it
    looks (`save_working` only mints an id when the record has none).
    """
    doc = revision.load_working(m)
    result = revision.apply_replacements(doc, scene_number, [{"old": old_line, "new": new_line}])
    assert result["applied"], f"the fixture line was not found: {result}"
    revision.save_working(m, doc, record={
        "id": record_id, "scene_number": scene_number, "applied": result["applied"],
        "skipped": [], "applied_at": time.time(),
    })
    return record_id


def _slowed(real_read, started: threading.Event, window_s: float = WINDOW_S):
    """Wrap a store read: complete it, announce it, then hold the window open."""
    def read(m):
        data = real_read(m)
        started.set()
        time.sleep(window_s)
        return data
    return read


def _run_with_concurrent_apply(m, monkeypatch, slow_name, op, record_id):
    """Run `op` on a thread whose store read is slowed; land one apply inside."""
    real_read = getattr(revision, slow_name)
    started = threading.Event()
    monkeypatch.setattr(revision, slow_name, _slowed(real_read, started))

    box = {}

    def run():
        try:
            box["result"] = op()
        except Exception as exc:  # surfaced below, never swallowed
            box["error"] = exc

    thread = threading.Thread(target=run)
    thread.start()
    assert started.wait(10), "the slowed read never ran — the probe is not measuring what it claims"
    # the concurrent writer: a real, locked apply on ANOTHER scene, so neither
    # operation depends on the other's text
    e2 = _apply(m, 2, LINE_2_OLD, LINE_2_NEW, record_id)
    thread.join(30)
    monkeypatch.setattr(revision, slow_name, real_read)
    assert not thread.is_alive(), f"{slow_name} never finished"
    assert "error" not in box, f"{slow_name} raised: {box.get('error')!r}"
    return box["result"], e2


def test_undo_does_not_drop_an_apply_that_lands_mid_flight(tmp_path, monkeypatch):
    """An edit applied while an undo is in flight keeps its log record.

    Broken: the undo writes back the list it read BEFORE the apply, so the
    apply's record is erased — the text stays in working.json, the record does
    not, and `can_undo` says there is nothing there.
    """
    m = _make_project(tmp_path)
    e1 = _apply(m, 1, LINE_1_OLD, LINE_1_NEW, "e1-race")

    undone, e2 = _run_with_concurrent_apply(
        m, monkeypatch, "edits_log", lambda: revision.undo_last_edit(m), "e2-race")

    assert undone["undone"]["id"] == e1
    ids = [rec.get("id") for rec in revision.edits_log(m)]
    assert e2 in ids, (
        "the concurrently applied edit lost its record: the log is a "
        f"load-modify-write that does not hold lock_for(edits.json) — ids={ids}"
    )
    # and the working copy still holds that edit's text: the two stores agree
    text = "\n".join(el.text for s in revision.load_working(m).scenes
                     if s.scene_number == 2 for el in s.elements)
    assert LINE_2_NEW in text


def test_redo_does_not_drop_an_apply_that_lands_mid_flight(tmp_path, monkeypatch):
    """The redo mirror: re-applying an undone edit must not erase a newer one.

    Same defect, other direction — and the window has to sit on the LOG read,
    because that is the write-back that clobbers: redo loads the log, a locked
    apply appends to it, and redo then writes its own stale list over the
    append. The redo stack's own read is not where the loss happens.
    """
    m = _make_project(tmp_path)
    _apply(m, 1, LINE_1_OLD, LINE_1_NEW, "e1-race")
    revision.undo_last_edit(m)          # E1 now sits on the redo stack

    redone, e2 = _run_with_concurrent_apply(
        m, monkeypatch, "edits_log", lambda: revision.redo_last_edit(m), "e2-race")

    assert redone["redone"]["scene_number"] == 1
    ids = [rec.get("id") for rec in revision.edits_log(m)]
    assert e2 in ids, (
        "redo appended to a log it read before the concurrent apply landed, and "
        f"overwrote the apply's record — ids={ids}"
    )
