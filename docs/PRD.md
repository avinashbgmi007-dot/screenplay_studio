# PRD — Script Doctor Studio

Product Requirements Document. The feature list, user stories, and acceptance criteria.
Last synced 2026-09-06 against the shipped implementation.

**Companion docs:** user stories here are cross-referenced to `docs/UI_UX_SPECIFICATION.md`
(the full UI/interaction/API contract — its §11 acceptance checklist is the engineering
sign-off), `docs/USER_PERSONAS.md` (who), `CONTEXT.md` (domain glossary).

## Product summary

Local, privacy-first screenplay analysis & co-writing suite. A writer uploads a screenplay
(`.fdx`/`.pdf`/`.txt`/`.fountain`/`.md`); the app parses it deterministically, runs an
LLM-powered 12-category analysis grounded in a 263-rule attributed knowledge base (every
quote verified against the actual text), and offers a conversational co-writer (Sameer)
plus a script-doctor report (Dr. Sushruta). Everything runs on the user's machine against
a user-run llama-server; a built-in demo craft model fills in honestly (amber) when no
server is reachable.

## Non-negotiable principles

1. **Script-first** — the manuscript is the center; analysis and chat orbit it.
2. **Privacy-first** — zero third-party calls; fonts self-hosted; nothing leaves the machine.
3. **Evidence-first** — every finding's quote is verified (fuzzy 0.72); unverifiable
   findings are flagged, never dropped.
4. **Diagnose/prescribe split** — analysis diagnoses; the co-writer prescribes.
5. **Fail loudly** — errors are shown with actionable messages, never silent.
6. **Honest status** — green = your model verified; amber = demo model; red = unreachable.
7. **Boring is good** — no database, no framework; file-based state.

## Epics & user stories

### Epic 1 — Get a script on the desk
- **US-1.1** As a writer, I upload a screenplay in my format (.fdx/.pdf/.txt/.fountain/.md)
  so my pages are on the desk without conversion. *AC: upload accepted via dropzone or
  click-drag; parser reports confidence + scene/character counts; unsupported/broken files
  fail with actionable errors.*
- **US-1.2** As a writer, I open the bundled sample project so I can try the desk before
  risking my own pages. *AC: "Open the sample page" creates/opens "The Late Hour"; dedupes
  if it already exists.*
- **US-1.3** As a writer with unreadable project files, my project stays visible on the
  shelf flagged "⚠ unreadable", so I can delete or retry it. *AC: flag-don't-drop; open
  shows the error; delete still works.*
- **US-1.4** As a returning writer, the app restores my last session (project, idea, view,
  scene) on reload. *AC: session restore covers all views incl. Feedback View.*
- **US-1.5** As a writer, I pick the report language (English/Tenglish/Hindi/Telugu/Tamil)
  before running analysis. *AC: selector drives `report_language`; report renders in that
  register; quotes stay verbatim (verification unaffected).*

### Epic 2 — Understand the diagnosis
- **US-2.1** As a writer, I run the full analysis so I get a structured report with
  verified, rule-attributed findings. *AC: 12 categories + deterministic passes run; each
  finding carries category/severity/issue/why-it-matters/scene refs/evidence quote/rule
  id/verification status; progress shows 20 stages with % and ETA.*
- **US-2.2** As a writer with a flaky local model, only the failed categories re-run when
  I retry. *AC: "⚠ Retry failed (N)" re-runs just failed categories and merges into the
  existing report; a failed retry preserves the previous partial record.*
- **US-2.3** As a writer, I browse the report in the Feedback room: Coverage card,
  Setup/Payoff ledger, Pacing bars, Character dials, Writer's Mirror, findings by
  category. *AC: all sections render per spec §4.4; click a pacing bar jumps to scene.*
- **US-2.4** As a writer, I work the Fix Queue by severity/act and see findings resolve
  (dawn meter) as I edit. *AC: fix queue sorted severity→act; Locate/Rewrite/Discuss/
  Dismiss-Restore actions; dawn meter = addressed/(open+addressed).*
- **US-2.5** As a writer, I dismiss findings that don't apply and can restore them.
  *AC: dismiss persists; "Show/Hide dismissed" appears when any exist.*

### Epic 3 — Revise the pages
- **US-3.1** As a writer, I edit any line inline (double-click, or `Enter` on the line the
  arrows walk me to) with undo/redo so my changes are safe — no mouse required. *AC: edits apply via the edits path; change stars mark new lines with
  hover "was: <old>"; Ctrl/⌘Z undo, Shift+Z redo; Discard edits clears all (confirmed).*
- **US-3.2** As a writer, I ask the doctor to rewrite a scene against a finding and choose
  which candidates to apply. *AC: rewrite modal shows old→new candidates with checkboxes;
  Apply runs through edits/apply (undoable); skipped lines listed with reasons.*
- **US-3.3** As a writer, I see whether a finding is addressed or still present as I edit.
  *AC: findings_status recomputes on every apply/undo/redo; Problem Board + Revision view
  reflect it live.*
- **US-3.4** As a writer, I keep a working copy distinct from my source. *AC: edits mutate
  working.json; export (fountain/fdx/txt) writes from the working copy; source untouched.*

