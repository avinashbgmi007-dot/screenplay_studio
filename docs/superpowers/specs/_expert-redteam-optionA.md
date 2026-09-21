# Red-Team: "ONE Feedback Room" Proposal (Option A)

Scratch analysis — product-design red-team of the proposed consolidation. Read-only; no
product code touched. Builds on `_expert-ux-critique.md` (the clutter audit) and
`docs/UI_UX_SPECIFICATION.md` §4.4b/§4.4c/§4.9.

**The proposal in one line:** one Feedback Room = left category accordion rail
(severity-weighted counts, collapsed) + center manuscript with ink (≥50%) + right dock with
Evidence|Sameer|Sushruta lenses; Evidence lens rebuilt to actually collapse, defaulting to
arrival strip + filter row + current-scene findings; Problem Board auto-open killed,
duplicate Pacing removed, `#feedback-view` clone deleted, craft shelf defers to dock;
arrival strip inverted; `verification.note`, `rule_id`, `errors[]`, `model_used` surfaced.

**What's right, up front:** every subtraction is correct and overdue — the audit's bottom
line was literally "subtraction and consolidation, not another surface." Killing the
Problem Board's divergent counting (it ignores `findingDisposition`), the second Pacing
chart, the 700-line dormant clone, and the shelf/dock duplication deletes four of the
"five doors." Surfacing `verification.note`/`rule_id`/`errors[]`/`model_used` strengthens
the app's one best-in-class asset: trust UI. None of that is re-litigated below.

---

## 1. The design's three weakest points

### W1 — The category accordion rail is the analyzer's taxonomy, not the writer's mental model — and it's a sixth door in waiting

A screenplay is navigated by **scene**, not by diagnostic category. The writer's questions
are "what's wrong with the midpoint scene?" and "what should I fix next?" — never "show me
everything the Theme pass flagged." A left rail of ~12 collapsed category headers with
severity-weighted counts is the *pipeline's* org chart wearing a UI costume. Worse:

- **Collapsed-default + counts = a survey tax.** With 36 open findings across 12
  categories, "see everything" costs 12 expansions. Accordion collapse is the exact
  progressive-disclosure failure the proposal (correctly) diagnoses in the Evidence lens —
  recreated one column to the left.
