# Midnight Desk — UI Redesign + Select-to-Reply Design

**Date:** 2026-08-13
**Status:** Approved in principle (direction chosen by user: "The Midnight Desk"); spec pending user review
**Related:** `screenplay_studio/webapp/preview.html` (approved high-fidelity mockup — the reference implementation)

---

## 1. Why

The user rejected the current webapp UI as not feeling like a writer's space: the welcome "den" is a cartoon CSS illustration (emoji props, flat shapes) and — critically — **the atmosphere disappears the moment a project is opened**, leaving a generic stock dashboard. The user wants a brand-new UI that lures them into the writing mood ("a writer's den"), plus a messaging-app-style way to **select a passage in the script and reply to Sam about it**, instead of describing what they mean in words.

## 2. Design direction — "The Midnight Desk" (approved)

A dark, warm workspace where the room surrounds you and the page stays bright. References: iA Writer night mode, ZenWriter/FocusWriter, dark-academia desk scenes, Scrivener dark.

### 2.1 Tokens

```css
--ink-950:#14110e   /* deep night — app background, vignette      */
--ink-900:#1b1713   /* desk surfaces — sidebar, rails, panels     */
--ink-850:#1f1a15
--ink-800:#251f1a   /* raised cards                               */
--ink-700:#2e2720   /* hover                                      */
--line:#3b322a      /* warm hairlines — no pure-gray borders      */
--line-soft:#2a241e
--paper:#f2e8d4     /* the script — aged cream                    */
--paper-ink:#2b241b
--paper-muted:#6d6050
--lamp:#e8a24f      /* warm amber — Co-write room                 */
--lamp-deep:#b06f27
--consult:#86a6bd   /* cool steel — Feedback room                 */
--consult-deep:#5b7c95
--text:#e9dfce      --text-muted:#9a8e7b
--danger:#c96a5a    --ok:#8fae7e
```

### 2.2 Typography — four roles, one system

| Face | Role |
|---|---|
| **Special Elite** (typewriter) | brand, room labels, project "spines", checkpoint index cards — the desk artifacts |
| **Courier Prime** | the script itself (industry-standard screenplay face — the page reads like a printed script) |
| **Source Serif 4** | chat + feedback prose (warm literary reading face) |
| **IBM Plex Mono** | status/data — model id, percentages, timestamps, shortcuts |

### 2.3 Layout

The functional skeleton is **unchanged** (three-pane: sidebar shelf / main / checkpoint rail; script pane + switchable room panel; all modals; keyboard shortcuts). Every pixel is re-skinned. No functionality is lost.

### 2.4 The signature element — the lamp

`body[data-room]` drives the room's lighting via CSS variables:

