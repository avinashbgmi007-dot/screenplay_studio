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


def _strip_comments(src):
    """app.js source with its `//` line comments removed."""
    return chr(10).join(re.sub(r"//.*$", "", line) for line in src.splitlines())


def _top_level_functions(src):
    """{name: [body, ...]} for every top-level `function`/`async function` decl.

    A top-level declaration starts at column 0 (no indentation), which is how
    app.js is written; indented helpers/nested functions are not collected.
    `async` counts: without it a gate on an async renderer silently reads an
    empty body and passes for the wrong reason.
    """
    matches = list(re.finditer(
        r"(?m)^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", src))
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


def test_mass_strip_reads_the_one_counter():
    # P0.3 rider (spec §7/§8): EVERY count in the dock comes from the one
    # counting path. The mass strip is the last surface that walked
    # state.findings itself: it kept a private `findingOpen` scan for its
    # headline, its severity mass and its category weights, so the day
    # findingCounts() gains a rule (a new disposition, a scope) the strip's
    # numbers start drifting from the chips, the queue header and the dawn
    # meter -- silently, in the one place the writer reads as "the truth about
    # this script". It now presents findingCounts()'s scan instead of running
    # its own.
    body = (_top_level_functions(_source()).get("buildScriptMassStrip") or [""])[0]
    assert "findingOpen(" not in body, \
        "the mass strip must not decide what is open -- read findingCounts()"
    assert "forEach" not in body, \
        "the mass strip must not scan the findings itself -- read findingCounts()"
    assert "findingCounts()" in body, \
        "the mass strip must print the one counter's numbers"


def test_pace_score_has_one_renderer():
    # P1.10 (spec §5, one panel per question): the per-scene pace index was drawn
    # only in the doctor's report panel while the craft shelf's Pacing chart drew
    # a DIFFERENT metric (dialogue vs action words per page). Two charts, one
    # name, neither answering "where does it drag". `renderPacingPanel` is now the
    # ONE renderer and carries both labeled metrics — which also means the shelf
    # and the dock's Pacing section (the same function) stop disagreeing.
    owners = sorted(n for n, bodies in _top_level_functions(_source()).items()
                    if any("pace_score" in b for b in bodies))
    assert owners == ["renderPacingPanel"], \
        f"pace_score must be drawn in exactly one renderer, found: {owners}"


def test_delta_vocabulary_is_one_source():
    # P1.10 (spec §8 "vocabulary unification"): the arrival strip said
    # "no longer flagged / still live / new" while the diff banner said
    # "resolved / carried / still open" — the same four numbers, two dialects,
    # in the two places a writer compares drafts. One constant now, and neither
    # renderer is allowed to restate the words.
    src = _source()
    assert re.search(r"(?m)^const DELTA_TERMS = \{", src), \
        "DELTA_TERMS must be a module-level constant (one vocabulary)"
    banner = (_top_level_functions(src).get("renderDiffBanner") or [""])[0]
    arrival = (_top_level_functions(src).get("buildArrivalStrip") or [""])[0]
    for body, who in ((banner, "renderDiffBanner"), (arrival, "buildArrivalStrip")):
        assert "DELTA_TERMS" in body, f"{who} must print DELTA_TERMS' words"
    # Comments are how a renderer names the server's own fields; only the words
    # a writer can read are held to the one vocabulary.
    said = _strip_comments(banner + chr(10) + arrival)
    for banned in (" resolved", " carried", " still open", "Still present",
                   "Resolved in this", " still live", " no longer flagged", " new`"):
        assert banned not in said, \
            f"a renderer still hard-codes the delta word {banned.strip()!r}"