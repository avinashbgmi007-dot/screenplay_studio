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



