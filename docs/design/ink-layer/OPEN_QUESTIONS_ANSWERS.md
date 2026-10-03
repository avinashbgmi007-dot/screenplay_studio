# Recommended answers to the open questions — and the case against each

The companion to `OPEN_QUESTIONS.md`. That file records *what is unsettled*; this one commits to an
answer for each, says why, and then argues the other side: the strongest counter-case, what would
falsify the recommendation, and what it costs if I am wrong. Where the recommendation is weak I say
so in the recommendation itself rather than burying it in the critique.

**Read first, before any of this is acted on.** Three sources I had not decoded when
`OPEN_QUESTIONS.md` was written are now extracted into `extracted/` (`API_ROUTE_MAP.md`,
`ARCHITECTURE.md`, `PRD.md`, via `tools/odf_extract.py`). They change three of the answers, and they
retract one of my earlier concerns. What they establish:

| Fact | Source | Effect on these answers |
|---|---|---|
| `POST /findings/intent/batch` exists, takes `{intents: {finding_id: intent}}` (500 max), persisted to `finding_marks.json` | route map | **Q8 can be answered with a route that already exists** — the by-choice mark can be made durable without inventing anything |
| `POST /findings/<index>/undismiss` exists; dismiss is described as "triage away (restorable)" | route map | the keep-by-choice decision is **reversible on the desk**, which is what the agreement's "every change deliberate and reversible" needs |
| `/findings/summary` returns `verification: {verified, not_found, no_quote}` | `contracts_UI` §2.B | my build collapses a **three-state** vocabulary into one boolean — a real gap in *my* code (new item, §12) |
| `/findings/summary` returns `by_severity: {high, major, medium, low}` — four bands | `contracts_UI` §2.B | the only severity vocabulary any document states is a **report band**, not a mark; Q1 sharpens |
| The setup/payoff ledger returns `{setup, kind, setup_scenes, payoff_scenes, status: paid\|dangling\|abandoned\|red_herring}` and its dangling/abandoned rows fold into `plot_thread` findings | architecture | Root System's door is **closer than I assumed** (Q9) |
| `fixqueue` is a severity-sorted worklist carrying dismissal and addressed state | route map | severity **ordering** is a product-level contract, not a rendering preference |
| `/rewrite` accepts an optional `instruction` ("Make the dialogue tighter.") | `contracts_UI` §2.C | the route can be driven by the writer's own direction; my surface deliberately does not use it (§11) |
| `lumen.html` is "Lumen — Studio UX v3", a glass-depth skin | the file itself | it is one of the **rejected directions**, not product evidence; I stopped reading it there |

---

## 1 · The two severity vocabularies

**Recommendation.** Treat them as two different things and stop pretending otherwise.

1. **Marks read findings only.** The page draws from the per-finding `severity` field; `by_severity`
   in the summary is a *report band* and must never reach a drawing path. `normalizeSummary` should
   say so in its own comment, because the temptation to draw from a pre-counted map is exactly how
   the 0 px defect happened.
2. **Pin the finding vocabulary at the wire** — `critical | major | minor`, the three weights this
   project's design system draws (`architecture_brief.html`, `palimpsest/DESIGN_SYSTEMS.md`,
   `detent.css`). Keep `SEV_ALIAS` for one release as a transition shim, then delete it.
3. **If the desk emits `medium` and `low` distinctly, say so on the page** rather than silently
   collapsing them to one mark. A one-line statement in the fold (`low → minor`) is what the build
   already does for `high → critical`; extending it costs nothing.

**Why.** The only severity value set any document states is the summary's four bands. The findings
payload's own vocabulary appears in none of the three documents I now have, so the demo's three
weights come from this project's design system, not from the wire. That means a shim is currently
load-bearing for something nobody has written down — which is precisely the state in which the alias
rot quietly.

