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

# Indian-language scene headings. The native-script equivalents of INT./EXT.
#
# Gap 24: this used to be one hand-written regex per language, built from a
# token list that had to list every spelling in advance. Telugu's list was
# missing two of its own tokens, so `లోపల. హాల్ - ఉదయం` (a perfectly ordinary
# Telugu INT. heading) matched nothing and opened no scene — the same class of
# omission that had already left Telugu out of the cue test. A per-language
# regex with an enumerated token list is a list nobody can keep complete; the
# pattern below derives from the token TABLES instead, so a token that
# `parse_scene_heading` accepts is a token the heading test accepts, by
# construction.
_NATIVE_HEADING_TOKENS = (
    "एक्सट", "इंट",                                      # Hindi
    "வெளி", "உள்",                                       # Tamil
    "ఎక్స్ట", "ఎక్సట", "బయట", "లోపల", "ఇంట",               # Telugu
    "ಹೊರಗೆ", "ಒಳಗೆ",                                     # Kannada
    "എക്സ്റ്റ", "ഇന്റ",                                    # Malayalam
)


def _alternation(tokens) -> str:
    """Longest-first alternation, so 'ఎక్సట' is not shadowed by 'ఎక్స'."""
    return "|".join(sorted((re.escape(t) for t in tokens), key=len, reverse=True))


_IN = _alternation(_NATIVE_HEADING_TOKENS)
# "TOKEN." then a separator, or "A/B" then a separator. The period is optional
# (some writers omit it) but the separator is not: "ఇంటగది" is a word, not a
# heading.
NATIVE_SCENE_HEADING_RE = re.compile(
    rf"^\s*(?:{_IN})\.?(?:/(?:{_IN})\.?)?[\s.\-].*",
)

# Backwards-compatible aliases: nothing outside this module imported the
# per-language names, but keeping them costs nothing and they document which
# languages the shared pattern covers.
DEVA_SCENE_HEADING_RE = TAMIL_SCENE_HEADING_RE = NATIVE_SCENE_HEADING_RE
TELUGU_SCENE_HEADING_RE = KANNADA_SCENE_HEADING_RE = MALAYALAM_SCENE_HEADING_RE = NATIVE_SCENE_HEADING_RE

TIME_OF_DAY_WORDS = [
    "DAY", "NIGHT", "MORNING", "EVENING", "AFTERNOON", "DUSK", "DAWN",
    "CONTINUOUS", "LATER", "MOMENTS LATER", "SAME TIME", "NOON", "MIDNIGHT",
]

