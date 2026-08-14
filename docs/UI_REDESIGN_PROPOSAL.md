# UI Redesign + Feature Roadmap — Research, Debate, Critique

> Status: proposal for review — **no code changed**. Companion to the live app on `:8522`.
> Date: 2026-08-14 · Scope: writing-software UI research, co-writer vs script-doctor feature debate, front-end UI debate, critique.

---

## Part 0 — The short answer: "Entire redesign — what do you think?"

**Yes to a redesign — but a *reskin + shell restructure*, not a rewrite from zero.**

My honest read after mapping the current app against the market:

- **The engine is the product.** The parse pipeline, analysis report, fix queue, relationship memory, guardrails, select-to-reply — these are the differentiators. The market's weakest area (see Part 1) is exactly where we're already strong.
- **The shell is the liability.** The current UI is a functional single-pane layout wearing a "den" costume (fonts, lamp illustration, dawn/dusk) — but the *information architecture* (IA) is still chat-first, script-second, with modals stacked on modals (settings, rewrite, palette, notes, fork all float over the page). Every writing tool that won writers over (Arc Studio, Highland, WriterDuet) won on **IA and typography**, not decoration.
- **The correct move:** keep every backend feature, rebuild the visual shell around a three-zone layout (Part 3), fix contrast/hierarchy per zone (Dawn already improved — but the structure still needs work), and retire the modal pile for anchored panels.

So: full **visual** redesign, **structural** reorganization of zones, **zero** feature regression. That's the recommendation both debate voices land on in Part 2/3.

---

## Part 1 — Writing-software UI references (categorized, sorted, sourced)

### 1.1 The six UI paradigms in the market, sorted by relevance to us

| # | Paradigm | Tools | Core idea | Relevance to us |
|---|----------|-------|-----------|-----------------|
| 1 | **Page-first linear** | Final Draft, Fade In | The formatted page IS the interface; formatting ribbon on top, script fills the screen | High — we already render per-element screenplay styling; this is our baseline |
| 2 | **Cloud-native collab** | WriterDuet, Arc Studio | Rooms, real-time cursors, comments, drafts sidebar; script center, tools around it | High — our room toggle + branches map here |
| 3 | **Structural-first canvas** | Arc Studio Plot Board, Storyflow, Scrivener corkboard | Story is cards/beats before it's pages; board visible *beside* the script | High — we already have a Beat Board; it's currently a separate full-screen view |
| 4 | **Minimal typographic** | Highland 2, Slugline | Typography is the UI; near-zero chrome, typewriter scroll, fullscreen focus | High — the "writers den" feel we keep chasing lives here |
| 5 | **AI-coverage dashboard** | ScreenplayIQ, ScriptReader.ai, Prescene, Callaia | The report IS the interface: scores, dials, per-facet notes, comparisons | High — this is the Feedback room's home turf |
| 6 | **Production/pre-pro suites** | Celtx, RivetAI | Scheduling, budgets, breakdowns bolted onto the editor | Low — explicitly out of scope |

**The key market insight:** no tool successfully mixes paradigms 1–4 with 5. Final Draft's AI is "bolted on"; WriterDuet's AI lives in a separate product (ScreenplayIQ); Arc Studio's AI is marketing-light. **The tool that wins is the one that lets the script stay center-stage and slides the AI in as a *panel*, not a takeover.** That is precisely the "70% script / 30% room" direction we already committed to — the redesign should double down, not drift back to chat-first.

### 1.2 UI option inventory — what exists in the market, categorized

Legend: ✅ we have it · ➕ worth adding · 🔁 reshape what we have · ✂️ skip (YAGNI)

**A. Shell & layout**
- ✅ Left rail (projects / "shelf") — ours is good; Arc Studio/WriterDuet keep this thin
- ✅ Top project bar with room toggle — reshape into a *contextual* bar (Part 3)
- ➕ **Right inspector panel that docks, doesn't float** — Arc Studio's Notes/Stash live in a sidebar, never modals
- ➕ **Collapsible left outline pane** (scene list with page numbers) — Arc Studio "Outline view", Final Draft Navigator
- ✂️ Ribbon toolbars (Final Draft) — dated; we keep a minimal toolbar

