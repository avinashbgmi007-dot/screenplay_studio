# Report 1 — E2E Production-Readiness Audit

**Date:** 2026-09-30 · **Target:** `main` @ `ddac2df` (R6 rung 20) · **Scope:** frontend + backend, verified by direct application driving
**Method:** no doc-trust. Every claim below was verified against the running studio (real browser via Playwright, real HTTP via token-carrying requests) or against source at a cited line. Evidence artifacts: [docs/audit/evidence-2026-09-30/](evidence-2026-09-30/README.md) (index), 6 evidence JSONs, 18 screenshots, 4 re-runnable probe scripts.
**Gate 1 applied:** every finding was re-checked against its evidence file before inclusion; two numbers were corrected during that pass (same-issue rows differ only in `scene_refs`; route census is 88+2=90, not "≈90"). Doc-only claims: excluded.

---

## 1. Verdict

**CONDITIONAL-GO for its production context** — a local, privacy-first, single-writer desktop app (the only deployment context it claims; DESIGN.md, README "local, privacy-first"). The headline, stated plainly rather than buried:

> **No P0, P1, or P2 findings anywhere in the audit.** 164 direct checks across boot + seven journeys + API contract probes passed; the repo's own 8 cross-run suites (244 checks total) all green on the same HEAD. Every product finding confirmed is P3-class polish.

The conditions are the standing P3s in §4 and the UNVERIFIED labels in §7 — none blocks a writer on a local machine; two would matter more if the API ever faced non-SPA clients.

What was actually exercised (correctness basis):

| Phase | Checks | Evidence |
|---|---|---|
| Boot & security posture | 16/16 | `evidence-2026-09-30/boot_evidence.json` |
| J1 onboard/upload · J2 analysis + stall-heal | 25/25 | `j1_j2_evidence.json` |
| J3 feedback surfaces · J4 writer loop | 48/48 | `j3_j4_evidence.json` |
| J5 ideas/graduation · J6 chat · J7 robustness | 44/44 | `j5_j6_j7_evidence.json` |
| Phase 2 API contract probes | 31/31 | `phase2_api_evidence.json` |
| Phase 3 repo suites (cross-run) | 8/8 suites, 244 checks | `phase3_suites_evidence.json` |

---

## 2. Method (what "verified" means here)

- The studio was booted exactly as shipped — capability token minted, demo model, throwaway projects dir — via the repo's own harness (`tests/e2e_browser_common.py`), not a special audit mode.
- Journeys completed **inside the probes**: seed → parse → analyze → report → fixqueue → revision loop all ran in-process; no surface was verified off an assumed prior state.
- Every error response was asserted against the SPA's `api()` contract (`screenplay_studio/webapp/app.js:103-140`: JSON body with a readable `error` string; 403 auto-retry; 408 watchdog flag) — the actual client is the contract.
- All demo-model-dependent behavior is labeled; nothing real-model is claimed (§7).
- Probe bugs were diagnosed product-contract-first, then fixed probe-side only. **Zero product code was changed** by this audit (commits `2c4a4ad`, `cd94203`, `ec0e7fa`, `d43d863` touch only `docs/audit/evidence-2026-09-30/`).

---

## 3. What held (the strongest evidence, briefly)

- **Honest-state machine under failure.** A real mid-run process kill + restart on the same projects dir: a fresh heartbeat does *not* heal to `stalled`; a heartbeat backdated 31 min heals with an honest "Re-run Analysis" detail; a torn `progress.json` answers HTTP 200 `{"status":"retrying"}` instead of a 400 mid-poll (`j1_j2_evidence.json: j2b_*`, `webapp_server.py:2177-2255`).
- **Streaming == persistence.** SSE tokens concatenated equal the persisted reply character-for-character (315ch == 315ch; `j5_j6_j7_evidence.json: j6_stream_lengths`), and a mid-stream disconnect leaves the session file valid with the server healthy (`phase2_api_evidence.json`).
- **The writer loop round-trips.** Rewrite → apply → `findings_status.summary` recompute (`addressed:1, still_present:0, unknown:6`) → undo → redo → export `.fountain`/`.fdx`; draft upload auto-activates and switch-back restores content verbatim (`j3_j4_evidence.json`).
- **Security by default.** Tokenless writes 403; encoded and plain path traversal on `<name>` never succeeds; `/api/config` leaks no token; CSP `frame-ancestors 'self'` + nosniff on the SPA document; zero external requests on first paint (`boot_evidence.json`, `phase2_api_evidence.json`).
- **Concurrency.** Concurrent analyze: exactly one 200, one clean 409 (`concurrent_analyze_codes: [200, 409]`); concurrent idea saves both accepted with the store intact.
- **Graduation carries the thread.** `premise.json` + conversation carried; manifest pins the carried session (`j5_j6_j7_evidence.json`).