- **Co-write** → `--accent: var(--lamp)`, warm amber glow (radial gradient tinting the room panel + button glows).
- **Feedback** → `--accent: var(--consult)`, cool steel glow (consultant's table lamp).
- The script pane stays cream paper in both rooms — neutral reading light.
- The room toggle changes the *lighting* of the room: the Co-write vs Feedback differentiation made physical.

### 2.5 Atmosphere, not cartoon

- Film grain at ~3% opacity (SVG feTurbulence data-URI, `pointer-events:none`) + a vignette overlay.
- Welcome scene: CSS lamp with a warm glow pool in the corner, a quiet night window (moon + faint stars + hill), a shelf of book spines, and the upload card as a **sheet of paper** on the desk.
- Zero emoji-as-decor; a single inline-SVG pen mark for the brand. Icons are minimal text/SVG glyphs.
- `prefers-reduced-motion` respected; no animation for its own sake.

### 2.6 Accessibility

Text contrast ≥ 4.5:1 on dark (light `--text` on `--ink-*`); visible keyboard focus; room toggle remains a proper `role="tablist"`/`role="tab"`; selection affordance works with keyboard (`Shift+arrows`) too.

## 3. Feature — Select-to-Reply (quote a passage, ask Sam)

The writer selects text in the script pane (mouse or keyboard) and a small floating action appears near the selection: **"Ask Sam about this"**. Clicking it attaches the passage as a *quote* to the composer (like replying to a message in a chat app), the writer types their question, and Sam answers *grounded on that exact passage* — no describing needed.

### 3.1 Core flow

1. User selects text in a rendered scene page (`#script-scenes`; each page has `dataset.sceneNumber` — walk up from the selection anchor to find it).
2. A floating button appears at the selection's bounding rect (dismissed on outside click / Escape / selection cleared).
3. Click → a **quote card** is inserted above the composer: `[Scene 2] "the pages are burned through with small, deliberate holes…"` (snapshot of the text; scene number from the DOM). The paper selection is marked with the warm "discussed" style (`--lamp`-tinted, matches the mockup legend).
4. User types their question → send. The message carries the quote.
5. Backend stores the quote on the `Message` and injects context: the quoted passage + the scene's text block (`build_scene_context_block` via the scene number) so Sam reads the exact moment.
6. Sam's reply renders with the quoted passage as a styled quote block at the top of the user bubble.

### 3.2 Data model / API (small, backward-compatible)

- `Message` (screenplay_cowriter/models.py) gains `quote: dict | None = None` → `{"scene_number": int, "text": str}`. `to_dict`/`from_dict` updated (missing key → None; old sessions load fine).
- `POST /api/projects/<name>/chat/sessions/<sid>/messages` accepts optional `quote` in the body; the webapp passes it to `engine.send_message(session, text, quote=…)`.
- `engine.send_message`: when `quote` present —
  - ensure the scene number is in `scene_refs` (context block injection),
  - append a `system` message (or inline block) carrying the quoted passage: `The writer selected this passage from Scene N: "…"`,
  - store `quote` on the user `Message`.
- GET session/messages responses include `quote` automatically via `to_dict` (frontend renders the quote block from it — round-trips through reloads and forks).
- Cowriter CLI/server: `quote` defaults to None — no behavior change.

### 3.3 Extensions around it (same context — improvisations)

1. **Click a quote to jump** — clicking a rendered quote block in the chat scrolls the script pane to that scene (`dataset.sceneNumber` → existing `scrollIntoView` pattern) and flashes a highlight on the quoted text.
2. **Findings → discuss with Sam** — each Feedback finding gets "Discuss with Sam": it quotes the finding's `issue` (and `evidence_quote` when present) into the composer and switches to the Co-write room. The same quote-card machinery, zero new concepts.
3. **Discussed-marking** — quoted passages get a persistent warm mark in the paper (the mockup's "discussed" legend swatch), so the writer sees what's already been talked over.

### 3.4 Edge cases

- Selection spanning two scenes → use the anchor node's scene (first), note it in the quote card.
- Selection in the Feedback pane or elsewhere → not offered (script pane only).
- Empty/collapsed selection → no button.
- Quoted text is a **snapshot** — later edits to the script don't change stored quotes (by design; the quote is a record of what was asked).
- **Rendering safety:** quote text is user/model content — always `textContent`/escaped, never `innerHTML`, in quote cards, chat bubbles, and jump-highlights.
- Selection must be captured at click time (floating button click clears the document selection — snapshot `getSelection()` on `mouseup`/`keyup` before showing, and keep the text in memory until the button is clicked or dismissed).

## 4. Scope

**In (this batch):**
- Full rewrite of `screenplay_studio/webapp/index.html` + `style.css` to the Midnight Desk system; `app.js` rewired to the new markup/classes + the select-to-reply feature; `preview.html` retained as the visual reference.
- Backend additions: `Message.quote`, engine quote-context injection, webapp route accepts `quote`.
- Tests: `Message.quote` round-trip (serialize/deserialize, old-session compat), engine sends quote context + stores it (fake client), `extract_scene_refs` still fires for quoted scene numbers. JS: `node --check` on app.js. Manual browser pass against the real server.

**Out (explicitly, YAGNI):**
- No new frontend dependencies / no build step (project convention: vanilla HTML/CSS/JS).
- No auth, no multi-user, no cloud sync.
- No changes to the analysis pipeline, memory, guardrails, or any backend behavior beyond the quote field.
- Dark/light theme toggle is NOT part of this batch (the Midnight Desk is the single theme; the "Dawn" button in the sidebar is a placeholder from the mockup — dropped or shown disabled).

## 5. Risks & mitigations (self-critique)

1. **Scope:** UI rewrite + backend field in one batch. Mitigation: the backend change is ~30 lines and fully backward-compatible; the two parts are independently verifiable (UI renders against existing API even before the quote field lands).
2. **Dark+glow can look muddy.** Mitigation: script pane stays bright paper; text contrast floor; hairlines warm and subtle; grain at 3%.
3. **"Theme" gimmick risk.** Atmosphere comes only from light/shadow/type — no props, no emoji decor; the lamp is the single signature.
4. **Selection UX pitfalls.** Capturing selection at click time (see 3.4); not breaking existing `extract_scene_refs` (quote scene number flows through the same path); quote text rendered escaped everywhere.
5. **Scope creep on improvisations.** Core (3.1) is the must; extensions (3.3) are incremental and can be delivered after the core is verified — partial delivery is still solid.

## 6. Success criteria

- Opening the webapp feels like a room, not a dashboard — the workspace itself (not just the welcome) carries the atmosphere.
- Co-write vs Feedback is visibly distinct via lighting at a glance.
- Select a passage → ask Sam → reply is grounded on the quoted text, with the quote visible in the conversation; clicking it jumps back to the scene.
- All existing functionality intact: projects, analysis, report, fix queue, beat board, compare, drafts, checkpoints, shortcuts, modals.
- Full test suite green + `node --check` + manual browser pass.
