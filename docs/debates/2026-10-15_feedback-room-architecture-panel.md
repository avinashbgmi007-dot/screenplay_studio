# Panel Debate — the Post-Analysis Feedback Room

**Date:** 2026-10-15 · **Branch:** `arena/e6a57b71-screenplay-studio` · **Base:** `5c1b953`
**Read from:** `avinashbgmi007-dot/screenplay_studio` @ `origin/arena/e6a57b71-screenplay-studio`,
working tree clean, no local modifications to `app.js` / `index.html` / `style.css` /
`screenplay_analyzer/` at the time of reading. Re-verify with `git rev-parse HEAD` before trusting a
line number.

> **REVISION 2 (2026-10-15), after external review.** Three factual errors corrected: the finding
> taxonomy is **eight** categories at `grammar.py:45-48`, not the twelve *passes* at
> `pipeline.py:847`; `SEVERITIES` is at `grammar.py:50`, not `:52`. Two substantive gaps closed:
> #10 reframed as promotion of an existing component (`app.js:7446-7451`), and the 8-to-2 bin mapping
> is now specified in §4a. **#8 is WITHDRAWN** as illegal against `tests/e2e_browser_layout_audit.py`
> (legal dock ceiling 676px) — see `2026-10-15_critique-two-agent-panel.md` §2. The branch was absent
> from `origin` during the first draft, so this document was not reproducible; it now is.
**Question put to the panel:** the Feedback room is visually cluttered after analysis. What belongs
in it, how should it align screen-wise, and what is the architecture-level cause?
**Method:** every claim below is grounded in a file and line read from this checkout. Where a claim
is an opinion rather than a measurement, it is labelled `[opinion]`. Where a claim rests on weak
data, it is labelled `[weak data]`.

---

## 0. Capability report, before the debate

Read this first so the panel's authority is not overstated.

**Could not run:**

| Asked for | Status | Why |
|---|---|---|
| Load multiple skills | gstack **not installed** | `.agents/skills/gstack/` does not exist in this checkout; the repo carries only `.agents/skills/sameer-humanizer/SKILL.md` and `.agents/skills/script-doctor-humanizer/SKILL.md`. No `bin/`, no `lib/`. The preamble script resolves to a missing directory. **gstack is in degraded mode.** |
| Install plugins | No plugin system | This harness has no plugin/package marketplace. Nothing to install. |
| Summon multiple agents | No Task/Agent tool | This arena agent has no subagent-spawn tool. The four experts below are **argumentative personas I executed as four separate, independently-reasoning passes**, not concurrent model calls. They are as rigorous as I could make them, and they are **not** four independent models. Treat convergence as weaker evidence than true multi-model agreement. |
| Establish MCP connections | Not attempted, determinately | The user has no apps connected. Calling the loader would return `disconnected`, which I can predict without burning a call. MCP would not change this debate: it is an argument about local DOM geometry and finding semantics, not about data in Notion or Slack. |

**Could and did do:** read the live source (`index.html`, `app.js`, `style.css`, `screenplay_analyzer/`),
read the prior audits so the panel does not re-tread settled ground, and ran four adversarial passes
followed by a critique pass on this document itself.

The repo's two humanizer skills were read. Their rule that the doctor "argues with the script, never
the writer" is applied by Expert D below, which is why he frames findings as *"this scene is
coasting"*, never *"you made a mistake."*

---

## 1. What the panel is arguing about (the shared brief)

Every expert received the same brief before any position was taken.

**The Feedback room today:**

- Two tabs: `#room-cowrite-btn` / `#room-feedback-btn` (`index.html:152-153`).
- A Context dock with four lens tabs: Evidence, Sameer, Sushruta, Stash & Notes
  (`index.html:277-281`).
- A right-edge gutter with two tabs: Sameer, Consultant (`index.html:455-456`).
- A legacy `#feedback-panel` div, now **empty and retired** (`index.html:450`).
- Evidence lens Tier 1 order: arrival strip → ambiguous-marks notice → filter row + fix-loop chip →
  current-scene box → Fix Queue (`app.js:6517-6560`).
