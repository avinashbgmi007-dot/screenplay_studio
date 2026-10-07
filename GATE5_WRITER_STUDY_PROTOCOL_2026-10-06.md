# Gate 5 — the writer study: protocol and instrument

**Status:** READY TO RUN. Everything the study needs now exists in the product.
**Owner:** you (it needs 3–5 real screenwriters; no code can produce it).
**Date written:** 2026-10-06. **Revised 2026-10-07** (§2, §5, §7) after PRs #11–#14 landed.
**Run against:** `origin/main` = **`65f4b9a`**. Pin this commit for the sessions — a study whose
build is unstated is not reproducible, and reproducibility is exactly what Gate 7 is about. If
`main` has moved by the time you run, re-read §7's field list: it changed on 2026-10-06/07.

---

## 1. What this gate answers, and why nothing else can

Every accuracy number this project has produced is a **proxy**. The figures
(96.8 % / 93.8 % writer-agreement, 98.58 % target) come from two scripts whose
correct/wrong labels were supplied by **one reviewer** — not a screenwriter, and
not the writer of those pages.

Only a writer can say whether a note about their own script is right. Gate 5 is
the step that replaces "our stand-in says so" with "writers agree", which is why
it is called *binding*: every other gate can be green while the true number is
still unknown.

It is also the only gate that can falsify the **design**, not just the
implementation. Gates 1–13 test whether the machinery does what it claims; this
one tests whether what it claims is what a writer wants.

---

## 2. The instrument (already built — do not improvise around it)

The **verdict channel** is in-product (`4246282`). Each finding card in the
Evidence lens carries a truth row:

| control | meaning |
|---|---|
| ✓ Correct | the note is true about my script |
| ~ Partial | true in part, or true but not worth acting on |
| ✗ Wrong | the note is false about my script |

It writes `finding_verdicts.json` beside the project. The desk's Coverage section
shows a live meter: `accuracy = (correct + partial) / judged`, with the judged
count beside it, because a rate over 3 findings is not the same claim as a rate
over 300.

**The one thing to get right:** the writer must mark **truth**, not intent. The
row below it (addressed / deferred) is a different question and is deliberately
separate — "it's true but I won't act on it" must be expressible, or the metric
collapses back into the ambiguous middle that made it unmeasurable.

**Two surfaces added 2026-10-07 — both are in the instrument, and neither is decoration:**

| surface | what it shows | why the study cares |
|---|---|---|
| **"Also flagged under" disclosure** (deep card) | the findings the dedupe **absorbed** into the survivor, with their own rule, severity, issue, observation and quote — collapsed by default | Until `65f4b9a` this content was preserved in the data and **readable by nothing**. If writers never open it, the merge is still a silent collapse to them and the fix bought nothing. |
| **Run caveat** (above the model line) | a plain note that a chunk hit its output limit and was re-run in smaller pieces, so **this run's findings may differ from an uninterrupted one** | This is churn *disclosure*. Step 5 asks "do they notice what changed?" — this is the surface that answers it. If it appears and the writer cannot say what it means, the disclosure failed. |

Note the deliberate split: a run caveat renders **beside, never inside**, the failure banner. A
recovered run is healthy; dressing it as a failure would make the study measure a false alarm.

---

## 3. Recruitment

- **3–5 screenwriters.** Fewer than 3 gives no spread; more than 5 is beyond what
  a formative study needs.
- **Their own scripts.** Not a fixture, not a sample. The whole point is that the
  writer has ground truth the system does not.
- **No coaching during the session.** Answer questions about the interface; do
  not explain what the notes mean or which ones to trust. The first 10 minutes
  of confusion is data.
- One script per writer is enough. A writer with two may run both.

---

## 4. Session script (~60 minutes per writer)

| # | Step | Time | What to record |
|---|---|---|---|
| 0 | Consent + what is being tested. Say plainly: *this is a test of the tool, not of your writing.* | 5 min | — |
| 1 | Create a project, import their script, run Analysis. | 10 min | Did it complete? How long? Any error the writer noticed? |
| 2 | **Open the report cold.** No explanation. | 5 min | First reaction, verbatim. Do they find the findings? Do they understand what a finding is? |
| 3 | **Mark every finding** ✓ / ~ / ✗ using the truth row. | 15 min | This is the metric. Do not help. Note hesitation points. |
| 4 | Work the fix loop on the ones they marked ✓. | 15 min | Which do they act on? Do they recover when an edit cannot apply? |
| 5 | Re-run Analysis. | 5 min | Do they notice what changed? Do they find the Feedback-ledger section? |
| 6 | Debrief. | 10 min | The four questions in §5. |

