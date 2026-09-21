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
   `retry-failed-categories` endpoint. All green → **soft-land**: the Feedback desk
   state with the arrival strip on top; the writer is not hard-redirected.
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
| **Second "Pacing" chart** (`renderReportPanel` 6163–6195) | Same name, different data than `renderPacingPanel`. One pacing renderer, one home. |
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
| `verification.note` + `rule_id` | Finding card body (not hover-only); `rule_id` deep-links to the KB rule's attribution |
| `check_id` | Rendered alongside `rule_id` when present |
| `errors[]` (report) | The §2.3 partial-failure banner |
| `model_used` | Report/dock header (status strip shows config model — possibly not the analyzing model) |
| `coverage.genre/tone/strengths/comparable_films` | Coverage section of the dock (collapsed by default) |
| `/fixqueue` stripped fields (`evidence_quote`, `verification`) | Add to server allowlist (`webapp_server.py:1867–1879`) so queue rows carry verification state |

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

- [ ] One canonical ledger: any finding visible in exactly one dock section; no Problem
      Board/drawer/clone copy diverges in count or status from the dock.
- [ ] `app.js` net-negative diff; `#feedback-view`, `renderFvBoard*`, `pb-*` (if
      retired) gone from the bundle.
- [ ] Evidence sections collapse and persist; default = live highs first; "this scene"
      chip works both directions.
- [ ] Arrival strip leads with "addressed by you"; fix loop launches from it.
- [ ] Partial analysis failure → banner with per-category rerun; all green → soft-land.
- [ ] `verification.note`/`rule_id`/`check_id`/`model_used`/`errors[]` visible in their
      §7 homes.
- [ ] Persona consult opens beside the dock with the originating card pinned; composer
      state survives switching.
- [ ] Floating cards never overlap manuscript text; inked line == clickable line.
- [ ] Dawn + night both render the new sections from tokens only.
- [ ] `pytest tests/` green; browser suites re-pinned where surfaces retired.

## 12. Out of scope

Backend pipeline passes, KB rules, personas' prompts, new endpoints beyond the
`/fixqueue` allowlist widening, margin threads (Phase 2), mobile-specific layouts.

