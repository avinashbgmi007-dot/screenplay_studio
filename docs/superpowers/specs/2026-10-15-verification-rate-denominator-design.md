# The Verification-Rate Denominator Fix

**Date:** 2026-10-15 · **Status:** draft for review · **Origin:** §1.7 of
`2026-10-15-one-room-ranked-queue-design.md` (`86c04a5`), which recorded the defect and deferred it
**Deliberately a separate spec.** It changes a server metric, an exported report, and three pinned
tests, two of which currently contradict the client. Bolting it onto the ranking PR means one revert
undoes both.

---

## §0. The defect

`screenplay_analyzer/verifier.py:225-241` and `screenplay_studio/webapp/core.js:176-188` compute the
same named rate under **opposite rules**.

| | denominator | effect |
|---|---|---|
| `verifier.py:235` | `verified + not_found` — **excludes** `scene_not_found` | **inflates** |
| `core.js:178` | `verified + not_found + scene_not_found` — **includes** it | correct |

**Arithmetic.** `verified=1, not_found=0, scene_not_found=1`:

- `verifier.py` → `1 / 1` = **100.0%**
- `core.js` → `1 / 2` = **50.0%**

One of two citations confirmed. The server reports that as perfect verification. The gap scales with
`scene_not_found` — at 5 verified / 2 not_found / 3 scene_not_found the two disagree by **21.4
points**, and it always errs in the direction of flattery.

## §1. Three readers, two rules

| Reader | Surface | Rule applied |
|---|---|---|
| `report.py:384-390` | exported `report.md` — `**Quote-verified rate: X%**` | server (inflating) |
| `report.py:511` | served `/report` `verification_summary` | server (inflating) |
| `app.js:6779` | Context section, `Verifiability (B) — X% of quoted findings…` | server (inflating) |
| `app.js:7214` → `core.js:178` | canonical trust line | client (correct) |

`report.py:382-383` explicitly names `verification_rate` as the owner: *"a percentage over nothing
is a lie (`verifier.verification_rate` owns the rule)"*. **Every server-side reader defers to one
function.** That is the good news: the fix is one function, not three surfaces.

**One stale comment.** `app.js:7215` claims verificationReadout is *"The ONLY reader of
`report.verification_summary`"*. `buildContextSection` (`app.js:6576`) is a second reader. The comment
is false and is itself part of why the divergence survived.

## §2. The rule, stated

> **A citation pointed at scenes that do not exist is a failed check. Failed checks belong in
> denominators.**

`scene_not_found` is a **check result** that came back negative — the verifier found the cited scenes
absent. Excluding it removes a failure from the denominator, which is the definition of flattering a
rate.

**The existing docstring argues the opposite** (`verifier.py:230-232`):

> *"`scene_not_found` is excluded too (it IS a check result, and folding a failure into the denominator
> would flatter the rate)."*

The logic is inverted: inclusion shames the rate, exclusion flatters it. A comment that describes
the opposite of what the code does cannot be used as documentation of intent by anyone who reads it.

**`core.js`'s rule is the one to adopt.** It is the tested rule
(`tests/js/verification_readout.test.js:32`), it is the stricter measure, and it needs no new
judgment — it is already what the product says in its most trusted surface.

## §3. Blast radius, measured

Computed against every pinned expectation in the suite.

| Pinned assertion | now | after fix | moves |
|---|---|---|---|
| `test_verification_summary_surface.py:102` (rate counts checkable) | 66.7 | **50.0** | **YES** |
| `test_verification_summary_surface.py:107` (no checkable → no pct) | `None` | **0.0** | **YES** |
| `test_verification_summary_surface.py:150` (`quote_bearing == verified + not_found`) | holds | breaks | **YES** |
| `test_verification_summary_surface.py:156` (served consistency) | 100.0 | 100.0 | no |
| `test_post_trust_hardening.py:268` (pre-block report re-stamp) | 100.0 | 100.0 | no |
| `e2e_browser_trust_line.py:170` (trust line, 2/1/0) | 66.7 | 66.7 | no |
| `tests/js/verification_readout.test.js:32` | 50% | 50% | no — **already correct** |

**Two of six Python assertions move.** The e2e trust line does not, because its fixture carries no
`scene_not_found`. Honest narrowing: the blast radius is three Python assertions and one function, not
a product-wide number change.

### 3.1 `:107` needs its premise rewritten, not its number

