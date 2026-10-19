# Simulated senior-writer UX review

**Original review date:** 2026-10-17

**Status updated:** 2026-10-19

**Type:** AI expert-style heuristic review, not a human usability session

**Requested lens:** a senior screenwriter and novelist with 25+ years of professional practice

**Original reviewed revision:** `52e12695a45dcc55b2e16cdfb0aaac10c5ff105d`; runtime identical to `bd86a8e`

**Current implementation baseline:** `422f4ebbd52cc46074eac30f08c5a45b5992a123`

**Branch:** `arena/e6a57b71-screenplay-studio`

## 0. Current status, superseding the original implementation objections

The original loop discrepancy below was real at `52e1269`; it is **not an open defect on this branch now**. It was repaired in `64da684`, followed by the positional binding repair in `40637d8`. Do not use the historical diagnostic or original next action as a current work order. This status refresh changes documentation only.

No overall completion percentage is asserted. Implementation, browser regression acceptance, writer validation and register calibration are separate gates. The earlier chat estimate of 90–95% should not be used as a progress measure.

| Gate | Implemented or recorded state | Still required |
|---|---|---|
| Ranked loop and positional binding | Shared `queueProjection()` in `64da684`; positional item binding in `40637d8`. Runner-reported parity 22/0 at `07e5d9b`. | Do not reimplement this repair. These receipts retain their own revision scope. |
| Quote-verification denominator honesty | Shipped in `84ce02a`: `scene_not_found` joins `verified` and `not_found` in the denominator; only `no_quote` is excluded. | Not an unshipped task and not evidence that a diagnosis is artistically correct. |
| Visible demotion reasons and settled state | `cf583f0` restores contested/identity/ungrounded badges on deep cards and writer-addressed styling. `422f4eb` also carries identity uncertainty through both row routes. | Fresh browser acceptance for the latest repair. The Windows-only, uncommitted 22/0 is not its acceptance result. |
| Queue-path suite migrations | `tests/e2e_browser_ungrounded_filter.py`, `tests/e2e_browser_counting_contract.py` and `tests/e2e_browser_readiness_gate.py` have been migrated in `cf583f0`, with their laws retained. | Execute all three against the identity-checked pushed revision. Updated code is not an executed browser pass. Fleet-wide green is not established by the earlier subset. |
| G5 fold geometry | Historical 882px/18px result at `bd86a8e`. The later flag repair adds Tier 1 content. | Fresh 1440×900 measurement against the unchanged `<900px` boundary. Do not transfer the old geometry result to the latest implementation. |
| Real-writer UX validation | `docs/REAL_WRITER_VALIDATION.md` remains 13 blank rows; this document is an AI heuristic prior. | An actual sitting, not simulated participant answers. |
| IMPACT v0 | Explainable and visibly uncalibrated; no weights retuned. | Writer judgments about rewrite priority and lane/rank usefulness. |
| Quote-match register calibration | `FUZZY_MATCH_THRESHOLD = 0.72` unchanged. | Authentic Hindi/Telugu/Tamil material for the separate quote-matching decision; not invented examples or an IMPACT calibration claim. |
| Larger programmes | T1–T11 restructure and R1–R6 redesign remain deferred and unchanged; R0 has recorded prior work. | Separate activation and scope decisions. Do not count this queue repair as implementing those programmes. |

Last local receipts for the implementation: **Node 189 passed / 0 failed; Python 2294 passed / 4 expected Linux skips**, plus seven distinguishing mutations. No tests were rerun for this documentation refresh. The runner-reported parity 22/0, layout audit 37/0 and dock sections 187/0 at `07e5d9b` remain historical results, not fresh browser approval of `422f4eb`.

**Current next action:** assert the served identity of the pushed revision, then obtain fresh G5 plus `tests/e2e_browser_ungrounded_filter.py`, `tests/e2e_browser_counting_contract.py` and `tests/e2e_browser_readiness_gate.py` results. A later docs-only tip may be used only with its actual served identity and verified runtime/test equivalence to this baseline. No revision match, no result. Writer validation and authentic-register calibration remain separate after those checks.

## 1. What this review is, and is not

The requested career history is a simulated perspective, not a credential or personal experience I possess. This review uses professional revision priorities to challenge the product's decisions. It is authored by the same agent working on the implementation, not an independent participant.

Inputs inspected at the original `52e1269` review:

