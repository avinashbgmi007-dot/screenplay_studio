# Design System — Script Doctor & Co-Writer Studio

## Product Context
- **What this is:** A local, privacy-first screenplay analysis and co-writing system running on llama-server
- **Who it's for:** Professional screenwriters who want craft intelligence
- **Space/industry:** Screenplay software (peers: Final Draft, Highland, Arc Studio, Fade In)
- **Project type:** Local web app — analysis dashboard + co-writing tool

## Aesthetic Direction
- **Direction:** Craft Precision — dark glass with surgical intent
- **Decoration level:** Minimal — the glass does the work, no decorative elements
- **Mood:** Serious intelligence instrument. Every surface serves the analysis. The glass says "transparent intelligence." The dark says "serious instrument."
- **Reference sites:** Nocta prototype (docs/design/ux2026/nocta.html)

## Typography
- **Display/Hero:** Instrument Serif — literary authority, headings. Carries the weight of the product's craft knowledge.
- **Body:** DM Sans — clean, precise, readable at small sizes. The workhorse of the interface.
- **UI/Labels:** Same as body (DM Sans)
- **Data/Tables:** JetBrains Mono (tabular-nums) — scene headings, palette items, finding IDs, status chips
- **Script:** Courier Prime — screenplay text itself. Industry-standard monospace for script formatting.
- **Loading:** Google Fonts via `<link>` tags (preconnect + crossorigin)
- **Scale:** Display 32-52px (clamp), Body 15px, Mono 11-13px, Script 13px

## Color
- **Approach:** Restrained — one accent that means "craft intelligence." Color is rare and meaningful.
- **Primary (Accent):** `#7e6bff` — craft intelligence, findings, active states. Violet says "this tool has opinions."
- **Secondary:** `#53c7f0` — links, model status, secondary actions. Cyan complements the violet.
- **Background:** `#09090e` — dark canvas, the stage for the script. Near-black with subtle warmth.
- **Ink:** `#ecebf4` — primary text. Warm white, not cold gray.
- **Muted:** `#8b889c` — secondary text, labels, hints.
- **Surface:** `rgba(255,255,255,.032)` — cards, panels. Barely visible, lets content breathe.
- **Surface2:** `rgba(255,255,255,.06)` — hover states, secondary surfaces.
- **Line:** `rgba(255,255,255,.085)` — borders, dividers. Subtle structure.
- **Glass:** `rgba(17,17,26,.66)` — floating panels, findings sidebar.
- **Glass Strong:** `rgba(19,19,29,.82)` — command palette, modals.
- **On Accent:** `#fff` — text on accent-colored surfaces.
- **Semantic:** success `#34d399`, warning `#fbbf24`, error `#f87171`, info `#60a5fa`
- **Dark mode:** Default (dark glass with subtle radial gradient accents)
- **Dawn mode (light):** bg `#f1ede4`, ink `#26242e`, muted `#75707f`, accent `#6b5ce6`, secondary `#3ab8d8`, surface `rgba(255,255,255,.55)`, glass `rgba(255,255,255,.72)`

## Spacing
- **Base unit:** 4px
- **Density:** Compact — screenwriters work with dense text; the tool respects their attention density
- **Scale:** 2xs(2px) xs(4px) sm(8px) md(16px) lg(24px) xl(32px) 2xl(48px) 3xl(64px)

## Layout
- **Approach:** Grid-disciplined with one creative break. Script column is disciplined (screenplay format demands it). Analysis panels and command palette break from the grid when they appear — they float above, signaling the tool's intelligence talking to you.
- **Grid:** Script column (max 768px centered) + findings panel (340px). Responsive: collapses to single column below 860px.
- **Max content width:** 1200px container
- **Border radius:** sm(4px) md(8px) lg(12px) xl(18px) full(9999px)

## Motion
- **Approach:** Intentional — surface morphing via View Transitions, word streaming during analysis, cursor spotlight on findings. No decorative animation.
- **Easing:** enter(ease-out) exit(ease-in) move(spring)
- **Duration:** micro(50-100ms) short(150-250ms) medium(250-400ms) long(400-700ms)
- **Key patterns:**
  - Surface morphing: desk → cowrite → feedback → ideas via View Transitions (one continuous thought)
  - Word streaming: text appears as the analyzer processes (tool feels alive)
  - Cursor spotlight: highlights where craft insight connects to text
  - Command palette: blur backdrop + spring entrance

## Grain Texture
Subtle SVG fractal noise at 4% opacity over the entire viewport. Adds material depth without distraction. Disabled in dawn mode (replaced with multiply blend).

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-01 | Initial design system created | Created by /design-consultation based on product context, competitive research, and three prototype evaluations (Nocta, Lumen, Beatwall) |
| 2026-09-01 | Nocta over Lumen as primary architecture | Command-driven dark glass serves craft intelligence better than atmospheric depth. Lumen's aurora blobs compete with analysis for attention. |
| 2026-09-01 | Violet accent #7e6bff | Every screenplay tool uses neutral grays or corporate blue. Violet says "this tool has opinions" — deep thought, not spreadsheet cells. |
| 2026-09-01 | ⌘K palette as primary navigation | Power users fly. The palette IS the product's personality — craft knowledge is the first thing you see when you reach for navigation. |
| 2026-09-01 | Surface morphing over page navigation | Tool feels like one continuous thought, not separate screens. The "fluid thinking" signal. |
| 2026-09-01 | Instrument Serif for display | Literary authority without being stuffy. The italic carries the product's craft knowledge visually. |
