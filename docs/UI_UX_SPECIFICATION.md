# Script Doctor Studio — UI/UX Specification

> **Purpose:** a complete, shareable spec for rebuilding the frontend of Script Doctor Studio
> and integrating it with the backend **without missing anything**. Every screen, component,
> state, interaction, keyboard shortcut, and API contract is cataloged here. Read this
> alongside `docs/ARCHITECTURE.md` (system), `docs/DATA_FORMATS.md` (JSON schemas), and
> `docs/CLI_REFERENCE.md` (CLI).
>
> The current implementation is a **vanilla JS + CSS SPA with zero build step** in
> `screenplay_studio/webapp/` (`index.html` + `app.js` + `style.css` + `core.js`). The backend
> is a single Flask process (`screenplay_studio/webapp_server.py`, port 8500) that serves the
> static files AND the JSON API. Any rebuild MUST keep every feature below — this file is the
> feature/integration contract, not a visual suggestion.

---

## 1. Product context

Local, privacy-first screenplay analysis & co-writing. A writer uploads a screenplay
(`.fdx` `.pdf` `.txt` `.fountain` `.md`), the app parses it deterministically, runs an
LLM-powered analysis (via a local `llama-server`, never the cloud), and offers a
conversational co-writer ("Sameer") plus a script-doctor report ("Dr. Sushruta"). Everything
stays on the machine.

**Non-negotiables (product principles):**
- **Script-first.** The manuscript is the center of the room. Analysis and chat are panels
  around it, never a takeover.
- **No build step.** Vanilla JS + CSS, no framework, no bundler, no external requests
  (all fonts self-hosted; the only HTTP the page makes is to the Flask API and llama-server).
- **Privacy-first.** Everything on-device; the UI must make zero third-party calls.
- **Boring is good.** State is file-based; sessions are JSON files; no database.
- **Fail loudly.** Unverified/flag/don't-drop; errors are shown, never silent.
- **Honest connection status.** Green = your real model verified; amber = built-in demo
  model; red = unreachable. The UI never pretends.

**Display languages:** English, Tenglish, Hindi, Telugu, Tamil, plus **Hinglish** as a
reply-translate register (the 🌐 globe menu offers en/te/hi/Tenglish/Hinglish; report
languages stay the five listed above). UI chrome stays English.

---

## 2. Design system

### 2.1 Palette (CSS custom properties, `:root`)

The app is a "warm room at night." Night = deep warm ink void with the manuscript as
sunlit-vellum paper under a volumetric gold key. The **room lighting is the signature**: the
Co-write room is Sameer violet, the Feedback room is Sushruta cyan, and the CSS `body[data-room]`
swaps the whole accent ramp.

> The shipped visual system is **"Tungsten"** (frozen: refine-freeze-tungsten) — a cascade
> override layer in `webapp/tungsten.css` that loads *after* `style.css` and re-pins the
> token ladder in **both registers** (night + `body.dawn` morning edition: warm parchment,
> same conic key geometry, Sameer violet + Sushruta cyan re-pinned for light). The base
> token values in the table below are the `style.css` fallback set (the pre-Tungsten
> "Nocta Craft Precision" violet/cyan ramp, still live in `:root`); the **shipped** night
> values come from the override: `--ink-950 #150f0a`, `--lamp #e8c56a` (gold),
> `--consult #7ad0e8`, `--danger #c8503a`; the dawn override re-pins `--lamp #7d5f16`,
> `--consult #15708a`, `--danger #a03722`. **All interactive/accented UI must read from
> these variables — never hardcoded colors — so both registers theme automatically.**

Base token set in `style.css` (`:root`, the fallback under the Tungsten override):

| Token | Night value (base) | Purpose |
|---|---|---|
| `--ink-950` | `#09090e` | page void background |
| `--ink-900` | `#0e0e14` | raised surfaces (bars, panels) |
| `--ink-850` | `#131319` | cards |
| `--ink-800` | `#1a1a22` | inputs, chips, wells |
| `--ink-700` | `#22222c` | hover wells |
| `--line` | `rgba(255,255,255,0.085)` | borders |
| `--line-soft` | `rgba(255,255,255,0.05)` | faint borders |
| `--glass` | `rgba(17,17,26,0.66)` | glass surfaces |
| `--glass-strong` | `rgba(19,19,29,0.82)` | stronger glass |
| `--surface` | `rgba(255,255,255,0.032)` | faint surface tint |
| `--surface2` | `rgba(255,255,255,0.06)` | hover surface tint |
| `--paper` | `#f2e8d4` | manuscript paper |
| `--paper-2` | `#ede1c8` | paper gradient top |
| `--paper-ink` | `#2b241b` | text on paper |
| `--paper-muted` | `#6d6050` | muted text on paper |
| `--paper-line` | `#d9ccae` | rules on paper |
| `--lamp` | `#7e6bff` | Sameer violet accent (Co-write) |
| `--lamp-deep` | `#6354cc` | violet deep |
| `--lamp-bright` | `#9b8aff` | violet bright |
| `--consult` | `#53c7f0` | Sushruta cyan accent (Feedback) |
| `--consult-deep` | `#3da8d4` | cyan deep |
| `--accent2` | `#53c7f0` | secondary accent |
| `--info` | `#60a5fa` | info accent |
| `--text` | `#ecebf4` | primary text on void |
| `--text-muted` | `#8b889c` | secondary text |
| `--text-faint` | `#5a586a` | tertiary/hints |
| `--danger` | `#fb7185` | errors / high severity |
| `--danger-bg` | `rgba(251,113,133,0.14)` | danger chip bg |
| `--ok` | `#34d399` | success / addressed |
| `--ok-bg` | `rgba(52,211,153,0.14)` | ok chip bg |
| `--sidebar-w` | `264px` | fixed sidebar width |
| `--radius` / `--radius-sm` | `14px` / `10px` | corner radii |
| `--ease-out` / `--spring` / `--t` | cubic-beziers / 200ms | motion curves |

Room swap: `body` sets `--accent/--accent-deep/--accent-bright/--glow/--glow-strong` to the
violet values by default; `body[data-room="feedback"]` overrides them to the cyan values
(`--accent-bright: #6dd8f7`). The Tungsten override re-pins both ramps
(night: gold lamp + cyan consult; dawn: deep-gold lamp + `#15708a` consult).
**All interactive/accented UI must read from these variables, never hardcoded colors.**

Dawn (light) theme: `body.dawn` re-overrides the ramp to a **daylight** palette — in the
shipped Tungsten register this is warm parchment (`--ink-950: #f2e8d6`, `--lamp: #7d5f16`,
`--consult: #15708a`, `--danger: #a03722`, `--ok: #14784a`; night+dawn share ink,
typography, severity shapes and the conic key geometry). It must round-trip cleanly with
the night theme (toggle button in sidebar + status strip).

