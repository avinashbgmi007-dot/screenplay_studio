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

**Display languages:** English, Tenglish, Hindi, Telugu, Tamil (analysis reports and chat
replies can be in these registers; UI chrome stays English).

---

## 2. Design system

### 2.1 Palette (CSS custom properties, `:root`)

The app is a "warm room at night." Night = deep ink-blue void (Spark Wall edition) with the
manuscript as bright cream paper under a lamp. The **room lighting is the signature**: the
Co-write room is warm amber, the Feedback room is cool slate, and the CSS `body[data-room]`
swaps the whole accent ramp.

| Token | Night value | Purpose |
|---|---|---|
| `--ink-950` | `#0a0e1a` | page void background |
| `--ink-900` | `#0e1322` | raised surfaces (bars, panels) |
| `--ink-850` | `#121830` | cards |
| `--ink-800` | `#161d36` | inputs, chips, wells |
| `--ink-700` | `#1d2544` | hover wells |
| `--line` | `#262f52` | borders |
| `--line-soft` | `#1c2340` | faint borders |
| `--paper` | `#f2e8d4` | manuscript paper |
| `--paper-2` | `#ede1c8` | paper gradient top |
| `--paper-ink` | `#2b241b` | text on paper |
| `--paper-muted` | `#6d6050` | muted text on paper |
| `--paper-line` | `#d9ccae` | rules on paper |
| `--lamp` | `#e8a24f` | warm amber accent (Co-write) |
| `--lamp-deep` | `#b06f27` | amber deep |
| `--lamp-bright` | `#f3c07e` | amber bright |
| `--consult` | `#86a6bd` | cool slate accent (Feedback) |
| `--consult-deep` | `#5b7c95` | slate deep |
| `--text` | `#dbe2f4` | primary text on void |
| `--text-muted` | `#8b96b8` | secondary text |
| `--text-faint` | `#5d6b8a` | tertiary/hints |
| `--danger` | `#c96a5a` | errors / high severity |
| `--danger-bg` | `rgba(201,106,90,.14)` | danger chip bg |
| `--ok` | `#8fae7e` | success / addressed |
| `--ok-bg` | `rgba(143,174,126,.14)` | ok chip bg |

Room swap: `body` sets `--accent/--accent-deep/--accent-bright/--glow/--glow-strong` to the
amber values by default; `body[data-room="feedback"]` overrides them to the slate values.
**All interactive/accented UI must read from these variables, never hardcoded colors.**

Dawn (light) theme: `body.dawn` re-overrides the full ramp with warm paper tones
(`rgb(231,223,205)` family). It must round-trip cleanly with the night theme (toggle button
in sidebar + status strip).

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
| `--font-mono` | IBM Plex Mono | labels, meta, timestamps, chips |
| `--font-hand` | Caveat | the writer's own margin notes |

Base: 15px, line-height 1.55, serif default. `body` uses `-webkit-font-smoothing: antialiased`.

### 2.3 Buttons & controls

- `.btn-primary` — amber gradient CTA; disabled at `opacity .55`.
- `.btn-secondary` — ghost bordered button; `.danger` variant red; `.btn-small`; `.icon-btn`.
- `.btn-paper` — paper-toned button on the welcome card.
- `.explore-chip` — pill chip; collapses to lone icon on first typing (see §8.5).
- `:focus-visible` — always a visible ring (`2px solid var(--accent-bright)`).
- `::selection` — amber selection.

### 2.4 Motion & accessibility

- `prefers-reduced-motion: reduce` → all animation/transition durations ≈ 0.
- Breathing lamp glow (`lampBreath`), room panel fade-in, paper settle, welcome card rise —
  all guarded by the reduced-motion rule.
- A full-screen vignette + film-grain overlay (`body::before/::after`, `pointer-events: none`).

---

## 3. App shell & layout

