# UX Foundation and Audit Packet

> **For agentic workers:** This packet implements Phase 0 of
> `2026-10-21-ux-completion-master.md`. Read the master plan first. Do not write
> product code in this packet. Work only in the lane named below.

**Status:** DRAFT FOR OWNER REVIEW — revision 5 after approval notes on
preflight order and file classification. Published review copy; execution is not authorised. No product change is
authorised by this draft.

**Goal:** Freeze the workspace lane, re-baseline the evidence, inventory the
live surfaces, audit the risky dependencies, and settle the shared-shell
contracts so R0 and R4 can start without guessing.

**Architecture:** Foundation is documentation and read-only inspection. It
produces four decision artifacts: a lane/baseline receipt, a live-surface
inventory and brief template, a dependency/feasibility matrix, and signed
shared-shell contracts. It does not
edit `app.js`, `style.css`, `index.html`, `webapp_server.py`, or any product
test.

**Tech Stack:** Git, Python 3, pytest, Node `npm test`, Playwright gate runner.
Arena commands are POSIX; external-lane path examples are Windows.

---

## Lane Preconditions

### Arena lane

- Approved branch: `arena/e6a57b71-screenplay-studio`.
- Do **not** create, switch, rename, reset, clean or delete branches.
- Do **not** use a worktree.
- The 2026-10-21 reviewed state is: branch correct, HEAD `5c1b953`, remote
  `1639fd6`, pre-existing modified/untracked files. Branch name passed;
  revision and tree readiness did not. Re-check instead of inheriting this
  snapshot.
- Run the three checks below. `LANE_MISMATCH`, `BASELINE_MISMATCH` and
  `DIRTY_TREE` are separate outcomes. A blocked outcome is not acceptance.

### External/worker lane

- Integration branch: `ux-completion`, based on `bd91ed6`.
- Worktree: `C:\tmp\uxc\integration`.
- Task branches: `task/UXC-FND-<id>-<slug>`.
- Agents may commit and push their task branch. The owner merges; agents never
  merge.
- `E:\screen_play_astra` is never used by this lane.
- Initial checks run before setup; the worktree is verified after setup.

### Authorization order

FND-01’s read-only checks are the one exception to the readiness gate: they must
run before `READY` can be established. While the lane is blocked, do not create
the receipt or alter any file; report the classification in the parent channel.
The lane receipt is written only after a `READY` preflight with owner
authorization. FND-02 onward and every write require `READY` and the owner’s
authorization.

---

## FND-01 — Lane and baseline preflight

**Owner:** Owner/IW

**Files:**
- Create after `READY`: `docs/audit/2026-10-21-uxc-lane.md` (receipt)
- If blocked, report the classification in the parent channel; do not create the
  file and leave the foundation gate blocked.

**Steps:**

- [ ] **Step 1: Initial repository check (both lanes, POSIX).**

```sh
git rev-parse --abbrev-ref HEAD
git rev-parse --short HEAD
git status --short --branch
```

- [ ] **Step 2: Record the pre-existing dirty set before writing receipts.**

List every already-modified or untracked path before creating any audit file.
Authorised programme/audit documents — including these plan files and the
receipts — are listed separately; they are not pre-existing dirt and do not make
the pre-existing tree clean. Keep the two lists separate in the receipt:

```text
pre-existing dirty paths:
new authorised audit paths:
```

- [ ] **Step 3: Classify the Arena lane.**

Arena expected:

```text
branch: arena/e6a57b71-screenplay-studio
published Arena remote: 1639fd6
accepted published baseline: bd91ed6 (origin/ux-leftover-wave0)
reviewed local HEAD: 5c1b953
working tree: dirty (pre-existing modifications/untracked)
```

Write the primary outcome and every applicable blocker:

```text
READY                  branch correct, accepted baseline aligned, tree authorised
LANE_MISMATCH          branch is not the approved Arena branch
BASELINE_MISMATCH       branch correct, HEAD/base not aligned
DIRTY_TREE             tracked or untracked changes present
BLOCKED_RECOVERY       baseline alignment needs an owner-authorised recovery
```

`LANE_MISMATCH` or `BASELINE_MISMATCH` is not fixed by switching branches.
`DIRTY_TREE` is not fixed by reset, clean, deletion, stash-and-drop, or
committing the recovered files as new work.

