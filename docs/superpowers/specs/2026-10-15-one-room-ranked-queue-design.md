# One Room, One Queue — IA and Ranking Spec

**Date:** 2026-10-15 · **Status:** draft for review · **Implements:** agreements #1–#7 of
`docs/debates/2026-10-15_feedback-room-architecture-panel.md` (§4 AGREED LIST, revision 3)
**Branch:** `arena/e6a57b71-screenplay-studio` · **Base:** `da9f135`

> This spec supersedes nothing. It is the build plan for seven agreements that were reached by
> adversarial review, corrected three times, and never yet written down as work.

---

## §0. Scope, non-goals, and falsifiers

**In scope (7 items):** chrome de-duplication (#1–#5), queue membership and ranking (#6, #7).

**Out of scope, with reasons:**

| Deferred | Why |
|---|---|
| #8 mode-aware dock geometry | **Blocked, not deferred.** The 44rem premise fails `tests/e2e_browser_layout_audit.py:442`. Legal dock ceiling is 676px. Needs a measurement spike, not a spec. |
| #9 Coverage/dials out of primary path | Analyzer output shape, not chrome. Separate spec. |
| #10 promote "What's working" | Already renders (`app.js:7446-7451`); it is a Tier 2→Tier 1 move with its own scope. |
| #12 the writer's letter | Needs the writer sitting (`docs/REAL_WRITER_VALIDATION.md`). |
| **Severity semantics** (D2's charge: severity conflates model confidence with craft cost) | **Analyzer-side.** Deliberately *not* silently dropped. Agreement #6 below partially answers it and says exactly where the rest lives. |
| **Verdict line in Tier 1** (two-agent panel's clash-2 ruling) | **Unfunded as written** — see §0.2. Its budget included deleting arrival arithmetic, which agreement #11 protects. |
| **Top-5 rewrite-order stack** | **Declined** — it is the ranked queue's rows 1–5. A second home for five rows is the defect, not the feature (§0.2). |

**Falsifiers. Agreement #13 ("no rewrite") falls if any of these is true, checked before §2:**

1. Any of §2–§6 requires changing the manuscript resize observer contract (currently implicit in
   `#context-dock`'s width transition, `style.css:5507-5516`).
2. §1 or §7 requires a new field on the finding object that whole-row dedupe would silently drop
   (`screenplay_analyzer/dedupe.py:242` keys on `json.dumps(f, sort_keys=True)`).
3. ~~§2–§5 requires editing a pinned `role="tablist"` / `aria-controls` pair.~~
   **FIRED — see §0.1. Agreement #13 survives, narrowed.**

---

### §0.1 Falsifier 3 result: it fired, on four sites, and agreement #13 survives

The first draft asserted falsifier 3 before checking it. Checked, it fires.

`setRoom` is driven **by name** and is load-bearing in three roles unrelated to the tablist:

| Role | Evidence |
|---|---|
| **Route verb** — deep links must keep working | `tests/e2e_browser_deep_links.py:209` drives `setRoom('feedback')` then asserts `location.hash` contains `/feedback` |
| **Return stack** for four full-screen tools | `setRoom(premisePrevRoom)` `app.js:1842`, `setRoom(comparePrevRoom)` `:8307`, `setRoom(revisionPrevRoom)` `:8420`, `setRoom(bbPrevRoom)` `:8738` |
| **Idea-room lens switch** | `applyIdeaLens(room)` inside `setRoom` (`app.js:2614`) |

Driving sites, not one but four:

- `tests/e2e_browser_deep_links.py:209` — `setRoom('feedback')` + route assertion
- `tests/e2e_browser_phase12_visual_motion.py:235` — `setRoom('feedback')`
- `tests/e2e_browser_phase12_visual_motion.py:245` — `setRoom('cowrite')`
- `tests/e2e_browser_readiness_gate.py:563` — `setRoom('feedback'); openRoomDrawer()`

**Ruling: the falsifier fires, but it falsifies the *UI* cut, not the function.** `setRoom` is the
router's verb and the full-screen tools' stack discipline. **It survives intact.** §2 deletes the
tablist that *drove* it, never `setRoom` itself.

**Agreement #13 status: survives, narrowed.** The original claim was "everything ships as deletion
or unification, no rewrite." The narrow, accurate claim is **no new state machine.** §2's cost is
migrating four tests from "drive `setRoom`, expect tablist ARIA" to "drive `setRoom`, expect dock
Evidence lens." The route assertion at `deep_links.py:209` must pass **unchanged**.

That is what the falsifier was for. It fired, the cost is named, and the spec is corrected in text
rather than discovered in CI.

### §0.2 Tier-1 contents: the Top-5 and the verdict line are resolved, not omitted

An earlier draft left Tier 1's contents under-specified while G5 asserted a height against them.
Both disputed blocks are now disposed of, and neither disposition is "forgot it."

**Top-5 rewrite-order stack: DECLINED, because the ranked queue already is one.** After §1.3 the
queue is ordered by craft impact, verification, span, and writer intent. **Rows 1–5 are the rewrite
order.** Rendering a separate Top-5 block above the queue draws the same five findings twice on one
surface, which is the multi-surface duplication this entire spec exists to remove
(`docs/debates/2026-10-15_critique-two-agent-panel.md` §1). A second home for five rows is the
defect, not the feature.

**Verdict line (coverage + logline + counts): DEFERRED, and the cross-panel conflict is named.**
The two panels ruled opposite. The four-expert panel's agreement #9 puts the Coverage verdict, logline
test and comparables **out** of the primary path. The two-agent panel's clash-2 ruling put a verdict
line **in** Tier 1 — funded by deleting *"the arrival strip's arithmetic, the ghosted details, and
the category chips."*

**That funding is void.** This spec deletes the category chips (§7) but **keeps** the arrival
strip, because agreement #11 keeps it, and that question was independently endorsed as settled.
One third of clash-2's budget is protected, so the ruling is unfunded as written. G5 is therefore
asserted against a Tier 1 that does not gain two blocks.

**If the verdict line is wanted later, it is a new argument with new funding** — not a line item
carried over from a ruling that can no longer pay for it.

## §1. Queue membership, lanes, and rank v0

**This is the section that must land first.** Everything in §2–§7 is deletion or relabeling; this is
the only part that changes what the writer is asked to do.

### 1.1 The membership principle

> **Every finding gets exactly one home. Queue membership requires a scene and a verb.
> Script-level and deterministic findings get their own lanes inside the same surface, never a
> deleted surface.**

Argued from repo rules, not taste: `AGENTS.md:66` ("Flag, don't drop"), and the one-home-per-finding
agreement. Replaces the revision-2 "neither" bin, which was struck because it deleted locatable,
one-line-fixable `continuity` findings from a surface whose promise is every fixable note, one home.

### 1.2 Lanes (the disposition of all eight `FINDING_CATEGORIES`, `grammar.py:45-48`)

| Lane | Members | Basis |
|---|---|---|
| **Structure** | `structure`, `plot_thread` | missing turn / event-chain; setup-payoff economy |
| **Line** | `dialogue`, `scene_function` | characters state what is known; the scene changes nothing |
| **Deterministic** | `continuity` (+ any `check_id`) | locatable, `scene_refs` present, one-line fixes |
| **Observation** (not queued) | `theme`, `genre`, and any finding with **no** `scene_refs` | nothing to locate; a thesis or a conformance note is not a task |

`character` is **queued** and binned by span at rank time. It is also in
`SCRIPT_LEVEL_CATEGORIES` (`pipeline.py:589`), so it may arrive with no `scene_refs`, in which case
the observation lane catches it by the principle, not by a special case.

**Closing the "ranked low is a second-class queue" gap.** The deterministic lane is **not** sorted to
the bottom of the queue. It is a **group with equal visual weight and its own group header**, in the
same queue, above the fold. Its purpose is **batching affordance**, not deprioritisation: six
continuity notes are one kind of fix and should be fixable in one pass, which a rank-sorted list
interleaved with structural notes actively destroys. Each lane exposes one batch verb. No lane is
ever below another by default.

### 1.3 Rank v0 (UNCALIBRATED — see §9)

Ranking applies **within a lane only.** Inputs are all fields that exist today.

```
score(f) = IMPACT[f.category] × 10
         + (f.verification && f.verification.status === "verified" ? 3 : 0)
         + (min(sceneRefCount(f), 3) - 1)
         + (findingMarks[findingIds[i]] === "fix" ? 5 : 0)
```

- `IMPACT` — **one hand-authored constant table**, placed beside `CATEGORY_LABELS`
  (`app.js:4232`). It is a judgment stated as reviewable data, which is the entire difference
  between a slogan and a ranking function.
  ```js
  const IMPACT = {
    structure: 5, plot_thread: 5, character: 4,
    scene_function: 3, dialogue: 3,
    continuity: 2, theme: 1, genre: 1,
  };
  ```
- **Verified outranks unverified at equal impact.** Never hides — `AGENTS.md:66`.
- **Span** rewards multi-scene findings. Note this is the *ranking* input only; the earlier
  `scene_refs <= 2 / >= 3` split is **struck as a membership test**. A number that only orders rows
  already admitted needs far less justification than one that decides existence.
- **Writer intent is sticky.** A finding marked fix/park/dismiss keeps its slot; re-sorting a list
  under the writer mid-session is how trust dies.
- **No `check_id` penalty.** It was in the v0 sketch; it is removed, because the deterministic lane
  already segregates those rows (§1.2). Penalising a row twice for the same property is how a
  ranking silently becomes a demotion.

### 1.4 Implementation traps (verified, not speculative)

1. **`scene_refs` is mixed-type.** `findingOnScene` (`app.js:6978-6981`) tests both `refs.includes(n)`
   and `refs.includes(String(n))`. `sceneRefCount` must tolerate numeric and string refs, and the
   span term must never assume numeric values.
2. **Do not fork the predicate.** `findingPassesFilter` (`app.js:6964-6973`) is the ONE filter
   behind ink, board list, loop, and queue. `findingAdmitted`, `findingDisposition`, and the
   scene/severity clauses already live inside it. Adding a lane check anywhere else reintroduces
   GAP-1 (page and ledger disagreeing, verified at 15 cards vs 9 rows).
3. **`findingFilter.category` already exists** (`app.js:6970`) and is a single-category filter. §7's
   clickable group headers set exactly this field. No new filter state.
4. **Group headers must not own a filter the predicates cannot express.** A header toggles
   `findingFilter.category`; it does not filter client-side on its own.

### 1.5 Required output: every row explains its rank

Each queue row renders, on the collapsed row or in its tooltip:

> *ranked here: Structure (impact 5), verified, spans 3 scenes*

That string **is** the acceptance test for §1. A row that cannot print its own reason is not ranked,
it is sorted by something nobody can audit.

---

### 1.6 Cross-lane read order (the gap in "rows 1–5 are the rewrite order")

Ranking runs **within** a lane (§1.3) and lanes carry **equal** visual weight (§1.2). So "rows 1–5
are the rewrite order" is true inside one lane and **undefined across** them.

> **Cross-lane order: Structure → Line → Deterministic. Observation is not queued.**

**RETRACTED after §9a ran: "one table, two projections."** An earlier draft of this section derived
lane order from `IMPACT` maxima, on the reasoning that one table should serve both. The calibration
run falsified it. See §9a: calibrating `IMPACT` to Expert D's own craft ordering
(structure 50 > dialogue 40 > character 30 > plot_thread 20 > scene_function 10) puts **Line above
Structure**, because D3 ranks exposition above dangling setup and those live in different lanes.

**The retraction exposes a real category error in the original claim.** Two different questions were
being merged:

| Question | Answered by |
|---|---|
| "What kills a script?" | Expert D's craft list (§1.3 `IMPACT`) |
| "If I can only fix one thing, what is it?" | lane order — **fix upstream before downstream** |

D3 ranks by the first. Structure-first is the second. They need not agree, and forcing one to derive
from the other was the error. **Lane order is a declared product decision with its own rationale, not
a projection of the impact table.**

Three properties, restated so they are testable:

1. **Stable across runs.** Lane order is declared, never recomputed per script. A queue that
   reorders itself between sessions cannot be learned.
2. **Upstream first.** Line work in a structurally broken script is discarded by the structural fix.
   This is the craft argument, and it is *why the declaration exists* — not a consequence of `IMPACT`.
3. **Calibration touches one thing.** §9a calibrates `IMPACT` (within-lane rank). It does **not**
   re-derive lane order. Changing one does not move the other.

**Tiebreak:** equal lane maxima fall back to declaration order in the lane table. Declared, not
discovered.

**OPEN, not closed (review amendment, accepted).** This section previously read "closed." That
overcorrected. The evidence is *divided*: upstream-first is defensible craft practice and rewrite
rooms run structure-down, but it contradicts Expert D's own ordering, which ranks exposition (#2)
above dangling setup (#4). **A decision with divided evidence is a hypothesis, not a premise.** The
upstream-first default ships, and lane order rides into the writer sitting as an explicit open
question alongside the uncalibrated weights — see §10.1. Closed decisions do not get revisited;
hypotheses do, and this one has not earned closure.

**G9 (acceptance):** lane headers render in the declared order, byte-identical across two loads of
the same script, and unaffected by any `IMPACT` recalibration.

**Implementation note:** rows in the Observation lane must be excluded from `score()` entirely, not
scored and then not displayed. A real report exercises this — see §9a, where a `theme` finding
carries `scene_refs: [2]` yet is unqueued. Scoring it produces a number no reader ever sees.

### 1.7 DEFECT FOUND IN CALIBRATION — the two verification readouts disagree, and the server inflates

**Outside the #1–#7 scope. Recorded, not adopted.** Found while reconciling Result 3 of the external
review. The review claimed the product displays "the wrong number" for verification and that the fix
is "two numbers." **The two numbers already exist** — and the real defect is worse and in a
different place.

**What already ships.** `verificationReadoutText()` (`core.js:176-188`) prints:

```
N of M quotes verified (P%) · K carried no quote
```

Both numbers, one line, unit-tested at `tests/js/verification_readout.test.js:16-20`. So "add a
coverage number" is already done.

**The actual defect: two implementations, opposite rules, and the server inflates.**

| | denominator | verdict |
|---|---|---|
| `screenplay_analyzer/verifier.py:235` | `verified + not_found` — **excludes** `scene_not_found` | inflates |
| `screenplay_studio/webapp/core.js:178` | `verified + not_found + scene_not_found` — **includes** it | correct |

**Arithmetic proof.** `verified=1, not_found=0, scene_not_found=1`:

- `verifier.py` → `1 / 1` = **100.0%**
- `core.js` → `1 / 2` = **50.0%**

**One of two citations confirmed. The server reports "100% verified."** The delta scales with
`scene_not_found`: at 5/2/3 the two disagree by **21.4 points**.

**The docstring has the logic inverted.** `verifier.py:230-232` justifies the exclusion: *"`scene_not_found`
is excluded too (it IS a check result, and folding a failure into the denominator would flatter the
rate)."* Removing a failure from a denominator **raises** the rate — that is what flattering *is*.
Including it is the stricter measure, and `core.js` takes it.

**Two tests, near-identical names, opposite assertions** — which is how this survived:

- `tests/js/verification_readout.test.js:32` — *"scene_not_found is a failure, **not a denominator
  exclusion**"* → asserts `1 of 2 (50%)`, includes it
- `tests/test_verification_summary_surface.py:99` — comment *"a FAILURE, **not a denominator**"* →
  asserts `quote_bearing == 3`, `66.7%`, excludes it

**Blast radius.** `verified_pct_of_quoted` feeds the Context section's "Verifiability (B)" line
(`app.js:6779`) and the exported report (`report.py:385-388`). Both can overstate. It does **not**
reach the canonical trust line (`app.js:7214` → core.js), so the two readouts disagree *within one
surface* — the exact failure `app.js:7211` warns about: *"two honest-looking numbers that disagree is
how a writer stops trusting both."* Its comment also claims to be *"The ONLY reader of
report.verification_summary"*; `buildContextSection` (`app.js:6576`) is a second reader. **That
comment is false.**

**Recommendation, for a separate spec — not folded into §1.** Fix `verification_rate()` to include
`scene_not_found`, update the two pinned tests to agree, and route `buildContextSection` through
`verificationReadout()` so one implementation serves every surface. **Do not "fix" this inside the
ranking work:** it touches a server metric, an exported report, and four test files, and it deserves
its own falsifiers.

**What this changes about the reviewer's Result 3.** The verdict on D6 moves from "weak data" to
**"the metric has a second, contradicting implementation on the server."** That is stronger *and*
more actionable than "wrong number" — but it is a different defect, in a different layer, and it is
still not evidence about how often quotes verify.

## §2. Delete the room tablist (#1)

**Delete** `#room-toggle`, `#room-cowrite-btn`, `#room-feedback-btn`, `#room-chip`
(`index.html:151-156`).

**`setRoom()` SURVIVES.** It is the router's verb and the return stack for four full-screen tools
(§0.1). Only the tablist goes. Deleting `setRoom` would break four deep-link-driving tests and the
`prevRoom` restore path for Premise, Compare, Revision and Beat Board.

**Evidence this is vestigial:** `openFeedbackView()` (`app.js:8426-8431`) does
`setRoom("cowrite")` then `openDock("evidence")` — the Feedback tab *moves the writer into the
Co-write room*. Both tabs land in the same physical room. The HTML comment admits the retarget:
*"aria-controls on #room-feedback-btn now points at #room-drawer, which is what the button actually
opens."* (`index.html:448-449`).

**Replacement:** one control, labelled by what it opens, not by which room it teleports you to.
Keyboard `f` (`app.js:9324`) and the palette entry both keep working and now mean the same thing as
the button. `#cowrite-panel` becomes a plain panel, not a tabpanel.

#### The route-preservation corollary, and the defect it uncovered

Corollary raised in review: the deep-links test pins `/feedback` in the hash, so the replacement
control **must drive the same route**, or the spec's own "textually unmodified" ship condition fails.

Following it surfaced something larger. **Today, nothing a user can click writes `/feedback`.**

The chain, verified end to end:

1. `buildRoute()` derives the hash from `state.view` — `app.js:2273-2274`.
2. The Feedback button calls `openFeedbackView()` — `app.js:10528-10531`.
3. `openFeedbackView()` forces `setRoom("cowrite")` — `app.js:8427`.
4. `setRoom` → `saveSession()` → `syncRoute()` — `app.js:2237`.
5. `buildRoute()` therefore emits **`#/project/cowrite`**.

So clicking "Feedback" writes **`/cowrite`** into the address bar. The deep-links test
(`deep_links.py:209`) passes only because it calls `setRoom('feedback')` **directly**, bypassing the
click handler — it pins a route the product's own visible control does not produce. `app.js:2259`
states the governing principle: *"The hash is DERIVED from `state`, never the source of truth."*
That principle is what makes this a real defect rather than a naming preference: `state.view` is
`"cowrite"` while the URL says `feedback`.

**Fix, in §2:** the replacement control drives **`setRoom("feedback")` then `openDock("evidence")`**,
not `openFeedbackView()`. `openFeedbackView()` keeps only its load half
(`loadScriptData()` when `!state.script`, `app.js:8428-8430`) and loses the `setRoom("cowrite")` line.

Side effect, and a desirable one: `setRoom("feedback")` hides `#cowrite-panel`
(`app.js:2634`), which is what the two rooms actually mean. Forcing `cowrite` was the vestigial half
of the tablist: it kept showing the Co-write panel inside the "Feedback" room.

**Now check the corollary's second horn:** `openViewByName("feedback")` routes through
`openFeedbackView()` (`app.js:2338`), and its comment claims the deep link "redirects to the desk +
the Evidence lens". `syncRoute()` early-returns while `routeApplying` is true (`app.js:2285`), so a
URL arrival keeps the `/feedback` hash while showing the Co-write room. The comment says redirect;
the hash does not move. That divergence closes when the `setRoom("cowrite")` line goes.

**Ship condition, tightened:** `deep_links.py:209` unmodified **AND** clicking the replacement
control results in `location.hash === "#/<project>/feedback"`. The second clause is new and is the
one the existing test cannot catch.

**Test migration (falsifier 3, §0.1 — required, not optional):**

| Site | Before | After |
|---|---|---|
| `e2e_browser_deep_links.py:209` | `setRoom('feedback')` + hash assertion | **unchanged** — the route assertion must keep passing verbatim |
| `e2e_browser_deep_links.py:76` (docstring) | documents route-sync timing around `setRoom` | unchanged; `setRoom` is untouched |
| `e2e_browser_phase12_visual_motion.py:235, :245` | drive `setRoom`, assert motion/ARIA | re-point the assertion at the dock Evidence lens; keep the motion timing checks |
| `e2e_browser_readiness_gate.py:563` | `setRoom('feedback'); openRoomDrawer()` | keep both calls; the readiness gate does not depend on the tablist |

**Ship condition for §2:** all four sites green, with `deep_links.py:209` **textually unmodified**.
If that one assertion has to change to make §2 pass, §2 has cut something it should not have.

## §3. Delete the gutter (#2)

**Delete** `.gutter`, `#gutter-sam`, `#gutter-doc` (`index.html:453-457`), its handlers
(`app.js:2584`, `app.js:10532-10534`), and the `.gutter` rules at `style.css:3979-4016`.

Both tabs duplicate dock lenses 2 and 3 (`index.html:279-280`) and both routes already land on
`openDock()` (`app.js:10836`, `app.js:10849`). The gutter is already `display: none` under 900px
(`style.css:3575`) and in print (`style.css:3627`) — **chrome that survived its own breakpoint.**

## §4. Delete the duplicate Dawn control (#3)

**Delete** `#dawn-btn` (`index.html:78`, sidebar footer). **Keep** `#status-dawn`
(`index.html:474`, status strip). One control, one state.

Note for the record: agreement #11 ("rename the dawn meter or the Dawn theme") is **rejected as
misdiagnosed**. The meter (`app.js:4447`) and the theme (`#dawn-btn`, `.dawn-wash` at
`index.html:723`) genuinely share a word, but the actual defect was **two controls driving one
state**, and deleting one fixes it. A rename would have left the duplication in place under a
new name.

## §5. Sameer converges to two homes (#4)

Four reachable homes today: `#cowrite-panel` (`index.html:419`), `#room-drawer` (`index.html:402`),
`#dock-tab-sameer` (`index.html:279`), `#gutter-sam` (`index.html:455`). §2 and §3 remove the last
two. **Two survive:** the desk panel and the dock lens (which adopts the conversation while the dock
is open, per the existing portal contract at `index.html:292-294`).

## §6. Run Analysis is never behind auto-hide chrome (#5)

`.auto-hide-chrome` sets `#project-bar` and `#desk-toolbar` to `opacity: 0; pointer-events: none`
(`style.css:4742-4743`). On a first visit the writer sees a clean desk with no visible way to start
the product's entire reason for existing.

- `#desk-analyze-btn` (`index.html:178`) is **excluded from auto-hide** and always visible while a
  project is open.
- **Running state:** show stage progress and client-measured elapsed.
- **ETA is explicitly deferred.** The server emits per-stage *status* events
  (`pipeline.py:1308-1311`), not durations. A predicted duration would be a fabricated number, which
  is the exact failure mode the other-panel reviewer named when it ruled "never render a control
  whose click is an apology error." Ship ETA when the server emits stage durations, not before.
- `#desk-analyze-cancel` (`index.html:184`) does not move.

## §7. Craft impact replaces severity as the sort key (#6, #7)

**Sort** the queue by §1.3 within each §1.2 lane. **Keep severity displayed** — the rim/mass/label
language in `DESIGN.md` is verified in use and is not being touched. Severity stops being the
*ordering* and remains an *attribute*.

**Filter row** collapses to severity chips + This-scene + the fix-loop chip. Category chips leave
the filter row and become **clickable group headers** on each lane, setting
`state.findingFilter.category`. This preserves GAP-1's single-predicate contract by construction:
the header sets the same field the chips set today, and `findingPassesFilter` remains the only
predicate.

---

## §8. Acceptance gates

New checks in `tests/e2e_browser_layout_audit.py`, which already seeds an analyzed desk and gates
dock geometry. Each is a hard assertion, not a screenshot.

| # | Assertion |
|---|---|
| G1 | `#room-toggle`, `.gutter`, `#dawn-btn` are absent from the document |
| G2 | exactly one element with id `status-dawn` |
| G3 | `#desk-analyze-btn` computed `opacity === 1` with a project open and the pointer parked away from the top edge |
| G4 | fix-queue filter row chip count `<= 6` (severities + This-scene + loop) |
| G5 | **Tier 1 first actionable queue row has `getBoundingClientRect().bottom < 900`** at 1440×900, dock open — measured against the **enumerated** Tier 1 of §0.2, not an assumed one |
| G6 | every fix-queue row renders its rank-reason string (§1.5) |
| G7 | lane headers for all present lanes, and **no lane header is below the fold** |
| G8 | the existing `by-category` assertions in `tests/e2e_browser_dock_sections.py` (21 references) still pass |
| G9 | lane headers render in descending max-`IMPACT` order and the order is identical across two loads of the same script (§1.6) |
| G10 | **clicking the replacement control yields `location.hash === "#/<project>/feedback"`** — the clause `deep_links.py:209` cannot catch (§2) |

**Tier 1 contents enumerated for G5**, per §0.2 — arrival strip, ambiguous-marks notice, filter row
(severity + This-scene + loop), current-scene box, then the lane-grouped queue. The Top-5 stack and
the verdict line are **not** in that list, by ruling, not by omission.

G5 passed on the identity-anchored `bd86a8e` re-anchor at **882px**, with **18px** of headroom
(§14.51). This is a result for the measured input, not a guarantee for every report.

**Standing regression requirement:** every future Tier 1 addition or geometry-affecting change must
re-measure G5. Assert served-tree identity first, then measure at 1440×900 with the dock's default-open
worklist, lens scroll 0 and no manual scrolling. Report the first actionable row's top, bottom and
remaining margin. The hard assertion stays `bottom < 900`; source/Node checks cannot waive it.

---

## §9. Calibration

**Split, because the original plan contradicted the ship order.** §9's header once read "must run
before §1 ships" while §11 shipped §1 first and calibrated last. Resolved into two phases with
different prerequisites.

### §9a. `IMPACT` values — BLOCKED, needs a real model

**What ran.** Demo-model pipeline over `tests/fixtures/pain_tenglish.fountain` via
`webapp_server --demo-model`. 7 findings, full report captured.

**Why it cannot calibrate, three measured reasons:**

| Finding | Evidence |
|---|---|
| **Severity carries zero signal** | all 7 findings are `severity: low`. No ranking can be validated against a field with one value. |
| **4 of 7 findings are filler** | 4 are literally `[demo] Sample <category> finding — demo model, not a real analysis.` They carry no craft content. |
| **6 of 7 have no quote** | `no_quote: 6`, `quote_bearing: 1`, `verified: 1`, `verified_pct_of_quoted: 100.0` |

**Two side results worth keeping:**

1. **The "11% verified" figure is a `no_quote` artifact.** Here 100% of *quoted* findings verify. The
   gun_pen figure of `1 of 9 (11%)` (`docs/FULL_FEEDBACK_AUDIT_VERDICTS.md` row C1) therefore measures
   **how many findings quote anything**, not whether the quotes are true. Any UI reading it as a
   quality score is misreading it. This vindicates flagging D6's number as `[weak data]`.
2. **`genre` arrived with `scene_refs: []`** — a script-level finding with no scene, exactly the case
   §1.2's membership principle routes to the Observation lane. **The rule is exercised by real data,
   not hypothetical.** (`theme` also arrived with `scene_refs: [2]` and is unqueued by rule, which is
   the implementation note at the end of §1.6.)

**What this means:** the two reports named in the original plan are both demo-model runs. **The
third, "one full-length real screenplay," requires a live `llama-server`, which this environment does
not have.** `IMPACT` therefore stays **v0, explicitly uncalibrated** — which is the correct outcome,
not a deferral. Do not calibrate against demo output; it will flatten every weight toward zero
because filler findings carry no craft signal.

### §9b. Rendered-order calibration — runs after §1 ships

Once the queue renders, check the order against §1.6's declared lane order and §1.5's rank-reason
string. **Pass condition:** a reviewer reads the queue top to bottom and agrees with the order. If
they cannot say why row 3 outranks row 4, the weights are wrong, not the reviewer.

### §9c. Ship-order correction

**Original §11 shipped §1 first and calibrated last, contradicting this section's header.** The
correct order is: **§9a is an input to §1, not a follow-up** — and it is currently blocked, so §1
ships with v0 weights *explicitly marked as such in the UI copy*, never silently. §9b follows §1.

## §10. What could rot

- **`IMPACT` drifts from the analyzer.** v0 lives client-side for a reason (no schema change). If a
  category is added server-side and not here, it scores `undefined`. **Fail loud:** an unknown
  category must render an explicit "unranked" marker, not sort to 0 silently. This is the
  `app.js:5179` `CATEGORY_LABELS[f.category] || f.category` pattern already in use.
- **`IMPACT` silently reads as settled.** §9a is blocked, so §1 ships with placeholder weights.
  The rank-reason string (§1.5) must say so: *"ranked here: Line (impact 3, v0 — uncalibrated)"*.
  A ranking that pretends to be settled is the failure this spec exists to prevent.
- **Calibrating against demo output.** §9a measured why it cannot: 4 of 7 findings were literal
  `[demo]` filler and all 7 were `severity: low`. A future calibration pass run against the demo model
  will flatten every weight toward zero and look like a successful result.
- **A lane with no batch verb.** §1.2 promises one per lane; a lane that ships without it is the
  "second-class queue by another name" failure, restated.
- **Group headers as a second filter.** If a header ever filters without going through
  `findingPassesFilter`, GAP-1 returns.

### 10.1 Open questions for the writer sitting

`docs/REAL_WRITER_VALIDATION.md` is the only gate that counts, and it has never been run. Two
questions from this spec go into that sitting, both as **hypotheses**, neither as a closed decision:

| Question | Carried because |
|---|---|
| **Read the queue top to bottom. Does Structure-first match what you would actually do first?** | §1.6's evidence is divided — upstream-first is craft practice but contradicts D3's own ordering |
| **Do the ranked rows feel like your rewrite order, or like a report?** | §9a is blocked; `IMPACT` ships v0 and is explicitly marked uncalibrated (§10) |

A writer who cannot say why row 3 outranks row 4 has answered the second question badly, and the
weights are wrong — not the reviewer.

## §11. Ship order

**Restructured: deletions first, in parallel with the calibration wait** (review amendment,
accepted). §2–§6 need no calibrated weight. The falsifier, the predicate traps, and gates G1–G4 and
G10 are all specified and testable today, and nothing about them blocks on §9a.

| # | Step | Gate |
|---|---|---|
| **A** | **§2–§6, the deletions.** Independent of calibration. Parallelisable across three people. | G1, G2, G3, G10; falsifier 3 satisfied by `deep_links.py:209` unmodified |
| **B** | **§1 + §7**, membership and ranking. Ship with `IMPACT` **v0**, rank-reason string marked uncalibrated. | G4, G5, G6, G7, G9 |
| **C** | **§9b** rendered-order calibration, then re-tune `IMPACT`. | §9b pass condition |
| **D** | **§1.7**, the verification-rate defect — **separate spec**, do not fold into B. | its own falsifiers |

**Why deletions lead.** They are the whole of the original complaint — one finding in five places,
three spines, a verb hidden behind a hover — and they are the half that needs no new judgment. A
ranking over an undeduplicated surface orders the clutter; it does not remove it.

**Why §1.7 must not ride along.** It changes a server metric (`verifier.py`), an exported report
(`report.py`), the canonical client function (`core.js`), and four pinned tests, including two that
currently disagree with each other. Bolting that onto the ranking PR means one revert undoes both.

**Write the letter to yourself for the next pull request:** every change here is a deletion, and
deletions are invisible in a diff. Record what was removed and what measurement justified it.

---

## §12. Track A execution record (2026-10-15)

Sections 3, 4 and 2 shipped on `arena/e6a57b71-screenplay-studio`. Three of this spec's
claims were wrong when written and are corrected here, because each one cost a wrong
prediction and the next reader deserves the corrected number.

| § | Item | Commit | State |
|---|---|---|---|
| 3 | Gutter | `e3c8f17` | shipped, 1 test file touched |
| 4 | Duplicate Dawn | `ad21fa4` | shipped, 1 test file touched |
| 2 | Room tablist + route fix | `463aa29` | shipped, 5 test files touched |
| 5 | Sameer converges | — | **falls out of §2 and §3; nothing left to do** |
| 6 | Run Analysis | — | not started |

### 12.1 §4's blast radius was wrong by 2 sites in my own favour, then 1 against

The spec treated §4 as a deletion with no test migration. Reality: six call sites referenced
`#dawn-btn`, but **only two actually break** — `_ui_capture.py:296,310`. The other four were
already written to tolerate absence: `_p1_visual_gate.py` falls back to `#status-dawn` on its
*next line*; `pass_arc:109` tries both selectors; `phase12:308,318` null-guard
`getElementById`.

The first breakage table I produced claimed `_p1_visual_gate.py:157` was a hard locator. It
read the line, not the block. That is probe bug #3 — validating the probe before trusting its
output — committed in the same round I flagged it in someone else's analysis.

### 12.2 §2's test table undercounted by one file and missed a failure mode

The spec listed four sites. There are five files. The omission mattered:
`e2e_browser_phase9_idea_canvas.py:133` writes
`check("Premise Doctor reachable...", !!b && b.offsetParent !== null)`. With the button
deleted, `b` is `null`, the expression is `false`, and the suite **records a failure** rather
than raising. A structural scan for "will this throw?" would have cleared it.

`e2e_browser_common.py` also referenced the old id, but only in a `reveal_and_click` docstring
— the function takes its selector as a parameter, so it carries no live dependency.

### 12.3 `#room-chip` is kept, against the spec's own delete list

§2 listed `#room-chip` for deletion. It is **not vestigial**: `setIdeaLens()` renders
`"✍️ Idea Room"` vs `"📋 Concept Validation"` through it, making it the live room indicator in
the idea room. Deleting it would discard rendered information to satisfy a list entry, which is
the exact failure this arc has been correcting against. The tablist is gone; the readout stays.

### 12.4 What §2 actually fixed, beyond the deletion

`openFeedbackView()` no longer forces `setRoom("cowrite")`. The replacement control
(`#room-evidence-btn`) calls `setRoom("feedback")` first, so `buildRoute()` emits
`#/<project>/feedback` — the route `deep_links.py:209` has always asserted and that **no
visible control previously produced**. `deep_links.py` gained a second assertion that clicks
the control and fails if the hash says `/cowrite`.

Two unguarded `classList` dereferences of the deleted buttons (`syncRoomUI`, `applyIdeaLens`)
would have thrown on every room change. They are replaced by an `aria-pressed` toggle on the
single control.

### 12.5 A ratchet fired and was right to

The new deep-links check was first written inside `if page.locator(...).count():`. That guard
would let the block skip itself and still print PASS if the control vanished — precisely the
regression under test. `test_browser_check_hygiene` refused the 24th if-guarded check against a
ceiling of 23. Correct response: **remove the guard**, not raise the ceiling. The control is
promised to exist, so its absence must fail loudly.

### 12.6 Verification status

`CSS balanced 1451/1451`, `app.js` parses under `node --check`, 2254 python tests pass, 86/87
node. Two `test_repo_hygiene` failures are pre-existing (`ModuleNotFoundError`, reproduced at
HEAD with all changes stashed). The one node failure,
`preview-ink-layer/tests/dom.test.mjs`, is pre-existing at HEAD.

**Not yet verified:** every browser suite. `smoke`, `export_flush`, `render_scale`,
`phase9_idea_canvas`, `phase12`, `readiness_gate` and `deep_links` all require a Playwright
runner. The two `smoke`/`export_flush` migrations are the live risk — they move from
`openRoomDrawer()` to the dock's Sameer lens, a different surface, and their assertions may
read drawer-specific DOM. If they fail, §2 is over-scoped and the failing assertion will say so.

### 12.7 Section 6 shipped: Run Analysis is never behind auto-hide chrome

`.auto-hide-chrome #desk-toolbar` carried `opacity: 0; pointer-events: none` after 4s idle.
Run Analysis — the control that starts the product's entire reason for existing — was inside
it, so on a first visit the writer saw a clean desk with no visible way to begin. The only
recovery was a mousemove with `clientY < 120`, which a keyboard user and a trackpad user both
fail.

`#desk-toolbar` is now exempt. `#project-bar` still auto-hides. **No DOM moved and no layout
shifted** — `opacity` cannot be undone per-child, so the only way to keep one button lit inside
a faded parent is to stop fading the parent.

**The rest of §6 was already true and was left alone.** `#desk-analyze-progress` carries the
stage caption in `.ap-stage` and the client-measured elapsed in `.ap-beat`
(`app.js:2831-2832`), both direct children and always visible — the hover-only part is
`.stage-ladder`, which is a separate, deeper affordance. Recording this rather than "adding"
it: the spec described a gap that the code had already closed.

**No ETA, and none added.** `stageElapsedText` (`app.js:2740`) renders
`"working… 12s on this pass"` or `"no word from the model — waiting 1m 20s"`. Both are measured
client-side. A predicted duration would be a fabricated number, which is deferred until the
server emits stage durations.

**Test impact: none, and the check was done before the edit, not after.** `reveal_chrome` and
`reveal` are defensive helpers — they move a mouse then poll for the hit target — so they
return `True` immediately when nothing hides. `phase13:230` asserts *spotlight* hides the
toolbar, which is a separate rule (`.spotlight-mode #desk-toolbar`, `style.css:3439-3442`) and
untouched. `phase8:216` asserts the toolbar sits above the manuscript row, a geometric check
`opacity` never affected. Three docstrings describing the toolbar as auto-hiding were
corrected, and `reveal_chrome`'s docstring now records why the helper stays even though it is
no longer load-bearing for the analyze button.

**Track A is complete: sections 2, 3, 4, 5, 6.** Section 5 fell out of 2 and 3 and needed no
commit of its own.

### 12.8 §7: the section 3 edit destroyed two CSS rules, and one was invisible

The §3 deletion removed the `.gutter` selector from two comma-separated selector lists. In
both, the edit took the list's shared `{ display: none !important; }` block with it. What
remained was a **dangling selector list**, which is valid CSS — the survivors merged into
whatever rule came next and inherited its declarations.

| Rule | What happened | Caught by |
|---|---|---|
| Spotlight hide | 4 selectors absorbed `padding-top: 26px`; **nothing hid under spotlight** | `e2e_browser_phase13` |
| `@media print` hide | ~25 chrome selectors absorbed `display: block !important` from `#manuscript-workspace`, so the sidebar, both toolbars, the modals and the project bar would have **printed** on top of the script | **nobody** |

The print rule was the more serious of the two and it survived four rounds of review, three
of them after it was broken, because no suite renders print media.

**Why the existing checks passed.** Brace balance held (1451/1451) and `node --check` passed
on the destroyed stylesheet. Neither looks at whether a selector kept its declaration, because
losing one unbalances nothing.

**Why a parser cannot catch it either.** The broken spotlight rule was syntactically valid:

```css
.spotlight-mode #diff-banner,
.spotlight-mode #manuscript-container { padding-top: 26px; }
```

Well-formed, merely wrong. So the guard pins the rules that carry product behaviour rather
than inferring intent from syntax — `tests/test_css_selector_list_integrity.py`, verified to
FAIL against the real broken file from `6510e2f` and to pass against the fix.

**Selector disposition, stated as required.** `.gutter` is gone because §3 deleted the element.
`#room-drawer` is **restored** to the spotlight list — the element still exists in the DOM.
`.craft-shelf` and `.script-level-notes` are **deliberately absent**: both were already dead at
`538d2df`, with zero occurrences anywhere in the DOM. Dropping them is cleanup of pre-existing
debt, not collateral damage, and that distinction was checked rather than assumed.

### 12.9 Print CSS is source-guarded and never rendered — recorded limit

Confirmed by runner sweep on `c28cb50`: **nothing in the suite corpus renders print media.**
`emulate_media` appears once across the corpus, for `reduced_motion` only. No `page.pdf()`, no
`media="print"`, no print-preview snapshot.

So the `@media print` hide rule has exactly two layers of coverage, both static:
`test_spa_contract.py`'s `@media print` rule count, and
`test_css_selector_list_integrity.py`'s selector-list guard. **A regression that only manifests
in rendered print output has no browser check that can catch it** — which is precisely how the
absorbed `display: block !important` survived four rounds of review.

**CLOSED 2026-10-15, by execution.** A runner reproduced the regression under
`page.emulate_media(media="print")` with a failing-then-passing pair: on `6510e2f` (broken) 10
chrome elements were visible and the manuscript was crushed to 187px; on `c28cb50` (fixed) every
chrome element was hidden and the manuscript rendered 1438x898. That probe now lives in the repo
as `tests/e2e_browser_print_media.py`.

**The first committed version of this suite never passed anywhere, and could not have.** It
asserted on `#manuscript-workspace` from the welcome screen, where no project is open and the
element has a 0x0 box. A width assertion against a nonexistent manuscript is vacuous in exactly
the sense the suite's own control section warns about. Runner execution caught it: 4/6 on the
fixed tree, 3/6 on the broken one, with the manuscript checks red on both.

The controls are now split by view, because the two elements never share one:

| Check | View | Why |
|---|---|---|
| `#sidebar` and `#welcome-view` visible | welcome | the view the shelf certainly lives in |
| sample page opens; `.workspace` visible | transition | `openProject` flips the title and reveals the workspace in the same tick, so **both** are waited on — smoke.py learned this when a title-only wait passed on a stale placeholder |
| `#manuscript-workspace` visible **and larger than 1000x300** | desk | a bare `is_visible()` on a container that has just appeared is weak; the control insists it has real area |

Then print emulation asserts all 31 chrome selectors hidden, and the manuscript visible **and
wider than 1000px** — a bare `display != none` passes on the broken build's crushed 187px box.

**Print suite verified by execution, both directions.** Broken-first on `6510e2f`: 8/9, failing
only on "print hides all chrome selectors" with 20 named visible selectors and all five controls
passing — so the red is meaningful rather than environmental. Fixed tree: **9/9**. Green on the
tree it was written for, red on the regression it was written for.

**The sidebar disagreement, dissolved by measurement — and the spec's own claim above was
wrong.** The runner reported Playwright seeing `#sidebar` invisible on the desk view. The code
reading here said nothing hides it. Both were right. Measured on the desk view with a project
open: `display=flex visibility=visible box=0x872` — a **present-but-zero-pixel** element, the case
where "visible" means three different things to CSS, to Playwright, and to a writer.

`openProject` *does* touch it: `app.js:2484` calls `toggleSidebar(true, false)`, which adds
`sidebar-collapsed` — `width: 0; padding: 0; overflow: hidden`, with `> * { display: none }`. That
is exactly the measured `0x872`: full height, zero width. The earlier claim that "`openProject`
never touches it" was wrong, and the mechanism is **not** flex collapsing the child.

**Intentional, and documented at the call site.** `app.js:2480-2483`:

> WIREFRAME ALIGNMENT — the writing environment has no permanent left navigation: the shelf
> slides away so the Scene Index owns x:0-44 and the 700px manuscript column can centre on the
> viewport. Not persisted (persist=false) — the landing desk keeps the writer's shelf preference,
> and the edge tab brings the shelf back at any time.

The idea canvas does the same (`app.js:1565-1567`); `toggleSidebar`'s own docstring
(`app.js:1305-1307`) gives the `persist=false` reason; and `.sidebar-edge-tab` is the affordance
that brings the shelf back. **Deliberate behaviour carrying its own rationale, not a latent
defect** — the disposition question is closed.

**The generalisable hazard is recorded as a hazard, not a bug.** A zero-width element that
Playwright counts as present will trip the next suite that asserts on it with `count()` instead
of by box. Real trap for future work here; not a defect in this tree.

**Drift between the CSS and the suite is now a pytest failure.**
`test_the_print_suite_covers_every_selector_the_css_hides` compares the suite's `PRINT_CHROME`
list against the live stylesheet in both directions. Verified non-vacuous by adding a
`#made-up-drift-probe` selector to the CSS and watching the assertion name it. Otherwise someone
adds a selector to the hide list, the browser suite silently stops covering it, and the only
signal is a regression nobody catches — which is how the print rule survived four rounds in the
first place.

**On the runner's self-critique, recorded because it generalises.** The probe was run against the
fixed tree first and the broken tree second, so the favourable result came first and the
confirmatory one second — exactly the sequence that lets a flawed probe survive. The
non-vacuity run redeemed it this time. The discipline: **broken first, fixed second, always.**

### 12.10 The guard's correctness is now evidenced in-repo, not by claim

`test_css_selector_list_integrity.py` originally asserted fail-on-broken **in a commit message**.
That is a claim, and the runner declined to reproduce it, correctly. The two real breakages are
now literal fixtures in the module — the exact selector lists as they stood in `6510e2f` — and
the guard must reject them.

Verified non-vacuous three ways: the two broken strings genuinely lack
`display: none !important` while the healthy string has it; mutating `_rule_body` to return the
whole stylesheet is caught; and the guard fails against the real broken file from `6510e2f` with
the merged selector list printed in the assertion.

A first mutation attempt was itself wrong — it neutered the *fixture's* assertion to `assert
True`, which passes trivially and tests nothing. The mutation has to break the guard's lookup,
not the test's expectation. Worth recording because it is the same shape as the arc's standing
error: a check that cannot fail looks identical to a check that passes.

---

## §13. Track B falsifier: two real finding categories have no lane and no IMPACT value

Run before writing any Track B code, per the discipline adopted after §12.8: every file-and-line
claim in a spec gets opened before the spec lands, not after a runner measures around it. §1's
seven cited claims were opened. Five held exactly. Two drifted. Opening them surfaced a
shippable-blocking defect in Track B's own premise.

### 13.1 The claim audit

| Claim | Cited | Actual | Verdict |
|---|---|---|---|
| `FINDING_CATEGORIES`, eight of them | `grammar.py:45-48` | exact, 8 | ✅ |
| "Flag, don't drop" | `AGENTS.md:66` | exact | ✅ |
| `SCRIPT_LEVEL_CATEGORIES` contains `character` | `pipeline.py:589` | exact | ✅ |
| `CATEGORY_LABELS` | `app.js:4232` | `app.js:4230` | ⚠️ drift, and **11 entries** |
| `findingOnScene` tests numeric and string refs | `app.js:6978-6981` | `app.js:6981-6985` | ⚠️ drift, claim holds |
| `findingPassesFilter` is the one predicate | `app.js:6964-6973` | `app.js:6971+` | ⚠️ drift, claim holds |
| `findingFilter.category` is a single-category filter | `app.js:6970` | `app.js:6975` | ⚠️ drift, claim holds |

Every line number in §1.2–§1.4 is off by 2–7 lines. The **claims** survive; only the coordinates
are stale. That is the cheap failure. The expensive one is what the `CATEGORY_LABELS` drift
exposed.

### 13.2 The defect: `voice` and `subtext` are real finding categories

`CATEGORY_LABELS` (`app.js:4230`) names **eleven** categories. `FINDING_CATEGORIES`
(`grammar.py:45-48`) names **eight**. The two extras are `voice` and `subtext`, and they are not
vestigial labels:

- `screenplay_analyzer/voice.py:130, 217` emit `"category": "voice"` (voice-bleed, idiolect drift).
- `screenplay_analyzer/voice.py:253` emits `"category": "subtext"` (on-the-nose dialogue).
- `pipeline.py:1331-1341` runs all three analyses, so these findings are **reachable in
  production**, not dormant code.
- `report.py:52-53` maps both, with a comment recording that they "existed in
  `report.findings.json` and the Fix Queue but silently never rendered."

### 13.3 It is already a live invariant violation, not a Track B concern

`tests/test_finding_integrity_gate.py:208-222` pins
`test_gate_never_emits_a_category_outside_the_taxonomy`: every delivered finding's category must
be in `FINDING_CATEGORIES`. That test passes — but only because its three hand-built rows never
include `voice` or `subtext`. **The invariant is not enforced on real output.**

Executed directly against the gate:

```
gate_findings([{category: "voice"}, {category: "subtext"}])
  -> delivered categories: ['voice', 'subtext']
  -> in FINDING_CATEGORIES:  False, False
  -> VIOLATIONS: ['voice', 'subtext']
```

Ordering confirms it cannot be caught upstream: the voice passes run at `pipeline.py:1331-1341`,
`FindingIntegrityGate().run(...)` at `pipeline.py:1756-1757`. The gate runs **after**, and
normalizes only one out-of-taxonomy label — `scene` → `scene_function`
(`finding_integrity.py:611-615`), with a comment saying `"scene" was never in FINDING_CATEGORIES`.
The gate has precedent for this exact repair and missed the two legitimate categories.

### 13.4 Why this blocks Track B as specified

1. **§1.2 has no lane for them.** The lane table is explicitly "the disposition of all eight
   `FINDING_CATEGORIES`". A `voice` finding satisfies the membership principle (it has
   `scene_refs`), so it is queued — and lands in no lane.
2. **§1.3 scores them `NaN`.** `IMPACT` has eight entries. `IMPACT["voice"]` is `undefined`,
   `undefined × 10` is `NaN`, and `NaN` in a sort comparator is unspecified behaviour.
3. **"Every finding gets exactly one home" is already false** for these rows before Track B
   writes a line.

### 13.5 The decision Track B cannot skip

Not a number to tune — a taxonomy question, and the three real options differ in blast radius:

| Option | Effect | Risk |
|---|---|---|
| **A.** Add `voice`, `subtext` to `FINDING_CATEGORIES` | fixes lanes, IMPACT, and the gate invariant in one move | `grammar.py:76` builds the LLM findings grammar from this list, so the model is newly *invited* to emit voice/subtext as observation findings, duplicating the deterministic passes. Needs a read-only distinction. |
| **B.** Leave the grammar alone; extend only §1.2 lanes and §1.3 `IMPACT` | smallest change, no LLM surface touched | leaves the gate invariant violated; two category sources stay permanently split |
| **C.** Deterministic passes write their own category namespace (`voice_bleed`, `subtext_flag`) | cleanest separation, no grammar collision | renames categories across report, queue, and any pinned test |

**Recommendation: B, with the gate invariant amended to admit deterministic-pass categories
explicitly.** It is the only option that does not change what the model is asked to produce, and
the gate defect is then a named, tested exception rather than an unenforced invariant.

Track B does not start until this is decided. Writing `IMPACT` against a taxonomy that cannot
rank a tenth of its own rows is how a ranking ships broken.

---

## §14. Track B §1 decision taken, and the ranking tables land

Ruling: **Option B**, with requirements 1–3 from review. Option A stays ruled out
(rewrites the LLM grammar and invites the model to duplicate the deterministic passes);
Option C stays ruled out (a rename across report, queue and pinned tests for what is one
missing exception).

### 14.1 What ships

`voice` and `subtext` are laned to **Line** — they are line-level craft notes with quotes
and scene refs — and carry `IMPACT` entries alongside every other category. Marked
UNCALIBRATED like the rest of v0. The tables live in `core.js` beside `CATEGORY_LABELS`, so
they are testable without a browser, which is the only reason this could be verified from a
workspace with no Playwright.

`findingLane`, `sceneRefCount`, `rankScore` and `rankReasonText` are exported through the
existing Node test hook.

### 14.2 Three corrections to the spec's own sketch, made by opening the lines

1. **The sticky term reads `"addressed"`, not `"fix"`.** The spec sketch says "+5 if marked
   fix"; the value the product actually writes is `state.findingMarks[id] === "addressed"`
   (`app.js:43`, `:4288`). A rank term keyed on a mark value nothing ever writes is a constant
   zero wearing the costume of a tiebreaker.
2. **`state.findingMarks` is read through a `typeof` guard.** `core.js` loads before `app.js`,
   so a bare reference would throw the moment `rankScore` was called in a context without
   global state — taking the whole queue down rather than ranking it.
3. **Unknown categories score 0, not `NaN`.** `rankScore` uses
   `hasOwnProperty` rather than indexing blind. That is the structural fix for the §13 defect,
   independent of the coverage test: even a category nobody thought of cannot poison the sort.

### 14.3 The coverage guard, and why it reads source instead of a list

`tests/test_queue_lane_coverage.py` enumerates every `"category": "..."` literal the analyzer
writes into a finding dict, by scanning the analyzer's own source, and asserts `IMPACT` and
`LANE_OF` cover each one. Reading source rather than importing `FINDING_CATEGORIES` is the
whole point: that constant constrains the **LLM grammar only**, and the gap between it and
what deterministic passes actually emit *is* the defect.

It also pins the decision back: a test asserts `voice` and `subtext` are **still absent** from
`FINDING_CATEGORIES`, so a future contributor cannot quietly make the change that was ruled
out. And `test_the_emitter_scan_actually_found_categories` guards the guard — an empty scan
would make every other assertion in the file pass vacuously, which is the failure mode this
whole module exists to end.

Verified non-vacuous: deleting `voice` and `subtext` from both tables produces three failures
naming exactly those two categories.

### 14.4 The gate invariant, amended and exercised

`test_finding_integrity_gate.py` previously asserted `category in FINDING_CATEGORIES` over
three hand-built rows, and passed — because none of them were the categories that break it.
Now the delivered taxonomy is written down as the union, `voice` and `subtext` rows are in the
fixture, the gate is asserted not to *drop* them (`AGENTS.md:66`), and a companion test pins
that `voice.py` really emits them and `pipeline.py` really runs it — so the amendment rests on
a verified premise rather than on the fixture being taken at face value.

### 14.5 A test I wrote that contradicted the spec

My first `queue_lanes.test.js` asserted that `theme` **with** scene refs is queued. It is not:
§1.2 puts `theme` and `genre` in Observation unconditionally, because a thesis is not a task and
a scene anchor does not turn one into a task. The implementation was right and the test was
wrong. Corrected, and the correction now asserts the spec's rule directly rather than the
inference I had mistaken it for.

### 14.6 The lane default for unknown categories — decided, and the review's premise was inverted

Review raised it as a §7 decision: an unknown category scores `IMPACT` 0 and lands in Line,
so does it float among high-attention rows or sink? Measured rather than argued:

```
  45  line        character (known, verified, 3 scenes)
  32  line        dialogue  (known, 3 scenes)
  31  line        voice     (known, 2 scenes)
   5  line        brand_new (unknown, verified, 3 scenes — the UNKNOWN CEILING)
  30  line        dialogue  (known, 1 scene — the KNOWN FLOOR)
```

**It sinks, and that is worse than floating.** An unknown row tops out at 5 against a known
`dialogue` floor of 30: a 30-point demotion. §1.3 explicitly ruled this out — *"penalising a row
twice for the same property is how a ranking silently becomes a demotion."* And it is the §13
defect one step from shipping as designed: had `voice` and `subtext` reached §1 with only the
`hasOwnProperty` NaN guard and no coverage test, **every voice and subtext finding would have
sunk to the bottom of Line.** The guard stopped the crash; it did not stop the demotion.

Three options, and the two obvious ones are both wrong:

| Option | Verdict |
|---|---|
| fall back to `line` at impact 0 | **wrong** — a 30-point silent demotion for rows `AGENTS.md:66` says must not be buried |
| fall back to `observation` | **wrong** — that removes them from the queue entirely; "flag, don't drop" |
| their own `uncategorised` lane | **chosen** |

A lane is the only option that is neither. The row is visible, it is not ranked against rows it
has no opinion about, and a category nobody weighed becomes a **group header someone can see**
instead of a diff nobody notices. That last property is the real argument: this failure mode has
now hidden twice — once as `NaN`, once as a demotion — and both times invisibly.

`rankReasonText` prints `unweighed` rather than `impact 0` for these rows, because "impact 0"
implies a judgement was made. `tests/test_queue_lane_coverage.py` pins that `LANE_LABELS`
carries the lane, so deleting it cannot quietly return these rows to the bottom of Line.

### 14.7 §7 shipped: craft impact is the sort key, and the queue is lane-grouped

Three changes, and one thing deliberately left alone.

**Changed.** The ledger's `SEV_RANK` ordering table is gone. Rows sort by `rankScore` inside a
lane; lanes sort by descending max `IMPACT`, tie-broken on lane name so two loads of the same
script produce the same order — a queue that reshuffles itself between loads is a queue the
writer stops trusting. **Severity is still displayed and still filters.** It stopped being the
order, not the attribute; DESIGN.md's rim/mass/label language is verified in use.

**Category chips left the filter row** and now ride as clickable headers inside each lane. They
set exactly the field they set before, `state.findingFilter.category`, which is the whole reason
GAP-1's single-predicate contract survives the migration by construction. Each carries its own
count over the rows its lane actually holds — a count has to describe what its own press will
show, which is the defect family the old chips already had one round of.

**Left alone, on purpose:** a **lane** header is identity, not a control. A lane spans several
categories, so there is no single `category` value it could set, and §1.4 trap 4 forbids a
header owning a filter the predicates cannot express. The clickable controls are the category
sub-headers inside it.

**The grouping is PURE.** `groupByLane` filters nothing; it is handed rows `findingPassesFilter`
already admitted. No second predicate was forked. §1.4 trap 2 is respected structurally rather
than by care.

**G6 landed in the same commit:** every row appends `rankReasonText(f)`.

### 14.8 The section key stayed `"by-category"`, and that is not a bug

The obvious refactor is to rename the dock section from `by-category` to `by-lane`. **Doing so
would silently unhook `e2e_browser_dock_sections.py`**, which opens the section by that literal
in ~21 places (G8). The key is a harness hook, not a name, so it stays and a guard now pins it.

### 14.9 Two predicates exist, and this work did not make that worse

§1.4 trap 2 says `findingPassesFilter` is "the ONE filter". There are in fact two:
`findingPassesFilter` (`:6968`, disposition + severity + category + scene) and `inFindingFilter`
(`:7689`, severity + category + scene + groundedness). Both carry overlapping clauses and both
are documented as "the ONE". That is **pre-existing debt, not something §7 introduced**, and
refactoring it belongs in its own change with its own blast radius.

What §7 must not do is grow either into a lane check, because a lane clause inside a predicate
decides admission, and admission has one predicate. That is now a guard, not a convention:
`tests/test_queue_lane_rendering.py` fails if either predicate calls `findingLane`.

Verified non-vacuous by mutation: reintroducing `SEV_RANK` fails the sort-key test, and adding
one `findingLane` line to `inFindingFilter` fails the single-predicate test.

---

## §14.10 §9b calibration: PASS, on real-model evidence

**§9b's pass condition** is *"a reviewer reads the queue top to bottom and agrees with the
order; if they cannot say why row 3 outranks row 4, the weights are wrong, not the reviewer."*
It is met. Three real reports through `qwen3.6-35b` — gunpen (6pp), Pain (full length), and the
Tenglish fixture — 116 findings total, scored under rank v0.

| Report | Findings | verified / not_found / no_quote | Lanes populated |
|---|---:|---|---|
| gunpen | 23 | 16 / 1 / 6 | Line, Structure, Observation |
| pain3 | 63 | 40 / 5 / 18 | Line, Structure, Deterministic (3), Observation |
| pain_tenglish | 30 | 18 / 2 / 10 | Line, Structure, Deterministic (1), Observation |

Structure led in all three (delayed inciting incident, missing midpoint/objective/deadline,
underdeveloped Act Two). Character outranked dialogue in Line throughout. Verified and span acted
as tiebreakers only, with the 10-point `IMPACT` gaps doing the ordering — the design working as
described. Rank came out **decorrelated from severity**: gunpen's structural killers were labeled
low and still led their lane, which vindicates §7's sort-key swap rather than threatening it.
Deterministic rows batched; Observation held `theme`/`genre` out of the queue without dropping
them. Zero uncategorised rows.

### 14.11 What §9b does NOT establish, stated plainly

The verdict says the v0 weights **hold**. It does not say the weights are **correct**, and the two
are not the same claim.

- **The reviewer who validated the order is the reviewer who approved the weights.** That is the
  pass condition as written, and it was met, but it is a single reader and not an independent one.
- **Three scripts is a sample, not a distribution.** All three are the same kind of thing — a
  screenplay or a short. Nothing here speaks to a genre with no continuity errors, or to a writer
  who wants structure last.
- **What §9b tested was ordering.** §9a asked whether the `IMPACT` *values* are right. A queue that
  reads correctly top to bottom does not pin an absolute value; it only shows the current ordering
  is defensible.

So `IMPACT` moves from *v0 placeholder* to **v0, sanity-checked against real output**. The word
"calibrated" is not earned yet. §10.1's writer sitting, not this run, is what would settle it.

### 14.12 A ship obligation this build missed, and it was mine

§9c has always said: §1 ships with v0 weights **explicitly marked as such in the UI copy, never
silently**. Track B §1 shipped with the word UNCALIBRATED twice — both times inside a **comment**
in `core.js`. The writer saw nothing. And that same comment claimed the weights *"ship labelled as
such"*, which was simply false: it asserted a property the code did not have.

That is the arc's standing error in a new costume — a claim about behaviour written into a comment,
checked by nobody, and wrong. The marking now lives in the ledger section head
(`dock-section-hint`, "impact weights uncalibrated"), printed once so it is present without shouting
over the rows, and `tests/test_uncalibrated_marking_reaches_the_writer.py` strips every comment out
of the shipped JS and requires the word to survive. A word that only exists in comments cannot
render. Verified non-vacuous by moving the marking back into a comment and watching it fail.

### 14.13 Three things the calibration surfaced, none of them ranking

1. **Zero `voice`/`subtext` findings in 116.** They are specified, laned and weighed, and no real
   data has exercised them. Worth checking on arrival rather than assuming.
2. **The three craft passes share ONE `try`.** `pipeline.py:1328-1346` wraps `run_voice_analysis`,
   `run_subtext_analysis` and `run_idiolect_analysis` in a single `try/except`. A raise in the
   **first** suppresses the other two, appends one error string, and emits `voice complete, failed`.
   **The failure mode is indistinguishable from "the pass found nothing."** Before concluding the
   passes are merely quiet, someone should check `result.errors` on those three runs — a genuine
   failure and a genuine zero look identical from the findings alone. Recorded, not changed: it
   alters pipeline behaviour and the calibration just ran against the current behaviour.
4. **Near-duplicate findings persist** — five "static scene" and four "relies on visual
   storytelling" variants on pain3. Analyzer dedupe quality, not ranking. But a ranked queue
   multiplies duplicate visibility, so this belongs on the analyzer backlog with a higher priority
   than it had.

### 14.14 §7 rendered gates: G6 pass, G9 deterministic, G5/G7 failed on real output

| Gate | Result |
|---|---|
| G6 — every row renders its rank reason | **PASS.** "Line, impact 4", "Line, impact 3", "Deterministic, impact 2, verified" |
| G9 — lane order across two loads | **Sort is deterministic by construction**; the browser two-load assertion is **specified but unexecuted**, because the first probe compared a row *set* that varies with which scene the strip claims on each load |
| G5 — first actionable row above the fold | **FAIL.** 1593px in a 900px viewport |
| G7 — lane headers above the fold | **FAIL**, same cause |
| layout_audit | 37/37, no regressions |
| dock_sections | 174/176 — two obsolete assertions, see 14.16 |

### 14.15 G5: the threshold does not move

The first actionable queue row sat at **1593px against a 900px viewport**. The cause was not the
queue. It was everything ahead of it: arrival strip, filter row, scene strip, queue header — plus
two detail sections that are not Tier 1 at all.

**§0.2's Tier 1 enumeration is: arrival strip, ambiguous-marks notice, filter row, current-scene
box, then the lane-grouped queue.** `scene-findings` and `script-level` are **not on that list.**
They are the same findings rendered as per-scene detail cards, and they were being appended
*before* the ranked queue — so the one section that answers "what do I do first" was below two
sections answering "what is on this scene".

They are now built in place and appended **after** the queue. No predicate, no dedupe, no audit
hook and no DOM order within a section changed; only the moment of appending moved.

**The threshold was not restated.** Restating a gate so it fits its own failure is moving the
goalposts, and the complaint this gate encodes — the actionable finding sits below the fold — is
the complaint Track A and Track B exist to answer. If this reorder does not close the gap on the
next run, the next step is **Tier 1 compaction** (collapse the arrival strip, compact the filter
row), and only after that, a restated threshold with reasons recorded.

Guarded structurally: `test_the_ranked_queue_is_appended_before_the_detail_cards` asserts the
append order in source. It cannot measure pixels — the runner still owns that — but it stops the
ordering being undone between runs. Verified non-vacuous by restoring the old append order.

### 14.16 G8 amended: two dock_sections assertions encode the pre-§7 contract

`P1.7 highs-first` and `P1.8 group retention` both seed a **`"pacing"`** category group and assert
severity ordering inside it. Under the shipped code `"pacing"` is an **unknown category**: it lanes
to Uncategorised, scores `IMPACT` 0, and its title is now a `button.dock-lane-cat` sub-header
rather than a `.dock-cat-group` title.

So these two checks **cannot pass under the new contract by design**, which makes **"G8 as stated —
the existing assertions still pass — false**, and a permanently red suite is a gate that stops being
read. The migration preserves both checks' original intent rather than deleting them: re-seed with
real categories spanning **two IMPACT tiers**, then assert **rank order inside the group** and
**single rendering**. That is still "ordering within a group" and "one card per finding", which is
what P1.7 and P1.8 were written to protect.

Recorded as an amendment rather than left as red. Not yet migrated here — it is test-only work and
wants the reviewer's seed data, which lives outside this workspace.

### 14.17 G9's unexecuted assertion, specified properly

The sort is settled: `rankScore` descending with an index tiebreak inside a lane, max-`IMPACT`
descending with a name tiebreak across lanes, and the render consumes the canonical `order` rather
than object insertion order. Node confirms reversed input yields byte-identical output.

What is unproven is the **browser-level two-load assertion**, and the first probe confounded it:
the queue's row *set* changes with which scene the strip claims on each load, so comparing order
measured state, not sort. A valid check must **fix the scene first, then compare**, or compare
lane-header order only.

### 14.18 One-home audit: the Fix Queue and the lane queue are the same findings, rendered twice

Runner's G5 re-measure produced two different answers, and the disagreement was the finding.

| Surface | First row bottom | Verdict |
|---|---:|---|
| Fix Queue panel | 834px | above the fold |
| `by-category` lane queue | 1493px | below it |

G5 says "first actionable queue row" and does not say which surface it means. **That ambiguity is
not a drafting nit**, because both surfaces render the same findings.

**Confirmed by reading the source, not inferred from the screenshot.** `renderFixQueuePanel`
(`app.js:4379-4380`) renders `state.fixQueue.items` from `/api/projects/<name>/fixqueue`, and
`_fixqueue_items` (`webapp_server.py:2609`) iterates `report.get("findings", [])` — **the exact
array** the lane queue reads via `state.report.findings`. The server's own docstring states the
purpose: *"shared by `/fixqueue` and `/findings` so the two lists cannot drift. One build, two
shapes."* They do not drift because they are **the same list**, rendered in two places, in two
presentations: a full card with Locate/Rewrite/Discuss/Dismiss, and a lane row.

**This violates agreement #1 from the first debate and §1.1's membership principle.** §7 built
lanes inside `by-category` and left the Fix Queue panel rendering alongside it. §0.2's Tier 1 list
contains *two queues* and the spec never noticed.

**The decision, and it is forced by a principle rather than by preference:** one finding, one home.

- The Fix Queue is the surface that **opens by default** and carries the action verbs.
- The lane queue carries **ranking and lane identity**, which is this Track's entire contribution.

So the resolution is to **move the lanes and the rank into the Fix Queue panel and retire
`by-category` as a second queue** — not to delete either. Deleting the Fix Queue would remove the
verbs; deleting the lanes would discard the ranking Track B was built to produce. Merging keeps
both and satisfies the principle.

**G5's target is therefore disambiguated by the merge, not by a wording change**: after it, there
is one queue surface and "first actionable queue row" means one thing.

This is the largest remaining item in the arc and it is **not started**. It is recorded here,
with the evidence and the decision, rather than half-applied.

### 14.20 ONE HOME, landed: the lanes moved INTO the queue

**Precondition accepted and then revised by the code, honestly.** The stated precondition was that
`carded` dedupe must survive the move, "because the P1.8 assertions pin them". Reading the build
before wiring it showed that applying it literally to the Tier 1 Fix Queue would be wrong:

`carded` is **scene-scoped** — the union of current-scene findings plus script-level findings.
Subtracting it from the worklist would remove the scene the writer is reading from their to-do, and
empty the queue whenever they stand on a scene that has findings. A worklist that omits the page
underneath it is not a worklist.

**What the code actually showed, and it changed the answer.** The two surfaces are in **different
tiers**:

| Surface | Tier | Open by default | Measured first row |
|---|---|---|---|
| Fix Queue | 1 | **yes** (`defaultOpen: true`) | 834px |
| `by-category` ledger | 2, the Context disclosure | **no** | 1493px |

So the 1493px number was taken on a section a writer never sees unless they expand it. `carded`
existed only to stop the Tier 2 ledger repeating the two sections *beside it*. It was never in a
position to stop the Fix Queue, because the Fix Queue is in Tier 1. **P1.8's dedupe was internally
consistent and globally duplicating.**

**Landed:** the lanes, lane order, category sub-headers and per-row rank reason moved **up** into
`renderFixQueuePanel`, which now takes `{ lanes: true }`. The Tier 2 ledger, the `carded` set and
`dedupeDockFindings` are gone. The scene and script-level sections survive as **pointers**: a count
and where the rows went, keeping their keys and the `.dock-section-scene-findings` audit hook.

`carded` and `dedupeDockFindings` were deleted **deliberately, not collaterally** — they arbitrated
between card sections that no longer render cards.

### 14.21 G5 re-scoped to the default-open surface

G5 measured two numbers and returned one verdict, which is what made it ambiguous in the first
place. Scoped: **G5 measures the first actionable row on the surface that opens by default.** That
is the state the fold complaint was always about, and a writer's default state is Tier 1 with
Context collapsed.

This is not a loosening. A gate that can be passed by expanding a disclosure is weaker than one
that cannot. The expanded-state geometry is kept as a **recorded diagnostic, not a verdict**, so
the information survives without becoming a second pass/fail.

### 14.22 Guard migrations at 14.20, none weakened

| Guard | Before | After |
|---|---|---|
| 4 | "`by-category` key survives" | "the queue is the only place a finding is rendered" — the old guard pinned the very section that duplicated the queue |
| 9 | "queue appended before the detail cards" | "the ranked queue leads the default-open surface" — pinned Tier 1 build with `{ lanes: true }` |
| new | — | "the Tier 2 sections are pointers, not cards" |
| uncalibrated | pinned `renderFixQueuePanel(container)` | pins the **name**, walks the brace-balanced body, so the signature change did not silently scope it to the whole file |

All three new/changed guards mutation-verified: restoring the ledger, putting a `findingNoteEl`
card back in a pointer section, and dropping `{ lanes: true }` each fail with a precise message.
Fixed build re-run second, 10 passed.

### 14.23 Outstanding for the runner

`tests/e2e_browser_dock_sections.py` still opens the section by key `by-category`, which no longer
exists in the DOM. **P1.7 and P1.8 must be re-pointed at the Fix Queue panel** — both look for
`.dock-cat-group` inside a dock section. The migration already specified still applies: re-seed real
categories spanning two IMPACT tiers, assert rank order inside the lane, assert one rendering per
finding. That is now checkable in its strongest form, because "one rendering per finding" is a
property of a single surface rather than of an ordering between two.

### 14.24 P1.7 / P1.8 migrated to the merged queue, and what the migration actually found

The migration was **not** a selector re-point. Re-seeding surfaced a hole that would have made every
assertion meaningless:

> `SEED_JS` set `state.findings` and `state.report.findings` but **not `state.fixQueue.items`**,
> which is what the Fix Queue renders from. Before the merge that did not matter — the ledger read
> `report.findings`. After it, the seed left the queue rendering stale server rows and the whole
> fixture would have been measuring the wrong findings.

`SEED_JS` now populates `state.fixQueue.items`, and the `pacing` seed is gone.

**The fixture now discriminates instead of agreeing with itself.** The old seed gave the two Line-lane
rows a single unknown category, `"pacing"`, which now lanes to Uncategorised at impact 0 — so the old
"highs first" assertion had nothing to say. Re-seeded with two **real** categories at two **IMPACT**
tiers (`structure` 5, `dialogue` 3), which gives lane order and row order as separate things to assert.

**A defect caught before shipping, recorded because it is the kind that passes.** The first draft
seeded the *verified* row at **high** severity. Every assertion held — and proved nothing, because
severity and rank happened to order the pair identically. The fixture now seeds the verified row at
**low** severity, so "highs first" and "rank first" order it in **opposite** directions:

| Lane | Order | Why |
|---|---|---|
| Structure | medium, high | both impact 5; index tiebreak |
| Line | **low (33)**, high (30) | same impact; verified +3 decides it |

So the Line lane leads with its **low**-severity row, which is only correct because rank changed.

**Verified without a browser.** `groupByLane`, `rankScore` and `rankReasonText` were run in node
against the real `core.js` with the exact seeded fixture, and every expectation holds: lane order
`['structure','line']`, Line `[low, high]`, scores `33 > 30`, reason
`"ranked here: Line, impact 3, verified"`, findex set `0,1,2,3`. Those four are now permanent tests
in `tests/js/queue_lanes.test.js`, so a fixture that stops discriminating fails in CI rather than on
the runner's machine.

**Also migrated:** the collapse-contract block borrowed `"by-category"` as a **vehicle** for
dockSection's close/persist/motion behaviour. The vehicle is now `"coverage"` and the content probe
is generic (`.dock-section-body *`) rather than `.finding-note`, because the merge turned the
finding-bearing sections into pointers and a collapse test should not depend on which element a body
contains. Prefs keys follow: `dock_section_coverage`.

**New guard:** `test_the_e2e_does_not_reach_for_the_retired_section_key`. A Playwright locator naming a
removed key either trips an assertion or, worse, silently stops testing anything — which is how a
suite can go green against the wrong tree.

**Still unverified:** the DOM selectors themselves. There is no Playwright in this workspace. The
ordering contract is proven in node; the selectors that read it out of the page are the runner's.

### 14.25 RULING: the queue row keeps its depth and gains the verbs

Anchored run on `2ce132a`: **134 passed, 45 failed**. The failures are not one thing, and the
largest group is not a test bug.

**I introduced a regression at 14.20 and recorded it as a merge.** The Tier 2 ledger rendered its
rows with `findingNoteEl(f, index, {deep: true})` — a deep card carrying the evidence quote, the
rule/attribution chip, the finding's own observation, and the truth-axis verdict. The Fix Queue
renders `.fix-row` via `buildFixRow`: badges, issue, why, verbs. The merge adopted the Fix Queue's
renderer, so **every finding in the worklist lost its depth**. The runner's DOM audit found no quote,
no rule chip, no pin, no verdict row, no expand handler on a queue row.

Two consequences, neither of which is taste:

1. **The verdict judgments lost their surface.** The accuracy meter counts verdicts that nothing
   renders. That is a shipped feature deleted by omission.
2. **Evidence visibility failed.** The quote is not behind a disclosure; it is absent. The agreement
   both panels signed requires it on the card.

**The ruling:** depth is not negotiable; verbs are additive. **The lane row is the deep card with the
verb row attached.** `buildFixActions` was extracted so the flat report-page path and the lane path
share one verb row and cannot drift, while the lane path renders `findingNoteEl(..., {deep: true})`.

A reviewer choosing shallow rows would have had to retire the evidence agreement and rewire the
meter. That is a real design change and it was never written down, so it does not get to happen
because a merge happened to route rows through a different function.

**Test bugs fixed (3), all confirmed against code:**

- The two P1.7 lane assertions matched with `startswith`; the card prints `"Scene N — "`. Now
  substring, with the prefix stripped in the helper. **The sort needed no change** — the observed
  order was correct rank order.
- `livecheck` was asserted in the always-render set. `buildLiveCheckSection` returns null without
  lint state on every tree; it was never unconditional. Now asserted as present **exactly when**
  `state.lint` exists.

**Helper obsolescence fixed:** `live_cards`, `section_cards` and the dupe probe counted
`.fix-row`/`data-findex`. They now follow the deep-card contract (`.finding-note`,
`data-finding-index`) again, so every count-based assertion means something.

**New guard:** `test_the_queue_row_keeps_its_depth_and_gains_the_verbs`. That regression passed every
other check in this file, including the one-home guard. Mutation-verified both ways — reverting to
the shallow row fails, and keeping depth while dropping the verbs also fails.

### 14.26 The dock rendered NOTHING: a temporal dead zone, and what it proves

Anchored run on `43f1622`: **3 passed, 14 failed, zero `.dock-section` elements**. One throw.

`isAddressed` was a `const` arrow declared inside the Context builder at line 6694.
`renderFixQueuePanel` called it at 4642, and is itself invoked at 6643 — all three inside that same
function body. First use, then declaration, in the same tick: **TDZ, `ReferenceError`, the Evidence
lens aborted before a single section mounted.** All 45 previous failures, including the
collapse-contract gate that exits early, were downstream of that single throw.

I introduced it at 14.25 by calling `isAddressed` from the queue without checking where it was bound.
Hoisted to a module-scope `function` declaration, which is immune to ordering.

### 14.27 The guard found a SECOND defect on its first honest run

`rerender` — the call every lane category sub-header made — **does not exist**. The only binding in
the file is a `const` local to `buildFilterRow` (app.js:7909). Calling it from the chip handler was a
`ReferenceError` **on every click**. The category sub-headers shipped broken at §7 and nothing caught
it: python and node both went green, because the call is inside a callback and never executes during
a render.

It now calls `refreshAllFindingSurfaces()`, the ONE re-render entry point (P0.4) and exactly what
`rerender` itself wraps.

**Two defect classes in this arc that only the browser run could see** — CSS selector-list
destruction (§14 note), and now execution-order defects in render code. Neither `node --check` nor
pytest evaluates a browser render path. The runner is not a convenience; it is the only instrument
covering a whole category of failure.

### 14.28 Guard: `test_the_queue_renders_no_function_scoped_dependency`

Strips comments and string literals, folds in `core.js` (a classic `<script>` tag, so its top-level
functions are **globals**, not app.js bindings — without that, `groupByLane` and `rankReasonText`
read as phantom callees), then walks the queue's body and fails on any **bare** identifier it calls
that is neither module-scope nor function-local. `x.foo(` is a method and is excluded.

Mutation-verified twice, broken first and fixed second: restoring `isAddressed` as a `const` in the
other builder fails, and reintroducing the phantom `rerender` fails.

The first draft of this guard reported 35 nonsense names (method calls, prose) and was itself fixed
before being trusted — recorded because a guard that cries wolf gets ignored within a week.

### 14.29 Anchored 136/43: all three roots confirmed, and one was mine

Runner triage: 3 from `.fix-row`, 2 from a groundedness equality that predates
grounded-by-default, ~36 from seeds that no longer feed the queue. All verified against source
before acting.

**Root 3 is also a product defect, and the runner was right to ask.** Lane rows joined items to
findings **positionally**: `state.findings[item.index]`. `item.index` is correct only because
`_fixqueue_items` enumerates the array it built from. Nothing guarantees that pairing across a
report reload followed by a fixQueue reload.

`computeFindingId` is a content hash over category + quote + `scene_key`. That is precisely the
property that makes an id worth having — it is what lets a verdict or an addressed mark survive
re-analysis. **Positional index has no such property.** So the queue now joins by `finding_id`, with
index as the fallback for an older server payload that carries none.

**Seeds.** Four more payloads wrote `state.findings` and stopped there. After 14.20 the queue renders
from `state.fixQueue.items`, so those seeds rendered **zero rows, silently**. All four now write
items carrying `verification`, `rule_id`, `check_id` and `observation`, which is what the
deep-anatomy and verdict-meter checks actually need.

**`.fix-row` selectors (Root 1).** The dock queue row is a deep card with `queue-row`; `.fix-row` is
the flat report-page row only. Querying `.dock-section-fixqueue .fix-row` matched nothing, so P1.10
passed **vacuously — blind, not green** — and the P2.12 probe iterated zero rows. Re-pointed.
`.craft-shelf .fix-row` is correct and untouched: that is the report page.

**Pointer check.** It read `inner_text()` on a **collapsed** section, which returns only rendered
text, so the pointer line in the body was never in the string. Now `text_content()`.

**Lane category chips, first runtime coverage (14.27's gap).** No check had ever clicked one — which
is why a queue whose category filter could not be changed at all looked identical to a working one.
New check clicks the sub-header, asserts the row count narrows, that the ONE category field is set,
and that a second click widens it back.

**Two guards that were vacuous, and one that took three tries.**

`test_every_seed_that_writes_findings_also_writes_queue_items` passed its mutation test twice
before it worked. First it matched a character window that reached into the next seed; then it
matched raw text, and the block it guards **opens with a comment naming `state.fixQueue.items`**, so
deleting the assignment left the comment and satisfied the check. It matches code with comments
stripped now, and fails on the mutation.

### 14.30 Still open, stated rather than buried

The **groundedness equality** (2 checks) is not a fix, it is a decision, and it is the runner's to
call with product eyes: `OPEN_ON_SCENE_JS` counts every open finding (7 on the demo report) while
the queue renders filtered items with ungrounded rows behind the Kit A toggle. Either engage
`Show ungrounded` first, which also exercises the toggle, or compare against the grounded count. The
current assertion is simply wrong and I have left it visible rather than quietly relaxing it.

### 14.31 The verb row was not a budget collision. It was me duplicating the verbs.

The runner called the three geometry failures a collision between the 14.25 depth ruling and an
older one-row action budget, and put the decision to the writer. **It was neither.** Reading the
code:

- `findingNoteEl` renders `.finding-note-actions` with **Locate always**, and **Rewrite/Discuss
  whenever `!opts.pin`** — and the queue does not set `pin`, so all three render.
- `buildFixActions` then appended **a second Locate/Rewrite/Discuss** on top.

Six buttons doing three jobs. And the card's own comment, directly above those buttons, already
states the rule:

> *"Rewrite and Discuss are the writer's judgment and have one home each… Rendering them here too is
> what made one finding read as four competing surfaces at once."*

So the budget never had to move. The queue now contributes **triage only** — Dismiss and Reopen,
which the card does not have and which P1.10 puts in the queue — mounted **into the card's existing
action row** so there is exactly one action row per finding. The 14.25 depth ruling is untouched.

The runner also caught, correctly, that **my previous fix contained a second defect**: the join used
`indexOf`, which returns the first match, so two items sharing one content id both bound to
`findings[0]`. The shared-mark seed proves it — both cards render, the second is a clone. The join
is now a **consuming multimap**: the Nth item carrying an id gets the Nth finding carrying it, with
the index fallback retained and first-item-first-finding order kept. That defect arrived *inside* the
fix for the last one, which is worth recording rather than regretting.

### 14.32 The groundedness call, ruled

"Every live finding is in the queue" was never the contract and never was true. Kit A hides rows
with no evidence quote by default and puts them one toggle away. The honest contract has two halves
and the suite now states both:

1. every **grounded** live finding is in the queue, and
2. ungrounded ones are reachable through the documented toggle, **not dropped**.

`OPEN_ON_SCENE_JS` takes `(scene, groundedOnly)`. The reachability half is ONE unconditional check
rather than an `if`: a guarded check with no `else` records nothing when the guard is false while
the suite still prints PASS, and an `else` asserting a literal trips the hygiene ratchet. Folding
the branch into the condition is what the ratchet asks for. `IF_GUARD_CEILING` was **not** raised.

### 14.33 P2.12: the probe was reading the wrong attribute

`byIndex.get(r.dataset.findex)` on a `.queue-row` — but the merged row is a `.finding-note` and
carries `data-finding-index`. Every lookup was `undefined`, every row skipped, so `0/0` was a
statement about a broken probe, not about the payload.

The payload claim itself was also in the wrong place. It ran on the **demo report**, whose findings
carry no verification, so `withV > 0` could never hold and its failure was not a missing field. The
claim moved to the seeded path, where the seeded finding *has* a verdict. What stays on the real
report is the parity claim, which is meaningful either way: a row with a verdict paints one, and no
row paints a stray.

### 14.34 Seeds engage the Kit A toggle

The shared seed block stamps `ungrounded: !f.evidence_quote`. A CHECK finding and a SCENE/SCRIPT
finding legitimately carry no quote, so five checks were reading Kit A doing its job as a product
failure. Seeds now set `state.fixQueueShowUngrounded = true`. Kit A's hidden-by-default behaviour has
its own suite (`e2e_browser_ungrounded_filter.py`) with its own seeds, so this cannot weaken it.

### 14.35 The 14.29 join ruling was NOT implemented. It is now.

**Record the correction plainly: 14.29 claimed a join that never ran.** The inline code was

```js
const at = item._seen == null ? -1 : item._seen[item.finding_id] || 0;
```

`seen` starts at `0`, so `0 === -1` is never true, `hit` stays -1, `_seen` is never written, and
**every row fell back to positional binding on every render**. The shared-mark clone "passed"
because aligned arrays happen to agree positionally. The reorder robustness the ruling was for is
not implemented.

The deeper lesson is the runner's, and it is the one worth keeping: **a mutation test that cannot
distinguish the new code from the old code is certifying the old code.** The 14.29 guard
mutation-verified the presence of a call, never its reachability. The code under test never
executed, and the suite stayed green.

**The fix is structural, not a one-character edit.** The join moved to `core.js` as
`bindQueueItems(items, findings, findingIds)` — a pure function, so it is testable without a
browser, exactly as `groupByLane` is. The queue cannot now bind differently from the tests.

Two details the move also fixed:

- Lane entries carry the finding's **true array position**, not `item.index`. When the two disagree
  the card previously stamped `data-finding-index` pointing at the wrong row.
- `itemAt` is keyed by that true position, so the row and the verb row resolve the same finding.

**Four tests, and the mutation is the one that matters.** The reorder case — items whose ids point
away from their positions — cannot pass under positional binding. Both mutations were run broken
first:

| Mutation | Result |
|---|---|
| the exact 14.29 defect (`nth` undefined on first use) | reorder binds `[0,1]` instead of `[1,0]`, **test fails** |
| `indexOf`, first match wins | duplicate-id test **fails** |

108 node tests pass, up from 104. 14.29 should be read as "decided but not delivered" for that
commit; this is the delivery.

### 14.36 Open, with the ruling made

**The verb row is now a real budget question, and it is mine, not the writer's.** The duplication
theory is exhausted and the wrap persists: one action row per finding does not hold nine verbs at
current control sizes. **Ruling: the queue's own four stay inline — Locate, Rewrite, Discuss,
Dismiss — because that is the queue's grammar and P1.10 puts it there. The card's intent and verdict
cluster (✓, ⏹, the pin and why glyphs) collapses behind a disclosure**, with their existing
`finding-intent-hint` line explaining what the marks cost before the click rather than after it. Not
implemented this round; recorded so the next one does not reopen the question.

**The label-scope mismatch is not a toggle leak to be patched, it is N3.** The chip-on label counts
grounded-open-in-scene while the list beside it shows all-open-in-scene. Two surfaces printing
different scopes side by side is exactly what the counting contract forbids, and the honest repair is
for the label to count what the list contains.

**Three missing cards:** every static element of the admit path is verified clean by the runner, so
what remains is runtime state between the seed and the assertion. Not guessed at.

### 14.37 The membership ruling: scene-less findings split on provenance

Anchored 177/8, and the runner closed the missing-cards thread with three corrections, two of them
to their own prior analysis, which is worth noting because it is why this took four rounds.

**Correction owed and made: the Kit A theory was a red herring** for the three missing cards. The
toggle work was real and needed elsewhere. The clue that should have been taken two rounds earlier is
**invariance across implementations** — the symptom survived three different join implementations
unchanged, which meant it was never about the join.

**Root cause, confirmed by reading `core.js`, not inferred:** `findingLane:269` returned
`"observation"` for any finding with empty `scene_refs`, and `groupByLane:411` drops observation
entries from the queue. The three missing cards are exactly the scene-less seeded findings.

**The comment above it was false, and that is the part that matters.** It said an observation "is
shown outside the queue". Every render path was searched: writer-memory observations (a different
concept), per-finding observation text, flag titles. **No dock surface renders observation-lane
findings as cards.** A comment claiming a guarantee that does not exist is worse than the gap it
conceals, because it reads as one. Rewritten to state what is true: an observation is not on the
desk because it is not something you act on there; it stays in the report and the export, so nothing
is dropped, it is simply not worklist.

**The ruling.** Not "build an observations surface and leave the tests red until it exists" — that
defers the drop rather than ending it, and AGENTS.md:66 is not satisfied by a surface promised for
later.

The scene requirement exists because **locating is how you act on a finding**. That is *circular* for
a mechanical check whose subject is the missing anchor: "this clock jump has no slugline" cannot cite
a slugline, so the rule ate the defect it described. So:

| Finding | Lane |
|---|---|
| `theme` / `genre`, with or without a scene | `observation`, unconditional |
| no `scene_refs`, no `rule_id`/`check_id` | `observation` — an opinion with nowhere to point |
| **no `scene_refs`, but `rule_id` or `check_id`** | **queued**, `LANE_OF[cat] \|\| "uncategorised"` |

The signal is `rule_id` / `check_id`, which the analyzer really sets (`continuity.py:91-92, 157-158`)
— not a category invented for this argument.

**Four tests, mutation-verified both directions, broken first:** reverting the exception fails, and
queueing *every* scene-less finding while ignoring provenance also fails. The last one matters
because it pins the other half of the rule — the exception is narrow, not a general loosening.

112 node tests, up from 108.

### 14.38 The two item-3 assertions contradicted the ruling, and are rewritten not deleted

Anchored 179/6. The item-3 script finding is seeded as `category: "theme"`, `scene_refs: []`, with
neither `rule_id` nor `check_id` — so under §14.37 it is an observation on **two independent
grounds**. "All three reached a deep card" and "says it is about the whole script" therefore
contradict the ruling as written, and no product change short of un-ruling could make them pass.

**Rewritten to cover both halves, which is stronger than deleting them.** The script finding is
re-seeded as a **scene-less mechanical finding** — `continuity` with `rule_id: timeline_consistency`,
no scene — which is exactly the shape the exception exists for, so the browser now exercises the
exception *and* the whole-script scope label through the real render path. A `theme` opinion is seeded
beside it and asserted to **stay out of the queue**, with a scene.

The node suite already pinned both halves. **The browser pinned neither**, and the phantom `rerender`
is the standing precedent for what an unexercised path does.

### 14.39 The verb collapse, implemented

The queue's four stay inline — **Locate, Rewrite, Discuss, Dismiss** — because that is the queue's
grammar and P1.10 puts it there. The card's intent cluster (**addressed / next-pass / copy / why /
pin**) collapses behind a `<details>` labelled **"marks & tools"**, a real `<summary>`, so it is
keyboard-reachable and announces its state with no line of JS. The card already prints what those
marks cost in `finding-intent-hint`, so nothing is learned by hiding them.

**Gated on `opts.collapseIntents`, and off everywhere else.** The report page and margin pins keep the
flat row: only the queue stacks its Dismiss on top of the card's controls and only the queue overflows
the measured budget. The cluster binding is a hoisted `let`, because the disclosure is built after the
`opts.deep` block closes and a `const` inside it would throw on every shallow card.

### 14.40 The N3 label predicate, implemented

`openFindingsOnScene` walked `state.findings`, which includes rows the queue **hides** behind the Kit
A toggle. So the This-scene chip printed a grounded count beside an unfiltered list: two numbers, both
true, neither agreeing. It now counts `state.fixQueue.items` through `bindQueueItems` using the
**same exclusion rule as `queueCounts`** — dismissed out, Kit A hidden unless asked for,
writer-dispositioned rows bypassing the groundedness claim. One rule, three surfaces.

### 14.41 Guards, and one that was too weak

| Guard | Mutation it catches |
|---|---|
| scene chip counts the list's scope | label walks `state.findings` again |
| scene chip counts the list's scope | Kit A exclusion dropped from the label |
| one surface opts into the collapse | disclosure wrap made unconditional |

The third caught nothing at first. It counted `collapseIntents: true` call sites, which stays at one
even when the **wrap** is unconditional — so making the collapse global passed. It now pins the gate
expression itself. 2289 python tests, 112 node.

Both new tests were written without their `app_js` fixture parameter and failed on the fixture object
rather than the assertion. Fixed; noted because it happened twice in this arc and a test that errors
before asserting is not a test.

### 14.42 The wrap was width, not blockification — and the `display` declaration was inert

Anchored 179/7. The collapse landed; the row still wrapped to two. The runner's first hypothesis was
right about the symptom and about the cost ("one declaration") but the mechanism was different in a
way worth recording, because it changes what the fix is.

`.finding-note-actions` is **`display: flex`**, and **a flex child's `display` is blockified whatever
it says.** So `display: inline-block` on the disclosure did nothing, and the row wrapped on **width**:
the content box is 322px and "marks & tools" cost roughly 90 of it, landing the fifth item over the
edge. The disclosure was already a flex item in the row by construction.

**The fix is the label, not the layout mode.** The visible word is now `marks`, and the full phrase
lives in `aria-label` and `title`. P1.10 wants the gesture learnable *before* the click and a bare
glyph teaches nothing, so the visible word is shortened rather than removed. CSS now pins
`flex: 0 0 auto; min-width: 0` instead of a `display` declaration that was never load-bearing.

### 14.43 P2.14: pin stays in the cluster, and the test opens the disclosure

The pin button moved inside the closed disclosure, so the test's click found nothing reachable. The
card, the button and the endpoint were all correct; the path was simply not open.

**Placement called, and it is not the queue's four.** Locate jumps and Discuss consults; **pin
creates a permanent artifact** — a margin note on the writer's own script. It is the considered verb,
and one disclosure away is the right weight for it. The cluster's visible word `marks` covers addressed
and next-pass too: all three are dispositions, and pin is a disposition with a receipt.

The test now opens the disclosure by setting `d.open = true` before clicking, which is what a writer
does, and asserts the disclosure exists and opens on demand.

### 14.44 Guard, mutation-verified three ways

`test_the_disclosure_is_a_flex_item_not_a_block` pins the lesson rather than the old fix: the actions
row still carries `flex-wrap: wrap` (the rule the pin-rewrap check measures), the disclosure is pinned
as a non-shrinking flex item, the visible label is short, **and the full phrase is still in the
accessible name**. Dropping the label, dropping the `aria-label`, or dropping the flex pin each fail.
2290 python tests, 112 node.

### 14.45 GREEN: 187/0, exit 0, anchored

The first fully green run of `e2e_browser_dock_sections.py` since the merge. Nothing is
red-by-design, red-pending-ruling, or red-pending-investigation.

**Held simultaneously in one anchored run:**

| Contract | Proven by |
|---|---|
| 14.25 depth on every admitted row | quote, chip, pin, verdict, scope present at runtime |
| 14.29 join, true-position multimap | node-pinned against reorder AND duplicate-id mutations |
| 14.37 membership exception | both halves browser-exercised, not just node |
| single-predicate counting (N3) | chip label, queue rows and counts agree |
| 14.38 verb budget | five items, one row, 322px |
| 14.43 pin placement | disclosure opened first, note lands, button says it took |

Local at recording: **2290 Python pass**, **112 Node pass**. The two failures in
`tests/test_repo_hygiene.py` were `ModuleNotFoundError: playwright`; the separate Node failure was
`screenplay_studio/webapp/preview-ink-layer/tests/dom.test.mjs`. The previous wording incorrectly
attached the Python import error to both. See §14.50 for the dependency-complete run.

### 14.46 What green does NOT mean, stated before it is claimed elsewhere

A green suite is one instrument. Recorded so a later reader does not over-read it.
The G5/print statuses below were current at `fa81dba`. §14.48 records the subsequent G5 failure;
§14.51 records the later passing G5 and print re-anchors at `bd86a8e`.

- **G5 has never been re-measured as a named check since the merge.** The merge disambiguated it —
  there is one queue surface now, so "first actionable queue row" names one thing — but a
  disambiguated gate that has not been run is disambiguated, not passed. **This is the original
  complaint of the entire arc and it is the one gate still outstanding.**
- The print suite last passed against pre-depth DOM. Rows changed shape twice since (deep card, then
  the collapsed intent cluster). It needs one re-anchor, not a fix.
- Lane order and the `IMPACT` values await a real writer. Threshold A/B/C awaits real register
  material. Those are inputs that never arrived, not regressions.
- Every one of the seven rounds' findings above came from the browser run. Python and node were green
  while the dock rendered nothing, while the category chips threw on every click, while the join was
  dead code, and while a membership rule ate its own defect.

### 14.47 The collaboration record

Seven anchored rounds: one ship-blocker (TDZ), one guard-only fix driven to runtime coverage (the
chip click), one dead-code join exposed and structurally repaired, one false comment corrected, one
membership ruling with both halves browser-pinned, one width misdiagnosis corrected before it became
a declaration that did nothing.

The pattern that kept paying was reporting the **mechanism**, not the verdict, and letting the next
run judge it. Three times in this arc the first answer was wrong in a way only measurement caught:
the highs-first seed that passed while proving nothing, the multimap that certified its own fallback,
and the `display` declaration that was inert under a flex parent.


### 14.48 G5 measured on the merged queue: FAIL, 1007px

The runner confirmed served-tree identity at `fa81dba` on both runs. At 1440×900, lens scroll 0,
no manual scrolling and no page errors, the first actionable card bottom was **1007px**, identical
on both runs. The `<900px` gate remains unchanged and **failed**.

| Band | Measured extent |
|---|---|
| Top chrome, not individually itemized | 0–303px |
| Tier switch | 303–330px |
| Filters | 338–390px |
| Current scene | 390–453px |
| Queue section header | 467–500px |
| Queue preamble before the first card | 500–746px |
| First deep card | 746–1007px, 261px high |

The card's depth is not the remedy target. The runner's thin-input caveat stands: this output
admits one queue row. Two identical runs establish the failure on that input, not a margin for
other reports.

**Empty lane headers were a hypothesis, not the measured mechanism.** The full
`renderFixQueuePanel` path filters items before building entries; `groupByLane` creates only
populated groups. The new DOM test also runs the original renderer against a hidden Structure
row, a theme observation with a scene, a scene-less opinion and one admitted Line row. Only the
Line header renders. There is no evidence for an empty-lane suppression fix.

### 14.49 Compact the queue preamble, not the card or the gate

Source inspection identifies the pre-card occupants: the inner count/caveat/meter header, the
queue's Dismiss explanation, then lane identity and its first category chip on separate rows.
There is also a concrete spacing defect: `.dock-lane-group:first-of-type` never exempts the first
lane because the earlier `.craft-panel-head` is itself a `div`. These facts do not apportion the
246px into independently measured heights.

Implemented in `screenplay_studio/webapp/app.js` and `screenplay_studio/webapp/style.css`:

- The lane path opts into `fix-queue-ranked`, including the filtered-empty branch. The flat report
  keeps its layout and its explicit Fix Queue label. The dock section already supplies that label,
  so the compact inner count line retains all three counts without repeating the name.
- Counts occupy one grid row. The visible `impact weights uncalibrated` caveat and the same dawn
  percentage share the next. The track is shorter, not a different progress calculation. Conditional
  dismissed/ungrounded toggles share one wrapping row. Neither toggle is removed.
- The Dismiss explanation stays visible before the cards, in shorter copy with the same consequence:
  `Dismiss: out of this to-do, kept in the report.`
- The first category chip deliberately moves from `.dock-finding-list` into `.dock-lane-head`,
  beside `.dock-lane-title`. Later category changes retain their subheaders beside the relevant rows.
  All category-chip classes and the shared refresh callback survive. The combined heading stays sticky.
- A real lane-sibling selector adds separation only between successive lanes. The ineffective
  `:first-of-type` selector was **deliberately replaced**, not lost as collateral.

No selectors for finding anatomy or actions were dropped. No card renderer, membership rule,
counting predicate, rank weight, route, return stack or threshold changed. Side padding and type
sizes are unchanged. Nothing is clipped, scaled, given a fixed height or put behind a new disclosure.
The 0–303px arrival band is untouched.

### 14.50 Reachable-render guards, complete local suites, browser verdict pending

`tests/js/queue_preamble.test.js` executes the shipped `renderFixQueuePanel` with real core binding,
lanes and ranking in jsdom. Deep cards and unrelated application services are explicitly stubbed.
It checks the actual populated and filtered-empty branches, the flat-path exclusion, retained
counts/caveat/meter/toggles/explanation, first-category relocation and later-category ordering,
category clicks narrowing **and** widening through the shared refresh, absence of empty headers,
and CSS selectors matching the real first lane. **It has no layout engine and proves no pixels.**

Before the product edits, four new checks failed and two existing-behavior checks passed. Six
subsequent mutations each failed: unreachable compact opt-in; restored separate category row;
restored ineffective first-of-type exemption; restored stacked flex header; a refresh call present
but unreachable inside `if (false)`; global rather than queue-only compaction. Files were restored
byte-identically, then all six checks passed again.

Local verification after installing the declared missing test dependencies:

- `/tmp/ss/bin/python -m pytest tests/ -q -rf`: **2292 passed, 4 skipped**, exit 0. Before installing
  the Playwright Python package, the same run was 2290 passed and the two known import failures in
  `tests/test_repo_hygiene.py`. No browser binary or browser suite was run locally.
- `npm test`: **166 passed, 0 failed**, exit 0 after `npm ci`. No changes to the preview-ink-layer
  suite were needed. Do not carry forward the earlier environment's 112/1 result as a current failure.
- `node --check` for the changed application/test JS and `git diff --check`: pass. Existing Python
  queue, uncalibrated-copy, CSS-integrity and SPA guards were not weakened.

Recovery before editing: the checkout had reset to `5c1b953` with the prior work as uncommitted
files. Safety tag `safety/g5-reclone-20261016T120654Z` preserves snapshot `0e20dcc`. Its complete tree
was byte-identical to origin `fa81dba`; resetting the session branch to that origin left a clean
worktree before this change. The safety tag is retained.

**Status before the re-anchor:** G5 remained FAIL at 1007px. The next action was a served-tree
identity check on the pushed repair, the same G5 measurement, then re-anchors of
`tests/e2e_browser_dock_sections.py` and `tests/e2e_browser_print_media.py`. No predicted pixel saving
was reported as a result. §14.51 records the completed re-anchor.


### 14.51 Original fold complaint closed: all three re-anchors green on `bd86a8e`

The runner confirmed served-tree identity for all three runs on
`bd86a8eb45c8a027c2fe2fc869d725a682b685d4` and reported a cleaned worktree.

| Instrument | Anchored result | Exit |
|---|---|---|
| Named G5 probe, 1440×900 | **PASS**, first actionable row bottom **882px**, no page errors or scrolling | 0 |
| `tests/e2e_browser_dock_sections.py` | **187 passed, 0 failed** | 0 |
| `tests/e2e_browser_print_media.py` | **9 passed, 0 failed** | 0 |

| G5 geometry | `fa81dba` | `bd86a8e` |
|---|---|---|
| First row top | 746px | 621px |
| First row bottom | 1007px | 882px |
| Deep-card height | 261px | 261px |
| Margin to the unchanged 900px boundary | -107px | 18px |

The observed saving is **125px**, entirely before the unchanged-height deep card. The empty-lane
hypothesis was rejected, not implemented. Preamble compaction and the first-of-type spacing repair
closed the measured defect without weakening depth or moving the threshold.

The full dock re-anchor retains chip-click coverage, geometry, N3 counting, both membership halves,
depth, binding and verbs. The print re-anchor closes the outstanding pre-depth-DOM verification.
All three results belong to `bd86a8e`, not to the later documentation commit recording them.

### 14.52 The 18px margin is watched, not chased

The original complaint is closed on the measured input. An 18px margin is thin; it is not a reason
for speculative compaction or a wider threshold. The §8 regression requirement makes remeasurement
mandatory for future Tier 1 additions or geometry changes. A future failure is measured against the
same `<900px` gate, not excused by this passing anchor.

Remaining inputs for this arc: a real writer for lane-order/impact validation and real register
material for threshold A/B/C. `IMPACT` v0 stays visibly uncalibrated; the fuzzy-match threshold stays
at `0.72`. No additional product or test changes are justified by this closure report.


### 14.53 Simulated expert review is useful evidence, not a real writer session

At the user's request, an AI expert-style review now applies a senior screenwriter/novelist lens
to all 13 questions in `docs/REAL_WRITER_VALIDATION.md`, the current source, the recorded browser
anchors and the existing short Tenglish excerpt. Full report:
`docs/audit/2026-10-17_simulated_senior_writer_ux_review.md`.

The requested 25+ years of experience is a simulated perspective, not an actual credential. No
human participated, no long sitting or fresh browser run occurred, and the human checklist remains
unfilled. The review does not replace authentic register material or recalibrate weights/thresholds.

**A prior status statement was too strong:** external inputs block empirical calibration, not every
useful review or mechanically testable improvement. The simulation exposed an additional workflow
gap outside the previously covered acceptance cases.

**New code-confirmed follow-up:** `loopList` walks report order through `findingPassesFilter`, while
`renderFixQueuePanel` uses queue admission, binding and lane/rank ordering. A deterministic Node
probe using shipped functions and extracted queue expressions produced queue indices `[1, 0, 5]`
versus loop indices `[0, 1, 2, 3, 4, 5]` on constructed English controls. The extra loop entries were
a theme observation, an ungrounded note and a scene-less opinion. A single-category positive control
agreed on `[1]`; a two-item Line case produced queue `[1, 0]` versus loop `[0, 1]`.

These are logic results, not pixel or human-preference measurements. The old browser anchors remain
valid for what they covered. No runtime or test assertion changed. The review also identifies the
protocol's stale highs-only-arrival question: the shipped default includes all three severities.

**Next:** repair shared loop/queue traversal semantics with discriminating tests, explicitly preserve
disposition behavior, then verify browser traversal on the pushed repair. Do not add lane membership
to the general predicate, silently retune IMPACT or treat the simulated checklist as a completed
human study. Writer validation and native-register calibration remain separate open requirements.
