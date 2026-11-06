# Per-entry grade table — every numbered finding, graded individually

This file exists because the self-critique's grading lived in prose and in two aggregate tables that
did not sum to the register. That made "how strong is gap 47?" a judgement call instead of a lookup.
Here every entry gets one grade, on the scheme already published in
`SELF_CRITIQUE_OF_GAP_REGISTER.md` §1.

**The scheme, restated so this file stands alone:**

| Grade | Meaning |
|---|---|
| **A** | Reproduced through the real interface (real route, real CLI, real parser/exporter, real function on synthetic input). |
| **B** | Real mechanism, but the reproduction needed a constructed condition: concurrency, fault injection, a fake model or mock server, a fake clock, or a pre-damaged store. |
| **C** | Source inference or contract asymmetry — read in code, not driven. |
| **D** | Documentation drift, housekeeping, opinion, or an unvalidated-quality caveat. |
| **W** | Withdrawn after re-testing. |
| **–** | Tested and found **not to be a gap** (a reproduced negative). Kept visible so the negatives travel with the positives. |

**A second column was added on 2026-11-04 at the user's request: *genuine?*** The grade answers "how sure am I
that I saw this?"; the authenticity column answers "is this a gap at all?" — a question four entries fail while
being perfectly well evidenced. `G` = genuine gap, `K` = known trade-off, `P` = product direction, `W` =
withdrawn, `–` = tested and not a defect. Only `G` entries remain in `GAP_REGISTER_AND_EXECUTION_PLAN.md`;
everything else is preserved with its argument in `ARCHIVE_NOT_GAPS.md`.

**Rules I applied while filling this in, so the grades are auditable rather than asserted:**

1. A synthetic *document* (script, PDF, project directory) does not lower the grade — the interface was
   still real. A synthetic *failure* (injected exception, held lock, fake clock, stub client) does: that
   is **B**.
2. If the finding's content came from the demo craft model, the mechanism can be A but the claim about
   feedback quality is capped at B, and the row says so.
3. Anything I never drove at all, only read, is C — no exceptions, no "source-confirmed" euphemism.
4. Where this table disagrees with the aggregate rows in §11 of the critique, **this table wins**; §11
   has been regenerated from it and now says so in its own header.

---

## Entries 1–15 (consolidated table in the register)

| # | Grade | Driven through | Note | Genuine? |
|---|---|---|---|---|
| 1 | **A** | Real Flask routes: edit, upload, reactivate | **FIXED 2026-11-04** — the edit cycle is snapshotted per draft and restored on switch; 2 of 3 tests fail without it. Edits, edit log and working copy destroyed by an action the UI calls non-destructive. | **G** |
| 2 | **B** | Real orchestrator with a stubbed analyzer | Mechanism is source-visible; publication half is proven at A under 65. **FIXED 2026-11-04** — analysis now reads the working draft, and the report carries the digest of the script it read. Grade stays B: the reading half was proven with a stubbed analyzer. | **G** |
| 3 | **B** | Injected total failure | Contradicts the orchestrator's own comment that a failed run preserves the prior report — that is why it keeps high severity despite B. **FIXED 2026-11-04** — staged generations, one pointer; the last good reading survives a failed run. Grade stays B (injected total failure). | **G** |
| 4 | **A** | Two-client HTTP test | A finding from draft A landed in the completed report for draft B. **FIXED 2026-11-04** — publication re-reads the live draft and refuses if the digest moved. | **G** |
| 5 | **A** | Real `/analyze/cancel` + real `retry-failed`, and a real re-run stopped mid-flight | The *UI* half was C and is now closed too. **FIXED 2026-11-05.** Three defects, all reproduced before the fix. **(1) Publication:** the last `_cp()` stood before step 6b, leaving 169 lines — steps 7-8i and the `return` — unchecked. Measured on the real route with the model server live: Stop answered **200 `cancel_requested`**, then the run returned normally, the stage went **`complete`** and `report.md` was **rewritten** over the writer's previous reading. Two checks added: before the observation pass (the run's last model-backed pass, so a stop is no longer followed by calls the writer cancelled) and immediately before `emit("done","complete")` — the one that makes publication impossible past a stop. **(2) The answer:** `runAnalysis()` and `retryFailedCategories()` never read the response body, so a stopped run announced "Analysis complete" / "the report has been merged and updated"; a retry also ran with no Stop control at all. Both now go through one terminal handler and one wording helper. **(3) The retry** (gap 66) was already fixed and is now pinned here. Reverts measured per half: **3 fail** with the publication check removed, **1** with the pre-observation check, **5** with both. Critique S50. | **G** |
| 6 | **B** | Injected edit-log write failure | Divergence between working text and history. | **G** |
| 7 | **B** | Two OS processes on one project | Constructed interleaving; no frequency claimed. | **G** |
| 8 | **B** | Controlled backup with a skipped file and a synthetic key marker | Two distinct claims in one entry: incompleteness (A-shaped) and credential retention (B-shaped). Graded at the weaker half. | **G** |
| 9 | **A**, consequence **C** | Both attached PDFs through the real parser | The *coverage facts* are measured. "This degrades feedback quality" is inference and is graded C inside the entry. |
| 10 | **B** | Controlled `analyze()` plus post-gate enrichment | A fabricated contradictory observation survived with a verified quote. | **G** |
| 11 | **B** | Synthetic note through the real filter | Plus a rule-inventory computation that is A-shaped; graded at the weaker half. | **G** |
| 12 | **B** | Two controlled findings forced to share category/quote/scene | ID collision and verdict leakage. | **G** |
| 13 | **C** | Read the accuracy formula and the serve path | Labelling critique; no run produces a wrong number I can point at. | **G** |
| 14 | **C** | Classifier calls on documented phrasings | Deterministic, but the *behaviour* claim ("interrogates a writer who stated intent") needs a real model; overlap with 98. | **G** |
| 15 | **D** | — | A caveat about unvalidated quality, not a defect. Belongs in the caveat block, not the count. | **G** |