- `docs/REAL_WRITER_VALIDATION.md`, including all 13 questions.
- `docs/USER_PERSONAS.md` and the current one-room ranked-queue spec through §14.52.
- The shipped queue, ranking, filter, card, arrival-strip and keyboard-loop source.
- The existing excerpt in `tests/fixtures/pain_tenglish.fountain`. It is a short Latin-transliterated fixture, not a full screenplay and not native-script Hindi/Telugu/Tamil calibration material.
- The previously recorded browser anchors: G5 at 882px, `tests/e2e_browser_dock_sections.py` 187/0, and `tests/e2e_browser_print_media.py` 9/0. These were not rerun for this review.

The original deterministic Node diagnostic executed the `52e1269` application functions and queue expressions on constructed English control findings. It found the historical workflow discrepancy in §5, subsequently repaired. It did not launch a browser, run a model or change application code.

No 30–45 minute session, ten-finding navigation trial, timed comparison, eye-tracking, long-sitting comfort observation or second analysis pass took place. The original human checklist remains unfilled. No new Indic-language material was invented.

## 2. The simulated professional's starting position

> Simulated viewpoint: “Do not give me a longer report. Help me choose the next consequential rewrite, show me the passage and reasoning, and let me disagree before I change the page.”

For a screenplay, I would usually resolve a consequential motivation or causal problem before polishing lines that the structural repair may remove. For a novel, the same dependency principle applies, but interiority, narrative distance and deliberate ambiguity can do work that would be externalized in a screenplay. Neither medium earns a universal category-based kill order.

**Heuristic verdict: keep the one-room, one-queue architecture.** A deep finding beside the manuscript is a better revision instrument than duplicated summaries. Preserve evidence, attribution, the writer's verdict and the distinction between “this note is right” and “I will act on it.” Do not rebuild the interface on the strength of this simulated opinion.

## 3. All 13 checklist questions, answered as simulation

These are conditional expert assessments, not participant answers or new acceptance-test passes. Evidence cells for repaired implementation objections were updated on 2026-10-19; no writer session or navigation-speed trial was added.

| # | Checklist question | Simulated assessment | Evidence boundary |
|---|---|---|---|
| 1 | Did arrival numbers change how you started, or did you skip them? | On the first reading I would start with the most consequential finding, not the arithmetic. On returning to a revision I would want my settled/open work visible. Keep counts secondary to an actionable card. | Preference hypothesis. The prior G5 anchor establishes placement for its input, not what a writer notices. |
| 2 | Did the Pass line read as writer progress or analyzer progress? | The explicit “from the last run, not your edits” wording is the right distinction. I would not interpret a changed analysis count as proof that the draft improved. | `buildArrivalStrip` prints the distinction. Actual comprehension was not tested. |
| 3 | Was “N of M addressed by you” trustworthy and consistent? | Useful if it means my disposition or the working-copy observation, not an objective judgment of artistic improvement. Preserve the separate correct/partial/wrong judgment. | Source and prior counting anchors support the implementation. This review does not add a persistence trial. |
| 4 | Were ghosted marks honest and non-punitive? | A muted, expandable record is preferable to a red failure. “Moved on” still needs to mean the analysis no longer carries the old note, not that my intent was discarded. | The source names the former issue and intent. No participant interpretation was observed. |
| 5 | Was N/P faster than clicking a list? | Keyboard traversal should follow the ranked worklist before speed is measured. That mechanical repair is now implemented; whether N/P is faster remains an empirical question. | Historical gap at `52e1269`; repaired in `64da684`/`40637d8`, with parity 22/0 reported at `07e5d9b`. No speed measurement. |
| 6 | Did eyes stay on the manuscript, and did auto-open help? | Auto-opening the corresponding evidence card should reduce searching. The old absent-card mismatch has been repaired; whether the interaction maintains attention is still a hypothesis. | Historical §5 reachability is not a current defect claim. The later card changes still require current browser acceptance. Eye movement was not observed. |
| 7 | Did mark, next-pass, Discuss and copy land where hands were? | Direct loop actions are useful for repetitive triage. The queue's disclosure preserves its width budget, but “marks” may be less discoverable for a first-time writer. Keep the current pin placement until actual use establishes frequency. | A discoverability hypothesis, not evidence that the green verb budget or pin placement is wrong. |
| 8 | Did Esc leave cleanly while the dock stayed open? | Leaving the mode without destroying the reading context is the right behavior. | `exitLoop` resets loop state and redraws the bar; it does not close the dock. No felt response is claimed. |
| 9 | Was highs-only ink on arrival the right amount? | The question's premise is stale. The shipped default admits high, medium and low. I would not recommend hiding low-severity structural findings merely to make a clean-looking screen. Evaluate actual default ink density instead. | `state.findingFilter.severities` contains all three severities. This is not a new ink-density measurement. |
| 10 | Did peek-chip and unread dot earn attention? | A cue should earn its place by naming new, actionable context. Repeated or ambiguous attention cues would be noise. | Conditional opinion only. No timing, attention or unread-dot lifecycle experiment was run. |
| 11 | Did page and board ever disagree? | Prior browser anchors cover their own inputs and revisions. The loop/queue discrepancy was a separate mechanical gap, now repaired; do not mislabel it as a newly observed page/board browser failure. | Historical browser receipts plus the original scoped diagnostic. Current card/suite changes await fresh acceptance; no new writer journey is claimed. |
| 12 | Did dawn/night hold up over a long sitting? | Calm, legible presentation is necessary, but source inspection cannot establish fatigue, comfort or preference over a long session. | Unanswered empirically. No invented comfort rating. |
| 13 | Was anything noisy, slow or wrongly defaulted? | Verify the latest card and suite repairs rather than reimplementing the fixed loop. Keep report churn from reading as creative progress. Explain quote verification without implying the diagnosis is correct. Update the stale validation question before a real sitting. | Product and suite code repairs are pushed through `422f4eb`; current browser/G5 acceptance remains open. Copy/discoverability concerns are hypotheses. Latency was not measured. |