**B. Navigation**
- ✅ Script search (character/prop/line) — ours exists
- ✅ Command palette (Ctrl+K) — ours exists; extend to all actions
- ✅ `j`/`k` scene navigation — ours exists
- ➕ **Scene list with page anchors** (click heading → jump to page) — Final Draft Navigator, Arc Studio outline
- ➕ **Mini-map / progress bar of script length per act** — ScreenplayIQ's visual supports

**C. Script canvas**
- ✅ Per-element styling (character centered, dialogue indented, transitions right) — ours is correct post-parse-fix
- ➕ **Typewriter scrolling + focus mode** (grey everything but the current line) — Highland 2's signature; cheap to add, huge mood win
- ➕ **Change marks ("stars") in the right margin** — Arc Studio's most-praised feature (auto-track changes, show asterisk per edited line, toggle per draft)
- 🔁 **Read-only display → light editing** (fix typos inline, undo/redo already exist) — currently the script pane is a viewer; editing exists in drafts but the pane should at least support in-line note anchors
- ✂️ Page-number rulers, production markup — out of scope

**D. Structural tools**
- ✅ Beat Board (drag reorder, print cards, export) — exists but is a separate full-screen view; **reshape into a dockable board beside the script** (Arc Studio keeps beats visible in the same window as writing)
- ➕ **The Stash** — Arc Studio's scrapbook: highlight a line, "stash" it to a right sidebar (title + editable), drag it back into the script later. This is a top-3 loved feature in Arc Studio and maps perfectly to our margin-notes DNA
- ➕ **Notes-as-wiki** (categorized notes, links between them, beside the script) — Arc Studio; replaces the pile of modal-based note taking

**E. Collaboration & review**
- ✅ Drafts list + upload + compare side-by-side — we have it
- ➕ **Change tracking with stars** (see C) — makes compare *continuous* instead of on-demand
- ➕ **Anchored margin comments** (Google-Docs-style, line-anchored) — both Sam (co-write) and the consultant (feedback) post notes here; our select-to-reply is the seed of this
- ✂️ Real-time multi-cursor (WriterDuet Pro) — not our lane (single user, local)

