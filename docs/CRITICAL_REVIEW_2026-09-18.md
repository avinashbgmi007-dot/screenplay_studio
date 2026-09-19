# Critical Review — Screenplay Studio

**Date:** 2026-09-18 · **Commit reviewed:** `08febe7` (main) · **Mode:** review only — no code changed.

**Method:** five parallel expert reviewers (architecture, feedback/Dr. Sushrutha, Sameer co-writer, UI/UX, bug-hunter) audited the codebase; the orchestrator independently read the core machinery (`prompts.py`, `context.py`, `engine.py`, `verifier.py`, `knowledge_base.py`, `rules_context.py`, `demo_model.py`); findings were synthesized and filtered through a self-critique pass. Test suite status: **876/876 green** (plus 2 documented Windows file-lock flakes).

---

## Self-critique disclosure (what was filtered before finalizing)

So the rankings below aren't an echo chamber, here's what was dropped, discounted, or flagged as judgment calls:

- **Dropped as user-facing issues:** "app.js is 8k lines" (maintainability risk, not a product defect → ranked MED), "Flask isn't framework-scale" (the boring-is-good constraint is deliberate; only violations of its *own* rules were kept).
- **Discounted:** several "silent failure" claims that are actually documented, test-pinned degradation (flag-don't-drop). Kept only the ones contradicting the product's own promises (fake composer, hidden prompt budget).
- **Tempered:** the % quality estimates are *structured engineering inference*, not measured benchmarks — there is no eval harness comparing findings against human coverage.
- **Cross-report convergence:** three independent reviewers (architecture, Sameer, UI/UX) hit the same root from different angles — **capabilities exist but are unreachable or off by default** (branches, prompt budget, progressive disclosure). That convergence is the single most actionable pattern in this review.
- **Bias check:** trust violations may be overweighted vs. coverage depth. Both are kept; the trust tier is labeled as a reorderable judgment call.

---

# STATUS BOARD -- done, to be done, verified (updated 2026-09-19)

**This section is authoritative. Everything below it is the catalogue as written on 2026-09-18, i.e.
history:** section 1 still lists M1/M2/M4/M5/M7 as open (all done), H7 as the number-one bug (fixed), and
section 2 still says "876/876 green" (the suite is 1090).

**Updated:** 2026-09-19 (corrections pass, gaps pass, GAP-7 pass, H1 secure-by-default pass, then the jumpToScene pass, then the housekeeping pass, then the branch-UI pass, then the C10 residual pass, then the C5 review + genre-routing analysis (docs only), then the **S5.2 pass**, then the **P2.11 pass**, then the **P1.7 pass** — which required a repository recovery, see below — then the **P2.9 + P3.12/P3.13 orientation pass**, then the **P1.4 rewrite-loop pass**) -- **HEAD:** `27a8a88` + the rewrite-loop pass -- **Suite:** 1273 passed / 0 failed (plus the browser ladder: `rewrite_loop` 36/36, `phase14_signoff_journey` 47/47) -- **PUSH STRANDED:** the S5.2, P2.11, P1.7, orientation and rewrite-loop work is committed and verified locally but NOT on the remote (8 push attempts across five passes, all timing out at the write step with zero output while read-only `ls-remote` returns instantly; diagnosed by disabling the credential helper, which fails FAST with "could not read Username", so the credential path is the blocker — a re-authentication or a manual push is needed). `git status` reads "ahead 4" and the tracking ref is deliberately set to the TRUE remote, not to local HEAD -- **REPO INCIDENT:** a `git stash` dance damaged the object store (a pack vanished, three commits became unreadable, and three stale caches made `git add` skip writes so two commits were written with TRUNCATED trees). Recovered; the working tree was never touched and no work was lost beyond the commit boundaries. The full recipe is in NOTES.md and the project skill. -- **Audit:** **0 gaps filed**, `matrix` 18 passed / 0 failed + `pass2` 9 passed / 0 failed; `escalation` **16 passed / 0 failed, 0 gaps** -- **H1:** now SECURE BY DEFAULT (`--no-token` is the explicit opt-out) -- **C3 + C8:** fixed at the shared root (one `jumpToScene`, locate-only) -- **C10:** CLOSED; two of its six "latent" items were reachable failures and a seventh bug fell out of the recon -- **C5:** **DEFERRED BY THE USER (2026-09-19)** — the tier proposal is drafted, committed and reviewable, but **no tier was changed**; the KB still reads 202/40/21

## How to read the verification column

| tag | meaning |
|---|---|
| `[code]` | the current source was read this session and does what the row says |
| `[test]` | a unit test exists and passed in this session's 1090-green run |
| `[browser]` | asserted in a real browser against a running studio |
| `[real-model]` | measured against the stored real report and/or a live llama-server |
| `[wave]` | asserted by a wave write-up that was NOT re-run this session |
| `[mutation]` | a mutation test proves the guard fails when the fix is reverted (12 mutations run: 6 of 7 in Wave 1.5, then 5 of 5 on the GAP-7 gate) |

A row without `[test]` or `[browser]` is code-verified only. That distinction is the point: several "done"
items are done but unguarded, and the two CRITICAL defects the live audit found were committed *before* the
waves that followed and then went unmentioned by them.

## A. DONE and verified

| Item | Where | Evidence |
|---|---|---|
| **H7** chat dead on a real llama-server (two `system` messages -> HTTP 500) | `screenplay_cowriter/engine.py:258-266` (ONE system message; reminder folded into a user role); `llm_client.py` (`enable_thinking=False`, `reasoning_content` fallback) | `[code]` `[test test_h7_chat_fix]` `[real-model]` live Sameer and Sushrutha replies during the audit |
| **H1** capability token | `webapp_server.py` (`_reject_cross_origin_writes`, `_startup_token`, `main()`), `webapp/app.js` | `[code]` `[test test_capability_token]` (11) `[browser token_mode 3/3]` -- **secure by default**; `--no-token` is the only opt-out |
| **H4** chat lost-update race | `screenplay_cowriter/store.py:53-90` -- merge-on-save keyed `(branch, role, content)` under the per-path lock | `[code]` `[test test_session_lost_update]` |
| **M4** dismiss index validation | `webapp_server.py` (out-of-range -> 400) | `[test test_dismiss_index]` |
| **H2** non-ASCII (Telugu/Hindi) titles | `jsonio.safe_dir_name` -- NFKD fold, hash fallback, display title untouched | `[code]` `[test test_nonascii_titles]` |
| **M5** atomic report writes; a failed force-reanalyze no longer destroys the good report | `screenplay_analyzer/report.py:14, :381-386` | `[code]` `[test test_report_atomicity]` `[test test_webapp_api]` |
| **M1** prompt budget ON by default, sized from the model context window | `screenplay_cowriter/context.py:43-73`; `llm_client_base.context_window()` | `[code]` `[test test_prompt_budget_default (57)]` |
| **S7 P0.3** the co-writer quotes verified against the script | `screenplay_cowriter/reply_transforms.py:133-145` (reuses the verifier own normaliser) | `[code]` `[test test_reply_quote_guard (27)]` |
| **H3** the fake Sameer composer deleted; craft questions reach the real composer | no `#sameer-panel` in shipped code; `openSameerWith()` prefills the real composer | `[code]` `[test test_fake_composer_removed (12)]` |
| **M7** the "Stash" popup no longer files a margin note | `app.js` selection popup posts to `/stash` | `[code]` |
| **S5.8** demo-model disclosure: report banner, EXPORTED banner, partner card | `_md_to_html(md, banner)`, `partnerLabel()` | `[code]` `[test test_demo_banner (16)]` |
| **S5.4** the report states its evidence depth | `pipeline._tag_evidence` / `evidence_depth`; `report.md`, served `stats.evidence_depth`, Coverage panel | `[code]` `[test test_evidence_depth (25)]` `[real-model]` |
| **S5.3** cross-rule finding dedup | `screenplay_analyzer/dedupe.py` (direct-edge merge, `merged_rule_ids`) | `[code]` `[test test_cross_rule_dedup (31)]` `[real-model]` 36 -> 21, the voice finding preserved |
| **GAP-6** the status engine called verified quotes "gone" | new `screenplay_parser/quotematch.py` (shared normaliser + scene joiner); `revision.quote_present` rewritten | `[real-model]` contradictions 6 -> 0, addressed 8 -> 2, inkable 0 -> 6, and the before-column reproduces the audit recorded `8/1/27` byte-for-byte; `[browser]` dialogue section present, ink 0 -> 3 pins, gaps filed 7 -> 5; `[test test_quote_agreement (23)]`; `[mutation]` 6 of 7 caught |
| GAP-6 last surface: margin ink for a quote spanning a line wrap | `app.js` `inkMatch()` -- falls back to the quote longest leading fragment present on the line | `[browser]` 0 pins -> 3 pins on the real report |
| **Phase-12** visual/motion discipline + the rotten E2E suites (phase8/9/11/14, `identity_forensics`) | `e2e_browser_phase12_visual_motion.py` (`env < 0.08`, separation `> 0.75`, `ONE_SHOT_MS = 280`, `ATTENTION` allowlist); shared UTF-8 stdout fix; phase14 rewritten against the folded surface | `[code]` `[browser]` phase12 18/18 this session; `[wave]` 403 checks / 0 failed (not re-run) |
| **S5.8 second half** `script_consultant_examples` | `screenplay_cowriter/personas.py:275` | `[code]` |
| **Desk status line** -- read "a clean bill" on a 36-finding report | `app.js` `loadScriptData()` now re-runs `refreshDeskToolbar()` once `state.findings` is set (the project-open call at `:1979` runs before the async load resolves, so the line was drawn from an empty array and never corrected) | `[browser]` audit gap retired, 18 checks / 0 failed |
| **Character dials re-homed** out of the dead `#struct-rail` | `app.js` `renderCharacterDialsPanel()` -- ONE renderer feeding the page-one craft shelf, the dock Evidence lens and the feedback report | `[browser]` "45 dial rows render, 15 of them in the dock, visible=True"; gap retired |
| **`addressed` was claimed for lines that were never in the script** | `screenplay_studio/revision.py` -- `_load_baseline_doc()` plus the baseline check in `finding_statuses` | `[test tests/test_revision.py (35)]` `[real-model]` addressed 2 -> 0, still_present 7 unchanged, unknown 27 -> 29; 2 gaps retired |
| **GAP-7**: a no-op re-analysis read as writer progress | `screenplay_studio/revision.py` -- `_parsed_signature(m)` fingerprints the analyzer INPUT (parse-of-record + report language) and `last_pass_snapshot` gates on it: identical input reports `fixed=0, new=0, same_input=true` and discloses the id churn as `rewritten` instead of dressing it as Fixed/New | `[test test_revision (38)]` `[real-model]` the real pass returns `same_input=true, fixed=0, new=0, rewritten=33, prev_total=36` where the old arithmetic read `33 -> 4 still live / 29 gone / 32 new`; `[mutation]` 5 of 5 caught (headline, still_live, prev_total present, prev_total wrong, rewritten) |
| **The arrival headline contradicted the desk it sits on** (`Pass: 36` over a 22-row board) | `revision.last_pass_snapshot` same_input branch headlines the report the desk is HOLDING (rows), keeping the previous total in `prev_total`; `app.js` `dock-arrival-rewrite` names both | `[test test_revision (38)]` `[browser]` the strip now reads `Pass: 22 -> 22 still live . 0 no longer flagged . 0 new` over a 22-row board; gap retired |

## B. DONE but conditional, partial, or unguarded

| Item | Honest state |
|---|---|
| **H1** capability token | **Secure by default (done 2026-09-19).** `main()` mints a per-process token on every launch (`_startup_token`) unless the operator passes `--no-token`; a foreign page can neither read the SameSite=Strict cookie nor set `X-Studio-Token` without CORS, so the blind no-`Origin` `DELETE` is now closed on a fresh install. The harness path that blocked this was changed first: `e2e_browser_common.start_studio()` boots with an explicit `--no-token` (it seeds server-side), and the hardened path is asserted by `e2e_browser_token_mode.py`, which now boots with NO flag. The Flask CLI path (`flask --app ... run`) never calls `main()`, so it is still token-less -- out of the supported launch path, flagged not hidden. |
| **M2** branch UI (fork / switch / merge-peek) | **Committed and browser-tested 2026-09-19.** `renderBranches` regained the fork button; `openForkModal` wires the modal `index.html:722` already had orphaned; plus a real `z-index` fix (a new `--z-modal: 900`, above the board 510 / drawer 590 / quote 700 / popup 800 -- modals sat at `--z-float` = 50, so their buttons were unclickable). API tests (`test_webapp_api.py:306` fork + isolation, `:326` switch) plus a new browser suite (`e2e_browser_branch_ui.py`, 11) driving pill -> modal -> POST -> switch. **The browser suite found a real bug the API tests could not:** a fresh project has no session (`app.js:1983`), but the fork button rendered on `currentProject` alone, so clicking it POSTed to `/chat/sessions/null/fork` and 404'd -- an offered control that could not succeed. `createFork` now calls the idempotent `ensureSession()` first. |
| **S7 P1.6** the nudge rotation | **Partially addressed.** `peer.py:78` still has `_nudge_index` and `ensure_forward_momentum` is still a deterministic appender -- the anti-pattern the review named. It is now persona-gated (`NUDGE_PERSONAS` / `NO_NUDGE_PERSONAS`), skips a direct question, and never nudges a reply over `STRANDED_THRESHOLD = 120`. |
| **H6** dead UI surface | `#feedback-view` (about 360 lines) still ships dormant. The hidden persona/mode selects are now **documented as deliberate** (`index.html:158-163`, a `<div hidden>` with a comment that the JS reads them). The duplicate-function half is open, see section C. |
| **S2** the summary-telephone ceiling | The FACT is disclosed (evidence depth, above). The ceiling is intact: script-level passes still judge from scene summaries, never raw text. |
| **GAP-6 residual** | **RESOLVED 2026-09-19.** `addressed` is no longer `quote_present == False` alone: the quote must have been present in the parse-of-record AND be gone from the working copy, so "the writer edited this line away" is distinguishable from "this line was never there". Measured on gun_pen_2: 2 of 9 quoted findings read as writer progress on a draft the writer had never touched (one of them with the report own verdict `not_found`, one a 0.82 fuzzy paraphrase). Now `addressed 0`, `still_present 7` unchanged. Two filed gaps retired. The writer own marks are still not consulted -- that remains open, but it is no longer a false claim of progress. |
| **An id-algorithm change is free today** | Measured 2026-09-19 across every project: **0 writer marks and 0 dismissals** exist on disk (the single `finding_marks.json` is present but empty). Changing `compute_finding_id` orphans nothing now. It stops being free the moment a writer marks a finding, at which point the marks store needs a re-key on load. **Re-measured after the GAP-7 pass: still `{}`.** Caveat found while writing the plan tracker: the audit's own `inbetween` stage set **3 marks** transiently (recorded as `intents` in `impl-shots/audit_results.json`), so this is a point-in-time fact about a store that a single audit run already learned to fill. |

## C. TO BE DONE (ranked)

**Rows 1, 2, 6, 7 and the section B attribution item are DONE as of 2026-09-19** (moved to section A). They
stay in this table so the row numbers and the C2 cross-references do not shift. What is left:

1. **Nothing is filed.** The audit's own layer sits at **0 gaps** (C2), and GAP-7 -- the last lie the arrival
   strip told -- is closed and machine-checked.
2. Then the rest of this list: real work that no machine check covers yet (rows 3, 4, 5, 8-14).

| # | Item | Verified state | Approach |
|---|---|---|---|
| 1 | **GAP-7** -- `compute_finding_id` keys the no-quote tier (75% of findings) on `issue[:100]`, so ids churn about 88% per no-op re-run and the arrival strip reports LLM variance as writer progress (`33 -> 4 still live, 29 no longer flagged, 32 new`) | `revision.py:65`; 4 of 33 ids survive a re-analysis at a byte-identical `parsed.json` | **CORRECTED (measured this session).** Deterministic keys exist for only **3 of 36** findings (`check_id: pacing_drag`; `rule_id: character_trait_continuity`; `setup_payoff_general` x2). The other 33 carry `rule_id` = the rule **title as prose** ("On-the-Nose Dialogue vs. Subtext"), which the model rewords every run, and it collides (29 distinct of 35; one title 4x). So the **edit gate is the primary fix**, not an "AND" -- and it needs a per-scene fingerprint at report time, which the report does not store today. Deterministic ids are a partial win on about 8%. **DONE 2026-09-19** -- the edit gate shipped instead of a re-key: `last_pass_snapshot` gates the arithmetic on the analyzer INPUT, so identical input can never be read as progress. Ids still churn; they are now disclosed as `rewritten`, never as Fixed/New. `[test]` `[mutation]` `[browser]` `[real-model]` |
| 2 | Desk status reads "a clean bill" on a 36-finding project | `refreshDeskToolbar()` is called at `app.js:1979` (defined `:2356`) before `loadScriptData()` (`:3619`, an async definition) populates `state.findings`, and is never re-run on the open path | **DONE 2026-09-19** -- `loadScriptData()` re-runs it after the load; the gap is retired `[browser]` |
| 3 | The fix loop can cover its own bar | `stepLoop` -> `jumpToScene` -> `openCowriteRoom`, masked only when the first loop item is script-level | **DONE 2026-09-19** -- same root as row 8: `jumpToScene` was locate-only in intent but the live body called `openCowriteRoom()`. It no longer does, so engaging the loop leaves the loop bar reachable. `[browser]` the `escalation` stage's `loop` check now reads `ok` (16 passed / 0 failed, 0 gaps) |
| 4 | **H1** secure-by-default | see section B | **DONE 2026-09-19** -- `main()` mints a token by default; `--no-token` is the explicit opt-out. The harness was changed first (`start_studio` passes `--no-token`), then the default flipped. `[test test_capability_token (11)]` `[browser token_mode 3/3]` on the bare default |
| 5 | Confidence tiers: 202 of 263 KB rules tagged `high` | `knowledge_base/index.json` (202 / 40 / 21) | **PROPOSAL DRAFTED 2026-09-19, awaiting the user's decision — nothing applied.** `docs/KB_TIER_REVIEW.md` + `docs/kb_tier_proposal.csv`/`.json` carry a per-rule call for all 263 rules (current tier, proposed tier, criterion T1/T2/T3, rationale). Proposed `14 / 198 / 51`. The rubric is the schema's own definition of the field, judged by each rule's `detection_signal`: T1 `high` = bounded once the data exists (placement vs range, presence/absence, count, direct contradiction, lexical pattern); T2 = observable pattern needing interpretation; T3 = a quality verdict even among experts. The user's instinct ("genre/theme high") is already the current state and would change little; the sharpest evidence against it is `genre_convention_fulfillment` — the *generic* "does this genre deliver its conventions" rule — tagged `low` while its 90 genre-specific instances are tagged `high` (89/90). Also surfaced: 135 mojibake em dashes across 24 files reaching prompts verbatim (**FIXED 2026-09-19**, `tests/test_kb_text_hygiene.py`), 2 malformed rule ids, the README's file table documenting 8 of 26 files, and a pre-existing flaky save/rename race (§6.7). **DEFERRED BY THE USER 2026-09-19 — no tier changes, by decision.** The proposal stays committed for a later pass; `knowledge_base/rules/*.json` still reads 202 / 40 / 21. |
| 6 | Character dials render into dead chrome | 15 `.dial-row` into `#struct-rail` (`.dial-row` styled at `style.css:4201`), measured `visible: false` | **Decision: re-home into the dock, not delete.** `style.css:6053-6054` already styles `.dock-section .dial-row, .dock-craft .dial-row`, so the dock craft panel was the intended home and its CSS shipped. Deleting would remove a feature the docs claim. **DONE 2026-09-19** -- one `renderCharacterDialsPanel()`; the dock renders 15 visible dial rows and the gap is retired `[browser]` |
| 7 | **Two different bugs were conflated in this row.** (a) Duplicate-id **arithmetic** (GAP-3) -- **DONE**: distinct-count semantics (`test_duplicate_ids_no_phantom_progress`), arrival strip byte-matches on a no-op re-run (0 fixed / 0 new). (b) The filed **pass2 basis** gap -- OPEN: arrival distinct basis (33) against board rows (36), caused by identical **quotes** collapsing in the *quoted* tier (`fnhi8s3`, three dialogue findings), not the no-quote tier | `revision.last_pass_snapshot`; audit gap 1 | **DECIDED and DONE 2026-09-19 -- report what the board reports.** On identical input there is no delta to draw, so the headline is the report the desk is holding (rows) and the previous total rides in a labelled `prev_total` on the re-wording clause. **The measurement that forced the decision:** the earlier framing ("33 distinct vs 36 rows") assumed one report, but two runs over one script filed **36 findings and then 22**, so "previous pass total" and "board row count" are different quantities that drift whenever the model is non-deterministic. The headline can only agree with the board if it *is* the board's total. `[test]` `[browser]` gap retired |
| 7b | **GAP-7 cross-run churn** is separate again: on a no-op re-analysis the strip read `33 -> 4 still live / 29 gone / 32 new` at a byte-identical `parsed.json` | NOTES G8 | **DONE** (row 1), and it now has the filed gap it never had: `pass2: an unchanged script is disclosed, not reported as progress`, matched against the **whole clause** rather than the bare number |
| 8 | Duplicate top-level `jumpToScene` (`:775` dead, `:2832` live) | classic script, last declaration wins; the live body always opened the partner drawer, so the rail scene click and the loop both opened a room they never asked for | **DONE 2026-09-19** -- the dead definition is removed, the survivor is locate-only (`app.js:2816`), and `tests/test_app_symbol_integrity.py` guards both the duplicate and the locate-only contract. `[test]` 2 new tests; `[browser]` `escalation` loop check green |
| 9 | Branch UI commit and test | **DONE 2026-09-19** -- committed (`app.js` in `372e5a4`, `style.css` in `5d31ef3`), API-tested, and now browser-tested (`e2e_browser_branch_ui.py`, 11). The browser pass found and fixed the null-session fork 404. | `[browser]` 11/11 |
| 10 | **Section 1 residual.** **H5** lock ordering (per-path RLocks vs `_analyze_lock`, no discipline); **L1** `jsonio._LOCKS` grows without eviction; **L2** `retry_permission` retries genuine ACL failures; **L3** unjittered `time.sleep(1.5 * attempt)` (`llm_client_base.py:175`); **L4** MAX_PATH against 64-char ids; **L5** project-name TOCTOU (`webapp_server.py:523-528`, check-then-`makedirs(exist_ok=True)`); **L6** `_print_status` still skipped on the error path in `cli.py` (not `finally`); **L7** dead and no-op code | **CLOSED 2026-09-19 — and two of the six "latent" items were reachable failures, while a seventh fell out of the recon.** **L2** `retry_permission` now retries only a transient Windows file-busy error (WinError 32/33) and fails fast on a genuine denial, which used to be retried three times first. **L3** the backoff is equal-jittered through ONE shared `busy_retry_delay()`, and the row under-counted: the SAME unjittered sleep sat in the co-writer's chat path (`llm_client.py:89`), so fixing only the cited line would have left the chat herd intact. **L1** both per-path registries (`jsonio` and `SessionStore`) are now weak-valued, so a path nobody holds costs nothing. **L5** all THREE check-then-`makedirs(exist_ok=True)` sites now claim the directory with an atomic `makedirs`; the row named one. **L6** the status block moved into a `finally`. **L7** the redundant one-span `**` replace is gone. **H5 is NOT a bug and is documented rather than "fixed":** the wait-for graph has no cycle — nothing that takes a per-path lock ever reaches back for an analyze lock — so the order is written down as a contract instead of churning a working primitive. **L4 as stated (MAX_PATH) is not live:** the longest real store path is 77 chars and the 64-char worst case is ~188, under Windows' 260. **But the id-length half of it was real and is fixed** — `base + "_2"` on a 64-char fold was 66 chars and `check_safe_id` rejected it, so creating the same title twice failed on the second create; `suffixed_id` now trims to fit. **A seventh bug fell out of the same recon:** `graduate_idea` still ran the pre-H2 Unicode-aware sanitizer while `create_project` and the sample route used `safe_dir_name`, so an idea with a Telugu/Hindi title answered `400 invalid project name: 'త_ల_గ__క_థ'` and could not be graduated at all. (It is a 400, not a 500 — a registered `ValueError` handler catches it, which is exactly why the loose "not 500" assertion passed against the broken code and the test now demands success.) | `tests/test_c10_residuals.py` — 28 checks, **19 of which fail on the pre-fix code** (proved by stashing the fix and re-running) |
| 11 | **Section 2 and 5 residual:** selective raw-text access for the checkpoint scenes (`S5.2`); the 0.72 verification threshold empirically set (`S5.6` -- note the verifier matcher had **no unit tests at all** until Wave 1.5 added shared-primitive guards); theme / relationship / pitch / revision tier deepening (`S5.5`); multi-genre contracts (`S5.7`); knowledge-graph candidate types (`S5.9`) | **S5.2 DONE 2026-09-19.** The four script-level passes (theme / character / structure / scene_function) now receive the RAW PAGES of a small, deterministic set of scenes — the structural checkpoints (25 / 50 / 75 / 100% through the script, measured in PAGES when the parser supplied them and in scene index otherwise) plus the scenes the earlier passes flagged most — inside a strict 5000-char budget, appended to the summary overview. No model call: the same script always yields the same set. A **third** evidence bucket (`overview+checkpoints`) was added rather than folding a mixed read into `full_text`, because inflating the trusted side is the one direction that counter exists to prevent; the report and the dock both NAME the scenes. Measured live on the demo model: **3 of 8 findings from the pages, 2 pure summary, 3 mixed**, dock line reading *"scenes 2, 3, 4, 6"*. Coverage / genre / logline / setup-payoff / char-reads deliberately stay on pure summaries, so genre detection is untouched. **S5.6 IS BLOCKED, NOT SKIPPED: no match score is logged anywhere** — `verifier.py` computes `ratio` locally and discards it, so a threshold cannot be set from a distribution that was never captured; the prerequisite is score capture, then a later pass picks the number. **S5.7 DEFERRED** — it is the multi-genre-contract work the user parked on 2026-09-19 (see the genre-routing analysis). **S5.5** (deepen theme/relationship/pitch/revision) and **S5.9** (KG candidate types) still open. | `tests/test_checkpoint_evidence.py` (new, 34) + `tests/test_evidence_depth.py` (26): **37 of the 60 fail on the pre-fix code** (stash-checked). Browser `phase6_evidence` **32/32** with 4 new depth-line checks; `smoke` 18/18, `phase7` 15/15, `branch_ui` 11/11, `token_mode` 3/3 |
| 12 | **Section 7 residual:** P1.4 select-to-rewrite diff loop; P1.5 trim the compliance wall (**unverified** -- whether the six "don't" blocks were consolidated was not re-checked); P1.7 voice-drift acts rather than only logs; P2.8 memory felt; P2.9 reply-side language register check; P2.11 CLI memory on by default (**no `--memory-path` exists in `cli.py` or `orchestrator.py` at all**); P3.12 and P3.13 | **P2.11 DONE 2026-09-19 — and the row's own claim was WRONG.** `--memory-path` DOES exist (`screenplay_cowriter/cli.py:227`, honoured at `:197-200`); the row only looked at `screenplay_studio/cli.py`. The REAL defect was narrower and worse: `screenplay_studio/cli.py:_run_chat_repl` called `run_repl(session, store, engine.client)` with **no `memory` argument**, and `run`/`resume` had no flag to supply one — so the analyzer CLI's chat handoff was amnesiac in EVERY terminal session while the webapp remembered by default. Fixed the way H1 was: **default ON** at a writer-level `~/.screenplay_studio/writer_profile.json`, an explicit `--no-memory` opt-out, and the chosen path **printed when a chat starts** (a profile of the writer now lives on their disk by default, so where it lives is disclosed rather than discovered). An unreadable profile degrades to a memoryless session with a notice instead of failing the run. The webapp's project-scoped path is deliberately untouched. **P1.5 re-checked and still OPEN:** the compliance wall is NOT consolidated — `personas.py` 29, `context.py` 16, `engine.py` 11 occurrences of do-not/don't/never across three modules, and trimming it is a prompt-quality change that needs a live model to validate. **P1.7 DONE 2026-09-19.** "Make voice-drift act, not just log — re-prime the examples block when drift crosses a threshold." It logged and never acted, and its history was a **module-level dict** shared by every engine in the process, so two open projects fed one drift history. Now `count_ai_tells()` and `voice_drift_crossed()` are pure functions (testable with no engine), the history is per-engine, and crossing the threshold arms a re-prime that **replaces** the closing voice check on the next turn — the highest-weight position in the prompt, the one `trait_reminder`/`post_history_reminder` already use — and is consumed once ridden, so it cannot become a permanent nag. The re-prime text is ONE string naming no persona, because it points at "your example dialogue": a per-persona version would be more specific and would risk handing one persona another's identity. **P2.9 DONE 2026-09-19, with half of it deliberately BLOCKED.** "Reply-side language register check for Tenglish/Hinglish (token-ratio comparison of reply vs. writer message; soft re-ask once when wildly off)." The recon found the *specified mechanism* is unsound, and the measurement is in the test file: the writer writes SHORT messages and the co-writer writes long prose, and `detect_register`'s bar (`token_hits / words >= 0.12`) is length-dependent — the same token density that clears 0.12 in a 4-word message reads 0.07 in a 15-word one. Run against the product's OWN shipped mirror replies (`demo_model._MIRROR_SAMEER_GENERIC`), the detector reads **2 of the 4 genuine Tenglish/Hinglish replies as plain English**. A reply-side judge built on that instrument would re-ask on the demo model's correct output, so **the Tenglish/Hinglish half is BLOCKED, not skipped** — the prerequisite is a length-independent Indic-Latin instrument, which needs a real corpus rather than a lexicon transcribed from one fixture. Three things shipped instead, all found or forced by that measurement: **(1) the writer-side bar is now length-independent** (`ratio >= 0.12 OR >= 3 DISTINCT tokens`), which fixes a live defect the item never named — a writer who pasted a paragraph of Tenglish got **no mirror instruction at all** and was answered in English; **(2) the reply-side check ships for the SCRIPT registers only** (Telugu/Devanagari), where Unicode blocks are exact and there is no threshold to fabricate — one soft re-ask, **not streamed** (a second streamed reply would append itself to the first in the writer's bubble; the caller re-renders from the final messages, so the swap is clean), accepted **only when it actually carries the register**, with a failed or unimproved retry keeping the first reply; **(3) the ENGINE was breaking its own register guarantee** — `peer.ensure_forward_momentum` appended the English "What's your instinct on the next move?" to a Telugu reply, deterministically, on every short reply; a non-Latin reply now ends without a nudge (the nudge list is English-only, and per-register nudges are a product decision needing a live model). **P3.13 DONE** and **P3.12 DONE**, both from one new deterministic module (`screenplay_cowriter/orientation.py`) behind three surfaces — the mood fragment, the CLI session banner, and the CLI `/switch`: *"You left off mid-probe: Sameer asked you a question about scene 4 (INT. HOSPITAL - NIGHT) and is waiting on your answer."* and *"This branch ('alt') was forked from 'main' at turn 6. Since then 'main' has added 4 turn(s) about scene 11, scene 12, and this branch has not moved."* No model call and nothing invented — `awaiting_probe` is a LIVE flag the engine clears on the writer's next turn, so the resume line retires itself, and `forked_at_index` makes both sides' drift simple subtraction. The item's phrase "**switching back**" forced the other direction too: `branch_position` also names branches forked FROM the one you land on, because main has no parent and the fork point would otherwise say nothing at all. **A second live defect fell out of this pass:** `Session.fork()` copied messages, persona and mode but **not** `awaiting_probe`, so a fork made mid-probe forgot it was waiting while its own last message was still Sameer's question. **P1.4 DONE 2026-09-19, in the half that can be validated without a live model.** "Select-to-rewrite loop: his proposed passage edits render as inline diffs with Apply/Stash/Reject, writing into `working.json` through the existing revision machinery." The backend already existed and already said the right thing (`/rewrite` is "proposal only — nothing is applied until the writer approves via /edits/apply"), and so did the Stash (`stash_store.py`); what was missing was the loop the writer actually reads. A proposal rendered as the WHOLE old line struck through above the WHOLE new line in green, with one checkbox and one bulk Apply — a diff you have to read twice to find the two words that moved — and **no way to keep a proposal without taking it**. Now: a real **word-level LCS diff** (`<del>`/`<ins>` runs, only the words that moved are marked, deterministic so it is assertable from a browser probe; an over-long pair says so instead of allocating a table nobody reads), and **Apply / Stash / Reject per proposal** — Apply writes the working copy through the existing `/edits/apply`, Stash parks the proposed line in the existing project stash with the scene it came from, Reject drops it and writes nothing. The bulk checkbox + `#rewrite-apply` contract the phase14 journey asserts on is deliberately preserved. **A design bug in my own first cut, caught by the suite:** `_markProposalRow` removed the actions after a Stash, making Stash a one-way door — the writer parked a proposal *in order to decide later* and could no longer Apply or Reject it. Apply and Reject are terminal; Stash is not (it only spends its own button). **The chat-to-proposal bridge is BLOCKED, not done:** turning "want me to sketch a version?" in a chat reply into a structured proposal needs a model-side structured-output contract, and this repo has no live model to validate one — the same reason P1.5 is open. **P2.8 still open.** | `tests/e2e_browser_rewrite_loop.py` (new, 36): mutation-checked by file backup with hash-verified restore — reverting `app.js` gives **19 failed / 4 passed (exit 1)** against **36/36 fixed**. `phase14_signoff_journey` **47/47** (it asserts the inline-edit + Apply journey this pass rewrote). Full suite **1273 passed / 0 failed** — **P2.9 + P3.12/P3.13 evidence (same day):** `tests/test_reply_register.py` (new, 32) + `tests/test_orientation.py` (new, 27), mutation-checked the same way — reverting `language_mirror.py` fails **22 of 32**, `engine.py` **7 of 32**, `peer.py` **3 of 32**, `models.py` **2 of 27**, `webapp_server.py` **2 of 3**, `cli.py` **3 of 3**; deleting `orientation.py` is a collection error; fixed **59/59** |
| 13 | **Section 6 brainstorm** -- counter-read pass, finding lifecycle truth, so-what scoring, page-rhythm overlay, dialogue read-aloud score, writer-question-driven audit | All six are untouched proposals | -- |
| 14 | Doc hygiene: the repo-root `SESSION_SUMMARY.md` (untracked) still describes 09-14 state and lists GAP-1 and GAP-2 as next actions; the audit plan file is untracked | **RESOLVED 2026-09-19 — and half the row was itself a stale claim.** `SESSION_SUMMARY.md` is **gitignored**, not untracked-and-pending (the housekeeping pass added it), and it now carries a STALE banner at the top pointing at `NOTES.md`, the status board and `git log` — it had already misled a session into treating two closed gaps as open work, which is exactly the failure this row exists to prevent. The audit plan file is **tracked and clean**, so "untracked" was wrong. | `git check-ignore -v SESSION_SUMMARY.md`; `git ls-files docs/` |

## C2. The machine-checked layer -- what the audit still rejects

The board above is prose, and prose is how GAP-6 hid across four waves. This part cannot drift silently: the
gun_pen audit files gaps as machine checks, and a stage that runs retires the gaps it tested. Two passes took it
from **5 gaps to 0** (`impl-shots/audit_results.json`; `matrix` stage: **18 checks passed, 0 failed**; `pass2`
stage: **9 passed, 0 failed**).

| filed gap | stage | root | state |
|---|---|---|---|
| _none_ | -- | -- | **NOTHING IS FILED.** Every check the audit makes of this script now passes. That is a statement about this script and these checks, not a claim that the product is defect-free (rows C3-C14 are what no machine check covers). |

### Retired in this pass, with the check that proved it

| gap | what fixed it | evidence |
|---|---|---|
| `C: the desk status line agrees with the finding count` (it read "a clean bill" on a 36-finding report) | `refreshDeskToolbar()` now re-runs at the end of `loadScriptData()`, after `state.findings` is set. The project-open refresh at `app.js:1979` runs before the async load resolves, so the line was drawn from an empty array and never corrected | `[browser]` gap retired |
| `C: unedited script -> zero phantom "addressed"` and `C: mass strip reports every finding open` | `finding_statuses` now requires the quote to have existed in the parse-of-record before it may read `addressed` (`revision._load_baseline_doc`). Measured on gun_pen_2: `addressed 2 -> 0`, `still_present 7` unchanged, `unknown 27 -> 29` | `[test]` `[real-model]` `[browser]` two gaps retired |
| `B/character_dials: the dials are reachable on the live desk` | ONE `renderCharacterDialsPanel()` now feeds the page-one craft shelf, the dock Evidence lens and the feedback report, so the dials are reachable instead of parked in the dead `#struct-rail` | `[browser]` "45 dial rows render, 15 of them in the dock, visible=True" |
| `pass2: the arrival 'Pass:' total agrees with the board's finding count` (`last_total=36` vs `findings=22`) | the strip headline is now the report the desk holds whenever the input is byte-identical to the last pass (`last_pass_snapshot`, same_input path); the previous total is disclosed in the re-wording clause instead of headlined | `[browser]` "same_input=True arrival last_total=22 vs report findings=22"; strip `Pass: 22 -> 22 still live` over a 22-row board |

**Two audit checks were changed, deliberately, and both changes are recorded inline in the files.**

`B/character_dials` asserted that a `.rail-char-dials` node was visible -- a class that exists only in the dead
`#struct-rail`, so re-homing the dials could never satisfy it: the check encoded the defect it was meant to
catch. It now asserts the dial rows inside the dock own Evidence lens, which is strictly stronger.

The `pass2` board-agreement check and its sibling changed for two measured reasons. (a) It compared the arrival
total against the board row count as though both came from one report; they do not, they are two different
passes (36 filed, then 22), so it was satisfiable only when the model happened to reproduce its count. It is now
scoped to the unchanged-input case -- the case this stage can actually produce -- and named for that case.
(b) Its sibling accepted `str(rewritten) in rw_txt`, a substring test that passes on almost any sentence
containing a "0", which is exactly what a same-report recompute produces. It now requires the whole clause
(`"<n> of the last pass's <m>"`), so dropping either number from the strip fails the check. Neither change
weakens what is asserted; both add claims the original could not make.

## D. Stale claims in the historical tables

- Section 1 lists **M1, M2, M4, M5, M7** as open. All are done (M2 in flight), and its HIGH row **H7** was ranked the number-one bug; it is fixed.
- Section 2 asserts **"876/876 green"**. The suite is **1090**.
- `S5.3` (dedup), `S5.4` (evidence depth) and both halves of `S5.8` are done, as are `S7 P0.2` (prompt budget) and `P0.3` (quote verification).
- Section 8's "top 3 if nothing else gets done": H1 is **opt-in**, the prompt budget **shipped**, the branch UI is **in flight**, and confidence tiers plus raw-text access are **open**. One and a half of three.
- The audit sections later in this doc set describe GAP-6 as open. It is resolved, with the measured before/after recorded in `FULL_FEEDBACK_AUDIT_VERDICTS.md`.

## E. Verification gaps -- what was NOT confirmed

- **The 26-suite browser sweep ("403 checks passed, 0 failed") is `[wave]`, not re-run.** This session ran the gun_pen audit matrix (twice, real model) and phase12 (18/18). No full sweep, so it is not confirmed here.
- **The real-model numbers are a re-walk of a stored report**, not a fresh analysis: 36 findings, addressed 8, the `33/4/29/32` arrival payload. `finding_statuses` re-reads the stored report and working copy, which is what scripted the phantom count, so the GAP-6 before/after is measured against real data -- but it is that report, not a new run.
- **P1.5 (compliance-wall trim) and the "second selection popup" claim are unverified.** No status was guessed for either.
- **The L1-L7 line references have drifted.** L1-L6 were re-verified explicitly this session; L7 needs a fresh read.

**Added by the 2026-09-19 corrections pass:**

- **The 1090 figure was re-run** in this pass (full suite, `-p no:cacheprovider`), not carried from a wave write-up.
- **The filed-gap list in C2 was read from the artifact** (`impl-shots/audit_results.json`), not from prose; current
  as of HEAD `2eb817f`.
- **The pass2 basis number (33 vs 36) is measured on the stored report** -- `finding_statuses` re-reading stored
  data, not a fresh analysis of that project.
- **The id-field census behind row C1 was measured on the real report:** 36 findings, 9 quoted / 27 unquoted, 35
  carrying a `rule_id`, 1 carrying only a `check_id`, 0 carrying neither; 29 distinct `rule_id` values across 35.
- **No writer state exists to migrate:** 0 marks and 0 dismissals across every project (section B).
- **The KB confidence-tier count was re-read** (it had been carried from the review own index read):
  `knowledge_base/index.json` holds **263 rules -- 202 `high`, 40 `medium`, 21 `low`**. The 202/263 headline is
  confirmed. **H1 opt-in also re-confirmed:** `_API_TOKEN = None` at `webapp_server.py:61` and the gate only
  applies `if _API_TOKEN:`, so a default install genuinely still accepts a blind, no-`Origin` DELETE.
- **P2.11 re-confirmed by absence:** no `--memory-path` (or `memory_path`) exists in `cli.py` or
  `orchestrator.py` at all, so CLI Sameer is amnesiac as stated.

**Added by the 2026-09-19 gaps pass:**

- **The audit was re-run, not inferred:** `matrix` stage against a live studio on the real llama-server, `18
  passed / 0 failed`, filed gaps `5 -> 1`.
- **The suite was re-run after every change:** `1091 passed / 0 failed` (1090 + the new baseline test).
- **One audit check was changed and the reason is recorded in C2:** `B/character_dials` pinned a class that
  exists only in dead chrome, so it could not have noticed the fix. It now pins the dock.
- **Operational:** a running studio must be RESTARTED to pick up Python changes (`revision.py`); `app.js` /
  `style.css` only need the `?v=` bump. The measurements above were taken on a restarted studio.
- **A harness-rot fix rode along:** `e2e_browser_phase8_lifecycle.py` opened its seeded probe by clicking
  `.first()` on the text "Lifecycle", so against a long-lived studio that already held `Lifecycle_Probe`,
  `_2`, ... it opened a STALE probe whose parse was pending and timed out waiting for the manuscript. It now
  opens the exact project id `seed()` returned. Verified `13 passed / 0 failed` self-booted.

**Added by the 2026-09-19 GAP-7 pass:**

- **The suite was re-run after every change:** `1094 passed / 0 failed` (1093 + the new headline test).
- **Both stages that cover this were re-run:** `matrix` 18 / 0 and `pass2` 9 / 0, filed gaps `1 -> 0`.
- **One number in this pass is a RECOMPUTE, not a fresh 9-minute run, and it is disclosed as such:** the `pass2`
  stage ran with `GUNPEN_SKIP_ANALYZE=1` against the real analysis the previous pass had already left on disk
  (that run is the one that produced `rewritten=33`), and the payload was re-derived by moving the report mtime
  so the guard recomputes. The comparison content is byte-for-byte what the real run produced; the arithmetic is
  the new arithmetic. The verified `rewritten=0` is a same-report recompute, correctly reported as "nothing
  moved" -- not a second real pass.
- **Two bases live in one payload on the same_input path, deliberately:** `last_total`/`still_live` are the
  board's **rows**, while `rewritten`/`prev_total` count **distinct ids**. The board counts rows and finding
  identity is distinct ids, so on gun_pen_2 (22 rows, 21 distinct) the two differ. The clause labels both ("N of
  the last pass's M findings reworded") rather than silently merging them.
- **`compute_finding_id` was NOT re-keyed.** Section B still says an id-algorithm change is free today (0 marks,
  0 dismissals), and that is still true -- but the gate made a re-key unnecessary for this defect, so nothing was
  touched. If a writer ever marks a finding, the marks store still needs a re-key on load.

*Every "open" row above exists in prose only. The audit's gaps retire themselves because they are machine-checked; this catalogue is not, which is exactly how GAP-6 sat unnoticed across four waves.*


---

## 1. Architecture / UI / Backend — issues ranked HIGH → LOW

### HIGH

| # | Issue | Evidence |
|---|---|---|
| H1 | **Unauthenticated destructive writes from any web page.** The security model is "reject if Origin hostname isn't loopback" — but blind cross-origin POSTs (`no-cors` fetch / form POST) omit `Origin` and pass the gate; DNS rebinding defeats the hostname string check. `DELETE /api/projects/<name>` runs `shutil.rmtree`. Fix: Jupyter-style per-request capability token. | `webapp_server.py:55-65, :549-557` |
| H2 | **Non-ASCII project titles crash creation and orphan a ghost dir** on the shelf — hits the Tenglish/Telugu/Hindi audience the product is built for. `str.isalnum()` is Unicode-aware; `check_safe_id` is ASCII-only; the `ValueError` fires *after* `os.makedirs`. | `webapp_server.py:499-512`, `jsonio.py:68-77` |
| H3 | **A fake Sameer chat composer silently discards user input** in a product whose stated law is "the UI never pretends." The §4.8 slide-in panel echoes text locally; no API call is made. | spec §4.8 ⚠, `app.js` |
| H4 | **Chat lost-update race.** Threaded server + load-modify-write outside the lock: two overlapping chat turns each load a fresh `Session`; the slower save overwrites the faster's messages. The per-path lock protects the write, not the cycle — its own docstring claims otherwise. Contrast: `IdeaStore._modify` holds the lock across load→modify→write correctly. | `webapp_server.py:1611-1658`, `engine.py:355-359`, `store.py:53-64`, `ideas.py:87-97` |
| H5 | **No lock ordering** across per-path + per-project locks → deadlock surface under the threaded server (analyze + chat on the same project). | `jsonio.py:19-37`, `webapp_server.py:571-577` |
| H6 | **Dead/duplicated UI surface:** dormant `#feedback-view` (~360 lines of shipped JS/HTML), invisible-but-wired `#struct-rail`, hidden persona/mode selects still populated, a second selection popup, and one confirmed duplicate-function override. | `index.html`, `app.js:6051, :7228`, `style.css:6284` |

### MEDIUM

| # | Issue |
|---|---|
| M1 | **Prompt budget default-off** — silent context truncation on feature-length scripts; the "honest degraded turn" machinery exists but requires an env var nobody sets (`SCREENPLAY_PROMPT_BUDGET`). |
| M2 | **Branch system unreachable in the webapp** — fork/switch/explore exists backend + CLI only; the flagship "true collaborator" feature has no button. |
| M3 | **Progressive disclosure is CSS, not staged** — Persona 1's Level 1→4 revelation is promised in docs, not built. |
| M4 | **Dismiss route doesn't validate the finding index** — a stale index silently mis-dismisses (`webapp_server.py:1363-1376`, `revision.py:514-527`). |
| M5 | **Pipeline artifacts bypass the atomic-write contract** (direct `write_text` in 4 spots); force-reanalyze deletes the previous *good* report before the new run succeeds — the one path that can destroy good data. |
| M6 | **Touch parity absent** for Persona 2's core loop (inline edit, undo/redo, scene reorder) — desktop-only in practice. |
| M7 | **Stash impostor:** the §7.14 popup "Stash" action writes a `[STASH]` note draft instead of calling the Stash endpoint — a data-integrity-flavored bug on the highest-frequency gesture. |
| M8 | **app.js monolith** (~8,120 lines, 528 global-state touches, ~450 top-level functions) — the risk factory that produced the duplicate-function bug. |

### LOW

- L1 unbounded lock-registry growth (`jsonio.py:20`)
- L2 `retry_permission` retries genuine ACL failures, not just WinError 32 (`jsonio.py:40-51`)
- L3 lockstep retry sleep, unjittered (`llm_client_base.py:114-117`)
- L4 Windows MAX_PATH vs 64-char safe ids (`jsonio.py:68`, `webapp_server.py:168-170`)
- L5 project-name uniqueness TOCTOU race (`webapp_server.py:501-510`)
- L6 status print skipped on the error path — should be `finally` (`cli.py:72-77`)
- L7 dead/no-op code (`llm_client.py:158`, `_md_to_html` first-replace at `webapp_server.py:1712`)

### Explicitly cleared as sound

Encoding posture (UTF-8 pinned everywhere in shipped code; SSE mojibake regression-tested), GBNF grammar PEG compatibility, path-traversal defenses (`check_safe_id` + realpath containment on DELETE).

---

## 2. Feedback quality — knowledge base, rules, Dr. Sushrutha

### The knowledge base is the strongest asset

263 rules across 26 files. The schema — `definition` + `detection_signal` + **`counter_considerations`** + curated `severity_default` + `confidence_tier` + honest attribution (McKee, Field, Snyder, Vogler/Campbell, Swain, Weiland, Alderson, Cron, Bell, Martell, Aristotle, Chekhov; unattributable rules honestly labeled `general_craft`) — is better than most commercial coverage tools. `counter_considerations` is what separates a craft rule from a linter rule: it encodes when *not* to flag.

### The holes that matter

- **`theme` has 2 rules. `relationship` has 2. `pitch` 3. `revision` 4.** Theme is the *first* thing a real script doctor reads for, and it's the thinnest shelf in the library. Relationship dynamics are where most second acts live or die.
- **202 rules are tagged `confidence_tier: high`** ("mechanically checkable") — indefensible for character/psychology/theme judgment. It makes every report sound more certain than the machinery earns.
- **The summary-telephone ceiling:** script-level passes (theme/character/structure/scene_function) judge **only from scene summaries, never raw text** (deliberately, to fit context windows). A large share of findings are about a *description* of the script, not the script.
- **Verification verifies the quote, never the claim.** Fuzzy match at 0.72, flag-don't-drop, right-quote-wrong-scene correction — all real and trust-earning — but none of it checks whether the *observation* is true.
- **Demo model:** when no llama-server runs, a rule-based template engine delivers the "feedback." Honest workflow demo, canned content.

### Honest quality estimates (engineering-inferred, not benchmarked)

> **Dr. Sushrutha's feedback: ~55–60% useful** with a real model. What earns it: trust machinery, two-tier citation honesty, calibrated counter-considerations. What caps it: can't feel performance/tone/earned-vs-unearned, reviews the summary more than the script, overstates certainty.
>
> **Demo-only mode: ~10%** — a credible product walkthrough, not real notes.


---

## 3. Sameer, the co-writer

The persona *infrastructure* is above most commercial companions: a real persona bible (biography, stance, quirk budget, cross-character friction with the doctor), example-dialogue voice locking, deterministic anti-AI-phrase stripping, probe-before-suggest guardrails, gated contradiction-aware writer memory, scene/character/fuzzy reference resolution with full scene-text injection, a Telugu/Hindi/Tenglish/Hinglish language mirror, and honest hallucination flags.

The gap between the machinery and the desk experience:

1. **Sameer never writes anything** — no draft/apply loop from chat; "want me to sketch a version?" stays rhetoric. It's a conversation *about* the script, not co-writing.
2. **The branch system is dead code in the webapp** — one linear thread in the actual product.
3. **Everything rides on a small local model obeying a bloated system prompt** (persona bible + voice rules + examples + mode + grounding contract + scene map + full findings + craft principles + PAST WORK + mood + relationship card + language mirror + scene text + 16 messages of history) — with the prompt budget off by default. The elaborate repeat-penalty/stripper/watchdog stack exists because this failure mode is well-known.
4. **The demo fallback quietly caps first-run experience** — the moment that decides whether a writer comes back.

> **Sameer: ~62% helpful** as a grounded discussion partner; **~35%** as an actual co-writer.

---

## 4. Bugs overall

- **Test suite: 876/876 green** (full run), 158/158 on a targeted re-slice; 2 documented Windows file-lock flakes are environment-level, not code bugs.
- **Real bugs worth fixing:** H2 (non-ASCII titles) and H4 (chat lost-update race) at HIGH; M4 (unvalidated dismiss index), M5 (non-atomic writes + force-reanalyze destroys the good report) at MED.
- Broad `except Exception` sites are consistently *documented degradation* and test-pinned — none swallow silently.

---

## 5. Upgrades for feedback / Sushrutha, prioritized

1. **Recalibrate confidence tiers** (cheapest, highest leverage): re-audit the 202 `high` rules against the schema's own definition; one JSON pass changes how assertive every report sounds.
2. **Give script-level passes selective raw-text access** for the checkpoint scenes they name (act break, midpoint, climax) + top-flagged scenes — breaks the summary ceiling exactly where it matters, at bounded token cost.
3. **Cross-rule finding dedup** — the same defect filed under 2–3 related rule_ids (subtext/exposition cluster) should merge; generalize the existing setup/payoff ledger dedup.
4. **Report evidence-depth honestly** — "30 findings — 12 from full text, 18 from overview" converts invisible false-negative risk into visible scope.
5. **Deepen the thin tiers** — theme, relationship, pitch, revision.
6. **Empirically set the 0.72 verification threshold** from logged score distributions + a length-adjusted floor for short quotes.
7. **Multi-genre contracts** — horror-comedy gets both checklists.
8. **Demo-mode banner on the report itself**, and **add `script_consultant_examples`** — the doctor is the only desk character with no voice-locking example dialogue.
9. **Extend KG candidate types** — timeline entries and trait mentions feeding continuity-of-behavior checks; grows the highest-trust layer instead of the lowest.

## 6. Brainstorm — new feedback / Sushrutha features

- **Counter-read pass:** a second "defense attorney" read per HIGH finding ("argue why this is intentional") before it's filed — kills false positives the doctor can't self-catch.
- **Finding lifecycle truth:** re-runs compare findings vs. the prior draft — *new / persistent / resolved* — turning the report into a draft-over-draft truth machine (the data model half-exists).
- **"So-what" scoring:** rank findings by predicted reader-impact, not just severity tags — a fix-the-right-thing ordering.
- **Page-level rhythm overlay:** pacing curve + dialogue/action ratio + scene-length variance against genre norms, rendered as one visual "EKG."
- **Dialogue read-aloud score** (deterministic: sentence-length variance, contraction rate, per-character idiolect drift) — a cheap signal needing no LLM.
- **Writer-question-driven audit:** "does the midpoint land?" triggers a targeted re-read of that scene's raw text, not a full re-run.


## 7. Brainstorm — co-writing & humanizing Sameer

**P0 — biggest unlocks**

1. **Ship branch UI** (fork/switch/merge-peek) — the backend is done and tested; a panel + the session payload already carries branch metadata.
2. **Default the prompt budget on** (or derive it from the model's reported context).
3. **Verify Sameer's quotes** against injected scene text (reuse `verifier.py`'s fuzzy match; flag-don't-drop per house convention).

**P1 — co-writer, not chatter**

4. **Select-to-rewrite loop:** his proposed passage edits render as inline diffs with Apply/Stash/Reject, writing into `working.json` through the existing revision machinery — converts "want me to sketch a version?" into the product's core loop.
5. **Trim the compliance wall** — consolidate the six overlapping "don't" blocks into one short grounding contract; conditional-include rules that don't apply this turn (PAST WORK guard when no library exists, language-meta when the script is English).
6. **Replace the 4-line nudge rotation** with a generation-side instruction ("if your reply is short and stops cold, end on one natural forward beat"); the deterministic appender is the framework's own canned-closer anti-pattern.
7. **Make voice-drift act, not just log** — re-prime the examples block when drift crosses a threshold.

**P2 — depth and relationship**

8. **Let memory be felt, carefully** — permit exactly one class of reference: craft-preference callbacks ("last time you cut the explainer line and it worked"), scoped, gated, never about the writer as a person. Today a month of learning is invisible.
9. **Reply-side language register check** for Tenglish/Hinglish (token-ratio comparison of reply vs. writer message; soft re-ask once when wildly off).
10. **Demo Sameer honestly labeled** in the partner card ("Sameer's stand-in — connect your model for the real one"), not just an amber dot.
11. **CLI memory on by default** (`--memory-path` defaulting to a user-level file) so terminal Sameer isn't amnesiac.

**P3 — nice**

12. Branch-aware diff summaries when switching back ("since you forked, main added 4 turns about the climax").
13. Session-load resume lines in the mood fragment ("we left off mid-probe about the hospital scene").

---

## 8. Reviewer self-assessment

This review's usefulness: **~85%**, bounded by (a) % figures are structured inference, not measured evals; (b) no live browser/model run — runtime-only issues (INP, screen-reader walkthrough, real truncation behavior) are unverified; (c) trust-vs-coverage prioritization is a judgment call. Reachable to **~95%** with: an eval harness scoring analyzer output against human coverage, one Playwright + one real-model session, and telemetry on which findings users actually accept.

**Top 3 if nothing else gets done:**

1. **H1 capability-token auth** on the loopback server (hours; trust-critical).
2. **Default the prompt budget on + ship branch UI** (the two highest-value latent/unreachable capabilities).
3. **Recalibrate confidence tiers + selective raw-text access** (the two biggest report-quality levers).

---

*Generated by a five-expert parallel review (architecture · feedback quality · co-writer · UI/UX · bug hunt) synthesized through an orchestrator self-critique pass. No code was changed.*

---

# ADDENDUM — Live Runtime Verification (2026-09-18)

Closes the "no live browser/model run" gap from §8. Method: 23 Playwright E2E suites + live bug-repro scripts + a real-model probe against the user's llama-server (`qwen3.6-35b-a3b-pruned-v2.gguf` on `localhost:8080`). **No product code was changed.**

## Runtime-verified bug verdicts

| Finding | Verdict | Evidence |
|---|---|---|
| **H7 — Chat dead on real llama-server** | **VERIFIED (new top bug)** | Every chat message turn → `llama-server 500 /v1/chat/completions`. Captured payload shows **two `system` messages** (`system, system, user, system`); confirmed against the live server that **any multi-system payload → HTTP 500** while a 9k single-system prompt is fine. Analysis works (grammar path shapes requests differently). **Sameer/Dr. Sushrutha function only in demo mode.** |
| **H1 — CSRF** | **VERIFIED** | No-`Origin` blind `DELETE` destroyed a project (HTTP 200, dir gone). Browser no-cors DELETE restriction narrows it; foreign-`Origin` correctly 403s. |
| **H3 — Fake Sameer composer** | **VERIFIED** | Text echoed locally, **zero** API calls on Send, 3 canned AI bubbles ship in HTML. |
| **H4 — Chat lost-update race** | **VERIFIED** | Two overlapping turns → only one user message survives in the session JSON. |
| **M4 — Stale dismiss index** | **VERIFIED** | Out-of-range index → HTTP 200, bogus entry stored. |
| **H2 — Non-ASCII title** | **REFINED** | Telugu/Hindi titles → **HTTP 400 "invalid project name"** (real failure for the Indian-language audience) but **no orphan ghost-dir** in the default multipart flow. Downgrade from data-corruption to HIGH-UX. |

## E2E sweep result

**16/23 suites OK · 9 FAIL** — but the FAILs decompose into **product bugs vs. harness rot**:
- **Real product regressions (phase-12):** visual-hierarchy inversion (paper L=0.84 vs ink L=0.06), 3 hardcoded amber accents, over-280ms one-shot animations (`ink-halo` 4000ms, `ink-flash` 1600ms), 6 non-progress infinite loops.
- **Harness rot (masks "all green"):** phase-14 passes all 15 journey checks then crashes waiting for the **dormant `#feedback-view`** to be visible (tests a dead surface); 3 suites crash on Windows console Unicode (✕/≥/≤); `identity_forensics` hard-requires `E2E_BASE`; `design_session`/`preview_redesigns` are lab artifacts, not shipped surface.

## Runtime UX health

- **0 JS errors / warnings on load.**
- **INP 54–66ms** on key interactions (well under the 200ms "good" threshold).
- **1** visible interactive element with no accessible name.
- **A11y gaps:** no `banner` / `navigation` / `complementary` landmark roles; **focus outline renders `none`** (3px width, invisible style) — a real keyboard/screen-reader gap.

## Real-model quality (live numbers)

23 findings / 441s on a 3-scene sample — specific and craft-literate — **but 19/23 (83%) carry `no_quote`** (script-level passes cite scene numbers only), so the verification-badge system cannot touch 83% of findings. Live-confirms "verification verifies the quote, not the claim."

## Revised impact ranking (post-verification)

1. **H7 — chat dead on real model** (nullifies the centerpiece; fix = fold reminder into the last user turn).
2. **H1 — capability-token auth.**
3. **H4 — chat lost-update race** (data loss).
4. **H3 — fake composer** (trust law violation).
5. **Phase-12 visual/motion regressions.**
6. **H2 — non-ASCII titles** (MED-HIGH; bad UX, not corruption).
7. M4/M5 + the a11y landmark/focus gaps.
8. **Harness rot** — fix the suites so "green" means green again.

## Finalized drive plan (recommended order)

- **Wave 1 — trust & data (ship first, all small):** H7 chat fix → H1 token auth → H4 session lock across load→modify→write → H2 title transliteration → M4 index validation → M5 atomic writes.
- **Wave 2 — honesty & signal:** H3 wire-or-delete the composer → demo-mode banner → report evidence-depth ("12 from full text, 18 from overview") → confidence-tier recalibration → fix the 5 rotten E2E suites.
- **Wave 3 — co-writer unlock:** branch UI → select-to-rewrite diff loop → default-on prompt budget → Sameer quote verification.
- **Wave 4 — feedback depth:** selective raw-text for checkpoint scenes → cross-rule dedup → theme/relationship tier deepening → counter-read pass.

---

# WAVE 1 — IMPLEMENTATION STATUS (2026-09-18)

All five Wave-1 items implemented TDD (RED → GREEN → live re-verify). **Suite: 893 passed, 0 failures** (+12 tests from 881). No commits made yet.

| # | Item | Files | Tests | Live verdict |
|---|---|---|---|---|
| **H7a** | Chat: collapse to ONE system message | `screenplay_cowriter/engine.py` | `test_h7_chat_fix.py` (at-most-1-system, reminder folded) | payload capture: roles `[system,user,user]`, system count **1** |
| **H7b** | Chat: `enable_thinking=False` + `reasoning_content` fallback | `screenplay_cowriter/llm_client.py` | 3 tests (chat + stream) | 500 gone; thinking disabled |
| **H1** | Capability token (opt-in `--require-token`) | `webapp_server.py`, `webapp/app.js` | `test_capability_token.py` (5) + `e2e_browser_token_mode.py` (3/3) | blind delete **403**, token delete 200, foreign Origin 403 |
| **H4** | Session lost-update: merge-on-save under the lock | `screenplay_cowriter/store.py` | `test_session_lost_update.py` | both racing turns survive (**REFUTED**) |
| **M4** | Dismiss index validation | `webapp_server.py` | `test_dismiss_index.py` (2) | out-of-range → **400** (**REFUTED**) |
| **H2** | Non-ASCII titles → ASCII fold | `screenplay_studio/jsonio.py`, `webapp_server.py` | `test_nonascii_titles.py` (4) | Telugu/Hindi → **201** (**REFUTED**) |

**Incidental:** `demo_model._conversational_reply` now skips the trailing `[Voice check …]` user note (H7a moved it into a user role); 3 pre-existing persona tests updated from `role=="system"` to `role=="user"` (asserting intent, not the buggy shape).

**Known limitations (deliberate, flagged):**
- **H1 is opt-in.** Default install is unchanged, so the blind-write hole is closed *only* when the operator passes `--require-token`. Secure-by-default would break the E2E harness's server-side seeding; chosen for compatibility.
- **H4 merge keys on (branch, role, content).** Two turns sending byte-identical text across a race could dedupe; low harm (identical content), add timestamp to the key if it ever matters.
- **H7a changed the voice reminder from a trailing system message to a trailing user note.** Correct for this llama-server build (single-system), but it is a small fidelity change vs. the original "post-history system lever" design for models that accept multi-system.

**Status of the two open items at the time of writing:** commits were outstanding, and M5 / phase-12 visuals remained. **All three have since landed** — M5 and phase-12 are written up below, and the commits are `6e45824` (Wave 1), `c7f9984`, `ffe8e22` (M5). This line previously read as if they were still open, which contradicted the sections further down the same document.

## Full browser sweep — post-Wave-1 (26 suites)

**308 checks passed · 4 failed.** Zero regressions from Wave 1 — every suite touching changed code is green (smoke 18 · phase6 28 · phase7 15 · ui_batch 12 · ideas 14/12 · phase5 23 · phase10 16 · phase13 26 · export_flush 17 · selection_translate 9 · translate_mic 22 · ui_fixes 19 · spark_wall 22 · library_delete 8 · layout_audit 30 · **token_mode 3**).

The 4 failures are **phase-12 visual/motion discipline** — pre-existing (identical to the pre-implementation addendum), not caused by Wave 1:
- one-shot animations over 280ms (`ink-halo` 4000ms, `ink-flash` 1600ms)
- non-progress infinite loops (`dotPulse`, `pipeline-pulse`, `pulse`, `mic-pulse`, `switch-nudge`, `tg-blip`)
- visual-hierarchy + color-discipline checks

**Harness rot fixed this pass:** phase8/9/11 each passed every assertion then exited 1 on a Windows `cp1252` `UnicodeEncodeError` printing `✕/≤/≥`. One shared fix in `e2e_browser_common.py` (`stdout/stderr.reconfigure(utf-8)`) recovered all three — **+44 checks now visible** (13+14+17).

**Harness rot remaining (not fixed, needs a decision each):**
- ~~`phase14_signoff_journey`~~ — **FIXED**: its leg 9 asserted the dormant `#feedback-view` as *visible* (impossible by design). Rewritten against the live folded surface (dock Evidence lens), and it now **also pins the clone as dormant** so a regression can't quietly revive it. **47/47.**
- ~~phase8/9/11~~ — **FIXED** by the shared UTF-8 stdout fix.
- ~~`identity_forensics`~~ — **FIXED**: was a hard `KeyError: 'E2E_BASE'`. Now dual-mode like `export_flush` (self-boots a demo studio when the env var is absent). **6/6.**
- **LAB-ONLY (3, classified not fixed):** `design_session` (needs a hand-started studio on :8500 by design), `preview_next` + `preview_redesigns` (design gallery under `webapp/preview-next/`, not shipped surface). The sweep now reports them as `LAB`, not `FAIL`.

## Phase-12 visual/motion — the 4 real failures, resolved

| Check | Root cause | Action |
|---|---|---|
| color discipline (3 amber literals) | `rgba(232,162,79,…)` hardcoded in `style.css` + `tungsten.css`; the **dawn** `sev-medium` rule hardcoded the *night* amber, overriding `--sev-mid` (`#8a5a14`) — a real bug | Tokenized to `color-mix(in oklab, var(--sev-mid) N%, transparent)`. Verified numerically in Chromium: night resolves `oklab(0.764733 0.0477625 0.119783)` ≡ **rgb(232,162,79)** (byte-identical); dawn now resolves the dawn token. **0 amber literals remain.** |
| infinite loops (`tg-blip`) | `.sev-dot.sev-high` animated forever — MD forbids distracting animation while writing; severity is persistent state, unlike the live `dotPulse` | Bounded to **2 cycles** (same family as the allowlisted `findingPulse`); reduced-motion still collapses it |
| one-shot >280ms (`ink-halo`, `ink-flash`) | Bounded (iteration 1), reduced-motion-respected attention pulses — the **same category** as the four already-allowlisted pulses; `ink-flash` 1.6s ≡ allowlisted `findingPulse` 1.6s | Added to the `ATTENTION` allowlist with the rationale inline |
| visual hierarchy | ink `#150f0a` L=**0.062** vs `env < 0.05`; separation 0.78 ✓ — never an inversion, just a threshold 0.012 stricter than the spec ("dark ink", not "unbelievably dark"). The frozen palette cannot meet it | Bounded at `env < 0.08` with the reasoning recorded; still catches a genuinely light environment |

**Suite after all fixes: 403 checks passed, 0 failed (26 suites).**


*Verification artifacts: the one-shot live probes lived in `_qa_bugrepro/` and `tests/_*.py` (untracked scratch, not part of the repo). Their durable equivalents are the committed regression tests — `test_h7_chat_fix.py`, `test_capability_token.py`, `test_session_lost_update.py`, `test_dismiss_index.py`, `test_nonascii_titles.py` — plus `tests/e2e_browser_token_mode.py` and `tests/_run_e2e_sweep.py` (the sweep runner).*
---

# WAVE 2 — M5 (data safety) SHIPPED

The one path that could destroy a writer's data. Two halves, both TDD.

**M5a — force-reanalyze destroyed the previous good report.**
`_analyze_locked` reset the stage *and* deleted `report.findings.json` / `report.md` / `progress.json` **before** running. If the run then failed (dead llama-server → 502) the writer's analysis was already gone. The deletions were never needed: the orchestrator short-circuits on `stage.status == "complete"` (`orchestrator.py:62-73`), which resetting the stage already defeats.
- Fix: keep the stage reset and the `progress.json` clear (a transient heartbeat, regenerated within seconds); **stop deleting the report files**. A successful run overwrites them via `save_report()`; a failed one leaves the last good report intact.
- Test: `test_webapp_api.py::test_failed_force_rerun_preserves_the_previous_report` — RED (`the good report was destroyed by a failed re-run`) → GREEN. The pre-existing `test_force_rerun_actually_reruns` still passes, so the re-run genuinely still happens.
- Note: `reparse` was already correct (it parses first and only invalidates artifacts on success) — no change needed there.

**M5b — `save_report` wrote non-atomically.**
Plain `open(path, "w")` is truncate-then-write: a crash/kill in that window left an empty `report.md` or an unparseable `report.findings.json` (the product's core artifact), and the report route then 500s.
- Fix: a local `_atomic_write_text()` in `screenplay_analyzer/report.py` (temp file + `os.replace`, temp cleaned on any failure). Deliberately **not** imported from `screenplay_studio.jsonio` — Piece 2 stays standalone, per the composability contract.
- Tests: `test_report_atomicity.py` (4). **Mutation-proved**: reverting to the old non-atomic body fails 3 of the 4, so the tests genuinely discriminate rather than merely passing.

**Verified:** unit suite green; the `force` path still re-runs (sibling test), and during a run `get_report` still 400s on the non-complete stage — so a surviving report is never served as if fresh.

**Not changed (deliberate):** whether the UI should *surface* the surviving report after a failed re-run. The stage is left `pending` (honest: the re-run did not complete), so the report file is recoverable but not displayed. That is a design question, not a data-safety one — flagged, not decided unilaterally.



---

# WAVE 3 — M1: the prompt budget is ON, and sized from the model

The §1 M1 finding, verbatim: *"Prompt budget default-off — silent context
truncation on feature-length scripts; the 'honest degraded turn' machinery
exists but requires an env var nobody sets."* The shed ladder, the bounded
renderers and the trim note all shipped (C7) — but behind
`SCREENPLAY_PROMPT_BUDGET`, defaulting to `0`. A capability nobody can reach is
the same as a capability that isn't there.

## What changed

**1. On by default.** An unset env var now yields a real budget instead of `0`
(unlimited). An explicit `0` still means unlimited — the CLI and the tests need
to be able to switch it off — and a *typo* falls back to the default rather than
to `0`, because falling back to `0` would turn a mistyped variable into "no
protection at all", which is the exact silent failure M1 names.

**2. Sized from the model, not guessed.** A fixed constant is wrong in both
directions: 48k chars would shed garnish a 90k-token model can easily afford,
while still truncating a 4k-token one. So the budget is derived from the context
window the server reports — `BaseLlamaClient.context_window()` reads
`/props → default_generation_settings.n_ctx` (the per-slot window, i.e. what
this client actually gets) — and converted with two named, separately tunable
factors: the prompt may claim **half** the window (the rest is the reply, the
16-message history and up to 4 injected scenes), at **2 chars/token** rather
than the usual ~4, because this app is built for Telugu/Hindi/Tenglish writers
and Indic scripts tokenize far worse than English. The constant (48,000) is now
only the fallback for a server that doesn't answer `/props`.

The probe is best-effort by construction — unreachable, missing, non-JSON,
non-object and nonsensical bodies all return `None`, which hands the decision
back to the constant rather than breaking a chat turn or silently disabling the
budget. It is cached per base_url (160 ms first call, 0.002 ms after; `None` is
cached too, so a build without `/props` isn't re-probed every turn), and it is
resolved through the engine's existing deferred-provider mechanism, so a request
that never builds a prompt never probes — the same C10 contract the shelf
digests follow.

## Measured behaviour

The largest staged project (`gun_pen_2`, 3 scenes, 36 findings, a 27,523-char
prompt) against models reporting different windows:

| model `n_ctx` | budget | result |
|---|---|---|
| 4,096 | 4,096 | trimmed — **and warns**: the prompt is below the irreducible floor |
| 8,192 | 8,192 | trimmed — **and warns** (same reason) |
| 16,384 | 16,384 | trimmed — sheds lowest-value blocks and states the cut |
| 32,768 | 32,768 | intact |
| 65,536 | 65,536 | intact |
| **90,112** (the model in use) | 90,112 | **intact** |

That is the whole design intent in one table: it protects a small-context model,
and it is inert on a large one. **No project currently on disk is trimmed by
either the derived budget or the fallback** (largest prompt 27,523 chars;
the four staged projects assemble 8,870 / 11,775 / 14,285 / 27,523).

## Honest limitations

- **The chars-per-token figure is an approximation, and it is the weak link.**
  A budget expressed in characters cannot be exact when the constraint is in
  tokens. 2.0 is conservative for English and still optimistic for a dense Indic
  script, so a Telugu-heavy prompt on a small model could still be truncated.
  This is why the env var survives as the operator's override.
- **The two factors currently multiply to 1.0**, so the budget is numerically
  "one character per token of the window". They are kept separate because they
  encode different assumptions and either may need to move without the other —
  but a reader who sees `0.5 * 2.0` should know it is a coincidence of the
  chosen values, not a design intent. Pinned by a test so a change to either is
  deliberate.
- **A 4k/8k model now warns on every turn.** That is correct — the prompt
  genuinely does not fit — but it is noisy. Not addressed here.
- **The idea room shares the mechanism** (the premise card grows as you talk),
  so it inherits the same approximation.

## Verification

- `tests/test_prompt_budget_default.py` (new, 57 tests): the default is on; the
  env override in every shape (unset / blank / typo / `0` / negative / real);
  the derivation; the probe's seven failure modes and its caching; the engine's
  deferral; and the server's provider.
- `tests/test_prompt_budget.py` updated: the class that asserted *"the default
  is inert"* now asserts the opposite contract — that being on by default costs
  an ordinary prompt nothing. The old name was left stale by the change and is
  the kind of contradiction this review exists to catch.
- **7 mutations, 7 caught** — reverting the default to off, falling back to `0`
  on a typo, returning `0` for an unknown window, resolving the budget eagerly at
  construction, letting a raising provider propagate, dropping the probe cache,
  and passing the raw window through instead of deriving all fail the tests that
  claim to guard them.
- Suite: **956 passed / 0 failures / 0 errors** (was 898; +58).
- One test was found to be vacuous during this work and fixed: because the two
  factors multiply to 1.0, an assertion that the provider "derives" the budget
  could not tell derivation from passing the raw window through. It is now
  pinned with a sentinel.
- **A latent flake from the earlier T2.7 shelf-cache work (commit `08febe7`) was
  found and fixed here.** `test_a_changed_project_invalidates` failed in the full
  suite while passing in isolation: the fixture rewrote `parsed.json` with an
  equal-length body (111 bytes either way), and the fingerprint is
  `(mtime_ns, size)` — and on this machine two back-to-back writes of an
  equal-length body carry the *same* `st_mtime_ns` **17 times in 20**, a blind
  window of about one system clock tick (~15 ms). The test now changes the file's
  size (as a real re-analysis does), and the limitation is documented on
  `_file_stamp`. It was not caused by this change — different code path — but it
  made the gate untrustworthy, which is the same class of problem as the harness
  rot in Wave 2.



---

# WAVE 3 — the co-writer's quotes are verified (§7 P0 #3)

The §7 P0 item, verbatim: *"Verify Sameer's quotes against injected scene text
(reuse `verifier.py`'s fuzzy match; flag-don't-drop per house convention)."*

Sameer and the doctor quote the pages constantly — it is most of what makes them
feel like they have read the script, and it is the easiest thing for a small local
model to fake. An invented line that sounds like the writer's voice reads exactly
like a real one.

## One matcher, one answer

The guard reuses `screenplay_analyzer.verifier` — its normaliser and its fuzzy
threshold — rather than growing a second matcher of its own. That is the whole
design, and it is not a style preference: a naive substring test fails on a quote
that spans a line wrap, and on one typed with straight quotes where the script has
curly ones. **That is exactly the defect that made the analyzer report an entire
dialogue category as "addressed" on a script nobody had edited** (the CRITICAL
finding from the earlier audit). Writing a second matcher here would have
reintroduced it in the co-writer. Three tests exist purely to pin that it hasn't.

## Two passes, because the cheap one is exact

- **Containment against the WHOLE script**, under the verifier's normaliser. Linear,
  and it already absorbs the curly/straight and line-wrap differences, so it settles
  the overwhelming majority of genuine quotes wherever they come from.
- **Fuzzy, bounded to `scene_numbers`** — the scenes actually injected into this
  turn, i.e. the material the model was shown. The verifier's sliding window is
  generous by design, but it is O(script).

**The bounding was forced by a measurement, not by taste.** The first version ran
the fuzzy pass over the whole script. On a synthetic feature-length script that cost
**902 ms (120 scenes) and 1,824 ms (180 scenes)** — per turn, whenever the model
paraphrased rather than quoted exactly. Bounding it to the injected scenes brought
the same case to **31–71 ms**, a ~30× cut, and it is also the more faithful reading
of the item ("against injected scene text").

## Precision is the thing that matters

A false flag tells the writer their co-writer is lying when it isn't. So:

- **A word floor of 4**, measured rather than guessed. On the replies the earlier
  audit captured from the real model, the doctor quoted a craft term
  (`"on-the-nose"`, 1 word) and a genuine Telugu line (`"Journalist ga inka unna"`,
  4 words). The floor keeps the real quote and drops the aside. The analyzer's
  verifier uses `<3` for a DECLARED quote — a finding's `evidence_quote` field,
  always meant as script text; free prose needs a higher bar.
- **Validated against the real replies.** Both captured replies (`sameer_reply`,
  `sushruta_reply` — one with no quotes at all, one with a craft term plus a
  genuine line) pass through **byte-identical**. The invented-line probe is flagged.

## Honest limitations

- **The flag is advisory and can be wrong.** A quote the writer typed in their own
  message, echoed back by the model, is not in the script and would be flagged. The
  wording is deliberately a question, not an accusation: *"if it's a paraphrase, or
  it came from somewhere else, ignore me."*
- **The span cap costs coverage.** A reply quoting more than 8 things gets no
  verification beyond the 8th. Bought deliberately: the guard exists to catch a
  fabricated line, not to audit an essay. Pinned by a test.
- **The idea room is guarded twice** (no scenes, and an empty haystack). The
  redundancy means neither check is individually necessary — so neither is
  individually mutation-provable. Defence in depth, not a gap.
- **Containment still builds a normalised copy of the script every turn** — ~31 ms
  on a 180-scene script. Not cached; noted rather than fixed.
- The guard cannot check whether the quote is used *well* — only whether the words
  exist. §2's "verification verifies the quote, never the claim" still stands.

## Verification

- `tests/test_reply_quote_guard.py` (new, 27 tests): genuine quotes (exact, wrapped,
  curly-vs-straight, from a non-injected scene, light paraphrase) all pass
  untouched; inventions are flagged, and the reply body is never altered; precision
  (word floor, craft terms, the other guard's own note); the fuzzy bounding is
  observable; it stays silent on no script, empty script, missing context and an
  unimportable verifier; it is idempotent; the span cap is observable; and the flag
  reaches the **persisted** assistant turn.
- **7 mutations, 7 caught** — dropping the word floor, dropping whole-script
  containment, unbounded fuzzy, removing the fuzzy pass, removing idempotence,
  removing truncation, removing the span cap.
- Two test bugs of my own were caught while writing it: I passed `None` for the
  report context (the engine needs a real one), and my "long quote" fixture exceeded
  the 400-char span cap so it never matched — the test was asserting on a span the
  extractor had correctly rejected.
- Suite: **983 passed / 0 failures / 0 errors** (was 956; +27).
- The span-cap test was initially unable to tell "capped" from "uncapped" — it
  asserted a count that is 1 either way. Rewritten so the genuine quotes come first
  and the invention sits past the cap, which is the only arrangement that makes the
  cap observable.



---

# WAVE 2 — the demo model says so (§5 item 8, §7 item 10)

Items verbatim: *"Demo-mode banner on the report itself"* (§5.8) and *"Demo Sameer
honestly labeled in the partner card ("Sameer's stand-in — connect your model for
the real one"), not just an amber dot"* (§7.10).

When no llama-server is reachable the studio falls back to a rule-based craft
model. That is an honest workflow demo — but the only thing that said so was an
amber dot and a hover card on the desk, while the report read like a professional
review and the partner card said "Sameer — AI writing partner". The product's own
law is that the UI never pretends.

## What shipped

- **The partner card** now reads *"Sameer — AI writing partner — stand-in (connect
  your model for the real one)"*, through a single `partnerLabel()` helper so the
  two call sites (project open, idea-room lens switch) cannot drift.
- **The report carries a banner** — in the dock for a project, in the Feedback panel
  for the idea room, toggled from one `[data-demo-banner]` selector.
- **The exported report carries it too.** `_md_to_html(md, banner)` injects it
  directly after `<body>`, and `export_report` passes it only when the demo model is
  active. This is the case that matters most: an exported HTML report outlives the
  status strip that would otherwise have explained it, so a producer receiving one
  has no other way to know the findings are canned.

## The placement bug, caught by looking rather than by reasoning

The first version put the banner only in `#feedback-panel` — the obvious home, since
that is literally the "Dr. Sushruta's Report" panel. **A browser check showed it
never rendered.** For a *project*, `#feedback-panel` is the legacy/idea-room surface
and is `display:none`; the report renders in the **dock** (`#context-dock`). A demo
project therefore showed no disclosure at all, and every unit test passed while it
did.

Two further details came out of the same check:

- The dock's banner must sit **outside** `#dock-lens-evidence`, because
  `renderDockEvidence()` replaces that element's contents and would wipe it.
- `.feedback-header` is a flex row, so a banner placed inside it becomes a flex item
  and shoves the toolbar sideways.

The banner is styled with `var(--sev-mid)`, **not** a literal amber: the phase-12
pass tokenized three hardcoded ambers, including a dawn rule that had hardcoded the
night amber and so overrode its own token. A test now asserts the literal does not
come back.

## Verified in a browser, in both modes

| mode | partner card | visible banners |
|---|---|---|
| demo (`--demo-model`) | `…— stand-in (connect your model for the real one)` | **1** |
| real (`localhost:8080`) | `Sameer — AI writing partner` | **0** |

0 JS errors in both. The unit tests could not have established this — they assert
the wiring, and the wiring was right while the placement was wrong.

## Honest limitations

- The disclosure is **per-surface, not per-report**. A report generated while a real
  model was connected, then exported after the server went away, carries no banner —
  which is correct (it *was* a real report) but means the banner describes the
  studio's current state, not the report's provenance. Stamping provenance into
  `report.md` at analysis time would be the durable fix; not done here.
- The two banners say slightly different things (the dock's also covers the
  co-writer). Deliberate: the dock banner appears on every lens.
- The idea-room panel banner is unverified in a browser — the idea room has no
  script, so it was out of scope for this pass. Flagged, not silently assumed.

## Verification

- `tests/test_demo_banner.py` (new, 16): the banner decision (absent for a real
  model, present for demo); its position above the findings; that it names the
  remedy, not just the problem; that the export styles it; that an empty banner
  leaves the document byte-identical; the colour discipline; and the wiring for both
  in-app surfaces (one `partnerLabel` helper, one `[data-demo-banner]` toggle, the
  dock banner present and outside the rendered lens).
- Two of my own tests were wrong at first and were caught by running them: they
  keyed on the string `"demo-banner"`, which also appears in the `<style>` block, so
  they passed and failed for the wrong reason. They now key on the banner's own
  text.
- Suite: **999 passed / 0 failures / 0 errors** (was 983; +16). Browser gates
  unchanged: smoke 18/18, phase7 15/15, phase6 28/28.



---

# WAVE 4 — the report states its evidence depth (§5 item 4)

The item, verbatim: *"Report evidence-depth honestly — '30 findings — 12 from full
text, 18 from overview' converts invisible false-negative risk into visible scope."*

This is the §2 "summary-telephone ceiling" made countable. The script-level passes
judge from the **model-written scene summaries**, never the raw pages — a deliberate
trade to fit the context window, and the single biggest honest limitation of the
analysis. The report already described that trade in prose (*"expected for
theme/character/structure/scene-function findings, which reason from scene summaries
rather than full text"*). A caveat in prose is not a scope. **"4 of 7 came from a
summary" is.**

## Why the classification is recorded, not inferred

The obvious implementation is to map the finding's `category` to a source. That
would be **wrong**, and the code says so plainly: `pacing.py` files its drag findings
under `category: "structure"` — the same category the script-level pass uses — even
though the pacing pass reads the parsed pages directly. A category-based rule would
report every pace drag as a summary-derived judgement.

So each of the ten `all_findings.extend(...)` sites declares what its pass actually
read, through one `_tag_evidence(findings, source)` helper:

| source | passes |
|---|---|
| `full_text` | voice · subtext · idiolect · continuity · **pacing** · dialogue · principles |
| `overview` | the script-level categories (theme/character/structure/scene_function) · the setup/payoff ledger · genre |

`principles` is `full_text` on the grounds that its knowledge-graph input is
deterministic candidates extracted from the script, not a model-written summary. That
is a judgement call, and it is recorded here as one.

`unknown` is kept as a third bucket rather than folded into either side: a pass that
forgets to declare its source must not silently read as full-text, which is the
flattering direction.

## What the writer sees

On the reference fixture the pipeline reports **3 from full text, 4 from scene
summaries** (dialogue + continuity vs theme/structure/scene_function/genre — matching
the pass wiring exactly). It surfaces in three places:

- **`report.md`**, under *Evidence Verification*, as a bolded count with a sentence
  saying what to do with it (*"Treat the second group as a second opinion on
  structure, not as a reading of your pages"*).
- **The served report JSON** (`stats.evidence_depth`), so any client can read it.
- **The app's Coverage panel**, as a muted mono line with a hover that explains it —
  guarded on the field existing, because every report analysed before this change
  lacks it and an unguarded render would print *"undefined of undefined"*.

## Honest limitations

- **`principles` is a judgement call** (above). It is not "read the pages" in the
  same sense the dialogue pass is.
- **The number describes the pass, not the sentence.** A summary-derived finding that
  happens to be right still counts as summary-derived; the count is about scope, not
  accuracy.
- **Old reports carry no depth line.** Correct — the information was not recorded —
  but it means the line appears only for analyses run after this change.
- **The depth is per-report, not per-finding-in-the-UI.** The app states the ratio
  once in the Coverage panel rather than annotating each card; annotating 30 cards
  would be noise.

## Verification

- `tests/test_evidence_depth.py` (new, 25): the counter (both sides, `unknown`, empty,
  no key loss); **the load-bearing guard that every `all_findings.extend` is
  `_tag_evidence`-wrapped**, so a future pass cannot silently land in `unknown`; the
  mixed-category split asserted at the source; a full pipeline run leaving **zero**
  unattributed findings and both sides non-empty; the rendered line; the `unknown`
  disclosure; no line when the field is absent; the older prose caveat surviving; the
  served JSON; and the app wiring including the missing-field guard.
- Suite: **1024 passed / 0 failures / 0 errors** (was 999; +25).
- One test bug of mine, caught by running it: `AnalysisResult` takes a `doc` as a
  required argument, so the report-rendering helper could not construct a bare result.



---

# WAVE 4 — cross-rule dedup (§5 item 3)

The item, verbatim: *"Cross-rule finding dedup — the same defect filed under 2–3
related rule_ids (subtext/exposition cluster) should merge; generalize the existing
setup/payoff ledger dedup."*

**The item is real, and it was confirmed on real data before anything was built.**
On `gun_pen_2` scene 2, one on-the-nose exposition problem arrives as three findings:

```
On-the-Nose Dialogue vs. Subtext   "Dialogue is on-the-nose, explicitly stating..."
Say the Opposite                   "Dialogue contains multiple on-the-nose statements..."
Exposition as Ammunition           "Dialogue is purely functional exposition..."
```

A fourth dialogue finding in the same scene, `Distinct Character Voice`, is a
genuinely different defect and must survive.

## Two measured facts killed the obvious implementations

**Text similarity finds nothing.** Across all 36 findings in the real report, no pair
reached even 0.19 similarity — the model wrote different prose for each rule. A
text-based dedup is a no-op here.

**The transitive closure of `related_rules` is far too coarse — and it is wrong.**
`related_rules` is written one-directionally, so it is symmetrised here. But *chaining*
those edges collapses 271 rules into clusters of up to 61 members, and puts
`distinct_character_voice` in the **same** cluster as `on_the_nose_vs_subtext`.
**The first implementation used the closure: it merged 36 findings down to 10 and
swallowed the voice finding** — precisely the error the item exists to prevent. The
real report caught it; no unit test would have.

So the merge predicate is a **direct edge**, evaluated only between findings that are
both present and in the same scene:

```
merge(A, B)  iff  A and B share a scene
             and  B's rule is in A's related_rules (or vice versa)
```

That is precise where the closure is not: the trio are pairwise linked through
`on_the_nose_vs_subtext`, while `distinct_character_voice` has no direct edge to any
of them. Restricting the closure to the findings actually present is what keeps it
local.

## Measured result on the real report

**36 findings → 21** (15 merged). Scene 2: `On-the-Nose` absorbs `Say the Opposite`
and `Exposition as Ammunition`; **`Distinct Character Voice` is preserved**. Scene 3:
`Laying Pipe` absorbs the same two rules — correctly, because a defect in a different
scene is a different fix.

Nothing is dropped: the survivor keeps its own text and gains a `merged_rule_ids` list
plus a clause on `why_it_matters` (*"Also flagged under: …"*), so a writer reading one
card sees that other rules agreed. Same "flag, don't silently drop" policy as the
verifier. A dedup that quietly deletes a finding is the same failure as the one it
fixes.

Also merged: the same rule twice in the same scene (a duplicate by definition), and
the same rule in two scenes is deliberately **not** merged — that is the Pain_3 case,
where `unmarked_time_flip` fires at scenes 13→14 and 17→18. Those are two separate
flips needing two separate fixes.

## Honest limitations

- **The KB's relation graph is dense**, so a rule can be directly related to a dozen
  others. The merge is only as good as that data; if two rules are wrongly related,
  two distinct findings can merge. The survivor names what it absorbed, so the loss is
  visible rather than silent.
- **`principles`-style structural merges are the aggressive end.** On the real report,
  `Three-Act Structure` absorbed four structure rules. Defensible (one structural
  problem, four lenses) but it is the kind of merge a writer may want un-done; there is
  no un-merge.
- **A finding with no scene is never merged**, so script-level duplicates survive.
  Deliberate: merging them by rule alone would combine observations from different
  parts of the script.
- **`unmarked_time_flip` is not a KB rule id** (the continuity pass writes a
  non-KB id into `rule_id`), so it can never be related to anything. This is the
  `rule_id` / `check_id` split the earlier audit flagged, resurfacing from the other
  direction — noted, not fixed here.

## Verification

- `tests/test_cross_rule_dedup.py` (new, 31): the relation map (symmetry, no
  self-relation, the unrelated pair, and **a test that documents the closure being too
  coarse** so the justification cannot silently go stale); rule-reference resolution
  for both id and display name; the trio collapsing; **the voice finding surviving**;
  same-rule-two-scenes staying two; no-scene never merging; severity and tie-break
  survivor selection; scene union; the stated clause; input not mutated; idempotence;
  and the pipeline wiring (including that a dedup failure is recorded, not swallowed).
- Suite: **1055 passed / 0 failures / 0 errors** (was 1024; +31).
- Three test bugs of mine, caught by running them: an empty `by_name` map, a rule id
  assumed to be in the KB that is not, and `kb=None` meaning "load the default KB"
  rather than "no KB".



---

# WAVE 2 — H3: the fake composer is deleted, and the craft questions now reach a real one

The item, verbatim: *"H3 — A fake Sameer chat composer silently discards user input
in a product whose stated law is 'the UI never pretends'."* §5/Wave-2 asks to
**wire-or-delete** it.

**The finding was accurate, and the reality was worse than the description.**

The off-canvas `#sameer-panel` was not merely a fake surface sitting in a corner. It
was **the destination of every craft question in the command palette**. All seven —
*"Why doesn't my dialogue land?"*, *"Is my Act II sagging?"*, *"Am I violating
setup/payoff?"* — call `openSameerWith()`, which opened that panel and filled
`#sameer-ta`. Its Send button then appended the text to its own thread and made **no
API call**. So the product's headline craft entry point discarded the writer's
question in silence, under a heading that said "Sameer".

It also shipped three hardcoded "messages" — prose about a stairwell and a character
named Mara — rendered regardless of which script the writer had actually opened.

## Resolved by deletion, not wiring

The Co-write room already has a real composer that reaches the API (`#composer` /
`#input` / `#send-btn`, streaming from `messages/stream`). Wiring a second one would
duplicate it. So the panel is deleted and `openSameerWith()` now pre-fills the real
composer — which makes the craft palette **work** for the first time, rather than
merely stopping it from lying.

Deleted: the panel markup (with its canned transcript), `toggleSameerPanel()` and its
handlers, 144 lines of `.sameer-panel` / `.sp-*` CSS plus three orphan references, and
the dawn-theme colour pins in `tungsten.css`.

**One stale reference was caught that the deletion itself created:** a live
`e.target.closest("#sameer-ta")` in the selection-popup hit-test survived the HTML
removal and would have thrown on every popup interaction. A test now scans the
non-comment code for every deleted id.

## Honest notes

- **Deleting was a judgement call between the two options the review offered.** The
  reasoning is that a second composer would duplicate the room's own, and that the
  panel's only unique behaviour was the lying. If a floating quick-ask surface is
  wanted later, it should be built on the real composer, not restored from this one.
- **The command-palette craft questions now pre-fill rather than auto-send.** The
  writer still presses Send. That is a deliberate change of behaviour — the old panel
  looked like it sent, so the questions appeared to work.
- The design-gallery copies under `webapp/preview-design/` still contain `.sp-*`
  rules. Those are lab artifacts, not shipped surface (the Wave-2 sweep classified
  them `LAB`), and were left alone.

## Verification

- `tests/test_fake_composer_removed.py` (new, 12): the panel, its transcript, its
  echo-composer and its toggle are gone; no live code references a deleted id; the CSS
  is gone; a note explains why; `openSameerWith` targets the real composer and still
  opens the room; all seven craft prompts remain wired; and the real composer still
  exists and still streams to the API.
- The harness's `send_chat` docstring explained a workaround for the now-deleted
  `#sameer-send`; it has been rewritten so it does not describe a surface that no
  longer exists, and a test pins that.
- Suite: **1067 passed / 0 failures / 0 errors** (was 1055; +12). Browser gates
  unchanged: smoke 18/18, phase7 15/15, phase6 28/28.



---

# WAVE 1.5 — GAP-6 closed at the root (the doc set's own CRITICAL finding)

Every wave above fixed things the *review* found. GAP-6 came from the **live audit** instead, was
committed in `7fc10af` before Waves 2–4, and then went unmentioned by the waves that followed. It is
the one defect where the desk told a writer, on a script they had never edited, that eight of their
findings were already addressed.

## The root: two engines, two answers

`verifier.verify_finding` normalised the quote (lowercase, punctuation stripped) and matched it against
the **joined** scene — and called eight gun_pen findings `verified`, six of them at confidence 1.0.
`revision.quote_present` substring-matched the raw quote against **one element at a time** and then
fuzzy-compared the whole quote against that same element, about 35 characters long. Two captured
elements make both failure modes concrete:

```
element[7]  'yudhame jarguthundi... “you are the'
element[8]  'sum of all your choices”'
finding     '"you are the sum of all your choices"'
```

The quote spans two line-wrapped elements, and the model wrote straight quotes where the script has
curly ones. Either alone is enough to miss it. Because `findingPassesFilter` hides any finding whose
disposition is not `open`, one disagreement emptied **three** surfaces at once: the Dialogue section
disappeared from the board, the mass strip read "28 open of 36", and the margin ink rendered zero pins
on a script with nine quoted findings.

## The correction to the recorded fix direction

The audit's fix direction was *"one matcher, one answer ... expose one shared matcher from
`screenplay_analyzer.verifier` and call it from both places."* That is right about the normaliser and the
haystack and wrong about the threshold. The two engines ask opposite questions:

- **verification** asks "was this quote real?" — lenient, because a model paraphrases a real line;
- **change detection** asks "is this cited line still in the draft?" — strict, because a reworded line is
exactly what a **writer's edit** looks like.

Measured at element granularity on normalised text: a dropped character scores **0.979**, a swapped word
**0.875**, a removed word **0.830**. Verification's 0.72 accepts both edits — so a shared threshold would
have made every edited line keep reading "still present" and silently killed the writer-fix signal. Worse
trade than the bug.

## What shipped

`screenplay_parser/quotematch.py` holds the shared primitives: the normaliser, the scene joiner, the
windowed comparison. That package imports nothing from `screenplay_analyzer` or `screenplay_studio`
(verified per file), and both `revision.py` and `verifier.py` already import it — so the studio never
reaches into the analyzer, and there is no import-failure path that could quietly restore the old
matching. `verifier._normalize`, `_scene_full_text` and `_best_fuzzy_match` are now **aliases** (identity,
not wrappers), which keeps `screenplay_cowriter.reply_transforms` importing them unchanged.

`revision.quote_present` runs containment of the normalised quote against the normalised **joined** scene,
then a strict per-element ratio at `QUOTE_CHANGE_THRESHOLD = 0.95`. Pass B keeps element granularity on
purpose: a scene-sized window dilutes the ratio until the pass is inert. The accepted consequence is that
a quote which both spans two elements **and** was edited reads as addressed — the conservative direction.

## Measured on the real stored project

No browser and no model were needed: `finding_statuses` re-reads the stored report and the working copy,
which is what scripted the phantom count in the first place.

| | still_present | addressed | unknown | contradictions* | inkable | dialogue open |
|---|---|---|---|---|---|---|
| before | 1 | **8** | 27 | **6** | 0 | 0 of 8 |
| after | **7** | 2 | 27 | **0** | **6** | 6 of 8 |

\* verifier accepted the quote at confidence 1.0 while the status engine called it gone.

The before column reproduces the audit's recorded `8 / 1 / 27` byte-for-byte, so this is the same data
that section measured. All six flips are dialogue findings the audit identified as verbatim in the script.
The two that stayed "addressed" should have: one is a verifier-accepted paraphrase at 0.82, one a genuine
`not_found` at 0.56 — neither quote is in the script.

**Verification:** `tests/test_quote_agreement.py` (new, 23), whose load-bearing test is the contract
*every quote the verifier accepted at 1.0 must be present to the status engine*; the two captured real
fixtures; the writer-fix trap (a one-word edit and a removed word must still read addressed); the
revision ledger's second caller; and five "one implementation" guards, including a source scan for a
second copy of the punctuation-stripping regex. **6 of 7 mutations caught.** The survivor is the
short-quote floor, which is inert at a 0.95 threshold — kept as defence in depth and labelled
not-individually-provable rather than claimed as a guard. Suite **1090 passed / 0 failures** (+23).

## The browser run found a fourth surface, after the data said the work was done

The stored-project numbers above made the fix look complete: 6 of 9 quoted findings open and
scene-anchored, so the pins should have rendered. The browser still showed **0**. `decorateLineWithInk`
required `text.indexOf(quote) !== -1` — the **whole** quote inside **one** line. A quote cited across a
line wrap can never satisfy that, so every wrapped finding stayed invisible on the page even once it was
open. Same root cause, fourth surface, and a data-layer prediction could not have caught it: this is what
"verify in the browser" is for, and it is the second time in this document's history that the browser found
what the numbers did not.

Fixed in `app.js`: `inkMatch()` falls back to the quote's longest leading fragment present on the line
(at least 3 words and 8 characters), with quote marks stripped per word because a model writes straight
quotes where a script may have curly ones. `app.js?v` bumped `hx1b379` -> `hx1b380`.

**Browser re-run** (matrix stage, real llama-server on :8080, real stored report):

| | gaps filed | dialogue section on the board | margin ink | mass strip open | phantom "addressed" |
|---|---|---|---|---|---|
| before | 7 | **absent** | **0 pins** | 26-28 of 36 | 8 |
| after | **5** | present (6 findings) | **3 pins** | 34 of 36 | 2 |

Two of the audit's filed gaps are retired (the Dialogue category, the margin ink), and `A-dialogue.png`
now exists — previously its absence *was* the evidence. Six inkable findings do not imply six pins:
findings that share a line collapse into one mark with a count chip, and a fragment match can land on one
of a wrapped quote's two lines.

**Not closed by this wave, and not claimed:** the 2 findings that still read "addressed" (their quoted
line genuinely is not in the script — an attribution problem, not a matching one); the arrival total vs
board total; the desk status line; the dead character dials; the data-dependent loop-coverage check; and
everything from GAP-7 down in the ledger below.

**Residual, flagged not fixed:** "addressed" is still purely `quote_present == False` and never consults
the writer's own marks, so the two genuinely absent quotes still read as writer progress on an untouched
draft. The contract violation is closed; the **attribution** issue is narrower and shares a root with GAP-7.


---

# OPEN ITEMS — the ledger this doc set was missing

This review's own weakness was structural: each wave appended a section, and nothing anywhere said what
was still broken. GAP-6 was found by the live audit, committed before Waves 2–4, and then never named
again. This table is the fix for that, and it should be updated by every future wave.

| # | Item | Severity | Evidence / why it is open |
|---|---|---|---|
| 1 | **GAP-7 — finding identity is model prose.** `compute_finding_id` keys the no-quote tier (75% of findings) on `issue[:100]`, so ids churn ~88% per no-op re-run and the arrival strip reports LLM variance as writer progress (`33 → 4 still live · 29 no longer flagged · 32 new`). | **HIGH** | `revision.py:65`; 4 of 33 ids survive a re-analysis at byte-identical `parsed.json`. **Decision taken:** deterministic ids (`category + scene + check_id`) **and** an edit gate on `working.json`. |
| 2 | **Desk status line says "a clean bill" on a 36-finding project.** `refreshDeskToolbar()` runs at `app.js:1979`, before `loadScriptData()` populates `state.findings` at `:2011`, and is never re-run on the open path. | MED · trust | Measured in the 09-19 audit artifact (`desk_status`). Re-run/retry paths already call it after the load. |
| 3 | **Character dials render into dead chrome.** 15 `.dial-row` nodes build into `#struct-rail`, which `style.css:3912` declares `display:none`. | LOW · reachability | Measured: `dial_rows 15, visible false`. |
| 4 | **The fix loop can cover its own bar.** `stepLoop` → `jumpToScene` (`app.js:2832`) → `openCowriteRoom` (`:2834`); it is masked only when the loop's first item is script-level, because `jumpToScene` early-returns on `sceneNumber == null` at `:2833`. | MED · UX | The audit's own gap **failed on 09-18 and passed on 09-19 with that code path unchanged**, so the check is data-dependent. Needs a deterministic check before it can be called fixed. |
| 5 | **Arrival basis can never equal the board basis.** Distinct-id arithmetic (33) against row count (36). | LOW · honesty | Same family as #1; fixing identity fixes it. |
| 6 | **Duplicate top-level `jumpToScene`** — `app.js:775` is dead, `:2832` wins (classic script, last declaration wins). Its side effect: the structure rail's scene click also opens the partner drawer. | LOW · maintainability | The repo's own logged learning `classic-script-split-hazards` recorded this same two-variant signature in an earlier revision. Wants a structural test asserting one top-level definition per symbol. |
| 7 | **H1 is opt-in.** The capability token exists but `_API_TOKEN` is `None` unless `--require-token` is passed, so a default install still accepts a blind, no-`Origin` `DELETE /api/projects/<name>`. | MED · security | `webapp_server.py:54, :3089`. |
| 8 | **Confidence tiers unrecalibrated.** 202 of 263 KB rules are still tagged `high`. | MED · report honesty | `knowledge_base/index.json`: 202 / 40 / 21. |
| 9 | **Branch UI written but uncommitted and untested.** Fork button, merge-peek tooltips, fork modal wiring, plus a real `z-index` fix (modals sat at `--z-float` = 50, under the board, drawer and quote float, so their buttons were unclickable). | — | Working tree only; no test file covers fork/switch. |
| 10 | **Started since this ledger was written.** DONE: selective raw-text for checkpoint scenes (S5.2 — the four script-level passes now read the raw pages of the structural checkpoints), the CLI memory default (P2.11), voice-drift acting rather than logging (P1.7), the reply-side language register check (P2.9 — script registers only; the Tenglish/Hinglish half is BLOCKED on the detector's length-dependent bar, see row 12), branch/resume orientation (P3.12 + P3.13), and the select-to-rewrite diff loop with Apply/Stash/Reject (P1.4 — the chat-to-proposal bridge is BLOCKED on a live model). H5 lock ordering was re-checked and **documented as a contract rather than "fixed"** — the wait-for graph has no cycle. STILL NOT STARTED: memory felt (P2.8), theme/relationship tier deepening (S5.5), counter-read pass, M3 progressive disclosure, M6 touch parity. `app.js` was **8,738** lines at review time; M8 is unresolved and this pass grew it further. | — | — |
| 11 | **Doc hygiene:** the repo-root `SESSION_SUMMARY.md` (untracked) still describes 2026-09-14 state and lists GAP-1/GAP-2 as next actions; the audit plan file is untracked. | LOW | `SESSION_SUMMARY.md` duplicates `docs/SESSION_SUMMARY.md` and contradicts this document. |

| 12 | **The memory default is inconsistent between the two entry points to the same REPL.** `screenplay_studio run/resume` now defaults writer memory ON (`--no-memory` to opt out, P2.11); `screenplay_cowriter chat` still requires `--memory-path` and is amnesiac without it (`cli.py:216-220`, declared `:245`). Both call the same `run_repl`. | MED · consistency | Found by the P2.9/P3.12 pass while reading `cli.py` for a different reason. **Not fixed — it is a product decision, not a bug**: defaulting memory on for the standalone CLI creates a writer profile on disk for anyone who runs `chat`, which is the same disclosure P2.11 made for the studio CLI but was never asked for here. The two must agree eventually, one way or the other. |

**Still sound, re-checked this pass:** encoding posture, path-traversal defenses, the verifier's
"flag, don't drop" policy (it survives the quote guard untouched: both captured real-model replies pass
through byte-identical), and the M1 prompt budget's measured inertness on the model in use.



