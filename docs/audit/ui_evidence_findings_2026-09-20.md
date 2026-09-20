# UI Evidence Findings — 2026-09-20 (Playwright walk)

Captured with `tests/_ui_capture.py` (boots the studio on the demo model, seeds an
analyzed sample + an idea, walks 30 states, screenshots to `impl-shots/ui_audit/`).
Findings below are **seen in the screenshots**, not inferred from code.

## Surfaces reviewed by eye
welcome (no projects) · landing (with project) · idea canvas (blank, typed) ·
idea chat · desk + Problem Board + ink · dock Evidence lens · dawn register ·
narrow 900 / narrow 600 · narrow + drawer · command palette · spotlight ·
compare · settings.

## Not yet visually reviewed (harness blocked by the SPA's persisted view)
desk-without-analysis · analysis progress · craft shelf · dock tabs (Sameer /
Sushruta / Stash & Notes) · fix loop · beat board · revision view · focus ·
reader · river read. The steps exist and are guarded; each fails on a locator
because the app restores its previous view across `goto`.

## Defects (evidence-backed)

| # | Defect | Where |
|---|---|---|
| 1 | **Floating finding cards occlude the manuscript.** Action lines are clipped mid-word ("A stack of bla⎮"). Cards also stack over each other. | desk + board |
| 2 | **The same finding renders 4× simultaneously:** floating card + Problem Board + dock Evidence + craft-shelf header. Nothing recedes. | desk + board + dock |
| 3 | **The dock contradicts itself:** header "6 open of 6 findings" vs "FIX QUEUE — 0 SHOWN / 6 TOTAL", plus the empty-state hint twice. Root cause: default filter is `severities:["high"]` (app.js:25) while the header counts all. | dock Evidence |
| 4 | **Density collapse:** 7 filter chips + mass strip + trust readout + bar chart + scene group + fix queue + coverage in ~330px. | dock Evidence |
| 5 | **Left scene rail is cryptic:** "1 ▮ 2 3 c" — no labels; an unread badge with no context. | desk |
| 6 | **Idea canvas is a dead end.** Blank with no prompt, hint, or placeholder. | idea room |
| 7 | **Idea-room chat is not discoverable, and input is misrouted:** `c` shows a thin violet "Sameer" bar (not a composer); typed text was swallowed as *canvas content* and auto-titled the idea. | idea room |
| 8 | **Palette in the idea room offers dead commands:** Beat Board / Compare / Revision / Spotlight are project-only and do nothing there. | palette |
| 9 | **Narrow width: canvas clipped.** At 900px the premise-doctor drawer takes ~48% and the canvas runs under it. | narrow + drawer |
| 10 | **Trust readout reads as failure:** "0 of 6 quotes verified (0%)" on demo data. | dock Evidence |

## Genuinely good (do not regress)
- **The manuscript** — warm paper, Courier, lamp glow. The premium moment of the product.
- **The command palette** — clean hierarchy, real shortcut hints, the most polished surface seen.
- **The Premise Doctor's onboarding card** — genuinely useful prose explaining what to do next.
- **Dawn / night theming** and the ambient "Level 1 · Upload & Discover" step marker.

## The shape of the problem
Clutter is **concentrated in the feedback layer** (4 duplicate surfaces + text
occlusion), not the reading surface. The idea room has the *opposite* problem:
too little — a blank page with no prompt and a chat that never appears.

## Harness note
Full walk attempted 5×; each iteration fixed a real navigation constraint (app
restores its last view; idea room ↔ desk transitions; ambiguous locators needing
`>> visible=true`). Remaining blocker: holding desk state across steps. Tracked
for the next pass — the shots already captured cover the feedback story in full.