**Self-critique.** The weakest joint is step 2's premise: I am recommending a *wire* change from a
client repository, on the inference that the desk intends three weights because the design draws
three. If the desk really has four finding weights, then `medium → minor` and `low → minor` are a
**lossy** collapse: two distinct weights would draw the same 1 px rule, and the writer could not see
the difference. My alias table makes that loss invisible, and invisible loss is the failure mode this
whole pass was about. Falsifier: one `GET /findings` payload showing `medium` and `low` as distinct
finding severities. Cost if wrong: a second vocabulary must be either drawn (a fourth width) or
stated, and the alias table grows a comment instead of shrinking. Reversible: yes, one table.

## 2 · The strip: ledger first, or proposal first?

**Recommendation.** Keep **ledger → takes → scope → reason → keys**, and treat the order as a
one-line decision that a writer test can overturn. If a single writer says the ledger delays the
proposal, swap the first two children; nothing else depends on the order.

**Why.** Position is what an audition needs: "take 2 of 3" is the fact that makes the list legible
as a list, and it is one line of small type, not a rationale. The rationale is emphatically after the
takes — and that part is not in question.

**Self-critique.** This is the **least evidenced recommendation in the list**. "The ledger makes the
list legible" is a rationalisation I cannot test with zero users; the realistic failure is ceremony —
a line of letterspaced instrument type standing in front of every proposal for a writer who already
knows how many takes there are. The counter-design (ledger at the end, with the keys) loses only the
"where am I" fact, and loses it in the one moment it is most useful. I have no measurement either
way; I am recommending a coin-flip I already called. Falsifier: three writers reading both orders
cold. Reversible: yes, one line.

## 3 · An ambiguous quote is cast, with the warning kept

**Recommendation.** Keep warn-and-cast, **state which occurrence** ("the first of the two"), and rely
on undo for the mistake. Do **not** build an occurrence ring yet; build it only if writer tests show
misfires.

**Why.** Refusing would block legitimate work on a line that repeats a phrase for effect — and the
repetition is visible in the passage the writer is looking at. Naming the occurrence converts a
warning into a fact, which is the difference between "be careful" and "here is what will happen".

**Self-critique.** "Rely on undo" is doing a lot of work in that sentence. The commit closes the fold
and removes the strip, so the only evidence of a misfire is the line itself — and if the writer does
not look, the mistake survives until they re-read that scene. An occurrence ring (`J`/`K` over the
occurrences *inside* the frame, before the take ring) is the honest fix and is small — a second ring
over spans `targetSpans` already computes — but it is a new modal layer inside the one interaction
that already has three (`ring`, `rehearsal`, `editor`), and every extra layer is a new place for the
state machine to lie. Cost if wrong: a writer applies a change to the wrong occurrence and blames the
instrument. Reversible: yes.

## 4 · `Escape` inside the editor abandons the edit, not the line

**Recommendation.** Keep the two-step, and **spend one string** making the first step forecast the
second: *"Edit abandoned — the proposal is still open. Escape again keeps your line."*

**Why.** The rule protects the only irreversible act in the surface (a decision about the
manuscript). The cost of the rule is that a writer who expects one `Escape` to end everything gets a
half-exit; the string removes the surprise without weakening the rule.

**Self-critique.** Two `Escape`s is a modal-irritation pattern and I know it. The alternative
(read `Escape` as "leave the whole exchange") is *destructive* — it would dismiss the finding on the
desk from a keystroke the writer pressed to get out of a text field — so the honest choice is between
an irritation and a hazard, not between two irritations. The real question this dodges: **is `Escape`
doing too many jobs in this surface?** It peels cast → fold → focus → all folds, and now also the
editor. If a writer test shows `Escape` confusion, the fix is to move "keep the original" to an
explicit key (`X`?) and let `Escape` be purely "close the innermost thing" — a real change to the
keymap's spine, which I would not make without evidence. Reversible: yes.

## 5 · Post-commit comparison — I am withdrawing the concern

**Recommendation.** **Do nothing.** The receipt for a written fix is the line itself, the row's
dry-by-evidence ink, and the desk's own addressed finding; the record of *which* take was applied is
in the undo stack. Document the option (a read-only "spent" strip on re-opening the fold) but do not
build it.

