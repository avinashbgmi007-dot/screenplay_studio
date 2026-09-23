# One Desk, One Ledger — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the SPA's ~11 feedback surfaces into one canonical Evidence ledger beside the manuscript, delete the divergent duplicates, surface the backend honesty fields the UI drops, and add live deterministic lint + pass history.

**Architecture:** Spec: `docs/superpowers/specs/2026-09-22-one-feedback-room-design.md` (approved). Four independently-green phases: **P0** subtractions + one counting path → **P1** Evidence-lens rebuild → **P2** honesty surfacing + analysis-run UX + two small backend additions → **P3** layout polish + final gate. No pipeline changes; two new endpoints (`/quickcheck`, `/rules/<id>`) + one new store (`pass_history.json`).

**Tech Stack:** Python 3 / Flask (`screenplay_studio/webapp_server.py`), no-build vanilla JS SPA (`screenplay_studio/webapp/app.js` + `index.html` + `style.css` + `tungsten.css`), pytest (`tests/`), Playwright e2e (`tests/e2e_browser_*.py`), `node --check` JS gate.

## Global Constraints

- One counting path: every finding count reads `findingDisposition(f, index)` / `findingCounts()` (`app.js:5608/5637`). No surface counts independently. (N3 law.)
- One filter state: `state.findingFilter = {severities, showDeferred, category, scene}`; every list/ink/loop reads it through `findingPassesFilter(f, index)` (`app.js:5268`).
- All finding/report text through `escapeHtml()` (`core.js`); no inline event handlers (`script-src 'self'` CSP); colors only from CSS custom properties (night + dawn via `tungsten.css`).
- No build step, no new dependencies, no external requests.
- After every `app.js` edit: `node --check screenplay_studio/webapp/app.js` must pass (hard-learned convention — NOTES.md 2026-09-08).
- Asset cache-busting is automatic (`webapp_server._stamp_asset_versions`) — never hand-edit `?v=` tokens.
- New stores: `jsonio.atomic_write_json` + `jsonio.lock_for(path)`, lock held across read-modify-write, one lock at a time.
- `prefers-reduced-motion` respected; `:focus-visible` rings on all new interactive elements.
- A *total* analyze failure is `failed`; a *partial* failure is `complete` with `failed_categories` — never conflate them.
- Update `docs/CODEBASE_MAP.md` when a public symbol changes; append a dated entry to `NOTES.md` at each phase end.

## Verified anchors this plan relies on

- Frontend: `state.findingFilter` (app.js:32), `findingDisposition` (5608), `findingOpen` (5620), `inFindingFilter` (5626), `findingCounts` (5637), `isFindingDismissed` (5650), `findingStatusOf` (5657), `buildFindingFilterRow` (5669), `renderDockEvidence` (5074), `buildArrivalStrip` (5397), `renderFixQueuePanel` (3814), `buildCraftShelf` (4085), `renderProblemBoard` (8808), `pbItemClick` (8843), `renderFvBoard` (6471), `renderReportPanel` (6123), `retryFailedCategories` (182), `refreshMetrics` (491), `updateDawnMeter` (170), `loadScriptData` (3745), progress poller (2404), `scheduleArrivalPeek` (5370), `inkAnchorsFor` (5281), `decorateLineWithInk` (5321), `renderDiffBanner` (4186), `startLoop`/`renderLoopBar` (~5484–5563), `setFindingIntent` (~5360), `savePrefs`/`loadPrefs`.
- Markup: `#problem-board` (`index.html:332–345`), `#feedback-view` (`index.html:582–639`), `#feedback-panel` (`index.html:269–273`).
- Backend: `get_fixqueue` allowlist (`webapp_server.py:1867–1879`), `_manifest_summary` `failed_categories` (531), `analyze_project` (1048), `POST /api/projects/<name>/analyze/retry-failed` (1156), progress reader (723), `_analyze_lock` (1043); `orchestrator.run_analyze(categories, report_language, retry_failed)` (orchestrator.py:53); `revision.last_pass_snapshot` (revision.py:183); `metrics.summarize` (metrics.py:73); `run_continuity_analysis(doc) -> (findings, errors)` (continuity.py:156); `check_formatting(doc) -> findings` (formatting_check.py:13); `manifest.progress_path` (manifest.py:108); `KnowledgeBase` rules carry a human `source` citation (knowledge_base.py:48).
- Tests: `tests/test_app_symbol_integrity.py` (1-def-many-uses symbol gate), `tests/test_webapp_api.py`, `tests/test_feature_batch.py`, `tests/e2e_browser_*.py` (Playwright), `tests/js/` (node --test, DOM-free `core.js` only).

---

# PHASE P0 — Subtractions + one counting path

### Task 1: Delete the dormant Feedback View clone

**Files:**
- Modify: `screenplay_studio/webapp/index.html` (delete `#feedback-view` block, ~582–639)
- Modify: `screenplay_studio/webapp/app.js` (delete `renderFvBoard` ~6471 and all `fv-*` renderers/helpers, ~700 lines; delete every call site)
- Modify: `screenplay_studio/webapp/style.css` (delete orphaned `.fv-*` rules)
- Test: `tests/test_app_symbol_integrity.py`

**Interfaces:** Consumes: nothing. Produces: absence — no `renderFvBoard*` symbol or `#feedback-view` element anywhere.

- [ ] **Step 1: Failing test** — append to `tests/test_app_symbol_integrity.py`:

```python
def test_feedback_view_clone_is_gone():
    src = Path("screenplay_studio/webapp/app.js").read_text(encoding="utf-8")
    html = Path("screenplay_studio/webapp/index.html").read_text(encoding="utf-8")
    assert "renderFvBoard" not in src
    assert "feedback-view" not in html
```

- [ ] **Step 2: Run, expect FAIL** — `python -m pytest tests/test_app_symbol_integrity.py -v`
- [ ] **Step 3: Delete.** Grep `fv`, `Fv`, `feedback-view` across `app.js`/`index.html`/`style.css`; delete the markup, the renderer family, and every call site that belongs to the clone. Careful: `.fv-scene .paper` in style.css belongs to the clone, but verify each `.fv-` rule is clone-owned before deleting (the 2026-09-10 NOTES entry documents a careless multi-line delete here before — review the diff line by line).
- [ ] **Step 4: Gates** — `node --check screenplay_studio/webapp/app.js`; `python -m pytest tests/test_app_symbol_integrity.py tests/test_webapp_api.py -q` PASS; `python -m pytest tests/e2e_browser_smoke.py -q` PASS.
- [ ] **Step 5: Commit** — `git commit -m "P0.1: delete the dormant #feedback-view clone (~700 lines)"`

