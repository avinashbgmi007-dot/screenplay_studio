# Critique — the two-agent Feedback-Room Panel

**Date:** 2026-10-15 · **Reviewing:** the "Both agents reported" synthesis (architect + veteran writer,
12 agreements, 5 clash rulings, 18 + 18 pointers, self-critique)
**Reviewer stance:** adversarial. Every claim below was checked against this checkout at a cited line.
Claims that survived are credited plainly. Claims that did not are shown with the arithmetic.

---

## 0. Provenance, and how this differs from my panel

Not mine. Structurally a different panel: two agents (architect, veteran writer) against my four
(end-user advocate, its critique, architect, veteran writer). The casts overlap by two; the rulings
differ on three load-bearing points. I cannot confirm which model produced it or when, only that it
is not the work I did in the previous turn. Where we agree I say so. Where we differ, the
differences are the useful part.

**Headline: the analysis is good, and it has one fatal arithmetic error that also exists in my own
document.** I am leading with that because it invalidates a headline recommendation on both sides.

---

## 1. What it got right, and I want that on the record

Before the defects, the parts that survive contact with the source:

| Claim | Status |
|---|---|
| Tier 1 buries the first action under substantial preamble | **Confirmed.** `app.js:6517-6560` stacks arrival strip → ambiguous-marks notice → filter row → scene box → queue. The `renderTier1Worklist` comment itself records the earlier regression: *"the writer landed on a ledger of eleven closed headers with the answer hidden behind a click."* |
| The deep card is a ~15-atom wall | **Confirmed, approximately.** `findingNoteEl` (`app.js:5171`) builds 13 `el()` atoms in the top block, plus a separate `.finding-deep` disclosure and a `.finding-note-actions` row carrying its own measured `<=30px` budget (`app.js:5246`, `app.js:6461`). "15" is a fair count. |
| One finding renders in several places | **Directionally right, numerically loose.** Five `findingNoteEl` call sites exist (`app.js:5628, 5779, 6620, 6632, 6686`) but the prior audit already **deleted** the fourth *surface* (the legacy panel, `index.html:450`). Call sites are not surfaces. |
| Seven counters answer "how much is left" | **Confirmed in spirit.** Counts live in the arrival strip, the filter row chips, the queue header, the desk toolbar chips (`finding-summary`), the status strip metrics, the dawn meter (`app.js:4447`), and the revision strip. Seven is fair. |
| The dawn meter is a real component | **Confirmed.** `app.js:4447`, `app.js:4448` (its own title string), `style.css:4952`. The naming collision with the Dawn *theme* is genuine: one word, two meanings. |
| `voice` / `subtext` are stale labels | **Confirmed.** They sit in `CATEGORY_LABELS` (`app.js:4235`) but appear in neither `ALL_CATEGORIES` (`pipeline.py:847`) nor `FINDING_CATEGORIES` (`grammar.py:45-48`). |
| Evidence must never be hidden | **Agreed, and this is the panel's best idea.** It inverts the standard "progressive disclosure everywhere" instinct, and it is right: doubt is not a detail. |
| Truth axis and intent axis must stay separate rows | **Confirmed as an existing design invariant.** `app.js:5262-5264` already implements it: *"The accuracy meter is computed from THIS row and nothing else, so it is a SEPARATE row asking a SEPARATE question from the intent row."* This panel rediscovered a rule the code already holds. |

That is a genuinely strong list. Seven of thirteen checked claims survive.

---

## 2. D1 — The 44rem dock is illegal. Both panels broke it.

