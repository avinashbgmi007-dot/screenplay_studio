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
