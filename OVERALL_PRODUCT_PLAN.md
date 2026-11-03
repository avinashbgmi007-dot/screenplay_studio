# Screenplay Studio — consolidated writer-first plan

**Status: working proposal; application changes not approved or started.** This is the decision-ready map of the review so far, not a claim that all repository files or all user needs have been reviewed. Detailed evidence, probes, exceptions and prior design explorations are in [WRITER_FIRST_EXPERIENCE_PLAN.md](WRITER_FIRST_EXPERIENCE_PLAN.md) and [DARSHI_WRITER_INTENT_TEST_PLAN.md](DARSHI_WRITER_INTENT_TEST_PLAN.md). The three areas below reflect our working understanding of the original concerns; we should correct the framing if it misses something.

## Product outcome and the three original areas

1. **After analysis: graceful, uncluttered findings.** A writer can keep writing, choose when to open a concise first reading, and explore the complete set of findings with evidence and limitations. No forced dashboard, unwanted revision or fabricated clean bill of health.
2. **Feedback quality: precise, grounded and contextually appropriate.** Analysis sees the right draft and relevant scenes; craft rules are lenses rather than mandates. Factual observations, quotation matches, interpretations and uncertainty remain distinct. Important useful notes must not be lost in pursuit of fewer false positives.
3. **Sameer and Dr. Sushruta: real collaborators, writer in control.** Sameer helps the writer think, responds directly and offers suggestions when requested. Sushruta listens to intent, reconsiders and can still offer a reasoned, evidenced disagreement. Both retain distinct, human-feeling voices without invented credentials or memories.

Additional foundations: preserve drafts and reports, privacy and scope, model-independent evaluation rather than wording matching, performance, accessibility and failure recovery.

## Writer journey: visual sketch and when it appears

```text
WRITING DESK — before or during analysis
  Your pages remain primary. A small status says what is running.
  [Read the last completed analysis]  [Stop]  (when applicable)

AFTER A READING COMPLETES — optional first reading, not a landing page
  One supported strength, one consequential question, or an honest limitation.
  [Open the full reading]  [Return to writing]

FULL READING — opened deliberately, with manuscript context available
  Story-level discussion  /  scene-linked notes  /  coverage and limitations
  Select a note → observation, passage(s), interpretation, counter-reading,
                  source and uncertainty — only the detail needed at first.
  [Discuss with Sushruta]  [Think with Sameer]  [Set aside]

DISCUSSION → OPTIONAL REVISION
  Selected note + source + draft version + writer intent travel together.
  Explore before suggesting. If requested, compare a proposal with the draft.
  [Apply]  [Discard]  [Keep discussing]   (no change without approval)

RE-READING AFTER EDITS
  Analyze a named immutable snapshot of the current working draft.
  Show changed / possibly related / not raised / unknown — not “fixed” by default.
  Preserve prior notes and decisions; ask before uncertain carryover.
```

This is a journey and information hierarchy, not a finished UI. Bright, spacious, book-like presentation with restrained typography remains the preferred direction; prior concept selections were not approval. Test alternatives with writers, including keyboard/mobile use, empty/partial results and no-screenplay-leaves-local defaults.

## Recommendations and alternatives

### A. Protect the writer's work before redesigning the reading

**Recommend:** snapshot the current working draft per run; produce immutable, versioned report generations; validate results and cancellation before atomically publishing one generation pointer. Keep the prior reading accessible, clearly marked with its own draft. Correlate Stop and retry with run IDs; preserve writer marks and failed-pass metadata. Test recovery at every publication step and cross-process lock boundary.

- **Original-upload re-analysis:** simpler, but demonstrably ignores working edits in the tested orchestrator path.
- **Read mutable draft throughout a run:** responsive, but can mix versions.
- **Lock the editor while analyzing:** avoids mixed versions, but blocks the writer for potentially long model calls.
- **Trade-off:** snapshots and generation publication require migration, local storage, cleanup and more careful concurrency. They are worth it for recoverability; old reports lacking provenance must be labelled unknown rather than invented.

### B. Feedback that can be questioned, not a verdict factory

**Recommend:** capture per-pass coverage and source provenance, analyze complete relevant scene spans with bounded overlap and story-level retrieval, select applicable craft principles with exceptions, and keep evidence matching separate from claim support. Use narrowly reliable mechanical checks; allow interpretable readings as explicitly revisable, not falsely certified. Preserve excluded/merged candidates with reasons in a project-local audit trail, under project deletion rules. Distinguish incomplete coverage from a script defect.

