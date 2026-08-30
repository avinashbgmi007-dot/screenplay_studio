# Six Worlds UIUX (v4) — Design Spec

**Date:** 2026-08-30
**Status:** Approved design (Sections 1–5 approved interactively; this document is the record)
**Scope:** Static UIUX redesign previews — NOT a change to the live app
**Follow-on:** Winner porting is a separate future project

---

## 1. Problem — the five asks that drove this redesign

Feedback from live use of the current app (Spark Wall reskin, 2026-08-29):

1. Script is in focus by default (good), but the analysis — the very reason a writer uploads a
   script — lives as a tab inside a small summoned 380px drawer on the right. The report is a
   minor pane, not the major surface it deserves to be.
2. Click-outside dismissal works in the idea room only; Sameer/doctor drawers close only via ✕
   and Esc. The idea-room behavior should apply everywhere.
3. Explore chips should behave everywhere the way they do in the idea room: visible until first
   input, then collapse to a vertical icon rail with hover-reveal labels, restoring on clear.
4. The chat composer feels too small: it starts at one row inside a narrow drawer.
5. **The headline ask:** co-write and feedback must become two main, separate rooms — and if
   required, the entire UIUX should be redesigned. Six brand-new, unique, modern designs as
   static pages to review and finalize.

## 2. Decisions (made interactively, 2026-08-30)

| # | Decision | Choice |
|---|---|---|
| D1 | Relation to prior preview rounds (v1/v2/v3, Spark Wall hybrid) | **Fresh slate** — 6 completely new designs; old previews untouched |
| D2 | Spatial model | **3 full-screen rooms** — Script Desk / Co-write Room / Feedback Room; one persistent switcher; each room owns the viewport; nothing primary is a summoned pane |
| D3 | Variation across the six | **Structure AND identity both unique** per design |
| D4 | Aesthetic spread | **Full spread** — dark cinematic, light editorial/paper, at least one wildcard |
| D5 | Deliverable shape | **Approach A** — six full-journey interactive worlds + gallery index |
| D6 | Skill placement (from gstack skill review) | `design-shotgun` (PNG mockups) rejected as vehicle — cannot demonstrate interaction contracts. `design-review` adopted as the **quality gate after build**. `design-consultation` adopted **post-finalization** to codify the winner into `DESIGN.md` |

## 3. Scope & Deliverable

Six self-contained static HTML pages + one gallery index in a **new folder**:

```
screenplay_studio/webapp/preview-next/
├── index.html          ← gallery: flip between the six worlds
├── ledger.html         ← The Ledger        (light editorial)
├── midnight.html       ← The Midnight Desk (dark cinematic)
├── screening.html      ← The Screening Room (dark cinema)
├── quarterly.html      ← The Quarterly     (light magazine)
├── terminal.html       ← The Terminal      (wildcard, monospace)
└── studio-wall.html    ← The Studio Wall   (warm craft wildcard)
```

- The existing Flask server serves any path under `webapp/` via its catch-all
  `<path:filename>` route (`webapp_server.py:129-135`) — **zero server changes needed**.
  Review URL: `/preview-next/index.html`.
- Each page: single HTML file, inline CSS/JS, **zero external dependencies** (no CDN fonts,
  no libraries) — offline-safe, consistent with the privacy-first product.
- Demo-level interactivity: rooms switch, chips collapse, composer grows, click-outside and
  Esc dismiss floating surfaces, cross-room bridges work. Nothing talks to a backend.
- Old `preview-redesigns/` folder stays untouched as history.
- **Gallery** (`index.html`): one card per world — world name, a small identity swatch
  (its palette), one-line metaphor description, and an open link. v2-gallery precedent.

### 3a. Shared demo payload (same content across ALL six worlds)

Same content, different presentation — the comparison isolates design, not data:

- **Script:** a 4-scene sample, mixed English/Tenglish, in the project's voice (characters,
  headings, dialogue with Tenglish lines), including one transition and one parenthetical.
- **Findings:** 9 findings — 3 high / 4 medium / 2 low — with verbatim evidence quotes,
  category labels, verification badges (verified on most, one unverified), scene refs.
- **Fix queue:** derived from the same findings with severities + verbs
  (locate / discuss / rewrite / dismiss).
- **Coverage:** logline (one workable sentence), genre, synopsis paragraph, recommendation.
- **Pacing:** per-scene pace rows with one dragging scene flagged.
- **Character dials:** 4 characters × 5 bipolar trait poles (1–10) with scene refs.
- **Setup/payoff ledger:** ~4 entries including 2 dangling/abandoned.
- **Character reads:** 2 short writer's-mirror reads.

### 3b. Honesty of static scope

Features are **placed and demo-visible, not functional**. The translator shows a translated
panel; the mic chip exists; memory shows a filled card — but nothing translates, dictates, or
recalls live. The review bar (see §7) is demo-only chrome. What is being finalized is layout,
placeholder positions, interaction patterns, and identity.

## 4. The v4 Contract — 12 points, binding on every world

