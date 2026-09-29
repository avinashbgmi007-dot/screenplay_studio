# Report 2 — Feedback UIUX Architecture Analysis

**Date:** 2026-09-30 · **Target:** `main` @ `ddac2df` · **The question you asked:** the feedback surface's handling of backend API data feels cluttered — fix the current one, or design a new architecture that raises the writer's productivity?
**Method:** grounded in the audit's captured evidence ([evidence index](evidence-2026-09-30/README.md)) plus source read at cited lines. Doc-only claims excluded. No product code changed. Common-vs-specific cross-reference with [Report 1](2026-09-30_e2e_readiness_report.md) is in §7.

---

## 1. The verdict up front

**Fix the current architecture — but by removing, not by adding.** The clutter you feel is real, measured, and located: it is not the room model, the dock, or the design system failing — it is that the Evidence lens has quietly become a **single-viewport dump of ~12 stacked sections**, and the same findings state is projected by **four overlapping surfaces**. A new IA would be a $2,000 answer to a $200 problem: the muscle memory, a11y contracts, route map, and 244-check suite all belong to the current architecture, and the measured problems are all *additive* problems — solvable by deletion and one structural change (§4). My recommendation: **Option A+ (below) — a two-tier Evidence lens with a single findings-state model**, phased, no big-bang rewrite.

---

## 2. The measured clutter mechanism (from the audit, not vibes)

### 2.1 The Evidence lens stacks ~12 sections in one scroll

`renderDockEvidence()` (`screenplay_studio/webapp/app.js:5901-6020+`) assembles, in order: arrival strip (0b) → pass-arc line (0b2) → strengths (0c) → failure banner (0d) → model line (0d) → filter row + fix-loop chip (0a) → script-mass strip + ruler (0) → current-scene box (1) → fix queue (2) → scene findings (3) → script-level findings (3) → by-category catch-all (4). All of it renders into one ~319px dock column (`style.css` dock geometry; the rung-18 comment in `renderFixQueuePanel` measures the column at 319px).

**Measured from the audit:** the demo report produced 7 findings (`j3_j4_evidence.json: seed_findings`) — meaning **≥13 chrome sections preceded or surrounded 7 content rows** in one scroll. The chrome-to-content ratio is the clutter mechanism: every section is individually justified (each has an explanatory comment naming a real past defect), but their *sum* has no gate. Progressive disclosure exists *within* sections (P1.6 collapsible headers, phase6 suite), never *across* the lens.

### 2.2 Four surfaces project the same findings state

1. **Evidence lens** (dock) — the primary surface (J3-verified).
2. **Legacy `#feedback-panel`** — Report pane + Fix Queue tabs, reachable **only via deep link** `#/<project>/feedback` (J3 drove it and verified both panes filled; every shipped route — room toggle `app.js:9753-9755`, gutter tab, palette `:8551`, `f` key `:8826-8828` — lands on `openFeedbackView()` → `openDock("evidence")` instead). A hidden second surface rendering the same report/fixqueue data is unmaintained surface area, not a feature.
3. **Revision view** — re-renders the fix queue panel again (`app.js:7822` calls `renderFixQueuePanel`).
4. **Margin pins** on the manuscript — Locate-only since the Problem Board was retired (CONTEXT.md, code-verified).

One finding can therefore appear on up to four surfaces; the "ONE filter" (R5-b) and "ONE counter" (N3) contracts in the code exist precisely because the surfaces kept drifting.

### 2.3 Dedupe is whole-row, so the writer still sees near-duplicates

