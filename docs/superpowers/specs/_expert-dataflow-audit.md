# Data-Flow Audit: Backend Feedback → SPA

> Scratch analysis document (expert audit, 2026-09-21). Citations are `file:function:line`. No product code changed.

## 0. Server endpoints (what each returns)

**GET `/report`** — `webapp_server.py:get_report:1299` → `_load_report_sanitized:652` → `_sanitize_report:637` (drops dialect/subtitle findings; `_normalize_rule_ids:614` re-files unknown `rule_id`→`check_id`). Full `report.findings.json`: `title, source_filename, model_used, coverage, character_reads, logline_test, findings[] (category, issue, why_it_matters, severity, scene_refs, evidence_quote, rule_id, check_id, verification{status,matched_scene,confidence,note}), setup_payoff[], character_dials[], pacing[], formatting_findings[], stats{…,evidence_depth,checkpoint_coverage,character_arc,pacing}, verification_summary, errors` (schema: `docs/DATA_FORMATS.md:165-272`).

**GET `/fixqueue`** — `get_fixqueue:1837`. Per item: `index, finding_id, category, severity, issue, why_it_matters, scene_refs, scene_heading, act, act_name, status, dismissed` (:1867-1888) + envelope `{items, acts, dismissed_flags, dismissed_count, total_count}` (:1893). **Note: `evidence_quote`, `verification`, `rule_id`, `check_id` are stripped at :1867-1879.**

**GET `/edits`** — `get_edits:1486` → `{edits, findings_status{findings[{index,category,finding_id,status}], summary{addressed,still_present,unknown}, checked_at}, can_undo, can_redo, finding_intents{fid:"addressed"|"deferred"}, last_pass|null{computed_at,last_total,still_live,fixed,new,same_input,rewritten,prev_total,ghosted_marks[]}}` (:1501-1502; shapes `revision.py:finding_statuses:751`, `last_pass_snapshot:183`).

**GET `/metrics`** — `get_metrics:1657` → `metrics.summarize` → `{analysis_seconds, avg_reply_seconds, discussed, findings_open, findings_total, findings_fixed, findings_fixed_pct}` (`metrics.py:73-88`).

## 1. Payload → state → surface map

Single load path: `loadScriptData` (`app.js:3745`) — `Promise.all([/script,/edits,/drafts,/notes])` then sequential `/report` (:3766), `/fixqueue` (:3792).

| Payload | `state.*` key (set at) | Surfaces |
|---|---|---|
| `/report` | `state.report` (:3771), `state.findings` (:3770), `state.reportStats` (:3772) | craft shelf (`renderManuscript:4684-4690`→`buildCraftShelf:4085`); dock Evidence lens (`renderDockEvidence:5074`); Feedback room Report tab (`renderReportPanel:6123`); Revision view (:6950); manuscript margin pins + ink (`renderScenePage:4548-4558`, `inkAnchorsFor:5281`); scene index (`renderSceneIndex:4808`); beat-board flags (:7051) |
| `/edits.findings_status` | `state.findingStatus` by id+index (:3778-3783) | summary chips (:4760), mass strip (`buildScriptMassStrip:5716`), arrival draft clause (:5432), revision strip (:6975), all via `findingDisposition/findingStatusOf` (:5608/:5657) |
| `/edits.finding_intents` | `state.findingMarks` (:3785) | `findingDisposition:5613-5615`; intent buttons on deep cards (`findingNoteEl:4310-4322`) |
| `/edits.last_pass` | `state.lastPass`/`lastPassKey`/`ghostedIds` (:3786-3790) | arrival strip `buildArrivalStrip:5397` (dock only) + `scheduleArrivalPeek:5370` |
| `/fixqueue` | `state.fixQueue` (:3792, reload `:162`) | `renderFixQueuePanel:3814` in **4 containers**: shelf, dock (:5124), Feedback Fix Queue tab (:6100), Revision view (:6951); dawn meter (`updateDawnMeter:170`); dismissal lens (`isFindingDismissed:5650`) |
| `/metrics` | none (transient) | status strip `#status-metrics` (`refreshMetrics:491`) |

## 2. Same feedback rendered in 2+ surfaces

- **Fix queue × 4** — one renderer, four containers (above). Shelf + Feedback tab + Revision can coexist; dock adds a 4th live copy.
- **Finding cards × 3-4** — `findingNoteEl:4271` renders each finding as: margin pin per scene (:4558), dock scene/script-level/category sections (:5142/:5154/:5178), plus legacy Problem Board (`renderProblemBoard:8808`, still wired :8682) and dormant `#feedback-view` board (`renderFvBoard:6471`).
- **Pacing twice, different data** — shelf/dock use `state.reportStats.pacing` page-segments (`renderPacingPanel:3913`); Feedback Report tab uses `state.report.pacing` per-scene pace bars (:6165-6196). Two payloads, two charts, same name.
- **Verification trust readout twice, different math** — arrival strip (:5437-5442) includes `no_quote` in the denominator; mass strip (:5746-5758) excludes it. Same dock lens can print "3 of 5 verified (60%)" and "3 of 3 verified (100%)" simultaneously.
- **Dials × 3, Mirror × 3, SP ledger × 2** — `renderCharacterDialsPanel:3974`/`renderWriterMirrorPanel:4007` feed shelf, dock (:5247-5251), Feedback tab (:6201/:6206); `setup_payoff` renders in dock (:5228, spine+rows) and Feedback tab (:6147, rows only, no `kind`).


