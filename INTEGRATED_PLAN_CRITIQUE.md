# Integrated plan: adversarial critique and revised proposal

**Status: planning only, not approved.** This is a provisional critique, not a claim that every file has been audited, all defects found, or real-model/writer validation completed. See the [consolidated gap register](GAP_REGISTER_AND_EXECUTION_PLAN.md) for evidence and the 15 numbered gaps. The next decision is approval of a final plan after remaining high-risk review; implementation is not authorized by this document.

## 1. The actual product promise

A writer can read their own work, receive a clearly attributed independent reading of the precise revision analyzed, question it without being pushed into compliance, and choose what to change. Sameer helps them think in their voice; Sushruta examines the work independently, listens and may change their mind or explain a reasoned disagreement. Neither invents human credentials or memories. The product cannot promise that an audience will react as intended or that every model will be equally capable.

These are one system, not three separate features: a misplaced scene can corrupt a reading; an unsupported reading can become a misleading conversational premise; a misleading premise can steer an edit; a lost edit can make all of that harmful.

## 2. Writer's journey — schematic, not approved screen design

Each box describes a moment, not a demand for six permanent screens or sidebars. Bright, book-like page; restrained type; quiet controls; no score, problem-board or dashboard as the default. The arrangement of feedback remains undecided and must be tested.

```text
A. WRITING DESK (before and after analysis)
   [manuscript page, current working draft]
   subtle: Read feedback / Start reading    saved-state and draft identity
                         |
B. FIRST READING (only after a reading completes; optional, dismissible)
   A short orienting reading: what the work appears to be doing,
   selected meaningful observations and what was/wasn't read.
   [Continue to manuscript] [Explore the reading]
                         |
C. EXPLORING A NOTE (when the writer chooses one)
   Claim in plain language → relevant passage in context → alternative reading
   → uncertainty/coverage.  [Discuss with Sushruta] [Think with Sameer]
   [Return to page]  Full findings remain reachable; never hidden by a summary.
                         |
D. CONVERSATION (on invitation; back returns to same manuscript location)
   Sushruta: evidence + independent view; asks/listens when intent matters.
   Sameer: helps think; responds directly and suggests when asked.
   Actual quotation, interpretive claim and writer intent are distinct.
                         |
E. REVISION (optional, writer-initiated)
   Exact original ↔ proposed text, scope and draft shown. [Apply] [Discard]
   No automatic rewriting. Undo/redo stays available after draft changes.
                         |
F. NEW READING (when requested after edits)
   The new snapshot and older reading are identified. Change in wording is
   not proof an issue is resolved. Uncertain cross-reading links stay uncertain.
```

Empty, running, failed, cancelled and stale-reading states must be legible without pretending the last good reading is current. The first-reading summary is a hypothesis, not a requirement that writers accept an added screen: test direct-to-page feedback alongside it. A review can be skipped or stopped, with the writer's place retained. A diagram cannot settle density, accessibility or workflow; no existing concept image is approved.

## 3. Critique from opposing viewpoints, and changes made

### Writer: “Are you making me manage the machine instead of write?”
- **Objection:** snapshots, versions, evidence, and coverage could turn the desk into paperwork. Summaries could bury the very feedback I came for or sound like an authoritative diagnosis.
- **Revision:** keep technical detail progressive and human-readable; surface the minimum necessary when stale or incomplete; one clear route to the complete reading. No forced triage, score, acceptance, or summary screen. Preserve context and focus when returning. Test whether direct-to-page or a brief first reading better serves real writers.
- **Trade-off:** making uncertainty visible can add friction; suppressing it would be more dangerous. Test comprehension, not simply click count.

### Consultant: “Does respecting intent make feedback toothless?”
- **Objection:** a writer's explanation is important context, not evidence that an audience will receive it; polite assistants can automatically endorse explanations or turn legitimate ambiguity into a flaw.
- **Revision:** separate *author intent*, *what the pages support*, and *untested audience reception*. Sushruta may say, “I understand the intention; here is why I still read this differently,” with the evidence and uncertainty. For Darshi, don't suggest eliminating the intended continuing influence of a good book or explaining away ambiguity. Ajay's intended handoff to Venu and the intended unresolved Siddhu–Rahul relationship are inputs, not audience-study findings. Sameer responds directly to questions; suggestions are welcome when requested rather than imposed.
- **Trade-off:** healthy disagreement may feel uncomfortable; test explanation, fairness, context, and whether the writer can decline without penalty, not agreement rate.

