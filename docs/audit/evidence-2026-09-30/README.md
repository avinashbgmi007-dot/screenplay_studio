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

## Reproduce

```bash
python docs/audit/evidence-2026-09-30/scripts/audit_boot_probe.py
python docs/audit/evidence-2026-09-30/scripts/audit_j1_j2_journeys.py
```

Both boot their own private studio (demo model, throwaway projects dir,
capability token) via `tests/e2e_browser_common.py` and tear it down.

## Findings so far (register starts at P3; none of the below is a product bug)

- [probe-fixed] Boot probe header comparison was case-sensitive — probe artifact.
- [probe-fixed] Progress filename and dock-open assumptions in J2 probes — probe artifacts.
- [observed, by-design] Desk toolbar is auto-hiding chrome (opacity 0 +
  pointer-events none until a top-edge mousemove); discoverability of
  Run Analysis for a first-time writer is logged for the Report-2 UIUX
  analysis, severity TBD there.
- All demo-model-dependent claims are labeled; no real-llama-server claims made.
