# PHASE_B — FV Fold + Writer's Ledger Riders (R1-R9, refined) — In-Repo Spec

**Status:** GO 1 (identity + counting contract + forward-compatible states) IMPLEMENTED in this commit.
**GO 2 (fold surfaces, loop, arrival strip) — next approved step, per phases below.**
**Source of truth:** this file (self-contained; replaces the external anchoring-doc dependency).
**Constitution:** behaviors on T1/T2 surfaces only — zero new surfaces, no pin, no pagination, one manuscript.

---

## 0. Writer-verdict context (ratified 2026-09-14)

The room-state plan beats today's Feedback View on trust/speed/calm. In-app editing is the
honest deferred frontier — **the defer stands**; the reopening criterion is refined (A1 below).
Every rider below passed: *which tier?* (T1/T2 behavior), *which writer question?* (trust/speed/calm/continuity).

## 1. R1 — content-hash finding identity (IMPLEMENTED, refined R1-b)

- **Key = category + evidence_quote** (the quote is verified against script text — the stable anchor).
  **Refinement R1-b over the ratified R1:** scene_refs ride as DATA, not key — they renumber when the
  writer inserts a scene; a key carrying them orphans the writer's marks through the back door.
  Severity is a judgment about a note, not its identity — re-scoring keeps the id.
- **no_quote tier (documented weak):** key = category + normalized issue (first 100 chars). Drift
  re-classifies honestly on the next pass (scorekeeping shows "New").
- **One rule, two implementations:** `screenplay_studio/revision.py:compute_finding_id` (server
  observes) + `screenplay_studio/webapp/app.js:computeFindingId` (client displays) — djb2 →
  base36 on `category + "|" + (quote | "issue:" + norm)`. Golden match verified by live probe.
- **Persistence:** `dismissed_findings.json` entries gain `finding_id` (legacy `(index, issue)`
  entries keep working — old projects); `findings_status` entries carry `finding_id`; the client
  keys `state.findingStatus` by id with index fallback.

## 2. N3 — the finding counting contract (IMPLEMENTED, pulled into GO 1)

- `app.js:findingDisposition/findingOpen/findingStatusOf` — ONE source for disposition
  (open / addressed / deferred / ghosted / dismissed). Every counting surface reads it:
  mass strip, script ruler, scene index counts, `findingStatusSummary`, fix queue
  (server `dismissed_flags`), revision navigator, beat-board flags.
- Law (R5-b generalized): **the writer's totals cannot disagree between surfaces** —
  disagreement is impossible by construction, not by assertion.

## 3. Forward-compatible states (IMPLEMENTED — rendering rides Phase D/E)

- **R3 defer ("Next pass")** — id-keyed client-intent store (`state.findingDefer`); excluded from
  open counts; dimmed card + "next pass" chip. Phase D adds the full interaction (own filter, persist).
- **R9 stale = ghosted** — id-keyed drift set (`state.ghostedIds`); muted + desaturated, **never
  red**, excluded from scene totals. Phase E fills it from the R4 diff.
- CSS-only (marks never reflow script text); `.finding-note.deferred/.ghosted` + state chips.

## 4. GO 2 riders (per shared plan phases — next approved step)

| Rider | Phase | Contract |
|---|---|---|
| R2-b keyboard next-finding loop | B Stage 3 | N/↓ span-to-span; ONE loop across all surfaces (manuscript spans, dock evidence lens, fix queue); chip auto-open; mark-addressed + Discuss from the loop (portal contract); visible focus ring, instant reveal, reduced-motion collapsed. Verify `N` unbound vs palette keys. |
| R5-b ink discipline | B Stage 3 | ONE filter state (severity + category + defer) drives ink, rail counts, board, dock counts, loop. Default = highs inked, mediums/lows in rail counts + board until summoned. Several findings on one line → one numbered chip. Marks never reflow script text (no layout shift). Arrival shows ink via rail dots + first-finding halo. |
| R8 category count-chips + ambient cap | B Stage 3 | Rail header chips (pacing 4 · dialogue 7 · …); tap = filtered view, NO regrouping. One ambient event: peek-chip suppresses lens pulse; ambience never queues. |
| R6 leak guards | B assertions | Lasting unread dot after peek-chip fades; Esc hides drawer never kills transcript; drawer overlays dock never manuscript width (ratified geometry, now asserted); compare/beatboard exact scroll return. |
| R3 defer full | D | id-keyed client intent persisted (rides edits-data store); "addressed-or-nothing makes me lie" — resolved; own filter; dimmed, excluded from open counts. |
| R7 copy evidence | D | One-click copy of evidence quote + scene slug on the finding card. |
| R4 scorekeeping | E | On analysis arrival: "Last pass: 62. Still live: 41. Fixed: 14. New: 7." ONE generation snapshot (`lastPassIds`) in the project store; diff on arrival; cap one generation back (boring is good). R1-b ids make cross-pass lineage structural; scene_refs drift classifies as SAME finding. |
| N1 trust in arrival | E | The arrival strip carries `verification_summary`: "4 of 6 quotes verified (67%)". |
| N2 inline retry | E | Partial arrivals expose Retry-failed inline at the arrival moment. |
| A1 (criterion only) | — | Deferred in-app editing's reopening criterion refined to **surgical edits at Locate targets** (single-element edits; drafts + undo/redo already production-real in revision.py). The defer stands — criterion refinement, not a build. |

## 5. Verification gates (per step)

- GO 1 (this commit): `pytest tests/test_revision.py tests/test_webapp_revision.py` (existing + new
  id-persistence tests) · `python tests/e2e_browser_layout_audit.py` 29/29 · live probe: seeded report
  re-analysis (re-score + scene insert) preserves addressed/dismiss marks; golden JS/Python id match;
  counting module counts agree across dock + fix queue + summary.
- GO 2: e2e phase5/6/7/14 + R6 leak-guard assertions + layout audit 29/29 + live loop probe across dock + manuscript.
- Push remains the user's job.

## 6. Critique notes (the filter this spec passed)

- Two writer-audit voices converged (signal, not proof); zero real-writer usage data remains the
  epistemic hole — Phase E's arrival strip is the fastest felt test.
- R1-b changes a ratified key — justified: scene insertion is the most common script edit; the
  ratified key orphans through the back door within the first pass-heavy draft.
- A1 touches a ratified deferral — kept as criterion-only refinement.
- Cut: idea-graduation seeded notes (new tier, violates zero-new-surfaces); stash-through-reuploads
  (passage-stash is a separate passage-keyed system — correctly future); two-tier fuzzy id matching
  (deterministic wins).
