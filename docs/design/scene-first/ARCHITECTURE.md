# Scene-First Ink — v3.1 (final)

**Date:** 2026-10-04 · **Status:** v3.1 — the finalized architecture baseline · **Prototype:** `index.html` (this folder)  
**Supersedes:** v3 (this file, earlier today), v2, and the line-first reading of `docs/design/ink-layer/INK_LAYER_SPATIAL.md`  
**Provenance:** v3 accepted the corrections in `CRITIQUE_OF_EVIDENCE_PRECISE_INK_2026-10-04.md` and the  
uploaded *"Scene-First Ink v3"* proposal, and fixed the contradiction they exposed in v2 (**C3′ vs S4**).  
**v3.1 applies five surgical amendments — it does not rewrite the architecture.** Each is marked in place  
(`▶ Amendment N`), with the original text left visible. Together they close one wording contradiction,  
one **release-blocking** open question, and two provenance/scoping lapses.

> **Do not rewrite this again.** A fifth architecture would repeat the cycle both critiques warned  
> against — documents arguing with documents while no writer touches the product. The next action is  
> **validation, not another document** (§5).

---

## §0 · What v3 corrects (the changelog)

| v2 said                                                                                                                    | v3 says                                                                                                                                                 | Why                                                                                                                                                |
| -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| C3′ gave script-level findings an in-flow ledger; **S4** listed script-level among those "announced once, never re-listed" | **Split the axis:** script-*scoped* findings → the **script ledger**; **unresolved *placement*** → announced **and** persistently reachable in the lens | The two rules **contradicted each other**. Scope and placement are different questions.                                                            |
| Scope is "mapped directly onto `scene_refs`"                                                                               | **Scope ≠ placement.** `scene_refs` is a partial proxy for scope and says **nothing** about placement; an empty array is **ambiguous**                  | `"scene_refs": []` is used for a script-level finding (`formatting_check.py:76`) but nothing *guarantees* that meaning                             |
| "Rewrite … **never** for structural or global findings"                                                                    | **Rewrite = a proposal for explicit targets.** A broad finding begins with a **plan or target selection**                                               | Structural revision is legitimate writing work. Refuse *automatic broad replacement* — not assistance.                                             |
| C9: "a proposal whose target has **moved** is stale and must be refused"                                                   | **Movement ≠ conflict.** Relocate only when identity and preconditions prove it safe; otherwise require reselection                                     | A line that moved is not necessarily a line that changed.                                                                                          |
| `≥ 0.72` "grants" an earned precision                                                                                      | **`≥ 0.72` = candidate discovery.** *Located* requires an exact match with no rival                                                                     | A unique fuzzy match can be **wrong** without producing a tie.                                                                                     |
| Four actions: Locate · Rewrite · Discuss · **Noted**                                                                       | **The product's own marks:** Locate · Rewrite · Discuss, then **Addressed · Defer · Dismiss**                                                           | The product already persists `addressed`/`deferred` (`revision.py:101,112`) and triage `dismissed`; a six-action parallel vocabulary duplicates it |
| Unresolved findings "announced once"                                                                                       | **Announced, and persistently reachable** in the dock's Evidence lens                                                                                   | `app.js:2846`: *"the dock's Evidence lens has the ledger."* An announcement supplements access; it never replaces it.                              |
| "Watch the line **not move**"                                                                                              | **The manuscript is not written until you accept**; the affected span is shown in place                                                                 | Visual stability fails for long replacements, zoom, small screens. The **data** guarantee is the real one.                                         |

---

## §1 · Why it changed — and what the real model changed back

The Ink Layer was line-first: a critique is worn by *the line it is about*, and a replacement is cast  
into that line. The first measurement (`docs/design/ink-layer/REAL_SCRIPT_RESULTS.md`, a 28-page run)  
used the **demo** craft model:

| demo-model run                            | measured                                  |
| ----------------------------------------- | ----------------------------------------- |
| findings                                  | 16                                        |
| carry a quote at all                      | 3 (19 %)                                  |
| quote-bearing findings that reached a row | 3 of 3 — every one on a **scene heading** |
| **prose lines carrying ink**              | **0** of ~1,001 rows                      |

That result drove the entire scene-first correction.