### Technical/recovery: “Your snapshot is just another file until failure proves otherwise.”
- **Objection:** immutable files and atomic rename alone cannot make several files, processes, a report and a pointer into one transaction; a new storage system can itself lose existing work. Locks and a snapshot label do not make old tools safe.
- **Revision:** define transactional boundaries and compatibility before selecting storage. Preferred candidate is a transactional local store for authoritative revision metadata, history, run ownership and published pointers, paired with immutable content blobs; retain original files as import/export and migration input. Compare with a journaled file-only protocol. Database transactions simplify multi-record commits but add migrations, tooling, disk and recovery complexity; they are not automatically safe on every filesystem. Choose only after a short design spike with crash and cross-process tests, not by assumption. Old CLI/API writers must use the same authority or be blocked/read-only: dual writers are unsafe. Never hold the edit transaction open during model inference.
- **Trade-off:** extra implementation and migration effort now is preferable to a silent loss of writing. Ensure crash-recovery and rollback are designed and exercised, not bolted on.

### Privacy and memory: “Do you really know which project this memory belongs to?”
- **Objection:** matching character names cannot reliably determine project scope, particularly when projects share a name, and unspecified observations may be story-specific. Archive redaction alone does not handle memory deletion or credentials elsewhere.
- **Revision:** newly generated memories carry immutable originating project/session scope and explicit consent/control. Legacy items of uncertain origin are quarantined as unassigned and not fed into other projects; let the writer inspect/delete/assign them, without silently guessing. User-level preferences remain user-level only when supported by provenance. Provide deletion semantics across stores, backups and pending jobs, and say what cannot be revoked from previously downloaded archives or external providers. Inventory all secret locations; default exports redact secrets and declare omitted files; avoid claiming a backup is restorable until a restore test succeeds.
- **New controlled migration probe:** two temporary projects both contained a character AJAY. Existing `_entity_scope_map` kept only one project; `_migrate_v2` assigned an “Ajay” observation there and treated an unnamed ending observation as global. This establishes ambiguous/unknown-scope misclassification in a synthetic helper test, not proof of an actual user's data leak or of which project the observation came from. Directory enumeration can affect the selected project.

### Accessibility and performance: “Elegant for whom, and at what cost?”
- **Objection:** quiet, hover-only controls can disappear for keyboard/touch/screen-reader users. More grounding calls can multiply latency and cost, and a faster model can deliver worse feedback.
- **Revision:** persistent keyboard-accessible entry points, visible focus, semantic navigation and announcements, adequate targets, zoom/reflow and reduced motion. Evaluate with disabled users and assistive tech, not only automated DOM checks. Measure time to first useful result and complete result, p50/p95, tokens, costs and failures by model and hardware while independently judging quality. Keep the previous valid report available during an in-progress read. Batch or parallelize only with bounded resource limits, stable ordering and cancellation; do not skip context merely to meet a latency target.
- **Trade-off:** model calls already in flight may not stop immediately; communicate this honestly. No universal quality or latency guarantee without real measurements.

## 4. Coordinated technical shape and migration constraints

1. **One authority for draft changes:** writer edit + undo history + active-draft identity must commit together or be recoverable as a unit; acknowledge success only after durable commit. Concurrent writers get explicit conflict handling, not silent last-writer wins. Preserve all existing revision content and history.
2. **Analysis lifecycle:** capture an immutable working revision and content digest; run ID, model/config, KB version, parser version and per-pass coverage travel with it. Long inference runs outside the write lock. One active job per project by default; lifecycle/ownership uses cross-process coordination and stale-owner recovery. A final compare-and-publish transaction checks run ownership, cancellation and relevant current version. If the draft changed, retain the completed reading as labelled historical, never silently publish it as current. Decide whether every historical run is stored only after storage/privacy assessment.
3. **Publication:** stage machine-readable and readable reports as one generation; validate and atomically publish a pointer to that complete generation. Prior valid report remains retrievable on cancellation, failure or restart. Recompute display counts from the delivered finding set. Retry must use the original snapshot and preserve pass provenance, or explicitly start a new reading.
4. **Evidence:** each finding distinguishes a claim from its quoted evidence and source location, known scene coverage, interpretation, intent, uncertainty and provenance. IDs must not conflate opposite claims sharing an excerpt. A matching quote establishes presence, not support or truth. Missing, contradictory, transformed or unreviewed evidence remains visible as such; a skeptical review path must not silently discard every nuanced finding.
5. **Chat handoff:** structured, neutral claim and exact optional passage, snapshot identity, context bounds and writer-supplied intent. No fabrication of a passage when one is missing. Mark older report context explicitly; do not mix it into current script context as if contemporaneous.
6. **Legacy migration:** inventory data and version it; make a local pre-migration copy with a verified manifest, warn about existing secrets and secure its permissions. Migrate into a separate staging area, check counts, content hashes and history, then switch authority atomically; record migration version and make restart idempotent. Preserve unknown fields and unassign ambiguous identities rather than guessing. Test upgrades on representative historical projects, interruption at each boundary, disk-full, corruption, rollback and a fresh-process restore. A rollback after new writes must preserve or export those writes; do not silently revert them. Validate old CLI and app combinations and fail closed on unsupported writers. Backups need coherent point-in-time content, explicit omissions, safe restore paths and a tested restore process.

