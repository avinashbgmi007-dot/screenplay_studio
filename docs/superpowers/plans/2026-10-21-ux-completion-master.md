# UX Completion Master Plan — Agent Handoff

> **For agentic workers:** This is the programme plan. Do not execute a wave from
> this file alone. Execute the referenced packet after its owner gate is signed.
> Track steps with checkbox (`- [ ]`) syntax in the packet, not here.

**Status:** DRAFT FOR OWNER REVIEW — revision 5 after approval notes on
preflight order and file classification. Published review copy; execution is not authorised. No code, gate, weight or
threshold change is authorised by this draft.

**Goal:** Close the remaining UX programme — R0 tokens, every R4 surface, all
remaining deferred UIs, R5 motion, R6 removals/T ledger, and final acceptance —
without lowering a gate, inventing evidence, losing shipped behaviour, or
touching the protected Windows checkout `E:\screen_play_astra`. Arena packets
land only on the approved Arena branch; they do not create task branches.

**Architecture:** A master plan indexes small execution packets. Each packet is
owned by one agent and has a single testable outcome. External-lane packets land
on a task branch that only the owner merges; Arena packets land as an
owner-approved commit series on the fixed Arena branch. Shared SPA files are
serial. Surface work is
brief-first: an agent drafts the brief, the owner signs it, then code starts.
Empirical validation is a separate owner-gated track and never blocks
engineering completion.

**Tech Stack:** Python 3 (stdlib-first), Flask, vanilla JS/CSS (no build step),
Playwright, pytest, Node `npm test`.

---

## Locked Decisions

| # | Decision | Value |
|---|---|---|
| 1 | Scope | Full remaining programme **plus all remaining deferred UIs** |
| 2 | Visual direction | Five-axis hybrid: keep current density, navigation and dawn; bundle fonts; restrained motion with spotlight moments |
| 3 | Completion labels | Keep **engineering accepted**, **writer-validated** and **calibrated** as three distinct final statuses |
| 4 | Agent authority | External agents may implement, test, commit and push task branches; agents never merge |
| 5 | Shared files | One primary writer at a time for `app.js`, `core.js`, `index.html`, `style.css`, `tungsten.css`, `webapp_server.py` |
| 6 | Design approval | Agent drafts each surface brief; owner signs before code |
| 7 | Validation | Writer sitting, IMPACT calibration and quote-threshold calibration remain owner-gated and local-only |
| 8 | Working base | Environment-specific lanes: Arena stays on its approved branch and never creates/switches branches; external workers use an integration branch from `bd91ed6` |
| 9 | Parallelism | Two to three agents: integration writer, test/evidence agent, optional independent backend/audit agent |
| 10 | Task detail | Agent-ready packets: files, interfaces, commands, acceptance, stop conditions, commit boundary |
| 11 | D10 deliverable | Actual finding batches at completed-pass boundaries; progress-only is an explicit scope reduction, not D10 |
| 12 | D05 rule | Retire a genuinely duplicate UI only after semantic-equivalence proof; never retire an unmet usefulness requirement |
| 13 | Shared shell | Responsive/navigation/focus/overlay contracts are decided before R4-A; implementation follows the first dependent surface; final polish is last |
| 14 | Guard ratchet | `IF_GUARD_CEILING` 23 is the current ceiling; it may be lowered by legitimate removal, never raised to hide an unexecuted check |

---

## Current Truth

**Accepted baseline:** `origin/ux-leftover-wave0` = `bd91ed6`, containing the
accepted Wave 1A tip `5dd0baa`. Application code is `5dd0baa`; `bd91ed6` is
documentation only.

