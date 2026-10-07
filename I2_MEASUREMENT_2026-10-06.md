# I2 — measured, not argued

**Date:** 2026-10-06 · **Commit:** `e67ce6e` (on `origin/main` = `b6652a6`) · **Model:** `qwen3.6-35b-a3b-pruned-v2.gguf` on `:8080`
**Scripts:** `Pain_3` (22 scenes), `gun_pen` (3 scenes) · **Shipped defaults:** integrity gate ON, observation pass ON
**Product code changed:** none (runtime instrumentation only)
**Raw data:** `C:/tmp/ss_probe/i2_report.json` · **Instrument:** `C:/tmp/ss_probe/i2_probe.py` · **Cause proof:** `i2_cause.py`

> **Revision 6 (2026-10-06, THE FIX — measured).** All four recommendations below were executed and the
> instrument was re-run on the same scripts and model. **§9** reports it: budgets raised → the discard
> rate **halved** (Pain_3 16/74 → 7/64; gun_pen 1/38 → **0/36**) and **every pass except dialogue now
> completes with zero discards** — including `character_dials`, whose pass had been **failing outright**.
> Two of my own conclusions were wrong and are corrected in §9.3: `character` did **not** need chunking
> (8000 sufficed on the first attempt), and §4.1's dedupe content loss is **fixed**, not merely
> diagnosed. The observability fix (§8.2) **fired live** in the re-run.
>
> **Revision 5 (round-7 review).** Two additions. §2.3 is a **controlled test** of the open question —
> does chunk-backoff splitting recover the output? It does (**recovered: yes**), but **not
> equivalently** (12 findings vs 8 on the same input), which turns the question into a
> **reproducibility** gap rather than just an audit gap. Also tightened: §5 now scopes the receipt
> design to **both** payloads; §8.2 states plainly that the observability fix is **not** retention;
> §3.1 demotes "chunking" from the remedy to a candidate; §6.1 narrows "visible" to "not excluded by
> the two defaults I read".
>
> **Revision 4 (round-6 review, re-measured).** The review asked for per-call evidence instead of a
> derivation, so I instrumented logical call ids and re-ran Pain_3. **It refuted my own claim.** The
> derived "16 rescued / 1 exhausted" is **wrong**; measured is **7 rescued / 9 exhausted** — and the
> derivation's premise was false, because `_with_chunk_backoff` hides an exhausted call from
> `category_outcomes` (§2.2). The re-run also proved truncation for **16 of 16** discards (§3.1) and
> **broke my own recommended fix**: the `character` pass already runs at 4000 tokens and truncated a
> 17,437-char reply. §8 is rewritten. Also corrected: §4.1's counts are scoped to these runs, §6.1
> fixes a *second* error in my UI correction, §5 adopts the two-distinct-needs framing.
>
> **Revision 3 (round-6 review).** Verified the saved artifact holds **no `call_id` and no
> `finish_reason`** — so §2.1's split was *derived, not observed*, and §3's "13 directly explained" was
> too strong.
>
> **Revision 2 (round-5 review).** Five corrections applied: a retry-outcome mapping was added (§2.1);
> §3's title no longer over-claims the scope of the proof; §4's merge claim was **corrected and is now
> a finding against the dedupe, not for it**; §5's decision rule was narrowed; and §6 **retracts** the
> "70% hidden by the default filter" claim, which was **wrong**. Corrections are marked ⟲.

This settles the question four rounds of review kept circling: *is the receipt ledger a subsystem or a
guard test?* The measurement found the real problem — and it is not the one the draft is aimed at.

---

## 1. What was measured

Two different hops, deliberately **not pooled**:

- **I2a — capture.** Every HTTP attempt; for each, did a body arrive, and did it parse? A body that
  arrives and does not parse is discarded unretained (`llm_client.chat_json`, retry ladder at
  `llm_client.py:180-213`, keeps only an error *string*).
- **I2b — delivery.** Every feedback item traced through each deterministic disposition stage to the served set.

Method: wrap `_post_chat`, `_extract_json`, `_normalize_findings`, `filter_findings` (both call sites),
`dedupe_related_findings`, `collapse_exact_duplicates`; run the shipped path; compare against
`report.to_findings_json` and `webapp_server._sanitize_report`. No product file was edited.