## 4. Applying the lens to the existing Pain excerpt

This is a revision-priority walkthrough of available pages, not a fresh model analysis or a claim about the complete story.

1. **Clarify the dramatic consequences of the premise.** The doctor's statement, “Both Physically and Emotionally,” establishes a major story proposition. I would ask which choices and consequences demonstrate it later. I cannot conclude that those consequences are missing from a short excerpt, or treat a fictional proposition as a medical fact.
2. **Check orientation before imposing chronological order.** The two-month-forward transition followed by the earlier material may be intentional withholding. The question is whether a reader can track when and why, not whether flashbacks are categorically wrong.
3. **Protect characterization already carried by action.** Rahul damaging Siddhu's drawings establishes a power relationship through behavior. I would preserve that function before accepting generic advice to make the scene more explicit. Whether particular beats are redundant requires reading the scene's escalation, not counting similar words.
4. **Treat exposition as a dramatic transaction.** The doctor supplies information, but Rishi's reaction and what the information means between the characters matter. “Exposition” is not itself a rewrite instruction. The existing observation/why-it-matters fields should explain what the information does or fails to do.
5. **Polish language after deciding scene function.** The metro material and Siddhu's relationship to his drawings can carry vulnerability through action. I would resolve the intended effect before rewriting individual sentences. I would not automatically standardize the excerpt's code-switching into English.

A professional-looking critique must not invent a missing midpoint, Act Two or final payoff from four-scene material. A novel-derived preference for internal explanation must not be applied automatically to a screenplay's external action.

### Lane order and IMPACT

- Structure-leading is a defensible starting hypothesis when a structural repair would invalidate downstream line work.
- A small structural note does not automatically matter more than a causal continuity break on which the ending depends.
- Category, verified quotation and scene span are useful ordering proxies, not measurements of rewrite cost or artistic importance.
- The implementation orders populated lanes by their maximum IMPACT, rather than enforcing an unconditional hard-coded Structure-first order. Do not describe the product as doing something the source does not do.
- Retain v0 and its visible uncalibrated marking. This simulated review supplies no defensible replacement numeric weights.

## 5. Historical code-confirmed loop discrepancy at `52e1269` (repaired)

**Original priority: high. Evidence: source plus deterministic execution at `52e1269`. Current status: repaired in `64da684` and `40637d8`; see §0 for remaining acceptance gates.**

`screenplay_studio/webapp/app.js` at the original `52e1269` revision, not the current implementation:

- `renderFixQueuePanel` filtered queue items through `inFindingFilter`, bound them with `bindQueueItems`, then grouped/ranked them with `groupByLane`.
- `loopList` instead iterated `state.findings` in report-array order and applied `findingPassesFilter`.
- That latter predicate did not perform queue-lane membership or the ungrounded exclusion implemented by the queue's filter.
- `stepLoop` then looked for a queue card with the selected report index. When the old loop admitted an observation or hidden ungrounded row, there need not have been a matching queue card.

The historical writer-facing consequence was that choosing the fix loop from a ranked worklist did not necessarily mean following that worklist. The repaired loop now consumes the shared ordered projection. This diagnostic was not evidence that a real writer preferred another order.