```
┌───────────────────────────┬─────────────────────────────────────────────┐
│  SIDEBAR (shelf)          │  MAIN                                        │
│  brand · connection dot   │  ┌─ project bar: ⌂ | title | branches ─────┐ │
│  + Lay a new page         │  │  room toggle (Co-write|Feedback) · chip · ⌘K │
│  ───────────────────      │  ├─ WORKSPACE (flex, 3 zones) ─────────────┤ │
│  Ideas (flyout)           │  │  [struct rail] [ DESK: script pane ]     │ │
│  On the shelf (flyout)    │  │                            [gutter tabs] │ │
│  Your library (flyout)    │  │  [room drawer — summoned from gutter]    │ │
│  ───────────────────      │  └──────────────────────────────────────────┘ │
│  ☀ Dawn · ⚙ Settings      │  STATUS STRIP: project · model · conn ·      │
└───────────────────────────┘   metrics · sprint · elapsed · Dawn          │
                                └──────────────────────────────────────────┘
```

- `#app` is a full-height flex row: fixed `264px` sidebar + flexible main.
- **The desk** (`#script-pane`) owns the room: full width, the paper centered at
  `max-width: 700px`. The manuscript never shrinks below 50% of the desk.
- **Room drawer** (`#room-drawer`): the partner panel (Sameer / Dr. Sushruta), summoned
  from the right-edge gutter tabs, dismissed by ✕ / Esc / clicking the manuscript. The
  script keeps the room.
- **Structural rail** (`#struct-rail`): collapsible left rail (scenes · characters ·
  the Stash · margin notes + Beat Board / Compare buttons). Edge tab `☰ Structure` reopens.
- **Status strip** (`#status-strip`): thin footer with model/connection/metrics/sprint/dawn.

### 3.1 Responsive behavior
- The structure rail collapses; a thin edge tab restores it.
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
and actions: 📌 Premise (only if a graduated idea carried a premise card), ✳ Focus, Reader,
≋ Flow, ↶ Undo, ↷ Redo, ✎ Revise, 📋 Beat Board, 🗂 Compare, ⬇ Backup .zip, Export
.fountain/.fdx/.txt, Print / Save PDF, Discard edits (danger, only when edits exist).

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
- **Inline editing**: double-click any line → contentEditable → Enter/blur saves via the
  edits/apply path (undoable), Esc cancels.
- **Craft shelf** (`#craft-shelf`): a collapsed-by-default header over the four analysis
  panels that live at the top of the manuscript — Fix queue · Pacing · Characters · Writer's
  Mirror. One click expands; state persisted.
- **Script-level notes bucket**: findings with no scene ref + writer's script-level notes.
- **Select-to-ask float**: select text → floating "✎ Ask Sameer about this" button (plus
  "📥 Stash this" and "📝 Note this line" below it). §8.2.

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
- **Idea context card** (idea mode only): proof Sameer "has your page" — word count +
  show/hide snapshot toggle.
- **Composer** (`#composer`): growing `<textarea>` (auto-resize to ≤160px), quote card slot
  above it, previous-message history popup (ArrowUp/Down), Send button. Enter sends,
  Shift+Enter newline. Mic chip for dictation (§8.6).
- **Explore chips** (idea mode): guided prompts ("Sameer runs with it"), collapse to icons
  on typing.
- Streaming: assistant replies **stream token-by-token** (SSE) into the bubble with an
  elapsed ticker; a 408 watchdog offers a "still working — keep waiting?" retry instead of
  a silent hang.

### 4.4 Feedback room (`#feedback-panel`, in the drawer)

The consultant's desk — "Dr. Sushruta's Report".

- **Header**: "Report in" language select (English/Tenglish/Hindi/Telugu/Tamil), live
  analysis progress chip (bar + % + ETA; hover opens the 17-stage pipeline map), 📥 Report
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
  autotitles from the first line), autosave state ("Saving…"/"Saved"), ▸ Structure toggle
  (logline + open questions behind it), "✦ Grow into pages" (graduate → upload first pages),
  a floating "Sameer" pill to summon the idea chat, and a mic chip. Typing autosaves
  (debounced 1.2s + on blur + `sendBeacon` flush on pagehide); the idea chat is **one idea =
  one session**, lazy-created, with the whole page in context.

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
| **Command palette** | input + fuzzy results (commands · scenes · help); `Ctrl/⌘ K` opens, `?` shows all shortcuts; ↑↓ Enter, Esc closes |
| **Fork** | name the branch → create fork |
| **Sam's notes on you** | writer relationship memory: dimensions, observations list (each with "forget this"), "Refresh now", empty state, Close |

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
  deletes the other); rows also carry hover-reveal ✕.
