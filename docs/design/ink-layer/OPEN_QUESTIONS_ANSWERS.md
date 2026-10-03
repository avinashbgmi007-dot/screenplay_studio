# Recommended answers to the open questions — and the case against each

The companion to `OPEN_QUESTIONS.md`. That file records *what is unsettled*; this one commits to an
answer for each, says why, and then argues the other side: the strongest counter-case, what would
falsify the recommendation, and what it costs if I am wrong. Where the recommendation is weak I say
so in the recommendation itself rather than burying it in the critique.

**Read first, before any of this is acted on.** These answers were first written from
`contracts_UI`, the route map, the PRD and the architecture brief. They have now been re-checked
against **the code that produces the data** — and, for the findings surface, **observed against the
studio itself**: the demo-model desk was booted, the sample project analysed, and the live routes
answered. Where a claim below says *observed*, it is a recorded response, not a reading
(`LIVE_VERIFICATION.md` holds the payloads). The re-check was against — `screenplay_analyzer/*`,
`screenplay_studio/{webapp_server,revision}.py`, `screenplay_parser/quotematch.py`,
`knowledge_base/rules/*.json`, and the SPA at `screenplay_studio/webapp/app.js` — because a document
is a claim about the code and the code is the fact. Five answers moved. Where an earlier claim is now
disproved it is marked **retracted** rather than quietly deleted: a table that was wrong about a wire
field is itself evidence about how the earlier answers were reasoned.

| Fact, read from the producer | Where | Effect on these answers |
|---|---|---|
| Severity is a **closed, three-member set**: `SEVERITIES = ["low", "medium", "high"]`, compiled into the findings grammar | `grammar.py:50,69` | **Q1 settled.** The "pin the wire at `critical \| major \| minor`" step is **retracted** — the wire vocabulary was readable all along |
| The curated corpus agrees: 26 rule files, **263 rules — medium 149 / high 71 / low 43**; `severity_for()` makes the cited rule the source of truth, `"medium"` only for unknown ids | `knowledge_base/rules/*.json`, `rules_context.py:274` | a finding's weight is a curated fact, not a model flourish — the page may draw it without hedging |
| `by_severity` is **tallied from the findings' own strings** (default `low`) | `webapp_server.py:2460-2467` | **retracted:** the "four bands `high\|major\|medium\|low`" row. `major` is not a key and never was — the fourth band was a document's error, and my alias table was built to absorb it |
| Verification has **four** states: `verified \| not_found \| no_quote \| scene_not_found`, and the summary adds two derived fields — `quote_bearing`, `verified_pct_of_quoted` — the latter **`None` when nothing quote-bearing exists** (no denominator, no number) | `verifier.py:46`; observed live | **retracted:** "three-state vocabulary" — there is a fourth, and it is the one a citation can hit when the scene number itself is wrong. Q12 |
| The report badges exactly **two** of them (`not_found`, `scene_not_found`) and leaves `no_quote` **blank** | `report.py:36-40` | Q12: the warning copy has an owner, and it is the published report rather than the summary's arithmetic |
| An unverifiable quote is **never discarded** — downgraded, flagged, kept | verifier policy; `report.py` renders every finding regardless of state | the "kept, never dropped" rule was already the desk's, not mine: unchanged, and now cited rather than asserted |
| The finding's quote field is **`evidence_quote`**, and a per-row **`verification` block is served** | `/findings` item shape; `revision.py:960` | the demo's `evidence` is a rename the adapter must keep doing; `verification` is not a summary-only concept |
| `finding_id` is a **content hash**: `"f" + base36(djb2(category + "\|" + stripped_quote))`, else `"issue:" + first 100 chars` | `compute_finding_id` | the durable key Q8 needed already exists, and it survives report regeneration — which is exactly the failure an index-keyed mark would have had |
| The writer's intent vocabulary is exactly **`addressed \| deferred`**; **`null` clears** | `finding_marks.json`; SPA `setFindingIntent` | **Q8's step 1 is answered.** "Do not guess the value" becomes "do not send anything else" |
| Observed status is **`addressed \| still_present \| unknown`**, computed against the parse-of-record, never from absence alone | `revision.py:930-983` | two axes, not one, and the desk already resolved how they meet (see Q8.4). `unknown` is the honest answer for a quote the script never contained |
| Two thresholds, **deliberately not shared**: verifier **0.72** (lenient — "a model paraphrased a real line") vs change-detection **0.95** (strict, element granularity) | `verifier.py`, `quotematch.py`, `revision.py:862` | **Q10 must say which question it answers.** 0.72 is the *targeting* gate; 0.95 is *"has the writer changed this line"*, a different question with a different error asymmetry |
| `/findings` filters: `scene`, `status`, `severity`, `category`, `include_dismissed`, `group_by=issue-text` | `webapp_server.py:2497-2550` | `severity` takes **one** value, so a multi-toggle reading stays client-side; the display dedupe exists server-side with `scene_refs` preserved |
| The SPA's own loop bar is **position → nav → verbs**, with span-level ink anchors and a scene fallback *because cross-line quotes are the known case* | `app.js:6566-6660, 6949-7035` | the strip's order and the loop's mechanics are not inventions of this build — two of them are the product's existing answers |
| The SPA badges **every** non-`verified` state "unverified"; the report does not | `app.js:4234` vs `report.py:36` | where the two disagree the page follows the report, and says so (Q12) |

