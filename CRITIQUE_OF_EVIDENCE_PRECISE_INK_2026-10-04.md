# Critique — "Scene-First, Evidence-Precise Ink"

**Date:** 2026-10-04 · **Subject:** the uploaded review/refinement of `docs/design/scene-first/ARCHITECTURE.md`
**Method:** every claim checked against the repository it describes and against the architecture document it critiques — not against its own summary. No tracked file modified.

---

## Verdict

**Legitimate, valuable, and not a replacement.** The document is a careful refinement that finds **three genuinely important gaps** in Scene-First Ink — and two of them are *stronger* than the document itself claims, because the repository already emits the cases it worries about. But roughly a third of its critique table is either a restatement of caveats my document already carries, or a misreading of one rule; and its own proposed architecture **re-introduces the exact defect this product deliberately retired and now guards with tests.** The right move is not to adopt it as the verdict or discard it — it is to fold its three real contributions into Scene-First Ink and reject its two surface proposals.

The single most important thing it gets right: **a finding's scope is not always one scene.** The product's own schema has said so all along.

---

## 1 · My measurements vs the document's

| Claim in the document | What the repository actually shows | Verdict |
|---|---|---|
| "A finding's home is its scene" — some findings concern **multiple scenes** | `continuity.py:148` → `"scene_refs": sorted(a_scenes \| b_scenes)[:6]`; `dedupe.py:211-214` merges `scene_refs` on merge; `grammar.py:73` types it `int-array`; `report.py:69` renders `"Scene 5, Scene 6"`. Multi-scene is **first-class in the data**. | **Confirmed — and stronger than stated** |
| "Low quotation coverage may be legitimate… forcing quotes can encourage fabricated evidence" | `REAL_SCRIPT_RESULTS.md:159-164` (§5) already warns the notes are `[demo]` fixtures and "judge the notes elsewhere". The instruction to raise the citation rate was mine. | **Confirmed — best point in the document** |
| "Script ledger at the top **and** a separate Report room — these may duplicate… competing state" | The Report/Fix-Queue pane was **retired** because it was "a third surface projecting the same findings state" (`index.html:437-445`); the law is "**one findings state, one lens**" (`app.js:7653-7654`). | **Confirmed — and stronger than stated** |
| "Fuzzy `≥ 0.72` grants precision" | `ARCHITECTURE.md:34` (K5) already says "a tie is reported, never guessed". But a *non-tie* wrong match at 0.72–0.99 is not caught. | **Partly valid** |
| "‘The commit is the only write’ conflicts with saving notes, preferences, discussions" | `ARCHITECTURE.md:31` (K2): "Auditioning a rewrite never touches **the document**; the commit is the only write." In context, *the document* = the manuscript. | **Misreading** |
| "State that the sampled report did not support useful prose-line anchoring… treat as a stress case, not a population estimate" | `ARCHITECTURE.md:78-81` — "**Still open (deliberately):** … the 16-finding sample is **n = 1**; a quote-rich report from a real model would weaken C1." | **Already in the target document** |
| "Four actions: Locate · Rewrite · Discuss · Keep — use scope-aware actions" | The **prose** says four uniformly (`ARCHITECTURE.md:39`); the **prototype** already varies them — the scene finding has no *Locate* (`index.html:381`), the measured finding has no *Rewrite* (`index.html:405`). | **Valid against the prose, already true in the artifact** |
| "One count can hide filters / deferred / partial" | `DEVELOPMENT.md:94-96` states the N3 contract: one `findingFilter` drives ink, board list, loop list and counts together. | **Valid — and already the product's law** |

---

## 2 · Confirmed contributions — adopt these

### A. Multi-scene scope is real, and the schema already produces it *(High)*
This is the document's best find. My C1 said "a finding's home is its scene" and C3 gave only *script*-level findings a separate home — leaving **multi-scene** (two to six scenes) unrepresented. The repository does not merely allow this case; it **emits** it: the deterministic continuity pass unions two scenes into `scene_refs` (`continuity.py:148`), `dedupe` merges the arrays of findings it merges (`dedupe.py:211-214`), and the report text already prints "Scene 5, Scene 6" (`report.py:69`). The Ink Layer prototype **collapses** every such finding to a single row: `anchorFinding` returns one `rowIndex` (`core.js` anchor fn) and the bucketing loop assigns it once (`ink-layer.js:487-537`). So the second scene loses its mark, silently.