---

## 4. Findings register (locked format; rubric in §5)

**F-01 · Backend · P3 · Activating the already-active draft returns a misleading 400**
- **Evidence:** `j3_j4_evidence.json: j4_activate_active_quirk` — `POST /drafts/activate {"name":"draft-1"}` (already active) → `400 {"error":"No snapshot for draft 'draft-1'."}`
- **Repro:** upload a draft (auto-activates, `screenplay_studio/diff.py:112-114`), then POST activate with the same name. The 400 comes from `diff.activate_draft` requiring `drafts/<name>/parsed.json` (`diff.py:140-145`) — a snapshot only exists after the draft is folded.
- **Impact:** an API caller retrying an activate can't distinguish "already done" from "your data is gone." Not reachable through the UI (the drafts `<select>` cannot fire `change` on its own value — verified J4).
- **Fix direction (prose):** treat "activate the active draft" as a success no-op, or answer 409 with an "already active" error; either way the message should not imply missing data.

**F-02 · Backend · P3 · Negative finding index falls through to an HTML 405**
- **Evidence:** `phase2_api_evidence.json: finding_negative_index` — `POST findings/-1/dismiss` → 405 with `<!doctype html>` body.
- **Repro:** POST to `/api/projects/<name>/findings/-1/dismiss`. `-1` escapes `<int:index>`, matches the GET-only catch-all `/<path:filename>` (`webapp_server.py:663`), and Werkzeug answers its default HTML 405.
- **Impact:** the error body is unparseable by `api()`, so any client sees a generic failure, not the M4 guard's message. UI-unreachable (indices come from the server's own report).
- **Fix direction:** make the dismiss/undismiss routes accept negative-int paths (or validate before routing) so the M4 JSON-400 contract covers the whole integer domain.

**F-03 · Backend hardening · P3 · `nosniff` is scoped to the SPA document, not API JSON**
- **Evidence:** `phase2_api_evidence.json: api_json_nosniff` (`present: false` on `/api/health`); contrast `boot_evidence.json: security_headers_root` (nosniff on `/`), pinned by `tests/test_spa_security_headers.py:106`.
- **Impact:** minimal for `application/json` (no MIME confusion), but the hardening contract is document-scoped while the API is same-origin and token-bearing.
- **Fix direction:** move `X-Content-Type-Options` (and optionally Referrer-Policy) into `after_request` so every response carries it; keep CSP scoped to documents.

**F-04 · Analyzer · P3 · KB prompt budget exceeds its own soft ceiling**
- **Evidence:** `phase3_suites_evidence.json` (pytest tails, 3 suites): `RuntimeWarning: KB fragment for 'character' is 65226 chars (soft ceiling 40000). Set SCREENPLAY_KB_BUDGET to cap it.` (`screenplay_analyzer/rules_context.py:212`).
- **Impact:** a >60% over-ceiling prompt fragment on a model-sized context; the product's own warning machinery fired. With a small-context model this crowds the very budget M1 built.
- **Fix direction:** default a budget for the character fragment (or shard it per scene-count) so the shipped default honors its own ceiling without env vars.

**F-05 · Docs · P3 · The route map has drifted (+4 undocumented routes)**
- **Evidence:** `phase2_api_evidence.json: route_census` — source census: `webapp_server` 88 `@app.route(` + demo 2 = **90**, vs `docs/API_ROUTE_MAP.md` header claim of 84+2=86 (generated 2026-09-06). The doc's own regeneration rule is violated by the recent rungs.
- **Impact:** small but real for an audit trail that claims to be an authoritative source of truth.
- **Fix direction:** regenerate the map as its header instructs; consider a unit test that pins the census.

**Cross-reference (UX findings with product implications are analyzed in Report 2, not duplicated here):** every Feedback route lands on the Evidence lens while the legacy tabs survive deep-link-only; same-issue-text findings render as two rows by whole-row dedupe contract; auto-hiding desk chrome. All verified — see [Report 2](2026-09-30_feedback_uiux_analysis.md) §2.

---

## 5. Rubric (locked at Gate 1; applied as written)

- **P0** — data loss, crash, security hole, or a state that lies to the writer. **None found.**
- **P1** — core workflow broken or misleading. **None found.**
- **P2** — degraded UX with a workaround. **None found.**
- **P3** — actionable polish with evidence. **F-01…F-05.**

