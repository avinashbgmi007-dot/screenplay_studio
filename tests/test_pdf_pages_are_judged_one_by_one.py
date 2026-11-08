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

import os

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


# ---------------------------------------------------------------- the stage gate

class TestAnUnreadParseIsNotAnalysed:
    """The second half of the filed entry: a scanned-only PDF with OCR
    unavailable returned zero scenes and an error-severity warning, while the
    parse stage was marked `complete`. Analysis was not run in that probe — and
    that is exactly the state it left available.

    The gate belongs at the ANALYZE boundary, not inside run_parse: a sceneless
    upload is a legitimate validation failure the upload route already rejects
    with a 400 and specific guidance, and raising inside run_parse turned that
    careful 400 into a 500 (two pre-existing tests caught it immediately).
    """

    def _project_with(self, root, monkeypatch, doc):
        import screenplay_studio.webapp_server as W
        from screenplay_studio.manifest import ProjectManifest

        src = root / "scan.fountain"
        src.write_text("INT. ROOM - DAY\n\nMARA\nHello.\n", encoding="utf-8")
        m = ProjectManifest.create(str(root / "p"), str(src))
        m.save()
        project_name = os.path.basename(m.project_dir)
        doc.save(m.parsed_path)
        m.mark_complete("parse", {"parsed": m.parsed_path})
        monkeypatch.setattr(W, "PROJECTS_DIR", str(root))
        W.app.config["TESTING"] = True
        m.project_name = project_name
        return W.app.test_client(), m

    def test_a_parse_with_no_scenes_is_refused_with_the_parsers_reason(self, tmp_path, monkeypatch):
        from screenplay_parser.models import ParseWarning, ScriptDocument

        empty = ScriptDocument(title=None, author=None, source_format="pdf",
                               source_filename="scan.pdf")
        empty.parse_confidence = "low"
        empty.warnings.append(ParseWarning(
            message="no OCR engine is available", severity="error"))
        client, m = self._project_with(tmp_path, monkeypatch, empty)

        resp = client.post(f"/api/projects/{m.project_name}/analyze")
        assert resp.status_code == 400, (
            "an analysis was started on a parse that read zero scenes")
        assert "no scenes" in resp.get_json()["error"].lower()
        assert "OCR" in resp.get_json()["error"], (
            "the refusal does not repeat the parser's own reason")

    def test_a_readable_parse_is_not_refused(self, tmp_path, monkeypatch):
        from screenplay_parser.models import ScriptDocument
        from screenplay_parser.models import Scene, Element, ElementType

        doc = ScriptDocument(title="T", author="A", source_format="fountain",
                             source_filename="scan.fountain")
        sc = Scene(scene_number=1, heading_raw="INT. ROOM - DAY")
        sc.elements = [Element(type=ElementType.ACTION, text="Mara waits.")]
        doc.scenes = [sc]
        client, m = self._project_with(tmp_path, monkeypatch, doc)
        reason = __import__("screenplay_studio.webapp_server", fromlist=["x"]
                            )._unread_parse_reason(m)
        assert reason is None


class TestTheCoverageRecordSurvivesTheRoundTrip:

    def test_page_coverage_is_saved_and_loaded(self, tmp_path, monkeypatch):
        # R5 revert survived because the record was only ever asserted in the
        # object the parser just returned. It is worthless if it does not reach
        # disk: the desk reads the SAVED parse.
        from screenplay_parser.models import ScriptDocument

        monkeypatch.setattr(pdf_parser, "_get_ocr_engine", lambda *a, **k: None)
        pdf = _image_only_page_pdf(tmp_path / "mixed.pdf")
        doc = pdf_parser.parse_pdf(pdf)
        path = str(tmp_path / "parsed.json")
        doc.save(path)
        back = ScriptDocument.load(path)
        assert back.page_coverage is not None, (
            "page coverage was lost on save -- the desk never sees it")
        assert back.page_coverage["pages_unread"] == [2]
        assert back.page_coverage["complete"] is False

    def test_a_fully_read_pdf_round_trips_without_inventing_coverage(self, tmp_path):
        from screenplay_parser.models import ScriptDocument

        pdf = _text_pdf(tmp_path / "clean.pdf", [PAGE_ONE])
        doc = pdf_parser.parse_pdf(pdf)
        path = str(tmp_path / "parsed.json")
        doc.save(path)
        back = ScriptDocument.load(path)
        # None is "no paginated read was needed"; asserting `complete: true` here
        # would be inventing a check nobody ran.
        assert back.page_coverage is None or back.page_coverage["complete"] is True