- **Trust a quote match:** fast but demonstrably permits contradictory findings.
- **Use another model to judge every note:** may improve some cases, but adds latency and correlated or new errors; not proof.
- **Suppress every uncertain note:** clean surface but risks losing valuable interpretation and independent dissent.
- **Trade-off:** local coverage bookkeeping, conservative abstention and reviewable audit cost engineering and some storage; staged, bounded checking must be benchmarked for recall, harm and latency, not assumed better.

### C. Discussion instead of compulsory fixes

**Recommend:** neutral, typed handoff including the selected claim, actual excerpt(s), version, limitations, counter-evidence and optional writer-stated intention. Sameer follows the writer's conversational lead; direct questions receive direct answers. Sushruta treats intent as context, can update or maintain a respectful evidence-based disagreement. Rewrite is optional and cannot overwrite a changed passage.

- **One generic persona:** easier, but loses their distinct roles.
- **Automatically obey intent or automatically push back:** both flatten collaboration and make the exchange less truthful.
- **Automatic suggestions/rewrites:** may look productive but takes control away from the writer.
- **Trade-off:** a natural interaction requires context budgeting and evaluation over multiple turns; no prompt wording can guarantee human-like behavior across models.

### D. Memory, privacy and writer decisions

**Recommend:** default story facts and interpretations to their project/draft; carry refresh context immutably, isolate concurrent updates, and separate pause, edit and delete. General collaboration preferences can be writer-wide with clear controls. Cross-project recall is an explicit, reversible choice. Separate claim IDs from evidence IDs; keep verdicts about individual claims and preserve ambiguous legacy shared marks as history, not guessed transfers.

- **Remember everything automatically:** convenient but risks cross-project exposure and false familiarity.
- **No memory:** simpler and private, but prevents continuity and learning.
- **Trade-off:** transparent controls and deletion/version guards add complexity; audit-derived copies, queues, exports and backups before making deletion claims.

## Prioritized gap and dependency map

| Priority | Evidence and consequence | Plan requirement / dependency |
|---|---|---|
| Release blocker | Controlled temporary-project test: working edit absent from orchestrator's analysis input. | Immutable working-draft snapshot; update baseline, scene anchoring and comparison together. |
| Release blocker | Controlled total-failure test overwrote previous reports; injected second-write failure left mixed generations. | Validate before save; staged generation and atomic publish; recovery tests. |
| Release blocker | Controlled cancellation during grounding returned normally; frontend function treated cancelled response as complete; retry Stop returned 409. | Run-scoped cancellation across full runs/retries, safe publish cutoff and consistent UI. |
| Release blocker | Controlled concurrent memory refresh mis-scoped a note; suppression could be reintroduced. | Immutable per-call scope; suppression/deletion-aware commit and privacy boundaries. |
| High | Parser scene/cue errors; scene/overview caps and late-scene retrieval can omit material in both supplied scripts. | Coverage-aware windows and explicit priority; test parse, source identity and end-to-end retrieval. |
| High | Controlled pipeline accepted a contradictory observation with a real quote; post-gate enrichment can do the same. | Separate citation from support; scoped checks and honest abstention; validate after enrichment. |
| High | Distinct claims sharing a quote share verdict identity; report signature can miss changed claim text. | Separate claim/evidence/run identity, conservative migration and cache invalidation. |
| High | Rule tiers, required inputs and budget ordering can mislead; false-positive language/contradiction filters exist. | Expert KB audit, applicability and input checks, reversible filtering and multilingual evaluation. |
| High | Perceived accuracy/progress can overstate what writer verdicts or quote changes establish. | Report denominators and uncertainty; “passage changed” is not “resolved.” |
| Design gate | Handoff can assume a defect; persona behavior may drive unsolicited ideas or strip uncertainty. | Typed neutral handoff, writer-led Sameer, independent Sushruta; meaning-preserving transformations. |

Evidence is controlled or source-traced as described in the working plan; this table is not a rate-of-occurrence estimate. No real model, user study or full file-by-file audit was performed in this session.

## Delivery phases — after explicit approval, not a commitment to implement now

**0. Close review gaps.** Complete a tracked repository review by subsystem and surface; confirm full report/revision/chat/export lifecycle, storage and migrations. Prepare an executable consented benchmark and a clickable writer-journey prototype. Separate proven, inferred and untested claims. Establish a real local model/hardware baseline when available; do not use demo output as model validation.

