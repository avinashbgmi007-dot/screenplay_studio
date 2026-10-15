"""The uncalibrated marking must be in the UI copy, not in a code comment.

**The gap this closes.** Spec 9c states the ship obligation plainly: section 1
ships with v0 weights *explicitly marked as such in the UI copy, never
silently*. Track B section 1 shipped with the word UNCALIBRATED present in
`core.js` — twice, both times inside a code comment — and a comment next to a
constant table is invisible to the writer who is being asked to trust it. Worse,
that comment claimed the weights "ship labelled as such", which was false: it
asserted a property the code did not have.

That is the arc's standing error in a new costume — a claim about behaviour
written into a comment, checked by nobody, and wrong.

**How the check works.** Strip every comment out of the shipped JS and require
the word to survive. A word that only exists in comments cannot render, so if
it is gone after stripping, the marking is not in the copy. This is a blunt
instrument and deliberately so: it cannot tell you the marking is *legible* or
*well-placed*, only that it exists in something that can render.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBAPP = os.path.join(ROOT, "screenplay_studio", "webapp")


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$|(?<=[;{})\s])//[^\n]*", "", src)


def test_the_marking_exists_in_rendering_code_not_only_in_comments() -> None:
    survivors = []
    for name in ("app.js", "core.js"):
        path = os.path.join(WEBAPP, name)
        with open(path, encoding="utf-8") as fh:
            code = _strip_comments(fh.read())
        if "uncalibrated" in code.lower():
            survivors.append(name)
    assert survivors, (
        "the word 'uncalibrated' appears only in comments. Spec 9c requires the "
        "marking in the UI COPY so the writer sees that the impact weights are a "
        "hypothesis. A comment beside the constant table is invisible to exactly "
        "the person it is meant to inform."
    )


def test_the_marking_is_attached_to_the_queue_section_head() -> None:
    """Not merely present — attached to the thing the writer is looking at."""
    path = os.path.join(WEBAPP, "app.js")
    with open(path, encoding="utf-8") as fh:
        code = _strip_comments(fh.read())
    assert "dock-section-hint" in code, (
        "the hint class is gone; the uncalibrated marking is either detached "
        "from the queue section head or has been renamed without updating this."
    )
    assert re.search(r'el\("span", "dock-section-hint",\s*"[^"]*uncalibrated', code, re.I), (
        "the ledger section head no longer carries the uncalibrated marking."
    )
