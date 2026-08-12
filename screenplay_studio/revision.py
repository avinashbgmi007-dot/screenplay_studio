"""
The revision loop — findings -> suggested rewrites -> apply -> export.

This is the layer that turns Script Doctor Studio from a report-reader into
an editor. The original parse (parsed.json) is never touched: edits land in
a *working copy* (working.json), and every export / re-verification / chat
context read goes through the working copy so the writer always discusses
the current state of their draft, not the stale original.

Flow (all model calls go through the analyzer's grammar-constrained JSON
client so the shape is reliable):

    GET  /script                 -> working copy (ScriptDocument JSON)
    POST /rewrite                -> model proposes targeted line replacements
                                     (NOT applied yet — the writer reviews)
    POST /edits/apply            -> apply reviewed replacements to working copy
    GET  /edits                  -> applied edits + finding-resolution status
    POST /edits/reset            -> discard all edits, back to the original parse
    GET  /export?format=...      -> export working copy to fountain/fdx/txt
"""

from __future__ import annotations

import json
import os
import time
import uuid
from difflib import SequenceMatcher

from screenplay_parser.models import ScriptDocument


def working_path(m) -> str:
    return os.path.join(m.project_dir, "working.json")


def edits_log_path(m) -> str:
    return os.path.join(m.project_dir, "edits.json")


def edits_redo_path(m) -> str:
    return os.path.join(m.project_dir, "edits.redo.json")


