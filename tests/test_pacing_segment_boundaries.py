"""Gap 27 — pacing segment boundaries misplace scenes.

Two scenes ending on pages 5 and 10 produced **zero** scenes in 1-5 and both in
6-10. Three defects, measured against the real `pacing_curve`:

1. `idx = int(pos // segment_pages)` puts page 5 in segment 2 (`5 // 5 == 1`)
   while the label says 1-5. Segments are now 1-based inclusive:
   page 5 with n=5 is segment 1.
2. `total_pages` was the last scene's END page and every segment's `page_end`
   was clamped to it, so the segment COUNT depended on where the last scene
   stopped finishing — a 10-page script whose last scene ended on 5 reported
   one segment.
3. A scene crossing a boundary was charged wholly to one side. A scene spanning
   pages 10-12 put all its words in 11-15 and none in 6-10, while the bucket it
   was dropped from still contained page 10 of it.

The tests are arithmetic: no model, no parser, no fixtures beyond the dataclasses.
"""
import math

import pytest

from screenplay_parser.models import Element, ElementType, Scene, ScriptDocument
from screenplay_parser.structure import (
    pacing_curve,
    segment_of_page,
    share_over_segments,
)


def _scene(num, page_start, page_end, words=100, kind=ElementType.ACTION):
    sc = Scene(scene_number=num, heading_raw=f"INT. R{num} - DAY", int_ext="INT",
               location=f"R{num}", time_of_day="DAY",
               page_start=page_start, page_end=page_end)
    sc.elements.append(Element(type=ElementType.SCENE_HEADING, text=f"INT. R{num} - DAY"))
    sc.elements.append(Element(type=kind, text=" ".join(["word"] * words)))
    return sc


def _doc(*scenes):
    d = ScriptDocument(title="t", author=None, source_format="fountain",
                       source_filename="t.fountain")
    d.scenes = list(scenes)
    return d


def _by_span(curve):
    return {(s["page_start"], s["page_end"]): s for s in curve["segments"]}


# ---------------------------------------------------------------------------
# 1. The filed case
# ---------------------------------------------------------------------------

def test_scenes_ending_on_pages_5_and_10_land_in_their_own_segments():
    """The reproduction in the register, asserted directly."""
    doc = _doc(_scene(1, 1, 5, words=10), _scene(2, 6, 10, words=20))
    segs = _by_span(pacing_curve(doc, segment_pages=5))

    assert segs[(1, 5)]["scene_count"] == 1, "the page-5 scene belongs in 1-5"
    assert segs[(6, 10)]["scene_count"] == 1
    # Only ACTION and DIALOGUE elements are counted — a scene heading is not
    # pacing words. (My first version of these assertions added the heading.)
    assert segs[(1, 5)]["action_words"] == 10
    assert segs[(6, 10)]["action_words"] == 20


def test_a_scene_ending_exactly_on_a_boundary_page_is_in_the_earlier_segment():
    """The off-by-one, isolated: page 5 is the LAST page of 1-5, not the first
    page of 6-10."""
    assert segment_of_page(5, 5) == 1
    assert segment_of_page(5.0, 5) == 1
    assert segment_of_page(5.1, 5) == 2
    assert segment_of_page(6, 5) == 2
    assert segment_of_page(10, 5) == 2
    assert segment_of_page(10.5, 5) == 3


@pytest.mark.parametrize("page,expected", [
    (0, 1), (0.5, 1), (1, 1), (4.999, 1), (5, 1),
    (5.0001, 2), (6, 2), (10, 2), (11, 3), (15, 3), (16, 4),
])
def test_segment_of_page_table(page, expected):
    """Page 0 is clamped rather than raising: a parser that numbers from zero
    must not send a scene to segment 0 (a negative index into the list)."""
    assert segment_of_page(page, 5) == expected


def test_the_boundary_holds_for_other_segment_lengths():
    for n in (1, 3, 4, 10):
        assert segment_of_page(n, n) == 1, f"page {n} with n={n} is the end of segment 1"
        assert segment_of_page(n + 0.5, n) == 2


# ---------------------------------------------------------------------------
# 2. The segment count comes from the script's length, not the last page_end
# ---------------------------------------------------------------------------