**Why.** I listed this as a gap in `OPEN_QUESTIONS.md` §5; on reflection the gap is smaller than the
cost of closing it. A "spent" strip means the fold can show two visually similar states whose
difference is whether they accept input — in a surface whose entire discipline is that state and
appearance agree. The strip currently disappears because the frame it was cut from no longer exists
on the line; that is honest. Adding a second, inert strip is adding a fiction to avoid a small
inconvenience.

**Self-critique.** Withdrawing a concern is easy to dress up as discipline. The counter-case is real:
writers *do* re-read what they just did, and today the only way back is undo (which reverses the
edit, not merely shows it) or a fresh `J` (which asks the desk again). If writer tests show "what did
I just do?" as a recurring question, the spent strip is the right answer and this recommendation
should be reversed. Note the asymmetry: reversing *this* recommendation is cheap; shipping it and
being wrong is expensive. That asymmetry is the whole reason it is the recommendation. Reversible:
yes, trivially — which is why it is worth deferring rather than arguing about.

## 6 · The walk follows the filter; the arrows do not

**Recommendation.** Keep the asymmetry. Add **one clause** to the landing announcement when a filter
or threshold is active: *"…· the reading is narrowed."* — so a writer who wonders where the other
findings went is told, in the moment they arrive somewhere unexpected.

**Why.** `n` means "the next critique that is speaking up"; `↑↓` means "the next line of the script".
Two questions, two answers, both stated. Receding is the same channel the ink threshold already uses,
so nothing here is a new idea — only its reach changed.

**Self-critique.** Transient copy is weak compensation for a hidden state: the no-chrome rule means
the annunciator is the *only* channel, and it forgets. So the honest description of this
recommendation is "a tolerable wart, documented", not "solved". The alternative — `n` walks every wet
row regardless of the filter — makes `n` contradict the filter the writer just set, which I believe is
worse, but I hold that belief without evidence. Falsifier: a writer filtering to a scene and then
being unable to find a blocking finding they know exists in it. Reversible: yes, one predicate.

## 7 · A visit leaves no mark on the page

**Recommendation.** **Do not build a visual mark.** The arrival sentence already names the return
(*"Press O to come back to where you were reading."*), which is the part that matters. Instead:

* keep the return in the announcement, and repeat it in the annunciator when the writer lands
  anywhere else while a visit is outstanding (they were taken somewhere; say that they are still in a
  visit and how it ends);
* make the *return* reachable after an interruption — today `O` is claimed by casting while a
  proposal is open, so a writer who starts casting from the visited row must close the proposal
  before they can return. Document that, or route `O` to the return whenever a visit is outstanding.

**Why.** Marks on this page are one channel per meaning, and every plausible visual mark for "you
were sent here" collides with an existing one: a dashed left rule is the unverified-scene-anchor
vocabulary, and anything inside the line would be a mark on the manuscript. A shared channel for two
meanings is the thing the Detent rules forbid, and inventing a third channel for one rare state is
worse than saying it in the one channel that exists for prose about state.

**Self-critique.** This is the recommendation most likely to be wrong in the direction of
under-delivering: "the annunciator said it once" is not a location, and my argument against a mark is
an argument from tidiness. If a writer test shows people stranded after a visit, the cheap fix is not
a mark at all — it is making `Backspace` (or `O` from anywhere) return, because then the *state* is
recoverable even when the message is gone. I have ordered the recommendation that way deliberately.
Reversible: yes.

## 8 · Durable decisions — use the routes that already exist

**Recommendation.**

1. **Read the intent route's values first, then use it.** `POST /findings/intent/batch` with
   `{intents: {finding_id: intent}}` is the durable record of the writer's own mark. Until the
   accepted `intent` vocabulary is known, **do not guess it** — guessing a wire vocabulary is the
   mistake this pass exists to fix. The proven path (`/findings/:index/dismiss`) stays as the
   fallback.
2. **Keep `fixedOn` session-scoped and say so in the code**, which the build now does. Rebuilding it
   from the desk would need a field that does not exist: the apply response carries
   `findings_status.findings[].{index,status}`, not the row the fix landed on, and the page can only
   reconstruct that for edits it made itself.
