# UI/UX Restructure Plan — 2026-09-20

**Produced by:** `/plan-eng-review` (gstack v1.87.4.0) over `docs/audit/ui_ux_architecture_review_2026-09-20.md`.
**Branch:** `main` · **Commit:** `a818eca` · **Mode:** FULL_REVIEW (scope accepted as Option B).
**Status:** all decisions resolved; ready to implement.

This plan is the output of an interactive review. Every section's remedy was
approved individually; therapy is recorded here rather than re-argued.

---

## 1. Approved decisions

| ID | Issue | Decision |
|---|---|---|
| 1A | Module-split hazard | **A** — land a structural symbol-uniqueness guard test first, then move to native ES modules one concern at a time behind the ~460-check browser net |
| 2A | Evidence consolidation | **B** — one client finding model + one render path; **plus** a shared server item-assembly helper, with envelopes/failure semantics kept at the routes |
| 3A | Router ownership | **A** — the router owns the view; `localStorage` session stores project/idea + scene only (one-time migration of the stored view) |
| 4A | Dormant Feedback View | **A** — delete the dormant `#feedback-view`; migrate stored `view:"fv"` to the workspace Evidence lens |
| 5A | Theme layer | **A** — pixel-neutral fold of the base tokens into Tungsten; delete the second `:root` and duplicate dawn; computed values byte-identical, gated by phase12/13 |
| 6A | Router mechanism | **B** — History API (`pushState`) + a Flask catch-all that does not swallow `/api/*` |
| 2.1A | `innerHTML` discipline | **A** — model/user text through `el()`/`textContent`; `innerHTML` only for static chrome |
| 2.2A | Swallowed load errors | **A** — 404 means "no analysis yet"; every other failure surfaces via `showError` |
| 3A-T | Test coverage | **A** — ESM guard + router unit tests + deep-link/reload/back-forward E2E; re-scribe (not delete) the phase6/phase13 pins that assert three coexisting surfaces |
| 4A-P | Manuscript render cost | **A** — measure first with a long synthetic script; optimize only if the number warrants it |
| 8A | Preview labs | **A** — delete the four dirs, the `/api/preview/*` routes, and their suites after confirming no live consumer |
| — | Cache-bust | Convention (not a decision): every touched asset bumps `?v=hx1bNNN` |

---

## 2. Architecture

```
                    ┌──────────────────────────── router.js (NEW) ───────────────────────────┐
  URL  ──pushState──▶  parse route → {project, scene, view}  ──▶  render(view)               │
                    │  unknown route ──▶ fallback (last project OR welcome)                  │
                    └───────────────┬───────────────────────────────────────────────────────┘
                                    │  router OWNS view; session keeps {project|idea, scene}
                                    ▼
   ┌── store.js (state) ──┐   ┌── evidence.js (ONE model, ONE render) ─┐   ┌── manuscript.js ─┐
   │ state, setters       │   │ filter predicate + counts + render      │   │ pages, ink, edit  │
   └──────────┬───────────┘   └────────────────────┬───────────────────┘   └────────┬─────────┘
              │                                     │                                │
              ▼                                     ▼                                ▼
        reader surface (read-only ink)      work surface (dock panel)          the manuscript
                                    ▲
                    app.js legacy ──┘  (deleted last; no big-bang rewrite)

  Server: webapp_server.py — /api/* unchanged; adds ONE catch-all for non-/api GET → index.html.
          Shared item assembly for findings; envelopes + failure semantics stay at the routes.
```

**Single points of failure / blast radius**
- The router is the highest-blast item: a bad route parse strands the whole SPA. Mitigated by a fallback route and E2E.
- The theme fold is the highest-visual-risk item: gated by existing computed-value pins.
- The evidence consolidation is highest user-visible: gated by re-scribed pins.

---

## 3. What already exists (reuse, don't rebuild)

| Sub-problem | Existing asset | Reuse? |
|---|---|---|
| DOM-free module split precedent | `webapp/core.js` + `node --test tests/js/` | **Reuse** as the pattern |
| Token override layer | `tungsten.css` (working) | **Fold into**, not reinvent |
| Shell architectures | 4 preview labs / 26 HTML files | **Read once, then delete** (8A→A) |
| Regression net | `tests/e2e_browser_common.py` + `run_browser_suites.py` (~460 checks) | **Reuse** as the gate for every slice |
| Finding identity + status | `computeFindingId` / `finding_statuses` (test-pinned) | **Reuse**; do not fork a second identity |
| Design intent | `docs/designs/product-ui-alignment.md` (craft-first nav, mentor, progressive revelation) | **Use as the spec** for the router's route names |

