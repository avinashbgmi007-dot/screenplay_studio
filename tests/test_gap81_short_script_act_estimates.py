"""Gap 81: short scripts get proportional act estimates, not empty-act claims."""

from screenplay_analyzer.pipeline import AnalysisResult
from screenplay_analyzer.report import render_markdown
from screenplay_parser import parse_fountain
from screenplay_parser.structure import assign_acts, estimate_scene_pages


THREE_SCENE_EXCERPT = """Title: Short test
Author: Test

INT. ROOM - DAY

ALICE
A short line.

CUT TO:

EXT. STREET - NIGHT

BOB
Another short line.

CUT TO:

INT. CAR - NIGHT

ALICE
One more line.
"""


def _parse(tmp_path, script=THREE_SCENE_EXCERPT):
    path = tmp_path / "short.fountain"
    path.write_text(script, encoding="utf-8")
    return parse_fountain(str(path))


def test_short_proxy_positions_are_normalized_across_the_observed_span(tmp_path):
    doc = _parse(tmp_path)
    positions = estimate_scene_pages(doc)

    assert max(positions.values()) < 1.0  # the parser's content-based page proxy
    acts = assign_acts(doc)

    assert [act["act"] for act in acts] == [1, 2, 3]
    assert [act["scene_numbers"] for act in acts] == [[1], [2], [3]]
    assert all(act["estimated"] for act in acts)
    assert all(act["position_basis"] == "content_estimate" for act in acts)
    assert acts[0]["page_start"] == round(positions[1], 2)
    assert acts[0]["page_end"] == round(positions[1], 2)


def test_absolute_page_bounds_start_at_the_first_scene_not_a_magic_one(tmp_path):
    doc = _parse(tmp_path)
    acts = assign_acts(doc, {1: 1.2, 2: 4.0, 3: 8.0})

    assert [act["act"] for act in acts] == [1, 2, 3]
    assert acts[0]["page_start"] == 1.2
    assert acts[0]["page_end"] == 1.2
    assert all(act["position_basis"] == "source_page_positions" for act in acts)


def test_incomplete_page_map_falls_back_as_a_whole_instead_of_mixing_units(tmp_path):
    doc = _parse(tmp_path)
    acts = assign_acts(doc, {1: 1.2, 3: 8.0})

    assert all(act["position_basis"] == "content_estimate" for act in acts)
    assert all(act["page_end"] < 1.0 for act in acts)


def test_empty_document_has_no_act_estimates():
    from screenplay_parser.models import ScriptDocument

    doc = ScriptDocument(title=None, author=None, source_format="fountain",
                         source_filename="")
    assert assign_acts(doc) == []


def test_equal_positions_collapse_to_one_populated_estimate():
    from screenplay_parser.models import ScriptDocument, Scene

    doc = ScriptDocument(
        title=None, author=None, source_format="fountain", source_filename="",
        scenes=[
            Scene(scene_number=1, heading_raw="INT. ROOM - DAY"),
            Scene(scene_number=2, heading_raw="EXT. STREET - DAY"),
            Scene(scene_number=3, heading_raw="INT. CAR - NIGHT"),
        ],
    )
    acts = assign_acts(doc, {1: 3.0, 2: 3.0, 3: 3.0})

    assert len(acts) == 1
    assert acts[0]["act"] == 1
    assert acts[0]["scene_numbers"] == [1, 2, 3]
    assert acts[0]["page_start"] == acts[0]["page_end"] == 3.0


def test_report_discloses_estimates_and_never_lists_empty_acts(tmp_path):
    doc = _parse(tmp_path)
    result = AnalysisResult(doc=doc, stats={"acts": assign_acts(doc)})

    report = render_markdown(result)

    assert "### Estimated act ranges" in report
    assert "act breaks are not marked in this parse" in report
    assert "Estimated Act 1" in report
    assert "no scenes in this range" not in report
    assert "estimated positions" in report
