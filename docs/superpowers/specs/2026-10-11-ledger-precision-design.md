# Ledger Precision — Design

Date: 2026-10-11. Branch: `feature/post-analysis-ia`. Status: approved as presented, awaiting spec review.

## Context and evidence

Two-script trial (gun_pen, Pain_3, qwen3.6-35b): ledger verdicts score ~2 solid
of 16 entries. Failure mode is one-sided: threads the pages resolve are called
dangling/abandoned (comic burn pays via sc20 tear + sc22 wave; debts collect
in sc22; tea test IS the proof scene; X-company resolves into the job move).
Fold-in findings (`dangling_findings`, `setup_payoff.py:112`) carry no quote by
construction, so the evidence floor demotes all of them to low. Scope is
ledger-only; the Principles Engine is untouched by explicit decision.

Targets: every kept verdict mechanically checked; true rows grounded with
quotes; no new model calls; golden ledger facts (comic, debt, tea, job,
countdown) flip to correct on re-run.

Non-goals: Principles Engine verdicts, paid-to-dangling flips on absence,
UI surfacing of new fields, new model calls.

## D1. Verdict adjudication, asymmetric

After `run_setup_payoff_ledger` returns, before `dangling_findings` folds rows
in (`setup_payoff.py`). "Setup terms" throughout means stopword-filtered
content words of the entry's `setup` string (the `_token_overlap` convention).
For each entry, using the verifier's tested primitives
(`quotematch` normalize + windowed similarity, token overlap from D2's
`verifier._token_overlap`):
- Setup terms must appear in `setup_scenes`; else mark `setup_ungrounded`.
- Paid entries: terms must recur in `payoff_scenes`; else mark
  `payoff_unproven` and keep paid.
- Dangling/abandoned entries: search scenes after the setup for the terms;
  on a hit flip to paid with a `verified` note naming scenes, on a miss keep
  the model verdict untouched.
Asymmetry is load-bearing: recurrence proves payoff, absence proves nothing
(visual payoffs exist), so the checker exonerates but never convicts. It
cannot invent a failure by construction.

## D2. Setup-quote extraction

For each kept entry, extract the best-matching line from its setup scenes via
the existing windowed matcher and store it as `setup_quote`. `dangling_findings`
carries it as the finding's `evidence_quote`. True ledger rows leave the
ungrounded bucket with real severity instead of demoting to low en masse.

## D3. Ledger fields

Entries gain `verified: true/false` plus `verify_note` (what checked, with
scene numbers). Served in report JSON; the desk ignores them until a surface
wants them. No severity changes in this design; grading stays with the
existing cited rule.

## D4. Tests and acceptance

Pin tests with synthetic docs per verdict path (paid-kept, dangling-flipped,
dangling-kept, setup-marked, quote-landed), repo pin-test style. Acceptance:
golden ledger facts correct on both trial scripts on re-run, zero
high-severity ungrounded ledger rows.