River-read (Spark Wall) special surface: dark-glass stream with teal accents
(`#5eead4` borders/lines on `rgba(10,14,26,.82)` pages) — a read-like-water mode.

### 2.2 Typography

Self-hosted fonts (all bundled as `.woff2`, zero external requests; Indic scripts fall back
to system fonts by design):

| CSS var | Family | Use |
|---|---|---|
| `--font-typewriter` | Special Elite | desk artifacts, buttons, headings of chrome |
| `--font-script` | Courier Prime | the manuscript itself (screenplay page) |
| `--font-serif` | Source Serif 4 | prose, body, reports |
| `--font-display` | Instrument Serif | display headings |
| `--font-ui` | DM Sans | default UI font (body) |
| `--font-mono` | IBM Plex Mono | labels, meta, timestamps, chips |
| `--font-hand` | Caveat | the writer's own margin notes |

Base: 15px, line-height 1.55, **`--font-ui` (DM Sans) is the body default** (not serif).
`body` uses `-webkit-font-smoothing: antialiased`.

> ⚠ **Known gap:** `--font-display: "Instrument Serif"` and `--font-ui: "DM Sans"` are
> referenced in `:root` but **not bundled** — there is no `@font-face` for them and no
> `.woff2` in `webapp/fonts/`, so both silently fall back (Georgia / system-ui). Bundling
> them (or re-pointing the vars at bundled families) is an open code task; a rebuild must
> either ship the woff2 files or accept the fallback.

### 2.3 Buttons & controls

- `.btn-primary` — accent gradient CTA; disabled at `opacity .55`.
- `.btn-secondary` — ghost bordered button; `.danger` variant red; `.btn-small`; `.icon-btn`.
- `.btn-paper` — paper-toned button on the welcome card.
- `.explore-chip` — pill chip; collapses to lone icon on first typing (see §7.8).
- `:focus-visible` — always a visible ring (`2px solid var(--accent-bright)`).
- `::selection` — accent selection.

### 2.4 Motion & accessibility

- `prefers-reduced-motion: reduce` → all animation/transition durations ≈ 0.
- Breathing lamp glow (`lampBreath`), room panel fade-in, paper settle, welcome card rise —
  all guarded by the reduced-motion rule.
- A full-screen vignette + film-grain overlay (`body::after`, `pointer-events: none`).
  Note: `body::before` is re-purposed by the NOCTA layer as a 1px top accent gradient line
  (with `!important`), overriding the original `::before` vignette background.

---

## 3. App shell & layout

```
┌───────────────────────────┬─────────────────────────────────────────────┐
│  SIDEBAR (shelf)          │  MAIN                                        │
│  brand · connection dot   │  ┌─ project bar: ⌂ | title | branches ─────┐ │
│  + Lay a new page         │  │  room toggle (Co-write|Feedback) · chip · ⌘K │
│  ───────────────────      │  ├─ WORKSPACE (flex, 3 zones) ─────────────┤ │
│  Ideas (flyout)           │  │  [ DESK: script pane ]   [gutter tabs]   │ │
│  On the shelf (flyout)    │  │  [Context Dock — Evidence / notes]       │ │
│  Your library (flyout)    │  │  [room drawer — summoned from gutter]    │ │
│  ───────────────────      │  └──────────────────────────────────────────┘ │
│  ☀ Dawn · ⚙ Settings      │  STATUS STRIP: project · model · conn ·      │
└───────────────────────────┘   metrics · sprint · elapsed · Dawn          │
                                └──────────────────────────────────────────┘
```

- `#app` is a full-height flex row: fixed `264px` sidebar (`--sidebar-w`) + flexible main.
  **The sidebar collapses** (`#sidebar-toggle` + edge tab `#sidebar-edge-tab`,
  pref `sidebar_collapsed`) 
- **The desk** (`#script-pane`) owns the room: full width, the paper centered at
  `max-width: 700px`. The manuscript never shrinks below 50% of the desk.
- **Room drawer** (`#room-drawer`): the partner panel (Sameer / Dr. Sushruta), summoned
  from the right-edge gutter tabs, dismissed by ✕ / Esc / clicking the manuscript. The
  script keeps the room.
- **Structural rail** — **RETIRED** (`#struct-rail`; its markup, `r` shortcut, edge
  tab and CSS are gone). Its jobs: scene outline → the scene index; Stash + notes →
  the dock's Stash & Notes lens; character dials → the craft shelf and Evidence lens.
- **Problem Board** — **RETIRED** (`#problem-board` and its `#pb-edge-tab`: markup, CSS,
  palette command and scroll-sync are gone, not dormant). Its jobs: the finding list,
  severity filter and Locate/Rewrite/Discuss/Dismiss controls → the Context Dock's
  **Evidence lens** (§4.4b); the per-line reminder → the manuscript margin pins. One home
  per finding row, per §4.4b's "zero new surfaces".
- **Status strip** (`#status-strip`): thin footer with model/connection/metrics/sprint/dawn.

### 3.1 Responsive behavior
- The script pane width is resizable via `#pane-divider` (drag), clamped 50–78% of the desk;
  double-click resets. Persisted (`localStorage pane-width-v2`).
- Full-screen tools (Beat Board, Compare, Revision) take the whole main area.
- Mobile: sidebar becomes the shelf; the desk stays the center. Keep the manuscript
  readable and the panels collapsible.

---

## 4. Screens & views (complete inventory)

### 4.1 Welcome / Desk view (`#welcome-view`)

Shown when no project is open. Atmosphere: a drawn lamp (`scene-lamp`), a night window with
moon/stars/hills (`scene-window`), a shelf of book spines (`scene-shelf`). Time-aware greeting
("Still up, writer?" / "The kettle's on." / "The desk is yours." / "The lamp's on.").

Contents:
- **Welcome card**: headline "Put the pages on the desk.", language blurb, a **dropzone**
  (click or drag-drop; accepts `.fdx .pdf .txt .fountain .md`), upload status line.
- **Alt actions**: "💡 Talk to Sameer about an idea" (creates an idea), "Open the sample
  page" (creates the bundled sample project).
- **Shortcut hint** (dismissable): `Ctrl+K` commands · `j`/`k` scenes · `?` all shortcuts.
- **Dashboard** (`#dashboard`): "On the desk" — every project as a card with status dot,
  stats, one-click actions (open / delete / stage label); a connection pill; a 3-step
  "how it works" strip (Lay the pages down → Run the doctor → Rewrite with Sameer).
- Privacy footnote: "Everything stays on this machine."

### 4.2 Project desk (`#project-bar` + workspace) — the main surface

