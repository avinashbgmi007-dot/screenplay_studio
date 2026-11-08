"""
Beat board — the writer's corkboard. A proposed scene order, saved per
project, independent of the working copy (so reordering never touches the
actual draft). When the writer likes the new arrangement, it can be exported
as a reordered draft (.fountain/.fdx/.txt) with scenes renumbered 1..N.

The stored form is just a permutation of the script's scene numbers. If no
board has been saved, the natural order (1..N) is the board.
"""

from __future__ import annotations

import os
import time

BOARD_FILE = "beatboard.json"


def _path(m) -> str:
    return os.path.join(m.project_dir, BOARD_FILE)


def _load(m) -> dict:
    # A damaged beatboard.json used to read as "no saved order" (i.e. the board
    # silently reverted to natural order) and the next set_order then overwrote
    # the writer's arrangement. Missing -> {} ; damaged -> StoreUnreadable.
    from .jsonio import StoreUnreadable, load_json_store
    data = load_json_store(_path(m), default={})
    if not isinstance(data, dict):
        raise StoreUnreadable(_path(m), f"expected an object, found {type(data).__name__}")
    return data


def _save(m, data: dict) -> None:
    from .jsonio import atomic_write_json
    atomic_write_json(_path(m), data)


def scene_numbers(m) -> list[int]:
    """The script's scene numbers in natural order (from the working copy,
    which equals the parsed order unless edits exist — edits never add or
    remove scenes)."""
    from .revision import load_working
    doc = load_working(m)
    return [s.scene_number for s in doc.scenes]


def _scene_map(m) -> dict:
    """{scene_number: heading} for the working copy — the IDENTITY of a card.

    Gap 20: the board used to store a bare permutation of scene NUMBERS, so it
    could only ask "is this still a valid permutation?" — never "are these still
    the same scenes?". A re-parse that keeps the count but changes what scene 3
    IS made a saved order silently apply to different scenes, and the board still
    reported itself as current.
    """
    from .revision import load_working
    doc = load_working(m)
    return {s.scene_number: (s.heading_raw or "") for s in doc.scenes}


def _stored_headings(data: dict) -> dict:
    """The heading map the board was saved with, keys as ints.

    JSON object keys are strings, so a board written by `set_order` stores
    "3": "INT. KITCHEN - DAY". A board saved before gap 20 has no map at all.
    """
    raw = data.get("headings") or {}
    out = {}
    for k, v in raw.items():
        try:
            out[int(k)] = v
        except (TypeError, ValueError):
            continue
    return out


def board_state(m) -> dict:
    """The board, and the truth about how well it still fits the script.

    Returns {order, saved, stale, saved_order, changed, reason, verified_by}.

    - `order` is what the corkboard should render. When the board is stale it is
      the NATURAL order, because drawing a saved arrangement over scenes that
      no longer exist would be showing the writer something untrue.
    - `saved` is only "a board exists" — the fact `has_board` reports, kept so
      the two can never contradict each other silently.
    - `stale` is the disclosure this entry is about. `has_board` returning True
      used to be the ONLY thing the desk was told, so a stale board looked
      exactly like a current one.
    - `saved_order` and `changed` are preserved so the writer can RECONCILE
      against their real arrangement instead of being handed the natural order
      with no explanation. Nothing on disk is rewritten here: a failed match is a
      question for the writer, never a reason to overwrite their work.
    - `verified_by` says what the match could be checked against:
      "scenes" (headings, gap 20) or "numbers_only" (a board saved before
      headings were recorded — the permutation check is all that can be done,
      and pretending otherwise would either invent staleness or hide it).
    """
    data = _load(m)
    saved = data.get("order")
    current = _scene_map(m)
    natural = list(current)
    if not saved:
        return {"order": natural, "saved": False, "stale": False,
                "saved_order": None, "changed": [], "reason": "",
                "verified_by": None}
    base = {"saved": True, "saved_order": list(saved)}
    if sorted(saved) != sorted(natural):
        missing = [n for n in saved if n not in current]
        added = [n for n in natural if n not in saved]
        reason = ("the script's scenes changed since this board was saved"
                  + (f" (scene {missing[0]} is gone)" if missing else "")
                  + (f" ({len(added)} new scene(s) appeared)" if added else ""))
        return {**base, "order": natural, "stale": True,
                "changed": sorted(set(missing) | set(added)),
                "reason": reason, "verified_by": "numbers_only"}
    headings = _stored_headings(data)
    if not headings:
        # Legacy board: the permutation holds, and that is genuinely all that can
        # be verified. Reported as numbers_only rather than as a pass.
        return {**base, "order": list(saved), "stale": False,
                "changed": [], "reason": "", "verified_by": "numbers_only"}
    changed = [n for n in saved
               if n in current and headings.get(n) not in (None, current[n])]
    if changed:
        return {**base, "order": natural, "stale": True, "changed": sorted(changed),
                "reason": (f"scene {changed[0]} is a different scene now than when "
                           "this board was saved (the numbering survived the "
                           "re-parse, the scenes did not)"),
                "verified_by": "scenes"}
    return {**base, "order": list(saved), "stale": False, "changed": [],
            "reason": "", "verified_by": "scenes"}