| Item | Verified state |
|---|---|
| Wave 1A | Complete: G5 gate committed, BROKEN 978px at `b868da8`, PASS 884px at `8907ad5` |
| Wave 1B | Packets prepared and published; **no empirical data** |
| Full browser fleet | 67 passed / 0 failed / 1 skipped, 1663 checks (68 scripts including live-only `gun_pen_audit`) |
| Python | 2295 passed / 3 skipped on Windows; Linux 2294 / 4 with named skip reasons |
| Node | `npm test` 198/0 |
| Inventory | 67 default-selected browser scripts; 68 total |
| R0 | Partial: 2 `:root` blocks, 20 `body.dawn`, off-token literals, ~23 dead fallbacks |
| R4 | Not started; no signed surface brief |
| R5 | Not started; View Transitions undecided |
| R6 | Partial: structural rail retired; preview labs and `#pane-divider` remain |
| T ledger | T1/T5/T7 done; T6 folded into R0; T2/T3/T4/T8/T9/T10/T11 open or partial |
| Deferred UIs | Items 1–10 in `UI_CHANGES_DEFERRED.md`; item 3 is already shipped as the stage ladder |
| Arena lane | Branch is `arena/e6a57b71-screenplay-studio`; do not create, switch, reset or clean. Dated review state (2026-10-21): HEAD `5c1b953`, remote `1639fd6`, pre-existing modified/untracked files. Branch name passed; baseline/revision and working-tree readiness were unresolved. This is evidence to re-check, not a permanent instruction: after an owner-authorised recovery, a fresh preflight must establish `READY`. |
| External lane | `origin/ux-leftover-wave0` contains `bd91ed6`; workers may branch from it in a separate worktree |

**Known stale references to correct in this plan:** the old programme plan says
“66-suite fleet” in Wave 6 and has unchecked Wave 1A boxes that are already
complete. Final acceptance must use the discovered inventory, not a hardcoded
count.

---

## Scope

### In scope

- R0 token-layer completion and encoding debt.
- R4 briefs and implementation for every live surface.
- R5 motion and polish.
- R6 removals, IA homes, and the T ledger.
- All remaining deferred UIs:
  1. Knowledge-base browser
  2. Genre detection visualization
  3. Stage ladder (verification only — already shipped)
  4. Rules confidence-tier badges
  5. Writer feedback (thumbs)
  6. Scene cards view
  7. Character arc visualization
  8. FDX analysis-results export
  9. Quick analysis mode
  10. Real-time feedback (finding batches at completed-pass boundaries)
- Final acceptance and documentation receipts.
- Validation handoff for the writer sitting, IMPACT calibration, and quote
  threshold.

### Out of scope

- A new framework, bundler, build step, database, threading model, or cloud
  service.
- New environment-variable guards.
- Automatic confidence adjustment from writer feedback.
- Invented participants, screenplay pages, register material, screenshots, or
  calibration results.
- Agent merges into `main`, the protected Windows checkout `E:\screen_play_astra`,
  or the Arena branch without owner instruction.

---

## Non-Negotiables

- No build step. No framework. No bundler.
- All outbound URLs remain loopback-only unless the process-level remote opt-in
  is set. Never hand-roll a third loopback predicate.
- Browser acceptance is DOM/text/computed-style/geometry only. No screenshots.
- `bottom < 900` stays `< 900`; no evidence clamp, font reduction, hidden
  observation, or coverage deletion.
- Every browser receipt names the served revision and the actionable finding
  identity.
- One primary writer per shared SPA file. A second writer must wait for a clean
  merge or work only in a non-shared file.
- Findings’ array position is the index. Do not add an `index` field.
- `escapeHtml()` is the one render-boundary escape; no data-built event handlers.
- `jsonio.atomic_write_json` plus `jsonio.lock_for()` for every writer-owned
  store; one lock direction only.
- `IF_GUARD_CEILING` 23 is the current ceiling. Lower it when guards are
  legitimately removed; never raise it to hide an unexecuted check.
- Asset `?v=` tokens are automatic; never hand-bump.
- Full Node command is `npm test`; `node --test tests/js/` is not acceptance.
- Writer validation and calibration are owner tasks; do not fill blanks.
- UI surfaces render from persisted parse/report data; do not add a model call
  merely to paint a surface. D09 quick mode is the explicit exception.
