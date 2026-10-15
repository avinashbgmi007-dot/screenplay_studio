# Critique of the Ashna verdict — is it the best fit, or can we do better?

**Date:** 2026-10-04 · **Reviewed:** `Ashna_answer_in_markdown.md`
**Method:** claim-by-claim validation against the repository it describes, with every
empirical claim re-run. **No tracked file was modified.**

---

## 0. Verdict (one paragraph)

Ashna's document is a **competent design review that did real work** — the repo's own
`SELF_CRITIQUE.md §6` is titled *"the verdict checked against the build"* and names **"the uploaded
Ashna verdict"** as its input, so at least four contract-level defects were fixed because she raised
them. But as an answer to *"is this ready?"* it is the **wrong instrument**: it repeatedly asks for
verification instead of performing it, and **three of its "required corrections" were already
implemented before it was written**. It is not the best fit. A verification-first answer is — and the
repo has already produced most of one, in `SELF_CRITIQUE.md §6–§7`.

The single most important thing she gets right: **the product's "central safety guarantee" is not
proven server-side.** I confirmed it, and it is worse than she said.

---

## 1. My measurements vs the document's

| Claim | Ashna's position | What I measured | How |
|---|---|---|---|
| "**60 tests green**", "proven mechanics" | reported, not verified | **62/62 core** green as shipped; **48/48 DOM** green *only after* `npm i jsdom` **and** patching a Node ≥21 harness line; **110 total, 0 failed** | `node --test tests/core.test.mjs tests/dom.test.mjs` |
| The DOM suite | — | **unrunnable as shipped**: no `package.json` anywhere, `jsdom` undeclared, and the harness throws `Cannot set property navigator … which has only a getter` on Node 22 → **1/48** | `node --test tests/dom.test.mjs` |
| The documented run command | — | **`node --test tests/` fails on Node 22** (`Cannot find module …\tests`) — the directory is treated as a module | same |
| Test counts in the repo's own docs | — | **three different numbers, all wrong**: `INK_LAYER_SPATIAL.md:5` says 103, `:538` says 60, `SELF_CRITIQUE.md:28` says "77 … 104 now". Actual: 62 + 48 = **110** | `grep` |
| "Server-side stale-edit rejection" unproven | **correct** | **correct, and worse than stated** — the `stale` flag is **absent from the wire entirely** | live `POST /edits/apply` |
| "Tolerant parsing of rewrite response shapes" | dangerous as a contract | **already fixed before her doc** — `normalizeRewrite` now returns `{unknown, reason}` and casts nothing | `SELF_CRITIQUE §6.1` |
| "Refuse **automatic target selection**, not assistance" | required correction | **already implemented** — `ink-layer.js:957-960` | `grep` |
| "Defer Root System and Story River" | final recommendation | **already the repo's position** — `OPEN_QUESTIONS.md §9` | `grep` |
| "Zero attention travel optimizes the wrong thing" | **correct** | repo independently agrees — "the docs already retired Zero-Travel as a UI metric" | `SELF_CRITIQUE §6.1` |
| "No writer has touched any of it" | stated as a limitation | **correct** — §5, §6.4 and §7.6 all say so | `SELF_CRITIQUE` |

---

## 2. Where she is right — confirmed, with a sharper mechanism

### 2.1 The stale refusal is not merely unproven; its contract does not exist
Her claim: *"Client-side preview restoration does not establish server-side stale-edit rejection."*
Confirmed — and the precise mechanism is worse than "unproven":

