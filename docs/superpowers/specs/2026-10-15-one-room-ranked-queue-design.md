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

G5 is the one the panel could not previously make. It is measurable **today** because the instrument
exists.

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
