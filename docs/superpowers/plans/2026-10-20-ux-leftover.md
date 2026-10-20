# UX Leftover Programme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining queue acceptance and UX architecture/redesign work
(G5, R0, R4–R6, the T ledger and deferred-UI homes) without lowering a gate,
inventing evidence, or losing shipped behavior.

**Architecture:** Queue acceptance is a separate engineering wave: commit the G5
gate and a deterministic fixture first, capture the red receipt, then make one
measured presentation change at a time. R0 is the pixel-neutral token layer. R4
is a sequence of per-surface briefs, each with its own gate. R5 motion and R6
removals follow. Calibration and writer validation are owner-gated empirical
work that runs beside the engineering waves, not inside them.

**Tech Stack:** Python 3 (stdlib-first), Flask, vanilla JS/CSS (no build step),
Playwright, pytest, Node `npm test`.

---

## Global Constraints

- **No build step.** No framework, no bundler, no node build.
- **Privacy:** every outbound URL stays loopback unless the process-level
  `--allow-remote-server` / `SCREENPLAY_STUDIO_ALLOW_REMOTE_SERVER=1` opt-in is
  set. Do not add another loopback predicate.
- **Browser acceptance is DOM/text/computed-style/geometry only.** No
  screenshots.
- **No gate lowering.** `bottom < 900` stays `< 900`; no evidence clamp, font
  reduction, hidden observation, or coverage deletion may be used to pass it.
- **No revision mismatch.** A browser receipt must name the served revision and
  the result must be reproducible at that revision.
- **One revertible commit series per wave/surface.** Not one commit per wave; a
  series is allowed when each step is independently reviewable.
- **One primary writer per shared file.** `app.js`, `style.css`,
  `webapp_server.py` stay serial. Parallel agents only on independent tests/docs.
- **Full Node command is `npm test`.** It includes
  `screenplay_studio/webapp/preview-ink-layer/tests/*.test.mjs`; `node --test
  tests/js/` is a subset and must not be used as the acceptance command.
- **Browser inventory is discovered, not hardcoded.** 67 `e2e_browser_*.py`
  scripts; 66 run by default; `gun_pen_audit` needs a live studio/model.
- **Asset cache-bust is automatic.** `index.html` `?v=` tokens are placeholders
  rewritten by `webapp_server._stamp_asset_versions`. Never hand-bump them.
- **No new environment-variable guards.** The guard ceiling stays 23.
- **Flag, don't drop.** Unverifiable findings are flagged, never silently
  removed.
- **Writer validation and calibration are owner tasks.** Do not invent
  participants, dates, screenplay material or register examples. Track owner
  waiting time separately from active engineering time.

## Status Ledger (verified 2026-10-20)

| Area | State | Evidence |
|---|---|---|
| R1 type/spacing | shipped | `844eab8`, `a7b02e9` |
| R2 primitives | shipped | `86a8927`, `fd369c5` |
| R3 composites | shipped | `9d1455c` |
| R0 token layer | partial | 2 `:root` blocks, 20 `body.dawn`, off-token literals remain; R0.1/0.4/0.6/0.7 recorded |
| R4 surfaces | not started | no surface brief signed |
| R5 motion | not started | View Transitions undecided |
| R6 removals | partial | structural rail retired; `#pane-divider` and preview labs remain |
| T1 symbol guard | done in substance | `tests/test_app_symbol_integrity.py` |
| T2 router/store modules | not done | hash router inline `app.js:2251-2339`; no `router.js`/`store.js` |
| T3 clean-URL catch-all | not done / retire goal | hash routing is the shipped mechanism |
| T4 one finding model | partial | shared row assembly done; 65 `innerHTML` sites |
| T5 shared row assembly | done | `_fixqueue_items` |
| T6 token fold | folded into R0 | duplicate base blocks remain |
| T7 dormant FV | done | deleted; `view:"fv"` redirects |
| T8 escaped dynamic text | partial | `escapeHtml` + CSP shipped; conversion incomplete |
| T9 honest load errors | partial | full 404-vs-real audit open |
| T10 preview labs | open | 6 dirs + API + suites + Node `.mjs` tests |
| T11 render perf | open | no measurement |
| G5 | **PASS 884px** | same grounded finding index 0, 328px card; committed gate at `b868da8` captured **FAIL 978px**; repair `1a207d8` + `8907ad5` |
| Queue acceptance | readiness 116/0, counting 22/0, ungrounded 24/0, layout 37/0, phase6 40/0, width 32/0, xss 36/0, trust 5/0 | `8907ad5` |
| Fleet current | **67 passed, 0 failed, 1 skipped, 1663 checks** | 68 scripts incl. live-only `gun_pen_audit`; baseline at `1639fd6` was 62/4/1 |
| Python / Node | pytest **2295/3**, `npm test` **198/0** | `8907ad5` |
| Writer validation | 13 blank rows | `docs/REAL_WRITER_VALIDATION.md` |
| IMPACT calibration | uncalibrated | live model + writer needed |
| Quote threshold | `0.72` unchanged | authentic register material needed |