- **Footer**: ☀ Dawn · ⚙ Settings.

---

## 6. Status strip

Thin footer, left→right:
- `#status-project` — "{project} · {room} · Esc to leave" (Spotlight keeps this lit).
- `#status-model` — model id (not URL), hover card with full state/model/server truth.
- `#status-conn` — "—" / "● demo craft model (built-in)" / "● your model is back — click to
  switch" (in demo mode when the real server returns, one click re-attaches) / connection
  message. Re-checked every 30s.
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
Top-most visible modal closes first; then river-read → Spotlight → Revision view → room
drawer → craft shelf → structure rail → close flyouts.

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
- Session (last project/idea/view/scene) → `localStorage screenplay_studio.session.v1`; a
  reload restores where the writer left off.
- Prefs (dawn, reader, focus, flow, craft_open, hintDismissed, stt lang, pane width) →
  `localStorage screenplay_studio.prefs.v1` (+ `pane-width-v2`, `studio-stt-lang`).
- An unreadable/corrupt project stays visible (flag-don't-drop) with an actionable error.

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
| `a` | Toggle the Craft shelf (analysis panels) |
| `r` | Toggle the Structure rail |
| `z` | Spotlight mode — nothing but the page (Esc leaves) |
| `b` | Open the Beat Board (project only) |
| `d` | Compare drafts side by side (project only) |
| `v` | Toggle the Revision view (project only) |
| `j` / `n` | Next scene (script view) |
| `k` / `p` | Previous scene (script view) |
| `/` | Search the script |
| `?` | Show all shortcuts (palette help) |
| `Esc` | Leave spotlight → dismiss partner drawer → craft shelf → structure rail → modals → flyouts |
| `↑`/`↓` + `Enter` | Palette navigation / run |
| Inline edit: `Enter` save · `Esc` cancel · `Shift+Enter` newline | |
| Composer: `Enter` send · `Shift+Enter` newline · `↑`/`↓` history · `Esc` cancel history | |
| Inline note editor: `Enter` save · `Esc` cancel | |

Idea room: `c`/`f`/`a`/`r` also work (Sameer ↔ Premise Doctor lens). Full-screen tools
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
| POST | `/projects/<name>/backup` *(GET)* | — | `.zip` download |
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
| GET | `/projects/<name>/edits` | — | `{edits, findings_status, can_undo, can_redo}` |
| POST | `/projects/<name>/edits/apply` | `{scene_number, replacements:[{old,new}]}` | `{applied, skipped, scene_text_after, findings_status}` |
| POST | `/projects/<name>/edits/undo` | — | `{..., findings_status}` |
| POST | `/projects/<name>/edits/redo` | — | `{..., findings_status}` |
| POST | `/projects/<name>/edits/reset` | — | `{ok, has_edits}` |
| GET | `/projects/<name>/export` | `?format=fountain|fdx|txt` | file download |
| GET | `/projects/<name>/metrics` | — | `{avg_reply_seconds, analysis_seconds, findings_total, findings_fixed, findings_fixed_pct, discussed}` |

`findings_status` shape: `{findings:[{index, status}], summary:{addressed, still_present,
unknown}}`.

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
`/settings`, `/translate`).

**quote** (select-to-reply): `{scene_number?: int, text: string}`.

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
      co-write room, feedback room, beat board, compare, revision view, idea room, all 5 modals.
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

- Frontend source of truth: `screenplay_studio/webapp/` — `index.html` (SPA shell),
  `app.js` (~5,900 lines, all client logic), `style.css` (~4,300 lines, full design system),
  `core.js` (DOM-free pure helpers: `fuzzyScore`, `formatMessageContent`, `truncate`,
  `formatElapsed`, `fmtDuration`, `shortModelId`).
- Backend: `screenplay_studio/webapp_server.py` (~2,700 lines) — all endpoints in §9.
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
