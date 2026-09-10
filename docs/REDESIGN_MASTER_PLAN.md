# UI Redesign Master Plan — Step Zero

> **Status:** ACTIVE · the working pre-design document for the full UI/UX rebuild.
> **What this is:** the safety scaffold. It does NOT contain the new design — it makes
> the new design safely buildable: inventory, audit, frozen rules, gates, phasing, and
> the open questions the design phase must answer.
> **What this is NOT:** a visual direction. Colors/layouts/motion live in the design
> phase that follows (and partially already in `DESIGN.md` + `docs/design/ux2026/`).
>
> **Sequencing agreed with the user (2026-09-10):** finish this doc → then the UI/UX
> discussion (direction, references, taste) → then design → then phased build.
> Working model: **design free (Scope B), build gated (Scope A's discipline)**.

---

## 0. Relationship to existing documents

| Doc | Role here |
|---|---|
| `DESIGN.md` (2026-09-01) | The *intended* design system (Nocta). Drifted from the shipped app — see §4. |
| `docs/design/ux2026/*.html` | Three evaluated prototype directions + shared kit (kit.css/kit.js/motion.css/graphics.css). Prior design capital — reuse, don't discard. |
| `docs/UI_UX_SPECIFICATION.md` | The **feature/integration contract** (761 lines: every screen, state, shortcut, API call). Any rebuild keeps 100% of it — visual freedom, behavioral lock. |
| `UI_CHANGES_DEFERRED.md` | 10 deferred feature-UIs. The redesign IA must reserve homes for them (§9). |
| `NOTES.md` | Phase 0–14 history + the hard-won invariants this doc freezes (§5). |
| `docs/USER_PERSONAS.md` | Three writer archetypes the redesign serves — density and flow decisions trace back here. |

---

## 1. Current-state inventory (surfaces × protection)

Every live surface, the phase that built it, and the gate that protects it during redesign:

| Surface | Origin | Protecting gate |
|---|---|---|
| Welcome desk (shelf · library · ideas) | Phase 0–3 | `smoke`, `ui_batch`, `ui_fixes` |
| Idea canvas (write · autosave · Sameer pill · structure card) | Phase 9 | `phase9_idea_canvas`, `ideas`, `ideas_v3` |
| Spark wall | pre-P9 | `spark_wall` |
| Manuscript workspace (scene pages · scene index · inline edit anchors) | Phase 3B→13 | `smoke`, `phase8`, `export_flush` |
| Desk toolbar (Run Analysis · progress chip · retry · status · search · Focus/Revise · drafts · overflow) | Phase 8 + 13-D | `phase8_lifecycle` (incl. the ≤64px slim gate) |
| Context Dock (Evidence · Sameer · Sushruta · Stash&Notes lenses) | Phase 5–7, 13-A | `phase5_dock`, `phase6_evidence`, `phase7_chat_lenses` |
| Problem Board + edge tab (live workspace row) | Phase 13-C/D | `phase13_legacy_cleanup` |
| Partner drawer (co-write room) | Phase 0–4 | `smoke` (streaming proofs), `phase4` |
| Feedback View (3-panel: Sushruta · script · board/Sameer) | Phase 4/6 | `phase6`, `phase7` (consult adoption) |
| Premise View (full-screen card) | Phase 13-B | `phase13` |
| Revision View · Compare · Beat Board · Reader · Flow | Phase 10 | `phase10_structural_tools` |
| Status strip (model · connection · dawn · level) | Phase 0 | `smoke`, `phase12` |
| Responsive system (tablet 900 / mobile sheet) | Phase 11 | `phase11_responsive` |
| Visual/motion pass (spring, spotlight, reduced-motion clamp) | Phase 12 | `phase12_visual_motion` |
| Selection floats (Ask Sameer · Stash · Note) + text popup | P13-C | `selection_translate`, `ui_fixes` |
| Command palette · keyboard layer | Phase 10 | `phase10`, `phase14` (focus leg) |
| Session restore | Phase 3 | `phase14` (restore leg) |
| Sign-off journey (all of it, chained) | Phase 14 | `phase14_signoff_journey` (48 checks) |

**Rule: a surface may not be redesigned unless its gate is green the day before and the day after.**

## 2. Measured architecture audit (2026-09-10, at commit `fd181a4`)

### Webapp size
- `style.css` — **5,765 lines**, 28 media queries, 68 `!important`
- `app.js` — 7,790 lines (vanilla, no build step — this stays)
- `index.html` — 744 lines (6 full-screen views, all `main#main` children)

### CSS debt (the redesign must pay this down FIRST, before any visual change)
| Finding | Count | Consequence |
|---|---|---|
| Token definitions | 45 tokens × 2 blocks (night `:root` L114 + `body.dawn` L2752) | Dawn lives 2,600 lines below night — override collisions, no single source. **Consolidate into one token layer at the top.** |
| `var(--…)` usages | 1,004 | Good bones — tokens are real and load-bearing. |
| Off-token hex literals | ~60 (top: `#b98a44`×10, `#a89c88`×9, `#1a140d`×8, `#b3573f`×7, `#4a4238`×7) | The Midnight-Desk warm palette was never tokenized. Normalize into named tokens or delete. |
| `rgba(` literals | 166 | Mostly glass/surface whites — fold into `--glass*`/`--surface*` tokens. |
| z-index values in the wild | 59 declarations (R0 audit; the earlier "17 distinct" count under-measured — 28 distinct values incl. micro-layers) | **R0.1 DONE:** 31 overlay/system literals → 21 named `--z-*` tokens (values 1:1); 0–8 micro-layers intentionally literal. |
| Fonts actually shipped | Caveat · Courier Prime · IBM Plex Mono · Source Serif 4 · Special Elite (9 self-hosted woff2 ✓) | `DESIGN.md` claims Instrument Serif + DM Sans + JetBrains Mono — **the design doc and the app disagree**. See §4. |
| `!important` count | 68 | **R0.4 audit verdict: 0 removals.** Every site is load-bearing (beats inline styles from JS: `#script-pane` flex vs pane-width restore, dock-slot display vs setRoom inline; beats important-vs-important media rules: river-read dock vs mobile sheet), canonical (reduced-motion, print, resizing cursors), or beats ID-specificity bases (mode-hiding rules). R1+ component rewrites may retire them case-by-case with fresh cascade proofs. |

### Known hazards (carry the discipline, not just the code)
- **Mojibake**: baked double-encoded UTF-8 in webapp files (`â€”` = em-dash, 3rd char U+201D). Edits must match literal file bytes. One placeholder (`#project-title`) was user-visible and got fixed in P14; the rest are comment-level. A redesign pass is the natural moment to clean the file encoding for real.
- **Flexbox wrap trap**: wrap decisions use hypothetical basis sizes (P13 lesson). Any redesigned toolbar/row needs an explicit basis budget.
- **Views nesting invariant**: `.view` sections MUST stay `main#main` children (depth 2). `hideAllViews()` hides `.workspace` — a view inside it renders 0×0 (P13 gate caught this live).
- **Auto-hide chrome**: project bar fades on idle; tests must wake it. Any redesigned chrome must keep the wake affordance.
- **Escape vs drawer**: Escape does not close `#room-drawer` (`#drawer-close` does). Standardize dismissal semantics in the redesign.
- **Context Dock is manuscript-scoped**: in-flow inside `.workspace`, which the Feedback View hides by design. FV has its own panel set. Either preserve this split or redesign it *deliberately* — not by accident.

## 3. Non-negotiables (inherited from the product)

From `UI_UX_SPECIFICATION.md` §1 — reconfirmed as redesign law:
1. **Script-first** — the manuscript is the center; panels never take over.
2. **No build step** — vanilla JS + CSS, no framework, no bundler.
3. **Zero third-party calls** — fonts self-hosted (already true, 9 woff2), only Flask API + llama-server.
4. **Privacy-first** — everything on-device.
5. **Boring is good** — the redesign changes *what it looks like*, not *how it's engineered*.

## 4. The strategic fork: two design vocabularies

This is the single decision the design phase must make first. Both are real, both are documented, they disagree:

**A. Nocta / "Craft Precision" (DESIGN.md, 2026-09-01)**
Dark glass, violet `#7e6bff` accent ("the tool has opinions"), cyan secondary, Instrument Serif display + DM Sans body + JetBrains Mono data, ⌘K palette as primary navigation, surface morphing via View Transitions, grain texture. Backed by three evaluated prototypes (`ux2026/nocta.html` chosen over `lumen.html`, `beatwall.html` third) + a shared kit (kit.css/kit.js/motion.css).

**B. Midnight Desk (the shipped app)**
Warm lamp-lit writing room: `--ink-950` near-black warm canvas, lamp/sev-mid amber accents, paper-toned manuscript, Caveat handwritten touches, Special Elite typewriter accents, Courier Prime script. Never written down as a system — it accreted phase by phase and users (you) have been living in it since Stage 3.

**Options for the design phase (with the doc's stance):**
- **B1 — Evolve Midnight Desk into a full system.** Tokenize what ships, add the missing structure (type scale, spacing scale, z-ladder, motion spec), borrow Nocta's *ideas* (palette, morphing) but not its palette. Lowest emotional risk — it's the room you already know.
- **B2 — Land Nocta for real.** Replace the visual layer wholesale per DESIGN.md + prototypes. The prototypes are finished and evaluated; this is the "completely new UI/UX" reading in its purest form. Highest change impact; the warm-room identity goes away.
- **B3 — Hybrid.** Nocta's structure/discipline with Midnight's warmth retuned (e.g., keep warm ink canvas, adopt the type scale + z-ladder + motion + palette pattern).

*Doc stance:* the fork is a **taste decision — yours**, made in the design discussion with the prototypes open in a browser. This doc only guarantees all three are executable behind the same gates, because §2's token consolidation happens first either way.

## 5. Frozen architecture rules (the invariant list)

Carried from NOTES.md; every redesign PR asserts them:
1. `.view` sections are children of `main#main` (depth 2). Always.
2. One-line rows need a flex-**basis** budget, not shrink hopes.
3. Browser verification is DOM/text only — no screenshots, ever.
4. Test strings with real em-dashes never match baked mojibake — re-read before editing.
5. Visibility, not existence, is the assertion standard (0×0 ≠ shipped).
6. Severity middle tier = `--sev-mid` token; chrome accents = `color-mix(in oklab, var(--accent) N%, transparent)`. No hardcoded semantic rgbas in the new system.
7. Asset cache-bust `?v=hxNNN` on BOTH style.css and app.js after every webapp edit (currently `hx1b320`).
8. Findings: array position = index; no `index` field on report findings.
9. Keyboard parity is a feature: Ctrl+Z/Ctrl+Shift+Z, `/` search focus, palette, scene step — the redesign may re-map but never drop.
10. The Phase-14 journey (`tests/e2e_browser_phase14_signoff_journey.py`, 48 checks) is the redesign's final acceptance gate, updated alongside any deliberate behavior change.

## 6. Ring-fenced removals (own dependency-proof batch)

`#struct-rail` + `#rail-edge-tab` + `#pane-divider` — deferred from P13 into the redesign. Their batch:
1. Dependency proof per id (grep JS handlers, CSS rules, test references).
2. Migrate any still-live behavior (Stash/notes already live in the Dock; scenes in the scene index).
3. Remove, run the full ladder + journey, commit in one isolated commit.

The legacy `.desk` wrapper (index L331) joins this batch once the redesign decides the pane-divider's fate (it is `.desk`'s sibling).

## 7. Per-phase gate contract (how redesign phases are verified)

Every redesign phase lands green or doesn't land:
1. `node --check app.js` after any JS touch.
2. Asset bump both files.
3. Full browser ladder — the 18-suite canon: `phase5…phase13` (9), `phase14_signoff_journey`, `spark_wall`, `ideas`, `ideas_v3`, `selection_translate`, `ui_fixes`, `smoke`, `ui_batch`, plus `export_flush`/`translate_mic`/`library_delete` when their surfaces are touched.
4. pytest full run (686 baseline; the 2 known Windows file-lock flakes tracked, never "fixed" silently).
5. Viewport matrix spot-check: 1440×900 / 900×1200 / 390×844 (the journey automates the sweep).
6. Keyboard parity is a feature: Ctrl+Z/Ctrl+Shift+Z, `/` search focus, palette, scene step — the redesign may re-map but never drop. Keyboard + reduced-motion assertions stay in the journey.
7. One commit per phase, message = what changed visually + which gates prove no behavioral change.
8. Baseline discipline: `git diff --check`, inspect diff, no unrelated file changes.
9. The Phase-14 journey (48 checks) is the redesign's final acceptance gate, updated alongside any deliberate behavior change.
10. Findings indexing (array position = index) is load-bearing for cards, board rows, and findingStatus — any finding-surface redesign preserves it.

## 8. Migration phasing skeleton (R-series)

Deliberately conservative order — the token/primitive layers are where safety is bought:

| Phase | Name | Content | Gate emphasis |
|---|---|---|---|
| R0 | **Token layer** | Consolidate night+dawn token blocks to the top; normalize the ~60 off-token hexes + 166 rgba literals into named tokens; adopt the z-ladder; clean file encoding (mojibake). Zero visual change by definition. | Pixel-neutral: ladder green, journey green. |
| R1 | **Type + spacing scale** | One scale, applied; retire ad-hoc px values; font decision from the design discussion lands here. | phase12 (motion/visual), phase11 (responsive). |
| R2 | **Primitives** | Buttons, inputs, chips, cards, selects, scrollbars — single components styled once. | ui_batch, smoke. |
| R3 | **Composites** | Desk toolbar, Context Dock, Problem Board, status strip, palette. | phase5–8, phase10, phase13. |
| R4 | **Surfaces** | Welcome desk, idea canvas, manuscript workspace, Feedback View, premise/revision/compare/beatboard. | phase9, phase10, phase13, phase14. |
| R5 | **Motion + polish** | The design phase's motion spec; View Transitions decision (surface morphing) is evaluated HERE, not earlier. | phase12 + journey. |
| R6 | **Ring-fenced removals + IA homes** | §6 batch; reserve homes for the high-priority deferred UIs (§9). | full ladder + journey + pytest. |

R0 is the only phase that can start before the design discussion concludes; R1+ need the direction answers.

## 9. Reserved homes for deferred feature-UIs

`UI_CHANGES_DEFERRED.md` items, mapped so the redesign's IA doesn't paint the redesign into a corner:

| Deferred item | Priority | Reserved home in the new IA |
|---|---|---|
| Writer feedback (thumbs per finding) | **High** | Finding cards (manuscript) + FV board rows — a rate affordance on the existing finding card. |
| Scene cards view | Medium | New `.view` (depth-2 child of `main#main`) or a beatboard tab. |
| Character arc visualization | Medium | Beat Board extension or its own view. |
| KB rule browser · genre viz · confidence badges | Medium | Dock: a fifth lens ("Craft") is the natural slot. |
| Pipeline progress viz · realtime feedback | Low | Extends the existing progress chip/popover pattern (phase 8). |
| FDX export UI · quick analysis | Low | Overflow menu + desk toolbar respectively. |

## 10. Open design questions (the agenda for the UI/UX discussion)

1. **The fork** (§4): evolve Midnight Desk, land Nocta, or hybrid — decided with the three prototypes open side-by-side.
2. Typography: keep the shipped five (Caveat/Courier Prime/IBM Plex Mono/Source Serif 4/Special Elite) or move to DESIGN.md's trio (Instrument Serif/DM Sans/JetBrains Mono)? Which voice is this product?
3. Density: current compact writing-tool density vs. anything airier — check against `docs/USER_PERSONAS.md`.
4. Navigation: palette-first (Nocta's ⌘K stance) vs. the current chrome-first model?
5. What you HATE in the current UI (this list drives more than any moodboard).
6. References: 3–5 products/screenshots whose feel is the target (Arc Studio? Highland? Notion? Linear? something else).
7. Dawn (light) mode: first-class or demoted?
8. Motion appetite: Phase-12's spring/spotlight system — keep, amplify, or mute?
9. Mobile ambition: current mobile sheet is functional-minimal — is the phone a real writing surface in this product's future, or an ingestion/reading device?

---

*Written 2026-09-10 as step zero of the redesign effort. Next artifact after user sign-off:
the design brief, produced in the UI/UX discussion.*
