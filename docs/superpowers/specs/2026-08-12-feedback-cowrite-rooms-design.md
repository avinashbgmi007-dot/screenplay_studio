# Design: Feedback / Co-write Room Differentiation + Writing-Partner Guardrails

**Date:** 2026-08-12
**Status:** Approved by user (design review), pending spec review
**Applies to:** `screenplay_studio/webapp` (UI shell), `screenplay_cowriter` (partner voice + guardrails)

---

## 1. Problem

Today the webapp has one **"Chat" view** that mixes both assistants: the co-writer conversation, the persona/mode/report-language dropdowns, the **Run Analysis** button, and analysis progress all share a single header. The feedback report is surfaced through chat context (`ReportContext`) and as red-pencil notes in the separate *Script & Notes* view.

Consequences:

- The writer cannot tell, at a glance, whether they are "being analyzed" or "working with a peer" — the product never tells the two jobs apart.
- Because the co-writer lives next to the analyst's controls, it is always tempted to switch into evaluator mode mid-conversation — which reads as the AI "outsmarting" the writer.
- The analysis report and fix queue are not first-class surfaces (the fix queue is API-only).

## 2. Goals

1. **Two rooms, two perspectives, clearly told apart.** A *Co-write room* (the writer's desk — a peer partner who works beside you) and a *Feedback room* (the consultant's desk — a script consultant/doctor delivering a professional review). Recognizable at a glance, without reading.
2. **The script never leaves your sight.** Both rooms are split views: the same script pane on the left, the room's panel on the right. Switching rooms never loses your place.
3. **A co-writer that feels human.** One consistent partner with a stable voice; structural guardrails guarantee: acknowledge-first, permission-before-critique, one idea at a time, never a dead-end, "why do you think so?" probing, and never volunteering the report.
4. **No option overload.** Zero dropdowns in the Co-write room; two tabs + one button in the Feedback room.

## 3. Non-goals (out of scope)

- The analyzer pipeline, report generation, fix-queue API, diff, beat board, compare, revision/undo/redo flows — all unchanged.
- Relationship memory (writer-profile / tone calibration over sessions) — explicitly deferred to v2 (Approach 3). The design leaves room for it; it is not built now.
- Renaming the partner via UI (single config value only, for now).
- Any cloud/online integration.

## 4. Locked decisions (from design review)

| # | Decision | Choice |
|---|----------|--------|
| 1 | UI model | **Two separate rooms** (Co-write, Feedback) — deliberate stepping into one or the other |
| 2 | Draft home | **Pages always visible** — split view, script pane fixed on the left in both rooms |
| 3 | Partner personality | **One consistent writing partner** ("Sam", configurable); personas become conversational lenses, not dropdowns |
| 4 | Report access | **Informed partner** — knows the report, never volunteers it, can discuss it when the writer raises it |
| 5 | Approach | **Approach 2 — voice + structural guardrails** (`peer.py` engine layer) |
| 6 | Beat Board / Compare | **Toolbar icons on the script pane**, not top-level destinations |

---

## 5. Section 1 — Room architecture & navigation

### 5.1 Top-level navigation

```
┌──────────────────────────────────────────────────────────────────┐
│ PROJECT: Pain_Tenglish     [Co-write] [Feedback]   ✍️ Writer's Desk│
├──────────────────────────────────────────────────────────────────┤
│ ┌─ SCRIPT PANE (left, fixed) ─┐   ┌─ ROOM PANEL (right) ────────┐ │
│ │ scenes · search ·           │   │ Co-write: conversation      │ │
│ │ red-pencil notes ·          │   │ Feedback: Report │ Fix Queue│ │
│ │ undo/redo · export · print  │   │                             │ │
│ │ [📋Beat][🗂Compare][📄Drafts] │   │                             │ │
│ └─────────────────────────────┘   └─────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

- Exactly **two destinations** in the top bar: `[Co-write]` and `[Feedback]`.
- **Beat Board, Compare, Drafts, Export, Print** become **icon buttons on the script pane toolbar** — tools used *on* the script, not destinations.
- The script pane is **identical in both rooms** — same scenes, same centered scene, same search, same red-pencil notes. Switching rooms preserves position.
- **Default room on project open: Co-write** (the writer's desk comes first).

### 5.2 Co-write room (the writer's desk)

- Right panel: the existing conversation (`#messages`) + composer.
- Header: a **partner card** (avatar + name "Sam", "writing with you") + branch switcher. **No persona dropdown, no mode dropdown, no report-language dropdown.**
- Personas become **conversational lenses**: *"what would a producer say about this cold open?"* — Sam adopts the lens in-voice and drops it when the conversation moves on.
- `peer` is the default mode (see §7).