Opening a project (from shelf, dashboard card, sample, or session restore) shows:

**Project bar** (top): `⌂` home button, project title, branch switcher pills, room toggle
(Co-write | Feedback), room chip ("✍️ Writer's Desk" / "📋 Consultant's Desk"), palette button
(`Ctrl K` / `⌘K` platform-aware).

**Script toolbar** (above the pages): search box, finding summary chips (N open / N addressed),
plus visible actions: 📌 Premise (only if a graduated idea carried a premise card), ✳ Focus,
✎ Revise, and an **overflow "⋯" menu** (`#overflow-toggle` / `#overflow-dropdown`) holding:
Reader, ≋ Flow, 📋 Beat Board, 🗂 Compare, ⬇ Backup .zip, Export .fountain/.fdx/.txt,
Print / Save PDF, Discard edits (danger, only when edits exist). ↶ Undo / ↷ Redo buttons
exist but are `display:none` — undo/redo is keyboard-only (`Ctrl/⌘ Z`).

**The manuscript** (`#script-scenes`): each scene renders as a **cream paper page**
(`.scene-page`, slight alternating rotation that straightens on hover):
- Scene head: "Scene N", heading, `≈ N min` estimate chip, "discussed" tag (if the writer
  asked Sameer about this scene), "✎ note" button.
- Elements styled per type: scene heading (bold caps), action (left), character (centered
  with `padding-left:220px`), dialogue (indented `150px`), parenthetical (italic, `190px`),
  transition (right-aligned), shot (italic muted).
- Search highlights `<mark>` in headings + element lines; non-matching scenes hide.
- **Change-mark stars**: lines that are the NEW text of an applied edit get a `★` gutter
  star; hover shows "Edited — was: <old>".
- **Anchored findings**: lines whose text matches a verified evidence quote become clickable
  (`el-anchored`, `❋` marker); clicking opens the finding card or locates it.
- **Anchored margin notes**: lines with a pinned writer note get a `📌` marker; click opens
  the note card.
- **Margin notes column** (`scene-notes`): the doctor's finding cards for the scene
  (severity color-coded left border, category label, issue, state, actions) + the writer's
  own hand-font notes.
- **Inline editing**: double-click any line — or focus it with `s` then the arrows and press
  `Enter` — → contentEditable → Enter/blur saves via the edits/apply path (undoable), Esc
  cancels. Keyboard edits put the line cursor back on the page afterwards.
- **Craft shelf** (`#craft-shelf`): a collapsed-by-default header over the four analysis
  panels that live at the top of the manuscript — Fix queue · Pacing · Characters · Writer's
  Mirror. One click expands; state persisted.
- **Draft bar** (`#draft-bar`): draft switcher + "Upload new draft" — always visible while
  a project is open (drives Compare/diff); a diff banner (`#diff-banner`) appears after a
  draft activation.
- **Script-level notes bucket**: findings with no scene ref + writer's script-level notes.
- **Select-to-ask float**: select text → floating "✎ Ask Sameer about this" button (plus
  "📥 Stash this" and "📝 Note this line" below it). §7.2. A second, richer selection popup
  (`#text-popup`) also exists — see §7.14.

### 4.3 Co-write room (`#cowrite-panel`, in the drawer)

- **Partner card**: avatar, "Sameer — AI writing partner", actions: "back to Sameer"
  (reset lens), "Sameer's notes on you", "🗑 Clear chat".
- **Message thread** (`#messages`): user bubbles right, assistant bubbles left with role
  header ("You"/"Studio"), per-message **branch badge** (color per branch), and a **🌐
  translate globe** on assistant replies (hover → 5-register menu: English / తెలుగు /
  हिन्दी / Tenglish / Hinglish; picking renders an inline, display-only translation panel —
  never stored).
- **Empty states**: project — "Ask about a theme, a character…"; idea — context-specific
  (see §4.6).
- **Conversation overview rail** (`#msg-rail`): a hover rail alongside the thread with one
  line per user message; click-to-jump, current-message tracking.
- **Idea context card** (idea mode only): proof Sameer "has your page" — word count +
  show/hide snapshot toggle.
- **Composer** (`#composer`): growing `<textarea>` (auto-resize to ≤160px), quote card slot
  above it, previous-message history popup (ArrowUp/Down), Send button. Enter sends,
  Shift+Enter newline. Mic chip for dictation (§7.9). **`/sameer <ask>`** typed anywhere in
  the idea page summons Sameer's drawer with the ask prefilled.
- **Explore chips** (idea mode): guided prompts ("Sameer runs with it"), collapse to icons
  on typing.
- Streaming: assistant replies **stream token-by-token** (SSE) into the bubble with an
  elapsed ticker; a 408 watchdog offers a "still working — keep waiting?" retry instead of
  a silent hang.

### 4.4 Feedback room (`#feedback-panel`, in the drawer)

The consultant's desk — "Dr. Sushruta's Report".

- **Header**: "Report in" language select (English/Tenglish/Hindi/Telugu/Tamil), live
  analysis progress chip (bar + % + ETA; hover opens the **20-stage** pipeline map), 📥 Report
  export link (when a report exists), Run Analysis / ↻ Re-parse / ⚠ Retry failed buttons.
- **Tabs**: Report | Fix Queue.
- **Report pane** (`#feedback-report`): Coverage card (recommendation badge, logline,
  synopsis, weaknesses); **Setup/Payoff** ledger card (✓ Paid off / 🚩 Dangling / 🪦
  Abandoned / 🪄 Red herring); **Pacing** SVG (per-scene pace bars, drags flagged, dashed
  threshold line, click bar → jump to scene); **Character dials** (per-character 1-10
  trait sliders); **Writer's Mirror** (logline signal + character reads with evidence);
  then findings grouped by category (severity, scene refs, why-it-matters, 🎯 Locate).
- **Fix Queue pane** (`#feedback-fixqueue`): reused `renderFixQueuePanel` — severity badges,
  act chips, scene labels, actions (🎯 Locate · Rewrite · Discuss · Dismiss/Restore), a
  **dawn meter** (night→dawn fills as findings resolve), and a "Show/Hide dismissed" toggle
  when any finding is dismissed.
- **Empty state**: "No analysis yet — Run Analysis to get the consultant's report."
- **Persona/mode selects**: the DOM `<select>`s for persona and mode are kept `hidden` —
  conversational lenses are switched via rooms/lens, not dropdowns. `/api/config` still
  serves the full persona/mode lists and the fallback contract below stands.

### 4.4b Feedback View (`#feedback-view`) — DORMANT since the GO 2 fold

