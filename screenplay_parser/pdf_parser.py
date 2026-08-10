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
import statistics

import pdfplumber

from .models import ParseWarning
from .text_parser import _parse_lines

PARAGRAPH_BREAK_FACTOR = 1.35  # gap > this * median line-height counts as a paragraph break


def _extract_reconstructed_lines(pdf_path: str) -> tuple[list[str], dict]:
    lines: list[str] = []
    page_of_line: dict[int, int] = {}

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            try:
                page_lines = page.extract_text_lines(layout=False, strip=True)
            except Exception:
                page_lines = []

            if not page_lines:
                continue

            tops = [pl["top"] for pl in page_lines]
            gaps = [b - a for a, b in zip(tops, tops[1:]) if b > a]
            median_gap = statistics.median(gaps) if gaps else 12.0

            prev_bottom = None
            for pl in page_lines:
                text = pl.get("text", "").strip()
                if not text:
                    continue
                top = pl["top"]
                bottom = pl.get("bottom", top)

                if prev_bottom is not None:
                    gap = top - prev_bottom
                    if gap > median_gap * PARAGRAPH_BREAK_FACTOR:
                        lines.append("")  # synthetic blank line = paragraph break

                page_of_line[len(lines)] = page_index
                lines.append(text)
                prev_bottom = bottom

            # page boundary itself is a soft break, unless the next page clearly
            # continues the same paragraph — we can't know that reliably, so we
            # insert a blank line at every page boundary and accept that a
            # dialogue block split across a page turn may get closed early.
            lines.append("")

    return lines, page_of_line


def parse_pdf(path: str):
    filename = os.path.basename(path)
    lines, page_of_line = _extract_reconstructed_lines(path)

    if not lines or not any(l.strip() for l in lines):
        from .models import ScriptDocument
        doc = ScriptDocument(title=None, author=None, source_format="pdf", source_filename=filename)
        doc.parse_confidence = "low"
        doc.warnings.append(ParseWarning(
            message="No extractable text found in PDF. It may be a scanned/image-based PDF — "
                    "run OCR first (e.g. ocrmypdf) and re-import the result.",
            severity="error",
        ))
        return doc

    doc = _parse_lines(lines, source_format="pdf", filename=filename, page_of_line=page_of_line)
    doc.parse_confidence = "low"
    doc.warnings.insert(0, ParseWarning(
        message="Parsed from PDF using layout-gap heuristics, not explicit formatting tags. "
                "Scene boundaries and character attribution are best-effort — spot-check before "
                "trusting citations in the analysis report. For higher accuracy, re-export or "
                "convert the source to Final Draft (.fdx) or Fountain if available.",
        severity="warning",
    ))
    return doc
