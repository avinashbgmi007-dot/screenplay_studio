# Gate 5 — the writer study: protocol and instrument

**Status:** READY TO RUN — **§3.5 pre-flight: steps 1, 2 and 4 (machine half) DONE 2026-10-07; step 3
outstanding** (`GATE5_PREFLIGHT_2026-10-07.md`) — step 3 (one desk session, ~10 min) is the owner's, and
step 4's per-session recording happens before each writer signs.
**Owner:** you (it needs 3–5 real screenwriters; no code can produce it).
**Date written:** 2026-10-06. **Revised 2026-10-07** — §2, §5, §7 after PRs #11–#14 landed; **§3.5, §4, §6
after an operational review** that found the session was budgeted at ~1 hour for ~2 hours of work, the
metric was misnamed "accuracy", and an untested surface could have been reported as a passed one.
**Run against:** `origin/main` = **`65f4b9a`**. Pin this commit for the sessions — a study whose
build is unstated is not reproducible, and reproducibility is exactly what Gate 7 is about. Later commits
on `main` are documentation only, so the pin holds. If `main` moves again, re-read §7's field list.

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
over 300. **⟲ The product labels it "accuracy"; read it as the *not-wrong* rate**
(§5) — `partial` counts as acceptable, so it is not a correctness rate.

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

## 3.5 Pre-flight, consent, and surface exposure *(added 2026-10-07)*

### Pre-flight — run this once, before the first session, with no writer present

