# Expert UX Critique: How the SPA Presents Backend Analysis Feedback

Scratch analysis document — product-design critique of feedback presentation in the
Screenplay Studio SPA. Read-only analysis; no code edited.
(Reassembled 2026-09-21: the original chunked write left §1 items H–K and three
sentence-fragments orphaned after the Bottom line; content unchanged, order repaired.)

Scope: `screenplay_studio/webapp/app.js` (9,201 lines), `index.html`,
`docs/UI_UX_SPECIFICATION.md` §1/§4.4/§4.4b/§4.4c/§4.9/§7, NOTES.md (craft-shelf
2026-08-16 entry; ONE-filter T2 entry; character-dials re-homing entry).

---

## 1. Inventory: every surface where feedback appears

**A. Desk toolbar row** (`index.html:195–206`, `app.js:refreshDeskToolbar` ~2485–2510,
`renderManuscript` tail 4759–4764): Run Analysis button, progress chip + 20-stage hover
map, `#desk-retry-failed-btn`, `#desk-analyze-status` text ("N findings on the desk — the
dock's Evidence lens has the ledger."), `#finding-summary` chips ("N open / N addressed" —
static, non-clickable).

**B. Craft shelf** (`buildCraftShelf` 4085, fed at 4683–4690): collapsed header ("Craft ·
36 open · 44 total · 110-page pacing · mirror") over four panels at the top of the
manuscript: fix queue (`renderFixQueuePanel` 3814), pacing (`renderPacingPanel` 3913 —
dialogue/action words per *page segment*), characters (`renderCharacterPanel` 3944),
character dials (`renderCharacterDialsPanel` 3974), Writer's Mirror
(`renderWriterMirrorPanel` 4007 — logline test + character reads).

**C. The manuscript itself**: inline ink marks (`inkAnchorsFor` 5281 /
`decorateLineWithInk` 5321, wired at 4526–4536), anchored-line click targets
(`el-anchored`, 4713–4728), per-scene margin pins (`findingNoteEl(pin:true)`, 4548–4558),
script-level findings bucket *above page one* with full-action cards (4692–4702),
change-mark stars, "discussed" tags.

**D. Scene index rail** (`renderSceneIndex` 4808, `sceneIndexSeverity` 4796): per-scene
severity aggregates.

**E. Problem Board** (`renderProblemBoard` 8808, `index.html:332–345`): docked right
aside, its own `#pb-filter` severity `<select>`, IntersectionObserver scroll-sync,
**auto-opens on project open when findings exist** (`app.js:2118–2121`),
auto-expands/collapses on scroll (8888–8897), click = scene-level scroll + flash only
(`pbItemClick` 8843).

**F. Context Dock — Evidence lens** (`renderDockEvidence` 5074): arrival strip
(`buildArrivalStrip` 5397), filter row + ⇉ fix-loop button (`buildFindingFilterRow`
5663), script mass strip (`buildScriptMassStrip` 5716), script ruler (`buildScriptRuler`
5792), current-scene strip (5031), fix queue (5124 — same renderer as B), scene findings
as deep cards (5134), script-level deep cards (5149), **all findings again grouped by
category** as deep cards (5165–5181), coverage + evidence-depth line (5193–5221),
setup/payoff spine + text rows (5228–5242), then the four craft panels *verbatim again*
(5244–5251), plus the loop bar (`renderLoopBar` 5536).

**G. Feedback room drawer** (`#feedback-panel`, `loadFeedbackPanels` 6072): header
(language select, progress, Run/Re-parse/`#retry-failed-btn`), tabs Report | Fix Queue
(`switchFeedbackTab` 6106); Report pane (`renderReportPanel` 6123) = coverage card,
setup/payoff card, a **second, different "Pacing" chart** (6165 — per-scene `pace_score`
drag bars), dials, mirror, findings-by-category read-only rows; Fix Queue pane =
`renderFixQueuePanel` a fourth time. Reachable for projects via session-restore of a
stored `view:"feedback"` (8410) and `openFeedbackRoom` (2248).

**H. Revision view** (6338, 6950): scene navigator with severity dots, the fix queue yet
again, mono status strip "A open / B addressed" (6981).

**I. Diff banner** (`renderDiffBanner` 4186): "N resolved · N new · N carried · N still
open" chips after draft activation.

**J. Status strip**: "⚡ Ns · X/Y fixed" metrics (`index.html` §6; spec line 478).

**K. Dormant-but-shipped**: the full 3-panel Feedback View clone (`#feedback-view`,
`index.html:582–639`; `renderFvBoard` 6471 etc.) — grep-gated unreachable, but ~700 lines
of parallel board/sev-dot/chat code still in the bundle. Plus the Beat Board's per-scene
finding flags (7051–7066).

---

## 2. Per-surface clutter/confusion risks

- **A — Desk row**: the status text is a *signpost to a hidden surface*. The dock is
  closed by default; its only affordance is an edge button labeled "Context"
  (`index.html:325`). "N findings on the desk — the dock's Evidence lens has the ledger"
  requires the writer to already know what the dock is and that "Context" = "Evidence".
  The `N open / N addressed` chips beside it are inert text — a count that doesn't
  navigate anywhere.
- **B — Craft shelf**: good default (collapsed), but the summary line is
  crypto-compressed: "36 open · 44 total · 110-page pacing · mirror" (4094–4098).
  "mirror" as a bare noun means nothing to a first-time writer. Inside, the fix queue
  repeats every row's Locate/Rewrite/Discuss/Dismiss that the dock also carries — the
  shelf is the dock's content with a different lid.
- **C — Manuscript**: the densest honest surface, but a single line can now accumulate:
  an ink `<mark>` + ×N chip, an `el-anchored` click handler, an `el-noted` marker, an
  `el-changed` star, a search `<mark>`, and an inline-edit dblclick handler. Ink and
  `el-anchored` use *different matching strategies* on the same quote (`inkMatch`
  fragment fallback 5307 vs. the anchored pass at 4715–4719), so a finding can ink a line
  without making it clickable, or vice versa — the writer sees a highlight that doesn't
  respond, and a clickable line that isn't highlighted. Also: margin pins are read-only
  by design (R6), but the *script-level bucket* (4692) renders full-action cards — same
  visual card family, different affordances, one scene apart.
- **E — Problem Board**: the worst offender. It ignores the entire GO 2 contract: no
  `findingDisposition`, no `findingPassesFilter`, no intent state — `renderProblemBoard`
  (8812–8813) filters only by its own severity `<select>` and shows
  addressed/dismissed/deferred findings as plain live rows. Its counts *will* disagree
  with the mass strip's "N open." It auto-opens on project open (2120) — a returning
  writer who came to *write* gets the findings panel shoved in — and it slides in/out on
  scroll (8888–8897), i.e. moving chrome during reading, the exact thing the Phase-12
  motion discipline banned elsewhere. Clicking a row does a scene-level scroll while
  every other surface does finding-level locate — same gesture, weaker result.
- **F — Evidence lens**: the code comment (4992–4998) promises "sections stack vertically
  and **collapse under one header each**" — but every section title is a plain
  `el("div", "dock-section-title")` with no toggle (5136, 5151, 5173, 5196, 5231).
  Nothing collapses. The lens is a single scroll containing: arrival banner → filter
  chips → mass strip → ruler → scene strip → full fix queue → scene deep cards →
  script-level deep cards → *every finding again* by category → coverage →
  evidence-depth prose → S/P spine → S/P rows → pacing → characters → dials → mirror.
  A finding in the current scene appears **three times within this one panel** (queue
  row, scene card, category card). The comment says "a contextual ledger, not a dashboard
  of equal cards"; the render is a dashboard of everything.
- **F — arrival strip** (5397–5481): the densest single component in the app. One banner
  carries: 4 pass-diff numbers + scope chip + (conditionally) a model-rewording
  disclosure clause + "K of M addressed by you" + "N of M quotes verified (P%)" + a retry
  button + an expandable ghosted-marks list. The honesty machinery (GAP-5/GAP-7) is
  admirable, but the writer's actual question — "did my edits work?" — is answered by the
  *smallest* clause ("addressed by you"), while the four biggest numbers are explicitly
  *not* about their edits. That hierarchy is inverted.
- **F — intent buttons** (4311–4334): ✓ / ⏭ / ⧉ / 🩺 are icon-only; meaning lives
  entirely in tooltips. ✓ ("my call: addressed") vs. the server-observed "addressed" vs.
  Dismiss (queue) vs. ⏭ ("next pass") vs. ghosted ("stale") is a five-way disposition
  taxonomy the writer must learn to triage one card. "Dismiss" and "next pass" in
  particular are near-synonyms with different consequences (hidden-from-queue vs.
  shown-when-toggled), and nothing on the card explains the difference.
- **G — Feedback drawer**: renders a *second chart named "Pacing"* with different data
  and a different visual (`renderPacingPanel` = dialogue/action words per page segment;
  `renderReportPanel` 6163–6195 = per-scene pace_score with drag threshold). Same name,
  two truths. Its category rows ignore the ONE filter — the drawer's Report can show
  findings the writer filtered out everywhere else. And `index.html:269–273` says this
  panel "is display:none for a project," while `openFeedbackRoom` (2261–2264) will still
  `setRoom("feedback")` and populate it — the docs and the code disagree about whether
  this surface is alive.
- **I — Diff banner** (4205–4209): "resolved / new / carried / still open" — a *fourth
  vocabulary* for the same conceptual delta the arrival strip calls "still live / no
  longer flagged / new" and the status strip calls "fixed." A writer who activates a
  draft sees both within minutes and cannot tell if "carried" = "still live."
- **K — Dormant FV**: ~700 lines of dead parallel UI (its own board, its own severity
  filter, its own scroll sync) shipped to every user. Not visible clutter — but it's why
  `renderFvBoard`'s `f.description || f.issue` and the Problem Board's identical
  expression (8836) still exist as divergent copies, and it's a standing invitation for
  someone to resurrect a fourth board.

---

## 3. Duplication map

| Content | Surfaces |
|---|---|
| Fix queue (`renderFixQueuePanel`) | craft shelf, Evidence lens, Feedback drawer tab, Revision view — **4 homes** |
| Pacing chart | shelf + Evidence lens (page-segment bars) **and** Report pane (pace-score bars) — same title, different data |
| Character dials / Writer's Mirror / Characters | shelf, Evidence lens §7, Report pane — verbatim ×3 |
| Coverage recommendation | desk status ("clean bill"), Evidence lens §5, Report card |
| Finding row rendering | `findingNoteEl` (4 variants), `fix-row`, `pb-item`, report rows, `fv-board-row` (dormant) — **5 renderers for one finding** |
| Severity aggregation per scene | scene index, dock scene box, ruler ticks, mass strip, Beat Board flags, Revision nav, fv dots (dormant) — 6 live |
| Filtering models | ONE filter chips (`state.findingFilter`) vs. `#pb-filter` select vs. queue's dismissed toggle — the pb select is an N3 violation by construction |
| "Retry failed" button | desk toolbar, arrival strip, feedback drawer header — 3 copies |
| "N open / N addressed" | finding-summary chips, arrival draft clause, dawn meter, revision strip, status-strip "X/Y fixed" — 5 phrasings |

---

## 4. The 5 worst writer-confusion moments, ranked

1. **"Which board is true?"** — The Problem Board auto-opens on project open
   (`app.js:2120`), shows *all* findings including ones the writer marked addressed or
   dismissed (`renderProblemBoard` 8811–8813), and its severity `<select>` knows nothing
   of the ONE filter. Simultaneously the desk chip says "22 open" and the mass strip says
   "22 open of 36 · 14 shown by filter." Three counts, three scopes, zero shared logic.
   The writer's moment: *"I addressed this an hour ago — why is it still on the board?"*
2. **"Did my fixes count?"** — The arrival strip leads with analyzer-vs-analyzer
   arithmetic ("Pass: 62 → 41 still live · 14 no longer flagged · 7 new") that the UI
   itself admits (in a small chip) cannot respond to edits, while the writer's real
   progress is the trailing clause. Then the diff banner answers the same question in
   different words ("resolved/carried"). The writer's moment: *"14 no longer flagged —
   but I only fixed 3. Did the doctor change its mind, or did I?"* The app knows the
   answer (the `same_input` rewrite clause) but buries it under the headline numbers.
3. **"Where do I actually work?"** — After analysis, feedback is simultaneously: a
   collapsed shelf summary, ink on the page, margin pins, an auto-opened side board, two
   toolbar chips, and a hidden dock that the status text calls "the ledger." Five doors,
   no map, and the door the app itself calls canonical ("the dock's Evidence lens has the
   ledger") is behind a button labeled "Context." The writer's moment: *"Do I fix things
   from the shelf, the board, the margin, or this Context thing?"*
4. **"Dismiss, next pass, or ✓ — what's the difference?"** — Three writer gestures that
   all remove a finding from view, with distinct persistence semantics (dismiss =
   queue-only hidden; defer = parked, returns next pass; ✓ = my-call-fixed, survives
   re-analysis), exposed as two icon-only buttons on deep cards and a text button on
   queue rows, on *different cards of the same finding*. The writer's moment: *"I clicked
   ⏭ yesterday and it came back — I thought I dismissed it."* Ghosted "marks moved on"
   then punishes the wrong guess.
5. **"Two pacings, three mirrors."** — The shelf and the dock show "Pacing — N pages"
   (word-count bars); the Feedback drawer's Report shows "Pacing — where the script
   drags" (pace-score bars) (`app.js:3913` vs `app.js:6165`). Dials, Mirror, Coverage
   repeat verbatim across three surfaces. The writer's moment: *"Is this the same chart
   telling me something new, or a new chart I already read?"* Repetition reads as
   emphasis; here it reads as disagreement.

(Dishonorable mention: the palette's "Toggle the Problem Board" shows key `b`, which
actually opens the Beat Board — spec §4.4c flags this and it is still true at
`app.js:7491` vs `7725`.)

---

## 5. Genuinely good — do not lose

1. **The N3 counting contract** (`findingDisposition` 5608 / `findingOpen` /
   `findingStatusOf` / `findingPassesFilter` 5268): one predicate behind ink, board,
   loop, and queue is exactly the right architecture — the failure is that the Problem
   Board and drawer Report don't participate, not the contract.
2. **The honesty layer**: scope chip ("from the last run, not your edits"), the
   `same_input` rewording disclosure (5417–5423), the evidence-depth line with its
   "second opinion on structure, not a reading of your pages" tooltip (5216–5218), the
   verification readout with the corrected `no_quote` denominator (5741–5758),
   unverified-quote badges on deep cards (4293–4300), ghosted marks rendered
   muted-never-red (5468–5480). This is best-in-class trust UI for LLM feedback; any
   decluttering must preserve the *statements* while fixing their hierarchy.
3. **Ink discipline** (`decorateLineWithInk` 5321): inline marks that inherit the page
   font and never reflow, severity-ordered collapse into ×N chips, `aria-hidden`
   decoration with semantics on the board, search suppresses ink (transient beats
   persistent). This is how margin-of-a-manuscript annotation should feel.
4. **Page-first progressive disclosure**: the craft shelf's collapsed default (NOTES
   2026-08-16 documents the 9,000px wall it replaced), read-only margin pins (R6), the
   single ambient arrival halo + lasting unread dot instead of a modal (5365–5387), and
   the "honest empty states" when filters hide everything (3822–3831, 5182–5190).
5. **One renderer, many homes** for the queue (`addPanel` array-or-node trick, 3809) and
   `prepareManuscriptData` as the single aggregation source — the duplication problem is
   *placement*, not data paths, which makes it cheap to fix.
6. **The keyboard fix loop** (5484–5563): contextual key capture that restores
   scene-stepping on Esc, wrap-around, bar re-docks itself after lens re-renders
   (5253–5255) — a rare example of a power-user feature that doesn't mortgage the
   novice's keys.

---

## Bottom line

The app's feedback problem is not dishonesty or missing craft — it's that every
historical answer to "where does feedback live" is still partially alive. The GO 2 fold
anointed the dock's Evidence lens as the one board, but the Problem Board still
auto-opens with stale semantics, the Feedback drawer still resurrects via session restore
with a second "Pacing," the shelf duplicates the lens's tail, and the lens itself is an
uncollapsed wall that contradicts its own design comment. The fix direction is
subtraction and consolidation — route the Problem Board and drawer through
`findingDisposition`/`findingPassesFilter` or retire them, collapse the Evidence lens's
sections for real, invert the arrival strip so the writer's number leads — not another
surface.

