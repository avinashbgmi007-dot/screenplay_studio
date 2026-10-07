# Gate 5 — Pre-flight Record

**Date:** 2026-10-07 · **Run against:** `origin/main` = `fac81d3` (PRs #11–#16 merged)
**Script:** `Pain_3` (22 scenes) · **Model:** `qwen3.6-35b-a3b-pruned-v2.gguf` (the loaded local model)
**Command:** `python -m screenplay_analyzer real/Pain3/parsed.json --categories all -o preflight/Pain3.report.md`
**Result:** **steps 1 and 2 PASS. Step 3 is not runnable without a desk session — it is the owner's step.**

---

## 1. Timing — **30.4 minutes**

`stats.runtime_minutes = 30.4`, read from the finished report, not estimated.

This is the number to quote to participants. It reproduces the earlier measurement **exactly**
(30.4 min on the same script), which is the useful part: the §4 session budget is not a one-off.

| | |
|---|---:|
| Analysis, 22-scene script, this laptop | **30.4 min** |
| `gun_pen`, 3-scene script, same laptop | 4.9 min |

**§4's ~2-hour session stands.** The retired 60-minute budget gave Analysis 10 minutes — a ~3× error.

---

## 2. Surface exposure — **both surfaces appear**

The §3.5 rule is that a surface no participant sees was *not tested*. Both were exercised by this run:

| surface | appears when | this run |
|---|---|---|
| **"Also flagged under" disclosure** | the dedupe merged two findings under one rule | **YES** — `stats.findings_merged = 30`; **15 of 61 delivered rows carry `merged_findings`**; 13 occurrences render in `report.md` |
| **Run caveat** | a chunk hit its output limit and was split | **YES** — 1 recovery: *"Dialogue analysis: the model's reply hit its output limit on 1 chunk(s) (scenes 8–10) and the chunk was re-run in smaller pieces…"* |

**These are observations from this run, not population rates** — 15 of 61 rows and one caveat, on one
script, one model, one run. What they establish is that both surfaces *occur on this build*, which is
what the pre-flight asks. Whether the disclosure is "common" is a claim about a distribution that a
single run cannot support. What can be said: the merge *count* has appeared on every feature-length run
so far (29 / 30 on `Pain_3`, 5 on `gun_pen`), while the caveat appeared once and may well not appear in
a given session — so §3.5's post-marking walkthrough is still the only way to test that one deliberately.

### The composition that makes this a real check

Neither half alone satisfies step 2:

- **the run proves the data occurs** at a real base rate on the current build; and
- **`tests/e2e_browser_delivery_contract.py` (18 checks) proves the renderer reads it** — injected
  field → on-disk report → `/findings` → DOM, including that the disclosure is **collapsed by default**
  and that a recovery never nests inside the failure banner.

Data without a renderer is a field nobody reads (the defect class that shipped four times); a renderer
without data is a fixture. This run closes the first half against the real model.

---

## 3. Why the pre-flight could not have been signed off earlier

**The artifacts on disk could not answer it.** Before this run:

| | `stats.findings_merged` | rows carrying `merged_findings` | `recoveries` |
|---|---:|---:|---:|
| stored `real/Pain3` | 29 | **0** | 0 |
| stored `real/GunPen` | 5 | **0** | 0 |
| **this run** | 30 | **15** | **1** |

The stored payloads **predate the fix** (PR #11/#13): the count was there, the content was not. A
pre-flight run against them would have reported "surface absent" and been wrong. Any pre-flight must be
run on the build being tested — which is what §3.5 says, and why it says it.

---

## 4. What this run also shows (not part of the pre-flight)

- **The recovery channel works in production.** `errors = []` while `recoveries` is non-empty. Before
  PR #12 that same event either vanished or landed in `errors` — where it would have rendered the desk's
  *"N passes reported a problem"* banner and dressed a healthy run as broken.
- **Gate 11 holds on a real run:** `observation_pct = 88.5`, `verified_pct_of_quoted = 84.6`.
- **Gate 7's variance is still live:** 61 delivered findings here, against 73 / 73 / 80 on earlier runs
  of the same script and model. Same input, same build, different count — the defect Gate 5 exists to
  characterise.
- 0 withdrawals this run (the integrity gate removed nothing), against 1 earlier. Also variance.

---

## 5. What is NOT proven here

- **No writer was involved.** This says the instrument runs and the surfaces exist; it says nothing about
  whether a writer finds them useful. That is Gate 5, and only Gate 5.
- **Step 3 is untested** — `finding_verdicts.json` and `feedback_ledger.json` are written by the
  **product**, not the analyzer, so no `finding_verdicts.json` or `feedback_ledger.json` exists in any
  probe directory. Confirming they land requires a desk session: open a project, mark one finding, and
  check the two files appear.
- **n = 1 run.** Timing is a single measurement, and it agrees with one earlier measurement of the same
  script. Two agreeing observations are not a distribution.
- **One script.** `gun_pen` (3 scenes) is too short to exercise the surfaces; a second feature-length
  script has not been timed.

---

## 6. Next

1. **Step 3 (owner, ~10 min):** in the desk, mark one finding on this report and confirm
   `finding_verdicts.json` and `feedback_ledger.json` appear. That closes the pre-flight.
2. **Run the study** — 3–5 writers, their own scripts, per `GATE5_WRITER_STUDY_PROTOCOL_2026-10-06.md`.
   Quote **~30 minutes** for a feature-length script, and use `GATE5_CONSENT_FORM_2026-10-07.md`.