def ensure_working(m) -> str:
    """Create the working copy from the parsed document on first use."""
    path = working_path(m)
    if not os.path.exists(path):
        if not os.path.exists(m.parsed_path):
            raise FileNotFoundError(
                f"Project has no parsed script ('{m.parsed_path}') — run parse first."
            )
        with open(m.parsed_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def load_working(m) -> ScriptDocument:
    return ScriptDocument.load(ensure_working(m))


def save_working(m, doc: ScriptDocument, record: dict | None = None) -> None:
    doc.save(working_path(m))
    if record:
        log = edits_log(m)
        if "id" not in record:
            record["id"] = uuid.uuid4().hex[:12]
        log.append(record)
        with open(edits_log_path(m), "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2, ensure_ascii=False)
        # a fresh edit invalidates any redo history
        clear_redo(m)


def has_edits(m) -> bool:
    """True once any edit has been applied (working copy may exist just from
    viewing the script — that alone doesn't count as edits)."""
    if not os.path.exists(edits_log_path(m)):
        return False
    try:
        with open(edits_log_path(m), "r", encoding="utf-8") as f:
            return len(json.load(f)) > 0
    except (json.JSONDecodeError, OSError):
        return False


def reset_working(m) -> None:
    for path in (working_path(m), edits_log_path(m), edits_redo_path(m)):
        if os.path.exists(path):
            os.remove(path)


def _load_json_list(path: str) -> list:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_json_list(path: str, data: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def redo_stack(m) -> list[dict]:
    return _load_json_list(edits_redo_path(m))


def clear_redo(m) -> None:
    if os.path.exists(edits_redo_path(m)):
        os.remove(edits_redo_path(m))


def _replace_in_scene(doc: ScriptDocument, scene_number: int, from_text: str, to_text: str):
    """Find the element currently equal to from_text in the scene and set it
    to to_text. Exact match only — undo/redo must never fuzzy-guess.
    Returns True on success."""
    elements = scene_elements(doc, scene_number)
    exact = [el for el in elements if el.text == from_text]
    if len(exact) == 1:
        exact[0].text = to_text
        return True
    return False


def undo_last_edit(m) -> dict:
    """Reverse the most recent applied edit group (new -> old). The record
    moves from the undo log to the redo stack. Returns a summary dict."""
    log = edits_log(m)
    if not log:
        raise ValueError("Nothing to undo.")
    record = log[-1]
    doc = load_working(m)
    restored, failed = [], []
    for rep in record.get("applied", []):
        old_text, new_text = rep["old"], rep["new"]
        if _replace_in_scene(doc, record["scene_number"], new_text, old_text):
            restored.append({"old": new_text, "new": old_text})
        else:
            failed.append({"old": new_text, "new": old_text})
    doc.save(working_path(m))
    # move the record: undo log -> redo stack
    log.pop()
    _save_json_list(edits_log_path(m), log)
    redo = redo_stack(m)
    redo.append(record)
    _save_json_list(edits_redo_path(m), redo)
    return {
        "undone": record,
        "restored": restored,
        "failed": failed,
        "can_undo": bool(log),
        "can_redo": True,
    }


def redo_last_edit(m) -> dict:
    """Re-apply the most recently undone edit group (old -> new). The record
    moves from the redo stack back onto the undo log."""
    redo = redo_stack(m)
    if not redo:
        raise ValueError("Nothing to redo.")
    record = redo[-1]
    doc = load_working(m)
    applied, failed = [], []
    for rep in record.get("applied", []):
        old_text, new_text = rep["old"], rep["new"]
        if _replace_in_scene(doc, record["scene_number"], old_text, new_text):
            applied.append({"old": old_text, "new": new_text})
        else:
            failed.append({"old": old_text, "new": new_text})
    doc.save(working_path(m))
    redo.pop()
    _save_json_list(edits_redo_path(m), redo)
    log = edits_log(m)
    log.append(record)
    _save_json_list(edits_log_path(m), log)
    return {
        "redone": record,
        "applied": applied,
        "failed": failed,
        "can_undo": True,
        "can_redo": bool(redo),
    }


def edits_log(m) -> list[dict]:
    if not os.path.exists(edits_log_path(m)):
        return []
    with open(edits_log_path(m), "r", encoding="utf-8") as f:
        return json.load(f)


def scene_elements(doc: ScriptDocument, scene_number: int) -> list:
    for s in doc.scenes:
        if s.scene_number == scene_number:
            return s.elements
    raise ValueError(f"Scene {scene_number} not found in script.")


def scene_text(doc: ScriptDocument, scene_number: int) -> str:
    lines = []
    for s in doc.scenes:
        if s.scene_number == scene_number:
            lines.append(f"[Scene {s.scene_number} — {s.heading_raw}]")
            for el in s.elements:
                lines.append(el.text)
            return "\n".join(lines)
    raise ValueError(f"Scene {scene_number} not found in script.")


def _match_element(elements: list, old_text: str):
    """Find the element whose text should be replaced by `old_text`.

    Exact match first; then a unique fuzzy match above 0.8 similarity.
    Returns (element, similarity) or (None, 0) if ambiguous / not found.
    """
    stripped = old_text.strip()
    if not stripped:
        return None, 0

    exact = [el for el in elements if el.text == stripped]
    if len(exact) == 1:
        return exact[0], 1.0
    if len(exact) > 1:
        return None, 0  # ambiguous — several identical lines; require disambiguation

    best, best_ratio = None, 0.0
    for el in elements:
        ratio = SequenceMatcher(None, el.text, stripped).ratio()
        if ratio > best_ratio:
            best, best_ratio = el, ratio
    if best is not None and best_ratio >= 0.8:
        return best, best_ratio
    return None, 0


def apply_replacements(doc: ScriptDocument, scene_number: int, replacements: list[dict]) -> dict:
    """Apply [{old, new}] line replacements to one scene of the working copy.

    Returns {applied: [{old, new}], skipped: [{old, new, reason}]}. Replacements
    are applied in order; a skipped replacement is never partially applied.
    """
    elements = scene_elements(doc, scene_number)
    applied, skipped = [], []
    for rep in replacements or []:
        old_text = (rep.get("old") or "").strip()
        new_text = (rep.get("new") or "").strip()
        if not old_text:
            skipped.append({"old": "", "new": new_text, "reason": "empty old line"})
            continue
        if "\n" in old_text:
            skipped.append({"old": old_text, "new": new_text, "reason": "old spans multiple lines"})
            continue
        el, ratio = _match_element(elements, old_text)
        if el is None:
            reason = "no exact match, and multiple identical lines" if ratio == 0 and any(
                e.text == old_text for e in elements
            ) else "line not found in scene"
            skipped.append({"old": old_text, "new": new_text, "reason": reason})
            continue
        el.text = new_text
        applied.append({"old": old_text, "new": new_text, "similarity": round(ratio, 3)})
    return {"applied": applied, "skipped": skipped}


def rewrite_scene(client, doc: ScriptDocument, scene_number: int, finding_text: str = "", instruction: str = "") -> dict:
    """Ask the model to propose targeted line replacements for one scene.

    Returns the raw parsed JSON: {replacements: [{old, new}], note}. Nothing
    is applied here — the writer reviews the candidates first.
    """
    from screenplay_analyzer.grammar import replacements_grammar

    scene = scene_text(doc, scene_number)
    system = (
        "You are a script doctor proposing a targeted revision. You will be given "
        "one scene's full text and a note about it. Return JSON with a list of "
        "line replacements and a short note explaining the change.\n\n"
        "RULES:\n"
        "- 'old' must match exactly one existing line in the scene (verbatim, "
        "character-for-character — copy it from the scene text).\n"
        "- Only include lines that actually change. Keep every other line out.\n"
        "- Preserve the speaker's voice, the scene's function, and the screenplay "
        "formatting (do not add scene headings, cues, or parentheticals unless "
        "replacing ones that exist).\n"
        "- Replace dialogue with dialogue and action with action. Do not merge or "
        "split lines; each replacement is one line for one line.\n"
        "- If the scene is already fine, return an empty replacements list."
    )
    user = f"FINDING / NOTE:\n{finding_text or '(no specific note — general polish)'}\n"
    if instruction:
        user += f"\nWRITER'S INSTRUCTION:\n{instruction}\n"
    user += f"\nSCENE TEXT:\n{scene}\n"

    return client.chat_json(system, user, grammar=replacements_grammar(), max_tokens=1500)


def quote_present(doc: ScriptDocument, quote: str | None) -> bool:
    """Is a finding's evidence quote still present in the working copy?

    Exact substring match first; then near-verbatim fuzzy (>= 0.95). The
    threshold is deliberately strict: a line that was edited at all (even a
    word changed) should count as 'addressed', not 'still present'."""
    if not quote or not quote.strip():
        return False
    target = quote.strip()
    all_texts = [el.text for s in doc.scenes for el in s.elements]
    if any(target in t for t in all_texts):
        return True
    return any(
        SequenceMatcher(None, t, target).ratio() >= 0.95
        for t in all_texts
        if t
    )


def finding_statuses(m) -> dict:
    """Which findings are still live in the working copy vs. addressed by edits.

    A finding is 'addressed' when its evidence quote can no longer be found in
    the edited script (the problematic line was changed or removed). Findings
    with no quote can't be auto-checked and are reported as 'unknown'.
    """
    try:
        with open(m.report_findings_path, "r", encoding="utf-8") as f:
            report = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"findings": [], "summary": {"addressed": 0, "still_present": 0, "unknown": 0}}

    doc = load_working(m)
    statuses = []
    for idx, f in enumerate(report.get("findings", [])):
        quote = f.get("evidence_quote")
        if not quote:
            statuses.append({"index": idx, "category": f.get("category"), "status": "unknown"})
        elif quote_present(doc, quote):
            statuses.append({"index": idx, "category": f.get("category"), "status": "still_present"})
        else:
            statuses.append({"index": idx, "category": f.get("category"), "status": "addressed"})

    summary = {"addressed": 0, "still_present": 0, "unknown": 0}
    for s in statuses:
        summary[s["status"]] += 1
    return {"findings": statuses, "summary": summary, "checked_at": time.time()}
