"""Final Draft emphasis must survive parse -> model -> export.

Gap 22 was filed as "FDX export loses original formatting" and then archived as
"the format's limit, and the exporter documents it". Measured against the code,
that is wrong: FDX carries emphasis natively — a `<Paragraph>` holds `<Text>`
runs and each run accepts `Style="Bold"`, `Style="Italic"`,
`Style="Bold+Italic"`. Nothing in the format had to give.

The loss was ours at every stage. `parse_fdx` concatenated the runs and threw
the `Style` attributes away — its own helper says "FDX splits styled text into
runs" and then joins them. `Element` had no field to hold a style. `to_fdx`
wrote one plain `<Text>` per paragraph. Feeding a real FDX with bold on two
paragraphs and an italic run inside dialogue through the real parser and
exporter returned `styles=[None]` for every paragraph and flattened the
three-run dialogue to one.

What this file pins:

  * a whole-paragraph style survives, and a PARTIAL one keeps its boundaries;
  * combined `Bold+Italic` is not silently collapsed;
  * the spans stay correct when the paragraph's text is stripped, because
    offsets computed before the strip point at the wrong characters after it;
  * a document with no emphasis exports exactly as it did before this change;
  * spans survive `working.json` (to_dict/from_dict) — without that the fix
    would work until the next save and then evaporate;
  * older saved documents with no `spans` key still load.

Not claimed here: `.txt` cannot carry emphasis (plain text genuinely has no
mechanism, so that half of the old filing was right), and the PDF parser
extracts no styling at all, so bold in a PDF still will not arrive. Both are
stated in the register rather than counted as fixed.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from screenplay_parser.export import to_fdx
from screenplay_parser.fdx_parser import parse_fdx
from screenplay_parser.models import Element, ElementType, Scene, ScriptDocument


BOLD = "Bold"
ITALIC = "Italic"


HEADING = '<Paragraph Type="Scene Heading"><Text>INT. ROOM - DAY</Text></Paragraph>'


def _write(tmp_path, content_xml: str) -> str:
    path = tmp_path / "styled.fdx"
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<FinalDraft DocumentType="Script" Template="No" Version="1">\n'
        f"<Content>\n{HEADING}\n{content_xml}\n</Content>\n</FinalDraft>\n",
        encoding="utf-8")
    return str(path)


def _paragraphs(doc, scene_index: int = 0):
    """(type, text, [(run_text, style_or_None)]) as the EXPORTED xml reads.

    Exported with provenance suppressed: the note is an XML comment carrying a
    parse warning count, and it must not vary what these assertions compare.
    """
    root = ET.fromstring(to_fdx(doc, provenance=None).encode())
    out = []
    for p in root.find("Content"):
        runs = []
        for t in p.findall("Text"):
            runs.append((t.text or "", t.get("Style")))
        out.append((p.get("Type"), "".join(r[0] for r in runs), runs))
    return out


def _scene_with(*elements) -> ScriptDocument:
    doc = ScriptDocument(title="T", author="A", source_format="fdx", source_filename="x.fdx")
    scene = Scene(scene_number=1, heading_raw="INT. ROOM - DAY")
    # The exporter emits a scene's heading itself and only while that scene is in
    # doc.scenes, so the heading element here would be a second copy.
    scene.elements = [el for el in elements if el.type != ElementType.SCENE_HEADING]
    doc.scenes = [scene]
    return doc


# ---------------------------------------------------------------------------
# the filed defect
# ---------------------------------------------------------------------------

def test_a_whole_bold_paragraph_survives_the_round_trip(tmp_path):
    path = _write(tmp_path, '<Paragraph Type="Action"><Text Style="Bold">A BOLD LINE.</Text></Paragraph>')
    doc = parse_fdx(path)

    el = doc.scenes[0].elements[1]   # [0] is the scene heading
    assert el.text == "A BOLD LINE."
    assert el.spans, "the parser dropped the Bold style — that was the gap"

    _, text, runs = _paragraphs(doc)[1]   # [0] is the emitted scene heading
    assert text == "A BOLD LINE."
    assert runs == [("A BOLD LINE.", BOLD)], f"export lost the emphasis: {runs}"


def test_a_partial_italic_keeps_its_boundaries(tmp_path):
    path = _write(
        tmp_path,
        '<Paragraph Type="Dialogue">'
        "<Text>This is </Text><Text Style=\"Italic\">emphasised</Text><Text> speech.</Text>"
        "</Paragraph>")
    doc = parse_fdx(path)

    _, text, runs = _paragraphs(doc)[1]
    assert text == "This is emphasised speech.", "the words must not change"
    assert runs == [("This is ", None), ("emphasised", ITALIC), (" speech.", None)], runs


def test_combined_bold_and_italic_is_not_collapsed(tmp_path):
    path = _write(
        tmp_path,
        '<Paragraph Type="Action"><Text Style="Bold+Italic">BOTH.</Text></Paragraph>')
    doc = parse_fdx(path)

    el = doc.scenes[0].elements[1]   # [0] is the scene heading
    assert el.styles_at(0) == frozenset({BOLD, ITALIC}), (
        f"Bold+Italic read as {el.styles_at(0)!r}; Final Draft composes styles "
        "with '+' and both must survive")

    _, _, runs = _paragraphs(doc)[1]
    assert runs[0][1] is not None
    assert set(runs[0][1].split("+")) == {BOLD, ITALIC}, runs


def test_offsets_are_right_when_the_text_is_stripped(tmp_path):
    """`parse_fdx` strips the joined text, so spans must be shifted to match.

    Computed against the un-stripped concatenation they would point at the wrong
    characters — the failure that looks like "emphasis lands one word early".
    """
    path = _write(
        tmp_path,
        '<Paragraph Type="Action">'
        "<Text>   </Text><Text Style=\"Bold\">BOLD</Text><Text> plain</Text>"
        "</Paragraph>")
    doc = parse_fdx(path)

    el = doc.scenes[0].elements[1]   # [0] is the scene heading
    assert el.text == "BOLD plain", el.text
    assert el.styles_at(0) == frozenset({BOLD})
    assert el.styles_at(5) == frozenset(), "the trailing word must not be bold"

    _, _, runs = _paragraphs(doc)[1]
    assert runs == [("BOLD", BOLD), (" plain", None)], runs


def test_a_round_trip_is_stable(tmp_path):
    """Export -> parse -> export must not drift, or every save rewrites the file."""
    path = _write(
        tmp_path,
        '<Paragraph Type="Action">'
        "<Text>a </Text><Text Style=\"Bold\">b</Text><Text> c</Text></Paragraph>")
    once = parse_fdx(path)
    first = to_fdx(once)

    # Same filename, because the provenance note records the source file and a
    # renamed copy is a different document by that measure.
    twice_path = tmp_path / "styled.fdx"
    twice_path.write_text(first, encoding="utf-8")
    second = to_fdx(parse_fdx(str(twice_path)))

    assert second == first


# ---------------------------------------------------------------------------
# the trap: spans must survive being written to disk and read back
# ---------------------------------------------------------------------------

def test_spans_survive_a_working_copy_round_trip():
    """`from_dict` builds Element(...) explicitly, so a new field is dropped
    unless it is read there too. working.json is reloaded constantly, so a fix
    that forgets this works until the next save and then evaporates."""
    doc = _scene_with(Element(type=ElementType.ACTION, text="A BOLD LINE.",
                              spans=[{"start": 0, "end": 6, "styles": [BOLD]}]))
    reloaded = ScriptDocument.from_dict(doc.to_dict())

    el = reloaded.scenes[0].elements[0]
    assert el.spans, "the spans were lost through to_dict/from_dict"
    assert el.styles_at(0) == frozenset({BOLD})


def test_an_older_document_without_spans_still_loads():
    """Every project already on disk was written before this field existed."""
    old = {"title": "T", "author": "A", "source_format": "fdx", "source_filename": "",
           "parse_confidence": "high", "front_matter": [], "warnings": [],
           "scenes": [{"scene_number": 1, "heading_raw": "INT. ROOM - DAY",
                       "elements": [{"type": "action", "text": "plain line"}]}]}
    doc = ScriptDocument.from_dict(old)

    el = doc.scenes[0].elements[0]   # this document has no heading element
    assert el.text == "plain line"
    assert el.spans == []
    assert el.styles_at(0) == frozenset()


def test_unstyled_documents_are_unaffected():
    """No emphasis in, byte-identical shape out — one plain run per paragraph."""
    doc = _scene_with(Element(type=ElementType.ACTION, text="Plain."),
                      Element(type=ElementType.CHARACTER, text="MARA"),
                      Element(type=ElementType.DIALOGUE, text="Hello."))
    for ptype, text, runs in _paragraphs(doc)[1:]:
        assert len(runs) == 1, f"{ptype} gained a spurious run: {runs}"
        assert runs[0][1] is None, f"{ptype} gained a spurious Style: {runs}"


def test_adjacent_runs_with_the_same_style_are_merged():
    """Two Bold runs side by side are one run; emitting two is not a defect but
    the exporter should produce the minimal form so a round trip is stable."""
    doc = _scene_with(Element(type=ElementType.ACTION, text="BOLDBOLD",
                              spans=[{"start": 0, "end": 4, "styles": [BOLD]},
                                     {"start": 4, "end": 8, "styles": [BOLD]}]))
    _, _, runs = _paragraphs(doc)[1]
    assert runs == [("BOLDBOLD", BOLD)], runs


def test_overlapping_spans_compose_rather_than_duplicate_text():
    doc = _scene_with(Element(type=ElementType.ACTION, text="abcdef",
                              spans=[{"start": 0, "end": 4, "styles": [BOLD]},
                                     {"start": 2, "end": 6, "styles": [ITALIC]}]))
    _, text, runs = _paragraphs(doc)[1]

    assert text == "abcdef", f"text was duplicated or dropped: {text!r}"
    styles = [r[1] for r in runs]
    assert len(runs) == 3, f"expected bold-only / both / italic-only: {runs}"
    assert set(styles[1].split("+")) == {BOLD, ITALIC}, styles


def test_a_span_beyond_the_text_is_clamped_not_crashed():
    """Corrupt or hand-edited data must not take the export down."""
    doc = _scene_with(Element(type=ElementType.ACTION, text="short",
                              spans=[{"start": 0, "end": 999, "styles": [BOLD]}]))
    _, text, runs = _paragraphs(doc)[1]
    assert text == "short"
    assert runs == [("short", BOLD)], runs


# ---------------------------------------------------------------------------
# the editing rule
# ---------------------------------------------------------------------------

def test_replacing_a_line_drops_its_emphasis():
    """A whole-line replacement cannot know where the emphasis belonged.

    Keeping the old spans would attach the writer's emphasis to whatever
    characters happen to sit at those offsets in the new sentence — a silent,
    wrong edit dressed up as preservation. Dropping it is the honest rule, and
    it is the rule this test exists to state.
    """
    from screenplay_studio.revision import apply_replacements

    doc = _scene_with(Element(type=ElementType.ACTION, text="OLD BOLD LINE.",
                              spans=[{"start": 0, "end": 3, "styles": [BOLD]}]))
    result = apply_replacements(doc, 1, [{"old": "OLD BOLD LINE.", "new": "A completely different line."}])
    assert result["applied"], result

    el = doc.scenes[0].elements[-1]   # _scene_with emits no heading element
    assert el.text == "A completely different line."
    assert el.spans == [], "stale spans survived a full-line replacement"


def test_an_unstyled_line_edited_stays_unstyled():
    from screenplay_studio.revision import apply_replacements

    doc = _scene_with(Element(type=ElementType.ACTION, text="OLD."))
    apply_replacements(doc, 1, [{"old": "OLD.", "new": "NEW."}])
    assert doc.scenes[0].elements[-1].spans == []