- Evidence lens Tier 2: one collapsed "Context" disclosure holding the former ~12-section stack.
- Dock geometry: `width: 380px`, `min-width: 320px` (`style.css:5507-5510`).
- Desk toolbar is `.auto-hide-chrome` (`style.css:4742-4743`).
- Dawn control appears twice: `#dawn-btn` sidebar (`index.html:78`) and `#status-dawn` status strip
  (`index.html:474`).
- **Eight finding categories** (`grammar.py:45-48`): theme, character, structure, dialogue,
  scene_function, plot_thread, genre, continuity. `CATEGORY_LABELS` (`app.js:4232-4236`) carries ten
  keys, two of them (`voice`, `subtext`) stale: they appear in neither `FINDING_CATEGORIES` nor
  `ALL_CATEGORIES`.
- **Twelve model-based analysis passes** (`pipeline.py:847`), which is a *different* set and not a
  finding taxonomy: dialogue, theme, character, structure, scene_function, principles,
  setup_payoff, char_reads, character_dials, coverage, genre, logline_test.
- Severities `low / medium / high` (`grammar.py:50`).

**The prior audit's verdict was Option A+, and it shipped.** `renderTier1Worklist` and the Tier 2
Context disclosure are live. The legacy panel is deleted. So the panel is **not** re-litigating
"collapse the lens." That work is done.

---

# PART 1 — The End-User Productivity Advocate vs. its Critique

## 2. EXPERT A — Productivity Advocate (end-user lens)

**Stance:** the product's job is to cut the wall-clock between "analysis finished" and "line edited."
Everything that does not do that is decoration, however well designed.

**A1. The cost is in the decisions before the keystroke, not the reading.**
Measured against the shipped Tier 1: the writer passes arrival strip, ambiguous-marks notice, four
severity chips, ~9 category chips, the fix-loop chip, the current-scene box, and *then* reaches the
Fix Queue row, clicks Locate, scrolls the manuscript, double-clicks a line. That is roughly eight
decisions before the first keystroke of revision. A 20-minute analysis gets repaid with 8 minutes of
reading chrome. **[opinion, grounded in the render order at `app.js:6517-6560`]**

**A2. One screen, three questions, in this order.**
1. *What is most broken?* 2. *What do I do about this specific thing right now?* 3. *Did last pass
land?* Every current section must justify itself against those three. Everything else is summoned.
Arrival strip is question 3 but is rendered first, which is why it gets skipped. **[opinion]**

**A3. Make the default do the work.** The queue should open as a **decision**, not a list: top row
rendered as "Fix this line" with the line in view, not a card you must click through to understand.

**A4. Row = location + content + verb, fused.** A finding row must carry scene **and page**, the
issue, the quote, and the four verbs. No hunt step. Today the row is the "what" and Locate is the
"where", which forces a click between them.

**A5. Once-per-script controls do not belong in the primary row.** Re-parse, Compare, Beat Board,
and four export formats are insurance, not workflow. They belong in the command palette, which
already exists (`⌘K`, `index.html:156`).

**A6. Keyboard is the default entry, not an escape hatch.** The fix loop exists and is excellent
(`N`/`P`, mark, park, discuss, copy, `Esc`). It should be the announced default after analysis
completes, not a chip the writer has to discover.

**A7. The real metric is fixes-per-analysis, not seconds-per-edit.** Analysis costs 6 to 15 minutes
and can be cancelled mid-stage. If a writer cannot verify a fix cheaply, they batch their fixes,
which destroys the line-level loop that is the whole reason the tool exists.

**A8. Do not show a control before showing its consequence.** The category chips should not appear
until severity chips have been touched.

## 3. EXPERT B — Critique of A

**Stance:** A is optimizing the first sixty seconds and billing the product in month two.