- [ ] **Step 4: Preserve and compare recovered files.**

For every modified/untracked file, record its path and a hash or diff summary,
then compare it with the published history. Do not modify, move or delete the
file in this step. The comparison is evidence for the owner’s recovery decision.

- [ ] **Step 5: Mark the gate.**

`READY` requires the branch, baseline and tree checks to pass. After the owner’s
authorised recovery, this command must exit 0:

```sh
git merge-base --is-ancestor bd91ed6 HEAD
```

At the 2026-10-21 review the state was `BASELINE_MISMATCH` plus `DIRTY_TREE`.
If the current preflight still shows those conditions, record them and stop the
packet; the foundation gate remains blocked. If the owner has since authorised
and completed recovery, accept only a fresh `READY` preflight — do not inherit
the dated snapshot as an instruction to stay stopped.

- [ ] **Step 6: External setup, only after `READY` and owner authorization.**

```powershell
git cat-file -e bd91ed6^{commit}
Test-Path C:\tmp\uxc\integration
git worktree add C:\tmp\uxc\integration -b ux-completion bd91ed6
git -C C:\tmp\uxc\integration status --short --branch
git -C C:\tmp\uxc\integration rev-parse --short HEAD
```

Run `git worktree add` only when `C:\tmp\uxc\integration` is absent. The worktree
must report branch `ux-completion` and base `bd91ed6`; the original checkout
must be unchanged. Do not run these commands in the Arena lane.

**Acceptance:** the receipt persists the lane, branch, HEAD, base/remote,
classification, separate pre-existing/authorised paths, preserved-file summary
(if dirty), and post-setup verification for the external lane. Only `READY` (or
a clean external worktree) satisfies FND-01. A blocked classification is
recorded but explicitly fails the gate.

**Commit:** none here. `docs/audit/2026-10-21-uxc-lane.md` is captured by FND-02
in `docs: baseline UX completion evidence`; add it to that packet’s allowed
files and commit boundary.

---

## FND-02 — Verify the baseline evidence

**Owner:** TE

**Files:**
- Create: `docs/audit/2026-10-21-uxc-baseline.md`
- Capture in this packet’s commit: `docs/audit/2026-10-21-uxc-lane.md` (created
  by FND-01)
- Modify: `docs/TESTING.md` only if its current counts are stale
- Modify: `docs/REAL_WRITER_VALIDATION.md` only if its current counts are stale

**Steps:**

- [ ] **Step 1: Verify the existing receipts first.**

Read `NOTES.md`, `docs/REAL_WRITER_VALIDATION.md`, `docs/TESTING.md`, and the
G5 receipt. Record each receipt’s revision and counts. Do not run a fresh fleet
merely because new planning documents exist.

- [ ] **Step 2: Build the complete change set against the accepted baseline.**

```sh
git rev-parse --short HEAD
git status --short --untracked-files=all
git diff --name-status bd91ed6
git ls-files --others --exclude-standard
```

Classify every changed path:

```text
documentation-only    docs/**, NOTES.md, README, plan/spec text
frontend              screenplay_studio/webapp/**, tests/js/**
backend/runtime       screenplay_parser/, screenplay_analyzer/,
                      screenplay_cowriter/, screenplay_studio/,
                      knowledge_base/, tests/
config/dependencies   pyproject.toml, requirements*.txt, package.json,
                      lockfiles, CI/workflow files
```

Classify by actual consumer, not directory. A `docs/**` file that runtime or
tests read belongs to that consuming class, not documentation-only. The
documentation-only class must be explicit; do not infer it from a frontend
glob. Only when every changed path is documentation-only may all prior receipts
be reused unchanged. Otherwise compare the receipt’s scope with the changed
classes and reuse a receipt only when all runtime/test inputs relevant to that
receipt are equivalent. A frontend-only diff cannot justify reusing backend or
full-fleet results.

A fresh run is justified only when code/tests changed since the receipt, the
environment differs, the receipt is missing, or equivalence cannot be shown.
Record the reason for every fresh run.

- [ ] **Step 3: Discover the browser inventory.**

```sh
ls tests/e2e_browser_*.py | sort
python tests/run_browser_suites.py --help
```

Record the number of scripts, default-selected count, live-only scripts, and
whether the runner reports the served revision. A runner that cannot name the
served revision is an evidence gap; do not claim revision-scoped acceptance.