3. **Ask for the landing row only if cross-session accuracy turns out to matter** — e.g.
   `findings[].anchor` or `landed_line` on an addressed finding. Low priority; the failure mode
   without it is "vague, never wrong": the answered finding parks (counted, claimed by no line)
   instead of re-pointing at a line it cannot prove.

**Why.** The route map settles the question I had raised: the durable mark and the undo for it both
exist. The only thing standing between the current build and a decision that survives a reload is one
POST.

**Self-critique.** The intent route is a *different* mechanism from dismissal — marks in
`finding_marks.json` versus the report's own triage state — and I do not know whether the product
treats them as synonyms or as two facts (a mark *and* a triage). If they are two facts, sending both
is right and sending only one loses part of the writer's decision; if they are synonyms, sending both
writes the same thing twice and will look like a bug to whoever reads the store. That is exactly the
kind of question the documents I have cannot answer, and it is why step 1 is "read, then use" rather
than "use". Cost if wrong: a decision recorded in the wrong store, discoverable (the desk will show
it), not silent. Reversible: yes.

## 9 · Root System and Story River stay deferred — but the room is warmer than I said

**Recommendation.** Keep both deferred as *surfaces*. Do this instead, in order:

1. Ask the desk whether `setup_scenes` / `payoff_scenes` / `status` survive onto the **finding**
   payload for `plot_thread` findings (the architecture says the ledger folds into them; it does not
   say which fields survive).
2. If they do, let the **roam** read them: `O` then becomes "the other end of this setup/payoff",
   with the same return. That is a lane, not a graph, and it costs one branch in `relatedScene`.
3. Revisit a drawn thread structure only when a writer asks for *"show me all the threads at once"* —
   i.e. when the question genuinely spans more than two places.

**Why.** The verdict deferred these, and the data is now visibly close: the ledger exists, the
finding kind exists, and the fold already has a place to say *"setup in scene 3, payoff here"*. The
Ink Layer's answer to "where else does this matter?" is a visit with a return, and one hop is enough
to answer the question the writer actually asks while reading a line.

**Self-critique.** This is me defending my own scope, and I should say the counter-case plainly: if
the product's differentiator is structure *across* scenes, a two-hop visit is a gesture, not a
feature, and the deferral is a cost I am pushing onto the product. The one-hop limit is a design
choice, not a law — the honest statement is "one hop, measured against nothing", and the measurement
that would settle it is whether writers ask for the second hop. Also note the deferral has a real
cause I should not soften: a drawn thread graph is the first thing in this surface that would want a
second region, which the agreements forbid. Reversible: yes.

## 10 · The 0.72 gate: keep it for targeting, loosen only for showing

**Recommendation.**

1. **Never loosen the threshold for the auto-target decision.** The gate decides whether the page may
   point a critique at a line by itself; keep 0.72 until a measurement justifies a change, and change
   it only as a number, never with a special case.
2. **Measure before touching it.** `anchorFinding` is a pure function: run it over the studio's own
   scripts and findings and report the loose rate, the false-anchor rate, and the score distribution
   of matches a human would call obvious. My two data points are in `OPEN_QUESTIONS.md` §10; one of
   them (a clause quoted out of a longer line, 0.645) is the case that worries me.
3. **If the measurement supports it, add a *showing* rule, not a *targeting* rule** — a row may be
   marked as "possibly this line" for a loose quote, while casting still refuses and the writer still
   has to select the passage explicitly.

**Why the asymmetry.** The two errors are not equally bad. A false *loose* costs a critique that
sits on its scene instead of its line: visible, flagged, harmless. A false *anchor* costs a critique
confidently attached to the wrong line — and the writer may then rewrite the wrong sentence. Trading
a safe failure for a dangerous one to raise a yield number would be a bad trade at any yield.

