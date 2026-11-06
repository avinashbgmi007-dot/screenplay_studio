"""
Pacing — deterministic per-scene pace index. No model calls.

The writer asked for a visual of *where the script slows down*, with scene
numbers on it. A model-judged tension curve is one way; a deterministic,
reproducible pace index is the better first cut — consistent on every run,
explainable, and it never contradicts the pages.

The proxy: a scene may be slow when it is long in words but low in the text
this pass can measure as movement. Two signals:

  - density   — words per beat (beat = one action or dialogue element).
  - action_share — shared action words / shared total words. High = movement
                on the page; low = talking heads.

Gap 45. These are COUNTS. They are not dramatic movement and not audience
reception, and the earlier version of this module described the result as if
they were: it called a scene "meanders where the story needs to move" and
returned identical scores (100.0, 100.0, 100.0) for three scenes whose only
difference from each other was the words inside them. Three things were wrong
and are fixed here:

  1. Character cues were counted as action. The old loop was `if DIALOGUE ...
     else action += words`, so every cue, every transition and every parenthetical
     landed in "action words" — 11% of a dialogue-only scene was reported as
     on-page movement that consisted entirely of the name MIRA and the slug line.
  2. pace_score was a rank, and a self-contradicting one. Density and action
     share were min-max normalised across the script, so the slowest scene
     always scored near 100 and the fastest always 0 no matter what either
     contained; three identical scenes all scored exactly 100.0. Worse, the two
     terms measured different things and pulled opposite ways — density is words
     per element, so a long action paragraph outranked a talky scene as
     "draggier", and the 0.6/0.4 weights decided the verdict. Both terms are now
     absolute and point the same way: length against a fixed SLOW_SCENE_WORDS,
     and the dialogue share of prose words. Scores compare across scripts, and
     `pace_rank` (competition-ranked, ties shared) is available for ordering
     without being mistaken for an amount.
  3. The finding asserted a creative diagnosis. It now states the measurable
     signal and marks itself an observation.

Unmeasurable text is excluded rather than guessed at: a script whose words are
mostly non-Latin is reported as not measurable by this pass instead of being
scored on a share that does not mean anything.
"""

from __future__ import annotations

from screenplay_parser.models import ScriptDocument, ElementType

# pace_score >= this (out of 100) flags a scene as a pace drag
DRAG_THRESHOLD = 68.0
# never flag more than this many scenes
MAX_DRAGS = 4

# Gap 45: these elements are formatted text rather than prose — a cue is a NAME,
# a heading is a slug line, a transition is "CUT TO:". The old code counted them
# as action words, which turned a dialogue-only scene into 11% "movement".
_NON_PROSE_TYPES = frozenset({
    ElementType.CHARACTER, ElementType.SCENE_HEADING, ElementType.TRANSITION,
    ElementType.PARENTHETICAL,
})

# Below this share of Latin words the action/dialogue split is not measurable by
# this pass: a Telugu or Hindi script parses fine but its "words" do not split
# the way these counts assume.
MIN_LATIN_SHARE = 0.5

# Gap 45: a fixed reference length, so "long" means the same thing in every
# script. A scene of this many words scores full marks on the length term.
SLOW_SCENE_WORDS = 200
LENGTH_WEIGHT = 0.6
TALK_WEIGHT = 0.4


