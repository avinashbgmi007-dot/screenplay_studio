# gun_pen.pdf — Full Feedback-Projection Audit — VERDICT TABLE

**Date:** 2026-09-14 (corrected Phase D re-run; tuning go through 2026-09-15)
**Script:** `gun_pen.pdf` — 6 pages, 3 scenes, clean text layer
**Engine:** built-in demo craft model (`webapp_server --demo-model`) — deterministic; findings depth is demo-limited and stated where it matters.
**Harness:** `tests/e2e_browser_common.start_studio` (Playwright) — the project's own first-class browser harness.
**Probes:** `docs/audit/validation-d2.py` … `validation-d6.py` (corrected; tuning regressions `validation-d7.py` … `validation-d10.py`) · shots `impl-shots/validation-22..29-*.png`

> **Probe honesty note.** The first Phase D run (`validation-d.py`) was invalidated by three
> probe bugs, all fixed here: (1) it read `findings`/`finding_ids` from `/edits`, which
> **do not exist** (findings live at `/report`); (2) it read the Sushruta lens's messages with
> `.msg`, but the adopted FV consult chat renders **`.fv-msg`**; (3) it dispatched a synthetic
> `Enter`, which **cannot submit** the FV `<form>`. Two further probe bugs were caught in my own
> corrected runs and fixed before drawing conclusions: `findingDisposition(f)` called without its
> required `index` (false "all open"), and a filter toggle that was a no-op because the default
> filter is already highs-only.

---

## The verdict table (one screen)

