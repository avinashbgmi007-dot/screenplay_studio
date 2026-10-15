# Gate 3 re-measurement — 2026-10-06

**Why.** Gate 3's row reads *"EXECUTED — DEFECT CONFIRMED ON A REAL MODEL: 80 % of marks lost, 88 % of
ids churn"*, measured 2026-10-04. The identity fix `6b99fe0` ("a finding's id names its scene") has since
**landed on `main`**, and the row was never re-measured. A stale row is worse than no row: it hides both
the progress and the part that is still broken.

**Method.** No model call. Re-ran the *same* artifact the original measurement used —
`The_Long_Road_Scale_Probe` (`/tmp/ss_probe/projects/…`, **73 findings**, parse-of-record on disk) — plus
two real-model reports (`GunPen` 22, `Pain3` 39), against the **current** `compute_finding_id`
(`revision.py:81`), with `scene_key` stamped through the shipped `annotate_report_scene_keys` path
(`screenplay_parser/scenekey.py`). Probes: `C:/tmp/ss_probe/gate3_remeasure.py`, `gate3_exposure.py`,
`gate3_fix.py`.

---

## 1. The collision half is FIXED

| | 2026-10-04 | 2026-10-06 |
|---|---:|---:|
| 73 findings → unique ids | **34 (39 collisions)** | **73 (0 collisions)** |
| quote tier (29) collisions | 0 | 0 |
| `no_quote` tier (44) → unique ids | **5** | **44** |

`scene_key` is stamped on **72 of 73** findings and closes the collision completely on the artifact that
exhibited it — the 40-finding cross-scene group that shared one id is gone. **This is a real fix, and the
row understates it.**

## 2. The mark-survival half is NOT an identity problem — and that was already known

A static rephrase simulation looks like it offers a fix. Holding `rule_id`/`scene_key` fixed and
rewriting only the `issue` prose:

| | today's id | anchored id (`category \| rule_id \| scene_key`) |
|---|---:|---:|
| `GunPen` `no_quote` (16) surviving a full rephrase | 0/16 | **15/16** |
| `Pain3` `no_quote` (22) surviving a full rephrase | 0/22 | **22/22** |
| injectivity | 22/22 · **38/39** | 22/22 · **39/39** |

**That measurement is misleading, and the repo already says so.** Amendment 6 (2026-10-05) ran the real
thing — two actual runs, 20 marks set before run 2, script unedited:

| Matching algorithm (real two-run pair) | carry | false-carry | orphan |
|---|---:|---:|---:|
| today's id (`compute_finding_id`) | 4/20 | 0 | 16/20 |
| stable key `category\|rule_id\|scene\|quote` | **3/20** | 0 | 17/20 |
| `rule_id + scene` | 4/20 | **2/20** | 14/20 |
| `category + scene` (coarsest) | 5/20 | **15/20** | 0/20 |

**The anchored key carries *less* than today's id — 15 % vs 20 % — and its author's own note says why:
*"It fixes collisions, not churn."*** A static simulation holds the rule attribution fixed; a real
re-analysis is precisely the thing that changes it, and drops points entirely (65 % of marked findings
were **not re-raised at all**).

So §2's table is **not** a fix proposal. It is a second confirmation of the 2026-10-04 *sensitivity* row
(any lexical change flips the tier) — and it is the third time this engagement that a static instrument
has flattered a change the end-to-end run rejects. **Do not propose an id change for Gate 3 again without
the two-run pair.**

## 3. Why the demo artifact looked worse than real runs — and the hedge is now resolved

| report | findings | `no_quote` tier | carries a mechanical anchor (`rule_id`/`check_id`) |
|---|---:|---:|---:|
| `GunPen` | 22 | 16 (73 %) | **19/22 (86 %)** — 15 of the 16 `no_quote` |
| `Pain3` | 39 | 22 (56 %) | **38/39 (97 %)** — 22 of the 22 `no_quote` |
| demo artifact (`The_Long_Road_Scale_Probe`) | 73 | 44 (60 %) | 30/73 (41 %) — **1 of the 44 `no_quote`** |

On **real** runs, `no_quote` means *no quotable line was cited* — not *no rule was matched*. Those
findings carry a rule id. The demo model was the outlier: it emitted placeholder findings with no
attribution, which is why its `no_quote` tier had nothing to anchor to, and why its collision figure
(39) was inflated. The 2026-10-04 note hedged this correctly; the numbers above settle it.

**It does not change the verdict**, because Amendment 6's real pair already covers the real-model case —
and there the anchored key still loses.

## 4. Verdict

**Gate 3 is now fully characterised. The row must stop reporting only the 2026-10-04 numbers.**

- **Fixed and previously unrecorded:** id injectivity — **39 collisions → 0** on the same artifact, and
  the `no_quote` tier goes from **5 ids for 44 findings** to **44 for 44**. Delivered by `6b99fe0`.
- **Confirmed unfixable by identity:** mark survival. Measured twice, independently (2026-10-04: 4/20
  survive; Amendment 6: 4/20 today, **3/20** for the anchored key). **No id function fixes it**, because
  the failure is model variance in *which points get re-raised* (65 % are not re-raised at all), not id
  instability.
- **Mitigated, not eliminated, by two shipped mechanisms:** GAP-7 disclosure (`last_pass_snapshot`,
  `same_input`, churn labelled `rewritten` rather than dressed as Fixed/New) and the **Gate 9**
  reconciliation ledger (CLOSED 2026-10-06) — which is exactly what Amendment 6 concluded: *"That is a
  ledger, not a better identity function."*
- **Not re-run:** the live two-run end-to-end experiment (4/20 ids survived, 2026-10-04). It costs two
  full analyses (~70 min of model time on `Pain_3`). Everything above is pure-function and reproducible
  without the model; the live run would add confidence, not a different conclusion.

**So Gate 3 closes on the writer study, not on code.** Its remaining symptom is a *disclosure and
reconciliation* obligation, and whether the disclosure is sufficient is a writer question — i.e. it rides
on **Gate 5**, the binding gate. Until a writer has seen a re-based review and judged the disclosure,
Gate 3 stays **DEFECT CONFIRMED (injectivity fixed; survival mitigated by design)**.