**Which documents were actually stale — the clarification this pass was for.** The instruction to
read the code rather than the docs was about *drift*, not about distrust: a document may describe an
older API. Auditing both shows the drift was real, and it was not in the repo's own docs:

| Claim | `contracts_UI` (the doc I was handed) | the repo's own docs | the code |
|---|---|---|---|
| Verification states | **three**: `verified`, `not_found`, `no_quote` | **four** — `docs/DATA_FORMATS.md:221,271`, `docs/DEVELOPMENT.md:115` | **four** (`verifier.py:46`) |
| `by_severity` bands | **four**: `high, major, medium, low` | not restated | **three** keys at most, tallied from the findings (`webapp_server.py:2460-2467`) |
| How common `no_quote` is | not stated | **83 % of findings on a real script** — `docs/CRITICAL_REVIEW_2026-09-18.md:399` ("19/23 carry `no_quote` … script-level passes cite scene numbers only") | consistent with the verifier's assignment rules |

So the two wrong facts in my earlier answers came from the extracted contract, and the repo's own
documentation already agreed with the code. The lesson is narrower and more useful than "docs lie":
**check a claim against the newest artifact that owns it** — here the code, and behind it the repo's
own format docs — rather than against whichever document is nearest to hand.

The `83 %` figure deserves to be repeated, because it changes the weight of Q12: a quoteless finding
is not an edge case, it is the **majority** of what a real report contains. Under the flag predicate
this build shipped before the audit, the fold's "N unverified" line would have counted 83 % of a real
script's findings as failed searches — the normal case rendered as a defect. The fix is not a
polish; it is the difference between a report that reads true and one that cries wolf on most of
itself.

Two defects **in this build** were found by the same reading and are fixed in the same change as this
document: the severity collapse (Q1) and the flag predicate that counted a quoteless finding as a
failed search (Q12). Both have tests, and the test for the second now imports the shipped predicate
instead of re-implementing it — a local copy of a shipped rule is how the copy and the code drift
apart.

---

## 1 · The two severity vocabularies — settled: there is one, and it has three tiers

**Recommendation (revised).**

1. **The wire's vocabulary is the desk's**: `low | medium | high`, closed by grammar. It is not a
   "report band" that must be kept away from drawing paths — it is the finding's own weight, and a
   drawing path may read it.
2. **The three tiers map one-to-one onto three marks** — `low → minor`, `medium → major`,
   `high → critical` (internal names; the DOM, CSS and geometry read those). No collapse. The
   geometry was already sized for exactly three: pip widths 4 / 8 / 12 px and a three-step ink
   threshold, whose middle step was previously **unreachable from real data**.
