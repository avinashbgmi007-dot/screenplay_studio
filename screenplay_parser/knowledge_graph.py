"""
Knowledge graph — deterministic structural layer.

This is explicitly a CANDIDATE GENERATOR, not a semantic judgment engine.
Piece 1 stays model-free by design, so what it can offer here is fast,
free, reliable structural extraction: who's in which scene, what objects
get emphasized and recur, what the timeline looks like, what dialogue
sounds like a promise. It cannot judge whether a recurring object was
narratively *significant* (Chekhov's Gun) or whether a promise was
actually *paid off* — that's semantic judgment, and it belongs in Piece 2
where a model is available, using this module's output as its retrieval
scaffold (so the model only has to look at scenes where a candidate
actually appears, not re-read the whole script).

This mirrors the find-candidates -> judge-significance -> suggest-resolution
pattern discussed for the Principles Engine: this module is stage one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

from .models import ScriptDocument, ElementType

# ---- extraction heuristics ----

AGE_RE = re.compile(r"\b(\d{1,3})\s*(?:s\b|years?[\s-]old\b)")
INTRO_DESCRIPTOR_RE = re.compile(r"\(([^)]{3,80})\)")  # parenthetical near a character's name in action text

TIME_SKIP_RE = re.compile(
    r"\b(LATER|MOMENTS LATER|THE NEXT (?:DAY|MORNING|NIGHT)|EARLIER|"
    r"\d+\s+(?:YEARS?|MONTHS?|WEEKS?|DAYS?|HOURS?)\s+(?:LATER|AGO)|"
    r"(?:19|20)\d{2})\b",
    re.IGNORECASE,
)

PROMISE_RE = re.compile(
    r"\b(I'?ll (?:tell|show|explain|prove)|I promise|when this is (?:all )?over|"
    r"you'?ll understand|someday you'?ll|I swear|trust me,? (?:I|you))\b",
    re.IGNORECASE,
)

# capitalized or emphasized noun phrase candidates in action text — the heuristic
# proxy for "this object was given narrative weight". Deliberately conservative:
# requires the phrase to appear with a leading article (a/an/the) OR be fully
# capitalized (common script convention for emphasizing a significant object on
# first appearance), and to recur in more than one scene to count as a candidate.
EMPHASIZED_NOUN_RE = re.compile(
    r"\b(?:a|an|the)\s+((?:[A-Z][A-Za-z\'-]*\s*){1,3}\b(?:[A-Z]{2,}|[a-z]+))\b"
)
ALLCAPS_NOUN_RE = re.compile(r"\b([A-Z]{3,}(?:\s[A-Z]{3,}){0,2})\b")

STOPWORD_CANDIDATES = {
    "THE", "AND", "BUT", "FOR", "WITH", "FROM", "INT", "EXT", "DAY", "NIGHT",
    "CONTINUOUS", "LATER", "MOMENTS", "CUT", "FADE", "SAME",
}


@dataclass
class TraitMention:
    scene_number: int
    text: str
    kind: str  # "age" | "descriptor"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CharacterEntry:
    name: str
    scenes_present: list = field(default_factory=list)
    scene_dialogue_counts: dict = field(default_factory=dict)  # scene_number -> line count
    first_scene: int = None
    last_scene: int = None
    trait_mentions: list = field(default_factory=list)  # list[TraitMention]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "scenes_present": self.scenes_present,
            "scene_dialogue_counts": self.scene_dialogue_counts,
            "first_scene": self.first_scene,
            "last_scene": self.last_scene,
            "trait_mentions": [t.to_dict() for t in self.trait_mentions],
        }


@dataclass
class PropCandidate:
    name: str
    scenes_mentioned: list = field(default_factory=list)
    mention_texts: list = field(default_factory=list)  # list[{"scene": int, "text": str}]

    @property
    def mention_count(self) -> int:
        return len(self.mention_texts)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "scenes_mentioned": self.scenes_mentioned,
            "mention_count": self.mention_count,
            "mention_texts": self.mention_texts,
        }


@dataclass
class TimelineEntry:
    scene_number: int
    int_ext: str
    time_of_day: str
    explicit_markers: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PromiseCandidate:
    scene_number: int
    character: str
    text: str
    pattern_matched: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class KnowledgeGraph:
    characters: dict = field(default_factory=dict)  # name -> CharacterEntry
    prop_candidates: list = field(default_factory=list)  # list[PropCandidate]
    timeline: list = field(default_factory=list)  # list[TimelineEntry]
    promise_candidates: list = field(default_factory=list)  # list[PromiseCandidate]
    character_cooccurrence: dict = field(default_factory=dict)  # "A|B" -> list[scene_number]

    def to_dict(self) -> dict:
        return {
            "characters": {k: v.to_dict() for k, v in self.characters.items()},
            "prop_candidates": [p.to_dict() for p in self.prop_candidates],
            "timeline": [t.to_dict() for t in self.timeline],
            "promise_candidates": [p.to_dict() for p in self.promise_candidates],
            "character_cooccurrence": self.character_cooccurrence,
        }

    def save(self, path: str) -> None:
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


def _extract_trait_mentions(scene, character_name: str) -> list:
    """Look for age/descriptor parentheticals near a character's first mention
    in this scene's action text (common script convention:
    'JOHN (30s, unshaven, tired eyes) sits alone.')."""
    mentions = []
    for el in scene.elements:
        if el.type != ElementType.ACTION:
            continue
        if character_name not in el.text:
            continue
        idx = el.text.find(character_name)
        # only look at a small window right after the name — this is where
        # intro descriptors conventionally appear, not anywhere in the sentence
        window = el.text[idx: idx + len(character_name) + 90]
        paren_match = INTRO_DESCRIPTOR_RE.search(window)
        if not paren_match:
            continue
        descriptor = paren_match.group(1)
        age_match = AGE_RE.search(descriptor)
        if age_match:
            mentions.append(TraitMention(scene_number=scene.scene_number, text=descriptor, kind="age"))
        else:
            mentions.append(TraitMention(scene_number=scene.scene_number, text=descriptor, kind="descriptor"))
    return mentions


def _extract_prop_candidates(doc: ScriptDocument) -> list:
    candidates: dict = {}  # normalized name -> PropCandidate

    for scene in doc.scenes:
        for el in scene.elements:
            if el.type != ElementType.ACTION:
                continue
            found_in_line = set()

            for m in ALLCAPS_NOUN_RE.finditer(el.text):
                phrase = m.group(1).strip()
                words = phrase.split()
                # skip if it's actually a character name/cue, or a stopword artifact
                if phrase in doc.all_characters:
                    continue
                if all(w in STOPWORD_CANDIDATES for w in words):
                    continue
                if len(phrase) < 3:
                    continue
                found_in_line.add(phrase)

            for phrase in found_in_line:
                key = phrase.upper()
                if key not in candidates:
                    candidates[key] = PropCandidate(name=phrase)
                entry = candidates[key]
                if scene.scene_number not in entry.scenes_mentioned:
                    entry.scenes_mentioned.append(scene.scene_number)
                entry.mention_texts.append({"scene": scene.scene_number, "text": el.text[:160]})

    # only keep candidates that recur across 2+ scenes — a single mention is
    # far more likely to be incidental description than a planted setup
    return [c for c in candidates.values() if len(c.scenes_mentioned) >= 2]


def _extract_timeline(doc: ScriptDocument) -> list:
    timeline = []
    for scene in doc.scenes:
        markers = []
        for el in scene.elements:
            if el.type == ElementType.ACTION:
                markers.extend(m.group(0) for m in TIME_SKIP_RE.finditer(el.text))
        timeline.append(TimelineEntry(
            scene_number=scene.scene_number,
            int_ext=scene.int_ext,
            time_of_day=scene.time_of_day,
            explicit_markers=list(dict.fromkeys(markers)),  # dedupe, preserve order
        ))
    return timeline


def _extract_promise_candidates(doc: ScriptDocument) -> list:
    promises = []
    for scene in doc.scenes:
        for el in scene.elements:
            if el.type != ElementType.DIALOGUE or not el.character:
                continue
            m = PROMISE_RE.search(el.text)
            if m:
                promises.append(PromiseCandidate(
                    scene_number=scene.scene_number,
                    character=el.character,
                    text=el.text,
                    pattern_matched=m.group(0),
                ))
    return promises


def _build_character_index(doc: ScriptDocument) -> dict:
    characters: dict = {name: CharacterEntry(name=name) for name in doc.all_characters}

    for scene in doc.scenes:
        for name in scene.characters_present:
            entry = characters[name]
            if scene.scene_number not in entry.scenes_present:
                entry.scenes_present.append(scene.scene_number)
            if entry.first_scene is None:
                entry.first_scene = scene.scene_number
            entry.last_scene = scene.scene_number

        dialogue_counts_this_scene: dict = {}
        for el in scene.elements:
            if el.type == ElementType.DIALOGUE and el.character:
                dialogue_counts_this_scene[el.character] = dialogue_counts_this_scene.get(el.character, 0) + 1
        for name, count in dialogue_counts_this_scene.items():
            if name in characters:
                characters[name].scene_dialogue_counts[scene.scene_number] = count

        for name in scene.characters_present:
            characters[name].trait_mentions.extend(_extract_trait_mentions(scene, name))

    return characters


def _build_cooccurrence(doc: ScriptDocument) -> dict:
    cooc: dict = {}
    for scene in doc.scenes:
        present = sorted(scene.characters_present)
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                key = f"{present[i]}|{present[j]}"
                cooc.setdefault(key, []).append(scene.scene_number)
    return cooc


def build_knowledge_graph(doc: ScriptDocument) -> KnowledgeGraph:
    return KnowledgeGraph(
        characters=_build_character_index(doc),
        prop_candidates=_extract_prop_candidates(doc),
        timeline=_extract_timeline(doc),
        promise_candidates=_extract_promise_candidates(doc),
        character_cooccurrence=_build_cooccurrence(doc),
    )