**Completion estimates:** core UX architecture/redesign + queue ~50% left; full
scope including deferred UIs and validation ~60–70% left; R4 ~85–90% left. These
are planning estimates, not acceptance percentages.

## File Structure

**New**

- `tests/e2e_browser_g5_fold.py` — committed G5 gate; deterministic seed,
  identity/admission assertions, component geometry, font readiness.
- `docs/superpowers/plans/2026-10-20-ux-wave1a-g5.md` — task-level Wave 1A plan.
- `docs/superpowers/plans/2026-10-20-ux-leftover.md` — this programme plan.

**Modified in Wave 1A**

- `tests/e2e_browser_phase6_evidence.py` — re-point the stale P1.6, severity
  rim, dismiss-row and scene-strip assertions. No product change.
- `tests/e2e_browser_width_budget.py` — open Tier 1, the ungrounded toggle and
  the `marks` disclosure before the doctor gesture.
- `tests/e2e_browser_xss_inert.py` — target the queue row, not `.fix-row`.
- `screenplay_studio/webapp/style.css` — only the measured Option A changes.
- `docs/superpowers/specs/2026-10-15-one-room-ranked-queue-design.md` — gate
  status correction (done in Wave 0).
- `docs/audit/2026-10-20_g5_recovery_options.md` — receipt table after the gate.

**Later**

- `screenplay_studio/webapp/style.css`, `tungsten.css`, `index.html` — R0/R4/R5.
- `screenplay_studio/webapp/app.js` — R0/R4, preview deletion, T ledger.
- `screenplay_studio/webapp_server.py` — only if a preview/route removal is
  proven safe; no new route.
- `docs/REDESIGN_MASTER_PLAN.md`, `docs/audit/ui_ux_restructure_plan_2026-09-20.md`
  — status updates (Wave 0 done).

---

## Wave 0 — Evidence baseline (current)

- [x] **0.1** Re-baseline the status docs to verified facts:
  `docs/REDESIGN_MASTER_PLAN.md`, `docs/audit/ui_ux_restructure_plan_2026-09-20.md`,
  `docs/audit/2026-10-17_simulated_senior_writer_ux_review.md`,
  `docs/REAL_WRITER_VALIDATION.md`, `docs/TESTING.md`,
  `docs/audit/2026-10-20_g5_recovery_options.md`, spec §8.
- [x] **0.2** Discover the gate inventory: 67 browser scripts, 66 default,
  `gun_pen_audit` live-only; `npm test` is the Node contract.
- [x] **0.3** Run the default fleet once and record reds: 62 passed, 4 failed,
  1 skipped. `phase6_evidence` 31/5 (removed `by-category` key, old severity
  badge, old section helper, old dismiss row, scene-strip scroll); `width_budget`
  17/3 (queue rows hidden behind the ungrounded toggle and the doctor gesture
  behind the closed `marks` disclosure); `xss_inert` 33/3 (old `.fix-row`
  selector); `trust_line` boot 404 (5/0 standalone, flake). No fixes in Wave 0.
- [x] **0.4** Design the G5 gate: dedicated suite, deterministic seed, served
  revision, first admitted finding, hidden ungrounded control, font readiness,
  1440×900, default worklist, scroll 0, component rectangles.
- [x] **0.5** Split calibration: IMPACT (live model + writer) vs quote matching
  (model-free / server-free / GPU-free, authentic register goldens).
- [x] **0.6** Scope the T2/T3/T4/T10 and preview-lab dependency audits.
- [x] **0.7** Save this programme plan and the Wave 1A task-level plan.

**Exit:** ledger signed; known-red list recorded; Wave 1A plan approved. No
runtime change.

## Wave 1A — G5 engineering acceptance

- [ ] **1A.0A** Triage `phase6_evidence` 31/5 at `1639fd6`. Re-point the five
  stale assertions: the removed `by-category` key, the severity rim, the
  already-open queue section, the old `.fix-row` dismiss row, and the scene
  strip's scroll subject. No product change.
- [ ] **1A.0B** Re-point `width_budget` 17/3: open Tier 1 and the ungrounded
  toggle so the queue rows exist, then open the `marks` disclosure and target
  the first queue row's doctor button. No product change.
