# One Desk, One Ledger — Consolidated Feedback UX (Design)

**Status:** approved direction (user, 2026-09-22), pending spec review
**Date:** 2026-09-22
**Evidence base:** `_expert-ux-critique.md` (11-surface clutter audit),
`_expert-dataflow-audit.md` (payload→state→surface map), `_expert-redteam-optionA.md`
(red-team verdict: adopt-with-changes) — all in `docs/superpowers/specs/`.

---

## 1. Problem (what we are fixing, not re-litigating)

Backend feedback is rich and honest; the SPA renders it in **~11 surfaces at once**.
Fix queue renders 4×, a finding can appear 3× inside a single dock panel, floating
finding cards overlap manuscript text, the Problem Board auto-opens with counts that
contradict the dock, a second chart named "Pacing" shows different data, and ~700 lines
of a dormant Feedback View clone ship in the bundle. Meanwhile the backend sends honesty
the UI drops: `verification.note`, `rule_id`, `check_id`, `errors[]`, `model_used`,
most of `coverage` and `stats`. Two status stores (`/edits` vs `/fixqueue`) can disagree;
writer intent moves one lens but not the queue header or dawn meter.

**The fix is subtraction and consolidation, not a new surface.**

## 2. Flow (user-approved)

1. **Landing** — unchanged. Ideas + scripts, analyzed badges.
2. **Idea selected** — blank, uninterrupted canvas (unchanged). Sameer on demand
   (exists). **Sushruta does not appear until a draft exists** — a doctor with no
   patient is clutter.
3. **New script** — Run Analysis sits centered on the empty manuscript (hero position).
   Progress chip + 20-stage hover map stays. Partial failure → one banner:
   *"N passes failed (e.g. Plot) — rerun just those"* driving the existing
   `retry-failed-categories` endpoint. All green → **soft-land**: the desk shows the
   arrival peek (halo + unread dot — the existing `scheduleArrivalPeek` behavior); the
   dock does NOT spring open unprompted. Page-first wins over report-first: the writer
   sees their pages and one calm "what changed" signal, and opens the ledger when ready.
4. **Analyzed script** — opens directly into the desk state below.

## 3. The desk layout — "One Desk, One Ledger"

```
┌──────────┬─────────────────────────┬──────────────┬─────────────┐
│ SCENE    │      MANUSCRIPT         │  EVIDENCE    │  on demand: │
│ RAIL     │      ≥50%, ink marks    │  DOCK — the  │  Sameer /   │
│ (exists, │      (cards stop        │  ONE ledger  │  Sushruta   │
│ severity │       overlapping page  │              │  drawer,    │
│ dots)    │       text)             │              │  beside dock│
└──────────┴─────────────────────────┴──────────────┴─────────────┘
```

