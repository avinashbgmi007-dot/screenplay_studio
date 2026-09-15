# gun_pen.pdf — Full Feedback-Projection Audit — VERDICT TABLE

**Date:** 2026-09-14 (corrected Phase D re-run; tuning go through 2026-09-15)
**Script:** `gun_pen.pdf` — 6 pages, 3 scenes, clean text layer
**Engine:** built-in demo craft model (`webapp_server --demo-model`) — deterministic; findings depth is demo-limited and stated where it matters.
**Harness:** `tests/e2e_browser_common.start_studio` (Playwright) — the project's own first-class browser harness.
**Probes:** `docs/audit/validation-d2.py` … `validation-d6.py` (corrected) · shots `impl-shots/validation-22..29-*.png`

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
| E2 | Escalation · **Sushruta** "why" | **GAP-4** | Lens replies (grounded on scene map + findings count) but carries **no per-finding context**; `msgsContainQuote=false` |
| F1 | Arrival strip — browser == server | ✓ exact | Pass line byte-matches the `/edits` payload (copy now scoped — "Pass: N → M still live · K no longer flagged · J new") |
| F2 | Arrival strip — **arithmetic is true** | ✓ **FIXED (GAP-3)** | Reported `Fixed: 2 · New: 2` with **zero writer action** — now distinct-id honest (`0 no longer flagged · 0 new`) |
| F3 | Unread-dot lifecycle | ✓ projected | Dot present on fresh load after a new pass; cleared on Evidence-lens open |
| G1 | Intent marks survive + exclude from open count | ✓ projected | `finding_intents` on disk; `openCount 5 < 9`; deferred disposition surfaces |
| G2 | Writer-fix signal (observed "addressed") | ✓ projected | Quote-visible edit → `findings_status` = `addressed`; survives reload |
| G3 | "Quote-visible drift" drives Fixed/New | ✓ **RESOLVED (GAP-5)** | Edit applied (`similarity 1.0`) yet the pass line stays `0 no longer flagged` — re-analysis reads the parse, so the numbers can't mean writer progress. Now scoped on-screen + a draft clause ("K of M addressed by you") carries the working-copy truth instead |
| H1 | Ghosted state renders | ✓ projected (render-path) | Seeded payload renders "1 of your marks moved on" + the vanished issue tagged "was next pass"; the *arithmetic* stays unreachable per GAP-5 |
| I1 | **Severity/category filter × board list** | ✓ **FIXED (GAP-1)** | Filter now drives board list + fix queue too (was 15 cards + 9 rows at highs-only); d8 14/14 |
| I2 | Discuss on a no-quote finding | ✓ **graceful** (GAP-2 downgraded) | Fallback pins the issue text (`evidence_quote \|\| issue`); quote card visible |

**Score:** 13 ✓ (projected/graceful/escalation) · 5 confirmed GAPs/structural · 0 unexercised.
**Post-tuning:** all four code GAPs fixed (GAP-3 T1, GAP-1 T2, GAP-4 T3, GAP-5 T4) plus one en-route
guard bug (T4b). 0 open GAPs. Every finding-emitting surface now reads the same filtered,
distinct-id, scoped-signal truth.

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