**Status (GO 2, "1A — fold FV in"): the Feedback room toggle, the `f` shortcut, and the
Consultant gutter tab now all route to the main workspace** — they open the Context Dock
with the **Evidence lens** active (mass strip + deep cards + filter row) instead of this
surface. `openFeedbackView()` is a fold: it never sets `state.view = "fv"`; session
restore maps a stored `view: "fv"` to the workspace too, and the layout audit grep-gates
that no reachable path sets it. The three-pane surface below remains in the DOM **dormant,
unreachable — not deleted** (its removal is a separate later commit). The drawer panel
(§4.4) remains reachable in idea-less contexts via `openFeedbackRoom()`.

- **Three panes (dormant)**: left Dr. Sushruta chat (streaming via `sendFvMessage`), center script
  column with per-scene finding severity dots (`renderFeedbackView`), right panel with
  Board/Sameer tabs (`switchFvTab`).
- **Layout machinery (dormant)**: maximize toggle (`fv-maximized`), draggable pane dividers
  (`initFvDividers`), scroll sync between script column and findings (`initFvScrollSync`),
  and an honest `fin` end-marker at the bottom of the script column.

### 4.4c Problem Board (`#problem-board`) — RETIRED

**Status: removed, not dormant.** The docked right-side findings panel, its edge tab
(`#pb-edge-tab`), its palette command and its IntersectionObserver scroll-sync are gone
from the DOM, CSS and command palette. A finding row has ONE home now:

- Severity filter, scene grouping, and the Locate / Rewrite / Discuss / Dismiss controls
  → the Context Dock's **Evidence lens** (§4.4b) — mass strip, deep cards, filter row.
- "What sits on this line while I'm reading it" → the manuscript margin pins (`R6`),
  which keep Locate only and stay read-only by contract.
- The old `b` palette collision note is moot: `b` opens the Beat Board, and nothing else
  claims it.

### 4.5 Full-screen tools

- **Beat Board** (`#beatboard-view`, key `b`): corkboard of scene cards. Each card: position
  number, heading, int/ext chip, min estimate, note count, **open-finding severity dots +
  count** (addressed findings excluded), ↑↓ move buttons, drag-and-drop reorder. Toolbar:
  Restore original order · Export reordered draft (.fountain) · Print cards · Save order
  (disabled until dirty). Saving writes a permutation; the draft is untouched until export.
- **Compare** (`#compare-view`, key `d`): side-by-side draft comparison. "Showing <from>
  → <active draft>" with a from-select; per common scene, two aligned columns; line kinds:
  same (muted), changed, added (underlined), removed (struck through). Summary chip: "N
  scenes compared".
- **Revision view** (`#revision-view`, key `v`): three columns — scene navigator (per-scene
  rows with severity dots + count, strikethrough when all addressed) | the manuscript pages
  | the findings queue. Anchored lines flash their queue row. Mono status strip: "Scene N of
  M · X words · A open / B addressed · title".

### 4.6 Idea room (scriptless development)

Two sub-surfaces inside `#script-pane`:

- **Premise pane** (`#premise-pane`): for ideas already with a project (graduated). Editable
  premise card: working title, logline, premise, open questions. Buttons: Save, 📄 Upload the
  first pages, explore-path chips. Hint: "The card rides with the conversation…".
- **Idea canvas** (`#idea-canvas`, the current "Spark Wall" idea surface): a **blank page
  on the void** with a starfield + light-threads ambience. Title input (click to rename,
  autotitles from the first line), autosave state (lowercase "saving…" → "saved HH:MM",
  auto-clears after 4s), ▸ Structure toggle (logline + open questions behind it), "✦ Grow
  into pages" (graduate → upload first pages), a floating "Sameer" pill to summon the idea
  chat, and a mic chip. Typing autosaves (debounced **300ms** + on blur + `sendBeacon`
  flush on pagehide); the idea chat is **one idea = one session**, lazy-created, with the
  whole page in context.

The room toggle becomes two **lenses on one conversation**: Co-write = Sameer (explore),
Feedback = Premise Doctor (validate). No doctor, no scripts, no shelf in idea mode
(`body.idea-mode` hides room toggle / gutter / rail edge tab).

**Graduation**: upload first pages → a real project is created; the premise card + the idea
conversation carry over so the same Sameer/memory continues on the script desk.

### 4.7 Modals (all share focus trap + Esc-close + click-outside)

| Modal | Contents |
|---|---|
| **Settings** | llama-server URL, response timeout (30–7200s), fast model (optional), chat turn cap (15–1800s), Test Connection with result, Save/Cancel |
| **Rewrite** | per-scene: finding context, optional instruction, "Generate rewrite" → candidate list (checkbox each, old → new), "Apply changes" (applies checked via edits/apply), status + note lines |
| **Command palette** | input + fuzzy results (commands · scenes · help · craft hints); `Ctrl/⌘ K` opens, `?` shows all shortcuts; ↑↓ Enter, Esc closes. Seven `type:"craft"` entries ("Why doesn't my dialogue land?" etc. — McKee/Snyder/Field/Vogler/Swain) route through `openSameerWith()` |
| **Fork** | name the branch → create fork |
| **Sam's notes on you** | writer relationship memory: dimensions, observations list (each with "forget this"), "Refresh now", empty state, Close |

### 4.8 Tungsten chrome layer (v4 additions)

On top of the base shell (all in `app.js` `initNoctaDesign` — the function kept its
historical name — plus the `style.css` NOCTA section and the `tungsten.css` override):

- **Auto-hide chrome**: the project bar + script toolbar fade to `opacity 0` after 4s idle;
  any mouse move within 120px (or hovering sidebar/modal) restores them.
- **Sameer slide-in panel** (`#sameer-panel`): a contextual panel with hardcoded seed
  messages + craft references (McKee — Gap Analysis etc.). ⚠ Currently a **visual mock** —
  its composer only appends locally; no API call is made.
- **Craft level badge** (`#level-badge`): "Level 1 · Upload & Discover" → Level 4;
  auto-advances on finding-card clicks (`setCraftLevel`).
- **Cursor spotlight** (`#cursor-spotlight`): a fixed radial gradient following the mouse.

### 4.9 GO 2 evidence surfaces (the writer's loop + the fold)

Riders on the main workspace (zero new surfaces — the Context Dock's Evidence lens IS the
board; full rationale in `docs/PHASE_B_FV_FOLD_SPEC.md`):

- **The fold**: Feedback entry points open the dock Evidence lens (§4.4b status).
- **One filter row** (dock Evidence header, `buildFindingFilterRow`): severity toggles +
  category count-chips + next-pass toggle + `⇉ fix loop` button. **One filter state
  (`state.findingFilter`) drives ink, board list, loop list and counts together** — the
  page and the board cannot disagree by construction. Default = highs inked.
