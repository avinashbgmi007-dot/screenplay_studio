# Evidence Index — 2026-09-30 Audit

Ground rules in force: no product code changed; every claim is app-derived
(running server, real browser, real HTTP); demo-model runs are labeled as such.

## Step 0 — pull & re-baseline

- Pulled 3 commits (`c89572e` → `ddac2df`, rungs 18–20): analyzer dedupe module
  (`screenplay_analyzer/dedupe.py`), status-strip finding-count refresh on
  analysis completion, Locate-verb unification, evidence-scope labels,
  aria-labels on glyph intent buttons.
- App-surface diff: `webapp/app.js` +128, `style.css` +67, `webapp_server.py`
  +59, `pipeline.py` +23, new `dedupe.py` +57, plus tests and docs.
- Audit target re-baselined to `ddac2df` (rung 20).

## Phase 0 — boot proof (16/16 PASS)

Script: `scripts/audit_boot_probe.py` → `boot_evidence.json`

| Check | Result |
|---|---|
| `/api/health` answers | PASS |
| `GET /` serves the SPA (Script Doctor Studio) | PASS |
| Capability token minted via Set-Cookie (secure by default) | PASS |
| Write without token → 403 | PASS |
| All four assets carry content-hash `?v=` stamps (no on-disk placeholders) | PASS |
| `X-Content-Type-Options: nosniff` on `/` | PASS |
| CSP `frame-ancestors 'self'` on `/` (X-Frame-Options deliberately absent — repo test pins this) | PASS |
| Referrer-Policy on `/` | PASS |
| `/api/health` GET exempt from token | PASS |
| `/api/real-server-check` reports demo model honestly | PASS |
| Welcome view paints at 1440×900 | PASS |
| Zero external requests on first paint (self-hosted fonts) | PASS |
| Zero console errors / zero page errors | PASS |

Screenshot: `shots/boot_welcome_1440x900.png`

Probe-honesty note: the first boot run failed 2 checks that were **probe bugs,
not product bugs** (case-sensitive header comparison; expecting X-Frame-Options
when the shipped contract is CSP frame-ancestors, asserted by
`tests/test_spa_security_headers.py:87,108`). Fixed in the probe; product untouched.

## J1 — Onboard & upload (8/8 PASS)

Script: `scripts/audit_j1_j2_journeys.py` → `j1_j2_evidence.json`

- File input is keyboard-reachable (visible in tree + accepts focus).
- Real fixture `tests/fixtures/pain_tenglish.fountain` uploaded through the real
  input → parse → desk opens, `#project-bar` carries title, scene pages paint.
- Zero console errors, zero failed network calls during the whole journey.
- Console capture: `j1_console.json`.

## J2 — Analysis journey (17/17 PASS across J2a/J2b/J2c)

- J2a (demo model, labeled): Run Analysis button enabled after parse → desk
  toolbar reveals on writer hover (hit-target proof, not just opacity-visible)
  → re-entry guard engages → stage ladder/progress UI paints
  (`shots/j2_stage_ladder_running.png`) → completion flips button to
  "Re-run Analysis" → manifest says `analyze: complete` → force rerun completes
  a second time. Zero console errors / failed network calls
  (`j2_console.json`).
- J2c (forced partial, client-seeded same technique as
  `tests/e2e_browser_dock_sections.py`): with `failed_categories=['dialogue']`,
  the Evidence ledger renders the failure banner with the "Rerun the failed
  pass" control (`shots/j2c_failure_banner.png`).
