# UI/UX Architecture Review — 2026-09-20

**Scope:** the shipped frontend architecture of Script Doctor Studio — its information
architecture, state/view model, theming, and alignment with `docs/PRD.md` and
`docs/USER_PERSONAS.md`.
**Mode:** read + live verification. **No product file was modified.** A throwaway
Playwright harness was used for the measurements below and then deleted.

> Evidence tags: `✅ measured` (my own live probe this session) · `✅ code-verified`
> (traced in source) · `✅ report` (prior audit, not re-executed by me) · `❓ unverified`.

---

## 0. Verdict

The product's **principles and its manuscript surface are strong**. The **UI architecture
is the liability**: several generations of UI co-exist behind a single 9,026-line script,
one finding can render on three surfaces at once, there is no URL state, and the theme
system can only win by out-specifying itself.

Two of the headline defects from the 2026-09-20 UI walk are **now genuinely fixed** (I
measured them). One was **weaker than reported** when probed live. The architectural
problems underneath all of them are untouched.

---

## 1. How the critique was built

Skills applied: `design-review`, `ui-ux-pro-max`, `web-design-guidelines`, `frontend-design`.
Expert lenses used (no subagents available in this environment — applied directly, tagged):
Information Architecture · Design Systems · Frontend Architecture · Accessibility ·
Product/Persona fit.

Live pass: booted the real studio on the built-in demo model (private port, throwaway
projects dir), seeded + analyzed the sample, then measured in headless Chromium at
1440×900. Method notes and the full JSON are in §7.

---

## 2. Findings

### F1 — The evidence layer has no owner (highest severity)

`✅ measured`. With the desk open and the dock's Evidence lens active, one finding renders
**simultaneously on three visible surfaces**:

| Surface | elements | visible | renders the finding |
|---|---|---|---|
| margin pins (`.finding-note`) | 17 | 17 | yes (6 findings) |
| Problem Board (`#problem-board`) | 1 | 1 | yes (6) |
| Context Dock (`#context-dock`) | 1 | 1 | yes (6) |
| craft shelf (`.craft-shelf`) | 1 | 1 | 0 when collapsed; a 4th surface when expanded |
| Feedback View (`#feedback-view`) | 1 | 0 | dormant |
| Revision View (`#revision-view`) | 1 | 0 | hidden until opened |

For every one of the 6 demo findings, my probe recorded a surface set of
`{margin_pins, problem_board, context_dock}`. The duplicate character finding rendered on
two pins and two board rows at once. The audit's "renders 4×" is conservative: it is **3
live, 4 with the shelf open, plus 2 more dormant/queued surfaces** in the same build.

This is not a bug list; it is *an unresolved argument about where the writer works*
encoded as five containers. The earlier contradictions (two surfaces computing a count
from two predicates, `F0`) were a symptom of exactly this.

**IA lens:** the product needs exactly two evidence surfaces with a declared job —
a **read surface** (the page; read-only ink/marginalia, no controls) and a **work surface**
(one panel: filter, intent, rewrite, discuss, escalate). Everything else is legacy and
should be deleted, not kept dormant.

### F2 — No URL/routing state, by construction

`✅ measured`. `grep pushState|replaceState|hashchange|popstate` in `app.js` → **0**.
Live: switching desk → Revision (`v`) → Beat Board (`b`) left `location.href` and
`location.hash` **byte-identical** (`url_changes: false`).

Navigation is an ad-hoc mutable `state.view` string union that has already drifted: the
declaration comment still reads `// "chat" | "script"` while the real values are
`cowrite | feedback | fv | premise | compare | revision | beatboard`, and `"fv"` is a
**dead value still consulted by session restore**.

Consequence: no deep links, no Cmd+click, and a QA harness that fights the app — the UI
walk's own note says *"the app restores its previous view across `goto`"* and it failed 5×
partly on that. A hash router (zero deps) would make every view deep-linkable and testable.

### F3 — A monolithic script that "no build step" is used to justify

`✅ code-verified`:

| Metric | Value |
|---|---|
| `app.js` | **9,026 lines**, **349 functions**, one mutable global `state` |
| `init()` | **695 lines** |
| `addEventListener` calls | **267** |
| `innerHTML` sites | **71** |
| ids in `index.html` | **260** |
| routing primitives | **0** |

"No build step" is a good constraint; **"no modules" is a false equivalence**. Native ES
modules run with zero bundler (`<script type="module">`). Splitting `app.js` into
`state.js`, `router.js`, `api.js`, `evidence.js`, `manuscript.js` kills the global and the
god-function while keeping the zero-build promise. This is the single highest-leverage
change available.

