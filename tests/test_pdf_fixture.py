"""Fixture-based PDF tests.

Pain_FD_4_scenes.pdf is the user-supplied canonical test PDF (a 4-scene
Final Draft export). Its fonts are Type3 with numeric glyph names and no
ToUnicode table, so the text layer is unrecoverable by any extractor. The
correct behavior is not a crash and not a silent empty parse — it's a
clear, actionable error. These tests lock that in, and keep the fixture
available for future PDF-path tests.
"""

import os

from screenplay_parser import parse_pdf

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "Pain_FD_4_scenes.pdf")


def test_fixture_exists():
    assert os.path.exists(FIXTURE), "canonical test PDF missing from tests/fixtures/"


def test_unrecoverable_pdf_does_not_crash():
    doc = parse_pdf(FIXTURE)
    assert doc.scenes == []
    assert doc.parse_confidence == "low"


def test_unrecoverable_pdf_gives_actionable_error():
    doc = parse_pdf(FIXTURE)
    errors = [w.message for w in doc.warnings if w.severity == "error"]
    assert errors, "expected an error-severity warning"
    msg = errors[0]
    # the message must tell the writer what's wrong and what to do
    assert "Unicode" in msg or "recover" in msg
    assert ".fdx" in msg or "OCR" in msg or "ocrmypdf" in msg
