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
    """Per page-segment dialogue/action word volume.

    Returns {segments: [{page_start, page_end, dialogue_words, action_words,
    scene_count, spans_boundary}], total_pages, segment_pages, weighted:
    bool}.

    Gap 27 — three things here used to be wrong, and all three were measured:

    1. **The boundary was off by one.** `idx = int(pos // segment_pages)` is
       right for pages 1..5 (0..4) but puts page 5 itself into segment 2, since
       5 // 5 == 1. A script whose only two scenes ended on pages 5 and 10
       reported **zero** scenes in 1-5 and both in 6-10. Segments are now
       1-based and inclusive: a position `p` belongs to `ceil(p / segment_pages)`.
    2. **`total_pages` was the last scene's END page, not the segment count**,
       and the last segment's `page_end` was clamped to it — so the number of
       segments depended on where the last scene happened to finish. It is now
       the segment count times the segment length, which is what the labels say.
    3. **A scene crossing a boundary was charged wholly to its end segment.**
       Measured: a scene spanning pages 10-12 put all of its words in the
       11-12 bucket and nothing in 6-10 — a 5-page bucket reading as empty while
       pages 10 of it were full. Words are now split by the fraction of the
       scene's page span that falls inside each segment, and `weighted` says so,
       because a split is an ESTIMATE and the report must be able to say that
       rather than print it as an observation.

    Scenes with no positional data keep the old behaviour (attributed to the
    first segment) — they are a parse gap, not a pacing fact.
    """
    pages = estimate_scene_pages(doc)
    if not pages:
        return {"segments": []}
    last_scene_page = max(pages.values()) or 1.0
    n_segments = max(1, math.ceil(last_scene_page / segment_pages))
    total = n_segments * segment_pages            # span the LABELS describe
    segments = [
        {"page_start": i * segment_pages + 1,
         "page_end": (i + 1) * segment_pages,
         "dialogue_words": 0, "action_words": 0, "scene_count": 0,
         "spans_boundary": False}
        for i in range(n_segments)
    ]

    weighted = False
    for scene in doc.scenes:
        end = pages.get(scene.scene_number)
        if end is None:
            # No positional data: keep it visible in the first segment rather
            # than dropping it, and leave the arithmetic alone.
            segments[0]["scene_count"] += 1
            for el in scene.elements:
                words = len(el.text.split())
                if el.type == ElementType.DIALOGUE:
                    segments[0]["dialogue_words"] += words
                elif el.type == ElementType.ACTION:
                    segments[0]["action_words"] += words
            continue

        if scene.page_start is None:
            # A text parse: `estimate_scene_pages` supplies a fractional END
            # position and nothing else, so there is no span to split — the
            # scene is attributed wholly to the segment it ends in. Applying
            # the page-span split here divided by a nonsense interval and
            # charged a 40-word scene 1 word (measured).
            buckets = {segment_of_page(end, segment_pages): 1.0}
        else:
            buckets = share_over_segments(
                scene.page_start, end, segment_pages, n_segments)
        seg_last = segment_of_page(end, segment_pages)
        segments[seg_last - 1]["scene_count"] += 1
        if len(buckets) > 1:
            # The words below are split, so the segment's total is an estimate.
            for seg_no in buckets:
                segments[seg_no - 1]["spans_boundary"] = True
            weighted = True
        for el in scene.elements:
            words = len(el.text.split())
            if not words:
                continue
            for seg_no, frac in buckets.items():
                if el.type == ElementType.DIALOGUE:
                    segments[seg_no - 1]["dialogue_words"] += words * frac
                elif el.type == ElementType.ACTION:
                    segments[seg_no - 1]["action_words"] += words * frac

    for seg in segments:
        seg["dialogue_words"] = int(round(seg["dialogue_words"]))
        seg["action_words"] = int(round(seg["action_words"]))
    return {"segments": segments, "total_pages": round(total, 1),
            "segment_pages": segment_pages, "weighted": weighted}


def segment_of_page(page: float, segment_pages: int) -> int:
    """Which 1-based segment a page position belongs to.

    Gap 27: the boundary that was wrong. Segments are inclusive ranges
    `[(k-1)*n + 1 .. k*n]`, so page 5 with n=5 is segment **1**, not 2.
    A page given as 0 (a parser that numbers from 0) is clamped into segment 1.
    """
    if segment_pages <= 0 or page is None:
        # `None` reaches here from a text parse, where the real pagination is
        # absent and `estimate_scene_pages` supplies the proxy — but a caller
        # can still hold the raw None. Treating it as page 1 keeps the scene
        # visible instead of raising in the middle of a report.
        return 1
    return max(1, int(math.ceil(float(page) / segment_pages)))


def share_over_segments(start: float, end: float, segment_pages: int,
                        n_segments: int) -> dict:
    """{segment_number: fraction_of_the_scene_that_falls_inside_it}.

    A scene "from page 10 to page 12" OCCUPIES pages 10, 11 and 12 — a writer
    counting pages counts three, not the distance between two numbers. So the
    occupied span is `(start - 1, end]` and segments are `((k-1)*n, k*n]`:

        scene 1 -> 5   gives {1: 1.0}          (exactly segment 1)
        scene 5 -> 6   gives {1: 0.5, 2: 0.5}  (straddles the boundary)
        scene 10 -> 12 gives {2: 1/3, 3: 2/3}  (one page in 6-10, two in 11-15)

    My first version used `[start, end]` as the span, which is the same thing
    for a one-page scene and wrong for every other: it scored 10->12 as
    {3: 1.0} — a scene whose `spans_boundary` flag said it crossed, charged
    entirely to one side. Fractions of PAGE SPAN, not of words: words per page
    is exactly what this module estimates rather than observes.
    """
    if end is None:
        return {1: 1.0}
    s0 = float(start) if start is not None else float(end) - 1.0
    end = float(end)
    # `(s0 - 1, end]` -- see the docstring. Guard a zero/negative span so a
    # malformed parse page_start=page_end still yields exactly one bucket.
    lo_span = min(s0 - 1.0, end - 1e-9)
    span = max(end - lo_span, 1e-9)
    shares: dict = {}
    for seg_no in range(segment_of_page(lo_span + 1e-9, segment_pages),
                        segment_of_page(end, segment_pages) + 1):
        lo = (seg_no - 1) * segment_pages
        hi = min(seg_no * segment_pages, n_segments * segment_pages)
        overlap = max(0.0, min(end, hi) - max(lo_span, lo))
        if overlap > 0:
            shares[seg_no] = overlap / span
    if not shares:                     # degenerate; keep the scene visible
        shares[segment_of_page(end, segment_pages)] = 1.0
    return shares


def character_arc(doc: ScriptDocument, kg_characters: dict | None = None) -> list[dict]:
    """Factual per-character trajectory. kg_characters is the Piece 1
    knowledge-graph character index (optional; enriches with trait mentions
    and per-scene dialogue counts when provided)."""
    from collections import Counter, defaultdict

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
