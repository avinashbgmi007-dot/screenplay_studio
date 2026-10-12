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
   again`, `never reappears`): content terms from the named object, checked
   with the adjudicator's term-recurrence (`_terms_in_scenes`) over scenes
   after the setup range. Positive match withdraws.
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
  unchecked. Pronoun subjects (`he never speaks`) are unchecked —
  no coreference machinery exists, and guessing is forbidden.
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
