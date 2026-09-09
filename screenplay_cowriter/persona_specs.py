"""
Persona spec documents — codify what each persona never does.
Based on 2026 research into AI voice drift and anti-patterns.

These are deterministic rules that run AFTER the LLM generates a reply.
They catch voice drift that the model can't prevent on its own.
"""

import re

# --- Shared anti-AI tells (applied to all personas) ---
SHARED_BANNED_PHRASES = [
    # Canned openings
    r"\b(?:Great question[!.]|Absolutely[!.]|I'?d be happy to|"
    r"That'?s a (?:really )?(?:good|great|excellent|interesting) point[!.]|"
    r"Let me (?:help|think|consider|address)|"
    r"I (?:appreciate|understand) (?:your|the)|"
    r"Thank you for (?:sharing|asking|bringing))\b",
    # Hedging phrases
    r"\b(?:it'?s (?:worth|important) (?:noting|mentioning|pointing out) that)\b",
    r"\b(?:in (?:order to|terms of))\b",
    r"\b(?:due to the fact that)\b",
    r"\b(?:with (?:regard to|respect to))\b",
    r"\b(?:at the end of the day)\b",
    r"\b(?:it goes without saying)\b",
    r"\b(?:needless to say)\b",
    # Canned closings
    r"\b(?:let me know if you need anything else|"
    r"I (?:hope|hope this) (?:helps|was helpful)|"
    r"don'?t hesitate to (?:reach out|ask)|"
    r"feel free to (?:ask|reach out|let me know))\b",
    # AI self-reference
    r"\b(?:as an AI|as a language model|as an assistant)\b",
]

# --- Sameer (writing_partner) banned phrases ---
SAMEER_BANNED = [
    # AI assistant phrases that break the co-writer fiction
    r"\b(?:I'?d be happy to|Let me (?:help|assist)|"
    r"That'?s a (?:great|good|interesting) question|"
    r"I (?:understand|appreciate) your)\b",
    # Overly formal language
    r"\b(?:furthermore|moreover|additionally|consequently)\b",
    # Passive constructions
    r"\b(?:it (?:should be|could be|might be) noted)\b",
    # Generic encouragement without substance
    r"\b(?:keep (?:up|going|it up)|you'?re (?:doing|going) (?:great|well|amazing))\b",
]

# --- Sushruta (script_consultant) banned phrases ---
SUSHRUTA_BANNED = [
    # Hedging — the doctor never hedges
    r"\b(?:I think|I feel|maybe|perhaps|it seems like|"
    r"it (?:appears|looks) (?:like|as if)|"
    r"this (?:might|could|may) be)\b",
    # Filler words
    r"\b(?:actually|basically|honestly|frankly|to be honest)\b",
    # Softening language
    r"\b(?:a little|somewhat|kind of|sort of|in a way)\b",
    # Exclamation marks (already handled in _persona_register, but belt-and-suspenders)
    r"!",
    # Compliments without substance
    r"\b(?:good (?:job|work|effort)|nice (?:work|job)|well done|great (?:work|effort))\b",
]

# --- Premise Doctor banned phrases ---
PREMISE_DOCTOR_BANNED = [
    # Overly academic language
    r"\b(?:furthermore|moreover|additionally|consequently|henceforth)\b",
    # Vague praise
    r"\b(?:interesting concept|compelling (?:idea|premise)|fascinating)\b",
    # hedging
    r"\b(?:I think|I feel|maybe|perhaps|it seems like)\b",
]


def get_banned_phrases(persona: str) -> list[str]:
    """Return the banned phrases for a given persona."""
    base = SHARED_BANNED_PHRASES.copy()
    if persona == "writing_partner":
        return base + SAMEER_BANNED
    elif persona == "script_consultant":
        return base + SUSHRUTA_BANNED
    elif persona == "premise_doctor":
        return base + PREMISE_DOCTOR_BANNED
    return base


def strip_banned_phrases(reply: str, persona: str) -> str:
    """Strip banned phrases from a reply. Returns the cleaned reply."""
    banned = get_banned_phrases(persona)
    for pat in banned:
        reply = re.sub(pat, "", reply, flags=re.IGNORECASE)
    # Collapse multiple spaces
    reply = re.sub(r"  +", " ", reply)
    # Collapse space after punctuation
    reply = re.sub(r"([.!?,]) +", r"\1 ", reply)
    # Clean up orphaned sentence starts
    reply = re.sub(r"^ +", "", reply, flags=re.MULTILINE)
    return reply.strip()
