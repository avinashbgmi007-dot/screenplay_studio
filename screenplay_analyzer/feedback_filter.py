"""
Filters out "non-writing" feedback — commentary about the script's LANGUAGE
itself rather than about the craft of the writing.

A local model reviewing a Tenglish / Hindi / Tamil script will sometimes
spend a finding identifying the dialect ("reads as regional — probably
Telugu or a South Indian language") or warning about accessibility ("it'll
need either subtitles or context for non-native speakers"). For a writer
mid-read that is noise, not feedback: it breaks the momentum of the notes,
and it's information they already have (they wrote it). Feedback belongs to
story, character, dialogue, structure, and craft — never to "what language
is this script in".

The filter is deliberately conservative: it only drops findings whose
issue/why_it_matters is dominated by language identification or
subtitle/accessibility meta-commentary, plus notes whose whole complaint is
that non-English dialogue is hard to read (language named in the
observation, incomprehension pleaded in the claim). Craft feedback that quotes a
Tenglish line as evidence, or discusses a character's voice, is kept.
"""

from __future__ import annotations

import re

# --- patterns for "I can't read this" claims (trial 5: a Tamil exchange was
# filed high-severity "opaque text, impossible to assess" with the language
# mention sitting in `observation`, which no pattern scanned) ---
_INCOMPREHENSION_PATTERNS = [
    re.compile(r"opaque", re.I),
    re.compile(r"impossible to assess", re.I),
    re.compile(r"cann?ot be (assessed|evaluated|understood)", re.I),
    re.compile(r"unable to (assess|evaluate|understand)", re.I),
    re.compile(r"without (context or )?subtitles", re.I),
    re.compile(r"phonetic", re.I),
    re.compile(r"language mixing", re.I),
    re.compile(r"creates? confusion", re.I),
]

# --- claim-side transliteration complaints (trial 13: both halves of the
# pattern sit in the claim — "untransliterated foreign language ...
# inaccessible to non-speakers", "transliterated language ... impossible
# to evaluate" — where the observation-side rule cannot see them). Both
# halves must hit on issue+why_it_matters (quotes exempt, as throughout):
# a language-vehicle signal AND an incomprehension plea. Either half alone
# is a legitimate note ("the Romanized Tamil dialogue is punchy" judges
# voice; "the timeline is impossible to evaluate" is about staging).
_REGISTER_LANG = [
    re.compile(r"transliterat\w*", re.I),
    re.compile(r"untransliterated", re.I),
    re.compile(r"foreign language", re.I),
    re.compile(r"romanized", re.I),
]
_REGISTER_HARM = [
    re.compile(r"inaccessible", re.I),
    re.compile(r"unintelligible", re.I),
    re.compile(r"impossible to (evaluate|assess|understand)", re.I),
    re.compile(r"without (providing )?(context|translation|an? english equivalent|subtitles)", re.I),
]

# --- patterns for commentary that identifies / classifies the language ---
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

# --- patterns for accessibility / subtitle meta-commentary ---
_SUBTITLE_PATTERNS = [
    re.compile(r"subtitle", re.I),
    re.compile(r"non[- ]native (speaker|viewer|audience)", re.I),
    re.compile(r"(viewer|audience)s? (who|that) (don'?t|do not|won'?t) (speak|understand)", re.I),
    re.compile(r"(foreign|international|western) (viewer|audience)", re.I),
    re.compile(r"translat\w+ (is |would be )?(needed|required)", re.I),
    re.compile(r"needs? (either )?subtitles", re.I),
    re.compile(r"untranslated", re.I),
    re.compile(r"phonetic (transcription|transliteration|script)", re.I),
    re.compile(r"(obscures|blocks|barrier to) (meaning|understanding)", re.I),
    re.compile(r"mix(es|ed|ing) languages without", re.I),
]


def _matches_any(text: str, patterns: list) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in patterns)


def is_non_writing_feedback(finding: dict) -> bool:
    """True when the finding is meta-commentary about the script's language
    rather than feedback on the writing. Looks at issue + why_it_matters
    (the finding's claims); evidence_quote is exempt since it's verbatim
    script text by design. The observation IS scanned for language
    identification, but only together with an "I can't read this" claim —
    a craft note that quotes a Tenglish line as evidence is kept, while a
    note whose whole complaint is that the dialogue is in another language
    (trial 5: Tamil filed "opaque, impossible to assess") is dropped, as is
    a claim-side transliteration complaint pairing the vehicle with
    incomprehension (trial 13)."""
    if not isinstance(finding, dict):
        return False
    issue = str(finding.get("issue") or "")
    why = str(finding.get("why_it_matters") or "")
    combined = f"{issue} {why}"
    if _matches_any(combined, _LANGUAGE_ID_PATTERNS) or _matches_any(combined, _SUBTITLE_PATTERNS):
        return True
    obs = str(finding.get("observation") or "")
    if ((_matches_any(obs, _LANGUAGE_ID_PATTERNS) or _matches_any(obs, _SUBTITLE_PATTERNS))
            and _matches_any(combined, _INCOMPREHENSION_PATTERNS)):
        return True
    return (_matches_any(combined, _REGISTER_LANG)
            and _matches_any(combined, _REGISTER_HARM))


def filter_findings(findings) -> list:
    """Drop non-writing feedback findings, preserving order of the rest."""
    kept, _ = partition_findings(findings)
    return kept


def partition_findings(findings) -> tuple[list, list]:
    """(kept, removed) under the same predicate — the removed half comes
    back so callers can record what left. A guardrail whose firings are
    unobservable cannot be validated by any trial (trial 9); non-dict
    garbage is dropped on the floor as before, never ledgered."""
    kept, removed = [], []
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        (removed if is_non_writing_feedback(f) else kept).append(f)
    return kept, removed


# --- patterns where the observation rebuts the note (accuracy kit A) ---
_CONTRADICTION_PATTERNS = [
    re.compile(r"\bhowever\b", re.I),
    re.compile(r"\bactually\b.{0,30}\b(not|no)\b", re.I),
    re.compile(r"\bcontradicts?\b", re.I),
    re.compile(r"\bno evidence\b", re.I),
    re.compile(r"\bclaims?\b.{0,30}\b(but|yet)\b", re.I),
]

_SEVERITY_LADDER = ("low", "medium", "high")


def is_refuted(finding: dict) -> bool:
    """True when the finding's own observation rebuts its note. Checks the
    observation only — the issue is the claim under test, never the judge."""
    if not isinstance(finding, dict):
        return False
    return _matches_any(str(finding.get("observation") or ""), _CONTRADICTION_PATTERNS)


def demote_severity(finding: dict) -> None:
    """One step down the ladder (high→medium→low); the shared primitive so
    every demotion path spells severity the same way."""
    sev = str(finding.get("severity") or "low").lower()
    if sev in _SEVERITY_LADDER[1:]:
        finding["severity"] = _SEVERITY_LADDER[_SEVERITY_LADDER.index(sev) - 1]


def demote_contested(finding: dict) -> None:
    demote_severity(finding)
    finding["contested"] = True
