# Absence-Falsification Gate Design (2026-10-12)

Overconfident absolutes stated as fact: "objects do not recur" while the pen
recurs two scenes later (trial-10 #4). The checkable subset is absence
claims falsifiable by presence in the parsed document.

## Decisions (locked in brainstorming)

- Scope: falsifiable absolutes only. Identity ambiguity (Raj vs Pen Guy)
  stays out — it needs judgment, not lookup.
- Outcome: withdraw to the integrity-gate ledger (false is false; the
  withdrawals ledger already solves visibility).
- Coverage: all three absence shapes (non-recurrence, missing lines,
  missing beats) sharing one presence check.

## §1 — Detection and check mechanics (approved)

Three claim shapes, each a narrow regex over issue text, each paired with
one presence check against the parsed doc:

1. Non-recurrence (`do not recur`, `never referenced/mentioned/seen
   again`, `never reappears`): content terms from the named object via the
   adjudicator's `_content_terms` (same "short setup string to terms"
   problem, same stopwords — no second tokenizer), checked with
   `_terms_in_scenes` over scenes after the setup range. Positive match
   withdraws.
2. Missing lines (`no dialogue (lines) for X`, `X never speaks`, `no
   action lines for X`): X resolved against speaker cues and action
   attributions in range. Fully deterministic, no fuzzy matching.
3. Missing beats (`no confrontation`, `never addressed`, `absent from`):
   term search for the beat's content words in range.

All three fire only on positive proof of presence. Reads issue plus
observation; quotes never scanned.

## §2 — Safety rails, placement, ledger (approved)

- Hedged phrasing (`appears`, `seems`, `may`, `arguably`, `suggests`) or a
  contrast turn vetoes the check. A careful model is never punished.
- Full content-term set must land (verifier's 0.72 fuzzy / 0.5 overlap
  floors), not one shared word.
- Scene ranges come from the finding's own `scene_refs`; no refs means
  unchecked, and refs outside the document (trial-11 #28 cites sc[16] on
  an 11-scene doc) also mean unchecked — never clamp, never guess.
  Pronoun subjects (`he never speaks`) are unchecked —
  no coreference machinery exists, and guessing is forbidden.
- Speaker lookup inherits parser error, in the safe direction only:
  parsers miss cues but do not invent them, so a missed cue keeps the row
  while only a hallucinated cue could wrongly withdraw. No mitigation
  needed beyond this asymmetry, recorded here so the next reader does not
  re-litigate it.
- Merge runs before checking: a duplicate absorbed into a keeper is not
  examined separately; the keeper is judged on its own text alone. An
  absorbed falsehood therefore survives if and only if the keeper's own
  text passes — accepted edge, rarity over machinery.
- New gate method beside `_inverted`, action `reject`, reason `absence
  claim falsified by presence in scene(s) N`. No prompt, grammar, report,
  or UI changes.

## §3 — Verification and non-goals (approved)

- Unit tests per shape (fires on the trial-10 #4 shape), conservative
  siblings (hedged, pronoun-subject, ref-less kept), quote exemption.
- 19-report backtest before commit: expected fire only on #4-shaped rows;
  any solid-scored hit blocks and narrows the regexes.
- Non-goals: identity ambiguity, tone policing, invented ranges, pronoun
  resolution, touching verification status.
