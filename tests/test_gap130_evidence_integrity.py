"""Gap 130: audit screenshots must be distinct, disclosed captures.

This guards the old byte-identical-caption failure and preserves PNG-side
provenance for the explicitly approved demo evidence. It does not pretend to
infer the semantic UI state from a hash; the browser journey and visual review
are recorded in the evidence README and Gap 130 critique.
"""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT / "impl-shots"
J4 = ROOT / "docs/audit/evidence-2026-09-30/shots"


def _png_text(path: Path) -> dict[str, str]:
    """Read PNG tEXt chunks without an imaging-library dependency."""
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n"), f"not a PNG: {path}"
    pos = 8
    result = {}
    while pos + 12 <= len(data):
        size = struct.unpack(">I", data[pos : pos + 4])[0]
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + size]
        if kind == b"tEXt":
            key, sep, value = body.partition(b"\0")
            if sep:
                result[key.decode("latin-1")] = value.decode("latin-1")
        pos += size + 12
        if kind == b"IEND":
            break
    return result


def _assert_disclosed_and_distinct(paths: list[Path]) -> None:
    digests = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
    assert len(set(digests)) == len(paths), f"duplicate evidence frames: {paths}"
    for path in paths:
        metadata = _png_text(path)
        label = metadata.get("Gap130-Capture-Label", "")
        provenance = metadata.get("Gap130-Demo-Provenance", "")
        assert "DEMO" in label.upper(), f"missing DEMO label metadata: {path}"
        assert provenance and ("demo" in provenance.lower() or "synthetic" in provenance.lower()), path


def test_scene_function_and_character_dials_are_distinct_disclosed_frames():
    _assert_disclosed_and_distinct([
        IMPL / "A-scene_function.png",
        IMPL / "B-character-dials.png",
    ])


def test_evidence_overview_and_coverage_are_distinct_disclosed_frames():
    _assert_disclosed_and_distinct([
        IMPL / "A02-evidence-lens-full.png",
        IMPL / "B-coverage.png",
    ])


def test_j4_inline_edit_beatboard_and_draft_are_distinct_disclosed_frames():
    _assert_disclosed_and_distinct([
        J4 / "j4_inline_edit.png",
        J4 / "j4_beatboard_exported.png",
        J4 / "j4_draft_activated.png",
    ])
