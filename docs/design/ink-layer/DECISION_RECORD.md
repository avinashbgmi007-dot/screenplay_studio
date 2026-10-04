# Ink Layer — decision record and state of the build

**Status, 2026-10-04 (`main` @ `2a49efb`): the direction is agreed; the live app has not migrated.**

How to read this. **Agreed** = agreed with the owner. **Open** = needs an owner decision, and says what waits on it. **Proposed** = a recommendation, not a decision. *Verified* = checked on a running desk on the date above. *Untested* = no evidence yet. This record paraphrases the external architecture review that this repo calls "the Ashna verdict" (see `OPEN_QUESTIONS.md`, `SELF_CRITIQUE.md`); it does not reproduce it.

## 1 · What was agreed

1. **Agreed — the architecture.** The Ink Layer (the "Living Palimpsest") is the architecture for the **manuscript room's critique loop**: read → inspect → choose scope → generate → compare → refine and accept → apply and recover → reassess, at the affected passage, in one column. Rehearsal (an Original / Proposed audition) is an optional comparison mode inside it. Root System and Story River are **deferred** until an observed writer need justifies them.
2. **Agreed — the principle.** Keep the writer in the passage, make the reasoning inspectable, and make every change deliberate and reversible.
3. **Agreed — a rejected metric.** "Zero-Travel" (0 px of attention travel, one surface, at most one stroke) is **not** a UI metric: it rewards fewer keystrokes over understanding. The measure is low reorientation cost and *deliberate* acceptance, with speed read together with comprehension and error rates.

## 2 · What the decision does not cover

It covers one loop on one manuscript and says nothing about the rest of the product. The prototype has no answer for:

* the Context Dock's other lenses — Sameer, Sushruta, Stash & Notes — and the co-write rooms;
* the selection floats (Ask Sameer · Stash · Note). The prototype's own mechanism for these, "the writer's own ink" (select → Note / Stash / Ask), was specified and **not built**;
* the welcome desk, library, idea canvas, spark wall, Revision / Compare / Beat Board / Reader / Flow, the status strip, the command palette and session restore. `docs/REDESIGN_MASTER_PLAN.md` §1 inventories 18 protected surface rows; the Ink Layer addresses one of them.

**Open (owner):** where each of these lives in an Ink-Layer-first product. Until that is answered, "retire the dock" is not a coherent end state.

## 3 · Corrections adopted from the review, and where each stands

