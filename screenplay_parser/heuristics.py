"""
Shared line-classification heuristics for text-based screenplay parsing
(plain .txt, Fountain, and PDF-extracted text all funnel through these).

FDX is excluded — it carries explicit paragraph-type tags and needs none
of this guesswork.
"""

import re

SCENE_HEADING_RE = re.compile(
    r"^\s*(?:\d+[A-Z]?\s+)?"  # optional leading scene number
    r"(?:INT\.?/EXT\.?|EXT\.?/INT\.?|I/E|EST|INT\.?|EXT\.?)"
    r"[\s.-]"
    r".*",
    re.IGNORECASE,
)

# Indian-language scene headings: Hindi (Devanagari) and Tamil equivalents of
# INT./EXT. Indian scripts in the Roman script (Tenglish/Tanglish) already use
# standard INT./EXT., so these cover the native-script case.
# Hindi: इंट (int) / एक्सट (ext); Tamil: உள் (ull/int) / வெளி (veli/ext).
DEVA_SCENE_HEADING_RE = re.compile(
    r"^\s*(?:एक्सट\.?/इंट\.?|इंट\.?/एक्सट\.?|इंट\.?|एक्सट\.?)[\s.-].*",
)
TAMIL_SCENE_HEADING_RE = re.compile(
    r"^\s*(?:வெளி\.?/உள்\.?|உள்\.?/வெளி\.?|உள்\.?|வெளி\.?)[\s.-].*",
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

# All-caps time markers like "TWO MONTHS LATER" / "2 YEARS EARLIER" — very
# common in Indian screenplays as beat markers. They're not character cues,
# even though they're short and all-caps; treat them as action/transition.
TIME_MARKER_RE = re.compile(
    r"^\s*(?:\d+|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|A\s+COUPLE\s+OF|A\s+FEW)\s+"
    r"(?:MINUTES?|HOURS?|DAYS?|WEEKS?|MONTHS?|YEARS?)\s+"
    r"(?:LATER|EARLIER|AFTER|BEFORE|AGO)\b",
    re.IGNORECASE,
)

# Caseless-script ranges: Devanagari (Hindi/Marathi/Sanskrit) and Tamil have no
# letter case, so the all-caps character-cue heuristic can't apply to them.
DEVA_SCRIPT = range(0x0900, 0x0980)
TAMIL_SCRIPT = range(0x0B80, 0x0C00)


def _script_share(line: str) -> tuple[int, int]:
    """(n_script_chars, n_total_letters) for the dominant caseless script."""
    deva = sum(1 for c in line if ord(c) in DEVA_SCRIPT)
    tamil = sum(1 for c in line if ord(c) in TAMIL_SCRIPT)
    letters = sum(1 for c in line if c.isalpha())
    return (deva if deva >= tamil else tamil), letters


SHOT_RE = re.compile(
    r"^\s*(ANGLE ON|CLOSE ON|CLOSE-UP|WIDE SHOT|POV|INSERT|AERIAL SHOT|"
    r"TRACKING SHOT|TIGHT ON|ON [A-Z]+)\b",
)

PARENTHETICAL_RE = re.compile(r"^\s*\(.*\)\s*$")

# Character cue: short, mostly uppercase line. Allow trailing (V.O.), (O.S.),
# (CONT'D), (INTO PHONE) etc. Reject lines that are clearly action (too long,
# contains lowercase sentence-like content, ends in punctuation like a full
# sentence).
# Underscore is allowed because transliterated Indian names / beat markers
# often use it as a space substitute (e.g. GOON_ONE, KID_SIDDHU).
CHARACTER_CUE_RE = re.compile(
    r"^\s*([A-Z][A-Z0-9 ._\-'#]{0,40}?)"
    r"(\s*\((?:[A-Z0-9 ._'\-/]+)\))?"
    r"\s*$"
)

CHARACTER_EXTENSION_RE = re.compile(r"\((V\.?O\.?|O\.?S\.?|CONT'?D|OFF|INTO PHONE|FILTERED)\)", re.IGNORECASE)


def looks_like_scene_heading(line: str) -> bool:
    stripped = line.strip()
    if SCENE_HEADING_RE.match(stripped):
        return True
    if DEVA_SCENE_HEADING_RE.match(stripped):
        return True
    if TAMIL_SCENE_HEADING_RE.match(stripped):
        return True
    return False


def looks_like_time_marker(line: str) -> bool:
    return bool(TIME_MARKER_RE.match(line.strip()))


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


def looks_like_character_cue(line: str, next_nonblank_line: str = "", second_next: str = "") -> bool:
    """
    A character cue is: short, uppercase (ignoring extensions like (V.O.)),
    not a scene heading/transition, and is followed by dialogue or a
    parenthetical (not another all-caps line, not blank-to-end-of-scene).

    Indian-language support: caseless scripts (Devanagari/Hindi, Tamil) have no
    uppercase, so a short line written entirely in such a script is only a cue
    when the following line is clearly content — a parenthetical, or a line that
    is itself neither a cue nor a heading (i.e. dialogue). The next-two-lines
    lookahead disambiguates "राहुल" (speaker, followed by dialogue) from
    "राहुल और पुलिस" (action beat, followed by another cue).
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 45:
        return False
    if looks_like_scene_heading(stripped) or looks_like_transition(stripped) or looks_like_time_marker(stripped):
        return False

    script_chars, letters = _script_share(stripped)
    if letters and script_chars >= letters * 0.8:
        # caseless-script cue: short (by words AND chars — combining marks
        # inflate char counts), followed by a parenthetical or a dialogue line
        nxt = next_nonblank_line.strip()
        nxt2 = second_next.strip()
        words = len([w for w in stripped.split() if any(c.isalpha() for c in w)])
        if not nxt or len(stripped) > 30 or words > 3:
            return False
        nxt_is_paren = looks_like_parenthetical(nxt)
        nxt_is_dialogue = (
            not nxt_is_paren
            and not looks_like_scene_heading(nxt)
            and not looks_like_transition(nxt)
            and not looks_like_character_cue(nxt, nxt2)
        )
        return nxt_is_paren or nxt_is_dialogue

    # must be uppercase once extensions are stripped
    core = CHARACTER_EXTENSION_RE.sub("", stripped).strip()
    if not core or core != core.upper():
        return False
    # Unicode-aware character check: every letter must be uppercase (so accented
    # names like RENÉE, JOSÉ, MÜLLER pass), non-letters limited to a small allowed
    # punctuation/digit set. Deliberately not ASCII-only ([A-Z]) since screenplay
    # character names are not limited to English.
    allowed_punct = set(" .'-#_")
    if not all(ch.isupper() or ch.isdigit() or ch in allowed_punct for ch in core):
        return False
    # Reject bare numbers/punctuation artifacts with no actual letter in them
    if not any(ch.isupper() for ch in core):
        return False
    return True


# Native-script INT./EXT. equivalents: Hindi (Devanagari) and Tamil.
# इंट / एक्सट and உள் / வெளி (same token order as their Roman cousins).
DEVA_INT_EXT = {
    "इंट": "INT", "एक्सट": "EXT",
    "इंट/एक्सट": "INT/EXT", "एक्सट/इंट": "INT/EXT",
}
TAMIL_INT_EXT = {
    "உள்": "INT", "வெளி": "EXT",
    "உள்/வெளி": "INT/EXT", "வெளி/உள்": "INT/EXT",
}


def parse_scene_heading(raw: str) -> dict:
    """Extract int/ext, location, and time-of-day from a scene heading line."""
    text = raw.strip()
    # strip leading scene number token if present, e.g. "12A INT. HOUSE - DAY"
    text = re.sub(r"^\d+[A-Z]?\s+", "", text)

    int_ext = None
    m = re.match(r"^(INT\.?/EXT\.?|EXT\.?/INT\.?|I/E|INT|EXT|EST)[\.\s]", text, re.IGNORECASE)
    if m:
        token = m.group(1).upper().replace(".", "")
        int_ext = "INT/EXT" if token in ("INT/EXT", "EXT/INT", "I/E") else token
        text = text[m.end():].strip()
    if int_ext is None:
        first_tok = text.split(None, 1)[0] if text else ""
        tok_clean = first_tok.rstrip("./")
        if tok_clean in DEVA_INT_EXT:
            int_ext = DEVA_INT_EXT[tok_clean]
            text = text[len(first_tok):].strip()
        elif tok_clean in TAMIL_INT_EXT:
            int_ext = TAMIL_INT_EXT[tok_clean]
            text = text[len(first_tok):].strip()
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
    # underscore-as-space (GOON_ONE -> GOON ONE) so transliterated names merge
    # with their space-separated twins.
    name = name.replace("_", " ")
    return name.rstrip(".")