- [ ] **Step 4: Run the default browser fleet only when justified.**

```sh
python tests/run_browser_suites.py
```

Record the suite counts, total checks, served revision, and exit status. The
drafting baseline is:

```text
67 passed / 0 failed / 1 skipped / 1663 checks
```

Stop for any unexplained missing suite, assertion-count reduction, new skip,
`ERROR`/`TIMEOUT` outcome, nonzero exit, or failed served-revision check.

- [ ] **Step 5: Run pytest only when justified.**

```sh
python -m pytest tests/ -q
```

Record the result and the platform. The drafting baseline is:

```text
2295 passed / 3 skipped
```

The three skips are the non-load-modify-write cases in
`tests/test_store_fault_injection.py`. Linux has those three plus the
Windows-specific open-file deletion case in `tests/test_delete_project.py`
(2294 passed / 4 skipped). Preserve the platform and each skip reason; do not
treat 2295/3 and 2294/4 as equivalent totals.

- [ ] **Step 6: Run Node only when justified.**

```sh
npm test
```

Record the result. The drafting baseline is:

```text
198 passed / 0 failed
```

- [ ] **Step 7: Write the baseline receipt.**

`docs/audit/2026-10-21-uxc-baseline.md` must contain:

```text
revision:
branch:
receipt verified? (path + revision)
changed path classes:
receipt scope:
runtime/test/config equivalence:
reuse decision:
fresh-run reason:
command:
result:
served revision:
skips/failures (with reasons):
platform:
environment notes:
```

Use one section per command. If a suite is flaky, record the port/log and do not
call it a pass.

**Acceptance:** every claim names a receipt revision; the complete change set is
classified; counts and skip reasons are distinguished from the master baseline;
missing suites, reduced checks, new skips, timeouts, nonzero exits and
served-revision failures are not waived.

**Commit:** `docs: baseline UX completion evidence` (includes the FND-01 lane
receipt).

---

## FND-03 — Live-surface inventory and brief template

**Owner:** Owner/IW

**Files:**
- Create: `docs/superpowers/specs/2026-10-21-surface-inventory.md`
- Create: `docs/superpowers/specs/2026-10-21-surface-brief-template.md`

**Steps:**

- [ ] **Step 1: Read the surface sources.**

Read:

```text
docs/UI_UX_SPECIFICATION.md
docs/REDESIGN_MASTER_PLAN.md
docs/PROJECT_OVERVIEW.md
docs/USER_PERSONAS.md
UI_CHANGES_DEFERRED.md
```

- [ ] **Step 2: Enumerate live surfaces from the shipped app.**

Use the shipped SPA's nav/view code and the master inventory. For each surface
record:

```text
name
view id / DOM root
entry path
return path
protecting suite
live / retired / partial
owner
notes
```

At minimum verify: welcome desk, shelf, library, ideas, idea canvas, spark wall,
manuscript workspace, scene index, desk toolbar, Evidence dock, fix queue,
feedback room, premise, revision, compare, beat board, reader, flow, partner
drawer, selection floats, command palette, status strip, responsive shell, and
Stash & Notes. Record separately: the retired structural/left rail and the live
dock lens (`#dock-tab-notes`, `#dock-lens-notes`, surviving `#rail-notes` host
inside the dock). Do not mark the whole Stash feature retired.

- [ ] **Step 3: Resolve the premise path.**

Record the premise view’s actual entry and return path from the shipped code.
If it is retired or partially reachable, mark it `retired` or `partial`; do not
schedule a redesign from an old doc alone.

- [ ] **Step 4: Mark the accepted queue as preserved.**

Record the accepted queue/dock as a preserved component for R4-A. It may change
only if the R4-A brief names a specific improvement and its gate.

- [ ] **Step 5: Write the brief template.**

The template must contain the fields in the master plan:

```text
surface and writer moment
current structure
five-axis baseline
explicit deviations
layout / flex-basis budget
components and states
type / density / dawn-night
keyboard / focus / Escape / reduced motion
responsive 1440x900 / 900x1200 / 390x844
data and API dependencies
tests and surface gate
explicit non-goals
SIGNED: <date> <initials>
```

**Acceptance:** every live surface has a row; premise and queue status are
explicit; a blank brief template exists with a sign-off block.

**Commit:** `docs: inventory live surfaces and add the brief template`

---