## 3. Backend fields dropped / flattened / hidden

- **`/fixqueue` strips `evidence_quote`/`verification`** → queue Locate (`locateFinding:3010`) can't flash the exact line (:3039-3040 early-return); `findingTargetScene:3002`'s verified-scene correction never applies from the queue.
- **Queue ignores writer intent** — rows/header/dawn read raw `item.status` (:3834, :3861, :172-174); `findingMarks` never consulted, so "✓ my call: addressed" doesn't move queue, header count, or dawn meter.
- **`verification`** — confidence/matched_scene only on dock deep cards (:4293-4302); `verification.note` nowhere; Feedback category rows (:6215-6225) and queue show nothing.
- **`rule_id`** — hover `title` only (:4302); **`check_id`** never rendered.
- **coverage** — `genre, tone, strengths, comparable_films` dropped everywhere (:6134-6143, :5193-5200); `one_page_synopsis` only in Feedback tab.
- **`errors[]`** — never rendered; only manifest-level `project.errors.analyze` surfaces (:2096). **`model_used`** never shown (status strip shows config model, possibly not the analyzing model).
- **`formatting_findings[]`** — separate report array, rendered only into `report.md` (`report.py:253`); app.js never reads it (only `category==="formatting"` inside `findings` is skipped from counts at :4263).
- **`stats`** — only `character_arc` (top-10, :3944-3966) and `evidence_depth` (dock only, :5204-5219); `dialogue_action_ratio, location_usage, scene_length_stats, parse_confidence, int_ext breakdown` dropped.
- **character_reads** — `scene_refs`, confidence, note dropped (:4045-4067). **dials** — per-trait `scene_refs` dropped; `note` hover-only (:3993). **setup_payoff** — `kind` missing in Feedback tab rows (:6156).
- **Severity flattening** — server `SEVERITY_WEIGHT` knows `"major"` (`webapp_server.py:1833`); client has only high/medium/low styling. Legacy board defaults missing severity to `'medium'` (:8813) vs `'low'` everywhere new (:3863).

## 4. State-sync risks

1. **Two status stores, different fetch times** — `state.findingStatus` (from `/edits`) vs `state.fixQueue.items[].status` (from `/fixqueue`), same server source but separately cached; a queue reload (`reloadFixQueue:160`) refreshes only one.
2. **Intent vs observed lenses disagree** — summary chips/mass strip/arrival clause count via `findingDisposition` (intent-aware); queue header, dawn meter, `findingCounts`-independent totals read raw server status. Writer intent moves one lens, never the other.
3. **Dismiss path leaves dock stale** — :3894-3896 re-renders Feedback tab *or* manuscript (manuscript tail hits `refreshDockEvidence:4757`); in `view==="feedback"` the open dock's queue copy isn't re-rendered. Conversely `setFindingIntent:5360-5362` re-renders dock+manuscript but not `#feedback-fixqueue`.
4. **Metrics staleness** — server records findings metrics on apply/redo (`webapp_server.py:1650-1653, :1678`), but `refreshMetrics` runs only at `openProject:2062` and retry (:198); the strip's "N/M fixed" is stale until project re-open.
5. **Fetch ordering** — `/report` then `/fixqueue` are sequential after a 4-way `Promise.all`; between them `state.findings`/`findingStatus` are new while `state.fixQueue` is old (any interleaved re-render mixes generations). Conditional `/report` skip (:3764) relies on `state.projects` manifest summaries being fresh.
6. **Arrival keying** — `lastPassKey === lp.computed_at` (:3787-3789) is the only arrival detector; ghosted-id Set is rebuilt only when `ghosted_marks` is non-empty (:3790), never cleared otherwise.

## 5. New finding field tomorrow?

**One additive field costs ~1 server line (the `/fixqueue` allowlist at `webapp_server.py:1867-1879`, if queued) plus 4-6 renderer touch-ups in `app.js` (`findingNoteEl:4271`, `renderFixQueuePanel:3814`, `renderReportPanel:6215`, `findingDisposition:5608` if it affects counting, `core.js:computeFindingId:143` if it affects identity) — because `/report` passes through verbatim but rendering is hand-written per surface with no shared card schema.**
