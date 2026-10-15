# The Fuzzy-Match Threshold Is Stricter Than Its Stated Intent

**Date:** 2026-10-15 · **Status:** draft for review · **Found during:** the Track D investigation
(the verification-rate denominator fix), one layer down
**Predecessor:** `2026-10-15-verification-rate-denominator-design.md` (`93786c4`)

> Track D fixes the **arithmetic** of the trust metric. This concerns its **input**. Both readers and
> both tests are wrong in the same subsystem, so they are specified together and reviewed together.

---

## §0. Finding

`FUZZY_MATCH_THRESHOLD = 0.72` (`verifier.py:27`) is the sole arbiter of `verified` vs `not_found`.
Measured through the real `verify_finding` path against `tests/fixtures/pain_tenglish.fountain`:

| Quote handed to the verifier | status | confidence |
|---|---|---|
| exact line from the script | `verified` | 1.0 |
| **one word altered** | **`not_found`** | **0.63** |
| two words altered | `not_found` | 0.61 |
| fabricated, unrelated sentence | `not_found` | 0.28 |

**The threshold sits above the entire discrimination band.**

```
0.28 ───────────── 0.61 ── 0.63 ──────────── 0.72 (threshold)
  fabrication        2-word   1-word            rejects all three
```

The separation the metric should exploit runs **0.28 → 0.63**. The threshold is drawn at 0.72, above
it. So `not_found` does not mean "fabricated" — it means "fabricated *or* a real quote with a word
changed," and the tool cannot tell those apart.

## §1. The stated intent says the opposite

`verifier.py:26-27`, immediately above the constant:

> *"Verification is LENIENT on purpose: a model paraphrases a real line, and calling a real quote
> fabricated is the expensive error here."*

**The constant implements strictness; the comment describes leniency.** A model that paraphrases a
real line — which the comment names as the expected case — lands at 0.63 and is reported as fabricated.

This is the **second inverted comment in the same subsystem** (the first is the denominator docstring
at `verifier.py:230-232`, recorded in the Track D spec). Two adjacent comments in one file describing
the opposite of what the code does is a signal about the file, not about either comment.

## §2. Why it outranks the denominator bug

`AGENTS.md:67`: *"Evidence-first — every analyzer quote is verified against the actual script text."*

Verification exists to catch hallucinated citations. At 0.72 it **manufactures false ones**: real
evidence is labelled fabricated, and by the product's own accounting that is the expensive error.

It also sits upstream of Track D. `verified_pct_of_quoted` is `verified / denominator`. Track D
corrects the denominator; this governs the numerator. **Fixing D without this leaves the number
arithmetically correct and semantically wrong.**

## §3. The razor margin on the primary path

Scored directly through `windowed_similarity`, the **exact line scores 0.724** against a threshold of
**0.72** — a margin of **0.004**. It survives only because the substring fallback at `verifier.py:104-112`
catches it and rewrites confidence to `1.0`.

So the primary fuzzy path is effectively inert for exact quotes: any change to `normalize_text`,
`windowed_similarity`, or the window size flips it, and the fallback quietly absorbs the difference.
The path that is *meant* to carry most real quotes is doing almost none of the work.

## §4. This needs no model — and that is the operational point

The verifier is a pure deterministic function of `(finding, document)`. **A model produces findings;
it has nothing to do with whether the verifier classifies them correctly.**

Every number in §0 was produced in this sandbox with no `llama-server`, no GPU, and no network. The
review position that "calibration waits on starting the server" is correct for `IMPACT`
(`2026-10-15-one-room-ranked-queue-design.md` §9a) and **incorrect for the verifier.** Half the trust
metric is calibratable today, and it has a measured defect.

## §5. Change set

1. **`verifier.py:26-27`** — rewrite the comment to state the rule the code implements, or change the
   code to match the comment. **Decide which first;** do not ship a third state where they agree by
   accident.
2. **Calibrate the threshold on a golden set**, not on one line. Method in §6.
3. **Add a golden-set test** pinning the band, so a future change to `windowed_similarity` cannot
   silently move it. None exists today.

