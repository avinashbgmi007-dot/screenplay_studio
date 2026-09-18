"""Synthetic clean-bill fallback (plan fix #5).

gun_pen has no zero-finding row naturally, so the plan sanctions a synthetic
mini-project. This seeds a tiny clean scene, uploads it, then writes a
completed analysis whose findings list is EMPTY — the exact state the
"clean bill" reading exists for. Labeled synthetic in the results.
"""
import json
import os
import sys
import urllib.request

BASE = "http://127.0.0.1:8500"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

CLEAN = """Title: The Quiet Kitchen
Author: audit probe

INT. KITCHEN - MORNING

MAYA, 30s, in yesterday's clothes, cracks an egg into a hot pan.
The smoke alarm chirps once. She doesn't look up.

DEV enters, already dressed, keys in hand.

DEV
You're up.

MAYA
The pan's up.

He opens the fridge, finds nothing, closes it.

DEV
I'll get coffee.

MAYA
You always say that.

He doesn't answer. She turns the egg over. It holds.

MAYA (CONT'D)
I fixed the alarm.

DEV
I noticed.
"""


def main():
    import requests
    r = requests.post(f"{BASE}/api/projects",
                      files={"file": ("The Quiet Kitchen.fountain", CLEAN.encode(), "text/plain")},
                      data={"title": "Clean Bill Probe"}, timeout=90)
    r.raise_for_status()
    name = r.json().get("project") or r.json().get("name")
    print("project:", name)

    pdir = os.path.join(REPO, "studio_projects", name)
    # write a completed analysis with ZERO findings (the clean-bill state)
    empty = {
        "title": "The Quiet Kitchen",
        "source_filename": "The Quiet Kitchen.fountain",
        "model_used": "synthetic (clean-bill probe)",
        "findings": [],
        "formatting_findings": [],
        "coverage": {
            "recommendation": "recommend",
            "logline": "A woman and a man circle each other over a stove and a broken alarm, "
                       "saying almost nothing.",
            "genre": "Drama", "tone": "Quiet, wry",
            "strengths": ["The scene turns on what is not said."],
            "weaknesses": [],
        },
        "verification_summary": {"verified": 0, "not_found": 0, "no_quote": 0, "scene_not_found": 0},
        "setup_payoff": [], "character_reads": [], "character_dials": [],
        "logline_test": None, "pacing": [], "stats": {},
    }
    with open(os.path.join(pdir, "report.findings.json"), "w", encoding="utf-8") as f:
        json.dump(empty, f, indent=2)
    with open(os.path.join(pdir, "report.md"), "w", encoding="utf-8") as f:
        f.write("# Script Doctor Report: The Quiet Kitchen\n\n"
                "## Coverage\n**Recommendation: RECOMMEND**\n\n"
                "**Logline:** A woman and a man circle each other over a stove and a broken "
                "alarm, saying almost nothing.\n\n## Findings\n_None._\n")

    from screenplay_studio.manifest import ProjectManifest
    m = ProjectManifest.load(pdir)
    m.mark_complete("parse", {"parsed": os.path.join(pdir, "parsed.json")})
    m.mark_complete("analyze", {
        "report_md": os.path.join(pdir, "report.md"),
        "report_findings": os.path.join(pdir, "report.findings.json"),
        "category_outcomes": {}, "failed_categories": [],
    })
    m.save()
    print("marked analyze complete with 0 findings ->", name)
    print("SHELF_LABEL=" + (m.title or name))


if __name__ == "__main__":
    main()