**B1. A's headline metric is gameable, and gaming it breaks trust.**
Delete the arrival strip and seconds-to-first-edit collapses. So what. The arrival strip answers
*"did my edits land?"* Without it the writer re-runs analysis blind, gets a different number, and has
no idea whether the tool is working. Throughput **with retained trust** is the real objective.
Productivity is not speed.

**B2. A8 is exactly backwards for filters.**
"Hide the control until it's needed" means the writer never sees the severity distribution. A
writer who sees "5 shown of 87" believes the tool found five problems. A writer who sees
`high 12 · medium 40 · low 35` understands they are looking at a filtered slice of a large
diagnosis. The distribution **is** the information. Hiding it manufactures false confidence, which
is the most expensive kind of clutter there is.

**B3. A2's "one screen with three answers" is a longer column, not a shorter one.**
At 380px, three stacked answers wrap. A is asking for progressive disclosure to solve a problem
that horizontal composition would solve, in a rail built for glance-sized metadata.

**B4. A5 calls insurance clutter.** If the FDX parse is wrong, Re-parse must be one click, not one
command-palette invocation. Hiding a control does not remove the task; it removes the writer's
ability to *know the task exists*. That is worse.

**B5. A3 and A8 collide with the app's actual failure history.**
Every serious defect in this codebase is invisible automation, not visible clutter:
- **GAP-3** (`FULL_FEEDBACK_AUDIT_VERDICTS.md`): the arrival strip reported `Fixed: 2 · New: 2`
  with **zero writer action**, because `revision.py:143-156` mixed a list length with a set size.
- **GAP-4**: the consultant was handed `quote = null`, so "why was this flagged?" answered at
  project level instead of about the finding on screen.
- **GAP-1**: the ONE filter drove ink and the loop but not the board list, so page and ledger
  disagreed by 15 cards against 9 rows.

In all three the fix was to **project the truth explicitly**. A's "make the default do the work" is
the design instinct that caused them.

**B6. A's model assumes the writer already knows what to fix.**
Persona 1 is the primary user (`docs/USER_PERSONAS.md`): the goal is to *understand WHY* a script
does not work. An unopinionated "fix this line" tool teaches nothing and is indistinguishable from a
linter. A is quietly optimizing for Persona 2, the working rewriter, and sacrificing Persona 1.

**B7. A never once accounts for the re-run cost.** A7 gestures at it and then A stops. The cost
structure is: analysis is minutes, editing is minutes, re-analysis is minutes. The lever is
*whether the writer can tell a fix worked without paying a re-run*, which is a provenance problem,
not a layout problem. A solves layout.

**Verdict from B:** A is right that the Fix Queue must be the primary surface and right that the
room toggle is dead weight. A is wrong that the arrival strip, the provenance line, and the filter
distribution are decoration. **Keep all three.** They are not chrome, they are the reason the numbers
are believed.

---

# PART 2 — The UI/UX Design Architect vs. the Veteran Screenwriter

## 4. EXPERT C — UI/UX Design Architect

**Stance:** Report 2 fixed the clutter at the **section** level and never touched the **surface**
level. The disease moved from twelve sections in one column to four navigation spines across the app.

**C1. The room toggle is vestigial, and it is the most expensive thing on screen.**
`openFeedbackView()` (`app.js:8426-8431`) does this:

```js
async function openFeedbackView() {
  if (state.view !== "cowrite") setRoom("cowrite");   // <-- switches INTO Co-write
  ...
  openDock("evidence");
}
```

The **Feedback** button switches the writer **into the Co-write room**, then opens a dock lens. Both
tabs of the `role="tablist"` land in the same physical room. The tab that says "Feedback" has
`aria-controls="room-drawer"` (`index.html:153`), which is literally the *partner* region, labelled
`aria-label="Partner"`.

**Correction to my own first reading, stated plainly:** this routing is *intended*. Option A+ moved
the ledger into the dock on purpose. The defect is not the route. The defect is that the control
still presents as a **two-room tablist** while there is only one room, so every click on it costs the
writer a re-orientation ("where did that take me?"). That is a trust tax, and it is worse than
visual clutter because it is invisible until it is annoying.