This is a design proposal, not a claim the current repository supports those guarantees. Platform-specific locking and filesystem durability must be established empirically.

## 5. Evaluation and release decisions

- **Regression baseline:** encode the controlled draft loss, old-report publication, cancellation, edit/history split, ID collision, backup failure/redaction and memory-scope cases before fixes. Include both API and CLI, separate processes, concurrent edit/switch, failures and process restarts. A green pre-existing suite is not enough.
- **Two real scripts:** evaluate actual full parsed text and versioned scene anchors against the supplied Darshi and Pain 3 PDFs locally, including late scenes, multilingual cues and deliberate ambiguity. Record coverage and source-grounding separately from whether a note is useful. Correct the parser/scene mapping if tested evidence warrants it. Do not send scripts to an external model without explicit consent.
- **Independent quality study:** recruit or use consented held-out work and qualified multilingual readers, keeping a split that is not used to tune prompts. Blind or randomized reviewers compare existing, selective and on-demand grounding across multiple available model configurations. Score citation fidelity, claim support, factual error, major-issue recall, unsupported flags, scene context, useful disagreement, intent handling and actionable usefulness; record disagreements, uncertainty and unjudged items. Compare structured judgments, not exact words. Include hard cases and report sample sizes, distributions and confidence limitations.
- **Experience study:** observe writers and consultants navigating first reading, complete findings, disagreement, edits, recovery and an unavailable model; include keyboard, screen reader, small screen, zoom and reduced motion. Compare brief first reading versus direct manuscript return. Evaluate agency and comprehension as well as time.
- **Performance:** record hardware, model, concurrency, script size, token consumption/cost and p50/p95 time to first useful and full result, failures and cancellation responsiveness. Set thresholds with stakeholders after baseline; no fabricated targets or guaranteed parity across models.
- **Stop-ship:** unrecoverable acknowledged edits, unsafe draft switch, cross-revision mispublication, loss of the last valid report, silent incomplete backups presented as complete, exposed secrets in default exports, unbounded cross-project memory leakage, or unsupported claims presented as verified should block release. Define measurable acceptance and supported operating environments before implementation; these are risks and gates, not assertions of exhaustive coverage.

## 6. What remains before approval

Review remaining high-risk source/integration and migration paths; reconcile this critique with the consolidated register and make unresolved decisions explicit. Real-model evaluations, independent audience reception, accessibility/user studies, and exhaustive audit remain unproven; distinguish prerequisites for a plan decision from release gates. Then present one consolidated recommendation, genuine alternatives and repercussions, a visual journey, the critiques and residual unknowns, and seek explicit approval. Until then: no application implementation.

### Added safety and verification obligations from continued sweep

Watch-folder mode must not replace a same-named source or mark failed processing complete; preserve inputs until a verified durable copy exists and use collision-safe cross-process claiming and restart handling. A controlled simulated disk failure showed that the current implementation can replace an earlier source in `done/` before any project copy exists. Treat this as a watch-mode stop-ship issue.

Investigate repeated-error announcements with assistive technology and improve the live-region test without introducing a visible empty alert. The existing XSS test's dashboard failure appears to flag inert markup text inside a quoted attribute, not an executed payload; keep structural checks and independently verify before drawing a security conclusion. The pagehide autosave browser assertion failed once under concurrent suite load and passed on isolated rerun; reproduce under controlled load and failure injection before assigning root cause. See gaps 16–17 in the consolidated register.

### Additional writer-owned content obligations

