"""
Gap 25: PDF completeness was assessed GLOBALLY, so a page could vanish.

Filed: a synthetic two-page PDF with an extractable page 1 and an image-only
page 2 returned lines for page 1 only. No OCR ran for page 2, no page-specific
warning was issued, and the parse looked complete. The writer's scene on page 2
was simply gone from the analysis.

The unit of judgment has to be the PAGE, because the page is the unit the writer
lost. These tests drive the real `parse_pdf` against real PDFs built here, so the
behaviour tested is the behaviour that runs. The PDFs are assembled as raw bytes
on purpose: the repo has no PDF-writing dependency, and adding one to test a
parser would be a new failure mode in the build for no coverage.
"""

import pytest

from screenplay_parser import pdf_parser

# --- a minimal, valid PDF writer (no dependency) ---------------------------

PAGE_ONE = ["INT. STUDY - NIGHT", "MARA unlocks a drawer.",
            "MARA", "I'll tell you everything."]
PAGE_TWO = ["INT. KITCHEN - DAY", "Mara sits at the table, saying nothing."]


def _pdf_text_page(lines, y0=720):
    """Helvetica text placed on a Letter page, as PDF content-stream bytes."""
    parts = ["BT", "/F1 12 Tf", "72 %d Td" % y0]
    for i, ln in enumerate(lines):
        esc = (ln.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)"))
        parts.append("14 TL")
        parts.append("(%s) Tj" % esc)
        if i != len(lines) - 1:
            parts.append("T*")
    parts.append("ET")
    return "\n".join(parts)


def _write_pdf(path, page_streams):
    """A complete PDF: one page per content stream, none sharing resources."""
    objs = []
    n_pages = len(page_streams)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n_pages))
    objs.append("<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>")
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, stream in enumerate(page_streams):
        page_obj = 4 + 2 * i
        content_obj = page_obj + 1
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj} 0 R >>")
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref_at = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n").encode()
    with open(str(path), "wb") as fh:
        fh.write(bytes(out))
    return str(path)


def _text_pdf(path, pages):
    return _write_pdf(path, [_pdf_text_page(p) for p in pages])


def _image_only_page_pdf(path):
    """Page 1 has a real text layer; page 2 is ink with no text on it at all."""
    return _write_pdf(path, [_pdf_text_page(PAGE_ONE), "0 0 1 RG 1 w 72 300 400 300 re S"])


class TestAPageThatYieldedNothingIsNotSuccess:

    def test_the_extractor_reports_the_blank_page_instead_of_dropping_it(self, tmp_path):
        pdf = _image_only_page_pdf(tmp_path / "mixed.pdf")
        blank = []
        lines, _pol, _layout = pdf_parser._extract_reconstructed_lines(pdf, blank)
        assert any(ln.strip() for ln in lines), "page 1 should have extracted"
        assert blank == [2], f"page 2 yielded nothing and was not reported: {blank}"

    def test_a_fully_readable_pdf_reports_no_blank_pages(self, tmp_path):
        pdf = _text_pdf(tmp_path / "clean.pdf", [PAGE_ONE, PAGE_TWO])
        blank = []
        pdf_parser._extract_reconstructed_lines(pdf, blank)
        assert blank == []


class TestTheParseSaysWhatItDidNotRead:

    def test_a_mixed_pdf_discloses_the_unread_page(self, tmp_path, monkeypatch):
        # No OCR engine: the honest outcome is an ERROR naming the page, not a
        # successful-looking parse that is quietly missing a scene.
        monkeypatch.setattr(pdf_parser, "_get_ocr_engine", lambda *a, **k: None)
        pdf = _image_only_page_pdf(tmp_path / "mixed.pdf")
        doc = pdf_parser.parse_pdf(pdf)
        errors = [w for w in doc.warnings if getattr(w, "severity", "") == "error"]
        assert errors, "a page's text was missing and nothing was flagged as an error"
        joined = " ".join(w.message for w in errors)
        assert "2" in joined and "MISSING" in joined.upper(), (
            "the error does not say WHICH page is missing or that it is missing:\n"
            + joined)

    def test_the_coverage_record_names_the_unread_pages(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_parser, "_get_ocr_engine", lambda *a, **k: None)
        pdf = _image_only_page_pdf(tmp_path / "mixed.pdf")
        doc = pdf_parser.parse_pdf(pdf)
        cov = doc.page_coverage
        assert cov["total_pages"] == 2
        assert cov["pages_unread"] == [2]
        assert cov["read_pages"] == 1
        assert cov["complete"] is False, (
            "a parse missing a page reported itself complete")

    def test_a_fully_readable_pdf_is_complete_with_no_warning_about_pages(self, tmp_path):
        pdf = _text_pdf(tmp_path / "clean.pdf", [PAGE_ONE, PAGE_TWO])
        doc = pdf_parser.parse_pdf(pdf)
        assert doc.page_coverage is None or doc.page_coverage["complete"] is True
        assert not any("MISSING" in (w.message or "").upper() for w in doc.warnings)

    def test_ocr_recovers_the_blank_page_and_says_it_was_ocr(self, tmp_path, monkeypatch):
        # The good path: an engine exists and returns text for the missing page.
        pdf = _image_only_page_pdf(tmp_path / "mixed.pdf")
        monkeypatch.setattr(pdf_parser, "_get_ocr_engine", lambda *a, **k: "ocr")
        called = {}

        def fake_ocr(path, engine, pages=None):
            called["pages"] = pages
            return ["INT. KITCHEN - DAY", "", "Mara sits at the table."]

        monkeypatch.setattr(pdf_parser, "_ocr_extract", fake_ocr)
        doc = pdf_parser.parse_pdf(pdf)
        assert called["pages"] == {2}, (
            "OCR was run over pages whose text layer already worked, or over none")
        cov = doc.page_coverage
        assert cov["pages_recovered_by_ocr"] == [2]
        assert cov["pages_unread"] == []
        text = " ".join(w.message for w in doc.warnings)
        assert "OCR" in text and "page(s) 2" in text.replace("Page(s) 2", "page(s) 2"), (
            "the writer is not told which pages were read by OCR:\n" + text)

    def test_ocr_that_recovers_nothing_leaves_the_page_unread(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_parser, "_get_ocr_engine", lambda *a, **k: "ocr")
        monkeypatch.setattr(pdf_parser, "_ocr_extract",
                            lambda path, engine, pages=None: ["", "", ""])
        pdf = _image_only_page_pdf(tmp_path / "mixed.pdf")
        doc = pdf_parser.parse_pdf(pdf)
        assert doc.page_coverage["pages_unread"] == [2]
        assert doc.page_coverage["complete"] is False, (
            "OCR returned nothing and the page was counted as read")