- Owner design review uses the live app at the named viewports; do not create
  screenshot artifacts as evidence.
- Stop and report a blocker rather than inventing a design, API shape, finding,
  participant answer, or model result.

---

## Operating Model

### Workspace lanes

**Arena lane (this session and any agent launched inside it):**

- Stay on `arena/e6a57b71-screenplay-studio`. Do not create, switch, rename,
  reset or clean branches and do not assume a worktree.
- Preflight runs three separate checks:
  1. `LANE_MISMATCH` — branch name is not the approved Arena branch.
  2. `BASELINE_MISMATCH` — branch is correct, but HEAD/base is not aligned with
     the published baseline and the owner has not authorised recovery.
  3. `DIRTY_TREE` — tracked or untracked changes are present. Preserve and
     compare them against published history; never reset, delete, stash-and-
     drop, or commit them as new work without owner authorisation.
- A correct branch name alone is not readiness. The lane must also pass the
  baseline and working-tree checks, or be explicitly marked blocked.
- Recovery is an owner-authorised procedure: preserve the existing files,
  compare them with the published baseline, then align the accepted revision
  through integration. A blocked receipt is not acceptance.
- Commit/push only on the owner’s explicit instruction. Never merge.
- `E:\screen_play_astra` is a separate Windows checkout and is not modified by
  this lane; its `main` state does not describe this Arena session.

**External/worker lane (only where branch creation is available):**

- Initial checks run before setup: verify `bd91ed6` is reachable and the chosen
  paths do not already hold a worktree.
- Integration branch: `ux-completion`, created from `bd91ed6`.
- Integration worktree: `C:\tmp\uxc\integration`.
- Optional agent worktrees: `C:\tmp\uxc\writer`, `C:\tmp\uxc\tests`,
  `C:\tmp\uxc\backend`.
- Task branch naming: `task/UXC-<id>-<slug>`.
- Post-setup verification: the integration worktree reports branch
  `ux-completion` and base `bd91ed6`; the original checkout is unchanged.
- Agents commit and push their task branch. The owner merges into the lane’s
  approved target (`ux-completion` for external work; the Arena branch only on
  owner instruction for Arena work). No agent merges to `main`,
  `ux-leftover-wave0`, or the Arena branch.
- After a merge, the owner updates the other worktrees before new work starts.

A packet must name its lane. A packet that cannot run in the Arena lane without
a branch switch is not an Arena packet.

### Agent roles

| Role | Owns | May not |
|---|---|---|
| Integration Writer (IW) | Shared SPA files, surface implementation, final integration | Merge; change design outside a signed brief; touch calibration constants |
| Test/Evidence Agent (TE) | Tests, receipts, docs, audit reports, isolated test-only fixes | Edit product files while IW holds the shared-file lane |
| Backend/Audit Agent (RB) | Independent Python modules, API/data spikes, dependency audits | Edit `webapp_server.py` concurrently with IW; merge |
| Owner | Surface briefs, wave merges, scope/design decisions, empirical data | Delegate final design taste or invent calibration answers |

With only two agents, TE also takes the RB read-only audit work; backend code
waits for the IW lane. An Arena agent works on the approved Arena branch; an
external agent uses a task branch. Both obey the same shared-file serialization.

### Packet contract

Every execution packet must contain:

1. **ID, title, owner, dependencies** and the branch it starts from.
2. **Outcome:** one testable deliverable, not a theme.
3. **Files and interfaces:** exact create/modify paths; consumed and produced
   symbols.
4. **Preconditions:** signed surface brief for any UI packet; baseline receipt
   for any gate.
5. **Test-first steps:** failing test or browser check, command, expected
   failure, minimal implementation, expected pass.
6. **Acceptance evidence:** exact command, revision, expected count, and the
   artifact path for the receipt.
7. **Stop conditions:** what forces a stop instead of improvisation.
8. **Commit boundary:** one independently reviewable commit or a small series.
9. **Handoff:** what the next packet may rely on.

