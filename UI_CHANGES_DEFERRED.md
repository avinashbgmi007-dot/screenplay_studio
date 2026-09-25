# UI Changes — Incoming / Deferred

Track all UI-related work that is on hold or planned for later implementation.

---

## Status Legend
- **DEFERRED** — Not started, waiting for implementation window
- **IN PROGRESS** — Currently being worked on
- **DONE** — Completed and shipped

---

## Deferred UI Items

### 1. Knowledge Base Integration UI
- **Status:** DEFERRED
- **Description:** UI for browsing, searching, and managing the craft rules in the knowledge
  base — the shipped KB loads **263 rules across 26 files** (`KnowledgeBase.all()`; the old
  "146 rules" count here pre-dates the genre expansion)
- **Features:**
  - Rule browser with filtering by taxonomy level, genre, confidence tier
  - Rule detail view with definition, detection signal, counter-considerations
  - Genre-specific rule visualization
  - Rule usage tracking (which rules fired during analysis)
- **Depends on:** KB genre integration (DONE)
- **Priority:** Medium

### 2. Genre Detection Visualization
- **Status:** DEFERRED
- **Description:** Visual indicator showing detected genre and which genre rules were applied
- **Features:**
  - Genre badge on analysis report
  - Genre rules breakdown panel
  - Confidence score for genre detection
- **Depends on:** KB genre integration (DONE)
- **Priority:** Medium

### 3. Analysis Pipeline Progress UI
- **Status:** DONE — shipped as the analysis **stage ladder**
- **Description:** Real-time progress visualization for the 12-pass analysis pipeline
- **Shipped as:** the heartbeat-driven stage ladder — `STAGE_LADDER` in
  `screenplay_studio/webapp/app.js:2337-2348` (the Analyze button shows live % + ETA;
  hovering the progress chip opens a pipeline map of which stage is done/running,
  per `pipeline.py`'s `emit()` events). Deliberately no per-pass bars/weights —
  "the only honest progress signal is WHICH pass reported last and HOW LONG AGO".
- **Features (original wish list, kept for history):**
  - ~~Per-pass progress bars~~ — superseded by the stage ladder (no fake percentages)
  - Rules injection count per pass (not shipped)
  - Error/warning indicators per pass (analysis errors surface via the report banner)
- **Depends on:** Pipeline instrumentation (existing)
- **Priority:** ~~Low~~ — delivered

### 4. Rules Confidence Tier Badges
- **Status:** DEFERRED
- **Description:** Visual badges showing confidence tier (high/medium/low) for each finding
- **Features:**
  - Color-coded badges (green=high, yellow=medium, red=low)
  - Tooltip explaining confidence tier meaning
  - Filter by confidence tier
- **Depends on:** KB confidence tier system (DONE)
- **Priority:** Low

### 5. Writer Feedback UI (Thumbs Up/Down)
- **Status:** DEFERRED
- **Description:** Allow writers to rate analysis findings for feedback loop
- **Features:**
  - Thumbs up/down per finding
  - Feedback storage (feedback.json)
  - Auto-adjust confidence tiers after N feedback points
- **Depends on:** Feedback storage system (NOT STARTED)
- **Priority:** High

### 6. Scene Cards View
- **Status:** DEFERRED
- **Description:** Visual card-based view of scenes with drag-and-drop reordering
- **Features:**
  - Card per scene with summary, characters, mood
  - Drag-and-drop reordering
  - Scene detail expansion
- **Depends on:** Scene summaries (DONE)
- **Priority:** Medium

### 7. Character Arc Visualization
- **Status:** DEFERRED
- **Description:** Visual character arc charts showing emotional journey
- **Features:**
  - Arc timeline per character
  - Emotional state indicators
  - Key moment markers
- **Depends on:** Character analysis (DONE)
- **Priority:** Medium

### 8. FDX Export
- **Status:** PARTLY DONE — the script exports as `.fdx`; the analysis results do not
- **Description:** Export analysis results to Final Draft (.fdx) format
- **Shipped:** working-copy export to `fountain` / `fdx` / `txt` —
  `GET /api/projects/<name>/export?format=fdx` (`webapp_server.py:1899` →
  `screenplay_parser/export.py:to_fdx`, an exact fdx→parse→export→parse round trip) —
  wired as `#export-fdx` in the UI (`app.js:5159`). The analysis report also exports, but as
  self-contained printable HTML (`/report/export`), not .fdx.
- **Still deferred:**
  - Export findings as script notes
  - Export character reads as character report
  - Export coverage as title page
- **Depends on:** Analysis pipeline (DONE)
- **Priority:** Low

### 9. Quick Analysis Mode
- **Status:** DEFERRED
- **Description:** Faster analysis with reduced rule set for quick feedback
- **Features:**
  - Toggle between full/quick analysis
  - Quick mode uses only high-confidence rules
  - Estimated time savings display
- **Depends on:** KB confidence tier system (DONE)
- **Priority:** Low

### 10. Real-Time Feedback During Analysis
- **Status:** DEFERRED
- **Description:** Live updates as analysis progresses
- **Features:**
  - WebSocket connection for live updates
  - Findings appear as they're generated
  - Progress indicators per pass
- **Depends on:** Pipeline instrumentation (existing)
- **Priority:** Low

---

## Notes
- UI changes are explicitly excluded from current scope per user request
- All UI items to be implemented in a later stage
- This file serves as the tracking document for deferred UI work
- Items may be reprioritized based on user feedback

---

*Last updated: 2026-09-25 (verified against the shipped app: KB rule count corrected to
263; item 3 marked shipped as the stage ladder; item 8 marked partly shipped — script .fdx
export exists, analysis-results .fdx export does not)*
