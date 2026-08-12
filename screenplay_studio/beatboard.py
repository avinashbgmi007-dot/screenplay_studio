"""
Beat board — the writer's corkboard. A proposed scene order, saved per
project, independent of the working copy (so reordering never touches the
actual draft). When the writer likes the new arrangement, it can be exported
as a reordered draft (.fountain/.fdx/.txt) with scenes renumbered 1..N.

The stored form is just a permutation of the script's scene numbers. If no
board has been saved, the natural order (1..N) is the board.
"""

from __future__ import annotations

import json
import os
import time

BOARD_FILE = "beatboard.json"


def _path(m) -> str:
    return os.path.join(m.project_dir, BOARD_FILE)


def _load(m) -> dict:
    if not os.path.exists(_path(m)):
        return {}
    try:
        with open(_path(m), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save(m, data: dict) -> None:
    with open(_path(m), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def scene_numbers(m) -> list[int]:
    """The script's scene numbers in natural order (from the working copy,
    which equals the parsed order unless edits exist — edits never add or
    remove scenes)."""
    from .revision import load_working
    doc = load_working(m)
    return [s.scene_number for s in doc.scenes]


def get_order(m) -> list[int]:
    saved = _load(m).get("order")
    natural = scene_numbers(m)
    if not saved:
        return natural
    # guard against a stale board (e.g. a re-parse changed scene numbers)
    if sorted(saved) != sorted(natural):
        return natural
    return saved


def set_order(m, order) -> dict:
    natural = scene_numbers(m)
    try:
        order = [int(n) for n in order]
    except (TypeError, ValueError):
        raise ValueError("order must be a list of scene numbers.")
    if len(order) != len(natural) or sorted(order) != sorted(natural):
        raise ValueError(
            f"order must be a permutation of the script's scene numbers "
            f"({len(natural)} scenes: {natural[:12]}{'…' if len(natural) > 12 else ''})."
        )
    board = {"order": order, "saved_at": time.time()}
    _save(m, board)
    return board


def reset_order(m) -> dict:
    if os.path.exists(_path(m)):
        os.remove(_path(m))
    return {"order": scene_numbers(m)}


def has_board(m) -> bool:
    return os.path.exists(_path(m))


def export_reordered(m, fmt: str = "fountain") -> str:
    """Export the working copy with scenes in the beat-board order, renumbered
    1..N. Returns the exported text. fmt: fountain | fdx | txt."""
    from .revision import load_working
    from screenplay_parser.models import ScriptDocument, Scene
    from screenplay_parser.export import export

    doc = load_working(m)
    order = get_order(m)
    by_num = {s.scene_number: s for s in doc.scenes}
    if len(order) != len(doc.scenes) or any(n not in by_num for n in order):
        raise ValueError("Beat-board order no longer matches the script — re-save the board.")

    scenes_by_new = []
    for new_num, old_num in enumerate(order, start=1):
        old = by_num[old_num]
        scene = Scene(
            scene_number=new_num,
            heading_raw=old.heading_raw,
            int_ext=old.int_ext,
            location=old.location,
            time_of_day=old.time_of_day,
            page_start=old.page_start,
            page_end=old.page_end,
        )
        scene.elements = old.elements
        scenes_by_new.append(scene)

    reordered = ScriptDocument(
        title=doc.title,
        author=doc.author,
        source_format=doc.source_format,
        source_filename=doc.source_filename,
        scenes=scenes_by_new,
        front_matter=doc.front_matter,
    )
    reordered.parse_confidence = doc.parse_confidence
    return export(reordered, fmt)


def board_view(m) -> dict:
    """Everything the frontend needs to draw the corkboard: the saved order
    plus per-scene card data (heading, runtime, notes/findings counts)."""
    from .revision import load_working
    from screenplay_parser.stats import scene_estimates
    from .notes import notes_for_scene

    doc = load_working(m)
    order = get_order(m)
    by_num = {s.scene_number: s for s in doc.scenes}
    estimates = scene_estimates(doc)
    cards = []
    for position, num in enumerate(order, start=1):
        s = by_num.get(num)
        if not s:
            continue
        est = estimates.get(num, {})
        cards.append({
            "position": position,
            "scene_number": num,
            "heading_raw": s.heading_raw,
            "int_ext": s.int_ext,
            "page_estimate": est.get("minutes", 0),
            "word_count": est.get("words", 0),
            "your_notes": len(notes_for_scene(m, num)),
        })
    return {
        "order": order,
        "cards": cards,
        "saved": has_board(m),
        "natural_order": [s.scene_number for s in doc.scenes],
    }