- J2b (process-level, real kill + restart on the same projects dir):
  - Mid-run kill leaves `progress.json` behind; file then pinned to the
    `running` heartbeat shape (kill raced the fast demo run — documented, the
    leg proves the endpoint's stall contract).
  - Fresh heartbeat does NOT heal to `stalled` (a live run must not be lied about).
  - Heartbeat backdated 31 min heals to `stalled` with an honest
    "Re-run Analysis" detail.
  - Torn progress file on a never-analyzed project answers HTTP 200
    `status: retrying` (R6-BE-9 contract: a transient read never surfaces as 400).

## J3 — Feedback surfaces (24/24 PASS) — script `scripts/audit_j3_j4_journeys.py` → `j3_j4_evidence.json`

Every stage a check depends on completed inside the probe: seed → parse →
analyze (demo model) → report (7 findings) → fixqueue → revision legs.

- **Evidence lens**: fix-queue section + rows render (`shots/j3_evidence_lens.png`);
  rows are severity-ordered high→low; the ONE filter row drives queue and board
  together — severity chips are EXCLUSION toggles (clicking "low" hides low:
  7→2 rows, mediums only).
- **Keyboard fix loop**: ⤉ fix-loop button engages `loopState`; N steps forward,
  P steps back (wrap-safe, positions verified via `loopState.pos`); the current
  card gets `.loop-current`; Esc exits (`shots/j3_loop_active.png`).
- **Locate** (rung 18: one spelling, no 🎯): present on every queue row; jump
  produces no error banner.
- **Rung-20 duplicate contract**: no whole-row duplicate findings survive in a
  served report. Same-issue-text rows DO appear (two rows, differing fields) —
  by design (`collapse_exact_duplicates` keys the WHOLE row), recorded as
  writer-visible duplication evidence for Report 2 (`j3_same_issue_rows` in the
  evidence JSON).
- **Rung-19 strip count**: desk status strip names the finding count after
  analysis.
- **Triage**: Dismiss removes the row (7→6), the dismissed toggle appears,
  Restore returns it; marking a finding resolved warms the dawn meter
  (`shots/j3_dawn_after_mark.png`).
- **Feedback route contract (Report-2 evidence)**: for a PROJECT, every shipped
  route into Feedback — room toggle, gutter tab, palette, f key — lands on the
  Evidence lens by design (openFeedbackView → openDock). The legacy report /
  fix-queue tabs survive only through deep-link restoration
  `#/<project>/feedback`; probe drove that path and both panes render filled
  (`shots/j3_legacy_feedback_tabs.png`).

## J4 — Writer loop (24/24 PASS) — same script/evidence file

- **Rewrite → apply**: /rewrite returned candidates (demo model); /edits/apply
  applied; /edits carries `findings_status.summary` (addressed/still-present
  recompute) and `can_undo` flips true.
- **Undo/redo**: undo accepted, redo offered, redo accepted.
- **Export**: `.fountain` carries the working copy; `.fdx` returns FinalDraft XML.
- **Inline edit** (real UI): dblclick a clean line → type " AUDITED" → Enter →
  lands in `/script` (`shots/j4_inline_edit.png`).
- **Beatboard**: GET order → PUT permutation → persists → reordered .fountain
  export presents the new scene order → reset restores
  (`shots/j4_beatboard_exported.png`).
- **Drafts**: upload auto-activates (server-assigned name `draft-1`), content
  goes live; switching back to `original` restores the original content;
  diff `original→active` returns `{scenes, findings, from, to, characters}`;
  compare answers the same shape (`shots/j4_draft_activated.png`).
- **FINDING (recorded, P3)**: `POST /drafts/activate` for the ALREADY-ACTIVE
  draft answers **400 "No snapshot for draft 'draft-1'"** — a no-op gets a
  misleading data-shaped error. UI-unreachable (the drafts select cannot fire
  change on its own value), so API-contract polish, not a workflow bug.
  Evidence: `j4_activate_active_quirk` in the evidence JSON.
- Zero console errors / failed network calls across both journeys
  (`j3_j4_console.json`).

## J5 — Ideas lifecycle & graduation (12/12 PASS) — script `scripts/audit_j5_j6_j7.py` → `j5_j6_j7_evidence.json`

- Idea created via shipped API → canvas opens in the UI (`shots/j5_idea_canvas.png`).
- **Autosave**: typed content reaches `/api/ideas/<id>` ("memory palace" persisted).
- **Premise card** saved through the Structure panel (logline verified in the store).
- **Idea chat**: session starts; a turn answers (demo model).
- **Graduation**: multipart upload → project created; `premise.json` carried;
  the idea conversation carried into `sessions/`; the manifest pins the carried
  session — the same thread continues on the script desk.
- Graduated project opens on the desk (`shots/j5_graduated_desk.png`).

## J6 — Chat journeys (12 checks PASS, 3 labeled UNVERIFIED) — same script/evidence file

- **SSE parity (the smoking-gun check)**: tokens streamed over
  `messages/stream` == the persisted reply in `branches[current].messages`,
  character-for-character.
- **Quote-to-reply**: a quoted turn persists the quote with the message.
- **Fork/switch**: fork creates `audit-branch`; switch (payload key `name`)
  returns to `main`.
- **Persona settings**: flip to `script_consultant` and back to
  `writing_partner` per contract.
- **Translate**: route answers for the last assistant reply.
- **Consultant lens**: Dr. Sushruta answers in the dock through the real UI
  (`shots/j6_sushruta_lens.png`).
- **Delete**: a throwaway session deletes; strict 404 afterwards.
- **Memory suppress**: route contract verified (no live observation existed —
  see UNVERIFIED below).
- **UNVERIFIED (needs real model) ×3, reasons stated in evidence**: persona
  VOICE distinctness (demo answers from rules); translation fidelity (rule-based
  demo translation); real-observation suppression (demo turns produce no
  scoped observation).

## J7 — Robustness (16/16 PASS) — same script/evidence file

- **Deep links**: `#/p/cowrite`, `#/p/feedback` (legacy panel), `#/p/revision`,
  `#/p/beatboard` each restore their surface
  (`shots/j7_deep_links.png`); refresh mid-flow recovers without crash.
- **Keyboard-only**: `j` walks the manuscript forward monotonically over a
  20-scene script (positions recorded); `Ctrl+K` opens the palette and the
  typed command opens Revision — no mouse (`shots/j7_palette.png`).
- **Reduced motion**: `prefers-reduced-motion: reduce` collapses the palette
  animation (`animationName: none`).
- **XSS inertness**: hostile `<img onerror>` payloads in the script TITLE and a
  margin NOTE render inert — no execution, no injected node
  (`shots/j7_xss_title_literal.png`). The safe-id title fold was verified in
  source; the pass condition is inertness, not literal-text presence.
- **Delete guard**: `confirm()` cancel keeps the project; acceptance deletes it
  and the shelf answers 404.
- Zero console errors (expected `/report` 400 contract polls excluded by URL)
  and zero unexpected network failures across all three journeys
  (`j5_j6_j7_console.json`).

## Reproduce

```bash
python docs/audit/evidence-2026-09-30/scripts/audit_boot_probe.py
python docs/audit/evidence-2026-09-30/scripts/audit_j1_j2_journeys.py
python docs/audit/evidence-2026-09-30/scripts/audit_j3_j4_journeys.py
python docs/audit/evidence-2026-09-30/scripts/audit_j5_j6_j7.py
```

Each boots its own private studio (demo model, throwaway projects dir,
capability token) via `tests/e2e_browser_common.py` and tears it down.

## Findings so far (register starts at P3; none of the below is a product bug)

- [probe-fixed] Boot probe header comparison was case-sensitive — probe artifact.
- [probe-fixed] Progress filename and dock-open assumptions in J2 probes — probe artifacts.
- [probe-fixed] J3/J4 first-run probe assumptions (chip semantics, direct
  setRoom() bypassing loadFeedbackPanels, guessed draft names, guessed diff
  keys) — all diagnosed product-contract-first, then fixed probe-side.
- [probe-fixed] J5–J7 first-run probe assumptions (guessed session shape,
  switch payload key, translate index contract, dock-tab visibility, one-scene
  seed for the keyboard walk, console-error URL correlation) — same rule.
- [finding P3] Activate-already-active draft → 400 "No snapshot" (misleading
  error on a no-op; UI-unreachable). Recorded for the findings register.
- [observed, by-design → Report 2] Every Feedback route lands on the Evidence
  lens; the legacy report/fix-queue tabs are deep-link-only — a hidden second
  surface the writer can only reach by pasting a URL.
- [observed, by-design → Report 2] Same-issue-text findings render as two rows
  (whole-row dedupe contract) — writer-visible duplication.
- [observed, by-design] Desk toolbar is auto-hiding chrome; Run Analysis
  discoverability for a first-time writer — logged for Report 2.
- All demo-model-dependent claims are labeled; no real-llama-server claims made.