---

## 2. I2a — response bodies discarded, and what happened to each call

| | gun_pen | Pain_3 | **pooled** |
|---|---:|---:|---:|
| HTTP requests | 38 | 74 | 112 |
| bodies received | 38 | 74 | 112 |
| **bodies discarded unparsed** | **1** | **16** | **17** |
| **rate** | 2.6% | **21.6%** | **15.2%** |
| attempts with no body (timeout / connection error) | 0 | 0 | 0 |
| HTTP statuses | 200 ×38 | 200 ×74 | all 200 |

**Every discard is an HTTP 200 response.** Nothing failed at the network.

Discards by pass (pooled): **dialogue 13 · character_dials 3 · char_reads 1**.
Discarded body size: **min 4,656 / mean 5,053 / max 6,527 characters.**

### ⟲ 2.1 Retry outcome — was the body the only casualty, or the output too?

The counts above are **attempt-level**, not call-level: 17 unparsed bodies is not 17 lost findings.
My first attempt to map them to calls used the category-level outcomes — and **§2.2 shows that method
was unsound and its answer wrong.** The measured split is in §2.2.

~~**Result: 17 discards → 16 rescued by a later attempt → 1 call exhausted its ladder.**~~
**REFUTED by §2.2. The derivation below is unsound — see the retraction.**

⟲ **Two retractions stacked here.** (a) My first draft said "the retry ladder isn't rescuing the call"
— too broad, withdrawn. (b) My Revision 2 replacement ("the ladder rescued 16 of 17") is **also
withdrawn: §2.2 measures 7 rescued / 9 exhausted.** The ladder is both *expensive* and, on this
script, *insufficient* for 3 calls.

### ⟲ 2.2 The measured split — and why the derivation above was unsound

Run 1 saved only summaries, so I re-ran Pain_3 with a `chat_json` wrapper that stamps every HTTP
attempt with its **logical call id** and records each call's outcome. Observed (run 2, 73 attempts,
16 discards):

| | count |
|---|---:|
| logical calls | 60 |
| calls that ended `ok` | 57 |
| **calls that EXHAUSTED the ladder** | **3** |
| discards inside **rescued** calls | **7** |
| discards inside **exhausted** calls | **9** |

| call | pass | attempts | discards | outcome |
|---|---:|---:|---:|---|
| #10 | dialogue | 3 | 2 | ok |
| **#14** | **dialogue** | 3 | 3 | **exhausted** |
| #18 | dialogue | 2 | 1 | ok |
| **#20** | **dialogue** | 3 | 3 | **exhausted** |
| #21 | dialogue | 2 | 1 | ok |
| #24 | character | 2 | 1 | ok |
| #31 | char_reads | 2 | 1 | ok |
| **#33** | **character_dials** | 3 | 3 | **exhausted** |
| #36 | genre | 2 | 1 | ok |

**So the derived 16/1 was wrong: the measured split is 7 rescued / 9 exhausted.** Worse, the
derivation's premise was false, and the code says why:

**`category_outcomes == 'ok'` does NOT imply every call succeeded.** Calls #14 and #20 exhausted their
ladders — and `dialogue` is still recorded `ok` with **no `errors` entry**, because
`_with_chunk_backoff` (`pipeline.py:96-123`) catches the `LlamaServerError`, **splits the chunk in half
and retries the halves**. When the halves succeed, no error is ever recorded. An exhausted call is
therefore **invisible at the category level**. Only `character_dials` surfaced, because its failure
path does not absorb it the same way.

**This is a genuine visibility gap, and it is the strongest evidence yet for the retention contract:**
a run can report `dialogue: ok` while two of its calls burned their entire ladder and discarded 6
bodies. Nothing in the run-level accounting says so.

**What this does NOT establish:** whether those two dialogue chunks lost *output*. This instrument does
not link a split back to its parent call, so "exhausted call ⇒ lost output" was **not** proven — §2.3
tests it directly. What *is* proven here: 9 bodies were discarded inside calls that exhausted, and at
least one of those (character_dials, `errors[0]`) lost its output outright.

### ⟲ 2.3 Controlled test: does chunk-backoff splitting recover the output?

