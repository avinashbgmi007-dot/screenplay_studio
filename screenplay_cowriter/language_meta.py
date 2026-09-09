"""
Keeps the co-writer's replies free of "non-writing" feedback — commentary
about the script's LANGUAGE itself rather than its craft (dialect
identification, subtitle/accessibility meta-commentary). Local models
reviewing a Tenglish/Hindi script will occasionally spend a sentence
identifying the dialect ("reads as regional — probably Telugu") or warning
that it "needs subtitles for non-native speakers". That is noise for the
writer, so it's stripped from replies.

Deliberately self-contained: Piece 3 must keep working standalone without
importing screenplay_analyzer (the analyzer has a sibling filter in
screenplay_analyzer/feedback_filter.py — keep the pattern sets in sync).
"""

from __future__ import annotations

import json
import re

_LANGUAGE_ID_PATTERNS = [
    re.compile(r"reads as (a )?(regional|tenglish|hinglish|indian)", re.I),
    re.compile(r"(comes across|comes off|sounds) (as |like )?(a )?(regional|tenglish|hinglish)", re.I),
    re.compile(r"probably (a )?(telugu|tamil|hindi|kannada|malayalam|tenglish|hinglish)", re.I),
    re.compile(r"likely (a )?(telugu|tamil|hindi|kannada|malayalam|tenglish|hinglish)", re.I),
    re.compile(r"(telugu|tamil|hindi|kannada|malayalam|tenglish|hinglish) (language|dialect)", re.I),
    re.compile(r"(south|north|southern|northern) indian (language|dialect)", re.I),
    re.compile(r"(an?|the) indian (language|dialect)", re.I),
    re.compile(r"language (appears|seems|looks) to be", re.I),
    re.compile(r"(identif\w*).{0,40}language", re.I),
    re.compile(r"mixed[- ]language", re.I),
    re.compile(r"code[- ]switc", re.I),
    re.compile(r"regional (language|dialect|accent)", re.I),
    re.compile(r"what (language|dialect)", re.I),
]

_SUBTITLE_PATTERNS = [
    re.compile(r"subtitle", re.I),
    re.compile(r"non[- ]native (speaker|viewer|audience)", re.I),
    re.compile(r"(viewer|audience)s? (who|that) (don'?t|do not|won'?t) (speak|understand)", re.I),
    re.compile(r"(foreign|international|western) (viewer|audience)", re.I),
    re.compile(r"translat\w+ (is |would be )?(needed|required)", re.I),
    re.compile(r"needs? (either )?subtitles", re.I),
]

_PATTERNS = _LANGUAGE_ID_PATTERNS + _SUBTITLE_PATTERNS

# Sentence boundary: punctuation + space + a capital letter / quote / paren.
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(“«])")


def _matches_any(text: str) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in _PATTERNS)


def strip_language_meta(text: str) -> str:
    """Remove sentences/lines that are meta-commentary about the script's
    language. Craft sentences next to the meta commentary survive — only the
    offending sentences are cut, so the reply keeps its flow and substance."""
    if not text:
        return text
    kept_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or not _matches_any(stripped):
            kept_lines.append(line)
            continue
        # The line mentions the language — try sentence-level removal so
        # craft sentences in the same line survive.
        sentences = _SENT_SPLIT.split(stripped)
        kept = [s for s in sentences if s.strip() and not _matches_any(s)]
        if kept:
            kept_lines.append(" ".join(s.strip() for s in kept))
        # else the line was entirely meta — drop it
    out = "\n".join(kept_lines).strip("\n")
    # collapse >1 blank line runs left by dropped lines
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


_FENCED_JSON = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
_JSON_TEXT_KEYS = ("content", "answer", "reply", "response", "text", "message", "output")