**C2. Three spines carry the same payloads.**

| Payload | Room toggle | Dock lenses | Gutter |
|---|---|---|---|
| Sameer | `cowrite-panel` / drawer | `#dock-tab-sameer` | `#gutter-sam` |
| Sushruta | (retired FV panel) | `#dock-tab-sushruta` | `#gutter-doc` |
| Evidence | `#room-feedback-btn` | `#dock-tab-evidence` | (none) |
| Dawn | (none) | (none) | sidebar `#dawn-btn` **and** strip `#status-dawn` |

Sameer has **four** reachable homes: `#cowrite-panel` (`index.html:419`), `#room-drawer`
(`index.html:402`), `#dock-tab-sameer` (`index.html:279`), `#gutter-sam` (`index.html:455`).
The gutter (`.gutter`, `style.css:3979`) is a literal duplicate of dock lenses 2 and 3, and is
already `display: none` under 900px (`style.css:3575`) because it ran out of room. It is chrome
that survived its own breakpoint.

**C3. The primary surface is sized like a sidebar.**
380px open, 320px floor (`style.css:5507-5510`). A Fix Queue row must carry severity, scene and
page, issue, quote, rule id, four verbs, and the addressed state. At 380px that is roughly six
wrapped lines per finding. The Fix Queue is the one surface that opens by itself
(`app.js:6554-6559` comment: *"the ONE section that opens on its own"*) and it is the narrowest
surface in the app.

Meanwhile `AGENTS.md:56` sets a hard invariant: **"script pane never <50%"**. So the manuscript
never gets the rail's width. Page and ledger are permanently in a tug-of-war over the same 1440px,
and the writer loses every time because the manuscript is what auto-hides.

**C4. Chrome hides the verb.** `.auto-hide-chrome` sets `#project-bar` and `#desk-toolbar` to
`opacity: 0; pointer-events: none` (`style.css:4742-4743`). Run Analysis is the entry point to the
product's entire reason for existing, and on a first visit there is no visible way to start.

**C5. Eight ways out, one destination.** welcome, dashboard, idea canvas, script desk, revision,
compare, beatboard, premise. Seven views each carry their own "Back to the page" button
(`index.html:480, 501, 522, 554`).

**Architect's rules, which the rest of the panel tests itself against:**

- **R1 One spine.** Every object reachable by exactly one control. Duplication is a per-glance tax
  and it drifts, which GAP-1, GAP-3 and GAP-4 each prove.
- **R2 Geometry follows role.** 380px is a glance column. A worklist is a working column, minimum
  44rem.
- **R3 Chrome never hides the verb.** Progressive disclosure may hide secondary affordances. The
  product's entry point is not secondary.
- **R4 Provenance is not chrome, and neither is the queue.** The queue is not a summary of findings.
  It is a queue.

## 5. EXPERT D — Veteran Screenwriter (20+ years)

**Framing per the repo's own humanizer rule** (`script-doctor-humanizer`): argues with the script,
never with the writer.

> I've read four thousand scripts and worked on sixty of them. Your tool is arguing with itself in
> front of me, and it does it with a severity model it got from a confidence score.

**D1. I did not ask for a verdict. I asked whether my second act is dead.**
`CONSIDER / RECOMMEND / PASS`, comparables, logline test, genre fit, and the character dials are a
producer's memo and a coverage analyst's memo. They live in the Coverage block today. That block
should be a drawer nobody opens twice. I know what I want to do. I do not know what the script is
doing wrong, and those are different questions.

**D2. Your "high" is a confidence value wearing a craft costume.**
`SEVERITIES = ["low","medium","high"]` (`grammar.py:50`) is assigned by a model that also had to
decide whether it was sure. A high-confidence note about a comma splice ranks beside a
high-confidence note that the middle of the script has no turn. Those are not the same class of
problem. Show me two numbers, not one: how sure you are, and how much page this costs.