**1. Preservation and control.** Solve working-draft snapshots, report-generation publication and cancellation/retry, including legacy migration and rollback. Do not tie this safety work to a cosmetic redesign.

**2. Provenance and retrieval.** Establish versioned source/claim/evidence identity; parser and coverage visibility; coherent context selection including ending and explicit scene priority; no cross-run mark corruption. Keep existing report/session paths interoperable during migration.

**3. Feedback and collaborators.** Calibrate KB and verification, support reviewable filtering, typed handoffs and neutral discussion; implement writer-controlled memory boundaries and distinct persona behavior. Avoid releasing an apparently intelligent interface whose evidence or privacy layer is still unreliable.

**4. Experience and rollout.** Validate one coherent clickable prototype, then deliver the first-reading/full-reading/discussion/optional-revision flow, accessibility and resilient partial/failure states. Incrementally roll out only after the gates below; preserve rollback and prior data.

Ordering is a dependency map, not a claim that every task is serial. An approved vertical slice can span phases if it preserves the same safety gates.

## Acceptance and release gates

- **Data safety:** real-store and multi-process tests for edit → snapshot → report, failure at every write, cancellation during each stage, retry, restart, concurrent edits and rollback. No confirmed stop or total failure may overwrite the prior published report. An in-flight call's cancellation limits must be disclosed.
- **Grounding:** verify quote type/location separately from claim support; selected fake-client regressions for negation, post-gate enrichment, absence, missing names, multilingual text and incomplete coverage. Record false confident claims, missed useful notes and abstentions separately.
- **Agency and personality:** multi-turn writer/consultant testing of Sameer's initiative and direct answers, Sushruta's independent reassessment and reasoned disagreement, no invented credentials/memories, and explicit apply/discard. Test both screenplays without presuming audience reception or over-explaining intended ambiguity.
- **Privacy:** cross-project and overlapping-name tests, delete/suppress during refresh, cache/derived-data invalidation, restart, explicit export/backup limitations and both collaborators. No real screenplay sent to an external endpoint without informed consent.
- **Writer experience:** test the whole journey with writers and consultants, not only screens; ensure all findings remain discoverable without a wall of flags. Accessibility, keyboard, small-screen and failure states are mandatory.
- **Quality and performance:** consented diverse held-out scripts and multiple available model configurations; independent reviewers assess accuracy, usefulness, harm, recall and disagreements. Measure first usable reading, completion, p50/p95, retries, tokens and hardware; compare like-for-like against the existing baseline. Establish quantitative thresholds from the baseline and stakeholder review before release; do not claim guarantees across every model.

## Open issues before critique and sign-off

1. Full 665-file inventory exists, but the promised detailed file-by-file review is not complete. Track the remaining files by risk and subsystem; don't equate inventory with review.
2. No real-model application run or writer/consultant validation has been performed in this session. An accessible compatible server and explicit consent are prerequisites for real-script testing; exact wording is not the benchmark.
3. The user's preferred editorial aesthetic is known, but the feedback arrangement and navigation remain unapproved. The existing concepts are explorations, not sign-off.
4. Commit-level storage design, lock ordering, snapshot lifecycle, incremental updates, ambiguous legacy marks and backup deletion semantics need detailed design and adversarial tests.
5. The three original concerns above are a working synthesis; avoid presenting it as the user's exact words if the original formulation is unavailable.

## Critique gate — after the review gaps are closed

Before implementation, run a separate adversarial review from four viewpoints: (1) writer/creative agency, (2) independent screenplay consultant and multilingual reader, (3) privacy/data integrity and failure recovery, (4) performance, accessibility and deployment. Attempt to falsify each recommendation, compare rejected alternatives and articulate repercussions. Record findings, changes and unresolved disagreements; then present the revised plan to the writer for approval. The present document is **not yet through that critique gate**.

## Further storage and backup review — added risk and decisions

