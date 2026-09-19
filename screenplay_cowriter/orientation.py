"""Deterministic orientation — where this conversation stands.

Two facts a writer has to reconstruct from scratch every time they come back to
a desk: where the conversation left off, and where their branch sits relative to
the one it was forked from. Both are already computable from stored state — the
probe flag, the message list, `forked_at_index` — so both are computed here and
stated as FACTS. Nothing is inferred by a model, and nothing is invented (the
same honest-memory rule the mood fragment follows: the personas colour their
energy with these lines, they never quote them as script content).

Pure and cheap: no model call, no disk walk, no state. `script_ctx` is optional
and only its scene headings are read — with it absent the lines still work, they
just name scene numbers instead of headings.

The lines are one implementation behind three surfaces: the mood fragment (so
the persona knows where you are), the CLI session banner, and the CLI `/switch`
output. One resolver, so the three cannot drift.
"""

from __future__ import annotations

# The names the writer knows these two by. The persona keys are internal
# identifiers; the mood fragment is read by the model (which knows who it is)
# but the CLI banner is read by the WRITER, so a human name is the point.
PERSONA_NAMES = {
    "writing_partner": "Sameer",
    "script_consultant": "Dr. Sushruta",
}

# A heading is script text and rides into a prompt (as `script_map` already
# does), so it is bounded — a malformed heading must not become a paragraph.
MAX_HEADING_CHARS = 80

# How many of the parent's added scenes to name before trailing off. Enough to
# orient, not a second ledger.
MAX_NAMED_SCENES = 3


def _persona_name(persona: str | None) -> str:
    if not persona:
        return "the co-writer"
    return PERSONA_NAMES.get(persona, persona)


def _heading_for(scene_number: int, script_ctx) -> str:
    if script_ctx is None:
        return ""
    try:
        scenes = script_ctx.data.get("scenes") or []
    except Exception:
        return ""
    for s in scenes:
        if s.get("scene_number") != scene_number:
            continue
        heading = (s.get("heading_raw") or s.get("heading") or "").strip()
        if len(heading) > MAX_HEADING_CHARS:
            heading = heading[:MAX_HEADING_CHARS - 1].rstrip() + "…"
        return heading
    return ""


def _scene_phrase(scene_refs, script_ctx=None) -> str:
    """' about scene 4 (INT. HOSPITAL - NIGHT)' — or '' when nothing was
    referenced. Only the first reference is named: a turn can pull in several
    scenes, and a resume line that lists five of them is a report, not a
    greeting."""
    for ref in (scene_refs or []):
        if not isinstance(ref, int):
            continue
        heading = _heading_for(ref, script_ctx)
        return f" about scene {ref} ({heading})" if heading else f" about scene {ref}"
    return ""


def _scenes_in(messages) -> list[int]:
    """Distinct scene numbers referenced by these messages, in order."""
    seen: list[int] = []
    for m in messages or []:
        for ref in (getattr(m, "scene_refs", None) or []):
            if isinstance(ref, int) and ref not in seen:
                seen.append(ref)
    return seen


def resume_line(session, script_ctx=None) -> str | None:
    """Where the conversation left off, or None for a session with no turns.

    `awaiting_probe` is the load-bearing fact and it is a LIVE flag, not a
    timestamp: the engine sets it when it ends a turn on a probe question and
    clears it on the writer's next turn, so 'you left off mid-probe' is true
    exactly while it is true and disappears by itself once answered.
    """
    branch = session.branch
    messages = list(branch.messages or [])
    if not messages:
        return None
    last_user = next((m for m in reversed(messages) if m.role == "user"), None)
    where = _scene_phrase(getattr(last_user, "scene_refs", None), script_ctx) if last_user else ""
    who = _persona_name(branch.active_persona)
    if branch.awaiting_probe:
        return (f"- You left off mid-probe: {who} asked you a question{where} and "
                f"is waiting on your answer.")
    return f"- Your last turn was with {who}{where}."


def _fork_children(session, name: str) -> str | None:
    """The other direction: branches forked FROM the one you are standing on.

    Without this, switching back to the fork point says nothing at all (main has
    no parent), which is exactly the half of "switching back" the writer is
    most likely to be asking about — they left a fork behind and want to know
    whether it went anywhere.
    """
    kids = [b for b in (session.branches or {}).values() if b.parent_branch == name]
    if not kids:
        return None
    parts = []
    for b in sorted(kids, key=lambda b: b.name):
        added = max(0, len(b.messages) - (b.forked_at_index or 0))
        parts.append(f"'{b.name}' ({added} turn(s))")
    return f"- Branches forked from '{name}': " + ", ".join(parts) + "."


def branch_position(session) -> list[str]:
    """How this branch stands relative to the ones it was forked from AND the
    ones forked from it, or [] for a session with a single branch.

    `forked_at_index` is the parent's message count at the moment of the copy,
    and the fork starts with exactly that many messages — so both sides'
    movement since is simple subtraction, not a diff of message content. A
    content diff would need a model; the counts do not, and the counts are what
    the writer is actually missing ("main moved and I didn't notice").
    """
    branch = session.branch
    lines: list[str] = []
    parent_name = branch.parent_branch
    if parent_name:
        lines.extend(_against_parent(session, branch, parent_name))
    child_note = _fork_children(session, branch.name)
    if child_note:
        lines.append(child_note)
    return lines


def _against_parent(session, branch, parent_name: str) -> list[str]:
    parent = (session.branches or {}).get(parent_name)
    forked_at = branch.forked_at_index or 0
    mine = max(0, len(branch.messages) - forked_at)
    if parent is None:
        return [f"- This branch ('{branch.name}') was forked from '{parent_name}', "
                f"which is no longer on file."]
    theirs = max(0, len(parent.messages) - forked_at)
    head = (f"- This branch ('{branch.name}') was forked from '{parent_name}' "
            f"at turn {forked_at}.")

    if not theirs and not mine:
        return [head + " Neither has moved since."]

    if theirs:
        moved = f"'{parent_name}' has added {theirs} turn(s)"
        scenes = _scenes_in(parent.messages[forked_at:])[:MAX_NAMED_SCENES]
        if scenes:
            moved += " about " + ", ".join(f"scene {n}" for n in scenes)
        tail = f"this branch has added {mine}" if mine else "this branch has not moved"
        return [head + " Since then " + moved + ", and " + tail + "."]

    return [head + f" You have added {mine} turn(s) here and '{parent_name}' has not moved since."]


def orientation_lines(session, script_ctx=None) -> list[str]:
    """Everything above, in reading order: where you left off, then where the
    branch sits. One call for every surface."""
    lines: list[str] = []
    line = resume_line(session, script_ctx)
    if line:
        lines.append(line)
    lines.extend(branch_position(session))
    return lines
