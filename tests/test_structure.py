"""Tests for screenplay_parser.structure — deterministic act mapping, pacing
curve, and character-arc analytics (no model involved)."""

from screenplay_parser import parse_fountain
from screenplay_parser.structure import (
    assign_acts, act_for_scene, estimate_scene_pages, pacing_curve, character_arc,
)


def _doc(sample_fountain):
    return parse_fountain(sample_fountain)


class TestActs:
    def test_three_acts_in_order(self, sample_fountain):
        doc = _doc(sample_fountain)
        acts = assign_acts(doc)
        assert [a["act"] for a in acts] == [1, 2, 3]
        # every scene belongs to exactly one act, in ascending order
        nums = [n for a in acts for n in a["scene_numbers"]]
        assert nums == sorted(nums) == [s.scene_number for s in doc.scenes]

    def test_short_script_all_in_act_one(self, sample_fountain):
        doc = _doc(sample_fountain)
        acts = assign_acts(doc)
        # 3-scene sample is short; the first act boundary (25% of ~1 page)
        # means everything lands in Act 1 — but all acts must still exist
        assert len(acts) == 3
        assert sum(a["scene_count"] for a in acts) == doc.scene_count

    def test_act_for_scene(self, sample_fountain):
        doc = _doc(sample_fountain)
        acts = assign_acts(doc)
        assert act_for_scene(acts, 1) is not None
        assert act_for_scene(acts, 999) is None

    def test_pages_monotonic(self, sample_fountain):
        doc = _doc(sample_fountain)
        pages = estimate_scene_pages(doc)
        values = [pages[s.scene_number] for s in doc.scenes]
        assert values == sorted(values)
        assert values[-1] > 0


class TestPacing:
    def test_segments_cover_script(self, sample_fountain):
        doc = _doc(sample_fountain)
        curve = pacing_curve(doc, segment_pages=1)
        assert curve["total_pages"] > 0
        assert curve["segments"]
        total_scenes = sum(s["scene_count"] for s in curve["segments"])
        assert total_scenes == doc.scene_count

    def test_dialogue_words_detected(self, sample_fountain):
        doc = _doc(sample_fountain)
        curve = pacing_curve(doc, segment_pages=1)
        assert sum(s["dialogue_words"] for s in curve["segments"]) > 0


class TestCharacterArc:
    def test_presence_facts(self, sample_fountain):
        doc = _doc(sample_fountain)
        arcs = character_arc(doc)
        by_name = {c["character"]: c for c in arcs}
        assert "MARA" in by_name
        mara = by_name["MARA"]
        assert mara["first_scene"] == 1
        assert mara["last_scene"] == 3
        assert mara["scene_count"] == 3
        assert mara["dialogue_lines"] == 3  # one line per scene in the sample
        assert mara["appears_throughout"] is True

    def test_sorted_by_presence(self, sample_fountain):
        doc = _doc(sample_fountain)
        arcs = character_arc(doc)
        counts = [c["scene_count"] for c in arcs]
        assert counts == sorted(counts, reverse=True)