- Two direct orchestrators entered analysis concurrently in a controlled temporary-project/two-thread test; the webapp's in-memory per-project lock does not govern direct CLI/watch callers. **Recommend:** cross-process protection at a shared orchestrator/publication boundary, not just another webapp lock. This was not a cross-process corruption test.
- Individual file writes are atomic, but the working draft + edits + redo stores and the Markdown + JSON reports are not multi-file transactions. **Recommend:** test a durable immutable-revision or journal protocol with a single published generation, while reviewing storage cost and compatibility. Do not claim that a pointer fixes old edit-log crash gaps by itself.
- A temporary-project Flask test confirmed a backup includes the project's synthetic `api_key` field. A real configured key could therefore travel with an archive if shared. **Recommend:** redact credentials from shareable backups by default and disclose restore limitations. No real key was used.
- Project backup can silently skip individual files and is assembled while stores may change; a complete, coherent archive is not established. **Recommend:** generation-consistent backups with a manifest, explicit missing-file reporting and restore tests. The library backup deliberately excludes the writer profile; explain that recovery scope. These backup consistency points are source-traced, not all independently tested.

The critical path therefore includes recovery and privacy of the *archive*, not only normal publication. Further work: injection tests of edit-log crash points, two-process CLI/webapp concurrency, and local backup/restore under concurrent edits; no implementation has been approved.

Controlled follow-up: injecting an edit-log write error caused `apply_edit` to return an error after the working draft had already changed, with no edit-log entry. Injecting a file-write error during `/backup` returned HTTP 200 with an archive missing that file. Neither is a measurement of real-world frequency. Release gates must cover unambiguous edit acknowledgement and recovery as well as explicit backup incompleteness; do not blindly retry a possibly already-applied edit.

Controlled follow-up: **two separate OS processes** entered the direct orchestrator's analysis phase simultaneously on one temporary project; both were intentionally stopped before report publication. Recommend a shared cross-process run lifecycle, rejecting duplicate active runs by default while keeping draft edits free, with crash recovery and safe publication. Both project and library backup routes also retained a synthetic credential marker; the tested library archive omitted the writer profile. These are controlled tests, not evidence of actual data loss or a real credential leak.

### Retry provenance and metrics — added controlled findings

An actual orchestrator test with a fabricated prior report and a directly changed parsed draft merged an old-version character note and a new-version dialogue note, then marked the retry categories complete. This demonstrates the merge path's missing input-version guard under the constructed conditions, not that an ordinary UI flow necessarily permits the same sequence. Separately, `AnalysisResult.merge` kept an evidence-depth count for one fresh finding after combining two findings. No real model was used.

**Recommend:** bind retries to the original immutable draft snapshot and record per-pass model/prompt/KB provenance. If the active draft changed, offer either an explicitly old-snapshot retry or a fresh current-draft analysis; don't silently mix. Recompute all summary metrics from the published merged set. Re-running costs time, but publishing a mixed-version result as a single reading undermines trust. Tests must establish UI reachability and all migration/failure paths.

### New release blocker: switching drafts can discard working edits

In a disposable project, the real edit, upload-draft and activate-draft functions were exercised: an applied working edit and its history disappeared when a second draft was uploaded and the original activated; the restored text was the original parse. The snapshot implementation copies source/parse/report, not the working draft or edit history, before resetting working state. No user project was touched. Prioritize coherent per-draft working-state snapshots and explicit recovery before any UI redesign.

Reparse and draft-switch code resets analysis, so the earlier synthetic mixed-version retry was not shown reachable through an ordinary sequential UI flow. Concurrent cross-route cases still need testing. Never present an old or mixed result as a reading of the current working draft.

The draft-edit loss is now also confirmed through the real HTTP endpoints in an isolated synthetic project: create, apply edit, upload new draft and activate original all returned successful statuses, but the restored script lacked the edit. Existing `tests/test_diff.py` passed 15 tests without covering this case. No model or user data was used. This is an API test, not a browser test.

### Confirmed API race: old reading can appear on a newly uploaded draft

A controlled two-client Flask test paused a fake analysis after it read synthetic Draft A, uploaded Draft B through the actual `/drafts` route, then let the old analysis finish. Both requests succeeded; `/script` returned Draft B while `/report` returned the fabricated Draft A finding as a completed report. No real model or user project was used. This is a release blocker distinct from the earlier unproven ordinary-UI mixed-version retry scenario.

**Decision:** publish against immutable snapshot and run IDs; atomically compare the target draft generation at completion. A late result for an old draft may remain an explicitly labelled historical reading, but must not become the current draft's report. Coordinate upload, activate, reparse, delete and publishing across processes, while allowing the writer to keep editing. Test in-flight transitions and crashes, not only sequential draft workflows.