> **Status 2026-10-07: steps 1, 2 and 4 (machine half) are DONE; step 3 is the owner's** — see
> `GATE5_PREFLIGHT_2026-10-07.md`. Measured on `Pain_3` with qwen3.6: **30.4 min**, and **both surfaces
> appear** (30 merges → **15 of 61** delivered rows carry `merged_findings`; **1** run caveat).
> **Step 3 needs a desk session**, because `finding_verdicts.json` and `feedback_ledger.json` are written
> by the product, not the analyzer.
>
> **Step 4 has two halves, and only one is a pre-flight measurement.** Its *machine* half is done (the
> endpoint is loopback — `cli.py:36`, and the server is bound to `127.0.0.1:8080`, not `0.0.0.0`); its
> *per-session* half — filling the consent form's endpoint table — is **outstanding by design**, because it
> happens before each writer signs and cannot be discharged before a session exists. So the pre-flight is
> **not** complete yet, and this block must not be read as saying it is.
>
> **The trap, recorded:** the *stored* payloads could **not** have answered step 2. They predate the fix
> (PR #11/#13), so they carried `stats.findings_merged` (29 / 5) while **0** rows carried
> `merged_findings`. A pre-flight run against them would have reported "surface absent" and been wrong.
> **Run the pre-flight on the build being tested.**

1. **Time the analysis on this machine**, on a script of comparable length. Read `stats.runtime_minutes`
   from the finished report; do not estimate it. The 30.4 / 33.8 min figures in §4 are from one laptop
   with ~half the model on CPU — **your number may differ, and it is the one you quote to participants.**
2. **Confirm both surfaces appear at least once** (see below). If they do not, you have not tested them.
3. **Confirm the data lands** — `finding_verdicts.json`, `feedback_ledger.json`, and `report.findings.json`
   with non-empty `recoveries` where a split occurred.
4. **Verify the model endpoint is on this machine** — *(added 2026-10-07)*. The consent form promises the
   script never leaves the machine, and the writer cannot check that. The analyzer sends the script text
   to whatever `--server` names, and it **explicitly supports a remote OpenAI-compatible endpoint**
   (`cli.py`'s `--server` + `--api-key`, or `SCREENPLAY_STUDIO_API_KEY`). The promise therefore holds only
   if the endpoint is local: **confirm the host resolves to loopback (`127.0.0.1` / `localhost`) and record
   it on the consent form.** If it does not, reconfigure to a local server or stop — "nothing is
   transmitted" is not something the product's design can guarantee on its own.

### Informed consent — the scripts are unpublished IP

**Use the form:** `GATE5_CONSENT_FORM_2026-10-07.md` — one page, handed to the writer before import,
signed by both. It carries the terms below in a form they can actually read and keep.

This is a **privacy-first, local** product, so the study should be too, and the terms must be agreed
**before** import, not after:

- **Where the data lives:** the project directory on the machine running the study. State the path.
- **What is collected:** their script, the generated report, `finding_verdicts.json` (their judgements),
  and `feedback_ledger.json`. **Nothing is transmitted off this machine** — say this explicitly, because
  it is the product's premise and the writer has no way to verify it — **but only after pre-flight step 4
  confirms the model endpoint is local.** The claim is conditional on that check, not on the product's
  design; `GATE5_CONSENT_FORM_2026-10-07.md` §3 carries the verification table.
- **Retention and deletion:** agree a retention period and a deletion date; the writer may withdraw and
  have the project directory deleted at any point, including after the session.
- **Quoting:** ask separately for permission to quote their verbatim reactions in the write-up. A quote
  about their own pages can identify them.
- **Anonymise in the write-up:** writer IDs (`W1`…`W5`), not names or script titles.

### Surface exposure — an untested surface is not a passed surface

Two surfaces added 2026-10-07 (§2) appear **conditionally**, so a session can run cleanly and never show
either. Record exposure explicitly and report it honestly:

| surface | appears when | observed so far (a few runs — an observation, not a rate) |
|---|---|---|
| **"Also flagged under" disclosure** | the dedupe merged two findings under one rule | seen on every feature-length run: merge counts **29 / 30** on `Pain_3`, **5** on `gun_pen`. Row-level *content* confirmed post-fix on the 2026-10-07 run only (**15 of 61** rows). Expect it, but do not report it as a base rate. |
| **Run caveat** | a chunk hit its output limit and was split | **rare** — one chunk on the qwen `Pain_3` run, absent on others. May not appear in a given session at all. |

**Rule:** if a participant never saw a surface, that surface was **not tested**. Write "not exercised" in
the write-up — never "passed". If you want it tested deliberately, add a short **post-marking walkthrough**
(step 3.5 of the session) that opens one merge disclosure on screen and asks the writer to read it aloud;
record that as a **facilitated** observation, clearly separated from the unprompted findings.

---

## 4. Session script (~2 hours per writer — **revised 2026-10-07**)

> ⟲ **The original 60-minute budget was wrong by ~3× and is retracted.** It gave Analysis **10 min**.
> The report records its own wall-clock as `stats.runtime_minutes`, and the measured payloads are:
> **`Pain_3` (22 scenes) = 30.4 min** (gemma) and **33.8 min** (qwen, `I2_MEASUREMENT_2026-10-06.md`);
> `gun_pen` (3 scenes) = 4.9 min. A feature-length script is a **~30-minute** wait, and step 5 re-runs
> it — so the honest session is **~2 hours**, not one. Do the **pre-flight** in §3.5 first; that number,
> on your machine, is the one to quote to participants.

| # | Step | Time | What to record |
|---|---|---|---|
| 0 | Consent, privacy, and what is being tested (§3.5). Say plainly: *this is a test of the tool, not of your writing.* | 10 min | Signed consent; script-storage and deletion terms agreed. |
| 1 | Create a project, import their script, run Analysis. **Start it, then brief while it runs.** | **~30 min** (measured) | `stats.runtime_minutes`. Did it complete? Any error the writer noticed? |
| 2 | **Open the report cold.** No explanation. | 5 min | First reaction, verbatim. Do they find the findings? Do they understand what a finding is? |
| 3 | **Mark findings** ✓ / ~ / ✗ using the truth row. **Do not require every finding** — a full census of 73 findings in 15 min is 12 s each, which is skim-reading. Ask for **one category in full plus a sample of the rest**, and record how many were judged. | 20–25 min | This is the metric. Do not help. Note hesitation points. **Record the judged count** — it is the denominator, and a partial census is legitimate. |
| 4 | Work the fix loop on the ones they marked ✓. | 15 min | Which do they act on? Do they recover when an edit cannot apply? |
| 5 | **Re-run Analysis.** | **~30 min** (measured) | Do they notice what changed? Do they find the Feedback-ledger section? **And: did a run caveat appear, and could they say what it meant?** |
| 6 | Debrief. | 10 min | The five outcomes in §5. |

**Split it if the writer prefers:** session A = steps 0–3; session B = steps 4–6. The two Analysis runs
are long waits, not work, and a single 2-hour sitting will exhaust attention before the fix loop — which
is the step that tests the product's core loop. **Do not compress the waits by lowering the script size**;
a short script under-tests exactly the passes that truncate.

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

- **Metric A (the *not-wrong* rate)** — `(correct + partial) / judged`, per writer and pooled, from their
  own verdicts. **⟲ Name it the not-wrong rate, never "accuracy".** `partial` is counted as acceptable
  by construction, so the number answers *"how often is a delivered note not false?"* — it does **not**
  answer *"how often is a note right?"*. Always report it **with the three raw counts**
  (`correct / partial / wrong`) **and the judged count**. A rate without its numerator is unreadable.
- **Metric B (verifiability)** — the share of quoted findings whose citation the
  verifier confirmed, from the report's `verification_summary`.
- **Observation coverage** — `observation_pct` from `verification_summary`; the
  share of delivered findings that state a checkable claim. If this is low, the
  notes read as opinions and the writer will say so.

---

## 6. Pre-registered pass/fail bar

Written down **before** the sessions, so the result cannot be reinterpreted
afterwards. **⟲ Revised 2026-10-07: the bar is a falsification test, not a proof.**

### First, what 3–5 writers can and cannot establish

This is **formative** evidence. It can **falsify** the design and **expose** gaps. It **cannot** prove a
population-level rate, and it must never be written up as doing so.

**The unit of analysis is the writer, not the finding.** Findings cluster within one script and one
writer, so pooling 73 findings × 5 writers does not give 365 independent observations — a finding-level
rate would badly overstate precision. Report **per writer, then pooled**, and say the clustering out loud.

**The zero-event case, stated honestly.** If no writer commits a mistaken acceptance, the 95 % upper
bound is roughly **3/n** (*rule of three*). With 5 writers that is **≈60 %** — i.e. five clean sessions
are consistent with a majority of writers being misled. That is not a defect in the study; it is the
study telling you the truth about its own power, and it is **why "98.58 % is demonstrated" can never be
the claim here.** Say this in the write-up before anyone else does.

### The bar

| Result | Reading |
|---|---|
| **Zero** mistaken acceptances, and the not-wrong rate **≥ 98.58 % pooled** across **≥ 3** writers | **No falsification observed in this sample.** The design survives. It is **not** proof of the target. |
| Not-wrong rate **95–98.58 %**, or **any** mistaken acceptance | The target is **not** met. Report the gap honestly; do not round up. |
| Not-wrong rate **< 95 %** | The design is wrong, not the implementation. Go back to the architecture, not to the prompts. |
| Fewer than **3** writers complete all steps | **No result.** Do not report a number from one writer. |
| A participant never saw a surface (§3.5) | That surface is **"not exercised"**, never "passed". |

**Three things that invalidate a session:** the writer marked without reading; the facilitator explained
what a note meant before the writer judged it; or the session ran on a build other than the pinned commit.

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
- Writers ignore the truth row and only use addressed/deferred → the not-wrong
  rate has no home in the product.
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

**And after it has been run, the ceiling on what may be claimed is a *falsification* result.** The
strongest defensible sentence is:

> **The design survived N writers without a mistaken acceptance; the pooled not-wrong rate was X %
> over M judged findings (c₁ correct / c₂ partial / c₃ wrong). This is formative evidence: N writers
> cannot establish a population rate, and with zero wrong verdicts the 95 % upper bound on the
> writer-level error rate is ≈3/N.**
