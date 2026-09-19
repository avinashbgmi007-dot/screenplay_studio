"""Language mirror — the writer sets the language, Sameer and the doctor follow.

Detection is deterministic (Unicode block scans + transliteration token lists),
so the instruction rides in the prompt as a FACT, never a model guess. The
instruction is appended to the system prompt each turn from the CURRENT writer
message — writers switch languages mid-conversation and the desk follows.

Registers handled:
  - telugu script  (తెలుగు Unicode block)
  - hindi script   (Devanagari block)
  - tenglish       (Latin-script Telugu-English mix — "enti baaga undi")
  - hinglish       (Latin-script Hindi-English mix — "kya scene hai yaar")
  - english        (default: no instruction block at all)

The mirror rule is one sentence: match the writer's language and register,
never translate them, never upgrade to formal English.
"""

from __future__ import annotations

import re

_TELUGU_CHAR = re.compile(r"[\u0C00-\u0C7F]")
_DEVANAGARI_CHAR = re.compile(r"[\u0900-\u097F]")

# Latin-script transliteration tokens (Tenglish + Hinglish share many). These
# are function/content words a writer wouldn't drop into English prose.
_INDIC_LATIN_TOKENS = {
    # Telugu
    "enti", "ela", "baga", "baaga", "chudu", "choodu", "cheppu", "cheppandi",
    "avunu", "ledu", "inka", "mawa", "anna", "endi", "antey", "ante", "kada",
    "ra", "rya", "nenu", "nuvvu", "meeru", "mana", "nijam", "asalu",
    # Hindi
    "kya", "kyun", "kyu", "yaar", "matlab", "nahi", "nahin", "achha", "acha",
    "thoda", "bahut", "hai", "hain", "hoon", "hunga", "dost", "bhai", "arre",
    "chal", "chalo", "dekho", "suno", "accha", "theek",
}

_WORD = re.compile(r"[a-zA-Z]+")


def detect_register(text: str) -> dict:
    """Classify the writer's current message. Returns:
    {script: 'telugu'|'hindi'|None, tenglish: bool, hinglish: bool}
    Script detection wins over Latin-mix detection; a mixed message with real
    Telugu/Devanagari content is treated as script-first."""
    text = text or ""
    telugu = len(_TELUGU_CHAR.findall(text))
    devanagari = len(_DEVANAGARI_CHAR.findall(text))
    words = [w.lower() for w in _WORD.findall(text)]
    token_hits = sum(1 for w in words if w in _INDIC_LATIN_TOKENS)

    if telugu >= 2 and telugu >= devanagari:
        return {"script": "telugu", "tenglish": False, "hinglish": False}
    if devanagari >= 2:
        return {"script": "hindi", "tenglish": False, "hinglish": False}

    latin_words = len(words)
    token_kinds = len({w for w in words if w in _INDIC_LATIN_TOKENS})
    # LENGTH-INDEPENDENT bar. A pure ratio silently stops firing as a message
    # gets longer: one hit reads 0.33 in a 3-word message and 0.03 in a 30-word
    # one, so a writer who pastes a full paragraph of Tenglish used to get no
    # mirror instruction at all and Sameer answered in English. The ratio still
    # settles the short case (where one loanword is weak evidence); the absolute
    # count settles the long one (where three distinct transliterated tokens is
    # code-mixing at any length). DISTINCT tokens, so "hai hai hai" is one kind.
    is_latin_mix = (
        token_hits >= 1 and latin_words >= 3
        and ((token_hits / max(latin_words, 1)) >= 0.12 or token_kinds >= 3)
    )
    if not is_latin_mix:
        return {"script": None, "tenglish": False, "hinglish": False}

    telugu_tokens = {"enti", "ela", "baga", "baaga", "chudu", "choodu", "cheppu",
                     "cheppandi", "avunu", "ledu", "inka", "mawa", "endi",
                     "antey", "ante", "kada", "nenu", "nuvvu", "meeru",
                     "nijam", "asalu"}
    hindi_tokens = {"kyun", "kyu", "matlab", "nahi", "nahin", "achha", "acha",
                    "thoda", "bahut", "hoon", "hunga", "dost", "bhai", "arre",
                    "chal", "chalo", "dekho", "suno", "theek"}
    t = sum(1 for w in words if w in telugu_tokens)
    h = sum(1 for w in words if w in hindi_tokens)
    if t >= h:
        return {"script": None, "tenglish": True, "hinglish": False}
    return {"script": None, "tenglish": False, "hinglish": True}


