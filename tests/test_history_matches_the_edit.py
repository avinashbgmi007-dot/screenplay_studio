"""A log that cannot be written must not leave an edit that undo cannot see.

Gap 6, filed grade B: "Injected edit-log failure returned an error after working
text changed and before a history record existed."

The write order in `save_working` made this reachable: the working copy was
saved FIRST and `edits.json` appended second. Anything that failed between them
— a full disk, a sharing violation on Windows, a crash — left the writer's text
changed in the only place it survives, with no undo record for it. The call
raised, so the interface could at least say "something went wrong", but there
was nothing left to tell it WHAT happened, and the writer's one real recovery
route (undo) was now blind to the edit.

The invariant this file enforces is stated as an outcome, not a write order,
because the write order is the implementation and the outcome is the promise:

  after ANY failed apply, either the edit is fully recorded and undone by undo,
  or the text is untouched — never "text changed, history silent".

`revision.THREE_STORES_DIVERGED` and `recover_working_from_log` are the two
halves of the answer: a failure now rolls the working copy back, and a rollback
that itself fails leaves a marker so the NEXT cycle repairs the copy from the
log instead of presenting the divergence as normal.
"""

from __future__ import annotations

import json
import os

import pytest

from screenplay_studio import jsonio, revision

from test_undo_redo_lock_race import LINE_1_NEW, LINE_1_OLD, _make_project

SCENE = 1


@pytest.fixture()
def project(tmp_path):
    return _make_project(tmp_path / "proj")


def _working_text(m) -> str:
    return revision.scene_text(revision.load_working(m), SCENE)


def _fail_log_writes(m, monkeypatch, times: int = 1, exc=OSError):
    """Make the NEXT `times` writes to the edit log fail, and nothing else.

    Injected at `jsonio.atomic_write_json`, the one function every store write
    goes through, and filtered by the target path: failing globally would take
    the working-copy write down too, which is a different fault than the one
    this gap is about.
    """
    real = jsonio.atomic_write_json
    state = {"left": times}

    def flaky(path, data, **kwargs):
        if os.path.abspath(str(path)) == os.path.abspath(revision.edits_log_path(m)) \
                and state["left"] > 0:
            state["left"] -= 1
            raise exc("injected: the edit log could not be written")
        return real(path, data, **kwargs)

    monkeypatch.setattr(jsonio, "atomic_write_json", flaky)
    return state