## Entries 16–47

| # | Grade | Driven through | Note | Genuine? |
|---|---|---|---|---|
| 16 | **A** | Isolated temp dir, real `ProjectManifest`, real `process_pending()`, real filesystem | Release-blocker framing was mine; the reproduction is real. **FIXED 2026-11-05.** Three defects measured before the fix, all on disk: **(A)** `shutil.move` reused the filename, so two different scripts dropped as `draft.fountain` left **one** file — the first replaced, with no message; **(B)** the move was gated on `ok or error`, so an ENOSPC during `ProjectManifest.create` **cleared the inbox and filed the script under `done/`** while no project copy existed anywhere; **(C)** the same gate was reached through `manifest.save()`. Now: filings are collision-safe (`draft_2.fountain`) via an `O_CREAT` + `O_EXCL` reservation, failures go to `failed/` beside a `<name>.error.txt` explaining why and how to retry, each drop is claimed by an atomic rename into `.processing/` before work starts, and the result record reports where the source actually went (`filed`). Reverts measured per defect: **2 fail** (no-clobber), **3 fail** (the done/ gate), **2 fail** (the claim). 11 tests. One of my own bugs was caught by the pre-existing suite: I checked `ok` before `move_done`, so `move_done=False` still filed into `done/`. Critique S51. | **G** |
| 17 | **A** | Source-read + an extracted real handler (node), a pure-function harness; the Chromium legs still not run here | Browser suite behaviour; not re-run this session (playwright absent), so the grade rests on the suite's own recorded failure. Flagged. **PARTLY FIXED 2026-11-05.** Two of the three legs produced real work. **(a) XSS leg — fixed.** The register's guess was right and is now proven: `renderDashboard` puts the payload in a *quoted title attribute* (`title="Open &quot;<img ...>&quot; on the desk"`), which `outerHTML` serializes literally, so `"<img" not in html` reported a tag while `handlers == 0 and exec == 0` reported an inert DOM. The check now strips quoted attribute values first (`has_raw_tag`), so it still catches a genuine tag and can no longer be fooled by an escaped one; 13 tests, 4 fail if it is reverted to the substring. **(b) unload leg — a real defect, fixed.** The pagehide flush opened with `if (!ideaSaveTimer) return;`, and `saveIdeaContent()` clears that timer BEFORE sending its POST — so for the whole duration of an in-flight save the flush sent nothing, and the in-flight fetch is exactly the one a pagehide aborts. The decision now comes from the text, not the timer; the real handler is extracted from `app.js` and driven in node (10 tests, 1 fails with the old guard). **(c) live-region repeat leg — unchanged and still unverified:** whether assistive technology re-announces an identical error is not observable from the DOM, which is the suite's own stated position. **Still open:** the Chromium legs were NOT run — no browser binary is reachable here (the Playwright CDN is blocked), so this entry is not a browser pass and does not claim to be. Critique S52. | **G** |
| 18 | **B** | Concurrent session saves in isolation | Both concurrency and forced-failure variants used. **FIXED 2026-11-04** — (a) message identity + (b) durable deletion tombstone with stale-snapshot refusal + (e) fail-closed on a failed `.bak`; (c)/(d) covered only indirectly by the existing branch tombstone and `OSError` branch (critique §35). | **G** |
| 19 | **A** | Real `add_to_stash` with 4,004 characters, and the real route | Saved 4,000, dropped the tail silently. **FIXED 2026-11-05.** Reproduced exactly (4,004 in, 4,000 saved, tail gone, no error) and found to be worse than filed: the route answered **201**, so the UI said "Stashed ✓" over a passage whose tail had just been deleted, and the success record had no field that could even express it. The bound stays (4,000 chars, now `MAX_TEXT_CHARS` rather than a slice in a dict literal) but is no longer silent: text over it is **refused** with a sentence naming both lengths and stating nothing was saved or cut, and the bound is served on `GET /api/projects/<n>/stash` so the selection float refuses before the round trip. Legacy entries the old code cut are **reported, never rewritten** — `entry_truncated()` derives the evidence from the file (`len == bound`) and says the original length is unknown rather than inventing a dropped count. Reverts: **5 fail** with the silent slice restored, **1** with the served bound removed. 11 tests. Critique S53. | **G** |
| 20 | **B** | Mocked current scene numbers | Staleness is real; the mock is what makes it visible. | **G** |
| 21 | **A** | Real exporter, then re-parse | `AJAY/VENU` becomes three AJAY lines. Round-trip use reassigns dialogue. **FIXED 2026-11-04** — a CHARACTER cue now always starts a new block, so the next speaker is no longer read as the previous one's dialogue; 6 of 8 new tests fail without it, and the repo fixture goes 3-of-36 churn to 0. The register's larger per-script counts are not re-derivable here (no PDF-derived scripts in the repo) — critique §36. | **G** |
| 22 | **A** | Synthetic FDX through the real parser/exporter | Fidelity limits are also documented in the export docstring — known trade-off, still tested. | **K** |
| 23 | **A** | Real `quotematch.normalize_text` | `కల`/`కాల` collide; a different word verifies as an exact quote. **FIXED 2026-11-04** — the normaliser keeps combining marks and NFC-folds, and the verifier no longer certifies a near-identical-but-different quote. 8 tests fail on the old normaliser, 1 on the old threshold. **Residual:** `revision.quote_present` still treats a one-mark edit as unchanged — separate documented trade-off, pinned in a `_RESIDUAL` test, critique §37. | **G** |
| 24 | **A** | Synthetic Fountain with a Telugu cue, plus Hindi/Tamil/English controls | Native-script speaker cue missed — the reproduction is real and was worse than filed. **FIXED 2026-11-05.** Three independent causes, measured one at a time. **(1)** `_script_share` counted only Devanagari and Tamil, so a Telugu cue scored **0** script chars and fell through to the all-caps test, which no caseless line can pass; the heading tokens were in no table either, so the script parsed to **zero scenes** — every line went to front matter. The script set is now the ten caseless Brahmic scripts, and the heading pattern is *derived from the token tables* instead of being one hand-written regex per language (that duplication is what let `లోపల.` be resolvable by `parse_scene_heading` and unknown to `looks_like_scene_heading`). **(2)** With cues fixed, `రాము` was *still* action: its dialogue is short, so it looked like a cue itself and disqualified the line above it. A cue does not end a sentence — that is now the discriminator, and it fixes the same asymmetry in Hindi and Tamil. **(3)** The Telugu heading token list was missing two of its own tokens. Reverts: **7 fail** (script set), **7 fail** (sentence-end rule), **2 fail** (heading tokens). 19 tests, with Hindi/Tamil/English as controls. Critique S54. | **G** |
| 25 | **B** | Constructed PDF with a page missing | Global completeness check; the artefact had to be manufactured. | **G** |
| 26 | **A** | AJAY silent beside VENU in scene 1, speaking in scene 2, through the real parser + graph + prompt | Silent presence read as absence — reproduced exactly. **FIXED 2026-11-05.** `characters_present` is cue-derived, so AJAY was in **no** scene-1 list; the graph reported `scenes_present=[2]`, recorded **no co-occurrence pair at all** for two characters in one room, and the summary prompt said `Characters: VENU` — a closed list asserting he was not there. Three evidence tiers are now kept apart: **cue** (he speaks), **mentioned** (named in the text, no cue — what silent presence looks like, and also what an off-screen or past-tense reference looks like), **unconfirmed** (a caps word that may be a person). The prompt says `Characters who speak: VENU` / `Also named in the text … do not assume they are in the scene` / unconfirmed names with why. The `none` case no longer says `none`. The third tier catches the character who NEVER speaks, who cannot be found by matching a cue-derived character list at all (RAVI on the phone). Graph entries are not invented from unconfirmed names. Reverts: **3 / 6 / 2 / 1 / 1**. 15 tests. Critique S57. | **G** |
| 27 | **A** | Controlled document through the real `pacing_curve` (no model needed) | Segments misplaced at page boundaries — reproduced exactly. **FIXED 2026-11-05.** Three defects, all arithmetic: **(1)** `idx = int(pos // segment_pages)` puts page 5 in segment 2 because `5 // 5 == 1`, so two scenes ending on pages 5 and 10 reported **zero** scenes in 1–5 and both in 6–10 — segments are now 1-based inclusive (`segment_of_page`); **(2)** `total_pages` was the last scene's end page and every label was clamped to it, so the segment count depended on where the last scene happened to finish; **(3)** a scene crossing a boundary was charged wholly to its end segment, so a bucket could read empty while pages of it were full — words now split by the fraction of *page span* inside each segment, and the row is marked `~` with a legend saying the figure is an estimate. The page-span convention matters: I first used `[start, end]`, which scored a 10–12 scene as wholly in 11–15; a scene 'page 10 to 12' occupies three pages, so the interval is `(start-1, end]`. My own fix also had a `None`-page crash and a bogus-span bug for text parses, both caught by the tests. Reverts: **10 / 7 / 2 / 1** (boundary, labels, split, report mark). 27 tests. Critique S55. | **G** |
| 28 | **B** | Fake model returning a short reply | Crash precedes any model call in the real path. | **G** |
| 29 | **B** | Fake model returning a direct answer | Filter erases it. | **G** |
| 30 | **A** | Synthetic 30k-char scene, `prompt_budget=2048`, whole payload measured through the real engine | The budget bounded ONE segment of the turn. **FIXED 2026-11-05.** Reproduced: `prompt_budget=2048` sent a **29,971-char system message / 30,369-char payload** (filed: 39,117 / 39,508 — the shape was right). The budget WAS enforced, on `build_system_prompt` alone, whose result `_assemble_messages` then appended to with no budget argument at all: the scene block (62,484 chars for three scenes), the quote, the few-shot examples, the trait and post-history reminders, and the history window. Now: the whole turn is bounded, with a reply reserve held back; scene text is windowed into an equal share of the room actually left, marked where cut and **disclosed** when a scene does not fit; history is the last elastic block and gives way first; and a budget below the irreducible floor **raises** instead of warning and sending anyway. Six reverts measured: 6 / 9 / 8 / 4 / 1 / 2. 23 tests + 2 existing budget tests updated. Critique S56. | **G** |
| 31 | **B** | Fake model plus the real library provider | Cross-project bleed into a prompt. | **G** |
| 32 | **B** | Fake SSE stream | Guards run after streaming begins. | **G** |
| 33 | **B** | Real `BaseLlamaClient` against a mock redirector | SSRF-shaped; constructed. | **G** |
| 34 | **B** | Isolated save with umask 022 | Credential and archive boundaries; two claims, graded at the weaker. | **G** |
| 35 | **A** | Real project layout (`source.fountain` at its canonical name) with a malformed `project.json`, through `POST /api/sample` | Sample-open overwrites it — reproduced. **FIXED 2026-11-06.** Before: `201`, and `source.fountain` went from the writer's draft to `Author: Sample Page / INT. WRITER'S ROOM`, i.e. **six months of work replaced by a demo with a success status**. Cause: `except Exception: pass  # corrupt dir — fall through and re-create`; the route's `os.makedirs` claim fails on an existing directory and any manifest-load error fell into the re-create path. Now a damaged directory is never written to: **409** with the file list, an explicit "it has NOT been overwritten", and the two recoveries (repair the manifest, or move the folder aside). Transient read errors take the same safe path — the register flagged them as untested; they are tested. My first fixture missed the defect entirely because it used a filename real projects never write; the canonical name is `source.<ext>` from `ProjectManifest.source_path`. Reverts: **5 / 4 / 1**. 12 tests. Critique S58. | **G** |
| 36 | **B** | Mock server advertising new limits | Global context cached stale. | **G** |
| 37 | **B** | Held-open file during watch | Timing-dependent. | **G** |
| 38 | **B** | Telugu filename plus a fake orchestrator | Project the desk cannot open. | **G** |
| 39 | **A** | Real CLI subprocess, `watch --once`, on a broken FDX and a mixed batch | Prints FAILED, exits 0 — reproduced. **FIXED 2026-11-06.** A batch where every file failed printed `FAILED` and exited **0**; a mixed batch also exited 0. Automation reads exit status, so a failed import was indistinguishable from a clean one. `cmd_watch` now documents and returns three codes — **0** all succeeded (including an empty inbox, which is cron's normal case), **1** the batch ran and something failed, **2** usage/configuration error, matching the CLI's existing convention so a retry loop does not also retry a typo. A failure count is printed to stderr, an unreadable watch folder is a 2 rather than an uncaught traceback, and `--json` emits per-file outcomes (filename, ok, project, error) agreeing with the exit code. Reverts: **3 / 5 / 2 / 2 / 1**. 13 tests. Critique S59. | **G** |
| 40 | **B** | Mock server advertising one model | Silent fallback to a different model. | **G** |
| 41 | **B** | Mock server implementing `/v1/models` | `/v1` duplication in URL construction. | **G** |
| 42 | **B** | Injected manifest write error | Partial settings application. | **G** |
| 43 | **A** | Twelve-years-delayed confession through the real `run_subtext_analysis` | Direct emotion declared missing subtext — reproduced. **FIXED 2026-11-06.** `I love you.` in a scene staged as a long-delayed release produced *"the subtext is missing, so the scene tells instead of shows"* and *"the moment lands flat"* — **identical to the same line with no framing at all**, and to a comic beat built on the bluntness. One regex match was printed as three separate claims: an absence, a craft verdict, and a claim about the reader. A deterministic check knows only that the line **names an emotion**; it now says exactly that, marked `is_observation` and badged in the report as *"a pattern, not a verdict; whether it works depends on the scene, which is your call"*. Context: action around the line that stages a release (*held this*, *twelve years*, *finally*, *confess*) changes the explanation to note that it looks deliberate. Directness is not banned — every blunt line still raises the observation. Reverts: **1 / 3 / 1 / 1 / 1**. 15 tests. Critique S60. | **G** |
| 44 | **A** | Two-scene synthetic script, real continuity pass | Day/night reported as a dropped transition — reproduced. **FIXED 2026-11-06 together with 77** (one defect, two sides). `INT. KITCHEN - DAY` → `EXT. STREET - NIGHT` produced *"Unmarked time flip … with no transition marker"*. The premise was wrong: **the heading is where a screenplay states time**, and a new slug line is itself the transition. Ordinary cuts now report nothing. What survives is the only case a heading cannot express — **same place, opposite time, nothing between** — reported as `Possible …`, marked `is_observation`, quoting **both** headings and telling the writer an ellipsis may be exactly what they intend. Also: FLASHBACK/DREAM/MEMORY/MONTAGE now count as time markers (the register asked for flashbacks by name; my first pass missed it). Reverts: **4 / 1 / 1 / 1 / 1**. 13 tests. Critique S61. | **G** |
| 45 | **A** | Synthetic multi-scene scripts through the real `per_scene_pace` / `drag_findings` | Numeric proxy stated as diagnosis — reproduced, and worse than filed. **FIXED 2026-11-06.** Three long all-dialogue scenes + two action scenes: `pace_score` `[100.0, 100.0, 100.0, 0.0, 0.0]` and every long scene filed *"only 11% action words — the scene meanders"* on a scene with **no action line at all** — the 11% was four character cues and the slug line (`else: action += words`). The filed entry missed the worse half: the score was a min-max **rank** (three identical scenes tied at exactly 100.0; a uniformly slow script scored 0.0) and it **contradicted itself** — density is words per *element*, so a 44-word action paragraph outranked a 106-word dialogue scene as "draggier" (measured 60.0 vs 40.0; the 0.6/0.4 weights decided it). Now: cues/headings/transitions/parentheticals count towards size and beats but never towards movement; the score is **absolute** (length vs a fixed `SLOW_SCENE_WORDS`, plus dialogue share), so it compares across scripts and identical scenes tie exactly — the same two scenes now score 13.2 and 71.8, in the order the numbers describe; `pace_rank` is a competition rank for ordering only; the finding reads *"Slowest scene by counted words — Scene N (rank 1 of 5)"*, is `is_observation`, drops `medium` to `low`, and ends *"… if it is doing its work, this is not a note."*; the report section is *"Pacing — relative text density"* and its empty state no longer claims the script keeps its momentum. A Latin-word-share gate reports a Telugu script **not measurable** rather than scoring it. Reverts: **5 / 16 / 3 / 1**. 14 tests + the severity pin corrected. Critique S62. | **G** |
| 46 | **B** | Real subtext pass, **demo model** | Mechanism A; the "two findings" are demo content. | **G** |
| 47 | **A** | Rendered a synthetic `AnalysisResult` | "No significant findings" printed for a failed category. | **G** |

## Entries 48–76

| # | Grade | Driven through | Note | Genuine? |
|---|---|---|---|---|
| 48 | **C** | Source read of prompt assembly | Untrusted text in instruction context; explicitly needs a real model to weigh. | **G** |
| 49 | **B** | Forced identical UUID prefixes | Ideas and chats overwritten. | **G** |
| 50 | **A** | Disposable directory, real CLI create | Orphaned source data replaced. | **G** |
| 51 | **A** | Real Flask routes | Undo reports success while failing. | **G** |
| 52 | **A** | Temp-project API test | Structure and exports left inconsistent. | **G** |
| 53 | **B** | Synthetic screenplay, **demo model** | The promoted "fact" is demo output; mechanism is the promotion rule. | **G** |
| 54 | **A** | Controlled two-scene script, real pass | Setup recurrence read as payoff. | **G** |
| 55 | **B** | Injected `IdeaStore` failure | Graduation claims a transfer that failed. | **G** |
| 56 | **A** | Separate process, default model unreachable | Real startup paths disagree with the documented opt-out. | **G** |
| 57 | **B** | Real Flask routes + a loopback server that counts requests | Credentials followed a changed endpoint without a new trust decision. **FIXED 2026-11-05** - the token records the ORIGIN it was entered for and is refused everywhere else, before any outbound call (measured: zero requests reach the second server). Applies to both reachable flows: Test Connection with a blank box, and `POST /api/config` moving `server_url` with no `api_key`. Migrating is one explicit action (type the new token); same-origin port or path changes, clearing the token, and a desk with no token are unaffected. A token with no recorded origin (CLI flag, env var, older config) still works on loopback and is refused off-machine. 8 of 20 tests fail on revert. Critique S44. | **G** |
| 58 | **B** | Real routes + real manifests; a refused save is read back field by field | Partial application; a local-only switch left a remote destination. **FIXED 2026-11-05** - `set_config` now validates the whole request into a plan (`_settings_candidate`) and applies it only if that succeeds, so a 400 leaves every field as it was and never rewrites a manifest. "Go local" now propagates to existing projects **including the credential clear**, so a project's effective destination (`_make_client`) is loopback. A project that still disagrees is REPORTED: a `destinations` block on `/api/config` (GET+POST) and `/api/health` names it, and the settings panel shows a warning instead of a green "Local". 9 of 21 tests fail on the atomicity half reverted, 2 on the propagation half. Critique S46. | **G** |
| 59 | **A** | Temporary project with an analysis-complete manifest | Banner follows current demo mode, not report origin. | **G** |
| 60 | **B** | Fake clock | Nested busy retries past the logical deadline. | **G** |
| 61 | **B** | Two synchronized concurrent uploads | Shared temp file and swap target. **NARROWED 2026-11-04** — private staging file + per-project lock remove the race; the crash window between snapshot/swap/manifest remains. | **G** |
| 62 | **A** | Real route with two synthetic projects | **FIXED 2026-11-04** — `draft_dir` validates at the chokepoint; 5 tests, 3 of which fail without the fix. **Most serious item in the register.** Read and overwrite a sibling project; reached outside `PROJECTS_DIR` on a later write. | **G** |
| 63 | **A** | Draft activation on a real project | **FIXED 2026-11-04** — whole bundle restored; before the fix the original draft lost its cast entirely. | **G** |
| 64 | **A** | Real upload of an invalid FDX, then reactivation | **FIXED 2026-11-04** — refused before the swap; parse stage restored with the snapshot. | **G** |
| 65 | **A** | Stubbed long run plus a real draft switch | **NARROWED 2026-11-04** — switch refused (409) while a run holds the lock; not closed for a cross-process publish. | **G** |
| 66 | **A** | Real `/analyze/cancel` during a real `retry-failed` | 409; the analysis lock is not taken by upload/activation. **FIXED 2026-11-04 (both halves)** — upload/activation take the analysis lock (§28); retry is cancellable (200), a cancelled retry answers `cancelled: true` and the stage is restored, not `failed`. | **G** |
| 67 | **W** | Measured | ~7 ms of subprocess work on a seconds-long operation. Withdrawn. | **W** |
| 68 | **B** | Held `lock_for`, 0.05 s deadline, same-process waiter | In-process contention only. | **G** |
| 69 | **B** | Completed report plus a busy store | Transient warning replaces a good result. | **G** |
| 70 | **A** | Corrupted `idea.json`, real routes | Shown, unrepairable, saves fail as request errors. | **G** |
| 71 | **B** | Synthetic library archive | Idea store labelled a project; relationship memory omitted. | **G** |
| 72 | **A** | Both backup routes with a forced `OSError` | Archive silently incomplete, 200 returned. `except OSError: continue`. | **G** |
| 73 | **A** | Real export with a leftover `source.pdf` beside the active one | No provenance disclosure. | **G** |
| 74 | **B** | Two loaded manifests writing one stage | Merged with 75; whole-stage overwrite from a long-held object. | **G** |
| 75 | **B** | Concurrent nested-stage saves | Last-writer-wins at field level. Merged into 74 as one finding. | **G** |
| 76 | **D** | Listing a project directory | Lock sidecars visible; excluded inconsistently. Housekeeping. | **K** |

## Entries 77–108

| # | Grade | Driven through | Note | Genuine? |
|---|---|---|---|---|
| 77 | **A** | Two-scene synthetic script, real continuity | Day/night cut under an action heading flagged as dropped — reproduced. **FIXED 2026-11-06 together with 44.** Confirmed the sharpest detail: the finding's own `evidence_quote` was the **second scene's heading** — the text stating the new time. A finding quoting its own refutation. Fixed at the root in 44; 77's extra requirements met: cuts/act breaks distinguished from ambiguity, the uncertainty stated in the wording, and **never one heading quoted as evidence a transition is absent** (the evidence is now the pair). The 5→6 / 13→14 / 17→18 class of normal act cuts is pinned by a seven-scene test. Reverts: **4 / 1 / 1 / 1 / 1**. Critique S61. | **G** |
| 78 | **B** | Controlled speaker-name pairs | 2-edit-distance guess produces confident nonsense. | **G** |
| 79 | **A** | Real export then revision | No provenance line; reconstructed indistinguishable from original. | **G** |
| 80 | **A** | Damaged project on the real shelf routes | "Unreadable", then refuses to open, no recovery path. | **G** |
| 81 | **B** | Three-scene excerpt | Act bucketing collapses for short scripts. Display behaviour, overlaps 115. | **G** |
| 82 | **A** | Both shelf responses compared | Project shelf says `unreadable`, idea shelf says something else for the same damage. | **G** |
| 83 | **A** | Real `--help` versus the documented surface | Top-level commands disagree. | **G** |
| 84 | **A** | Live Flask `url_map` compared mechanically with the doc | Stale in both directions. | **G** |
| 85 | **A** | Doc header claims checked against behaviour | Port and process model wrong. | **G** |
| 86 | **A** | Package listing | `graph.json`, `graph_output…` ship inside importable packages. | **G** |
| 87 | **A** (mechanism) | Demo run end to end | A detail absent from the script reached the rendered report. The *content* came from the demo stand-in, so no claim about real-model fabrication. **FIXED 2026-11-04** — `render_markdown` now marks an ungrounded row `⚠️ unsupported` in place and states "N of M notes below are unsupported", which also covers the HTML export (it renders the stored `report.md`). Rows are still rendered, not suppressed. 3 of 8 tests fail without it; the classification half already existed in `_setup_quote` + `apply_evidence_floor` and is proven non-vacuous by neutralising it. Critique §39. | **G** |
| 88 | **C** | Renderer source | Demo output disclosed by name, not by nature. **FIXED 2026-11-04** — the renderer states the stand-in in words from the run's persisted `model_used`, above the findings; the HTML export banner now follows the run instead of the current demo setting (gap 59's shape), and the tiny md renderer gained a blockquote branch so the warning cannot degrade into a `>` paragraph. 5 tests fail on each half reverted. Critique §40. | **G** |
| 89 | **C** | Renderer source | Deterministic and model findings indistinguishable. | **G** |
| 90 | **B** | Refresh after a complete analysis, timed | Second full pass; demo server outlives the run. | **G** |
| 91 | **W** | Real POST/GET | GET returns `branches`, POST returns `messages` — API asymmetry, not a discarded reply. | **W** |
| 92 | **D** | Demo transcripts | Canned first-meeting lines. A statement about the stand-in, not the product. | **G** |
| 93 | **A** | Demo over both attached screenplays, timed | Fast, zero checkable evidence. | **G** |
| 94 | **B** | Route reads plus the 113 probe | "What the writer sees" is assembled per request from several stores. | **G** |
| 95 | **D** | Route reachability | Design lab is a deliberate shipping decision. | **G** |
| 96 | **D** | Filename serving | Dead labs; housekeeping. | **G** |
| 97 | **D** | — | A design proposal for a recovery room, not a reproduced defect. | **P** |
| 98 | **A** | Real intent classifiers, writer's own phrasings | A statement of intent classified as a bare idea. | **G** |
| 99 | **C** | Prompt text read | The safety contract lives only in prompt text. | **G** |
| 100 | **C** | `craft_history` source | Only still-applied edits are citable. | **G** |
| 101 | **B** | Substring rules traced and exercised | Persona-visible behaviour decided by `has_embedded…`-style rules. | **G** |
| 102 | **W** | Probe re-keyed | Mis-keyed pass name in my own probe; two categories do get grounding. Withdrawn. | **W** |
| 103 | **W** | Measured | Genre fragment 7,760–10,389 chars; pacing pass deterministic by design. Withdrawn. | **W** |
| 104 | **W** | Re-traced | The 39,923-char fragment came from a pass name the pipeline does not call. Withdrawn. | **W** |
| 105 | **C** | Rule-id plumbing read | Nothing verifies a `rule_id` came from the fragment supplied to that pass. | **G** |
| 106 | **C** | Analyzer entry signature, prompt vocabulary | The premise card is saved, carried, never read. **The product gap.** | **P** |
| 107 | **D** | — | Design proposal: scene-level intent has nowhere to live. | **P** |
| 108 | **C** | Both collaborator prompt builders | Intent absent from both personas' inputs. | **P** |

