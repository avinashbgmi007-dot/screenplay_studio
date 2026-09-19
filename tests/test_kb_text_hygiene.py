"""The craft KB's rule text must be readable prose, not codec debris.

Context: 135 em dashes had been mangled into the three characters
U+00E2 U+20AC U+201D and stored as the JSON escape text ``\\u00e2\\u20ac\\u201d``
across 21 of the 26 rule files. ``Rule.to_prompt_fragment()`` interpolates
``definition`` and ``detection_signal`` verbatim, so every analyzer prompt
carried the debris:

    "...from the story's beginning to its end â€" not just a change..."

Two of the mangled dashes sat in rule NAMES, so they surfaced in reports as
titles. One rule (``bell_midpoint_shift``) additionally carried two Chinese
words mangled the same way.

The KB's whole reason for existing is that grounding beats the model's memory.
Grounding text that is itself corrupted defeats the point, and the failure is
silent — nothing raises, the prompt just reads slightly wrong. These tests make
it loud.

See ``docs/KB_TIER_REVIEW.md`` section 6.1.
"""
from __future__ import annotations

import glob
import json
import os

import pytest

from knowledge_base import KnowledgeBase

_RULES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "knowledge_base", "rules",
)

# The fields `to_prompt_fragment()` interpolates, plus the two that are shown to
# a writer as a finding's title and rule reference.
_TEXT_FIELDS = ("id", "name", "definition", "detection_signal",
                "counter_considerations")

# A Latin-1 supplement / C1 character in an English craft rule is always
# debris: the mangling above lands entirely inside this range, while legitimate
# punctuation (em dash U+2014, arrow U+2192) sits outside it.
_MOJIBAKE_RANGE = (0x0080, 0x00FF)


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase()


def test_no_rule_text_carries_a_mojibake_character(kb):
    """A character in U+0080-U+00FF means a wrong codec touched the file."""
    lo, hi = _MOJIBAKE_RANGE
    offenders = []
    for rule in kb.all():
        for field in _TEXT_FIELDS:
            value = str(getattr(rule, field, "") or "")
            bad = sorted({c for c in value if lo <= ord(c) <= hi})
            if bad:
                shown = " ".join(f"{c!r}(U+{ord(c):04X})" for c in bad[:4])
                offenders.append(f"{rule.id}.{field}: {shown}")
    assert not offenders, (
        "rule text carries mangled characters (a codec bug, not content): "
        + "; ".join(offenders[:8])
    )


def test_every_rule_file_is_pure_ascii_on_disk():
    """The durable half of the fix.

    The corruption was stored as JSON ``\\u`` escapes, so a scan for the
    mangled characters' UTF-8 bytes finds nothing. Keeping the files ASCII-only
    means a later wrong-codec save cannot reintroduce it at all: there is no
    non-ASCII byte left to mis-decode. JSON ``\\u`` escapes are lossless here —
    the loader opens every file with ``encoding="utf-8"``.
    """
    non_ascii = []
    for path in sorted(glob.glob(os.path.join(_RULES_DIR, "*.json"))):
        raw = open(path, "rb").read()
        if any(b > 127 for b in raw):
            name = os.path.basename(path)
            bad = sorted({b for b in raw if b > 127})[:4]
            non_ascii.append(f"{name} (bytes {[hex(b) for b in bad]})")
    assert not non_ascii, (
        "KB rule files must stay ASCII-only so a wrong-codec save cannot "
        "reintroduce the mojibake; escape non-ASCII as \\uXXXX: "
        + "; ".join(non_ascii)
    )


def test_the_repaired_names_and_definition_read_correctly(kb):
    """Pin the specific sites that were broken, so a regression is caught as a
    named failure rather than a count."""
    # Two user-visible rule NAMES carried the debris.
    assert kb.get("bell_fictive_dream").name == (
        "The Goal Is the Fictive Dream\u2014Transport the Reader"
    )
    assert kb.get("zinsser_dump_the_clutter").name == (
        "Dump the Clutter\u2014Every Word Must Earn Its Place"
    )
    # And one definition carried two mangled Chinese words next to their own
    # English glosses; the foreign word is dropped, the gloss kept.
    definition = kb.get("bell_midpoint_shift").definition
    assert "often passive; after, they become active." in definition, definition
    # Guard the specific way this repair can go wrong: deleting the foreign
    # word must not weld it onto the English one.
    assert "oftenpassive" not in definition, definition
    assert "becomeactive" not in definition, definition


def test_a_prompt_fragment_renders_the_dash_not_the_debris(kb):
    """End-to-end: what the model actually receives.

    This is the assertion that matters — the fragment is the artifact that
    shipped corrupted, not the JSON."""
    fragment = kb.get("character_arc_change").to_prompt_fragment()
    assert "\u2014" in fragment, "the em dash is missing from the fragment"
    assert "\u00e2\u20ac" not in fragment, (
        "the mojibake sequence still reaches the prompt"
    )
    # No fragment anywhere in the KB may contain the debris.
    dirty = [r.id for r in kb.all()
             if "\u00e2\u20ac" in r.to_prompt_fragment()]
    assert not dirty, f"fragments still carrying mojibake: {dirty}"