**F. AI surfaces**
- ✅ Co-write chat room (Sam) with select-to-reply
- ✅ Feedback room: report + fix queue + rewrite candidates
- ✅ Relationship memory ("Sam's notes on you")
- ➕ **Character dials** — ScreenplayIQ's killer feature: "Did you intend your protagonist to be devious? You can adjust the dials" — per-character trait sliders derived from the analysis, with *quoted evidence lines*; we have the character analysis, we lack the visualization
- ➕ **Logline generator** (Vondy/coverage tools all ship one; it's a top "annoyance removed" feature)
- ➕ **Pacing/act visual graph** (page counts per act with tension curve) — ScreenplayIQ-style visuals
- ✂️ Comps ("Inception meets The Insider"), cast suggestions, market insights — business-facing; not the writer's productivity lane

**G. Writing-mood & environment**
- ✅ Dawn/Dusk themes (improved contrast)
- ✅ Room metaphor copy ("The lamp's on", "Put the pages on the desk")
- ➕ **Fullscreen focus ("just the page")** — Highland's fullscreen; one keystroke
- ➕ **Typewriter scroll** (C)
- ➕ **Sprint timer / session timer** — Highland's sprint timer; pairs with our elapsed tickers
- ✂️ Background music/ambience players — gimmick risk; skip unless wanted

### 1.3 Placeholder positions — the map (where ghost text lives, what it says)

The market pattern: **placeholders live exactly where the user's next action is** — at the cursor, in the search, at the drop, in the empty state. Never in the way.

| Zone | Element | Current placeholder | Recommended |
|------|---------|---------------------|-------------|
| Welcome | Dropzone | "Lay a manuscript here — .fdx .pdf .txt .fountain .md" | Keep (best copy in the app). Add a subtle "your story stays on this machine" reassurance line |
| Top bar | Project search | — (none) | Add command-palette-triggered "Search scenes, characters, props, notes…" |
| Script pane | Script search | "Search the script… (e.g. a character, a prop, a line)" | Trim to "Search the script…" — example belongs in the empty state, not the placeholder |
| Script pane | Empty state | — | "The page is blank. Start typing — or ask Sam to sketch the next scene." |
| Co-write | Composer | "Ask about a scene, a character, a note in the margins…" | Split behavior: default "Talk to Sam…"; when a selection exists "Reply to Sam about this selection…" (context-aware placeholder = the ChatGPT pattern users expect) |
| Co-write | History pop (↑) | "Previous messages" | Keep; add "↑ to resume an earlier thought" hint |
| Co-write | Empty chat state | — | "Sam is listening. Start anywhere — a scene, a character, a doubt." |
| Feedback | Report empty | "No analysis yet — Run Analysis to get the consultant's report." | Keep; add what the report will cover (3-line preview list) |
| Feedback | Report language | "English / Tenglish / Hindi / Tamil" | Keep |
| Sidebar | Empty shelf | "The shelf is empty — bring in a screenplay." | Keep (on-brand) |
| Sidebar | New project | "+ Lay a new page on the desk" | Keep |
| Sam notes | Empty | "Nothing yet — Sam is still getting to know you…" | Keep; add an example observation so the user learns what Sam *will* learn |
| Rewrite modal | Instruction | "e.g. make this less on-the-nose, keep her voice, tighten it" | Keep; add a second line "…or leave blank for Sam's best pass" |
| Palette | Input | "Type a command, a scene, a shortcut…" | Keep; add recent items below the input (Recency = productivity) |

**Rule for all placeholders:** one example maximum, never a paragraph; the empty state carries the teaching, the placeholder carries the invitation.

### 1.4 Site references (primary sources used)

- **Final Draft** — https://www.finaldraft.com/ (industry-standard FDX, dated UI, AI bolted on)
- **Fade In** — https://fadeinpro.com/ (one-time purchase, full feature parity, dated interface)
- **WriterDuet / ScreenplayIQ** — https://www.writerduet.com/ , https://screenplayiq.com/ (cloud-native collab; AI coverage with character dials, no scores)
- **Arc Studio Pro** — https://www.arcstudiopro.com/ ; favorite-features walkthrough: https://www.arcstudiopro.com/blog/my-favorite-arc-studio-features-as-a-pro-screenwriter (Stash, auto change-marks/stars, drafts beside script, Notes wiki, Plot Board beside the script)
- **Arc Studio Plot Board guide** — https://help.arcstudiopro.com/guides/the-plot-board
- **Highland 2 / Pro** — https://quoteunquoteapps.com/highland-pro/ (minimal typographic UI, fullscreen, typewriter scroll, sprint timer); review: https://screenplayreaders.com/screenwriting-app-highland-review/
- **Scrivener** — https://www.literatureandlatte.com/scrivener/overview (corkboard/binder; UI crowded — the cautionary tale)
- **Celtx** — https://www.celtx.com/ (browser collab + pre-production)
- **Storyflow** — https://storyflow.so/blog/best-final-draft-alternatives-2026 (2026 market comparison; structural canvas paradigm)
- **Trelby / KIT Scenarist** — https://www.trelby.org/ , https://www.kitscenarist.com/ (open-source reference for structure + stats)
- **AI coverage landscape** — https://scriptation.com/blog/best-ai-script-coverage-feedback-analysis/ (ScreenplayIQ, Prescene, Slated, Callaia, RivetAI, Scriptreader.AI, Premium Screenplay, Vondy, Greenlight Coverage)
- **ScriptReader.ai** — https://scriptreader.ai/ (scores per facet, coverage in minutes)
- **Prescene** — https://prescene.ai/ (ask questions of your screenplay; Paradigm cut coverage time >95%)
- **Screenwriting software comparison** — https://www.scriptreaderpro.com/screenwriting-software/

---

## Part 2 — The feature debate: Co-writer vs Script Doctor

Two advocates, one goal: **the few features that give a writer ~90% of the productivity gain, from both rooms.** They argue in rounds and must converge. (Note: no subagents available this session — I ran both positions with full codebase context.)

### Round 1 — The Co-writer advocate (Sam's case)

> "My job is to keep the writer **in flow**. The enemy is friction: switching apps, reformatting thoughts, waiting, re-explaining context. Every feature I fight for must (a) trigger from inside the script, (b) never block the writing, and (c) get smarter about *this writer* over time. I concede I'm bad at objectivity — that's the doctor's job."

1. **Selection-aware everything** (✅ select-to-reply exists — extend it): the single highest-leverage interaction in the app. Selecting text + replying removes 100% of "which part do you mean" overhead. Extend: selection → "stash", selection → "ask for a rewrite", selection → "check continuity here".
2. **Standing script context** (✅ script map exists — deepen it): Sam already carries scene headings + character presence. Make it richer (per-scene beats once analysis is done) so answers are specific without the writer naming scenes.
3. **Never-interrupt protocol** (✅ guardrails exist): probe before advising, forward-momentum nudges, no unsolicited rewrites. This is the trust contract — without it, none of the other features matter. **Non-negotiable.**
4. **Relationship memory** (✅ exists — keep growing): the writer's working style (options vs thinking-partner), tone, callbacks. It's the *human* co-writer differentiator.
5. **The Stash** (➕ from Arc Studio): writers constantly lose good lines to bad drafts. A drag-in/drag-out scrapbook is pure flow-preservation.
6. **In-line light editing** (➕): fix a typo / tweak a line in the pane without leaving the page; Undo/Redo already exist.

### Round 1 — The Script Doctor advocate (the consultant's case)

> "My job is **objective truth the writer can act on**. Sam keeps them company; I keep them honest. The enemy is *unactionable opinion* — 'pacing feels slow' without page numbers, 'character is weak' without quotes. Every feature I fight for must (a) cite evidence from the page, (b) rank by impact, and (c) end in an action the writer can take in one click. I concede I'm cold — that's the point."

1. **Evidence-anchored report** (✅ report exists — deepen): every finding quotes the exact lines (we already do post-parse-fix). Add per-finding *severity + page/scene*.
2. **Prioritized Fix Queue with one-click apply** (✅ fixqueue + rewrite modal exist — this is the crown jewel): "Fix this" → generated candidates → apply → Undo. That loop is the productivity multiplier.
3. **Character dials** (➕ ScreenplayIQ): per-character trait sliders from the analysis with quoted evidence. Turns "your protagonist reads differently than you intended" from an insult into a dial.
4. **Continuity & consistency checks** (➕): character-voice drift, prop/scene/continuity errors, timeline holes. Highest *trust* feature — when it's right, the writer trusts everything else.
5. **Pacing & act structure graph** (➕): page counts per act, tension curve, where Act 2 sags. The single most-requested objective visual.
6. **Logline generator** (➕): coverage tools all ship it; writers dread writing it; trivial with our analysis.

### Round 2 — Rebuttals (the tension)

- **Co-writer → Doctor:** "A fix queue is a *to-do list*. Writers don't finish scripts by doing to-dos; they finish by staying in the story. If the doctor's features pull the writer out of the page, they cost more than they save."
- **Doctor → Co-writer:** "A cozy chat that never tells you your Act 2 is 40 pages of wheel-spinning is *flattery*, not partnership. Sam without evidence is a rubber duck. The 'flow' you protect is sometimes just comfortable procrastination."
- **Co-writer:** "Accepted — but the evidence must arrive *in the room*, not as a verdict. Anchored margin notes (doctor's findings pinned to the exact line) let the writer absorb hard truths without leaving the page."
- **Doctor:** "Accepted — and the fix queue should be *generative*, not bureaucratic: each item opens the rewrite modal directly. Diagnosis and remedy in one motion."

### Round 3 — Convergence: the agreed feature set

**Thesis:** the overlap zone is **"continuous, evidence-anchored, non-blocking assistance with one-click apply, living in panels beside the page."** Everything below serves both rooms.

| # | Feature | Co-writer value | Doctor value | Status |
|---|---------|-----------------|--------------|--------|
| 1 | **Selection-aware actions** (reply / rewrite / check-continuity / stash from a selection) | Flow: no re-explaining context | Precision: findings tied to exact lines | ➕ extend (reply ✅) |
| 2 | **Anchored margin notes** (Google-Docs-style) | Sam's comments pin to lines, stay out of the way | Findings pin to lines with severity color | ➕ new (seed: select-to-reply) |
| 3 | **Fix Queue → one-click rewrite loop** (diagnosis + remedy in one motion) | Rewrites drafted *in Sam's voice* on request | The actionable core of coverage | ✅ exists, ➕ deepen |
| 4 | **Character dials + consistency checks** | Sam references traits conversationally | Objective character/voice/continuity truth | ➕ new (analysis exists) |
| 5 | **Pacing/act graph** | Sam talks about rhythm with real numbers | The classic coverage visual | ➕ new |
| 6 | **The Stash** | Flow-preservation | Keeps cut material for later drafts | ➕ new |
| 7 | **Never-interrupt protocol** (probe-first, no unsolicited rewrites) | The trust contract | Keeps feedback from feeling like a verdict | ✅ exists |
| 8 | **Relationship memory** (working style, tone, callbacks) | The human differentiator | Doctor persona can *also* learn how direct to be | ✅ exists |

**Productivity math (the 90% claim):** the biggest time sinks in professional writing are (a) explaining context, (b) waiting, (c) searching for cut material, (d) absorbing unfocused notes, (e) re-reading to find *what* the note meant. Items 1–2 kill (a)+(e); 3 kills (b)+(d); 6 kills (c); 4–5 make notes *specific* so a single pass sticks. That combination, not any single feature, is the 90%.

---

## Part 3 — The UI debate: what should it look like?

Same two voices, now arguing about the **shell**.

### Round 1 — Co-writer UI advocate

> "The room is a **writer's den at night** — the page is the lamp-lit desk, everything else is shadow. The script is center and it is *huge*. Sam is not a dashboard; he's the person in the chair opposite. So: minimal chrome, warm paper tones, the chat as a *narrow* side column (like a messaging pane, not a window), collapsible to a whisper. Placeholders whisper ('Talk to Sam…'). Mood: typewriter scroll, focus mode, sprint timer. The script must *never* shrink below half the screen."

### Round 1 — Script Doctor UI advocate

> "The room is a **consulting office** — the report is the diagnosis on the desk, the script is the chart on the wall. The Feedback panel must read like a coverage document: **evidence left, verdict right, action bottom**. Tabs, severity chips, graphs. This is a *work* surface; it needs density, contrast, and structure — a cozy chat column can't hold a 40-finding report. Also: the two rooms currently share one chat-shaped panel; the report needs a fundamentally different layout than the conversation."

### Round 2 — Rebuttals & resolution

- The doctor's core objection is correct: **the Feedback room shouldn't reuse the chat-panel shape.** A report is a document, not a conversation.
- The co-writer's core objection is correct: **the script must never shrink below half the screen**, and the chat should feel like a pane, not a page.
- **Resolution — one shell, two room-layouts:**

```
┌──────────────────────────────────────────────────────────────────────┐
│  Top bar:  ▸ project title · branch · [Co-write | Feedback] · ⌘K     │
├────────────┬─────────────────────────────────────┬───────────────────┤
│  Left rail │        THE SCRIPT (never < 50%)     │  Right panel      │
│  (collaps.) │  scene list · page anchors         │  (docks, no modal)│
│            │                                     │                   │
│  · scenes   │  formatted page, typewriter scroll  │  CO-WRITE:        │
│  · beats    │  margin notes pinned right edge     │  Sam (chat pane,  │
│  · stash    │  change-mark stars in margin        │  narrow)          │
│  · notes    │                                     │  FEEDBACK:        │
│            │                                     │  report doc with  │
│            │                                     │  tabs, severity,  │
│            │                                     │  graphs, fix list │
├────────────┴─────────────────────────────────────┴───────────────────┤
│  Status strip: model · connection · elapsed · dawn/dusk · focus mode  │
└──────────────────────────────────────────────────────────────────────┘
```

- **One page, three zones.** Left rail = structure (scenes/beats/stash/notes, collapsible to icons). Center = the script, always. Right panel = *the room*, and the room **switches layout with its persona**: Co-write renders as a narrow messaging pane; Feedback renders as a document with tabs (Report / Fix Queue / Continuity / Pacing) + anchored finding chips.
- **Panels, not modals:** settings, rewrite, palette, and Sam's notes move out of floating overlays into docked panels or command-palette results. (Palette stays a modal — that's its job.)
- **Placeholders (from 1.3) contextualize:** the composer's placeholder changes with selection; the feedback empty-state previews the report's contents.
- **Look:** keep the den metaphor but make typography do the work — Courier Prime for the page, a clean humanist sans for UI labels, IBM Plex Mono for data. Dawn = paper/sand with real contrast (already improved); Dusk = deep ink with the lamp glow. Beat board docks beside the script instead of replacing it.