- **Ink marks** (`inkAnchorsFor`/`decorateLineWithInk`): each inked finding's verified
  quote is wrapped in an inline `<mark class="finding-ink">` on its scene page — inherits
  the page font, never reflows, `aria-hidden` (decoration; the board carries semantics);
  active search suppresses ink (transient beats persistent).
- **The keyboard fix loop** (`startLoop`/`stepLoop`/`exitLoop`/`renderLoopBar`): engaged
  via the `⇉` button; loop bar (i-of-N · prev/next · mark-addressed · next-pass · Discuss
  · copy · Esc) re-docks itself after any lens re-render; N/P step with wrap-around across
  the filtered list, scrolling to the finding's ink anchor + flash, auto-expanding its dock
  card (`.loop-current`); Discuss = `setPendingQuote` + the Sameer lens; copy = quote +
  scene slug (clipboard with execCommand fallback). Esc exits the loop — the dock stays.
- **Intent buttons** (deep dock cards): ✓ mark-addressed / ⏭ next-pass / ⧉ copy — persisted
  to `finding_marks.json` (id-keyed via GO 1 identity, survives report regeneration);
  deferred findings dim, leave open counts, and carry a "next pass" chip.
- **Escalation to Dr. Sushruta** (deep dock cards): 🩺 pins the finding's quote, opens the
  Sushruta lens and seeds the "why was this flagged?" question — one gesture from a card to
  the doctor WITH the finding in hand. The consult turn then rides the quote into the
  doctor's prompt, and every stored turn is tagged `partner` (`writing_partner` |
  `script_consultant`) so the Sushruta lens renders the writer's own question + a quote chip
  alongside the doctor's replies (legacy sessions without tags keep the assistant-only view).
  The composer's partner is flushed onto the session before the turn is stored, so a session
  created by the send never speaks the doctor's first answer in Sameer's voice.
- **The arrival strip** (`buildArrivalStrip`, dock Evidence top): when a new report lands —
  the **pass line** "Pass: N → M still live · K no longer flagged · J new" (computed from
  `last_pass.json`, one generation back) + a scope chip ("from the last run, not your edits")
  + a **draft clause** carrying the writer's OWN working-copy progress ("K of M addressed by
  you", same counting contract as the revision strip) + the trust readout ("N of M quotes
  verified (P%)", pushed right) + an inline **Retry failed (k)** when categories failed +
  **ghosted marks** (writer-intent findings absent from the new pass — muted, expandable,
  never red, in no open count). One ambient peek-chip on arrival; a lasting unread dot rides
  `#dock-tab-evidence` until the lens is opened.
  **GAP-5 honesty:** the pass numbers compare one analysis pass to the previous one; both
  read the parse-of-record (`orchestrator.py` loads `m.parsed_path`), so they can never
  respond to writer edits. The scope chip says so on-screen and the draft clause carries the
  working-copy truth (`finding_statuses`) that the strip previously lacked — the word
  "Fixed" (which borrowed writer credit it couldn't earn) is gone.

---

## 5. The sidebar (shelf)

- **Brand**: "Script Doctor / Studio" + connection dot (green=your model verified · amber=demo
  craft model · red=unreachable).
- **"+ Lay a new page on the desk"** — amber CTA → goes to the welcome desk dropzone.
- **Ideas / On the shelf / Your library**: three collapsible **flyout sections**. Hover opens
  the scrollable list; click pins it open; a mousemove guard closes it when the pointer
  leaves the section+flyout union; Esc/outside-click closes. Each has a section count badge.
  Shelf rows: stage dot (complete=filled ok / failed=red), title, status line, hover-reveal
  ✕ delete (with cascade-honest confirm). **Unreadable projects** show a "⚠ unreadable"
  flag, error on open, remain deletable. Library = a live view of the shelf (deleting one
  deletes the other); library rows render **without** a delete button (deletion happens via
  shelf/dashboard).
- **Footer**: ☀ Dawn · ⚙ Settings.
- **Collapse**: the whole sidebar collapses via `#sidebar-toggle` / `#sidebar-edge-tab`
  (pref `sidebar_collapsed`), mirroring the structure-rail pattern.

---

## 6. Status strip

Thin footer, left→right:
- `#status-project` — "{project} · {room} · Esc to leave" (Spotlight keeps this lit).
- `#status-model` — model id (not URL), hover card with full state/model/server truth.
- `#status-conn` — "—" / "● demo craft model (built-in)" / "● your model is back — click to
  switch" (in demo mode when the real server returns, one click re-attaches) / connection
  message. Re-checked on init, settings save, and demo-switch (no fixed interval).
- `#status-metrics` — "⚡ Ns · X/Y fixed" with hover detail (avg reply, last analysis, %
  fixed, passages discussed).
- `#sprint-timer` — 25:00 countdown; click start/pause, double-click reset; pulsing dot
  while running, green when done.
- `#status-elapsed` — "⏱ Nm at the desk" (session timer).
- ☀ Dawn toggle.

---

## 7. Interaction patterns (reusable behaviors)

### 7.1 Rooms
`setRoom("cowrite"|"feedback")` swaps panel + `body[data-room]` (theme) + drawer identity +
gutter + chip + room-toggle active state. Co-write opens Sameer drawer; Feedback opens the
consultant drawer. Keys `c`/`f`.

### 7.2 Select-to-ask / float actions
Select ≥4 chars in the manuscript (or idea page) → a floating button stack appears next to
the selection: "✎ Ask Sameer about this" (prefills the composer with a quote card), "📥
Stash this" (saves to the Stash, shows "Stashed ✓"), "📝 Note this line" (opens an inline
note editor pinned to that line). Selection cleared / scroll / outside-click hides them. The
composer placeholder becomes "Reply to the highlighted passage…" while text is selected.

### 7.3 Esc cascade ("the page wins")
A craft-rule popover closes first, then the top-most visible modal, then river-read
(flow). Below those, in order: the keyboard fix loop → Spotlight → Revision view →
Premise card → Compare → Beat Board → **Context Dock** → room drawer → craft shelf.
Sidebar flyouts handle their own Esc separately. (The retired Feedback View and Problem
Board are no longer rungs — nothing can open them, so nothing closes them.)

### 7.4 Spotlight mode (key `z`)
TOTAL chrome removal — project bar, toolbars, rail, drawer, gutter, craft shelf, script-level
notes all `display:none`; pages widen to 720px; status strip dims to 0.45 (keeps
project · sprint · elapsed · dawn). Esc leaves. Full-screen tools auto-exit Spotlight.

### 7.5 Focus mode (`✳ Focus`, persisted)
Chrome desaturates; non-current scenes dim to 0.28; the current scene keeps only the live
line full (typewriter scroll). Click/focus the manuscript exits focus-typewriter.