Direct test (`i2_split.py`): run the gun_pen dialogue pass twice, forcing **only the first `chat_json`
call** to a `max_tokens` of 300 (guaranteed truncation) so `_with_chunk_backoff` must split it.

| | `chat_json` calls | findings returned | errors |
|---|---:|---:|---|
| **control** (no forced failure) | 2 | **8** | none |
| **forced** first-call truncation | 4 (1 exhausted + 3 ok) | **12** | none |

**Recovered: YES. Equivalent: NO.**

- **The separation the review asked for is now measured.** The forced run's first chunk discarded 3
  bodies and exhausted its ladder — and the scenes *were still analysed*: 12 findings came back with no
  error recorded. So **"raw response lost" does not imply "finding output lost"** (except where the
  split itself cannot help, as with `character_dials`).
- **But the output is not equivalent — 12 vs 8.** Splitting the chunk into smaller prompts changes the
  finding set (more granular output per half). So **whether a transient truncation happens changes the
  analysis result**: the same script yields 8 or 12 findings depending on an unrelated failure.
- **Cost: 4 calls vs 2** — 2× the model work for the same input.

**Consequence for §2.2:** the two exhausted dialogue calls in run 2 most likely did *not* lose output —
so "9 discards inside exhausted calls" must **not** be read as "9 lost findings". The bodies were lost;
the output was probably recovered, but **not identically**.

**Consequence for the retention case:** this strengthens need (1). Without a receipt you cannot tell
whether a run's findings came from the direct path or from a split — and the two paths yield **different
results**. That is a **reproducibility** gap, not only an audit gap.

---

## 3. The cause: truncation at the output budget ⟲ (was: "proven for dialogue, inferred for the other two")

Every discarded body belongs to a long-output pass, and the discard count scales with the reply's size
against that pass's `max_tokens`:

| pass | `max_tokens` | source | reply size observed | discards |
|---|---:|---|---:|---:|
| character_dials | 1800 | `dials.py:44` | 6,048–6,527 | **3 / 3 → pass failed** |
| dialogue | 1200 | `pipeline.py:545` | 4,656–4,927 | **13** |
| char_reads | 1200 | `pipeline.py:594` | 4,875 | **1** |
| setup_payoff | 2000 | `setup_payoff.py:78` | — | 0 |
| coverage | 900 | `pipeline.py:571` | — | 0 |
| observation | 500 | `observation_pass.py:239` | small | 0 (24 calls each) |

Passes whose budget clears their output lost **nothing**.

**Direct proof — dialogue only.** Re-issuing the exact dialogue call that lost bodies (gun_pen, one chunk):

```
max_tokens=1200  → finish_reason=length   completion_tokens=1200  content_len=4989  parsed=False   127.8s
                   finish_reason=length   completion_tokens=1200  content_len=4916  parsed=False
                   finish_reason=length   completion_tokens=1200  content_len=4788  parsed=False
max_tokens=4000  → finish_reason=stop     completion_tokens=1671  content_len=6422  parsed=True     55.7s
                   findings=8
```

`completion_tokens=1200` is *exactly* the cap on all three attempts; the reply needed **1,671**. It was
cut mid-JSON — the captured tails end inside a finding object — which is why `_extract_json` cannot
salvage it.

### ⟲ 3.1 The cause is now proven for EVERY discard — and it is worse than the replay suggested

Revision 2 claimed "13 of 17 directly explained"; Revision 3 downgraded that to "one call proven". The
instrumented re-run settles it: the probe now captures `finish_reason` per attempt, and run 2 reports

```
discarded bodies with finish_reason=length : 16 of 16
finish_reason histogram: {'length': 16}
```

with `completion_tokens == sent_max_tokens` on every single one. **Truncation at the output budget
explains 100% of the discards**, across dialogue, char_reads, character_dials, genre **and character**.

**And it breaks my own recommended fix.** The `character` pass runs at `SCRIPT_LEVEL_MAX_TOKENS`
(`pipeline.py:563`), which the payload shows is **4000** — and it still truncated:

| pass | sent `max_tokens` | reply reached | discarded |
|---|---:|---:|---|
| character | **4000** | **17,437 chars** | yes |
| character_dials | 1800 | 5,887–6,339 | yes |
| dialogue | 1200 | 4,648–5,208 | yes |
| char_reads | 1200 | 4,690 | yes |
| genre | 1200 | 4,870 | yes |