3. **`by_severity` is not a second vocabulary.** The route tallies the findings' own strings, so its
   keys are that same closed set. Drawing from it is still refused — a count is not a finding — but
   for the ordinary reason, not because it speaks a different language.
4. **Keep the alias table small and honest**: the page's internal names, the desk's three, and the
   legacy spellings still abroad in cached payloads (`blocker`, `moderate`, and `major`, which the
   desk's own ordering table still ranks at `webapp_server.py:2319`). Unknown text stays `none` — no
   mark rather than a guessed one.

**Why, and what changed.** The previous answer recommended pinning the wire at
`critical | major | minor`, inferred from this project's design system *because no document stated the
finding vocabulary*. That inference was wrong, and the falsifier I wrote beside it had already fired:
the producer states the vocabulary, compiles it into the grammar so the model cannot leave the set,
and the curated corpus counts the three tiers 149 / 71 / 43. There was never a second vocabulary to
reconcile. There was a guess about a wire format that was readable.

**Self-critique.** Two things worth keeping honest. First, the `medium → minor` collapse I shipped was
*defensive*, and its cost was invisible: the middle pip width and the middle threshold step could not
be reached by any real finding, so a part of the interface existed and did nothing — the 0 px mark's
failure class, one layer down. Second, the retraction cuts against my own earlier ranking: I listed
"Q1 step 2" as the second-weakest recommendation, and the reason it was weak is that it argued from
design intent rather than from the producer. The falsifier survives in a better place: if the desk
ever emits a weight outside the three, the grammar is where it shows up first, and `none` is what
keeps that from becoming a silent mark.
Reversible: yes, one table.

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

## 8 · Durable decisions — the vocabulary is `addressed | deferred`, and the store already exists

**Recommendation.**

1. **Send exactly two words.** `POST /findings/intent` with `{finding_id, intent}`, where `intent` is
   `"addressed"` or `"deferred"`; **`null` clears the mark**. This is fact now, not a guess: the
   store is `finding_marks.json`, the SPA's `setFindingIntent` sends precisely this, and the batch
   route takes `{intents: {finding_id: intent}}` (≤500 entries; **`200`**, or **`207`** with
   `{ok, applied[], failed[]}` when only part of the batch lands). The old instruction — "read the
   accepted vocabulary before sending anything" — is discharged; the same discipline now points the
   other way: **send nothing outside that set.**
2. **Key the mark by `finding_id`, never by index.** The id is a content hash
   (`"f" + base36(djb2(category + "|" + stripped_quote))`), so it survives a report being
   regenerated; an index-keyed mark does not, and would attach the writer's decision to whatever
   finding later occupies that row. `dismissed` rides the same id (`webapp_server.py:2386-2392`),
   and the batch route's partial-failure body exists precisely because a batch can straddle a
   regeneration.
3. **Keep `fixedOn` session-scoped and say so in the code** (unchanged: the apply response carries
   `findings_status.findings[].{index,status}`, not the row the fix landed on, so the page can only
   reconstruct that for edits it made itself).
4. **Mirror the desk's two axes, and their one meeting point.** Observed status is
   `addressed | still_present | unknown`, computed against the parse-of-record — `unknown` is the
   honest answer for a quote the script never contained, because absence alone is not progress. The
   writer's intent is a **separate fact**. The row speaks the observed one; the **meter speaks the
   writer's**: the dawn arithmetic counts an `addressed` intent as done while the row still says
   `still_present`. That is the product's own answer to "two facts or one synonym", so the page needs
   no third state — it needs to keep the two apart in the row and let them meet only in the count.

**Why.** The mechanism question is closed, so the only live risk is drift: an interface that invents
a third intent word, or a mark that dies with the report it was made against. Both are avoidable now
with data rather than with a guess.

**Self-critique.** The earlier worry is answered in the least comfortable direction: they *are* two
facts, so the desk can show a writer "you marked this addressed and the page still contains the
line". That contradiction must be rendered, not resolved — the page's decision-dry state is where it
surfaces, and if it ever reads as the app arguing with the writer the fix is copy, not state. What
remains unproven is written down rather than assumed: the `207` body is known from the route table
and the SPA, **not from an observed partial failure**, so the failure copy is written to a shape. And
the checkable thing is one POST away — mark a finding, reload, confirm `finding_marks.json` holds it.

## 9 · Root System and Story River stay deferred — and the one-hop roam is blocked on data, not taste

**Recommendation.**

1. **Do not wait for `setup_scenes` / `payoff_scenes` to arrive on a finding: they do not.** The
   ledger carries `{setup, kind, setup_scenes, payoff_scenes, status, note}`
   (`setup_payoff.py:64-104`), but the `plot_thread` finding folded out of a dangling or abandoned
   row carries only `scene_refs` (`setup_payoff.py:142`) — the setup scenes. **The payoff list — the
   thing a roam would travel to — is left behind in the ledger payload.**
2. **So the roam has two routes to a first version, and I would take the second.** (a) Read the
   ledger's own payload for `plot_thread` findings and join on `scene_refs`: accurate, but it makes a
   reading surface depend on a second endpoint that the finding row already fails to carry. Or
   (b) **ask for the fields on the finding** — `payoff_scenes` and `status` — which is a two-field
   addition to a payload that already ships ten, and the same shape of ask Q8.3 makes for a landing
   row. One ask, two answers.
3. **Keep the visit, not the graph.** `O` travelling to the payoff scene with the same return, one
   hop, remains the right shape *once the data exists to point at*. Until then the fold may say what
   the ledger knows — this setup is dangling — without pretending to know where it ends.

**Why this is the sharpest correction in the pass.** I recommended building the roam *if* the fields
survive onto the finding, and wrote "ask the desk whether they do". The answer is no. The
recommendation inverts: the ask comes first, the surface second. Worth noting for balance — the
deferral of Root System and Story River as *surfaces* is unaffected; nothing here needs a second
region.

**Self-critique.** This is me defending my own scope, and the counter-case stands as written: if the
product's differentiator is structure across scenes, a two-hop visit is a gesture rather than a
feature, and the deferral pushes a cost onto the product. The one-hop limit is a design choice
measured against nothing; what would settle it is whether writers ask for the second hop. The audit
adds one uncomfortable fact to that: the data to answer the first hop faithfully does not yet ride
the payload, so "one hop is enough" is currently untestable rather than merely unmeasured.
Reversible: yes.

## 10 · The 0.72 gate: keep it for targeting — and say which question it answers

**The two thresholds are deliberately not shared**, and that is now read from the code rather than
inferred: `screenplay_parser/quotematch.py` exports the matching *primitives* and no threshold, the
verifier sets its own **0.72** (lenient, because "a model paraphrased a real line" is the common
case), and `revision.QUOTE_CHANGE_THRESHOLD` sets **0.95** (strict, element granularity) for the
different question *"has the writer changed this line"*. Measured at that gate: a dropped character
scores 0.979 and is still present; a swapped word 0.875 and a removed word 0.830 are addressed. So
the numbers below answer the **targeting** question only. Nothing here loosens change-detection, and
nothing there should ever be used to place a critique.

**Recommendation.**

1. **Never loosen the threshold for the auto-target decision.** The gate decides whether the page may
   point a critique at a line by itself; keep 0.72 until a measurement justifies a change, and change
   it only as a number, never with a special case.
2. **Measure before touching it — the measurement has now been taken, once** (`REAL_SCRIPT_RESULTS.md`
   §2, harness at `tests/measure-anchors.mjs`). Over a real 28-page short film with its live findings
   payload: **3 of 3 quote-bearing findings anchored, every one at score 1.000 (exact substring);
   none in the 0.72–0.99 band; none loose; none ambiguous after the duplicate-heading defect was
   fixed.** So on this script the gate is not the bottleneck at all — **quote *presence* is**: 13 of
   16 findings carry no quote and can never ink a line (81 %). That reframes the question: the 0.72
   worry (a paraphrase that lands loose) is real but *unmeasured*, while the dominant real-world cost
   is `no_quote` findings sitting scene-anchored. One script is a sample, not a rate: a
   paraphrase-heavy report from a real model is still the payload that would stress the gate, and
   the recorded 43-finding session (real model, this script) is the obvious next measurement if its
   payload can be found.
3. **If the measurement supports it, add a *showing* rule, not a *targeting* rule** — a row may be
   marked "possibly this line" for a loose quote, while casting still refuses and the writer still
   selects the passage explicitly.
4. **Mirror the verifier's own extensions, which the page currently lacks.** A quote found in the
   whole document but not in the cited scene is `verified` with a note — *"Quote found in Scene N,
   not the cited scene(s) … — corrected."* — and it carries `matched_scene`. The page's targeting
   reads `scene_refs` only, so it cannot reproduce that correction. Two lines of code and one honest
   sentence; it is the desk's own answer to the cross-scene quote.

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

* **`/rewrite` answers for the whole scene, and says so in its own payload.** The route returns
  `{scene_number, note, replacements, scene_text}` — so the strip's scope sentence may honestly name
  the scene rather than the line, and `scene_text` is available if a comparison ever wants the whole
  room. Two smaller facts ride the same route: `finding_index` is optional, and the producer strips
  JSON-emit noise from `old`/`new` (`_strip_rewrite_noise`, `webapp_server.py:1900-1912`) precisely
  so the copied line can match the scene verbatim — which is the failure mode the apply guard exists
  for, mitigated at source. The verbatim comparison stays.
* **The display dedupe already exists server-side.** `GET /findings?group_by=issue-text` returns
  groups with `count`, `severities`, and the union of members' `scene_refs` preserved. The build
  re-derives its grouping client-side, which remains defensible — row-level state (dismissal, intent,
  verification) has to be readable per row — but it is worth recording that the desk does not need a
  client to do it, and that the two must agree on *what counts as identical* (byte-identical issue
  text, per the route). And `severity` on that route takes **one** value, so a multi-severity filter
  can only be a client-side reading. Both facts point the same way: the client keeps the filter, and
  the grouping is a rendering choice rather than a missing capability.

## 12 · Verification is a four-state vocabulary, and the report already writes the copy for it

**The states**, read from the verifier rather than from a summary field: `verified`, `not_found`,
`no_quote`, `scene_not_found` (`verifier.py:46`). The summary counts all four; the verified ratio
excludes `no_quote` and `scene_not_found`, which is a different arithmetic from the one I assumed. And
`no_quote` is not a failure mode — it is a state the verifier **assigns**: a finding with no quote to
offer cites scene numbers instead, anything under three words is quoteless, and a finding whose cited
scenes all fail to exist becomes `scene_not_found`. A quoteless finding is a *citation*, not a broken
one.

**Recommendation.**

1. **Say which state applies, and let the report write the sentence.** `report.py:36-40` badges
   exactly two states — `not_found` (*"unverified — quote not confirmed in cited scene(s)"*) and
   `scene_not_found` (*"unverified — cited scene number doesn't exist"*) — and leaves `no_quote`
   **blank**. Mirroring the report means the two failed searches warn, and a quoteless finding is
   quiet: there was nothing to search for, so nothing failed.
2. **This is a fix to shipped copy, not a new state.** The build currently collapses the four states
   into one boolean and says *"its quote could not be matched to the text"* — a lie for both
   `no_quote` (nothing could match) and `scene_not_found` (the scene itself is missing, which is a
   fact about the citation, not the line). **Fixed in this change**, with the predicate imported into
   the test rather than re-implemented in it.
3. **Where the page and the SPA disagree, follow the report and say so.** The SPA badges *every*
   non-`verified` state "unverified" (`app.js:4234`); the report distinguishes. The report is the
   desk's published artifact and the only place the four states are given precise prose, so it is the
   copy of record. If the product later aligns the SPA to the report, the page moves with it — one
   predicate, one table.
4. **`no_quote` is still never a target.** Nothing to match means `anchorFinding` scores it 0 and
   parks it scene-anchored, and casting refuses it with the real reason. That behaviour was already
   right; only the counting was wrong.

**Observed live.** On the sample project (`The Late Hour`, demo model), `/findings` returned five
findings, **all five `no_quote`** with `evidence_quote: null` — and the published `report.md`
contains **zero** "unverified" badges, exactly as `report.py` leaves a quoteless state blank. The
arithmetic the report gives for it is `{'verified': 0, 'not_found': 0, 'no_quote': 5,
'scene_not_found': 0, 'quote_bearing': 0, 'verified_pct_of_quoted': None}`. Under the predicate this
build shipped before the audit, that report would have been described as *"5 unverified"* — every
finding on the page flagged, against a published report that names none. The fix is the difference
between the page and the report agreeing and the page contradicting the report on 100 % of a live
sample.

**How common is this, really.** The repo's own review of a live run answers it:
`docs/CRITICAL_REVIEW_2026-09-18.md:399` reports **19 of 23 findings carrying `no_quote`** (83 %), because
the script-level passes cite scene numbers rather than lines. The old predicate would have reported
that as `19 unverified` — the majority of the report described as failed. This is the strongest
justification for the change in the whole document, and it was in the repo's own docs the entire time.

**Why.** Two of the four words are *reasons*, and a page that reports one reason for two causes is the
0 px defect again: the data held the distinction and the interface threw it away. The audit's
contribution is that the four states are per-finding facts — the `verification` block rides the row —
not summary arithmetic to be inferred.

**Self-critique.** My earlier self-critique said the correct form was the tolerant one — recognise the
words, keep a boolean fallback, invent no third sentence for a word I had not seen. That was right,
and it is why this stayed a small change: a state table, a set membership test, and the report's own
two sentences. The remaining asymmetry is deliberate and worth stating: the page now shows *fewer*
warnings than the SPA does, and more than a strict reading of "verified or not" would justify. If a
writer ever asks why a quoteless finding carries no caveat, the honest answer is that the desk
verified its citation instead of its quotation, and the fold is where that gets said.

---

## Alignment status, question by question

The ask was to revisit every answer and verify it against the repo. This is the ledger of that
verification: which answers the code settled, which the code confirms, and which are judgement calls
that no amount of reading can settle.

| Q | Verdict | What verified it |
|---|---|---|
| 1 | **Settled by code, answer corrected** | `grammar.py:50,69` (closed set), rule corpus counts, `webapp_server.py:2460-2467`. The build's collapse was fixed |
| 2 | **Aligned with the build** | `ink-layer.js:965-1041` — the strip is authored ledger → takes → scope → reason → keys, in that append order |
| 3 | **Aligned with the build** | `ink-layer.js:931-948, 986` — an ambiguous quote casts, the warning is said once and kept in the strip's meta line |
| 4 | **Aligned with the build** | `core.js:999-1004` — while `editingProposal`, `Escape` → `proposal.abandon`, and the strip's key line says so |
| 5 | **Aligned (nothing to ship)** | `ink-layer.js:1256-1315` — no "spent" state exists: the strip is removed on apply and undo is announced; the withdrawn concern stays withdrawn |
| 6 | **Aligned with the build** | `ink-layer.js:825` (`stepWet`) walks `r.wet && !r.quiet` (filter + ink floor), `stepRow` steps every row — the asymmetry is exact |
| 7 | **Aligned with the build** | `S.roam` is state only (`ink-layer.js:1470-1497`); no class, dataset or attribute marks the visited row |
| 8 | **Settled by code, answer rewritten** | `finding_marks.json` vocabulary, `compute_finding_id`, the batch route's `207` body |
| 9 | **Settled by code, answer inverted** | `setup_payoff.py:142` — only `scene_refs` rides the finding; the ask now precedes the surface |
| 10 | **Settled by code, answer qualified** | `verifier.py` 0.72 vs `revision.py:862` 0.95; `matched_scene` correction documented |
| 11 | **Confirmed** | `/rewrite` returns scene-scope + `scene_text` (`webapp_server.py:1993-1997`, `_strip_rewrite_noise` at 1900); `group_by=issue-text` at 2533 |
| 12 | **Settled by code, defect fixed** | `verifier.py:46`, `report.py:36-40`, and the 83 % datum in the repo's own review |

Nothing in the alignment pass came back misaligned: every answer Q2–Q7 and Q11 was either already
what the code does or a policy recommendation (Q10's "possibly this line") the code neither confirms
nor contradicts. The two that needed changing were both **settled by facts I had previously only
inferred** — and both had shipped as code.

## Where these recommendations are weakest, ranked

*Updated after the code audit. The list is shorter than it was, and one entry left it by being
settled rather than by being argued.*

1. **Q2 (strip order)** — still no evidence at all; a coin-flip already called. Cheapest to overturn,
   and the audit found a third vote for it: the SPA's own loop bar is position, then nav, then verbs.
2. **Q9 (one-hop roam)** — now blocked on data rather than on taste: the payoff list does not ride the
   finding, so the question "is one hop enough?" cannot be tested until the two-field ask lands.
3. **Q7 (no mark on a visit)** — arguing from tidiness; the real fix (return from anywhere) is cheaper
   than the mark and covers the same failure.
4. **Q3 (warn-and-cast)** — sound as a policy, but "rely on undo" carries more weight than it should.
   The audit adds one support: an unverifiable finding is never discarded by the desk either.
5. **Q10's "possibly this line"** — a new state proposed to fix a measurement nobody has taken. Still
   the right order (measure, then decide), and it is now the only new state left on the list.

*Left the list: Q1 step 2, which was second-weakest because it argued from design intent — the
producer settled it.*

## What I would do first, in order

1. **Mark a finding, reload, read `finding_marks.json`.** One POST against a route whose vocabulary
   and storage are now known (`addressed | deferred`, `null` clears, keyed by content hash). It
   converts Q8 from reasoned to verified, and it is the smallest possible test of the whole
   durability story.
2. **Take the two-field ask to the desk** (`payoff_scenes`, `status` on `plot_thread` findings, plus
   the landing row Q8.3 mentions). One ask, three answers — and the roam is blocked on it, so it is
   the only item here that blocks a surface rather than a sentence.
3. **Q10's measurement** — a pure-function harness over real scripts; it either retires the worry or
   turns it into a number. `anchorFinding` is pure and the corpus is in the repo.
4. **Q4 and Q6's strings** — two sentences, both strictly-improving, no new state.
5. **Q12's remaining half** — the copy is fixed and tested; what is left is the fold sentence for a
   quoteless finding, which should be written only if a writer asks.

*Done since the last revision: the real payloads were read (Q1, Q8, Q12, and the shape table at the
top), and the two defects that reading exposed — the severity collapse and the flag predicate — are
fixed with tests. The "read one real payload" step that headed this list is discharged.*

## What I recommend *not* doing

* **Do not add a fourth severity width** (Q1) — there is no fourth tier to draw. The grammar closes
  the set at three, so a fourth width would be decoration, and decoration on the severity channel is
  exactly what the register forbids.
* **Do not mirror the SPA's `unverified` badge** (Q12) — it is the one place the product's own two
  surfaces disagree, and the report is the artifact with the precise copy.
* **Do not ship a "spent" strip** (Q5) — the fiction costs more than the gap.
* **Do not relax the anchor threshold to raise the yield** (Q10) — the two errors are not symmetric,
  and the two thresholds are deliberately unshared.
* **Do not invent an `intent` value** (Q8) — the vocabulary is two words and a `null`; anything else
  is the invented wire format this pass exists to prevent.
* **Do not build a mark for the visit** (Q7) — make the return reachable instead.