### F4 — The theme system escalates against itself

`✅ code-verified`:

- `style.css` is **6,511 lines** with **69 `!important`**, **58 `z-index`**, **34 sections**,
  and **two `:root` blocks** (`:161`, `:5276`).
- **Dawn is declared twice** — in `style.css` (~`:370`) *and* in `tungsten.css`.
- `tungsten.css` is 26 lines but must use `html body .selector { … !important }` to beat the
  base layer it was layered *after*.

When a "frozen visual system" can only win by out-specifying its own base, the token
architecture has already failed. There is no single source of truth for a token or a theme.

### F5 — Doc/reality drift makes the spec an unsafe rebuild contract

`✅ code-verified`. `docs/UI_UX_SPECIFICATION.md` opens by asserting *"Any rebuild MUST keep
every feature below"*, yet itself records:

- §4.4b Feedback View — *"dormant, unreachable — not deleted"*.
- §4.8 a Sameer slide-in panel — *"⚠ Currently a visual mock — its composer only appends
  locally; no API call is made."* But `app.js:8801` states that panel **was retired**
  ("This used to open the off-canvas `#sameer-panel`…"). So the spec documents a **fake
  feature that no longer exists.**
- §2.2 says Instrument Serif + DM Sans are **not bundled**; §12 says they **are** (18
  `@font-face`). The spec contradicts itself.
- §4.4c warns the palette advertises `b` for two different boards (a real collision,
  partially fixed in F10).
- Line counts are stale (spec ~8,530; actual 9,026).

A contract that promises "keep every feature" while listing dormant and imaginary ones
would have a rebuild faithfully port dead code and a mock.

### F6 — Four abandoned design labs ship inside the webapp

`✅ code-verified`. `webapp/preview-next/`, `preview-redesigns/`, `preview-r4/`,
`preview-design/` — **26 HTML files** across four generations of design exploration, still
in the served tree.

---

## 3. Alignment against PRD & personas

| Principle / derived rule | Aligned? | Evidence |
|---|---|---|
| Script-first (manuscript is the center) | **Strained** | Dock + board + pins + shelf crowd it; the occlusion defect (§7) showed cards over text until this month's fix. |
| Privacy-first, zero external calls | **Yes** | No hardcoded external hosts; fonts self-hosted. Exemplary. |
| Honest status (green/amber/red) | **Yes** | The best-engineered surface in the product. |
| Diagnose / prescribe split | **Yes** | Rooms → Sameer vs Dr. Sushruta. |
| Fail loudly | **Mostly** | Strong since the store fault-injection pass. |
| **Progressive revelation mandatory** (persona rule #2) | **Not built** | No real level gate; `setCraftLevel` auto-advances on click. The dock instead loads 7 filter chips + mass strip + trust readout + chart + queue + coverage into ~330px. This is *anti*-progressive. |
| Mentor-led: Sameer is a character | **Undermined** | The one surface that promised a persistent character panel was a mock and is now removed. |
| Idea-stage writer served | **Weakest** | Canvas renders no prose prompt (measured, §7); see §5. |
| Keyboard-first mastery | **Partial** | `b` collision; undo/redo are `display:none` (keyboard-only); palette once offered dead commands. |

The principles are not the problem. The problem is that the interface the principles
describe was never reconciled with the interface that got built.

---

## 4. What the live pass confirmed, refuted, or weakened

| Claim (prior audit) | My measurement | Verdict |
|---|---|---|
| One finding renders on 4 surfaces | 3 concurrent visible surfaces (pins + board + dock); 4th (shelf) when expanded | **CONFIRMED** (3 live) |
| Dock counts contradict the fix queue | mass strip `6 open of 6 findings` vs fix queue `6 open / 6 shown / 6 total` — they agree | **FIXED** (F0 holds) |
| Trust readout reads as failure (`0 of 6`) | shows `6 findings carried no quote to verify` | **FIXED** |
| Floating cards occlude the manuscript | 17 pins × 29 script lines → **0 overlapping pairs, 0px**; `.scene-notes` computed `position: static` (in-flow) | **FIXED** (R6 holds) |
| Idea canvas is a dead end (no prompt/hint) | canvas text = only `▸ Structure ✦ Grow into pages`; 0 prose placeholder in the canvas, but **12 explore chips exist** and a composer input is **visible** | **WEAKENED** — visual thinness confirmed; "no affordance at all" is not |
| Idea-room chat undiscoverable, input misrouted | `#input` visible (299×42) before and after `c`; drawer opens on `c` | **NOT reproduced** in the demo state |
| No URL state across views | `url_changes: false`, hash empty | **CONFIRMED** |

**Honesty note:** my earlier summary (in chat) repeated the audit's "occlusion" and
"4 surfaces" numbers as if they were mine. They were not; the occlusion measurement is
only now valid, and the live result is **0px** — correct that to *fixed*.

---

## 5. Idea room (the weakest surface) — corrected reading

`✅ measured`. The blank idea canvas renders no prose prompt; its entire inner text is the
two controls `▸ Structure` and `✦ Grow into pages`. That part of the "dead end" claim is
real: a first-time writer sees almost no guidance in the canvas itself.

But the earlier framing overstates the failure:
- guided **explore chips** are present (12 matched globally),
- the chat **composer input is visible** (299×42) and `c` opens the drawer.

So the honest defect is **not** "no affordance" — it is **hierarchy/thinness**: the useful
affordances exist but the canvas does not *say what to do first*. That is a design pass,
not a missing-feature bug. `#idea-content` also carried no `contenteditable` attribute at
rest and no `placeholder`, so the "where do I type" signal is weak.

---

## 6. Options & recommendation

### Option A — Truth-telling cleanup (low risk, ~1–2 weeks)
Delete dormant `#feedback-view`/retired chrome; remove the 4 preview labs; make the spec
honest; keep the count contract single-predicate; add the idea-canvas prompt. High value
per hour. Does not fix the monolith, the router, or the theme war. **Completeness: 6/10.**

### Option B — Strangler restructure, in place (recommended)
Keep the shipped behavior and the ~460-check browser net; rebuild from scratch the four
rotten subsystems:
1. hash **router** (deep-linkable, testable),
2. **native ES modules** out of `app.js` (zero-build preserved),
3. **one evidence model, two surfaces** (delete duplicates),
4. **one token/theme layer** (retire `!important` escalation, single `:root`, dawn once),
5. instinct-first **idea canvas**.

Highest value per unit of risk. **Completeness: 9/10.**

### Option C — Full greenfield rebuild
Gate on the §11 checklist + the browser suites as a conformance suite, and clean the spec
first or you will port the ghosts. The product's hard-won detail (quote verification at
0.72, honest connection semantics, mojibake-safe chat, i18n registers, store fault
tolerance, the 20-stage map) is exactly what a clean-slate rewrite loses.
**Completeness: 8/10, highest risk.**

