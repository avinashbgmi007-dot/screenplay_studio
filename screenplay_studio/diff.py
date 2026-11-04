"""
Draft-to-draft diffing — the writer's revision-progress view.

Writers revise in cycles: Draft 1 -> notes -> Draft 2 -> notes -> ... The
single most useful question after uploading a new draft is "what changed,
and what got fixed?" This module answers it:

  - snapshot_active(): freeze the current active draft (source + parse +
    report) into drafts/<name>/ so it can be diffed against later.
  - upload_new_draft(): swap a new uploaded file in as the active draft.
  - activate_draft(): switch back to an earlier snapshot.
  - diff_drafts(): structural diff (scenes added/removed/changed, changed
    lines within scenes) PLUS a findings diff — for every finding in the
    older report, is its evidence quote still present in the newer script
    (resolved / still_present), and which findings in the newer report are
    new vs. carried over from the old one.

All comparisons are deterministic (no model call) — they operate on the
parsed structure and the evidence quotes the analyzer already verified.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from difflib import SequenceMatcher

from screenplay_parser.models import ScriptDocument

from .jsonio import atomic_write_json, check_safe_id
from .manifest import StageStatus
from .revision import (edits_log_path, edits_redo_path, quote_present,
                       reset_working, working_path)


# Names that mean "the writer's current state", not a stored snapshot. They
# never become a directory and must not be validated as one.
_DRAFT_SENTINELS = (None, "", "active")


# Names that mean "the writer's current state", not a stored snapshot. They
# never become a directory and must not be validated as one.
_DRAFT_SENTINELS = (None, "", "active")


def drafts_dir(m) -> str:
    return os.path.join(m.project_dir, "drafts")


def draft_dir(m, name: str) -> str:
    """`drafts/<name>`, refusing any name that is not a plain single segment.

    This is the ONE chokepoint for turning a draft name into a path, so the
    containment check lives here rather than in each caller. Before it, a
    request-supplied name was joined onto `drafts/` verbatim: activating
    `../../OtherProject/drafts/v2` from project A read project B's snapshot,
    copied it over A's active source and report, and recorded the traversal
    string as `active_draft` (gap 62). `check_safe_id` is the existing
    ASCII-id rule the project and idea stores already use, so this adds no new
    notion of a valid name — it applies the one that was already there.

    Sentinels (`None`, `""`, `"active"`) mean the live root files, not a
    snapshot, and are never joined into a path; callers resolve them first.
    """
    if name in _DRAFT_SENTINELS:
        raise ValueError(f"draft name {name!r} is not a stored snapshot")
    try:
        check_safe_id(name, "draft name")
    except ValueError:
        raise ValueError(
            f"Draft name {name!r} is not valid — a draft name is letters, "
            "digits, '-' and '_' only."
        ) from None
    return os.path.join(drafts_dir(m), name)


def draft_parsed_path(m, name: str) -> str:
    return os.path.join(draft_dir(m, name), "parsed.json")


def draft_report_path(m, name: str) -> str:
    return os.path.join(draft_dir(m, name), "report.findings.json")


def snapshot_active(m, name: str) -> None:
    """Freeze the currently-active draft's files into drafts/<name>/.

    Overwrites an existing snapshot of the same name (re-uploading draft N
    after edits refreshes that draft's snapshot, which is the right semantics
    — the snapshot always reflects the latest state of that draft).
    """
    dst = draft_dir(m, name)
    os.makedirs(dst, exist_ok=True)
    # The source copy happens whether or not the script parsed. Both callers
    # remove or replace the active source right after, so a snapshot gated on
    # `parse == complete` could leave a draft's text on disk nowhere else — and
    # a draft whose parse failed (a bad upload, an OCR miss) is exactly the one
    # the writer still has to get back to.
    if os.path.exists(m.source_path):
        shutil.copy2(m.source_path,
                     os.path.join(dst, os.path.basename(m.source_path)))
    if m.stage("parse").status != "complete":
        return  # nothing parsed to snapshot
    for src, rel in _bundle_files(m):
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dst, rel))
    # The stage status belongs to the snapshot too (gap 64): activation used to
    # leave `parse` saying `failed` while restoring a perfectly good parse, so
    # `/script` kept refusing "Project hasn't been parsed yet" and only a manual
    # reparse cleared it. Recorded as a small sidecar rather than reconstructed
    # from the files, because "complete" is a claim the pipeline made, not
    # something the presence of parsed.json can assert on its own.
    atomic_write_json(snapshot_stage_path(dst), {
        "parse": getattr(m.stage("parse").status, "value", m.stage("parse").status),
    })
    # The writer's own edit cycle travels with the draft (gap 1). Before this,
    # `_reset_derived_state` deleted working.json + edits.json on every switch,
    # so "switch away and switch back" — an action the UI calls
    # non-destructive, "switching preserves the current one" — silently
    # destroyed the applied edits, the undo log and the redo stack. The text is
    # restored from this copy instead, which is what makes switching a safety
    # net rather than a hazard.
    for path, rel in (
        (working_path(m), _WORKING),
        (edits_log_path(m), _EDITS),
        (edits_redo_path(m), _REDO),
    ):
        if os.path.exists(path):
            shutil.copy2(path, os.path.join(dst, rel))


# Snapshot names for the edit cycle. Prefixed so they can never collide with the
# draft's own `source.*` / `parsed.json` / `report*` files.
_WORKING = "_working.json"
_EDITS = "_edits.json"
_REDO = "_edits.redo.json"
_STAGE = "_stages.json"

def snapshot_stage_path(snapshot_dir: str) -> str:
    return os.path.join(snapshot_dir, _STAGE)


def load_snapshot_stage(snapshot_dir: str):
    """The stage status recorded with a snapshot, or None.

    Damage is NOT absence. This store was first written with a bare
    `except OSError/ValueError: None` (gap 64), which folds "the file is
    unreadable" into "there is no record" — the exact A3 shape the fault-injection
    registry exists to catch, and it caught this one. A truncated sidecar means
    the switch happens without a known stage status, so the writer must be told
    that the draft's parse state could not be read, not quietly handed a draft
    whose stage looks like it was never written.
    """
    path = snapshot_stage_path(snapshot_dir)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise ValueError(
            f"the snapshot's stage record is unreadable ({e}); the draft was "
            "restored but its parse status could not be determined") from e
    if not isinstance(data, dict):
        raise ValueError(
            "the snapshot's stage record is not an object; the draft was "
            "restored but its parse status could not be determined")
    return data.get("parse")


def _bundle_files(m):
    """Every live file that BELONGS TO ONE SNAPSHOT of the script.

    Restoring only `parsed.json` and the report pair left the knowledge graph
    bound to the outgoing draft, so `/characters`, and anything else built from
    `parsed.kg.json`, described the draft the writer had left (gap 63: after
    switching back, the original draft showed the OTHER draft's cast — or, when
    the graph was newer than the restored parse, no cast at all).

    The finding-level stores are here for the same reason: a dismissal, a
    finding mark and the last-pass dedup snapshot all key off finding ids that
    belong to this draft's report. Carrying them across a switch would attach
    one draft's judgments to another's findings.

    Deliberately NOT included: sessions/ (chat threads have their own scope and
    a switch does not end a conversation), stash/notes (the writer's material
    about the work, not a product of one snapshot), and the locks. This list is
    the per-snapshot set, not "everything in the directory".
    """
    from .revision import (ambiguous_marks_path, dismissed_path,
                           finding_marks_path, last_pass_path)
    return (
        (m.parsed_path, "parsed.json"),
        (m.kg_path, "parsed.kg.json"),
        (m.report_findings_path, "report.findings.json"),
        (m.report_md_path, "report.md"),
        (dismissed_path(m), "dismissed_findings.json"),
        (finding_marks_path(m), "finding_marks.json"),
        (ambiguous_marks_path(m), "finding_marks.ambiguous.json"),
        (last_pass_path(m), "last_pass.json"),
        # The published reading's provenance travels with the draft too: without
        # these two, switching back restored the report FILES but left a pointer
        # (or none) from the other draft, so `/report` refused a reading whose
        # text was on disk. The generation directories themselves are not
        # copied — they are content-addressed by digest and kept on disk, so the
        # pointer still resolves to the reading it names.
        (m.report_snapshot_path, "report.snapshot.json"),
        (m.report_pointer_path, "report.current.json"),
    )


def restore_edit_cycle(m, name: str) -> None:
    """Put a snapshot's edit cycle back as the active draft's.

    Copies the draft's stored working copy and edit log over the live ones, and
    removes any live cycle member the snapshot does not have — a draft that was
    never edited must not inherit the outgoing draft's undo stack, or the writer
    would undo an edit that belongs to different text. Caller holds the switch;
    `activate_draft` invokes this after the derived files are restored.
    """
    d = draft_dir(m, name)
    for path, rel in (
        (working_path(m), _WORKING),
        (edits_log_path(m), _EDITS),
        (edits_redo_path(m), _REDO),
    ):
        src = os.path.join(d, rel)
        if os.path.exists(src):
            shutil.copy2(src, path)
        elif os.path.exists(path):
            os.remove(path)


def _reset_derived_state(m) -> None:
    """After swapping the active draft: discard edits, re-queue analysis.

    "Discard" is safe only because the outgoing draft's cycle was snapshotted
    first (see `snapshot_active`); the files removed here are restored by
    `restore_edit_cycle` when the writer switches back.
    """
    reset_working(m)
    m.stages["analyze"] = StageStatus()
    m.stages["chat"] = StageStatus()


def upload_new_draft(m, uploaded_path: str, filename: str):
    """Snapshot the current active draft, then make the upload the active one.

    The original upload is implicit (not in m.drafts); every subsequent upload
    gets an auto-named draft entry. Returns the manifest (mutated + saved).
    """
    # Unconditional: `snapshot_active` copies the source and skips the derived
    # files when there is nothing parsed yet, so an unparsed draft's text is
    # preserved here before the atomic swap below retires the active source.
    snapshot_active(m, m.active_draft or "original")

    ext = os.path.splitext(filename)[1].lower()
    m.source_filename = filename
    m.source_format = ext
    # Copy FIRST, swap SECOND: the new upload lands beside the old source and
    # an atomic replace swaps them, so a failed copy can never destroy the
    # writer's only copy of the script (previously the old source was deleted
    # before the copy ran — a copy failure on a project with no draft snapshot
    # meant unrecoverable data loss).
    incoming = m.source_path + ".incoming"
    shutil.copy2(uploaded_path, incoming)
    os.replace(incoming, m.source_path)

    _reset_derived_state(m)
    m.stages["parse"] = StageStatus()  # new source -> re-parse
    name = f"draft-{len(m.drafts) + 1}"
    m.drafts.append({"name": name, "source_filename": filename, "uploaded_at": time.time()})
    m.active_draft = name
    m.save()
    return m


def _snapshot_source(m, name: str, source_filename: str):
    """The snapshot's own copy of that draft's source, or None if there isn't
    exactly one candidate.

    `snapshot_active` files the source under `source<ext>` rather than the
    uploaded filename, so the ext is read back from the snapshot instead of
    trusting the manifest: "original" has no draft record to take it from, which
    is what made the old lookup look for `drafts/original/draft2.fountain` — a
    path no writer of that snapshot ever produced.
    """
    d = draft_dir(m, name)
    try:
        names = sorted(n for n in os.listdir(d) if n.startswith("source."))
    except OSError:
        return None
    want = "source" + os.path.splitext(source_filename)[1].lower()
    if want in names:
        return os.path.join(d, want)
    return os.path.join(d, names[0]) if len(names) == 1 else None


def activate_draft(m, name: str):
    """Switch the active draft back to a previously-snapshotted one."""
    d = draft_dir(m, name)
    parsed_src = os.path.join(d, "parsed.json")
    if not os.path.exists(parsed_src):
        raise ValueError(f"No snapshot for draft '{name}'.")
    # Read the stage record BEFORE anything is touched (gap 64). A damaged
    # sidecar must refuse the switch, not switch first and apologise after: by
    # the time the bundle has been restored the writer is already on the other
    # draft, and "restored, but I don't know if it is parsed" is a worse place
    # to leave them than "not switched".
    stage_record = load_snapshot_stage(d)

    # preserve the current state first (so switching is never destructive)
    snapshot_active(m, m.active_draft or "original")

    # find this draft's source filename from the manifest record
    source_filename = m.source_filename
    for rec in m.drafts:
        if rec["name"] == name:
            source_filename = rec["source_filename"]
            break

    # Copy FIRST, swap SECOND, exactly as `upload_new_draft` does. The active
    # source used to be removed before anything was restored, so either a copy
    # that failed (a Windows sharing violation is routine) or a snapshot whose
    # source sits under a name this function never looked for left the project
    # with no script file at all — while parsed.json restored cleanly, so the
    # writer saw a healthy draft with nothing behind it.
    snap_src = _snapshot_source(m, name, source_filename)
    previous_source = m.source_path
    m.active_draft = name
    if snap_src:
        m.source_filename = source_filename
        m.source_format = os.path.splitext(snap_src)[1].lower()
        incoming = m.source_path + ".incoming"
        shutil.copy2(snap_src, incoming)
        os.replace(incoming, m.source_path)
        if m.source_path != previous_source and os.path.exists(previous_source):
            os.remove(previous_source)  # the two drafts use different formats
    # No source in the snapshot at all: keep the current file. It belongs to the
    # draft being left, which is wrong, but the writer's copy is unrecoverable
    # and a stale source can be re-uploaded.

    # Restore the WHOLE bundle, not just the parse and the report pair (gap 63):
    # a member the snapshot lacks is REMOVED from the live project rather than
    # left behind, because a file that survives a switch is a claim about the
    # draft the writer is now looking at, and a draft that was never analyzed
    # has no report, no graph and no finding marks to inherit. The outgoing
    # draft keeps its own copy in this snapshot, taken above.
    for live, rel in _bundle_files(m):
        src = os.path.join(d, rel)
        if os.path.exists(src):
            shutil.copy2(src, live)
        elif os.path.exists(live):
            os.remove(live)

    _reset_derived_state(m)
    # ...and put THIS draft's edits back, if it had any. After
    # `_reset_derived_state` so the reset can never race the restore.
    restore_edit_cycle(m, name)
    # The parse stage comes back with the parse (gap 64). Without this the
    # restored draft carried the FAILED status of whatever upload was rejected
    # since, so `/script` refused a draft whose parsed.json was sitting right
    # there. A snapshot with no stage record predates this file: fall back to
    # what the restored files support rather than guessing `complete`.
    restored_stage = stage_record
    if restored_stage is None:
        # No record: either the snapshot predates the sidecar or the draft was
        # never parsed. parsed.json is restored by the loop above, and the
        # parse stage's own contract is that it is `complete` exactly when that
        # file exists — so fall back to the file rather than leaving a stale
        # status from whatever ran last.
        restored_stage = "complete" if os.path.exists(m.parsed_path) else None
    if restored_stage:
        m.stages["parse"] = StageStatus(status=restored_stage, output_paths={
            "parsed": m.parsed_path, "kg": m.kg_path,
        })
    if os.path.exists(m.report_findings_path):
        m.stages["analyze"] = StageStatus(status="complete", output_paths={
            "report_md": m.report_md_path, "report_findings": m.report_findings_path,
        })
    m.save()
    return m


# ---------- structural diff ----------

def _element_signature(scene) -> list:
    return [(e.type.value, e.text) for e in scene.elements]


def _changed_lines(old_els, new_els) -> list[dict]:
    """Approximate line-level changes between two scenes' element lists."""
    old_sig = [(e.type.value, e.text) for e in old_els]
    new_sig = [(e.type.value, e.text) for e in new_els]
    sm = SequenceMatcher(None, old_sig, new_sig)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        for k in range(max(i2 - i1, j2 - j1)):
            old_txt = old_els[i1 + k].text if i1 + k < i2 else None
            new_txt = new_els[j1 + k].text if j1 + k < j2 else None
            if old_txt != new_txt:
                out.append({"old": old_txt, "new": new_txt})
    return out


