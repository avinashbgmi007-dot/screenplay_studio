"""Craft history — what the writer actually did to their own pages (P2.8).

Review section 7, item 8: *"Let memory be felt, carefully — permit exactly one
class of reference: craft-preference callbacks ('last time you cut the
explainer line and it worked'), scoped, gated, never about the writer as a
person. Today a month of learning is invisible."*

Two things were invisible, and they need different fixes:

  1. The relationship card learns HOW the writer works, but the card's own
     rules forbid ever speaking it: "Never quote the memory to the writer
     ('you always say…' is forbidden)." That prohibition is correct and stays.
  2. The strongest evidence of what the writer actually accepts — the revision
     log, every line edit they applied and did not undo — was never read by
     anyone but undo/redo. The card cannot supply it either: the refresh prompt
     explicitly forbids script content, so a craft decision is out of scope for
     memory by design.

So this module supplies the one class of reference the review permits, from the
one source that can support it honestly. It reads the project's edit log
(`revision.edits_log` → `edits.json`), which holds ONLY edits still in effect —
`undo_last_edit` pops the record onto the redo stack — so every record here is
a decision the writer kept. That is the honest reading of the review's
"and it worked": not "it worked" (nobody measured that) but "they took it and
kept it", which is a fact the log can prove.

Deterministic, no model calls. What it reports is counted, never inferred: how
many lines changed, in which scenes, in which direction (word count went up or
down), and how recently. It does not guess at intent ("cut the explainer") —
that needs a model and a corpus to validate, so it is deliberately absent
rather than approximated.

Scope is structural rather than tagged: the edit log belongs to one project, so
a callback about this script cannot surface in another. That is stronger than
the observation scope gate, which has to be applied.

The block is a PERMISSION, not an instruction. It says the co-writer may bring
this up when it bears on the question in front of them, and names the four
rules that keep it safe — the first of which is that it is about the WORK and
never about the writer as a person.
"""

from __future__ import annotations

import json
import os
import time

# Two separate occasions, not two lines: two replacements inside one edit group
# are one decision made once. A single occasion is a moment, not a pattern, and
# the whole risk of this feature is overclaiming from thin evidence.
MIN_OCCASIONS = 2

# The block stays small on purpose. It is a reminder, not a report.
MAX_SCENES_NAMED = 3

DAY = 86400.0

# The carve-out from CARD_RULES' "never quote the memory". Deliberately names
# what is still forbidden, because the risk of widening a prohibition is that
# the model hears the widening as "quoting is fine now".
CRAFT_HISTORY_PERMISSION = (
    "REFERRING TO THIS IS ALLOWED — it is the one thing you may bring up "
    "unprompted, because noticing the writer's own working decisions is the "
    "whole point of remembering them. Four rules, and they are strict: "
    "(1) it is about the WORK, never about the writer as a person — never "
    "\"you always…\", never \"you tend to be…\", never a claim about their "
    "character, taste or talent; (2) only when it bears on what they are "
    "asking right now — never as an opener, never as a formula, never twice in "
    "a row; (3) their current turn always wins over anything here; (4) this is "
    "NOT the memory profile — the profile is still never quoted. If none of it "
    "is relevant to this turn, say nothing about it."
)

CRAFT_HISTORY_HEADER = (
    "WHAT THE WRITER HAS ALREADY DONE TO THESE PAGES — counted from this "
    "script's revision log, not inferred (the log holds only edits still in "
    "effect, so every one of these is a decision they kept):"
)

# The revision log's filename, matching revision.edits_log_path. Named here so
# every surface can reach the digest through ONE entry point instead of each
# re-deriving the project layout — the webapp has a manifest, the terminal has
# only a session pointing at parsed.json, and they must not disagree.
EDITS_FILE_NAME = "edits.json"