`test_no_checkable_finding_means_no_percentage` asserts
`verification_rate({"no_quote": 5, "scene_not_found": 1})["verified_pct_of_quoted"] is None`.

Under the fix that becomes `0.0`. **That is correct and the test's premise is what is wrong**, because
it conflates two different states:

- **empty denominator** — nothing to check → a percentage *would* be a lie → print `None`
- **all-failures denominator** — one check ran and failed → `0%` is true and actionable

`scene_not_found=1` is the second case, not the first. The rule *"a percentage over nothing is a lie"*
means an empty denominator, never a zero numerator. Rewrite the test to assert both branches
separately.

### 3.2 `:150` is the assertion that will fail first, and it is the honest one

```python
assert vs["quote_bearing"] == vs["verified"] + vs["not_found"]
```

Its comment calls this *"internal consistency: the rate's denominator is exactly the two statuses a
mechanical check can judge."* It pins the bug by name. Update it to
`verified + not_found + scene_not_found` and the comment becomes true.

## §4. Change set

1. **`verifier.py:235`** — `quote_bearing = verified + not_found + scene_not_found`.
2. **`verifier.py:229-233`** — rewrite the docstring to §2's rule. Delete the inverted sentence
   entirely rather than softening it; it will mislead the next reader either way.
3. **`report.py:382-383`** — update the prose that describes what the denominator counts.
4. **`app.js:6779`** — route `buildContextSection` through `verificationReadout()` so one
   implementation serves every surface. This removes the fourth reader and the flattest number.
5. **`app.js:7215`** — delete or correct *"The ONLY reader of `report.verification_summary`"*; it is
   false and it is how the divergence stayed invisible.
6. **Tests** — update `:102`, `:107` (premise rewrite, §3.1), `:150` (§3.2).

## §5. Falsifiers

This fix fails if any holds:

1. `scene_not_found` is produced by a path that is **not** a verification attempt — e.g. it counts a
   finding the verifier never checked. Then including it would be wrong, and the fix must target the
   producer instead. **Check `verifier.py`'s `scene_not_found` branch before starting.**
2. Fixing `app.js:6779` breaks the Context section's existing layout audit. Then §4.4 needs the
   Context box restructured, not patched.
3. Any writer-visible number is load-bearing in an exported artifact that cannot be regenerated
   (e.g. a report already sent to a reader). Then this ships as an additive second number rather than
   a correction.

### 5.1 Falsifier 1 — RESOLVED, does not fire

Checked before starting, as instructed. `scene_not_found` has exactly two producers, and **both are
failed attempts, not skipped checks:**

- `verifier.py:61-65` — a quote-less finding whose cited scenes are *all* absent.
- `verifier.py:95-97` — a finding **with** a quote whose cited scenes all lack full text.

In both, the verifier ran and the citation came back negative. **Nothing here was "never checked."**
Falsifier 1 does not fire; the change is the two-line version.

**But the producers carry a product fact the change set must not miss.** `:64` fires for **quote-less**
findings, and quote-less is forced on exactly the summary-reasoning categories —
`SCRIPT_LEVEL_CATEGORIES = ("theme", "character", "structure", "scene_function")`
(`pipeline.py:589`), whose prompts set `evidence_quote` to null. So **`scene_not_found` is
disproportionately a script-level finding's failure mode.**

Consequence: including it lowers the reported rate mostly because *script-level* citations failed.
That is the correct behaviour — a script-level finding citing a scene that does not exist is a real
citation failure, and today it is invisible. But it is a **visible** change to which findings the
number counts, and `report.py:384`'s prose ("findings that cite quotable text") must be updated to
describe the new denominator accurately or the exported report will explain a number it no longer
computes.

## §6. Ship

- **One PR, separate from the ranking work.** Independent revert.
- Land `:102` and `:150` updates in the **same commit** as the function change. A commit that changes
  the metric without updating the assertion that pins it recreates the contradiction in a new place.
- Do **not** bundle the `app.js:6779` consolidation. It is a real improvement but it is a fourth
  surface; land the metric first, consolidate second.

## §7. Supporting evidence already in the repo

`report.py:511` merges `_observation_coverage(result.findings)` next to the quote rate, with this
comment:

> *"Reported beside the quote rate because they answer different questions: 'can I find the line?'
> versus 'can I check the claim?'"*

**The codebase already states the principle this fix implements — in the same file as the bug.** A
reader would have to look past three correct sentences to reach the inverted one.