# Open questions, concerns, and the decisions taken

Written with the alignment pass (the Ashna verdict + `contracts_UI` against this repo), because
several of the things that pass could not settle on its own are **product** questions, not code
questions.

> **Recommended answers, with the case against each, are in `OPEN_QUESTIONS_ANSWERS.md`** — one
> answer per item below, the evidence for it, and what would falsify it. Read the two together: this
> file is the list of what is unsettled, that one is where I commit. Each entry says what is in the code today, what I would do next, and what it would cost
to change. Nothing here is a TODO dressed as a question: every one of these has a live answer in
the build and a different answer that a writer or the desk could reasonably insist on.

---

## 1 · The desk speaks two severity vocabularies

**In the code today.** Findings arrive spelled `critical | major | minor`; `/findings/summary`
reports `high | major | medium | low`. `SEV_ALIAS` in `core.js` collapses them by weight
(`high`/`blocker` → `critical`, `medium`/`moderate`/`low` → `minor`), and everything that draws —
the row rule's width, the horizon pip, the fold's ▪ blocks — reads the canonical word only.

**Why it is a question, not a fix.** Silently aliasing two vocabularies is a compatibility layer
that will outlive its reason. The demo carries both spellings *on purpose* (a `high` and a
`medium`) so the collapse is exercised and visible: the fold prints `high → critical` where the
desk's word differs from the page's. That is honest, and it is also a small, permanent apology
printed in the writer's way.

**Decision to make:** pin one vocabulary at the wire, then delete the alias. My recommendation:
`critical | major | minor` everywhere (the words the page draws), with the alias kept one release
as a transition. **Cost to change:** one table plus the demo fixture. **Cost of not deciding:**
the apology stays in the UI forever, and every new field that carries severity has to remember the
rule.

## 2 · The strip: ledger first, or proposal first?

**In the code today.** `ledger → takes → scope → reason → keys`. The ledger is a one-line
instrument head (`TAKE 01 / 03 ● ○ ○ +26 −00`); the takes follow immediately.

**Why it is a question.** "Progressive disclosure" can be read two ways: the *reading* (the
proposal) first, with its position stated after; or the *instrument* first, with the position
established before any text is read. I chose instrument-first because the ledger answers "how many
are there and where am I", which is what makes the take list legible as a list, and because the
ledger is a single line of small type, not a rationale. The rationale is emphatically *after* the
takes — that part is not in question.

**Cost to change:** one line in `renderCastStrip`. **What would settle it:** a writer reading both
orders cold. If the ledger reads as a heading that delays the proposals, swap them.

## 3 · An ambiguous quote is cast, with the warning kept

**In the code today.** When the frame's target occurs twice in the line, the take is still offered
and the strip carries `this quote matches more than one line`; the annunciator says it once, riding
with the take's own sentence, and never on a step that could overwrite it. The take is applied to
the **first** occurrence.

**Why it is a question.** There are two defensible rules: warn-and-cast (the writer decides, and
the warning is in front of them) or refuse-and-ask (nothing is cast until the writer selects the
occurrence). I chose warn-and-cast because refusing would block legitimate work on a line that
repeats a phrase for effect — and because the second occurrence is visible in the passage the
writer is looking at. The risk I accepted: a writer who presses Enter without reading the strip
applies the change to the wrong occurrence.

**What would settle it:** whether the applied result is *visible* enough to catch. Today the
commit is the only write and the fold closes on success, so the mistake would be caught on the
page — but only if the writer looks. A cheaper mitigation than refusing: keep the fold open for
one beat after a commit *when the frame was ambiguous*. Not built.

## 4 · `Escape` inside the proposal editor abandons the edit, not the line

