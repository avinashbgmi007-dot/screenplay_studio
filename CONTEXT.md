# CONTEXT.md — Domain Glossary

The official names for the core "things" in Script Doctor Studio. Every doc, UI label, and
conversation should use these terms exactly. Last synced 2026-09-06.

## Core entities

- **Project** — one screenplay under the desk. A self-contained directory under
  `studio_projects/` holding the manifest, source copy, parsed output, report, and all
  stores. Created by upload, sample, or **graduation**.
- **Manifest** (`project.json`) — the resume-state record of a Project: parse/analyze/chat
  stage statuses, drafts, active draft, report language, failed categories.
- **Idea** — a scriptless embryo of a Project: a free-form autosaving page + premise card +
  one chat session, stored under `studio_projects/ideas/<id>/`. Grows into a Project via
  **graduation**.
- **Premise Card** — title · logline · premise · open questions. Rides with an Idea, and
  carries into the Project on graduation (persisted as `premise.json`).
- **Graduation** — the flow that turns an Idea into a Project: upload the first pages, the
  premise card + idea conversation carry over, the same Sam and memory continue.
- **Draft** — a named snapshot of a Project (source + parsed.json + report files) under
  `drafts/<name>/`. `original` is the implicit first draft. One draft is **active** at a
  time.
- **Session** — one chat conversation (Project or Idea), a single JSON file. Contains
  **Branches**.
- **Branch** — a fork of a Session's message thread (`main` is default). Fork/switch/delete;
  per-message badges carry the branch hue.
- **Message** — one chat turn. May carry a **Quote** (a select-to-reply script passage).
- **Finding** — one diagnosed craft issue from the analysis: category, severity, issue,
  why-it-matters, scene refs, evidence quote, rule id, verification status.
- **Verification** — the fuzzy match (threshold 0.72) of a Finding's evidence quote against
  the actual script text. Statuses: `verified` / `not_found` / `no_quote` /
  `scene_not_found`. Flag, never drop.
- **Addressed / Still Present** — a Finding's state after edits: the old text is gone from
  the working copy (addressed) or remains (still present).
- **Dismissed Finding** — a Finding the writer triaged away (`dismissed_findings.json`).
  Dismissable and restorable; never deleted from the report.
- **Fix Queue** — the per-Project worklist of Findings sorted by severity/act, joined with
  dismissal + addressed state. Powers the Fix Queue panel, Revision view, and Problem Board.
- **Rule** — one attributed craft principle from the **Knowledge Base** (263 rules across
  26 files: Aristotle, McKee, Field, Snyder, Swain, Vogler, Chekhov + genre conventions).
  Findings may cite a rule by id.
- **Knowledge Graph** (`parsed.kg.json`) — the deterministic candidate generator from the
  parser: character index, recurring props (2+ scenes), timeline, promises, co-occurrence.
  Proposes candidates; never judges.
- **Coverage** — the top-of-report verdict: logline, genre, tone, synopsis, strengths,
  weaknesses, comparables, recommendation (consider / recommend / pass).
- **Setup/Payoff Ledger** — the end-of-pipeline whole-script audit: setups with their
  payoffs, status `paid` / `dangling` / `abandoned` / `red_herring`. Dangling entries fold
  into Plot Economy findings.
- **Character Dials** — model-scored 1–10 trait sliders for the main cast (≤8).
- **Pacing** — deterministic per-scene pace index (density × inverted action share); slow
  scenes flagged as **drags**.
- **Character Track** — the serve-time per-character layer: presence, dials, traits,
  interactions, reads (assembled from KG + report; no model).
- **Stash** — the writer's saved snippets per Project (`stash.json`): select a passage →
  Stash this → the rail lists them.
- **Margin Note** — the writer's own hand-font note pinned to a scene or line
  (`notes.json`). Distinct from the doctor's Finding cards.
- **Beat Board** — the reorderable corkboard of scene cards; saving writes a permutation,
  export produces a reordered draft.
- **Working Copy** (`working.json`) — the editable ScriptDocument the revision loop mutates;
  the source file is untouched until export.
- **Edit Log** (`edits.json` / `edits.redo.json`) — the undo/redo record of applied
  replacements with per-line change stars.
- **Writer Memory** (`writer_profile.json`) — Sam's learned sense of the writer across all
  Projects: 8 dimensions with confidence gates, scoped observations, topic gravity.
- **Writer Library** — the deterministic digest of every parsed Project (characters/themes/
  scenes) injected as a PAST WORK block — never merged with the current script.
- **Sprint** — the 25:00 desk timer in the status strip.
- **Demo Craft Model** — the built-in rule-based model that fills in when no llama-server is
  reachable. Honestly marked amber; a reachable real model always wins.

## People of the system

- **The Writer** — the only human. Everything is designed around one writer at one desk.
- **Sameer (Sam)** — the writing-partner persona (`writing_partner`), the Co-write room's
  voice. Remembers the writer via Writer Memory.
- **Dr. Sushruta** — the script-consultant persona (`script_consultant`), the Feedback
  room's voice. Diagnoses; never prescribes rewrites inline.
- **Premise Doctor** — the `premise_doctor` persona; the Feedback *lens* in the Idea room
  (stress-tests the concept).
- **Persona / Mode** — 8 personas × 5 conversational modes served by the co-writer
  (producer, dev exec, teacher, audience, genre specialist, …). Personas are lenses, not
  dropdowns.

## Surfaces (the app's rooms)

- **Shelf** — the left sidebar: Ideas · On the shelf (Projects) · Your library flyouts.
- **Desk** — the manuscript-first workspace; the script pane never shrinks below 50%.
- **Room** — one of two lenses over the script: **Co-write** (warm/violet, Sameer) or
  **Feedback** (cool/cyan, Dr. Sushruta). Swapped by `body[data-room]`.
- **Room Drawer** — the summoned right-side partner panel.
- **Feedback View** — the full-screen 3-panel consultant surface (`state.view="fv"`): chat ·
  script column with severity dots · Board/Sameer tabs. What the Feedback room opens for
  Projects.
- **Problem Board** — the docked right-side severity-filtered findings panel on the Desk.
- **Structure Rail** — the collapsible left rail: scenes · characters · Stash · notes.
- **Craft Shelf** — the collapsed-by-default analysis panels header (Fix queue · Pacing ·
  Characters · Writer's Mirror).
- **Idea Canvas (Spark Wall)** — the blank starfield page an Idea is written on.
- **Design Lab** — the read-only preview prototypes (`preview-next/`, `preview-redesigns/`).

## Reading modes & flows

- **Focus** (✳) — dims all but the live line (typewriter scroll).
- **Reader** — the clean printable draft.
- **River Read** (≋) — continuous dark-glass flow with a current-dot nav.
- **Spotlight** (`z`) — total chrome removal.
- **Dawn** — the light theme (daylight glass); also the **Dawn Meter** (the room warms as
  findings resolve).
- **Analysis** — the 12-category pipeline run (plus deterministic passes); resumable,
  retry-failed per category.
- **Resume** — the manifest-driven continuation: completed stages never re-run.
- **Rewrite** — the doctor's proposed replacements for one scene (candidates only; the
  writer applies what they accept).