- **Scene rail stays the ambient severity map** (scene-shaped = writer's mental model).
  **No category rail.** Category is a *filter* dimension (chips in the ONE filter row)
  and a *grouping* dimension (collapsible sections in the dock) — never a third
  navigation surface.
- **Manuscript**: ink discipline unchanged. Bug fix: floating finding cards must never
  overlap page text; ink matcher and `el-anchored` click-target matcher unified so a
  highlight is always clickable and vice versa.
- **Evidence dock = the single canonical ledger.** See §5.
- **Personas (Sameer/Sushruta) open beside the dock** (existing drawer), NOT as dock
  lenses — chat wants tall, ledger wants wide, and the 🩺 consult-with-evidence-card
  gesture is the product's best interaction; it must keep the card in view.
  Composer/scroll/stream state is never destroyed by persona switching.

## 4. Subtractions (the kill list)

| Remove | Why (evidence) |
|---|---|
| **Problem Board retired** (`app.js:2118–2121` auto-open, `#pb-filter`, `renderProblemBoard`, `pb-*`) | Ignores `findingDisposition`/`findingPassesFilter`; counts contradict the dock; slides during reading. Retired outright — its one honest feature (scene-severity overview) is already the scene rail's job. |
| **Second "Pacing" chart** (`renderReportPanel` 6163–6195) | Same name, different data than `renderPacingPanel`. Fix = **merge, don't delete data**: one dock Pacing section holding BOTH metrics (page-segment word density AND per-scene `pace_score` drag), clearly labeled. The chart duplication dies; both datasets live. |
| **Dormant `#feedback-view` clone** (`index.html:582–639`, `renderFvBoard` 6471, ~700 lines) | Dead parallel UI; invitation to resurrect a fourth board. Delete from bundle. |
| **Craft shelf fix-queue copy** | Shelf keeps pacing/dials/mirror collapsed summary; the queue's canonical home is the dock. Shelf header links to dock instead of embedding the queue. |
| **Duplicate "Retry failed" buttons** (desk toolbar, arrival strip, drawer header → 1) | One banner (§2.3), one affordance. |

Net effect: `app.js` shrinks by ~1,000+ lines; "five doors" become **page → rail → one
ledger**.

## 5. Evidence lens rebuild (the ledger)

- **Make the lying code comment true** (`app.js:4992–4998` promises collapsible
  sections; today every `dock-section-title` is a plain div). Every section gets a real
  collapse toggle with persisted state.
- **Default cut: all live findings, highs first** (the filter row's existing default),
  with a **"this scene" toggle chip**. Rationale (red-team W2): scene-scoped default
  renders a dead panel on clean scenes and hides cross-scene crown jewels
  (theme/structure/setup-payoff).
- **One rendering per finding per panel.** The current scene's finding may appear as
  queue row OR scene card OR category card — not three times. Section set (in order):
  arrival strip → filter row (⇉ fix loop) → **Live findings** (highs first, grouped by
  category, collapsed) → this-scene strip → coverage → setup/payoff → craft panels
  (pacing/dials/mirror, collapsed by default).
- Mass strip + ruler stay (ambient, honest), but must read the same counts as
  everything else (§8).

## 6. Arrival strip inversion + fix-loop CTA

- Lead with the writer's number: **"K of M addressed by you"** becomes the headline;
  the four pass-diff numbers shrink to a secondary clause; the `same_input`
  model-rewording disclosure stays verbatim (trust layer, non-negotiable).
- Primary CTA: **"Start the fix loop — N highs"** engaging the existing keyboard loop.
  Guided one-finding-at-a-time review lives here — not as a separate wizard interface.

## 7. Honesty surfacing (backend fields the UI currently drops)

| Field | New home |
|---|---|
| `verification.note` + `rule_id` | Finding card body (not hover-only); `rule_id` shows a popover with rule name + craft source (a full KB browser is a deferred feature — do not deep-link into a surface that doesn't exist) |
| `check_id` | Rendered alongside `rule_id` when present |
| `errors[]` (report) | The §2.3 partial-failure banner |
| `model_used` | Report/dock header (status strip shows config model — possibly not the analyzing model) |
| `coverage.genre/tone/strengths/comparable_films` | Coverage section of the dock (collapsed by default) |
| `/fixqueue` stripped fields (`evidence_quote`, `verification`) | Add to server allowlist (`webapp_server.py:1867–1879`) so queue rows carry verification state |
| `formatting_findings[]` (separate report array; today rendered only into `report.md`, app.js never reads it) | Dock "Formatting" section (collapsed by default; labeled as deterministic checks, not model judgment) |

Rider (red-team): every count in the banner/queue/dock is computed through
`findingDisposition` — no exceptions.

## 8. State-sync: one counting path

- `findingDisposition` / `findingPassesFilter` become the single source for ink, dock
  counts, queue header, dawn meter, summary chips, and arrival clause. Fixes the known
  splits: `/edits` vs `/fixqueue` two-store disagreement; intent moving one lens but
  not the other; dismiss leaving the dock stale; metrics stale until project re-open
  (`refreshMetrics` also runs after apply/undo/redo).
- Vocabulary unification: one phrasing for the pass delta. Canonical term set is the
  arrival strip's **"still live / no longer flagged / new"**; the diff banner's
  "resolved / carried / still open" is reworded to match.
- Deferred disposition taxonomy UX: Dismiss vs ⏭ next-pass vs ✓ addressed get
  one-line on-card explanations (today: icon-only, tooltip-only, learnable only by
  punishment).

## 9. Guardrails (load-bearing conventions — restated)

- One filter state (`state.findingFilter`) drives every count; any new counting surface
  reads `findingDisposition`. (N3 contract — violated twice before, both times by
  exactly the pattern this design removes.)
- All finding text through `escapeHtml`; no inline handlers (`script-src 'self'` CSP);
  token-driven colors only (night + dawn via Tungsten override); no build step, no new
  dependencies, no external requests.
- `prefers-reduced-motion` respected; `:focus-visible` rings; dock/keyboard loop
  behavior preserved (Esc cascade, wrap-around, bar re-dock).
- `tests/test_asset_cache_bust.py` contract: no manual `?v=` bumps —
  `_stamp_asset_versions` handles it.
- E2E suites touching retired surfaces (`tests/e2e_browser_*`) updated in the same
  change; layout-audit and GO 2 contract tests stay green or are consciously re-pinned.

## 10. Banked for Phase 2 (explicitly NOT this work)

- **Margin-anchored comment threads** (Google-Docs-style) for scene-anchored findings —
  the one genuinely better *new* idea; blocked on anchor-drift/orphan semantics riding
  flag-don't-drop. Biggest engineering risk in no-build vanilla JS; consolidation first.
- Scene-spatial feedback board — rejected outright (strips evidence to dots; duplicates
  Beat Board).

## 11. Acceptance criteria

Walked 2026-09-23 (plan Task 21). Every box below carries the gate that pins it,
so a later change that breaks one fails something named rather than something
remembered.

- [x] One canonical ledger: any finding visible in exactly one dock section; no Problem
      Board/drawer/clone copy diverges in count or status from the dock.
      -> `e2e_browser_dock_sections.py` (P1.8: no finding carded twice),
         `e2e_browser_counting_contract.py`, `test_app_symbol_integrity.py` (one-counter strip).
- [ ] `app.js` net-negative diff; `#feedback-view`, `renderFvBoard*`, `pb-*` (if
      retired) gone from the bundle.
      -> HALF MET, on purpose. The retired surfaces are gone and now pinned in JS,
         markup AND sheet (`test_app_symbol_integrity` covers all three; the 3 dead
         `#feedback-view` rules came out in this pass). `app.js` is NOT net-negative:
         +944/-392 against `main`, because each deletion bought a surface this spec
         asks for (collapsible persisted sections, the one-rendering dedupe, the
         convergence line, the stage ladder, `/quickcheck`, the rule popover). Either
         the box is amended to "the retired surfaces stay retired" or ~550 lines of
         spec-mandated chrome come out; that is a product call, not a gate tick.
- [x] Evidence sections collapse and persist; default = live highs first; "this scene"
      chip works both directions.
      -> `e2e_browser_dock_sections.py` (reload + prefs, highs-first, chip both ways).
- [x] Arrival strip leads with "addressed by you"; fix loop launches from it.
      -> `e2e_browser_dock_sections.py` (first child is the addressed count; the
         fix loop is the strip's CTA).
- [x] Partial analysis failure → banner with per-category rerun; all green → soft-land.
      -> `e2e_browser_dock_sections.py` (both rerun paths + endpoints),
         `e2e_browser_phase16_*` (retry split, one banner).
- [x] `verification.note`/`rule_id`/`check_id`/`model_used`/`errors[]` visible in their
      §7 homes.
      -> `e2e_browser_dock_sections.py` (one leg per field, incl. the rule popover).
- [x] Persona consult opens beside the dock with the originating card pinned; composer
      state survives switching.
      -> `e2e_browser_width_budget.py` (the pin is visible IN the open lens and is the
         finding's own evidence text), `e2e_browser_phase7_chat_lenses.py` (unsent draft
         and pin survive a lens round trip). Fixed in this pass: the pin rendered only
         on Sameer's composer, so escalating to the doctor parked the finding off-screen.
         "Beside the dock" is now "is the dock" - the persona IS a lens (see Task 20).
- [x] Floating cards never overlap manuscript text; inked line == clickable line.
      -> `e2e_browser_one_matcher.py` (both directions, no card over the page).
- [x] Dawn + night both render the new sections from tokens only.
      -> `tests/_p1_visual_gate.py` photographs the ledger/cards/queue/working list in
         both registers; `e2e_browser_layout_audit.py` fails on any unresolved token;
         `e2e_browser_pass_arc.py` adds the arc line in both (a hard-coded colour would
         not move with the theme, so that leg fails by construction on a literal).
- [x] `pytest tests/` green; browser suites re-pinned where surfaces retired.
      -> counts in the NOTES P3-gate entry for this run.

## 12. Out of scope

Backend pipeline passes, KB rules, personas' prompts, new endpoints beyond the
`/fixqueue` allowlist widening, margin threads (Phase 2), mobile-specific layouts.


## 13. Self-critique resolutions (risks found by attacking this spec)

1. **Big-bang risk.** This touches `app.js` (9,201 lines), `index.html`, `style.css`,
   `webapp_server.py`, and the e2e suites at once. The implementation plan MUST phase
   it, each phase independently green:
   - **P0 — Subtractions + one counting path** (kill list, `findingDisposition`
     everywhere, metrics refresh). Pure deletion + rewiring; biggest clutter win,
     lowest risk.
   - **P1 — Ledger rebuild** (real collapse, live-highs default + "this scene" chip,
     one-rendering-per-finding, arrival inversion + fix-loop CTA).
   - **P2 — Honesty surfacing + failure banner + soft-land** (§7, §2.3).
   - **P3 — Layout polish** (floating cards off the page text, unified ink/click
     matcher, persona-beside-dock width rule below).
2. **Width budget (script-first ≥50% can be violated).** Dock + persona drawer open
   together can squeeze the manuscript below 50% — the exact failure the audits
   photographed. Rule: **below ~1600px viewport, the persona drawer takes the dock's
   zone** (dock collapses to its edge button; the originating finding card stays pinned
   atop the chat); at ≥1600px they may sit side by side. Manuscript never drops under
   50% — enforced in the layout audit tests.
3. **Legacy stored state can resurrect retired surfaces.** Session restore
   (`view:"feedback"`, Problem Board open flags, old prefs) must be sanitized on load:
   retired view → desk; unknown/removed surface keys ignored, logged, never rendered.
4. **Visual truth gate.** Acceptance criteria are functional; "clutter-free and
   graceful" is visual. First task of the implementation plan: render the new desk
   with real Gun_Pen data and screenshot-review it (night AND dawn) BEFORE the P1
   rebuild is called done. The ~15% layout uncertainty is retired by pixels, not prose.


## 14. Productivity additions (writer + doctor POV — filtered hard)

Admission rule: uses data the backend ALREADY sends, needs NO new surface, shortens
the path from reading feedback to acting on it. Four passed; everything else rejected
(see bottom).

1. **"What's working" leads the ledger** (doctor POV: a good consultant names the
   healthy organs before the sick ones). A thin collapsed line directly under the
   arrival strip — *"What's working (3)"* — fed by `coverage.strengths` (already
   computed, currently dropped). Writer opens feedback to encouragement + orientation,
   not a wall of problems. Cost: one section, zero backend change.
2. **Finding → my note, one click** (writer POV: triage becomes action). A "📝 pin to
   notes" verb on finding cards creates a margin note carrying the finding's scene +
   quote via the EXISTING notes API. The writer can park a finding into their own
   to-do-in-margin without learning the Dismiss/⏭/✓ taxonomy first. Cost: one button +
   one POST to an existing endpoint.
3. **Clean-scene ✓ on the scene rail** (writer POV: progress you can feel). A scene
   with zero live findings shows a quiet ✓ where severity dots would be. Turns the rail
   from "map of problems" into "map of progress" — the dawn-meter instinct at scene
   granularity. Cost: one conditional glyph off the existing aggregate.
4. **Character-read confidence + scene_refs on cards** (doctor POV, honesty sweep
   completion). The audit flagged these as dropped; §7 already surfaces the same class
   of fields for findings — reads get parity. Cost: two fields on an existing card.

**Rejected (with reasons, so they stay rejected):** gamified streaks/scores (noise;
dawn meter already does morale honestly), an analytics dashboard (a new surface — the
disease), export/share reports (out of scope, privacy-first product), AI "fix it for
me" auto-apply (diagnose/prescribe split is a load-bearing convention; Rewrite modal
already exists for the writer-initiated case).


## 15. Analysis-run UX + user-approved backend additions (P2 phase)

### 15.1 Progress storytelling (upgrade of the existing chip + stage hover map)
The progress data (stage events + `ts` heartbeat in `progress.json`) already exists;
this is presentation only. The running state shows a **stage ladder** (the 12 passes as
a vertical rail: done ✓ / current ● with elapsed seconds / pending ○), the current
stage's plain-language caption ("Reading dialogue — who sounds like whom"), and a live
heartbeat ("working… 34s on this pass") so a long pass reads as *working*, never
*stuck*. Hover/focus on any stage shows what it does and what it produced so far.
Creative-but-honest constraint: no fake percentages — only real stage events; elapsed
time, not invented progress.

### 15.2 Retry: failed-only vs full re-run — BOTH offered, honestly labeled
Endpoint semantics (verified `orchestrator.py:53–87`, ARCHITECTURE §5):
`retry_failed=True` re-runs ONLY failed categories and merges (`AnalysisResult.merge`);
`genre`/`logline_test` retries auto-pull `coverage` (their prerequisite); a failed
retry preserves the previous partial record. UI copy:
- **"Rerun the 2 failed passes"** — *fast, and your good findings stay worded exactly
  as they were.* (Default action.)
- **"Rerun the whole analysis"** — *fresh eyes on everything; note: the model may
  re-word findings it already gave you, so 'fixed/new' counts get noisy unless you've
  edited the script.* (Secondary.)
Rule of thumb surfaced in the banner: **edited the script → full; just want the missing
passes → failed-only.**

### 15.3 (A) Live deterministic lint on edit — `POST /projects/<n>/quickcheck` (NEW)
On inline edit / rewrite apply / undo / redo: re-run the DETERMINISTIC passes only
(`continuity.py` + `formatting_check.py` — no LLM, milliseconds), refresh ink + counts.
Results are **provisional and labeled** ("live check — full pass pending") until the
next model analysis, preserving the honesty contract. The deterministic doctor never
sleeps; the model stays on-demand.

### 15.4 (B) Pass history + convergence line (NEW)
Append-only `pass_history.json` store (one entry per completed/partial analysis:
timestamp, totals, addressed, still_live, categories ok/failed — the numbers
`last_pass` already computes, kept beyond one generation). Ledger shows one line:
*"Pass 5 · 62 → 19 open · converging"* with a hover sparkline. One line, not a
dashboard. Written inside the existing store conventions (`atomic_write_json` +
`lock_for`, one lock).

