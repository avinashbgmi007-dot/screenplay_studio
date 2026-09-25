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

import hashlib
import json
import os
import time
import uuid
from difflib import SequenceMatcher

from screenplay_parser import quotematch
from screenplay_parser.models import ScriptDocument


# ---------- content-hash finding identity (R1 refined) ----------
# A finding's identity is its content, not its position in the report array.
# Key = category + evidence_quote (the quote is verified against script text,
# so it is the stable anchor); scene_refs ride as DATA — they renumber when
# the writer inserts a scene and must NOT orphan the writer's marks.
# Severity is a judgment about a note, not its identity — re-scoring keeps
# the id. Reasoning-only findings (no quote) key on category + normalized
# issue text (documented weak tier: drift re-classifies honestly on the
# next pass).
# The JS twin lives in webapp/app.js (computeFindingId + _strHash) — the
# server observes, the client displays; both MUST produce the same id.
_BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def _base36(h: int) -> str:
    if h == 0:
        return "0"
    out = ""
    while h:
        out = _BASE36[h % 36] + out
        h //= 36
    return out


def _str_hash(s: str) -> int:
    h = 5381
    for ch in s:
        h = ((h << 5) + h + ord(ch)) & 0xFFFFFFFF
    return h


def compute_finding_id(f: dict) -> str:
    quote = (f.get("evidence_quote") or "").strip()
    if quote:
        norm = quote
    else:
        norm = "issue:" + " ".join((f.get("issue") or "").lower().split())[:100]
    return "f" + _base36(_str_hash((f.get("category") or "other") + "|" + norm))


def dismissed_finding_ids(m) -> set:
    """Set of finding_ids currently dismissed for this project (legacy
    entries that never carried an id simply don't appear here).

    Missing -> empty set; DAMAGED -> StoreUnreadable. The lenient version read a
    torn triage file as "nothing dismissed", so every finding the writer had
    cleared came back, and the next dismiss overwrote the damaged file.
    """
    from .jsonio import StoreUnreadable, load_json_store
    path = dismissed_path(m)
    data = load_json_store(path, default=[])
    if not isinstance(data, list):
        raise StoreUnreadable(path, f"expected a list, found {type(data).__name__}")
    return {d["finding_id"] for d in data
            if isinstance(d, dict) and d.get("finding_id")}


# ---------- writer intent (R2-b mark-addressed + R3 defer) ----------
# ONE store for the writer's own judgment, keyed by content-hash id so it
# survives report regeneration. Observed status (quote gone from the text)
# still wins display; intent is the writer's call on everything else.
def finding_marks_path(m) -> str:
    return os.path.join(m.project_dir, "finding_marks.json")


def finding_intents(m) -> dict:
    """{finding_id: "addressed" | "deferred"} — the writer's intent marks.

    Missing -> {} ; damaged -> StoreUnreadable. The lenient version dropped every
    mark the writer had made (they silently reappeared as open findings) and the
    next mark then overwrote the damaged file.
    """
    from .jsonio import StoreUnreadable, load_json_store
    path = finding_marks_path(m)
    data = load_json_store(path, default={})
    if not isinstance(data, dict):
        raise StoreUnreadable(path, f"expected an object, found {type(data).__name__}")
    return {k: v for k, v in data.items() if v in ("addressed", "deferred")}


def set_finding_intent(m, finding_id: str, intent) -> None:
    from .jsonio import StoreUnreadable, load_json_store, lock_for
    path = finding_marks_path(m)
    # The lock spans the READ as well as the write. Without it two marks made at
    # once (two tabs, or the CLI and the webapp) each load the pre-mark store,
    # and the second write drops the first mark. Reproduced across 4 processes:
    # 800 attempts, 9 successes, finding_marks.json unparseable at rest.
    with lock_for(path):
        data = load_json_store(path, default={})   # damaged -> raises: no mark is
        if not isinstance(data, dict):             # written over a damaged store
            raise StoreUnreadable(path, "expected an object")
        if intent in ("addressed", "deferred"):
            data[finding_id] = intent
        else:
            data.pop(finding_id, None)
        from .jsonio import atomic_write_json
        atomic_write_json(path, data)


# ---------- last-pass scorekeeping (R4, one generation back) ----------
def last_pass_path(m) -> str:
    return os.path.join(m.project_dir, "last_pass.json")