def get_order(m) -> list[int]:
    """The order to DRAW. Delegates to `board_state`, so a stale board yields the
    natural order — and the caller that needs to know that is `board_view`, which
    reports `stale` instead of leaving the fallback unobservable."""
    return board_state(m)["order"]


def set_order(m, order) -> dict:
    natural = scene_numbers(m)
    # L6 (re-audit 2026-09-24): the list comprehension iterated any iterable, so
    # {"order": "312"} became [3, 1, 2] and was SAVED (a valid permutation of a
    # 3-scene script), and int() coerced bools (True -> 1) and numeric strings
    # the same way — schema drift that silently rearranged the corkboard instead
    # of failing. The board stores scene numbers: a list of ints, nothing else.
    if not isinstance(order, list) or any(isinstance(n, bool) or not isinstance(n, int) for n in order):
        raise ValueError("order must be a list of scene numbers (integers).")
    if len(order) != len(natural) or sorted(order) != sorted(natural):
        raise ValueError(
            f"order must be a permutation of the script's scene numbers "
            f"({len(natural)} scenes: {natural[:12]}{'…' if len(natural) > 12 else ''})."
        )
    # Gap 20: store what each card WAS, not just where it sat. Without this the
    # next read can only re-check the permutation, which is how a same-number /
    # different-scene change slipped through looking current.
    board = {"order": order, "saved_at": time.time(),
             "headings": {str(n): _scene_map(m).get(n, "") for n in order}}
    _save(m, board)
    return board


def reset_order(m) -> dict:
    try:
        os.remove(_path(m))
    except FileNotFoundError:
        # R6-BE-9: `if os.path.exists(...)` then remove is a two-step check on a
        # file a second window (or the CLI) may delete between them, and the
        # losing caller got a 500 for a reset that had already succeeded. The
        # desired end state is "no board", which both branches now reach.
        pass
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
    state = board_state(m)
    order = state["order"]
    by_num = {s.scene_number: s for s in doc.scenes}
    if state["stale"]:
        # Refusing is the point: exporting the natural order under the label
        # "your board" would hand the writer a script they did not arrange.
        raise ValueError(
            f"Beat-board order no longer matches the script — {state['reason']}. "
            "Re-save the board to export it.")
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
    state = board_state(m)
    return {
        "order": order,
        "cards": cards,
        "saved": state["saved"],
        # Gap 20: `saved: true` used to be the entire story, so a board that no
        # longer fitted the script rendered identically to one that did. These
        # four fields are the difference between "your board is showing" and
        # "your board is still on disk, and here is why it is not showing".
        "stale": state["stale"],
        "saved_order": state["saved_order"],
        "changed_scenes": state["changed"],
        "stale_reason": state["reason"],
        "verified_by": state["verified_by"],
        "natural_order": [s.scene_number for s in doc.scenes],
    }