The same durable, versioned protocol must extend to chats, branches, notes, stash, beat-board arrangements and analysis history—not just script drafts. Controlled store probes found lost repeated messages, session/branch resurrection after deletion, overwrites after injected read/backup failures, silent stash truncation, and stale board fallback. They also found that identical ledger contents can collapse different actual model runs. See gaps 18–20 and 13 in the consolidated register. Preserve content and deletion intent; avoid silently guessing stale scene associations; retain exact run provenance. Test each store via its actual routes as well as across processes and crash boundaries.

### Export and recovery correction

The earlier simple edited-line export check did not establish a safe round trip. The Fountain/TXT exporter joins consecutive speakers without a separating blank; a minimal test and both real-script parsed representations showed altered speaker attribution on re-import. FDX retained element text/type/speaker in those two bounded tests but a synthetic source lost original scene numbering and bold styling. Source-preserving recovery, explicit fidelity disclosures, multi-speaker round trips and independent application checks must be part of Phase A rather than an afterthought. See gaps 21–22; no existing reconstructed export should be described as a complete backup.

### Multilingual, extraction and analytics obligations

Unicode-aware quote comparison must retain meaningful combining marks and separate exact matching from approximate matching. Native Telugu cue parsing needs independent examples and correction workflows. PDF reading coverage must be tracked per physical page; mixed text/image PDFs cannot be treated as fully read simply because some text was extractable, and a parse error must not masquerade as a completed usable parse. Parser-derived speaker lists must not be used as definitive presence/absence or interaction evidence. Correct and label coarse pacing analytics. Controlled examples and limitations are recorded as gaps 23–27 in the consolidated register.

### Collaborator and privacy additions from continued sweep

The dialog system must accept brief and native-script turns reliably, honor direct questions without silently filtering away the answer, and enforce a full-turn budget rather than a system-prefix estimate. Cross-project details must have explicit scope and consent, especially for remote providers. Streaming cannot promote hidden reasoning fields or unverified provisional output as a final answer. All five conclusions are based on the bounded code paths and fake-client probes in gaps 28–32, not a real-model benchmark.

### Connection and recovery critique

The privacy architecture cannot stop at validating the initial endpoint: the actual analyzer followed a synthetic 307 to a separately rejected hostname, with DNS safely redirected to a local test server. Specify redirect, DNS and proxy policy for analyzer, collaborators and STT, with clear consent for remote providers; verify each transport rather than extrapolating a reproduced analyzer case. Stronger blocking may disrupt providers that legitimately redirect or depend on proxies, so make supported routes and consent explicit rather than silently falling back.

Archives must exclude credentials by default and not dereference links outside their declared scope, while preserving a transparent inventory of excluded material and allowing verified restoration. Secret storage and file permissions require OS-specific threat modeling; same-user local processes and a user who intentionally exports data are separate trust boundaries. Opening a sample must never overwrite an unreadable pre-existing project; preserve and recover it. Refresh model capability information when endpoint identity or configuration changes. Gaps 33–36 include controlled evidence and limitations. These are additional stop-ship considerations for affected paths, not proof of an actual compromise or a completed security audit.

### Intake and provider choices — critique of the coordinated plan

The watch-folder fix must define *when a producer has finished*, not only avoid overwrite: an open synthetic source was successfully copied halfway, then finished in `done/`. Prefer an explicit atomic-arrival contract over an arbitrary quiet period where producers support it; if stability polling is offered for convenience, disclose that it cannot guarantee completeness. Unify stable internal project identifiers while preserving Unicode titles, and make batch failure machine-detectable. See gaps 16 and 37–39.

Provider independence also needs an honest compatibility contract: honor an explicit model selection or obtain consent before substitution, preserve requested and actual identities per run/pass, normalize supported base URLs, and show the destination that each operation will actually use. A failed settings propagation can leave an existing session on its old destination while the global API reports success; make partial application and in-flight operations explicit rather than silently trusting the status indicator. These recommendations trade friction and migration complexity for informed choice and reproducible quality/performance; verify against representative local and consented remote providers. See gaps 40–42.

Additional redirect tests now reproduce the same unvalidated 307 behavior in collaborator synchronous and streaming calls and external STT, using synthetic content and a redirected loopback test server only. The proxy, DNS and remaining protocol cases are still untested.

### Consultant critique: measurements are not diagnoses