def load_project_edits(project_dir) -> list:
    """A project's revision log, or [] when it has none or cannot be read.

    Never raises: this is called on the path to a chat turn, and a damaged or
    absent log has to degrade to "nothing to say", not to a broken chat.
    """
    if not project_dir:
        return []
    try:
        with open(os.path.join(project_dir, EDITS_FILE_NAME), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def craft_history_for_dir(project_dir, now: float | None = None) -> str | None:
    """The prompt block for a project directory, or None.

    The one entry point every surface uses. A caller that has a manifest passes
    `m.project_dir`; a caller that has only a session passes the directory its
    parsed.json sits in. Neither needs to know the log's filename or shape.
    """
    return craft_history_text(build_craft_history(load_project_edits(project_dir), now=now)) or None


def _word_count(text) -> int:
    return len(str(text or "").split())


def _scene_number(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_craft_history(edits, now: float | None = None) -> dict | None:
    """Digest one project's edit log, or None when there is not enough of it.

    `edits` is the parsed `edits.json` list (see `revision.edits_log`). Returns
    a plain dict of counts, or None below the gate — callers treat None as
    "nothing to say", never as an error.

    Only the records handed in are read, so the digest cannot span projects.
    Malformed records are skipped rather than raising: this feeds a chat turn,
    and a damaged log must not be able to break one.
    """
    groups = []
    for entry in edits or []:
        if not isinstance(entry, dict):
            continue
        applied = entry.get("applied")
        if not isinstance(applied, list) or not applied:
            continue
        scene = _scene_number(entry.get("scene_number"))
        if scene is None:
            continue
        groups.append((scene, applied, entry.get("applied_at")))

    if len(groups) < MIN_OCCASIONS:
        return None

    lines = 0
    shorter = longer = same = 0
    per_scene: dict[int, int] = {}
    stamps = []
    for scene, applied, applied_at in groups:
        for rep in applied:
            if not isinstance(rep, dict):
                continue
            before = _word_count(rep.get("old"))
            after = _word_count(rep.get("new"))
            lines += 1
            if after < before:
                shorter += 1
            elif after > before:
                longer += 1
            else:
                same += 1
            per_scene[scene] = per_scene.get(scene, 0) + 1
        if isinstance(applied_at, (int, float)):
            stamps.append(float(applied_at))

    if not lines:
        return None

    ranked = sorted(per_scene.items(), key=lambda kv: (-kv[1], kv[0]))
    return {
        "occasions": len(groups),
        "lines": lines,
        "scenes": len(per_scene),
        "shorter": shorter,
        "longer": longer,
        "same_length": same,
        "top_scenes": [{"scene_number": n, "lines": c} for n, c in ranked[:MAX_SCENES_NAMED]],
        "last_at": max(stamps) if stamps else None,
        "now": float(now) if now is not None else time.time(),
    }


def _ago_phrase(last_at, now) -> str:
    """'today' / 'N day(s) ago', or '' when the log carries no timestamps."""
    if last_at is None:
        return ""
    days = int(max(0.0, now - last_at) // DAY)
    if days == 0:
        return "The most recent was today."
    return f"The most recent was {days} day(s) ago."


def craft_history_text(history) -> str:
    """The prompt block, or '' when there is nothing to say.

    Reads as counts on purpose. 'Five of the seven lines came out shorter' is
    checkable against the log; 'they cut the explainer' would not be, and an
    unverifiable claim about the writer's intent is exactly what this feature
    must not put in the co-writer's mouth.

    Two phrasings are built rather than templated, because the template lied in
    reachable cases: 'most of that work sits in X' is false when the busiest
    scene only ties, and 'shorter and 0 longer' reads as noise. Both now say
    what the counts actually support.
    """
    if not history:
        return ""
    lines = history.get("lines") or 0
    if not lines:
        return ""
    scenes = history.get("scenes") or 0
    out = [CRAFT_HISTORY_HEADER]
    out.append(
        f"- {lines} line edit(s) applied across {scenes} scene(s) "
        f"in {history.get('occasions', 0)} sitting(s)."
    )

    direction = []
    if history.get("shorter"):
        direction.append(f"{history['shorter']} came out shorter")
    if history.get("longer"):
        direction.append(f"{history['longer']} came out longer")
    if history.get("same_length"):
        direction.append(f"{history['same_length']} kept the same length")
    if direction:
        out.append("- Of those, " + ", ".join(direction) + ".")

    named = history.get("top_scenes") or []
    if named and scenes == 1:
        out.append(f"- All of it is in scene {named[0]['scene_number']}.")
    elif named:
        where = ", ".join(
            f"scene {s['scene_number']} ({s['lines']} line(s))" for s in named
        )
        # The list is capped, so say so — naming 3 of 8 scenes without a word
        # about the rest reads as the whole picture.
        rest = scenes - len(named)
        out.append(f"- Busiest scenes: {where}" + (f"; {rest} other scene(s)." if rest > 0 else "."))

    ago = _ago_phrase(history.get("last_at"), history.get("now") or time.time())
    if ago:
        out.append(f"- {ago}")
    out.append(CRAFT_HISTORY_PERMISSION)
    return "\n".join(out)
