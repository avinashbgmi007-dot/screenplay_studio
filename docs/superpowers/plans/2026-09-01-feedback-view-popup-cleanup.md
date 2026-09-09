# UI/UX Integration Plan — Toolbar, Popup, Feedback View

> **For agentic workers:** Execute tasks in order. Each task is independently testable.

**Goal:** Reduce toolbar clutter, add contextual text selection, and build a 3-panel Feedback View where the writer can see findings on the script while chatting with both Sameer and Dr. Sushruta simultaneously.

**Architecture:** The Feedback View is a new full-screen view (like Beat Board/Revision) with three panels. The toolbar gets a dropdown overflow menu. A floating popup appears on text selection in context-appropriate locations.

**Tech Stack:** Vanilla JS, CSS custom properties, existing design tokens (--accent, --glass, --line, etc.)

---

## Task 1: Toolbar Overflow Menu ✅ DONE

**Files:**
- Modify: `screenplay_studio/webapp/index.html` (lines 254-271)
- Modify: `screenplay_studio/webapp/style.css` (after .script-actions)
- Modify: `screenplay_studio/webapp/app.js` (after reader-btn listener)

**What changed:** Exports, Reader, Beat Board, Compare, Print moved behind ⋯ dropdown. Undo/Redo hidden (keyboard shortcuts still work). Visible: Search | Findings | Focus | Revise | ⋯

---

## Task 2: Status Bar Simplification ✅ DONE

**Files:**
- Modify: `screenplay_studio/webapp/index.html` (lines 368-378)
- Modify: `screenplay_studio/webapp/style.css` (after status-btn)

**What changed:** Model info hidden by default, revealed on hover of connection dot. Metrics hidden. Visible: connection dot | sprint timer | elapsed | Dawn

---

## Task 3: Contextual Text Selection Popup ✅ DONE

**Files:**
- Modify: `screenplay_studio/webapp/index.html` (before script tags)
- Modify: `screenplay_studio/webapp/style.css` (new section)
- Modify: `screenplay_studio/webapp/app.js` (new IIFE after init)

**What it does:** When user highlights text, a floating popup appears with context-appropriate actions:
- Idea Room: Ask Sameer, Add to logline, Margin note, Stash
- Script reading: Ask Sameer, Ask Consultant, Margin note, Stash  
- Revision View: Discuss w/ Sameer, Discuss w/ Consultant, Rewrite, Locate

---

## Task 4: Feedback View — 3-Panel Layout

**Files:**
- Modify: `screenplay_studio/webapp/index.html` (new section after revision-view)
- Modify: `screenplay_studio/webapp/style.css` (new section)
- Modify: `screenplay_studio/webapp/app.js` (new functions)

**Layout:**
```
┌─────────────┬──────────────────────────┬─────────────┐
│  Sushruta   │     Script + Finding     │   Sameer    │
│  (consult)  │        Cards             │  (co-writer)│
│  300px      │     flex: 1              │   300px     │
│             │                          │             │
│  findings   │  Scene 1: [text]         │  rewrite    │
│  + chat     │  ┌──HIGH──┐ ┌──MED──┐   │  suggestions│
│             │  │charact │ │dialog │   │  + chat     │
│             │  └────────┘ └───────┘   │             │
│  [Ask...]   │                          │  [Ask...]   │
└─────────────┴──────────────────────────┴─────────────┘
```

**Key decisions:**
- Finding cards pinned BELOW each scene (not overlaid)
- Each card: severity badge + category + description + Locate/Rewrite/Discuss buttons
- "Discuss" sends finding context to the partner's chat
- Center scrolls independently
- Both chat panels narrow (300px) to maximize script space
- Accessible via room toggle "Feedback" button or `f` key

**Step 4.1: Add HTML section**

Add after `#revision-view` section in index.html:
```html
<section id="feedback-view" class="view" style="display:none;">
  <div class="fv-header">
    <span class="fv-title">Feedback View</span>
    <span class="fv-sub">Findings on the page, both partners at hand.</span>
    <button id="fv-close" class="btn-secondary" type="button">← Back to the page</button>
  </div>
  <div class="fv-body">
    <!-- Left: Sushruta chat -->
    <div class="fv-panel fv-consult">
      <div class="fv-panel-head">
        <div class="fv-avatar consult">D</div>
        <div><div class="fv-name">Dr. Sushruta</div><div class="fv-role">script consultant</div></div>
      </div>
      <div id="fv-consult-messages" class="fv-messages"></div>
      <form id="fv-consult-composer" class="fv-composer">
        <input id="fv-consult-input" type="text" placeholder="Ask Dr. Sushruta..." class="inp">
        <button type="submit" class="btn-primary btn-small">➤</button>
      </form>
    </div>
    <!-- Center: Script with finding cards -->
    <div class="fv-script" id="fv-script"></div>
    <!-- Right: Sameer chat -->
    <div class="fv-panel fv-cowrite">
      <div class="fv-panel-head">
        <div class="fv-avatar cowrite">S</div>
        <div><div class="fv-name">Sameer</div><div class="fv-role">co-writer</div></div>
      </div>
      <div id="fv-cowrite-messages" class="fv-messages"></div>
      <form id="fv-cowrite-composer" class="fv-composer">
        <input id="fv-cowrite-input" type="text" placeholder="Rewrite suggestion..." class="inp">
        <button type="submit" class="btn-primary btn-small">➤</button>
      </form>
    </div>
  </div>
</section>
```