A deterministic rule that detects “I love you” cannot know the line lacks subtext; a day-to-night scene cut is not automatically an unmarked continuity failure; a count-based dialogue/action ratio cannot establish dramatic drag. Each currently generates definitive creative language in bounded synthetic probes. Retain transparent measurements where useful, but reserve judgment for contextual, evidence-backed interpretations that a writer can challenge. Do not solve this by censoring disagreement or replacing every note with a question: an independent consultant can make a strong case when supported. Related-rule/scene grouping also needs claim-level evidence, not an assumption that distinct passages are duplicates. And report surfaces must distinguish failed or unrun analysis from a clean result. See gaps 43–47.

A further unvalidated threat-model obligation: screenplay and generated report text can be interpolated into prompts, including collaborator system-prompt blocks. Evaluate instruction-like material as untrusted content across providers; no successful prompt injection was demonstrated and legitimate dialogue must remain analyzable. No prompt-only defense is a guarantee. See gap 48.

### Narrative judgment and unattended workflow critique

A grounded quote or repeated word is not evidence that a dramatic payoff occurred, that a dream is objectively the story's reality, or that a dialogue-heavy scene drags. Controlled counterexamples exposed all three failure modes in current deterministic/model-adjudication paths. Preserve literal evidence, model interpretation, confidence and writer intent separately; do not let a lexical heuristic silently suppress independent challenges or promote invented citations to confirmed facts. Replace prescriptive continuity/pacing heuristics with transparent measurements or properly evaluated contextual judgments. Deliberate ambiguity and unresolved relationships remain legitimate; the consultant may still challenge whether the intended effect reaches an audience.

For data safety extend atomic no-clobber identity claims to idea and chat creation, and protect orphaned CLI destinations. Watch automation needs useful failure exit codes in addition to source preservation. Tests must force collisions and failures, not rely on their low random frequency. These require changes across shared creation and recovery flows, not a UI-only redesign; see gaps 39 and 49–54.

### Revision and narrative-judgment correction

A revision must preserve its typed structure, stable identity and reversible history, not merely change a matching text string. A duplicate-line test caused undo to fail while the UI declared success; separate accepted heading and speaker edits left associated structure stale. The future plan must make structured apply/undo/export a single coherent contract and refuse unsupported operations without losing work.

A consultant should distinguish observations, hypotheses and evaluated claims. A fake-client example showed an invented dream line elevated to a “confirmed” story mechanic in downstream prompts, while a synthetic setup/payoff test equated mention recurrence with fulfillment. Both can distort the independent reading and are particularly risky for Darshi's deliberately ambiguous mechanism and Pain 3's unresolved relationship. Preserve alternative interpretations and writer intent, but do not turn either into a veto of grounded criticism. See gaps 51–54.

### Handoffs and unavailable-model behavior

Idea graduation must preserve the original, expose partial transfer and carry only a verified snapshot; a successful project creation is not proof that the premise and conversation came across. Import paths need consistent parse-readiness checks. Separately, demo fallback behavior differs between import and normal startup and the displayed opt-out is ineffective at import. Decide explicitly whether demo is opt-in, disclose actual model identity and unavailable states, and never use demo output as a model-quality proxy. See gaps 55–56.

### Settings, secrets and report provenance

A credential belongs to an explicitly approved provider/origin, not a globally reusable blank form value. Synthetic mocked tests found that testing a different endpoint reuses the saved token, and saving a new endpoint retains it. Decide how to handle intentional provider migration, local authentication and URL aliases without ever sending a secret to a newly entered destination before informed approval. Settings must be validated before mutation; distinguish failed application, per-project propagation and the effective destination used by an existing chat. A local-only API switch currently can leave a project's remote destination intact; the standard UI sends additional fields, so do not generalize that specific result to every UI switch.

Disclosures must describe the report's own generation, not the connection active when it is opened or exported. A synthetic historical demo report lost its prominent demo banner when current demo mode was off. Persist run-level and mixed-pass identity, retain an unknown-origin state for legacy reports and separate current-connection status from historical provenance. See gaps 57–59; no actual credentials or data were sent to a provider.


### Deadline correction

Performance and cancellation must share a real end-to-end deadline across nested busy retries, waiting and provider calls. A fake-clock reproduction showed calls being scheduled after the logical deadline; synchronous requests also cannot guarantee cancellation of work already running on a provider. Measure honest elapsed time and cancellation outcomes under contention instead of treating a per-request timeout as a hard total bound. See gap 60.

## 7. Draft switching must be trustworthy before it can be the writer's undo