def _report_signature(report: dict) -> str:
    """Cheap content fingerprint of a findings report.

    The mtime guard alone is not sound: a report written twice within one
    filesystem timestamp tick (a fast re-analyze, or a test that rewrites in
    the same tick) keeps the same mtime, so the guard would serve the STALE
    payload — reporting `None` (first-pass) after arithmetic already exists,
    or stale Fixed/New numbers. Pairing the mtime with a content hash closes
    that hole without re-reading the report on every GET.
    """
    findings = report.get("findings", [])
    h = hashlib.sha1()
    for f in findings:
        h.update(compute_finding_id(f).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _parsed_signature(m):
    """Content fingerprint of the analyzer INPUT (the parse-of-record).

    The pass arithmetic compares two analysis passes. Different scripts mean a
    real draft-over-draft delta. Byte-identical input means every id that moved
    is the model re-wording its own sentence: the no-quote tier (about 75% of
    findings) hashes model prose, so a no-op re-analysis churns ~88% of ids on
    gun_pen_2. Returns None when the parse is unreadable (the gate then stays
    open rather than inventing a "nothing changed" verdict on no evidence).

    The report language rides along: it is part of the ask, so switching it is a
    real change of input, not writer progress. The model id deliberately does not:
    it is resolved per run and would make the fingerprint flicker.
    """
    try:
        with open(m.parsed_path, "rb") as f:
            body = f.read()
    except OSError:
        return None
    h = hashlib.sha1()
    h.update(body)
    h.update(bytes([0]))
    h.update((getattr(m, "report_language", "") or "").encode("utf-8"))
    return h.hexdigest()


def last_pass_snapshot(m):
    """Diff this pass against the previous one: {last_total, still_live,
    fixed, new, ghosted_marks}. Computed lazily with an mtime+sig guard so
    repeated GETs are idempotent; one generation back (boring is good).
    Returns None on the first pass (no arithmetic yet — honest).

    Identity is DISTINCT finding ids (compute_finding_id can collide —
    e.g. two dialogue findings quoting the same line). Duplicate ids in
    either pass are ONE finding for arithmetic: a re-analysis that
    changes nothing must report fixed=0/new=0, never manufacture
    phantom progress out of duplicate rows.

    GAP-7 gate: two passes are only read as draft-over-draft movement when the
    analyzer INPUT moved. On identical input the no-quote tier re-words itself,
    so the payload reports fixed=0, new=0, same_input=True and discloses the
    movement as `rewritten` — the model re-worded its findings, the writer
    did not move.

    On that identical-input path `last_total` is the report the desk is HOLDING
    (rows), not the previous pass's count: there is no delta to draw, and the
    strip headline has to agree with the board it sits under. Measured on
    gun_pen_2: one script, two runs, 36 findings then 22, so a "Pass: 36"
    headline over a 22-row board is the UI contradicting itself. The previous
    total is kept in `prev_total` for the re-wording clause. On a real diff
    `last_total` keeps its original meaning: the previous pass's distinct count.
    """
    report_path = m.report_findings_path if m.stage("analyze").status == "complete" else None
    if not report_path or not os.path.exists(report_path):
        return None
    rp_mtime = os.path.getmtime(report_path)
    snap = None
    try:
        with open(last_pass_path(m), "r", encoding="utf-8") as f:
            snap = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError):
        snap = None
    # The guard is (mtime, content signature): a same-tick rewrite changes the
    # signature even when the mtime cannot. Legacy snapshots without a sig
    # simply recompute once and gain one.
    snap_sig = snap.get("report_sig") if isinstance(snap, dict) else None
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    report_sig = _report_signature(report)
    if snap and snap.get("report_mtime") == rp_mtime and snap_sig == report_sig:
        if isinstance(snap, dict) and snap.get("parsed_sig") is None:
            # Legacy snapshot (written before the GAP-7 gate). Stamp the input
            # this pass ran on, once, so the NEXT comparison is gated instead of
            # granting every old project a free pass. No arithmetic here.
            snap["parsed_sig"] = _parsed_signature(m)
            try:
                from .jsonio import atomic_write_json
                atomic_write_json(last_pass_path(m), snap)
            except OSError:
                pass  # an unwritable snapshot must never break the edits fetch
        return snap.get("payload")
    # fingerprint the input only when a recompute is actually happening, so the
    # cached path never pays for a file read
    parsed_sig = _parsed_signature(m)
    findings = report.get("findings", [])
    new_ids = [compute_finding_id(f) for f in findings]
    issues = {compute_finding_id(f): (f.get("issue") or "") for f in findings}
    payload = None
    if snap and isinstance(snap.get("ids"), list):
        old_ids = [gid for gid in dict.fromkeys(snap["ids"])]  # distinct, order kept
        old_set, new_set = set(old_ids), set(new_ids)
        still = old_set & new_set
        intents = finding_intents(m)
        # A legacy snapshot carries no parsed_sig, so it cannot answer "did the
        # input move?". It keeps the old arithmetic for exactly one pass and gets
        # stamped below; every comparison after that is gated.
        same_input = bool(parsed_sig) and snap.get("parsed_sig") == parsed_sig
        if same_input:
            # Byte-identical script: nothing was fixed and nothing is new. The id
            # churn is the model re-wording itself — disclose it as such, and
            # never as writer progress or as a vanished mark.
            payload = {
                "computed_at": time.time(),
                # the desk's own total: identical input means the previous
                # pass's count is not what the writer is looking at
                "last_total": len(new_ids),
                "still_live": len(new_ids),
                "fixed": 0,
                "new": 0,
                "same_input": True,
                "rewritten": len(old_set - new_set),
                "prev_total": len(old_set),
                "ghosted_marks": [],
            }
        else:
            payload = {
                "computed_at": time.time(),
                "last_total": len(old_set),
                "still_live": len(still),
                "fixed": len(old_set) - len(still),
                "new": len(new_set) - len(still),
                "same_input": False,
                "rewritten": 0,
                "ghosted_marks": [
                    {"finding_id": gid, "issue": (snap.get("issues") or {}).get(gid, ""),
                     "intent": intents.get(gid)}
                    for gid in old_ids if gid not in new_set and intents.get(gid)
                ][:50],
            }
    from .jsonio import atomic_write_json
    atomic_write_json(last_pass_path(m), {"ids": [gid for gid in dict.fromkeys(new_ids)], "issues": issues,
                 "report_mtime": rp_mtime, "report_sig": report_sig,
                 "parsed_sig": parsed_sig, "payload": payload})
    return payload


