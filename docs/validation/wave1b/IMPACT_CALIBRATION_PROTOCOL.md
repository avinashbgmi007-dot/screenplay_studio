# IMPACT calibration protocol — blinded ranking comparison

**Status:** blank protocol. No real findings or writer judgments have been
collected. This does not change the v0 IMPACT table.

## Purpose and boundary

Test whether the shipped within-lane ranking reflects a writer's rewrite
priority. This is a judgment about **priority**, not about whether a finding is
diagnostically correct. Collect the two judgments separately:

1. **Diagnosis check:** is the issue supported by the cited page?
2. **Priority check:** assuming the issue is real, what would you rewrite first?

A finding that fails the diagnosis check is recorded as an analyzer issue and
is excluded from priority metrics. Do not let a compelling but false finding
raise or lower a weight.

The rendered lane order is currently **descending max IMPACT**, with a
lane-name tiebreak (`laneOrder()` in `core.js`), not a fixed Structure-first
declaration. The spec's Structure-first hypothesis is a separate open product
question. This packet records cross-lane preference as an observation; it does
not change lane order or infer a new order from a proposed weight table.

## Frozen inputs

- One real, full-length screenplay and its completed real-model analysis. No
  demo-model output and no synthetic fixture.
- The application revision used to produce the queue projection. Record it.
  This packet's Wave 1A baseline is `5dd0baa`.
- The queue projection from that revision, with the default filter state:
  all three severities admitted, no deferred/addressed rows, no scene filter,
  ungrounded rows hidden.
- A local-only workspace. Do not upload the report or writer's judgments.

## Population and sampling

The population is the **default Tier 1 worklist**: findings the shipped queue
would show as actionable. Observations are excluded by the product's own rule
(`theme`, `genre`, and scene-less non-mechanical findings are not tasks).
Duplicate content IDs are collapsed to one row and the collapse is recorded.

Sampling rules:

- **Minimum:** 12 unique admitted findings, spanning at least two populated
  lanes and at least three categories. If the report cannot supply that, stop:
  the sample is too small to compare, and adding fixtures would fake coverage.
- **Target:** 16 findings. **Ceiling:** 20, to keep a full ordering feasible in
  one sitting.
- If the population is at or below the ceiling, take all of it.
- If it is larger, use stratified random sampling by lane and category:
  allocate proportionally, take at least two per populated stratum, take all
  when a stratum has fewer than two, and record the seed and the full selection
  table.
- Primary sample uses the default queue. A secondary ungrounded sample requires
  separate owner approval and is reported separately; it is never mixed into
  the primary result.
- Do not select only the top-ranked rows. That would make the comparison
  circular.

## Blinding

The writer sees the content needed to judge the finding, not the product's
answer about it:

**Show:** scene number(s), evidence quote, issue, why it matters, observation,
and any neutral proposed action text.

**Hide:** category label, lane, severity, verification status/confidence, rank
score, rank reason, current queue position, and writer marks.

Assign a random `blind_id` and a random presentation order. Keep the mapping in
an analyst-only manifest; never show that manifest to the writer. The writer
may reorder the cards freely. Record the starting order and the final order.

## Procedure

### 1. Diagnosis pass

For every sampled finding, before discussing priority, the writer marks:

- **supported** — the quote/page supports the issue;
- **not supported** — the issue is contradicted or the evidence does not carry
  it;
- **can't tell** — the page is insufficient to judge.

Record a one-line reason for `not supported` and `can't tell`. This judgment is
about diagnosis only. Do not ask "would you fix it?" yet.

### 2. Priority pass

Give the writer only the `supported` (and, if the owner chooses to retain them,
`can't tell`) findings. Ask:

> "Assuming this issue is real, put these in the order you would rewrite them,
> first to last. If two are genuinely tied, keep them in one tie group."

Require a strict order where possible. Do not show the product's rank, lane or
category. Record the final order, tie groups, and time taken.

### 3. Explanation probe

Ask the writer to explain:

- why their first three are first;
- one adjacent pair they hesitated over;
- after unblinding only at the end, whether they can say why the product put a
  given row above the next one.

The last answer tests whether the rank-reason string is understandable; it is
not a vote on the weights.

### 4. Unblind and join

Only after the writer has finished, join `blind_id` to the analyst manifest.
Compute the model's within-lane order from the same projection. Do not edit the
writer's order after seeing the model's.

## Measures

Report these separately:

- **Diagnosis rate:** supported / all, plus counts for `not supported` and
  `can't tell`.
- **Within-lane concordance:** for each lane, pairwise agreement between the
  writer's order and the model's order:
  `(concordant pairs + 0.5 × tied pairs) / comparable pairs`.
- **Top-three overlap:** number of the writer's top three that are also the
  model's top three, per lane where the lane has at least three rows.
- **Rank-reason comprehension:** can the writer explain the product's adjacent
  pair? yes / no / partial, with their words.
- **Cross-lane preference (secondary):** the writer's overall first choices by
  lane, compared with the rendered lane order. Report observed agreement only;
  do not describe the rendered order as a declared rule or a weight result.
- **Session cost:** time to order, and any fatigue/confusion note.

Do not combine diagnosis accuracy and priority concordance into one score.

## Decision criteria

This packet is evidence, not an automatic retune. A single writer sitting is
**exploratory** and cannot replace the v0 table.

A decision-grade result requires at least three independent writers and two
real screenplays, with at least one working rewriter among the participants.
If that is not met, report the result as exploratory and keep v0.

A candidate weight change may be proposed only if all hold:

1. Mean within-lane concordance improves by at least **0.10 absolute** over
   v0.
2. No populated lane drops by more than **0.05 absolute**.
3. Top-three overlap does not get worse in any lane.
4. The verified-at-equal-impact rule still holds; no safety invariant is
   traded for agreement.
5. The writer can explain the product's adjacent-pair order at least partially;
   an order nobody can explain is not calibrated, even if it matches.

If the criteria are not met, retain v0 and its visible "uncalibrated" marking.
If they are met, the weight change is a **separate implementation task** with
its own tests and UI copy. Do not change weights or the `0.72` quote threshold
inside this packet.

## Stop rules

Stop and record why if:

- fewer than 12 admitted findings are available;
- the report is from the demo model or its provenance is unknown;
- the writer sees the product's rank/category before finishing;
- the writer cannot complete the ordering without fatigue;
- the sample was padded with synthetic or duplicate material;
- diagnosis and priority judgments were mixed.

## Artifacts

- `impact_case_manifest.csv` — analyst-only mapping and sampling metadata.
- `impact_blind_set.csv` — writer-facing content only; no category, severity,
  verification, rank or lane.
- The writer's diagnosis rows and final order, stored locally.
- `analysis.md` — measures, decision, and explicit limits.

Templates are blank; do not add example findings or example judgments.
