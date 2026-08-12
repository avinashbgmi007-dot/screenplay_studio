"""
Genre-convention check — evaluates how well a script delivers on the genre's
audience expectations, and where it deliberately (or accidentally) diverges.

The conventions below are deliberately written as *expectations to test*,
not rules to obey: a great script can violate any of them on purpose. The
model's job is to say whether the script delivers, and whether a miss reads
as a choice or an accident.

This is a model-dependent category that runs AFTER coverage, using the genre
coverage reported — no separate user input needed.
"""

GENRE_CONVENTIONS = {
    "thriller": [
        "A credible, escalating threat with real stakes appears early and tightens through the second act",
        "The protagonist is active (investigating, running, deciding), not just reacting",
        "Timeliness pressure: a ticking clock, deadline, or countdown the audience can feel",
        "Reveals are earned: information the audience learns recontextualizes earlier scenes",
        "The antagonist or threat stays plausibly competent; cheap fake-outs are avoided",
    ],
    "horror": [
        "The threat is established early, but its rules are revealed gradually, not explained away",
        "Isolation or vulnerability is engineered so the characters cannot simply leave/call for help",
        "Scares escalate in novelty rather than repeating the same beat",
        "The final act answers the threat's rules coherently (whether it's defeated or not)",
        "The monster/threat has a logic the audience can infer from evidence shown, not a deus ex machina",
    ],
    "romance": [
        "The two leads have chemistry *in scenes together* — obstacles are external or internal, not just miscommunication",
        "The lovers' wants conflict meaningfully before they converge",
        "The midpoint reunion/argument is earned by earlier friction, not contrived",
        "The ending resolves why these two belong together specifically, not generically",
    ],
    "drama": [
        "The central conflict tests the protagonist's values, not just their goals",
        "Characters' wants change or deepen over the course of the script",
        "Emotional beats are dramatized in scenes, not narrated in dialogue",
        "The stakes are personal and specific, felt through concrete scenes",
    ],
    "comedy": [
        "Jokes/beats escalate — the same setup pays off differently each time",
        "The comedy serves character (we laugh with, not just at)",
        "The premise's comedic engine (the mismatch) is exploited throughout, not abandoned after act 1",
        "Straight men/foils exist so the comedy has something to play against",
    ],
    "action": [
        "Action set pieces escalate in scale or inventiveness, and each advances the story",
        "The protagonist's physical competence is established before the big set pieces",
        "Stakes are concrete and time-pressured; the audience always knows what the hero is trying to achieve",
        "The villain's plan must be stopped *by* the action, not in spite of it",
    ],
    "sci-fi": [
        "The speculative element has rules the story respects (no convenient tech fixes)",
        "The concept is explored through the plot and characters, not just explained in dialogue",
        "The futuristic setting raises a theme the story actually engages",
        "The world's rules are established early enough that later reveals feel earned",
    ],
    "western": [
        "The landscape/community exerts pressure on the story (isolation, justice, resources)",
        "The protagonist's code of conduct is tested and costs something to maintain",
        "Justice is local and personal — the law is distant or corrupt",
        "The climax resolves the central moral conflict, not just the plot",
    ],
    "fantasy": [
        "The magic/world rules are introduced through action, not exposition dumps",
        "The fantastic elements have costs or limits that create story pressure",
        "The chosen-one/prophecy tropes, if used, are interrogated rather than just adopted",
        "The worldbuilding serves the emotional story, not the other way around",
    ],
    "mystery": [
        "Clues are planted fairly — the solution is inferable from evidence shown",
        "The detective/protagonist uses a discernible method rather than luck",
        "Red herrings are purposeful and pay off as misdirection",
        "The solution recontextualizes earlier scenes rather than arriving from nowhere",
    ],
}

DEFAULT_GENRE = "drama"


def conventions_for(genre: str) -> list[str]:
    """Best-effort genre match: exact key, then substring/word overlap."""
    if not genre:
        return GENRE_CONVENTIONS.get(DEFAULT_GENRE)
    g = genre.strip().lower()
    if g in GENRE_CONVENTIONS:
        return GENRE_CONVENTIONS[g]
    for key, conv in GENRE_CONVENTIONS.items():
        if key in g:
            return conv
    # word-level fallback
    words = set(g.split())
    best, best_score = None, 0
    for key, conv in GENRE_CONVENTIONS.items():
        overlap = len(set(key.split()) & words)
        if overlap > best_score:
            best, best_score = conv, overlap
    return best or GENRE_CONVENTIONS.get(DEFAULT_GENRE)


def run_genre_check(coverage: dict, scene_overview: str, client, rules_ctx=None, language: str = "eng") -> list[dict]:
    """Evaluate the script against its genre's conventions. Returns findings
    with category 'genre'. Raises if the model server fails."""
    from .grammar import findings_grammar
    from .prompts import genre_check_prompt

    genre = (coverage or {}).get("genre") or ""
    conventions = conventions_for(genre)
    system, user = genre_check_prompt(genre, conventions, scene_overview, language=language)
    result = client.chat_json(system, user, grammar=findings_grammar(), max_tokens=1200)
    # tolerate models that emit the findings as a bare JSON array
    if isinstance(result, list):
        return result
    return result.get("findings", []) if isinstance(result, dict) else []
