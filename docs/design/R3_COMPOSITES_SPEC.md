# R3 Composites — design spec (IMPLEMENTED)

Status: IMPLEMENTED (2026-09-13) — all three decisions signed and landed;
elevation tokens + palette + backdrop + dawn shadows, with the glass-rim
elevation fix the palette probe surfaced.
Date: 2026-09-13. Author: session agent (census + lead critique);
elevation consult: ui-ux-designer-2 — FAILED (network 502, DNS error, no
content received); recipes are lead-authored.

## What R3 is

Per `docs/REDESIGN_MASTER_PLAN.md` phasing table: **Composites** — desk
toolbar, Context Dock, Problem Board, status strip, palette. Gates:
phase5–8, phase10, phase13 (geometry/behavior suites) + the full ladder.

## Census (2026-09-13)

### Geometry (untouchable — wireframe contract + suite-asserted)
- Desk toolbar: 700×40, one-line, overflow-x scroll, 4px thin scrollbar.
- Context Dock: right rail, open width 380 / min 320, slide 0.25s,
  visibility-hidden when closed (2.4.3), bows to power modes.
- Problem Board: absolute right:38, width 300/250–350, transform slide,
  bows to open dock (right: 380px; collapsed → edge-tab).
- Status strip: 28px pinned, mono 10px.
- Palette: modal 480px, palette-pop 0.22s, results max-height 320.

