# Arrive Quiet, Fix by Scene — Post-Analysis Feedback IA (Design)

**Status:** approved direction (user, 2026-10-02); implementation not started. Builds
on *One Desk, One Ledger* (`2026-09-22-one-feedback-room-design.md`, approved and
shipped) — this doc refines the IA on top of that baseline, it does not re-open it.
**Scope:** information architecture, arrival and flow behavior. Visual direction is a
separate decision (`REDESIGN_MASTER_PLAN.md` §4/§10 fork) and stays parked.
**Origin:** design thread of 2026-10-02. Decisions marked *(locked)* were chosen by the
writer in that thread.

---

## 1. What already ships (kept, not re-spec)

- **One ledger.** The Evidence lens is the canonical findings ledger; Problem Board,
  Feedback View clone and the category rail are retired (`test_app_symbol_integrity`).
- **Arrival peek + arrival strip.** Completion shows a halo + unread dot
  (`scheduleArrivalPeek`, `app.js:6770`) and does not spring the dock open; the dock's
  arrival strip leads with "addressed by you" and carries the fix-loop CTA.
- **Scene rail** = ambient severity map, with a quiet clean-scene ✓ for scenes with no
  live findings.
- **Dock lenses** = Evidence / Sameer / Sushruta / Stash & Notes
  (`#dock-tab-*` / `#dock-lens-*`, `index.html:278-320`); the consult gesture
  (`discussWithDoctor`, `app.js:7712`) pins a finding into the doctor's lens.
- **N3 counting contract**: every count flows through
  `findingDisposition` / `findingPassesFilter`; no second aggregation path.
- **Honesty layer**: verified quotes (0.72 fuzzy threshold), `verification.note`,
  `rule_id`/`check_id` popover, `errors[]` banner, live deterministic `/quickcheck`
  labeled provisional, `pass_history` convergence line.

## 2. The problems this doc fixes

One Desk, One Ledger removed the duplication clutter. What remains is **how feedback
arrives and how the writer moves through it**:

1. **Simultaneity.** Twelve passes land at once and everything is "on" — the writer
   meets a state, not a sequence. Pain: *"too much at once; can't tell what to do first."*
2. **Page colonization.** Several mark vocabularies (anchored, changed, selected, ink)
   can stack on one line; the page stops being the writer's page when feedback is loud.
   Pain: *"panels compete with the page; too much text per finding."*
3. **Invisible provenance.** Deterministic lint and model judgment look identical, and
   whole-script audits (setup/payoff, coverage) render like rows, not reads. Pain:
   *"not managed / aligned / segregated."*

## 3. Locked decisions (2026-10-02 thread)

- **Default post-analysis mode = the guided fix loop** *(locked)*.
- **Loop unit = the scene** *(locked)*.
- **Everything counted and one tap away** *(locked)* — folded, never hidden.
- **Idea room door** *(locked)*: Sameer is the default presence; the Premise Doctor's
  test is opt-in and labeled, with a state-dependent invitation (see §9).
- **Script ≥50% and the width-budget rule** stay law (prior spec §13.2).
- Visual work waits for the direction fork; **nothing in this doc hides information**.

## 4. The IA model (the vocabulary this doc uses)

**4.1 Existence vs Expression.** Every atom (finding, scene aggregate, script total,
audit read) keeps *Existence* unconditionally. *Expression* — the full card, the verbs —
is granted only when demanded. "No hiding" is satisfied precisely as: counted, and
reachable in ≤1 tap from one place, ≤2 clicks overall.

**4.2 Three writer verbs.** Scan (quantities and locations) → Pick (one-line gist +
trust signal) → Work (full card + verbs). Every surface serves exactly one verb; a
surface that tries to serve all three is the wall returning.

**4.3 The resolution ladder (three rungs, capped).**
- **L0 Quantity** — a number on a fold ("12", "3 new").
- **L1 Gist** — one line: category, severity, scene, first clause of the issue.
- **L2 Card** — the full finding with evidence, verification state, verbs.
- Focus is not a fourth rung: focus = L2 + the fix-loop tool. (Earlier drafts had four
  rungs; the cap is deliberate.)

