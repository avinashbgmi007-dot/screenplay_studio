"""
Parser for screenplay PDFs.

Standard screenplay PDFs don't carry semantic tags the way .fdx does — we
only have positioned text. Reliably classifying scene heading vs. action vs.
character vs. dialogue from column position alone is fragile across the many
tools that export screenplay PDFs (margins vary), so this takes a different
approach:

We use pdfplumber to detect paragraph *breaks* (a vertical gap between lines
noticeably larger than the page's typical line spacing signals the end of
one block and the start of another — this is robust across tools, unlike
absolute indentation). We reconstruct a plain-text version of the script
with real blank lines inserted at those breaks, tag each reconstructed line
with its source page number, and then run it through the exact same
classifier used for .txt files (heuristics.py + text_parser._parse_lines).

This is the lowest-confidence source format of the four — PDF text
extraction can merge columns, drop hyphenation, or misjudge gaps on
non-standard layouts — so output is always marked parse_confidence="low"
and callers should treat it as a solid starting draft rather than ground
truth, and expect to spot-check scene boundaries and character attribution.
"""

import os
import re
import statistics
import tempfile

import pdfplumber

from .models import ParseWarning
from .text_parser import _parse_lines

# Signal that a PDF's text layer is unrecoverable: fonts without a ToUnicode
# map extract as raw glyph tokens. Two patterns cover the extractors we use:
# pdfplumber emits "(cid:N)" per glyph; pypdf echoes the glyph names
# ("/0", "/13", ...) for Final-Draft-style Type3 fonts. When a file is
# dominated by either, no character information exists to reconstruct —
# OCR is the only path, and we say so explicitly instead of silently
# producing an empty script.
_CID_TOKEN_RE = re.compile(r"\(cid:\d+\)")
_GLYPH_NAME_RE = re.compile(r"^[/0-9 ]+$")


def _looks_unrecoverable(lines: list[str]) -> bool:
    nonblank = [l for l in lines if l.strip()]
    if not nonblank:
        return False
    cid_lines = sum(1 for l in nonblank if _CID_TOKEN_RE.search(l))
    glyph_lines = sum(1 for l in nonblank if _GLYPH_NAME_RE.match(l.strip()))
    return (cid_lines / len(nonblank)) > 0.5 or (glyph_lines / len(nonblank)) > 0.5

PARAGRAPH_BREAK_FACTOR = 1.35  # gap > this * median line-height counts as a paragraph break

# ---------------------------------------------------------------------------
# Text-layer cleanup and layout hints.
#
# Two artifacts show up in real-world screenplay PDFs:
#   1. Glyph doubling — some exporters (and pdfplumber's own line merge of
#      overlapping text objects) emit every character twice: "DOCTOR (CONT'D)"
#      comes back as "DDOOCCTTOORR ((CCOONNTT''DD))". The every-char-twice
#      pattern is unambiguous, so we collapse it.
#   2. Page-number footers like "2." / "3." (sometimes doubled to "22.."),
#      which are never screenplay content.
#
# The parser also reattaches each line's *column position* (normalized to the
# page width) so the shared classifier can use indentation as a strong hint:
# screenplay PDFs use the same relative indents regardless of exporter —
# action & scene headings at the left margin, dialogue ~1in in, character
# cues centered, transitions right-aligned. Normalized bands adapt to
# whatever margins the exporting tool used.
# ---------------------------------------------------------------------------

_PAGE_NUMBER_RE = re.compile(r"^\d{1,3}\.?\s*$")


def _collapse_doubled(line: str) -> str:
    """Collapse an every-glyph-doubled line (see above) back to its real text.

    Exporters double every *character* but not spaces — the two interleaved
    halves differ only where a space fell on the odd positions — so the halves
    are compared without spaces and the even half (which keeps the spaces) is
    returned."""
    if len(line) < 4:
        return line
    half_a = line[::2]
    half_b = line[1::2]
    if half_a.replace(" ", "") == half_b.replace(" ", ""):
        return half_a
    return line