The latest sweep adds one product-level constraint that outranks its individual defects: "switch back to my earlier draft" is the writer's safety net, and it currently restores only part of a draft (source, parse and report), keeps the knowledge graph and characters from the outgoing draft (gap 63), can accept a broken upload as the active draft and leave the writer unable to reopen the good one without a manual reparse (gap 64), can publish a running analysis into a different draft than it read (gap 65), and can be pointed at another project's snapshot by a crafted name (gap 62). Concurrency between two uploads is not a normal writer action, but it is a normal consequence of two open tabs or a retry, and it loses a draft (gap 61).

So the snapshot/immutable-bundle contract in §4 is not only plumbing for provenance: it is the feature. Until it exists, any journey screen that offers draft history must be honest about it — show which artifacts belong to the active draft, mark the ones that are stale or belong to another generation, and never present a restored-but-not-switchable state as success. The recommended order therefore stands: identity and containment, then one lock for mutation and analysis, then whole-bundle restore with explicit stale states, then the writer-facing screens.

## 8. What "the sweep is complete" can and cannot mean here

The register now covers every Python module in the three packages, every JSON store, the SPA's main surfaces, both attached scripts and the documented surfaces; the remaining unread areas are the preview design labs' HTML, most narrative docs, and anything requiring a real model. That is the honest boundary: a code and behaviour sweep, not a quality trial.

Three consequences for the plan:

- **Do not treat gap count as progress.** The later batches (61–86) are mostly one theme — *the app cannot yet tell the writer which draft, file or generation a claim belongs to*. The fix is a small number of contracts (identity, containment, atomic publication, whole-bundle restore, honest provenance), not 26 independent patches. Any implementation that starts with the UI before those contracts will reproduce the same bugs behind a prettier surface.
- **Recovery is a first-class room, not an error toast.** Damaged projects, damaged ideas, failed uploads, refused backups and stranded active drafts all currently end in a dead card or a raw exception string. The writer journey needs one visible recovery surface with the same visual restraint as the manuscript, and it must be reachable *from* the failure, not from a settings page.
- **The collaborator work still cannot be validated here.** Sameer and Sushruta quality, grounded disagreement, and performance across models need a real endpoint the user runs; everything in this sweep about them is prompt shape, context assembly, transport and failure behaviour. The evaluation gate in §5 stays a prerequisite for claiming the redesign succeeded.

Recommended next step before any code: approve the contracts in §4 plus the recovery surface, then let me prototype the journey screens against them for critique.

## 9. The one architectural cause behind most of the register

Reading the sweep back in order, the 118 live entries reduce to a single missing idea: **the system has no unit of identity for "what the writer was looking at when a claim was made".** Drafts are folder names, reports are files, findings are content hashes, runs are stage statuses, chat turns are messages, and intent is prose in a separate card. Each store is individually careful — there are real locks, atomic writes, damage detection, backups — and yet nearly every serious finding is a disagreement *between* those stores: a report published against a draft it did not read, characters from one draft shown against another, a restored parse whose stage status belongs to a failed attempt, a demo banner decided by today's settings over yesterday's run, a knowledge graph from the wrong bundle, a finding whose rule may not have been in the prompt.

So the coordinated plan should be stated as five contracts, not 118 fixes:

1. **Identity.** One immutable snapshot id per script state; one run id per analysis; one finding id stable across re-analysis and scoped to the snapshot that produced it; one intent record per scene and per finding.
2. **Containment.** Every path derived from user input or from a stored name resolves inside its own project and nowhere else, checked at one chokepoint, tested with traversal and cross-project names.
3. **Atomic publication.** A run writes into its own generation; publication is a single pointer swap that is refused if the snapshot moved. Failed or cancelled runs never overwrite a previous good report, and the desk always serves the last successfully published generation plus its true status.
4. **Whole-bundle restore.** A draft is a bundle (source, parse, graph, report pair, derived analytics, working edits and their history). Switching restores all of it or visibly marks what is missing — never a mixed state presented as success.
5. **Honest provenance.** Every served and exported artefact carries: snapshot id, run id, provider/model identity, whether the output was a stand-in, which rules were actually supplied, and the evidence tier of each claim. Anything unknowable says "unknown" rather than being inferred from current settings.

Everything else in the register is either a consequence of these five being absent, a quality problem that needs a real model to evaluate (Sameer/Sushruta voice, grounding accuracy), or a content problem (the KB's missing pacing/continuity coverage).

**What I recommend approving first:** contracts 1–5 plus the recovery surface in gap 97, with the intent brief (gaps 106–108) as the product change that makes the redesign worth doing. The visual journey stays unapproved until those exist, because a beautiful desk over a mixed-state store would reproduce every failure this sweep found — just more quietly.
