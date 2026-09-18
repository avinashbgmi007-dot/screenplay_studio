"""
Persona spec documents — codify what each persona never does.
Based on 2026 research into AI voice drift and anti-patterns.

These are deterministic rules that run AFTER the LLM generates a reply.
They catch voice drift that the model can't prevent on its own.

The shared list is split by HOW a phrase has to be removed, because the
removal strategy is what separates a clean reply from a mangled one:

- OPENERS / CLOSERS are standalone pleasantries. They must go as a WHOLE
  SENTENCE. Deleting the phrase alone leaves a fragment — that is exactly how
  "Great question! Let me think about this. Your act two sags." used to come
  out as "about this. Your act two sags."
- HEDGES sit inside a sentence and are rewritten in place (a clean equivalent
  where one exists), so the sentence stays grammatical.
- SELF-REFERENCE ("as an AI") is dropped in place, wherever it appears.
"""

import re

# --- Shared openers: removed as a whole leading sentence ---------------------
SHARED_OPENERS = [
    r"Great question",
    r"Absolutely",
    r"Love that",
    r"Sure thing",
    r"That'?s a (?:really )?(?:good|great|excellent|interesting|fair) (?:point|question)",
    r"I'?d be happy to(?: help(?: you)?(?: with (?:this|that))?)?",
    r"Thank you for (?:sharing|asking|bringing)",
    r"I (?:appreciate|understand) (?:your|the)",
    r"Let me (?:think about (?:this|that)|consider (?:this|that))",
    r"Let me (?:help|assist)(?: you)?(?: with (?:this|that))?",
]

# --- Shared closers: removed as a whole trailing sentence --------------------
SHARED_CLOSERS = [
    r"Let me know if you need anything else",
    r"I hope (?:this )?(?:helps|was helpful)",
    r"Hope (?:this|that) helps",
    r"Don'?t hesitate to (?:reach out|ask)",
    r"Feel free to (?:ask|reach out|let me know)",
]

# --- Shared hedges: rewritten in place ---------------------------------------
# (pattern, replacement) — a shorter, human equivalent where one exists.
SHARED_HEDGES = [
    (r"\bin order to\b", "to"),
    (r"\bdue to the fact that\b", "because"),
    (r"\bin terms of\b", "for"),
    (r"\bwith (?:regard|respect) to\b", "about"),
    (r"\b(?:it'?s (?:worth|important) (?:noting|mentioning|pointing out) that)\s*", ""),
    (r"\b(?:it goes without saying that|needless to say,?)\s*", ""),
    (r"\bat the end of the day,?\s*", ""),
]

# --- Shared self-reference: always wrong, dropped in place -------------------
SHARED_SELF_REFERENCE = [
    r"\bas an AI\b",
    r"\bas a language model\b",
    r"\bas an assistant\b",
]

# --- Sameer (writing_partner) banned phrases ---
# In-place removals only; the shared openers/closers/hedges are handled above,
# so they are deliberately NOT repeated here (they used to be, which is how the
# same phrase came to be applied twice per reply).
SAMEER_BANNED = [
    # Overly formal language
    r"\b(?:furthermore|moreover|additionally|consequently)\b",
    # Passive constructions
    r"\b(?:it (?:should be|could be|might be) noted)\b",
    # Generic encouragement without substance
    r"\b(?:keep (?:up|going|it up)|you'?re (?:doing|going) (?:great|well|amazing))\b",
]

# --- Sushruta (script_consultant) banned phrases ---
# NB: the exclamation rule is a REPLACEMENT ("!" -> "."), not a removal, so it
# lives in reply_transforms.persona_register where the register is set. As a
# removal pattern it would have deleted the marks instead of softening them.
SUSHRUTA_BANNED = [
    # Hedging — the doctor never hedges
    r"\b(?:I think|I feel|maybe|perhaps|it seems like|"
    r"it (?:appears|looks) (?:like|as if)|"
    r"this (?:might|could|may) be)\b",
    # Filler words
    r"\b(?:actually|basically|honestly|frankly|to be honest)\b",
    # Softening language
    r"\b(?:a little|somewhat|kind of|sort of|in a way)\b",
    # Compliments without substance
    r"\b(?:good (?:job|work|effort)|nice (?:work|job)|well done|great (?:work|effort))\b",
]

