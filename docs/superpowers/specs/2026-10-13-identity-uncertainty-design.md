# Identity-Uncertainty Flag Design (2026-10-13)

Unhedged identity verdicts over ambiguous text: "Pen Guy is a distinct
entity, not Raj" (trial-10 #12) stated as fact where the script supports
two readings. The deterministic mirror failed thirteen runs the other way
(GUN_GUY is PEN_GUY). Both directions need the same check.

## Decisions (locked in brainstorming)

- Scope: identity assertions in both directions (sameness and distinctness).
- Outcome: flag `identity_uncertain` plus one demotion step. Uncertainty
  is not falsehood — the row stays delivered, question visible, certainty
  stripped.
- Home: pipeline finalize (`apply_identity_check`), beside the observation
  check. The gate has no demote action; the pipeline family owns demote.

## §1 — Trigger and name resolution (approved)

Trigger patterns over issue text binding two capitalized names: `X is Y`,
`X is not Y`, `X is really`, `distinct entit`, `same character`,
`no X present`, `X absent`, `X never appears`, `X does not appear`.
Hedged variants (`appears to be`, `may be`, `possibly`, `reads as`) skip.
Pronouns skip. Single-name rows skip. Names normalize via
`normalize_character_name().upper()` (the continuity lesson: raw cue text
and normalized presence must meet).

## §2 — Evidence ladder (approved)

Over the cited scene range, for the two resolved names:

- Explicit equation in text (a line addressing X as Y, a parenthetical
  `(as Y)`, a renaming heading) matching the verdict: keep, no flag.
- Co-presence with both names carrying dialogue in one cited scene:
  supports distinctness; the sameness case is already skipped upstream.
- Neither signal: indeterminate — flag and demote, quote and observation
  intact.
- Out-of-range refs, missing doc, unresolvable names: unchecked, keep.

## §3 — Verification and non-goals (approved)

- Unit tests per direction, hedged/pronoun/ref-less keeps, quote exemption.
- 19-report backtest before commit: expected fire only on trial-10 #12
  shapes; any solid-scored hit blocks and narrows.
- Non-goals: resolving identities, touching verification, prompt changes,
  pronoun resolution.