def working_path(m) -> str:
    return os.path.join(m.project_dir, "working.json")


def edits_log_path(m) -> str:
    return os.path.join(m.project_dir, "edits.json")


def edits_redo_path(m) -> str:
    return os.path.join(m.project_dir, "edits.redo.json")


def ensure_working(m) -> str:
    """Create the working copy from the parsed document on first use.

    Also self-heals a stale copy: when the source parse has been regenerated
    (a re-parse, e.g. after a parser fix or a new draft upload) and the writer
    has NOT applied any edits, the working copy is rebuilt from the fresh
    parse so the viewer/chat never show outdated classification. If the writer
    HAS edits, their work is never overwritten silently."""
    path = working_path(m)
    if not os.path.exists(path):
        if not os.path.exists(m.parsed_path):
            raise FileNotFoundError(
                f"Project has no parsed script ('{m.parsed_path}') — run parse first."
            )
        with open(m.parsed_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        from .jsonio import atomic_write_json
        atomic_write_json(path, data)
        return path

    # re-parse refreshes the display copy when there's nothing to preserve
    if not has_edits(m) and os.path.exists(m.parsed_path):
        try:
            if os.path.getmtime(m.parsed_path) > os.path.getmtime(path):
                with open(m.parsed_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                from .jsonio import atomic_write_json
                atomic_write_json(path, data)
        except (OSError, ValueError):
            pass  # if the timestamps/parse are unreadable, keep the existing copy
    return path


def load_working(m) -> ScriptDocument:
    return ScriptDocument.load(ensure_working(m))


def save_working(m, doc: ScriptDocument, record: dict | None = None) -> None:
    doc.save(working_path(m))
    if record:
        from .jsonio import atomic_write_json, lock_for
        log_path = edits_log_path(m)
        # Locked across the read+append+write — the edit log is an accumulate
        # store, so an unlocked cycle loses entries (measured: 150 kept of 508
        # applied). Deliberately NOT wrapped around doc.save() above: that
        # writes working.json, a SECOND store, and holding two store locks at
        # once is the one thing jsonio.lock_for must never be asked to do.
        with lock_for(log_path):
            log = edits_log(m)
            if "id" not in record:
                record["id"] = uuid.uuid4().hex[:12]
            log.append(record)
            atomic_write_json(log_path, log)
        # a fresh edit invalidates any redo history
        clear_redo(m)


def has_edits(m) -> bool:
    """True once any edit has been applied (working copy may exist just from
    viewing the script — that alone doesn't count as edits).

    A1 (audit 2026-09-20): a truncated/corrupt edit log must NEVER read as
    "no edits" — that lets ensure_working() overwrite working.json (the only
    copy of applied edits) with the pre-edit parse. A decode failure or a
    transient read failure (WinError 32) is treated as edits-present, so the
    working copy is preserved until the log can be repaired.
    """
    path = edits_log_path(m)
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            return len(json.load(f)) > 0
    except json.JSONDecodeError:
        return True  # corrupt log ≠ empty log — preserve the working copy
    except OSError:
        return True  # transient read failure ≠ empty log — same reasoning


def reset_working(m) -> None:
    for path in (working_path(m), edits_log_path(m), edits_redo_path(m)):
        if os.path.exists(path):
            os.remove(path)


def _load_json_list(path: str) -> list:
    """Read a list-shaped store: MISSING -> `[]`, PRESENT-BUT-UNREADABLE -> raise.

    BE-M1. This used to answer `[]` for a corrupt file, collapsing "damaged"
    into "empty" — the A2/A3 shape, on the redo stack, where it has a sting: the
    writer was told "Nothing to redo" about a stack that was sitting right there,
    and `undo_last_edit`'s load-modify-write then appended to that phantom empty
    list and overwrote the only recoverable copy.

    Shape checking stays with the caller (as `jsonio.load_json_store` documents):
    a dict where a list belongs is just as damaged as a torn file.
    """
    from .jsonio import StoreUnreadable, load_json_store
    data = load_json_store(path, [])
    if not isinstance(data, list):
        raise StoreUnreadable(path, f"expected a list, found {type(data).__name__}")
    return data


def _save_json_list(path: str, data: list) -> None:
    from .jsonio import atomic_write_json
    atomic_write_json(path, data)


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
    moves from the undo log to the redo stack. Returns a summary dict.

    H5 (re-audit 2026-09-24): the log is an accumulate store like every other
    one, so its read-modify-write happens UNDER `lock_for(edits.json)`. It used
    to hold no lock at all, which erased the record of an edit applied while the
    undo was in flight — the text stayed in working.json, the record did not, and
    the writer could never undo that edit again. Measured by the probe with a
    slowed log read: final `ids=[]`. The redo stack is a SECOND store, so its
    lock is taken only after this one is released (`jsonio.lock_for` must never
    be asked to hold two store locks at once).
    """
    from .jsonio import lock_for
    log_path = edits_log_path(m)
    redo_path = edits_redo_path(m)
    with lock_for(log_path):
        log = edits_log(m)
        if not log:
            raise ValueError("Nothing to undo.")
        record = log[-1]
        # Pre-flight the redo stack BEFORE anything moves. It raises on a damaged
        # stack (BE-M1), and reading it up here rather than after the working copy
        # and the edit log have already been rewritten is what makes the refusal
        # clean: a corrupt edits.redo.json declines the undo instead of silently
        # consuming it and leaving a half-applied reversal behind.
        redo_stack(m)
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
        _save_json_list(log_path, log)
    with lock_for(redo_path):
        # re-read under the lock: the write-back must append to the stack as it
        # is NOW, not to the copy this call happened to see earlier
        redo = redo_stack(m)
        redo.append(record)
        _save_json_list(redo_path, redo)
    return {
        "undone": record,
        "restored": restored,
        "failed": failed,
        "can_undo": bool(log),
        "can_redo": True,
    }


def redo_last_edit(m) -> dict:
    """Re-apply the most recently undone edit group (old -> new). The record
    moves from the redo stack back onto the undo log.

    H5, the mirror of undo_last_edit: the redo stack's own read-modify-write runs
    under its lock, and the LOG append re-reads under the log's lock — otherwise
    a locked apply landing mid-flight lost its record (`ids=['e1-race']`: the
    redo's stale list overwrote the apply's append).
    """
    from .jsonio import lock_for
    log_path = edits_log_path(m)
    redo_path = edits_redo_path(m)
    with lock_for(redo_path):
        redo = redo_stack(m)
        if not redo:
            raise ValueError("Nothing to redo.")
        record = redo[-1]
        # Same pre-flight as undo_last_edit: a damaged edits.json refuses the redo
        # before the working copy is rewritten, instead of after.
        edits_log(m)
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
        _save_json_list(redo_path, redo)
    with lock_for(log_path):
        # fresh read under the lock — never append to the list this call read
        log = edits_log(m)
        log.append(record)
        _save_json_list(log_path, log)
    return {
        "redone": record,
        "applied": applied,
        "failed": failed,
        "can_undo": True,
        "can_redo": bool(redo),
    }


def edits_log(m) -> list[dict]:
    """The applied-edit log: MISSING -> `[]`, DAMAGED -> raise.

    BE-M2 — the sibling of BE-M1. This read the file raw, so a corrupt
    `edits.json` escaped as a bare `json.JSONDecodeError`, which is a
    `ValueError`: the webapp's ValueError handler then answered the writer with
    **400 "bad request"** and a Python message about line 1 column 1, for what is
    really a damaged disk. Same store contract as every other writer-owned
    store, so the answer is now 503 "damaged and was not touched".
    """
    return _load_json_list(edits_log_path(m))


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

    # 1500 tokens was truncating long replacement JSON mid-emit (finish_reason=
    # 'length'), which the parser then rejected and the model degraded into
    # trailing comma noise. 4000 gives the replacements list room to close.
    return client.chat_json(system, user, grammar=replacements_grammar(), max_tokens=4000)


# ---------- finding triage (dismiss / restore) ----------

# The writer's own judgment layer over the report: a finding they've decided
# to live with. Stored as (index, issue) pairs so a dismissal only sticks
# while the report still says the same thing at that index — a regenerated
# report re-opens everything honestly (flag-don't-drop, applied both ways).

def dismissed_path(m) -> str:
    return os.path.join(m.project_dir, "dismissed_findings.json")


def dismissed_issues(m) -> set:
    """Set of (index, issue) tuples currently dismissed for this project."""
    from .jsonio import StoreUnreadable, load_json_store
    path = dismissed_path(m)
    data = load_json_store(path, default=[])
    if not isinstance(data, list):
        raise StoreUnreadable(path, f"expected a list, found {type(data).__name__}")
    return {(int(d["index"]), d.get("issue") or "") for d in data if isinstance(d, dict)}


def dismiss_finding(m, index: int, issue: str, finding_id: str | None = None) -> None:
    from .jsonio import StoreUnreadable, load_json_store, lock_for
    path = dismissed_path(m)
    with lock_for(path):
        data = load_json_store(path, default=[])
        if not isinstance(data, list):
            raise StoreUnreadable(path, "expected a list")
        entry = {"index": int(index), "issue": issue or ""}
        if finding_id:
            entry["finding_id"] = finding_id
        if entry not in data:
            data.append(entry)
        from .jsonio import atomic_write_json
        atomic_write_json(path, data)


def undismiss_finding(m, index: int, finding_id: str | None = None) -> None:
    from .jsonio import load_json_store, lock_for
    path = dismissed_path(m)
    with lock_for(path):
        data = load_json_store(path, default=[])
        if not data:
            return
        # Prefer id (survives report regeneration); fall back to legacy index
        # entries that never carried one (old projects).
        data = [d for d in data if not (
            isinstance(d, dict)
            and (d.get("finding_id") == finding_id if finding_id
                 else int(d.get("index", -1)) == int(index))
        )]
        from .jsonio import atomic_write_json
        atomic_write_json(path, data)


# Change detection is STRICT on purpose, and it is deliberately NOT the
# verifier's threshold: a line the writer reworded must read "addressed", not
# "still present". (GAP-6: sharing one threshold would have traded this bug for
# a quieter one — the writer-fix signal would stop firing.)
QUOTE_CHANGE_THRESHOLD = 0.95
# Below this many words a fuzzy hit is noise, not evidence, so only containment
# counts. Mirrors the verifier's own `< 3 words -> cannot check` rule.
SHORT_QUOTE_WORDS = 3


def quote_present(doc: ScriptDocument, quote: str | None) -> bool:
    """Is a finding's evidence quote still present in the working copy?

    Both passes run over the JOINED, NORMALISED scene text via `quotematch`, the
    same primitives the analyzer's verifier uses, so the two engines can no
    longer disagree about a quote that spans a line wrap or mixes straight and
    curly quotes. That disagreement was GAP-6: six dialogue findings read
    `verified` at confidence 1.0 to the verifier and "gone" here, so on a script
    nobody had edited the desk reported them "addressed by you", the board
    dropped its Dialogue section and the manuscript lost every margin pin.

      1. containment of the normalised quote in a normalised scene. Settles
         every genuine quote, wherever it sits and however it is punctuated.
      2. a strict fuzzy fallback (`QUOTE_CHANGE_THRESHOLD`) against each
         element, for a quote the writer mistyped or that the parse mangled.

    Strictness is the point: a line edited at all — even one word — counts as
    'addressed'. Measured separation at ELEMENT granularity, normalised: a
    dropped character scores 0.979 (still present), a swapped word 0.875 and a
    removed word 0.830 (both addressed). The price of passing (1) is that a
    punctuation-only edit reads as still present; a finding's substance is
    unchanged by a comma.

    Pass B deliberately keeps ELEMENT granularity rather than reusing the
    verifier's scene-sized window: a ratio wants two strings of similar length,
    and a scene-sized window dilutes it until the pass is inert. The consequence
    is that a quote spanning two elements AND edited reads as addressed, which is
    the conservative direction.
    """
    if not quote or not quote.strip():
        return False
    target_norm = quotematch.normalize_text(quote)
    if not target_norm:
        return False
    scenes = [quotematch.normalize_text(t) for t in quotematch.iter_scene_texts(doc)]
    if any(target_norm in s for s in scenes):
        return True
    if len(target_norm.split()) < SHORT_QUOTE_WORDS:
        return False
    return any(
        SequenceMatcher(None, quotematch.normalize_text(el.text), target_norm).ratio()
        >= QUOTE_CHANGE_THRESHOLD
        for s in doc.scenes
        for el in s.elements
        if el.text
    )


def _load_baseline_doc(m):
    """The parse-of-record: the script as it was analyzed.

    The baseline that separates "the writer edited this line away" from "this
    line was never in the script". None when the parse is unreadable, in which
    case callers must stay at 'unknown' rather than claim progress -- an
    unverifiable 'addressed' is the exact failure this exists to prevent.
    """
    try:
        return ScriptDocument.load(m.parsed_path)
    except (OSError, ValueError):
        return None


def finding_statuses(m) -> dict:
    """Which findings are still live in the working copy vs. addressed by edits.

    'addressed' means the writer changed or removed the quoted line: the quote
    must have been present in the parse-of-record AND be gone from the working
    copy. A quote the script never contained stays 'unknown' -- absence alone
    is not evidence of progress. Findings with no quote can't be auto-checked
    and are reported as 'unknown'.
    """
    try:
        with open(m.report_findings_path, "r", encoding="utf-8") as f:
            report = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"findings": [], "summary": {"addressed": 0, "still_present": 0, "unknown": 0}}

    doc = load_working(m)
    # A quote missing from the working copy only proves writer progress if the
    # line was in the script to begin with. Absence alone is not evidence: the
    # report's own verifier accepts a paraphrase at 0.72 and reports not_found
    # for the rest, so "gone from the working copy" can describe a line that was
    # never there -- measured on gun_pen_2, 2 of 9 quoted findings told the
    # writer they had fixed a line on a draft they had never touched. The
    # parse-of-record is the baseline, loaded lazily so a draft with nothing
    # missing pays nothing for it.
    baseline = None
    baseline_loaded = False
    statuses = []
    for idx, f in enumerate(report.get("findings", [])):
        quote = f.get("evidence_quote")
        entry = {
            "index": idx,
            "category": f.get("category"),
            "finding_id": compute_finding_id(f),
        }
        if not quote:
            entry["status"] = "unknown"
        elif quote_present(doc, quote):
            entry["status"] = "still_present"
        else:
            if not baseline_loaded:
                baseline = _load_baseline_doc(m)
                baseline_loaded = True
            # no readable baseline -> unknown, never a claimed fix
            entry["status"] = ("addressed" if baseline is not None
                               and quote_present(baseline, quote) else "unknown")
        statuses.append(entry)

    summary = {"addressed": 0, "still_present": 0, "unknown": 0}
    for s in statuses:
        summary[s["status"]] += 1
    return {"findings": statuses, "summary": summary, "checked_at": time.time()}