**Stale doc to fix as part of this work:** `DESIGN.md` (Nocta violet, Google-Fonts `<link>`)
contradicts the shipped Tungsten system and the zero-external-requests promise. This is a
known learning (`docs-drift-vs-code`, 9/10). Update it to Tungsten + self-hosted fonts.

---

## 4. NOT in scope

- **Full product rewrite / new shell** — rejected; attacks the product to fix the architecture.
- **Server payload unification** — the two fix-queue contracts stay (deliberate).
- **Scene-list virtualization** — measure first (4A-P); not committed.
- **Clean-URL SEO / SSR** — no server-rendered product.
- **Idea-room redesign** (the thin-canvas pass) — separate design change; tracked, not here.
- **`LICENSE` / `CHANGELOG`** — owner decision, unrelated.
- **`/cso` native helper** — needs the MSVC toolchain; unrelated.

---

## 5. Implementation Tasks

- [ ] **T1 (P1, human: ~2h / CC: ~20min)** — `tests/js/` — add the structural symbol-uniqueness guard test
  - Surfaced by: Anatomy 1A; prior learning `classic-script-split-hazards` (9/10)
  - Files: `tests/js/structural.test.js` (new)
  - Verify: `node --test tests/js/` fails when a symbol is defined twice, passes on HEAD

- [ ] **T2 (P1, human: ~1d / CC: ~40min)** — `webapp/` — extract `store.js` + `router.js` as native ES modules; router owns the view
  - Surfaced by: Architecture 3A, 1A
  - Files: `webapp/index.html`, `webapp/router.js` (new), `webapp/store.js` (new), `webapp/app.js`
  - Verify: `tests/e2e_browser_*.py` green; new deep-link/reload/back-forward E2E green

- [ ] **T3 (P1, human: ~6h / CC: ~30min)** — `webapp_server.py` — Flask catch-all for non-`/api` GET → `index.html`
  - Surfaced by: Architecture 6A
  - Files: `webapp_server.py`; test in `tests/test_webapp_api.py`
  - Verify: `/api/*` still 404/JSON as before; `/project/x/scene/3` serves the SPA

- [ ] **T4 (P1, human: ~1.5d / CC: ~1h)** — `app.js` → `evidence.js` — one finding model + one render path; delete the 3 duplicate renderers
  - Surfaced by: Code Quality (DRY) + Architecture 2A
  - Files: `webapp/evidence.js` (new), `webapp/app.js`, re-scribe `tests/e2e_browser_phase6_evidence.py`, `tests/e2e_browser_phase13_legacy_cleanup.py`
  - Verify: `phase6` + `phase13` green with the new one-surface contract

- [ ] **T5 (P2, human: ~4h / CC: ~25min)** — `webapp_server.py` — shared finding item assembly, envelopes kept at the routes
  - Surfaced by: Architecture 2A; prior learning `fixqueue-two-route-contract` (9/10)
  - Files: `webapp_server.py`; `tests/test_fixqueue.py`, `tests/test_preview_lab.py`
  - Verify: both envelopes unchanged; preview `dismissed_keys` intact

- [ ] **T6 (P2, human: ~5h / CC: ~30min)** — `style.css`+`tungsten.css` — pixel-neutral fold; delete second `:root`, duplicate dawn, dead blocks
  - Surfaced by: Architecture 5A; prior learning `shipped-token-layers` (9/10)
  - Files: `style.css`, `tungsten.css`, `index.html`
  - Verify: phase12 luminance/amber-free + phase13 geometry green; computed values unchanged

- [ ] **T7 (P2, human: ~3h / CC: ~20min)** — `app.js` — delete dormant `#feedback-view`; migrate stored `view:"fv"`
  - Surfaced by: Architecture 4A
  - Files: `webapp/app.js`, `webapp/index.html`, `webapp/style.css`, `docs/UI_UX_SPECIFICATION.md`
  - Verify: old-session migration lands on the workspace; no `"fv"` branch remains

- [ ] **T8 (P2, human: ~2h / CC: ~15min)** — `app.js` — dynamic text via `el()`/`textContent`; `innerHTML` for static only
  - Surfaced by: Code Quality 2.1A
  - Files: `webapp/app.js`
  - Verify: a finding whose `issue` contains `<b>`/`<img onerror=…>` renders literally

- [ ] **T9 (P2, human: ~1h / CC: ~10min)** — `app.js` — stop swallowing load errors (404 vs real)
  - Surfaced by: Code Quality 2.2A
  - Files: `webapp/app.js`
  - Verify: a 500 on `/report` shows a real error, not "No analysis yet"