- [ ] **1A.0C** Re-point `xss_inert` 33/3 from `.fix-row` to the queue row
  (`.dock-section-fixqueue .finding-note.queue-row`); keep every payload and
  interaction assertion. No product change.
- [ ] **1A.0D** Re-run `trust_line` (5/0 standalone) and record the fleet boot
  404 as flaky/environmental. If it fails again, capture the studio log/port;
  do not change product behavior.
- [ ] **1A.1** Add `tests/e2e_browser_g5_fold.py` and run it at the gate-only
  commit. Expected **BROKEN 978**; record served revision, finding identity,
  admission, card/component rectangles, lens scroll.
- [ ] **1A.2** If the identity does not match the `1639fd6` receipt (index 0,
  continuity, grounded, 357px card), stop. Fix the fixture/gate before any CSS.
- [ ] **1A.3** Apply Option A candidates one at a time, in this order:
  filter row one line; current-scene strip compaction; panel-head compaction;
  panel hint; remaining non-evidence spacing. Measure after each; keep only
  changes that improve the first-card bottom. Preserve evidence, full rank
  facts, Dismiss retention meaning and pre-action intent help.
- [ ] **1A.4** If the bottom remains `>=900`, stop and propose the next
  evidence-supported presentation change. Do **not** auto-apply Option B. The
  correct card's quote is one line/18px; B leaves short quotes unchanged.
  Collapsing the observation requires separate approval.
- [ ] **1A.5** Re-run the acceptance set: G5 gate, readiness, counting,
  ungrounded, layout, phase6_evidence, width_budget, xss_inert, trust_line,
  loop parity, `npm test`, pytest.
- [ ] **1A.6** Commit the repair as one revertible series; the receipt names the
  gate commit, the test re-points, the repair commit and both bottoms.

**Exit:** G5 gate proves BROKEN→FIXED; `bottom < 900`; phase6/width_budget/
xss_inert re-pointed and green; trust_line 5/0 recorded as a fleet flake; queue
suites green; no product evidence removed.

## Wave 1B — Empirical validation (parallel with R0)

- [ ] **1B.1** Writer sitting prep: correct the stale highs-only question (done
  in Wave 0); owner runs the 13 rows; do not invent answers.
- [ ] **1B.2** IMPACT calibration: live `llama-server`, full screenplay, writer
  judgments about lane/rank usefulness; never demo output.
- [ ] **1B.3** Quote-threshold calibration: authentic Hindi/Telugu/Tamil
  register material, deterministic model-free/server-free/GPU-free harness.
- [ ] **1B.4** Record the decisions; keep the threshold at `0.72` until a
  measured replacement is approved.

**Exit:** empirical decisions recorded. Owner waiting does not block Wave 2.

## Wave 2 — R0 finish

- [ ] **2.1** Fold the base token blocks into one top layer; scoped theme
  overrides; delete the duplicate base blocks.
- [ ] **2.2** Normalize remaining off-token hex/rgba values; token census.
- [ ] **2.3** Repair visible mojibake in a separate commit/suite. Corrected
  text is not pixel-neutral.
- [ ] **2.4** Remove dead fallbacks only with evidence they cannot fire.
- [ ] **2.5** Gate: pixel-neutral checks for 2.1/2.2/2.4; separate text
  acceptance for 2.3; ladder + journey + pytest.

**Exit:** one token layer; no visual change from token work; visible text fixes
accounted for separately.

## Wave 3 — R4 surfaces

- [ ] **3.0** Surface brief template; every deviation from the five-axis
  baseline is explicit; sign-off before code.
- [ ] **3.1** Manuscript workspace + scene index (provisional first surface).
- [ ] **3.2** Welcome desk + shelf/library/ideas.
- [ ] **3.3** Idea canvas.
- [ ] **3.4** Premise / Revision / Compare / Beat Board / Reader / Flow.
- [ ] **3.5** Feedback-room polish only for a documented post-G5 delta.
- [ ] **3.6** Each surface: surface suite + journey + a11y + 1440/900/390;
  Tier 1 changes re-measure G5.

**Exit:** each surface independently green; no shared-file parallel writers.

## Wave 4 — R5 motion

- [ ] **4.1** Motion spec; spotlight moments; reduced-motion behavior.
- [ ] **4.2** View Transitions go/no-go; implement only where it aids
  orientation.
- [ ] **4.3** Gate: phase12 + journey + reduced-motion.

**Exit:** motion is deliberate, reversible and reduced-motion safe.

## Wave 5 — R6 removals + T ledger

- [ ] **5.1** Preview dependency audit: `/api/preview/*`,
  `tests/test_preview_lab.py`, preview browser suites, token/security tests,
  `preview-ink-layer` `.mjs` tests in `npm test`,
  `tests/probe_ink_layer_trap_frame.py`. Migrate surviving assertions before
  deleting.
