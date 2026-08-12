"""
Deterministic craft analytics — act mapping, pacing curve, character arcs.

All computed purely from the parsed ScriptDocument, no model call. These are
the "free" structural views a writer expects from any coverage tool:

  - Act mapping: scenes bucketed into the classic three-act shape by page
    position (Act 1 ≈ first quarter, Act 2 ≈ middle half, Act 3 ≈ final
    quarter — the 30/60/30 convention scaled to any page count).
  - Pacing curve: per page-segment dialogue-vs-action word volume, so a
    writer can SEE where the script goes talky or gets dense with action.
  - Character arcs: factual per-character trajectory — first/last scene,
    scene presence, dialogue volume, and quiet-period gaps — so arc claims
    in the report have a concrete backbone to point at.

Page estimation: FDX/PDF parses carry page_start/page_end; text parses
don't, so we estimate a scene's page length from its content (action ~10
words/line, dialogue ~14 words/line, 54 lines/page). The estimate is a
proxy — it's labeled as such wherever it surfaces.
"""

from __future__ import annotations

import math

from .models import ElementType, ScriptDocument

LINES_PER_PAGE = 54.0
ACTION_WORDS_PER_LINE = 10.0
DIALOGUE_WORDS_PER_LINE = 14.0

# Act boundaries as fractions of total pages (30/60/30 scaled).
ACT_1_END = 0.25
ACT_2_END = 0.75


def estimate_scene_pages(doc: ScriptDocument) -> dict:
    """scene_number -> estimated page position (end of scene), using real
    pagination where the parser provided it, else a content proxy."""
    page_ends: dict = {}
    running = 0.0
    for scene in doc.scenes:
        if scene.page_start is not None and scene.page_end is not None:
            page_ends[scene.scene_number] = float(scene.page_end)
            running = float(scene.page_end)
            continue
        lines = 0.0
        for el in scene.elements:
            words = len(el.text.split())
            if el.type in (ElementType.ACTION, ElementType.SCENE_HEADING):
                lines += max(1, math.ceil(words / ACTION_WORDS_PER_LINE))
            elif el.type == ElementType.DIALOGUE:
                lines += max(1, math.ceil(words / DIALOGUE_WORDS_PER_LINE))
            else:
                lines += 1
        running += lines / LINES_PER_PAGE
        page_ends[scene.scene_number] = running
    return page_ends


def assign_acts(doc: ScriptDocument, pages: dict | None = None) -> list[dict]:
    """Bucket scenes into acts by page position. Returns a list of act dicts:
    {act: int, name: str, scene_numbers: [..], page_start, page_end}."""
    if not doc.scenes:
        return []
    pages = pages or estimate_scene_pages(doc)
    total = max(pages.values()) or 1.0
    act_1_end = ACT_1_END * total
    act_2_end = ACT_2_END * total

    acts = [
        {"act": 1, "name": "Act 1", "scene_numbers": [], "page_start": 1.0, "page_end": None},
        {"act": 2, "name": "Act 2", "scene_numbers": [], "page_start": None, "page_end": None},
        {"act": 3, "name": "Act 3", "scene_numbers": [], "page_start": None, "page_end": None},
    ]
    for scene in doc.scenes:
        pos = pages.get(scene.scene_number, 1.0)
        idx = 0 if pos <= act_1_end else (1 if pos <= act_2_end else 2)
        acts[idx]["scene_numbers"].append(scene.scene_number)
        if acts[idx]["page_start"] is None or pos < acts[idx]["page_start"]:
            acts[idx]["page_start"] = pos
        acts[idx]["page_end"] = pos

    for a in acts:
        if a["scene_numbers"]:
            a["page_start"] = round(a["page_start"], 1)
            a["page_end"] = round(a["page_end"], 1)
        else:
            a["page_start"] = None
            a["page_end"] = None
        a["scene_count"] = len(a["scene_numbers"])
    return acts


def act_for_scene(acts: list[dict], scene_number: int) -> int | None:
    for a in acts:
        if scene_number in a["scene_numbers"]:
            return a["act"]
    return None


def pacing_curve(doc: ScriptDocument, segment_pages: int = 5) -> dict:
    """Per page-segment dialogue/action word volume. Returns {segments: [
    {page_start, page_end, dialogue_words, action_words, scene_count}]}."""
    pages = estimate_scene_pages(doc)
    if not pages:
        return {"segments": []}
    total = max(pages.values()) or 1.0
    n_segments = max(1, math.ceil(total / segment_pages))
    segments = [
        {"page_start": i * segment_pages + 1, "page_end": min((i + 1) * segment_pages, math.ceil(total)),
         "dialogue_words": 0, "action_words": 0, "scene_count": 0}
        for i in range(n_segments)
    ]

    for scene in doc.scenes:
        pos = pages.get(scene.scene_number, 1.0)
        idx = min(int(pos // segment_pages), n_segments - 1)
        segments[idx]["scene_count"] += 1
        for el in scene.elements:
            words = len(el.text.split())
            if el.type == ElementType.DIALOGUE:
                segments[idx]["dialogue_words"] += words
            elif el.type == ElementType.ACTION:
                segments[idx]["action_words"] += words
    return {"segments": segments, "total_pages": round(total, 1), "segment_pages": segment_pages}


def character_arc(doc: ScriptDocument, kg_characters: dict | None = None) -> list[dict]:
    """Factual per-character trajectory. kg_characters is the Piece 1
    knowledge-graph character index (optional; enriches with trait mentions
    and per-scene dialogue counts when provided)."""
    from collections import Counter, defaultdict

    scene_of = {s.scene_number: s for s in doc.scenes}
    presence: dict = defaultdict(list)
    dialogue_counts: dict = Counter()

    for scene in doc.scenes:
        for c in scene.characters_present:
            presence[c].append(scene.scene_number)
        for el in scene.elements:
            if el.type == ElementType.DIALOGUE and el.character:
                dialogue_counts[el.character] += 1

    out = []
    for name, scenes in presence.items():
        first = scenes[0]
        last = scenes[-1]
        # quiet gaps: consecutive-scene stretches where the character is absent
        gaps = []
        if len(scenes) >= 2:
            for i in range(1, len(scenes)):
                gap_size = scenes[i] - scenes[i - 1] - 1
                if gap_size >= 2:
                    gaps.append({"after_scene": scenes[i - 1], "scenes_absent": gap_size})
        total_scenes = doc.scene_count
        entry = {
            "character": name,
            "first_scene": first,
            "last_scene": last,
            "scene_count": len(scenes),
            "scene_presence_pct": round(100 * len(scenes) / total_scenes, 1) if total_scenes else None,
            "dialogue_lines": dialogue_counts[name],
            "quiet_gaps": gaps,
            "appears_throughout": len(scenes) >= total_scenes * 0.6,
        }
        kg_entry = (kg_characters or {}).get(name)
        if kg_entry:
            entry["trait_mentions"] = [t.to_dict() if hasattr(t, "to_dict") else t for t in kg_entry.get("trait_mentions", [])]
        out.append(entry)

    out.sort(key=lambda c: (-c["scene_count"], c["first_scene"]))
    return out