def diff_scenes(old_doc: ScriptDocument, new_doc: ScriptDocument) -> dict:
    old_by_num = {s.scene_number: s for s in old_doc.scenes}
    new_by_num = {s.scene_number: s for s in new_doc.scenes}
    common = sorted(set(old_by_num) & set(new_by_num))

    changed = []
    for n in common:
        old_s, new_s = old_by_num[n], new_by_num[n]
        if _element_signature(old_s) == _element_signature(new_s) and old_s.heading_raw == new_s.heading_raw:
            continue
        changed.append({
            "scene_number": n,
            "heading": new_s.heading_raw,
            "old_heading": old_s.heading_raw,
            "changed_lines": _changed_lines(old_s.elements, new_s.elements),
        })

    return {
        "added_scenes": [new_by_num[n].scene_number for n in sorted(new_by_num) if n not in old_by_num],
        "removed_scenes": [old_by_num[n].scene_number for n in sorted(old_by_num) if n not in new_by_num],
        "changed_scenes": changed,
        "unchanged_scene_count": len(common) - len(changed),
    }


# ---------- findings diff ----------

def _load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _issue_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def diff_findings(old_report: dict, new_doc: ScriptDocument, new_report: dict) -> dict:
    old_findings = (old_report or {}).get("findings", [])
    new_findings = (new_report or {}).get("findings", [])

    resolved, still_present = [], []
    for f in old_findings:
        quote = f.get("evidence_quote")
        if not quote:
            continue  # no quote -> can't auto-check; not counted either way
        status = "resolved" if not quote_present(new_doc, quote) else "still_present"
        entry = dict(f)
        entry["draft_status"] = status
        (resolved if status == "resolved" else still_present).append(entry)

    carried, new_ones = [], []
    for f in new_findings:
        best = max((_issue_similarity(f.get("issue", ""), g.get("issue", "")) for g in old_findings), default=0.0)
        if best >= 0.7:
            entry = dict(f)
            entry["draft_status"] = "carried"
            carried.append(entry)
        else:
            entry = dict(f)
            entry["draft_status"] = "new"
            new_ones.append(entry)

    return {
        "resolved": resolved,
        "still_present": still_present,
        "carried": carried,
        "new": new_ones,
        "summary": {
            "resolved": len(resolved),
            "still_present": len(still_present),
            "carried": len(carried),
            "new": len(new_ones),
        },
    }


