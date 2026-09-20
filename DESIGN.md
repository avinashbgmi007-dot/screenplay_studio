---
# gstack: design-md-format=spec
name: Script Doctor Studio
description: A lit instrument in a dark room — warm paper under a single gold key, on an almost-black void.
colors:
  primary: "#e8c56a"
  on-primary: "#1a140d"
  surface: "#20160f"
  surface-raised: "#1a120c"
  void: "#150f0a"
  text: "#f2e8da"
  text-muted: "#b0a28c"
  text-faint: "#8f7e58"
  accent-consult: "#7ad0e8"
  paper: "#e8d5b5"
  paper-ink: "#2b2013"
  paper-muted: "#5c4c38"
  success: "#7fc98a"
  warning: "#e8a24f"
  error: "#c8503a"
typography:
  display:
    fontFamily: Instrument Serif
    fontWeight: 400
    fontSize: clamp(2rem, 4vw, 3.25rem)
    letterSpacing: -0.01em
  body:
    fontFamily: DM Sans
    fontSize: 1rem
    lineHeight: 1.5
  label:
    fontFamily: IBM Plex Mono
    fontSize: 0.75rem
    letterSpacing: 0.04em
  mono:
    fontFamily: IBM Plex Mono
    fontFeature: tnum
  script:
    fontFamily: Courier Prime
    fontSize: 0.8125rem
    lineHeight: 1.4
rounded:
  sm: 10px
  md: 14px
  lg: 18px
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  2xl: 48px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.md}"
  button-secondary:
    textColor: "{colors.text}"
    borderColor: "{colors.text-faint}"
    rounded: "{rounded.md}"
  input:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.text-faint}"
    rounded: "{colors.sm}"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.md}"
  nav-link:
    textColor: "{colors.text-muted}"
---

# Script Doctor Studio

## Overview

**Creative North Star:** A lit instrument in a dark room. The manuscript is the only
brightly lit object; everything the product adds (analysis, chat, findings) is chrome
around the page, never a takeover. A writer works here for hours, at night, alone.

**Product context:** Local, privacy-first screenplay analysis and co-writing. Users are
aspiring and working screenwriters doing long-form craft work on their own machine.
Category peers: Final Draft, Arc Studio, Highland, Fade In. Project type: local web app
(desktop browser), an analysis dashboard wrapped around a manuscript editor.

**Mode per surface:** Operate (the desk and all panels) · Read (the manuscript) ·
Experience (the idea room, the dawn meter).

**Key characteristics**
- Warm paper on a near-black void; one gold key light; the page always the brightest.
- One accent means attention. Gold is never decoration.
- Severity is never encoded by color alone.
- Two registers, night and dawn, sharing one geometry and one severity language.
- Zero external requests. Fonts are self-hosted woff2.

## Colors

**Strategy:** Restrained, committed. One warm key (gold) carries attention and progress;
a single cool accent (cyan) is re-pinned per room so the consultant's desk reads
differently from the co-writer's; everything else is a warm neutral that derives from the
void, not from a gray ramp.

**Light or dark:** Both, paired. The use scene is a writer at a desk at night, so night is
the default and dawn is the daylight edition of the same room (the same conic key geometry,
re-tuned alpha). Neither is a mere lightness inversion of the other.

`{colors.primary}` (gold) signals interaction and progress only: the active room toggle, the
primary action, the dawn meter, the resolved-finding fill. `{colors.accent-consult}` (cyan)
is the identity of the consultant room and is applied through a `data-room` swap, so it
never appears as a competing warm signal. Severity uses `{colors.error}`,
`{colors.warning}`, and `{colors.success}` **plus** a shape cue (a jagged rim) and a text
label, so a finding stays readable for colorblind users and in both registers. Surfaces
step up by warmth and tint (`{colors.void}` → `{colors.surface-raised}` →
`{colors.surface}`), not by adding shadow, so hierarchy survives the light theme.

## Typography

The faces come from the writing world, not from a UI kit. A literary serif for display,
a quiet grotesk for chrome, a mono for data and labels, and the industry's screenplay face
for the pages themselves. All are bundled as `webapp/fonts/*.woff2` with declared
`@font-face` rules; the page makes no external font request.

- **Display — Instrument Serif.** Titles and the few moments that should feel authored.
  Used with restraint; it is not a body face.
- **Body/UI — DM Sans.** The workhorse of an Operate surface: dense, precise at small
  sizes. (DM Sans is on the overused-as-display list; here it is body/UI on an Operate
  surface, which is exactly the permitted exception, and it is not used as a display voice.)