`collapse_exact_duplicates` keys the **whole row** (`screenplay_analyzer/dedupe.py:242` — `json.dumps(f, sort_keys=True)`), by design so no information is ever dropped (rung 20's own docstring). Measured consequence: the demo report showed the same sentence twice — `[demo] Sample dialogue finding…` on **scene 1 and scene 4, identical in every field except `scene_refs`** (`j3_j4_evidence.json: j3_same_issue_rows`). The writer reads one note, twice. Per-scene repetition of a whole-script note is exactly the "same opinion rendered twice" clutter you flagged.

### 2.4 Auto-hiding chrome hides the primary verb

The desk toolbar (Run Analysis, its status line) is `.auto-hide-chrome`: `opacity: 0; pointer-events: none` until a top-edge mousemove (`e2e_browser_phase8_lifecycle.py:55-84` root-caused this; J2 verified the hit-target contract). A first-time writer sees a clean desk with no visible way to start. Discoverability of the *one verb that starts everything* is delegated to a hover.

### 2.5 What is NOT the problem (cleared by evidence)

- The **room model** (Co-write/Feedback as lenses over one script) — every route works, deep links restore all four views (`j5_j6_j7_evidence.json`, J7).
- The **severity language** (rim+mass+label, DESIGN.md) — verified in use, not the source of clutter.
- The **fix queue ordering/filters** — severity-ordered, one-filter-drives-all verified (J3); this is the healthiest part of the pipeline.
- **Backend payloads** — `/report` and `/fixqueue` are lean; the client does joins (statuses/intents) the backend could pre-compute, but payload size was never the measured problem. Clutter is a *rendering decision*, not a data problem.

---

## 3. Expert-panel review (rubrics applied to the captured evidence; outputs gated)

- **IA architect:** the lens violates its own progressive-disclosure principle — disclosure happens inside sections but never across the lens. Verdict: restructure in two tiers; do not re-invent navigation.
- **Writer-advocate (JTBD):** the writer's loop is find → locate → decide → fix → verify → next. The lens serves "find" well (queue, loop, filters) but every other step's support arrives as *additional stacked sections* rather than as state on the current one. Verdict: the fix-queue must become the lens's home; context sections must be summoned, not stacked.
- **Trust & provenance reviewer:** verification badges, model line, failure banner are honest (verified in J3/J2) but each claims a permanent slot. Verdict: provenance belongs in the section it describes, not in a chrome preamble.
- **Design-system auditor:** DESIGN.md is violated by *accumulation*, not by any component: "the manuscript is the only brightly lit object" and the dock's chrome mass now compete for attention at 319px. Verdict: removal restores conformance; no new tokens needed.
- **A11y/perf:** `innerHTML` full re-render of the whole lens on every state change (verified call sites: dismissal, intent marks, filters) re-announces and re-mounts everything; live-region discipline elsewhere in the app is better than this one lens. Verdict: single-state model (§4) fixes this as a side effect.
- **Usability walk (demo-data session):** 7 findings → writer must scroll past ~8 sections before the queue; the loop mitigates it for keyboard users only.

**Unanimous panel verdict: fix, don't rebuild** — and the loudest finding is that the app *already knows* this: every clutter fix shipped so far (rung 18's verb unification, rung 19's count refresh, rung 20's dedupe) was a deletion or unification.

---

## 4. The options, and the recommendation

**Option A — patch in place (reject):** collapse some sections, keep the 12-section single tier. Reject because it leaves the root cause (one undifferentiated scroll, four surfaces) and regresses within months — the historical pattern.

**Option B — brand-new IA (reject):** a fresh surface model (e.g., the `preview-next/` "report-first" lab). Reject because: (a) the measured problems are not IA problems — the routes, room model, and queue semantics verified healthy; (b) migration cost is real: deep links, a11y outline contracts, 244 green checks and writer muscle memory all bind to the current shell; (c) Option A+ delivers the same clarity for a fraction of the risk.

**Option A+ — two-tier Evidence lens on ONE findings-state model (RECOMMENDED).** Three moves:

