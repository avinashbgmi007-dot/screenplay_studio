"""
Character track — a per-character layer over the knowledge graph + report.

The writer asked for a clickable track of *important* characters: their
presence across the script, traits, and interactions with other characters.
Everything here is assembled from data the pipeline already produced — the
deterministic KG (presence, dialogue counts, trait mentions, co-occurrence)
and the report (character_dials scores + character_reads). No model calls
at serve time, so the track is instant and always consistent with the
analysis that produced it.

Importance is derived, not guessed: scenes present, dialogue share, and
co-occurrence breadth. A character is "main" when they appear in a solid
share of scenes and carry dialogue; "supporting" when present but lighter;
"bit" when barely present. The UI can show mains prominently and let the
writer expand the rest — the writer shouldn't have to scroll a wall of
every name that ever appears in an action line.
"""

from __future__ import annotations

import json
import os

# A character is "main" when they appear in at least this share of scenes
MAIN_SCENE_SHARE = 0.25
# ...or hold at least this share of total dialogue lines (voice-heavy roles)
MAIN_DIALOGUE_SHARE = 0.15
# A character is at least "supporting" at this scene share
SUPPORTING_SCENE_SHARE = 0.08


def build_character_tracks(kg_path: str, report: dict | None) -> list[dict]:
    """Returns character tracks ranked by importance (most important first).

    Each track: {name, importance, scenes_present, scene_count, dialogue_lines,
    dialogue_share, first_scene, last_scene, traits (KG mentions + dials),
    interactions: [{name, scenes}], reads}. Missing KG or report pieces are
    tolerated — the track degrades gracefully instead of erroring.
    """
    if not kg_path or not os.path.exists(kg_path):
        return []
    try:
        with open(kg_path, "r", encoding="utf-8") as f:
            kg = json.load(f)
    except (OSError, ValueError):
        return []

    characters = kg.get("characters") or {}
    cooccurrence = kg.get("character_cooccurrence") or {}
    if not characters:
        return []

    report = report if isinstance(report, dict) else {}
    dials_by_name = {d.get("character", "").upper(): d for d in (report.get("character_dials") or []) if isinstance(d, dict)}
    reads_by_name = {r.get("character", "").upper(): r for r in (report.get("character_reads") or []) if isinstance(r, dict)}

    total_dialogue = sum(
        sum((c.get("scene_dialogue_counts") or {}).values())
        for c in characters.values() if isinstance(c, dict)
    ) or 1

    tracks = []
    for name, entry in characters.items():
        if not isinstance(entry, dict):
            continue
        scenes = entry.get("scenes_present") or []
        dialogue_counts = entry.get("scene_dialogue_counts") or {}
        dialogue_lines = sum(dialogue_counts.values())

        # interactions: co-occurrence scenes with each other character
        interactions = []
        for key, scenes_together in cooccurrence.items():
            parts = key.split("|")
            if name in parts:
                other = parts[0] if parts[1] == name else parts[1]
                interactions.append({"name": other, "scenes": sorted(scenes_together)})
        interactions.sort(key=lambda i: -len(i["scenes"]))

        # traits: KG mentions (age/descriptor parentheticals) + dials scores
        traits = []
        for tm in entry.get("trait_mentions") or []:
            if isinstance(tm, dict) and tm.get("text"):
                traits.append({
                    "kind": tm.get("kind", "descriptor"),
                    "text": tm["text"],
                    "scene": tm.get("scene_number"),
                })
        dials = dials_by_name.get(name.upper())
        dial_traits = (dials.get("traits") or []) if dials else []

        scene_count = len(scenes)
        scene_share = scene_count / max(1, len(kg.get("timeline") or []) or scene_count)
        dialogue_share = dialogue_lines / total_dialogue
        if scene_share >= MAIN_SCENE_SHARE or dialogue_share >= MAIN_DIALOGUE_SHARE:
            importance = "main"
        elif scene_share >= SUPPORTING_SCENE_SHARE:
            importance = "supporting"
        else:
            importance = "bit"

        reads = reads_by_name.get(name.upper())

        tracks.append({
            "name": name,
            "importance": importance,
            "scenes_present": scenes,
            "scene_count": scene_count,
            "dialogue_lines": dialogue_lines,
            "dialogue_share": round(dialogue_share, 3),
            "first_scene": entry.get("first_scene"),
            "last_scene": entry.get("last_scene"),
            "traits": traits,
            "dials": dial_traits,
            "interactions": interactions[:8],
            "reads": reads,
        })

    tracks.sort(key=lambda t: (
        {"main": 0, "supporting": 1, "bit": 2}[t["importance"]],
        -t["scene_count"],
        -t["dialogue_lines"],
    ))
    return tracks