## Entries 125–128 (eighth to tenth passes — last modules, packaging, frontend)

| # | Grade | Driven through | Note | Genuine? |
|---|---|---|---|---|
| 128 | **D** | Static read of every `innerHTML` sink in `app.js`/`core.js` | Escaping is correct everywhere today; the invariant is enforced by convention only — no test, lint rule or escaping-by-construction wrapper. Regression guard for a future commit, not a live defect. | **K** |

## Entries 125–127 (eighth and ninth passes — last modules, and packaging)

| # | Grade | Driven through | Note | Genuine? |
|---|---|---|---|---|
| 127 | **D** | `python -m build --wheel`, then install into a clean `--target` and boot it | Wheel is correct: 180 files, 4.04 MB, 263 rules, SPA and fonts present, no tests or scratch files, `/` → 200. The only weakness is that CI's packaging tests inspect the source tree, not the wheel, so they could pass while an installed copy broke. | **K** |

## Entries 125–126 (eighth pass — the last modules at "inventory only")

| # | Grade | Driven through | Note | Genuine? |
|---|---|---|---|---|
| 125 | **A** | Real `/api/stt/languages` + `/api/stt`, remote whisper URL | Capability endpoint advertises `engine: whisper-server` (200) for a configuration the guard refuses (503). The guard itself is correct; the label is not. Low severity, hand-edited config only. **FIXED 2026-11-04** - the label now runs the real guard (`stt.engine_status`) and answers `faster-whisper` + `misconfigured` + the guard own reason, so the two endpoints cannot disagree, including for a `127.0.0.1@evil.com` lookalike. 4 tests fail on each half reverted. The restart-to-reload-env limit is pre-existing and untouched. Critique S42. | **G** |
| 126 | **C** | Real `/api/stt`, 3 MB and empty blobs | No magic-byte or duration check, 256 MB ceiling inherited from uploads. **Downgraded B→C in §22**: the external-server half is the user's own machine, and the inherited ceiling is defensible. Informational; I would not schedule it. | **G** |