**In the code today.** With the editor open, `Escape` = abandon the edit (the take reverts to the
desk's wording; the proposal stays open). A second `Escape` keeps the writer's own line, which is
the decision that dismisses the finding on the desk.

**Why it is a question.** A writer who has just typed a sentence and changed their mind may expect
one `Escape` to end the whole exchange. Two `Escape`s is a second thought. I chose the narrower
meaning because `Escape` must never silently reverse a decision about the *manuscript* while the
caret is inside a text field, and because the annunciator plus the strip's `EDITING` state say
which escape this is.

**Cost to change:** `abandonProposalEdit` losing one line. **What would settle it:** watching a
writer abandon an edit and then look for their line.

## 5 · A committed take spends its frame — the strip is removed

**In the code today.** On success the fold closes and the strip is deleted. The record that a
change happened lives on the row (`data-cast="applied"`, `data-delta="true"`, the dry/evidence ink)
and in undo.

**Why it is a question.** The strip is a diff drawn against a frame that the line no longer holds;
leaving it visible would be a picture of the past pretending to be the present. But it also means
there is **no post-commit comparison** in place — a writer who wants to see what they just did must
audition again (the take still exists on the desk) or undo.

**Decision to make:** whether a committed line should offer a read-only "what changed" line (the
`del`/`ins` diff, marked spent) instead of nothing. My recommendation: yes, but only as the fold's
own record, never as an actionable strip. **Cost:** one element, one state, and a rule about which
of the two the fold shows when a line is re-wet by undo.

## 6 · The walk follows the filter; the arrow keys do not

**In the code today.** `n`/`p` stop only where a critique is speaking up (wet **and** not receded
by the ink floor or the context filter), and say so at the ends: *"No further lines speaking up —
the filter is hiding the rest. Press F to widen it."* The arrow keys still step through every row,
and receded rows stay on the page at full contrast.

**Why it is worth stating.** This is a deliberate asymmetry: `n` is "the next critique that is
speaking", `↑↓` is "the next line of the script". If a writer's mental model is the opposite, they
will press `n` expecting to reach a row they filtered out. **Cost to change:** one predicate.
**What would settle it:** which key writers use to get back to a line they know exists.

## 7 · A visit is not visible on the page

**In the code today.** `O` jumps to the other scene a finding cites (the row whose text matches
the same quote, else that scene's head), announces `Related passage: scene 15…`, and `O` again
returns to where the writer was reading. The landing row carries **no mark**.

**Why it is a question.** The annunciator is the only thing that says "you are here because a
finding sent you". If the writer looks away, the visit leaves no trace, and the *return* is then a
key they have to remember rather than a place they can see.

**Decision to make:** whether the visited row should carry a quiet mark (a dotted rule in the void
colour, the same vocabulary as an unverified scene anchor) until the return. My recommendation:
yes — it is the difference between a jump and a place. **Cost:** one state, one rule, and a rule for
what happens when the writer starts casting from the visited row.

## 8 · `fixedOn` and the by-choice mark live for the session only

**In the code today.** When a fix lands, the page remembers where it landed (`S.fixedOn`) so the
answered finding is not re-anchored to the scene's head; a line kept by decision (`Escape`) is
recorded on the desk via `/findings/:index/dismiss`. Both are session state on the page: after a
reload, `fixedOn` is empty and the answered finding falls back to parking (counted on the desk,
claimed by no line).

**Why it is a question.** If the desk's `/findings` response carried the landing row (or the
finding's `intent`), the page could rebuild both marks from the server and never guess. That is a
route change, not a page change. **Cost:** one field in the payload plus one branch. **Cost of not
doing it:** a reload makes the page slightly less informed than it was — never wrong, just vaguer.

## 9 · Root System and Story River stay deferred

**In the code today.** Neither is built. The roam (`O`) is the cheap version of "where else does
this matter?": navigation between cited passages with a return, and **no edge that the payload does
not assert**.

**What the verdict asked for before either returns:** the door is data, not UI — `setup_scenes`,
`payoff_scenes`, `status` on `/findings`. Until those arrive, any root or river drawn on this page
would be an invented structure, which is the one thing the honesty rules forbid. The project's
other selection is unchanged: Root System and Story River are deferred, Rehearsal is the comparison
interaction, and Ink Layer is the primary surface.

## 10 · The 0.72 gate is measured, but only against this corpus

**In the code today.** `fuzzyScore` (containment → 1, else Sørensen–Dice over character bigrams)
with a threshold of **0.72** and a tie window of 0.04. Two real cases from the demo, measured:

| Quote | Text | Score | Result |
|---|---|---|---|
| `You're late. The stairs gave you away.` | `You're late. The stairs told on you.` | 0.735 | located |
| `The ON AIR sign is dark` | `The ON AIR sign has been dark for a while` | 0.645 | **loose** |

**The concern.** The second row is the interesting one: a finding that quotes a *clause* of a
longer line falls below the gate and is therefore scene-anchored, flagged, and not auto-targeted —
even though a human would say the quote obviously belongs to that line. That is the correct
behaviour for the rule as written (never re-point a finding at a line it cannot prove), but the
*yield* of 0.72 on a real screenplay is unmeasured: too high and findings scatter to their scenes;
too low and quotes attach to the wrong line. The number was chosen from the contract, not fitted.

**What would settle it:** run `anchorFinding` over the studio's own scripts with their findings and
look at the loose rate and the false-anchor rate. It is a pure function; the measurement is a
script, not a feature.

## 11 · Two smaller notes, recorded so they are not forgotten

* **The empty proposal is refused as a deletion.** `editProposal` refuses empty text with *"the
  apply route takes a replacement, not a deletion"* — because `/edits/apply` cannot express a
  deletion today. If deleting a passage becomes a first-class request, this refusal is the thing to
  revisit.
* **The demo's severity words are a fixture, not a recommendation.** `d6` (`high`) and `d7`
  (`medium`) exist to keep the alias exercised in the demo and the tests. A real desk that pins one
  vocabulary makes them redundant (see §1), and the tests that assert them should then be rewritten
  rather than deleted — the collapse is still worth a unit test even when the desk speaks one
  language.