def mirror_instruction(text: str) -> str:
    """The prompt block enforcing the mirror rule for THIS message. Empty for
    plain English — English needs no instruction, and an absent block keeps
    prompts byte-stable for existing flows/tests."""
    reg = detect_register(text)
    if reg["script"] == "telugu":
        return (
            "LANGUAGE MIRROR: the writer just wrote in TELUGU. Reply in "
            "natural, conversational Telugu -- the way people actually talk "
            "about films, not textbook Telugu. Keep craft terms (beat, arc, "
            "payoff) as the writer uses them. Do NOT switch to English, do "
            "not translate their words back at them."
        )
    if reg["script"] == "hindi":
        return (
            "LANGUAGE MIRROR: the writer just wrote in HINDI (Devanagari). "
            "Reply in natural, conversational Hindi -- filmi spoken Hindi, "
            "not shuddh textbook prose. Keep craft terms as the writer uses "
            "them. Do NOT switch to English."
        )
    if reg["tenglish"]:
        return (
            "LANGUAGE MIRROR: the writer writes in TENGLISH (Telugu + English "
            "mixed in Latin script). Reply in the same natural Tenglish mix -- "
            "match their ratio of Telugu to English, keep it casual. Never "
            "translate them, never upgrade to formal English."
        )
    if reg["hinglish"]:
        return (
            "LANGUAGE MIRROR: the writer writes in HINGLISH (Hindi + English "
            "mixed in Latin script). Reply in the same natural Hinglish mix -- "
            "match their ratio, keep it casual. Never translate them, never "
            "upgrade to formal English."
        )
    return ""


# --------------------------------------------------------------------------
# Reply-side register check (P2.9).
#
# The writer writes SHORT messages; the co-writer writes long prose. The bar
# above is calibrated for the first and does NOT transfer to the second --
# measured on the repo's own shipped mirror replies (13-15 words each),
# `detect_register` reads 2 of the 3 genuine Tenglish / Hinglish replies as
# plain English, because the same token density that clears 0.12 in a 4-word
# message reads 0.07 in a 15-word one. Judging a reply by that instrument
# would re-ask on the product's own demo output, so the Tenglish / Hinglish
# half of this check is BLOCKED until there is a length-independent Indic-Latin
# instrument. The prerequisite is a real corpus of reply-length code-mixed
# text; a lexicon transcribed from one demo fixture would be overfitting, not
# calibration. The measurement is recorded in the test file and the docs.
#
# What IS sound today is the SCRIPT half. Unicode blocks are exact, carry no
# threshold to tune, and do not care how long either side is: a writer who
# wrote Telugu and got back a reply with no Telugu in it is not a judgement
# call. That half ships.
# --------------------------------------------------------------------------

# A stray Telugu/Devanagari word inside an English sentence is a loanword, not
# a language choice. A phrase is. Six characters is the low end of a real
# phrase (and well above the >=2 that `detect_register` uses to classify).
STRONG_SCRIPT_CHARS = 6

# Below this a reply cannot be judged: "Correct." carries no register either
# way, and a re-ask on it would be a false accusation.
MIN_JUDGEABLE_WORDS = 10


def register_mismatch(writer_text: str, reply: str) -> str | None:
    """The register the reply DROPPED, or None. Script registers only — see
    the note above on why the Latin-mix half is not judged here.

    Deliberately conservative in three places, because the caller spends a
    second generation on a positive: the writer must have written a real
    phrase in the script, the reply must be long enough to have had a chance
    to mirror, and the reply must contain NONE of that script at all. A
    partial mirror is not a failure worth re-asking over.
    """
    script = (detect_register(writer_text) or {}).get("script")
    if not script:
        return None
    pattern = _TELUGU_CHAR if script == "telugu" else _DEVANAGARI_CHAR
    if len(pattern.findall(writer_text or "")) < STRONG_SCRIPT_CHARS:
        return None  # a stray word is not a language choice
    # Length in WHITESPACE-separated tokens, not in Latin words. A reply
    # written in Telugu script contains no Latin words at all, so a Latin word
    # count would read every correct reply as "zero words, too short to judge"
    # and return None before ever reaching the check below — right answer,
    # wrong reason, and the guard would be dead for exactly the case it exists
    # to detect.
    if len((reply or "").split()) < MIN_JUDGEABLE_WORDS:
        return None  # too short to judge — silence is not a language slip
    if pattern.search(reply or ""):
        return None
    return script


def reply_is_non_latin(text: str) -> bool:
    """True when `text` carries letters outside the Latin blocks.

    Exact, threshold-free, and length-independent: a character is either a
    Latin letter or it is not. Accented Latin letters (é, ñ) count as Latin —
    they are still the same alphabet — so this asks "is this written in a
    different SCRIPT", not "is this pure ASCII".

    Used by the nudge gate in `peer.ensure_forward_momentum`: the nudge list is
    English-only, and appending an English question to a reply the mirror rule
    just kept in Telugu is the engine breaking its own register guarantee.
    """
    import unicodedata

    for ch in text or "":
        if not ch.isalpha() or ch.isascii():
            continue
        if not unicodedata.name(ch, "").startswith("LATIN"):
            return True
    return False


def mirror_reask_instruction(text: str) -> str:
    """The one soft re-ask, used only when the reply dropped the writer's
    SCRIPT register. Names the language, asks for the SAME answer rather than
    an apology, and forbids meta-commentary about the retry — a reply that
    opens with "sorry, let me try that again in Telugu" has spent the writer's
    tokens on the machinery instead of the work.

    Empty for every other register, so a caller can append it unconditionally.
    """
    script = (detect_register(text) or {}).get("script")
    if script == "telugu":
        lang = "Telugu"
    elif script == "hindi":
        lang = "Hindi"
    else:
        return ""
    return (
        f"Your reply came back in English, but the writer wrote in {lang}. "
        f"Answer again in {lang} — the same answer, the same content, nothing "
        "added. Do not mention this instruction, do not apologise, and do not "
        "comment on the language at all. Just answer."
    )
