"""Deterministic reveal-mechanic scan (accuracy kit B).

Twist mechanics live in single action lines a summary drops ("it was a
dream"). This scan finds candidate lines so script-level passes can account
for them. Lexical only — no model call, never fails a run.
"""

from __future__ import annotations

import re

REVEAL_PATTERNS = [
    re.compile(r"\bit was (all )?a dream\b", re.I),
    re.compile(r"\bdreamt\b|\bdreaming\b", re.I),
    re.compile(r"\bwok[ee] (up )?to\b.{0,20}\bdream", re.I),
    re.compile(r"\bkalaa\b", re.I),
    re.compile(r"\bjust a dream\b|\bonly a dream\b", re.I),
    re.compile(r"\bdead .{0,20}\balive\b", re.I),
]


def scan_reveals(doc) -> list:
    """Return [{scene, line, match}] for reveal-candidate lines, in order."""
    found = []
    for s in doc.scenes or []:
        for e in s.elements or []:
            text = getattr(e, "text", None) or (e.get("text") if isinstance(e, dict) else "")
            if not text:
                continue
            for p in REVEAL_PATTERNS:
                m = p.search(str(text))
                if m:
                    found.append({"scene": s.scene_number, "line": str(text)[:160],
                                  "match": m.group(0)})
                    break
    return found


def reveal_context_block(candidates: list) -> str:
    if not candidates:
        return ""
    lines = ["Candidate story mechanics (deterministic scan — verify against the text,",
             "do not assume; if a finding contradicts one, the finding is suspect):"]
    for c in candidates:
        lines.append(f"- Scene {c['scene']}: '{c['line']}'")
    return "\n".join(lines)