### 7.6 River read (`≋ Flow`, persisted)
Manuscript becomes one continuous dark-glass flow: pages as glass cards with teal borders,
wave separators between scenes, margin machinery hidden; a fixed right-edge current nav
(tracked dot + click-jump). Esc leaves.

### 7.7 Reader mode (`Reader`, persisted)
The draft clean — no margin machinery, craft shelf hidden. Printable (window.print).

### 7.8 Explore chips (idea room + composer)
Pill chips of guided prompts; **collapse to lone icons** on first real input in the idea
page or composer; clearing the box restores them. Hover reveals the label.

### 7.9 Dictation (mic chips)
A mic glyph beside every writing surface (`#idea-content`, `#input`, premise fields, idea
logline/questions, rail note). Click to record → transcribe → insert at caret. Right-click
picks spoken language (persisted). Fully local via `/api/stt`.

### 7.10 Reply translation (🌐 globe)
Hover an assistant reply's globe → 5-register menu → inline display-only translation panel
(beneath the bubble, never persisted). Positioned fixed, flipped above the viewport edge.

### 7.11 Dawn meter
A night→dawn fill driven by `addressed / (open+addressed)` in the fix queue; the whole room
warms (`--spark-dawn`) as findings resolve. Rendered in the Fix Queue panel head.

### 7.12 Branch-based conversations
Fork (create), switch, delete branches; per-message origin badge with stable per-branch hue;
"main" is always neutral brass. Composer history recall (↑/↓).