- **It duplicates the ONE filter row's category chips.** `buildFindingFilterRow` already
  offers category count-chips driven by the single `state.findingFilter`. A rail with its
  own counts is a second counting surface; unless it reads the same state (in which case
  it's a redundant rendering of the same chips, vertically), it re-opens the N3
  count-disagreement wound the audit flagged as the Problem Board's original sin.
- **It collides with the existing structural rail.** The three-zone shell's left rail is
  scenes/Stash/notes/beats. Two left rails, or a mode-switch on one, both add chrome to the
  zone that is supposed to stay quiet so the manuscript can hold ≥50%.

The category-rail instinct is right about one thing — *writers do need a persistent,
ambient severity map* — but that map already exists and is scene-shaped: the scene index
rail with per-scene severity aggregates. That's the taxonomy the writer already thinks in.

### W2 — "Current-scene findings only" as the Evidence default is the wrong cut

Scene-scoping is a good *filter*; it's a bad *default*, for three reasons:

1. **The dead-panel problem.** Clean scenes (which is most scenes after pass two) render an
   empty dock. An empty default state in the surface the app calls "the ledger" teaches the
   writer the dock is usually useless — precisely the discoverability hole the audit flagged
   with the "Context" edge button.
2. **It hides the highest-value findings.** The 12-pass pipeline's differentiators are
   cross-scene: theme, structure, the setup/payoff ledger, plot economy. A scene-scoped
   default systematically buries the findings no other tool produces, in favor of the
   line-level ones the ink marks already show on the page.
3. **It fights the fix loop.** The keyboard loop steps the *filtered* list across scenes
   with wrap-around. A dock whose default content is scene-locked either desyncs from the
   loop (loop shows finding N, dock shows current scene) or forces a mode toggle mid-loop.

The writer-relevant default cut is **liveness × severity** ("what's still open, highs
first"), which is also what the arrival strip, the filter-row default (highs inked), and
the counting contract already agree on. Scene-scoping belongs as one chip in the filter
row ("this scene"), not as the lens's resting state.

### W3 — Personas-as-lenses collapses a room into a tab, and chat + evidence can never be seen together

Sameer and Sushruta are designed as *rooms with presence* (persona cards, streamed letters,
branch-based sessions, the 🩺 escalation that arrives "with the finding in hand"). Chat is
a **mode** — sustained scrollback, composer focus, streaming latency on a local model.
Evidence is a **document** — a ledger you scan. Switchable lenses force one container to
serve both, and the costs land exactly where the product can least afford them:

- **State loss on lens switch.** Composer drafts, chat scroll position, stream-in-progress:
  unless the spec explicitly mandates per-lens state preservation (it doesn't say), the
  lens switch becomes a trap door. Writers will learn not to switch mid-thought — i.e., the
  lenses will be treated as rooms anyway, just rooms that occasionally eat your sentence.
- **The escalation gesture is weakened.** Today's 🩺 pins a quote and opens the doctor
  *with the card still visible*. Lens-switching replaces the card with the chat; the writer
  discusses a finding they can no longer see. The single most powerful layout this product
  can offer is **evidence card + persona reply simultaneously** — and one-dock-lenses makes
  it impossible by construction.
- **Aspect-ratio conflict.** Evidence deep cards want width; chat wants narrow-and-tall.
  One dock width is a compromise for both.

"Lenses, not rooms" is a good *naming* simplification. As a *layout* constraint it throws
away the consult-with-evidence-in-hand interaction that §4.9 documents as a deliberate,
shipped feature.

---

## 2. Is there a better layout? Three challengers, honestly evaluated

### Challenger 1 — Google-Docs-style margin-anchored comment threads + category filter chips

**Where it beats the proposal:**
- **Writer-first anchoring.** Feedback lives *on the words it cites*. The board-vs-page
  disagreement (N3) stops being a contract you maintain and becomes a non-issue — there is
  only one rendering, anchored. This is the purest expression of "script-first."
- **It's an evolution of shipped primitives, not a new surface.** Ink marks, margin pins,
  anchored-line click targets already exist. Upgrading pins into expandable threads
  (collapsed chip → card → reply) is incremental; the proposal's rail+dock rebuild is not.
- **Chat unifies with feedback.** "Reply in thread" *is* asking Sameer about this finding.
  One primitive (anchored thread) carries evidence, disposition, and conversation —
  including the writer's reply, which today has no home. Category filter chips merge
  cleanly into the existing ONE filter row.

**Where it loses, for this product:**
- **Script-level findings have no anchor.** Theme, structure, setup/payoff spine — the
  pipeline's crown jewels — cannot live in a margin. A Docs-style model still needs a
  ledger for these, so the dock survives anyway; you've added threads *on top of* the dock,
  not instead of it.
- **Anchor drift on a working copy.** Writers edit; quotes move or are rewritten. Google
  solves this with server-side OT and a fleet of engineers. Here the honest mechanism
  exists in embryo (fuzzy quote verification at 0.72, `computeFindingId`), but robust
  re-anchoring of edited text in **no-build vanilla JS** is the single largest engineering
  risk on the table. Ghosted/flag-don't-drop semantics help (a lost anchor renders as an
  orphan thread, never silently dropped) — but "orphan thread" is a new state the trust UI
  must explain.
- **Margin real estate vs. the ≥50% rule.** A usable comment column eats ~280–360px of the
  manuscript zone. On a 1440px desk with two rails, the page drops toward the floor the
  proposal is trying to protect.

**Verdict:** *Beats the proposal as a direction for scene-anchored findings; cannot replace
the ledger.* The honest version is a Phase-2 upgrade of existing margin pins into
expandable threads — not a Docs clone, and not the primary interface.

### Challenger 2 — Guided one-finding-at-a-time review as the PRIMARY interface

**Where it beats the proposal:**
- **It is the strongest possible answer to the actual diagnosis.** The audit's core finding
  is cognitive overload — "five doors, no map," 36 findings facing an aspiring screenwriter.
  A guided flow (arrival → "36 open, start with the 5 highs" → one finding, full context,
  fix / mark / defer / discuss → next) reduces the decision surface to one card. Nothing
  else on the table comes close for the overwhelmed-writer persona.
- **The machinery is already shipped.** The keyboard fix loop (`startLoop`/`stepLoop`,
  N/P wrap-around, mark-addressed/next-pass/Discuss, re-docking bar) is 90% of a guided
  mode. Promotion is cheap; invention is not required.

**Where it loses, for this product:**
- **As *primary*, it disrespects scanning.** Working rewriters (a named persona) survey
  before they commit; a wizard as the front door is a linter's UX — infantilizing to the
  expert and *slow* for the writer who wants to cherry-pick. Every guided-review tool
  (spell-check dialogs, import wizards) is tolerated, not loved.
- **Local-LLM latency punishes it.** Discuss-in-loop on llama.cpp means the guided flow's
  one escape hatch is its slowest path. A bored writer waiting on a stream inside a modal
  flow is worse than a busy dock.
- **One-finding focus decontextualizes.** Scene-level fixes need surrounding scenes;
  theme-level fixes need the whole spine. A single-card viewport fights the manuscript
  that must stay ≥50%.

**Verdict:** *Loses as primary; wins as the entry gesture.* The proposal plus "the arrival
strip's primary CTA is **Start the loop (5 highs)**" captures ~90% of the cognitive-load
benefit with none of the straitjacket.

### Challenger 3 — Scene-spatial board (corkboard of scenes carrying their findings)

**Where it beats the proposal:**
- **Scene-shaped thinking is real.** Writers hold acts and sequences spatially; "the act-2
  sag cluster" is how a rewrite plan is actually described. The Beat Board already proves
  the metaphor and already carries per-scene severity dots.
- **Triage-friendly.** Reordering and bulk-disposition feel natural on cards.

**Where it loses, for this product:**
- **Feedback is evidence, not metadata.** Findings are verified quotes with disposition
  state; scene cards strip exactly that, reducing each finding to a dot — a *regression*
  in the trust UI the proposal is trying to strengthen.
- **It's a second manuscript.** A board of scene representations competes with the
  manuscript for the writer's eye; the proposal's whole thesis is that the page is primary.
- **It duplicates the Beat Board** without consolidating it — a sixth surface, the precise
  failure mode under review.

**Verdict:** *Loses as a feedback home.* Its one good idea — severity dots on scene cards —
should simply keep reading the same counting contract where it already lives.

### Synthesis

No challenger replaces the proposal whole. The honest ranking for *this* product
(writer-first, script-first, vanilla JS, local LLM):

1. **Proposal (with changes)** — best consolidation-per-rupee; subtractions are unambiguous.
2. **Margin threads** — the correct *Phase-2* evolution for anchored findings; too costly
   (anchor drift) and incomplete (script-level findings) as the whole answer.
3. **Guided mode as entry, not interface** — fold into the proposal via the arrival CTA.
4. **Scene-spatial board** — do not build; keep Beat Board dots on the shared contract.


---

## 3. Verdict: **ADOPT-WITH-CHANGES**

**Adopt without modification:**
- All subtractions (Problem Board auto-open → routed through `findingDisposition` or
  retired; duplicate Pacing gone; `#feedback-view` clone deleted; shelf defers to dock).
- Evidence lens sections that actually collapse (fixing the lying code comment).
- Arrival strip inversion ("K of M addressed by you" leads).
- Surfacing `verification.note` + `rule_id` on cards, `errors[]` as a partial-failure
  banner, `model_used` in the header — with one rider: the `errors[]` banner's counts must
  be computed through the same `findingDisposition` path, and `rule_id` should deep-link to
  the KB rule's attribution (craft-source trust is the product's moat).
- "Lenses, not rooms" as the *vocabulary*.

**Required changes:**

1. **Delete the category accordion rail.** Category is a filter dimension (chips in the ONE
   filter row), not a navigation dimension. If an ambient severity map is wanted, invest in
   the existing scene-index rail's aggregates — scene-shaped, already shipped, already
   writer-legible. Do not ship a second counting surface; the N3 contract has been violated
   by exactly this pattern twice before (Problem Board, drawer).
2. **Change the Evidence default from "current scene" to "all live findings, highs first"
   (i.e., the filter row's existing default), with a "this scene" toggle chip.** Scene
   scope on demand; liveness by default. This also keeps the dock and the fix loop in
   lockstep and prevents the dead-panel problem on clean scenes.
3. **Preserve simultaneity for chat + evidence.** Either (a) persona lenses open in the
   existing drawer/gutter so a consult can sit beside the Evidence dock — the 🩺 escalation
   keeps its finding-in-hand power — or (b) if personas must be dock lenses, mandate
   per-lens state preservation (composer draft, scroll, in-flight stream) and a "discuss"
   affordance that keeps the originating card pinned atop the chat. Option (a) is cheaper
   and truer to the shipped design intent; the lens vocabulary can still be used for the
   dock's internal tabs.
4. **Make the fix loop the arrival strip's primary CTA** ("Start the loop — 5 highs"),
   harvesting the guided-mode insight without a wizard shell.
5. **Bank margin-anchored threads as the named Phase 2**, scoped to scene-anchored findings
   only, with explicit anchor-drift/orphan semantics riding the existing flag-don't-drop
   rule. Do not let it block this consolidation.

**Guardrails to restate in the spec** (they're load-bearing conventions): one filter state
drives every count; all new finding text through `escapeHtml`; no inline handlers
(`script-src 'self'`); any new surface that counts findings reads `findingDisposition` —
no exceptions.

---

### Bottom line

The proposal's instinct — subtract, consolidate, make the dock honest — is right, and its
subtraction list is exactly the audit's prescription. Its three original contributions are
its three weakest: the category rail re-taxonomizes the analyzer instead of the writer,
the scene-scoped default buries the product's best findings, and personas-as-lenses trades
the consult-with-evidence interaction for tidier vocabulary. Fix those three, adopt the
rest, and put margin threads and guided review where they belong: Phase 2 and the arrival
CTA, respectively.