| # | Row | Verdict | Evidence |
|---|---|---|---|
| A1 | Finding-emitting surfaces (9 findings, 5 categories) | ✓ projected | Cards/ink/chips/ruler/queue all render; `verification_summary` present |
| A2 | Zero-finding clean state | ✓ graceful | Zero findings render a real **"clean — no open findings"** affordance + bare ruler, 0 cards, no JS errors (d6) |
| B1 | Coverage block | ✓ graceful | Logline + weak-chip render (demo values) |
| B2 | Writer's mirror (`char_reads`) + genre | ✓ graceful | Absent sections → honest absence, no crash |
| C1 | Quote trust | ✓ projected | "1 of 9 quotes verified (11%)" |
| C2 | Failed categories | ✓ quiet-state | None failed live; retry credited to existing tests (plan fix #4/#6) |
| C3 | `report.md` matches desk numbers | ✓ projected | `report.md` (5,454 B) opens; header matches the desk (Scenes 3 · Characters 3 · pages 6 · CONSIDER · logline · genre); findings count == `report.findings.json` (9) |
| E1 | Escalation · **Sameer** handoff | ✓ escalation | `pendingQuote` pinned (scene 1 + text), drawer opens, quote card visible, composer prefilled |
| E2 | Escalation · **Sushruta** "why" | ✓ **FIXED (GAP-4)** | Was project-level only (`msgsContainQuote=false`); now the consult turn rides the pinned quote into the prompt AND stores it — the doctor answers the finding the writer is looking at; the writer's own question renders in the column (T3/d9 13/13) |
| F1 | Arrival strip — browser == server | ✓ exact | Pass line byte-matches the `/edits` payload (copy now scoped — "Pass: N → M still live · K no longer flagged · J new") |
| F2 | Arrival strip — **arithmetic is true** | ✓ **FIXED (GAP-3)** | Reported `Fixed: 2 · New: 2` with **zero writer action** — now distinct-id honest (`0 no longer flagged · 0 new`) |
| F3 | Unread-dot lifecycle | ✓ projected | Dot present on fresh load after a new pass; cleared on Evidence-lens open |
| G1 | Intent marks survive + exclude from open count | ✓ projected | `finding_intents` on disk; `openCount 5 < 9`; deferred disposition surfaces |
| G2 | Writer-fix signal (observed "addressed") | ✓ projected | Quote-visible edit → `findings_status` = `addressed`; survives reload |
| G3 | "Quote-visible drift" drives Fixed/New | ✓ **RESOLVED (GAP-5)** | Edit applied (`similarity 1.0`) yet the pass line stays `0 no longer flagged` — re-analysis reads the parse, so the numbers can't mean writer progress. Now scoped on-screen + a draft clause ("K of M addressed by you") carries the working-copy truth instead |
| H1 | Ghosted state renders | ✓ projected (render-path) | Seeded payload renders "1 of your marks moved on" + the vanished issue tagged "was next pass"; the *arithmetic* stays unreachable per GAP-5 |
| I1 | **Severity/category filter × board list** | ✓ **FIXED (GAP-1)** | Filter now drives board list + fix queue too (was 15 cards + 9 rows at highs-only); d8 14/14 |
| I2 | Discuss on a no-quote finding | ✓ **graceful** (GAP-2 downgraded) | Fallback pins the issue text (`evidence_quote \|\| issue`); quote card visible |

**Score (at audit time):** 13 ✓ (projected/graceful/escalation) · 5 confirmed GAPs/structural · 0 unexercised.
**Post-tuning:** all four code GAPs fixed (GAP-3 T1, GAP-1 T2, GAP-4 T3, GAP-5 T4) plus one en-route
guard bug (T4b). 0 open GAPs — rows E2/F2/G3/I1 carry their FIXED/RESOLVED verdicts above. Every
finding-emitting surface now reads the same filtered, distinct-id, scoped-signal truth.

---

## Confirmed findings

### GAP-1 — the "ONE filter" is PARTIAL (board ignores it) · **FIXED (tuning go, T2/d8)**
`state.findingFilter` drove **ink** (`inkAnchorsFor`, app.js:4952), the **loop** (`loopList`,
app.js:5099) and the **chips/counts** — but **not the board list**: `renderDockEvidence`
(app.js:4860-4874) iterated `sceneFindings`/`data.scriptLevel` unfiltered; the fix queue
ignored it too. The doc comment claimed the filter drives "ink, board list, loop" — implementation
disagreed with intent (N3 violation).
**Fix (T2):** ONE predicate `findingPassesFilter(f, index)` now sits behind ink, board list (scene +
script-level + category sections), loop list, and fix queue — every surface reads the same filter, so
page/board/queue agree by construction. A filter matching nothing shows the honest empty hint ("No
findings match the current filter — toggle a severity or category chip above"), never a blank; the queue
reads "N open / M shown / T total". d8 end-to-end on gun_pen: cards 0→11→4→15→3 tracking the chips,
queue rows in lockstep, category narrows both surfaces — **14/14 checks pass**. phase6 e2e contract
updated to exercise both sides (default empty-hint + widened reveal); suite **28/28** after one
real bug the first run exposed (the empty-queue panel bypassed `addPanel`, throwing TypeError on the
craft-shelf's array container — the manuscript never rendered).

### GAP-3 — arrival arithmetic manufactures false Fixed/New under duplicate ids · reproduced
`last_pass_snapshot` (revision.py:143-156) computes `still = set(old) & set(new)` but then
`fixed = len(old_ids) - len(still)` and `new = len(new_ids) - len(still)` — mixing a **list length**
(which counts duplicates) with a **set size**. gun_pen's report has **9 findings but only 7 distinct
ids** (two pairs share `category + normalized issue`), so with **no writer action** the strip reports
`Fixed: 2 · New: 2` when the set-truth is `0 · 0`. This is not demo-only: the weak no-quote tier keys
on normalized issue text, so repeated phrasing collides with a real model too.

### GAP-4 — the Sushruta lens carries no per-finding context · **FIXED (tuning go, T3/d9)**
`sendFvMessage` passed `quote = null` into `streamChatTurn` — only the Sameer cowrite path consumed
`pendingQuote`. Live: a real "why was this flagged?" reply arrived (grounded on the scene map + "9
findings riding along") but the answer was project-level, never pinned to the finding the writer was
looking at. Secondary UX note: `renderFvChat` filtered the consult column to `role === 'assistant'`,
so the writer's own question was **not shown** in the doctor's column.
**Fix (T3):** (1) consult turns now ride the pinned quote into `streamChatTurn` — the doctor's prompt
carries `Passage from the script: "…"` and the passage is stored on the user message; (2) the
composer's partner is flushed onto the live session BEFORE the turn is stored (a session created by
the send started on the default persona — the idea room's premise-doctor first-send contract, mirrored);
(3) every stored turn is tagged `partner` (writing_partner | script_consultant) and the consult column
scopes by it, rendering the writer's own turn + a quote chip (legacy sessions fall back to the old
assistant-only view — no history vanishes); (4) a 🩺 escalation action on deep board cards pins the
finding, flips to the Sushruta lens and seeds the "why" question in one gesture.
Verified: 6 new pytest cases (`tests/test_consult_context.py` — quote reaches the prompt, is stored,
malformed dropped, persona tagging both ways, legacy round-trip); d9 end-to-end on gun_pen
(`docs/audit/validation-d9.py`) — the escalation gesture, the stored quote + persona (client AND server
session JSON), the writer's turn rendering in the doctor's column, the quote chip, and a consultant-voiced
reply — **13/13 checks pass**. First d9 run caught a real bug: the lens persona switch was skipped when
no session existed yet (dockLensPersona no-ops without one), so the doctor's first turn spoke and was
tagged as Sameer — fixed with the send-time flush.

### GAP-5 — "quote-visible drift" is structurally impossible · **RESOLVED (tuning go, T4/d10)**
`Orchestrator` loads `m.parsed_path` for analysis (orchestrator.py:110, :232) — the **original
parse**, not the working copy. So editing a cited line never changes the analyzed text, the finding's
`category+quote` id is stable, and Fixed/New can never respond to writer fixes. The writer-fix signal
does exist — but it lives in `finding_statuses` (observed `addressed`, from the **working copy**,
revision.py:549-563) and the disposition/counts, **not** the arrival strip. Net: the strip's
"Fixed/New" means *analyzer-pass drift only*, and (via GAP-3) can be false even then.

**Resolution (T4):** recon reframed this from "make analysis read the working copy" to a labeling
defect with a ready-made true signal. `revision.py:6-7` states the split as design intent — *"every
export / re-verification / chat context read goes through the working copy"* — so there are
deliberately **two signals**, and both already ride the same `/edits` response the strip comes from
(webapp_server.py:857): the pass diff (parse-of-record) and `findings_status` (working copy). Making
analysis read the working copy would have changed the analyzer's evidence base and quote-verification
semantics — a large, risky change to honest zero. The smaller honest change was already available:
(1) the pass line reads "Pass: N → M still live · K no longer flagged · J new" with a scope chip
("from the last run, not your edits") — the word "Fixed" is gone, so nothing borrows writer credit;
(2) a **draft clause** carries the writer's own working-copy progress ("K of M addressed by you",
same counting contract as the revision strip — N3), the signal the strip lacked. Verified: d10
end-to-end (`docs/audit/validation-d10.py`) — the writer edited a verified line (`similarity 1.0`,
draft flipped to `addressed`) yet the pass line stayed `0 no longer flagged · 0 new`, proving the
numbers cannot track writer fixes; the strip then shows "1 of 9 addressed by you" — **16/16**.

**En-route bug (T4b):** the mtime-only guard in `last_pass_snapshot` was unsound — a report rewritten
within one filesystem timestamp tick keeps the same mtime, so the guard served a **stale payload**
(`null` after arithmetic already existed, or stale Fixed/New). Surfaced as a full-suite flake
(`test_second_pass_arithmetic` intermittently `assert None is not None`; reproduced deterministically,
baseline-confirmed absent-in-isolation at HEAD `512a866`). Fixed by pairing the mtime with a
**content signature** (`report_sig` = SHA-1 over distinct finding ids); new regression test
`test_guard_survives_same_tick_rewrite` (fails on the old code, passes on the fix). Flake gone:
87/87 × 5 repeats; full suite **713 passed**.

### GAP-2 — DOWNGRADED (was filed as a gap; live evidence contradicts it)
Phase C reported "Discuss on a no_quote finding → `pendingQuote: null`". The code pins
`evidence_quote || issue` (app.js:5179) and the live dump shows a populated `pendingQuote` with a
visible quote card. It is a **graceful fallback** (issue text pinned instead of a verbatim quote),
not a dead-end. Tuning note only: consider labelling the card "note" vs "quote".

---

## Coverage closed (d6 — the three rows that were ⏳)
- **C3 `report.md`** — exists (5,454 B), opens, and its header matches the desk: Scenes 3 · Characters 3
  · pages 6 · recommendation CONSIDER · logline · genre; its findings count equals
  `report.findings.json` and the desk's `/report` (9). ✓ projected.
- **A2 zero-finding clean state** — the UI renders a genuine **"clean — no open findings"** affordance
  (plus a bare ruler, 0 cards, no JS errors). Honest caveat: the **demo engine cannot produce a
  zero-finding report** for any script with scenes (dialogue/theme/character emit whenever scenes
  exist; genre emits unconditionally), so the state was verified by seeding `findings: []` — a
  render-path test, not an end-to-end engine test. ✓ graceful.
- **H1 ghosted** — the summary renders ("1 of your marks moved on") with the vanished issue tagged
  "was next pass". Verified with a **seeded** `last_pass.json` payload, because the *arithmetic* that
  would produce it is unreachable (GAP-5 keeps ids stable; GAP-3's duplicate churn removes no real id).
  ✓ render-path verified; the triggering path remains structurally unreachable.

## Documentation corrections (carried into NOTES.md)
- The prior session's "backend ground truth" category breakdown (dialogue 3, structure 2, character 2,
  scene_function 1, principles 1) is **wrong**. The actual demo report is: **continuity 1, structure 1,
  dialogue 2, theme 1, character 2, plot_thread 1, genre 1** — 9 findings, 7 distinct ids.
- The prior "Fixed: 2 · New: 2" on an unedited script was attributed to demo nondeterminism; the real
  cause is **GAP-3** (duplicate-id arithmetic), and the demo model is deterministic.

## Recommended next go (tuning — gaps filed, not hotfixed)
1. ~~**GAP-3 first**~~ — **DONE** (T1): the diff is set-based on distinct ids; arrival strip
   reports honest zeros under duplicates. 33/33 revision tests + 80/80 webapp API tests green.
2. ~~**GAP-1**~~ — **DONE** (T2): ONE predicate `findingPassesFilter(f, index)` behind ink, board
   list, loop list and fix queue; honest empty-filter hints on board + queue; phase6 contract
   updated (28/28), d8 probe 14/14.
3. ~~**GAP-4**~~ — **DONE** (T3): consult turns ride the finding's quote, the turn is tagged with the
   persona and the writer's own question renders in the doctor's column; a 🩺 escalation gesture on
   deep cards pins + flips + seeds in one move. d9 probe 13/13, 6 new pytest cases.
4. ~~**GAP-5**~~ — **DONE** (T4): the strip's pass line is scoped and honest ("Pass: N → M still
   live · K no longer flagged · J new" + "from the last run, not your edits"), and it now carries
   the writer's own working-copy progress ("K of M addressed by you"). Analysis deliberately still
   reads the parse-of-record (revision.py:6-7 is the design intent); the fix is honest copy plus the
   true signal, not a change to the analyzer's evidence base. d10 probe 16/16. En route: fixed the
   `last_pass_snapshot` same-tick mtime-guard hole (content signature) that was flaking the suite.
5. ~~Close the three ⏳ rows~~ — **done in d6** (see "Coverage closed"). Residue: the clean-bill and
   ghosted states were verified via *seeded* payloads, so one real-model pass would still be worth it.

*The felt gate — `docs/REAL_WRITER_VALIDATION.md` — remains yours: no probe substitutes for a writer
using the strip and the loop on their own pages.*

---
---

# RE-RUN ON A REAL MODEL — the demo-validated premises do not survive

**Date:** 2026-09-18/19 (session-only; **no production code was changed**)
**Script:** the same `gun_pen.pdf` (6 pages, 3 scenes, real text layer, Telugu/Tenglish)
**Engine:** a **real `llama-server`** (`qwen3.6-35b-a3b-pruned-v2.gguf`, `localhost:8080`) — NOT the
demo craft model. Project `studio_projects/gun_pen_2`, two full 12-pass analyses (~527 s each).
**Harness:** `tests/e2e_browser_gun_pen_audit.py` (stages `matrix | escalation | inbetween | pass2 |
cleanbill`, driven by `E2E_BASE` against the real server) · shots in `impl-shots/` · raw results
`impl-shots/audit_results.json`. Read-only probe `tests/_gunpen_probe.py`; synthetic clean-bill seed
`tests/_gunpen_clean_bill.py`.
**Why a re-run was owed:** the section above closes with *"one real-model pass would still be worth
it."* This is that pass — and it falsifies two premises the tuning work rested on.

> **Probe honesty note.** Five of my own artefacts polluted early measurements and were corrected
> before any conclusion was drawn: (1) the audit's own writer marks (`finding_marks.json`) hid two
> findings, so the "0 verified badges" first reading was partly mine — the marks were cleared and the
> measurement re-taken; (2) my one working-copy edit was **undone** at the end (`/edits/undo`) so the
> project is left writer-neutral; (3) the results file overwrote earlier stages' gaps
> (`RESULTS["gaps"] = GAPS` replaced instead of merged) — fixed, stages re-run; (4) the per-category
> screenshots silently never fired, because a **lens-scoped locator passed to `has=` is re-rooted
> against each candidate** (`.dock-section >> .dock-lens >> .dock-section-title` matches nothing) —
> the inner locator must be page-rooted; (5) after fixing (3), gaps then accumulated forever and a
> retired gap survived — accumulation is now per-stage (retire-and-replace).
> `parsed.json` was never touched, which is the point of GAP-7 below.

## The verdict table — real model

| # | Row | Verdict | Evidence |
|---|---|---|---|
| A | Finding-emitting surfaces (36 findings, 8 categories) | ⚠ **partial** | Cards/ink/chips/ruler/queue render — but **one whole category is missing** (GAP-6) |
| A2 | **Margin ink** (the "where is the flaw" answer) | ✗ **BROKEN on a real model** | **0 pins** on a script with 9 quoted findings — the 8 dialogue ones are hidden by GAP-6 and the 9th is script-level (GAP-6) |
| B | Report sections (pacing · dials · reads · logline · coverage · setup/payoff) | ✓ projected | All panels render from real data; the dials are still unreachable (GAP-4, carried) |
| C | Quote trust readout | ⚠ **self-contradicting** | Strip says **"8 of 36 quotes verified (22%)"**; the board shows **2** verified badges (GAP-6) |
| D | Failed categories / quiet state | ✓ quiet-state | `failed_categories` empty, `errors: []`, no retry button; retry credited to existing tests |
| E1 | Escalation · **Sameer** (deep card / fix queue / loop bar) | ✓ escalation | All three gestures pin the quote, open the room, seed the composer; a real reply streams back; the scene gains `.scene-discussed` |
| E2 | Escalation · **Sushruta** "why" | ✓ escalation | Seeded with category + scene; the reply carries genuine **per-finding** reasoning (names the flaw, explains it, locates Scene 2, quotes the Telugu line) — hypothesis confirmed, no gap |
| F1 | Arrival strip — browser == server | ✓ exact | Pass line byte-matches the `/edits` payload |
| F2 | Arrival strip — **arithmetic is true** | ✓ **fixed (GAP-7)** | On a byte-identical `parsed.json` the strip now reads `fixed=0 / new=0 / same_input=true` with the churn disclosed as `rewritten` (`33 of the last pass's 36 findings reworded`). Was `33 → 4 still live · 29 no longer flagged · 32 new` on zero writer action |
| G | Clean bill (synthetic, no zero-finding row occurs naturally) | ✓ graceful | Empty pass reads the clean-bill line, lens not blank, no cards/strip/retry — 6/6 |
| G2 | Unread-dot lifecycle | ✓ projected | Dot present on a fresh load after a new pass (dock closed), cleared when the Evidence lens opens — asserted live |
| H | `report.md` | ✓ projected | Exists (29,421 B / 251 lines), opens, matches the desk (3 scenes · 3 characters · 6 pages) — but titled `source.pdf` (carried) |
| I | **ID stability across passes** | ⚠ **unchanged by design, no longer deceptive (GAP-7)** | 4 of 33 ids still survive a no-op re-analysis — 75% of ids are keyed on LLM prose. The gate means that churn can no longer be read as progress, but the ids themselves are still not stable |

**Score:** 8 ✓ · 3 ✗ structural · 2 ⚠ partial · 0 unexercised.
**The headline:** the previous session fixed the arrival strip's *copy* on the theory that *"GAP-5 keeps
ids stable"*. On a deterministic demo engine that is true. On a real model it is false — and the same
id-instability silently deletes an entire category from the board. Separately, one matcher disagreement
(GAP-6) empties the manuscript's margin ink and hides every dialogue finding on a script nobody touched.

---

## GAP-6 (CRITICAL · trust) — the status engine calls 7 verified quotes "gone", and the board deletes the Dialogue category · **RESOLVED (Wave 1.5)**

**Symptom.** On a script **nobody edited**, the desk reports 8 findings as *"addressed by you"*, and the
board loses its **Dialogue** section — the largest category on a dialogue-heavy script.

**Evidence (measured against the pristine `parsed.json`, the analyzer's own input — never edited):**

| | |
|---|---|
| Report | 36 findings · dialogue 8 · structure 7 · character 5 · scene_function 5 · genre 5 · theme 3 · plot_thread 2 · continuity 1 |
| Verification | verified **8** · not_found 1 · no_quote 27 → strip: **"8 of 36 quotes verified (22%)"** |
| Status engine (`findings_status`) | **addressed 8 · still_present 1 · unknown 27** |
| The 8 "addressed" | **all dialogue** — **6 verbatim in the script** (verifier conf 1.0) + 1 at 0.82 fuzzy + 1 genuine paraphrase |
| Client disposition (no writer marks) | 28 open · **8 addressed** |
| Board sections rendered | FINDINGS — SCENE 1 · SCRIPT-LEVEL FINDINGS · CONTINUITY 1 · STRUCTURE 7 · THEME 3 · CHARACTER 5 · SCENE FUNCTION 5 · PLOT ECONOMY 2 · GENRE 5 · COVERAGE · SETUP / PAYOFF — **no DIALOGUE** |
| Mass strip category summary | `Structure 7 · Character 5 · Scene function 5 · Genre 5 · Theme 3 · Plot economy 2 · Continuity 1` — **no Dialogue** |
| Verified badges on the board | **2**, while the same strip claims **8** |

**Mechanism — two matchers, two answers (proven, not inferred).** The analyzer and the status engine
disagree by construction. `screenplay_analyzer/verifier.py:_normalize` **lowercases and strips
punctuation** (`re.sub(r"[^\w\s]", "", …)`), joins the scene's elements into one string, and matches
containment against that (falling back to a sliding-window fuzzy at ≥ 0.72).
`screenplay_studio/revision.quote_present()` does **neither**: it substring-matches the raw quote
**against one element at a time**, then fuzzy-compares the whole quote (≥ 0.95) against that same
single element — which is only ~35 chars long.

Worked example, verbatim from `parsed.json` Scene 1:

```
element[7]  'yudhame jarguthundi... “you are the'
element[8]  'sum of all your choices”'
finding.evidence_quote  '"you are the sum of all your choices"'
```

Two independent reasons the engine misses it, either of which suffices: the quote **spans two
line-wrapped elements** (the engine only ever compares a quote to one), and the model wrote **straight
quotes** where the script has **curly** ones (`“ ”`) — the verifier strips both, the engine strips
neither. So the verifier returns `verified · confidence 1.0` and the status engine returns
"the quote is gone".

**How strong is each of the 8.** Re-measured with the verifier's own normaliser:

| | count | what it means |
|---|---|---|
| verbatim in the script (verifier conf **1.0**) | **6** | the engine is flatly wrong — the line is there |
| accepted by the verifier at **0.82** fuzzy | 1 | model paraphrase the verifier chose to accept |
| genuine paraphrase (`not_found`, 0.56) | 1 | "addressed" is accidentally closer to true — but still not caused by a writer edit |

`finding_statuses` never consults the writer's intent — "addressed" is *purely*
`quote_present == False`. So the phantom is structural, not a one-off: on **both** real-model passes
the count was 7 and 8 — **100 % of the dialogue findings, every time.**

**Writer-visible consequence — all three of the writer's questions break.** The dialogue category —
the single most useful surface on a dialogue-heavy script — is **deleted** from the board's sections,
the category chips and the mass strip's own summary. Because the verified tier is dialogue-dominated,
the trust surface collapses: the strip advertises 8 verified quotes and the board shows 2.

Worst of all, the **margin ink goes completely blank**. An ink pin requires a finding that is *open*,
*carries a quote* and *names a scene*. Of the 9 quoted findings, 8 are the phantom-addressed dialogue
ones, and the 9th (continuity) is script-level (`scene_refs: []`) so it has no scene to anchor to:

```
.finding-ink (margin pins) total: 0
inkable (open AND quoted AND scene-anchored): 0 of 9 quoted findings
```

So on a script the writer never edited, the manuscript shows **no margin pins at all**. The plan's
audit spine asks the desk to answer three questions — *what did I get? where is the flaw? what do I
do?* The first is miscounted, and the second is **silent**. That is the product's own N3 law broken on
the first screen a real writer sees.

**Fix direction — superseded (RESOLVED in Wave 1.5, below).** One matcher, one answer: have `quote_present()` normalise
the way the verifier does (lowercase + strip punctuation) and compare against the **joined** scene text
rather than a single element — or better, expose one shared matcher from `screenplay_analyzer.verifier`
and call it from both places, so the two can never drift again.

### Resolution (Wave 1.5) — the normaliser is shared, the THRESHOLD is not

The fix direction above was right about the normaliser and the haystack, and wrong about "one matcher".
Sharing the threshold would have traded this bug for a quieter one: verification must be lenient (a model
paraphrases a real line) while change detection must be strict (a reworded line is what a **writer's edit**
looks like). Measured at element granularity on normalised text: a dropped character scores **0.979**
(still present), a swapped word **0.875** and a removed word **0.830** (both edits). Verification's 0.72
accepts both edits, so a shared threshold would have made every edited line keep reading "still present"
and silently killed the writer-fix signal.

Shipped: `screenplay_parser/quotematch.py` holds the shared primitives (the normaliser, the scene joiner,
the windowed comparison). That package imports nothing from the analyzer or the studio, and both
`revision.py` and `verifier.py` already import it, so the studio never reaches into the analyzer and there
is no import-failure path that could restore the old matching. `verifier._normalize`,
`_scene_full_text` and `_best_fuzzy_match` are now **aliases**, not wrappers. `revision.quote_present`
runs containment over the joined, normalised scene, then a strict per-element ratio at
`QUOTE_CHANGE_THRESHOLD = 0.95`.

**Measured on the stored project** (`gun_pen_2`, no browser and no model — `finding_statuses` re-reads the
stored report and working copy):

| | still_present | addressed | unknown | contradictions* | inkable | dialogue open |
|---|---|---|---|---|---|---|
| before | 1 | **8** | 27 | **6** | 0 | 0 of 8 |
| after | **7** | 2 | 27 | **0** | **6** | 6 of 8 |

\* verifier accepted the quote at confidence 1.0 while the status engine called it gone.

The before column reproduces the audit's recorded `8 / 1 / 27` byte-for-byte, so it is the same data this
section measured. The 6 that flipped are exactly the six the audit identified as verbatim in the script.
The 2 that stayed "addressed" should have: one is a verifier-accepted paraphrase at 0.82, one a genuine
`not_found` at 0.56. Neither quote is in the script.

**Browser re-run** (matrix stage, real llama-server on :8080, real report - the same way this section was
measured the first time):

| | dialogue section | margin ink | mass strip open | phantom addressed | gaps filed |
|---|---|---|---|---|---|
| before | **absent** | **0 pins** | 26-28 of 36 | 8 | 7 |
| after | **present (6 findings)** | **3 pins** | 34 of 36 | 2 | **5** |

Two of GAP-6's four writer-visible consequences are gone: the board renders its Dialogue section, and the
manuscript carries margin ink again. Two are reduced and honest: 2 findings still read "addressed"
because their quoted line genuinely is not in the script, so the mass strip counts 34 open of 36 rather
than 36. `A-dialogue.png` now exists - the missing screenshot was the evidence for this gap.

**The ink needed its own fix, and only running it found that.** After the status fix the findings were
open and scene-anchored (6 of 9) and the data-layer prediction said the pins would render, but the browser
still showed **0**. `decorateLineWithInk` required `text.indexOf(quote) !== -1`: the **whole** quote inside
**one** line. A quote cited across a line wrap can never satisfy that, so every wrapped finding stayed
invisible on the page even once it was open. Same root cause, fourth surface. The renderer now falls back
to the quote's longest leading fragment present on the line, with quote marks stripped per word (a model
writes straight quotes where a script may have curly ones). Measured: 0 pins, then 3. Predicted 6 inkable
findings do not imply 6 pins - several share a line and collapse into one mark with a count chip.

> **Artifact disclosure.** Re-running the matrix stage regenerated the shots in `impl-shots/`, so those
> images now show the **fixed** desk - including `A-dialogue.png`, which could not exist before. The
> pre-fix working-tree images were overwritten by that run (they were themselves uncommitted); the pre-fix
> *numbers* are preserved in the tables above and in `_qa_bugrepro/audit_results.PREFIX.json`, and
> `git show HEAD:impl-shots/...` still holds a pre-fix image set. A verdict table whose screenshots get
> silently replaced by the fix is a small honesty bug of the same family this document exists to catch.
>
> **Fixed (pass 14h).** The mechanism, not just the instance: a `gun_pen` audit run now writes to
> gitignored `impl-shots/runs/latest/`, and reaching the versioned set is the explicit act
> `AUDIT_PROMOTE=1`. So the images this table cites can no longer be swapped out from under it by
> someone merely re-running the audit. See `docs/TESTING.md`; the rule is pinned in
> `tests/test_repo_hygiene.py`.

**Rows A, A2 and C above describe the pre-fix walk.** The Dialogue section returns (6 of 8 findings open),
the manuscript regains 6 inkable quoted findings, and the mass strip's open count tracks the report. The
rows are left as measured, because a verdict table that quietly rewrites its own history is worth less
than one that shows what was true when it was taken.

**Residual (flagged, not fixed):** "addressed" is still purely `quote_present == False` and never consults
the writer's own marks, so the 2 genuinely absent quotes still read as writer progress on a draft nobody
edited. The contract violation is closed; the **attribution** issue is narrower and is the same root as
GAP-7.

---

## GAP-7 (HIGH · trust) — the arrival strip reports LLM run-to-run variance as writer progress · **RESOLVED (2026-09-19)**

**Symptom.** Re-running Analysis on an **unchanged** script reports
`Pass: 33 → 4 still live · 29 no longer flagged · 32 new`.

**Evidence.**

- `parsed.json` mtime **2026-09-18 17:30:01** (pass 1) is *unchanged* through pass 2; the report is
  **2026-09-19 00:26:05**. The analyzer read byte-identical input both times.
- The writer made no edits to the analyzer's input (edits go to `working.json`; the analyzer reads
  `parsed.json` — the design intent, `revision.py:6-7`).
- `last_pass` payload: `{last_total: 33, still_live: 4, fixed: 29, new: 32}`.
- `last_pass_snapshot` has **no writer-action gate**: `fixed = len(old_set) - len(still)`, purely id-based.

**Mechanism.** `compute_finding_id` = `hash(category | evidence_quote or "issue:" + issue[:100])`. For
the **no-quote tier — 27 of 36 findings (75 %) — the id is a hash of LLM-authored prose**, which the
model rewords on every run. Proof by construction: appending " (reworded)" to a no-quote finding's
issue changes its id `fc8epm4 → fj0wwc9`; the same mutation on a quoted finding leaves its id
(`f1atq8x7`) unchanged.

**Correction to the previous section.** Its GAP-5 resolution is quoted above as *"GAP-5 keeps ids
stable; GAP-3's duplicate churn removes no real id"* — and its H1 row says the ghosted path is
*"structurally unreachable"*. Both statements were **true of the deterministic demo engine and are
false of a real model**: ids churn ~88 % per run, so Fixed/New move without the script moving, and the
ghosted path is reachable. The copy fix ("from the last run, not your edits") is honest about *what is
being compared* — but it cannot make a number meaningful that moves 88 % on identical input.

**Fix direction (not open — needs a product decision).** An id stable across runs is required before
the arrival arithmetic can mean anything: key the no-quote tier on a **deterministic** signal
(category + scene + check_id, not the model's sentence), or gate Fixed/New on an actual writer edit.

**RESOLUTION (2026-09-19).** The second option won, because the first cannot pay: a census of the real
report shows only **3 of 36** findings carry a deterministic key (`check_id: pacing_drag`,
`rule_id: character_trait_continuity`, `setup_payoff_general`), while the rest carry `rule_id` = the rule
**title as prose** ("On-the-Nose Dialogue vs. Subtext"), model-chosen and re-worded every run. So the gate
shipped instead of a re-key:
`_parsed_signature(m)` fingerprints the analyzer INPUT (parse bytes + report language) and
`last_pass_snapshot` refuses to read movement as progress when that fingerprint is unchanged: `fixed=0`,
`new=0`, `same_input=true`, with the churn disclosed as `rewritten` and the previous total in `prev_total`.
The strip now reads `Pass: 22 → 22 still live · 0 no longer flagged · 0 new` plus
`33 of the last pass's 36 findings reworded by the model — your script did not change` on the real pass,
where it used to read `33 → 4 still live · 29 no longer flagged · 32 new`.

**A second defect surfaced while fixing this one, and it had no gap filed against it.** With the gate
reporting the truth, `last_total` was still the *previous* pass's count, so the strip headlined `Pass: 36`
while the board beside it counted 22 rows. Two runs over one script filed 36 findings and then 22, so
"previous pass total" and "board row count" are different quantities that drift on a non-deterministic
model. On the identical-input path the headline is now the report the desk is holding (rows) and the
previous total moves into the labelled clause. Ids still churn; they no longer read as progress.

---

## Carried over from the 2026-09-18 session (filed in `NOTES.md`, not fixed)

These were found by the same audit and remain open. Full mechanism + evidence in `NOTES.md`
(§ *gun_pen.pdf — FULL FEEDBACK-PROJECTION AUDIT*).

- **Desk status says "a clean bill" on a 36-finding project** — `refreshDeskToolbar()` runs at
  project-open *before* `state.findings` is populated and is never re-run. (MED · trust)
- **The fix loop covers its own bar** — `startLoop → stepLoop → jumpToScene → openCowriteRoom` opens
  the partner drawer over `#context-dock`, so the loop bar's mark/park/discuss buttons are unreachable
  by mouse. 26 of 35 findings have no quote, so the fallback fires for most of them. (MED · UX)
- **Character dials render into dead chrome** — 15 `.dial-row` nodes exist, but they live in
  `#struct-rail`, which `style.css:3886` declares `display:none`. (LOW · reachability)
- ~~**The arrival basis can never equal the board basis** — distinct-id arithmetic vs row count.~~ (LOW ·
  honesty) **RESOLVED 2026-09-19**, together with GAP-7. On a byte-identical script there is no delta to
  draw, so the headline is the report the desk is holding (rows) and the previous total is disclosed in the
  re-wording clause. Check: `pass2: on an unchanged script the arrival 'Pass:' total equals the board's
  finding count`.
- **`report.md` is titled after the temp upload name** (`source.pdf`, not `gun_pen`). (cosmetic)
- **Parse confidence "low" on a PDF with a real text layer.** (cosmetic)

## Matrix correction (the plan's split matrix vs what the backend actually emits)

- `principles` produced **zero** findings (graceful empty row, not a gap).
- `setup_payoff` owns **no** category: its abandoned setups surface as `plot_thread` findings
  (`rule_id=setup_payoff_general`) — exactly the plan's "dangling entries fold into Plot Economy".
- `genre` is a **finding category**, not a report block; the "genre block" is `coverage.genre`.
- Categories the plan omits that **do** emit: `continuity`, `plot_thread`.
- `rule_id` vs `check_id` is live: **3 of 36** findings carry a KB `rule_id`, so the *"Grounded in
  knowledge-base rule X"* tooltip applies to 3 of 36.

## Coverage closed on the real model

- **Both escalation routes work end-to-end with a live model** — Sameer from a deep card, a fix-queue
  row and the loop bar; Sushruta's "why" seeded with category + scene and answered with genuine
  per-finding reasoning. The plan's escalation hypothesis is **confirmed, no gap**.
- **Failed-category retry** — quiet state verified (`failed_categories: []`, no retry button) and the
  mechanism credited to `test_feature_batch`, `test_bugfix_batch`, e2e `phase8_lifecycle`, e2e
  `phase14_signoff_journey`.
- **Clean bill** — no zero-finding row occurs naturally, so the plan's sanctioned synthetic seed was
  used (`tests/_gunpen_clean_bill.py`); 6/6.
- **Unread-dot lifecycle** — asserted live: the dot is present on a fresh load after a new pass (with
  the dock closed) and clears when the Evidence lens opens.
- **Per-category screenshots** — `A-structure.png` and `A-scene_function.png` exist; `A-dialogue.png`
  **cannot exist**, because GAP-6 removes the section it would photograph. The absence is the evidence.
- **Intent marks survive a re-analysis** — all three of the audit's marks survived pass 2 (and were
  cleared afterwards to leave the project writer-neutral).

*The felt gate — `docs/REAL_WRITER_VALIDATION.md` — is still yours. Nothing above substitutes for a
writer using the strip and the loop on their own pages — and GAP-6 is the strongest argument yet that
they should: a writer who never edited a line is being told eight of their findings are addressed.*

