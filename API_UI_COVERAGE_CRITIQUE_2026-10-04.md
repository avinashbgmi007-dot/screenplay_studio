# Feedback delivery — API → UI coverage critique

**Date:** 2026-10-04 · **Question:** does the UX architecture deliver *"the feedback from all the APIs shall be received and nothing lost, and the findings shall be efficient and productive"*?
**Method:** every feedback-bearing GET endpoint called against a **live desk with a real model** (`Pain3`, `gemma_vn26b-experts-v1-Q4_K_M`); every returned field name checked against the shipped SPA corpus (`app.js` + `core.js` + `index.html` + `tungsten.css`, 525,158 chars). Read-only; no tracked file modified.

---

## 0 · First: the repository moved under this audit

My measurements were taken at **`4d71c6f`**. `origin/main` is now **`2a49efb`** — 8 commits ahead, and **two of the defects I reported are already fixed**:

| Commit | Fix | My finding it closes |
|---|---|---|
| `6b99fe0` (#8) | **"a finding's id names its scene"** — the id now carries the scene's slugline key (`revision.py:81-93`) | the 40-way collision / one press marking 40 findings |
| `bb9ce92` (#7) | **"refuse a stale proposal rather than skip it silently"** — `POST /edits/apply` now returns `400 {error, stale: true}` | the Gate-1 gap (no machine-readable conflict) |
| `d4ab37c` | **`docs/design/ink-layer/DECISION_RECORD.md`** — the authoritative state of the build | — |

**The fix is better than the one I proposed.** I suggested `category|rule_id|scene_refs|quote`; they used the **slugline**, and the commit says why: *"`scene_refs` still never key the id: ordinals renumber on insert, which is what a mark has to survive."* They were right and I was wrong on that axis.

**What the fix does NOT close — and this is the crux for the writer:**

```python
quote = (f.get("evidence_quote") or "").strip()
if quote:  norm = quote
else:      norm = "issue:" + " ".join((f.get("issue") or "").lower().split())[:100]   # <-- still here
scene = (f.get("scene_key") or "").strip()
if scene:  norm += "|s:" + scene
```

The scene key is a **tie-breaker appended to** the issue text. For a `no_quote` finding the id is *still* driven by the model's own words — so **re-wording still orphans the mark**. `DECISION_RECORD.md:43` accepts this: *"when the model re-words it the id changes, **by design** — an id does not 'survive re-analysis' unconditionally."*

**The design is stated; its price is not measured. I measured it** (§3). That is the single most useful thing I can add here.

---

## 1 · The census: 294 API fields, ~94 never referenced by the UI

| | count |
|---|---|
| unique field names across 22 feedback endpoints | **294** |
| never referenced anywhere in the SPA corpus | **94 (32 %)** |

**Verified losses** — each confirmed to have *no* renderer and *no* generic access path:

| Lost feedback | Where it lives | Why it matters to the writer |
|---|---|---|
| **`one_page_synopsis`** | `report.coverage` | A whole written artifact — a synopsis of their script — produced and never shown |
| **`parse_confidence`**, **`warnings`** | `parsed.json` / upload | *"layout-gap heuristics… spot-check before trusting citations"* — the writer is never told their parse was low-confidence |
| **`verified_pct_of_quoted`**, **`quote_bearing`** | `report.verification_summary` | The report's **own honesty metrics** — how much of it is evidence-backed — are hidden |
| **`evidence_depth`**, **`character_stats`**, **`dialogue_action_ratio`**, **`estimated_page_count`**, **`findings_merged`** | `report.stats` | `findings_merged` in particular: the writer sees a count that dedupe already reduced, with no notice |
| **`/api/projects/<n>/characters`** | its own route | **Zero callers in `app.js`** — 27 fields, 9.7 KB, entirely dead |
| **`last_analysis_ts`** | `metrics.py:52` stores it; `summarize()` (`metrics.py:73-88`) returns 7 keys and omits it | The writer cannot tell how stale their report is. `DECISION_RECORD.md:33` admits this gap |

**Self-correction — my census over-counts.** I found a **false positive**: the writer-profile traits (`mentor_style`, `directness`, …) are 0-reference *by name*, but they **are** rendered — generically, from `data.gated` at `app.js:3753`. So "94 lost" is an **upper bound**, not a verified count. The reliable signals are the endpoint-level ones (`/characters`) and artifacts with no renderer at all (`one_page_synopsis`, `parse_confidence`, `warnings`).

---

## 2 · The critique of the UX architecture

### G1 — *"Nothing lost" is a product-wide property, and the Ink Layer is not a product-wide architecture
`DECISION_RECORD.md:19` is explicit: the master plan inventories **18 protected surface rows, and the Ink Layer addresses one of them.** §2 adds that the dock's other lenses, the selection floats and the welcome desk **have no design at all**, and *"until that is answered, 'retire the dock' is not a coherent end state."*

So the honest answer to the brief: **the restructure cannot, by construction, satisfy "nothing lost."** A critique loop for one manuscript is not a feedback-delivery contract. Conflating them is the architecture's central framing error.

### G2 — My own architecture reproduces the drop
I specified the Coverage room as *"the verdict and the category roll-up."* That gives a home to **findings** and to nothing else. `one_page_synopsis`, `coverage.strengths/weaknesses`, `character_dials`, `pacing`, `setup_payoff`, `stats` and parse quality are **not findings** — and my design, as written, would drop them exactly as the current app does. **That is a real gap in my document, not a hypothetical.**

### G3 — The UI's job is not "show everything"; it is "lose nothing silently"
The fix is not to render 294 fields. It is a **coverage contract**: every API field is either **rendered**, or **declared internal with a reason**. The repo already has the guard for the *opposite* direction — `test_app_symbol_integrity.py` refuses retired surfaces back. The missing twin is a **coverage guard**: a test that fails when an endpoint grows a field that no surface reads and no declaration excuses.

---

## 3 · The productivity threat is churn, not the interface

The brief's second half — *"findings shall be efficient and productive"* — is threatened by something no UI change can fix. Two **identical** runs of the same model on the same, unedited script:

| | run 1 | run 2 |
|---|---|---|
| findings | 45 | 39 |
| exact (category + issue) matches | — | **4** |
| related-but-rewritten | — | 44 % |
| same category, **different point** | — | **33 %** |
| severity `high` | 15 | 11 |
| **quote coverage** | **31 %** | **44 %** |
| **ids stable** | — | **5 of 43 — 12 %** |

**Marked 20 real findings, forced a real re-analysis: 16 of 20 marks lost (80 %).**

So the writer's review is re-based on **80 % of findings** every time they re-run analysis, and `findings_fixed = findings_total − findings_open` (`metrics.py:86`) is computed from a **moving denominator** — the progress meter is not trustworthy under churn. **A perfect critique UI on top of this delivers feedback the writer cannot keep.** Fixing churn outranks any polish of the loop.

Two viable directions, both already implied by the code: **pin the analysis** (fixed seed, temperature 0 for the judgment passes) so a re-run is reproducible; or **make the anchor semantic** (`category + rule_id + scene_key`, never the model's words) **and add a reconciliation step** that tells the writer what moved.

---

## 4 · What to do, in order

| # | Action | Why first |
|---|---|---|
| 1 | **Measure the churn's cost, then pin or reconcile it** (§3) | Every downstream metric — `findings_fixed`, marks, "addressed by you" — is computed on a moving base |
| 2 | **Write the coverage contract** and add the guard test (§2/G3) | Converts "nothing lost" from an aspiration into a gate; catches `one_page_synopsis`-class drops on the day they appear |
| 3 | **Give non-finding artifacts a specified home** (§2/G2) | The Coverage surface must carry synopsis / verdict / dials / pacing / setup-payoff / stats / parse quality — not just a category roll-up |
| 4 | **Delete or wire `/characters`** | A dead 27-field endpoint is a maintenance liability and a false promise |
| 5 | **Serve `last_analysis_ts`** | The store already has it; the writer needs to know their report's age |

---

## 5 · Where this critique could be wrong

- **My census is name-based.** It over-counts (the writer traits are a proven false positive) and could under-count fields read dynamically. Treat §1 as a **screen**, with the listed items individually verified.
- **I measured on a stale base.** Items in §0 are fixed upstream; the coverage and churn findings were re-derived against the live app, but a fresh run on `origin/main` should be done before acting.
- **n = 2 payloads, one model, temperature 0.3.** The churn figure is a property of *this* model at *this* temperature — a pinned-seed run would change it, which is the point of §4.1.
- **I did not run the writer study.** Nothing here substitutes for Gate 5; every productivity claim is a proxy from payload statistics.