The document asked for `passage · scene · multi-scene · script` scopes. That is correct, and it should be **mapped onto `scene_refs`**, which already is the multi-scene field. Adopted as **C1′** below.

### B. "Do not force quotes" is a safety requirement, not a nicety *(High)*
My document ended with "make the analyzer emit verifiable quotes, or an explicit `scene_anchor`" and framed the citation rate as "the bottleneck". The document is right that this framing carries a **fabrication incentive**: an analyzer tuned to raise quote coverage will produce quotes that do not support the diagnosis — worse than a `no_quote` finding, because it looks verified. The correct instruction is *appropriate evidence and explicit scope*, never *quote percentage*. This is the single most valuable sentence in the document and it is now a stated non-goal of the architecture.

### C. The Report-vs-script-ledger duplication is a real defect — and the product already retired it once *(High)*
The document flagged "competing state" between a script ledger and a Report room. The repository is more emphatic than the document could know: the Report/Fix-Queue pane was **deliberately removed** as "a **third surface projecting the same findings state** as the Evidence lens" (`index.html:437-445`), the law recorded as "**one findings state, one lens**" (`app.js:7653-7654`), and the removal is now **guarded by tests** — `test_app_symbol_integrity.py::test_feedback_view_clone_is_gone`, `::test_problem_board_is_gone`, and a `fv|pb|rail|struct-rail` class-family guard; plus `e2e_browser_dock_sections.py:723-725` ("no second chart surface exists"). My screen 5 ("Report") proposes to rebuild exactly that. **Adopted: the script ledger lives in the manuscript's flow (C3); there is no second findings list.**

### D. Evidence status ≠ critical validity *(Medium)*
K4 encoded "stroke is verification". The document correctly separates **location confidence** from **critical validity** — a quote can be present while the diagnosis is wrong, and a structural criticism can be useful with no quote. The mark should mean *"a citation was verified to this text"*, never *"this criticism is correct."* Adopted as **C7**.

### E. The review-loop safety table *(Medium)*
The document's "Discover → Inspect → Decide → Preview → Refine → Apply → Recover" table is more complete than my K2, and it independently reaches the same contract gaps I found in the runtime audit: *"If the manuscript changes while generation is running, the returned proposal must be treated as potentially stale"* and *"A retry must not duplicate an accepted edit."* These match the missing `stale` flag and the uncancellable SSE worker found earlier. Adopted as **C9**.

### F. Proportional failure *(Low-Med)*
"Fail loudly" (K6) is a backend principle; applied to a writing surface it can interrupt. Errors should be explicit, local, and proportional. Adopted as a refinement to K6.

---

## 3 · Wrong or overstated claims

### W1 — "The commit is the only write" is a misreading, not a finding *(High-priority row, but not High)*
`ARCHITECTURE.md:31` reads: *"Auditioning a rewrite never touches **the document**; the commit is the only write."* The sentence is scoped to the manuscript. No reader of K2 concludes that notes, preferences, or discussions do not persist. The document elevates a definitional quibble to its High tier, where it displaces a real finding. **Rejected.**

### W2 — The n = 1 "correction" is already the target document's own caveat
The document's first High row asks me to "state that the sampled report did not support useful prose-line anchoring… treat this as a design stress case, not a population estimate." `ARCHITECTURE.md:78-81` already says exactly this, under the heading "Still open (deliberately)". Presenting a hedge as a correction inflates the critique table. **Already true.**

### W3 — The document is written above the product
It never once names the product's actual differentiator: the **263-rule attributed craft corpus**, the `rule_id` → rule-name provenance, the diagnose/prescribe split, the co-writer personas, or the twelve analysis categories. Its vocabulary — "Review the overall assessment", "sustained discussion with explicit context" — could describe any document-annotation tool. My architecture was argued from *this* product's data (16 findings, 19 % quote coverage, the heading pile-up, the retired Report pane). A design review of a *specific* architecture should engage the specific advantage; this one floats above it.

### W4 — Its own architecture re-raises the surface-count problem it diagnoses
Having (correctly) flagged duplication between a script ledger and a Report room, the document's §E then lists **Desk · Report · Partner · Ideas · Structure** as five surfaces and says only that "movement between them should retain the writer's context" — without a state model. It does not resolve the "one findings state, one lens" law; it relabels the problem. Notably, it **independently derives half** of the N3 contract ("one canonical counting model") and then **violates the other half** (surface count).

