# Pain_3 — pre-staged session run card

A real full-length script is already sitting in the live desk, parsed, analyzed
once, and **left cold**. Everything that is dead time for you has been done.
You do the felt work — and the machine's answers become the data for
`docs/REAL_WRITER_VALIDATION.md`.

- **Desk project:** `Pain_3`  (`studio_projects/Pain_3`)
- **Script:** `Pain_3_updated_FULL.pdf` — 111 KB, full length (not a 3-scene seed)
- **Pass 1 result:** 17 findings / **8 distinct** ·
  severity `{low:16, medium:1}` · `{dialogue:9, continuity:3, character:2,
  theme:1, plot_thread:1, genre:1}` · quote trust 3 of 17 verified
- **Desk state:** **COLD** — `last_pass.json` absent, so **no arrival strip yet**.
  That is deliberate: the strip's **first appearance at your pass 2** is the
  felt moment (checklist step 3). Nothing here pre-empts it.

## Launch

```
cd E:\screenplay-studio_1_verdent
python -m screenplay_studio.webapp_server --port 8500 --projects-dir ./studio_projects --demo-model
```

Then open `http://localhost:8500` and click the **Pain 3** card.

`--demo-model` is required here: there is no real craft model on `:8080`, so the
built-in deterministic demo engine drives analysis. See **LIMITS** below — this
choice decides what the session can honestly judge.

## First, widen the filter (one click set)

The desk opens **highs-only**. This script has **0 high findings** (a demo-engine
artifact — the shallow engine never emits `high`), so the board opens showing the
hint *"No findings match the current filter — toggle a severity or category chip
above"*. Click the **Medium** and **Low** chips. The real 8 open up.
**An empty-looking board here is the engine, not a product finding.**

## The session (~30–45 min, one sitting)

1. With the filter widened, let the Problem Board and mass strip land. (Baseline.)
2. Press **⇉ fix loop** — step the findings with **N/P**. Fix 1–2 by hand, or mark
   addressed / next-pass. Make **one small edit** in the manuscript.
3. Run the **second pass** (Analyze → re-run). **Stop** the instant the
   **arrival strip** appears — *before anything else, what did you do first?*
   That first reaction is the data. Now read the strip closely:
   `Pass: N → M still live · K no longer flagged · J new` — and the scope chip
   `from the last run, not your edits`, and `N of M addressed by you`.
   Did you read the first line as *your* progress, or as the analyzer's?
4. Return to the loop with the new pass live. Deferred / ghosted marks should
   read honestly (never red, never in an open count).
5. Live in the desk a while: **Discuss** a finding with Sameer, open the
   **Sushruta** lens, toggle **dawn/night** once.

Answer the surface table in `docs/REAL_WRITER_VALIDATION.md` as you go.

## What this session CAN and CANNOT judge — the honest box

**CAN** judge the *machinery's felt quality*: does the arrival strip land or get
skipped; was the loop actually faster than clicking a list; was the ink the right
amount on the page; did the dock, the marks, and dawn/night hold up over a long
sitting; is the copy honest.

**CANNOT** judge the *content* of the findings, because the demo engine is
shallow — it emits placeholder issues (you will see `Sample dialogue finding.`
repeated ~9×). Whether a finding is *true and useful* needs a real model (drop
`--demo-model`, point the app at your llama-server) or your own script.

So: judge the instrument here; judge the notes elsewhere.

## Already captured for you

`docs/audit/pain3-session-0{0,1,2,3}.png` — dashboard, manuscript, board (filter
widened), and the fix loop engaged. These are the **before**; your pass-2 strip
is the **after**.

## Honest baseline numbers (so you can compare what you see)

- Board shows **19** finding cards = a **2-note "here now" slice** (your current
  scene + script-level) laid over a **17-note full category ledger**. Same
  findings, two views — not a disagreement.
- **Page ink: 0** at rest. Only **3** of 17 findings carry a verified quote
  (scenes 6 / 14 / 18); your current scene is **2**, so no ink is in view. Scroll
  to scene 6 to see ink appear. Ink is quote-dependent by design.
- **Arrival strip is absent** until your pass 2. That is the cold-desk contract.

## Re-running

```
python docs/audit/stage_pain3_session.py          # re-stage + report
python docs/audit/stage_pain3_session.py --shots  # + re-capture baselines
```

Idempotent: reuses the `Pain_3` project, re-runs pass 1, and **re-colds** the
desk (removes any snapshot a previous run or page load left behind).