| Correction | Prototype (`webapp/preview-ink-layer/`) | Live app | Evidence |
|---|---|---|---|
| Separate a finding's identity from its text location; use scene context; never silently attach to a questionable occurrence | `anchorFinding`: exact / loose / ambiguous, no silent guesses | The id carries the scene's slugline key; a stored mark that covered several findings is **held aside**, never spread (D1) | `SELF_CRITIQUE.md` §6.1; `tests/test_finding_id_scene_key.py`; *verified*: 16 findings → 16 distinct ids, the nine same-words findings → 9 ids (was 1) |
| A stale proposal is refused, never silently applied | the refusal is a *state* in the fold (`data-cast="stale"`) | `POST /edits/apply` refuses the whole call with `400 {error, stale: true}`; `/rewrite` offers only frames that still stand; the rewrite loop stops offering the action | `tests/test_stale_proposal_guard.py`; *verified*: a stale frame → 400, and `edits.json` / `working.json` stayed byte-identical |
| Unknown rewrite-response shapes fail clearly | `normalizeRewrite` returns `{unknown, reason}` and casts nothing | — (the live loop reads the route's own contract) | `SELF_CRITIQUE.md` §6.1 |
| Offer scene / category / status selection; do not ghost the screenplay | `F` cycles all → scene → category → status; the walk follows it; prose is never dimmed | the filter row already offers severity, category and scene | `SELF_CRITIQUE.md` §6.1; `docs/UI_UX_SPECIFICATION.md` §4.9 |
| Refuse *automatic* targeting only; allow explicit selection with the warning kept | `R` on the writer's own selection | — | `SELF_CRITIQUE.md` §6.1 |
| Every change deliberate and **reversible** | apply and undo — but **no mark, unmark or defer control**: its only server writes are apply, undo, dismiss and rewrite | `Reopen`, the `Addressed N` chip and the ✓ on the card (D2-a) | *verified* on both |
| Keep evidence-location status, backend "addressed" status and the writer's judgment distinguishable | its row state separates "dry because the fix landed" from "dry by the writer's choice" | the strip labels the writer's number "addressed by you" and puts observation beside it ("no longer flagged", "carried no quote", "from the last run, not your edits"). **Not shown:** the observed-status triple of the *marked* findings, and a per-row "you marked it, the page still shows it". `/metrics` still reports `findings_fixed = total − open` and does not serve the `last_analysis_ts` that `metrics.json` already stores | `app.js` `buildArrivalStrip`; `metrics.py` `summarize` |
| Defer the graph; offer "visit related passage" with a way back | `O` visits the cited passage and returns; Root System and Story River deferred | — | `OPEN_QUESTIONS_ANSWERS.md` Q9 |

## 4 · Claims in the first verdict that this record supersedes

The first verdict is kept outside this repo. Where it disagrees with this table, this table wins.

| The first verdict said | Today |
|---|---|
| Stale-proposal protection: **Closed** | The server half did not exist. It was closed on 2026-10-03 (#7) and *verified* on 2026-10-04. |
| Persistent anchors: closed as a design decision | Identity now carries scene context (D1). Anchoring is quote-derived with an explicit ambiguity state. A finding with no quote is keyed on its own words, so when the model re-words it the id changes, by design — an id does not "survive re-analysis" unconditionally. |
| "60 tests green", "hard parts proven" | Reported prototype results. The pure suite passes 62/62 (*verified* 2026-10-04, Node 20); the DOM suite needs `jsdom` and was **not run**. The alignment pass found real defects, four of them invisible to the tests (`SELF_CRITIQUE.md` §6.2). |
| "Cheapest delta from the shipped substrate" | **Unmeasured.** The prototype shares no code with the live app, which has 18 protected surface rows and a 59-suite browser gate. |
| Zero-Travel as the success criterion | Rejected (§1). |
| The severity threshold `[ ]` as the answer to scale | The threshold may soften *critique marks* only, never the screenplay's text; scene / category / status selection is the other half. |
| Refuse any rewrite when evidence is unverified | Refuse *automatic* targeting only. |

## 5 · Where things are

* **The prototype** — `screenplay_studio/webapp/preview-ink-layer/`, served at `/preview-ink-layer/index.html?project=<name>`. A separate document: nothing in the live `index.html` or `app.js` links to it (*verified*: 0 references). It reads the live API and writes only through `/rewrite`, `/edits/apply`, `/edits/undo` and `/findings/<index>/dismiss`.
* **Design docs** — this folder. `INK_LAYER_SPATIAL.md` is the blueprint (invariants I1 *one scroller*, I2 *one keyboard owner*, I3 *critique never occupies space of its own* — "there is no findings list, and there cannot be one"); `SELF_CRITIQUE.md` §6 is the alignment ledger; `OPEN_QUESTIONS_ANSWERS.md` holds the answers; `backend-patches/README.md` records the contract the prototype needs from the desk.
* **Backend contracts** — `revision.py` (`StaleProposalError`, `_assert_proposal_is_fresh`, `proposal_is_landable`) and `webapp_server.py` (`/edits/apply`, `/rewrite`).
* **Identity and marks** — `screenplay_parser/scenekey.py`, `revision.py`, `webapp/core.js`, `webapp/app.js`.
* **The live app** — unchanged in architecture: scene rail + manuscript + a docked Context panel.

## 6 · Two axes that are still open

1. **Migration path (architecture).** **Open**; a path is **Proposed** in §7.
2. **Visual language.** `docs/REDESIGN_MASTER_PLAN.md` §4 is still open: Nocta (A), or Midnight Desk (B — the shipped look, frozen as Tungsten). The prototype adds a third, **Detent** (`detent.css`), whose laws are in its header: prose is never dimmed; colour separates ink *state*, never severity; severity is width plus solid ▪ blocks; evidence is a 1-px lit filament; no fills behind text; the fold is an inset slot, not a card. These differ from Tungsten's treatment (glowing severity dots, glass cards), so adopting Detent in the shipped shell means unfreezing Tungsten. **Open (owner, taste).**

## 7 · Proposed path (not decided)

1. Scope the Ink Layer to the critique loop and enter it by **route** — a first-class document — not by an in-app toggle. The Ink Layer forbids chrome, and its invariants (one scroller, one keyboard owner, critique never in a region of its own) cannot hold inside the shell, which has several scrollers and many key handlers. The shell keeps the other lenses and rooms.
2. Make the prototype un-rottable first. Separate lab documents have broken silently when the platform moved under them: `webapp_server.py` records that all six `preview-next` labs "died on `missing or invalid capability token`" when the browser harness stopped booting with `--no-token`. Neither of the prototype's suites is a CI gate today. Running its dependency-free suite (62 tests) is one added step in the `test-js` job — `node --test screenplay_studio/webapp/preview-ink-layer/tests/core.test.mjs`. Whether to adopt `jsdom` for its DOM suite is a separate tooling decision, because the repo has no `package.json`.
3. **Design, do not build,** what is missing: mark / unmark / defer ("two inks"), the writer's own ink, and navigation between the Ink surface and the desk.
4. Validate (§8) before deciding the dock's fate.

## 8 · Validation still owed

1. **A run against a real model** (not `--demo-model`). The prototype's real-script pass used the demo model — `REAL_SCRIPT_RESULTS.md` says what remains open "is only the demo-vs-real *model*" — and the collision that motivated D1 (nine identical findings) is template output of the demo model.
2. **The review's quality gates for the Ink Layer — all *untested*:** change comprehension; productivity; scale and accessibility (a full-length script with dense findings; keyboard and screen reader; whether marks that rely on width and wash can be found); and creative authority (disagree, defer, dismiss, rewrite by hand — the prototype has no defer).
3. **The prototype's DOM suite** — needs `jsdom`; not run in the 2026-10-04 pass.
