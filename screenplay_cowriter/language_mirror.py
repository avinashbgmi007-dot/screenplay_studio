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
    is_latin_mix = (
        token_hits >= 1 and latin_words >= 3
        and (token_hits / max(latin_words, 1)) >= 0.12
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