## §6. Calibration method — what a real answer needs

§0 is a **probe, not a calibration**: one line from one short fixture. It is enough to show the
threshold is above the discrimination band, and not enough to pick the replacement number.

A defensible calibration needs, per language register (the product ships English/Tenglish/Hindi/
Telugu/Tamil — `USER_PERSONAS.md` derived rule 4):

| Bucket | Definition | Expected verdict |
|---|---|---|
| **verbatim** | exact line | verified |
| **formatting** | case/punctuation/wrapper differences only | verified |
| **light paraphrase** | 1–2 words altered | verified (per §1's stated intent) |
| **heavy paraphrase** | ~50% of words altered | `not_found` |
| **fabricated** | unrelated, topically adjacent | `not_found` |

Only after those five bands are measured with real counts should the number move. **The expected
shape is a threshold strictly between the heavy-paraphrase band and the light-paraphrase band** —
somewhere below 0.61 on this single probe, but a single probe cannot set a product constant.

## §7. Falsifiers

This analysis fails if any holds:

1. `not_found` is **not** surfaced to the writer as "this quote could not be found." If it is only
   used internally to reorder findings, the severity drops sharply and this is a ranking issue, not a
   trust issue. **Check the UI surface for `not_found` before starting.**
2. A later pipeline stage (the observation pass, `observation_pass.py`) already repairs
   `not_found` rows before they reach the writer. The pipeline docstring
   (`pipeline.py:1253`) says the observation pass re-asks the model about `no_quote` rows — if it
   also covers `not_found`, the user-visible impact is smaller than measured here.
3. The fuzziness is caused by this fixture's unusual text encoding rather than by the threshold.
   The fixture is Tenglish; re-run on a clean English script before concluding.

### 7.1 Falsifier 1 — RESOLVED, and it CONFIRMS rather than relieves

`not_found` is surfaced to the writer. `report.py:38`:

```
VERIFICATION_BADGE = {
    "not_found": " ⚠️ *unverified — quote not confirmed in cited scene(s)*",
```

**A real script line with one word changed is exported to the writer's report as
"⚠️ unverified — quote not confirmed in cited scene(s)."** That is the false accusation
`verifier.py:26-27` names as the expensive error, rendered in the writer's own document.

**Second-order consequence for Track D.** `core.js:178` puts `not_found` in the client metric's
denominator. If some of those rows are merely paraphrased real quotes rather than genuine citation
failures, then **the client's "correct" rule is only correct if `not_found` is trustworthy** — and
this finding says it partly is not. The two fixes therefore interact: lowering the threshold converts
`not_found` → `verified` and moves both the numerator and the denominator. **Sequence matters: the
threshold decision should land before, or with, Track D — not after it.**

### 7.2 Falsifier 2 — RESOLVED, does not fire

The observation pass repairs **`no_quote` only**. `observation_pass.py:159`:

```python
return (finding.get("verification") or {}).get("status") == "no_quote"
```

`pipeline.py:1253` confirms the scope: *"for each finding the verifier left at `no_quote`."*
**No later stage re-asks the model about a `not_found` row.** A paraphrased real quote stays
misclassified all the way to the exported report.

### 7.3 Falsifier 3 — open

Not tested: the fixture is Tenglish. The probe's absolute scores may reflect that encoding. The
*relative* shape (threshold above the one-word score) would survive a shift, but this has not been
confirmed on a clean English script. Lowest priority of the three; it bounds the absolute numbers,
not the structural finding.

## §8. Honest limits of this document

- One script, one line, one language register. §0 is a probe.
- No golden set exists in the repo, so the calibration in §6 cannot be run yet.
- The separation band (0.28 → 0.63) is measured on two points. A distribution, not a boundary.
- **What is solid:** the threshold is above the one-word-paraphrase score; the stated intent
  contradicts the constant; and this needs no model to investigate. What is not solid: the replacement
  number.