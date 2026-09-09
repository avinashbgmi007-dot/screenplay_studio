"""
Pacing — deterministic per-scene pace index. No model calls.

The writer asked for a visual of *where the script slows down*, with scene
numbers on it. A model-judged tension curve is one way; a deterministic,
reproducible pace index is the better first cut — consistent on every run,
explainable, and it never contradicts the pages.

The proxy: a scene drags when it is long in words but low in dramatic
movement. Two measurable signals:

  - density   — words per beat (beat = one action or dialogue element).
                High density = the scene meanders inside each beat.
  - action_share — action words / total words. High = movement on the page;
                low = talking heads.

pace_score combines them (higher = slower/draggier), normalized across the
script. Scenes scoring in the top drag band are flagged with their scene
numbers — those are the ones the pacing chart highlights and the writer
can jump to.
"""

from __future__ import annotations

from screenplay_parser.models import ScriptDocument, ElementType

# pace_score >= this (out of 100) flags a scene as a pace drag
DRAG_THRESHOLD = 68.0
# never flag more than this many scenes
MAX_DRAGS = 4


def per_scene_pace(doc: ScriptDocument) -> list[dict]:
    rows = []
    for scene in doc.scenes:
        total = action = dialogue = beats = 0
        for el in scene.elements:
            words = len(el.text.split())
            if not words:
                continue
            total += words
            beats += 1
            if el.type == ElementType.DIALOGUE:
                dialogue += words
            else:
                action += words
        rows.append({
            "scene_number": scene.scene_number,
            "words": total,
            "action_words": action,
            "dialogue_words": dialogue,
            "beats": beats,
            "density": round(total / max(1, beats), 1),       # words per beat
            "action_share": round(action / max(1, total), 3),  # movement share
            "pace_score": 0,
            "drag": False,
        })

    if not rows:
        return rows

    densities = [r["density"] for r in rows]
    shares = [r["action_share"] for r in rows]
    dmin, dmax = min(densities), max(densities)
    smin, smax = min(shares), max(shares)
    dspan = max(1e-9, dmax - dmin)
    sspan = max(1e-9, smax - smin)

    for r in rows:
        density_norm = (r["density"] - dmin) / dspan
        # invert action_share: low movement => high drag contribution
        action_norm = (smax - r["action_share"]) / sspan
        r["pace_score"] = round(100 * (0.6 * density_norm + 0.4 * action_norm), 0)

    # flag the slowest scenes, respecting the cap
    candidates = sorted(rows, key=lambda r: -r["pace_score"])
    for r in candidates[:MAX_DRAGS]:
        if r["pace_score"] >= DRAG_THRESHOLD and r["words"] >= 20:
            r["drag"] = True
    return rows


def drag_findings(rows: list[dict]) -> list[dict]:
    """Pace drags as findings (category structure, rule pacing_drag) so they
    land in the report and the Fix Queue."""
    findings = []
    for r in rows:
        if not r["drag"]:
            continue
        findings.append({
            "category": "structure",
            "rule_id": "pacing_drag",
            "issue": f"Pace drag — Scene {r['scene_number']} runs long with little movement",
            "why_it_matters": (
                f"{r['words']} words across {r['beats']} beats "
                f"({r['density']} words per beat) with only {round(100 * r['action_share'])}% "
                "action words — the scene meanders where the story needs to move. "
                "Check whether it can be cut, tightened, or given a real event."
            ),
            "severity": "medium",
            "scene_refs": [r["scene_number"]],
            "evidence_quote": None,
        })
    return findings
