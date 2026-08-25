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

from .manifest import StageStatus
from .revision import reset_working, quote_present


def drafts_dir(m) -> str:
    return os.path.join(m.project_dir, "drafts")


def draft_dir(m, name: str) -> str:
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
    if m.stage("parse").status != "complete":
        return  # nothing parsed to snapshot
    dst = draft_dir(m, name)
    os.makedirs(dst, exist_ok=True)
    for src, rel in (
        (m.source_path, os.path.basename(m.source_path)),
        (m.parsed_path, "parsed.json"),
        (m.report_findings_path, "report.findings.json"),
        (m.report_md_path, "report.md"),
    ):
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dst, rel))


def _reset_derived_state(m) -> None:
    """After swapping the active draft: discard edits, re-queue analysis."""
    reset_working(m)
    m.stages["analyze"] = StageStatus()
    m.stages["chat"] = StageStatus()


def upload_new_draft(m, uploaded_path: str, filename: str):
    """Snapshot the current active draft, then make the upload the active one.

    The original upload is implicit (not in m.drafts); every subsequent upload
    gets an auto-named draft entry. Returns the manifest (mutated + saved).
    """
    if m.stage("parse").status == "complete":
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


def activate_draft(m, name: str):
    """Switch the active draft back to a previously-snapshotted one."""
    d = draft_dir(m, name)
    parsed_src = os.path.join(d, "parsed.json")
    if not os.path.exists(parsed_src):
        raise ValueError(f"No snapshot for draft '{name}'.")

    # preserve the current state first (so switching is never destructive)
    if m.stage("parse").status == "complete":
        snapshot_active(m, m.active_draft or "original")

    # find this draft's source filename from the manifest record
    source_filename = m.source_filename
    for rec in m.drafts:
        if rec["name"] == name:
            source_filename = rec["source_filename"]
            break

    old_source = m.source_path
    if os.path.exists(old_source):
        os.remove(old_source)
    m.source_filename = source_filename
    m.source_format = os.path.splitext(source_filename)[1].lower()
    m.active_draft = name

    # copy the snapshot's files back to the active positions
    report_src = os.path.join(d, "report.findings.json")
    report_md_src = os.path.join(d, "report.md")
    for target, src in (
        (m.source_path, os.path.join(d, os.path.basename(source_filename) or "source" + m.source_format_ext)),
        (m.parsed_path, parsed_src),
        (m.report_findings_path, report_src),
        (m.report_md_path, report_md_src),
    ):
        if os.path.exists(src):
            shutil.copy2(src, target)
        elif os.path.exists(target):
            os.remove(target)

    _reset_derived_state(m)
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
