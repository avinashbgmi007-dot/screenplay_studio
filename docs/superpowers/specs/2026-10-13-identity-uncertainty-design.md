# Identity-Uncertainty Flag Design (2026-10-13)

Unhedged identity verdicts over ambiguous text. Motivating row
(trial-10 #12, character/high, sc[1,2,3]): issue "Protagonist Identity
Ambiguity: Raj's role in the central conflict (Scene 2) is unclear
because he does not appear to be the 'Pen Guy'." with observation "...
the character labeled 'PEN_GUY' ... is a distinct entity not named
Raj." The verdict ("distinct entity") lives in the observation, not the
issue — so patterns scan both. The deterministic mirror failed thirteen
runs the other way (GUN_GUY is PEN_GUY). Both directions need the same
check.

## Decisions (locked in brainstorming)

- Scope: identity assertions in both directions (sameness and distinctness).
- Outcome: flag `identity_uncertain` plus one demotion step. Uncertainty
  is not falsehood — the row stays delivered, question visible, certainty
  stripped.
- Home: pipeline finalize (`apply_identity_check`), beside the observation
  check. The gate has no demote action; the pipeline family owns demote.

## §1 — Trigger and name resolution (approved)

Trigger patterns over issue PLUS observation combined (the verdict
often lives in the observation — see motivating row above; Law V" calls
the observation the falsifiable claim for exactly this reason), binding
two capitalized names: `X is Y`, `X is not Y`, `X is really`,
`distinct entit`, `same character`, `no X present`, `X absent`,
`X never appears`, `X does not appear`, `does not appear to be`.
Hedged variants (`appears to be`, `may be`, `possibly`, `reads as`) skip.
Fewer than two capitalized names in the combined text skips (pronoun-only
subjects like `he never speaks` carry nothing to resolve).
Single-name rows skip. Names normalize via
`normalize_character_name().upper()` (the continuity lesson: raw cue text
and normalized presence must meet).

## §2 — Evidence ladder (approved)

Over the cited scene range, for the two resolved names:

- Explicit equation in text matching the verdict: keep, no flag.
  Equation is element-defined: a DIALOGUE element whose `character` is X
  and whose text names Y; or an ACTION element matching
  `X (calls|addresses|greets|names) ... Y` or a parenthetical `(as Y)`
  attached to X's cue or line; or a heading containing both names in an
  `X=Y`/`X-AS-Y` form. Anything vaguer does not count — guessed equations
  are how this check would invent certainty.
- An equation CONTRADICTING the verdict (claim "X is not Y" beside text
  addressing X as Y): not a demote — route to the integrity gate as a
  proven falsehood (same ledger, `reject`), since the text settles it.
- Co-presence with both names carrying dialogue in one cited scene:
  supports distinctness; the sameness case is already skipped upstream.
- Neither signal: indeterminate — flag and demote, quote and observation
  intact.
- Out-of-range refs, missing doc, unresolvable names: unchecked, keep.
- Display ships with the flag: a new `identity_uncertain` chip plus title
  in Fix Queue rows beside the contested/ungrounded flags (`app.js`
  rowFlags area), and in deep-card flag space. A demotion with no visible
  reason reads as an unexplained downgrade.
- Ordering: gate 8d runs before finalize, so a gate withdrawal wins ties;
  a row the gate removes is never flag-checked. Stated so no implementer
  re-derives it.

## §3 — Verification and non-goals (approved)

- Unit tests per direction, hedged/pronoun/ref-less keeps, quote exemption.
- 19-report backtest before commit: expected fire only on trial-10 #12
  shapes; any solid-scored hit blocks and narrows. Caution carried from
  review: nine trigger patterns generalize from essentially one observed
  row — the two-name requirement does most of the safety work, and the
  backtest measures the rest. If it fires wide, narrow patterns first,
  never the evidence bar.
- Non-goals: resolving identities, touching verification, prompt changes,
  pronoun resolution.