### 7.13 Session & preference persistence
- Session (last project/idea/view/scene — a stored `view: "fv"` restores as the workspace,
  see §4.4b's fold) → `localStorage screenplay_studio.session.v1`; a reload restores where
  the writer left off.
- Prefs (dawn, reader, focus, flow, craft_open, hintDismissed, stt lang, pane width,
  sidebar_collapsed) → `localStorage screenplay_studio.prefs.v1`
  (+ `pane-width-v2`, `studio-stt-lang`).
- The sprint timer state survives reload (`localStorage screenplay_studio.sprint.v1`);
  the session-elapsed start lands in **sessionStorage** (`studio.session.start`) so it
  persists across reloads within the tab.
- An unreadable/corrupt project stays visible (flag-don't-drop) with an actionable error.

### 7.14 Contextual text-selection popup (`#text-popup`)
A second selection surface (distinct from §7.2's float stack): a context-aware popup whose
actions depend on the current page (idea / script / revision): **Ask Sameer, Ask Consultant,
Add margin note, Stash, Add to logline, Rewrite passage, Locate finding**. Routes asks
through `/sameer <ask>`. Note: its **Stash** action writes a `"[STASH] …"` line into the
rail note input rather than calling the Stash endpoint — different from §7.2's float Stash.

---

## 8. Keyboard shortcuts (complete list)

| Keys | Action |
|---|---|
| `Ctrl/⌘ K` | Command palette |
| `Ctrl/⌘ Z` | Undo last applied edit |
| `Ctrl/⌘ Shift Z` | Redo the undone edit |
| `c` | Switch to Co-write (Sameer) |
| `f` | Switch to Feedback (Consultant) |
| `s` | Focus the manuscript — dismiss the partner, back to the page |
| `↑` / `↓` (from `#manuscript-container`) | Walk the line cursor one script line. The manuscript is **one tab stop** (`tabindex="0"` on the region), never nine hundred: lines carry `tabindex="-1"` and arrows move focus, so `Tab` still leaves the page in one press |
| `a` | Toggle the Craft shelf (analysis panels) |
| `z` | Spotlight mode — nothing but the page (Esc leaves; **project-gated**, like `b`/`d`/`v`) |
| `b` | Open the Beat Board (project only) |
| `d` | Compare drafts side by side (project only) |
| `v` | Toggle the Revision view (project only) |
| `j` / `n` | Next scene (script view) — **while the fix loop is active: next finding (with `↓`)** |
| `k` / `p` | Previous scene (script view) — **while the fix loop is active: previous finding (with `↑`)** |
| `/` | Search the script |
| `?` | Show all shortcuts (palette help) |
| `Esc` | Leave spotlight → **exit the fix loop (dock stays)** → dismiss partner drawer → craft shelf → modals → flyouts (full cascade in §7.3) |
| `↑`/`↓` + `Enter` | Palette navigation / run |
| Inline edit: double-click a line **or `Enter` on the focused one** → contentEditable · `Enter` save · `Esc` cancel · `Shift+Enter` newline · after a keyboard save the line cursor returns to the line you just changed | |
| Composer: `Enter` send · `Shift+Enter` newline · `↑`/`↓` history · `Esc` cancel history | |
| Inline note editor: `Enter` save · `Esc` cancel | |

Idea room: `c`/`f`/`a` also work (Sameer ↔ Premise Doctor lens). Full-screen tools
guard `b`/`d`/`v` to project mode.

---

## 9. API integration contract

> All routes are prefixed `/api` and served by the same Flask process on `http://localhost:8500`.
> Errors return `{"error": "<message>"}` with appropriate status codes (400 bad input · 404
> missing · 413 too large · 502 llama-server down · 503 co-writer missing · 408 watchdog).
> Project names/ids are URL-safe slugs; use `encodeURIComponent`.

### 9.1 Config & connection
| Method | Path | Request body | Response |
|---|---|---|---|
| GET | `/config` | — | `{server_url, model, timeout, fast_model, turn_timeout, demo_model, [real_server_url], personas: [], modes: []}` |
| POST | `/config` | `{server_url?, model?, fast_model?, timeout?, turn_timeout?}` | same shape |
| POST | `/test-connection` | `{server_url?}` | `{ok, message, models?}` |
| GET | `/health` | — | `{status, server_url, demo_model}` |
| GET | `/real-server-check` | — | `{demo:false}` or `{demo:true, available, url?, models?}` |

`personas`/`modes` come from the co-writer (fall back to `FALLBACK_PERSONAS`/`FALLBACK_MODES`
in the frontend when absent).

### 9.2 Projects
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/projects` | — | array of `_manifest_summary` (below) |
| POST | `/projects` | multipart `file` + `title` | `_manifest_summary`, 201 |
| GET | `/projects/<name>` | — | `_manifest_summary` + optional `premise` |
| DELETE | `/projects/<name>` | — | `{ok, project}` |
| POST | `/sample` | — | `_manifest_summary`, 201 |
| GET | `/projects/<name>/backup` | — | `.zip` download |
| POST | `/projects/<name>/reparse` | — | `_manifest_summary` |

**`_manifest_summary` shape** (returned by most project routes):
```
{ project, title, server_url, model_id,
  stages: { parse: status, analyze: status, chat: status },
  errors: {...}, sessions: [ {session_id,...} ],
  has_edits, edit_count, drafts: [...], active_draft,
  report_language, failed_categories: [...] }
```
Unreadable projects return `{project, title, unreadable: true, stages: {...}, sessions: []}`.

### 9.3 Analysis
| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/projects/<name>/analyze` | `{force?, report_language?}` | `_manifest_summary` |
| POST | `/projects/<name>/analyze/retry-failed` | `{}` | `_manifest_summary` |
| GET | `/projects/<name>/progress` | — | `{stage, status, detail}` (running/stalled/done) |
| GET | `/projects/<name>/report` | — | full `report.findings.json` (sanitized) |
| GET | `/projects/<name>/report/export` | `?` | `.html` report download |
| GET | `/projects/<name>/fixqueue` | `?include_dismissed=1` | `{items, acts, dismissed_count, total_count}` |
| POST | `/projects/<name>/findings/<index>/dismiss` | `{issue}` | `{ok, index}` |
| POST | `/projects/<name>/findings/<index>/undismiss` | — | `{ok, index}` |
| GET | `/projects/<name>/characters` | — | `{characters: [track...]}` |

**fixqueue item**: `{index, category, severity, issue, why_it_matters, scene_refs,
scene_heading, act, act_name, status (addressed|still_present|unknown), dismissed}`.
Sorted by (severity weight high→low, act, index).

**character track**: `{name, importance (main|supporting|bit), scenes_present, scene_count,
dialogue_lines, dialogue_share, first_scene, last_scene, traits, interactions:
[{name, scenes}], reads}`.

### 9.4 Manuscript / revision
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/projects/<name>/script` | — | `ScriptDocument` JSON + per-scene `page_estimate`/`word_count` + `runtime_minutes` |
| POST | `/projects/<name>/rewrite` | `{scene_number, finding_index?, instruction?}` | `{scene_number, note, replacements:[{old,new}], scene_text}` |
| GET | `/projects/<name>/edits` | — | `{edits, findings_status, can_undo, can_redo, finding_intents, last_pass}` |
| POST | `/projects/<name>/edits/apply` | `{scene_number, replacements:[{old,new}]}` | `{applied, skipped, scene_text_after, findings_status}` |
| POST | `/projects/<name>/edits/undo` | — | `{..., findings_status}` |
| POST | `/projects/<name>/edits/redo` | — | `{..., findings_status}` |
| POST | `/projects/<name>/edits/reset` | — | `{ok, has_edits}` |
| POST | `/projects/<name>/findings/intent` | `{finding_id, intent: "addressed"\|"deferred"}` | `{ok}` — the GO 2 intent store (`finding_marks.json`, id-keyed via GO 1 identity; survives regeneration) |
| GET | `/projects/<name>/export` | `?format=fountain|fdx|txt` | file download |
| GET | `/projects/<name>/metrics` | — | `{avg_reply_seconds, analysis_seconds, findings_total, findings_fixed, findings_fixed_pct, discussed}` |

`findings_status` shape: `{findings:[{index, status}], summary:{addressed, still_present,
unknown}}`. `finding_intents` shape: `{<finding_id>: "addressed"\|"deferred"}`. `last_pass`
shape: `{last_total, still_live, fixed, new, ghosted_marks}` or `null` (honest None on the
first pass; computed lazily with an mtime guard, one generation back). All `last_pass`
counts are **distinct finding-id counts**: duplicate ids (same category + quote/issue) are
counted once, so a no-op re-analysis reports `fixed: 0, new: 0`.

### 9.5 Notes, Stash, premise
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/projects/<name>/notes` | — | `{notes:[...]}` (newest first) |
| POST | `/projects/<name>/notes` | `{scene_number?, text, anchor?}` | note, 201 |
| PATCH | `/projects/<name>/notes/<id>` | `{text}` | note |
| DELETE | `/projects/<name>/notes/<id>` | — | `{ok}` |
| GET | `/projects/<name>/stash` | — | `{stash:[...]}` |
| POST | `/projects/<name>/stash` | `{text, title?, scene_number?}` | entry, 201 |
| DELETE | `/projects/<name>/stash/<id>` | — | `{deleted}` |
| POST | `/projects/<name>/premise` | `{card:{title?, logline?, premise?, questions?}}` | `{premise}` |

**note**: `{id, scene_number, text, anchor, created_at, updated_at}`.
**stash entry**: `{id, text, title, scene_number, created_at}` (newest first).

### 9.6 Beat board & drafts
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/projects/<name>/beatboard` | — | `{order:[...], cards:[...]}` |
| PUT | `/projects/<name>/beatboard` | `{order:[...]}` | board |
| POST | `/projects/<name>/beatboard/reset` | — | board |
| GET | `/projects/<name>/beatboard/export` | `?format=` | file download |
| GET | `/projects/<name>/drafts` | — | `{active_draft, drafts:[...]}` |
| POST | `/projects/<name>/drafts` | multipart `file` | `_manifest_summary` |
| POST | `/projects/<name>/drafts/activate` | `{name}` | `_manifest_summary` |
| GET | `/projects/<name>/diff` | `?from=&to=` | diff |
| GET | `/projects/<name>/compare` | `?from=&to=` | compare |

**beatboard card**: `{scene_number, heading_raw, int_ext, page_estimate, your_notes}`.
**compare response**: `{from, to, common_scene_count, scenes:[{scene_number, heading, rows:
[{kind: same|changed|added|removed, left, right}]}]}`.

### 9.7 Chat (project + idea)
| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/projects/<name>/chat/start` | — | `{session_id, model_id, branch}` |
| GET | `/projects/<name>/chat/sessions/<sid>` | — | session payload (branches/messages/personas) |
| DELETE | `/projects/<name>/chat/sessions/<sid>` | — | `{deleted}` |
| POST | `/projects/<name>/chat/sessions/<sid>/messages` | `{text, quote?}` | `{reply, branch, messages}` |
| POST | `/projects/<name>/chat/sessions/<sid>/messages/stream` | `{text, quote?}` | **SSE** — `data: {"token": "..."}` frames, final `data: {"done": true, reply, branch, messages}` or `data: {"error", still_working}` |
| POST | `/projects/<name>/chat/sessions/<sid>/fork` | `{name, from_branch?}` | `{current_branch, branches}` |
| POST | `/projects/<name>/chat/sessions/<sid>/switch` | `{name}` | `{current_branch}` |
| POST | `/projects/<name>/chat/sessions/<sid>/settings` | `{persona?, mode?}` | `{active_persona, active_mode}` |
| POST | `/projects/<name>/chat/sessions/<sid>/translate` | `{index, target_lang}` | `{index, translation}` |

Idea routes mirror these under `/api/ideas/<idea_id>/chat/...` with the same shapes
(`/chat/start`, `/chat/sessions/<sid>` GET/DELETE, `/messages` POST, `/messages/stream`,
`/settings`, `/translate`). **No fork/switch for idea sessions** — branching is
project-only.

**quote** (select-to-reply): `{scene_number?: int, text: string}`.

**Session payload** (GET session): includes `last_seen_content` — the last script content
the session "saw" (used for stale-session honesty), in addition to the shape in §10.

### 9.8 Idea store & writer memory
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/ideas` | — | `[{id, title, ...}]` |
| POST | `/ideas` | `{title?}` | meta, 201 |
| GET | `/ideas/<id>` | — | meta |
| DELETE | `/ideas/<id>` | — | `{deleted}` |
| POST | `/ideas/<id>/content` | `{content}` | `{title, auto_title}` |
| POST | `/ideas/<id>/rename` | `{title}` | `{title, auto_title:false}` |
| POST | `/ideas/<id>/card` | `{card:{...}}` | meta |
| POST | `/ideas/<id>/graduate` | multipart `file` + `title` | `_manifest_summary`, 201 |
| GET | `/writer-memory` | `?scope=` | `{profile, card, gated}` |
| POST | `/writer-memory/observations/<id>/suppress` | — | `{ok}` |
| POST | `/writer-memory/refresh` | `{project, session_id}` | `{profile, card}` |
| GET | `/writer-library` | — | `{projects:[...]}` |

### 9.9 Dictation
| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/stt` | multipart `audio` + `language` | `{text, ...}` (503 if engine missing) |
| GET | `/stt/languages` | — | `{languages:[...], engine}` |

### 9.10 Design Lab (read-only prototype feed)
| Method | Path | Response |
|---|---|---|
| GET | `/preview/projects` | `{projects:[{name,title,format,stage_parse,stage_analyze,has_findings}]}` |
| GET | `/preview/data/<name>` | `{name,title,format,stages,parsed,report,fixqueue,shelf}` |
| GET | `/preview/chat/<name>` | `{session_id, messages}` |
| POST | `/preview/chat/<name>` | `{reply, messages}` (isolated lab session) |
| DELETE | `/preview/chat/<name>` | `{cleared}` |

---

## 10. Data models (summary — see `docs/DATA_FORMATS.md` for full schemas)

- **ScriptDocument** (GET `/script`): `title, author, source_format, parse_confidence,
  scene_count, estimated_page_count, all_characters, front_matter, scenes[], warnings[]`.
  Scene: `scene_number, heading_raw, int_ext, location, time_of_day, page_start, page_end,
  characters_present, elements[]`. Element: `type, text, character, line_start`.
- **report.findings.json**: `title, model_used, coverage, character_reads, logline_test,
  findings[], formatting_findings[], stats, pacing, character_dials, setup_payoff,
  verification_summary, errors`.
- **Session**: `session_id, title, branches{name:{messages[], active_persona, active_mode,
  parent_branch, forked_at_index}}, current_branch, created_at, updated_at`.
- **Message**: `role, content, timestamp, mode, scene_refs, quote?`.
- **Writer memory**: dimensions w/ confidence gates, observations (suppressable), topic
  gravity, meta.

---

## 11. Acceptance checklist (what "built & integrated" means)

- [ ] All screens in §4 exist and render: welcome/dashboard, project desk, manuscript,
      co-write room, feedback room, **Context Dock Evidence lens (§4.4b)**, beat board,
      compare, revision view, idea room, all 5 modals, NOCTA chrome (§4.8). Feedback View
      (§4.4b) and Problem Board (§4.4c) are RETIRED surfaces — their absence is the
      expected state.
- [ ] Every interaction in §7 works: rooms, select-to-ask float, Esc cascade, spotlight,
      focus, river read, reader mode, explore chips, dictation, translation, dawn meter,
      branches, session restore.
- [ ] All keyboard shortcuts in §8 are wired.
- [ ] Every API call in §9 uses the documented paths/verbs/request shapes and handles the
      documented error codes + 408 "still working" watchdog retry.
- [ ] Streaming chat renders token-by-token and falls back to the blocking endpoint on 404.
- [ ] All 5 languages (eng/tenglish/hindi/telugu/tamil) round-trip without mojibake; the
      report language selector drives `/analyze` `report_language`.
- [ ] The status strip never lies: green=real model, amber=demo, red=unreachable; demo-mode
      "your model is back — click to switch" works.
- [ ] Zero external requests: fonts self-hosted, no CDN, no tracking.
- [ ] `prefers-reduced-motion` respected; `:focus-visible` visible everywhere; modals trap
      focus and restore it on close.
- [ ] Dawn (light) theme round-trips with night; `body[data-room]` swaps accents correctly.
- [ ] Dawn meter fills from fix-queue state; dismissed findings show/hide round-trips.
- [ ] Delete flows cascade honestly (confirm copy); unreadable projects flag-don't-drop.
- [ ] Manuscript renders every element type with correct screenplay styling; search
      highlights + hides; inline edit saves/undoes; change stars appear.
- [ ] `localStorage` session/prefs restore correctly; idea page autosave + pagehide flush.

---

## 12. Reference files & implementation notes

- Frontend source of truth: `screenplay_studio/webapp/` — `index.html` (~770 lines, SPA
  shell), `app.js` (~8,530 lines, all client logic), `style.css` (~6,520 lines, full
  design system incl. the NOCTA layer), `tungsten.css` (frozen visual system override,
  night + dawn registers — loads after `style.css`), `core.js` (~96 lines, DOM-free pure helpers:
  `fuzzyScore`, `formatMessageContent`, `truncate`, `formatElapsed`, `fmtDuration`,
  `shortModelId`), plus `fonts/` (self-hosted woff2, Instrument Serif + DM Sans,
  18 `@font-face` declarations) and the Design Lab preview folders
  (`preview-redesigns/`, `preview-next/`, `preview-r4/`).
- Backend: `screenplay_studio/webapp_server.py` (~2,805 lines) — all endpoints in §9.
- Pure helpers must stay DOM-free (unit-tested in `node --test tests/js/`).
- Cache-busting: `index.html` references `style.css?v=<hash>` / `app.js?v=<hash>` /
  `core.js?v=<hash>` — bump the query whenever those files change (no-cache only revalidates
  against the browser's own copy).
- Browser e2e suites (Playwright) live in `tests/e2e_browser_*.py`; any UI change that
  alters an element id/class/flow may need these updated — see `docs/TESTING.md`.
- Deferred UI items (KB browser, genre badge, pipeline progress UI, confidence badges,
  thumbs-up/down, scene cards, character arcs, FDX export, quick analysis, real-time
  feedback) are tracked in `UI_CHANGES_DEFERRED.md` — **out of scope for a rebuild** unless
  explicitly requested.