## Entries 109–124 (collected in the critique file, graded there and here)

| # | Grade | Driven through | Note | Genuine? |
|---|---|---|---|---|
| 109 | **W** | Root `ruff check .` | Passes. Withdrawn before it was ever filed as a defect. | **W** |
| 110 | **B** | Real CLI, missing source file | Traceback and exit 1 instead of one actionable line. **FIXED 2026-11-04** — one actionable line + exit 2; no directory left behind. | **G** |
| 111 | **A** | Real CLI create + `status` | Round-trip works; positional asymmetry (`--project` versus positional) is the only defect. **FIXED 2026-11-04** — `run` accepts the project positionally and via `--project`. | **G** |
| 112 | **D** | `du` + Pillow/scikit-image legibility check, then a byte-level read-back | `docs/` 12 MB, `impl-shots/` 7.2 MB. **DONE 2026-11-05** - 71 evidence PNGs (30.6 MB) quantised to a 128-256 colour palette where a structural text check (glyph-blob count >=80%, median glyph height, re-read after writing) confirmed the wording survived: **30.6 -> 12.9 MB, -58%**, 60 files converted, 11 left at original size. No resize: half-size keeps text but reads mushy (compared at 1:1), which is the evidence being lost. Worktree 52 -> 35 MB (-33%). History NOT rewritten - blobs remain in `.git`, so a clone is still ~19 MB; that needs branch-owner consent. **Fell out of this pass: 3 groups of byte-identical PNGs under different names** (j4_beatboard/draft/inline_edit; A-scene_function==B-character-dials; A02-evidence-lens==B-coverage), so at most one caption per group is true - filed as gap 130. See `docs/audit/EVIDENCE_IMAGES.md`. | **G** |
| 113 | **A** | `/fixqueue` and `/findings/summary` on a two-finding project | `total_count 2`, `open_count 2` while the desk hides the ungrounded row. **FIXED 2026-11-04** — both routes now ship the grounded/ungrounded split (`ungrounded_count`, `ungrounded_hidden_count`, `open_visible_count`), using the desk's own precedence. **Partly a self-correction:** the claim that the mass strip and dawn meter print this number is wrong — they use `findingCounts()`, which labels whole-script scope — so the impact was an API limitation, not a writer-facing lie. 5 of 7 tests fail without the fix; 2 are static guards. Critique §38. | **G** |
| 114 | **–** | Same probe | **Negative:** summary, queue and `/report` agree on the ordinary serve path. | **–** |
| 115 | **B** | One-scene script | `scene_count: 0` in act buckets. Cosmetic display. | **G** |
| 116 | **–** | Headers read | `X-Frame-Options` absent but CSP `frame-ancestors 'self'` covers it. Not a defect; do not "fix" it. | **–** |
| 117 | **–** | Demo run | A page that fails to parse shows a bare numeric badge — already 47/87 in spirit. Not filed twice. | **–** |
| 118 | **A** | `/api/config` with synthetic key and token | No key, no token - **negative on secrets**. `allow_remote`/`connection_mode` are plain booleans with no machine-readable consent scope. **FIXED 2026-11-04** - a `privacy` block on `/api/config` (GET+POST) and `/api/health` states whether the script leaves the machine, the destination ORIGIN, whether a credential is in use, and its scope. `credentials_scope` says `origin` **only** when an origin is actually recorded — now true, because gap 57 is FIXED (S44); a token with no recorded origin honestly reports `unrecorded` instead of rounding up. **S45 correction:** `credentials_in_use` was also false for a loopback endpoint on a false theory that the token is never sent there; measured against a loopback recorder it IS sent, the field now reports it, and a test pins the claim against the wire. 9 of 10 tests fail without it; the tenth is the secret-withholding negative. Critique S43, amended by S44. | **G** |
| 119 | **A** | Corrupted rules dir through the real pipeline and webapp | Analyze fails `OrchestratorError`, webapp 502 with parser text, then `/report` 400 "Analysis hasn't completed" while the prior report sits intact. Empty rules dir accepted silently. **FIXED 2026-11-04** — typed KB damage; analyze still produces a reading and says so, rules route 503, health degraded. (119's '/report hidden' half was step 3.) | **G** |
| 120 | **–** | `ast.parse(feature_version=(3,10))` over every module | Python floor honest. One UTF-8 BOM in `tests/test_h7_chat_fix.py`; 5 tests pass. Hygiene note. | **–** |
| 121 | **D** | `npm ci && npm test` | 134/134. Docstring says 127; `node --test tests/js/` fails on Node 22. Documentation and invocation trap only. **FIXED 2026-11-04** — docstring derives the count (verified 134); `npm run test:js-only`. | **G** |
| 122 | **C** | — | The four areas I cannot test here, named rather than faked: real model, audience reception, screen reader, non-Linux. | **G** |
| 123 | **A** | Corrupted rules dir, hit `/api/health` and `/api/rules/*` | Health 200 `status: ok`; rules lookup 400 with raw `JSONDecodeError` text, where a *missing* install gets a designed 503. **FIXED 2026-11-04** — a broken install answers 503 with a framed reason, not 400 with the JSON parser's sentence. | **G** |
| 124 | **D** | — | "Verified against both PDFs" means two features, one writer, one language mix. A bound on the evidence, not a gap. | **G** |

---

## Counts, computed from the rows above rather than typed

Counted by parsing this file, not from memory. **126 numbered entries**: 108 genuine gaps,
4 known trade-offs, 4 product-direction, 6 withdrawn, 4 tested and not a
defect. Only the 108 genuine ones remain in the register.

| Authenticity | Count | Where it lives now |
|---|---|---|
| **G** — genuine gap | 108 | `GAP_REGISTER_AND_EXECUTION_PLAN.md` |
| **K** — known trade-off | 4 | archive §1 |
| **P** — product direction | 4 | archive §2–§3 |
| **W** — withdrawn | 6 | archive §4 |
| **–** — tested, not a defect | 4 | recorded in the critique file |

Grades across the whole table (the "how sure was I" axis, unchanged):

| Grade | Count |
|---|---|
| **A** — reproduced through a real interface | 49 |
| **B** — real mechanism, constructed condition | 43 |
| **C** — source inference only | 12 |
| **D** — docs, housekeeping, opinion | 12 |
| **W** — withdrawn | 6 |

**Of the 108 genuine gaps, 48 are grade A, 43 B, 10 C, 7 D.** The pruning
removed 8 entries and merged 1; it did not touch the severe list, which is unchanged.

Five things worth stating plainly, including the two where I had it wrong:

1. **My own earlier summary was wrong, and in the direction that flattered the critique.** I said "roughly
   half the register is conditional or inferential" (that part holds: 47%) but I also said "about forty are
   inference, documentation, or opinion" and "22 cosmetic or opinion". The honest figure is **21 entries**
   (12 C + 11 D). I had been double-counting constructed-but-real entries as inferential. The register is
   *more* evidenced than my self-critique claimed — which means my self-criticism was itself unsupported
   in one of its central numbers.
2. **The severe list does not move.** 1, 3, 4, 18, 21, 23, 61–65, 87, 106, 113, 119. Grades answer "how
   sure am I?", never "how much does it matter?", and severity still drives the fix order in §6.
3. **Grade A ≠ ship blocker.** 30, 39, 45, 86, 93, 111 and 123 are all A and minor. Conversely 3, 106 and
   13 are the entries whose *severity* outruns their grade.
4. **Six withdrawals, not five.** 67, 91, 102, 103, 104, 109. Earlier files listed five because 102 was
   folded into 103; it is a separate mis-keyed probe and is listed separately here.
5. **Four proven negatives stay in the table** (114, 116, 117, 120) plus 118's secrets half, because a
   register that carries only failures gives a false picture of the codebase. The codebase on re-reading
   is more careful than the register's length suggests, and this table is where that becomes visible.

## What this table still cannot do

- It does not make C entries into evidence. Twelve findings remain read-not-driven, and no amount of
  tabulation changes that. They are the least likely to survive contact with a real user.
- It does not touch the four permanently unclosed areas (122). Real-model behaviour, audience reception
  of Darshi and Pain 3, screen-reader output and non-Linux filesystem semantics need the writer's own
  environment.
- The 17 entries graded **A** on behaviour observed in a browser suite that is not installed here (17,
  and the browser half of 5) rest on recorded suite results, not on a run I performed this session. They
  are marked as such rather than upgraded silently.
| 129 | **B** | Real `quote_change` on one real sentence, then the `/edits` route | A one-mark edit read `still_present`, so the writer's work looked like inaction. **FIXED 2026-11-05 as three states, not a retune.** The measurement is the finding: a typo fix scores 0.992, a two-word deletion 0.950, a one-word swap 0.928 - the ratio does not order cosmetic against substantive, so **no threshold can separate them**. The engine now says `unchanged` / `changed` / `gone`; `changed` is exactly the case where the quote is not literally present but still matches (the branch that used to claim the line was untouched), it stays OPEN, and the writer's own `addressed` mark closes it. `changed` counts as open everywhere via one `open_status_count`, so no total moves. The SPA labels it "edited - you decide". 2 tests fail with the engine unwired; 4 with the counting reverted. Critique S48. | **G** |
| 130 | **B** | `md5sum` over every tracked PNG | **NEW 2026-11-05**, found while shrinking the evidence for gap 112. Three groups of screenshots are byte-identical under DIFFERENT filenames: `j4_beatboard_exported.png` == `j4_draft_activated.png` == `j4_inline_edit.png`; `impl-shots/A-scene_function.png` == `B-character-dials.png`; `impl-shots/A02-evidence-lens-full.png` == `B-coverage.png`. At most one caption per group can be true, so at least two audit claims per group point at a picture that cannot be showing what they say. Either the capture script wrote the same frame three times, or three claims were evidenced by one shot. Evidence integrity, not app behaviour: needs a human who knows which frame is which - I cannot tell from the pixels which board state was intended, and guessing would replace a wrong caption with a wronger one. Not fixed, deliberately not deduped. | **G** |
| 131 | **A** | Two separate OS processes sharing one projects dir | **NEW + FIXED 2026-11-05.** The custom provider (base URL, model, API key, connect check) was configurable, but **Save only wrote process memory** and the connected status lived in the browser tab. Measured: configure `https://api.example.com/v1` + a model + a token, restart -> back to `127.0.0.1:8099`, no model, no token. Now `POST /api/config` persists url/model/key/timeouts to `<projects>/.studio_provider.json` **atomic, 0600** (it holds a secret), restored at startup, and the probe records `checked_at`/`ok`/`model`/`destination` so "connected" is a remembered fact with a timestamp rather than a claim about the moment the tab opened. A `provider` block on `/api/config` (GET+POST) and `/api/health` reports what is configured, whether it is **durable** (`saved_to_disk`), and the last check with `stale` when the endpoint has since changed. Three negatives pinned: the token file is owner-only, no route ever returns the token, and a settings file **cannot grant remote permission** — the launch opt-in still owns that. 7 tests fail with persistence reverted, 3 with the recording reverted; 7 node tests. Critique S49. | **G** |
