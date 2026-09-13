# R2 Primitives — design spec

Status: **IMPLEMENTED 2026-09-13** (user signed all four decisions as
recommended 2026-09-12; commits 86a8927 tokens + fd369c5 families).
Certification: full ladder — all 22 non-preview suites green, 0 failures
(preview_next + preview_redesigns remain the documented pre-existing
static-page pair). Permanent gate added: `_r2_a11y_guard.py` (flags any new
bare `outline: none` suppressor).
Date: 2026-09-12. Author: session agent, with consults (primitive-designer for
the CSS recipes, primitive-census for the inventory evidence).

## What R2 is

Per `docs/REDESIGN_MASTER_PLAN.md` (phasing table, R2 row): buttons, inputs,
chips, cards, selects, scrollbars — single components styled once. Gates:
`ui_batch` + `smoke` (plus the full ladder at the end of the phase).

## Current state (census evidence, 2026-09-12)

### Radius histogram (lead-verified, independent re-count)

All `border-radius` literals in style.css:

| value | count | what it is |
|---|---|---|
| 999px | 33 | true pills (chips, badges, pills, toggle tracks) |
| 4px | 26 | small squares (scrollbar thumbs, tiny tiles) |
| 8px | 18 | dock cards, inputs-family, medium chips |
| 6px | 18 | dock tabs, selects, small buttons |
| 10px | 13 | btn-paper family, cards, send button |
| 3px | 10 | hairline corners (kbd, mini squares) |
| 2px | 7 | micro corners (badge ticks, mono labels) |
| 7px | 4 | odd values (near-fold artifacts) |
| 5px | 3 | odd values |
| 9px | 2 | odd values |
| 99px | 2 | true pills mis-typed (sp pills, palette bar) → fold to 999px, pixel-identical |
| 12px | 2 | message cards (.compare-to-label, .sp-msg) |
| 16px | 1 | idea editor (.idea-content) |
| 22px 22px 22px 6px | 1 | deliberate asymmetric speech-bubble tail (river-read .scene-page) — EXEMPT, single-use expressive shape |
| 14px 14px 0 0 | 1 | mobile sheet top corners (@media L6143) — maps to legacy --radius |
| token uses | 23 | var(--radius)×4 (14px), var(--radius-sm)×19 (10px) |

### Focus

- Exactly 3 `:focus-visible` rules in the whole stylesheet: global ring
  (`:focus-visible` L482 — 2px accent @65% outline, offset 2), plus
  `#script-search:focus` (border+glow, L1355) and `.sp-composer
  textarea:focus-visible` (border swap, L5118) — the a11y passes (1-12)
  verified keyboard operability, but per-primitive focus *treatment* is not
  systematic.
- 15 `outline: none` declarations total. 13 are compensated (paired
  border+glow `:focus` rules). **2 were bare suppressors** — `.idea-rename-input`
  (L3083, WCAG 2.4.7 violation, equal specificity + later source than the
  global ring → keyboard focus ring invisible) and one other idea-mode
  pattern. `.idea-rename-input` is now FIXED (house border+glow rule added
  2026-09-12, uncommitted), with ideas suites running as the gate.
- `.idea-title-input` (L3006) documents the house pattern: swap ring for
  border + 2px glow (equally visible cue per WCAG 2.4.7).

### States

~31 hover/disabled rules with three competing recipes: `filter: brightness()`,
`color-mix` backgrounds, border swaps — no single system.

### Scrollbars

10px thin webkit scrollbars, one grouped rule (L3209–3224) shared across 11
surfaces.

### Selects

7 native `<select>`s (persona, mode, draft, pb-filter, report-lang,
compare-from, +1) with inconsistent radius treatments (6px, 8px, 10px literals).

## The four sign-off decisions

1. **Radius ladder** — which named steps, which current values each absorbs,
   and the fate of the legacy 14/10 tokens.
2. **Focus treatment** — one unified `:focus-visible` recipe satisfying
   WCAG 2.4.7 + 1.4.11 (3:1 non-text contrast) in BOTH night and dawn.
3. **State system** — one hover/active/disabled/focus-visible recipe for
   buttons/chips/tabs (200ms house motion; disabled stays keyboard-reachable
   per the a11y program).
4. **Selects + scrollbars** — native select styling matching inputs (no
   external assets; inline SVG data-URI caret allowed); slim scrollbar recipe.

## Consult recommendations (primitive-designer — lead-critiqued)

> Designer's recipes below, with the lead's two corrections applied: (a) the
> `:where()` wrapper alone does NOT neutralize equal-specificity later-source
> `outline:none` suppressors like the pre-fix `.idea-rename-input` — a
> remediation list is required alongside; (b) census count corrected from
> "10 distinct values" to the 13-value histogram above (99px×2, 12px×2,
> 16px×1, 22px×1, 14px×1 were missed).

### 1. Radius ladder

```css
--r-pill: 999px;   /* pills, badges, toggles — absorbs 999px×33 + 99px×2 */
--r-lg: 12px;      /* large cards, modals, composer surfaces — absorbs 12px×2,
                     14px legacy (--radius), 16px idea editor (fold down) */
--r-md: 8px;       /* buttons, inputs, selects, dock cards — absorbs 8px×18,
                     10px×13 + legacy --radius-sm, + 6px×18 + 7px×4 + 9px×2 (fold up) */
--r-sm: 4px;       /* small chips, thumbnails, scrollbar thumbs — absorbs 4px×26, 3px×10, 5px×3 (fold down) */
--r-xs: 2px;       /* micro corners, kbd — absorbs 2px×7 */
```