- [ ] **T10 (P3, human: ~1h / CC: ~10min)** — delete `preview-*` + `/api/preview/*` + their suites
  - Surfaced by: Architecture 8A
  - Files: `webapp/preview-*`, `webapp_server.py`, `tests/`
  - Verify: `run_browser_suites.py` passes with these suites removed from its list

- [ ] **T11 (P3, human: ~1h / CC: ~10min)** — measure `renderManuscript` on a 120-scene script
  - Surfaced by: Performance 4A-P
  - Files: throwaway Playwright harness (delete after)
  - Verify: a number, then a decision

---

## 6. Regression tests (mandatory — IRON RULE, no approval needed)

- **R1** the ESM extraction must not break any currently-green browser suite (25 suites).
- **R2** the evidence consolidation must not break `phase6`'s pinned predicate/counts.
- **R3** the theme fold must keep `phase12`/`phase13` computed values identical.

---

## 7. Failure modes

| New codepath | Realistic failure | Test? | Handling? | User sees |
|---|---|---|---|---|
| Router: unknown/malformed route | bad hash → blank SPA | E2E (T2) | fallback route | last project/welcome |
| Router: deep link before data loads | flash of empty workspace | E2E (T2) | render after fetch | brief skeleton |
| Catch-all vs `/api` | API call returns HTML | unit (T3) | predicate excludes `/api` | correct JSON |
| Evidence render | quote with markup executed | unit (T8) | `textContent` | literal text |
| Theme fold | a token loses its value | phase12/13 | pixel-neutral gate | unchanged |
| ESM extraction | duplicate symbol blanks UI | guard (T1) | build fails loudly | nothing (caught pre-ship) |
| Preview deletion | a live consumer imports it | manual grep (T10) | confirm first | none |

**Critical gaps remaining: 0** (the router fallback and the ESM guard were both folded into approved tasks).

---

## 8. Worktree parallelization

| Step | Modules | Depends on |
|---|---|---|
| T1 guard | `tests/js/` | — |
| T2 router/store | `webapp/` (js) | T1 |
| T3 catch-all | `webapp_server.py` | — |
| T4 evidence | `webapp/` (js) + 2 test files | T2 |
| T5 server assembly | `webapp_server.py` | T3 |
| T6 theme fold | CSS + `index.html` | — |
| T7 dormant FV | js + html + css + spec | T2 |
| T8/T9 hardening | `webapp/app.js` | T2 |
| T10 preview delete | dirs + server + tests | T5 |
| T11 perf measure | throwaway | T2 |

**Lanes:** `A: T1 → T2 → T4 → T7/T8/T9` (shared `webapp/` js) · `B: T3 → T5 → T10` (shared `webapp_server.py`) · `C: T6` (CSS, independent) · `T11` after T2.
**Order:** launch **C** in parallel with **A**; run **B** in parallel (different module). Merge C, then B, then A.
**Conflict flags:** T4/T7/T8/T9 all touch `webapp/app.js` — keep them **sequential** in Lane A. T3/T5/T10 all touch `webapp_server.py` — sequential in Lane B.

---

## 9. Completion summary

- Step 0: Scope Challenge — scope accepted as-is (Option B, 8+ files acknowledged)
- Architecture Review: 8 issues found (all approved)
- Code Quality Review: 8 evaluated, 2 new decisions (6 covered by earlier remedies, referenced not re-asked)
- Test Review: diagram produced, 12 gaps identified (1 regression-critical)
- Performance Review: 1 issue (2 suppressed as low confidence)
- NOT in scope: written
- What already exists: written
- TODOS.md updates: 0 proposed (repo uses `UI_CHANGES_DEFERRED.md`; nothing new to defer)
- Failure modes: 0 critical gaps flagged
- Outside voice: **unavailable** (codex not installed; no subagent tool in this host)
- Parallelization: 4 lanes, 3 parallel / 1 sequential
- Lake Score: 10/11 decisions chose the complete option (6A→B was the fuller option)
- Unresolved decisions: 0

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Outside Review | codex (not installed) | Independent 2nd opinion | 0 | unavailable | missing coverage |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 12 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **OUTSIDE COVERAGE:** provider=codex, phase=plan-review, state=unavailable (CLI not installed; no subagent tool in this host). Missing outside coverage is not a clean pass.
- **VERDICT:** ENG CLEARED — ready to implement T1→T11.
NO UNRESOLVED DECISIONS