- **Shipped code never emits it.** `grep -rn "Stale proposal\|stale.*True" screenplay_studio/*.py`
  → **nothing**. The only occurrences of `"Stale proposal: the text was modified manually."` are in
  the prototype's own doc-comment (`core.js:827`) and in an **un-applied patch** filed under
  `docs/design/ink-layer/backend-patches/revision_stale_guard.py` ("Paste the block below into
  `screenplay_studio/revision.py`"). Nothing imports it.
- **The client keys on a flag that never arrives.** `core.js:855`:
  `if (body && body.stale === true) return { kind: 'stale', … }`. The whole stale state machine —
  byte-exact restore, `data-cast="stale"`, the refusal printed in the fold, the re-cut frame — is
  unreachable against the real backend.
- **What the real route actually does** (live, on a 120-scene project):
  ```
  POST /edits/apply  (re-sending a proposal whose text had already moved)
  -> HTTP 200
     {"applied": [], "skipped": [{"old": "Counter 5: …", "new": "…",
                                  "reason": "line not found in scene"}], …}
  ```
  **No `stale` flag. No 4xx.**

So: **the safety property holds** (nothing is written; the writer is told why, via the generic
`applyReport` path — `"Nothing was applied. — line not found in scene"`), **but the dedicated
guarantee UI never fires.** The prototype exercises it only against its own mock
(`demoErr(status, message, stale = false)`). This is exactly Ashna's objection, promoted from a
doubt to a demonstrated contract gap.

### 2.2 The other two she is right about
- **"Zero attention travel" is the wrong objective.** The repo reached the same conclusion
  independently and retired it as a UI metric (§6.1).
- **"Tolerant parsing is dangerous as a production contract."** Correct — and it was a real defect:
  the tolerant parser is what let a wrong payload shape pass silently (§2.2, §6.1).

---

## 3. Where the document is wrong, imprecise, or already settled

### 3.1 Three "required corrections" were already implemented
This is the document's biggest weakness — it critiques the **verdict document** as if it were the
current state, when the repo had already moved past it. `SELF_CRITIQUE.md §6.1` is literally a table
titled *"What the verdict demanded, and where the repo already matched"*:

| Her "required correction" | Status when she wrote it |
|---|---|
| "Refuse **automatic target selection**, not assistance itself" | **already done** — `ink-layer.js:957-960`: *"Automatic targeting is refused whenever the evidence is unverified, but an explicit request is honoured WITH the warning retained: refusing assistance outright would block legitimate work on uncertain diagnoses."* Her sentence and the code's comment are the same argument. |
| "Establish a validated response schema; unknown shapes must fail clearly" | **already done** — `normalizeRewrite` reports `{unknown, reason}` and casts nothing |
| "Defer the graph (Root System)" | **already deferred** — `OPEN_QUESTIONS.md §9`: *"Root System and Story River stay deferred"*; her final recommendation #3 restates the repo's existing position |
| "Separate finding identity from text location" | **already done** — `fuzzyScore` + `anchorFinding` at 0.72 with `exact`/`loose`/`ambiguous` |

A reviewer who cannot see the repo cannot know this — but it means the document re-litigates
settled decisions, and adopting it as *the* answer would send work backwards.

### 3.2 Two factual claims are loose
- **"A content hash can change when finding wording changes."** The desk's identity is
  `compute_finding_id` = `category + evidence_quote` (with an `issue` fallback only for the
  no-quote tier). So changing the *issue wording* does **not** move the id for quote-bearing
  findings; only changing the *quote* does. Her worry is real for the `no_quote` tier only — and the
  desk's own `no_quote` rate is 83 % on a real script (`CRITICAL_REVIEW_2026-09-18.md:399`), so the
  concern is real but her statement of it is not accurate.
- **"Quote matching can also select the wrong occurrence when text repeats."** Already handled —
  `core.js:489-513` returns `{rowIndex, score, exact, ambiguous, loose}` and is documented as
  *"never a silent guess"*; an ambiguous quote is cast **with the warning kept**. She critiques a gap
  the build had already closed.

### 3.3 She repeats the number she is right to distrust
Her document says the attachment *"reports"* "60 tests green". She never replaces it with a real
number. I did: **110** (62 + 48) — and the DOM half is unrunnable as shipped.

---

## 4. What the document missed entirely

Because it never runs the artifact, it misses everything the artifact hides.

**Defects the repo's own alignment/code-audit passes found — none of which appear in her document:**
1. **A severity word that drew nothing** — the desk's `high` landed as `data-worst="high"`, which no
   stylesheet matched, so the row's severity border fell to **0 px**: *a critique present in the data
   and invisible on the page* (§6.2, §7.3).
2. **The strip's stylesheet did not exist** — in a real browser the take list rendered as a
   browser-numbered `1. 2. 3.` list wrapping every three words. Invisible to jsdom.
3. **A dead editor branch** — `renderTakeList` tested `C.editingProposal` (core namespace) instead of
   `S.editingProposal` (page state).
4. **The way back from a roam was unreachable.**
5. **The ambiguity warning could be overwritten** by the first keystroke (last-write-wins).
6. **Every scene heading was drawn twice** on a real payload → a false *"this quote matches more than
   one line"* on **3 of 3** real quotes (§7.7b).
7. **`applied` is a list, not a count** → a real apply would have announced `"Applied [object Object]"`.
8. **`.find-issue` carried the UA's `margin: 1em 0`** → 53 px for 22 px of text on every finding in
   every fold (§7.7c).

**Reproducibility gaps her document could have named but didn't:**
- No `package.json`; `jsdom` is a prose instruction, not a declared dependency.
- `node --test tests/` **fails** on Node 22 — the command in the docs does not work.
- **CI never runs the ink-layer suite** (`.github/workflows/ci.yml` has no reference to it), so 110
  tests can rot — and they have: the harness is broken on Node ≥21.
- The three conflicting, all-wrong test counts in the docs.

**The instrument that actually matters — and that neither document supplies:**
`SELF_CRITIQUE §5` states plainly what the work is not: *"evidence that the Detent is right …
None of that is a usability result"*; §6.4 and §7.6 repeat it — **no writer has touched any of it.**
Ashna's document identifies this ("Independent design agreement also does not establish usability")
but does not act on it either. **The binding constraint on this feature is a five-person usability
test, not another document.** Everything else is proxy.

---

## 5. Could I do better? Yes — but "better" is a different instrument, not a better essay

Her document is a **design review**; the question it is being asked to answer is a
**readiness question**. Those are different instruments, and a well-written review cannot substitute
for the other. Three concrete upgrades:

1. **Answer with measurements, not requests.** Where she writes *"validate the critical workflow with
   code, integration tests, and writers"*, the better answer runs it: 110/110 tests (with the two
   environment fixes named), the live `POST /edits/apply` transcript showing `stale` is absent, and
   the specific defects the run exposes. I have produced that here.