def compare_drafts(m, from_name: str, to_name: str) -> dict:
    """Side-by-side material: per common scene, the element lists of both
    drafts aligned by difflib into rows tagged same/changed/added/removed.
    The UI renders two columns from these rows."""
    old_doc = _baseline_doc(m, from_name)
    new_doc = _baseline_doc(m, to_name)
    old_by_num = {s.scene_number: s for s in old_doc.scenes}
    new_by_num = {s.scene_number: s for s in new_doc.scenes}
    common = sorted(set(old_by_num) & set(new_by_num))

    scenes = []
    for n in common:
        old_s, new_s = old_by_num[n], new_by_num[n]
        old_lines = [(e.type.value, e.text) for e in old_s.elements]
        new_lines = [(e.type.value, e.text) for e in new_s.elements]
        sm = SequenceMatcher(None, old_lines, new_lines)
        rows = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(i2 - i1):
                    rows.append({"kind": "same", "left": old_lines[i1 + k][1], "right": new_lines[j1 + k][1], "type": old_lines[i1 + k][0]})
            elif tag == "replace":
                for k in range(max(i2 - i1, j2 - j1)):
                    rows.append({
                        "kind": "changed",
                        "left": old_lines[i1 + k][1] if i1 + k < i2 else None,
                        "right": new_lines[j1 + k][1] if j1 + k < j2 else None,
                        "type": (old_lines[i1 + k][0] if i1 + k < i2 else new_lines[j1 + k][0]),
                    })
            elif tag == "delete":
                for k in range(i2 - i1):
                    rows.append({"kind": "removed", "left": old_lines[i1 + k][1], "right": None, "type": old_lines[i1 + k][0]})
            elif tag == "insert":
                for k in range(j2 - j1):
                    rows.append({"kind": "added", "left": None, "right": new_lines[j1 + k][1], "type": new_lines[j1 + k][0]})
        scenes.append({"scene_number": n, "heading": new_s.heading_raw, "rows": rows})

    return {
        "from": from_name,
        "to": to_name or "active",
        "scenes": scenes,
        "common_scene_count": len(common),
    }