def _fail_working_writes(m, monkeypatch, when_text: str | None = None):
    """Make a write to `working.json` fail AT THE LANDING.

    `ScriptDocument.save` delegates to `jsonio.atomic_write_json`, so failing
    that name is not enough — the fake is simply re-entered and the write goes
    through. `os.replace` is where a real write actually lands (tmp -> store),
    which is the step a full disk or a Windows sharing violation kills, so this
    fails the same way reality does instead of pretending to.

    `when_text` narrows the fault to a write whose PENDING BYTES contain that
    text, read from the temp file about to be renamed. Counting writes instead
    was wrong: `ensure_working` refreshes the copy from the parse on its own
    schedule, so an allowance of one is spent by a write this test never meant
    to target. Matching the content names the write that is meant — the forward
    save carries `new`, the rollback carries `old`.
    """
    real_replace = jsonio.os.replace
    target = os.path.abspath(revision.working_path(m))

    def _pending(src) -> str:
        try:
            with open(src, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def flaky_replace(src, dst, *a, **kw):
        if os.path.abspath(str(dst)) == target:
            if when_text is None or when_text in _pending(src):
                raise OSError("injected: the working copy could not be written")
        return real_replace(src, dst, *a, **kw)

    monkeypatch.setattr(jsonio.os, "replace", flaky_replace)


def test_a_failed_history_write_leaves_the_text_untouched(project, monkeypatch):
    """The writer's text and their undo history must agree after a refusal."""
    before = _working_text(project)
    assert LINE_1_OLD in before

    _fail_log_writes(project, monkeypatch, times=1)
    with pytest.raises(OSError):
        revision.apply_edit(project, SCENE,
                            [{"old": LINE_1_OLD, "new": LINE_1_NEW}])

    after = _working_text(project)
    assert after == before, (
        "the working copy kept an edit whose history record could not be "
        f"written; undo cannot reach it. before={before!r} after={after!r}")
    assert revision.edits_log(project) == []


def test_the_rollback_restores_the_exact_previous_text(project, monkeypatch):
    """Clearing the flag is not the same as undoing the edit.

    A refusal that leaves the new text in place and simply forgets the journal
    would pass every test that only asks whether the interface agreed with
    itself. The writer's document is the thing that has to go back.
    """
    before = _working_text(project)
    _fail_log_writes(project, monkeypatch, times=1)
    with pytest.raises(OSError):
        revision.apply_edit(project, SCENE,
                            [{"old": LINE_1_OLD, "new": LINE_1_NEW}])

    # Read the FILE, not the document: `load_working` runs the recovery hook,
    # so going through it would let the marker-and-repair safety net produce
    # the right answer while the rollback was doing nothing. The rollback's own
    # promise is narrower and faster — text and history agree on disk at the
    # moment the writer is told the edit failed — so that is what is asserted.
    with open(revision.working_path(project), "r", encoding="utf-8") as f:
        on_disk = f.read()
    assert LINE_1_NEW not in on_disk, (
        "the file on disk still carries an edit whose history record was never "
        "written; the writer's next read would be a repair, not a document")
    assert not os.path.exists(revision.divergence_marker_path(project)), (
        "the rollback succeeded, so nothing should be flagged for repair")

    after = _working_text(project)
    assert LINE_1_NEW not in after, (
        f"the rolled-back copy still carries the edit: {after!r}")
    assert after == before, f"rollback was not exact: {before!r} -> {after!r}"


def test_the_refusal_does_not_leave_a_stale_redo_stack(project, monkeypatch):
    """A rolled-back apply must not invalidate redo history it never created."""
    revision.apply_edit(project, SCENE, [{"old": LINE_1_OLD, "new": LINE_1_NEW}])
    revision.undo_last_edit(project)
    assert revision.redo_stack(project), "precondition: there is redo history"

    _fail_log_writes(project, monkeypatch, times=1)
    with pytest.raises(OSError):
        revision.apply_edit(project, SCENE,
                            [{"old": LINE_1_OLD, "new": LINE_1_NEW}])

    assert revision.redo_stack(project), (
        "a refused apply cleared the redo stack, so the writer lost a "
        "reversal they could previously re-apply")


def test_a_second_attempt_after_a_failure_succeeds(project, monkeypatch):
    """'Prevent unsafe retries': the retry must be safe, and it must work."""
    _fail_log_writes(project, monkeypatch, times=1)
    with pytest.raises(OSError):
        revision.apply_edit(project, SCENE,
                            [{"old": LINE_1_OLD, "new": LINE_1_NEW}])

    result = revision.apply_edit(project, SCENE,
                                 [{"old": LINE_1_OLD, "new": LINE_1_NEW}])
    assert [(a["old"], a["new"]) for a in result["applied"]] == [(LINE_1_OLD, LINE_1_NEW)]
    assert LINE_1_NEW in _working_text(project)
    assert len(revision.edits_log(project)) == 1


def test_the_journal_is_written_before_the_document(project, monkeypatch):
    """Write-ahead, in the only order that can recover: flag, then text.

    The journal's whole job is to be on disk at the instant the document could
    change, so that an interruption between the two is detectable. Written
    after the document it would record nothing the document does not already
    say, and a crash in the gap would be invisible — which is the gap itself.
    """
    seen = []
    real_save = revision.ScriptDocument.save

    def traced(self, path, *a, **kw):
        seen.append(os.path.exists(revision.journal_path(project)))
        return real_save(self, path, *a, **kw)

    monkeypatch.setattr(revision.ScriptDocument, "save", traced)
    revision.apply_edit(project, SCENE, [{"old": LINE_1_OLD, "new": LINE_1_NEW}])

    assert seen, "no document save was observed"
    assert all(seen), (
        f"a document save ran with no journal on disk (observed: {seen}); a "
        "crash at that instant leaves changed text and no record of it")


def test_a_failed_document_write_leaves_no_journal_behind(project, monkeypatch):
    """A refusal before anything changed must leave NOTHING flagged.

    The journal is written first, so a document write that fails would otherwise
    strand one — and the next cycle would then "repair" a project that was never
    damaged, which is a worse lie than the one this gap is about.
    """
    before = _working_text(project)
    _fail_working_writes(project, monkeypatch, when_text=LINE_1_NEW)
    with pytest.raises(OSError):
        revision.apply_edit(project, SCENE,
                            [{"old": LINE_1_OLD, "new": LINE_1_NEW}])

    # Asked BEFORE anything reads the copy: a read runs the same repair, so
    # reading first and asserting after would let a stranded journal be cleared
    # by the observation itself.
    report = revision.recover_working_from_log(project)
    assert report["repaired"] is False, (
        f"a clean refusal was reported as damage to be repaired: {report}")
    assert report["reason"] == "", f"a refusal was reported as damage: {report}"

    assert _working_text(project) == before
    assert not os.path.exists(revision.journal_path(project))
    assert not os.path.exists(revision.divergence_marker_path(project))


def test_an_unrecoverable_rollback_is_marked_not_hidden(project, monkeypatch):
    """When the rollback itself fails the next cycle must repair the copy.

    This is the crash-window half of the gap: text changed AND the record is
    missing. It cannot be prevented from inside the failing call, so it is
    recorded — the alternative is presenting a silently diverged document.
    """
    _fail_log_writes(project, monkeypatch, times=70)   # the log write fails
    _fail_working_writes(project, monkeypatch, when_text=LINE_1_OLD)  # ... and so does the rollback
    with pytest.raises(OSError):
        revision.apply_edit(project, SCENE,
                            [{"old": LINE_1_OLD, "new": LINE_1_NEW}])

    marker = revision.divergence_marker_path(project)
    assert os.path.exists(marker), (
        "text changed, the record was never written, and nothing on disk says "
        "so — the next cycle will present the divergence as normal")


def test_the_next_cycle_repairs_a_marked_copy_from_the_log(project, monkeypatch):
    """Reading the copy after a divergence must settle it, not echo it.

    The repair is not something a caller has to remember to invoke: the flag on
    disk is consumed at the top of the next working-copy cycle, so the first
    reader after the interruption sees agreement. That is why this asserts on a
    plain `load_working` — the same call `/script` makes — rather than on an
    explicit recovery call, which would only prove the helper works in isolation.
    """
    _fail_log_writes(project, monkeypatch, times=70)
    _fail_working_writes(project, monkeypatch, when_text=LINE_1_OLD)
    with pytest.raises(OSError):
        revision.apply_edit(project, SCENE,
                            [{"old": LINE_1_OLD, "new": LINE_1_NEW}])
    assert os.path.exists(revision.divergence_marker_path(project)), (
        "precondition: the divergence was flagged")

    # The fault is gone; the next ordinary read is what repairs it.
    monkeypatch.undo()
    text = _working_text(project)
    assert LINE_1_NEW not in text, (
        "the divergent text survived the next cycle; the log says no such edit "
        "was ever recorded, so presenting it is presenting an unrecorded change")
    assert LINE_1_OLD in text
    assert not os.path.exists(revision.divergence_marker_path(project))
    assert not os.path.exists(revision.journal_path(project))


def test_a_clean_project_is_never_repaired_or_marked(project):
    """No marker, no work: recovery must be inert on a healthy project."""
    report = revision.recover_working_from_log(project)
    assert report["repaired"] is False
    assert report["reason"] == "", report
    assert not os.path.exists(revision.divergence_marker_path(project))


def test_recovery_keeps_a_recorded_edit(project, monkeypatch):
    """A marked divergence with a live log keeps the logged edit."""
    revision.apply_edit(project, SCENE, [{"old": LINE_1_OLD, "new": LINE_1_NEW}])
    # Simulate the crash window directly: the record is intact, the copy is not.
    doc = revision.load_working(project)
    for el in revision.scene_elements(doc, SCENE):
        if getattr(el, "text", None) == LINE_1_NEW:
            el.text = "MARA holds a REVOLVER."
    doc.save(revision.working_path(project))
    revision.mark_divergence(project, "injected: copy clobbered outside the cycle")

    report = revision.recover_working_from_log(project)
    assert report["repaired"] is True
    assert report["source"] == "log"
    assert LINE_1_NEW in _working_text(project)


def test_a_damaged_marker_does_not_block_the_next_cycle(project, monkeypatch):
    """A marker is a warning, not a lock — a torn one must not wedge the studio."""
    path = revision.divergence_marker_path(project)
    with open(path, "w", encoding="utf-8") as f:
        f.write("{ this is not json")
    report = revision.recover_working_from_log(project)
    assert report["repaired"] is False
    assert report["reason"], "a damaged marker must be reported, not silently dropped"
    assert not os.path.exists(path), "a marker that cannot be read must be cleared"
