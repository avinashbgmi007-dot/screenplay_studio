"""
Writer's library — the cross-project knowledge layer.

Sam (Sameer) and the script doctor currently know only the script on the
desk; the writer's relationship memory learns *how they work*, but nothing
about *what they've written before*. This module closes that gap with a
deterministic, always-available digest of the writer's past projects: title,
characters, scene/page counts, and the top theme findings from each project's
analysis report (when one exists). No model calls — it's built from
parsed.json + report.findings.json, so it's instant and never flakes.

The digest rides into the co-writer system prompt as a clearly-labelled
"PAST WORK" block (with a grounding guard: never confuse past work with the
current script, never invent details beyond the digest), and the same data
powers a "Your library" panel in the sidebar for quick navigation back to
earlier scripts.
"""

from __future__ import annotations

import json
import os

LIBRARY_GROUNDING_GUARD = (
    "These are the writer's PAST scripts — a different shelf from what's on "
    "the desk right now. Never merge them with the current script or premise, "
    "never quote from them as if they were the current pages, and never invent "
    "details of past scripts beyond what is listed. Refer to them only when "
    "the writer brings them up or a pattern genuinely carries over to the "
    "work at hand."
)


def build_library(projects_dir: str, exclude: str | None = None, limit: int = 0) -> list[dict]:
    """Digest every parsed project under projects_dir (excluding the 'ideas'
    sibling store, and optionally the current project). Deterministic, no
    model calls. Sorted by name; set limit to cap the list."""
    projects_dir = os.path.abspath(projects_dir)
    entries = []
    if not os.path.isdir(projects_dir):
        return entries
    for name in sorted(os.listdir(projects_dir)):
        d = os.path.join(projects_dir, name)
        if not os.path.isdir(d):
            continue
        if name == "ideas":
            continue
        if exclude and name == exclude:
            continue
        parsed_path = os.path.join(d, "parsed.json")
        if not os.path.exists(parsed_path):
            continue
        try:
            with open(parsed_path, "r", encoding="utf-8") as f:
                p = json.load(f)
        except (OSError, ValueError):
            # Flag, don't drop: a corrupt parse still counts as past work.
            # Same key as a readable entry ("project") so consumers never have
            # to special-case the shape.
            entries.append({"project": name, "title": name, "unreadable": True})
            continue
        themes = []
        report_path = os.path.join(d, "report.findings.json")
        if os.path.exists(report_path):
            try:
                with open(report_path, "r", encoding="utf-8") as f:
                    r = json.load(f)
                for fnd in r.get("findings") or []:
                    if fnd.get("category") == "theme" and fnd.get("issue"):
                        themes.append(fnd["issue"][:120])
            except (OSError, ValueError):
                pass
        entries.append({
            "project": name,
            "title": (p.get("title") or "").strip() or name,
            "source_format": p.get("source_format"),
            "scene_count": p.get("scene_count"),
            "estimated_page_count": p.get("estimated_page_count"),
            "characters": (p.get("all_characters") or [])[:8],
            "themes": themes[:4],
        })
    if limit and len(entries) > limit:
        entries = entries[:limit]
    return entries


def library_digest_text(library: list[dict], limit: int = 6) -> str:
    """Compact prompt block for the system prompt — a few lines per project,
    clearly separated from the current script, with the grounding guard.

    An unreadable project is stated as such. It used to render as a normal
    entry full of "?" placeholders, which is the one thing the guard forbids:
    the guard says "never invent details of past scripts beyond what is
    listed", and a row of question marks is an invitation to fill the gap."""
    if not library:
        return ""
    lines = ["PAST WORK — other scripts on this writer's shelf (for reference only):"]
    for e in library[:limit]:
        if e.get("unreadable"):
            lines.append(
                f"- \"{e.get('title')}\": the file is unreadable — nothing about "
                f"this script is known. Do not describe it or guess at its contents."
            )
            continue
        chars = ", ".join(e.get("characters") or []) or "—"
        scenes = e.get("scene_count") or "?"
        fmt = e.get("source_format") or "?"
        themes = "; ".join(e.get("themes") or []) or "not analyzed yet"
        lines.append(
            f"- \"{e.get('title')}\" ({scenes} scenes, {fmt}): "
            f"characters {chars}; themes: {themes}"
        )
    lines.append(LIBRARY_GROUNDING_GUARD)
    return "\n".join(lines)