## FND-04 — Architecture and dependency audit

**Owner:** RB

**Files:**
- Create: `docs/audit/2026-10-21-uxc-architecture-dependencies.md`

**Steps:**

- [ ] **Step 1: Audit T2 router/store ownership.**

Record the current view/nav paths, hash state, state ownership, and any surface
that cannot be implemented without extraction. Output one of:

```text
do-before-R4
defer-to-R6
retire-with-evidence
```

- [ ] **Step 2: Audit T4 finding data flow, not just `innerHTML`.**

Trace one finding from report/fixqueue through client state, identity/binding,
filters, counts, update paths and each render projection (Evidence dock, queue,
margin/card, export). Record state ownership, mutation sites, dedupe identity,
positional binding, and the boundary at which display data is derived. Then
inventory `innerHTML` sinks and untrusted interpolation. Identify surfaces whose
R4 work would create a new unsafe sink. Do not convert code in this packet.

- [ ] **Step 3: Audit T8 and T9.**

T8: record the dynamic-text/attribute construction sites and the canonical
escape path. T9: audit load-error honesty (missing vs damaged stores, failed
project/report reads, 404 vs real load failure) or name the later packet that
owns it, with the reason it cannot land before R4.

- [ ] **Step 4: Audit T10 preview labs.**

List every preview directory, route, browser suite, `.mjs` test, and product
assertion. Mark each as:

```text
keep-as-reference
migrate-assertion
remove-after-R4
retain
```

- [ ] **Step 5: Audit T11 render performance.**

Record the current `renderManuscript` path and the measurement method. Do not
optimize in this packet.

- [ ] **Step 6: Reconcile every T item.**

The disposition matrix covers T1–T11. Completed, superseded and delegated items
keep linked evidence rather than disappearing:

```text
T1/T5/T7: evidence path + revision + why closed
T6: folded into R0; CSS scope + linked evidence
T2/T3/T4/T8/T9/T10/T11: open/partial + disposition
superseded/delegated: replacing item or owner
```

- [ ] **Step 7: Decide the dependency order.**

For each audit, state whether it must land before a named R4 surface or can wait
for G6. No speculative global refactor.

**Acceptance:** T1–T11 each have evidence, a disposition, and a named dependent
surface or `none`; T4 traces finding identity/state/render boundaries; T9 has an
audit or a named later owner.

**Commit:** `docs: audit UX architecture dependencies`

---

## FND-05 — Deferred-UI feasibility and overlap audit

**Owner:** RB

**Files:**
- Create: `docs/audit/2026-10-21-uxc-deferred-ui-feasibility.md`

**Steps:**

- [ ] **Step 1: Audit each deferred item.**

For D01–D10 record:

```text
original requirement
existing data/API
existing UI overlap
storage / privacy impact
model calls (must be none unless D09)
test strategy
decision: build / extend / retire
owner decision needed
```

- [ ] **Step 2: Resolve known overlaps.**

At minimum:

```text
D05 thumbs vs existing verdict/intent channels
D06 scene cards vs existing beat board
D01 KB browser vs existing rule popover
D02 genre visualization vs coverage text
D04 confidence badges vs verification confidence
D10 real-time vs existing stage ladder
```

- [ ] **Step 3: Record the retirement standard.**

For any `retire` decision, name the original requirement, the existing behavior
that fulfils it, storage/consumers, supporting tests, and the owner approval
needed. A duplicate UI may be retired; an unmet requirement may not.

- [ ] **Step 4: Decide D10’s contract.**

Record the finding-batch fields required before implementation. Batches arrive
at completed-pass boundaries; progress-only is not D10.

```text
provisional / final
stable identity
dedupe / reconciliation
verification / admission
honest counts
cancel / retry / re-analysis
revised / withdrawn findings
```

**Acceptance:** all ten items have a decision or a named owner decision; D05 and
D10 have explicit standards.

**Commit:** `docs: audit deferred UI feasibility and overlap`

---

## FND-06 — Correct stale plan and status references

**Owner:** TE

**Files:**
- Modify: `docs/superpowers/plans/2026-10-20-ux-leftover.md`
- Modify: `docs/TESTING.md` if needed
- Modify: `docs/REAL_WRITER_VALIDATION.md` if needed
- Modify: `NOTES.md`

**Steps:**

- [ ] **Step 1: Mark completed Wave 1A work.**