**4.4 Three scales — one per atom at a time.**
- **Line (page)** — ink only. "Something is here," nothing more; one mark vocabulary.
- **Scene (rail)** — aggregate: severity dots, clean-✓.
- **Script (dock)** — the full card and the verbs.

**4.5 Three tiers — the top partition, by trust.**
- **Mechanical** — deterministic (formatting, continuity, quickcheck). Batches as one
  checklist, never one-card-at-a-time trivia; labeled "check", not "judgment".
- **Judgment** — model findings, per-scene and cross-scene (category findings live here).
- **Structural** — whole-script reads (setup/payoff ledger, coverage, principles).
  Read-once blocks, never row-per-finding; offered as a stop, not sprinkled per scene.

**4.6 Obligations (the "no hiding" contract).**
1. Every folded group shows its count (and where it lives).
2. From a count, the thing itself is ≤1 tap away; everything is ≤2 clicks from one
   place (the ledger).
3. No silent filters: any filtered view says "N of M shown — K hidden by <reason>".
4. Every count comes from `findingDisposition`/`findingPassesFilter` (N3). A new counting
   surface is a defect unless it reads that predicate.
5. Flag, don't drop (unchanged): unverifiable findings stay visible, flagged.

## 5. Arrival sequence — Arrive → Guide → Reference

**Arrive (the moment analysis completes).**
- The page stays. The dock stays shut. No view change.
- One **arrival line** is the single signal: halo + unread dot (shipped), plus a
  desk-level one-liner with the honest numbers and the one action, e.g.
  *"Analysis ready · 12 high · Start the fix loop"*. All green reads
  *"Analysis done — no open findings"* with no CTA emphasis.
- One tap on the line starts the loop; the ledger stays one tap beyond it. Nothing else
  opens.
- **Timing belongs to the writer.** Writing during a run is allowed and never
  interrupted. A *total* failure shows the reason, not just the pass name; a partial
  failure keeps the shipped banner + failed-only rerun, with the reason named where the
  report carries one.

**Guide (the default).** The fix loop (§6), per scene. The writer can leave at any
point; nothing is lost, everything resumes.

**Reference (on demand).** The ledger in the dock: totals → facets → cards, all counts
honest, all filters declared. A week-later return lands quiet: no halo once seen, no
auto-open, the line shows current state (*"3 high still live"*), unread dot only for
findings new since the last visit.

## 6. The fix loop (default post-analysis mode) *(locked)*

**Shape.** Scene by scene, in script order. One scene on the desk at a time:
- A **whole-script stop** first (skippable): the Structural tier's read-once blocks
  (setup/payoff, coverage) — read once, act later.
- Per scene: the **mechanical batch** as one checklist (all deterministic notes for the
  scene, each one tap), then **judgment findings** one at a time, high first.
- Finishing a scene paints the clean-✓ (shipped) and moves on; the loop never reorders
  the script.

**Progress.** One honest number, phrased as action: *"4 of 12 highs cleared · scene 3
clean"*. No invented percentages, no gamification.

**Filters.** The loop opens with the writer's chosen depth: *just the highs* (default)
or *everything*. The filter honesty rule (§4.6.3) applies inside the loop.

**Exits and resume.** Esc leaves the loop; the ledger and the page are untouched. The
arrival line resumes it (*"Continue loop · 5 left in scene 3"*). Dispositions persist
through the existing stores (no new store).

