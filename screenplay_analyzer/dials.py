"""
Character dials — per-character trait scores, ScreenplayIQ-style.

For each main character (by scene presence + dialogue share), the model
scores five fixed trait poles on a 1-10 scale, citing the scenes where the
trait actually shows. Diagnosis only — a dial is a *read*, not a verdict:
the writer adjusts the story, never argues with the dial.

Evidence is scene numbers (the pass reasons from the scene overview, the
same summary-based citation contract as theme/character/structure — no
invented verbatim quotes). One model call for the whole cast, capped so a
crowded script stays bounded.
"""

from __future__ import annotations

from . import prompts
from .grammar import character_dials_grammar
from .deterministic_utils import int_list

# trait name -> (left pole, right pole); score 1 = left, 10 = right
TRAITS = [
    ("Proactive vs Passive", "proactive", "passive"),
    ("Warm vs Cold", "warm", "cold"),
    ("Articulate vs Terse", "articulate", "terse"),
    ("Emotional vs Stoic", "emotional", "stoic"),
    ("Grounded vs Dreamy", "grounded", "dreamy"),
]

MAX_DIAL_CHARACTERS = 8


def run_character_dials(doc, overview: str, client, characters: list[str], language: str = "eng") -> list[dict]:
    """Returns [{character, traits: [{trait, score, scene_refs, note}]}]."""
    cast = [c for c in characters if c][:MAX_DIAL_CHARACTERS]
    if not cast or not overview:
        return []
    title = doc.title if doc is not None else ""
    system, user = prompts.character_dials_prompt(overview, title, cast, language=language)
    try:
        data = client.chat_json(
            system, user,
            grammar=character_dials_grammar(),
            max_tokens=1800,
            temperature=0.3,
        )
    except Exception:
        raise
    if not isinstance(data, dict):
        return []
    out = []
    for entry in data.get("dials") or []:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("character") or "").strip()
        if not name:
            continue
        traits = []
        for t in entry.get("traits") or []:
            if not isinstance(t, dict):
                continue
            trait = (t.get("trait") or "").strip()
            if not trait:
                continue
            try:
                score = int(t.get("score"))
            except (TypeError, ValueError):
                continue
            score = max(1, min(10, score))
            traits.append({
                "trait": trait,
                "score": score,
                "scene_refs": int_list(t.get("scene_refs")),
                "note": (t.get("note") or "").strip()[:200],
            })
        if traits:
            out.append({"character": name, "traits": traits})
    return out
