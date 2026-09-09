"""
OCR-path tests for the canonical fixture PDF (Pain_FD_4_scenes.pdf).

That PDF's fonts carry no Unicode mapping, so its text layer is unrecoverable.
When an OCR engine is available the parser must render the pages, OCR them,
and run the result through the normal classifier — this is how a writer's
Tenglish/Hindi PDF actually gets read. These tests stub the engine (the real
OCR stack is optional and machine-dependent) and verify the pipeline end to
end against the real fixture file.
"""

import os

import pytest

from screenplay_parser import pdf_parser

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "Pain_FD_4_scenes.pdf")
TRANSCRIPTION = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "pain_tenglish.fountain")


def _stub_engine(calls: list):
    """A fake OCR engine: reads the canonical transcription (the text that a
    real tesseract/easyocr run produced for this exact PDF) and records the
    image paths it was asked to read."""
    body = open(TRANSCRIPTION, encoding="utf-8").read()
    body = body.split("\n\n", 1)[1]  # skip the fountain title page

    def engine(image_path: str) -> str:
        calls.append(image_path)
        # only the first page carries the script; later pages return nothing so
        # the parse isn't polluted by 4x duplication
        return body if len(calls) == 1 else ""

    return engine


@pytest.fixture
def ocr_engine(monkeypatch):
    calls: list = []
    monkeypatch.setattr(pdf_parser, "_get_ocr_engine", lambda: _stub_engine(calls))
    return calls


def test_ocr_path_reads_the_fixture_pdf(ocr_engine):
    doc = pdf_parser.parse_pdf(FIXTURE)
    # the pipeline must actually have rendered pages and called the engine
    assert len(ocr_engine) >= 1, "OCR engine was never called"
    for img in ocr_engine:
        assert os.path.exists(img) is False, "temp images must be cleaned up"
    assert doc.scenes, "OCR path produced no scenes from the fixture PDF"
    assert doc.parse_confidence == "low"
    chars = {c for s in doc.scenes for c in s.characters_present}
    assert "RISHI" in chars and "DOCTOR" in chars and "SIDDHARTH" in chars


def test_ocr_warning_mentions_ocr(ocr_engine):
    doc = pdf_parser.parse_pdf(FIXTURE)
    msgs = " ".join(w.message for w in doc.warnings)
    assert "OCR" in msgs
    assert ".fdx" in msgs or ".fountain" in msgs


def test_no_engine_still_gives_actionable_error(monkeypatch):
    monkeypatch.setattr(pdf_parser, "_get_ocr_engine", lambda: None)
    doc = pdf_parser.parse_pdf(FIXTURE)
    assert doc.scenes == []
    errors = [w.message for w in doc.warnings if w.severity == "error"]
    assert errors
    # the message must now point at both remedies: re-export AND the OCR path
    msg = errors[0]
    assert "OCR" in msg and ".fdx" in msg and "tesseract" in msg


def test_render_does_not_require_pil():
    """The render path uses pypdfium2's native PNG encoder, not PIL."""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(FIXTURE)
    bitmap = pdf[0].render(scale=200 / 72)
    png = pdf_parser._bitmap_to_png_bytes(bitmap)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
