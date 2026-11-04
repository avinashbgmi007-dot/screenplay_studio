"""Tests for screenplay_parser.export — deterministic source-format export.

These prove the return half of the writer's loop: a parsed script can be
exported to Fountain / FDX / plain text, and the exported text re-parses
into the same structure (exact for FDX, which carries type tags; equivalent
for the text formats on the happy path).
"""

import json

import pytest

from screenplay_parser import (
    parse_fdx, parse_fountain, parse_txt, export, export_to_path, to_fdx,
)
from screenplay_parser.export import SUPPORTED_FORMATS


def _load_doc(tmp_path, sample_fountain):
    doc = parse_fountain(sample_fountain)
    assert doc.scene_count == 3
    return doc


def _element_signature(doc):
    """(type, text) tuples per scene — the structural fingerprint used for
    round-trip comparisons."""
    return [
        [(e.type.value, e.text) for e in s.elements]
        for s in doc.scenes
    ]


class TestExportDispatch:
    def test_supported_formats_exportable(self, tmp_path, sample_fountain):
        doc = _load_doc(tmp_path, sample_fountain)
        for fmt in SUPPORTED_FORMATS:
            text = export(doc, fmt)
            assert isinstance(text, str) and len(text) > 100

    def test_unsupported_format_raises(self, tmp_path, sample_fountain):
        doc = _load_doc(tmp_path, sample_fountain)
        with pytest.raises(ValueError):
            export(doc, "docx")

    def test_export_to_path_writes_file(self, tmp_path, sample_fountain):
        doc = _load_doc(tmp_path, sample_fountain)
        out = tmp_path / "out.fountain"
        text = export_to_path(doc, "fountain", str(out))
        assert out.exists()
        assert out.read_text(encoding="utf-8") == text


class TestFountainRoundTrip:
    def test_round_trip_preserves_structure(self, tmp_path, sample_fountain):
        doc = _load_doc(tmp_path, sample_fountain)
        exported = export(doc, "fountain")
        # parse the export from a real file path
        p = tmp_path / "roundtrip.fountain"
        p.write_text(exported, encoding="utf-8")
        reparsed = parse_fountain(str(p))

        assert reparsed.scene_count == doc.scene_count
        assert _element_signature(reparsed) == _element_signature(doc)

    def test_fountain_contains_title_page(self, tmp_path, sample_fountain):
        doc = _load_doc(tmp_path, sample_fountain)
        exported = export(doc, "fountain")
        assert "Title: E2E Test Script" in exported
        assert "Author: Test" in exported

    def test_fountain_transitions_forced(self, tmp_path, sample_fountain):
        doc = _load_doc(tmp_path, sample_fountain)
        exported = export(doc, "fountain")
        assert "> CUT TO:" in exported


class TestFdxRoundTrip:
    def test_fdx_round_trip_is_exact(self, tmp_path, sample_fountain):
        doc = _load_doc(tmp_path, sample_fountain)
        exported = to_fdx(doc)
        p = tmp_path / "roundtrip.fdx"
        p.write_text(exported, encoding="utf-8")
        reparsed = parse_fdx(str(p))

        assert reparsed.scene_count == doc.scene_count
        assert _element_signature(reparsed) == _element_signature(doc)
        assert reparsed.title == doc.title
        assert reparsed.author == doc.author

    def test_fdx_is_valid_xml_with_paragraph_types(self, tmp_path, sample_fountain):
        doc = _load_doc(tmp_path, sample_fountain)
        exported = to_fdx(doc)
        assert "<FinalDraft" in exported
        assert 'Type="Scene Heading"' in exported
        assert 'Type="Action"' in exported
        assert 'Type="Dialogue"' in exported

    def test_edited_document_exports_and_reparses(self, tmp_path, sample_fountain):
        """Simulates the revision flow: change a dialogue line, export, re-parse —
        the edit survives the round trip."""
        doc = _load_doc(tmp_path, sample_fountain)
        scene = doc.scenes[1]
        for el in scene.elements:
            if el.type.value == "dialogue":
                el.text = "I changed my mind about all of it."
                break

        exported = to_fdx(doc)
        p = tmp_path / "edited.fdx"
        p.write_text(exported, encoding="utf-8")
        reparsed = parse_fdx(str(p))

        texts = [e["text"] for e in reparsed.scenes[1].to_dict()["elements"]]
        assert "I changed my mind about all of it." in texts


