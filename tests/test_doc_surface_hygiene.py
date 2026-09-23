"""A retired surface stays retired in the docs, not just in the DOM.

The Problem Board was cut in P0.2 and `test_app_symbol_integrity` has proved the
element is gone ever since — but `CONTEXT.md` (the glossary AGENTS.md tells every
agent to use for official names), the UI/UX spec, `ARCHITECTURE.md`, the PRD and
the persona doc all went on describing it in the present tense for a whole
release cycle. A next session reading the glossary would rebuild the fifth
findings surface the Evidence lens exists to replace, and every code test would
stay green, because none of them open a doc.

So this checks the docs the same way the symbol test checks the bundle: each
retired id may only be mentioned where the surrounding lines say so.
"""
from __future__ import annotations

import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_PATHS = ["CONTEXT.md", "docs/UI_UX_SPECIFICATION.md", "docs/ARCHITECTURE.md",
             "docs/PRD.md", "docs/USER_PERSONAS.md"]

# The names and ids a retired surface left behind -> the words that mark it as
# retired. A mention is honest when the line carries a marker itself or sits
# within WINDOW lines of one. Both spellings are listed because the glossary
# names surfaces in prose (`**Problem Board**`) while the spec names the element
# (`#problem-board`), and it was the prose entry that drifted longest.
MARKERS = ("retired", "dormant", "removed", "gone", "fold")
RETIRED = [
    ("Problem Board", "#problem-board", "#pb-edge-tab"),
    ("Structure Rail", "structural rail", "#struct-rail"),
    ("Feedback View", "#feedback-view"),
]
WINDOW = 3


def _offenders(rel_path):
    lines = open(os.path.join(_ROOT, rel_path), encoding="utf-8").read().split("\n")
    bad = []
    for names in RETIRED:
        for i, line in enumerate(lines):
            if not any(n.lower() in line.lower() for n in names):
                continue
            around = "\n".join(lines[max(0, i - WINDOW):i + WINDOW + 1])
            if not any(m in around.lower() for m in MARKERS):
                bad.append(f"{rel_path}:{i + 1}: {line.strip()[:78]}")
    return bad


def test_retired_surfaces_are_labelled_as_retired_wherever_a_doc_names_them():
    offenders = []
    for doc in DOC_PATHS:
        assert os.path.exists(os.path.join(_ROOT, doc)), f"{doc} disappeared"
        offenders += _offenders(doc)
    assert not offenders, (
        "a living doc describes a retired surface as if it still ships — a reader "
        "would rebuild it:\n  " + "\n  ".join(offenders))


if __name__ == "__main__":
    test_retired_surfaces_are_labelled_as_retired_wherever_a_doc_names_them()
    print("ok")