Every world is audited against this checklist before review (see §8).

1. **Three full-screen rooms** — Script Desk / Co-write Room / Feedback Room — one persistent
   switcher in the world's own idiom; each room owns the viewport; nothing primary is a
   summoned pane. The **Script Desk is the default landing** when a project opens.
2. **Feedback as the hero** — the report is the room. Must include:
   - **Lifecycle states:** empty (not analyzed → Run Analysis CTA), running (progress with
     pipeline stage names), complete (the full report). All three designed and reachable via
     the review bar.
   - Findings with severity marks + verification badges + verbatim evidence.
   - Fix queue with its verbs: locate / discuss / rewrite / dismiss (dismiss demo-state).
   - Coverage (logline / genre / synopsis / recommendation), pacing chart, character dials,
     setup/payoff ledger.
   - Analysis controls at Secondary tier: re-parse, report language, retry-failed,
     export/backup.
3. **Script in focus by default** — opening a project always lands on the Script Desk.
4. **Click-outside + Esc dismiss every floating surface** (modals, note cards, palette,
   summons). Esc cascade: topmost floating surface first. Rooms are never floats.
5. **Chips tuck away in every chat surface** — visible until first input → collapse to a
   vertical icon rail → hover reveals one label at a time → clearing the input restores.
   Required in the idea room; a world may choose whether the project Co-write room has chips
   at all, but any chips that exist obey this behavior everywhere.
6. **Composer grows with you** — starts at one row, expands multi-line, in every chat surface.
7. **Full journey per page** — six required screens: shelf → upload moment → script desk →
   co-write room → feedback room → idea room.
8. **Everything placed by importance** — the tier inventory in §6 is binding: P1 (visible or
   one click from its home room), P2 (≤2 clicks), REP (demo state shown somewhere).
9. **Modern & intuitive — quality gates (verifiable):**
   - WCAG AA contrast: 4.5:1 body text, 3:1 large text and UI components.
   - Body text ≥16px; captions/labels ≥12px.
   - Visible `:focus-visible` rings; hover + focus states on everything clickable.
   - Touch targets ≥44px.
   - SVG icons only — **no emoji-as-icons**.
   - `prefers-reduced-motion` respected.
   - **Deliberate named font stacks per role** (e.g. `Georgia, 'Iowan Old Style', serif`).
     A bare `system-ui`/`-apple-system` default is a contract fail.
   - AI-slop blacklist: no purple/violet gradient defaults, no 3-column icon-in-circle grids,
     no centered-everything, no uniform bubbly border-radius, no colored left-border cards,
     no generic hero copy, no emoji as design elements.
10. **Aesthetic spread (binding):** 2 dark cinematic (Midnight Desk, Screening Room), 2 light
    editorial (The Ledger, The Quarterly), 2 wildcards (The Terminal, The Studio Wall).
    No two worlds share a navigation paradigm.
11. **Cross-room bridges designed in each world's idiom:** a finding's **Locate** moves from
    the Feedback Room to the Script Desk at the exact scene (with a visual flash); **Discuss**
    opens the Co-write Room with the finding's quote pre-filled as a quote card.
12. **Honesty of static scope** (§3b) is part of the contract, not fine print.

## 5. The Six Worlds

All six satisfy the same contract; each answers "how does a verdict deserve to be read" in its
own idiom, and each carries its own identity (palette, typography, motion character).

### 5.1 The Ledger — light editorial
Cream paper, ink text, red-pencil severity marks. Serif throughout (`Georgia, 'Iowan Old
Style', serif`), tabular numerals for stats. The report is a **typeset craftsman's letter**:
findings as margin annotations, verbatim quotes as pull-quotes.
- **Nav paradigm:** newspaper masthead sections — SCRIPT / CO-WRITE / VERDICT as named
  section labels across the top.
- **Bridge idiom:** margin notes on script pages reference ledger entries; a ledger finding's
  Locate flips to the page and underlines the line in red pencil.
- **Motion character:** quiet — fades and underline draws; nothing bounces.

### 5.2 The Midnight Desk — dark cinematic
Void glass + warm amber lamp — the user's chosen taste evolved. Script pages glow on the dark
like lit paper; Sameer lives on one side of the desk, the doctor's case file on the other.
- **Nav paradigm:** brass tabs beneath the lamp glow (top switcher, the convention done
  beautifully).
- **Bridge idiom:** Locate jumps to the scene and flashes it amber.
- **Motion character:** slow ambient breaths (lamp glow), instant room swaps.

### 5.3 The Screening Room — dark cinema
Film-poster condensed display + mono data. The report **plays like a screening**: verdict
title card first, then findings as consecutive slides scrubbed on a timeline — severity as
color frames, pacing as a waveform strip.
- **Nav paradigm:** bottom film-strip scrubber — three frames: cutting table (script) /
  director's chair (co-write) / screening (feedback).
- **Bridge idiom:** a finding slide's cue jumps the cutting table to that scene.
- **Motion character:** slide transitions with a projector-flicker accent (reduced-motion
  collapses to cuts).