2. **Score the corrections against the implementation, not the document.** Her three already-done
   items become "confirmed, keep" instead of "required correction" — which stops the work from
   moving backwards. This is the highest-value single change to her document.
3. **Name the one gate that is still closed.** Not a design gate: **a writer has never seen it**,
   and the suite that would catch regressions is not in CI. Recommend exactly two next actions —
   (a) apply the backend stale guard so the safety contract exists on the wire, (b) put the 110
   tests in CI — then a writer test.

**What her document is still the best fit for:** as a *design* challenge sheet. Its rows on
zero-travel, severity-as-scale, and deliberate-acceptance are the right questions to put in front of
a designer, and §6.1 shows they landed real changes. Keep it — as a checklist that has already been
scored, not as the verdict.

---

## 6. Bottom line

| | |
|---|---|
| **Is it the best fit?** | No. Right questions, wrong instrument, and partly stale. |
| **Is it valuable?** | Yes — it drove a real alignment pass that fixed contract-level defects. |
| **Biggest strength** | The stale-rejection objection. Correct, and load-bearing. |
| **Biggest weakness** | Three of its "required corrections" were already implemented; it never ran the artifact it judged. |
| **The one thing neither document has** | A writer at the keyboard. |
| **Act on** | (1) Apply `backend-patches/revision_stale_guard.py` so `stale` exists on the wire; (2) put the 110 tests in CI and fix the Node ≥21 harness line; (3) correct the three test counts in the docs; (4) then run a 3–5 writer usability test. |
| **Do not** | Treat either document as evidence the design is right. Both say so themselves. |

---

*Every claim above was re-run or re-read at the cited location. Where I could not verify something,
I say so rather than assert it. The measurement that took the most work — and changed the answer
most — was simply running the tests the docs counted.*