**Keyboard.** The loop keeps the shipped keyboard contract (Esc cascade, wrap-around,
`↑`/`↓` while engaged; the manuscript's own arrow walk stays untouched). The loop is the
same tool whether driven by keyboard or pointer.

## 7. One rail, two registers, one shared object

The Context Dock's right rail has two registers; the writer switches register without
losing state:
- **Ledger register** (Evidence) — counts → facets → cards.
- **Conversation register** (Sameer or Sushruta) — one persona visible at a time; the
  shipped lens tabs are the switch, made visually loud by the room accent (Sameer
  violet / Sushruta cyan). Do not add side-by-side chats; the width budget forbids it
  and two conversations halve the writer's attention.
- **One shared object.** The finding is what crosses registers: `discussWithDoctor`
  pins it into the doctor's lens; the pin, unsent drafts and scroll survive switching
  (guarded by `e2e_browser_phase7_chat_lenses.py`).
- **Page drives the rail.** Clicking a scene or an inked line loads that scene's /
  finding's content. No mode selector; the context is the mode.
- The scene rail stays (ambient severity + clean-✓); the script stays ≥50%.

## 8. Projection matrix (where each atom lives)

| Atom | Line (page) | Scene (rail) | Script (dock) |
|---|---|---|---|
| Mechanical finding | ink (if anchored) | dot only if high | checklist row (batched) |
| Judgment finding | ink | severity dot | card (L2) in ledger + loop; one rendering per panel |
| Scene aggregate | — | dots / clean-✓ | "this scene" facet |
| Script totals | — | — | arrival line / ledger header, all via `findingDisposition` |
| Structural read (setup/payoff, coverage) | — | — | one collapsed block, count in header |
| Premise consult | — | — | idea room only (§9) |

Cross-cutting: one mark vocabulary on the page (ink); every fold carries its count;
every filtered list declares what is hidden.

## 9. The premise room (Idea room) — door + pass

**9.1 Door rule v2** *(locked 2026-10-02; the refinement of Option B).*
- **Sameer is the room's default presence.** The Premise Doctor
  (`personas.py:114`, dev-exec voice) never greets.
- **State-dependent invitation, never a state-dependent door.** Visibility scales with
  the idea's *substance*, not the room's pixels:
  - Nothing testable: the test is dormant; no pitch.
  - A testable premise exists (a logline / premise statement): the labeled affordance
    is visible — *"Test this premise: one pass, 5 questions, a verdict."*
  - Worked / returning premise: **one** proactive offer, phrased as state, not
    interrogation (*"You've a premise here. One pass tells you if it holds.
    [Start] [Not now]"*); dismissal remembered; a re-offer only when a prior verdict
    exists and the premise changed materially.
- **Never**: auto-start, the doctor as greeter, a second nudge. **Per idea, not per
  room** — a new idea in a room that holds a worked premise starts quiet.
- Existing wiring stays: the idea room maps to the doctor lens (`app.js:1783`);
  `PREMISE_DOCTOR_BANNED` (`persona_specs.py:95`) governs his tongue.

**9.2 The pass — shape.** One sitting. 5-7 questions, in his voice (dry, direct; test
the idea, not the writer). Ends with a **readiness verdict + exactly one fix**.
Readiness-only language, never good idea / bad idea:
- *"Ready to write."*
- *"Not yet — here's the hole."* (paired with the hole and the one fix)
- *"Strong concept, wrong shape."*

**9.3 The honesty rule for opinions.** The consult has no pages to quote; it is opinion
start to finish. It must never wear the verified-finding look (no quote-verification
badge, no `rule_id`), and the UI says what it is: one experienced reader's structured
read. The verdict is auditable in the transcript; the badge is not.

**9.4 Memory and graduation (proposed; Phase D/E).**
- **Graduation loop:** on graduation, the verdict, the one fix, and the answered
  questions ride into `premise.json` (additive fields; atomic write under the store
  conventions) so the script desk — and the structure pass — can compare pages against
  the promise made at premise. Docs to update when built: `DATA_FORMATS.md`,
  `STATE_STORES.md`, `CONTEXT.md`.
- **Cross-premise memory (Phase E, gated):** "this is the third premise with a passive
  protagonist" is the highest-value idea-room signal — but the idea engine deliberately
  drops `writer_library_text` (anti-leak decision, 2026-08-18). Any cross-premise signal
  must be **patterns, never passages** (counts, recurring shapes), must respect the
  existing suppress path ("wrong — forget"), and is an open question until the writer
  opts in (§13).

## 10. Kill list (dead, and stays dead)

| Dead | Why |
|---|---|
| Auto-open dock / view change on completion | Arrival is a line, not a takeover (prior spec §2.3, restated) |
| Problem Board, `#feedback-view`, category rail | Retired; `test_app_symbol_integrity` refuses them back |
| Row-per-finding rendering of structural audits | Structural is read-once; rows turn a read into a wall |
| New severity aggregations / second counting surface | N3: counts come only from `findingDisposition` |
| Undeclared filters | "N of M shown" is mandatory |
| One-card-at-a-time for mechanical notes | Batched checklist; trivia is not work |
| Auto-start / nagging premise interrogations | Door rule v2 (§9.1) |
| Good idea / bad idea verdicts | Readiness only (§9.2) |
| Side-by-side dual chats | One conversation visible; the lens switch is the gesture |
| More than one mark vocabulary on the page | Ink only; one scale per atom (§4.4) |

## 11. Guardrails (restated, load-bearing)

- N3 counting; `escapeHtml` / CSP / token-driven colors; no build step, no new deps, no
  external requests.
- Script ≥50% at every viewport; below ~1600px the persona drawer takes the dock's zone
  (prior spec §13.2).
- Keyboard parity is a feature; reduced-motion + `:focus-visible` stay.
- Asset version stamping (`_stamp_asset_versions`) — never hand-bump.
- Store conventions if premise fields land: `atomic_write_json` + `lock_for`; no new
  store for the loop (dispositions already persist).
- E2E suites touching changed surfaces re-pinned in the same change; docs that name
  surfaces updated in the same change (`test_doc_surface_hygiene.py`).

## 12. Phasing (draft; the implementation plan re-phases)

- **A — Arrival polish:** desk-level arrival line, quiet return, failure-reason copy,
  writing-during-run contract.
- **B — Tiers + segregation:** Mechanical/Judgment/Structural labels and folds; every
  section header carries its count.
- **C — The per-scene fix loop:** the walk, the mechanical batch, progress line, filter
  honesty, resume. (Consumes B's labels; may land after B.)
- **D — Premise room:** door v2 states, the pass, verdict language, graduation fields.
- **E — Banked:** cross-premise memory (opt-in), margin threads (prior spec §10), all
  visual work (waits for the fork).

## 13. Open questions

1. Cross-premise memory: opt-in per writer / per idea? (Constraint: patterns only.)
2. Exact arrival-line placement (toolbar vs dock edge label) — needs the visual phase;
   the IA requirement is "one visible line, one tap", not a specific pixel.
3. Mechanical batch verbs: bulk "reviewed" for all, or per-note taps only? (Leaning:
   per-note taps, plus a "nothing here" sweep for the batch.)
4. Whether the whole-script Structural stop is skipped when the writer's chosen depth is
   "just the highs" (leaning: always offered, marked skippable).

## 14. Acceptance criteria (draft — pin gates when the implementation plan lands)

- [ ] Completion never opens the dock or changes the view; the arrival line is the only
      signal; all-green has no CTA emphasis. → extend `e2e_browser_dock_sections.py` or
      new `e2e_browser_arrival_line.py`.
- [ ] The fix loop walks scene-by-scene, batches mechanical notes, shows the honest
      progress line, resumes from the arrival line, and exits without loss. → new
      `e2e_browser_fix_loop_scene.py`.
- [ ] Every fold shows its count; no undeclared filter exists; every count reads
      `findingDisposition`. → extend `e2e_browser_counting_contract.py`.
- [ ] Register switch (ledger ↔ conversation) loses no state (draft, scroll, pin). →
      exercised by `e2e_browser_phase7_chat_lenses.py` + `e2e_browser_width_budget.py`.
- [ ] Premise door states render per §9.1; the pass ends with a readiness verdict + one
      fix; no verified-finding chrome on premise output. → new
      `e2e_browser_premise_pass.py`; `tests/test_ideas.py` for graduation fields.
- [ ] Docs naming new surfaces updated (`CONTEXT.md` glossary first); `pytest tests/`
      and the browser fleet green.

## 15. Evidence and references

- User pain list (2026-10-02 thread): simultaneity; competing panels; text volume; no
  priority; nothing managed/aligned/segregated.
- `_expert-ux-critique.md` (11-surface audit); `2026-09-22-one-feedback-room-design.md`
  (baseline, shipped); `REDESIGN_MASTER_PLAN.md` (§4/§10 fork parked, §6 done);
  `UI_UX_SPECIFICATION.md` (feature contract this doc refines, never removes).