### 5.4 The Quarterly — light magazine
Editorial grid, sans body + serif display contrast, generous whitespace. Findings read as
**magazine items**: kicker, headline (the finding), body (the note), pull-quote (the evidence).
- **Nav paradigm:** left contents spine — numbered contents list with a thumb-tab marking the
  current section.
- **Bridge idiom:** each item carries a "¶ see page" cross-reference that turns the page and
  marks the passage.
- **Motion character:** restrained editorial reveals on room entry only.

### 5.5 The Terminal — wildcard, monospace
Phosphor on ink, two accent registers (one per room). The report is a **lint stream**:
findings as flagged lines with severity glyphs, coverage as an ASCII block, dials as bar
gauges.
- **Nav paradigm:** status-line buffer tabs + `:` commands (`:script` `:sam` `:verdict`) plus
  a ⌘K palette — keyboard-first world.
- **Bridge idiom:** `loc 12` or clicking a flagged line opens the buffer at that scene.
- **Motion character:** cursor blink; no easing curves — instant state changes.

### 5.6 The Studio Wall — warm craft wildcard
Corkboard, tape, pinned cards, paper grain, lamplight warmth. Findings are **pinned index
cards** on the board; the fix queue is a "to-do" clip strip; dials as hand-marked gauges.
- **Nav paradigm:** pan between three walls (arrow controls + wall labels + ←/→ keys):
  pages wall / Sameer's corner / verdict board.
- **Bridge idiom:** a card's pin pulls a reference to its scene card on the pages wall.
- **Motion character:** paper slides and pin wobbles (reduced-motion: instant).

## 6. Feature Placement — the binding tier inventory

Tiers: **P1** = visible or one click from its home room · **P2** = ≤2 clicks ·
**REP** = believable demo state shown somewhere in the journey.

| Home room | Primary (P1) | Secondary (P2) | Represented (REP) |
|---|---|---|---|
| **Script Desk** | Script pages · inline edit · search · margin/anchored notes · change stars · Stash save + rail | Re-parse, export, backup · reader/print · beat board · revision view · drafts/compare · focus mode · sprint timer | Watch-folder, metrics ⚡ |
| **Co-write Room** | Chat + streaming · quote card · translator on replies · mic on composer | Branches · persona lenses · Sameer's notes on you · clear chat · writer memory/library | — |
| **Feedback Room** | Report lifecycle (empty/running/complete) · findings w/ severity + verification · fix queue verbs · coverage · pacing · dials · setup/payoff ledger · Run Analysis + progress | Re-parse · report language · retry-failed · export/backup · Writer's Mirror reads · character tracks | — |
| **Journey surfaces** | Shelf · upload moment · idea room (chips, /sameer, graduation) | Settings · dawn/night toggle | Spotlight |

Contract nuance (point 5): chips tuck-away is required in the idea room; a world may choose
whether project Co-write has chips, but any chips obey the behavior everywhere.

## 7. Screens & Review Bar

**Required screens per world (6):** shelf → upload moment → script desk → co-write room →
feedback room → idea room. The **upload moment** is the interaction of choosing/uploading a
script file from the shelf — it resolves into the freshly opened project landing on the
Script Desk (contract point 3 in action).

**Per-world review bar** (demo-only, dismissible):
- Room jumps (all three rooms + idea room + shelf)
- Feedback-state toggle: empty / running / complete — so all three lifecycle states are
  reviewable without re-running anything
- Link back to the gallery

## 8. Verification — before the worlds reach the user

1. **Contract audit** — each world checked against the 12 points of §4 plus the §6 tier
   placements (grep-style checklist, one audit block per world recorded in NOTES.md).
2. **Browser walk** — every world: all six screens reached via review bar; both bridges
   clicked (Locate → script desk with flash; Discuss → co-write with pre-filled quote);
   zero console errors.
3. **Quality gates** — WCAG AA contrast spot-checks, body ≥16px, `:focus-visible` present,
   named font stacks declared, AI-slop blacklist scan.
4. **design-review pass** — the gstack design-review skill runs across the finished worlds
   as a final quality gate before the user's review.

## 9. Out of scope (this project)

- Porting any world into the live app (`webapp/index.html`, `app.js`, `style.css`) — the
  winner port is a separate project with its own spec/plan.
- Real backend behavior in the previews (analysis, chat, translation, dictation, memory).
- Mobile-first layouts — desktop-first (review resolution 1440×900); pages must remain
  graceful at narrower widths but mobile design is not finalized here.
- Changes to `preview-redesigns/` (kept as history) or any Python/server code.

## 10. Follow-on sequence

1. Spec self-review (inline) → user reviews this spec
2. `writing-plans` — implementation plan derived from this spec
3. Build the six worlds + gallery (§3 layout)
4. Verification per §8, including the design-review gate
5. User reviews the gallery and picks a winner
6. Post-finalization: `design-consultation` codifies the winner into `DESIGN.md`;
   porting project follows.
