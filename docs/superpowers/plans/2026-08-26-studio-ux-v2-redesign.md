# Studio UX v2 — Six-Direction Redesign: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans task-by-task. Steps use checkbox syntax.

**Goal:** Resolve five UX complaints (post-upload focus, click-outside dismissal,
explore-chip lifecycle, composer size, feedback-as-second-class) by producing six
complete reviewable UI/UX directions as interactive static pages, then implementing
the chosen direction as a shell restructure with zero feature regression.

**Architecture:** Phase A builds six self-contained-ish HTML pages sharing one
*shell contract* (stable rooms + data-fid hooks) plus a shared component stylesheet
and interaction script, so any winner implements without re-deriving structure.
Phase B migrates the real app onto the winning shell in thin slices: rooms, then
R1–R5 behaviors, then test migration. Follows docs/UI_REDESIGN_PROPOSAL.md's
reskin-and-restructure verdict while superseding its side-panel stance toward
three equal rooms (owner decision).

**Tech Stack:** Vanilla HTML/CSS/JS. No build step. Zero external network requests
(privacy-first). System font stacks in designs; production keeps self-hosted woff2.
Flask statics + ?v= cache bumps. Tests: 9 Playwright suites + tests/js/core.test.js.

## Global Constraints

- Zero external requests: system font stacks in designs; production keeps
  self-hosted woff2 (webapp/fonts/). Indic scripts hit system fallbacks.
- No build step, no frameworks. DOM-free helpers stay in core.js (node --test).
- Motion respects prefers-reduced-motion. Keyboard reachable; :focus-visible;
  touch targets >=44px.
- API contracts unchanged: /api/config, SSE chat stream token->done, report
  payloads, "demo craft model" strings.
- Windows CRLF care; ruff + pytest green before commits; ?v= bumps when
  style.css/app.js/core.js change.

## The Five Requirements — verified in EVERY design

- R1 Post-upload lands Feedback-ready: upload success presents the Feedback
  Room's ready state, Run Analysis primary, script one glance away.
- R2 Click-outside dismisses partner surfaces everywhere (drawer, consultant,
  quote floats, idea pill); Esc works; explicit close kept.
- R3 Explore-chip lifecycle: visible before first send -> vertical icon rail
  after -> hover/focus reveals label -> "..." restores all.
- R4 Composer fits the writing: >=4 lines visible, autogrows to ~40vh then
  scrolls internally; Enter sends, Shift+Enter newlines; quote chip above.
- R5 Co-write and Feedback are first-class rooms; report is a reading surface
  (score strip, category sections, verify badges); Fix Queue peer tab.

## Feature Inventory — findable in each design

- Shell: brand+connection dot, new-project, Ideas(count/flyout/+New idea),
  On-the-shelf, Your library, Dawn/theme, Settings, error banner.
- Welcome/dashboard: greeting, dropzone(.fdx/.pdf/.txt/.fountain/.md), upload
  status, idea button, sample page, dashboard cards(status/stats/actions),
  how-to steps, privacy footnote, shortcut hint.
- Project bar: home, title, branch switcher, room switcher, Ctrl+K palette.
- Structure rail: scenes outline, characters(+stage-with), Stash, margin notes
  +form, Beat Board, Compare, collapse/edge-tab.
- Script pane: search, finding summary, Premise btn, Focus, Reader, Undo/Redo,
  Revise desk, exports(fountain/fdx/txt/print/backup.zip), draft bar(select/
  upload/status), diff banner, scenes render, quote-float, stash-float,
  note-float, divider resize.
- Idea phase: canvas(autosave), premise card(title/logline/premise/questions/
  save), graduate-to-pages, structure panel, Sameer pill, chips(R3).
- Co-write: persona/mode lenses, partner card, reset persona, Sam's-notes,
  clear chat, messages(streaming cursor), quote-card, history pop(arrow-up),
  composer(R4).
