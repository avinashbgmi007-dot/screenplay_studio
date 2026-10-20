# Real-Writer Validation — the one-page checklist

The one gate left. Automation proved the machinery (713/713 pytest · 30/30 layout audit ·
live probes d6/d7/d10 with exact arithmetic) — only a writer with their own script can prove
the promises. One sitting, one page, honest notes.

## Status (2026-10-20)

No writer sitting has occurred: all 13 answer rows below remain blank. The
automated baselines are pytest **2295 passed / 3 Windows-only** at `422f4eb`,
and at `1639fd6` readiness **116/0**, counting **22/0**, ungrounded **24/0**,
layout audit **37/0**; G5 remains **FAIL 978px**. This checklist is an owner
task. The programme plan's active-work estimates exclude owner waiting time.

The setup and question text are being corrected where they describe retired
surfaces (`Problem Board`) or a highs-only default that no longer ships. Do not
populate an answer to a state the product does not have.

## Setup (5 min)

- `python -m screenplay_studio.webapp_server --port 8500 --projects-dir ./studio_projects`
- Open `http://localhost:8500` in Chrome.
- Pick a **substantially real screenplay** — full length. A 3-scene seed proves nothing felt.

## The session (~30–45 min, one sitting)

1. Upload + run the **first pass**. Let the Evidence dock/queue and mass strip land. (Baseline.)
2. Press **⇉ fix loop** — step 10+ findings without leaving it (N/P). Then fix 5–8 by
   hand, or mark addressed / next-pass. Make one small edit.
3. Run the **second pass**. The felt moment: the **arrival strip** appears. Stop — before
   anything else, what did you do first? (That answer is the data.)
4. Return to the loop with the new pass live. Deferred/ghosted marks should read honestly.
5. Live in the desk a while: discuss with Sameer, open the Sushruta lens, toggle dawn/night once.

## What to answer per surface

| Surface | Question | Answer | Felt note (one line) |
|---|---|---|---|
| Arrival strip | Did the numbers change how you started — or did you skip them? | | |
| Arrival strip | Did you read the **Pass** line as *your* progress, or as the analyzer's? (It compares analysis passes only — never your edits. Did the scope chip land, or did you miss it?) | | |
| Arrival strip | **"N of M addressed by you"** — did you trust it? Did it agree with what the board and cards showed? | | |
| Arrival strip | Ghosted marks: honest (never red, in no open count)? | | |
| Fix loop | Was N/P actually faster than clicking through a list? | | |
| Fix loop | Did your eyes stay on the manuscript? Dock card auto-open: help or distract? | | |
| Fix loop | Did mark / next-pass / Discuss / copy land where your hands were? | | |
| Fix loop | Esc: did leaving feel clean (dock stays open)? | | |
| Ink & filter | Default ink density (high, medium and low all admitted): right amount on the page? | | |
| Ink & filter | Peek-chip + unread dot: earned the glance, or felt like chrome? | | |
| Ink & filter | Did the page and the board ever disagree? (if yes — bug, note it) | | |
| Everything | Dawn/night both registers in a long sitting: held up? | | |
| Everything | Anything noisy, slow, or wrongly defaulted — anything at all? | | |

## What the answers decide

- **Strip**: prominence, placement (dock Evidence top), whether the scope chip earns its
  place or is noise, trust formatting, the wording of the draft clause.
- **Loop**: bar density, peek-chip timing (~4s), unread-dot persistence.
- **Defaults**: default ink density (all three severities admitted), filter state.
- **Anything felt-wrong**: file it — tuning is cheap now that machinery is verified.

## The rule

**Felt > machinery.** If a number is exact but the moment felt wrong, the moment wins —
machinery is already proven (713/713 · 30/30 · d6/d7/d10 green); this session judges the promise.