# Type3 fonts with a partial ToUnicode map emit U+FFFD for glyphs they can't
# map — in these scripts (and Final Draft exports generally) that is always the
# apostrophe, e.g. "SIDDHU\uFFFDS" and "(CONT\uFFFD D)". A replacement char is
# never legit screenplay content, so normalize it to a straight apostrophe;
# this also keeps character-cue detection working on names like
# "GOON_ONE (CONT'D)" that would otherwise fail the cue regex.

def _normalize_unmapped(text: str) -> str:
    return text.replace("\ufffd", "'")


def _clean_line(raw: str) -> str:
    return _normalize_unmapped(_collapse_doubled(raw.strip()).strip())


def _layout_band(x0, page_width: float) -> str:
    """Relative column band for a line's left edge: left | dialogue | center | right."""
    if not page_width or x0 is None:
        return "left"
    r = x0 / page_width
    if r >= 0.60:
        return "right"
    if r >= 0.34:
        return "center"
    if r >= 0.22:
        return "dialogue"
    return "left"

# ---------------------------------------------------------------------------
# OCR fallback for PDFs without a usable text layer (Type3 fonts / no ToUnicode
# maps — common with some Final Draft exports, and virtually all scanned or
# hand-typed PDFs). Rendering + OCR is the only way to read those; this path is
# optional and lazily detected so the parser never hard-depends on a specific
# OCR stack.
#
# Engines, in priority order:
#   1. tesseract via pytesseract (lang packs tel+hin+eng recommended)
#   2. easyocr (neural; downloads Telugu/Hindi/English models on first use)
#
# Set SCRIPT_DOCTOR_OCR=tesseract|easyocr to force an engine (skips probing),
# and SCRIPT_DOCTOR_OCR_LANG to override the tesseract -l language string.
# ---------------------------------------------------------------------------

_DEFAULT_OCR_LANG = "eng+tel+hin"


def _get_ocr_engine():
    """Return a callable(image_path) -> str, or None if no OCR engine is usable."""
    forced = os.environ.get("SCRIPT_DOCTOR_OCR", "").strip().lower()
    lang = os.environ.get("SCRIPT_DOCTOR_OCR_LANG", _DEFAULT_OCR_LANG).strip()

    def _tesseract():
        import pytesseract
        pytesseract.get_tesseract_version()  # raises if binary missing
        return lambda path: pytesseract.image_to_string(path, lang=lang)

    def _easyocr():
        import easyocr
        reader = easyocr.Reader(["en", "te", "hi"], gpu=False)
        return lambda path: "\n".join(res[1] for res in reader.readtext(path))

    if forced in ("tesseract", "pytesseract"):
        try:
            return _tesseract()
        except Exception:
            return None
    if forced == "easyocr":
        try:
            return _easyocr()
        except Exception:
            return None

    # auto-detect: tesseract first (fast, no heavy deps), then easyocr
    try:
        return _tesseract()
    except Exception:
        pass
    try:
        return _easyocr()
    except Exception:
        pass
    return None


def _bitmap_to_png_bytes(bitmap) -> bytes:
    """Encode a rendered page to PNG bytes without depending on pypdfium2's
    version-specific API surface (newer builds have .to_png(); older ones only
    .to_pil())."""
    to_png = getattr(bitmap, "to_png", None)
    if to_png is not None:
        return to_png()
    import io
    buf = io.BytesIO()
    bitmap.to_pil().save(buf, format="PNG")
    return buf.getvalue()


def _ocr_extract(pdf_path: str, engine) -> list[str]:
    """Render each page to an image and OCR it; return a text line list with
    synthetic blank lines at page breaks (same shape as the text-layer path)."""
    import pypdfium2 as pdfium

    lines: list[str] = []
    pdf = pdfium.PdfDocument(pdf_path)
    for i in range(len(pdf)):
        page = pdf[i]
        bitmap = page.render(scale=200 / 72)  # ~200 dpi
        png = _bitmap_to_png_bytes(bitmap)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(png)
                tmp_path = f.name
            text = (engine(tmp_path) or "") if tmp_path else ""
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        prev_blank = False
        for ln in text.splitlines():
            if ln.strip():
                lines.append(ln.strip())
                prev_blank = False
            elif not prev_blank:
                lines.append("")  # blank lines delimit blocks — preserve them
                prev_blank = True
        lines.append("")  # page break
    return lines