# A whole line made of one repeated non-alphanumeric character: the signature
# of a local model stuck in a repetition loop — it fills the token budget with
# `_`, `-`, `=`, `*`, `.` separators (often one per line) instead of ending
# the reply. Note: underscore is a WORD char in Python regex, so the check is
# explicit set-membership rather than a backreference pattern.
#
# A second loop flavor leaks the chat template's end-of-turn tag as literal
# text (`<im_end|>`, `<|im_end|>`, `<im_im_end|>`, ...) when llama.cpp's stop
# tokens don't match the model's template — sometimes glued to a content line,
# sometimes as whole lines, sometimes cut off mid-tag (no closing `>`).
# Whole tag-debris lines are dropped.
_TAG_DEBRIS_LINE = re.compile(r"^<[^\s]*$")      # `<im_end|>` or cut-off `<im_im...`

# A third flavor leaks HTML-ish markup the model half-remembers from its
# training (`<div class="card">`, `<font color="#ff69b4" size="+2">`,
# `</br />`, `</div>`) — tags WITH attributes or spaces, which the no-space
# rule misses. Two branches: a letter-starting tag with anything inside
# (HTML, attributes allowed; the `</?[a-zA-Z]` guard keeps prose operators
# like "a < b" or "<-" intact), plus the original no-space `<tag>` shape
# (covers `<|im_end|>` etc., which don't start with a letter).
_TAG_TOKEN = re.compile(r"</?[a-zA-Z][^>]*>|<[^>\s]+>")


def strip_repetition_lines(text: str) -> str:
    """Drop degenerate repetition / leaked-tag debris from a model reply.

    Some local models (reasoning / "experts" quants especially) get stuck in
    a token loop and either fill the budget with separator lines (`_`, `-`,
    `=`, ...), repeat the chat template's end-of-turn tag (`<im_end|>`),
    glued to content or cut off mid-tag, or leak HTML-ish markup
    (`<div class="card">`, `<font color="...">`). Real content is untouched
    — removed are: lines that are ENTIRELY one repeated non-alphanumeric
    character; lines that are pure angle-bracket debris (no spaces, starts
    with `<`, complete or not); and `<tag>`/HTML tokens (with or without
    attributes) glued anywhere in the text. Blank runs are collapsed so the
    reply ends on the actual content. Keeps lines like "a_b_c" (mixed),
    digit runs, and prose with `<`/`>` operators (e.g. "a < b") untouched.
    """
    if not text:
        return text
    kept = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            kept.append(line)
            continue
        if len(set(stripped)) == 1 and not stripped[0].isalnum():
            continue  # degenerate separator line
        if _TAG_DEBRIS_LINE.match(stripped):
            continue  # leaked end-of-turn tag line (complete or cut off)
        kept.append(line)
    out = "\n".join(kept).strip("\n")
    out = _TAG_TOKEN.sub("", out).strip("\n")  # peel glued tags (incl. HTML) anywhere
    out = re.sub(r"\n{3,}", "\n\n", out)
    # Peel a separator glued to the very end of the reply ("grounded?_") — a
    # leftover from the same loop; content-ending punctuation is untouched.
    out = re.sub(r"[_-]+\s*$", "", out).rstrip()
    return out


_SIG_MAX_CHARS = 120
_SIG_MIN_LEN = 16      # a fingerprint this short is too generic to dedup on
_SIG_MIN_PREFIX = 36   # normalized leading chars that count as "the same block"


def _paragraph_signature(para: str) -> str | None:
    """Fingerprint of a paragraph's opening, used to spot a model re-answering
    the same point. Normalized (lowercased, alphanumerics only) first ~120
    chars, cut at the first sentence boundary within that window. Short
    paragraphs (< 20 chars — "what about scene 4?", "Yes.") return None so
    question echoes and one-liners are never deduped."""
    compact = " ".join(para.split())
    if len(compact) < 20:
        return None
    head = compact[:_SIG_MAX_CHARS]
    m = re.search(r"[.!?]", head)
    if m:
        head = head[: m.end()]
    sig = re.sub(r"[^a-z0-9]+", "", head.lower())
    return sig if len(sig) >= _SIG_MIN_LEN else None