### Original reproduction retained as historical diagnostic data

The original Node probe loaded `52e1269`'s `core.js`, extracted that revision's `loopList` and its disposition/filter dependencies from `app.js`, and executed the queue's own admission/binding/grouping expressions extracted from `renderFixQueuePanel`. It used all severities, no scene/category restriction, open dispositions, and the default hidden-ungrounded state.

These inputs are constructed English controls, not real screenplay findings:

| Report index | Category | Scene refs | Extra state |
|---|---|---|---|
| 0 | dialogue | [1] | grounded |
| 1 | structure | [1] | grounded |
| 2 | theme | [1] | observation |
| 3 | dialogue | [1] | ungrounded |
| 4 | continuity | [] | no mechanical provenance |
| 5 | continuity | [] | `rule_id: timeline_consistency` |

| Diagnostic | Ranked queue indices | Keyboard loop indices |
|---|---|---|
| All six controls, default filters | **[1, 0, 5]** | **[0, 1, 2, 3, 4, 5]** |
| Positive control: category restricted to structure | **[1]** | **[1]** |
| Separate two-item Line fixture: dialogue then character in report order | **[1, 0]** | **[0, 1]** |

The control case agrees, while the mixed and within-lane cases distinguish the paths. This does not require a model, browser, GPU, server or new language material. No pixel, click or navigation-speed verdict follows from this probe. Its successful process exit confirmed these diagnostic outputs; it is **not** a passing acceptance test for loop parity.

**Original follow-up, now implemented:** the shared ordered projection, explicit disposition scope and discriminating tests landed in `64da684`; the subsequent browser walk exposed the positional binding defect repaired in `40637d8`. See spec §14.54–§14.55 and `tests/js/queue_loop_parity.test.js` / `tests/e2e_browser_loop_queue_parity.py`. Do not repeat that work. The later card, status and transport repairs in §14.56–§14.57 have their own pending browser/G5 acceptance listed in §0.

## 6. Other findings and their strength

| Finding | Classification | Recommendation |
|---|---|---|
| Human checklist asks about a highs-only default that no longer ships | Confirmed protocol staleness | Update that question to the actual default before recruiting a writer. Do not populate it with an answer to a fictitious state. |
| “Verified” could be read as “the diagnosis is correct” | Comprehension hypothesis | Retain the truth/intent distinction. If tested confusing, clarify existing badge copy as quote verification rather than adding another Tier 1 block. |
| “marks” hides frequent dispositions behind a disclosure | Discoverability hypothesis | Compare discoverability with the direct loop actions. Do not reopen the one-row budget or move pin based on invented frequency. |
| Numeric rank explanation may not explain the revision's dramatic consequence | Craft-communication hypothesis | Use the existing observation/why-it-matters surface to make the consequence concrete; retain auditable rank/provenance. |
| Long-session comfort | Not assessed | Requires an actual sitting. A simulated preference is not fatigue evidence. |

## 7. Current decision and next action

**Keep the architecture. Verify the latest repair before retuning artistic priorities.** The original loop/queue target is implemented, not still waiting to be coded. This simulation supplied testable engineering leads and craft/comprehension hypotheses, not a fictitious “writer approved” stamp. The subsequent work also restored demotion reasons, writer-addressed appearance and identity-flag transport. Their code is pushed; current browser acceptance is not yet claimed.

The earlier claim that no further useful evaluation could happen without external input was too absolute. A heuristic review can uncover additional testable defects even when the existing acceptance suites are green. Their recorded results remain valid for the behaviors and inputs they covered.

Neither the original simulation nor this status refresh establishes:

- completion of `docs/REAL_WRITER_VALIDATION.md` or independent writer validation;
- calibrated IMPACT, new lane rules or a new `FUZZY_MATCH_THRESHOLD` (still `0.72`);
- authentic Hindi/Telugu/Tamil pages or a native-register threshold decision;
- that a universal threshold is mathematically impossible. Existing probes show sample-dependent behavior, not a theorem about unseen registers;
- a new test run or a different revision scope for a historical browser result. The old 18px headroom is not a measurement of the later Tier 1 addition.

**Next action:** obtain the identity-anchored G5 and three migrated browser-suite results listed in §0 on the pushed implementation (or a verified runtime-identical docs-only tip). Do not describe suite code migrations as executed passes. Keep actual writer validation and authentic register calibration as separate, still-unfulfilled requirements. No global completion percentage or fleet-wide sign-off is inferred.