No packet may contain “TBD”, “handle edge cases”, or “similar to Task N”.
If a design or API shape is not decided, the packet is a **spike** with a
written decision and an owner gate, not an implementation packet.

### Evidence standard

- Names the served revision and, for finding work, the finding identity.
- States the exact command and the observed counts.
- Distinguishes baseline counts from post-change counts.
- Does not call a suite green if a setup step was skipped.
- Records environment flakiness separately; a retry is not a pass unless the
  suite itself is deterministic.
- Classifies files by their actual consumers, not their directory; a `docs/`
  path read by runtime or tests is not documentation-only.
- Updates stale docs in the same wave as the change.

### Definition of ready

Except for FND-01’s read-only preflight, a packet may start only when:

- the packet’s lane preflight is `READY`;
- its dependencies are merged into the packet’s **target lane branch** (Arena
  branch or `ux-completion`);
- its files are not held by another writer;
- any UI brief is signed;
- the baseline command for its gate has a recent receipt at the served
  revision;
- the agent has the packet’s exact branch, files and stop conditions.

FND-01’s read-only checks may run while blocked because they establish readiness.
Its receipt and every other write require `READY` and owner authorization.

If any item is missing, the agent reports the blocker; it does not substitute a
guess.

### Integration checklist (owner only)

Before merging an external task branch — or accepting an Arena commit series —
check:

- [ ] Branch is based on the current target-lane tip: the Arena branch
      `arena/e6a57b71-screenplay-studio`, or `ux-completion`.
- [ ] The diff contains only the packet’s declared files.
- [ ] The commit series is reviewable and has no unrelated cleanup.
- [ ] The packet’s gate is green at the branch tip, with the served revision
      named and verified.
- [ ] No screenshots, runtime data, credentials, or generated projects are staged.
- [ ] Docs and counts are updated in the same branch.
- [ ] The owner has signed any changed surface brief.
- [ ] The merge is followed by the wave gate on the target-lane tip.
- [ ] Other worktrees are updated before new work starts.

### Global stop conditions

Stop and report instead of improvising when:

- the packet’s lane preflight is not `READY`;
- a UI packet has no signed brief;
- a gate is red, flaky, or cannot be run;
- the change would lower a gate, hide evidence, or invent a percentage;
- a deferred UI’s required data/API does not exist and its audit has not decided
  build/extend/retire;
- a shared file would have two writers;
- empirical validation is missing and the task is a validation task;
- finding identity, lock order, privacy, or XSS invariants would be weakened.

### Rollback

Each packet lands as one revertible commit or a small ordered series. A rollback
is `git revert` of that series on the packet’s target lane branch, followed by
the wave gate. Never reset or force-push a shared branch. On the Arena lane,
rollback requires the owner’s explicit instruction.

---

## Sequence and Gates

```
G0 Foundation + shared-contract decisions
  -> G1 R0 token layer
  -> G2 R4 core surfaces (brief -> sign -> implement)
  -> G3 R4 remaining surfaces + R4-E final polish
  -> G4 Deferred UIs (host-surface features, then standalone/backend features)
  -> G5 R5 motion
  -> G6 R6 removals + T ledger
  -> G7 Final acceptance

V1 writer sitting ----\
V2 IMPACT calibration --+--> owner-gated parallel track; never blocks G1-G7
V3 quote threshold -----/
```

**Gate rule:** a wave gate is not a blanket prerequisite for every packet. A
packet starts when its own dependencies and the Definition of Ready are met.
A wave gate closes when its exit evidence is recorded and the owner has merged
it. A failed gate stops every packet that depends on it; it is never waived.

### Critical path and parallel map