**Facilitator notes:** if the writer stops marking and starts arguing with a
note, that is a *finding about the note* — record it. If they mark everything
✓ without reading, the study is void for that writer (say so in the write-up).

---

## 5. What is measured

Five outcomes, plus the number:

1. **Task completion** — did they get from import to a worked fix loop without
   facilitator rescue? Where did they stall?
2. **Mistaken acceptance** — did they act on a note that is wrong about their
   script? *This is the harm the whole design exists to prevent* (it is why the
   accuracy headline is the not-wrong reading, not the strict one).
3. **Recovery** — when something failed (an edit would not apply, a stale
   proposal, a damaged store), did they understand and recover, or did they
   conclude the tool was broken?
4. **Lost context** — did anything they had said or marked disappear between
   runs without explanation? (The Feedback-ledger section is the surface for
   this; watch whether they find it.) **And if a run caveat appeared, could they
   say what it meant** — that this run's findings may differ from an
   uninterrupted one? A caveat the writer cannot read is not a disclosure.
5. **Merge transparency** *(added 2026-10-07)* — on a card that says "also
   flagged under", did they open the disclosure and see the absorbed claims, or
   did they read the survivor as the whole story? If nobody opens it, the dedupe
   is still collapsing silently and §2's first new surface has failed.

Then the number:

- **Metric A (accuracy)** — `(correct + partial) / judged`, per writer and
  pooled, from their own verdicts. Report the **judged count** beside it, always.
- **Metric B (verifiability)** — the share of quoted findings whose citation the
  verifier confirmed, from the report's `verification_summary`.
- **Observation coverage** — `observation_pct` from `verification_summary`; the
  share of delivered findings that state a checkable claim. If this is low, the
  notes read as opinions and the writer will say so.

---

## 6. Pre-registered pass/fail bar

Written down **before** the sessions, so the result cannot be reinterpreted
afterwards:

| Result | Reading |
|---|---|
| Metric A ≥ 98.58 % pooled, ≥ 3 writers, **zero** mistaken acceptances | The target is met as a product metric. |
| Metric A 95–98.58 %, or any mistaken acceptance | The target is **not** met. Report the gap honestly; do not round up. |
| Metric A < 95 % | The design is wrong, not the implementation. Go back to the architecture, not to the prompts. |
| Fewer than 3 writers complete all steps | **No result.** Do not report a number from one writer. |

**Two things that invalidate a session:** the writer marked without reading, or
the facilitator explained what a note meant before the writer judged it.

---

## 7. Where the data lands

Per project, in the project directory:

- `finding_verdicts.json` — `{finding_id: correct|partial|incorrect}`. The metric.
- `feedback_ledger.json` — every run's delivered set, reconciled. Answers "did
  anything they marked vanish?".
- `report.findings.json` — `verification_summary` carries both rates. **Also read two fields added
  2026-10-06/07, because they are the run's own account of what it did:** `recoveries` (a list of
  writer-facing caveats; non-empty means a chunk was split, so this run's finding set is
  path-dependent) and, per finding, `merged_findings` (the absorbed findings' full content — the
  data behind the "Also flagged under" disclosure). `withdrawals` carries every removal with a
  reason, so `findings + withdrawals` reconciles against the pre-gate list.

Collect the project directories at the end. `verdict_accuracy()` reads them
directly; there is no separate export step and no second source of truth.

---

## 8. What would falsify the design (decide this now, not later)

Any of these means the architecture is wrong, and no prompt change fixes it:

- Writers routinely mark ✓ on findings they then admit are not true about their
  script → the notes are plausible-sounding, not checkable.
- Writers cannot tell a finding from an observation → the two-tier distinction
  is not carried by the UI.
- Writers ignore the truth row and only use addressed/deferred → the accuracy
  metric has no home in the product.
- Writers do not notice that a note from run 1 did not come back → the ledger is
  answering a question nobody asked.
- Writers never open the "also flagged under" disclosure, on any card, in any
  session → the merge fix is a **data** property with no **product** effect, and
  the dedupe is still collapsing silently from where the writer sits. *(Added
  2026-10-07; this is the honest test of whether PR #14 bought anything.)*

---

## 9. One honest sentence for the write-up

If the study has not been run, the correct claim is:

> **98.58 % is not demonstrated.** The machinery to measure it honestly exists
> and is tested; the number it produces is fed by one expert reviewer on two
> scripts. Gate 5 (3–5 writers, their own scripts) is what converts that proxy
> into a product metric.
