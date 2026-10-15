# Gate 7(b) — the split-path residual, measured

**Date:** 2026-10-07 · **Build:** `origin/main` = `a547a06` · **Model:** `qwen3.6-35b-a3b-pruned-v2.gguf`
on `127.0.0.1:8080` · **Probe:** `C:/tmp/ss_probe/g7b_probe.py` (raw: `g7b_report.json`)

## Why this was open

Gate 7 was decomposed on 2026-10-07 into two churn sources. **(a)** — model variance in *which* points
get re-raised — closes only on Gate 5. **(b)** — the split path — was marked *partly code-addressable,
partly done*, with this row's own words: **"the residual is unmeasured, so (b) is not closed."**

The evidence behind (b) was a **single pair** (`i2_split.py`, 2026-10-06): control **8** findings /
2 calls, forced **12** findings / 4 calls. Two things were wrong with resting on it:

1. **It predates the budget fix** (dialogue 1200 → 3000). A split is now caused only by ladder
   *exhaustion*, which that fix made rare.
2. **Its forced arm used `max_tokens=300`** — an artificial truncation that cannot occur at the current
   budget. It measured the *mechanism*, not the *residual*.

## Method

`gun_pen` dialogue pass (`chunk_size=3`), run through `pipeline.run_dialogue_analysis` with the shipped
defaults. The probe patches `LlamaServerClient.chat_json` only; **no product code was touched**, and the
patched signature matches the shipped one exactly (`max_tokens=1500`, `temperature=0.3`, `retries=2`),
which the dialogue call site relies on by passing only `grammar` and `max_tokens`.

| arm | what happens |
|---|---|
| **control** ×3 | normal run |
| **split** ×3 | the first `chat_json` call raises `LlamaServerError` — *exactly* what ladder exhaustion raises. `_with_chunk_backoff` then takes its **real** split path: the chunk is halved and both halves re-asked at the **normal** budget. No fake `max_tokens` anywhere. |

**Why N=3 per arm:** the arms are independent samples, so a single pair's delta carries model variance as
well as any split effect. Running each arm three times gives the *within-arm* spread — the only way to say
whether a delta is signal. (The old 8-vs-12 reading had no such control, which is precisely why it did not
reproduce.)

## Raw result

| arm | findings | mean | spread | calls |
|---|---|---:|---:|---:|
| control | **11, 5, 13** | 9.7 | **8** | 2 |
| split | **10, 9, 9** | 9.3 | **1** | 4 |

```
between-arm delta (mean) : -0.3
within-arm spread        : control 8, split 1
recoveries recorded      : 3 of 3 split runs
  sample: {"scenes": [1, 2], "size": 2, "cause": "output_limit", "recovered": true}
```

Content overlap, against control run 1 (9 identified findings):

| vs | shared | jaccard |
|---|---:|---:|
| control run 2 | 0 / 9 & 5 | 0.00 |
| control run 3 | 3 / 9 & 8 | 0.21 |
| split run 1 | 0 / 9 & 10 | 0.00 |
| split run 2 | 0 / 9 & 7 | 0.00 |
| split run 3 | 3 / 9 & 8 | 0.21 |

## What this establishes

1. **The split path is not a distinguishable churn source.** The between-arm delta is **−0.3** — an order
   of magnitude *inside* the control arm's own spread of 8. The split arm is also **tighter** (spread 1),
   the opposite of what "splitting adds variance" predicts. The old **8 vs 12** was a single-pair
   artifact, not a property; it does not reproduce.
2. **The churn that is there is (a), and it is severe.** Identical input, identical build:
   **5 → 13 findings (2.6×)**, and the finding *sets* share **0–3** items. That independently reproduces
   Gate 7's headline (45 → 39, 4 exact matches) on a second payload — which is the gate's real defect.
3. **The disclosure half works.** `recoveries` fired on **3 of 3** forced splits, naming the scenes, the
   cause (`output_limit`), and `recovered: true`.
4. **Cost confirmed:** 4 calls vs 2 — a split doubles the model work for the same input.

## What this does NOT establish

- **Power.** N=3, one 3-scene script, one pass. With a control spread of 8 on a mean of 9.7, a *small*
  split effect (±1–2 findings) would be invisible. This refutes a **large** split effect; it does not
  exclude a small one.
- **A mild split.** `gun_pen` has a single dialogue chunk, so the forced split was 2 scenes → `[1,2]` +
  `[3]`. A deep multi-level split on a 22-scene script is not exercised.
- **The failure's cost, only its shape.** Raising `LlamaServerError` reproduces what the split path
  *receives*; it does not reproduce the three wasted attempts that a real truncation burns first. That
  affects wall-clock and token spend, not the returned finding set.
- **Pain_3.** The larger payload was not re-run (≈34 min per run at current budgets).

## Where (b) now stands

The blocker named in the row was *"the residual is unmeasured"*. It is now measured, on the current
build, with the real split path. It is not separately distinguishable from (a), it is disclosed when it
happens, and its frequency is bounded by the discard rate the budget fix already cut (21.6 % → 10.9 %).

Gate 7 as a whole stays **DEFECT CONFIRMED / release-blocking** — because (a) is real, severe, and closes
only on Gate 5. This measurement narrows *which* source carries the defect; it does not remove it.