| Lane | Work | May run beside |
|---|---|---|
| A (serial core) | Foundation -> R0 -> R4-S shared contracts -> R4-A -> R4-B -> R4-C -> R4-D -> R4-E final polish -> R5 -> R6 -> FIN | nothing that edits shared SPA files |
| B (test/evidence) | Verify/re-baseline evidence, surface gates, receipts, docs, final inventory | A, but tests must name the revision they ran |
| C (independent backend/audit) | FND-04/FND-05 audits; D01/D08/D09/D10 backend modules | A only when `webapp_server.py` is not being edited |
| D (deferred host integration) | D01/D02/D04 after R4-A; D05/D06/D07 after their host surfaces | A only through a non-shared module or after the host surface merges |
| V (owner) | V1/V2/V3 when inputs exist | Everything; never blocks A |

R4 brief drafting may overlap R0, but R4 implementation waits for R0’s gate.
Deferred-UI briefs may be drafted during R4, but code waits for the host surface
and the owner’s build/extend/retire decision.

Dependencies are packet-level, not a blanket “previous wave must finish.” Early
audits/contracts and independent backend work may overlap. Host-surface
integration waits for the surface it decorates. R4-S shared-contract decisions
must be signed before R4-A; R4-A may implement only the parts it needs. R4-E is
final cross-surface polish, not the first time shared behavior is decided.

---

## Phase 0 — Foundation

**Exit:** a frozen workspace lane, a re-baselined inventory, signed audit and
shared-shell contract decisions, the surface-brief template, and an executable
packet index. No product change.

**Expanded packet:** `docs/superpowers/plans/2026-10-21-ux-foundation.md`
(FND-01..FND-07).

| ID | Outcome | Owner |
|---|---|---|
| FND-01 | Classify Arena lane branch/base/tree; create and verify `ux-completion` and worktrees only for the external lane | Owner/IW |
| FND-02 | Verify existing receipts and runtime/test/config equivalence; re-run only with a recorded reason; record inventory and capture the FND-01 lane receipt | TE |
| FND-03 | Live-surface inventory, surface-brief template, five-axis checklist | Owner/IW |
| FND-04 | Audit T1–T11, including T4 finding-data flow and T9 load-error honesty, plus preview-lab dependencies | RB |
| FND-05 | Audit deferred-UI data/API feasibility and overlap | RB |
| FND-06 | Correct stale references in current instructions (66 vs 67/68, checkboxes); preserve dated receipts | TE |
| FND-07 | Shared-shell contracts: responsive, navigation, focus/Escape, overlays, component boundaries | Owner/IW |

**FND-04 decision rule:** if a surface needs router/store extraction or a
finding-model change, schedule that dependency before the affected surface;
otherwise defer it to G6. Do not perform a speculative global refactor.
**FND-05 decision rule:** for each deferred UI, record build / extend / retire
with evidence. A duplicate of an existing shipped control is extended or
retired, never rebuilt beside it.

---

## Phase 1 — R0 Token Layer

**Exit:** one token layer; token work is pixel-neutral; mojibake is a separate,
text-accepted commit; full fleet/pytest/Node green; no visual regression
claimed without a receipt.

| ID | Outcome |
|---|---|
| R0-01 | Re-measure token counts and record the census |
| R0-02 | Consolidate night/dawn token blocks; keep one source at the top |
| R0-03 | Normalize off-token hex/rgba values into named tokens; keep intentional primitives |
| R0-04 | Remove dead fallbacks only where evidence proves they cannot fire |
| R0-05 | Repair visible mojibake separately; text acceptance |
| R0-06 | Pixel-neutral gate: layout audit, journey, phase12, smoke, full fleet |

R0 may not change spacing, type size, colour values, or layout except where a
token substitution is byte-equivalent in computed style. Any visible correction
is split into R0-05.

---

## Phase 2 — R4 Surfaces

**Exit for each surface:** signed brief, implementation packet, surface gate,
journey leg, viewport check, and a receipt. No brief, no code.

Surface groups and order:

| Group | Surfaces | Why this order |
|---|---|---|
| R4-S | Shared shell contracts | Decide responsive rules, navigation, focus/Escape, overlay relationships and component boundaries before they invalidate a signed surface |
| R4-A | Manuscript workspace, scene index, desk toolbar, Evidence dock/fix queue, feedback room | Core writing loop; G5 regression lives here. Preserve the accepted queue unless the brief names a specific improvement |
| R4-B | Welcome desk, shelf, library, ideas, premise view | Entry and project lifecycle; confirm premise entry/return paths in FND-03 |
| R4-C | Idea canvas, spark wall | Idea-stage flow |
| R4-D | Revision, Compare, Beat Board, Reader, Flow | Structural tools; depend on manuscript/nav |
| R4-E | Partner drawer, selection floats, command palette, status strip, responsive shell | Final cross-surface polish after dependent surfaces; no late shell rewrite |

FND-03 confirms the live surface inventory against the shipped app. A surface
that has been retired is not rebuilt because an old document names it; the
brief records the retirement instead. The inventory also confirms the premise
view’s actual entry and return paths and names the accepted queue as a preserved
component for R4-A.

Every brief must state:

- the surface’s job and the writer moment it serves;
- current structure and the five-axis baseline;
- explicit deviations from that baseline;
- layout and flex-basis budget;
- components and states, including empty/loading/error/damaged stores;
- type, density, colour-token and dawn/night behaviour;
- keyboard, focus, Escape and reduced-motion behaviour;
- responsive behaviour at 1440x900, 900x1200 and 390x844;
- data/API dependencies and no-model boundaries;
- test plan and the exact surface gate;
- what the brief deliberately does **not** change.

Owner sign-off is recorded in the brief as `SIGNED: <date> <initials>` after a
live-browser review at the named viewports. A change to a signed brief reopens
sign-off.

---

## Phase 3 — Deferred UIs

**Exit:** every remaining deferred item is built, extended, or retired with an
owner-approved decision; item 3 is verified only; no duplicate control ships.

| ID | Item | Host / dependency | Required decision before code |
|---|---|---|---|
| D01 | KB browser | New read-only rules list/search API; Craft lens | API shape and 263-rule paging |
| D02 | Genre visualization | Coverage + genre findings | Do not invent a confidence score if none exists |
| D03 | Stage ladder | Already shipped | Verify only; no new progress bars |
| D04 | Confidence-tier badges | `rule_id` + KB `confidence_tier` | Label as rule tier, not finding certainty |
| D05 | Writer feedback (thumbs) | Existing verdict/intent channels | Prove semantic equivalence before retire; distinguish correctness, intent and usefulness; no auto-confidence; storage contract |
| D06 | Scene cards | Scene summaries + beatboard reorder API | Extend Beat Board or add a tab; no duplicate reorder |
| D07 | Character arcs | `/characters` + report character data | Plot only available data; no fabricated emotional scores |
| D08 | FDX analysis export | Existing script FDX export | Spike the FDX notes/report mapping; preserve script export |
| D09 | Quick analysis mode | Pipeline categories/rules | Schema-compatible partial report; no silent quality claim |
| D10 | Real-time feedback | Pipeline events + existing SSE pattern | Actual finding batches at completed-pass boundaries; provisional/final contract; no fake percentages, no WebSocket-by-default |

D01/D02/D04 should follow R4-A because they live in the Evidence/Craft lens.
D05/D06/D07 follow R4-A/R4-D. D08/D09/D10 are backend-first and may run in
parallel with R4 only through independent modules, never while IW holds
`webapp_server.py`. D10’s contract must be signed before implementation:
provisional versus final findings, stable identity/dedupe/reconciliation,
verification/admission state and honest counts, cancellation/retry/re-analysis,
and withdrawn/revised findings.

### Deferred-UI constraints

- No new dependency for charts; use inline SVG or the existing canvas/CSS.
- No auto-adjustment of confidence; feedback is a record, not a policy change.
- No duplicate controls: writer thumbs may be retired only if a semantic-
  equivalence record shows an existing behavior fulfils the usefulness
  requirement; correctness (`verdict`) and intent (`intent`) are not the same
  question. The record names the original requirement, the fulfilling behavior,
  storage/consumers, supporting tests and owner approval. Retire duplicate UI,
  never an unmet feedback requirement.