# --- Premise Doctor banned phrases ---
PREMISE_DOCTOR_BANNED = [
    # Overly academic language
    r"\b(?:furthermore|moreover|additionally|consequently|henceforth)\b",
    # Vague praise
    r"\b(?:interesting concept|compelling (?:idea|premise)|fascinating)\b",
    # Hedging
    r"\b(?:I think|I feel|maybe|perhaps|it seems like)\b",
]


def get_banned_phrases(persona: str) -> list[str]:
    """The persona's OWN additional in-place patterns.

    The shared openers/closers/hedges are not included: they are removed by
    strategy (whole sentence vs in-place) and are applied unconditionally, so
    folding them in here is what created the duplicate pass.
    """
    if persona == "writing_partner":
        return SAMEER_BANNED
    if persona == "script_consultant":
        return SUSHRUTA_BANNED
    if persona == "premise_doctor":
        return PREMISE_DOCTOR_BANNED
    return []


# A whole leading pleasantry, up to and including its terminator.
_OPENER_RE = re.compile(
    r"^\s*(?:" + "|".join(SHARED_OPENERS) + r")\b[^.!?\n]*[.!?]\s*",
    re.IGNORECASE,
)

# A whole trailing pleasantry.
_CLOSER_RE = re.compile(
    r"\s*(?:" + "|".join(SHARED_CLOSERS) + r")\b[.!?]?\s*$",
    re.IGNORECASE,
)


def _tidy(text: str, capitalize: bool = False) -> str:
    """Whitespace and punctuation repair, so a removal never leaves ' .' or a
    lowercase sentence start behind.

    `capitalize` is only set when something was actually stripped from the
    FRONT of the reply: that is what creates a lowercase continuation. Doing it
    unconditionally would rewrite a legitimately lowercase reply that the
    filter never touched.
    """
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+([.!?,;:])", r"\1", text)
    text = re.sub(r"([.!?,;:])(?=[^\s.!?,;:\n])", r"\1 ", text)
    text = re.sub(r"^[\s.,;:!?]+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if capitalize and text[:1].islower():
        text = text[0].upper() + text[1:]
    return text


def strip_banned_phrases(reply: str, persona: str = "") -> str:
    """Remove canned AI phrasing from a reply.

    Correct by construction: opener and closer pleasantries go as WHOLE
    sentences, hedges are rewritten in place, self-reference is dropped, then
    the text is tidied. The previous implementation deleted every pattern in
    place, so "Great question! Let me think about this. Your act two sags."
    became "about this. Your act two sags." — the anti-AI filter manufacturing
    the damage it exists to prevent.
    """
    original = reply or ""
    text = original
    stripped_from_front = False

    # 1. Leading pleasantries — a reply can open with more than one.
    for _ in range(4):
        new = _OPENER_RE.sub("", text, count=1)
        if new == text:
            break
        text = new
        stripped_from_front = True

    # 2. Hedges — rewritten, so the sentence survives intact.
    for pat, repl in SHARED_HEDGES:
        if re.match(pat, text, flags=re.IGNORECASE):
            stripped_from_front = True
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)

    # 3. Self-reference and persona-specific patterns — dropped in place.
    for pat in SHARED_SELF_REFERENCE:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)
    for pat in get_banned_phrases(persona):
        text = re.sub(pat, "", text, flags=re.IGNORECASE)

    # 4. Trailing pleasantries.
    for _ in range(4):
        new = _CLOSER_RE.sub("", text, count=1)
        if new == text:
            break
        text = new

    cleaned = _tidy(text, capitalize=stripped_from_front)
    # A reply that was NOTHING but pleasantries would strip to empty. Emitting
    # an empty turn is worse than emitting the original, so fall back to it.
    return cleaned or _tidy(original)
