# PHASE_B — FV Fold + Writer's Ledger Riders (R1-R9, refined) — In-Repo Spec

**Status:** GO 1 (identity + counting contract + forward-compatible states) IMPLEMENTED.
**GO 2 (fold + loop + ink + intent store + arrival strip) IMPLEMENTED — all riders live.**
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

## 4. GO 2 riders (IMPLEMENTED — production homes post-1A)

**The fold (1A):** `openFeedbackView()` routes to the workspace + dock Evidence lens
(`app.js:openWorkspaceWithFold` semantics — 6 call sites + session restore all land on the
workspace); the 3-panel `#feedback-view` clone is **dormant, unreachable** (grep-gated), not deleted.

| Rider | Phase | Production home + contract |
|---|---|---|
| R2-b keyboard next-finding loop | B Stage 3 | `startLoop/stepLoop/exitLoop/renderLoopBar` — N/↓ next, P/↑ prev (wrap-around), Esc exits before the dock closes. Loop bar re-docks itself after any Evidence-lens re-render (filter toggle mid-loop never loses it). Contextual per 2A: loop-active owns n/j/p/k; scene-stepping resumes on exit. |
| R5-b ink discipline | B Stage 3 + T2 | ONE filter state `state.findingFilter` (severity + category + defer) drives ink, board list, loop list, fix queue and counts — through ONE predicate `findingPassesFilter(f, index)`; N3 law, disagreement impossible by construction. Default = highs inked; a filter that matches nothing shows the honest empty hint (board + queue), never a blank. Inline `<mark class="finding-ink">` inherits font — never reflows (aria-hidden). *T2 (GAP-1 fix): board list + fix queue previously bypassed the filter — now routed through the same predicate as ink and loop.* |
| R8 category count-chips + ambient cap | B Stage 3 | Dock Evidence header chips (board post-1A): severity toggles + category count-chips + next-pass toggle + `⇉ fix loop` button. Peek-chip is the one ambient event; lens pulse suppressed during it. |
| R6 leak guards | B assertions | Layout-audit section 9: FV routes-to-dock + dormant, dock open with manuscript ≥ half width, loop engages/steps, Esc exits loop keeping the dock open. Audit 30/30. |
| R3 defer full | D | `finding_marks.json` intent store (ONE store: mark-addressed + defer, id-keyed, survives regeneration); POST `/api/projects/<name>/findings/intent`; `findingDisposition` reads intents first; writer intent wins display, observed status stays visible. |
| R7 copy evidence | D | `copyFindingEvidence` on deep dock cards + loop bar — quote + `— Scene N` slug, clipboard with execCommand fallback. |
| R4 scorekeeping | E | `last_pass.json` mtime-guarded lazy diff (ONE generation back, honest None on first pass) riding the `/edits` payload → `buildArrivalStrip` at the Evidence-lens top. |
| N1 trust in arrival | E | Arrival strip carries the verification readout ("N of M quotes verified (P%)"). |
| N2 inline retry | E | `failed_categories` → inline "Retry failed (k)" button at the arrival moment. |
| R9 ghosted | E | `state.ghostedIds` filled ONLY from real writer intents absent from the new pass (never fabricated) — muted, expandable, never red, in no open count. |
| A1 (criterion only) | — | Deferred in-app editing's reopening criterion refined to **surgical edits at Locate targets**. The defer stands. |

## 5. Verification gates (per step)

- GO 1: `pytest tests/test_revision.py tests/test_webapp_revision.py tests/test_webapp_api.py`
  (existing + new id-persistence tests) · `python tests/e2e_browser_layout_audit.py` 29/29 · live probe:
  seeded report re-analysis (re-score + scene insert) preserves addressed/dismiss marks; golden JS/Python
  id match; counting module counts agree across dock + fix queue + summary.
- GO 2 (this commit): pytest GO 2 scope **92/92** (test_revision 31 incl. intent/last_pass + webapp 61) ·
  layout audit **30/30** (section 9 = GO 2 contracts) · live probe `probe-go2.py` **R1-R7 green**:
  fold route (view cowrite + dock evidence + fv hidden), filter drives ink both directions, loop steps
  across a real 2-entry seam (N + P) and re-docks the bar after a mid-loop filter re-render, intents
  persist to disk + survive reload with dispositions `[addressed, deferred]`, arrival arithmetic exact
  ("Last pass: 3 · Still live: 1 · Fixed: 2 · New: 1"), ghosted filled only from real intents, unread
  dot → cleared by Evidence open. Two pre-existing failures elsewhere in the full suite
  (`test_audit_hardening` ideas-race, `test_feature_batch` SessionStore race) are Windows file-lock
  races in modules GO 2 never touched (git-verified) — declared out of scope.
- FV deletion (the dormant clone) is a separate later commit.
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