def test_a_short_last_scene_does_not_collapse_the_segment_count():
    """A 10-page script whose last scene ends on 5 still has two segments — the
    old code clamped every `page_end` to `total = 5` and reported one, then
    filed both scenes into it."""
    doc = _doc(_scene(1, 1, 2), _scene(2, 3, 5))
    curve = pacing_curve(doc, segment_pages=5)
    assert len(curve["segments"]) == 1, "one segment covers pages 1-5"

    # ...but a script reaching page 10 has two, even if its last scene is small.
    doc2 = _doc(_scene(1, 1, 2), _scene(2, 9, 10, words=5))
    curve2 = pacing_curve(doc2, segment_pages=5)
    assert len(curve2["segments"]) == 2
    assert [s["page_end"] for s in curve2["segments"]] == [5, 10]


def test_total_pages_is_the_span_the_labels_describe():
    """It used to be the last scene's end page (10.0 for the filed case) while
    the labels ran 1-5 and 6-10 — a number the table contradicted."""
    doc = _doc(_scene(1, 1, 5), _scene(2, 6, 10))
    curve = pacing_curve(doc, segment_pages=5)
    assert curve["total_pages"] == 10
    assert curve["segments"][-1]["page_end"] == curve["total_pages"]


def test_segment_labels_are_contiguous_and_inclusive():
    doc = _doc(_scene(1, 1, 12), _scene(2, 12, 12))
    segs = pacing_curve(doc, segment_pages=5)["segments"]
    assert [(s["page_start"], s["page_end"]) for s in segs] == [(1, 5), (6, 10), (11, 15)]
    for a, b in zip(segs, segs[1:]):
        assert b["page_start"] == a["page_end"] + 1, "a gap between segments"


# ---------------------------------------------------------------------------
# 3. A scene crossing a boundary is split, and labelled as an estimate
# ---------------------------------------------------------------------------

def test_a_scene_spanning_two_segments_is_split_by_page_span():
    """Measured before: all of a 10-12 scene's words in 11-15, none in 6-10."""
    doc = _doc(_scene(1, 1, 5, words=100), _scene(2, 10, 12, words=90))
    curve = pacing_curve(doc, segment_pages=5)
    segs = _by_span(curve)

    # Pages 10, 11, 12: one of the three is in 6-10, two in 11-15.
    assert segs[(6, 10)]["spans_boundary"] is True
    assert segs[(11, 15)]["spans_boundary"] is True
    # 90 words over three pages => 30 in the first bucket, 60 in the second.
    assert segs[(6, 10)]["action_words"] == 30, segs[(6, 10)]
    assert segs[(11, 15)]["action_words"] == 60, segs[(11, 15)]
    assert curve["weighted"] is True, "the curve must admit that it split something"


def test_shares_are_fractions_of_page_span_that_sum_to_one():
    for start, end in ((1, 5), (5, 6), (10, 12), (1, 12), (4, 4)):
        shares = share_over_segments(start, end, 5, 3)
        assert math.isclose(sum(shares.values()), 1.0, rel_tol=1e-9), (
            f"{start}->{end}: {shares} does not sum to 1")
        for seg_no in shares:
            assert 1 <= seg_no <= 3


def test_a_one_page_scene_is_not_split():
    """The common case must stay exactly what it was: one bucket, no estimate."""
    curve = pacing_curve(_doc(_scene(1, 1, 5, words=50)), segment_pages=5)
    seg = curve["segments"][0]
    assert seg["action_words"] == 50
    assert seg["spans_boundary"] is False
    assert curve["weighted"] is False


def test_a_wholly_contained_multi_page_scene_is_not_split():
    doc = _doc(_scene(1, 2, 4, words=30))
    curve = pacing_curve(doc, segment_pages=5)
    assert curve["segments"][0]["action_words"] == 30
    assert curve["segments"][0]["spans_boundary"] is False
    assert curve["weighted"] is False


def test_words_are_conserved_across_the_split():
    """A split may distribute words, but it must not create or lose them —
    that is what makes the number an estimate rather than a fiction."""
    words = 137
    curve = pacing_curve(_doc(_scene(1, 4, 11, words=words)), segment_pages=5)
    total = sum(s["action_words"] for s in curve["segments"])
    assert total == words, f"{total} != {words}"


# ---------------------------------------------------------------------------
# 4. Edges: no pagination at all, and dialogue is split the same way
# ---------------------------------------------------------------------------