⟲ **Correction to §8:** "raise everything to 4000" is **wrong** — 4000 is already the `character`
pass's budget and it is insufficient by a factor of ~4. Budgets must be **sized per pass against the
observed reply length**. That much is established.

⟲ **What is NOT established:** that chunking is the fix for `character`. A 17,437-char reply against a
4,000-token cap shows the *reply* exceeded the cap; it does not show *why* the reply was that large, nor
that splitting the input would shrink it. Chunking is a **candidate** and needs its own controlled test
(split the `character` prompt, compare reply size and finding quality) before it is called the remedy.

⟲ **Scope of the proof:** `finish_reason` was captured **only** for the dialogue call, in a follow-up
run. The char_reads (1) and character_dials (3) discards are **inferred** from the same signature
(long body, valid-JSON head, budget below output size) — they were **not** directly reproduced. So this
is "one proven cause covering the majority, plus a consistent inference for the rest", not "one
constant explains all 17".

**The fix is also faster on this call.** 127.8s across three truncated attempts versus 55.7s on one that
succeeds. *n=1* — one call's timings, not a benchmark.

---

## 4. I2b — counts reconcile; content preservation is NOT proven ⟲

| stage | gun_pen | Pain_3 |
|---|---:|---:|
| findings entering the shared list | 36 | 97 |
| non-writing filter (`pipeline.py:1108`) | −0 → 36 | −0 → 97 |
| cross-rule dedup (`pipeline.py:1117`) | −6 → 30 | −23 → 74 |
| exact-duplicate collapse (`pipeline.py:1131`) | −0 → 30 | −0 → 74 |
| integrity gate (`pipeline.py:1143`) | −1 → 29 | −1 → 73 |
| **delivered** | **29** | **73** |
| serve-time filter (`webapp_server.py:894`) | −0 → 29 | −0 → 73 |
| **served** | **29** | **73** |
| count residual | **0** | **0** |

**The measured counts reconcile exactly on both runs.** That is the claim — *not* that every original
item's content is proven preserved.

### ⟲ 4.1 The dedupe is declared, but its absorbed text is unrecoverable

My first draft cited `merged_rule_ids` as evidence that merges are not a silent drop. **That was too
strong, and the code says so.** `dedupe.py:206-221`:

```python
survivor = dict(findings[survivor_idx])          # copies ONLY the survivor
others   = [findings[i] for i in members if i != survivor_idx]
merged_refs = [o.get("rule_id") for o in others if o.get("rule_id")]
survivor["merged_rule_ids"] = merged_refs
survivor["why_it_matters"] += "Also flagged under: " + ", ".join(merged_refs) + "."
```

The absorbed findings are dropped. What survives is a list of **rule-id strings** and one prose clause.
Their `issue`, `evidence_quote`, `observation` and `severity` are retained **nowhere** — unlike the
integrity gate, whose `withdrawals` ledger stores each removed finding's **full content**
(`finding_integrity.py:187-192`).

So on Pain_3, **23 findings were merged and their text is unrecoverable**; on gun_pen, 6 — *in these two
measured runs*. The mechanism is unconditional (whenever the dedupe merges, the absorbed text is
dropped), but the **counts are run-specific** and should not be generalised without repeats. The
operation is *visible* to the writer ("Also flagged under: …") but its content is *not* inspectable.

**This relocates part of the receipt ledger's concern.** Beyond the discarded bodies (§2.2 — 9 of 16 sat
inside calls that exhausted their ladder, and the run reported `dialogue: ok` anyway), there is a second
unrecoverable-content loss: the **dedupe**, which discards the absorbed findings' text whenever it
merges. That is the strongest evidence yet for the
draft's "nothing lost" requirement, and it sits at `pipeline.py:1117`, not at the client boundary the
draft instruments. Note also that the integrity gate's full-content ledger runs **later**
(`pipeline.py:1143`) and therefore **cannot cover these earlier merges** — the two are not
interchangeable.