- Feedback: language select(5), progress(bar/%/ETA/pipeline hover), Run
  Analysis, Re-parse, Retry failed, Report|FixQueue tabs, markdown render,
  queue rows/statuses, export .md, empty/loading/error states.
- Views: Beat Board(drag/restore/export/print/save), Compare(from-select diff),
  Revision desk(scene nav+findings+status).
- Modals: Settings(url/timeout/fast model/turn cap/test), Rewrite(finding/
  instruction/candidates/apply), Fork, Sam's notes.
- Status strip: model+conn card, connection, metrics, sprint timer, elapsed, dawn.

## Shell Contract (all six obey)

- Rooms: data-room="desk|cowrite|feedback"; modes: welcome/idea/beatboard/
  compare/revision. Feature elements carry data-fid="<id>" from inventory.
- Shared assets: ux2026/shared/base.css (components) + shared/app.js
  (~130-line identical behaviors). Each page adds only its identity skin
  <style> and its own structural markup. Production inlines equivalents.
- Behaviors: room switching; R2 outside-click dismissal; R3 rail collapse;
  R4 autogrow; Ctrl+K palette stub; modal open/close; R1 upload-finished demo.

## File Structure

- Create docs/design/ux2026/: index.html hub + console-dark + paper-desk +
  spotlight-stage + splitline + margins + atlas-grid (.html) + shared/.
- Phase B modifies screenplay_studio/webapp/{index.html,style.css,app.js},
  all tests/e2e_browser_*.py, README, NOTES.md.

## Phase A tasks

- [x] A1 plan + inventory (this file)
- [ ] A2 shared base.css + app.js; six pages with distinct identities;
      sample data: "The Late Hour" 3 scenes, chat thread w/ streaming cursor,
      report excerpt w/ verify badges, fix queue rows; rationale + R1-R5 +
      inventory checklist footer per page; hub compares all six.

## Phase B tasks

- B1 pick winner+runner-up -> freeze tokens as CSS custom properties on
  style.css; Dawn becomes a token swap. Commit feat(ui): design tokens.
- B2 room router, legacy ids aliased during migration. Verify pytest
  tests/test_webapp_api.py -q + manual --demo-model boot. Commit shell router.

## Design Intelligence Applied (ui-ux-pro-max + skills)

- Database default for this query (navy SaaS + Fredoka/Nunito, motion-heavy
  hero pattern) was REJECTED as the templated look; kept only as contrast.