Odd-value folding rule: nearest step (5→4, 7→8, 9→8) — max 1px delta,
sub-perceptual, same principle as the R1 spacing odd-fold. Directional
shapes keep their geometry with tokens: `10px 0 0 10px` → `var(--r-md) 0 0
var(--r-md)` (×5), `3px 0 0 3px` → `var(--r-sm) 0 0 var(--r-sm)`,
`14px 14px 0 0` → `var(--r-lg) var(--r-lg) 0 0`.

Exemptions: river-read speech-bubble tail (22/22/22/6 asymmetric, single-use
expressive), 50%/`::before` circles via `border-radius:50%` (not a "value",
it's a shape operator).

### 2. Focus recipe

```css
:focus-visible {
  outline: 2px solid color-mix(in oklab, var(--accent) 75%, transparent);
  outline-offset: 2px;
}
```
(Lead's correction: the designer's `border-radius: inherit` is dropped —
it would set the focused element's radius to its PARENT's radius (a pill
chip in a 12px card would visibly snap square-ish on focus). Outlines
already follow the element's own corner curve natively in Chromium 94+,
Firefox, Safari.)

Zero specificity via `:where()` so component rules can extend:
```css
:where(input, textarea, select, [contenteditable]):focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px color-mix(in oklab, var(--accent) 100%, transparent),
              0 0 0 4px color-mix(in oklab, var(--accent) 35%, transparent);
}
```
(Lead's correction: the second layer's token reference `--radius-glow` is
not defined in style.css — replaced with the house `var(--accent)` mix at
35%, matching the layer stack the app already uses in --glow tokens.)

**Lead's contrast correction (WCAG 1.4.11)**: the designer proposed 65% —
the same alpha as today's live global ring (L482). Composited over the
night shell `#09090e`, 65% violet = effective `rgb(65,55,144)` →
**2.74:1, below the 3:1 bar**. At **75%**: night = effective `rgb(97,83,195)`
→ **3.32:1 ✓**; dawn = effective `#867ace` on `#f1ede4` → **3.15:1 ✓**.
The solid inner layer of the input recipe passes with headroom (5.08:1
night, 4.93:1 dawn). Note: adopting 75% UPGRADES the live global
ring — a subtle visible delta, deliberate and disclosed.

**Lead's remediation add-on**: the bare `outline:none` suppressors must be
converted to compensated (border+glow) or removed — the `:where()` recipe
doesn't outrank them (both 0,1,0; suppressors sit later in source). The
`.idea-rename-input` fix already landed; remaining idea-mode pattern
audited in implementation step 1.

### 3. State system

```css
/* on-accent controls (accent-filled buttons, CTAs) */
.btn-primary:hover  { filter: brightness(1.1); }
.btn-primary:active { filter: brightness(0.9); transform: scale(0.98); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
/* unchanged body motion: transition: background 200ms ease, ... */

/* on-surface controls (ghost/secondary) */
.btn-secondary:hover { background: color-mix(in oklab, var(--accent) 8%, transparent); }
.btn-secondary:active { background: color-mix(in oklab, var(--accent) 12%, transparent); }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; color: var(--text-faint); }
/* 200ms house motion: transition: background 200ms ease, filter 200ms ease;
   per-house color-mix rule; works across night/dawn via tokens */
```

### 4. Selects + scrollbars

```css
select {
  appearance: none;
  appearance: -webkit-appearance: none;
  background: var(--surface) url("data:image/svg+xml,...") no-repeat right var(--sp-4) center / 8px 4px;
  padding-right: calc(var(--sp-6) + 8px);
  border-radius: var(--r-md);
}
select:focus-visible { /* the unified input recipe */ }
select:disabled { opacity: 0.5; cursor: not-allowed; }

::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { border-radius: var(--r-pill); background: color-min(in oklab, var(--accent) 30%, transparent); }
::-webkit-scrollbar-thumb:hover { background: color-mix(in oklab, var(--spec accent) 45%, transparent); }

```

Lead's critique on §4: two typos in the designer's draft preserved raw and
flagged — `color-mays` and `color-min`/`var(--spec accent)` are not valid CSS;
the implementation will use the correct `color-mix(in oklab, var(--accent) …)`
form. All scrollbar hover states work in both themes via tokens. The SVG
data-URI caret must be neutral (currentColor impossible in url() — use a
gray caret for both themes, or the app's --text-faint hex).

## Inventory evidence (primitive-census)

Report received 2026-09-12 (8 sections, line numbers, selectors, values).
Key sections used above: buttons (L2026-2108, ~40 button-family rules across
btn-paper / dock-lens-tab / icon / CTA / sidebar-footer families), chips
(~.sam-notes-chip L2755, status pills, tags), inputs (L833, L1355, L2237,
L2617, L4308 — five input families, five focus recipes), selects (7 native,
L634, L967, L2212, L3206, L3543, L4198, L4672), cards (glass cards
L1026-1093, dock cards L3225+, board cards), scrollbars (L3209-3224), states
(~31 rules, three competing recipes), radius histogram (above). Full census
with exact line numbers available in session log.

## Implementation order (after sign-off)

1. Tokens: `--r-*` ladder + focus-ring token → one commit (pixel-mechanical,
   sweep gate).
2. Buttons family → one commit (ui_batch + smoke).
3. Inputs + selects → one commit.
4. Chips + cards → one commit.
5. Scrollbars → one commit.
6. Full-ladder certification at phase end.

Each commit: cache bump, brace-balance gate, def/use sweep, relevant suites,
and a resolution probe (the house discipline established in R1).