- Quick mode must produce the same report/finding schema and honest partial
  status; it may not silently claim full coverage.
- Real-time means **actual finding batches at completed-pass boundaries** through
  the existing event/SSE pattern, not token-by-token analysis and not
  invented per-pass percentages. Progress-only is an explicit scope reduction,
  not D10. If the batch contract cannot satisfy the owner’s definition, stop for
  an owner decision; do not add a WebSocket or thread model by implication.
- FDX analysis export must not break the existing working-copy FDX round trip.

---

## Phase 4 — R5 Motion

**Exit:** deliberate, reversible motion; reduced-motion safe; no transition that
delays the writing loop.

| ID | Outcome |
|---|---|
| R5-01 | Motion spec: durations, easings, spotlight moments, reduced-motion table |
| R5-02 | View Transitions go/no-go with a measured orientation benefit |
| R5-03 | Gate: phase12, journey, reduced-motion, relevant surface suites |

R5 runs after R4 so motion is applied to stable surfaces, not rewritten twice.

---

## Phase 5 — R6 Removals and T Ledger

**Exit:** every removal has a dependency proof and migrated assertion; the T
ledger is closed by implementation or a recorded, owner-approved decision; full
fleet/pytest/Node green.

| ID | Outcome |
|---|---|
| R6-01 | Preview-lab dependency audit, assertion migration, removal/retention decision |
| R6-02 | `#pane-divider` / legacy `.desk` fate; remove or document |
| R6-03 | T2 router/store audit; extract only if a surface needs it |
| R6-04 | T3 retire clean-URL/catch-all goal; keep hash routing |
| R6-05 | T4/T8 dynamic-text escaping and finding-model audit; convert unsafe sinks |
| R6-06 | T9 404-vs-real error honesty audit and fixes |
| R6-07 | T11 `renderManuscript` measurement and decision |
| R6-08 | Deferred-UI homes: confirm built, reserved, or explicitly retired |

Preview removal is last in the wave: R4 may still need the prototypes as design
references. Migrate surviving assertions before deleting any preview test,
route, or `.mjs` coverage.

**T-ledger closure rule:** an item closes by implemented evidence or by a
recorded owner decision that the obligation is retired/changed with proof. “Not
needed” without a dependency audit is not closure.

---

## Phase 6 — Final Acceptance

**Exit:** all engineering packets accepted, all gates green, docs revision-
anchored, and validation status explicitly recorded (not invented).

| ID | Outcome |
|---|---|
| FIN-01 | Discover inventory and run the full default fleet; run live-only suites if a model is available; record counts and skips |
| FIN-02 | Run pytest and `npm test`; record counts and skips |
| FIN-03 | Viewport matrix 1440x900 / 900x1200 / 390x844; keyboard; reduced motion |
| FIN-04 | Docs close-out: plan, status ledger, testing counts, no stale claims |
| FIN-05 | Second writer sitting handoff (owner-gated; may remain not run) |

Final acceptance corrects the old “66-suite / journey 49” wording to the
discovered inventory and current journey count. It does not claim a percentage.

---

## Validation Track (Owner-Gated)

This track runs beside engineering and never blocks G0-G7.

| ID | Work | Gate |
|---|---|---|
| V1 | Writer sitting, 13 blank questions | Real writer, consent, permissioned full draft + report |
| V2 | IMPACT calibration | Live loopback model, real report, blinded writer judgments |
| V3 | Quote-threshold calibration | Authentic Hindi/Telugu/Tamil material + qualified adjudicators |

Rules: local-only records; participant IDs; no fabricated answers; no threshold
change without a measured replacement; `0.72` remains until approved.

---

## Required Commands

Run from the integration worktree unless a packet says otherwise.

```powershell
python tests\run_browser_suites.py
python tests\run_browser_suites.py <suite-name-substring>
python -m pytest tests\ -q
npm test
node --check screenplay_studio\webapp\app.js
git diff --check
```

Baseline counts are not acceptance counts after new tests are added. Re-baseline
at the start of each gate and record both numbers.