> **▶ CORRECTED — 2026-10-04 (Gate 4 executed): it was a demo-model artefact.** Re-run with a **real  
> model** (`gemma_vn26b-experts-v1-Q4_K_M`, 12.5 min, 12 passes, `errors: {}`) on the **same** script  
> (`Pain_3_updated_FULL.pdf`):
>
> | real-model run                                 | run 1                        | run 2                    |
> | ---------------------------------------------- | ---------------------------- | ------------------------ |
> | findings                                       | **45**                       | 39                       |
> | carry a quote                                  | **14 (31 %)**                | 17 (44 %)                |
> | **quote-bearing findings that reached a LINE** | **10 / 14 (71 %)**           | **12 / 17 (71 %)**       |
> | **prose lines anchored**                       | **~6**                       | **9**                    |
> | severity                                       | low 7 · med 23 · **high 15** | low 6 · med 22 · high 11 |
>
> **The Ink Layer's line-level mechanism is NOT dead on real data — it works, and the 71 % line-anchor  
> rate reproduced across two independent runs.** `REAL_SCRIPT_RESULTS.md:58` ("its central claim … is  
> unrealized on this payload") is a demo-model artefact and **must be corrected**.
>
> **Second payload** (`gun_pen.pdf`, 3 scenes, 22 findings, 385 s): quote 6 (27 %) · `no_quote` 16  
> (73 %) · multi-scene 6 (27 %) · collisions **0** · `rule_id` 18/22 · **2 of 6 quote-bearing findings  
> anchored to a line — both prose, zero headings**. Two independent payloads now agree: real-model  
> findings **do** reach prose lines.
>
> **What survives, and why C1′ still stands:** 69–78 % of findings still cannot ink a line, and  
> multi-scene scope is **15 of 45 (33 %)**. So the honest statement is not *"line-first is dead"* but  
> ***"line-first serves ~22 % of findings; scene-first serves 100 %, with the line as an earned  
> precision."* C1′ is unchanged; its rationale is inverted.**

**Other real-model payload facts (run 1, 45 findings):** `rule_id` on **45/45 (100 %)** — craft  
attribution is fully populated on real output (the demo's 30/73 was an artefact); quote-bearing  
14 · `no_quote` 31 · verification `verified 11 / no_quote 32 / not_found 2`; reachability **45/45**  
(0 missing-scene, 0 script-level); ledger load **max 8 findings on one scene**, 2 scenes over the  
six-cap; id **collisions 2/45 (4.4 %)** — the demo's 40-way was inflated, but the defect is real.

---

## §2 · The laws

### Kept, unchanged from the Ink Layer

- **K1 — One scroller, one column, one measure.** Nothing inside the manuscript scrolls. *"One  
  measure" governs reading coherence, not an immutable pixel width — the layout must reflow at  
  every viewport and zoom level without making text or actions unreachable.*
- **K2 — The trap frame.** Auditioning a rewrite never writes. **Only explicit acceptance mutates  
  the manuscript.** Ordinary author editing remains a separate, legitimate path.
- **K3 — The in-flow fold.** Critique displaces the page, never covers it.
- **K4 — Three non-colour channels.** Width = severity, stroke = verification, rule name =  
  provenance. Marks **supplement** readable labels; severity, evidence status and attribution must  
  remain legible without colour or a memorized stroke pattern.
- **K5 — Identity is not location.** Placement is a match on the evidence quote; a tie is reported,  
  never guessed. *(Sharpened in S below.)*
- **K6 — Fail loudly, lose nothing — and proportionally.** An error appears near the action that  
  failed, is recoverable, and never covers the manuscript. A failed request never discards a locally  
  refined candidate.

### S — Scope and placement are different axes *(the core correction)*

Two orthogonal questions, never inferred from each other:

**Semantic scope — what the finding concerns:**

| Scope           | Presentation                                                                                                    |
| --------------- | --------------------------------------------------------------------------------------------------------------- |
| **Passage**     | A passage mark where the target is unambiguous; otherwise shown at its supported broader location               |
| **Scene**       | A scene-boundary mark + an entry in that scene's ledger. The heading is **not** presented as the offending text |
| **Multi-scene** | Referenced at **every** affected scene; one finding identity, one decision state; counted **once**              |
| **Script**      | An entry in the **script ledger** at the manuscript's beginning. No fabricated scene attachment                 |

**Placement status — where the evidence can be located:**

| Status          | Meaning                  | Product mapping                            |
| --------------- | ------------------------ | ------------------------------------------ |
| **Located**     | Exact, no rival          | `exact` (score ≥ 1.0, no tie)              |
| **Approximate** | A candidate, not a proof | `loose` (0.72 ≤ score < 1.0)               |
| **Ambiguous**   | A tie within tolerance   | `ambiguous`                                |
| **Unavailable** | No locatable anchor      | no row (`no_quote`, missing scene, parked) |

**Rules:**

- **A multi-scene finding must not lose its broader scope merely because one supporting quotation  
  is located.** Scope is authored; placement is derived.
- `scene_refs` is a **partial proxy for scope** — it is an int-array (`grammar.py:73`), the  
  continuity pass unions two scenes (`continuity.py:148`), and `dedupe` merges arrays  
  (`dedupe.py:211-214`). It is **not** a placement field, and an empty array is **ambiguous**  
  (script-level in `formatting_check.py:76`, but nothing guarantees it). Where legacy data cannot  
  distinguish script scope from missing references, **show uncertainty** — do not silently classify.
- **`≥ 0.72` is candidate discovery, not proof and never permission to overwrite.** "Located" is  
  reserved for an exact match with no rival.
- **▶ Amendment 2 (v3.1).** **The uniqueness verdict is manuscript-wide.** "Located" requires an exact  
  match with **no rival anywhere the quote appears in the manuscript** — recurring lines (`CUT TO:`,  
  repeated dialogue) that match exactly in more than one scene are **Ambiguous, not Located**.  
  Scene-local uniqueness is **not** sufficient. *(Grounded in the product's own experience: a  
  heading-quoting finding "tied with its own duplicate" and the page reported ambiguity on **3 of 3**  
  real quotes — `REAL_SCRIPT_RESULTS.md:110-126`.)* The **candidate pool** may be scope-filtered; the  
  **uniqueness verdict is global**.

### A — Actions are the product's own marks, not a parallel vocabulary

| Action        | Contract                                                                                                                                                        | Persisted?                   |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| **Locate**    | Available when a meaningful destination exists; approximate/ambiguous retains its warning                                                                       | no (navigation)              |
| **Rewrite**   | Generates a proposal for **explicit targets**. A broad finding begins with a **revision plan or target selection** — never an automatic script-wide replacement | no (prescription)            |
| **Discuss**   | Carries the finding, attribution, scenes and draft context into the chosen partner; returning restores the originating context                                  | no (hand-off)                |
| **Addressed** | "My call: addressed" — the writer asserts they made the change. Survives re-analysis                                                                            | **yes** — `revision.py:101`  |
| **Defer**     | "Next pass" — a decision to revisit; recoverable through the shared filter                                                                                      | **yes** — `revision.py:112`  |
| **Dismiss**   | An explicit decision **not to act** (triage; reversible via Restore)                                                                                            | **yes** — `/fixqueue` triage |


These are **semantics, not a demand for six buttons on every finding** — present the relevant ones
progressively in flow, and keep them discoverable.

**Three outcomes are distinct and must never be conflated** (`revision.py:930-977`):
**acknowledged / decided** (writer intent) · **applied** (a change was written) · **verified-resolved**
(`addressed` / `still_present` / `unknown`). **Applying a rewrite must not auto-certify the diagnosis
resolved.**

### F — The audition frame protects authorship

Audition is provisional: choosing, editing, or discussing a candidate **does not write**. Show
original and proposed text well enough to inspect additions, deletions, and the **complete affected
span** — longer proposals stay readable; never clip them to preserve a visual trick. Visible controls
come first; `J`/`K` are optional, focus-scoped, and **inactive during ordinary text entry**. Preserve
the writer's reading context — but promise the **data** guarantee (nothing is written), not that a
line never visually moves.

### G — Apply is a backend-enforced contract

| Situation | Required behaviour |
|---|---|
| Target current and uniquely identified | Apply, and return the recorded outcome |
| Target content changed, or location ambiguous | **Refuse** unsafe application; preserve the proposal; explain the conflict |
| Target moved but otherwise unchanged | Relocate **only** if identity + preconditions prove it safe; otherwise require reselection |
| Multiple replacements | State whether it is all-or-nothing or explicitly partial. **Never present a mixed result as complete success** |
| Response times out | Treat completion as **unknown** until checked; do not blindly resend |
| Retried | Recognize the **same acceptance operation** so it cannot apply twice |
| Undo | Reverse only when safe; preserve later work; surface conflicts |

An explicit `stale` flag is **one possible representation, not the goal.** The required outcome is
**safe application plus an accurate, recoverable explanation.** The contract table above is the
requirement and stands **independently** of any particular wire observation.

> **▶ Amendment 5 (v3.1).** The current-wire observation — `/edits/apply` returns
> `200 {applied: [], skipped: [{reason: "line not found in scene"}]}` — is a **reported measurement**
> (first taken in `CRITIQUE_OF_ASHNA_VERDICT_2026-10-04.md`, reproduced during the production audit),
> **not re-verified in this document.** Re-verify at Gate 1 before citing it as fact. It is consistent
> with the table either way: the unsafe write is already prevented; the open question is whether **all
> clients** interpret `applied: []` + non-empty `skipped` consistently as a **conflict**.
>
> **▶ RE-VERIFIED — 2026-10-04 (Gate 1 executed).** Re-run against the **live app**: `/edits/apply` with
> an unlocatable target returns **`HTTP 200`**, `applied: []`,
> `skipped: [{old, new, reason: "line not found in scene"}]`, and **no `stale` key** (response keys:
> `applied`, `findings_status`, `scene_text_after`, `skipped`). **The unsafe write is prevented — the
> safety property holds.** The residual gap is narrower than "no stale flag": the conflict is signalled
> only by an empty `applied` plus prose in `skipped[].reason`, with **no machine-readable conflict
> outcome** — so correctness depends on every client parsing that shape identically. The observation is
> now **first-hand verified**, not merely reported.

### L — One findings **state**; many renderings; no independent list; nothing unreachable

> **▶ Amendment 1 (v3.1).** v3 said *"one findings state, one lens"* and then listed several renderings
> — the wording contradicted its own enumeration. Corrected below. **The amendment's *justification* is
> also corrected:** the product's own note says the retired pane was *"a third surface **projecting**
> the same findings state"* (`index.html:440-441`) — a duplicate **projection**, not a separate holder.
> The real distinction the product draws is **semantic vs decorative**: *"**Ink is decoration** …
> `aria-hidden`; **the board carries semantics**"* (`DEVELOPMENT.md:99-100`).

- **One findings state; every surface renders it; no surface owns its own copy.** The manuscript folds,
  the script ledger, and the dock's Evidence lens are **renderings** of one filter/state model — marks,
  counts, defers and dismissals are identical wherever they appear. What the retired Report/Fix-Queue
  pane did wrong was not being a second *view*; it was being a **second semantic holder** of findings
  state, reachable only by deep link.
- **A deliberate departure, stated plainly.** The shipped product treats in-manuscript ink as
  *decoration* (`aria-hidden`, non-semantic). The Ink Layer **promotes the fold to a semantic
  instrument** — that is the point of the design, and it is the one place this architecture knowingly
  overrides an existing product rule. It is defensible because the fold is **scene-scoped and in-flow**
  — context-local, not a second global list. *(`tests/test_app_symbol_integrity.py` guards the retired
  surfaces; those tests show migration **cost**, not architectural authority — but the cost is real.)*
- **One shared filter drives everything.** The global summary counts **unique** findings; **local counts
  are labelled** and cannot masquerade as global totals; hidden / deferred / filtered-out findings stay
  explainable (`DEVELOPMENT.md:94-96`).
- **Unresolved-placement findings stay reachable** — by pointer and keyboard, after the boot
  announcement has passed — in the dock's **Evidence lens**, the persistent ledger (`app.js:2846`). The
  announcement (`say.offPage`) explains; the lens carries access.
- **▶ Amendment 1b.** **While an analysis is running**, marks and ledgers render the **last verified
  state, visibly labelled as such**. A mid-analysis view must never present stale findings as current.

### R — Rooms and scope

- **The Ink Layer is the Desk**, not the product. Units: Desk → the scene, then the line · the
  **script ledger** → the script · Partner → the turn · Ideas → the premise · Structure → the draft.
- **Coverage** (the old "Report") is a **reading** surface: the verdict and the category roll-up. It
  carries **no findings list**; every number derives from the same state.
- **Print** excludes critique marks, proposals, ledgers and navigation chrome.

### D — Craft attribution is the product, not a nicety

An expanded finding presents the **diagnosis first**, then reasoning and evidence, with the
human-readable **craft rule** available directly. Resolve `rule_id` → rule name and source. A raw
identifier (`DIAL-114`) is not meaningful provenance. If attribution is missing or unresolvable, **say
so** — do not invent it, conceal the failure, or make the finding unreachable. **A named rule explains
the criticism's basis; it does not prove the criticism correct.** Keep diagnosis distinct from
prescription.

### V — Nothing is lost *silently* *(added 2026-10-04 — a gap in v3.1, found by audit)*

> **▶ CORRECTED.** v3.1 specified the Coverage room as *"the verdict and the category roll-up"* — a
> home for **findings** and nothing else. An audit against the live API found **294 field names, ~94
> (32 %) never referenced by the shipped UI**, including whole artifacts (`one_page_synopsis`), the
> report's own honesty metrics (`verified_pct_of_quoted`, `quote_bearing`), parse quality
> (`parse_confidence`, `warnings`), and an endpoint with **zero callers** (`/characters`).
> **v3.1 would have reproduced that drop**, because synopsis / dials / pacing / setup-payoff / stats /
> parse quality **are not findings**. See `API_UI_COVERAGE_CRITIQUE_2026-10-04.md`.

- **A coverage contract, not a promise.** Every API field is either **rendered by a named surface**,
  or **declared internal with a written reason**. Nothing sits in the gap by default.
- **Enforced by a test.** The repo already guards the reverse direction
  (`tests/test_app_symbol_integrity.py` refuses retired surfaces back). The missing twin is a
  **coverage guard**: it fails when an endpoint grows a field no surface reads and no declaration
  excuses.
- **The Coverage surface carries the non-finding artifacts** — synopsis, coverage verdict,
  strengths/weaknesses, character dials, pacing, setup/payoff, stats and parse quality — not only a
  category roll-up.
- **The report's honesty about itself is first-class feedback.** `verified_pct_of_quoted` and
  `quote_bearing` say how much of the report is evidence-backed; `parse_confidence` and `warnings`
  say whether to trust the citations. Hiding them hides the report's own uncertainty — the opposite
  of K6.

---

## §3 · The one thing the UI cannot fix

> **▶ Amendment 4 (v3.1).** v3 stated the bare *"80 % carry no quote"* here while §1 carefully scoped
> it — an internal inconsistency. The figure is now scoped **where it appears**, so nobody quoting §3
> alone re-inflates a stress case into a rate.

On the measured run, **80 % of findings carried no quote — a demo-fixture stress case on one real
document (§1), not a measured rate for real-model reports.** No page can attach a critique to a line
the producer never cited. The highest-leverage work is upstream: give every finding an honest
**scope** — a verifiable quote *where one exists*, and an explicit `scene_anchor` where it does not.

**And do not force it (C8).** Raising the quote *percentage* is not the goal — an analyzer tuned to
cite more will produce quotes that do not support the diagnosis, which is **worse** than a `no_quote`
finding because it looks verified.

---

## §4 · Prototype map

| # | Screen | What it demonstrates |
|---|---|---|
| 1 | The correction | the rules, on one page |
| 2 | Desk — at rest | the floor; the honest marks (dash = scene, bar = line) |
| 3 | Desk — scene ledger | the fix: named rules, **scope ≠ placement**, scope-aware actions, the script ledger in flow |
| 4 | Desk — line cast | the audition frame — press `J`/`K`: the takes move, **the manuscript is not written** |
| 5 | Coverage | the verdict + roll-up — **no findings list** |
| 6 | Partner | Sameer, with a finding pinned from its ledger row |
| 7 | Ideas | the premise — where the Ink Layer has nothing to say |
| 8 | Structure | compare + beat board — the other reason it is a room, not the product |


Open `index.html`; press `1`–`8` or click the rail.

---

## §5 · Still open (deliberately)

### ▶ Amendment 3 (v3.1) — **release-blocking: finding-identity durability**

**This is load-bearing and was missing from v3.** Persisted marks, defers and dismissals key on
`compute_finding_id` (`revision.py:66-72`), and the product's own law says they "must survive
regeneration" (`DEVELOPMENT.md:97-98`). But the id is:

```python
quote = (f.get("evidence_quote") or "").strip()
if quote:  norm = quote
else:      norm = "issue:" + " ".join((f.get("issue") or "").lower().split())[:100]
return "f" + _base36(_str_hash((f.get("category") or "other") + "|" + norm))
```

The **quote tier is stable**; the **`no_quote` tier keys on the issue text**, which a language model
rephrases between passes — and `no_quote` is the **majority tier** on the measured run (13 of 16).
**So the stated intent is unmet for the majority tier: re-analysing a marked manuscript can orphan the
writer's Addressed / Defer / Dismiss judgments silently.** Validate before sign-off — re-analyse a
marked manuscript and **measure how many marks survive**. If survival is poor, the fix is **upstream
identity** (a stable rule + scope anchor), **not UI**.

> **▶ MEASURED — 2026-10-04 (Gate 3 executed).** Run against the **live app** on a 73-finding report
> (`The_Long_Road_Scale_Probe`), calling the real `compute_finding_id` (`revision.py:66-72`):
>
> | Test | Result |
> |---|---|
> | Tier split | 29 quote (40 %) · **44 `no_quote` (60 %)** |
> | Sensitivity | **any** lexical change to `issue[:100]` flips the id — one word, one character. Case and whitespace *are* normalised, so those survive |
> | Simulated re-analysis (light paraphrase, quote unchanged) | **40 of 44 `no_quote` marks orphaned — 91 % of the tier** |
> | Injectivity | **73 findings → 34 unique ids (39 collisions)**. One group of **40 findings across different scenes** shares a single id. Quote tier: 0 collisions. `no_quote` tier: 5 ids for 44 findings |
> | **End-to-end spread** | Marking **one** finding "Addressed" → `done_count` **0 → 40**, `dawn_pct` **0 % → 55 %**. Dismissing **one** row → **40 rows flagged dismissed** (`/fixqueue`) |
> | Rephrase-proof key `category\|rule_id\|scene_refs\|quote` | **73 unique for 73 — 0 collisions** |
>
> **Honesty on scope.** The 40-way collision is **inflated by the demo model**, which emits identical
> placeholder issue text for every dialogue finding — a *mechanism* demonstration, **not a real-model
> collision rate**. The **orphan** result is not demo-specific: any rephrasing model triggers it, and
> `no_quote` is the majority tier. **Mechanism and exposure are proven; the real-model rate needs the
> 43-finding run (Gate 4).**
>
> **Verdict: the defect is CONFIRMED, not open** — and the fix direction is proven available (the
> stable key above yields **zero** collisions). **Move to the fix; do not re-measure the mechanism.**

> **▶ MEASURED ON A REAL MODEL — 2026-10-04 (the decisive run).** Marked 20 real findings
> (10 Addressed · 10 Deferred), then forced a **real re-analysis** of the same script with the same
> model (`POST /analyze {"force": true}` — `/analyze` is otherwise idempotent and returns in 0 s):
>
> | | result |
> |---|---|
> | marks whose id survived | **4 / 20** |
> | finding persisted, **mark orphaned** | 2 / 20 |
> | finding itself gone | 14 / 20 |
> | **effective mark loss** | **16 / 20 — 80 %** |
> | **ids stable across two real runs** | **5 of 43 — 12 %** |
>
> **▶ CORRECTED — 2026-10-05. This is NOT new; it is GAP-7, already filed and already disclosed.**
> This section previously said *"NEW — and bigger than the id bug: the analysis is not reproducible."*
> That was wrong on novelty. `docs/CRITICAL_REVIEW_2026-09-18.md` row 1 records the same defect in the
> same words — *"ids churn about 88 % per no-op re-run and the arrival strip reports LLM variance as
> writer progress (`33 -> 4 still live, 29 no longer flagged, 32 new`)"*, *"4 of 33 ids survive a
> re-analysis at a byte-identical `parsed.json`"* — and it was **fixed by disclosure**: `last_pass_snapshot`
> gates the arrival arithmetic on the analyzer INPUT, so an unchanged script reports `same_input=true`
> and the churn is disclosed as `rewritten`, never dressed as Fixed/New. The measurement below stands;
> the claim of novelty does not. *(Found by `ARCHITECTURE_CRITIQUE_AND_OPTIONS.html` §3.1; verified against
> the repo.)*
>
> **The measurement, restated without the novelty claim.** Two identical runs of the same model on the
> same, unedited script produced **45 → 39 findings**, with only **4 exact (category + issue) matches**:
> 5 identical · 5 near-identical · **20 related-but-rewritten (44 %)** · **15 same-category-different-point
> (33 %)**. Severity moved (high 15 → 11) and even **quote coverage moved (31 % → 43 %)**. The *report
> itself* churns; a better id function alone cannot fix it. The fix is two-part: **(a) a deterministic or
> semantic anchor**, and **(b) a reconciliation story** — tell the writer their review was re-based, and
> what moved.

### ▶ Amendment 6 (2026-10-05) — **the ledger is required, not optional: 65 % of marks have no counterpart**

The reconciliation experiment (`ARCHITECTURE_CRITIQUE_AND_OPTIONS.html` §6 slice 2 — asked for, and now
run on the real payload pair: 45 → 39 findings, script unedited, 20 marks set before run 2):

| Matching algorithm | carry | **false-carry** | orphan |
|---|---|---|---|
| today's id (`compute_finding_id`) | 4/20 | 0 | 16/20 |
| stable key `category\|rule_id\|scene\|quote` | **3/20** | 0 | 17/20 |
| `rule_id + scene` | 4/20 | **2/20** | 14/20 |
| `category + scene` (coarsest) | 5/20 | **15/20** | 0/20 |

**Three consequences that change the design:**

1. **No matcher can deliver "nothing lost".** Only **25 %** of marked findings had their point re-raised
   with a strong match; **10 %** matched only weakly; **65 % were not re-raised at all**. So "nothing lost"
   cannot mean *every mark survives* — it must mean *every mark stays accounted for*. That is a **ledger**,
   not a better identity function. (This supersedes the earlier *"fix direction is proven available"* note:
   a key that fixes collisions does **not** fix churn.)
   **▶ Robustness (falsification run, 2026-10-05).** Loosening the matcher to issue-text similarity alone
   moves the figures to **45 % matched / 55 % not re-raised**; the strict rule gives 35 % / 65 %. So the
   honest bound is **55–65 % not re-raised**, and of the 15 unmatched marks **only one is a genuine near
   miss** (similarity 0.88) — the rest sit at 0.17–0.43, i.e. different points. **The direction is robust;
   the exact figure depends on the matcher, which is why the ledger must not depend on one.**
2. **A coarse key is worse than losing the mark.** `rule_id + scene` mis-carries **10 %**; `category + scene`
   mis-carries **75 %**. Carrying a writer's *addressed* onto a *different point* is worse than dropping it.
3. **The rephrase-proof key I proposed (`category|rule_id|scene_refs|quote`) is worse across runs than
   today's id** (15 % vs 20 % carry) because including the quote makes it fragile. It fixes *collisions*,
   not *churn*.

**▶ The structural fact the whole design turns on — the deterministic tier is stable; the judgment tier is not.**
Match rate run 1 → run 2, same script, same model:

| tier | category | re-raised |
|---|---|---|
| **deterministic** (no model) | **continuity** | **3/3 — 100 %** |
| judgment (LLM) | character | 3/8 — 37 % |
| judgment (LLM) | dialogue | 4/18 — 22 % |
| judgment (LLM) | structure | 1/5 — 20 % |
| judgment (LLM) | scene_function | 1/5 — 20 % |

So the trustworthy core of this product is its **deterministic** feedback — formatting, continuity, pacing,
stats and the character gap analytics. **Promoting the deterministic tier to first-class findings is the
highest-value, lowest-risk work in the programme: no model, no ledger, no reconciliation, and it never
churns.** The judgment tier is a *stream of observations*, and must be persisted as one.

### ▶ Amendment 7 (2026-10-05) — **the accuracy contract: 98.58 % must be *produced*, not asserted**

The requirement is *"all findings ≥ 98.58 % accurate across all category feedbacks."* That **cannot** be a
property the model asserts — the engine is stochastic and non-reproducible (Amendment 3, gate 7). It can
only be a **precision measured against writer verdicts**. v3.1 has no way to capture them:

- **The vocabulary has no `incorrect`.** Writer intent is `addressed | deferred` (`revision.py:101`); triage
  is `dismissed` (`revision.py:75`). *Dismissed means "hide it", not "it is wrong"* — it cannot serve as
  ground truth.
- **The only proxy is citation locatability.** `verified_pct_of_quoted` = **88.2 %** (`Pain3`) / **100 %**
  (`GunPen`) — but **verified ≠ correct** (`verifier.py:1-16`), and per *all* findings the rate is
  **15/39 = 38.5 %** / **6/22 = 27.3 %**, because **56 % / 73 %** of findings carry no quote at all.
- **The value categories are the uncited ones.** On `Pain3`: `character` 0/5, `theme` 0/3, `structure` 0/3,
  `genre` 0/2, `plot_thread` 0/1 carry **no quote** — the categories that carry the value proposition are
  the ones with **zero verifiability**.

**The contract — law V extended:**

> **V′ — Accuracy is a measured property of the writer's verdicts, never an asserted property of the model.**
> Every finding the writer sees can be ruled **`correct` · `incorrect` · `partial`**. Those verdicts persist
> by stable id (the ledger, Amendment 6), accumulate across runs, and feed **one meter**: per-category
> precision = `correct / (correct + incorrect)`. The meter is the only honest reading of "98.58 %".

**Three consequences:**
1. **A verdict channel is a first-class product feature**, not telemetry. Without it, accuracy is
   unmeasurable and the 98.58 % target is unfalsifiable.
2. **The uncited categories need a checkable anchor** before they can be scored at all — a verifiable quote
   *or* an explicit, checkable scope claim. No UI can score a finding the analyzer never grounded.
3. **Applying a rewrite must not auto-certify** the finding `correct` — writer judgment, successful
   application, and verification are three distinct states (§L).


### ▶ Amendment 8 (2026-10-05) — **the accuracy baseline is measured, and the target is reachable only on the asserted tier**

Amendment 7 defined the contract. This amendment **measures it** — every real finding on both payloads read
against its evidence and judged (`docs/design/scene-first/accuracy_meter.py`; verdicts in the same folder).
**The instrument is now the fourth deliverable**, alongside the spec, the prototype and the ledger.

**Measured (expert-proxy ground truth, 61 findings):**

| | `Pain_3` (39) | `gun_pen` (22) |
|---|---|---|
| correct / partial / wrong | 11 / 23 / 5 | 6 / 13 / 3 |
| **error rate** | **12.8 %** | **13.6 %** |
| **precision band** | **28.2 % – 87.2 %** | **27.3 % – 86.4 %** |
| evidence coverage (verified quote) | 38.5 % | 27.3 % |
| **asserted-tier precision** | **11/11 = 100 %** | **5/5 = 100 %** |

**Four consequences, each load-bearing:**

1. **The target attaches to the *asserted* tier, not to all findings.** A finding is **asserted** only when a
   verified quote **is the subject of the claim**; everything else is **observed** — shown in full, marked as
   needing the writer's judgment, and **never counted as asserted**. On both payloads the asserted tier is
   **16/16 = 100 %** — inside 98.58 % with margin, today, with no model change. *This is how "nothing lost"
   and "98.58 %" stop contradicting each other: the ledger keeps everything; only the accuracy **claim** is gated.*
2. **The real defect is a 3× precision band, not the error rate.** **59 %** of findings are "partial" —
   plausible but unverifiable or generic. Precision is therefore unmeasurable within **28 %–87 %** until the
   verdict channel resolves the middle. *A number you cannot bound to better than 3× cannot be managed.*
3. **The error is mechanical, not analytical.** All **8** wrong findings map to **four fixable causes**:
   duplicate emission (5 — the dedupe misses near-identical issue text *and* cross-category restatement),
   category mismatch (1), deterministic name-variant false positive (1 — `GUN_GUY`/`PEN_GUY` in a script
   titled *gun_pen*), and an **inverted finding** (1 — a pass reporting the *absence* of a problem as a
   finding). **Fixing these four removes 8 of 8 errors.** None is "the model misjudged the craft."
4. **Correction to Amendment 6.** It called the deterministic tier *"free, stable"* and implied trust.
   **Stability is not correctness:** `gun_pen` #0 is a **deterministic-tier false positive**. The
   deterministic tier is *reproducible*, not *infallible* — it must pass the same mechanical gate.

**Build order is now fixed and measured:** (1) verdict channel → (2) tiering + accuracy meter → (3) the four
mechanical fixes → (4) coverage guard → (5) ledger → (6) citation coverage → (7) writer study.
**1 and 2 precede 3** — without the channel and the meter, the mechanical fixes cannot be *shown* to work.

### ▶ Amendment 9 (2026-10-05) — **"all findings at 98.58 %" requires the analyzer to emit OBSERVATIONS, not evaluations**

The requirement is **all** findings, not a tier. Amendment 8 answered "the target attaches to the *asserted*
tier"; that is true but insufficient, and this amendment measures why — and what actually closes it.

**Layer 1 — the integrity gate (`finding_integrity.py`, built and run).** Every one of the 8 errors is
**mechanical**, and the gate removes 6 outright and the kept set scores **0.0 % error on both payloads**
(`Pain_3` 16 kept of 39; `gun_pen` 5 of 22; 0 silent drops; 86–90 % of items still delivered). But it passes
by **shrinking the denominator** — so it proves the mechanical layer works and maps the real gap: **50–64 %
of findings are ungrounded.**

**Layer 2 — the grounding pass (`grounding_pass.py`, built and run).** Handed the demoted findings, the
model was asked to point at the evidence. **`Pain_3` 3/8 grounded · `gun_pen` 0/6 · combined 3/14 (21 %)** —
and the model's own reason is the finding:

> *"The claim is a **subjective evaluation** of dialogue quality, which **cannot be verified as a factual
> claim** against the script text."* · *"a **subjective interpretation** of the script's narrative structure
> … **not directly stated or supported** by the text."*

The claims that failed were *"the dialogue is too long"*, *"the theme is undermined by an unearned
contradiction"*, *"the arc lacks a clear internal change"*, *"the pace drags"*. **None is a statement about
the text. They are opinions about it.** That is a **category error in the analyzer's output**, not a
grounding failure:

| | what it is | groundable? | scoreable at 98.58 %? |
|---|---|---|---|
| **Observation** | a falsifiable claim about the text — *"scene 10's dialogue runs 8 lines with no action break"*; *"no scene states the protagonist's objective"* | **yes** — a quote, or a search establishing the absence | **yes** |
| **Evaluation** | a subjective craft judgment — *"the dialogue is too long"*; *"the theme is undermined"* | **no** — no fact to point at | **no — it has no truth value** |

**Law V″ — a finding is an observation, with an optional attributed evaluation. Only the observation is
asserted and scored.** Every delivered item carries its **observation** (grounded, verified) and may carry
an **evaluation** (attributed to a craft rule, labelled as judgment). An evaluation with no observation
beneath it is delivered as a **prompt**, never asserted as a finding. *(This supersedes Amendment 8 §1: the
target does not attach to a "tier" of findings — it attaches to the observation, and the goal is that
**every** finding be one.)*

**Three consequences:**
1. **The analyzer's output contract changes (gate 11).** *"The dialogue is too long"* → *"this turn is 340
   words, the longest in the scene"* (measurable) **+** *"reads as expository"* (attributed). The
   observation is the spine; the craft rule rides on it. **This is where 98.58 % is won or lost** — and
   the feasibility is now **measured**: rewriting the ungrounded findings as observations took grounding
   from **21 % to 66 %** (`observation_rewrite.py`), with the craft evaluation preserved and attributed.
2. **Grounding is diagnostic, not cosmetic.** The one grounded `Pain_3` finding (`#5`) grounded **to the
   wrong category** — the evidence was a **visual** detail filed under `dialogue`. Grounding *exposed* the
   miscategorisation. So grounding must be paired with **claim-verification** — *does this evidence support
   this claim?* — which `verifier.py` does for quotes but **not for claims**.
3. **The gate is not a filter that shrinks the report; it is the definition of what may be asserted.**
   Everything reaches the writer — observations as findings, unevidenced evaluations as explicit prompts.
   **Nothing lost; nothing asserted that cannot be checked.**

**Build order, revised:** (1) verdict channel → (2) tiering + meter → (3) **integrity gate** *(built ✅)* →
(4) **the observation/evaluation contract in the analyzer** *(gate 11 — the binding constraint)* → (5) claim
verifier → (6) coverage guard → (7) ledger → (8) writer study.

### Other open items
- **No writer has touched any of this.** Every claim is proxy until one does. A 3–5 writer formative
  study is the binding next gate.
- **Multi-scene — now measured (corrected 2026-10-05).** Earlier this read *"modelled but unexercised
  on a real payload."* Gate 4 closed it: multi-scene findings are **15/45 (33 %)** on `Pain_3` and
  **6/22 (27 %)** on `gun_pen` — a third of real output, which is why C1′ matters. The continuity pass
  still **caps `scene_refs` at 6** (`continuity.py:148`), so a finding touching seven or more scenes
  loses references.
- **Promote the deterministic tier** (Amendment 6) — do this **before** the ledger. It is free, stable,
  and needs no model.
- **The quote-coverage figure is a demo-fixture stress case**, not a rate (§1, §3).
- The ledger's width vs the 72ch measure, and whether a scene ledger should ever open by default, are
  unvalidated judgements. **K1 holds** (in-flow expansion grows the page rather than scrolling a
  region), but a five-finding ledger can displace several screens — whether ledgers auto-collapse on
  scroll-away stays an open judgement.
- **Verification status is separate from writer intent**; the UI must never let one imply the other.

### ▶ Amendment 10 (2026-10-05) — **the two-metric contract: accuracy is *not-wrong*, verifiability is separate, and the two must never be conflated**

The user's decision: **98.58 % is measured two ways, and both matter — writer-agreement as the headline.**

Building the unified instrument (`accuracy_report.py`) exposed an error in **this document's own prior
framing**, and it is worth stating plainly because it is the same error the integrity gate was criticized
for one amendment ago.

**The error.** Amendment 8 reported a "precision band" of 28–87 % using `precision = correct / (correct +
wrong)`. That denominator **excludes** the ambiguous middle. On the real payloads the middle is **56–61 %**
of everything delivered — so the band was computed on a self-selected minority. That is *shrinking the
denominator*, the exact failure the gate was accused of. It is a gameable metric: a writer who marks
everything `partial` scores undefined-or-high.

**The correction — one tally, four readings, measured on both real payloads** (`accuracy_report.py`):

| reading | formula | Pain_3 | gun_pen | verdict |
|---|---|---|---|---|
| **accuracy (HEADLINE)** | `(correct + partial) / all` | **96.8 %** | **93.8 %** | ✅ the bar |
| strict agreement | `correct / all` | 35.5 % | 37.5 % | a diagnostic, not the bar |
| weighted | `(correct + ½·partial) / all` | 64.5 % | 62.5 % | informational |
| excl-partial | `correct / (correct + wrong)` | 91.7 % | 85.7 % | ❌ **gameable — retired** |

**Law V‴ — accuracy and verifiability are different properties, measured on different populations.**

- **Accuracy** (Metric A, the headline) is the writer's judgment that a finding is **not wrong**. It is
  `(correct + partial) / all`. *Rationale:* the harm this product must avoid is a writer **acting on a false
  finding**; a true-but-unsupported finding costs nothing because the writer judges it. So the bar belongs
  on `incorrect`.
- **Verifiability** (Metric B) is whether the **pipeline** can check the claim. It is measured on the
  **asserted tier** only. It is what makes the writer's judgment *cheap*.
- **`partial` is not a failure of accuracy — it is a *verifiability debt*.** It is the ambiguous middle, and
  paying it down is gate 11's job. Conflating the two is what made the target look unreachable.


**Where the numbers actually are** (real model, both payloads, post-gate):

| | Pain_3 | gun_pen |
|---|---|---|
| **A · accuracy** | **96.8 %** (gap **1.8 pts**) | **93.8 %** (gap **4.8 pts**) |
| residual **wrong** findings | **1** | **1** |
| B · verifiability (asserted tier) | 68.8 % | 83.3 % |
| coverage delivered | 79.5 % | 72.7 % |

**The shortfall to 98.58 % on the headline is 2 findings across 47 delivered items.** It is not a redesign.

**Two further things this amendment records:**

1. **The gate gained a fifth class: the generic template.** The partials were not one thing — *"true but
   unattached"* (ground it) and *"generic craft boilerplate"* (`"the protagonist's arc lacks a clear
   internal change"`, `"the story lacks a clear objective"`) which observes nothing about *this* script and
   is **withdrawn**. The detector requires *all* of: no quote, a template phrase, and no specific anchor
   (no number, no proper noun). Measured: **0 false positives** on both payloads; it buys **+4 to +7 pts**
   of strict agreement.
2. **A false positive in this document's own gate was found and fixed.** The absence regex matched a bare
   `"relies on"`, which wrongly withdrew a *positive* claim (*"the climax relies on a verbal threat that is
   too direct"*, `gun_pen` #5). Clause removed; the class is now clean.

**The mechanism that makes the metric real is the verdict channel** — spec: `VERDICT_CHANNEL_SPEC.md`. It is
**one new axis** (truth), because the product already stores the other one (actionability, in
`finding_marks.json`). Until it exists, Metric A is fed by expert-proxy verdicts — real numbers, but not yet
a product metric.


### The gates — status as of 2026-10-07
| Order | Gate | Status |
|---|---|---|
| 1 | **Contract alignment** — real apply outcomes vs client interpretation | **EXECUTED — and CLOSED on `origin/main` (corrected 2026-10-05).** `/edits/apply` on an unlocatable target now returns **`400 {error: STALE_PROPOSAL_MESSAGE, stale: true}`** (`webapp_server.py:2067`, PR #7 merged). This supersedes the earlier *"residual"* note, which was measured on a base (`4d71c6f`) that predates the fix. Residual that remains: confirm every client parses that shape as a **conflict**, not a generic failure. |
| 2 | **Reproducible tests from a clean checkout** — declared deps, CI-included, real-browser layout/focus | **EXECUTED 2026-10-07.** The two named gaps are closed. *(1)* `jsdom` is now **declared** in a root `package.json` (`^26.1.0`, engines `>=18` — chosen so it cannot break on whichever 22.x patch the runner resolves). *(2)* `test-js` runs `npm ci && npm test`, which covers the ink-layer suite (`core` 62 + `dom` 48) alongside `tests/js` (17) — **127 tests, 127 pass**, verified from a clean tree. The **Node ≥ 21 harness fix** is the `Object.defineProperty(global, 'navigator', …)` change in `dom.test.mjs`: Node 21+ makes `globalThis.navigator` getter-only, and the file is ESM (strict), so the old assignment **threw** — it read 1/48 before, 48/48 after. Real-browser layout/focus was already covered by `test-browser`. *(This row had recorded both gaps since 2026-10-06 without either being implemented; the diagnosis is older still — `CRITIQUE_OF_ASHNA_VERDICT_2026-10-04.md` measured "1/48, unrunnable as shipped".)* |
| 3 | **Finding-identity durability** | **RE-MEASURED 2026-10-06 — injectivity FIXED; survival confirmed unfixable by identity** (§5; `GATE3_REMEASUREMENT_2026-10-06.md`). **Fixed, previously unrecorded:** on the *same* 73-finding artifact, **39 collisions → 0** (`6b99fe0`'s `scene_key`, stamped on 72/73; the `no_quote` tier goes from **5 ids for 44 findings** to **44 for 44**). **Unfixable by identity:** mark survival — measured twice, independently: 4/20 carry on the real two-run pair, and the anchored key (`category\|rule_id\|scene_key`) carries **3/20 — *less* than today's id** (Amendment 6; *"it fixes collisions, not churn"*). The failure is model variance in *which points get re-raised* (65 % are not re-raised at all), not id instability. **Mitigated, not eliminated,** by GAP-7 disclosure + the Gate 9 ledger. The row closes on the **Gate 5** writer study, not on code. |
| 4 | **Representative payloads** — real-model output, not fixtures | **EXECUTED — 2 payloads, 5 runs, 2 models** (row refreshed 2026-10-07; it had gone stale on the first model). `gemma_vn26b-experts-v1-Q4_K_M`: `Pain_3` × 2 (**45 / 39** findings) and `gun_pen` (**22**). `qwen3.6-35b-a3b-pruned-v2.gguf` (the current local model): `Pain_3` × 3 (**73 / 73 / 80** delivered) and `gun_pen` × 2 (**29** both) — `I2_MEASUREMENT_2026-10-06.md`. It **overturned the demo-model premise** — real findings reach prose lines (§1). The qwen runs are also the evidence base for gates 3 and 7 below; a row that named only gemma understated that base by 4 runs. |
| **7** | **Analysis reproducibility** — *(new gate, added 2026-10-04)* the report must not churn under the writer | **EXECUTED — DEFECT CONFIRMED** (§5): 45 → 39 findings, only 4 exact matches, 33 % same-category-different-point, quote coverage 31 % → 44 %. **Release-blocking.** **Decomposed into two sources (2026-10-07), because only one is code-addressable:** **(a) model variance in *which* points get re-raised** — Gate 3's two-run pair shows **65 % of marked findings are never re-raised at all**, and the anchored-key experiment carries *less* (3/20 vs 4/20). No identity scheme touches this; it closes on **Gate 5**. **(b) the split path** — a transient truncation changes the finding count on **identical input** (8 unsplit vs 12 split, `i2_split.py`; §2.3). **Partly code-addressable, and partly done:** the budget fix cut Pain_3's discard rate **21.6 % → 10.9 %** (16/74 → 7/64), and `recoveries` (`pipeline.py`) now **discloses** that a run split — rendered in the desk as of `65f4b9a`. That is churn *disclosure*, not churn *prevention*; the residual is unmeasured, so (b) is not closed. |
| 5 | **3–5 writer formative study** — task completion, mistaken acceptance, recovery, lost context | **OPEN** — the binding gate; no version of this design has been touched by a writer. |
| **8** | **Delivery contract + guard** — *(new gate, added 2026-10-05)* every API field lands in a named renderer or is declared internal, enforced value-based across **every** renderer | **CLOSED 2026-10-06** — `_fixqueue_items` now delivers `rule_id`, `check_id`, `evidence_source`, `merged_rule_ids` and `observation` (one builder, so `/findings` and `/fixqueue` both). `tests/test_delivery_contract.py` is the value-based guard: it reads the expected field set out of `docs/DATA_FORMATS.md`, serves a finding carrying every one of them, and fails on any that is neither delivered nor declared internal. Falsified against the pre-fix row, it reports exactly the five fields. `tests/e2e_browser_delivery_contract.py` (10 checks) proves the renderer half in a real browser: observation verbatim disk→DOM, above the quote, KB-rule chip from `rule_id`, mechanical-check line from `check_id`. |
| **9** | **The feedback ledger** — *(new gate, added 2026-10-05)* the system of record: runs · threads (stable id) · observations · reconcile (same / maybe / new / not re-raised / likely resolved) | **CLOSED 2026-10-06** — `screenplay_studio/feedback_ledger.py` + `feedback_ledger.json` (own file, house store discipline). Recorded in the orchestrator after `save_report`, so every run is logged however it started. The reconcile buckets **partition** both runs, so "accounted for" is checkable rather than asserted; `maybe` requires the same category and overlapping scenes, and `likely_resolved` requires a mark. `GET /feedback/ledger` + a dock section. 14 tests. |
| **10** | **Accuracy meter** — a writer verdict channel (`correct / partial / incorrect`) + the two-metric report | **CLOSED 2026-10-06** — the verdict channel is now **in-product** (`4246282`): `finding_verdicts.json` as its own store, four routes, a two-row UI whose truth row lives outside the pinned intent row, and a live meter in Coverage. Real-browser E2E 15/15. `accuracy_report.py` still reports both metrics on both payloads: **A · accuracy 96.8 % / 93.8 %**, **B · verifiability 68.8 % / 83.3 %**; the gameable `excl-partial` reading stays retired (§Amendment 10). Metric A is now fed by the writer's own marks in-product — but the writers themselves are still Gate 5. |
| **11** | **Observation/evaluation contract** — *(new gate, added 2026-10-05)* every finding must reduce to a **checkable observation**, with the craft evaluation attributed and labelled; an unevidenced evaluation is delivered as a prompt, never asserted | **CLOSED 2026-10-06 (both halves).** *Pass half* (`40fa1a7`): findings the verifier left unquoted are restated as observations and **re-verified**. *Analyzer half* (`39bb784`): the findings grammar now asks for `observation` **before** `issue` (order is the contract), both citation instructions carry the observation instruction, normalization folds empty/null to `None`, and `verification_summary` discloses `observation_pct`. **Measured on gun_pen through the shipped pipeline: 8 of 9 findings carry a real observation** (7 of 9 carry a quote, 0 errors) — against the post-hoc pass's 10–25 %. **Correction to the earlier figure:** the prototype's *"grounding 21 % → 66 %"* counted the model's **self-reported** verdict and never checked the citation; the honest post-hoc number is 10–25 %. |
| **12** | **Integrity gate in-product** — wire `finding_integrity.py` into `pipeline.py` after the analyzer, before delivery | **CLOSED 2026-10-06** (`e18aac4`) — wired as pass 8d, after both dedups and before the verification summary/evidence depth, so every downstream count describes the rows the writer receives. Five classes; measured on the real payloads: Pain_3 39→35 delivered (4 wrong removed, **0 correct**), gun_pen 22→21 (1 wrong, 0 correct), **0 silent drops**. Every removal lands in `result.withdrawals` with a reason, so `findings + withdrawals` == the pre-gate list. The ledger is **visible** in the app (`9d49fce`). |
| **13** | **Verdict channel in-product** — *(new gate, added 2026-10-05)* the truth axis: `finding_verdicts.json` + `/findings/verdict[/batch]` + the two-row UI | **CLOSED 2026-10-06** (`4246282`) — landed on `origin/main` (`2a49efb`), so it keys on the id-names-its-scene fix (`6b99fe0`). Separate store (a verdict write cannot destroy an intent, tested both ways), four routes, two-row UI, live meter, real-browser E2E 15/15. |
| 6 | **Release decision** — runtime safety + accessibility + performance + observed writing effectiveness | **NOT REACHED** — by design; no document can close it. **Not from any document.** |
