"""
Deterministic continuity checks — no model call. These catch the mechanical
continuity errors a reader trips on but that cost model tokens to find, and
they read the parsed structure directly so they work even when the server's
context is too small for the model passes.

  run_continuity_analysis — two checks:

    1. Unmarked time-of-day flips. Consecutive scenes that jump between
       opposite times of day (NIGHT <-> DAY/MORNING) with no transition
       marker (LATER / THE NEXT DAY / etc.) in either scene read as a
       dropped transition. Conservative: only full opposites flag, and a
       scene marked CONTINUOUS (or carrying a time-skip marker) clears its
       boundary.

    2. Character-name variants. The same person spelled two ways in cues
       ("SIDDHARTH" in some scenes, "SIDDHU" in others) splits into two
       characters in the parse, which quietly corrupts scene presence,
       arcs, and the KG. If two canonical characters look like spelling
       variants (edit distance <= 2, or one a short prefix of the other),
       never appear in the same scene, and both speak, flag them.

Both return (findings, errors) with errors always empty. Findings use the
standard schema (category/issue/why_it_matters/severity/scene_refs/
evidence_quote) and survive quote-verification because every evidence quote
is a verbatim script line.
"""

from __future__ import annotations


from screenplay_parser.models import ElementType, ScriptDocument
from screenplay_parser.knowledge_graph import TIME_SKIP_RE

CATEGORY = "continuity"

# Opposites only — a MORNING->EVENING drift is normal pacing; a full
# day/night flip with no marker is a dropped transition.
_OPPOSITE = {
    "NIGHT": {"DAY", "MORNING"},
    "DAY": {"NIGHT"},
    "MORNING": {"NIGHT"},
}

_HEADING_STOPWORDS = {"INT", "EXT", "INT/EXT", "EST", "CONTINUOUS"}


def _dialogue_lines_by_character(doc: ScriptDocument) -> dict[str, list[str]]:
    lines: dict[str, list[str]] = {}
    for scene in doc.scenes:
        current = None
        for e in scene.elements:
            if e.type == ElementType.CHARACTER:
                current = e.text.strip()
            elif e.type == ElementType.DIALOGUE and current:
                lines.setdefault(current, []).append(e.text.strip())
                current = None
    return lines


def _scene_has_time_marker(scene) -> bool:
    for e in scene.elements:
        if e.type == ElementType.ACTION and TIME_SKIP_RE.search(e.text):
            return True
    return False


def _time_flip_findings(doc: ScriptDocument) -> list[dict]:
    findings = []
    for prev, cur in zip(doc.scenes, doc.scenes[1:]):
        pt = (prev.time_of_day or "").upper()
        ct = (cur.time_of_day or "").upper()
        if not pt or not ct or pt == ct:
            continue
        if pt in ("CONTINUOUS",) or ct in ("CONTINUOUS",):
            continue  # CONTINUOUS explicitly means "same time as before"
        if ct not in _OPPOSITE.get(pt, set()) and pt not in _OPPOSITE.get(ct, set()):
            continue
        if _scene_has_time_marker(prev) or _scene_has_time_marker(cur):
            continue
        findings.append({
            "category": CATEGORY,
            "issue": (
                f"Unmarked time flip: Scene {prev.scene_number} ends in {pt} and "
                f"Scene {cur.scene_number} opens in {ct} with no transition marker "
                f"(LATER / THE NEXT DAY / etc.)."
            ),
            "why_it_matters": (
                "The reader has to do the writer's work and infer a jump that the "
                "page doesn't signal. A one-line transition beats a confused re-read."
            ),
            "severity": "low",
            "scene_refs": [cur.scene_number],
            "evidence_quote": cur.heading_raw,
            "rule_id": "unmarked_time_flip",
        })
    return findings


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _looks_like_variant(a: str, b: str) -> bool:
    a, b = a.upper(), b.upper()
    if a == b:
        return False
    if _levenshtein(a, b) <= 2:
        return True
    # one a short prefix of the other (SIDDHU / SIDDHARTH)
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 4 and long_.startswith(short) and len(long_) - len(short) <= 3


def _name_variant_findings(doc: ScriptDocument, by_char: dict) -> list[dict]:
    names = [n for n in by_char if n and n.upper() not in _HEADING_STOPWORDS]
    findings = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            if not _looks_like_variant(a, b):
                continue
            # True variants never share a scene — if they appear together,
            # they're deliberately different characters.
            a_scenes = {s.scene_number for s in doc.scenes
                        if a.upper() in {c.upper() for c in s.characters_present}}
            b_scenes = {s.scene_number for s in doc.scenes
                        if b.upper() in {c.upper() for c in s.characters_present}}
            if a_scenes & b_scenes:
                continue
            findings.append({
                "category": CATEGORY,
                "issue": (
                    f"'{a}' and '{b}' look like two spellings of the same character "
                    f"(they never appear together). If so, one cue spelling is wrong — "
                    f"the parse sees two people where the script has one."
                ),
                "why_it_matters": (
                    "A split character quietly corrupts scene presence, arcs, and the "
                    "knowledge graph — the analysis judges a person who doesn't exist "
                    "as two strangers who never meet."
                ),
                "severity": "low",
                "scene_refs": sorted(a_scenes | b_scenes)[:6],
                "evidence_quote": by_char[a][0] if by_char.get(a) else None,
                "rule_id": "character_name_variant",
            })
    return findings


def run_continuity_analysis(doc: ScriptDocument) -> tuple[list[dict], list[str]]:
    by_char = _dialogue_lines_by_character(doc)
    findings = _time_flip_findings(doc) + _name_variant_findings(doc, by_char)
    return findings, []