### Styling deltas (R3's actual work)
1. **Dock shadow RAW**: `#context-dock.open { box-shadow: -14px 0 36px rgba(0,0,0,0.28) }` — the only off-token composite shadow (board already uses var(--shadow-a35) with −18/40 geometry).
2. **Elevation is ad-hoc across the app** (reference set): sidebar 18px 0 46px a35; dock raw 0.28; board −18px 0 40px a35; modal 0 14px 44px a55; overflow banner + text-popup 0 12px 32px −8px a60; quote-float 0 8px 22px −8px raw 0.65; edge-tab −6px 0 18px raw 0.25. Two shadow families exist: plain alphas (--shadow-aN) as *colors*, and full recipes only for paper (--shadow-paper).
3. **Palette input pre-R2**: `#palette-input` still accent-deep border + inset a30; NO focus rule (global ring only) — inconsistent with the unified input treatment every other input got.
4. **Palette row hover off-token**: `.palette-row:hover:not(.sel) { background: rgba(233, 223, 206, 0.05) }` — warm-paper remnant; house rule = color-mix accent wash.
5. **Backdrop surfaces inconsistent**: glass-strong + blur(12) (banner/popup) vs color-mix srgb 85% + blur(20) (Sameer panel) vs glass + blur(14) (pill) — three blur+fill recipes for "glass over content".
6. Status strip / toolbar: flat (no elevation) today; wireframe contract silent on elevation.
7. **Dawn shadow story**: all shadows are black alphas — on dawn paper (#f1ede4) they can read muddy; dawn overrides exist for surfaces but NOT for the shadow family.

### Test-safety survey
phase5 asserts dock geometry/lens/tabs/Esc/focus — no shadow values. phase13
asserts board geometry/bows/clipping — no shadow values. Style-only swaps
safe; geometry stays frozen.

## Elevation recipes (lead-authored — consult FAILED: network 502, DNS error, after 34m; no content received)

The census revealed two shadow LANGUAGES, both legitimate: **lean** (X-offset
shadows for side panels sliding over content) and **lift** (Y-offset shadows
for overlays/pop-overs). The ladder names recipes; it does not force one
geometry onto both languages.

```css
/* R3 elevation ladder — full shadow recipes as tokens */
--elev-lean-right: -14px 0 36px var(--shadow-a35);  /* dock + board (unified;
   board folds from -18/40 — 4px delta, sub-perceptual) */
--elev-lean-left: 18px 0 46px var(--shadow-a35);    /* sidebar (keeps exact current geometry) */
--elev-modal: 0 14px 44px var(--shadow-a55);        /* modals, palette (current .modal recipe) */
--elev-float: 0 12px 32px -8px var(--shadow-a60);   /* pop-overs: banner, text-popup (current recipe) */
--elev-fab: 0 8px 22px -8px var(--shadow-a60);      /* quote-float (geometry kept; raw 0.65 → a60 token) */
--elev-tab: -6px 0 18px var(--shadow-a30);          /* pb-edge-tab (raw 0.25 → nearest token) */
```

Raw-literal retirement: dock 0.28 → a35 token family; quote-float 0.65 →
a60; edge-tab 0.25 → a30. (The idea-mode editor's 0 24px 70px a55 and
river-read's 0 22px 60px a55 are already token-alpha'd writing-surface
lifts — out of composite scope, left for R4 surfaces.)

**Dock inner content: FLAT** (lead verdict). The panel is the elevated
object; elevation inside it (cards, tabs, lens rows) would stack depth
signals against the "desk" language. Existing surface/border
differentiation stays.

**Toolbar + status strip: FLAT** (lead verdict). They are desk chrome pinned
flush to shell edges; the wireframe contract shows them as part of the
frame, not floating. Hairline borders only (current state).

### Palette input + rows (mechanical completion of the signed R2 input system)

```css
#palette-input {
  border: 1px solid var(--line);        /* was accent-deep — neutral rest border like every input */
  /* rest unchanged: ink-800, r-md, code font, inset a30 */
}
#palette-input:focus-visible {          /* the unified double-glow (R2.3) */
  outline: none; border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent), 0 0 0 4px color-mix(in oklab, var(--accent) 35%, transparent);
}
.palette-row:hover:not(.sel) { background: color-mix(in oklab, var(--accent) 8%, transparent); }
.palette-row:active:not(.sel) { background: color-mix(in oklab, var(--accent) 12%, transparent); }
/* .sel stays: accent 14% wash ✓ already house */
```

### Backdrop unification (sub-perceptual)

Seven backdrop-filter sites at blur 12/12/20/14/10/8. Proposal: one
`--blur-glass: 14px` for panels and pop-overs (Sameer 20→14, banner/popup
12→14, pill 14 stays; the idea-mode 10 / river-read 8 are writing-surface
atmosphere, out of composite scope). Fill tokens stay `--glass` /
`--glass-strong` per surface.

### Dawn shadow family (NEEDS SIGN-OFF — visible change)

108 box-shadow sites render black-alpha on dawn paper today; the ONE
existing dawn shadow override is warm-tinted (welcome-card
rgba(120,95,55,0.28)) — the house already chose warm shadows for paper.
Proposal: a single body.dawn override block remapping the nine
`--shadow-aN` tokens to warm-tinted equivalents (every elevation flips
consistently, one place):

```css
body.dawn {
  --shadow-a60: rgba(97, 76, 43, 0.60);
  --shadow-a55: rgba(97, 76, 43, 0.55);
  --shadow-a50: rgba(97, 76, 43, 0.50);
  --shadow-a45: rgba(97, 76, 43, 0.45);
  --shadow-a40: rgba(97, 76, 43, 0.40);
  --shadow-a35: rgba(97, 76, 43, 0.35);
  --shadow-a30: rgba(97, 76, 43, 0.30);
  --shadow-a18: rgba(97, 76, 43, 0.18);
  --shadow-a12: rgba(97, 76, 43, 0.12);
}
```
(Hue 35° warm brown matching the welcome-card precedent; same alphas, so
shadow WEIGHT is preserved — only the temperature changes.)

## Sign-off decisions

1. **Elevation ladder** — adopt the 6 `--elev-*` tokens; dock/board unify
   onto `--elev-lean-right`; 3 raw literals tokenize. (Flat dock interior,
   flat toolbar/status included.)
2. **Dawn warm shadows** — flip the nine `--shadow-aN` in body.dawn to the
   warm family (all dawn elevations change temperature, none change weight)
   — or keep black alphas on paper.
3. **Backdrop unification** — one 14px glass blur for panels/pop-overs
   (Sameer 20→14, banner/popup 12→14) — or keep per-surface blurs.

(Palette input/rows need no new sign-off: they complete the already-signed
R2 unified-input + state-system decisions.)

## Implementation order (after sign-off)

1. Elevation tokens + raw-literal retirement → tokens commit + sweep + phase5/13.
2. Palette input/rows (R2 completion) → Ctrl+K probe + smoke.
3. Backdrop unification (if signed) → Sameer + banner/popup suites.
4. Dawn warm shadows (if signed) → both-theme probes + full visual suites.
5. Full ladder + pytest certification.