def per_scene_pace(doc: ScriptDocument) -> list[dict]:
    rows = []
    for scene in doc.scenes:
        total = action = dialogue = beats = latin = 0
        for el in scene.elements:
            words = len(el.text.split())
            if not words:
                continue
            total += words
            beats += 1
            latin += sum(1 for w in el.text.split() if _is_latin_word(w))
            if el.type in _NON_PROSE_TYPES:
                # Counted towards the scene's size and its beat count, but not
                # towards "movement": a cue is not an action line.
                continue
            if el.type == ElementType.DIALOGUE:
                dialogue += words
            else:
                action += words
        shared = action + dialogue
        rows.append({
            "scene_number": scene.scene_number,
            "words": total,
            "action_words": action,
            "dialogue_words": dialogue,
            "beats": beats,
            "latin_share": round(latin / max(1, total), 3),
            "density": round(total / max(1, beats), 1),       # words per beat
            "action_share": round(action / max(1, shared), 3) if shared else None,
            "pace_score": 0,
            "drag": False,
        })

    if not rows:
        return rows

    # Gap 45, second defect. The old score was min-max normalised inside the
    # script: three identical all-dialogue scenes each scored exactly 100.0, a
    # uniformly slow script scored 0.0 everywhere, and — worst — the two terms
    # fought each other. `density` is words per ELEMENT, and a 40-word action
    # paragraph is one element (density 40) while a 16-word speech is also one
    # element (density 16), so the all-action scene ranked as the DRAGGIER of
    # the two on 0.6 of the weight while `action_share` ranked it the opposite
    # way on 0.4. The score was decided by the weights, not by the script.
    #
    # Both terms are now absolute, and both point the same way:
    #   length      — scene words against a fixed SLOW_SCENE_WORDS, not against
    #                 the script's own maximum. Long is long in any script.
    #   talk_share  — dialogue share of the prose words. 0..1, no normalisation.
    # Scores are therefore comparable BETWEEN scripts and identical scenes tie
    # exactly. A uniformly slow script scores high everywhere, which is the
    # truth about it.
    for r in rows:
        if r["action_share"] is None:
            r["pace_score"] = None
            r["pace_rank"] = None
            continue
        talk_share = 1.0 - r["action_share"]
        length = min(1.0, r["words"] / float(SLOW_SCENE_WORDS))
        r["pace_score"] = round(100 * (LENGTH_WEIGHT * length
                                       + TALK_WEIGHT * talk_share), 1)

    scored = [r for r in rows if r["pace_score"] is not None]
    # competition ranking: equal scores share a position
    for r in scored:
        r["pace_rank"] = 1 + sum(1 for o in scored if o["pace_score"] > r["pace_score"])

    # flag the slowest of the long, talky scenes, respecting the cap
    ordered = sorted(scored, key=lambda r: -r["pace_score"])
    for r in ordered[:MAX_DRAGS]:
        if r["pace_score"] >= DRAG_THRESHOLD and r["words"] >= 20:
            r["drag"] = True
    return rows


def drag_findings(rows: list[dict]) -> list[dict]:
    """The slowest scenes, as OBSERVATIONS about text this pass can count.

    Gap 45. The old finding said a scene "meanders where the story needs to
    move" and told the writer to give it "a real event". Nothing in these counts
    can establish that: they are word counts per element and a share of the
    words that are action rather than dialogue. A dialogue-driven climax, a
    deliberate silence, or a scene whose tension is entirely verbal all read as
    "low movement" to this pass, and all three may be the best writing in the
    script. The finding now states the measurable signal, calls itself an
    observation, and leaves the judgement where it belongs.
    """
    findings = []
    for r in rows:
        if not r["drag"]:
            continue
        share = round(100 * r["action_share"]) if r["action_share"] is not None else 0
        findings.append({
            "category": "structure",
            # `check_id`, not `rule_id`: the pace index is a mechanical measure
            # with no knowledge-base rule behind it. `rule_id` is reserved for
            # ids that resolve in the KB (the UI renders it as "Grounded in
            # knowledge-base rule <id>"), so a non-KB id there is a false claim.
            "check_id": "pacing_drag",
            # "the slowest of N by counted words" is a fact about this pass's
            # own numbers. "runs long with little movement" was a claim about the
            # writing, and the pass cannot support it.
            "issue": (
                f"Slowest scene by counted words — Scene {r['scene_number']} "
                f"(rank {r.get('pace_rank')} of {len([x for x in rows if x['pace_score'] is not None])})"
            ),
            "why_it_matters": (
                f"{r['words']} words across {r['beats']} beats "
                f"({r['density']} words per beat), of which {share}% are action "
                "rather than dialogue. That is a shape, not a verdict: a talking "
                "scene can be the tensest one in the script, and a long action "
                "passage can be the dullest. Worth reading this scene against its "
                "neighbours — if it is doing its work, this is not a note."
            ),
            "severity": "low",
            "scene_refs": [r["scene_number"]],
            "evidence_quote": None,
            "is_observation": True,
            "confidence": "observation",
        })
    return findings


def is_measurable(doc: ScriptDocument) -> bool:
    """Whether this pass's word-share arithmetic means anything for this script.

    The counts assume Latin-script words. A Telugu or Devanagari script parses
    correctly and then this pass reports an action share computed from a word
    split that does not reflect how those lines are written. Saying "not
    measurable" is honest; scoring it anyway is not.
    """
    words = latin = 0
    for scene in doc.scenes:
        for el in scene.elements:
            if el.type in _NON_PROSE_TYPES:
                continue
            for w in (el.text or "").split():
                words += 1
                if _is_latin_word(w):
                    latin += 1
    return words == 0 or (latin / words) >= MIN_LATIN_SHARE


def _is_latin_word(word: str) -> bool:
    letters = [c for c in word if c.isalpha()]
    return bool(letters) and all(ord(max(c, key=ord)) < 0x0250 for c in letters)
