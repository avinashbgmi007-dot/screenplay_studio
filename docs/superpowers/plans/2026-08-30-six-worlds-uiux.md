# Six Worlds UIUX (v4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build six self-contained, interactive full-journey UIUX worlds + a gallery in `screenplay_studio/webapp/preview-next/`, per the approved spec `docs/superpowers/specs/2026-08-30-v4-six-worlds-uiux-design.md`.

**Architecture:** Three full-screen rooms per world (Script Desk / Co-write Room / Feedback Room) switched by a per-world navigation idiom; a shared `_payload.js` supplies identical demo content to all six; a dismissible review bar exposes room jumps, a feedback-lifecycle toggle (empty/running/complete), and the gallery link. Worlds are single HTML files with inline CSS/JS; no server, no build step.

**Tech Stack:** Plain HTML/CSS/JS (no framework, no CDN, no build). System font stacks only. Playwright (existing `tests/e2e_browser_common.py` scaffolding) for the browser walk. Flask webapp server (existing) serves the folder — zero server changes.

**Branch:** `zAI` (implementation continues on this branch — the repo's working branch).

## Global Constraints (verbatim from spec §3/§4 — binding on every task)

- Zero external dependencies: no CDN fonts, no libraries, no network requests. (v2/v3 previews used Google Fonts — v4 deliberately does NOT.)
- WCAG AA: 4.5:1 body text, 3:1 large text and UI components. Body ≥16px, captions ≥12px, touch targets ≥44px.
- Visible `:focus-visible` rings; hover + focus states on everything clickable.
- SVG icons only — no emoji-as-icons, no emoji as design elements.
- `prefers-reduced-motion` respected (motion collapses to instant state changes).
- Deliberate named font stacks per role; a bare `system-ui`/`-apple-system` default is a fail.
- AI-slop blacklist: no purple/violet gradient defaults, no 3-column icon-in-circle grids, no centered-everything, no uniform bubbly border-radius, no colored left-border cards, no generic hero copy.
- Desktop-first at 1440×900; graceful (not finalized) at narrower widths.
- All six worlds share the SAME payload (one `_payload.js`) — same content, different presentation.
- Every world wires the 12-point contract (spec §4): 3 full-screen rooms, script desk default landing, feedback lifecycle (empty/running/complete) via review bar, click-outside + Esc dismiss floats (topmost first), chips tuck-away in every chat surface that has chips, growing composer, 6 required screens, P1/P2/REP feature placement (spec §6), quality gates, aesthetic spread, cross-room bridges (Locate → Script Desk at the exact scene with a visual flash; Discuss → Co-write with the finding's quote pre-filled as a quote card), honesty of static scope.

## File Structure

```
screenplay_studio/webapp/preview-next/
├── _payload.js         Task 1 — shared demo payload (window.PAYLOAD)
├── index.html          Task 2 — gallery (6 cards)
├── ledger.html         Task 3 — The Ledger (light editorial; masthead nav)
├── midnight.html       Task 4 — The Midnight Desk (dark; brass tabs nav)
├── screening.html      Task 5 — The Screening Room (dark; film-strip scrubber nav)
├── quarterly.html      Task 6 — The Quarterly (light; contents-spine nav)
├── terminal.html       Task 7 — The Terminal (wildcard; buffer tabs + :commands nav)
└── studio-wall.html    Task 8 — The Studio Wall (warm wildcard; wall-panning nav)
tests/e2e_browser_preview_next.py   Task 10 — browser walk suite
NOTES.md                            Task 9 — contract audit record
preview_shots/preview-next/         Task 11 — verification screenshots
```

**Deliberate deviation from the writing-plans "repeat code per task" rule:** the shared interaction JavaScript is written ONCE in the "Shared Interaction Patterns" section below. Every world task inlines it verbatim. The pattern block lives in this plan (which every implementer reads in full), and the duplication across world files is intentional — each page must stay self-contained. Do not extract it into another file; the spec's file layout is fixed at 8 files.

---

## Shared Interaction Patterns (inline verbatim into every world)

All worlds use the same skeleton: fixed review bar (`#pv`), three room sections (`[data-room="desk"|"cowrite"|"feedback"]`), plus journey screens (`[data-screen="shelf"|"upload"|"idea"]` managed by the same switcher — exactly one visible at a time via `.active`). The Script Desk is the default `.active` after a project opens.

```js
// ===== shared state + switcher =====
const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => [...(r || document).querySelectorAll(s)];
let FEEDBACK_STATE = "complete"; // "empty" | "running" | "complete"

function show(id) {                 // exactly one surface visible
  $$("[data-room],[data-screen]").forEach(el =>
    el.classList.toggle("active", el.dataset.room === id || el.dataset.screen === id));
  $$("#pv [data-go]").forEach(b => b.classList.toggle("on", b.dataset.go === id));
}

// ===== feedback lifecycle (contract pt 2) =====
function renderFeedback() {
  const empty = $('[data-state="empty"]'), running = $('[data-state="running"]'),
        complete = $('[data-state="complete"]');
  [empty, running, complete].forEach(el => el && (el.style.display = "none"));
  const el = $(`[data-state="${FEEDBACK_STATE}"]`);
  if (el) el.style.display = "";
}

// ===== cross-room bridges (contract pt 11) =====
function locateFinding(f) {         // Feedback → Script Desk at the exact scene
  show("desk");
  const page = $(`[data-scene="${f.scene}"]`);
  if (page) {
    $$(".flash-target").forEach(e => e.classList.remove("flash-target"));
    page.classList.add("flash-target");
    page.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "instant" : "smooth", block: "start" });
    setTimeout(() => page.classList.remove("flash-target"), 1600);
  }
}
function discussFinding(f) {        // Feedback → Co-write with quote card pre-filled
  show("cowrite");
  const card = $("#quote-card");
  card.hidden = false;
  $("#quote-text").textContent = f.quote;
  $("#quote-src").textContent = `Finding — ${f.category} · Scene ${f.scene}`;
  $("#input").focus();
}

// ===== growing composer (contract pt 6) =====
function growComposer(ta) {
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
}

// ===== chips tuck-away (contract pt 5) — required in idea room =====
function wireChips(surface, chipRow) {   // surface = textarea/input, chipRow = .chips container
  const chips = $$(".chip", chipRow);
  surface.addEventListener("input", () => {
    const collapsed = surface.value.length > 0;
    chipRow.classList.toggle("tucked", collapsed);
  });
  chips.forEach(c => c.addEventListener("mouseenter", () => {
    if (chipRow.classList.contains("tucked")) chipRow.classList.add("peeking");
  }));
  chipRow.addEventListener("mouseleave", () => chipRow.classList.remove("peeking"));
}
/* chips CSS contract (per-world palette): .chips.tucked .chip {width:40px} (icon only,
   label span hidden, row becomes a vertical rail via flex-direction:column);
   .chips.tucked.peeking .chip {width:auto} (hover reveals that one label);
   clearing the input removes .tucked — chips restore. */

// ===== click-outside + Esc dismissal (contract pt 4) =====
function wireFloatDismiss(closeFn, floatEl) {
  document.addEventListener("mousedown", e => {
    if (!floatEl.hidden && !floatEl.contains(e.target)) closeFn();
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeFn();   // topmost float wins: only one float open at a time
  });
}
function closeQuote() { $("#quote-card").hidden = true; }

// ===== review bar (demo-only, dismissible) =====
function wireReviewBar() {
  $$("#pv [data-go]").forEach(b => b.addEventListener("click", () => show(b.dataset.go)));
  $$("#pv [data-fb]").forEach(b => b.addEventListener("click", () => {
    FEEDBACK_STATE = b.dataset.fb; renderFeedback();
    $$("#pv [data-fb]").forEach(x => x.classList.toggle("on", x === b));
  }));
  $("#pv-close").addEventListener("click", () => $("#pv").remove());
}

// ===== boot =====
window.PAYLOAD; // <script src="_payload.js"> loads before the world's inline script
```

Every world's inline script: `wireReviewBar(); show("shelf");` on load (journey starts at the shelf; clicking the script on the shelf runs the **upload moment** → `show("desk")`).

---

### Task 1: Shared demo payload — `_payload.js`

**Files:**
- Create: `screenplay_studio/webapp/preview-next/_payload.js`

**Interfaces:**
- Consumes: nothing
- Produces: `window.PAYLOAD = { project, script, findings, coverage, pacing, dials, ledger, reads }` — every world and the gallery read only these keys. `findings[n] = {id, severity: "high"|"medium"|"low", category, note, quote, scene (1-4), verified: bool}`. `dials[n] = {character, poles: {proactive, warm, articulate, emotional, grounded} (1-10), scenes: [..]}`. `ledger[n] = {setup, kind, setup_scene, status: "paid"|"dangling"|"abandoned"|"red_herring", note}`. `pacing[n] = {scene, density, action_share, pace, drag: bool}`.

- [ ] **Step 1: Write `_payload.js`** — "The Second Shift", 4 scenes, mixed English/Tenglish, characters MEERA (night-shift nurse), VIKRAM (her brother), AMMA (mother), RAO GARU (comatose patient):

```js
// _payload.js — shared demo content for all six preview-next worlds (design artifact;
// not wired to any backend). Same data everywhere so the comparison isolates design.
window.PAYLOAD = {
  project: { title: "The Second Shift", author: "A. Writer", format: "fountain",
             scenes: 4, pages: 9.5, analyzed: true },

  script: [
    { n: 1, slug: "INT. CITY HOSPITAL - WARD 3 - NIGHT", int_ext: "INT", time: "NIGHT", page: "1-2.5",
      elements: [
        ["action", "Rain hammers the windows. MEERA (32), badge LATCHA-NURSE, works the row of beds with a torch she doesn't need — she knows this ward blind."],
        ["dialogue", "AMMA", "Tiffin pettanu. Tinu, ayite night duty lo tiyyalsina avasaram ledu."],
        ["parenthetical", "(in Telugu; subtitled)"],
        ["dialogue", "MEERA", "Amma, two minutes. Sister will catch me."],
        ["action", "She takes the box anyway. It is warm. That undoes her a little."],
        ["dialogue", "MEERA (CONT'D)", "I'll eat. Promise. Nenu vasthanu."],
        ["action", "At the last bed, RAO GARU lies exactly as he has for 61 days. She checks his chart, writes nothing, moves on."],
        ["transition", "CUT TO:"]] },
    { n: 2, slug: "INT. CITY HOSPITAL - NURSES STATION - CONTINUOUS", int_ext: "INT", time: "NIGHT", page: "2.5-5",
      elements: [
        ["action", "The station at 2 AM: three cold coffees, one ringing phone nobody answers. MEERA files charts. VIKRAM (38), rain-soaked, stands on the wrong side of the counter holding an envelope like evidence."],
        ["dialogue", "VIKRAM", "Complaint file chesanu. Managing trustee ki direct ga. Copy ikkada."],
        ["action", "He slides the envelope across. She doesn't touch it."],
        ["dialogue", "MEERA", "Hospital rules are rules, Vikram. Visiting hours end at nine."],
        ["dialogue", "VIKRAM", "Rules. Adhi nuvvu chepputunnava? Idigo raatri pandupu —"],
        ["action", "He empties the envelope: photographs of the ward, taken through the gate, nights. She scans them too fast to have read them."],
        ["dialogue", "VIKRAM (CONT'D)", "Evaru choosina ninnu choosaru. Nenu matrame kadhu."],
        ["action", "The phone stops ringing. Nobody has answered it. This is the longest silence in the script."],
        ["transition", "MATCH CUT TO:"]] },
    { n: 3, slug: "INT. CITY HOSPITAL - WARD 3 - LATER THAT NIGHT", int_ext: "INT", time: "NIGHT", page: "5-7.5",
      elements: [
        ["action", "Meera's torch beam finds Rao Garu's window — the glass dark, the ward beyond it darker. She unlocks his bed rail."],
        ["dialogue", "MEERA", "(under her breath) Kasi kasi mandhu okate rhythm lo padutundi... kaani Ee song ki."],
        ["action", "She sings — low, half-spoken, a lullaby their mother sang. And Rao Garu's finger curls. Once. Deliberate."],
        ["action", "In the doorway, unlit: VIKRAM. He has seen it. He does not move."],
        ["dialogue", "VIKRAM", "Idhi... complaints book lo ledu."],
        ["action", "Meera stands very still. The song is over. Neither of them closes the door."]] },
    { n: 4, slug: "EXT. CITY HOSPITAL - AMBULANCE BAY - DAWN", int_ext: "EXT", time: "DAWN", page: "7.5-9.5",
      elements: [
        ["action", "The city lights thin out. VIKRAM waits by the ambulance bay. MEERA comes out, badge turned backwards."],
        ["dialogue", "VIKRAM", "Ninnu suspend chestaru."],
        ["dialogue", "MEERA", "Suspend aithe patient lepotadu."],
        ["dialogue", "AMMA", "(from the shadows, holding the empty tiffin) Iddaru intiki. Ippudu."],
        ["action", "Amma walks. They follow. Nobody has won. The complaint envelope stays in Vikram's pocket, dry now."]] }] },

  findings: [
    { id: 1, severity: "high", category: "structure", scene: 3,
      note: "The discovery — the script's only true surprise — arrives at scene 3 of 4. Everything before it is setup; everything after is one scene. The midpoint owns the story and the back half doesn't push back.",
      quote: "And Rao Garu's finger curls. Once. Deliberate.", verified: true },
    { id: 2, severity: "high", category: "dialogue", scene: 2,
      note: "Vikram shifts register mid-scene: legal-brief Tenglish in one line, wounded intimacy two lines later. It reads as two characters, not one man cracking.",
      quote: "Rules. Adhi nuvvu chepputunnava? Idigo raatri pandupu —", verified: true },
    { id: 3, severity: "high", category: "scene_function", scene: 2,
      note: "Scene 2 has motion but no want and no obstacle — Meera receives information and changes nothing. The scene stalls; the phone that nobody answers is the scene telling you so.",
      quote: "The phone stops ringing. Nobody has answered it.", verified: true },
    { id: 4, severity: "medium", category: "plot_thread", scene: 1,
      note: "The warm tiffin is planted as Meera's one soft spot — then vanishes. If it returns at dawn it's the emotional spine; right now it's a prop.",
      quote: "She takes the box anyway. It is warm.", verified: true },
    { id: 5, severity: "medium", category: "character", scene: 4,
      note: "Amma settles the standoff in one line from off-frame. A decisive mother is a great engine — but she needs one earlier beat so the turn isn't borrowed from nowhere.",
      quote: "(from the shadows, holding the empty tiffin) Iddaru intiki. Ippudu.", verified: true },
    { id: 6, severity: "medium", category: "subtext", scene: 2,
      note: "On the nose: Meera states the theme instead of defending it. Let her justify with a detail (a patient's name, a shift count) and the line does the arguing itself.",
      quote: "Hospital rules are rules, Vikram. Visiting hours end at nine.", verified: true },
    { id: 7, severity: "medium", category: "continuity", scene: 4,
      note: "Time-of-day flips NIGHT to DAWN with no LATER/SUPER marker. The checker flags it; the reader feels it without knowing why.",
      quote: "EXT. CITY HOSPITAL - AMBULANCE BAY - DAWN", verified: true },
    { id: 8, severity: "low", category: "plot_thread", scene: 3,
      note: "Rao Garu's finger moves once — an un-earned miracle if nothing smaller precedes it. (Could not match this quote against the script text; flagged unverified.)",
      quote: "His hand twitched at the wrist, the monitor blipping.", verified: false },
    { id: 9, severity: "low", category: "structure", scene: 4,
      note: "No darkest hour: the suspension threat is spoken and immediately soothed by Amma. One beat of true cost before the walk home would land the ending.",
      quote: "Ninnu suspend chestaru.", verified: true } ],

  coverage: {
    logline: "When a night-shift nurse discovers her comatose patient wakes only when she sings, she must choose between the hospital's rules and the one thing that still works.",
    genre: "Family drama / medical",
    synopsis: "Meera has kept Ward 3 alive on routine for 61 days. Her brother Vikram files a complaint against the hospital with her at its center. On the night the complaint lands, Meera's private ritual — singing to a comatose man who no one expects to wake — is witnessed. Dawn forces the family to decide what the complaint was actually for.",
    recommendation: "PASS with reservations — a compact, shootable four-scene chamber piece; expand the middle and let the mother in earlier." },

  pacing: [
    { scene: 1, density: 0.62, action_share: 41, pace: 0.71, drag: false },
    { scene: 2, density: 0.38, action_share: 62, pace: 0.31, drag: true  },
    { scene: 3, density: 0.81, action_share: 47, pace: 0.88, drag: false },
    { scene: 4, density: 0.66, action_share: 38, pace: 0.74, drag: false } ],

  dials: [
    { character: "MEERA",    scenes: [1,2,3,4], poles: { proactive: 6, warm: 8, articulate: 7, emotional: 5, grounded: 8 } },
    { character: "VIKRAM",   scenes: [2,3,4],   poles: { proactive: 9, warm: 3, articulate: 8, emotional: 7, grounded: 4 } },
    { character: "AMMA",     scenes: [1,4],     poles: { proactive: 7, warm: 9, articulate: 5, emotional: 6, grounded: 9 } },
    { character: "RAO GARU", scenes: [1,3],     poles: { proactive: 2, warm: 5, articulate: 1, emotional: 4, grounded: 3 } } ],

  ledger: [
    { setup: "The warm tiffin box",   kind: "object",   setup_scene: 1, status: "dangling",  note: "Planted as Meera's soft spot; never returns until Amma holds it empty — the payoff is implied, never staged." },
    { setup: "The complaint envelope", kind: "object",  setup_scene: 2, status: "abandoned", note: "Drives scenes 2-3, then stays dry in Vikram's pocket. Either the stakes or the envelope needs an ending." },
    { setup: "The singing ritual",    kind: "ritual",   setup_scene: 3, status: "paid",      note: "Witnessed, confronted, and chosen at dawn — the script's one fully paid promise." },
    { setup: "Nobody answers the phone", kind: "motif", setup_scene: 2, status: "dangling",  note: "Rings twice, never answered, never explained. One line makes it the ward's whole condition." } ],

  reads: [
    { character: "MEERA",  read: "Comes across as dutiful to the point of eraseable — the script wants her cornered, but she complies so smoothly we never see what defiance costs her." },
    { character: "VIKRAM", read: "Played as the antagonist; written, probably, as the only family member doing something. The complaint should read as love with bad handwriting — it currently reads as process serving." } ]
};
```

- [ ] **Step 2: Verify syntax.** Run: `node --check screenplay_studio/webapp/preview-next/_payload.js` — Expected: exits 0, no output.
- [ ] **Step 3: Verify it serves.** Run: `python -c "import subprocess,sys,urllib.request,socket; s=socket.socket(); s.bind(('127.0.0.1',0)); p=s.getsockname()[1]; s.close(); import os; env=dict(os.environ); env['SCREENPLAY_STUDIO_DEMO_MODEL']='1'; proc=subprocess.Popen([sys.executable,'-m','screenplay_studio.webapp_server','--port',str(p),'--projects-dir','studio_projects','--demo-model'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); import time; time.sleep(3); r=urllib.request.urlopen(f'http://127.0.0.1:{p}/preview-next/_payload.js',timeout=5); print(r.status, len(r.read())); proc.terminate()"` — Expected: `200` and a byte count > 8000.
- [ ] **Step 4: Commit.**
```bash
git add screenplay_studio/webapp/preview-next/_payload.js
git commit -m "feat(preview-next): shared demo payload — The Second Shift (script, findings, coverage, pacing, dials, ledger, reads)"
```

---

### Task 2: Gallery — `index.html`

**Files:**
- Create: `screenplay_studio/webapp/preview-next/index.html`

**Interfaces:**
- Consumes: nothing (static card grid; links open `ledger.html` etc.)
- Produces: the review entry point at `/preview-next/index.html`.

- [ ] **Step 1: Write the gallery.** Six cards in a 3×2 grid (NOT a uniform AI-slop 3-column icon grid — cards differ: each carries its world's palette swatch strip, name, metaphor line, nav-paradigm label, and "Open" link). Structure: page header "Six Worlds — v4 redesign gallery" + one review-instruction paragraph (how to use the review bar, what the contract is — 3 sentences max, per omit-omit-again). Below: the six cards linking to each world. A footer line: "Shared demo payload: The Second Shift · static design artifacts · pick one, port later."

Per-card content (exact copy):
1. **The Ledger** — light editorial · "The report as a typeset craftsman's letter." · Nav: masthead sections
2. **The Midnight Desk** — dark cinematic · "The verdict read at the desk, under the lamp." · Nav: brass tabs
3. **The Screening Room** — dark cinema · "The report plays like a screening." · Nav: film-strip scrubber
4. **The Quarterly** — light magazine · "Findings as magazine items." · Nav: contents spine
5. **The Terminal** — wildcard monospace · "The report as a lint stream." · Nav: buffer tabs + `:` commands
6. **The Studio Wall** — warm craft wildcard · "Findings pinned to the board." · Nav: wall panning

Each card's swatch strip = its world's 4 palette colors (see Tasks 3–8). Cards get hover lift (respects reduced-motion) and visible focus rings.

- [ ] **Step 2: Verify.** Serve check (same one-liner pattern as Task 1 Step 3) for `/preview-next/index.html` — Expected: `200`.
- [ ] **Step 3: Commit.**
```bash
git add screenplay_studio/webapp/preview-next/index.html
git commit -m "feat(preview-next): gallery — six worlds review index"
```

---

### Shared per-world requirements (apply to Tasks 3–8; restated because each task is read independently)

Every world MUST (spec §4 contract, grep-auditable):
1. `data-room` sections `desk`/`cowrite`/`feedback` (full viewport) + `data-screen` `shelf`/`upload`/`idea`; `.active` = visible; first paint = shelf; opening the project = upload moment → desk.
2. Feedback room carries `[data-state="empty"]` (Run Analysis CTA + one warm empty-state line), `[data-state="running"]` (pipeline stage list: formatting → voice → summaries → dialogue → categories → principles → ledger → verification → coverage, with one stage marked current), `[data-state="complete"]` (the full report); review bar toggles all three.
3. Feedback complete state renders, from `PAYLOAD`: findings (severity color + verification badge + verbatim quote + Locate + Discuss + Dismiss), fix queue strip, coverage (logline/genre/synopsis/recommendation), pacing visualization (one scene flagged dragging), dials (4×5 poles), setup/payoff ledger (4 entries), analysis controls at P2 (re-parse, report language, retry-failed, export/backup).
4. Click-outside + Esc dismiss the quote card and any modal; Esc cascade = topmost float only.
5. Idea room: chips present and tuck-away wired (mandatory); Co-write room: world's choice, but any chips obey tuck-away.
6. Every composer: 1 row → grows (≤200px cap), `growComposer` on input.
7. Six screens reachable: shelf → upload → desk → cowrite → feedback → idea.
8. P1/P2 placement per spec §6 (e.g., Desk P1: pages, inline edit demo, search, notes, change stars, Stash; P2: beat board, revision, drafts/compare, reader, focus, sprint, re-parse, export).
9. Quality gates: named font stacks, AA contrast, focus-visible, 44px targets, SVG icons, reduced-motion, slop blacklist.
10. Bridges: `locateFinding(f)` and `discussFinding(f)` wired to every finding row/card (shared code above).

---

### Task 3: The Ledger — `ledger.html` (light editorial)

**Files:**
- Create: `screenplay_studio/webapp/preview-next/ledger.html`

**Interfaces:**
- Consumes: `window.PAYLOAD` (Task 1), shared patterns (plan body).
- Produces: `/preview-next/ledger.html`.

**Identity (exact tokens):**
- Palette: paper `#f7f3e8`, ink `#221d14`, red-pencil `#b3372c` (high severity + locate underline), graphite `#6b6355` (medium), faded ink `#a39a8a` (low), hairline `#d8cfbc`.
- Type: display+body `Georgia, 'Iowan Old Style', 'Times New Roman', serif`; data/mono `Consolas, 'Courier New', monospace` (tabular-nums for page/pace numbers).
- Motion: quiet — 160ms fades, underline draws (reduced-motion: instant).

**Layout blueprint:** masthead across the top — world wordmark left ("THE LEDGER"), three section labels center (SCRIPT · CO-WRITE · VERDICT, current one ruled under), project title right. Feedback room = the letter: dateline (project · date · "analysis no. 1"), salutation line ("Dear A. Writer — read it twice; the second read is the honest one."), findings as numbered margin annotations (¶n with severity pencil-marks, evidence as indented pull-quotes in italic), then the appendix sections: Fix Queue (a ruled list with verb buttons), Coverage, Pacing (thin horizontal rules whose lengths encode pace; the dragging scene's rule in red-pencil), Dials (5-axis table per character, tabular numerals), Ledger appendix (setup/payoff table with dangling rows struck in red). Script Desk = cream pages, ink text, red-pencil locate underline, margin-note dots.

- [ ] **Step 1: Scaffold** — copy the shared skeleton + patterns; wire masthead nav (three `data-go` buttons: `desk`/`cowrite`/`feedback`).
- [ ] **Step 2: Journey screens** — shelf (project as a ledger-bound volume), upload moment ("submit for review" → stamp animation, reduced-motion: appear), idea room (a blank left page + Sameer's column; chips wired).
- [ ] **Step 3: Script Desk** — render `PAYLOAD.script` as typewritten-but-typeset pages; search box (P1), margin dots, one change-star line demo, Stash rail (P2), beat board/revision/drafts as masthead-adjacent P2 menu.
- [ ] **Step 4: Co-write room** — chat column + Sameer replies from a canned exchange (streaming demo: one reply types in), quote card, translator chip on one reply, mic chip; growing composer; no chips required here.
- [ ] **Step 5: Feedback room (the letter)** — all three lifecycle states; complete state renders every PAYLOAD surface per the blueprint; wire Locate (red-pencil underline + flip to desk) and Discuss (pre-filled quote card).
- [ ] **Step 6: Verify** — run the 12-point grep checklist (Task 9 list) against this file; fix gaps; serve-check 200; open in chromium via the Task 10 harness pattern and confirm zero JS errors.
- [ ] **Step 7: Commit.**
```bash
git add screenplay_studio/webapp/preview-next/ledger.html
git commit -m "feat(preview-next): The Ledger — light editorial world (masthead nav, report-as-letter)"
```

---

### Task 4: The Midnight Desk — `midnight.html` (dark cinematic)

**Files:**
- Create: `screenplay_studio/webapp/preview-next/midnight.html`

**Identity (exact tokens):**
- Palette: void `#14110e`, raised surface `#1c1813`, line `#2e2820`, amber lamp `#e8a24f`, paper `#f2e9d4`, paper-ink `#2c2620`, dim `#8b8272`, dawn variant unused (night only).
- Type: display `Palatino, 'Palatino Linotype', 'Book Antiqua', Georgia, serif`; labels `'Courier New', Courier, monospace` (typewriter); body `Georgia, serif`.
- Motion: slow ambient lamp-glow breath (6s, disabled under reduced-motion), instant room swaps.

**Layout blueprint:** brass tabs under the lamp glow (top center: THE SCRIPT / SAMEER / THE CASE FILE — amber underline on current). Script Desk = glowing paper pages on void (the app's taste, evolved) with margin machinery summoned by hover, never docked. Co-write = Sameer's side of the desk (chat + warm amber accents). Feedback = the doctor's CASE FILE: a manila-folder header (project name typed on a label), findings as typed case notes with red stamp severities (HIGH = red stamp, rotated −4°), tabs inside the folder for Fix Queue / Coverage / Pacing (bar chart, amber bars, red drag bar) / Dials (amber gauge arcs) / Ledger (typed table, dangling rows stamped DANGLING). Review bar matches the dark chrome.

- [ ] **Steps 1–7: same step structure as Task 3** (scaffold → journey → desk → co-write → feedback → verify → commit), with this world's blueprint; commit message:
```bash
git add screenplay_studio/webapp/preview-next/midnight.html
git commit -m "feat(preview-next): The Midnight Desk — dark cinematic world (brass tabs, case-file report)"
```

---

### Task 5: The Screening Room — `screening.html` (dark cinema)

**Files:**
- Create: `screenplay_studio/webapp/preview-next/screening.html`

**Identity (exact tokens):**
- Palette: near-black `#0c0d10`, panel `#14161c`, line `#23262e`, silver text `#c9cdd6`, dim `#7d828e`, frame-amber `#f5a623`, record-red `#e05252`, frame-green `#7fb069` (paid).
- Type: display `'Franklin Gothic Medium', 'Arial Narrow', 'Segoe UI', sans-serif` (poster condensed, uppercase tracking); data `'Cascadia Mono', Consolas, monospace`; body `'Segoe UI', Tahoma, sans-serif` at 16px+ (deliberate pairing — poster voice + workman body; contrast-checked).
- Motion: slide transitions + a one-frame projector flicker on room change (reduced-motion: hard cuts).

**Layout blueprint:** bottom film-strip scrubber — three sprocket-holed frames labeled CUTTING TABLE / DIRECTOR'S CHAIR / SCREENING, current frame lit amber; ← / → keys also switch. Script Desk = the cutting table (pages as filmstrips, notes as splicing tape marks). Co-write = the director's chair (chat, clapperboard quote card). Feedback = THE SCREENING: complete state opens on a verdict title card (logline + recommendation as the poster), then findings are consecutive slides — ← / → / dots navigate, severity as frame edge color, pacing as a waveform strip across the timeline, dials as per-character frame meters, ledger as an end-credits crawl (dangling credits dimmed). Empty state = "no print delivered" leader countdown (8…7…6 animated, reduced-motion: static) + Run Analysis CTA; running = reel timer + stage list.

- [ ] **Steps 1–7: same structure as Task 3**; commit:
```bash
git add screenplay_studio/webapp/preview-next/screening.html
git commit -m "feat(preview-next): The Screening Room — dark cinema world (film-strip nav, screening report)"
```

---

### Task 6: The Quarterly — `quarterly.html` (light magazine)

**Files:**
- Create: `screenplay_studio/webapp/preview-next/quarterly.html`

**Identity (exact tokens):**
- Palette: ivory `#fbfaf5`, ink `#1a1a18`, oxblood accent `#7d2a2a`, sage `#5f7464` (medium), stone `#9b978c` (low), rule `#e3e0d6`.
- Type: display `'Bodoni MT', Didot, 'Playfair Display', Georgia, serif`; body `Corbel, 'Gill Sans Nova', Calibri, 'Segoe UI', sans-serif` 16px; kickers/labels Corbel caps, letter-spacing .18em.
- Motion: restrained editorial reveals on room entry only (12px rise + fade, 220ms; reduced-motion: none).

**Layout blueprint:** left contents spine (~220px) — numbered contents list: 1 The Script · 2 In Conversation · 3 The Verdict · 4 Marginalia (idea room) · 5 Submissions (shelf), a thumb-tab marking current. Feedback = the feature well: kicker (category, caps) → headline (finding note, Bodoni 28px) → body (the note) → pull-quote (verbatim evidence, oxblood rule above) per finding, in a 2-column editorial grid (CSS columns); fix queue as "Corrections" boxed section; coverage as the editor's letter; pacing as a folio-width sparkline; dials as a tasting-notes panel; ledger as "Accounts" column (dangling in stone, paid in sage). Script Desk = single wide measure (66ch) with margin notes in the outer gutter.

- [ ] **Steps 1–7: same structure as Task 3**; commit:
```bash
git add screenplay_studio/webapp/preview-next/quarterly.html
git commit -m "feat(preview-next): The Quarterly — light magazine world (contents spine, findings as items)"
```

---

### Task 7: The Terminal — `terminal.html` (wildcard monospace)

**Files:**
- Create: `screenplay_studio/webapp/preview-next/terminal.html`

**Identity (exact tokens):**
- Palette: ink `#0a0f0a`, raised `#0e150e`, line `#1c2a1c`, phosphor `#7ee787`, register-two `#67d6e8` (co-write room accent), warn `#e3c567`, fail `#e07070`, dim `#5d7a5d`.
- Type: everything `'Cascadia Mono', 'Cascadia Code', Consolas, 'Courier New', monospace` (deliberate single-family identity; sizes do hierarchy: 20px display, 16px body, 12px status).
- Motion: cursor blink only; all state changes instant (reduced-motion is free here).

**Layout blueprint:** bottom status line — buffer tabs `[script] [sam] [verdict] [ideas]` (current = inverse video) + command prompt `:` accepting `:script` `:sam` `:verdict` `:ideas` `:shelf` `:empty` `:running` `:complete` `:loc 2` + ⌘K palette (fuzzy list: "jump to scene 3", "open the verdict", "discuss finding 4"...). Feedback = lint stream: findings as `warning: HIGH structure s3 — note…` lines with severity glyphs (`!!`/`!`/`·`), `[verified]`/`[unverified]` tags; coverage as an ASCII box; pacing as bar gauges (`s2 ▇▇▁▁▁▁▁▁ drag`); dials as ASCII meters; ledger as a fixed table; fix queue with `:loc n` / `:discuss n` hints. Script Desk = buffer of script text with line numbers, `Ctrl+F`-style search field, notes as inline `NOTE:` gutter entries. Co-write (`sam` buffer) = chat transcript, prompt line with growing input. Idea room = scratch buffer with chips as `[1] explore` menu items that tuck to a right-edge rail on input.

- [ ] **Steps 1–7: same structure as Task 3**; the command parser is this world's nav — test `:verdict`, `:loc 2`, `:empty` by hand in Step 6; commit:
```bash
git add screenplay_studio/webapp/preview-next/terminal.html
git commit -m "feat(preview-next): The Terminal — monospace wildcard world (buffer tabs, :commands, lint report)"
```

---

### Task 8: The Studio Wall — `studio-wall.html` (warm craft wildcard)

**Files:**
- Create: `screenplay_studio/webapp/preview-next/studio-wall.html`

**Identity (exact tokens):**
- Palette: cork `#c9a876`, cork-shadow `#b2915f`, wall `#e8dcc3`, paper card `#fbf6ea`, tape `#efe6cf` (α .85), terracotta `#c96f4a` (high), mustard `#c9a13b` (medium), sage `#7d8f6b` (low/paid), ink `#3a3226`.
- Type: display accents `'Segoe Print', 'Bradley Hand'` — **only** for pinned labels and the wall wordmark, never body (Bradley Hand is on the slop blacklist as a *primary*; as a rare 2-line accent it's a deliberate craft voice); body `'Bookman Old Style', Bookman, Georgia, serif` 16px.
- Motion: pin wobble on card hover (rotate ±1.5°), wall pan 260ms ease-out (reduced-motion: instant).

**Layout blueprint:** three named walls panned with ← / → arrows + labels + keys: PAGES (script pages as pinned sheets, notes on masking tape, change stars as marker stars), SAMEER'S CORNER (chat on a clipboard, quote card as a taped scrap, composer on a legal pad, growing), VERDICT BOARD (findings as pinned index cards arranged in a loose grid by severity rows, red string from each card's pin to a small scene card thumbnail — CSS lines; fix queue as a clipboard to-do strip with check-off demo; coverage pinned as the board's title card; pacing as a hand-drawn bar chart; dials as gauges with drawn needles; ledger as index cards stamped DANGLING). Empty state = bare cork + one pinned note "board's empty — run the analysis" + CTA; running = Polaroids developing (blur→sharp per stage, reduced-motion: appear).

- [ ] **Steps 1–7: same structure as Task 3**; commit:
```bash
git add screenplay_studio/webapp/preview-next/studio-wall.html
git commit -m "feat(preview-next): The Studio Wall — warm craft world (wall panning, pinned findings)"
```

---

### Task 9: Contract audit — all six worlds

**Files:**
- Modify: `NOTES.md` (append audit record)

- [ ] **Step 1: Grep-audit each world against the 12 contract points + P1/P2 placements.** For each world record PASS/GAP per point. Minimum grep set (per world file):
```bash
rg -c 'data-room="(desk|cowrite|feedback)"' <world>.html          # 3 rooms (expect 3)
rg -c 'data-state="(empty|running|complete)"' <world>.html        # lifecycle (expect 3)
rg -c 'locateFinding|discussFinding' <world>.html                 # bridges wired
rg -c 'wireChips' <world>.html                                    # chips wired (idea room)
rg -c 'growComposer' <world>.html                                 # composer
rg -c 'wireFloatDismiss|keydown.*Escape' <world>.html             # dismissal
rg -c 'prefers-reduced-motion' <world>.html                       # motion gate
rg -n 'system-ui|-apple-system' <world>.html                      # must return NOTHING
rg -c 'data-go="shelf"' <world>.html                              # journey entry
```
Plus visual checks in chromium: first paint = shelf; upload → desk lands by default; review-bar empty/running/complete all render; Locate flashes the scene; Discuss pre-fills the quote card; Esc and click-outside dismiss.
- [ ] **Step 2: Fix any GAP in the owning world file, re-run its checks.**
- [ ] **Step 3: Append the six audit blocks (PASS table per world) to NOTES.md.**
- [ ] **Step 4: Commit.**
```bash
git add NOTES.md
git commit -m "docs(notes): preview-next contract audit — six worlds x 12 points"
```

---

### Task 10: Browser walk — `tests/e2e_browser_preview_next.py`

**Files:**
- Create: `tests/e2e_browser_preview_next.py`

**Interfaces:**
- Consumes: `tests/e2e_browser_common.py` (`open_studio`, `launch`, `assert_no_js_errors`, `Checks`), the six world files, `_payload.js`.
- Produces: the regression suite (self-hosted boot or `E2E_BASE` override, per repo convention).

- [ ] **Step 1: Write the suite** (checks: every world serves 200; per world — gallery → world → shelf visible → upload click lands on desk → review bar toggles feedback empty/running/complete → Locate flips to desk and flashes scene 2 (finding id 2) → Discuss opens co-write with the quote card filled and text = finding 2's quote → chips tuck in the idea room on input and restore on clear → composer grows past 40px on multi-line input → Esc dismisses the open quote card → zero JS errors):

```python
"""Browser walk for the six preview-next worlds (design artifacts, demo payload).

Self-hosted by default (demo model, throwaway projects dir); E2E_BASE sweeps
against an already-running studio. Run: python tests/e2e_browser_preview_next.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_browser_common import (Checks, assert_no_js_errors, launch, open_studio)

WORLDS = ["ledger", "midnight", "screening", "quarterly", "terminal", "studio-wall"]


def main():
    checks = Checks()
    with open_studio() as base, launch(__import__("playwright").sync_playwright().__enter__())[0:1] if False else _run(checks, base):
        pass


def _run(checks, base):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser, page, errors = launch(pw)

        # gallery
        page.goto(f"{base}/preview-next/index.html")
        checks.check("gallery serves 200", page.title() != "")
        checks.check("gallery has six cards",
                     page.locator("a[href*='.html']").count() >= 6)

        for w in WORLDS:
            errors.clear()
            page.goto(f"{base}/preview-next/{w}.html")
            checks.check(f"{w}: shelf is first paint",
                         page.locator('[data-screen="shelf"].active').count() == 1)
            page.locator('[data-screen="shelf"] [data-open], [data-screen="shelf"] .project-card').first.click()
            checks.check(f"{w}: upload lands on desk",
                         page.locator('[data-room="desk"].active').count() == 1)

            page.locator('#pv [data-go="feedback"]').click()
            for state in ("empty", "running", "complete"):
                page.locator(f'#pv [data-fb="{state}"]').click()
                checks.check(f"{w}: feedback {state} renders",
                             page.locator(f'[data-state="{state}"]').is_visible())

            page.locator('#pv [data-fb="complete"]').click()
            page.locator('[data-state="complete"] [data-locate], [data-state="complete"] .finding [data-act="locate"]').first.click()
            checks.check(f"{w}: Locate flips to desk",
                         page.locator('[data-room="desk"].active').count() == 1)
            page.locator('#pv [data-go="feedback"]').click()
            page.locator('[data-state="complete"] [data-discuss], [data-state="complete"] .finding [data-act="discuss"]').first.click()
            checks.check(f"{w}: Discuss pre-fills quote card",
                         page.locator('#quote-card').is_visible()
                         and len(page.locator('#quote-text').inner_text()) > 20)

            # esc dismissal
            page.keyboard.press("Escape")
            checks.check(f"{w}: Esc closes quote card",
                         not page.locator('#quote-card').is_visible())

            # idea room: chips tuck + restore
            page.locator('#pv [data-go="idea"]').click()
            chips = page.locator(".chips")
            ta = page.locator('[data-screen="idea"] textarea, [data-screen="idea"] [contenteditable]').first
            ta.fill("a bird wakes when she sings")
            checks.check(f"{w}: chips tuck on input", "tucked" in (chips.get_attribute("class") or ""))
            ta.fill("")
            checks.check(f"{w}: chips restore on clear",
                         "tucked" not in (chips.get_attribute("class") or ""))

            # composer grows
            page.locator('#pv [data-go="cowrite"]').click()
            box = page.locator("#input")
            before = box.bounding_box()["height"]
            box.fill("line one\nline two\nline three")
            after = box.bounding_box()["height"]
            checks.check(f"{w}: composer grows", after > before + 10)

            assert_no_js_errors(checks, errors, f"{w}: zero JS errors")
        browser.close()
        checks.finish()


if __name__ == "__main__":
    checks = Checks()
    with open_studio() as base:
        _run(checks, base)
```

(Implementer note: the dead `main()` above must be deleted — kept only to show the intended `_run(checks, base)` shape. Final file: module docstring, imports, `WORLDS`, `_run`, and the `__main__` block exactly as written.)

- [ ] **Step 2: Run it.** `python tests/e2e_browser_preview_next.py` — Expected: ~60 checks pass, exit 0. Fix worlds until green (fixtures may need per-world selector alignment — e.g., terminal's buffer tabs instead of `#pv` buttons: give terminal's status-line buttons the same `data-go`/`data-fb` attributes so the shared harness holds).
- [ ] **Step 3: Commit.**
```bash
git add tests/e2e_browser_preview_next.py
git commit -m "test(preview-next): browser walk — 6 worlds x journey/lifecycle/bridges/chips/composer/errors"
```

---

### Task 11: Quality gates + design-review pass + screenshots

**Files:**
- Create: `preview_shots/preview-next/` (screenshots, untracked evidence)
- Modify: `NOTES.md` (verification record)

- [ ] **Step 1: Quality gates.** For each world: chromium computed-style probe for body font-size ≥16px and computed color contrast (body text vs its background ≥4.5:1); verify `:focus-visible` ring styles exist; verify no `system-ui` primary; scan for slop blacklist patterns.
- [ ] **Step 2: Run the design-review pass** across the six worlds (audit → fix → verify, one commit per finding, per that skill's protocol). Screenshots before/after to `preview_shots/preview-next/`.
- [ ] **Step 3: Record the final table in NOTES.md** (per-world scores, findings fixed, remaining polish).
- [ ] **Step 4: Commit.**
```bash
git add NOTES.md
git commit -m "docs(notes): preview-next quality gates + design-review pass record"
```

---

## Rework (2026-08-30 R1) — structural rebuild + tri-pane desk

> Supersedes the layout model of Tasks 3–8 for structure; keeps payload, interaction contract, and data hooks.

**R0 — docs:** spec §4 pt 1 revised to the tri-pane desk (script center; feedback LEFT pane; Sameer RIGHT pane; independent toggles + master both-at-once; panes expand to full rooms; desk lands both-open), §4 pt 10 structural-uniqueness clause, §4 pt 13 semantic token layer, §5a binding blueprints.

**R1 — rebuild ×6** (per §5a blueprints; shared: `_payload.js`, interaction contract, `data-*` hooks incl. new pane hooks):
- Pane hooks (uniform): `[data-pane-left-toggle]`, `[data-pane-right-toggle]`, `[data-panes-master]`, `[data-expand="left|right"]`, `[data-collapse-to-desk]`, and `data-desk-state` on the desk container ∈ `both-open | left-only | right-only | none-open | focus-left | focus-right`. Desk lands `both-open`.
- R1.1 Ledger — index-tab dossier; R1.2 Midnight — desk-object nav + drawers; R1.3 Screening — reel rack + rails; R1.4 Quarterly — die-cut cover + gatefolds; R1.5 Terminal — tmux session (`z` zoom, `:monocle`/`:triage`); R1.6 Studio Wall — free-pan wall + hinged panels + mini-map.

**R2 — e2e v2:** keep v1 hooks; add pane-state walk (default both-open → left toggle → right toggle → master both ways → expand left/right → collapse) with per-world nav params. Run to green.

**R3 — re-audit:** 15-pt contract ×6 (+ pane + uniqueness checks), AA contrast re-probe, fresh screenshots, NOTES record.

## Self-Review (done at plan-writing time; re-verify after any plan change)

**Spec coverage:** §3 files ↔ Tasks 1–8 (8 files, 1:1) · §4 contract ↔ Shared patterns + per-world requirements + Task 9 audit · §5 identities ↔ Tasks 3–8 identity blocks (tokens named exactly) · §6 tiers ↔ per-world requirements item 8 · §7 screens/review bar ↔ shared `show()` + `wireReviewBar` · §8 verification ↔ Tasks 9–11. No spec requirement lacks a task.

**Placeholder scan:** payload data is fully authored (Task 1); shared interaction code is fully written (plan body); per-world blueprints give exact tokens, layout, and behavior. The only intentional looseness: world files' full HTML is authored at build (1500+ lines each — inlining six finished files in the plan would be the deliverable twice). Every step states what to build with exact values, and Tasks 9–11 verify the result against the contract, so nothing ships on vibes.

**Type consistency:** `window.PAYLOAD` keys (`project`, `script`, `findings`, `coverage`, `pacing`, `dials`, `ledger`, `reads`) match across Task 1 definition, per-world requirement 3, and Task 10 assertions. Shared function names (`show`, `renderFeedback`, `locateFinding`, `discussFinding`, `growComposer`, `wireChips`, `wireFloatDismiss`, `wireReviewBar`) match between the patterns block and the world tasks. E2E uses only `data-go`, `data-fb`, `data-state`, `#quote-card`, `#quote-text`, `#input`, `.chips`, `[data-room]`, `[data-screen]` — all defined in the patterns block; Task 10 notes terminal's status-line buttons must carry `data-go`/`data-fb`.
