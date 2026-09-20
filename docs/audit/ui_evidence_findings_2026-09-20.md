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

## Resolution (same day, second pass)

Each row is the state AFTER the follow-up implementation pass. "Fixed" means a
measurement moved and a check now pins it; "open" means nobody has touched it.

| # | Defect | State | Evidence |
|---|---|---|---|
| 1 | Floating cards occlude the manuscript | **FIXED** | The margin sat at `right:-18px`: 6 of 6 cards overlapped script text, worst case **164px of a 214px card** (measured with a Playwright probe at 1440x900). The margin is now in-flow by default and only claims the paper's gutter when a container query says the paper has the room — a *container* query, because the dock takes 380px without changing the viewport width, which is why the old `@media (max-width:1100px)` escape never fired with the dock open. Re-measured: **0 of 6 cards overlap, 0px**, board open and board hidden. |
| 2 | One finding renders 4× with nothing receding | **PARTIAL** | The duplicated *controls* are gone: a margin pin now carries `Locate` only, and `findingNoteEl`'s own contract ("margin pins stay read-only") is finally true — Rewrite/Discuss live on the dock's deep cards. The pin still renders alongside the board and the dock (in-context summary while reading vs. the ledger vs. the work surface), and the gutter promotion stands down while the Problem Board's absolute overlay holds that space. Text still appears on three surfaces by design. |
| 3 | Dock header contradicts its fix queue | **FIXED** | See `production_readiness_2026-09-20.md` §10 F0 — one predicate + scope labels; `phase6_evidence` 31/1 → 33/0. |
| 4 | Dock density collapse (7 chips + strip + readout + chart + queue in ~330px) | **open** | Untouched — a dock-layout pass, not a bug hunt. |
| 5 | Left scene rail is cryptic (`1 ▮ 2 3 c`) | **open** | Untouched; still needs labels/an accessible name. |
| 6 | Idea canvas is a dead end (no prompt/placeholder) | **FIXED** | The blank page now carries the onboarding as its placeholder: what to type (any shape it arrived), that the page saves itself and titles itself from the first words, and that C / Ask Sameer summons the chat. The arch review's corrected reading stood: the affordances existed, the canvas just never *said what to do first* — now it does. `phase9` pins it (16 → 21 checks). |
| 7 | Idea-room chat not discoverable; input misrouted into the canvas | **FIXED** | Both halves had code-level root causes. (a) Discovery: `updateIdeaSamPill` hid the pill on a blank page — the exact moment a first-time writer had no chat affordance at all. The pill now always stands: "Ask Sameer" as an invitation on a blank page, "Sameer" once there are words (`ideas_v3`'s pinned "pill hidden on blank" contract flipped to match). (b) Misroute: summoning the drawer never moved focus, so keys typed after `c`/pill went wherever focus sat — on the idea page, into the canvas, auto-titling the idea. `openRoomDrawer` now hands the keyboard to the composer (guarded so the project's composer-less feedback room focuses nothing). `phase9` pins both: cursor in `#input` after `c`, and post-summon keystrokes land in the composer while the canvas is untouched. |
| 8 | Palette offers project-only commands in the idea room | **FIXED** | §10 F10 — hidden without a project; a duplicate `b` binding removed; 2 new checks in `phase9` (14 → 16). |
| 9 | Narrow width: canvas clipped under the panel drawer | **open** | Untouched (the panel drawer's 48% claim). The margin itself no longer overlaps at narrow widths — that half is defect #1. |
| 10 | Trust readout reads as failure (`0 of 6 quotes verified`) | **FIXED** | `no_quote` findings no longer sit in the denominator; with nothing checkable the readout says "N findings carried no quote to verify" instead of 0%. |

**Regression cover added this pass:** `phase13_legacy_cleanup` gained 6 checks
(26 → 32) — a live geometry guard that no margin pin may intersect a line of
script, that a pin carries no judgment controls, and that the gutter column only
appears when the board's overlay is gone. `test_production_readiness.py` pins the
source contracts behind them (in-flow default, container query, the `!opts.pin`
gate), so the layout cannot silently slide back over the text.

**Regression cover added this pass (idea room, third pass):** `phase9` gained 5
checks (16 → 21) — the placeholder prose, the blank-page "Ask Sameer" invitation,
the label flip once words land, cursor-in-composer after `c`, and post-summon
keystrokes landing in the composer with the canvas byte-untouched. `ideas_v3`'s
"pill hidden on blank page" check was re-pinned to the new standing-invitation
contract (12 → 14 checks). Suites re-run green after the change: phase9 21/21,
ideas_v3 14/14, ui_fixes 19/19, spark_wall 22/22.

## Harness note
Full walk attempted 5×; each iteration fixed a real navigation constraint (app
restores its last view; idea room ↔ desk transitions; ambiguous locators needing
`>> visible=true`). Remaining blocker: holding desk state across steps. Tracked
for the next pass — the shots already captured cover the feedback story in full.