**Agreed UI priorities (sorted by impact on the writer):**
1. Script never < 50%, dockable right room-panel (kills the chat-takeover class of bugs permanently)
2. Room-persona layouts: chat pane vs report document (kills "feedback looks like chat")
3. Left structural rail: scenes + beats + stash + notes (kills modal pile, adds Arc Studio's Stash)
4. Anchored margin notes with severity color (the two rooms finally share the page)
5. Typewriter scroll + focus mode + sprint timer (the "den" becomes real)
6. Status strip (model/connection/elapsed visible always — no more mystery 400s)

---

## Part 4 — Critique (the self-critique you asked for)

### On the redesign idea itself
- **Strong:** the three-zone shell is where the whole market converged (Arc Studio, WriterDuet, Highland); it fixes real current pains (chat takeover, modal pile, report-as-chat). Typography-led design is the proven path for *writing* software.
- **Risk 1 — scope creep:** this is a full shell rebuild touching index.html/app.js/style.css at once. Mitigation: ship in phases (P0: zones + layout; P1: room layouts; P2: rail + stash + margin notes; P3: mood features). Each phase is independently verifiable in Thorium.
- **Risk 2 — the "den" can become kitsch:** every decorative element (lamp, window, stars) must earn its place; if it doesn't aid focus it's noise. Highland's lesson: restraint IS the aesthetic.
- **Risk 3 — editing in the pane:** light inline editing raises parse-sync risk (the exact class of bug we just fixed with working.json self-heal). Must go through the same revision pipeline with self-heal — do last, not first.
- **Cut (YAGNI):** ambient music, real-time multi-cursor, production/pre-pro features, market insights, cast suggestions. None move the solo writer's productivity needle.

### On the feature debate
- **Strong:** the convergence thesis (evidence-anchored, non-blocking, one-click apply) is genuinely the overlap zone — both voices defend it from their own priorities, which is the strongest kind of agreement.
- **Weakness:** "90%" is a persuasion number, not a measurement. The honest claim: items 1–3 remove the four biggest time sinks (context re-explaining, waiting, unfocused notes, hunting cut material). We should **instrument** it — after the redesign, measure time-from-question-to-answer and findings-per-fix-queue-item — rather than assert it.
- **Weakness:** continuity checks (item 4) are the hardest to make trustworthy; a wrong "continuity error" destroys trust in everything. Ship it *after* character dials, with a confidence threshold and a "wrong — forget" affordance (same pattern as relationship memory).

### On the UI debate
- **Strong:** splitting room layouts by persona is the single best idea in this doc — it fixes the deepest current confusion (why does the consultant's report look like a chat?) with one structural change.
- **Weakness:** two layouts mean two code paths in the right panel; keep the shared shell (header/tabs/scroll container) and swap only the body. Otherwise we rebuild the modal pile in a new shape.
- **Weakness:** the status strip risks becoming a second toolbar. Keep it one thin line, hover-reveal details.

### Final verdict
Proceed — but as **Phase 0: the three-zone shell with script-first sizing and docked room panels**, then re-verify with you before P1. Everything in this doc is designed to be implemented incrementally without touching the engine.

---

## Appendix — Full site reference list

1. https://www.finaldraft.com/
2. https://fadeinpro.com/
3. https://www.writerduet.com/
4. https://screenplayiq.com/
5. https://www.arcstudiopro.com/
6. https://www.arcstudiopro.com/blog/my-favorite-arc-studio-features-as-a-pro-screenwriter
7. https://help.arcstudiopro.com/guides/the-plot-board
8. https://quoteunquoteapps.com/highland-pro/
9. https://screenplayreaders.com/screenwriting-app-highland-review/
10. https://www.literatureandlatte.com/scrivener/overview
11. https://www.celtx.com/
12. https://storyflow.so/blog/best-final-draft-alternatives-2026
13. https://www.trelby.org/
14. https://www.kitscenarist.com/
15. https://scriptation.com/blog/best-ai-script-coverage-feedback-analysis/
16. https://scriptreader.ai/
17. https://prescene.ai/
18. https://www.scriptreaderpro.com/screenwriting-software/
