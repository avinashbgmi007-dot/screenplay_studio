"""
Shared line-classification heuristics for text-based screenplay parsing
(plain .txt, Fountain, and PDF-extracted text all funnel through these).

FDX is excluded — it carries explicit paragraph-type tags and needs none
of this guesswork.
"""

import re

SCENE_HEADING_RE = re.compile(
    r"^\s*(?:\d+[A-Z]?\s+)?"  # optional leading scene number
    r"(INT|EXT|INT\.?/EXT|I/E|EST)[\.\s]"
    r".*",
    re.IGNORECASE,
)

TIME_OF_DAY_WORDS = [
    "DAY", "NIGHT", "MORNING", "EVENING", "AFTERNOON", "DUSK", "DAWN",
    "CONTINUOUS", "LATER", "MOMENTS LATER", "SAME TIME", "NOON", "MIDNIGHT",
]

TRANSITION_RE = re.compile(
    r"^\s*(CUT TO:|SMASH CUT TO:|MATCH CUT TO:|DISSOLVE TO:|FADE TO:|"
    r"FADE OUT\.?|FADE IN:|FADE TO BLACK\.?|JUMP CUT TO:|TIME CUT TO:|"
    r"CONTINUOUS:|INTERCUT WITH:?)\s*$",
    re.IGNORECASE,
)

SHOT_RE = re.compile(
    r"^\s*(ANGLE ON|CLOSE ON|CLOSE-UP|WIDE SHOT|POV|INSERT|AERIAL SHOT|"
    r"TRACKING SHOT|TIGHT ON|ON [A-Z]+)\b",
)

PARENTHETICAL_RE = re.compile(r"^\s*\(.*\)\s*$")

# Character cue: short, mostly uppercase line. Allow trailing (V.O.), (O.S.),
# (CONT'D), (INTO PHONE) etc. Reject lines that are clearly action (too long,
# contains lowercase sentence-like content, ends in punctuation like a full
# sentence).
CHARACTER_CUE_RE = re.compile(
    r"^\s*([A-Z][A-Z0-9 .\-'#]{0,40}?)"
    r"(\s*\((?:[A-Z0-9 .'\-/]+)\))?"
    r"\s*$"
)

CHARACTER_EXTENSION_RE = re.compile(r"\((V\.?O\.?|O\.?S\.?|CONT'?D|OFF|INTO PHONE|FILTERED)\)", re.IGNORECASE)


def looks_like_scene_heading(line: str) -> bool:
    return bool(SCENE_HEADING_RE.match(line.strip()))


def looks_like_transition(line: str) -> bool:
    stripped = line.strip()
    if TRANSITION_RE.match(stripped):
        return True
    # Right-aligned all-caps short lines ending in "TO:" without matching the
    # canonical list (custom transitions) are still very likely transitions.
    return bool(re.match(r"^[A-Z0-9 '\-]{3,30}TO:\s*$", stripped))


def looks_like_shot(line: str) -> bool:
    return bool(SHOT_RE.match(line.strip()))


def looks_like_parenthetical(line: str) -> bool:
    return bool(PARENTHETICAL_RE.match(line.strip()))


def looks_like_character_cue(line: str, next_nonblank_line: str = "") -> bool:
    """
    A character cue is: short, uppercase (ignoring extensions like (V.O.)),
    not a scene heading/transition, and is followed by dialogue or a
    parenthetical (not another all-caps line, not blank-to-end-of-scene).
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 45:
        return False
    if looks_like_scene_heading(stripped) or looks_like_transition(stripped):
        return False
    # must be uppercase once extensions are stripped
    core = CHARACTER_EXTENSION_RE.sub("", stripped).strip()
    if not core or core != core.upper():
        return False
    # Unicode-aware character check: every letter must be uppercase (so accented
    # names like RENÉE, JOSÉ, MÜLLER pass), non-letters limited to a small allowed
    # punctuation/digit set. Deliberately not ASCII-only ([A-Z]) since screenplay
    # character names are not limited to English.
    allowed_punct = set(" .'-#")
    if not all(ch.isupper() or ch.isdigit() or ch in allowed_punct for ch in core):
        return False
    # Reject bare numbers/punctuation artifacts with no actual letter in them
    if not any(ch.isupper() for ch in core):
        return False
    return True


def parse_scene_heading(raw: str) -> dict:
    """Extract int/ext, location, and time-of-day from a scene heading line."""
    text = raw.strip()
    # strip leading scene number token if present, e.g. "12A INT. HOUSE - DAY"
    text = re.sub(r"^\d+[A-Z]?\s+", "", text)

    int_ext = None
    m = re.match(r"^(INT\.?/EXT\.?|I/E|INT|EXT|EST)[\.\s]", text, re.IGNORECASE)
    if m:
        token = m.group(1).upper().replace(".", "")
        int_ext = "INT/EXT" if token in ("INT/EXT", "I/E") else token
        text = text[m.end():].strip()
    text = text.lstrip(".- ").strip()

    time_of_day = None
    location = text
    # split on last " - " which conventionally separates location from time of day
    if " - " in text:
        loc_part, _, tod_part = text.rpartition(" - ")
        tod_upper = tod_part.strip().upper()
        if any(word in tod_upper for word in TIME_OF_DAY_WORDS) or len(tod_part.strip()) <= 20:
            location = loc_part.strip()
            time_of_day = tod_part.strip() or None

    return {"int_ext": int_ext, "location": location or None, "time_of_day": time_of_day}


def normalize_character_name(raw: str) -> str:
    """Strip parenthetical extensions like (V.O.), (CONT'D) from a cue to get the bare name."""
    name = CHARACTER_EXTENSION_RE.sub("", raw).strip()
    name = re.sub(r"\s+", " ", name)
    return name.rstrip(".")
