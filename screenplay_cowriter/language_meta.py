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
