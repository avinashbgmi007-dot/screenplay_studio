"""
Deterministic craft passes that need no model call — they run on the parsed
script text alone, which makes them fast, mock-testable, and immune to
server/context failures:

  run_voice_analysis  — voice-bleed detection. Every writer has heard it:
                        "all my characters sound like me." Builds a style
                        fingerprint per character (word-frequency vector,
                        mean line length, word length, question/exclamation
                        rate) from their dialogue, then flags character
                        pairs whose fingerprints are suspiciously close AND
                        who share scenes (so the reader actually experiences
                        the confusion).

  run_subtext_analysis — on-the-nose dialogue detection. Flags dialogue
                        lines where a character names their own emotion
                        directly ("I'm so angry") — the classic note that
                        the subtext is missing. Conservative regex lexicon;
                        the writer judges each hit.

Both return (findings, errors) with errors always empty. Findings use the
standard schema (category/issue/why_it_matters/severity/scene_refs/
evidence_quote) and survive the pipeline's quote-verification step because
every evidence quote is a verbatim script line.
"""

from __future__ import annotations

import re
from collections import Counter

from screenplay_parser.models import ScriptDocument, ElementType

MIN_DIALOGUE_LINES = 3        # characters below this never get a fingerprint
VOICE_SIMILARITY_THRESHOLD = 0.72
_MAX_VOICE_PAIRS = 6          # cap findings — don't spam the writer
MAX_PROFILE_WORDS = 40        # words kept per character fingerprint

# ---------------------------------------------------------------------------
# voice-bleed
# ---------------------------------------------------------------------------

_STOPWORDS = set(
    "a an the and or but if then else of to in on at for with from by as is are was were "
    "be been being i you he she it we they me him her us them my your his its our their "
    "this that these those do does did have has had will would can could should shall "
    "not no yes yeah okay well so just really very what who when where why how".split()
)


def _dialogue_lines_by_character(doc: ScriptDocument) -> dict[str, list[str]]:
    lines: dict[str, list[str]] = {}
    for scene in doc.scenes:
        current = None
        for e in scene.elements:
            if e.type == ElementType.CHARACTER:
                current = e.text.strip()
            elif e.type == ElementType.DIALOGUE and current:
                lines.setdefault(current, []).append(e.text.strip())
                current = None  # one line per cue; parentheticals attach to it
    return lines


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-zA-Z']+", text.lower()) if w not in _STOPWORDS]


def _fingerprint(lines: list[str]) -> dict:
    words = []
    lengths, q_marks, bangs = [], 0, 0
    for ln in lines:
        words.extend(_words(ln))
        lengths.append(len(ln.split()))
        q_marks += ln.count("?")
        bangs += ln.count("!")
    freq = Counter(words)
    common = {w: c for w, c in freq.most_common(MAX_PROFILE_WORDS)}
    n = max(1, len(lengths))
    total_words = max(1, len(words))
    return {
        "freq": common,
        "mean_line_len": sum(lengths) / n,
        "mean_word_len": sum(len(w) for w in words) / total_words,
        "q_rate": q_marks / n,
        "bang_rate": bangs / n,
    }


def _cosine(a: dict, b: dict) -> float:
    keys = set(a["freq"]) | set(b["freq"])
    dot = sum(a["freq"].get(k, 0) * b["freq"].get(k, 0) for k in keys)
    na = sum(v * v for v in a["freq"].values()) ** 0.5
    nb = sum(v * v for v in b["freq"].values()) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _style_distance(a: dict, b: dict) -> float:
    """Normalized closeness of the non-vocabulary style signals (0 = identical)."""
    d = (
        abs(a["mean_line_len"] - b["mean_line_len"]) / max(1.0, a["mean_line_len"] + b["mean_line_len"])
        + abs(a["mean_word_len"] - b["mean_word_len"]) / max(0.5, a["mean_word_len"] + b["mean_word_len"])
        + abs(a["q_rate"] - b["q_rate"]) / max(0.05, a["q_rate"] + b["q_rate"] + 0.001)
        + abs(a["bang_rate"] - b["bang_rate"]) / max(0.05, a["bang_rate"] + b["bang_rate"] + 0.001)
    )
    return max(0.0, 1.0 - d / 4.0)


