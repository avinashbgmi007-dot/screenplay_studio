"""
Deterministic screenplay analytics — computed purely from the structured
ScriptDocument, no model call involved. These are the "free" Phase-1 items:
character line counts, scene presence, dialogue/action ratios, location
usage. Piece 2 (Analyzer) can fold this straight into the report's Analytics
section without spending any tokens on it, and it's also useful as a sanity
check on parse quality (e.g. a character with 1 line when they should be a
lead usually means a name-normalization mismatch upstream).
"""

from collections import Counter, defaultdict

from .models import ElementType, ScriptDocument
from .structure import assign_acts, pacing_curve, character_arc

WORDS_PER_SCREEN_MINUTE = 160  # ~1 screenplay page per minute, ~160 words/page


def scene_estimates(doc: ScriptDocument) -> dict:
    """Per-scene word counts and runtime estimate: {scene_number: {words,
    minutes, dialogue_lines}}. Runtime assumes ~1 page per minute (160
    words/page), counting dialogue, parentheticals, and action — the parts
    of a scene that actually play. Output is keyed by scene_number for
    direct lookup."""
    out = {}
    for s in doc.scenes:
        words = 0
        dialogue_lines = 0
        for el in s.elements:
            if el.type in (ElementType.DIALOGUE, ElementType.PARENTHETICAL, ElementType.ACTION):
                words += len(el.text.split())
                if el.type is ElementType.DIALOGUE:
                    dialogue_lines += 1
        out[s.scene_number] = {
            "words": words,
            "dialogue_lines": dialogue_lines,
            "minutes": round(max(words / WORDS_PER_SCREEN_MINUTE, 0.1), 1),
        }
    return out


def character_stats(doc: ScriptDocument) -> dict:
    """Line count, word count, and scene-presence count per character."""
    line_counts = Counter()
    word_counts = Counter()
    scene_presence = Counter()

    for scene in doc.scenes:
        seen_this_scene = set()
        for el in scene.elements:
            if el.type == ElementType.DIALOGUE and el.character:
                line_counts[el.character] += 1
                word_counts[el.character] += len(el.text.split())
                seen_this_scene.add(el.character)
        for name in seen_this_scene:
            scene_presence[name] += 1

    all_chars = set(line_counts) | set(scene_presence)
    total_lines = sum(line_counts.values()) or 1

    result = []
    for name in sorted(all_chars, key=lambda n: -line_counts[n]):
        result.append({
            "character": name,
            "dialogue_lines": line_counts[name],
            "dialogue_words": word_counts[name],
            "scenes_present": scene_presence[name],
            "dialogue_share_pct": round(100 * line_counts[name] / total_lines, 1),
        })
    return {"characters": result, "total_dialogue_lines": sum(line_counts.values())}


def dialogue_action_ratio(doc: ScriptDocument) -> dict:
    dialogue_words = 0
    action_words = 0
    for scene in doc.scenes:
        for el in scene.elements:
            if el.type == ElementType.DIALOGUE:
                dialogue_words += len(el.text.split())
            elif el.type == ElementType.ACTION:
                action_words += len(el.text.split())
    total = dialogue_words + action_words
    return {
        "dialogue_words": dialogue_words,
        "action_words": action_words,
        "dialogue_pct": round(100 * dialogue_words / total, 1) if total else None,
        "action_pct": round(100 * action_words / total, 1) if total else None,
    }


def location_usage(doc: ScriptDocument) -> dict:
    counts = Counter()
    for scene in doc.scenes:
        if scene.location:
            counts[scene.location] += 1
    return {
        "unique_locations": len(counts),
        "usage": [{"location": loc, "scene_count": n} for loc, n in counts.most_common()],
    }


def scene_length_stats(doc: ScriptDocument) -> dict:
    """Approximate scene length in elements (proxy for page length without exact pagination)."""
    lengths = [len(s.elements) for s in doc.scenes]
    if not lengths:
        return {"scene_count": 0}
    lengths_sorted = sorted(lengths)
    n = len(lengths_sorted)
    median = lengths_sorted[n // 2] if n % 2 else (lengths_sorted[n // 2 - 1] + lengths_sorted[n // 2]) / 2
    return {
        "scene_count": n,
        "avg_elements_per_scene": round(sum(lengths) / n, 1),
        "median_elements_per_scene": median,
        "shortest_scene": {"scene_number": doc.scenes[lengths.index(min(lengths))].scene_number, "elements": min(lengths)},
        "longest_scene": {"scene_number": doc.scenes[lengths.index(max(lengths))].scene_number, "elements": max(lengths)},
    }


def int_ext_and_time_breakdown(doc: ScriptDocument) -> dict:
    int_ext_counts = Counter(s.int_ext or "UNKNOWN" for s in doc.scenes)
    time_counts = Counter((s.time_of_day or "UNSPECIFIED").upper() for s in doc.scenes)
    night_scenes = sum(1 for s in doc.scenes if s.time_of_day and "NIGHT" in s.time_of_day.upper())
    return {
        "int_ext_breakdown": dict(int_ext_counts),
        "time_of_day_breakdown": dict(time_counts),
        "night_scene_count": night_scenes,
        "night_scene_pct": round(100 * night_scenes / len(doc.scenes), 1) if doc.scenes else None,
    }


def full_stats_report(doc: ScriptDocument) -> dict:
    """Everything above, bundled — this is what Piece 2 pulls in wholesale."""
    return {
        "title": doc.title,
        "author": doc.author,
        "scene_count": doc.scene_count,
        "estimated_page_count": doc.estimated_page_count,
        "character_count": len(doc.all_characters),
        "parse_confidence": doc.parse_confidence,
        "character_stats": character_stats(doc),
        "dialogue_action_ratio": dialogue_action_ratio(doc),
        "location_usage": location_usage(doc),
        "scene_length_stats": scene_length_stats(doc),
        "int_ext_and_time_breakdown": int_ext_and_time_breakdown(doc),
        "acts": assign_acts(doc),
        "pacing": pacing_curve(doc),
        "character_arc": character_arc(doc),
        "scene_estimates": scene_estimates(doc),
        "runtime_minutes": round(sum(e["minutes"] for e in scene_estimates(doc).values()), 1),
    }
