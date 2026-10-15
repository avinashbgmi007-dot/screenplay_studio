# The Fuzzy-Match Threshold Is Stricter Than Its Stated Intent

**Date:** 2026-10-15 (rev 2) · **Status:** draft for review · **Found during:** the Track D
investigation (the verification-rate denominator fix), one layer down
**Harness:** `tests/test_verifier_perturbation_bands.py` — 7 tests, green, no model, no server
**Predecessor:** `2026-10-15-verification-rate-denominator-design.md` (`93786c4`)

> Track D fixes the **arithmetic** of the trust metric. This concerns its **input**. Both readers and
> both tests are wrong in the same subsystem, so they are specified together and reviewed together.

---

## §0. Finding — CORRECTED after independent reproduction

**An earlier version of this section reported 0.63 / 0.61 / 0.28 and claimed the threshold sat
*above* the discrimination band. That was wrong**, and it was an artifact of a Tenglish fixture. An
independent English probe reproduced neither those numbers nor that conclusion.

Now measured by `tests/test_verifier_perturbation_bands.py` (7 tests, green, no model, no server,
run with `pytest -v -s`):

| Quote | single-element scene | full six-line scene |
|---|---|---|
| exact | verified 1.00 | verified 1.00 |
| one word altered | verified 0.95 | verified 0.88 |
| two words altered | verified 0.89 | verified 0.83 |
| **heavy paraphrase** | **verified 0.74** | **not_found 0.63** |
| fabricated | not_found 0.36 | not_found 0.43 |

**The threshold (0.72) sits INSIDE the paraphrase band, not above it.** In both shapes the heavy
paraphrase lands within 0.09 of the line. And the harness pins the consequence directly:

```
test_scene_shape_alone_does_not_change_the_band
  => drifted labels whose verdict depends on scene composition alone:
     ['heavy_paraphrase']
```

**Same quote, same threshold, same code. The verdict flips on how much other text is in the scene.**

### 0.1 The band is language-register dependent — the real finding

| Probe | fabrication | paraphrase ceiling | threshold 0.72 is |
|---|---|---|---|
| English, synthetic scenes | 0.36 – 0.43 | 0.88 – 0.95 | **inside** the band |
| Tenglish, `pain_tenglish.fountain` | 0.28 | 0.63 | **above** the band |

The product ships English, Tenglish, Hindi, Telugu and Tamil (`USER_PERSONAS.md` derived rule 4).
**The metric's relationship to its own threshold is not the same in every register.** English gives
partial, scene-shape-dependent acceptance; Tenglish gives uniform rejection of paraphrase. **There is
no single constant that behaves correctly across the registers the product claims to serve.** That is
a larger problem than a mis-set number, and it is the finding this section should have led with.

### 0.2 Probe honesty — a bug in the first version of this section

The first probe set `tokens[1] = "detective"` on a sentence whose token 1 already *was* "detective".
The "one word altered" bucket was therefore testing the verbatim quote twice, and reported
`verified / 1.0`. The bug inflated the apparent separation and produced the wrong §0. It was caught
by noticing that a perturbation which changes nothing cannot raise a confidence score.

Recorded because `docs/FULL_FEEDBACK_AUDIT_VERDICTS.md` carries a "Probe honesty note" for exactly
this class of error, and because the corrected numbers are what the harness now pins.

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