The Wave 1A boxes are complete at `5dd0baa`; correct the old plan so it does not
read as unfinished.

- [ ] **Step 2: Correct the inventory count in current instructions only.**

Replace “66-suite” / “66 default” wording in current status/index/instructions
with the discovered count:

```text
67 default-selected / 68 total
```

Do not rewrite dated receipts or historical audit narratives: their counts were
correct for their own revisions. Do not hardcode a count in final acceptance;
FND-02 records it.

- [ ] **Step 3: Correct current skip explanations.**

Replace current “Windows-only skips” wording with the named reasons: the three
`tests/test_store_fault_injection.py` non-load-modify-write cases, plus the
Windows-specific open-file deletion case in `tests/test_delete_project.py` that
Linux skips (2294/4). Preserve dated receipt wording.

- [ ] **Step 4: Point the old plan at this programme.**

Add a short header to `2026-10-20-ux-leftover.md`:

```text
Superseded for execution by 2026-10-21-ux-completion-master.md.
Kept for history; do not execute its unchecked boxes.
```

- [ ] **Step 5: Verify doc surfaces.**

```sh
python -m pytest tests/test_doc_surface_hygiene.py -q
git diff --check
```

This test checks retired-surface wording in existing product documents. It does
not inspect these plan files or validate their execution logic.

**Acceptance:** no stale count or unchecked completed Wave 1A item remains; the
old plan points to the new master.

**Commit:** `docs: reconcile UX plan status and counts`

---

## FND-07 — Shared-shell contracts

**Owner:** Owner/IW

**Files:**
- Create: `docs/superpowers/specs/2026-10-21-shared-shell-contracts.md`

**Steps:**

- [ ] **Step 1: Decide responsive contracts.**

Record the layout rules at 1440x900, 900x1200, and 390x844: pane minimums,
dock behavior, mobile sheet, overflow, and which layout is authoritative.

- [ ] **Step 2: Decide navigation and return contracts.**

Record surface entry/return, hash routing, palette destinations, deep links, and
whether a surface is a view or a mode.

- [ ] **Step 3: Decide focus and Escape contracts.**

Record focus entry/return, Escape behavior per overlay, and the difference
between the partner drawer and the Context Dock.

- [ ] **Step 4: Decide overlay and component boundaries.**

Record which shared components are frozen, which R4-S may change, and which
surface owns each overlay.

- [ ] **Step 5: Sign the contract.**

Add:

```text
SIGNED: <date> <initials>
```

No surface implementation starts before this signature.

**Acceptance:** all four contract areas are explicit and signed; no shell
rewrite is implied.

**Commit:** `docs: record shared shell contracts`

---

## Foundation Gate

This packet is complete when:

- [ ] FND-01 lane receipt records `READY`, or a clean external worktree at
      `bd91ed6`.
- [ ] FND-02 baseline receipt exists with revision-anchored counts, complete
      change-set classification, any fresh-run reason, and the FND-01 lane
      receipt committed in the same evidence commit.
- [ ] FND-03 live-surface inventory and brief template exist.
- [ ] FND-04 architecture dependency audit covers T1–T11.
- [ ] FND-05 deferred-UI feasibility audit exists.
- [ ] FND-06 current docs are corrected without rewriting dated receipts.
- [ ] FND-07 shared-shell contracts are signed.
- [ ] `git diff --check` passes.
- [ ] No product file, test behaviour, weight, threshold, or gate was changed.

The 2026-10-21 review found the Arena lane **blocked**, not accepted. If the
current preflight still matches that state, a `LANE_MISMATCH`,
`BASELINE_MISMATCH`, `DIRTY_TREE` or `BLOCKED_RECOVERY` receipt is evidence of
the blocker and fails the Arena gate. A clean external worktree satisfies only
the external lane; it does not make the Arena lane ready. Stop if a required
audit has no evidence or a decision would require a product change.

---

## Handoff

The next packets may rely only on:

- the lane receipt;
- the baseline counts;
- the live-surface inventory;
- the signed shared-shell contracts;
- the dependency and feasibility decisions.

R0 may start after the gate. R4-A may start only after its brief is signed and
the shared-shell contracts are signed. D01/D02/D04 wait for R4-A; D05/D06/D07
wait for their host surfaces; D08/D09/D10 wait for the feasibility decisions.