- [ ] **5.2** T3: retire clean-URL/catch-all as a goal; keep hash routing. T2's
  module extraction and router/state ownership are separate, dependency-audited
  obligations — do not retire all of T2 by inference.
- [ ] **5.3** T4: dependency audit before extraction; preserve shared
  finding-model/render contracts; schedule before affected R4 rewrites if
  justified.
- [ ] **5.4** T8/T9: security and honest-error behaviors remain obligations;
  only the implementation approach may be retired with evidence.
- [ ] **5.5** T11 measure `renderManuscript` on a long synthetic script; decide
  from the number.
- [ ] **5.6** Reserve IA homes for deferred UIs. Writer thumbs is a separate
  feature plan; audit its overlap with verdict/intent controls; no automatic
  confidence adjustment.
- [ ] **5.7** Gate: full fleet + pytest + `npm test`; no dead coverage.

**Exit:** T ledger closed with evidence; preview removal (if any) preserves
obligations.

## Wave 6 — Final acceptance

- [ ] **6.1** Full 66-suite fleet + journey 49 + pytest + `npm test`.
- [ ] **6.2** Viewport matrix 1440×900 / 900×1200 / 390×844; keyboard and
  reduced-motion.
- [ ] **6.3** Second writer sitting after R4.
- [ ] **6.4** Docs close-out with revision-anchored receipts; no stale claims.

**Exit:** all gates green; writer validation recorded; no percentage claim
without evidence.

---

## Decision Register

| # | Decision | State |
|---|---|---|
| 1 | G5 route A only; no automatic B | proposed; needs Wave 1A approval |
| 2 | First R4 surface: manuscript + scene index | provisional; confirm after G5 |
| 3 | Keep hash routing; retire clean-URL/catch-all goal; T2 module extraction separate | proposed |
| 4 | T4 dependency audit before extraction; schedule before affected R4 if justified | proposed |
| 5 | Reserve deferred-UI homes; writer thumbs separate; audit overlap; no auto-confidence | proposed |
| 6 | Writer/model/material owners | pending; do not invent |
| 7 | Five-axis hybrid baseline; briefs name deviations | recorded in `1b86409`; apply in R4 |

## Effort (active engineering only)

| Wave | Days | Share |
|---|---:|---:|
| 0 | 2–4 | 4% |
| 1A | 4–7 | 10% |
| 1B | 2–3 agent + owner wait | 5% |
| 2 | 3–5 | 8% |
| 3 (R4) | 15–30 | 54% |
| 4 | 3–5 | 8% |
| 5 | 4–8 | 8% |
| 6 | 2–3 | 3% |
| **Total** | **35–65** | **100%** |

Two-agent acceleration applies only to independent test/docs work. Shared-file
implementation stays serial. No calendar promise; owner waiting is separate.

## Self-Critique / Residual Risks

1. **G5 fixture fidelity.** If the seeded report does not reproduce the exact
   357px/978 card, the gate measures a different subject. The gate must print
   and assert index/ID/category/groundedness and match the `1639fd6` receipt
   before any CSS; otherwise stop.
2. **Four fleet reds at `1639fd6`, not one.** `phase6_evidence` 31/5,
   `width_budget` 17/3 and `xss_inert` 33/3 are stale selectors/setup against
   the one-home queue; `trust_line` passed 5/0 standalone and is a boot flake.
   That classification is evidence-backed but not yet repaired. Do not call the
   queue suite green before 1A.0A–D.
3. **The fleet may reveal more reds after the test re-point.** Re-estimate R4
   after Wave 1A.
4. **Preview deletion may expand.** The audit may find product assertions inside
   preview labs; migrate first.
5. **Owner waiting is unbounded.** Writer availability, live model and authentic
   material have no dates. Never promise a calendar date.
6. **R4 has no code-level tasks until briefs are signed.** This is deliberate:
   agents must not improvise a visual redesign.
7. **G5 A may fail.** Stop-and-propose is correct, but it requires the owner to
   be available for the next proposal. Do not auto-apply B.
8. **The five axes live in a commit body.** Wave 0 extracts them here; every R4
   brief must restate them.
9. **Effort shares are estimates.** Gates are the truth; percentages are
   planning only.

## Acceptance for This Plan

- Wave 0 is complete when the ledger, known-red list, gate design, calibration
  split and dependency-audit scope are recorded and the Wave 1A plan is saved.
- Wave 1A is complete when the committed G5 gate prints BROKEN at the gate-only
  commit and FIXED `<900` at the repair commit, phase6_evidence is honestly
  green, and all queue acceptance suites are re-run.
- No later wave starts without its brief and its gate.