class TestDialogueAttributionSurvivesRoundTrip:
    """Gap 21: the exporter glued a new character cue onto the previous
    speaker's dialogue, so a re-parse read the next speech as more of the
    previous one. Every line was attributed to the first speaker.

    Driven through the real exporter and the real parser (write to a file,
    `parse_*` it back), because that is the loop the writer actually uses.
    """

    SOURCE = """Title: Round Trip

INT. ROOM - DAY

AJAY
Hello.

VENU
Hi.

AJAY
How are you?
"""

    # n.b. `AJAY / Hello. / VENU / Hi. / AJAY / ...` is the case that used to
    # break: the same speaker appearing twice also exercises the "no blank
    # between two character cues" path.
    EXPECTED = [
        ("character", "AJAY"), ("dialogue", "Hello."),
        ("character", "VENU"), ("dialogue", "Hi."),
        ("character", "AJAY"), ("dialogue", "How are you?"),
    ]

    @staticmethod
    def _speech(doc):
        return [(e.type.value, e.text) for s in doc.scenes for e in s.elements
                if e.type.value in ("character", "dialogue")]

    @pytest.mark.parametrize("fmt", ["fountain", "txt"])
    def test_adjacent_speakers_keep_their_lines(self, tmp_path, fmt):
        src = tmp_path / "in.fountain"
        src.write_text(self.SOURCE, encoding="utf-8")
        doc = parse_fountain(str(src))
        assert self._speech(doc) == self.EXPECTED, "fixture does not parse as intended"

        out = tmp_path / f"out.{fmt}"
        out.write_text(export(doc, fmt), encoding="utf-8")
        reparsed = parse_fountain(str(out))

        assert self._speech(reparsed) == self.EXPECTED, (
            f"{fmt} round trip reassigned dialogue:\n{out.read_text(encoding='utf-8')}")

    @pytest.mark.parametrize("fmt", ["fountain", "txt"])
    def test_a_new_cue_is_separated_by_a_blank_line(self, tmp_path, fmt):
        """Stated at the text level as well, so a future parser change cannot
        make the test above pass for the wrong reason."""
        src = tmp_path / "in.fountain"
        src.write_text(self.SOURCE, encoding="utf-8")
        text = export(parse_fountain(str(src)), fmt)
        assert "Hello.\n\nVENU\n" in text, (
            f"{fmt}: the next speaker's cue is glued to the previous dialogue:\n{text}")

    @pytest.mark.parametrize("fmt", ["fountain", "txt"])
    def test_an_empty_element_between_speeches_does_not_suppress_the_blank(self, tmp_path, fmt):
        """The blank used to be decided from `elements[i + 1]` — literally the
        next list entry — rather than the next element that actually gets
        EMITTED, so a text-less element in between suppressed it.

        This is a REGRESSION GUARD, not evidence of a fixed defect: I measured
        the parser's own output across every .fountain in the repo and found 0
        text-less elements out of 164, so nothing in the real parse path
        triggers this today. It is kept because the writers `continue` past such
        elements and the invariant is easy to re-break.
        """
        from screenplay_parser.models import Element, ElementType, Scene, ScriptDocument

        doc = ScriptDocument(title="T", author=None, source_format="fountain",
                             source_filename="x.fountain")
        doc.scenes.append(Scene(
            scene_number=1, heading_raw="INT. ROOM - DAY", elements=[
                Element(type=ElementType.CHARACTER, text="AJAY"),
                Element(type=ElementType.DIALOGUE, text="Hello."),
                # the shape a blank line between speeches takes: an element
                # with no text, which the writers `continue` past
                Element(type=ElementType.ACTION, text=""),
                Element(type=ElementType.CHARACTER, text="VENU"),
                Element(type=ElementType.DIALOGUE, text="Hi."),
            ]))

        out = tmp_path / f"out.{fmt}"
        out.write_text(export(doc, fmt), encoding="utf-8")
        reparsed = parse_fountain(str(out))

        assert self._speech(reparsed) == [
            ("character", "AJAY"), ("dialogue", "Hello."),
            ("character", "VENU"), ("dialogue", "Hi."),
        ], out.read_text(encoding="utf-8")

    @pytest.mark.parametrize("fmt", ["fountain", "txt"])
    def test_the_repo_fixture_round_trips_without_attribution_churn(self, tmp_path, fmt):
        """The shipped fixture, end to end. Pre-fix this changed 3 of its 36
        speech elements; it must now change none.

        Scope, stated plainly: this is the repo's only real .fountain fixture,
        so it is far smaller than the writer's own scripts. It demonstrates that
        the blank-line block boundary now survives a round trip; it does not
        reproduce the per-script counts quoted in the register, which came from
        parsed representations of the user's PDFs that are not in the repo.
        """
        import pathlib

        fixture = pathlib.Path(__file__).parent / "fixtures" / "pain_tenglish.fountain"
        doc = parse_fountain(str(fixture))
        before = self._speech(doc)

        out = tmp_path / f"out.{fmt}"
        out.write_text(export(doc, fmt), encoding="utf-8")
        after = self._speech(parse_fountain(str(out)))

        assert len(before) > 30, "fixture too small to be evidence"
        assert after == before, (
            f"{sum(1 for a, b in zip(before, after) if a != b)} speech elements "
            f"changed through a {fmt} round trip")
