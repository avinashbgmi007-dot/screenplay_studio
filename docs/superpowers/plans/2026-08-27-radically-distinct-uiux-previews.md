# Radically Distinct UIUX Previews — Implementation Plan v2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 6 palette-swap previews with 6 structurally distinct interactive mockups per spec `2026-08-27-radically-distinct-uiux-redesigns-design.md`.

**Architecture:** Each file gets a different DOM skeleton and navigation paradigm; the shared behavioral contract (script-first, click-outside dismissal, chips collapse, growing composer, dedicated rooms) is re-expressed in each skeleton's own markup. Overwrite the existing files in place.

**Tech Stack:** Standalone HTML/CSS/JS single files; served by existing Flask static handler.

## Global Constraints

- Same as v1: standalone files, reduced-motion respected, no horizontal overflow at 1440×900, zero app-code changes.
- Same class contract: `data-screen`, `go()`, `.pane-pop` (or per-design sheet), `.explore-chips` + `.collapsed`, `.composer`, `.sev-dot`.
- Preview bar (mockup chrome) stays; everything below it is the design's own structure.

## Structural Assignments (the anti-copy-paste core)

| File | DOM skeleton | Room navigation | Partner summon |
|---|---|---|---|
| noir | Full-bleed centered manuscript, no desk-top bar | Right-edge vertical gutter pills ONLY | Gutter pill → overlay sheet slides from right; sheet has "open full room" |
| paper | 3 persistent columns (nav / script / room) | Right column has room tabs (Sameer/Doctor/Queue); center swaps to report | Right column IS the room; report swaps center column |
| brutal | Corkboard card grid desk | Newspaper masthead sections row | Bottom dock bar → expands upward sheet |
| swiss | 2-pane split workspace | Top-center segmented control; panes maximize on toggle | Right pane hosts co-writer; left stays script |
| terminal | Zero-chrome mono editor + status line | ⌘K palette + `:commands` in status line | Palette action or `:sam` → centered overlay window |
| organic | Report-as-hero magazine spread | Contents strip (left) doubles as room nav | Right "Sameer's Study" rail with slide-out memo card |

## Tasks

### Task 1: noir.html — Manuscript Stage
- [ ] Build: centered column max 760px, no desk-top bar; gutter pills (S/D/📥) right edge vertical; sheets slide from right 400px; full rooms reached via sheet header link + palette-free top-right minimal wordmark nav (text links only, part of page not a bar).
- [ ] Verify: 4 screens, behaviors, distinct skeleton.
- [ ] Commit.

### Task 2: paper.html — 3-Column Editing Suite
- [ ] Build: CSS grid 240px | 1fr | 380px persistent; left = act/scene tree w/ flags; center = script pages (or report when in feedback); right = tabbed room (Sameer/Doctor/Fix Queue) with composer + chips.
- [ ] Verify + commit.

### Task 3: brutal.html — Corkboard + Bottom Dock
- [ ] Build: desk = responsive grid of scene cards (severity dots, page count, drag-hint); masthead sections nav; bottom dock = collapsed bar w/ Sameer face + input preview; click/typing expands sheet upward 420px.
- [ ] Verify + commit.

### Task 4: swiss.html — Split Workbench
- [ ] Build: workspace grid: left script pane / right pane with mode switch (Co-Writer | Report); draggable-feel divider (visual); segmented control top-center; "focus" buttons maximize either pane.
- [ ] Verify + commit.

### Task 5: terminal.html — Command Palette Desk
- [ ] Build: full-screen mono buffer with line numbers; bottom status line (vim-like) with `:command` input; ⌘K palette center overlay; report = log blocks; rooms only via palette/commands.
- [ ] Verify + commit.

### Task 6: organic.html — Magazine Report-First
- [ ] Build: default desk screen opens on the feature-article report with embedded script excerpt cards ("from the pages" pull boxes); left contents strip = report TOC + room links; Sameer Study = right rail memo card that slides wider.
- [ ] Verify + commit.

### Task 7: Gallery + verification + NOTES
- [ ] Update index.html card descriptions to structural one-liners.
- [ ] Contract grep across 6 files; Flask 200 test; commit; NOTES.md entry.

## Self-Review
- Spec coverage: all 6 skeletons mapped to spec §2; contract §3 re-checked per task; constraints §4 global.
- No placeholders; names consistent with v1 contract classes.
