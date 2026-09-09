# Six UIUX Redesign Previews Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build 6 self-contained static HTML mockups (`noir`, `paper`, `brutal`, `swiss`, `terminal`, `organic`) covering the full app journey plus a gallery, under `screenplay_studio/webapp/preview-redesigns/`.

**Architecture:** Each design is one single-file HTML page with a fixed preview bar (switches 4 screens: Welcome/Bookshelf → Desk → Co-Writer → Feedback). A small shared behavioral pattern (~120 lines JS) is re-implemented per file with design-specific markup: click-outside dismissal for summoned panes, explore-chips collapse-to-icons after first input, auto-growing composer. No shared assets; each file is fully standalone so any can be deleted independently.

**Tech Stack:** Vanilla HTML/CSS/JS. Google Fonts via `<link>` with system fallbacks (graceful if offline). No build step; served by the existing Flask static handler at `/preview-redesigns/`.

## Global Constraints

- Zero changes to any existing app file.
- Each `*.html` must render standalone by double-clicking the file.
- `prefers-reduced-motion` respected (transitions disabled when set).
- Minimum usable width ~1024px; no horizontal overflow at 1440×900.
- Sample project name "Pain" / sample script scenes used as placeholder content.
- Behaviors wired in ALL six: script-first desk, click-outside dismissal, chips collapse, growing composer.
- Severity dots language: high=red, med=amber, low=muted.

## File Structure

```
screenplay_studio/webapp/preview-redesigns/
├── index.html      # gallery + live iframe switcher + screenshot cards
├── noir.html       # dark cinematic lamp-lit amber/ink
├── paper.html      # light rice-paper serif, ink-green accent
├── brutal.html     # editorial black rules, hard offset shadows
├── swiss.html      # minimal light grid, one cobalt accent
├── terminal.html   # mono phosphor pro mode
├── organic.html    # warm magazine serif feature-article layout
└── shots/          # captured screenshots (verification evidence)
```

---

### Task 1: Common screen + behavior contract

**Files:** Create `screenplay_studio/webapp/preview-redesigns/noir.html` (this task also locks the contract all others copy).

**Interfaces (produced, reused verbatim in Tasks 2–6):**
- Screens as `<section data-screen="welcome|desk|cowrite|feedback">`; only `.active` visible.
- Preview bar: buttons `[data-go="welcome"]` etc.; JS `go(name)` toggles `.active`.
- Summoned panes: elements with class `pane-pop`; opened by edge tabs (`data-open="#id"`); `document.addEventListener('click')` closes any `.pane-pop.open` whose click target is outside it and not its opener.
- Chips block: `.explore-chips` with chip children; on first `input` event in the composer textarea add class `.collapsed` to chips container → CSS renders icons vertically; hover reveals label span (CSS-only).
- Composer: `<textarea class="composer">` with `input` listener: `el.style.height='auto'; el.style.height=Math.min(el.scrollHeight,160)+'px'`.
- Reduced motion: wrap all transitions in `@media (prefers-reduced-motion: no-preference)`.

- [ ] **Step 1:** Write noir.html with all four screens, preview bar, behaviors above, desk showing full-bleed script pages first with co-writer/doctor edge tabs, feedback room as long-form report (verdict hero + severity finding cards + jump anchors).
- [ ] **Step 2:** Open in browser (Thorium/system default): navigate all 4 screens; test pane dismissal, chip collapse, composer growth. Fix issues.
- [ ] **Step 3:** Commit: `git add screenplay_studio/webapp/preview-redesigns/noir.html && git commit -m "feat(previews): noir redesign mockup + shared journey contract"`

### Task 2: paper.html, brutal.html

Same contract as Task 1, distinct aesthetics/markup:

- **paper.html** — rice-paper cream (#f7f2e9), Cormorant/serif stack w/ fallback to Georgia; book-spine tabs for rooms (vertical tabs on left); report styled like a typeset manuscript review; ink-green accent (#3d5a4c).
- **brutal.html** — white bg, Archivo Black-style condensed headings (fallback Arial Black), 2px black rules, hard 6px offset shadows, zero border-radius, linear hovers; rooms as top-room pills; orange/cobalt signals.
- [ ] Step 1: build paper.html per contract; Step 2: browser-check all 4 screens + behaviors; Step 3: commit `feat(previews): paper atelier mockup`.
- [ ] Step 4: build brutal.html; Step 5: browser-check; Step 6: commit `feat(previews): brutal print mockup`.

### Task 3: swiss.html, terminal.html, organic.html

- **swiss.html** — near-white #fafafa, Inter-ish sans (fallback Segoe UI), strict 12-col grid, hairline rules, single cobalt accent (#2545d9); segmented-control room switcher; report as numbered sections.
- **terminal.html** — #0a0f0a bg, phosphor green text (mono stack Consolas/Menlo), scanline overlay (subtle), command-palette-driven navigation (`⌘K` opens palette listing screens); report rendered as categorized log blocks with severity prefixes `[HIGH]`.
- **organic.html** — warm cream + terracotta/olive, magazine masthead, two-column report article flow, contents-strip navigation; generous whitespace.
- [ ] Steps mirror Task 2 pattern (build → check → commit each).

### Task 4: Gallery index.html + screenshots + verification sweep

**Files:** Create `index.html`; create `shots/*.png` (captured).

- [ ] Step 1: Capture desktop screenshots of each file's desk screen into `shots/`.
- [ ] Step 2: Build gallery: card per design (screenshot, palette strip, one-line personality, "Open" links file); a live iframe switcher row.
- [ ] Step 3: Verification pass: serve Flask webapp, visit `/preview-redesigns/index.html`, confirm gallery loads, every card's link works, every file shows zero console errors and no horizontal overflow at 1440×900.
- [ ] Step 4: Update NOTES.md entry; commit everything: `feat(previews): gallery + screenshots for 6 redesign previews`.

## Self-review notes

- Spec coverage: welcome/desk/cowrite/feedback screens ✓ (tasks 1–3), behaviors ✓ (task 1 contract reused), gallery+shots ✓ (task 4), reduced-motion ✓ (global constraint).
- Placeholders: none — all steps carry concrete specs or files.
- Naming consistency: `data-screen`, `go()`, `pane-pop`, `explore-chips`, `composer`, `sev-dot` classes identical across all six files.