**D3. What actually kills a script, in the order I care:**
1. The turn is missing, or the middle is a list of events (`structure`)
2. Characters say what the audience already knows (`dialogue`)
3. The protagonist is passive for forty minutes (`character`)
4. Setup with no payoff in the last act (`setup_payoff`)
5. Scenes that change nothing (`scene_function`)

Everything else is a footnote. Eight categories is a filing system that matches your module layout,
not a diagnosis that matches my afternoon.

**D4. The dials are a waste of my time.**
A 1-to-10 slider on "brooding" tells me nothing I don't feel reading the scene. It is the machine
reporting its own guess back at me wearing a number, and numbers feel like grades. Hide them until
I ask "tell me more about him."

**D5. Bin by what I do next, not by which module produced it.**
Two bins survive: **fix this line** and **fix this structure**. Under each, the category is
metadata. Everything else is a filter, not a heading.

**D6. Your own audit says 1 of 9 quotes verified.** `FULL_FEEDBACK_AUDIT_VERDICTS.md` row C1, on
`gun_pen.pdf`. I am not going to trust a quote you have already caught yourself not verifying,
rendered in the row where it looks like proof. `[weak data: 6 pages, 3 scenes, demo craft model. This
is the demo floor, not a production rate. Direction holds, number does not.]`

**D7. I need what is working, protected. You do not give it to me.**
My real fear in revision is breaking something good. Give me a **"don't touch" list**: the five
strongest scenes, the setup that already pays off, the voice that stays consistent across the
script. The app shows me exclusively what is wrong. That is a one-sided conversation, and I have
been on the wrong end of one-sided conversations my whole career.

**D8. The screen should be the script, full width, with the ledger as a margin I can throw away.**
Triage is a list. Revision is a page. Those are two states, not one compromise column. You are
forcing both into a 380px rail beside a squeezed manuscript, and calling the compromise "a lit
instrument in a dark room" while dimming the manuscript to fit the instrument.

**D9. Offer me the instrument that has never lied: read it aloud.**
Dim everything, give me the page and nothing else, one scene at a time. You would be selling me
less software and I would be grateful.

**D10. The revision log is the product.**
At the end I want **a letter to myself**: what I changed, why, what is still open, what I decided
not to change. `report.md` is a machine dump. Nobody wrote it by hand and nobody will read it.

---

# PART 3 — Cross-examination

**Clash 1: Who gets the 1440px?**
C says give the ledger the width, it is the primary surface. D says give the page the width, the
ledger is a triage tool you summon.
**Resolution:** both are right about a different mode, and the current dock cannot express both
because it is one fixed 380px with one fixed content set. Split the dock by mode: **triage** at
44rem+ with the full queue, **revision** at ~200px showing only the addressed/open rail, page taking
the rest. Different content justifies different geometry. This satisfies C's R2 and D's D8 without
touching `AGENTS.md:56`'s 50% invariant.

**Clash 2: Kill the room toggle?**
C: delete it, it is a vestigial spine. D: I do not care about the mechanism, but do not delete the
word "Feedback". To a writer "Feedback" means somebody is talking to me. "Analysis" means a machine
graded me. The label carries meaning the toggle does not.
**Resolution:** delete the tablist, keep the *reachability* of the word. One control, one
destination, and the control is labelled by what it opens, not by which room it teleports you to.

**Clash 3: Does Run Analysis stay hidden?**
C: never, R3. D: yes, and while you are there put the time estimate on it and keep Stop where it is.
`#desk-analyze-cancel` (`index.html:184`) is good and should not move.
**Resolution:** unanimous. C's R3 is C's only rule D disputes, and D endorses it.

**Clash 4: Unverified quotes, hide or show?**
C: mark them visibly distinct, never hide, hiding state is how GAP-3 happened. D: at 11% verified,
an unverified quote in the row reads as proof; default them out.
**Resolution:** **conflict, and the repo arbitrates.** `AGENTS.md:66`: *"Flag, don't drop —
unverifiable findings are flagged, never silently removed."* D's proposal as stated is a direct
governance violation. The compliant version of D's instinct: **flag in place and demote in rank**,
an unverified-quote row sorts below every verified row of the same severity. D keeps the trust
protection; `AGENTS.md` keeps the flag-not-drop rule.