### 5.3 Feedback room (the consultant's desk)

- Right panel: two sub-tabs — **`Report`** and **`Fix Queue`**.
- Header: **"Script Consultant Report"** title bar with `Run Analysis` + report-language picker.
- **No chat in this room.** The consultant delivers a work product; it does not converse.
- **One bridge:** each fix-queue finding has *"→ discuss with my partner"* → switches to Co-write room and seeds the conversation (see §9).

### 5.4 What the current UI maps to

| Today | After |
|---|---|
| `#chat-view` (Chat) | Co-write room (conversation + partner card) |
| `#script-view` (Script & Notes) | Dissolves as a mode → its contents become the shared left script pane |
| `#beatboard-view`, `#compare-view` | Kept as full-screen views, opened via script-pane toolbar icons |
| Header: persona / mode / report-lang / Run Analysis | Report-lang + Run Analysis → Feedback room. Persona/mode dropdowns → removed |
| `#messages` + composer | Unchanged (Co-write room right panel) |

---

## 6. Section 2 — Visual identity (at-a-glance room recognition)

The script pane stays **neutral** in both rooms. Identity lives in the header + room panel:

| | Co-write (writer's desk) | Feedback (consultant's desk) |
|---|---|---|
| **Color** | Warm amber/ink accents | Cool slate/steel blue accents |
| **Header** | Partner card: avatar + "Sam — writing with you" | "Script Consultant Report" title bar + Run Analysis + report language |
| **Shapes** | Rounded chat bubbles, loose/conversational | Structured cards, tables, severity badges, document columns |
| **Cue** | "Someone's sitting here with me" | "A professional review, delivered" |

- Persistent **room chip** in the top bar: ✍️ Writer's Desk / 📋 Consultant's Desk.
- Active tab in the top bar is clearly highlighted with the room's accent color.
- CSS: implement via CSS variables (e.g. `--room-accent`) toggled by a `data-room` attribute on `<body>` or the view container; both rooms live in the same stylesheet with scoped theming.

---

## 7. Section 3 — The partner's voice & structural guardrails

### 7.1 Voice (personas.py + modes)

- **New persona `writing_partner`** (default): warm, subtly witty, peer energy — works *beside* the writer, never evaluates them. Name "Sam" (configurable constant).
- **New mode `peer`** (default): acknowledge-first, permission-before-critique, one idea at a time, "why do you think so?" probing, subtle humor/sarcasm carrying constructive criticism, fun but focused, never a dead end.
- Existing personas/modes remain defined (for conversational lenses and backward compatibility), but are no longer default or dropdown-driven.
- **Informed-partner lock** lives in the `peer` system prompt: the report is in context; the partner never volunteers findings and never says "the report says…" unless the writer raises the topic.

### 7.2 Guardrails (new module `screenplay_cowriter/peer.py`)

All four guardrails are pure functions where possible (unit-testable without a model).

1. **Two-phase turn (`classify_turn` + phase state).**
   - Classify the writer's message: `idea` (a statement sharing a thought), `question`, or `directive`.
   - If `idea` and the turn is not already in phase 2 → reply is forced to **phase 1**: reflect the idea back + ask what's driving it ("why do you think so?" / "what feels right about it?"). Suggestions are **structurally withheld** until the writer responds.
   - Phase state tracked on the **Branch** (a new optional `awaiting_probe` field, mirroring how persona/mode are already per-branch — forks copy the flag along with the history).
   - If the writer responds to the probe → full turn (suggestions allowed, subject to the one-idea cap).
