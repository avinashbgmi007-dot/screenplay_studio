"""The shipped HTML documents are UTF-8, BOM-free, and say so (audit pass 3).

`index.html` had picked up a UTF-8 BOM before its DOCTYPE and three runs of
double-encoded text — `â†'` where the label reads `→`, in the premise card's
close button and its journey line. Those glyphs reach the writer verbatim, so
a user-visible defect sat in the app's own document while every test stayed
green: the KB hygiene test (`test_kb_text_hygiene.py`) only reads craft-rule
JSON, and nothing looked at the frontend's bytes.

The three checks below are the whole gap. They scan every HTML file the webapp
serves (the `preview-*` concept dirs included — a BOM is a defect wherever a
browser opens it) and assert on the file's own bytes, not on a server response,
so a re-stamped document cannot mask a bad source file.
"""
from __future__ import annotations

import glob
import os
import re

WEBAPP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "screenplay_studio", "webapp")

BOM = b"\xef\xbb\xbf"

# UTF-8 read back as cp1252/latin-1, then saved as UTF-8 again: multi-byte
# arrows, dashes and quotes arrive as two or three characters, each in the
# Latin-1 supplement / currency block. None of these sequences is real English
# (or Indian-language) copy, so a hit is always the double-encode.
MOJIBAKE_RE = re.compile(
    r"[\u00c2\u00c3][\u00a0-\u00bf]"      # Ã‚-Ã¿ / Â¡-Â¿ pairs
    r"|[\u00e2\u00ef][\u0080-\u00bf\u2000-\u206f]"  # â€ / ï» style tails
    r"|\u00e2[\u2010-\u206f][\u2010-\u206f]")

_CHARSET_RE = re.compile(r"""<meta[^>]+charset=["']?utf-8["']?""", re.IGNORECASE)


def html_documents():
    return sorted(glob.glob(os.path.join(WEBAPP_DIR, "**", "*.html"),
                            recursive=True))


def mojibake_runs(text):
    return [m.group(0) for m in MOJIBAKE_RE.finditer(text)]


def _read(path):
    raw = open(path, "rb").read()
    return raw, raw.decode("utf-8", errors="replace")


def test_every_served_html_document_is_utf8_without_a_bom():
    docs = html_documents()
    assert docs, f"no HTML documents found under {WEBAPP_DIR}"
    bad = []
    for path in docs:
        raw, text = _read(path)
        if raw.startswith(BOM):
            bad.append(f"{os.path.relpath(path, WEBAPP_DIR)}: starts with a BOM")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as e:
            bad.append(f"{os.path.relpath(path, WEBAPP_DIR)}: {e}")
    assert not bad, "shipped documents are not clean UTF-8:\n  " + "\n  ".join(bad)


def test_no_served_html_document_carries_double_encoded_text():
    dirty = []
    for path in html_documents():
        _raw, text = _read(path)
        runs = mojibake_runs(text)
        if runs:
            dirty.append(f"{os.path.relpath(path, WEBAPP_DIR)}: "
                         + ", ".join(repr(r) for r in runs[:4]))
    assert not dirty, ("mojibake reached the writer's screen:\n  " + "\n  ".join(dirty))


def test_the_app_document_declares_its_charset():
    _raw, text = _read(os.path.join(WEBAPP_DIR, "index.html"))
    assert _CHARSET_RE.search(text), (
        "index.html no longer declares <meta charset=\"UTF-8\"> — the byte-level "
        "hygiene above is meaningless if the browser guesses the encoding")


if __name__ == "__main__":
    for fn in (test_every_served_html_document_is_utf8_without_a_bom,
               test_no_served_html_document_carries_double_encoded_text,
               test_the_app_document_declares_its_charset):
        fn()
    print("ok")
