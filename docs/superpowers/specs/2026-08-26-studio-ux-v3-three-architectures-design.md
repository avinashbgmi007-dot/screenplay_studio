# Studio UX v3 — Three-Architecture Redesign (Design Spec)

**Date:** 2026-08-26
**Status:** Approved (plan-mode review) · implementation in progress
**Supersedes:** Phase A of `docs/superpowers/plans/2026-08-26-studio-ux-v2-redesign.md` (six-direction reskins). That plan's feature inventory and R1–R5 requirements carry forward verbatim; Phase B (winner migration into the Flask webapp) remains future work pending a winner.

## Problem

The six v1 directions (`docs/design/ux2026/archive-v1/`) shared `base.css` components (~60% identical) and one shell contract: topbar → segmented room tabs → rails → script page. Only color/font tokens differed. Reviewer verdict (user, 2026-08-26): none felt intuitive, unique, or modern — "the same with just a color palette change."

Root cause: identity was applied at the **token layer**, but product identity lives in **layout architecture + navigation model + signature interaction + motion personality**.

## User decisions (calibration round)

| Question | Answer |
|---|---|
| Taste target | Linear/Raycast **and** visionOS glass **and** Figma/Framer spatial |
| Scope | 3 brand-new directions, each architecturally different |
| Motion level | Alive by default — springs, staggers, ambient graphics, micro-interactions |

The three taste picks map 1:1 onto the three directions, each anchored in a different interaction architecture so no two can converge.

## The three directions

### 1 · Nocta — command-driven dark glass
- **Architecture:** single focused surface. No tabs/rails chrome. ⌘K spotlight palette is primary navigation (rooms, scenes, Sameer prompts, exports, settings) with recent commands. Surfaces morph in place via View Transitions API (fade fallback).
- **Look:** near-black glass (`#09090e`), electric indigo→cyan accents, pointer-tracked radial spotlight, mono micro-labels, serif italic display moments.
- **Signature:** the palette IS the app; word-level fade streaming replaces blinking cursors.
- **Files:** `docs/design/ux2026/nocta.html`

### 2 · Lumen — glass depth over ambient light
- **Architecture:** floating frosted panels stacked in z-depth over an animated aurora mesh (4 drifting blobs + grain). Bottom dock with cursor-magnification navigates rooms; co-write summons as a right side panel with spring slide; parallax follows the pointer.
- **Look:** deep space base, high-blur glass (≤3 stacked backdrop-filters for perf), luminous edges, warm violet accent. Dawn toggle swaps the entire token set to daylight pastels.
- **Signature:** analysis runs as a light refraction sweep across the verdict card while an SVG ring counts up; waiting reads as luminous process.
- **Files:** `docs/design/ux2026/lumen.html`

### 3 · Beatwall — spatial scene canvas
- **Architecture:** zoomable/pannable board (camera transform, wheel-zoom-to-cursor, spring glide). Scene cards sit on dashed act lanes and are draggable with spring settle; findings pin near their scenes connected by dashed SVG curves; dragging a finding into the Fix queue lane enqueues it. Minimap jumps; list-view toggle is the keyboard-first twin of the wall; reader opens per-scene in a modal.
- **Look:** precision-tool light theme (`#f4f6f9`, dot grid, graphite ink), electric blue halos; dark-wall toggle.
- **Signature:** structure you can grab — upload drops cards onto the wall and the camera flies to the coverage card.
- **Accessibility guardrails:** keyboard zoom (+/−/0), arrow-key pan, Tab-focusable cards with Enter→reader, list view twin.
- **Files:** `docs/design/ux2026/beatwall.html`

## Shared toolkit (the only common code) — `docs/design/ux2026/shared/`

- `kit.css` — token reset + primitives: buttons (44px targets), inputs, segmented controls, popovers/modals/banners/toasts, severity system, tooltips (hover **and** focus reveal).
- `motion.css` — overshoot spring via `linear()` (cubic-bezier fallback), reveal/stagger utilities, word-stream keyframes, view-transition wrappers, ambient drift keyframes, global reduced-motion clamp.
- `graphics.css` — feTurbulence grain overlay, aurora blob scaffold, score-ring helpers, cursor-spotlight host, dot-grid helper.
- `kit.js` — inline SVG icon sprite (~40 icons, zero external requests); engines: reveal observer, count-up, popover/modal dismissal (R2), command-palette (filter/groups/recents/arrows), chat demo (R3 chip lifecycle + R4 autogrow + grounded footer), word streaming, toasts, mm:ss ticker.

Sharing target ≤40% — intentionally lower than v1's ~60% so pages diverge hard. Pages own all layout CSS and page-specific JS inline.

## Product requirements carried verbatim

R1 post-upload lands Feedback-ready · R2 click-outside/Esc dismissal everywhere · R3 explore-chip lifecycle (visible → rail/orb after first send → hover/focus reveals → restore) · R4 composer ≥4 lines autogrowing to ~40vh, Enter sends · R5 Co-write & Feedback first-class, report as reading surface, Fix Queue peer tab. Full feature inventory per `archive-v1` plan §Feature Inventory is represented per page (data-fid hooks retained): shell, welcome/dropzone, project bar, structure surfaces, script pane (search/focus/reader/undo-redo/premise/exports/draft bar/diff), idea phase, co-write (lenses/partner/reset/history/quote-card/streaming), feedback (language select, pipeline progress w/ stage hover, report+queue tabs, statuses, export .md, empty/loading/error states), views (beatboard native to Beatwall; compare & revision desk as modals/drawers elsewhere), modals (settings/rewrite/fork/Sam's notes), status strip.

## Constraints kept

Zero external requests (system fonts, inline SVG/data-URIs only) · no build step, vanilla HTML/CSS/JS · prefers-reduced-motion collapses all animation · :focus-visible rings everywhere · touch targets ≥44px on primary controls · Windows CRLF care · API contracts untouched (Phase B concern).

## Verification

- Each page exercised in preview against the R1–R5 checklist above; console must stay clean.
- Reduced-motion pass: animation collapses to fades, flows still complete.
- Contrast spot-checks on accent-on-surface text pairs (≥4.5:1).
- Keyboard-only pass: ⌘K palette, Esc dismissal, tab order per page.
- Static mocks — no pytest/typecheck applies; Playwright suites remain Phase B scope.

## Risks / tradeoffs

- Three architectures ≈ heavier review than six reskins but winner-only migration keeps Phase B cost at one architecture.
- View Transitions API is Chromium/Safari-only → Nocta falls back to instant swaps (CSS morphs carry Lumen/Beatwall).
- `backdrop-filter` GPU cost → capped stacked layers; grain is static.
- Spatial UIs can trap keyboard users → Beatwall ships zoom keys, arrow panning, focusable cards, and a full list-view twin from day one.

## File operations performed

```
docs/design/ux2026/index.html            ← rewritten hub (three previews + review guide)
docs/design/ux2026/{nocta,lumen,beatwall}.html
docs/design/ux2026/shared/{kit.css,motion.css,graphics.css,kit.js}
docs/design/ux2026/archive-v1/           ← six v1 pages + old shared/, links fixed
```