**Self-critique.** The "possibly this line" mark is a new state, and it is the kind of special case
that produced the worst defects in this codebase (the stale-anchor bug, the dead editor, the 0 px
mark). It is also a second way for a critique to be *about* a line, which the writer has to hold in
their head while reading. Falsifier for keeping 0.72: a measurement showing the loose rate above,
say, 15 % on real scripts — at that point the surface is mostly scene-anchored and the gate is
costing the product its central claim. Cost of measuring: one script, no UI. Reversible: yes.

## 11 · Two smaller notes

* **The empty proposal stays refused** — `/edits/apply` takes `{old, new}` and cannot express a
  deletion, so `editProposal`'s refusal is the route's constraint being stated rather than a product
  opinion. Revisit only if deletion becomes a first-class request.
* **`/rewrite`'s `instruction` field is deliberately unused.** The contract offers the writer's own
  direction as an input ("Make the dialogue tighter."). This surface asks the desk for candidates and
  lets the writer edit the wording in place instead, which is a strictly smaller loop. Note it as an
  affordance we are leaving on the table: the natural place for it is a **second ask** after the ring
  is exhausted ("Last take." → *more like this / different direction*), and that is a feature, not a
  fix.

## 12 · New, from the route map: verification is a three-state vocabulary

**Recommendation.** Read the three states the contract names — `verified`, `not_found`, `no_quote` —
and **say which one applies**. In the build today they collapse into one boolean and one sentence
("its quote could not be matched to the text"), which is a lie for a finding that never offered a
quote: nothing failed to match because there was nothing to match. `no_quote` findings should also
never be described as ambiguous or as "possibly this line" (Q10) — there is nothing to search for.

**Why.** `contracts_UI` §2.B names the three states in the summary payload; the demo carries only
`verified`/`unverified`. Two of the three words in that set are *reasons*, and a page that reports
one reason for two causes is the same defect class as the 0 px mark: the data had the distinction and
the UI threw it away.

**Self-critique.** I am again inferring a per-finding shape from a *summary* field; the desk's
finding-level verification object may use different words (the build already tolerates
`status`/`verified`/string forms, which was deliberate). So the correct form of this recommendation is
the tolerant one: **recognise the three words when they appear, keep the boolean fallback, and never
invent a third sentence for a word I have not seen.** Cost: about twenty lines across `core.js` and
two copy strings plus a test — worth doing *after* one real `/findings` payload is in hand.

---

## Where these recommendations are weakest, ranked

1. **Q2 (strip order)** — no evidence at all; a coin-flip already called. Cheapest to overturn.
2. **Q1, step 2 (pin the wire vocabulary)** — rests on an inference about the desk's intent, and the
   counter-case (four real finding weights) would make the current collapse *lossy and invisible*.
3. **Q9 (one-hop roam)** — I am defending a scope decision, and the counter-case is that the
   product's moat is exactly the thing a hop-free graph would show.
4. **Q7 (no mark on a visit)** — arguing from tidiness; the real fix (return from anywhere) is
   cheaper than the mark and covers the same failure.
5. **Q3 (warn-and-cast)** — sound as a policy, but "rely on undo" carries more weight than it should.

## What I would do first, in order

1. **Read one real payload** (`GET /findings`, and the intent route's accepted values). It settles
   Q1's counter-case, Q12's vocabulary, and Q8's mechanism in about ten minutes, and every other
   answer gets less speculative for it.
2. **Q8 step 1–2** — one POST away from a decision that survives a reload; the desk already keeps it.
3. **Q12** — the only item here that is a *truth* defect in the shipped copy rather than a judgement
   call.
4. **Q10's measurement** — a pure-function harness over real scripts; it either retires the worry or
   turns it into a number worth acting on.
5. **Q4 and Q6's strings** — two sentences, both strictly-improving, no new state.

## What I recommend *not* doing

* **Do not add a fourth severity width** (Q1) — not until the desk says the fourth weight is real.
* **Do not ship a "spent" strip** (Q5) — the fiction costs more than the gap.
* **Do not relax the anchor threshold to raise the yield** (Q10) — the two errors are not symmetric.
* **Do not invent an `intent` value** (Q8) — an invented wire vocabulary is the defect this pass was
  about.
* **Do not build a mark for the visit** (Q7) — make the return reachable instead.