### Task 2: Retire the Problem Board + sanitize legacy stored state

**Files:**
- Modify: `index.html` (delete `#problem-board`, ~332–345)
- Modify: `app.js` (delete auto-open ~2118–2121, `renderProblemBoard` ~8808, `pbItemClick` ~8843, scroll-sync ~8888–8897, `#pb-filter` wiring; relabel the palette entry that shows key `b` as "Toggle the Problem Board" — it opens the Beat Board)
- Modify: `style.css` (delete `.pb-*`)
- Test: `tests/test_app_symbol_integrity.py`; re-pin `tests/e2e_browser_phase8_lifecycle.py` / `e2e_browser_export_flush.py` if they assert board presence

**Interfaces:** Produces `_sanitizeLegacyState(p)` (app.js, beside `loadPrefs`) — drops stored keys referencing retired surfaces; consumed by `loadPrefs()` and the session-restore path (~8410).

- [ ] **Step 1: Failing test**:

```python
def test_problem_board_is_gone():
    src = Path("screenplay_studio/webapp/app.js").read_text(encoding="utf-8")
    html = Path("screenplay_studio/webapp/index.html").read_text(encoding="utf-8")
    assert "renderProblemBoard" not in src
    assert "problem-board" not in html
    assert "pbItemClick" not in src
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Delete + add the sanitizer**:

```javascript
function _sanitizeLegacyState(p) {
  const out = { ...(p || {}) };
  if (out.view === "feedback") out.view = "desk"; // retired drawer state -> desk
  delete out.pbOpen; delete out.problem_board;    // retired board prefs
  return out;
}
```

Wire it into `loadPrefs()` and the stored-`view` restore before either is used.
- [ ] **Step 4: Gates** — `node --check`; symbol-integrity PASS; `python -m pytest tests/e2e_browser_smoke.py tests/e2e_browser_phase8_lifecycle.py -q` PASS.
- [ ] **Step 5: Commit** — `"P0.2: retire the Problem Board; sanitize legacy stored view/prefs"`

### Task 3: One counting path — queue header, dawn meter, summary chips, revision strip

**Files:**
- Modify: `app.js` — `renderFixQueuePanel` header/counts (3814–3831), `updateDawnMeter` (170), `#finding-summary` chips (~4760), revision strip (~6981), arrival draft clause (~5432)
- Test: `tests/e2e_browser_gun_pen_audit.py` (extend row C counts check) or a focused new `tests/e2e_browser_counting_contract.py`

**Interfaces:** Consumes: `findingCounts() -> {total, open, shown, openShown}`, `findingDisposition(f, index) -> "open"|"addressed"|"deferred"|"ghosted"|"dismissed"`. Produces: `queueCounts() -> {open, total}` (app.js) mapping `/fixqueue` items through `findingDisposition` via `finding_id`→index (same mapping `isFindingDismissed` uses at 5650); every surface above prints from these two functions only.

- [ ] **Step 1: Failing e2e check** — new `tests/e2e_browser_counting_contract.py`: seed an analyzed project (mock server fixtures per `tests/e2e_browser_finding_id_parity.py` pattern), mark one finding intent=addressed via `POST /findings/intent`, then assert in the browser that the fix-queue header count, the `#finding-summary` chip, and the dawn meter all report the SAME open number:

```python
def test_queue_header_matches_disposition_count(base, page):
    # after marking one finding addressed...
    queue_open = int(page.locator(".fixqueue-head .open-count").inner_text())
    chip_open = int(page.locator("#finding-summary .open").inner_text())
    assert queue_open == chip_open  # fails today: queue reads raw item.status
```

- [ ] **Step 2: Run, expect FAIL** (queue header ignores `state.findingMarks` today).
- [ ] **Step 3: Implement** `queueCounts()` and rewire the five surfaces to `findingCounts()`/`queueCounts()`; delete any surface-local counting.
- [ ] **Step 4: Gates** — `node --check`; new e2e PASS; `python -m pytest tests/test_webapp_api.py -q` PASS.
- [ ] **Step 5: Commit** — `"P0.3: one counting path — queue header, dawn meter, chips, revision strip read findingDisposition"`


### Task 4: Re-render completeness + metrics freshness

**Files:**
- Modify: `app.js` — dismiss path (~3894–3896), `setFindingIntent` (~5360–5362), edits apply/undo/redo handlers, `refreshMetrics` (491)
- Test: `tests/e2e_browser_counting_contract.py` (extend)

**Interfaces:** Produces: `refreshAllFindingSurfaces()` (app.js) — the ONE function every mutation calls: re-renders dock Evidence (if mounted), manuscript ink, fix queue (whichever container is mounted), summary chips, dawn meter, then `refreshMetrics()`. All mutation handlers call it instead of their current partial subsets.

- [ ] **Step 1: Failing e2e** — with the Feedback Fix Queue tab AND the dock both mounted, mark an intent; assert BOTH surfaces reflect it without reload:

```python
def test_intent_updates_every_mounted_surface(base, page):
    page.locator(".finding-card .intent-addressed").first.click()
    page.locator("#feedback-fixqueue").scroll_into_view_if_needed()
    assert "addressed" in page.locator("#feedback-fixqueue .fix-row").first.get_attribute("class")
    # fails today: setFindingIntent re-renders dock+manuscript but not the queue tab
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** `refreshAllFindingSurfaces()`; replace the per-handler re-render lists (dismiss at 3894, intent at 5360, apply/undo/redo handlers) with it; add `refreshMetrics()` to the apply/undo/redo/intent paths (metrics staleness fix).
- [ ] **Step 4: Gates** — `node --check`; new e2e PASS; `python -m pytest tests/test_revision.py -q` PASS.
- [ ] **Step 5: Commit** — `"P0.4: refreshAllFindingSurfaces — one re-render entry point; fresh metrics after every mutation"`

### Task 5: P0 gate — suite green, surfaces gone

- [ ] **Step 1:** `python -m pytest tests/ -q -x --ignore=tests/e2e_browser_gun_pen_audit.py` — full unit suite green (baseline: 3 known flakes per NOTES: `test_save_rename_race_never_tears_json`, `test_store_save_serializes_concurrent_writers`, `test_chat_stream_decodes_utf8_not_latin1`).
- [ ] **Step 2:** Browser suites that referenced retired surfaces re-pinned and green: `python tests/run_browser_suites.py` (the CI runner).
- [ ] **Step 3:** Update `docs/CODEBASE_MAP.md` (remove `renderFvBoard`/`renderProblemBoard` entries) and append the dated P0 entry to `NOTES.md`.
- [ ] **Step 4: Commit** — `"P0 gate: subtractions shipped, one counting path live, suites re-pinned"`

---

# PHASE P1 — Evidence lens rebuild (the ledger)

### Task 6: Collapsible dock sections (make the lying comment true)

**Files:**
- Modify: `app.js` — `renderDockEvidence` (5074) and its section builders; `savePrefs`/`loadPrefs`
- Modify: `style.css` — `.dock-section` open/closed styles, chevron, token-driven
- Test: `tests/e2e_browser_dock_sections.py` (new)

**Interfaces:** Produces: `dockSection(key, title, buildBody, {defaultOpen=false}) -> HTMLElement` — renders a header button (`aria-expanded`, chevron) + body region; open state persisted as `prefs["dock_section_"+key]`; used by every section in the Evidence lens. Consumes: existing section builders unchanged (they keep returning elements).

- [ ] **Step 1: Failing e2e**:

```python
def test_dock_sections_collapse_and_persist(base, page):
    sec = page.locator('.dock-section[data-key="by-category"]')
    assert sec.get_attribute("data-open") == "false"   # default closed
    sec.locator(".dock-section-head").click()
    assert sec.get_attribute("data-open") == "true"
    page.reload()
    assert page.locator('.dock-section[data-key="by-category"]').get_attribute("data-open") == "true"