### W5 — Its "Unresolved location" section re-creates a list the implementation deliberately refused
§A proposes an "Unresolved location — in a clearly labeled unlocated section." The shipped Ink Layer **already** handles exactly this class — script-level, missing-scene, and parked findings — as a **one-time announcement**, not a list: `core.js:916-933` builds the sentence *"N finding(s) not on a line… The desk's board holds it"*, and `ink-layer.js:539,1886-1887` announces it once at boot. The header comment is explicit: *"FINDINGS THE PAGE CANNOT PUT ON A LINE — said, not swallowed."* The document's proposal would **regress** a solved problem into a second list. **Rejected.**

### W6 — Two proposals would trip existing tests
The "Report room" and the "Unresolved section" both add findings-list surfaces. The repository enforces their absence: `tests/test_app_symbol_integrity.py` asserts `renderFvBoard`/`renderProblemBoard` never return, `#feedback-view`/`#problem-board` are not in the DOM, and a `fv|pb|rail|struct-rail` family guard fails if CSS styles a class nothing renders. A design that proposes them without naming the guards is not yet implementable.

---

## 4 · What the document missed

1. **The `stale` contract does not exist on the wire.** The document correctly *requires* stale-proposal handling, but it is stated as a future requirement. It is in fact a **live gap**: `/edits/apply` returns `200 {applied: [], skipped: [{reason: "line not found in scene"}]}` and never emits the `stale` flag the client's `core.js` reads. The requirement is not aspirational — it is a currently-broken contract.
2. **The off-page model already exists** (W5) — so "unresolved" is not an open design question.
3. **`scene_refs` is already the multi-scene field** (A) — so the scope model needs no new schema.
4. **The craft corpus.** The document treats attribution as optional ("available attribution"). For this product the attributed rule *is* the value proposition; the prototype's own weakness (finding F4 in my earlier review — it prints `DIAL-114` instead of the rule name) is precisely the thing the document is silent on.

---

## 5 · Brainstorm — three readings of this document

| Reading | What it implies | Assessment |
|---|---|---|
| **Replace** Scene-First Ink with "Evidence-Precise Ink" | Cleaner scope model, but loses the measurement grounding, the rendered prototype, and the product-specific craft attribution — and re-introduces two surfaces the repo forbids. | **Reject.** A generic rewrite of a product-specific architecture. |
| **Ignore** it (it restates my caveats and misreads K2) | Keeps the prototype, but leaves multi-scene collapsed and keeps a fabrication incentive in the closing instruction. | **Reject.** Throws away three real finds. |
| **Merge** — fold its valid contributions into Scene-First Ink | Multi-scene scope, evidence ≠ correctness, scope-aware actions, "don't force quotes", the stale contract — onto the existing measured, rendered architecture. | **Adopt.** This is the best fit. |

**The corrected architecture is Scene-First Ink v2**, with six changes (see `docs/design/scene-first/ARCHITECTURE.md` §"Changed"): a first-class scope model mapped to `scene_refs`; evidence-status ≠ validity; scope-aware actions (already true in the prototype, now true in the prose); no second findings list; "don't force quotes" as an explicit non-goal; and the stale/retry contract stated as a required wire behaviour.

---

## 6 · Bottom line

- **Act on:** (1) multi-scene scope — mark every referenced scene, count once; (2) the "don't force quotes" safeguard; (3) collapse the Report room into the manuscript's script ledger to honour "one findings state, one lens"; (4) separate evidence-status from critical-validity in the mark's meaning.
- **Do not act on:** "the commit is the only write" (misreading), the separate Report room and the "Unresolved section" (both violate an enforced law), and the framing of my own n = 1 caveat as a correction.
- **Re-measure before citing:** whether a real (non-demo) model produces a quote-rich report — that single number decides how much of C1′ matters. It is not in the repository; the 43-finding real run is the payload that would settle it.
- **The document's own honesty holds:** it says its evidence boundary up front. That is why its three real finds survive scrutiny — and why its two surface proposals, made without the repo, do not.

**The one thing neither document can supply: a writer.** Every claim here is proxy until one touches it.