**This is the fatal one, and my own document proposed the same thing.** Both panels recommended a
mode-aware dock at **44rem for triage** (my agreement #8, their implied Tier 1 rewrite). That number
fails an existing, enforced, seeded layout gate.

The law, `tests/e2e_browser_layout_audit.py:442-447`:

```python
CHECKS.ok("manuscript keeps majority width with dock open",
          bool(widths) and widths["pane"] >= 0.5 * widths["app"] - 2, ...)
```

`widths["pane"]` is `#manuscript-container` (`layout_audit.py:423`) — the box that actually moves, not
the workspace row that contains the dock. The gate is sound. The audit's own comment records the
measured baseline:

> *`#manuscript-container` does move: 1394 closed → 1014 with the 380px dock open, i.e. 70% of the
> viewport.* (`layout_audit.py:440-441`)

**The arithmetic:**

| Quantity | Value | Source |
|---|---|---|
| app width at the audit's viewport | 1440 | `layout_audit.py` comment |
| dock open | 380 | `style.css:5507` |
| pane with dock open | 1014 | measured, `layout_audit.py:441` |
| pane + dock (constant) | **1394** | derived |
| floor: `0.5 × 1440 − 2` | **718** | gate formula |
| **max legal dock** | **676px** | 1394 − 718 |

**44rem = 704px → pane = 690px → 47.9% → the gate fails.**

The legal ceiling is **676px (42.25rem)**, and at 676px the manuscript sits *exactly* on the floor
with zero slack for the scene index. So the honest conclusion is:

> The dock cannot grow meaningfully. A triage dock at 44rem is not a design decision that needs a
> ruling, it is a number that fails CI.

This kills the geometric premise both panels built on. And note what it implies architecturally:
**if the ledger cannot get wider, the page and the ledger cannot be separated by width.** The only
remaining separation is *time* (a mode switch) or *layer* (the dock overlays and the page dims behind
it). Neither panel considered either. This is the real design space and both panels walked past it.

Slack note: the 46px gap between 1394 and 1440 is the scene index plus gaps, and I have not
re-measured it at a different viewport. The conclusion is robust across that uncertainty — 676 vs 704
is a 28px miss, not a rounding error.

---

## 3. D2 — Agreement 12 regresses a verified fix that has 21 test assertions

Their agreement 12: *"category chips leave the filter and become list group headers."*

That is not a presentation change. **Category-as-filter is a verified bug fix with a live test
contract.**

- `docs/FULL_FEEDBACK_AUDIT_VERDICTS.md`, **GAP-1**: the severity/category filter drove ink and the
  fix loop but *not* the board list, so the page showed 15 cards while the queue showed 9 rows. The
  fix introduced **one** predicate, `findingPassesFilter(f, index)`, behind ink, board list, loop and
  queue, verified end-to-end at "d8 end-to-end on gun_pen: cards 0→11→4→15→3 tracking the chips,
  queue rows in lockstep, **category narrows both surfaces** — 14/14 checks pass."
- The by-category dock section carries **21 references** in `tests/e2e_browser_dock_sections.py`
  alone (`28` across the suite), pinned to `.dock-section[data-key="by-category"]` and
  `.dock-cat-group`.

Moving category from a filter into a group header either (a) **deletes category filtering**, which
reopens GAP-1, or (b) makes headers clickable filters, which is a *different control* wearing the
old name. Neither option is stated. The panel ruled on it as if it were a header-typography decision
when it is a predicate-ownership decision.

**The rule the panel missed:** in this codebase a category chip is not a label, it is a predicate
argument. Anything that changes what it *filters* needs its contract named, not a ruling.

---

## 4. D3 — "Unproven until someone measures" is answerable today

Their self-critique, item 2: *"the net-pixel-reduction claim is unproven until someone measures Tier 1
height before and after."*

They framed missing measurement as outstanding future work. It is not. **The measuring instrument
already exists, already seeds an analyzed desk, and already gates the dock.**

`tests/e2e_browser_layout_audit.py` is a DOM-geometry audit (no screenshots, by project convention)
whose own docstring lists: *"9. GO 2 contracts — FV fold, dock width law, fix-loop keys"*, and whose
seed function uploads `fixtures/pain_tenglish.fountain` and **runs a real analysis** so the fix loop
and dock laws have findings to assert against. Its header also records a prior version of this exact
class of bug:

> *"Without a project, sections 8 and 9 recorded nothing at all: every check in them sat behind
> `if cards.count()`, so the 'manuscript never drops below half' law and the fix-loop contract
> stopped being asserted while the suite still printed PASS."*

So the project already knows that **a geometry claim nobody measures is a claim that silently stops
being true**. Tier 1 height before/after is a new check in a suite that is built to take it.

**Correction to my own panel, which made the identical error:** my document also said the net-pixel
claim was unproven and recommended someone measure it. Both panels described the work as undone when
the harness to do it was sitting in `tests/`.

*Limit:* I could not run it. `pip install playwright` is blocked by PEP 668 on this box, and the
venv path failed on the chromium download. So I have not executed the measurement myself. I am
pointing at the instrument, not pressing the button.

---

## 5. D4 — "continuity/formatting" is not a vocabulary the data model shares

Their architect pointer 9 and agreement 6: *"render `continuity/formatting` deterministic rows grey
with no verdict row."*

These two things live in different taxonomies:

| | `continuity` | `formatting` |
|---|---|---|
| Kind | **finding category** | **pipeline stage + dock section** |
| Declared | `grammar.py:46`, `pipeline.py` | `pipeline.py:1308-1311`, `app.js:6909` |
| In `CATEGORY_LABELS`? | **Yes**, `app.js:4235` | **No** — absent from the map entirely |
| Emits findings? | Yes | It is a stage; whether it emits is not evidenced here |

`CATEGORY_LABELS` has ten keys: theme, character, structure, dialogue, scene_function, plot_thread,
genre, voice, subtext, continuity. **`formatting` is not one of them.** So "grey the deterministic
rows" is not implementable as phrased: `continuity` findings would fall through to
`CATEGORY_LABELS[f.category] || f.category` (`app.js:5179`) and render as a raw key, and `formatting`
rows do not exist as findings to grey.

Implementing this requires a decision the panel never made: **does `formatting` become a finding
category, or does the formatting dock *section* get row-level treatment?** Those are different specs
with different store implications. As written it will ship as a half-applied CSS rule.

---

## 6. Where my panel was weaker, stated plainly

Self-serving comparison is worthless, so, honestly:

- **Their separation of truth from intent beat mine.** I never raised it. It is already a coded
  invariant (`app.js:5262-5264`) and neither panel defended it. They did.
- **Their "evidence never behind hover" rule is stronger than anything I proposed.** I moved
  confidence decimals to hover in my agreement #6 without noticing I was doing the thing they were
  right to ban.
- **Their challenge-1 ruling (keep three verification flags, demoted below the issue) is better than
  my "demote in rank" agreement #6.** Mine collapsed craft impact and verification into a sort order.
  Theirs keeps them *visible* and only demotes their position. Mine was closer to the architect's
  rejected "single read-carefully flag" than I admitted.
- **Their two-agent structure produced a tighter document.** My four-agent panel produced sprawl.

---

## 7. The Top-5 ranking function, which both panels left undefined

Their self-critique is correct that "structural > character > scene > dialogue" is a slogan. Here is
an algorithm buildable from fields that already exist. Every input below is already on the finding
object (`grammar.py:52-75`) or in an existing store (`CONTEXT.md`: `dismissed_findings.json`,
`finding_intents`, `findings_status`).

```
score(f) = IMPACT[f.category] × 10
         + (f.verification_status == "verified" ? 3 : 0)      # unverified sinks, never hides
         + (min(len(f.scene_refs), 3) - 1)                    # multi-scene = systemic
         - (f.check_id ? 10 : 0)                              # mechanical checks batch out
         + (writer_intent(f) == "fix" ? 5 : 0)                # sticky, see rule 5
```

1. `IMPACT` is a **hand-authored constant table**, one line per category, living next to
   `CATEGORY_LABELS` (`app.js:4232`). It is a judgment, stated as data, reviewable in a diff. That is
   the entire difference between a slogan and a ranking function.
2. **Verified quotes outrank unverified at equal impact.** Never hides, per `AGENTS.md:66`.
3. **Multi-scene findings outrank single-scene.** A note about scenes 1 and 4 is systemic; one about
   scene 4 is local. `scene_refs` already carries this.
4. **Mechanical checks sink regardless of impact.** Anything with a `check_id` (`app.js:5241`) is free
   and deterministic, so it should batch to the bottom, not compete with craft notes.
5. **Writer intent is sticky and is never re-ranked.** A finding marked fix/park/dismiss keeps its
   position. Re-sorting a list under a writer's feet mid-session is how trust dies.

The output is an ordered, explainable queue: every row can print *"ranked high because Impact 5,
verified, spans 3 scenes."* That string is the acceptance test, and it is the thing the panel should
have written down.

---

## 8. The question actually put to me: one layout, or a density toggle?

**One layout. No toggle. Three reasons, all grounded.**

**1. Your own persona rules forbid it.** `docs/USER_PERSONAS.md`, derived design rule 1: *"One writer,
many modes — the three personas are the same person at different stages; **never build role-based
UI**."* A "veteran mode vs guided mode" switch is role-based UI, keyed on identity. It is ruled out
by the repo's own IA doctrine before aesthetics enter.

**2. The geometry gate would have to run twice.** `e2e_browser_layout_audit.py` gates one geometry
per law (the docstring's "GO 2 contracts"). Two density modes means every law measured twice, every
seed re-run, and a gate that passes when the modes disagree. This is how the suite already got
audited once: *"the suite still printed PASS"* while asserting nothing.

**3. The need is real but it is not identity-shaped.** What the panel correctly identified is that a
*1am working rewriter* needs collapsed rows and a *first-time learner* needs expanded cards. But that
is not a persistent trait, it is **where you are in the loop right now**. Same person, two minutes
apart.

So: one layout, one density, and **depth follows work state, not persona.**

| State | Default row depth | Why |
|---|---|---|
| Analysis just landed | expanded — quote + rule visible | you have not read this script yet; you need the reasoning |
| Fix loop engaged (`N`/`P`) | collapsed — one line, four verbs | you are doing, not reading; expansion is opt-in |
| Revision view | collapsed + addressed rail | the work already happened; the row is a receipt |

That gives the panel's evidence-preservation win (expanded cards on arrival) and the rewriter's
speed win (collapsed rows in the loop) with **one layout, zero mode state, zero extra gate runs.**
It is also the only option that survives finding D1, because it never asks the dock to get wider.

---

## 9. Critique of this critique

1. **I have not run the suite.** Playwright is blocked here (PEP 668; venv chromium download failed).
   My D1 arithmetic is derived from the audit's own recorded measurements, not a fresh run. If a
   real run shows `app` wider than 1440 at the gate viewport, the ceiling rises proportionally and
   D1's margin shrinks. The *direction* survives; the exact 676px does not deserve to be quoted as
   precise.
2. **D2 may be a false alarm.** If group headers are made clickable filters over the same
   `findingPassesFilter` predicate, agreement 12 is legal and the 21 assertions still pass. The
   critique is that the panel **did not say so**, not that it cannot be done. I have stated it as
   "unstated predicate-ownership decision," which is the accurate charge.
3. **D4 could be a transcription artifact.** The panel's text shows repeated character-dropping
   (`themegenre`, `contestedidentity?ungrounded`, `continuityformatting)`), so `continuity/formatting`
   may be mangled formatting rather than a taxonomy error. I flag the ambiguity; I do not claim to
   have caught a hallucination.
4. **I am reviewing a document that criticizes mine.** Sections 6, 8 and 9 exist because that
   asymmetry is unavoidable. Where we differ I have tried to give the code rather than the opinion,
    and twice the code sided against me, which is the only bias check I can offer.
5. **The recommendation is now "do less," not "do more."** My critique removes the geometric premise
   from both panels. That leaves their 12 agreements standing minus the ones resting on it, which is a
   thinner output than either panel promised. That is the honest result of checking.

---

## Verdict

**The synthesis is strong work with one fatal arithmetic error.** Seven of thirteen spot-checked
claims survive. The evidence-visibility argument is better than mine and should be adopted. Agreement
12 is unstated about predicate ownership. The `continuity/formatting` ruling mixes two taxonomies.
And the geometric recommendation fails an existing CI gate at 676px max dock width, which means both
panels answered a question the layout law had already closed.

**Adopt:** agreements 2, 3, 4, 7, 8, 9, 10, 11, 12. **Drop:** the dock-width premise. **Rewrite:**
agreement 12 with a predicate contract, agreement 6 with a real category boundary.

**Start with:** the section 7 ranking function as one constant table beside `CATEGORY_LABELS`
(`app.js:4232`), and a Tier 1 height check added to `tests/e2e_browser_layout_audit.py`, which
already seeds an analyzed desk and already gates the dock.

**STATUS: DONE_WITH_CONCERNS.** Concerns: measurement instrument identified but not executed
(no browser available in this sandbox); D1 margin rests on a recorded baseline rather than a fresh
run; D4 may be a transcription artifact; and `docs/REAL_WRITER_VALIDATION.md` still holds, namely
that none of this has been felt by a writer yet.