```

- [ ] **Step 2: Run, expect FAIL** (sections are plain divs today).
- [ ] **Step 3: Implement** `dockSection()`; wrap each section in `renderDockEvidence` (queue, scene cards, script-level, by-category, coverage, setup/payoff, pacing, characters, dials, mirror). The comment at 4992–4998 becomes true; update it to describe the real behavior.
- [ ] **Step 4: Gates** — `node --check`; new e2e PASS; reduced-motion: no height animation without `@media (prefers-reduced-motion: no-preference)` guard.
- [ ] **Step 5: Commit** — `"P1.6: dockSection — every Evidence section collapses and persists"`

### Task 7: Live-highs default + "this scene" chip (scene as filter, not surface)

**Files:**
- Modify: `app.js` — `state.findingFilter` init (32), `findingPassesFilter` (5268), `buildFindingFilterRow` (5669), `renderDockEvidence` ordering
- Test: `tests/e2e_browser_dock_sections.py` (extend)

**Interfaces:** Consumes: `findingPassesFilter`. Produces: `state.findingFilter.scene: null | <scene_number>`; the chip "This scene" in the filter row sets/clears it. `findingPassesFilter` gains the scene clause:

```javascript
function findingPassesFilter(f, index) {
  const d = findingDisposition(f, index);
  if (d === "deferred" ? !state.findingFilter.showDeferred : d !== "open") return false;
  const sev = (f.severity || "low").toLowerCase();
  if (!state.findingFilter.severities.includes(sev)) return false;
  if (state.findingFilter.category && (f.category || "other") !== state.findingFilter.category) return false;
  const sc = state.findingFilter.scene;
  if (sc != null && !(f.scene_refs || []).includes(sc) && !(f.scene_refs || []).includes(String(sc))) return false;
  return true;
}
```

- [ ] **Step 1: Failing e2e** — clicking "This scene" narrows dock list + ink to the current scene; clearing restores all; counts label switches "N open on this scene" vs "N open" (scope always printed — the findingCounts comment contract).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** the filter field + chip; the "Live findings" section renders highs first, grouped by category inside `dockSection("live", ...)`; default = all live findings (NOT scene-scoped — red-team W2). **Also (spec §14.3):** in `renderSceneIndex`/`sceneIndexSeverity` (4808/4796), a scene with zero live findings renders a quiet ✓ glyph where its severity dot would be — the rail becomes a progress map.
- [ ] **Step 4: Gates** — `node --check`; e2e PASS; ink narrows identically (assert page marks == list count).
- [ ] **Step 5: Commit** — `"P1.7: scene as a filter dimension — this-scene chip on the ONE filter"`


### Task 8: One rendering per finding per panel

**Files:**
- Modify: `app.js` — `renderDockEvidence` (5074–5255): queue copy (5124), scene deep cards (5134), script-level cards (5149), by-category cards (5165–5181)
- Test: `tests/e2e_browser_dock_sections.py` (extend)

**Interfaces:** Produces: `dedupeDockFindings(queueIds, sceneIds) -> Set<id>` — precedence: this-scene strip > fix queue > by-category. A finding renders in exactly its highest-precedence section; later sections skip ids in the returned set.

- [x] **Step 1: Failing e2e**:

```python
def test_finding_renders_once_in_dock(base, page):
    # count occurrences of one known finding's issue text across the whole dock
    occ = page.locator("#dock-evidence").get_by_text(KNOWN_ISSUE, exact=False).count()
    assert occ == 1  # fails today: queue row + scene card + category card = 3
```

- [x] **Step 2: Run, expect FAIL.**
- [x] **Step 3: Implement** `dedupeDockFindings` and pass the seen-set through the section builders.
- [x] **Step 4: Gates** — `node --check`; e2e PASS; loop list (`startLoop`) unchanged (it reads the filter, not the DOM).
- [x] **Step 5: Commit** — `"P1.8: one rendering per finding in the ledger (scene > queue > category)"`


> **Executed 2026-09-22 with one change to the stated precedence.** The queue
> is NOT a claimer: `webapp_server.get_fixqueue` emits exactly one row per
> report finding, so `queueIds` in the skip-set would empty the categorized
> live list on every analyzed project (and §5 wants both sections — the queue
> row is the compact to-do, the card is the evidence view). What must not
> repeat is the CARD, so `dedupeDockFindings(sceneIdx, scriptLevelIdx)` gates
> the live list only, and its header tooltip says how many were carded above.
>
> **Also shipped in this commit (the spec §8 rider the plan never tasked):**
> `buildScriptMassStrip` kept a private `findingOpen` scan for its headline,
> severity mass and category weights — a seventh counting path. It now presents
> `findingCounts()`'s `bySeverity`/`byCategory`, and
> `test_mass_strip_reads_the_one_counter` fails the build if the strip starts
> scanning findings again.
### Task 9: Arrival strip inversion + fix-loop CTA

**Files:**
- Modify: `app.js` — `buildArrivalStrip` (5397–5481)
- Test: `tests/e2e_browser_gun_pen_audit.py` (arrival arithmetic checks) — re-pin expected DOM order

**Interfaces:** Consumes: `state.lastPass` (`{computed_at, last_total, still_live, fixed, new, same_input, ghosted_marks}`), `findingCounts()`. Produces: arrival strip DOM contract — first element = `K of M addressed by you` headline; secondary clause = pass-diff numbers; primary CTA button `.arrival-loop-cta` → `startLoop()`; `same_input` disclosure verbatim.

- [x] **Step 1: Failing e2e** — assert the strip's FIRST text node mentions "addressed by you" and a `.arrival-loop-cta` button exists and starts the loop (`#loop-bar` becomes visible).
- [x] **Step 2: Run, expect FAIL.**
- [x] **Step 3: Rewrite** `buildArrivalStrip` body: headline `findingCounts`-derived writer number, pass-diff as one muted clause, CTA `"Start the fix loop — N highs"` (N = open highs from `findingCounts`+severity), ghosted list + retry link preserved inside a collapsed detail. Keep every honesty statement — only the ORDER changes.
- [x] **Step 4: Gates** — `node --check`; arrival e2e re-pinned and PASS.
- [x] **Step 5: Commit** — `"P1.9: arrival strip answers 'did my edits work?' first; fix loop is the CTA"`