- Adopted: "Dramatic dark + spotlight gold" palette family (#0F0F23 bg,
  #1E1B4B primary, #CA8A04 accent) -> spotlight-stage. "Warm ink + amber on
  cream" (#FFFBEB/#78716C/#D97706) -> paper-desk starting point. Magazine
  Style pairing (Libre Bodoni + Public Sans) and Minimalist Monochrome
  Editorial triple-stack -> margins (system-font equivalents offline).
- UX rules honored: visible labels over placeholder-only; min touch 44px;
  hover never sole carrier (R3 rail reveals on focus too); empty states give
  next action; 150-300ms transitions; prefers-reduced-motion.
- minimalist-ui protocol governs paper-desk exclusively (hairline #EAEAEA,
  flat, no gradient/shadow/pill-large, no emoji icons, pastel spot tags).
- frontend-design anti-generic calibration: cream+serif+terracotta,
  black+acid-green, broadsheet-hairline defaults each avoided or subverted;
  one signature element per page; copy written from user side.

## The Six Directions (contrasting identities)

1. paper-desk — Writer's warm desk. Cream #FBFAF7, warm ink #2F3437,
   amber #D97706 accent, oxblood #9F2F2D revision marks; Georgia display +
   system sans + ui-monospace; hairline borders, flat. Signature: manuscript
   margin annotations + proofread-mark language. (minimalist-ui protocol.)
2. spotlight-stage — Screening room. Indigo-charcoal #12121F, card
   #1B1B30, tungsten gold #E8B33D, warm white text; cinematic framing.
   Signature: scenes as film frames on a sprocket rail; house-lights dimming.
3. console-dark — Production terminal. Slate #0D1117, phosphor cyan/green
   data accents, dense mono labels, stat blocks. Signature: everything reads
   like a call-sheet console; keyboard-first hints everywhere.
4. atlas-grid — Bento product console, light. Cool gray #F6F7F9 canvas,
   white 12px tiles, electric violet #6D28D9 single accent. Signature: the
   whole studio is an asymmetric bento; feedback score is the hero tile.
5. splitline — Literal two-room thesis. Hard vertical split co-write |
   feedback, warm half vs cool half, red seam divider, black type on white.
   Signature: the seam + mirrored room headers; drag to rebalance.
6. margins — Editorial magazine. Gallery white, Didot/Bodoni-stack display,
   cobalt #1D4ED8 + black, oversized numerals, sparse rules. Signature: the
   feedback report laid out as "The Notes Issue" cover story with folios.

## Placeholder Positions — brainstormed from two POVs

Writer POV ("I just uploaded; where do I look?"):
- Upload success lands in Feedback room ready-state (R1): Run Analysis is
  the biggest primary control on screen, verdict slot empty with an honest
  "about 40 seconds" promise; script stays one glance away (reading pane or
  one-tab switch) — never buried behind a small side button.
- Composer anchors the co-write room bottom, autogrowing from 2 lines to
  ~40vh then scrolling internally (R4); persona lenses sit directly above
  it; quote-chip floats above composer when text is selected.
- Explore chips live INSIDE the composer's empty state as "one tap, Sameer
  runs with it" suggestions (R3). After first send they collapse to a slim
  vertical rail hugging the composer's left edge; hover OR focus expands the
  label inline; a bottom "..." icon restores all chips.
- Margin notes anchor next to the selection that raised them; stash keeps
  cut lines one undo away; scenes/characters rail stays collapsible.

Feedback-provider POV ("Give me the verdict, then the evidence"):
- Report opens top-to-bottom like a review: verdict strip first (overall
  score oversized, draft compared, confidence), category sections beneath,
  every note severity-coded with a jump-to-scene link and grounded-evidence
  verify badge.
- Fix Queue is a peer tab, not a footnote: triage rows with status pills
  (open / applying / applied / skipped) + export .md for outside work.
- Empty/loading/error states each name the next action (Run analysis /
  Retry failed categories / what failed and why).
- Progress shows pipeline stage on hover of the bar (parse -> craft ->
  continuity -> verify) so waiting reads as process, not freeze.

## Self-Critique (designer's-eye review of THIS plan)

Scores (what a 10 needs in parens):
- Goal clarity 9/10 (a 10 names the single decision these pages exist for:
  pick one identity + placeholder map — stated up top now).
- Requirement coverage 9/10 (R1-R5 verified per page; a 10 also verifies
  minor features like fork/rewrite modals visually, not just data-fid).
- Distinctiveness 8/10 (six identities span warm/dark/terminal/bento/
  graphic/editorial; a 10 would user-test recognizability blind).
- Scope honesty 6/10: six full-feature pages is heavy; mitigated by shared
  base.css (~60% common) + inventory footer; risk = shallow coverage of
  rare surfaces (fork, compare, beat board get compact affordances).
- Technical risk 7/10: static pages can't prove streaming under real
  latency or SSE edge cases; Phase B e2e migration carries the real proof.
- Testability 6/10: Phase A is human-review only by design; Phase B tasks
  must pin which of the 9 suites each slice updates.
- Motion & accessibility 8/10: reduced-motion, focus-reveal rail, 44px
  targets planned; a 10 audits contrast on every skin (gold-on-indigo and
  violet-on-gray need checking).
Honest gaps: (1) sample data covers one project/one report shape; (2)
splitline's dual-theme halves may fight form controls; (3) Phase B effort
underestimated if winner diverges structurally — shell contract is the
insurance; (4) no mobile story yet beyond responsive intent.
Verdict: ship Phase A as specced; re-critique with pages live before B.