**Clash 5: Is the filter row clutter?**
A: hide it until touched. B: the distribution is the information. C: one control, keep it, it is the
thing that made page and ledger agree. D: severity is the wrong sort key anyway (D2).
**Resolution:** A loses, 3 to 1. The row stays and it becomes a **two-key sort**: craft impact
first, then verification state (per Clash 4). D's complaint is answered by changing the sort key,
not by removing the control.

---

# PART 4 — THE AGREED LIST

All four positions, converged. Ordered by cost-to-ship, cheapest first.

| # | Agreement | Grounded in | Cost |
|---|---|---|---|
| 1 | Delete the room tablist. One destination. One control per object. | `app.js:8426-8431`, `index.html:152-153` | Low |
| 2 | Delete the gutter. It duplicates dock lenses 2 and 3 and is already `display:none` under 900px. | `index.html:455-456`, `style.css:3979, 3575` | Low |
| 3 | Delete the duplicate Dawn control. Two controls, one state. | `index.html:78, 474` | Low |
| 4 | Sameer converges to exactly two homes (desk panel, dock lens). No more. | `index.html:279, 402, 419, 455` | Low |
| 5 | Run Analysis is never behind auto-hide chrome. Add an ETA to the button. Keep Stop. | `style.css:4742-4743`, `index.html:178-184` | Low |
| 6 | Severity becomes two keys: craft impact, then verification state. An unverified quote never outranks a verified one. **Confidence-vs-craft-cost is NOT resolved here** — see the revision note; it is analyzer-side work. | `grammar.py:50`, `AGENTS.md:66` | Medium |
| 7 | Sort bins are **fix this line** and **fix this structure**. The 8-to-2 mapping is specified below, not left as a slogan. | `grammar.py:45-48`, D3/D5 | Medium |
| 8 | ~~The dock is mode-aware: triage 44rem+~~ **WITHDRAWN — fails the layout gate.** See the critique doc, D1. The legal ceiling is 676px. | `style.css:5507-5510`, `layout_audit.py:442` | Blocked |
| 9 | Coverage verdict, comparables, logline test, and dials leave the primary path. Dials reveal on request. | D1, D4 | Medium |
| 10 | Promote the **existing** "What's working (N)" (`app.js:7446-7451`) out of Tier 2 into Tier 1, and add per-scene strongest-scene selection. Promotion, not invention. | D7, `app.js:7446-7451` | Medium (was Large) |
| 11 | Keep the arrival strip and the provenance line. They are not chrome, they are why the numbers are believed. | GAP-3, GAP-4, B1 | Keep |
| 12 | Report.md's finale becomes a writer's letter: what changed, why, still open, deliberately untouched. | D10 | Large |
| 13 | Everything ships as deletion or unification. **No rewrite.** 1,983 test functions across 222 files bind to the current shell. | `tests/*.py` | Constraint |

### 4a. The 8-to-2 bin mapping (specification, not slogan)

Added in revision. `FINDING_CATEGORIES` is **eight** (`grammar.py:45-48`). Mapping every one:

| Category | Bin | Rule |
|---|---|---|
| `structure` | **Fix this structure** | missing turn / event-chain |
| `plot_thread` | **Fix this structure** | setup and payoff economy |
| `scene_function` | **Fix this line** | the scene changes nothing |
| `dialogue` | **Fix this line** | characters state what is known |
| `character` | **conditional** | `len(scene_refs) <= 2` → line bin; `>= 3` → structure bin. Passivity in a scene is a page problem; an arc that never turns is a script problem. |
| `theme` | **neither** | not a defect, an observation. Not a queue row. |
| `genre` | **neither** | conformance is a Coverage note, not a fix. Not a queue row. |
| `continuity` | **neither** | deterministic mechanical check, `check_id` present. Batches to the bottom. |