**Deviation, Step 4 (recorded rather than claimed):** the “re-pin expected DOM order” leg was a
**no-op**. `tests/e2e_browser_gun_pen_audit.py` reads the arrival strip *by class*
(`.dock-arrival-draft` / `-line` / `-scope`), never by position, so inverting the order needs no
re-pin — and that suite needs a live llama-server, so it skips in this environment anyway. The new
arrival checks went to `tests/e2e_browser_dock_sections.py` instead (it boots the studio with the
demo model), where `ARRIVAL_SEED_JS` seeds a full `state.lastPass` and asserts the position contract
for real: headline first, `.arrival-loop-cta` present + clickable → `#loop-bar`, `same_input` and
scope wording byte-for-byte unchanged. RED `76/4` → GREEN `80/0`.

**Task order, so the boxes above are not misread as pending work:** P1.6 and P1.7 shipped in
`44bb136` and `0d12d56`, and P0.1–P0.5 in the five commits before them, but their step boxes were
never ticked; only their `NOTES.md` entries record it (P1.6/P1.7 have none). Ticking them needs
per-step verification, not trust in a commit message — do it in Task 21’s acceptance walk.

### Task 10: Shelf defers + one Pacing + vocabulary unification + disposition microcopy

**Files:**
- Modify: `app.js` — `buildCraftShelf` (4085): remove embedded queue, header gains "Open the ledger →" button that opens the dock Evidence lens; `renderReportPanel` (6123): delete the pace_score "Pacing" chart (6163–6195); `renderPacingPanel` (3913): add the per-scene `pace_score` drag bars as a labeled second block ("Where the script drags") inside the ONE pacing section; `renderDiffBanner` (4186): reword "resolved/carried/still open" → "no longer flagged / still live / new"; `findingNoteEl` (4310–4322): one-line explainers under intent buttons
- Test: `tests/e2e_browser_counting_contract.py`, `tests/e2e_browser_dock_sections.py` (extend)

**Interfaces:** Produces: single `renderPacingPanel` containing both labeled metrics; diff-banner copy constant `DELTA_TERMS = {fixed: "no longer flagged", carried: "still live", added: "new"}` used by banner AND arrival strip.

- [x] **Step 1: Failing checks** — (a) grep-gate in `test_app_symbol_integrity.py`: `pace_score` appears in exactly one renderer; (b) e2e: craft shelf has no `.fix-row`; (c) e2e: diff banner text uses "still live".
- [x] **Step 2: Run, expect FAIL.**
- [x] **Step 3: Implement** all four edits. Disposition microcopy on cards: `✓ addressed — "you fixed it (survives re-analysis)"`, `⏭ next pass — "park it; it returns next analysis"`, `Dismiss — "hide from the queue only"`.
- [x] **Step 4: Gates** — `node --check`; suites PASS.
- [x] **Step 5: Commit** — `"P1.10: shelf defers to the ledger; one Pacing with both metrics; one delta vocabulary; disposition explainers"`
**RED evidence (measured before the edits):** `test_app_symbol_integrity.py` 2 failed /
5 passed (pace_score had two renderers; DELTA_TERMS absent) and
`e2e_browser_dock_sections.py` 84 passed / 9 failed (`shelf rows=8`, `no button`, one
chart titled Pacing, `0 hints`, banner `0 resolved | 8 carried | 1 still open`).
GREEN after: 7/0 and 93/0.

**Two notes on how Step 3 landed.** (1) The grep-gate's `_top_level_functions()` helper
only matched `^function`, so a gate aimed at the `async function renderDiffBanner` read
an empty body and would have passed for the wrong reason; it now matches
`^async function` too, and the banned-word check runs on comment-stripped source (a
comment may name the server's own fields -- only the words a writer reads are held to
the one vocabulary). (2) The banner's `carried` and `still_present` are two
measurements of one thing (the finding survived the draft). Printing both as chips made the
banner say `31 still live` and `28 still live` two pixels apart -- the contradiction this plan
exists to kill -- so `carried` now rides inside the one chip's hover instead of becoming a
rival headline. Review also split the disposition hint: a deep card explains only the
addressed / next-pass marks it carries, because Dismiss is a queue-row gesture.

### Task 11: P1 visual truth gate

- [x] **Step 1:** Run the studio against the Gun_Pen fixture with the demo model; capture screenshots of the desk with the ledger open — night AND dawn — into gitignored `impl-shots/runs/latest/` (the `tests/_ui_capture.py` harness pattern).
- [x] **Step 2:** Review against the spec §11 checklist: no text overlap, sections collapsed by default, arrival headline correct, categories collapsed, manuscript ≥50%.
- [x] **Step 3:** Fix what the pixels reject (this is the 15% layout-uncertainty retire step — do not call P1 done on green tests alone).
- [x] **Step 4: Commit** — `"P1 gate: visual truth pass (night+dawn), 1 pixel fix"`
**Measured (see NOTES.md P1 gate entry):** 0/9 sections open on load, manuscript 70.4%
with the dock open, `overflowX == 0`, no surface overlap, no JS errors, scene chip 36 → 18
→ 36 rows on the real Gun_Pen report. Rejected: the fix-queue head tangled its count line
with the dawn meter in the ~380px column -> stacked in `style.css` (one pixel fix).


---

# PHASE P2 — Honesty surfacing + analysis-run UX + backend additions

### Task 12: /fixqueue carries evidence + verification; queue rows show verification state

**Files:**
- Modify: `screenplay_studio/webapp_server.py` — `get_fixqueue` allowlist (1867–1879): add `evidence_quote`, `verification`
- Modify: `app.js` — `renderFixQueuePanel` row: unverified badge when `verification.status != "verified"` (same badge component as deep cards, 4293–4300)
- Test: `tests/test_feature_batch.py` (extend the fixqueue block)