### Epic 4 — Drafts & structure
- **US-4.1** As a writer, I upload new drafts and switch the active one. *AC: drafts
  listed with name/source/time; activate swaps source+parsed+report snapshot; diff banner
  appears.*
- **US-4.2** As a writer, I compare two drafts side by side. *AC: per-scene aligned columns
  with same/changed/added/removed line kinds; from-select; friendly empty state on
  single-draft projects; Back/Esc exits.*
- **US-4.3** As a writer, I reorder scenes on the Beat Board and export the reordered
  draft. *AC: drag + ↑↓ reorder; Save order disabled until dirty; Restore original;
  Export writes a reordered .fountain; the draft itself untouched until export.*
- **US-4.4** As a writer, I see character tracks (presence, dials, interactions, reads) in
  the rail. *AC: rail Characters section from GET /characters (no model calls).*

### Epic 5 — Co-write with a mentor
- **US-5.1** As a writer, I chat with Sameer about my script, grounded in the actual
  report and pages. *AC: session lazy-created; scene injection; streaming token-by-token;
  408 watchdog offers keep-waiting; session persisted every turn.*
- **US-5.2** As a writer, I branch a conversation to explore alternatives. *AC:
  fork/switch/delete branches; per-message branch badges; "main" undeletable.*
- **US-5.3** As a writer, I select a passage and ask about it. *AC: select-to-ask floats
  (and the contextual text popup) prefill a quote card; the reply is grounded on it.*
- **US-5.4** As a writer, I keep notes of my own and stash passages. *AC: margin notes
  pinned to scenes/lines in hand font; Stash list in the rail; delete entries.*
- **US-5.5** As a writer, Sameer remembers how I like to work. *AC: writer memory learns
  8 dimensions with confidence gates (0.6, ≥3 signals); "Sam's notes on you" modal lists
  observations with forget-this; refresh button; suppressed observations never return.*
- **US-5.6** As a writer, Sameer knows my past work but never mixes it into my current
  script. *AC: PAST WORK block injected from the writer library; strictly firewalled from
  the current script context.*
- **US-5.7** As a writer, I dictate instead of typing and read replies in my language.
  *AC: mic chips on every writing surface via local STT; reply globe translates into
  en/te/hi/Tenglish/Hinglish, display-only.*
- **US-5.8** As a writer, Sam behaves like a peer, not a lecturer. *AC: two-phase probe on
  unreasoned ideas; forward-momentum on stranded replies; capped suggestions; never
  volunteers the report unprompted.*

### Epic 6 — Develop ideas before pages
- **US-6.1** As a writer, I start an idea as a blank autosaving page. *AC: idea canvas
  autosaves (300ms debounce + blur + pagehide flush); auto-title from first line until
  deliberate rename.*
- **US-6.2** As a writer, I stress-test the premise with the Premise Doctor lens.
  *AC: room toggle swaps Sameer↔Premise Doctor on the same idea session; no
  doctor/scripts/shelf in idea mode.*
- **US-6.3** As a writer, I graduate an idea into a project without losing anything.
  *AC: graduate uploads first pages; premise card + idea conversation + writer memory
  carry over.*
- **US-6.4** As a writer, idea chats stay isolated from my past scripts. *AC: idea engine
  gets no writer-library digest.*

### Epic 7 — The instrument itself
- **US-7.1** As a writer, I trust the connection indicator absolutely. *AC: green only
  after a verified real model; amber demo with one-click re-attach when the real server
  returns; red unreachable; hover card states the truth.*
- **US-7.2** As a writer, I configure my server/model once. *AC: settings modal (URL,
  timeouts, fast model, turn cap) with Test Connection; save syncs to projects so LLM
  calls never hit a stale port.*
- **US-7.3** As a writer, I read modes fit the moment. *AC: Focus, Reader, River Read,
  Spotlight all work and persist; Esc cascade leaves them in spec order.*
- **US-7.4** As a writer, I navigate by keyboard. *AC: every shortcut in spec §8 wired;
  command palette fuzzy-matches commands, scenes, help, craft questions.*
- **US-7.5** As a writer, I timebox my sessions. *AC: 25:00 sprint timer start/pause/
  reset; persists across reload; elapsed time in the status strip.*
- **US-7.6** As a writer, I export and back up. *AC: export fountain/fdx/txt; whole-project
  .zip backup; report export as self-contained HTML.*
- **US-7.7** As a writer, the app is accessible. *AC: focus-visible rings; modal focus
  trap + restore; WCAG AA on severity badges; prefers-reduced-motion respected.*

## Non-goals

- Multi-user / collaboration / cloud sync / accounts.
- Real-time co-editing or live model streaming of edits into the source file.
- Writing new screenplays from scratch (the desk edits an uploaded draft; blank-page
  creation is the Idea room's job, then graduation).
- Mobile-first design (desktop browser is the target; mobile must stay usable).

## Release acceptance

The full engineering checklist is `docs/UI_UX_SPECIFICATION.md` §11 (every screen,
interaction, shortcut, API contract, error code). A feature is "done" when: unit/integration
tests exist (pytest suite), browser e2e covers the user-visible flow where applicable
(`tests/e2e_browser_*.py`), and the docs index (AGENTS.md) reflects it.
