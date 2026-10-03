# Self-critique — building the agreed architecture and The Detent on this repo

Written after the implementation, not before it. Everything below is checkable against the
files in this directory; where I am describing a judgement rather than a fact, I say so.

> **Read this file in two parts.** §1–§5 are the record of the round that built the Detent on this
> repo, and they contain claims this build has since superseded — most visibly the strip's reading
> order, and "J/K cast inside the live line". §6 is the alignment pass that superseded them, and it
> names each superseded claim. `OPEN_QUESTIONS.md` holds the decisions this build could not settle
> on its own.

---

## 1 · What was asked, and what is now in the repo

**Asked:** implement the architecture we agreed (`ARCHITECTURE_VERDICT.md` §5/§6) and the
finalized UI (**The Detent**) on the existing `ink-layer/` code, going through the files
first, and turn the same work over as a self-critique.

**Shipped:**

| File | State | What changed |
|---|---|---|
| `detent.css` | **new, wired** | The Detent as the colour pass `ink-layer.css` explicitly asks for ("colour is a later pass"). Tokens + two grounds, ink states, the fold as a machined slot, the cast strip as an instrument, the horizon paint, focus, reduce, print. |
| `core.js` | changed | The real `/rewrite` and `/edits/apply` contracts; `classifyApplyError`; `normalizeFindings`; `normalizeSummary` reads the route's own field names; the ring gained a **zero point** (`stepRing` now spans `len + 1` places); **Rehearsal** (`rehearsalMode`, `rehearsalStep`, `REHEARSAL_BEAT_MS`) and its copy. |
| `ink-layer.js` | changed | Error bodies ride the thrown error; the demo adapter re-implements the route's verbatim guard *and* closes the finding a landed fix answered; the strip is an instrument (take → ledger → rationale → keys); the **void** for a refused proposal; **Rehearsal** (temporal for voice, spatial stack for structure); the ground toggle; one place decides ink state and *why* it is dry. |
| `index.html`, `build-single.mjs` | changed | `detent.css` linked second and inlined second; the bundler's emission order fixed (see §2.1). |
| `tests/` | changed | 77 tests, all green at the time (`node --test tests/`); **104 now** — see §6. New: stale-refusal classification, demo-guard parity, Rehearsal (timing, interruption, stack), the two inks, the ground, the instrument's reading order. |
| `ink-layer-preview.html` | regenerated | 133 KB single file, opens offline, no network. |

**Verified in a browser, not by inspection:** 20 rows / 2 scenes render; the strip's children
are `cast-take → cast-ledger → cast-meta → cast-keys`; a refused proposal leaves the writer's
text byte-identical and prints `Not written …` in the fold; the two inks resolve to
`rgb(227,166,83)` (evidence) and brass-at-42 % (choice); manuscript contrast is **15.8 : 1** on
the instrument ground and **13.7 : 1** on the lifted ground; no horizontal overflow at 1440 /
1280 / 860; `prefers-reduced-motion` zeroes the transitions; print is black on white with the
critique excluded; zero `button`, `input`, `a`, `dialog`, `aside`, `nav` elements on the page.

---

## 2 · Defects I found in the existing repo — and why they existed

These are not stylistic preferences. Each one was a real failure of the shipped code, and
three of them were invisible to a green test suite.

### 2.1 The only offline artifact was dead, and 60 green tests said nothing about it
`build-single.mjs` emitted the namespace object — `const C = { DWELL_MS, … }` — **before** the
core body it references. `const` bindings are in the temporal dead zone until evaluated, so
`ink-layer-preview.html` threw `Cannot access 'DWELL_MS' before initialization` on load and
rendered an empty page. Every test imported `core.js` directly, so the suite could not see it.

That is the most useful failure in this whole turn: **the tests tested the modules; the
deliverable was the bundle; nothing tested the deliverable.** Fixed (core → namespace → wiring,
with a comment naming the trap), and the browser pass is now part of the loop rather than a
final flourish.

