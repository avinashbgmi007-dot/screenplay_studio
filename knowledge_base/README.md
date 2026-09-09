# Screenplay Craft Knowledge Base

This is the source of truth referenced in our discussion: an explicit,
structured, attributed set of screenwriting craft principles that every
analysis check pulls its definition from, instead of a model relying on
whatever it happens to remember from training. This is the same fix we
already applied to evidence quotes (verify against real text, don't trust
the model's memory of the script) — applied one level up, to *craft theory*
itself.

## Why this exists

Before this file existed, "on-the-nose dialogue" or "midpoint" were defined
by a one-line paraphrase buried in a prompt string, with everything else
left to whatever the target LLM happened to remember from training. That's
inconsistent across models, unauditable, and impossible to extend
deliberately — we couldn't even say whether Chekhov's Gun was "checked for"
because there was no list to check against. This file is that list.

## Sources

Every rule is attributed to where it actually comes from. This is a
synthesis of major, widely-taught screenwriting/story-structure frameworks,
each described in original wording — not reproduced text from any book.
Primary frameworks drawn on:

- **Aristotle**, *Poetics* (c. 335 BCE) — foundational dramatic principles:
  three-part structure, reversal, recognition, catharsis.
- **Syd Field**, *Screenplay: The Foundations of Screenwriting* (1979) and
  *The Screenwriter's Workbook* (1984/2006) — the "Paradigm": 3-act
  structure with Plot Points, later Pinches and Midpoint.
- **Blake Snyder**, *Save the Cat!* (2005) — the 15-beat structure with
  target page/percentage placements.
- **Christopher Vogler**, *The Writer's Journey* (1992/2007), adapting
  **Joseph Campbell's** *The Hero with a Thousand Faces* (1949) — the
  12-stage Hero's Journey.
- **Robert McKee**, *Story: Substance, Structure, Style, and the
  Principles of Screenwriting* (1997) — controlling idea, the gap between
  expectation and result, scene turns, progressive complications, cast
  polarization, setups/payoffs.
- **Dwight V. Swain**, *Techniques of the Selling Writer* (1965) — scene
  structure (Goal-Conflict-Disaster) and sequel structure
  (Reaction-Dilemma-Decision).
- **Anton Chekhov** (attributed via letters/anecdote, popularized as a
  dramatic-economy principle) — "Chekhov's Gun."
- A small number of entries marked `"source_type": "general_craft"` are
  widely-taught conventions repeated across many of the above (e.g. "enter
  a scene late, leave early") without one single originating source —
  these are labeled as such rather than falsely pinned to one author.

## Schema

Every rule in `rules/*.json` follows this shape:

```json
{
  "id": "chekhovs_gun",
  "name": "Chekhov's Gun",
  "taxonomy_level": "plot_thread",
  "category": "setup_payoff",
  "source": {
    "type": "attributed_principle",
    "originator": "Anton Chekhov",
    "work": null,
    "note": "Popularized via letters/anecdote; standard principle of dramatic economy, not from a single treatise."
  },
  "definition": "Plain-language explanation, in our own words.",
  "detection_signal": "What a check should actually look for — the operational definition, not just the theory.",
  "counter_considerations": "Legitimate exceptions where NOT flagging is correct.",
  "severity_default": "medium",
  "confidence_tier": "high | medium | low",
  "requires": ["knowledge_graph"],
  "related_rules": ["setup_payoff_general"]
}
```

**`confidence_tier` is the important field for honesty.** It states how
mechanically checkable a rule is, independent of how well-established the
theory is:
- `high` — largely mechanical once the right data exists (e.g. "does this
  beat exist within its expected page range" once we know page count).
  Still needs LLM judgment to *identify* which scene fulfills the beat, but
  the check itself is well-defined.
- `medium` — needs real interpretive judgment, but the judgment call is
  narrow and well-specified (e.g. "does this scene's value shift from
  positive to negative or vice versa").
  `low` — genuinely subjective even among human script consultants (e.g.
  "does this controlling idea feel earned"). These should be presented as
  *discussion prompts*, not confident verdicts.

**`requires`** flags whether a rule needs the cross-scene knowledge graph
(props/characters/timeline tracked across scenes — the "Decision 2" build
item) or can run from single-scene / whole-script-summary context alone.

## Files

| File | Taxonomy level | What it covers |
|---|---|---|
| `rules/story_macro.json` | Story/Macro | Controlling idea, genre, theme, world-building, bookending |
| `rules/structure_pacing.json` | Structure/Pacing | Full beat sheets (3-act, Save the Cat 15, Hero's Journey 12), pacing/escalation |
| `rules/plot_thread.json` | Plot Thread | Chekhov's Gun, setups/payoffs, subplot function, causality |
| `rules/character.json` | Character (per-character) | Arc, true character vs. characterization, want vs. need, cast polarization |
| `rules/relationship.json` | Relationship | Antagonist force, dynamic consistency |
| `rules/scene.json` | Scene (per-scene) | Scene turn, Goal-Conflict-Disaster, obligatory scene, necessity |
| `rules/dialogue.json` | Dialogue | On-the-nose/subtext, exposition-as-ammunition |
| `rules/continuity.json` | Continuity (cross-cutting) | Prop/world-rule/trait/timeline consistency |

## How this gets consumed (for the build)

Each analyzer check, instead of hand-writing its own paraphrase of a craft
concept into a prompt, retrieves the relevant rule(s) by `taxonomy_level`
and/or `category` from this file and includes the rule's `definition` and
`detection_signal` verbatim in the prompt sent to the model. This means:

1. The same rule text is used every time that check runs, regardless of
   which local model is loaded — the theory doesn't degrade with model size.
2. Adding a new rule (say, entry #10 in the Principles Engine) means adding
   one JSON entry, not guessing whether a given model "already knows" it.
3. `confidence_tier` flows through to the report — `low`-confidence
   findings get framed as discussion prompts in the report/co-writer, not
   asserted as fact, matching how we already handle unverified quotes.

## Status

This is v1 — a solid, representative set per taxonomy level (not
exhaustive; screenwriting theory has hundreds of named principles across
dozens of schools). Extending it is meant to be cheap: add a JSON entry,
tag it with a taxonomy level and confidence tier, done.
