# Spec: 6 Radically Distinct UI/UX Redesign Previews

Date: 2026-08-27
Status: Approved

## 1. Purpose & Goals
Provide 6 completely unique structural UI/UX paradigms and interaction models for Screenplay Studio. Instead of superficial color swaps, each design features a fundamentally different spatial layout, navigation model, and information architecture engineered around:
- **Writer Perspective:** Focus, manuscript flow, unobtrusive AI tools, and line-anchored notes.
- **Consultant Perspective:** Clear diagnostics, severity-weighted finding queues, setup/payoff ledgers, and scene jump-links.
- **Idea & Brainstorming Perspective:** Blank canvas idea incubator, lazy partner summoning, and clean context isolation.
- **Intuitive Modern UI/UX:** Responsive growing composers, click-outside dismissals, and smart collapsible explore chips.

## 2. Deliverables
All files live in `screenplay_studio/webapp/preview-redesigns/`:
- `index.html` — Master comparison gallery with live embedded view & switcher.
- `noir.html` — **① The Manuscript Stage** (Full-bleed script sanctuary, zero persistent sidebars, summoned floating partner sheets).
- `paper.html` — **② The 3-Column Editing Suite** (Left Scene Navigator \| Center Script with line flags \| Right Co-Writer/Doctor Room).
- `brutal.html` — **③ The Corkboard & Bottom Dock** (Visual scene card grid desk, collapsible bottom chat dock that expands on input).
- `swiss.html` — **④ The Split Workbench** (Dual-pane split view with top segmented control for script + AI room side-by-side).
- `terminal.html` — **⑤ The Command Palette Desk** (Distraction-free monospace editor, zero visible chrome, keyboard-driven `⌘K` spotlight palette).
- `organic.html` — **⑥ The Magazine & Report Studio** (Feedback report is the hero reading view with embedded script excerpts and right-rail Sameer Study).

## 3. Shared Behavioral Contract (Mandatory Across All 6)
Every mockup implements the following interactive behaviors:
1. **Script-First Landing:** Opening a script lands directly on the manuscript pages.
2. **Click-Outside Dismissal:** Any summoned modal, drawer, or sheet dismisses on clicking outside or pressing `Esc`.
3. **Smart Collapsible Explore Chips:** Horizontal chips on open → collapse to vertical icon stack on first text input → hover reveals individual labels.
4. **Auto-Growing Multi-Line Composer:** Textarea smoothly auto-expands from 1 line (~42px) to 6 lines (~170px) with visible scroll.
5. **Primary Dedicated Rooms:** Distinct first-class views for Co-Writer (Sameer + Writer Memory) and Feedback Report (long-form document with score, verdict, finding cards, and pacing bars).

## 4. Technical Constraints
- Single-file standalone HTML/CSS/JS for each preview.
- No build steps or external bundlers required.
- Accessible fallbacks for fonts & styles.
- Support `prefers-reduced-motion`.
- Responsive layout down to 1024px width with zero horizontal overflow at 1440×900.

## 5. Verification Plan
- Verify HTTP 200 serving for all 7 files via `screenplay_studio.webapp_server`.
- Test each of the 5 interactive behaviors in all 6 files.
- Verify that every design is structurally and spatially distinct.
