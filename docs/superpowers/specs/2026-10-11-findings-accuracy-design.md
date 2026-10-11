# Findings Accuracy to 90%+ Grounded — Design (A: guardrails, B: recall)

Date: 2026-10-11. Branch: `feature/post-analysis-ia`. Status: approved per-section, awaiting spec review.

## Context and evidence

Two-script live trial on qwen3.6-35b (gun_pen.pdf: 6pp/3sc, Pain_3_updated_FULL.pdf: 28pp/22sc):
gunpen 18/29 solid (62%), pain3 34/75 solid (~45%), 5 unconfirmed. Mechanical output
already clears the bar (continuity 3/3, quote verification 96-100%, zero duplicates,
all scenes covered, zero errors). The gap is interpretive findings without evidence
(16 with neither quote nor observation), missed mechanics (dream reveal, countdown
denial), feature-length templates on shorts, Telugu-as-untranslated bias, refuting
observations delivered anyway (#43, #57 pattern), absence filings ("N/A"), and
template pileups (10x "protagonist lacks X").

Targets: 90%+ grounded (every delivered finding carries quote or observation) while
mechanical stays 100%; golden recall sets measured per run, target recorded not
asserted. 95% across ALL findings is explicitly out of scope: human readers disagree
20-30% on interpretive notes, so the bar is 90%+ grounded + 100% mechanical.

Non-goals: genre-specific findings, revision pass, synopsis render, reads/dials in
the queue (coverage-completion kit C, separate spec). No finding is ever deleted by
these changes (flag-don't-drop holds throughout).

## Design A — delivery guardrails

### A1. Evidence floor (`report.py::to_findings_json`, desk queue filter)

A finding with neither `evidence_quote` nor `observation` gets severity forced to
low plus `ungrounded:true`. The desk Fix Queue default view filters `ungrounded`
out (same `queueCounts`/`findingCounts` path in `app.js`, counts stay honest by
reading the same filtered set). JSON keeps the row; markdown gains an
"Ungrounded notes" section. Rationale: the trial's worst cluster (9 scene_function
one-liners, 7 ledger claims) shares exactly this shape.

### A2. Refutation adjudication

When an observation rebuts its note (v1: contradiction markers — however, no
evidence, contradicts, admits — over the note/observation pair, the exact shape
trial items #43/#57 exhibit), mark `contested:true` and demote one severity step.
Keep visible. A model-judge upgrade is future work, noted here to avoid scope creep
and new cost/failure modes in v1.

### A3. Short-form mode (deterministic, no model cost)

`estimated_page_count` < 15 skips framework findings that demand acts, midpoint, or
climax, by enumerated check ids (the gunpen structure/genre misfires). Craft-level
findings continue. Threshold lives in one named constant next to the gate.

### A4. Language consistency

If the script's non-English share is consistent across scenes (Tenglish throughout,
as in both trial scripts — reuse the language profiling behind `report_language` /
`language_meta`), suppress "untranslated barrier" findings. Flag only a line whose
language breaks the script's own pattern, stating the pattern. Kills the 4-finding
bias cluster without touching genuine code-switch observations.

### A5. Absence ban plus caps

Silent scenes are skipped, never filed (kills "N/A" and silence-as-defect). Cap
findings per (category, size bucket) with distinct scene anchors required (kills
the 10x template pileup). Caps sized from trial data, stated in-code.

### A-Tests

Pin-style tests per rule (repo convention: `test_chunk_recovery_visibility.py`
shape), plus a re-run over both trial reports asserting zero high-severity
ungrounded findings and no previously-solid finding demoted.

## Design B — recall architecture

### B1. Full-text shorts

Scripts fitting the context budget run script-level passes on full parsed text,
not summaries. Bounded to small scripts, where the summary telephone game hurts
most (the dream reveal died in one action line).

### B2. Reveal retrieval

Deterministic pre-pass scans for reveal mechanics (dream/wake/kalaa/dreamt,
death-that-unhappens, narrator-lie markers), injects candidate reveals into
script-level context, and adds one check: do any findings contradict the reveal?
Acceptance case is the gunpen dream and its 4 poisoned downstream findings.

### B3. Golden recall sets

Checked-in fact lists, 5 per trial script from the audit (gunpen: dream, countdown,
tea-proof rhyme, three-names, wrist-letter; pain3: debt payoff, comic payoff,
deadline outcome, job resolution, silence facts). Measured by a local eval script
in the `gun_pen_audit` style — real model required, so NOT CI-blocking. Hit rate
reported per run; no blind target asserted.

## Rollout and risks

A first (mechanical, test-pinned), then B (model-cost on small scripts only).
Risk 1: A1 hides findings a writer would want — mitigated by filter-not-delete plus
the Ungrounded section. Risk 2: golden sets overfit two scripts — mitigated by
drawing facts across categories and both scripts, and by reporting (not gating)
hit rate. Risk 3: B1 cost on mid-size scripts — mitigated by the budget gate.
Open question for review: exact short-form page threshold (15 proposed) and
per-bucket caps (sized in implementation plan from trial counts).