def _scenes_shared(doc: ScriptDocument, a: str, b: str) -> list[int]:
    shared = []
    for scene in doc.scenes:
        names = {c.upper() for c in scene.characters_present}
        if a.upper() in names and b.upper() in names:
            shared.append(scene.scene_number)
    return shared


def run_voice_analysis(doc: ScriptDocument) -> tuple[list[dict], list[str]]:
    by_char = _dialogue_lines_by_character(doc)
    profiles = {
        name: _fingerprint(lines)
        for name, lines in by_char.items()
        if len(lines) >= MIN_DIALOGUE_LINES
    }
    if len(profiles) < 2:
        return [], []

    names = sorted(profiles)
    scored = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            sim = _cosine(profiles[a], profiles[b]) * 0.7 + _style_distance(profiles[a], profiles[b]) * 0.3
            shared = _scenes_shared(doc, a, b)
            if sim >= VOICE_SIMILARITY_THRESHOLD and shared:
                scored.append((sim, a, b, shared))

    scored.sort(key=lambda t: -t[0])
    findings = []
    for sim, a, b, shared in scored[:_MAX_VOICE_PAIRS]:
        findings.append({
            "category": "voice",
            "issue": f"{a} and {b} read as the same voice — their dialogue fingerprints are near-identical "
                     f"(similarity {sim:.0%}) and they appear together in scenes {', '.join(map(str, shared))}.",
            "why_it_matters": "When two characters sound alike, the reader stops hearing people and starts "
                              "hearing the author. Distinct rhythm, word choice, and sentence length are how "
                              "a voice lives on the page.",
            "severity": "medium",
            "scene_refs": shared,
            "evidence_quote": by_char[a][0] if by_char[a] else None,
            "rule_id": "voice_bleed",
        })
    return findings, []


# ---------------------------------------------------------------------------
# subtext / on-the-nose dialogue
# ---------------------------------------------------------------------------

_EMOTION = (
    "angry|happy|sad|scared|afraid|hurt|tired|excited|worried|confused|nervous|"
    "jealous|proud|disappointed|furious|terrified|lonely|ashamed|guilty|frustrated|"
    "relieved|surprised|anxious|heartbroken|furious|mad|glad|frightened"
)

# Direct statements that name the speaker's own emotion — the classic
# on-the-nose tell. Deliberately excludes commands/questions/descriptions of
# other people's feelings, which are normal dialogue.
_ON_THE_NOSE_RE = re.compile(
    r"\b(i('m| am| feel| felt| was| became| got) (so |really |very )?(?:" + _EMOTION + r"))"
    r"|\b(i hate (you|this|it)|i love (you|this|it)|i('m| am) in love)\b",
    re.IGNORECASE,
)


def run_subtext_analysis(doc: ScriptDocument) -> tuple[list[dict], list[str]]:
    findings = []
    for scene in doc.scenes:
        current = None
        for e in scene.elements:
            if e.type == ElementType.CHARACTER:
                current = e.text.strip()
            elif e.type == ElementType.DIALOGUE and current:
                line = e.text.strip()
                m = _ON_THE_NOSE_RE.search(line)
                if m:
                    findings.append({
                        "category": "subtext",
                        "issue": f'On-the-nose line for {current}: "{line}" names the emotion outright — '
                                 f'the subtext is missing, so the scene tells instead of shows.',
                        "why_it_matters": "Real people rarely announce their feelings. When a line states the "
                                          "emotion directly, the moment lands flat; letting behavior and "
                                          "silence carry it makes the scene play.",
                        "severity": "low",
                        "scene_refs": [scene.scene_number],
                        "evidence_quote": line,
                        "rule_id": "on_the_nose",
                    })
                current = None
    return findings, []
