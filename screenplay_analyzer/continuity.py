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

    2. Possible character-name typos. Similar cue names that never share a
       scene may be one person spelled two ways, but string similarity cannot
       prove identity. Only tight spelling differences between sufficiently
       long cues are surfaced, as a low-severity question; names are never
       merged automatically.

Both return (findings, errors) with errors always empty. Findings use the
standard schema (category/issue/why_it_matters/severity/scene_refs/
evidence_quote) and survive quote-verification because every evidence quote
is a verbatim script line.
"""

from __future__ import annotations

import re


from screenplay_parser.models import ElementType, ScriptDocument
from screenplay_parser.knowledge_graph import TIME_SKIP_RE
from screenplay_parser.heuristics import normalize_character_name

from .deterministic_utils import dialogue_lines_by_character

CATEGORY = "continuity"

# Opposites only — a MORNING->EVENING drift is normal pacing; a day/night change
# is worth a look.
#
# Gaps 44 and 77. The original premise was that a day/night change with no
# LATER-style marker is a DROPPED TRANSITION, and it is wrong. In a screenplay
# the scene heading is where time is stated: `INT. KITCHEN - DAY` followed by
# `EXT. STREET - NIGHT` is the ordinary, correctly formatted way to move time.
# Demanding a redundant marker on top of it reports the writer's correct
# formatting as a defect.
#
# Measured before the change: the ordinary cut produced "Unmarked time flip"
# whose own `evidence_quote` was the SECOND SCENE'S HEADING — the text that
# states the new time. A finding quoting its own refutation.
#
# What survives is the only thing a heading cannot express: that the TWO
# headings are in tension with each other — same place, opposite time, nothing
# in between to account for the gap. That is a question, not a verdict, and it
# is reported as an observation with the uncertainty stated.
_OPPOSITE = {
    "NIGHT": {"DAY", "MORNING"},
    "DAY": {"NIGHT"},
    "MORNING": {"NIGHT"},
}

_HEADING_STOPWORDS = {"INT", "EXT", "INT/EXT", "EST", "CONTINUOUS"}


# Gap 44/77: TIME_SKIP_RE knows the explicit time-skip vocabulary but not the
# deliberate chronology moves, so a scene opening "FLASHBACK. Twelve years ago."
# still read as a dropped transition — the register asked for flashbacks by name.
# These are the writer SAYING the chronology is intentional, which is the
# strongest possible marker, so they silence the observation the same way.
_INTENTIONAL_CHRONOLOGY_RE = re.compile(
    r"\b(FLASHBACK|FLASH BACK|FLASH-FORWARD|FLASH FORWARD|DREAM|FANTASY|"
    r"MEMORY|SERIES OF SHOTS|MONTAGE|IMAGINE|REMEMBER(S|ED)?)\b",
    re.IGNORECASE,
)


def _scene_has_time_marker(scene) -> bool:
    """True when the scene says, in words, that time has moved or is not linear."""
    for e in scene.elements:
        if e.type not in (ElementType.ACTION, ElementType.PARENTHETICAL):
            continue
        text = e.text or ""
        if TIME_SKIP_RE.search(text) or _INTENTIONAL_CHRONOLOGY_RE.search(text):
            return True
    return False


def _place_changed(prev, cur) -> bool:
    """True when the two scenes are in different places.

    Uses the parsed location when both sides have one, and falls back to the
    heading text so an unusual slug line still counts as a move. Errs towards
    "changed": a false "different place" only suppresses an observation, while a
    false "same place" would raise one about an ordinary cut.
    """
    pl = (prev.location or "").strip().upper()
    cl = (cur.location or "").strip().upper()
    if pl and cl:
        return pl != cl
    ph = (prev.heading_raw or "").upper()
    ch = (cur.heading_raw or "").upper()
    return ph != ch


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
        # A location change is how a screenplay says "time has moved"; the
        # heading has already done the work the old check asked for.
        if _place_changed(prev, cur):
            continue
        findings.append({
            "category": CATEGORY,
            # The issue names what was noticed and nothing more. It does not say
            # a transition is missing, because the heading plainly states the
            # time and a transition is exactly what a new slug line is.
            "issue": (
                f"Possible same-place time jump: Scene {prev.scene_number} "
                f"(\"{prev.heading_raw}\") is in {pt} and Scene "
                f"{cur.scene_number} (\"{cur.heading_raw}\") returns to the same "
                f"place in {ct}, with nothing in between to account for the gap."
            ),
            "why_it_matters": (
                "A reader can follow this, and it may be exactly what you intend — "
                "an ellipsis is a normal cut. Worth a look only because both scenes "
                "are in the same location at opposite times: if the intervening "
                "hours matter, a beat or a line can carry them. If they don't, "
                "there is nothing to fix."
            ),
            "severity": "low",
            "scene_refs": [prev.scene_number, cur.scene_number],
            # A single VERBATIM line, because this module's contract (and the
            # pipeline's quote-verification step) requires it: every evidence
            # quote must be a line that exists in the script. My first version
            # wrote `f"{prev.heading_raw}  ->  {cur.heading_raw}"` to show the
            # pair, which is a composite that is in NO scene — verification
            # failed on it and a downstream revision test broke. The pair
            # belongs in the ISSUE text, where the writer still sees both
            # headings; the quote is the second heading, and it is quoted as the
            # evidence FOR "same place, opposite time", never as evidence that a
            # transition is missing (which was gap 77's complaint).
            "evidence_quote": cur.heading_raw,
            "paired_heading": prev.heading_raw,
            # Two fields, two meanings. `rule_id` is the knowledge-base rule
            # this check implements — the UI renders it as "Grounded in
            # knowledge-base rule <id>", so it must resolve in the KB.
            # `check_id` is this pass's own stable name, used by
            # AnalysisResult.merge to recognise a finding that regenerates on
            # every run (see _DETERMINISTIC_CHECK_IDS).
            "rule_id": "timeline_consistency",
            "check_id": "unmarked_time_flip",
            # Gap 44/77, same discipline as gap 43: a deterministic pass can
            # notice a pattern and cannot judge a cut.
            "is_observation": True,
            "confidence": "observation",
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


_MIN_VARIANT_NAME_LENGTH = 6
_MAX_VARIANT_EDIT_FRACTION = 0.13


def _looks_like_variant(a: str, b: str) -> bool:
    """Candidate only for a tight typo in a long cue; never infer nicknames.

    Two edits and the old prefix shortcut admitted distinct role labels such as
    MOTHER/BROTHER. The limit is a fraction of the longer name so one likely
    typo survives for long names while short/common labels need stronger
    evidence than string shape can provide.
    """
    a, b = a.upper(), b.upper()
    if a == b:
        return False
    longest = max(len(a), len(b))
    if longest < _MIN_VARIANT_NAME_LENGTH:
        return False
    return _levenshtein(a, b) / longest <= _MAX_VARIANT_EDIT_FRACTION


def _name_variant_findings(doc: ScriptDocument, by_char: dict) -> list[dict]:
    names = [n for n in by_char if n and n.upper() not in _HEADING_STOPWORDS]
    findings = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            if not _looks_like_variant(a, b):
                continue
            # True variants never share a scene — if they appear together,
            # they're deliberately different characters. Compare NORMALIZED
            # names on both sides: cue text keeps underscores ("GUN_GUY")
            # while characters_present is normalized ("GUN GUY"), and an
            # un-normalized comparison never sees them together (trial 14:
            # the same false GUN_GUY/PEN_GUY row regenerated 13 runs).
            a_norm = normalize_character_name(a).upper()
            b_norm = normalize_character_name(b).upper()
            a_scenes = {s.scene_number for s in doc.scenes
                        if a_norm in {normalize_character_name(c).upper() for c in s.characters_present}}
            b_scenes = {s.scene_number for s in doc.scenes
                        if b_norm in {normalize_character_name(c).upper() for c in s.characters_present}}
            if a_scenes & b_scenes:
                continue
            findings.append({
                "category": CATEGORY,
                "issue": (
                    f"'{a}' and '{b}' are similar cue names and never appear together. "
                    f"Could they be one character with a spelling difference?"
                ),
                "why_it_matters": (
                    "If these cues are intended to name one person, the parse keeps "
                    "them separate, which can split scene presence and character arcs. "
                    "Only the writer can confirm that identity."
                ),
                "severity": "low",
                "scene_refs": sorted(a_scenes | b_scenes)[:6],
                "evidence_quote": by_char[a][0] if by_char.get(a) else None,
                "rule_id": "character_trait_continuity",
                "check_id": "character_name_variant",
            })
    return findings


def run_continuity_analysis(doc: ScriptDocument) -> tuple[list[dict], list[str]]:
    by_char = dialogue_lines_by_character(doc)
    findings = _time_flip_findings(doc) + _name_variant_findings(doc, by_char)
    return findings, []