class TestOcrIsScopedToThePagesThatNeedIt:

    def test_ocr_never_touches_a_page_whose_text_layer_worked(self, tmp_path, monkeypatch):
        # R3 survived because the fake OCR was page-blind, so "OCR everything"
        # looked identical to "OCR the gap". This fake records the pages it is
        # ALLOWED to render and fails if a readable page is included.
        pdf = _image_only_page_pdf(tmp_path / "mixed.pdf")
        monkeypatch.setattr(pdf_parser, "_get_ocr_engine", lambda *a, **k: "ocr")
        rendered = []

        def strict_ocr(path, engine, pages=None):
            rendered.append(pages)
            assert pages == {2}, f"OCR was asked to read {pages}, not just the gap"
            return ["INT. KITCHEN - DAY", "", "Mara sits at the table."]

        monkeypatch.setattr(pdf_parser, "_ocr_extract", strict_ocr)
        doc = pdf_parser.parse_pdf(pdf)
        assert rendered == [{2}]
        assert doc.page_coverage["pages_recovered_by_ocr"] == [2]


class TestThePageFilterActuallyFilters:

    def test_ocr_renders_only_the_pages_it_was_given(self, tmp_path, monkeypatch):
        """The `pages` argument is enforced inside `_ocr_extract`, so a fake
        `_ocr_extract` cannot test it -- the previous version of this file
        asserted what parse_pdf PASSES, not what OCR DOES, and a revert that
        removed the filter entirely still passed. This drives the real function
        against a fake pdfium that records every page it renders.
        """
        import sys as _sys
        import types

        rendered = []

        class _Bitmap:
            def to_pil(self):
                import io as _io
                buf = _io.BytesIO()
                from PIL import Image
                Image.new("RGB", (4, 4), "white").save(buf, format="PNG")
                return buf

        class _Page:
            def __init__(self, n):
                self.n = n

            def render(self, scale=1):
                rendered.append(self.n)
                return _Bitmap()

        class _Doc:
            def __init__(self, path):
                pass

            def __len__(self):
                return 3

            def __getitem__(self, i):
                return _Page(i + 1)

        fake = types.SimpleNamespace(PdfDocument=_Doc)
        monkeypatch.setitem(_sys.modules, "pypdfium2", fake)
        # a tiny real PNG is needed only to give the engine a path
        monkeypatch.setattr(pdf_parser, "_bitmap_to_png_bytes",
                            lambda b: b"not-a-real-png")
        lines = pdf_parser._ocr_extract("ignored.pdf", lambda p: "INT. ROOM - DAY",
                                        pages={2})
        assert rendered == [2], (
            f"OCR rendered pages {rendered}; only the requested page was allowed")
        assert any("INT. ROOM - DAY" in ln for ln in lines)

    def test_with_no_page_argument_every_page_is_rendered(self, tmp_path, monkeypatch):
        import sys as _sys
        import types

        rendered = []

        class _Bitmap:
            def to_pil(self):
                import io as _io
                buf = _io.BytesIO()
                from PIL import Image
                Image.new("RGB", (4, 4), "white").save(buf, format="PNG")
                return buf

        class _Page:
            def __init__(self, n):
                self.n = n

            def render(self, scale=1):
                rendered.append(self.n)
                return _Bitmap()

        class _Doc:
            def __init__(self, path):
                pass

            def __len__(self):
                return 2

            def __getitem__(self, i):
                return _Page(i + 1)

        monkeypatch.setitem(_sys.modules, "pypdfium2",
                            types.SimpleNamespace(PdfDocument=_Doc))
        monkeypatch.setattr(pdf_parser, "_bitmap_to_png_bytes", lambda b: b"x")
        pdf_parser._ocr_extract("ignored.pdf", lambda p: "text")
        assert rendered == [1, 2]