def _is_question(para: str) -> bool:
    return para.strip().rstrip(".").endswith("?")


def _matches_seen(sig: str, seen: set) -> bool:
    """Exact match, or a long shared normalized prefix — the loop usually
    rephrases a little ("...not just explain" vs "...not just explain the
    situation"), so equality alone misses near-duplicates. A shared prefix
    shorter than _SIG_MIN_PREFIX (two genuinely different follow-ups, e.g.
    "Do you want the doctor to be..." in distinct forms) stays distinct."""
    for s in seen:
        if sig == s:
            return True
        shorter, longer = (sig, s) if len(sig) < len(s) else (s, sig)
        if len(shorter) >= _SIG_MIN_PREFIX and longer.startswith(shorter):
            return True
    return False


def strip_repeated_blocks(text: str) -> str:
    """Collapse a model's *semantic* repetition loop at the paragraph level.

    The line-level cleaner (strip_repetition_lines) handles separator/tag
    garbage; a different loop flavor re-answers the same point several times
    in one reply, each repetition restarting with the same opening sentence
    (sometimes re-echoing the user's question first). Paragraphs whose
    opening fingerprint matches an earlier paragraph (exact, or via a long
    shared normalized prefix) are dropped, keeping the first occurrence. A
    question echo is also dropped when the answer block directly after it
    repeats an opening already seen — that is the loop re-asking before it
    repeats. First occurrences always survive; paragraphs too short to
    fingerprint always survive.
    """
    if not text:
        return text
    paragraphs = re.split(r"\n\s*\n", text.strip("\n"))
    kept = []
    seen = set()
    for i, para in enumerate(paragraphs):
        sig = _paragraph_signature(para)
        if sig is not None and _matches_seen(sig, seen):
            continue  # repeated answer block
        nxt = paragraphs[i + 1] if i + 1 < len(paragraphs) else None
        if (
            sig is not None
            and _is_question(para)
            and nxt is not None
            and _paragraph_signature(nxt) is not None
            and _matches_seen(_paragraph_signature(nxt), seen)
        ):
            continue  # question echo before an already-seen answer
        kept.append(para)
        if sig is not None:
            seen.add(sig)
    out = "\n\n".join(kept).strip("\n")
    return re.sub(r"\n{3,}", "\n\n", out)


def _unwrap_parsed(parsed, original: str) -> str:
    """Extract the natural-language part of a parsed JSON reply; fall back to
    the original when there's nothing to unwrap."""
    if isinstance(parsed, str):
        return parsed.strip() or original
    if isinstance(parsed, dict):
        for key in _JSON_TEXT_KEYS:
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if len(parsed) == 1:
            only = next(iter(parsed.values()))
            if isinstance(only, str) and only.strip():
                return only.strip()
    return original


def strip_json_wrap(text: str) -> str:
    """Unwrap a chat reply that a model decided to JSON-ify on its own.

    The co-writer never asks for structured output in conversation (the
    system prompt now says so explicitly), but some local models — reasoning
    or JSON-tuned distills — wrap their answer anyway. A ```json fence is
    searched for ANYWHERE in the reply (models sometimes preface it with a
    sentence); otherwise the reply is treated as JSON only when it's pure
    JSON (starts with `{` or `[`). The natural-language part — the
    content/answer/reply/... field, or the sole string value — replaces the
    wrapper; anything that isn't JSON-shaped, or doesn't parse, passes
    through untouched.
    """
    if not text:
        return text
    stripped = text.strip()
    fenced = _FENCED_JSON.search(stripped)
    if fenced:
        try:
            parsed = json.loads(fenced.group(1).strip())
        except ValueError:
            return text
        return _unwrap_parsed(parsed, text)
    if not (stripped.startswith("{") or stripped.startswith("[")):
        return text
    try:
        parsed = json.loads(stripped)
    except ValueError:
        return text
    return _unwrap_parsed(parsed, text)