TRANSITION_RE = re.compile(
    r"^\s*(CUT TO:|SMASH CUT TO:|MATCH CUT TO:|DISSOLVE TO:|FADE TO:|"
    r"FADE OUT\.?|FADE IN:|FADE TO BLACK\.?|JUMP CUT TO:|TIME CUT TO:|"
    r"CONTINUOUS:|INTERCUT WITH:?|WHITE FLASH CUT:?|FLASH CUT:?|"
    r"FLASHE? CUTS?:|PRESENT:|MONTAGE:)\s*$",
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

# Caseless-script ranges. These scripts have no letter case, so the all-caps
# character-cue heuristic cannot apply to them and a different test is needed.
#
# Gap 24: this was `DEVA_SCRIPT` + `TAMIL_SCRIPT` and nothing else, so a Telugu
# cue scored 0 script chars, fell through to the uppercase test, and was read as
# ACTION — a Telugu-speaking writer's speaker cues vanished, and (because the
# heading tokens were unsupported too) the whole script parsed to zero scenes.
# The set is now the Brahmic scripts that are written without case, which covers
# every Indian language a screenplay is plausibly written in rather than the two
# that happened to be reported. Adding a script here is the whole change needed
# for both the cue test and the native INT./EXT. tokens below.
DEVA_SCRIPT = range(0x0900, 0x0980)      # Hindi / Marathi / Sanskrit
BENGALI_SCRIPT = range(0x0980, 0x0A00)   # Bengali / Assamese
GURMUKHI_SCRIPT = range(0x0A00, 0x0A80)  # Punjabi
GUJARATI_SCRIPT = range(0x0A80, 0x0B00)
ORIYA_SCRIPT = range(0x0B00, 0x0B80)     # Odia
TAMIL_SCRIPT = range(0x0B80, 0x0C00)
TELUGU_SCRIPT = range(0x0C00, 0x0C80)
KANNADA_SCRIPT = range(0x0C80, 0x0D00)
MALAYALAM_SCRIPT = range(0x0D00, 0x0D80)
SINHALA_SCRIPT = range(0x0D80, 0x0E00)

CASELESS_SCRIPTS = (
    DEVA_SCRIPT, BENGALI_SCRIPT, GURMUKHI_SCRIPT, GUJARATI_SCRIPT, ORIYA_SCRIPT,
    TAMIL_SCRIPT, TELUGU_SCRIPT, KANNADA_SCRIPT, MALAYALAM_SCRIPT, SINHALA_SCRIPT,
)


# Sentence-final punctuation across the caseless scripts: ASCII, the Devanagari
# danda/double-danda, and the Arabic-style full stop used by some Urdu/Telugu
# publishers. A line of dialogue ends with one; a character name does not.
SENTENCE_END_PUNCT = (".", "?", "!", "\u0964", "\u0965", "\u06d4")


def _count_script(line: str, rng) -> int:
    return sum(1 for c in line if ord(c) in rng)


def _script_share(line: str) -> tuple[int, int]:
    """(n_chars_in_the_dominant_caseless_script, n_total_letters).

    Every caseless script is counted, and the LARGEST count wins, so a line that
    mixes scripts (a Telugu cue with a Latin "(V.O.)", or a name transliterated
    in the middle) still measures against the script it is mostly written in.
    """
    counts = [_count_script(line, rng) for rng in CASELESS_SCRIPTS]
    dominant = max(counts) if counts else 0
    letters = sum(1 for c in line if c.isalpha())
    return dominant, letters


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
# U+2019 (curly apostrophe) appears in real script exports — Final Draft PDFs
# map it to an unmapped glyph that pdfplumber emits as-is, and typed .txt files
# often carry it in extensions like (CONT'D). The cue regexes accept both.
_EXT_CHARS = r"[A-Z0-9 ._'\-/’]"

CHARACTER_CUE_RE = re.compile(
    rf"^\s*([A-Z][A-Z0-9 ._\-'#’]{{0,40}}?)"
    rf"(\s*\({_EXT_CHARS}+\))?"
    r"\s*$"
)

# CONT'D arrives with either apostrophe (ASCII from typed files, U+2019 from
# Final Draft PDF exports) — accept both. Any short all-caps parenthetical is a
# valid cue extension ((O.S.), (CONT'D), (KID), (PRESENT), ...) — real scripts
# use many more than the canonical list, and a cue line's short all-caps shape
# is the actual signal. The guardrail against false positives is the cue regex
# itself (whole line must be short + uppercase once stripped).
CHARACTER_EXTENSION_RE = re.compile(r"\([A-Z0-9 ._'’\-/]{1,15}\)", re.IGNORECASE)


# Every native-script heading pattern, in one list. A new language is added
# here once; the old shape was an if-chain, which is how Telugu ended up
# supported by nothing (gap 24: its heading tokens existed nowhere, so a Telugu
# script parsed to ZERO scenes rather than to mislabelled ones).
def looks_like_scene_heading(line: str) -> bool:
    stripped = line.strip()
    if SCENE_HEADING_RE.match(stripped):
        return True
    return bool(NATIVE_SCENE_HEADING_RE.match(stripped))


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
    # "THE END" (and its native-script equivalents) close the script — it is
    # not a speaker, and often sits alone at the end with no following line for
    # the cue lookahead to disambiguate it.
    if stripped.upper() == "THE END":
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
        # A cue is a NAME, so it does not end a sentence. This is the one
        # reliable signal in a caseless script, where the all-caps test cannot
        # help: "రాము" is a cue, "నేను వెళ్తున్నాను." is a line of dialogue that
        # happens to be short. Without this, a short dialogue line looked like a
        # cue, which made the line ABOVE it look like it was not one — so a cue
        # followed by terse dialogue was parsed as action (measured: the first
        # Telugu cue in a two-line exchange became ACTION while the second
        # worked, purely because its dialogue was longer).
        if stripped.endswith(SENTENCE_END_PUNCT):
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
# Telugu (gap 24). "ఇంట" is the everyday transliteration of INT.; "బయట" (outside)
# is the native word a Telugu writer is more likely to reach for, the way Tamil
# uses வெளி rather than a transliterated EXT.
TELUGU_INT_EXT = {
    "ఇంట": "INT", "ఎక్సట": "EXT", "ఎక్స్ట": "EXT", "బయట": "EXT", "లోపల": "INT",
    "ఇంట/ఎక్సట": "INT/EXT", "ఎక్సట/ఇంట": "INT/EXT",
}
KANNADA_INT_EXT = {
    "ಒಳಗೆ": "INT", "ಹೊರಗೆ": "EXT",
    "ಒಳಗೆ/ಹೊರಗೆ": "INT/EXT", "ಹೊರಗೆ/ಒಳಗೆ": "INT/EXT",
}
MALAYALAM_INT_EXT = {
    "ഇന്റ": "INT", "എക്സ്റ്റ": "EXT",
    "ഇന്റ/എക്സ്റ്റ": "INT/EXT", "എക്സ്റ്റ/ഇന്റ": "INT/EXT",
}

# Every native-script INT./EXT. table, consulted in order. Adding a language is
# one entry here plus its map above.
NATIVE_INT_EXT_MAPS = (
    DEVA_INT_EXT, TAMIL_INT_EXT, TELUGU_INT_EXT, KANNADA_INT_EXT, MALAYALAM_INT_EXT,
)


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
        # One lookup across every native map (gap 24): the if/elif chain meant a
        # language could be "supported" by having a map and still never be
        # consulted, which is exactly what happened to Telugu.
        for token_map in NATIVE_INT_EXT_MAPS:
            if tok_clean in token_map:
                int_ext = token_map[tok_clean]
                text = text[len(first_tok):].strip()
                break
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
