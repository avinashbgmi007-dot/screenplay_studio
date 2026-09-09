# Spec: Six Full-Journey UIUX Redesign Previews

Date: 2026-08-27
Status: Approved

## Purpose
Produce 6 static, interactive HTML mockups covering the whole app journey so a winning UI direction can be chosen for the real Screenplay Studio redesign. Solves five writer-reported problems: script page not first-class on open; summoned panes lacking click-outside dismissal; explore chips never tucking away; cramped one-line composer; feedback report buried as a corner pane.

## Deliverables
`screenplay_studio/webapp/preview-redesigns/`:
- `index.html` — gallery with live switcher + screenshots
- `noir.html`, `paper.html`, `brutal.html`, `swiss.html`, `terminal.html`, `organic.html`

Served at `/preview-redesigns/index.html` by the existing Flask server. Zero changes to app code.

## Each mockup covers the full journey (preview bar navigation)
1. **Welcome/Bookshelf** — project shelf, upload/new-idea entry points
2. **Desk** — script pages are the hero, full-bleed; co-writer & doctor as edge-tab summons
3. **Co-Writer Room** — Sameer chat as its own room
4. **Feedback Room** — long-form report reading doc (verdict hero, severity-coded finding cards grouped by category, jump-to-scene anchors)

## Shared behavior spec (wired in all six)
- **Script-first:** opening a project lands on the pages; partner tools stay minor until summoned.
- **Click-outside dismissal:** any summoned pane closes on outside click (idea-room model).
- **Explore chips:** visible until first input → collapse to vertical icon stack → hover reveals label one icon at a time.
- **Composer:** auto-grows 1→~6 lines, text always visible.
- Placeholders for real features: Stash, margin notes, beat board, sprint timer, status strip, severity dots.

## Six directions
① Noir Desk (dark lamp-lit amber/ink) · ② Paper Atelier (rice-paper serif) · ③ Brutal Print (editorial rules/hard shadows) · ④ Swiss Signal (minimal grid, one accent) · ⑤ Terminal Draft (mono phosphor) · ⑥ Organic Magazine (warm magazine feature layout). Rooms differ per design: top-room pills vs book-spine tabs vs segmented control vs command palette vs magazine contents strip.

## Constraints
Self-contained single files, no CDN dependency required to render (graceful if fonts absent), light per-file JS only (~150 lines), `prefers-reduced-motion` respected, responsive to ~1024px minimum.

## Testing/verification
Browser-check each file: all four screens reachable from preview bar, the four behaviors demonstrable, zero console errors, zero horizontal overflow; screenshots captured into `preview-redesigns/shots/`; gallery embeds verified images.

## Out of scope
Backend/API changes; wiring mocks into the real app (post-selection work).