### 2.2 The wire contract in the code was not the wire contract of the product
`applyPayload` produced `{ project, edits: [{ line_start, old_text, new_text }] }`. The route
reads `{ scene_number, replacements: [{ old, new }] }` and refuses the *whole* proposal when
`old` no longer matches the working copy. The rewrite request sent `{scene, line_start,
finding_id}` where the route reads `{scene_number, finding_index, instruction}`.

So the repo had a beautiful cast mechanic that would 400 (or write nothing) against its own
backend. Both payloads are now the real ones, and `applyPayload` takes `old` from the frame's
captured target — the only source that can produce a proposal consistent with what the writer
saw on the page.

### 2.3 The stale refusal — the product's central safety guarantee — had no UI at all
The route protects the writer: if the text moved under the proposal, nothing is written and the
caller is told `{"error": "Stale proposal: …", "stale": true}`. The renderer caught the error,
printed `e.message`, left the failed candidate **on the page** and re-armed the row as `active`.
That is the one state the guarantee exists to prevent: a page showing a line that was never
written.

Now: the take comes off the line, the writer's own text goes back byte for byte, the row is
marked `data-cast="stale"` in dashed broken brown, the frame is re-cut against what is on the
page, and the refusal is **printed in the fold and left there** — a 400 that vanishes like a
toast is a 400 the writer has to remember. `classifyApplyError` decides from `body.stale`,
never from the sentence, because the sentence is prose and the flag is contract.

### 2.4 The reconciliation could not disagree with the server
`normalizeSummary` only read legacy field names (`open`, `addressed`, `dismissed`). The route
answers `{open_count, done_count, dismissed_count, by_status}`. Against a real studio the totals
came back `null`, the drift check compared nothing, and a meter built to catch disagreement was
structurally incapable of it. Same defect for findings (`items` vs `findings`, `evidence_quote`
vs `evidence`). Both now read the route's vocabulary first, and the tests assert that reading.

### 2.5 The ring had no zero point, and one test passed by luck
`stepRing` clamped at index 0 and treated `-1` as "the first press". The renderer's own state
used `ring: -1` to mean *the writer's own line*, so the strip could not step *back* to it, and
the ledger had nothing to name. Worse: one DOM test asserted "K restores the original byte for
byte" — it passed only because that fixture's take 1 happened to *be* the original text. The
model is now honest (`-1` is a real position, labelled `ORIGINAL / 03`, announced on arrival),
and the test that passed by accident is a full ring round trip that would catch accumulation.

**The pattern in all five:** the repo's mechanics were strong and its *contracts* were assumed.
Every defect above is a place where an assumption met a reality it had never been checked
against — payload shapes, field names, emission order, and one piece of state that was load
bearing and unnamed.

---

## 3 · Where I bent the agreed rules, and what it costs

### 3.1 I put structural properties in the colour pass (deliberate, disclosed)
`ink-layer.css` says colour "must slot in WITHOUT this file changing shape". Four elements the
Detent needs did not exist — `.cast-ledger`, `.cast-void`, `.cast-stack`, `.cast-keys` — so
their **placement** (`grid-column: 1 / -1`, a flex row) is declared in `detent.css`, the pass
that created them. The alternative was editing the structural sheet, which its own header
forbids. Cost, stated plainly: the structural sheet is no longer the complete source of the
strip's geometry, and anyone reading only `ink-layer.css` will not know how the strip lays out.
The correction is four lines in `ink-layer.css` §C — I did not take it because it changes the
file the round agreed not to change. **This is the one rule I knowingly bent; I bent it toward
"the colour pass owns what it introduced", not toward convenience.**

### 3.2 The fonts are not the fonts the Detent was drawn against
The Detent was designed against Instrument Serif and DM Sans. `detent.css` *prefers* those
faces when the studio has them self-hosted and falls back to system stacks with no network
fetch, so the artifact stays offline-clean — but the tracking values I set are tuned to the
fallback. On a machine without those faces the interface voice is close, not exact. A design
review should look at it in the studio's own build before the register is called settled.