⟲ **FIXED 2026-10-06 — see §9.** The survivor now carries **`merged_findings`**: the absorbed findings'
full content, alongside `merged_rule_ids`, matching the integrity gate's `withdrawals` contract. It is
delivered on `/findings` (`_fixqueue_items`) and documented in `DATA_FORMATS.md`, so the Gate 8 delivery
guard covers it. The analysis above stands as the **diagnosis**; the loss it describes no longer occurs.
`merged_rule_ids` is still *not* proof of preservation — it is attribution. `merged_findings` is the
claim.

---

## 5. What this does to the receipt ledger

**Its premise is confirmed; its target is wrong.**

- **Confirmed:** response bodies *are* discarded unretained, frequently (22% on the large script), as
  valid HTTP 200 payloads — and **100% of them are truncated at the output budget** (§3.1).
- **Corrected (was wrong):** I claimed 16 of 17 were rescued and only one call lost output. Measured:
  **9 of 16 discards sit inside calls that exhausted their ladder** (§2.2). The earlier figure came
  from a derivation that `_with_chunk_backoff` invalidates.
- **NEW — a visibility gap, and the strongest argument for the contract so far.** A run can report
  **`dialogue: ok`** while two of its calls burned their entire retry ladder and discarded 6 bodies,
  because the chunk split absorbs the failure silently. Run-level accounting says nothing is wrong.
  **A guard test would catch this; only capture would preserve it.**
- **Relocated:** the other unrecoverable-content loss is the dedupe (§4.1) — 23 findings merged on
  Pain_3 in run 1.
- **What a receipt store would buy:** the ability to see what the model actually said — including for
  the calls the run reports as `ok`. That is now a *stronger* case than the draft made, because the
  loss is invisible in the run's own accounting.
- **What it still would not buy:** it would fix none of the truncation; §8.1 does that.

⟲ **Decision rule, narrowed — and the source shows TWO distinct needs, not one.**

My first draft said "guard test if the rate falls to ~0, subsystem if it persists". That conflated
things that should stay apart:

1. **Raw response capture, at the client boundary.** Governed by a retention *contract*, which is a
   product decision and **not** empirically decidable. A low post-fix discard rate does **not** waive
   it — malformed responses, future schemas, retries and other APIs stay in scope regardless.
2. **Full-content disposition records, for items merged later.** This is the §4.1 case, and it is
   already observed: the cross-rule dedupe drops absorbed finding text on every merge, and the
   integrity gate's ledger runs **after** it and cannot cover those merges.

**Correction to my own earlier framing:** I offered "a guard test" as the low-rate outcome. That is
wrong as a substitute — **a guard test can *detect* a dropped response; it cannot *preserve* one.**
Detection and retention are different properties, and only the second satisfies the contract.

**Where the budget fix sits:** it is a **root-cause experiment, not a contract remedy**. It cannot
restore bodies already truncated, and it does not touch need (2) at all. Run it to *size* the residual
discard rate and to stop paying 3× for truncated calls — not to settle whether capture is required.

⟲ **The scope of the receipt design is therefore BOTH payloads, not one:**

- **raw response bodies** — including for calls the run reports as `ok` (§2.2); and
- **full-content links/dispositions for merged findings** — the §4.1 dedupe case, which the integrity
  gate's later ledger cannot cover.

Revision 2 said the case was "(2), not (1)". That was wrong: §2.2 supplied an independent case for (1),
because a run can report `dialogue: ok` while its calls exhausted their ladders. Both are concrete,
both are measured, and no budget change touches either.

**And the observability fix (§8.2) addresses neither** — it makes the failure detectable, not recoverable.

**A third property, measured in §2.3, that no budget change fixes: reproducibility.** The same input
produced **8 findings** on the direct path and **12** when a chunk was forced to split. A transient
truncation therefore changes the analysis result, and without a receipt there is no way to tell which
path a given run took. That is a distinct concern from retention and it belongs in the same design
conversation.

---

## 6. RETRACTED — the "70% hidden by the default filter" claim was wrong ⟲

An earlier draft claimed the desk opens highs-only and that 70% of served feedback is therefore
invisible by default. **Withdrawn. It is false for the shipped app.**

```
app.js:34-41
  // ONE filter: drives ink, board, loop, fix queue, counts (R5-b + GAP-1).
  // Default = ALL severities (2026-09-20 UI audit, defect #1): the dock's mass
  // strip counts every finding, so a highs-only default made the room read
  // "6 open of 6 findings" over "0 shown / 6 total" — a self-contradiction that
  // destroyed trust in every number. Show the ledger whole; the writer narrows
  // with the chips.
  findingFilter: { severities: ["high", "medium", "low"], ... }
```