**Step 4.2: Add CSS**

```css
/* Feedback View — 3-panel layout */
.fv-header { display: flex; align-items: center; gap: 12px; padding: 10px 18px; border-bottom: 1px solid var(--line-soft); flex-shrink: 0; }
.fv-title { font-family: var(--font-typewriter); font-size: 15px; color: var(--text); }
.fv-sub { font-family: var(--font-mono); font-size: 10px; color: var(--text-muted); }
.fv-body { flex: 1; display: flex; min-height: 0; }
.fv-panel { width: 300px; flex-shrink: 0; display: flex; flex-direction: column; }
.fv-consult { border-right: 1px solid var(--line-soft); }
.fv-cowrite { border-left: 1px solid var(--line-soft); }
.fv-panel-head { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-bottom: 1px solid var(--line-soft); }
.fv-avatar { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; font-size: 12px; font-weight: bold; color: #1a140d; }
.fv-avatar.consult { background: radial-gradient(circle at 35% 30%, var(--consult), var(--consult-deep)); }
.fv-avatar.cowrite { background: radial-gradient(circle at 35% 30%, var(--accent), var(--accent-deep)); }
.fv-name { font-family: var(--font-typewriter); font-size: 12px; color: var(--text); }
.fv-role { font-family: var(--font-mono); font-size: 9px; color: var(--text-muted); }
.fv-messages { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 10px; }
.fv-composer { padding: 8px 12px 12px; border-top: 1px solid var(--line-soft); display: flex; gap: 6px; }
.fv-composer .inp { flex: 1; }
.fv-script { flex: 1; overflow-y: auto; padding: 20px 32px; min-width: 0; }
.fv-script-inner { max-width: 720px; margin: 0 auto; }
/* Finding cards below scenes */
.fv-finding-cards { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 20px; }
.fv-finding-card { flex: 1; min-width: 200px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 6px; background: var(--glass); }
.fv-finding-card.high { border-left: 3px solid var(--danger); }
.fv-finding-card.medium { border-left: 3px solid var(--lamp); }
.fv-finding-card.low { border-left: 3px solid var(--ok); }
.fv-fc-header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.fv-fc-badge { font-family: var(--font-mono); font-size: 9px; font-weight: 600; padding: 1px 6px; border-radius: 4px; }
.fv-fc-badge.high { background: rgba(251, 113, 133, 0.15); color: var(--danger); }
.fv-fc-badge.medium { background: rgba(232, 162, 79, 0.15); color: var(--lamp); }
.fv-fc-badge.low { background: rgba(143, 174, 126, 0.15); color: var(--ok); }
.fv-fc-cat { font-family: var(--font-typewriter); font-size: 11px; color: var(--text); }
.fv-fc-desc { font-size: 11px; color: var(--text-muted); line-height: 1.4; }
.fv-fc-actions { display: flex; gap: 4px; margin-top: 6px; }
```

**Step 4.3: Add JavaScript**

Add functions to app.js:
- `openFeedbackView()` — shows the feedback-view section, renders script with finding cards, renders chat panels
- `closeFeedbackView()` — hides the section, returns to workspace
- `renderFvScript()` — renders script scenes with finding cards pinned below each
- `renderFvFindingCards(sceneIndex)` — returns HTML for finding cards for a scene
- Wire room-toggle Feedback button and `f` key to open the new view

**Step 4.4: Modify room toggle**

Currently clicking "Feedback" opens the drawer with the consultant panel. Change it to open the full Feedback View instead.

**Step 4.5: Test**

- Open a project with analysis results
- Click "Feedback" in room toggle or press `f`
- Verify 3-panel layout renders
- Verify finding cards appear below each scene
- Verify both chat panels work
- Verify "Back to the page" returns to workspace

---

## Task 5: Wire Everything Together

**Files:**
- Modify: `screenplay_studio/webapp/app.js`

**What to verify:**
- Toolbar overflow menu opens/closes, items work
- Status bar shows connection dot, model info on hover
- Text selection popup appears in Idea Room, script, Revision View
- Feedback View opens from room toggle and `f` key
- All keyboard shortcuts still work (Ctrl+Z, Ctrl+Shift+Z, etc.)
- No console errors
- Cache-bust version bumped