**Recommendation: B.** A total rewrite attacks the *product* to fix the *architecture*.
Rebuild the architecture; keep the product.

---

## 7. Method & raw evidence

Harness: temporary `tests/_arch_verify.py` (deleted after the run) using
`tests/e2e_browser_common.start_studio()` (demo model, `--no-token`, private port) +
headless Chromium 1440×900. Raw JSON written to `impl-shots/ui_audit/arch_verify.json`
(gitignored). Key raw values:

```
simultaneous_surfaces.worst_simultaneous = 3   (per finding: margin_pins, problem_board, context_dock)
occlusion.pins=17 lines=29 overlapping_pairs=0 worst_overlap_px=0
occlusion.notes_position="static" notes_right_px=870 paper_right_px=902
routing.url_changes=false (desk=revision=beatboard= http://127.0.0.1:<port>/| )
count_texts.mass_strip = "6 open of 6 findings | 6 findings carried no quote to verify"
count_texts.fix_queue_titles = "Fix queue — 6 open / 6 shown / 6 total"
idea_blank.canvas_text = "▸ Structure\n✦ Grow into pages", hint_elements=6, explore_chips=12
js_errors = []
```

---

## 8. Self-critique

1. **Visual claims now rest on measurement, not reading.** Corrected — the occlusion test
   was vacuous on first run (wrong selector) and only became valid after the re-probe.
2. **Code size is a symptom, not the diagnosis.** The real rot is five co-existing UI
   generations, an unowned evidence layer, two theme authorities, and no router. LOC is
   cited as corroboration only.
3. **"Dormant ≠ broken."** Dormant surfaces are low *runtime* risk and high *documentation
   and velocity* risk. Severity is ranked accordingly; they do not break the app.
4. **Some duplication is intentional** (in-context vs ledger vs work surface). The finding
   is the *absence of a single owner*, not the existence of more than one view.
5. **I did not visually inspect this session's screenshots** (text-only tooling). The
   numbers are sound; a human should still eyeball `arch_verify_desk.png`.

---

*Authored 2026-09-20 from a read + live-probe session. No product file changed; the
verification harness was removed. Related: `ui_evidence_findings_2026-09-20.md`,
`production_readiness_2026-09-20.md`.*