def _extract_reconstructed_lines(pdf_path: str) -> tuple[list[str], dict, dict]:
    """Returns (lines, page_of_line, line_layout): the reconstructed plain-text
    lines (with synthetic blank lines at paragraph breaks, glyph doubling
    collapsed, and page-number footers dropped), each line's source page, and
    each line's relative column band ('left'|'dialogue'|'center'|'right') —
    the layout hint the shared classifier uses to disambiguate dialogue vs.
    action and to catch right-aligned transitions."""
    lines: list[str] = []
    page_of_line: dict[int, int] = {}
    line_layout: dict[int, str] = {}

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            try:
                page_lines = page.extract_text_lines(layout=False, strip=True)
            except Exception:
                page_lines = []

            if not page_lines:
                continue

            width = page.width or 1.0
            tops = [pl["top"] for pl in page_lines]
            gaps = [b - a for a, b in zip(tops, tops[1:]) if b > a]
            median_gap = statistics.median(gaps) if gaps else 12.0

            prev_bottom = None
            for pl in page_lines:
                text = _clean_line(pl.get("text") or "")
                if not text or _PAGE_NUMBER_RE.match(text):
                    continue
                top = pl["top"]
                bottom = pl.get("bottom", top)

                if prev_bottom is not None:
                    gap = top - prev_bottom
                    if gap > median_gap * PARAGRAPH_BREAK_FACTOR:
                        lines.append("")  # synthetic blank line = paragraph break

                page_of_line[len(lines)] = page_index
                line_layout[len(lines)] = _layout_band(pl.get("x0"), width)
                lines.append(text)
                prev_bottom = bottom

            # page boundary itself is a soft break, unless the next page clearly
            # continues the same paragraph — we can't know that reliably, so we
            # insert a blank line at every page boundary and accept that a
            # dialogue block split across a page turn may get closed early.
            lines.append("")

    return lines, page_of_line, line_layout


def parse_pdf(path: str):
    filename = os.path.basename(path)
    lines, page_of_line, line_layout = _extract_reconstructed_lines(path)

    if _looks_unrecoverable(lines) or not lines or not any(l.strip() for l in lines):
        engine = _get_ocr_engine()
        if engine is not None:
            ocr_lines = _ocr_extract(path, engine)
            if any(l.strip() for l in ocr_lines):
                doc = _parse_lines(ocr_lines, source_format="pdf", filename=filename)
                doc.parse_confidence = "low"
                doc.warnings.insert(0, ParseWarning(
                    message="The PDF's text layer was not recoverable (Type3 fonts without a "
                            "Unicode mapping), so it was read via OCR instead. Expect OCR "
                            "imperfections — spot-check names, dialogue and scene headings. "
                            "For higher accuracy, re-export from Final Draft as .fdx or .fountain.",
                    severity="warning",
                ))
                return doc
        from .models import ScriptDocument
        doc = ScriptDocument(title=None, author=None, source_format="pdf", source_filename=filename)
        doc.parse_confidence = "low"
        doc.warnings.append(ParseWarning(
            message="This PDF's text layer is not recoverable (its fonts carry no Unicode "
                    "mapping), and no OCR engine is available. Re-export the screenplay "
                    "from Final Draft as .fdx or .fountain for full analysis, or install "
                    "tesseract + pytesseract (with tel, hin and eng language packs) so "
                    "the built-in OCR path can read it — the parser auto-detects it.",
            severity="error",
        ))
        return doc

    doc = _parse_lines(lines, source_format="pdf", filename=filename, page_of_line=page_of_line, line_layout=line_layout)
    doc.parse_confidence = "low"
    doc.warnings.insert(0, ParseWarning(
        message="Parsed from PDF using layout-gap heuristics, not explicit formatting tags. "
                "Scene boundaries and character attribution are best-effort — spot-check before "
                "trusting citations in the analysis report. For higher accuracy, re-export or "
                "convert the source to Final Draft (.fdx) or Fountain if available.",
        severity="warning",
    ))
    return doc