- **Label/data — IBM Plex Mono** with tabular figures for scene headings, chips,
  timestamps, and finding IDs.
- **Script — Courier Prime.** The pages. Screenwriters read monospace pages; this is the
  category's paper and deviating would read as broken. (Not Courier New, which is banned.)
- **Hand — Caveat.** The writer's own margin notes only.

Scale: display clamps 2–3.25rem; body 1rem/1.5; label 0.75rem; script 0.8125rem. Headings
differ from body by more than a weight.

## Layout

The script column is disciplined and never shrinks below half the desk; it is centered at
a 700px measure. Analysis panels break the grid when summoned (the dock, the board) and
recede when not, so the page keeps its width. Breakpoints: 900px (panels collapse to
overlays), 600px (single column; the manuscript stays readable). Spacing runs on a 4px base
with a compact rhythm, because the content is dense text and the tool should respect the
writer's attention, not pad it.

## Elevation & Depth

Depth is offset and soft: panels float above the void with a real shadow and a warm rim,
and paper sits above chrome. There are no zero-offset colored halos on components. The one
large ambient treatment is the room's key light, which is a lamp, not a component effect —
see Motion.

## Shapes

Radius hierarchy: inputs `{rounded.sm}`, cards and panels `{rounded.md}`, large surfaces
`{rounded.lg}`, pills `{rounded.full}`. Nested inner radius = outer radius − gap. Severity
dots deliberately break the language with a 1px square rim, so a square edge always means
"severity", never "button".

## Components

- **button-primary** — gold fill, `{colors.on-primary}` text. Hover brightens the fill;
  focus-visible draws a 2px gold ring; disabled drops to 0.55 opacity.
- **button-secondary** — ghost with a `{colors.text-faint}` border; hover raises the
  surface tint. Never used for the primary action.
- **input** — `{colors.surface}` well with a visible label above (never placeholder-as-label);
  focus-visible ring matches the accent; disabled is read-only styling, not opacity soup.
- **card / panel** — `{colors.surface}` with a warm rim; the manuscript page is
  `{colors.paper}` and is always the highest-luminance element on screen.
- **nav-link** — muted by default, gold on active; the active room is also marked by the
  room's accent swap, so position is never conveyed by color alone.

## Do's and Don'ts

- **Do** keep the manuscript the brightest object on screen in every state.
- **Do** carry severity with rim + mass + label, never hue alone.
- **Do** express attention with gold and nothing else; if two things glow, neither means anything.
- **Do** keep motion one-shot and short; the lamp is static.
- **Do** read tokens from the CSS custom properties, never hardcode a hex in a component.
- **Don't** reintroduce the rejected Nocta direction: violet/indigo gradients are the one
  look this product deliberately abandoned, and they are the most recognizable AI-slop palette.
- **Don't** add a second ambient glow or a decorative halo behind content.
- **Don't** use gradient buttons, uniform bubbly radii, or cards nested in cards.
- **Don't** put the co-writer's cyan and the desk's gold in the same room as equals; the
  room swap is the contract.
- **Don't** let an analysis panel take the manuscript's width.

## Motion

- **Approach:** intentional. Motion communicates state change and spatial continuity, never mood.
- **Easing:** enter (ease-out), exit (ease-in), move (ease-in-out).
- **Duration:** micro 50–100ms, short 150–250ms, medium 250–400ms, long 400–700ms. One-shot
  animations sit in the 120–280ms band.
- **The one authored moment:** the room's key light — a static volumetric gold key over the
  void. It is the product's signature and it does not animate. Progress is the only thing
  allowed to fill or pulse (analysis bar, dawn meter), because progress is information.
- `prefers-reduced-motion: reduce` collapses every animation to instant.

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-01 | Initial design system created (Nocta — violet #7e6bff) | Created by /design-consultation from three prototype evaluations; **superseded** |
| 2026-09-12 | Tungsten system frozen (gold #e8c56a on a warm void) | Nocta's violet gradients read as a generic AI palette; the gold key light makes the room a room. Supersedes the 2026-09-01 direction. |
| 2026-09-12 | Severity never encoded by color alone | Accessibility (colorblind, both registers) plus a distinctive instrument language (jagged rim + mass + label) |
| 2026-09-20 | DESIGN.md reconciled to the shipped Tungsten system | This document previously described the rejected Nocta direction and Google-Fonts loading, which would have violated the zero-external-requests promise |
| 2026-09-20 | Fonts confirmed self-hosted | Instrument Serif, DM Sans, JetBrains Mono, Source Serif 4 are all bundled woff2; no external font request ships |