### 3.3 The shipped ground is not the ground the round chose
The design round's canonical bench is the **lifted** ground (`#241a12`, L\*10.2). I shipped
`data-ground="instrument"` (the darker #150807 bench) as the default because that is the
existing register, with `g` toggling to the lifted one and the annunciator saying which you are
on. Defensible as continuity; dishonest if presented as the round's decision. If the lifted
ground won the comparison, the default should be flipped and this line deleted.

### 3.4 "Read aloud" is an overclaim
Nothing is spoken. The audition is a *beat* — the take changes on a tempo, and the annunciator
reads it for assistive tech. "Read aloud" invites the writer to expect audio. The honest label
is "V = a beat" or "V = in time". Kept for now because it is legible; flagged because it is the
kind of small lie that trains a writer to distrust the larger claims.

### 3.5 The beat is a fixed 1400 ms
Line length does not affect it. A twelve-word take and a two-word take get the same time — which
is precisely the failure mode of timed comparison the architecture warned about. The mitigations
are real (the ledger's delta stays on screen through the reading, and the stack is available for
structure), but a beat proportional to the text, with a floor, is the correct version.

### 3.6 The delta invites a misreading
The ledger prints `+26 −00` — characters added and removed against the passage the take was cut
from. It is arithmetic, it is labelled in the `title`, and it is the honest answer to "how much
of my line does this move". It is also trivially readable as a quality score, and I have no
writer evidence that it is not. This is the item on this list most likely to be wrong in use.

### 3.7 The by-choice mark is durable only for the session
Keeping a line now tells the desk (`/findings/:index/dismiss`) before anything is painted — the
page makes no claim the studio does not hold, and if the call fails the row stays **open** and
says so. But the *reason* ("closed by your decision") lives in `S.resolved`, so after a reload a
by-choice closure reads as an ordinary clean row. Making it durable needs one field on the
dismiss payload (an `intent`) that I have not verified the live route accepts, so I did not
invent it.

### 3.8 The demo's "the fix landed" rule is a heuristic
After an apply, the demo marks as addressed every finding whose located quote sits inside the
frame. A real studio re-runs its passes and knows; the demo infers. It infers only within the
evidence, never from shared vocabulary, and it never retires a flagged finding — but it is an
inference standing in for a server fact, and it belongs on the list of things the demo should
not be trusted for.

### 3.9 I changed tests, and one of those changes deserves scrutiny
- `applyPayload` shape, `stepRing` at 0, `normalizeRewrite` grouping → the contract is now
  known; the old assertions encoded the guess. Legitimate.
- `'First take.'` → `'Your own line.'` → follows from the zero point. Legitimate.
- The cast test's "K restores the original" → now a full round trip. **This one is worth
  watching:** the old version passed by coincidence, so *any* change would have broken it. My
  replacement is stronger, but "the test I rewrote when my change broke it" is exactly where
  self-serving edits hide. The assertion is arithmetic — the line must equal the string it had
  before the ring moved — so it is checkable by anyone reading it.

### 3.10 The repo's own blueprint had drifted from the repo's own code
`INK_LAYER_SPATIAL.md` specified the apply body as
`applyPayload({project, take, frame, candidate, findingId, lineStart})` — the same shape the code
sent, and neither is what the route accepts. A spec that agrees with the implementation and
disagrees with the product is worse than no spec: it makes a wrong contract look deliberate, and
it is how §2.2 survived. The blueprint is now corrected (§3.3 request and response shapes, §3.4
the apply body and the post-apply refresh order), the stale case has its own row in §3.5 because
it takes the **opposite** decision from an ordinary apply failure, Rehearsal and the two inks are
written up as §3.7/§3.8, and the spec's "60 tests" now says what the suite actually runs.

### 3.11 Rehearsal's stack contradicts the blueprint, and I let it
§3.3 is categorical: *"the candidates — a ring, never a list."* The spatial stack renders the
candidates as a list. My defence is that it is a reading, never a picker: the current take is
marked inside the stack, and the only way onto the line remains `J` / `K` / `Enter`. I wrote that
guard into §3.7 so the next person cannot quietly make the stack clickable. But the tension is
real and I am not pretending it away: Rehearsal was adopted as "same sprint" by the verdict, and
the verdict never reconciled its comparison mechanic with this blueprint's most emphatic
structural rule. If a stacked take ever becomes clickable, the ring has been replaced by a menu
and the copy must stop saying "ring".

---

## 4 · What I did not build, and why that is the right call today

### 4.1 Root System (verdict rank 3) — not built
The verdict gates it strictly: edges may come from the `setup_payoff` ledger (`setup_scenes` →
`payoff_scenes`, status `paid/dangling/abandoned/red_herring`), multi-scene findings whose quote
verifies in **both** scenes, name-variants, interaction tracks — and **never** from shared
vocabulary. I searched the repo: `setup_payoff`, `setup_scenes`, `payoff_scenes` and
`red_herring` appear **nowhere** — not in the adapters, not in the demo fixtures, not in the
route map. The only permitted edge source does not exist in any payload this code can see.

Building it now would mean either inventing the ledger client-side (drawing edges the server
never asserted — the exact failure the verdict forbids) or shipping an empty view. So the
honest output is the specification: **first** add `setup_scenes`/`payoff_scenes`/`status` to the
`/findings` payload, **then** a `.find-roots` block in the fold that lists only relationships
whose quote verifies in both scenes, with a walk to the other scene. The repair rule is already
satisfied by construction: one frame, one scene, one apply, one undo — a cross-scene fix is a
sequence of separate edits because the apply contract cannot express anything else.

### 4.2 River lane, altitude 1 — exists, and I only painted it
The Horizon already is this lane: one band per scene at true document proportion, severity pips
flush to the outer edge, a draggable window, keyboard-reachable as a slider, print-excluded.
`detent.css` paints it and adds nothing to it. The one tension the verdict left open —
*compression vs true proportion* — is untouched, and I would keep it that way: the lane's value
is that its geometry means exactly one thing. If it ever compresses, it must stop being readable
as structure.

### 4.3 Rehearsal — built, and this is the part I would test with a writer first
It is a mode of the same strip, chosen by the material, never by a setting: voice rows are
auditioned in time, structural rows are stacked in space with their deltas. The architecture's
constraint — that temporal comparison can hide a subtle deletion — is handled by keeping the
delta visible *during* the reading and by the stack for anything structural. What I cannot know
from here is whether a 1400 ms beat is a helpful cadence or a distracting metronome. That is a
one-line constant and a five-minute writer test.

---

## 5 · The uncomfortable summary

**What this work is:** a faithful port of a finalized UI onto a real substrate, plus the
contract corrections that port made unavoidable. The Detent's laws survive the port — severity
is typography and width, never hue; evidence is a filament that may soften but never dims
prose; nothing is invented; refusals are states with sentences, not toasts. The architecture's
spine, its revision loop, its comparison mode and its scale lane are all present and exercised.

**What it is not:** evidence that the Detent is *right*. Everything I verified is internal
consistency — the page agrees with the desk, the copy agrees with the state, the geometry agrees
with the text, the numbers are arithmetic. None of that is a usability result. The claims that
actually matter are unproven:

1. that a writer prefers a bench that dims to a page that doesn't;
2. that the ledger's delta helps rather than scores;
3. that a beat is a better way to judge a line than reading it;
4. that the whole thing is faster than reading the script and deciding.

Zero-Travel is now measurable — count the keystrokes and the scroll offsets between reading a
diagnosis and the edit appearing in place — and I would want that number from three writers
before calling any of this validated.

**The one thing I would change about how I worked:** I read the CSS seam early and treated it as
the plan, then spent most of the turn discovering that the *contracts* — payload shapes, field
names, the bundle's emission order — were the actual unknown. Two of the five defects in §2
(`/rewrite`, `/edits/apply`) were visible in the server code the user had already pasted, and
the bundle defect was one `node build-single.mjs && open` away. Next time: build the artifact
first, badly, and open it.

---

### Next, in order

1. **Open Root System's door:** get `setup_scenes` / `payoff_scenes` / `status` into `/findings`,
   then a `.find-roots` block that never draws an edge it cannot quote.
2. **Make the by-choice mark durable** (dismiss `intent`), so a decision survives a reload.
3. **Beat proportional to the take**, with a floor, plus a writer test at three speeds.
4. **Lift the four placements** in §3.1 into `ink-layer.css` if the seam cost is judged too high.
5. **Decide the shipped ground** (§3.3) — instrument by continuity, lifted by the round.

---

## 6 · The alignment pass — the verdict checked against the build, and what broke

**Asked:** take the uploaded Ashna verdict (the challenge table, the required corrections, the
quality gates), check the repo's UX against it, implement what did not match; confirm the UI is
the finalized Detent; then verify, test, commit, and write this up with the open questions in a
file. `§1–§5 above describe the PREVIOUS round`; where this pass superseded a claim in them, the
supersession is named here. The open questions live in `OPEN_QUESTIONS.md`.

### 6.1 What the verdict demanded, and where the repo already matched

| Verdict / contract requirement | State before this pass | Action |
|---|---|---|
| Ink Layer primary; **Rehearsal an optional comparison interaction** | already built as a mode of the strip | kept; the stack's conflict with "a ring, never a list" is now stated (blueprint §3.3, §3.7) |
| **Defer Root System and Story River** | deferred | kept deferred, and the door (the fields needed) is written down (`OPEN_QUESTIONS.md` §9) |
| Metric: **low reorientation cost, deliberate acceptance** — not minimum movement | the docs already retired Zero-Travel as a UI metric | kept; no movement counter exists anywhere |
| **Separate finding identity from text location** | partially: anchoring was exact-match with a scene fallback | `fuzzyScore` + `anchorFinding` at the contract's 0.72, with `exact`/`loose`/`ambiguous` and no silent guesses |
| **Unknown response shapes must fail clearly** | `normalizeRewrite` was tolerant only | it now reports `{unknown, reason}` and casts nothing |
| **Explicit passage selection for unverifiable evidence** | automatic targeting was already refused | kept (`R` on the writer's own selection), and the selection is recorded as the basis |
| **Offer scene/category/status selection in context** | absent | `F` cycles `all → scene → category → status(open)`; the walk follows it |
| **Keep the fold in-flow and the writer in the passage** | built | kept; the strip's geometry now lives in the structural sheet where the flow is defined |
| **Contract: `line_start` is unstable; J/K must never mutate the DOM** | **violated** — J/K wrote the candidate into the live line | the **trap frame**: the ring moves, the strip renders, nothing is written until the commit |
| Severity is typography, never hue alone | the fold had ▪-block rules | the rules existed but were **dead** (see 6.2) |

### 6.2 Defects this pass found — each one was real, and four were invisible to the tests

1. **The desk's severity word produced no mark at all.** `inkChannels` and `decorate()` stored the
   finding's own spelling, so a finding the desk called `high` landed as `data-worst="high"`, which
   no stylesheet matches: the row's severity border fell to **0 px** — a critique present in the
   data and invisible on the page. The fold's ▪ blocks were dead for the same reason: the rules
   existed in `detent.css` and nothing ever set `data-severity`. Fixed by canonicalising at both
   write sites, stating the collapse in the fold's signature line (`high → critical`), and adding a
   test that asserts **the widths** (6 / 3 / 1 px) and that no desk word reaches the DOM unaliased.
2. **The strip's stylesheet did not exist.** The renderer had been rewritten (ledger, take list,
   editor) while `ink-layer.css` §C and `detent.css` §D6 still described the old markup. In a real
   browser the take list rendered as a **browser-numbered list** (`1. 2. 3.`) in a three-column grid
   whose columns could not hold their content — every take wrapped every three words. Nothing in
   the jsdom suite could see it. Fixed by writing the strip's real geometry into §C and correcting
   the sheet-boundary note in §D6 (the structural sheet's header forbids *colour*, not structure —
   the earlier note had misread it); the rendering was re-checked in Playwright.
3. **The editor branch was dead code.** `renderTakeList` tested `C.editingProposal` (the core
   namespace) instead of `S.editingProposal` (the page state), so `E` announced the editor and
   rendered the diff instead. Fixed; the tests now assert the editable box, its content, and its
   return state.
4. **The way back from a roam was unreachable.** `roamToggle` asked the row it had *landed* on to
   justify the return, and a landing place is by definition a place with nothing on it. Fixed by
   checking the return first — and by routing `O` while a return is outstanding, not only when a
   fold happens to be open.
5. **The ambiguity warning could be overwritten.** The cast announced "N candidates came back… the
   quote matches more than one line", and the first `J` (which casts take 1) immediately announced
   the take — last-write-wins, so the warning the contract requires was never heard. Fixed by
   composing the warning into the opening sentence *and* letting it ride with the first step.
6. **A committed take left its own diff on the page.** The strip stayed in the DOM after the commit
   — a picture of the past pretending to be the present, and a live-looking editor for a frame the
   line no longer held. The frame is now spent with the commit.
7. **The strip contradicted itself while the writer was typing** ("ENTER = commit take" under an
   open editor) and kept the take's filament underline under the editable passage — two marks
   claiming the same thing at the moment the writer is most likely to act on reflex. The strip now
   carries `data-editing`, the keys line is the editor's own, and the underline yields to the
   editing rule.
8. **The demo's own summary was hard-coded** and disagreed with its findings. It is now quoted from
   the desk (counted in the desk's own words), which is the point of the alias.
9. **The offline build logged a console error it could do nothing about** (`fetch file:///api/health`).
   The probe is skipped offline; the state it announces is the same one.
10. **The strip printed the manuscript's indentation inside its own column**, so the ORIG row and
    the takes did not share a left edge. Normalised to the passage.

### 6.3 The seven failing tests were mostly wrong — and two of them were evidence

The previous round left `tests/dom.test.mjs` at 24/31, and I spent most of this pass assuming the
tests were stale. That was right for five of the seven (they asserted the old announcements and the
removed "audition writes into the live line" behaviour), and **wrong for two**: the roam-return
failure and the ambiguity failure were not test drift at all — they were defects 4 and 5 above,
found only because a test insisted. The lesson I would carry: when a test fails after a deliberate
behaviour change, decide *which* premise moved before rewriting the assertion. Five of the seven
were premises; two were bugs, and they looked identical from the outside.

One open question I decided rather than deferred: **the strip's order**. §3.3 of the blueprint said
"a ring, never a list", which the take list flatly contradicts. I kept the list, kept it
non-interactive, and wrote the supersession into the blueprint rather than quietly leaving a doc
that lies. The reasoning is in `OPEN_QUESTIONS.md` §2 for anyone who wants to overrule it.

### 6.4 What this pass did NOT prove

* **No writer has touched any of it.** Every claim in this file is internal consistency plus two
  browser passes. The ambiguous-quote policy (§3), the two-`Escape` semantics (§4) and the walk
  asymmetry (§6) are all shaping decisions that only a writer can settle.
* **The 0.72 gate's yield on a real screenplay is unmeasured** — the two demo data points are in
  `OPEN_QUESTIONS.md` §10, one of which falls below the gate while a human would call it obvious.
* **The demo is now a slightly harder world than a real desk**: it deliberately carries two
  severity vocabularies and a two-scene finding to keep the alias and the roam exercised. The
  fixture is the test, not the product.