**Net effect: the queue's category surface drops from eight to five (four fixed plus a conditional),
and three categories stop being queue rows at all.**

This strengthens the two-agent panel's agreement 5 rather than merely supporting it. That panel ruled
`theme`/`genre` script-level rows should get **no Locate button**. The correct fix is one step
further: they should not be rows in the fix queue at all, so there is no button to get wrong. A
`Locate` button with nothing to locate is exactly the architect's own R3 violated.

### 4b. Falsifier for agreement #13 ("no rewrite")

Added in revision, because self-critique item 3 said the claim is untested. **#13 falls if any of
these is true**, and each is checkable before a line of UI code is written:

1. Fixing agreement #8's replacement requires changing the manuscript resize observer contract
   (currently implicit in `#context-dock`'s width transition, `style.css:5507-5516`).
2. Agreement #6 or #7 requires a new field on the finding object that `dedupe.py` whole-row
   collapsing would silently drop (`screenplay_analyzer/dedupe.py:242`).
3. Any of #1-#5 requires editing a `role="tablist"`/`aria-controls` pair that
   `tests/e2e_browser_deep_links.py` or `tests/e2e_browser_one_matcher.py` pins.

If any holds, #13 is wrong and this panel's central constraint fails. That is the test.

**What was rejected, and by whom:**
- A3 "make the default do the work" → rejected by B, C, and D. Invisible automation caused GAP-1, 3, 4.
- A8 "hide controls until their consequence" → rejected by B. Hides the distribution, manufactures false confidence.
- A5 "move once-per-script controls to the palette" → rejected by B. Insurance is not clutter.
- B2 "the distribution is the information" → **upgraded, not rejected.** It became agreement #6: the distribution survives, but as a second sort key rather than a first-class display.
- D6 "default unverified quotes out" → **modified** by `AGENTS.md:66` into demote-in-rank, not hide.
- B7 "optimise for fixes-per-analysis" → **absorbed** into #12, the letter to self.

---

# PART 5 — Full pointer dumps (uncut, per expert)

## EXPERT A — Productivity Advocate, every pointer

1. Eight decisions before first keystroke (`app.js:6517-6560`).
2. One screen, three questions: what is broken, what now, did last pass land.
3. The Fix Queue should render as a decision, not a list.
4. Row fuses location and content, no hunt click.
5. Once-per-script controls belong in `⌘K` (`index.html:156`), not the desk row.
6. The fix loop should be the announced default after analysis, not a discoverable chip (`index.html:153`, `app.js:6538-6540`).
7. The metric is fixes-per-analysis, not seconds-per-edit.
8. No control before its consequence.

## EXPERT B — Critique, every pointer

1. Seconds-to-first-edit is gameable by deleting the arrival strip.
2. Trust, not speed, is the objective.
3. Hiding the filter distribution manufactures false confidence.
4. Three stacked answers in a 380px column is a longer column, not a shorter one.
5. Insurance controls are not clutter; hiding them hides the task's existence.
6. Invisible automation is this codebase's demonstrated failure mode: GAP-1, GAP-3, GAP-4, all fixed by projecting truth explicitly.
7. A optimizes Persona 2 and sacrifices Persona 1, the primary user (`docs/USER_PERSONAS.md`).
8. A never accounts for the 6 to 15 minute analysis cost.
9. Verdict: keep arrival strip, provenance line, and filter distribution.

## EXPERT C — UI/UX Design Architect, every pointer

1. `openFeedbackView()` at `app.js:8426-8431` calls `setRoom("cowrite")`: Feedback routes into Co-write.
2. `#room-feedback-btn` has `aria-controls="room-drawer"`, an `aria-label="Partner"` region (`index.html:153, 402`).
3. Sameer has four homes: `index.html:279, 402, 419, 455`.
4. `.gutter` (`style.css:3979`) duplicates dock lenses and is `display:none` under 900px (`style.css:3575`).
5. Dawn duplicated at `index.html:78` and `index.html:474`.
6. Dock is 380px/320px (`style.css:5507-5510`) while holding the one section that opens by itself (`app.js:6554-6559`).
7. `AGENTS.md:56` "script pane never <50%" means the manuscript never wins the width argument.
8. `.auto-hide-chrome` hides Run Analysis (`style.css:4742-4743`).
9. Seven views, each with its own "Back to the page" (`index.html:480, 501, 522, 554`).
10. R1 one spine. R2 geometry follows role. R3 chrome never hides the verb. R4 provenance and queue are not chrome.
11. Section-level clutter was solved. Surface-level clutter was never touched.

## EXPERT D — Veteran Screenwriter, every pointer

1. Coverage's CONSIDER/RECOMMEND/PASS is a producer's memo. Not asked for.
2. `grammar.py:50` severity is a confidence value, not a craft priority. Ship two numbers.
3. The five things that kill scripts, in order: turn, exposition, passivity, dangling setup, inert scenes.
4. Character dials are the machine grading itself. Reveal on request.
5. Two bins: fix this line, fix this structure. Category is metadata.
6. `FULL_FEEDBACK_AUDIT_VERDICTS.md` row C1: 1 of 9 quotes verified. Do not render unverified quotes as proof. `[weak data: demo model, 3 scenes]`
7. There is no "don't touch" list. Add it.
8. Two modes, not one compromise column: triage list, revision page.
9. Ship a read-aloud mode. Page only, everything dimmed.
10. The revision letter to self is the deliverable. `report.md` is a machine dump.

---

# PART 6 — Self-critique of this document

Run before publishing, per the mandate. Six things this document gets wrong or leaves soft.

1. **C1 overstates its own case, and I corrected it mid-draft.** My first pass called the Feedback
   routing a bug. It is not, Option A+ did it on purpose. The real defect is the *tablist framing*,
   and the correction is in the text. If a reader takes only the headline, they will implement a
   misdiagnosis.
2. **D6's number is the demo floor.** 1-of-9 is the built-in demo craft model on a 6-page script.
   It does not license "hide unverified quotes" on production reports. Agreement #6 is deliberately
   the weaker "demote in rank" rather than the stronger "hide," and it is labelled so.
3. **The four experts are not independent.** They are four passes by one model with one reading of
   the source. Convergence here is weaker evidence than four-model convergence. A genuine red-team
   that disagreed with all four has not happened yet, and agreement #13 (no rewrite) is the claim
   most likely to be wrong, because "no rewrite" is also the answer that requires the least new
   thinking.
4. **Agreement #8 is the cheapest-looking item and probably the hardest.** Mode-aware dock geometry
   touches `AGENTS.md:56`'s 50% invariant, the dock transition, the manuscript resize observer, and
   the print stylesheet, which hard-hides `#context-dock` (`style.css:3628`). The table rates it
   "Medium" on optimism.
5. **Nobody argued about the analyzer.** Every argument here is presentation. The single highest-leverage
   change might be in `pipeline.py` category ordering or severity assignment, which no expert
   proposed because all four were told the question was about the Feedback room. That is a scoping
   artifact, not a conclusion.
6. **No writer was asked.** `docs/REAL_WRITER_VALIDATION.md` exists and says the rule plainly:
   *"Felt > machinery."* This document is machinery. Every number in it is exact and none of it is
   felt. The panel should not be treated as a substitute for the one sitting that file describes.

---

## Status

**DONE_WITH_CONCERNS.** Two debates run in full, all pointers preserved per expert, one agreed list,
five clashes resolved with the repo's own `AGENTS.md` arbitrating the governance conflicts.

**Concerns:** the experts are not independent models (no subagent tool in this harness); gstack is
absent from this checkout so no skills or gates ran; D6 rests on demo-model data; agreement #8 is
under-costed; no writer has yet felt any of this.

**Next:** agreements #1 through #5 are deletions with no data-shape change and can be verified
against the existing suite immediately. #10 and #12 need a real writer sitting first.