2. **Dead-end check (`ensure_forward_momentum`).**
   - After the model reply, verify the text ends with a question, an explicit choice, or a stated next step. If not, append one from a small natural template pool (never robotic; the template pool is short and phrased in the partner's voice).
3. **One idea at a time (`cap_suggestions`).**
   - Prompt-level rule plus a light structural cap on bulleted suggestions per turn (default: 1; configurable constant). Excess suggestions are condensed by the prompt; the cap is a safety net, not a trimmer.
4. **Never-volunteer enforcement (prompt lock).**
   - Structural check: the `peer` system prompt always includes the informed-partner instruction (asserted in `build_system_prompt`); no structural post-processing needed beyond the prompt, but the instruction is locked into the default persona text.

### 7.3 Integration (engine.py)

- `peer.py` functions wrap `CoWriterEngine.send_message`:
  - phase-1 turn → single call, `awaiting_probe=True` recorded, reply returned.
  - phase-2 (writer responded) → full call with the probe context, `awaiting_probe=False`.
  - dead-end check runs on every reply.
- `Branch` gains an optional `awaiting_probe` field (backward compatible — absent = false). Existing saved sessions load fine.
- Error handling: if the model call fails during a phase-1 probe (server down), fall back to a single-turn reply with a visible note; never leave the writer with a stuck phase flag — reset `awaiting_probe` on any failed turn.

---

## 8. Section 4 — Feedback room internals

- **Report tab** → renders the existing report via `GET /api/projects/<name>/report` (coverage, findings by category, stats, verification summary). No new backend.
- **Fix Queue tab** → renders the existing `GET /api/projects/<name>/fixqueue` payload (already severity→act sorted): each finding as a card with severity badge, scene + heading, act, evidence quote, and current revision status (addressed / still_present / unknown).
- Header: `Run Analysis` (existing `POST /analyze`, keeps `force` + `report_language` semantics) + report-language picker (moved from the old chat header).
- Progress display (existing `GET /progress` + the in-header progress bar) relocates to the Feedback room header.

## 9. The bridge (Feedback → Co-write)

- Each fix-queue finding card has **"→ discuss with my partner"**.
- Clicking it: switches to the Co-write room and sends a seed message via the existing chat endpoint, e.g. *"The consultant flagged scene 14: '…issue…'. What do you think?"*
- This honors the **informed-partner** rule: the partner never volunteers; *you* bring the finding over.

---

## 10. Data flow (after)

```
Co-write room:  composer → POST /chat/.../messages → engine.send_message
                    → peer.py: classify turn
                         ├─ idea + !awaiting_probe → phase-1 reply (probe), set flag
                         └─ else → full reply (one-idea cap) → clear flag
                    → ensure_forward_momentum(reply) → return
Feedback room:  Run Analysis → POST /analyze (unchanged)
                Report tab  → GET /report   (unchanged)
                Fix Queue   → GET /fixqueue (unchanged)
                "→ discuss with my partner" → switch room + seed chat message
```

## 11. Backward compatibility & migration

- Existing sessions load unchanged (`awaiting_probe` absent → false).
- New sessions default to `writing_partner` / `peer`. Existing sessions keep their stored persona/mode; the partner card offers a **"back to Sam"** reset affordance so any user can return to the partner default.
- `/api/config` continues to expose personas/modes (used by tests and future UI); the webapp simply no longer renders dropdowns for them.
- All existing API routes are preserved; this change is additive at the UI + cowriter engine layer.

## 12. Testing plan

1. **Unit tests — `peer.py` guardrails** (`tests/test_peer_guardrails.py`, mock server, no real model):
   - `classify_turn`: statement → `idea`; question → `question`; directive → `directive`.
   - Phase-1 reply contains a probe and **no suggestions**; suggestions withheld while `awaiting_probe=True`.
   - Phase-2 turn (after writer response) allows suggestions, capped at one.
   - `ensure_forward_momentum` appends a forward question/choice when the reply dead-ends; leaves already-forward replies untouched.
   - `cap_suggestions` caps bulleted suggestions.
   - Informed-partner lock: system prompt for `writing_partner`/`peer` contains the never-volunteer instruction.
   - Branch round-trip: `awaiting_probe` survives save/load; failed turn resets the flag; forks copy the flag.
2. **Webapp tests** (`tests/test_webapp_api.py` additions or `tests/test_rooms_ui.py`):
   - New session defaults to `writing_partner`/`peer`.
   - Seed-message bridge: posting the consultant seed through the chat endpoint persists and is retrievable.
   - Report/Fix Queue endpoints unchanged (existing tests keep passing).
3. **Full suite:** all existing tests (298) stay green.

## 13. Open questions (resolved)

- *Partner name:* "Sam" as default constant; renameable later. ✅
- *Relationship memory:* deferred to v2. ✅
- *Room identity:* color + shape language per §6, no other artifacts needed. ✅