def test_a_scene_with_no_page_data_is_still_reported():
    """A text parse has no real pagination; `estimate_scene_pages` supplies a
    proxy. Whatever it supplies, the loop must not divide by zero or drop the
    scene."""
    sc = _scene(1, None, None, words=40)
    curve = pacing_curve(_doc(sc), segment_pages=5)
    # No real pagination on a text parse, so estimate_scene_pages supplies a
    # proxy and the scene is still counted exactly once, in full.
    assert sum(s["scene_count"] for s in curve["segments"]) == 1
    # A text parse has no real pagination; `estimate_scene_pages` supplies a
    # proxy position, so the scene is counted once at its proxy, not dropped.
    # (What this test actually guards is that a None page_start cannot crash
    # `segment_of_page` — which my first version of the fix did.)
    assert sum(s["action_words"] for s in curve["segments"]) == 40, (
        "an estimated position must charge the whole scene to its segment")


def test_dialogue_is_split_the_same_way_as_action():
    doc = _doc(_scene(1, 10, 12, words=90, kind=ElementType.DIALOGUE))
    segs = _by_span(pacing_curve(doc, segment_pages=5))
    assert segs[(6, 10)]["dialogue_words"] == 30
    assert segs[(11, 15)]["dialogue_words"] == 60
    assert segs[(6, 10)]["action_words"] == 0, "a heading is not pacing words"


def test_an_empty_document_returns_no_segments():
    assert pacing_curve(_doc(), segment_pages=5)["segments"] == []


# ---------------------------------------------------------------------------
# 5. The report says when a row is an estimate
# ---------------------------------------------------------------------------

def test_the_markdown_marks_split_segments_and_explains_the_mark():
    """The register asked to "label approximation explicitly rather than
    presenting it as precise timing". Rendered through the real report writer."""
    from screenplay_analyzer.pipeline import AnalysisResult
    from screenplay_analyzer.report import render_markdown

    result = AnalysisResult(doc=_doc(_scene(1, 1, 5)))
    # The acts lookup indexes `st`, so stats must be a dict for the pacer block
    # to be reached at all; an empty acts list keeps the section out of the way.
    result.stats = {
        "pacing": {
            "segments": [
                {"page_start": 1, "page_end": 5, "dialogue_words": 10,
                 "action_words": 20, "scene_count": 1, "spans_boundary": False},
                {"page_start": 6, "page_end": 10, "dialogue_words": 30,
                 "action_words": 40, "scene_count": 2, "spans_boundary": True},
            ],
            "weighted": True, "total_pages": 10, "segment_pages": 5,
        },
        # render_markdown nests the pacing block under `if acts:` — a real
        # ordering quirk of the report, not something this gap changes. One act
        # is enough to reach the table.
        "acts": [{"act": 1, "name": "Act 1", "scene_numbers": [1],
                  "page_start": 1.0, "page_end": 5.0, "scene_count": 1}],
    }
    md = render_markdown(result)

    assert "| 1–5 | 10 | 20 | 1 |" in md, md
    assert "| 6–10 | 30 ~ | 40 ~ | 2 |" in md, "a split row must be marked"
    assert "estimate, not a count" in md, "the mark must be explained"


def test_a_curve_with_no_split_carries_no_mark_and_no_legend():
    """The legend must not appear on a script that never crossed a boundary —
    a caveat attached to nothing trains the writer to ignore it."""
    from screenplay_analyzer.pipeline import AnalysisResult
    from screenplay_analyzer.report import render_markdown

    result = AnalysisResult(doc=_doc(_scene(1, 1, 5)))
    # The acts lookup indexes `st`, so stats must be a dict for the pacer block
    # to be reached at all; an empty acts list keeps the section out of the way.
    result.stats = {
        "pacing": {
            "segments": [
                {"page_start": 1, "page_end": 5, "dialogue_words": 10,
                 "action_words": 20, "scene_count": 1, "spans_boundary": False},
            ],
            "weighted": False, "total_pages": 5, "segment_pages": 5,
        },
        "acts": [{"act": 1, "name": "Act 1", "scene_numbers": [1],
                  "page_start": 1.0, "page_end": 5.0, "scene_count": 1}],
    }
    md = render_markdown(result)
    assert "| 1–5 | 10 | 20 | 1 |" in md
    assert "~" not in md.split("### Pacing")[1].split("###")[0], "no mark without a split"
    assert "estimate, not a count" not in md