---

## Definition of Done

**Engineering accepted** when:

- Every packet in FND/R0/R4/D/R5/R6/FIN is accepted.
- Every R4 surface brief is signed and its surface gate is green.
- Every deferred UI is built, extended, or retired with an owner decision.
- D10 delivers finding batches at pass boundaries, or its scope reduction is
  explicitly owner-approved and recorded.
- Full default browser fleet, pytest, and `npm test` pass with no unexplained
  skips.
- No stale counts, unchecked completed work, or unverified claims remain.
- The final docs index the evidence by revision.

**Writer-validated** and **calibrated** are separate statuses. V1-V3 may remain
unrun; the final report must say so. “Engineering accepted” does not mean
“writer-validated” or “calibrated.”

---

## Risks and Self-Critique

1. **Scope is very large.** R4 plus all 10 deferred UIs plus T2/T4 is more than
   a single agent pass. The packet model is the mitigation; a single mega-plan
   would hide dependencies.
2. **Deferred UIs are not all UI.** D05, D08, D09 and D10 need storage, export
   or pipeline work. Their packets must not pretend to be CSS changes.
3. **Writer thumbs overlaps the shipped verdict channel.** Correctness, intent
   and usefulness are different questions. Building both without a semantic-
   equivalence audit creates two truths; retirement is allowed only for a
   genuinely duplicate UI.
4. **Real-time feedback is larger than progress.** The plan requires actual
   finding batches at completed-pass boundaries, with provisional/final,
   identity, dedupe and cancellation contracts. Progress-only is a scope
   reduction, not a pass.
5. **Design sign-off is the bottleneck.** Agents can draft briefs, but only the
   owner can settle taste. The plan stops before code without a signature.
6. **T2 extraction is a high-risk refactor.** The plan audits first and only
   extracts when a surface needs it; it does not perform a speculative rewrite.
7. **Preview removal can delete design capital.** R4 may still need the labs;
   removal is last, with migrated assertions.
8. **The fleet is not 66 suites.** Final acceptance must discover 67 default /
   68 total and the current journey count; stale numbers are a plan defect.
9. **Windows/browser flakiness is real.** `trust_line` has a port-8099 boot
   flake; a retry is not a pass unless the suite is deterministic.
10. **No live model means IMPACT cannot run.** Engineering proceeds; V2 remains
    blocked and must be reported as blocked, not passed.
11. **Agent collisions.** Shared SPA files are serial. External workers use
    worktrees/task branches; the Arena lane stays on its approved branch and
    never switches. Owner-only merges are the collision barrier.
12. **This master plan is not a substitute for signed surface briefs.** It
    defines the gates and packet shape; the visual decisions remain owner-
    approved artifacts.
13. **Arena readiness has three separate checks.** At the 2026-10-21 review the
    branch name was correct; HEAD/base and the dirty tree were not. A packet
    must not “repair” that by switching, resetting, cleaning or committing
    recovered files as new work. A blocked lane is not foundation acceptance;
    after authorised recovery, re-run the preflight rather than inheriting the
    dated snapshot.
14. **The guard ceiling is a ceiling, not a quota.** Lowering 23 after a
    legitimate guard removal is allowed; raising it to accommodate an
    unexecuted check is not.

---

## Review Checklist

- [ ] Surface grouping and order accepted, including R4-S shared contracts.
- [ ] Foundation gate accepted as no-product-code and includes live inventory.
- [ ] R0 pixel-neutral scope accepted.
- [ ] R4 brief-first rule accepted.
- [ ] Deferred-UI build/extend/retire rule accepted.
- [ ] D10 finding-batch scope accepted; progress-only is not D10.
- [ ] Arena lane branch/revision/tree checks and external-worktree rules
      accepted.
- [ ] Guard-ceiling rule accepted.
- [ ] Definition of done separates engineering accepted, writer-validated and
      calibrated.
- [ ] No task in the expanded packets may proceed without its brief/gate.