It matches the checked-in spec (`2026-09-22-one-feedback-room-design.md:82`: "all live findings, highs
first").

**Where the error came from:** I took the default from `docs/PAIN3_SESSION_RUN_CARD.md` ("the desk opens
highs-only"). That run card describes a **demo-model session** and is stale against the 2026-09-20 fix.
`app.js:41` is the shipped truth. This is the **second** time in this engagement I asserted a UI default
without reading the checked-in record — the same class of error as the scene-default proposal.

**Corrected statement:** on Pain_3, 22 of 73 served findings are `high` and 51 are medium/low. That 51 is
a severity *distribution*, not a hidden count, and nothing about the default scope should be argued
from it. The instrument's field name `hidden_by_default_ui_filter` is **misnamed** and should read
`not_high_severity`.

### ⟲ 6.1 Second correction — "all 73 visible" was still too strong

I quoted `app.js:41` and read only the severities half of it. The same line also carries the
**disposition** filter:

```js
findingFilter: { severities: ["high", "medium", "low"],
                 showDeferred: false, showAddressed: false, category: null, scene: null },
```

So the desk **does** hide findings by default — not by severity, but by **disposition**: anything the
writer has marked *addressed* or *deferred* is filtered out (`findingCounts`, `app.js:7446+`, treats
only `open` as open and parks deferred/dismissed/ghosted out of both counters).

⟲ **Precise claim, narrowed again.** All I can support from `app.js:41` is: the 73 served findings are
**not excluded by those two default filters** — severity admits all three levels, and disposition admits
`open`. That is a statement about the *filter state*, not about rendered output.

I did **not** check the Context disclosure, any other disposition filter (dismissed/ghosted), scene
scoping, or the actual rendered DOM. So "visible" here means "not filtered out by the two defaults I
read", not "confirmed on screen". The earlier phrasing — "all 73 are visible" — asserted the stronger
thing and is withdrawn.

---

## 7. Limitations of this measurement

- **The residual (−4 / −12) is my instrument's units error, not a product anomaly.** `extracted` sums
  the inputs to `_normalize_findings`, which wraps only dialogue and the script-level categories. Voice,
  subtext, idiolect, continuity, drag (`pipeline.py:801–835`), principles (`:941`) and plot_thread
  (`:988`) append to `all_findings` directly. Reconcile from the pre-filter list instead.
- **§2.1's retry mapping was derived and is now REFUTED** (§2.2). The measured split comes from run 2's
  call-id instrumentation, and **run 1 still has no per-call data** — so the 16/1 figure should not be
  quoted for run 1 at all.
- **§3.1's cause is proven on run 2's 16 discards.** Run 1's attempts were never instrumented with
  `finish_reason`, so the proof is one run, not both.
- **The instrument still does not link a chunk-backoff split to its parent call.** §2.3 answers the
  *general* question by controlled test rather than by linkage, so it shows splitting *can* recover
  output — it does not prove that run 2's specific calls #14 and #20 were recovered.
- **§2.3 is n=1 per arm** on one script (gun_pen, 2-scene chunk). The 8-vs-12 gap is one observation of
  a non-equivalence, not a measured distribution of it.
- **n=1** on the 1200→4000 timing pair. Raising `max_tokens` also raises the ceiling on a degenerate
  loop, so the gain must be re-measured, not assumed.
- **Run-to-run variance is real and not quantified.** Same config, two Pain_3 runs: 74 vs 73 attempts;
  delivered 73 vs 76; withdrawals 1 vs 0; non-writing filtered 0 vs 1; discards 16 both times. Two runs
  is not a variance estimate.
- **Not verified:** whether a retry returns the *same* findings as the discarded attempt. That is
  precisely the provenance question, and it stays open.
- **§4.1 is a static reading of `dedupe.py`, not a runtime observation** of the absorbed content.
- The probe adds one wrapper per call; overhead is negligible but non-zero.

---

## 8. Recommended next step ⟲ (rewritten — the old #1 was wrong)

1. **Do not "raise everything to 4000".** §3.1 shows `character` is *already* at 4000 and truncated a
   17,437-char reply. Size each budget against its observed reply length, and treat `character` as a
   **chunking** problem: one reply is being asked to carry ~17 KB of findings. Candidates to measure,
   not assume: `pipeline.py:545` dialogue (1200), `:594` char_reads (1200), `dials.py:44` (1800),
   `pipeline.py:563` character (4000).
2. **Close the visibility gap — but do not mistake it for retention.** §2.2 shows a run can report
   `dialogue: ok` while two calls exhausted their ladders. `_with_chunk_backoff` should record the
   exhausted parent call in `result.errors` (or a counter) even when the split-halves succeed, so
   "we retried this chunk down to single scenes" is visible rather than silent.

   ⟲ **Scope, corrected:** this buys **observability, not preservation**. Logging an exhausted parent
   call does not retain the raw response and does not retain any merged finding's content. It makes the
   failure *detectable*; the two payloads the retention contract cares about stay unretained. It is a
   few lines and worth doing on its own merits — it is **not** a substitute for capture.
3. **Re-run I2** after (1) and (2) to size the residual discard rate — sizing the implementation, not
   deciding whether the contract exists.
4. **Address §4.1 separately.** The dedupe's absorbed text is unrecoverable whenever it merges, and the
   integrity gate's ledger runs later and cannot cover it. No budget change touches this.

⟲ **STATUS (2026-10-06): all four were executed and re-measured — see §9.** (1) budgets sized per pass
against measured reply length, and **`character` did not need chunking** (8000 sufficed, first attempt)
— that hypothesis was wrong; (2) the observability fix shipped and **fired live** in the re-run;
(3) I2 was re-run — the discard rate halved and dialogue is the one pass still truncating; (4) the
dedupe now preserves absorbed content — **§4.1 is FIXED**.

---

## 9. The fix, measured ⟲ — budgets raised, re-run, and what is left

Three code changes shipped against the findings in this document, then the same instrument was run
again, on the same two scripts, against the same model, with no other change.

### 9.1 The changes

| # | change | where |
|---|---|---|
| **(b)** | an exhausted-then-split chunk is recorded and surfaced to the writer | `pipeline._with_chunk_backoff` (+ `recoveries`), `pipeline._chunk_recovery_note`, `analyze()` |
| **(a)** | per-pass budgets sized against measured reply length, not a round number | `pipeline` (dialogue, char_reads, script-level), `dials.py`, `genre.py` |
| **(c)** | the dedupe preserves the absorbed findings' **full content** | `dedupe.dedupe_related_findings` → `merged_findings` |

Budgets: **dialogue 1200 → 3000**, **char_reads 1200 → 2500**, **character_dials 1800 → 3000**,
**genre 1200 → 2500**, **`SCRIPT_LEVEL_MAX_TOKENS` (character) 4000 → 8000**. Each is now a module
constant, and `tests/test_analyzer_prompt_sizing.py` pins every one above the cap that was measured to
truncate it.

### 9.2 The measured effect

| | run 2 (old budgets) | run 3 (raised) |
|---|---:|---:|
| gun_pen bodies discarded | 1 / 38 | **0 / 36** |
| gun_pen exhausted calls | 1 | **0** |
| Pain_3 bodies discarded | **16 / 74 (21.6%)** | **7 / 64 (10.9%)** |
| Pain_3 exhausted calls | 3 | **1** |
| Pain_3 delivered findings | 73 | 80 |
| Pain_3 wall | 1880 s | 2025 s |

Per pass, run 3:

| pass | old cap | new cap | run 3 outcome |
|---|---:|---:|---|
| character | 4000 | 8000 | **1 attempt, 0 discards** (was cut at 17,437 chars) |
| character_dials | 1800 | 3000 | **1 attempt, pass `ok`** (was `failed` — the dials panel came back empty) |
| char_reads | 1200 | 2500 | clean |
| genre | 1200 | 2500 | clean |
| **dialogue** | 1200 | 3000 | **7 discards — the only pass still truncating** |

Dialogue now truncates at **3000 tokens / ~12,200 chars** — roughly **4× the ~5,000-char reply** it was
producing under the old 1200 cap. Raising the budget did not merely stop cutting the reply; it revealed
that the reply had been cut to about a quarter of what the model wanted to say.

### 9.3 Two of my own conclusions were wrong, and the measurement says so

- **`character` did NOT need chunking.** §8.1 told you to treat it as a chunking problem. It needed a
  bigger constant: at 8000 it stopped on its **first attempt** with **zero discards**. The chunking
  hypothesis was an inference from a single truncated reply — the same class of error as the 16/1 split
  in §2.1. Measure; do not infer.
- **The observability fix is load-bearing, not cosmetic.** §8.2 argued it buys *detection, not
  preservation* — which is correct — but run 3 shows it also changes what the run can tell you. Its
  `result.errors` now carries: *"Dialogue analysis: the model's reply hit its output limit on 1 chunk(s)
  (scenes 11–12) and the chunk was re-run in smaller pieces…"*. Under run 2 that same event left
  `dialogue: ok` with an **empty** error list.

### 9.4 Dialogue: RESOLVED — and the answer is "do not raise it further"

The fork in §9.4 was whether dialogue's reply is **unbounded** (→ chunking) or needs a **larger
constant**. It was measured rather than assumed, by running the dialogue pass alone on Pain_3 at a
deliberately generous **8000**-token budget:

| call | finish_reason | completion_tokens | chars |
|---:|---|---:|---:|
| 1 | stop | 1098 | 4,548 |
| 2 | stop | 788 | 3,264 |
| 3 | stop | 2096 | 8,006 |
| 4 | stop | 1808 | 7,593 |
| 5 | stop | 1991 | 7,678 |
| 6 | stop | 736 | 3,158 |
| **7** | **length** | **8000** | **32,186** |
| 8 | stop | 942 | 3,894 |
| 9 | stop | 857 | 3,704 |
| **10** | **length** | **8000** | **31,656** |
| 11 | stop | 1437 | 5,816 |

**Two populations, and they are not the same phenomenon.** Nine of eleven chunks finished on their own
at **736–2,096 tokens**. Two filled the entire 8,000-token budget and emitted **~32,000 characters** —
four times the largest healthy reply. A 32 KB findings array for a three-scene chunk is not a script
doctor with more to say; it is the model looping.

**So the conclusion inverts the intuitive next step:**

- **3,000 is the right dialogue budget and should NOT be raised.** The healthy maximum measured is
  2,096 tokens, so 3,000 clears real work with ~1.4× headroom. At the old 1200, the cap sat *below*
  healthy replies (which run to 8,006 chars ≈ 2,096 tokens) — so 1200 was truncating genuine analysis.
  That is the defect (a) fixed.
- **What remains is degeneration, and a bigger cap makes it worse, not better.** A degenerate chunk
  fills *any* budget — at 8,000 it burned 4× the tokens of a healthy one. Raising the constant would
  convert a bounded waste into an unbounded one. This is why "raise everything to N" is the wrong
  reflex, twice over.
- **It is already mitigated, imperfectly.** `chat_json`'s retry ladder sometimes breaks the loop
  (temperature 0.3 gives variation), and `_with_chunk_backoff` splits the chunk once the ladder
  exhausts. Both worked here: `errors` is empty and the pass reported `ok`.

**Open, and deliberately not guessed at:** whether `chat_json` should *skip* its retries when
`finish_reason='length'` and fail fast so the split happens sooner. The evidence is **conflicting** —
run 2's dialogue call 14 truncated on all three attempts (three wasted generations), while two chunks in
this run recovered on the second attempt. Until that is measured, the ladder stays as it is.

### 9.5 Still open

- **Wall-clock cost.** Pain_3 1880 → 2025 s (**+7.7%**) while delivering 73 → 80 findings. gun_pen's
  1015 s is **not comparable**: a full pytest suite ran concurrently with it. Budgets are not free —
  they buy completed replies with time.
- **The receipt ledger's standing is unchanged and still unfavourable as a *subsystem*.** Its motivating
  discard is now **visible** in the run's accounting (§9.3), and its second motivating loss — the
  dedupe's absorbed content — is **fixed** (§4.1). What remains is genuine provenance: the model's first
  answer, and whether a retry returns the same findings (§2.3 showed it does **not** return the same
  count). That is real, but it is now the *only* case, and it is unmeasured in size.