The absence of P0–P2 is a *measured* result across 164 direct checks + 244 suite checks, not an aspiration; the register was not padded to look thorough (below-noise items are in the appendix, not the register).

## 6. Below-noise appendix (one line each, not counted)

- Dev-server `Server` header discloses `Werkzeug/3.1.8 Python/3.14.3` on API responses (`phase2_api_evidence.json` header dumps) — version disclosure with no remote attack surface in a loopback-only deployment.
- The SPA polls `/report` on every project open and unanalyzed projects answer 400 by contract — visible as three 400s in console captures (`j5_j6_j7_console.json`); correct behavior, cosmetic noise.
- `pytest_asyncio` `get_event_loop_policy` DeprecationWarning across the suite (Python 3.14), in repo test output only.

## 7. UNVERIFIED (needs real model) — labeled, not skipped

All journeys ran on the built-in demo craft model (disclosed by the product itself; `boot_evidence.json: real_server_check`).

1. **Persona voice distinctness** — demo answers come from rules; Sameer-vs-Sushruta voice quality, memory *usefulness*, and humanization passes are unauditable here (`j5_j6_j7_evidence.json`, J6 label).
2. **Translation fidelity** — the route contract was verified (assistant-reply indexing, `webapp_server.py:4008-4016`); the translation *quality* of the demo is rule-based.
3. **Real-observation memory suppression** — demo turns produced no scoped observation to suppress; the route contract was verified (200/404 handling), the behavior with a live writer profile was not.

Data-validity claims that would need a real llama-server run (analysis quality, timeout behavior under 20-minute stages) are likewise not asserted anywhere in this report; the stall-heal and progress-contract checks were engineered to be model-independent.

## 8. Docs-vs-reality delta

| Doc claim | Reality | Verdict |
|---|---|---|
| 84+2 endpoints (`docs/API_ROUTE_MAP.md`, 2026-09-06) | 88+2 by source census | +4 undocumented (F-05) |
| "Feedback View REMOVED; every route lands on Evidence lens" (CONTEXT.md) | True for mouse/palette/f-key; the `#feedback-panel` markup survives and renders **via deep link** `#/<project>/feedback` (driven and verified, J3) | Doc slightly ahead of DOM — Report 2 §2 |
| `X-Frame-Options` absent; CSP `frame-ancestors 'self'` | Confirmed on the wire | Accurate |
| Demo disclosure amber marker | `/api/real-server-check` reports `{available:false, demo:true}`; UI shows the disclosure | Accurate |

## 9. Phase 3 — the repo's own suites on this HEAD (cross-run, `phase3_suites_evidence.json`)

| Suite | Kind | Checks | Result |
|---|---|---|---|
| e2e_browser_smoke.py | browser | 18 | PASS |
| e2e_browser_quickcheck.py | browser | 15 | PASS |
| e2e_browser_phase6_evidence.py | browser | 40 | PASS |
| e2e_browser_phase8_lifecycle.py | browser | 26 | PASS |
| tests/test_fixqueue.py | pytest | 4 | PASS |
| tests/test_production_readiness.py | pytest | 44 | PASS |
| tests/test_webapp_api.py | pytest | 87 | PASS |
| tests/test_negative.py | pytest | 10 | PASS |

**8/8 green, 244 checks** — the repo's own verification layer corroborates the independent audit on the same commit.

## 10. Common vs. specific (per the mission's two-ask structure)

**Common to both asks** (the audit's verified foundation): the route fold, same-issue rows, auto-hide chrome, and everything in §3/§4 — Report 2 builds directly on these; no claim exists in one report that contradicts the other.
**Specific to this report (Ask 1):** the readiness verdict, the P3 register, the security/concurrency/stall-heal verification, the suite cross-run, the docs delta, the UNVERIFIED labels.
**Specific to Report 2 (Ask 2):** the clutter mechanism analysis, fix-vs-rebuild decision, target UX architecture, and proposed APIs.

## 11. Reproduce

```bash
python docs/audit/evidence-2026-09-30/scripts/audit_boot_probe.py
python docs/audit/evidence-2026-09-30/scripts/audit_j1_j2_journeys.py
python docs/audit/evidence-2026-09-30/scripts/audit_j3_j4_journeys.py
python docs/audit/evidence-2026-09-30/scripts/audit_j5_j6_j7.py
python docs/audit/evidence-2026-09-30/scripts/audit_phase2_api_probes.py
python docs/audit/evidence-2026-09-30/scripts/audit_phase3_suites.py
```

Each boots its own private studio and tears it down. Findings F-01/F-02/F-03 are re-derived by the Phase 2/J4 probes on every run.
