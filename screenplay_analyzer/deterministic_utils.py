"""Shared deterministic utility functions used across the analysis pipeline.
Extracted to eliminate code duplication while preserving the same behavior."""
from __future__ import annotations

from screenplay_parser.models import ScriptDocument, ElementType


def dialogue_lines_by_character(doc: ScriptDocument) -> dict[str, list[str]]:
    """Extract all dialogue lines organized by character name.
    Used by voice analysis, continuity checks, and other deterministic passes."""
    lines: dict[str, list[str]] = {}
    for scene in doc.scenes:
        current = None
        for e in scene.elements:
            if e.type == ElementType.CHARACTER:
                current = e.text.strip()
            elif e.type == ElementType.DIALOGUE and current:
                lines.setdefault(current, []).append(e.text.strip())
                current = None  # one line per cue; parentheticals attach to it
    return lines


def int_list(value) -> list[int]:
    """Convert a value to a list of integers, ignoring non-convertible elements.
    Used by character dials and setup/payoff ledger parsing."""
    if not isinstance(value, list):
        return []
    out = []
    for v in value:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            continue
    return out