def diff_drafts(m, from_name: str, to_name: str) -> dict:
    """Full diff between two drafts. to_name='active' (or None) means the
    currently active draft (root parsed.json / report)."""
    old_doc = _baseline_doc(m, from_name)
    new_doc = _baseline_doc(m, to_name)
    old_report = _load_json(draft_report_path(m, from_name))
    new_report = _load_json(m.report_findings_path if (to_name in (None, "active")) else draft_report_path(m, to_name))

    return {
        "from": from_name,
        "to": to_name or "active",
        "scenes": diff_scenes(old_doc, new_doc),
        "findings": diff_findings(old_report, new_doc, new_report),
        "characters": _character_presence_diff(old_doc, new_doc),
    }


def _baseline_doc(m, name: str) -> ScriptDocument:
    """Load a draft's parsed doc: 'original' or a snapshotted draft name from
    its snapshot dir; None/'active' from the root parsed.json."""
    if name in (None, "active"):
        return ScriptDocument.load(m.parsed_path)
    if name == "original":
        path = os.path.join(draft_dir(m, "original"), "parsed.json")
    else:
        path = draft_parsed_path(m, name)
    if not os.path.exists(path):
        raise ValueError(f"No parsed snapshot for draft '{name}'.")
    return ScriptDocument.load(path)


def _character_presence_diff(old_doc: ScriptDocument, new_doc: ScriptDocument) -> list:
    old_presence = {c: s for c, s in _presence_map(old_doc).items()}
    new_presence = _presence_map(new_doc)
    out = []
    for name in sorted(set(old_presence) | set(new_presence)):
        old_scenes = old_presence.get(name, [])
        new_scenes = new_presence.get(name, [])
        if old_scenes != new_scenes:
            out.append({
                "character": name,
                "old_scene_count": len(old_scenes),
                "new_scene_count": len(new_scenes),
                "added_scenes": [n for n in new_scenes if n not in old_scenes],
                "removed_scenes": [n for n in old_scenes if n not in new_scenes],
            })
    return out


def _presence_map(doc: ScriptDocument) -> dict:
    m = {}
    for scene in doc.scenes:
        for c in scene.characters_present:
            m.setdefault(c, []).append(scene.scene_number)
    return m
