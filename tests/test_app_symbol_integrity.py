"""Structural integrity of the shipped SPA bundle (app.js).

app.js is a classic script, not a module: a duplicated top-level function is a
silent override (the last declaration wins). That is exactly how two
`jumpToScene` definitions shipped -- the live one always called
`openCowriteRoom()`, so the fix loop's mark/park/discuss bar was covered by the
partner drawer and the rail scene click opened a room it never asked for.

These guards make that class of bug loud instead of silent.
"""
from __future__ import annotations

import collections
import os
import re

_APP_JS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "screenplay_studio", "webapp", "app.js")


def _source():
    with open(_APP_JS, encoding="utf-8") as f:
        return f.read()


def _top_level_functions(src):
    """{name: [body, ...]} for every `^function name(` declaration.

    A top-level declaration starts at column 0 (no indentation), which is how
    app.js is written; indented helpers/nested functions are not collected.
    """
    matches = list(re.finditer(r"(?m)^function\s+([A-Za-z_$][\w$]*)\s*\(", src))
    bodies = collections.defaultdict(list)
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(src)
        bodies[m.group(1)].append(src[m.start():end])
    return bodies


def test_no_duplicate_top_level_function_names():
    # classic-script last-declaration-wins: a duplicate silently overrides.
    dups = {n: len(b) for n, b in _top_level_functions(_source()).items() if len(b) > 1}
    assert not dups, f"duplicate top-level function definitions: {dups}"


def test_jump_to_scene_is_locate_only():
    # Every caller (rail, ruler dots, scene index, the fix loop, and the quote
    # block whose tooltip reads "Jump back to this passage") wants to LOCATE a
    # scene. The old body always called openCowriteRoom(), which is what made
    # the loop's own bar unreachable.
    bodies = _top_level_functions(_source()).get("jumpToScene") or []
    assert len(bodies) == 1, "jumpToScene must have exactly one definition"
    assert "openCowriteRoom" not in bodies[0], \
        "jumpToScene must not open the co-write room -- it is a locate, not a discuss"


_INDEX_HTML = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "screenplay_studio", "webapp", "index.html")


def test_feedback_view_clone_is_gone():
    # P0.1: the dormant Feedback View clone (the renderFvBoard family in app.js
    # plus the #feedback-view markup in index.html) is deleted; the Evidence
    # dock is the canonical feedback surface.
    assert "renderFvBoard" not in _source()
    with open(_INDEX_HTML, encoding="utf-8") as f:
        # the element id, not the historical phrase in comments
        assert 'id="feedback-view"' not in f.read()


def test_problem_board_is_gone():
    # P0.2: the Problem Board (a fifth findings surface that ignored
    # findingDisposition/findingPassesFilter, contradicted the dock's counts,
    # and slid over the page during reading) is retired outright. The scene
    # rail's severity dots and the Evidence dock are the canonical surfaces.
    src = _source()
    assert "renderProblemBoard" not in src
    assert "pbItemClick" not in src
    with open(_INDEX_HTML, encoding="utf-8") as f:
        # the element id, not the historical phrase in comments
        assert 'id="problem-board"' not in f.read()