**Interfaces:** Produces: fixqueue item gains `evidence_quote: str`, `verification: {status, matched_scene, confidence, note} | None`. Client consumes verbatim.

- [x] **Step 1: Failing test** — in the existing fixqueue test class (deviation: the test went in `tests/test_fixqueue.py::TestFixQueue::test_items_carry_evidence_and_verification`, which is where the item-shape contract already lives, and it asserts the quote actually matches the report's, not just that the key exists):

```python
def test_fixqueue_items_carry_evidence_and_verification(self, http_client):
    project = _upload(http_client).get_json()["project"]
    _seed_report(tmp_path, http_client, project)   # existing helper pattern
    items = http_client.get(f"/api/projects/{project}/fixqueue").get_json()["items"]
    assert "evidence_quote" in items[0]
    assert "verification" in items[0]
```

- [x] **Step 2: Run, expect FAIL** (allowlist strips both today).
- [x] **Step 3: Widen the allowlist** at 1867–1879; add the badge to queue rows (escapeHtml for note text). The badge is now one builder, `verificationBadge(v)`, shared by the deep card and the row — a row can't say "verified" where its card says "unverified".
- [x] **Step 4: Gates** — new test PASS; `pytest tests/test_fixqueue.py tests/test_feature_batch.py -q` → 22 passed. Full `pytest tests/ -q` → 1633 passed / 3 skipped. `e2e_browser_dock_sections.py` → 98 passed / 0 failed (3 new legs pin row badge == `verificationBadge(item.verification)`). `e2e_browser_counting_contract.py` → 20/0.
- [x] **Step 5: Commit** — `"P2.12: fixqueue carries evidence_quote + verification; rows show unverified badges"`

Deviation — the non-verified badge keeps the card's existing wording (`⚠ unverified`) rather than inventing per-status text; the precise server status (`not_found` / `no_quote` / `scene_not_found`) rides in the badge's `title`, so one builder stays honest without a new vocabulary in the ledger.

The P1 visual gate caught a regression from this change: the row badge squeezed `.fix-row-body` into a ~130px column and a row stood **486px tall** at one word per line. Fixed with `.dock-section .fix-row { flex-wrap: wrap }` + `.fix-row-body { flex: 1 1 100% }` (the shape `.revision-findings` already uses); re-measured 257px with 36 badges rendered, `FAILURES: none`. The gate now also fails on any queue row taller than 260px so this can't come back silently.

### Task 13: Finding-card honesty fields + rule popover endpoint

**Files:**
- Create: nothing (endpoint lives in `webapp_server.py`)
- Modify: `webapp_server.py` — new route `GET /api/rules/<rule_id>`: looks the id up in `KnowledgeBase()` and returns `{id, name, source}` or 404
- Modify: `app.js` — `findingNoteEl` (4271): body shows `verification.note` (escaped) and `check_id` when present; `rule_id` renders as a button that lazily fetches `/api/rules/<id>` and shows a popover (rule name + craft source)
- Test: `tests/test_webapp_api.py` (rules endpoint), e2e card check

**Interfaces:** Produces: `GET /api/rules/<rule_id> -> {id, name, source} | 404`. Client: `showRulePopover(ruleId, anchorEl)` (app.js).

- [x] **Step 1: Failing test**:

```python
def test_rule_endpoint_returns_attribution(self, http_client):
    resp = http_client.get("/api/rules/inciting_incident")  # a real KB id
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["name"] and body["source"]  # e.g. 'Robert McKee, Story (1997)'
    assert http_client.get("/api/rules/not_a_rule").status_code == 404
```

- [x] **Step 2: Run, expect 404/FAIL.** (3 failed: the route did not exist, so the 404 came back as HTML and `get_json()` was None.)
- [x] **Step 3: Implement** the route (KB lazy-load, unknown id → 404, no model calls) and the card fields + popover (one fetch per open, `escapeHtml` everything, close on Esc/outside-click per the Esc cascade convention).
- [x] **Step 4: Gates** — pytest PASS; `node --check`; e2e card shows the note text.
- [x] **Step 5: Commit** — `"P2.13: verification.note + check_id on cards; /api/rules/<id> attribution popover"`

Deviations — the plan's example id `inciting_incident` is not a knowledge-base rule (263 ids checked; there is no inciting-incident rule), so the test cites `chekhovs_gun` and adds a second case for a `general_craft` rule, whose attribution must say *widely-taught convention* rather than invent an author. The rule chip ended up in the card's **action row**, not the deep block: `.finding-deep` is `display:none` until hover/`:focus-within`, so a chip placed there could never be clicked (the e2e caught it as "click never landed"). `check_id` prints only when there is no `rule_id`, so one card never carries two competing provenance lines.

Also found and fixed on the way: `tests/test_webapp_api.py` defined `TestReportRuleIdNormalization` **twice** with byte-identical bodies — Python rebinds the name, so the first 62 lines were dead code that looked like coverage. Deleted the shadowed copy (63 tests before and after, so nothing was being lost, but the trap is gone).

Measured (the P1 gate now photographs this surface): `03e_rule_popover_night` shows `General Setup and Payoff` / `Robert McKee — Story: Substance, Structure, Style, and the Principles of Screenwriting (1997)`; `03f_rule_chip_night` shows the chip's label. The gate gained a `ruleChip` measurement that fails if the chip is clipped or under 60px, and the first run caught the chip wrapping mid-label inside the 320px card — fixed with `.dock-section .finding-note-actions { flex-wrap: wrap }` + `white-space:nowrap` on the chip (the same squeeze P2.12 hit in the queue row). Re-measured: 172px, one line, not clipped, `FAILURES: none`.

### Task 14: Report header model_used + errors[] banner + coverage/strengths/read-confidence + formatting section

**Files:**
- Modify: `app.js` — `renderDockEvidence` header (5074), new `buildFailureBanner()` (partial-failure UI from `failed_categories` + report `errors[]`), Coverage section (5193–5200: add `genre`, `tone`, `strengths`, `comparable_films`), "What's working" line under the arrival strip fed by `coverage.strengths`, `renderWriterMirrorPanel` (4007: add read confidence + scene_refs), new collapsed Formatting section fed by `report.formatting_findings` (labeled "deterministic checks, not model judgment")
- Test: `tests/e2e_browser_dock_sections.py` (extend)

**Interfaces:** Consumes: `state.report` fields `model_used`, `errors`, `coverage.{genre,tone,strengths,comparable_films}`, `formatting_findings`, `character_reads[].confidence/scene_refs`. Produces: `buildFailureBanner(failedCategories, errors) -> HTMLElement | null`.

- [x] **Step 1: Failing e2e** — seed a report with `model_used`, `errors: ["dialogue: timeout"]`, `coverage.strengths`; assert: header shows the model id, banner shows "1 pass failed — rerun just that", "What's working" line renders the strength text (escaped).
- [x] **Step 2: Run, expect FAIL.**
- [x] **Step 3: Implement** all six renderings; every string through `escapeHtml`; banner retry button calls `retryFailedCategories()` (182). **Also (spec §14.2):** `findingNoteEl` gains a "📝 pin to notes" verb — POSTs `{scene_number, text: finding issue + quote, anchor: evidence_quote}` to the EXISTING `POST /api/projects/<name>/notes` endpoint and confirms with the note's toast; no new backend.
- [x] **Step 4: Gates** — `node --check`; e2e PASS; dawn register screenshot check (tokens only).
- [x] **Step 5: Commit** — `"P2.14: model_used, errors[] banner, coverage extras, strengths-first, read confidence, formatting section"`

**Deviations (T14).**
- The arrival strip's inline retry block was **deleted**, not duplicated: `buildFailureBanner()` is now the only place a
  failed-pass retry lives, so a stale "1 pass failed" cannot hover over a report the retry already fixed
  (`retryFailedCategories` re-renders the lens in its `finally`). Task 16 therefore only has to add `.rerun-full`
  to the banner and remove the desk-toolbar + drawer buttons.
- The banner renders no count of its own — a second counter would be a second counting path (N3).
- `verificationReadout()` is the ONE builder behind both `.dock-trust` renderings (arrival strip + script-mass
  strip), fixing the two-denominator bug filed during P1 (100% vs 28% off the same report).
- `character_reads[].confidence` is absent on real reports, so it renders only when the key exists — same rule as
  the T13 verification note. `pinFindingToNotes` sits in the actions row, not `.finding-deep` (hover-only, so a
  verb there can never be clicked); pin state is derived from `state.notes`, so it survives re-render and cannot
  double-pin.
- `tests/_p1_visual_gate.py` now photographs `.dock-report-model`, `.dock-working` and `.dock-fmt-row` and fails
  if the model line prints a machine path, if either honesty surface is clipped, if a banner stands on a clean
  report, or if the two verification readouts disagree.


### Task 15: Progress stage ladder (honest, heartbeat-driven)

**Files:**
- Modify: `app.js` — progress poller (2404) and the desk progress chip / hover map (`refreshDeskToolbar` ~2485–2510)
- Modify: `style.css` — `.stage-ladder` styles (tokens only)
- Test: `tests/e2e_browser_phase8_lifecycle.py` (extend — it already drives a live analysis)

**Interfaces:** Consumes: `progress.json` events `{stage, ts, ...}` (orchestrator.py:102–110) via the existing poller. Produces: `STAGE_LADDER = [{key, caption}...]` (12 entries, plain-language: e.g. `{key:"dialogue", caption:"Reading dialogue — who sounds like whom"}`) and `renderStageLadder(container, currentKey, startedTs)` — done ✓ / current ● + live elapsed / pending ○; hover/focus shows the stage's purpose. No percentages — elapsed seconds only.

- [x] **Step 1: Failing e2e** — during a live analysis (mock server), assert `.stage-ladder` exists, exactly one `.stage.current`, its elapsed text ticks up, and completed stages carry ✓.
- [x] **Step 2: Run, expect FAIL.** — `ReferenceError: renderStageLadder is not defined`.
- [x] **Step 3: Implement** the ladder in the desk header area (visible without hover; hover adds the "what this pass does" detail). Elapsed derived from `ts` — if `ts` is stale > 2× timeout, show "checking…" (the heartbeat's documented purpose).
- [x] **Step 4: Gates** — `node --check`; lifecycle e2e PASS; reduced-motion respected.
- [x] **Step 5: Commit** — `"P2.15: stage ladder — real pass events, live elapsed, plain-language captions"`

**Deviations.**
1. The ladder has **20 entries, not 12** — one per stage key the pipeline actually
   emits (`pipeline.py` `progress_cb` boundary). A hand-picked 12 would silently omit
   real passes, and a pass with no row is exactly the invented-progress lie §15.1 bans.
2. `ANALYSIS_STAGES` + its per-stage weights + `ANALYSIS_TOTAL_WEIGHT` + `formatETA`
   + the `%` readout + the extrapolated ETA **and the `.ap-bar`** are deleted, plus the
   four dead `.ap-bar*` rules in `tungsten.css`. Both the bar and the ETA were
   extrapolation from a weight that no measurement backs.
3. The rail lives in the **hover/`:focus-within` popover**, not the always-visible
   desk header: `#desk-toolbar` is contractually ≤64px (`phase8_lifecycle`) and Task 19
   forbids covering the page, so 20 rows cannot be permanent chrome. What is always
   visible is the honest part — the plain-language caption for the pass that reported
   last plus its live elapsed ("working… 12s on this pass"). Keyboard-reachable via
   the chip's existing `tabindex="0"` + `:focus-within`.
4. Stale-heartbeat wording is "no word from the model — waiting X", at 2×
   `state.config.timeout` (the client's own copy of the server's 600 s default),
   measured against the event's own `ts` rather than a client clock.
5. The rail re-renders only when the run *moves* to a new stage; the current row's
   elapsed is patched in place, so a hovering writer's seconds tick without replacing
   20 nodes every poll.

### Task 16: Retry split UI (failed-only default vs full re-run, honestly labeled)

**Files:**
- Modify: `app.js` — `buildFailureBanner` (Task 14) gains both actions; remove the triplicate retry buttons (desk toolbar, arrival strip, drawer header → banner only)
- Test: `tests/e2e_browser_phase8_lifecycle.py` (extend — the failed-category flow already exists there, `#desk-retry-failed-btn` refs at 127–131)

**Interfaces:** Consumes: `POST /api/projects/<name>/analyze/retry-failed` (exists, webapp_server.py:1156) and `POST /analyze {"force": true}` (exists). Produces: banner DOM contract: primary `.rerun-failed` ("Rerun the N failed passes — fast; your good findings stay exactly as worded"), secondary `.rerun-full` ("Rerun the whole analysis — fresh eyes; re-words findings, noisy counts unless you edited").

- [x] **Step 1: Failing e2e** — with a partial-failure fixture, assert both buttons exist, clicking `.rerun-failed` POSTs to `/analyze/retry-failed`, clicking `.rerun-full` POSTs `{"force": true}` to `/analyze`.
- [x] **Step 2: Run, expect FAIL.** — 7 legs red: `.rerun-full` did not exist, and the DOM offered three rerun verbs across two surfaces.
- [x] **Step 3: Implement** the two actions; delete the old three retry buttons.
- [x] **Step 4: Gates** — `node --check`; lifecycle e2e PASS.
- [x] **Step 5: Commit** — `"P2.16: retry split — failed-only default, full re-run with the churn warning, one banner"`

**Deviations.**
1. The POST legs intercept with `page.route` and assert on the request the client
   makes. Driving a real re-analysis inside the honesty suite would reload the
   project and wipe the seeded failure the earlier sections assert on — and the
   contract under test is which endpoint and body the button chooses.
2. `.rerun-full` calls the existing `runAnalysis()` rather than issuing its own
   POST, so the desk, the drawer button and the banner remain ONE lifecycle
   (Phase 8's no-double-fire rule) — the banner is another door, not another run.
3. `retryFailedCategories` lost its global-button bookkeeping entirely: it now
   manages only its anchor and re-renders the lens in `finally`, which is what
   makes a banner that outlives its failure impossible.
4. The visual gate cannot photograph the split (`gun_pen_2` is a clean report, so
   the banner is correctly absent there); its pixels rest on the seeded suite.

### Task 17: Quickcheck — live deterministic lint (NEW endpoint + wiring)

**Files:**
- Modify: `webapp_server.py` — new route after `analyze_project` (~1063)
- Modify: `app.js` — call after edits apply/undo/redo + inline edit save; merge results into `state.findings` display as **provisional** (labeled "live check")
- Test: `tests/test_webapp_api.py`

**Interfaces:** Produces: `POST /api/projects/<name>/quickcheck -> {findings: [...], errors: [...], provisional: true}` — runs `run_continuity_analysis(doc)` + `check_formatting(doc)` on the WORKING doc (`revision.load_working`/`ensure_working`), no LLM, no state mutation. Client: `runQuickcheck()` merges into the lint layer; lint findings render with a "live check" chip, never counted in `findingCounts` (they are not model findings — separate `state.lintFindings`).

- [x] **Step 1: Failing test**:

```python
def test_quickcheck_runs_deterministic_passes_on_working_doc(self, http_client):
    project = self._upload_only(http_client).get_json()["project"]
    resp = http_client.post(f"/api/projects/{project}/quickcheck")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["provisional"] is True
    assert isinstance(body["findings"], list)
    # and: no model involved -> works with no llama-server configured
```

- [x] **Step 2: Run, expect 404.**
- [x] **Step 3: Implement** the route (guarded by the same `_error` pattern; NOT under `_analyze_lock` — it's read-only and fast) and the client wiring + "live check" chip styling.
- [x] **Step 4: Gates** — pytest PASS; `node --check`; e2e: edit a line that breaks a heading, lint chip appears without analysis.
- [x] **Step 5: Commit** — `"P2.17: /quickcheck — deterministic lint on edit, provisional and labeled"`

**Deviations.** (1) The route reads through `revision.load_working` and answers 400 when there is no script to check, so `ensure_working`'s `FileNotFoundError` cannot become a 500; it takes no `_analyze_lock` (read-only, milliseconds), which a test pins by holding the lock and calling it anyway. (2) The client does NOT merge into `state.findings` as §Files sketched — the Interfaces line forbids it, and merging would put unjudged rule rows inside `findingCounts()`, the mass strip and the ink. `state.lint` is its own layer, and the ledger's live-check section is mounted a second time in the *unanalysed* branch of `renderDockEvidence`, so the chip can appear with no report at all (that is what Step 4's gate asks for). (3) The five edit tails (inline save, apply-one, apply-many, undo, redo — plus reset) collapsed into one `afterScriptEdit()`; a full report landing clears `state.lint`, because the pass subsumes the provisional answer it replaces. (4) The e2e is its own suite (`tests/e2e_browser_quickcheck.py`, 15 legs) rather than a section of `dock_sections`, because its whole premise is a desk that has never been analysed.

### Task 18: Pass history + convergence line (NEW store)

**Files:**
- Create: `screenplay_studio/pass_history.py` — `append_pass(m, summary)` / `load_passes(m) -> list[dict]`; store `pass_history.json` in the project dir via `atomic_write_json` + `lock_for`
- Modify: `webapp_server.py` — append inside `_analyze_locked` completion path; `GET /api/projects/<name>/passes -> {passes: [...]}`
- Modify: `app.js` — one convergence line under the arrival strip: "Pass N · X → Y open · converging/steady" with hover sparkline (inline SVG, no lib)
- Test: `tests/test_pass_history.py` (new)

**Interfaces:** Produces: entry shape `{ts, total, open, addressed, failed_categories}`; `GET .../passes`. Consumes: `finding_statuses` summary + `failed_categories` already computed in the analyze path.

- [x] **Step 1: Failing test** — `tests/test_pass_history.py`: append twice, read back ordered; concurrent-append under `lock_for` keeps both entries; damaged file → `StoreUnreadable` (store contract, not silent empty).
- [x] **Step 2: Run, expect FAIL** (module missing).
- [x] **Step 3: Implement** store + append hook + endpoint + client line.
- [x] **Step 4: Gates** — pytest PASS; `node --check`; e2e: two analyses → line reads "Pass 2".
- [x] **Step 5: Commit** — `"P2.18: pass_history store + convergence line (your revision arc)"`

**Deviations (recorded, not hidden):**
1. Step 2's red was never watched for the STORE: `pass_history.py` and `tests/test_pass_history.py` were written in the same breath, so "module missing" could not fail. What WAS watched red: the client line (`tests/e2e_browser_pass_arc.py` printed `arc=None` on both legs before `buildPassArcLine` existed) and the append hook (commenting out the two `_record_pass(m)` calls fails exactly the three arc legs in `tests/test_webapp_api.py`; restoring them turns them green — so those legs prove the HOOK, not merely the route).
2. The plan named one test file; the work left four gates behind: `tests/test_pass_history.py` (store, incl. two real child processes appending at once), `/passes` endpoint legs, `tests/e2e_browser_pass_arc.py`, and a `StoreCase` in `tests/test_store_fault_injection.py` — the last was not optional: `test_every_store_writer_is_in_the_registry` failed until the new store joined the fault-injection battery.
3. The convergence line mounts in the Evidence dock, because that is where the ledger renders, so the suite opens the dock before measuring (the first RED run's `arc=None` was partly that, not only the missing builder).
4. Hover is the native `title` tooltip rather than a JS popover: same information, no new surface, no library.
5. `open` in the arc is the ledger's open count AS OF each analysis, which is why the line's title says so — counting the writer's marks made since the newest pass would read as progress the desk has not verified.

---

# PHASE P3 — Layout polish + final gate

### Task 19: Floating cards off the manuscript + one matcher for ink and click

**Files:**
- Modify: `app.js` — `inkAnchorsFor` (5281) + `decorateLineWithInk` (5321) + the `el-anchored` pass (4713–4728); floating card positioning (~4526–4558)
- Modify: `style.css` — card positioning (never over `.scene-page` text: pin to the margin rail or below the line)
- Test: `tests/e2e_browser_counting_contract.py` (extend)

**Interfaces:** Produces: `matchQuoteInScene(sceneEl, quote) -> Range | null` (app.js) — the ONE matcher used by BOTH ink decoration and click-anchor wiring, so inked ⇔ clickable by construction.

- [x] **Step 1: Failing e2e** — (a) every `.finding-ink` ancestor line also has a click handler (`el-anchored`); (b) no finding card's bounding box intersects any `.scene-page` text node's box (`getBoundingClientRect` overlap assertion).
- [x] **Step 2: Run, expect FAIL** (the audit photographed both failures).
- [x] **Step 3: Implement** the shared matcher and re-anchor cards to the margin.
- [x] **Step 4: Gates** — `node --check`; e2e PASS night + dawn.
- [x] **Step 5: Commit** — `"P2.19: cards never cover the page; ink and click share one matcher"`

**Deviation — the new suite is its own file.** The plan named
`tests/e2e_browser_counting_contract.py` (extend). That suite's premise is a REAL
demo analysis, and a real report inks NOTHING: measured 0 `.finding-ink` on the
sample project's 20 findings, because the model's quotes are paraphrases no single
line contains. An ink contract asserted there would be vacuously green. The legs
live in `tests/e2e_browser_one_matcher.py` instead, over a seeded fixture report
whose three quotes are chosen to make the two old matchers disagree (cross-wrap /
wrong punctuation / absent).

**Deviation — no `matchQuoteInScene(sceneEl, quote) -> Range | null`.** A Range
would be a third way to answer a question the ink already answered. The mark
itself is the anchor: `decorateLineWithInk` now stamps `el-anchored` +
`data-finding-index` on the line it decorated, and `wireInkClicks(root, activate)`
hangs the click off that line, so the two surfaces cannot disagree by construction.
Both mount-time anchor passes (workspace + revision view) and their
`lt.includes(qq) || qq.includes(lt.slice(0, 40))` predicate are deleted;
`prepareManuscriptData` no longer builds `anchorsByScene`.

**Cards: measured, not moved.** "Floating cards must never overlap page text"
already holds — P0.2's margin made `.scene-notes` in-flow under the container
breakpoint and gutter-pinned (`position:absolute; left:100%`) above it. Both
layouts measured 0 cards over text (night, dawn, and dock-open/in-flow), so
Step 3's re-anchor is a no-op and the leg stays as the absence contract.

**Honest cost.** Ink respects `findingPassesFilter`; the old click pass did not.
So a finding the ONE filter hides is now neither highlighted NOR clickable on the
page — previously it kept a `❋` marker you could click. That is the spec's own
"ink discipline unchanged ... the ONE filter drives the page" reading, and its
card is still reachable from the ledger.

### Task 20: Width budget — persona drawer vs dock (script never <50%)

**Files:**
- Modify: `app.js` — persona open paths (`openSameerWith`, 🩺 escalation ~4310), dock geometry
- Modify: `style.css` — the <1600px swap rule
- Test: `tests/e2e_browser_phase12_visual_motion.py` or the layout-audit suite (30-check layout audit mentioned in SESSION_SUMMARY) — add the 50% assertion

**Interfaces:** Produces: `PERSONA_BESIDE_DOCK_MIN_WIDTH = 1600` (app.js const). Below it: opening a persona collapses the dock to its edge button and mounts the chat in the dock's zone with the originating finding card pinned atop; at/above: side by side.

- [ ] **Step 1: Failing e2e** — at 1440px viewport, open 🩺 from a finding card: assert `#manuscript-container` width ≥ 50% of viewport AND the originating card's quote is pinned atop the chat.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** the width rule + pinned-card header in the persona drawer.
- [ ] **Step 4: Gates** — `node --check`; layout audit green at 1440 and 1920.
- [ ] **Step 5: Commit** — `"P3.20: persona-beside-dock width rule; manuscript never under 50%"`

### Task 21: Final gate

- [ ] **Step 1:** `python -m pytest tests/ -q` — full suite green (3 known baseline flakes excepted, per NOTES).
- [ ] **Step 2:** `python tests/run_browser_suites.py` — all browser suites green.
- [ ] **Step 3:** Spec acceptance walk — check every box in `2026-09-22-one-feedback-room-design.md` §11 against the running app.
- [ ] **Step 4:** `docs/CODEBASE_MAP.md` updated (`pass_history.py`, `/quickcheck`, `/rules/<id>`, `dockSection`, `refreshAllFindingSurfaces`, `matchQuoteInScene`, removed symbols); `NOTES.md` final entry.
- [ ] **Step 5: Commit** — `"P3 gate: One Desk, One Ledger complete — spec §11 walked"`

---

## Self-review notes (run before handoff)

- **Spec coverage:** §2 flow → Tasks 2 (restore), 15/16 (progress + retry), 14 (banner); §3 layout → Tasks 6–8, 20; §4 kill list → Tasks 1, 2, 10, 16; §5 ledger → 6–8; §6 arrival → 9; §7 honesty → 12–14 (+ `formatting_findings` in 14); §8 sync → 3, 4, 10; §9 guardrails → Global Constraints; §10 Phase 2 → out of scope here; §14 additions → 14 (strengths, read confidence), 8/10 cards (pin-to-notes is Task 14's finding-card work — **flagged: the "📝 pin to notes" verb is spec §14.2 and must land in Task 14's `findingNoteEl` edit, one button + existing POST /notes**), clean-scene ✓ → Task 7's scene-rail sibling (add to Task 7 step 3: rail renders ✓ for zero-live-finding scenes via `sceneIndexSeverity`); §15 → Tasks 15–18.
- **Placeholder scan:** every task carries files, anchors, and runnable gates; test code is real where the contract is new.
- **Type consistency:** `findingDisposition`/`findingCounts`/`findingPassesFilter` signatures identical everywhere used; `queueCounts()`, `refreshAllFindingSurfaces()`, `dockSection()`, `matchQuoteInScene()`, `runQuickcheck()` defined once, consumed by name in later tasks; `state.findingFilter.scene` added once (Task 7) and read only through `findingPassesFilter`.