1. **The lens opens on Tier 1 — the worklist.** Fix queue (severity → act), arrival strip (it answers "did my edits work?" — the inversion already shipped in code), dawn meter, filter row + fix loop. Everything else becomes **Tier 2, summoned**: Coverage/Strengths, script-mass + ruler, by-category catch-all, model/provenance line move behind a single "Context" disclosure at the lens foot; the current-scene box stays a slim header *because the queue already answers per-scene via Locate*.
2. **One findings-state model.** Today four renderers re-derive the same state from `/report` + `/fixqueue` + `/edits` (verified call sites). One store → one renderer → three thin hosts (lens, revision column, deep-link pane) is the structural change that stops the drift the N3/R5-b comments keep patching. The deep-link-only legacy panel is deleted in this move (Report 1 §8's doc delta becomes moot).
3. **Dedupe for the reader, not the machine.** Keep whole-row collapse for data integrity; add a *display* grouping: identical `issue` text across scenes renders once with a scene-count chip ("Scenes 1, 4 — same note"), expanding on click. No data loss (the underlying rows and marks stay per-scene), the repetition the writer sees disappears. Gate 2 note: in the measured case the only field differing between the two rows is `scene_refs` ([1] vs [4]) — the chip preserves exactly that information, so rung 20's "a difference the writer would lose" rule is honored at the display layer too.

Result at 1440×900: opening the lens shows the worklist and the dawn meter **first**, with zero scrolling to the first actionable row; every glance-aside is one click away, not 12 sections away.

**Success metrics (verify after):** sections-before-first-actionable-row ≤ 1; same-issue visible rows = 1; lens re-render DOM churn bounded by the visible tier; dock at 319px shows queue header + ≥3 rows without scroll on a 7-finding report.

**Migration & risk:** three shippable phases (Tier re-order → state-model consolidation → display dedupe), each reversible, each landing into the existing suite (phase6/dock-sections suites already pin queue behavior — they will catch regressions). No route, deep link (except the deleted legacy panel), keyboard contract, or design token changes.

---

## 5. Target UX architecture for the feedback pipeline (concise spec)

- **Tier 1 — Worklist (default):** arrival strip (draft-progress lead) · dawn meter · filter row + fix loop · fix queue rows (severity → act, Locate/Rewrite/Discuss/Dismiss verbs, scope label from rung 18) · scene chip row (This-scene count, jump).
- **Tier 2 — Context (summoned):** coverage + strengths · script-mass strip & ruler · by-category catch-all · provenance (model line, failure banner moved beside the rerun they explain) · live check (quickcheck) section.
- **State:** `FindingsStore` = server join of report + statuses + intents + marks, loaded once per script load (the `/edits` co-fetch contract already exists — `webapp_server.py:1840-1854`), notifying one renderer; hosts subscribe.
- **Interactions unchanged:** N/P loop, Esc, Locate jump, mark-addressed/defer, Dismiss/Restore, dawn warm-up — all verified behaviors carry over as-is.
- **A11y:** Tier switch is a labelled landmark toggle (not a hover); Tier 1 is the focus target after lens open; the deep-link legacy pane is retired with a redirect to the lens.
- **Motion:** one-shot tier reveal only (120–280ms band, DESIGN.md), reduced-motion collapses it.

## 6. Additional backend APIs the redesign would need (PROPOSED — not implemented, discuss first)

1. **`GET /api/projects/<name>/findings/summary`** — counts by severity × category × status + dawn %, one call. *Why:* the arrival strip, dawn meter, and filter chips currently derive counts client-side across three payloads; a summary endpoint makes Tier 1 renderable before the full report and gives the strip its number in one fetch (complements rung 19's write-time refresh).
2. **`GET /api/projects/<name>/findings?scene=N&status=open&severity=high`** — scene/status/severity-filtered findings. *Why:* Tier 1's per-scene chip and the loop's `loopList()` currently filter the full client-side list; a queryable endpoint keeps Tier 1 cheap on 100+ finding reports where today's full-report fetch is the only source.
3. **`POST /api/projects/<name>/findings/intent/batch`** — batch intent/marks. *Why:* the fix loop's mark-and-next cadence is a write per keypress today (`/findings/intent` one at a time); a batch endpoint bounds writes during the loop and enables future offline batching. (Feasibility: a thin loop over the existing per-id `revision.set_finding_intent`; the route shape above is Flask-idiomatic, correcting the earlier `intent:batch` sketch at Gate 2.)
4. *(Optional, Tier 2 only)* **`GET .../findings/groups?by=issue-text`** — server-side display grouping. *Why:* keeps the §4.3 display-dedupe from being recomputed client-side on every render. Could ship client-side first; only justify the endpoint if profiling shows cost.

Nothing in §4 requires these to ship first — all four are density/latency improvements that become worthwhile *after* the state-model consolidation.

## 7. Common vs. specific to Ask 2

- **Common with Report 1 (shared verified foundation):** the route fold (§2.2), same-issue rows (§2.3), auto-hide chrome (§2.4) — verified once, cited by both reports; Report 1 cross-references them as UX findings rather than duplicating analysis.
- **Specific to this report:** the ~12-section lens stack (§2.1), the four-surface projection count, the fix-vs-rebuild decision (§4), the two-tier target architecture (§5), the four proposed APIs (§6), the success metrics and phased migration.
- **Specific to Report 1:** readiness verdict, P3 register, security/concurrency/stall-heal verification, suite cross-run, docs delta, UNVERIFIED labels.

## 8. Open questions for the brainstorm you asked for

1. Should the arrival strip stay Tier 1 (my panel says yes — it answers the writer's first question) or move into Coverage (Tier 2)? *My position: Tier 1, but collapsed to one line after first read.*
2. Delete the legacy deep-link panel outright, or keep it behind a feature flag one release? *My position: delete — it is unverified surface area; the deep link should redirect.*
3. Display-dedupe grouping: collapse by identical issue text (measured case), or also by same quote under different rules (the rung-20 docstring's "two notes about one line" case, which it deliberately keeps)? *My position: identical-text only; same-quote-different-rule is real craft information.*
4. Do the Tier 2 sections need to remember their open state across sessions (prefs), or always open collapsed? *My position: remember per project, like the existing quickcheck collapse does.*

---

## 9. Gate 2 — adversarial red-team verdict (2026-09-30)

**Pressure-test of the recommendation:**
- **Against DESIGN.md:** the two-tier lens *restores* conformance rather than straining it — the contract's own "Do keep the manuscript the brightest object" and "don't let an analysis panel take the manuscript's width" are honored by *reducing* dock chrome mass; Tier switching is a labelled landmark (severity language, tokens, and the one-gold-key discipline untouched). The display-dedupe chip carries the severity rim/mass/label of its representative row, so severity is never encoded by color or count alone.
- **Against the writer-JTBD frame:** Tier 1 = the find/decide/verify loop; Tier 2 = the orient context. The only JTBD risk found: a writer who *uses* the script-mass strip as their primary map would now pay one click. Mitigation adopted: Tier 2 sections remember per-project state (open question 4), and the scene chip row stays Tier 1.
- **Against the measured numbers:** the target (sections-before-first-actionable-row ≤ 1; same-issue visible rows = 1; queue header + ≥3 rows unscrolled at 319px on the 7-finding report) is derived from the audited geometry and the `j3_same_issue_rows` case — not from aspiration.
- **Cross-checked vs Report 1:** shared claims (route fold, same-issue rows, auto-hide chrome) say the same thing in both reports with the same evidence paths; no contradiction.

**What the critique changed:** the batch-intent API sketch was corrected (`intent:batch` → `intent/batch`, with the thin-loop feasibility note over the existing `revision.set_finding_intent`); the dedupe recommendation now states explicitly that the scene-count chip preserves the only field that differed in the measured case (`scene_refs`), honoring rung 20's no-information-loss rule at the display layer.

**What the critique acquitted:** the fix-vs-rebuild verdict (both rejected options hold their rejection reasons), the four-surface count (call sites re-verified), the ~12-section stack order (matches `renderDockEvidence` source), the "what is NOT the problem" clearances, and proposed APIs 1, 2, and 4 as feasible against the current server code (`_record_findings_metrics`, `_load_report_sanitized`, `finding_statuses` all exist and are the right primitives).

**Verdict: the recommendation stands — Option A+, three moves, phased — with two repairs applied.** Report 1's Gate 2 section covers the readiness register.
