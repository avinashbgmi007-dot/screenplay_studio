# THE INK LAYER — SPATIAL BLUEPRINT
### Architecture I · Screenplay Studio · framework-free (Vanilla JS / HTML / CSS)
Structural specification only. **No colour, no theme, no cosmetics, no visual styling decisions** — none of the three mechanisms depends on a paint channel.

Runnable prototype in this folder. `npm i jsdom && node --test tests/` → **103 tests, all green**
(60 pure-logic, plus a DOM suite that boots the layer and drives it with real keyboard events).
Checked a second time in a real engine: `/tmp`-side Playwright renders of the offline build
confirm the geometry the jsdom suite can only assert by stylesheet (border widths 6/3/1 px by
severity, the strip's column order, the refusal state).
The colour pass lives in `detent.css` and is not covered here: no mechanism depends on it.

| File | Role |
|---|---|
| `core.js` | DOM-free primitives: geometry, state machines, string math, keymap. **The only place logic lives.** |
| `ink-layer.css` | Structure only: one scroller, the 12px track, the fold's two grid tracks, print exclusions. |
| `detent.css` | The colour pass over the above (the sheet's own header asks for it). Paints; does not restructure. |
| `ink-layer.js` | The DOM layer: renders, listens, executes what `core.js` returns. |
| `index.html` | The shell: three ids and one annunciator. Nothing else exists. |
| `build-single.mjs` | Emits `ink-layer-preview.html` (one offline file, for viewing without a server). |
| `tests/` | `core.test.mjs` (no deps) · `dom.test.mjs` (jsdom) |

---

## §0 · THE THREE INVARIANTS

Everything below follows from these. Break one and the architecture stops being this architecture.

| # | Invariant | Enforced by |
|---|---|---|
| **I1** | **One scroller.** The document scrolls; nothing inside it does. The manuscript has no `overflow` of its own, so there is exactly one scroll position in the system. | `.surface` sets no overflow; `.manuscript` never does; the Horizon is `position: fixed` (out of flow) |
| **I2** | **One keyboard owner.** A single `window` keydown listener; every decision returns an action id from a pure table. | `routeKey()` in `core.js`; the `switch` in `ink-layer.js` is the only executor |
| **I3** | **Critique never occupies space of its own.** The only non-manuscript element with layout presence is the fold — and a fold is *inside* a rowgroup, in the same column, in the same flow. | rowgroup `grid-template-rows: auto 0fr` |

The honest consequence of I3: **there is no findings list, and there cannot be one.** The critique exists in exactly one of two states — worn by a line (wet) or grown out of a line (fold).

---

## §1 · THE SINGLE SURFACE & HORIZON RADAR

### 1.1 DOM layout tree

```
body
└── main.surface                    ← THE scroller (page). padding-right reserves
    │                                  --horizon-w + half a pad, so no glyph can
    │                                  ever be occluded by the track
    └── article.manuscript          ← width: min(100%, 72ch); margin-inline: auto
        │                              → dead centre, and centring is flex/margin-based
        │                                so it cannot collapse when the track is busy
        ├── section.scene[data-scene="14"]
        │   └── div.rowgroup[data-index][data-type][data-fold][data-ink][data-worst][data-flagged]
        │       ├── div.row[data-type]          ← ONE text node: the manuscript text
        │       │                                  (leading whitespace included)
        │       └── div.fold                     ← grid track 2; 0fr when closed
        │           └── div.fold-pad
        │               ├── ol.finds             ← authored lazily, first open only
        │               │   └── li.find[data-verified][data-provenance]
        │               │       ├── p.find-issue
        │               │       ├── p.find-evidence
        │               │       └── span.find-sig
        │               ├── p.find-overflow      ← "N more on this line" (no link: there is nowhere to go)
        │               └── div.casting          ← only while casting (§3)
        │
        └── section.scene[data-scene="15"] …

div.horizon[role=slider][tabindex=0]      ← position: FIXED, width: 12px, inset-inline-end: 0
└── svg.hz-track                          ← the coordinate system: 0..trackH maps 0..scrollHeight
    ├── g#hzBands  → rect.hz-band[data-scene] per scene   (y/height in % of the track)
    ├── g#hzInk    → rect.hz-ink[data-scene][data-severity][data-flagged]  (width = severity, 0/4/8/12px)
    └── rect#hzWindow.hz-window             ← the viewport's true extent

p.annunciator[role=status][aria-live=polite]   ← 1px, clipped; `a` reveals it.
                                                 The ONLY text outside the manuscript.
```

**What is not there:** no `aside`, no `nav`, no `dialog`, no `[role=tablist]`, no element whose job is to hold critique. Asserted in the test suite.

### 1.2 Why the track is `fixed`, not `absolute`

An absolutely positioned element resolves against the **initial containing block**, which is viewport-height — so `inset-block: 0` would give a 12px track covering only the first screenful while claiming to be a true-proportion silhouette of a 96-page document. `position: fixed` gives a viewport-tall track, and the *whole document* is then mapped into it. That is also exactly how a scrollbar behaves, which is the mental model: **the Horizon is the semantic scrollbar.**

It takes **zero flow space**, so no window size, zoom level or fold state can ever squeeze the manuscript because of its own radar.

### 1.3 The coordinate systems

Three spaces, two conversions. All three functions live in `core.js` and are unit-tested; the DOM layer only measures and paints.

```
 CONTENT space                     TRACK space
 (document px)                     (0 .. trackH px)
 ┌ 0 ─ front matter ─────────┐     ┌ 0
 │  title, warnings          │     │  ← head void: honest empty band
 ├ scene 14  top: 4210 h:520 ┤     ├ y = 4210/H*trackH     h = 520/H*trackH
 ├ scene 15  top: 4730 h:130 ┤     ├ contiguous, ≥1px
 └ … documentElement.scrollHeight = H ────┴ trackH = horizon.clientHeight
```

| Function | Contract |
|---|---|
| `sceneBands(boxes, domain, trackHeight, {minBandPx})` | Integer-accumulated bands. Guarantees: **the bands tile the track exactly** (Σh = trackH, no gaps/overlaps), tops are monotonic, every band is ≥ 1px (a one-line scene stays clickable), and the last band closes the track. Returns `topPct/hPct` so the DOM never does arithmetic. |
| `windowRect(scrollTop, clientHeight, scrollHeight, trackHeight)` | The viewport's true extent, with an **8px floor** so the window stays grabbable inside a 4,000-line document. |
| `scrubTo(trackY, clientHeight, scrollHeight, trackHeight, {center})` | The inverse of `windowRect`. Every scrub and jump routes through it, so there is exactly one way to move the page. |

**Severity is encoded in the pip's WIDTH, not its colour** (`inkPx`: 0 / 4 / 8 / 12 — critical fills the whole track). Verification is a stroke style (flagged pips are outlined, not filled). This is why severity can never be colour-only: the channel was never colour to begin with.

### 1.4 Data: one call for the whole silhouette

```
GET /api/projects/<name>/findings/summary
  → normalizeSummary()  → { dawnPct, open, addressed, dismissed, flagged, bySeverity, byScene }
```

`normalizeSummary` **never invents a number** — an absent field is `null`, not `0`. `byScene` is a **capability flag detected at boot**: if the summary carries per-scene buckets, the whole track is painted from one call; if not, the radar degrades to per-scene queries (`GET /findings?scene=`) when a band is needed. The fallback is decided at boot, never assumed mid-interaction.

`reconcileInk(channels, summary)` diffs the client's buckets against the server's and reports `delta = SERVER − CLIENT`. Positive means the cache is stale (the client hasn't seen the newest findings). **The server is authority**; drift is announced rather than silently smoothed over.

### 1.5 Event flow — the radar

```
scroll (passive)  → rAF → horizon.paintWindow()      // one rect attribute update
resize (passive)  → horizon.measure() + paint()      // bands rebuilt only on resize
fold opens/closes → scheduleMeasure() (debounce FOLD_MS+120)   // silhouette follows the page
fonts.ready       → measure() + paint()              // never measure against a fallback face
pointerdown on track → setPointerCapture → scrubTo(clientY) → window.scrollTo
pointermove (dragging) → scrubTo()                   // measure() is suppressed while dragging
pointerup → release
```

`measure()` reads layout once per geometry change (one `getBoundingClientRect` per scene) and hands the results to `sceneBands`. `paint()` writes attributes only — it never measures. That split is what keeps a scrubbing finger at 60fps on a 96-page document.

Keymap while the track has focus: `↑/↓` step bands one scene at a time, `Home/End` jump to the extremes, `Enter` scrolls to that scene, `Esc` releases focus back to the manuscript. Each step announces `"Page 22, 3 open, worst critical."` — the radar is a *reading* surface, not a decorative one.

---

## §2 · THE DWELL-DEPTH ACCORDION FOLD

### 2.1 The push, not the overlap — how it is guaranteed

```
div.rowgroup                      display: grid;
│                                 grid-template-rows: auto 0fr;      ← TWO tracks
│                                 transition: grid-template-rows 260ms
├── div.row                       track 1: auto   — the line itself
└── div.fold                      track 2: 0fr    — the critique
    min-height: 0;  overflow: hidden               ← required, or 0fr cannot reach 0
    margin-inline-start: var(--indent)             ← the SAME map that indents the text
```

Because the fold is a **grid track of the row it belongs to**, not an overlay:

* it can never occlude a line — the lines below it are *displaced*, not covered;
* the scene's shape stays readable while the fold is open (lines above and below remain visible);
* the row's own `scroll-margin-block` is irrelevant — nothing needs to be brought into view, because nothing was summoned;
* growing the fold *below* the focused line moves nothing above it, so the writer's eye does not move.

`--indent` is written from `C.indentOf(type)` — **the same number that composes the row's leading whitespace**. Text column and fold column are the same number by construction, not by eye. (Tested: for every element type, text indent === fold indent.)

Opening is a **state transition**, so it is reversible and interruptible: an interrupted open settles through `closing`, and repeated dwells never stack duplicate fold content (asserted).

### 2.2 State machine

`data-fold` on the rowgroup. `pinned` is **orthogonal** — it is a fold the writer claimed with `Enter`/click, which therefore stops responding to the pointer.

| State | Cause | Meaning | Legal next |
|---|---|---|---|
| `closed` | default | critique exists only as wetness on the line | `arm`, `open` (key/click) |
| `armed` | `pointerover` on a wet line | the 420 ms clock is running | `fire` (timer) · `cancel` (any interrupt) |
| `open` | timer fired | the critique is exposed; **pointer-out closes it** | `close`, `pinned` |
| `closing` | collapse begun | transition running; scroll correction applied | `closed` (on `transitionend`, with a timeout backstop) |
| `pinned` | `Enter` / click | stays open until dismissed; survives walking away | `close` |

`foldNext(state, event)` is the whole table. Notably: **`fire` cannot open an unarmed fold** (a stale timer can never bloom a fold the writer has left) and re-arming an open fold is inert.

### 2.3 The 420 ms dwell — event flow

```
pointerover .rowgroup (wet only)
    └── clearTimeout(prev); dwellTimer = setTimeout(fire, 420)

ANY of these cancel the armed window:
    • pointerout to a node OUTSIDE this rowgroup   (moving line → its own fold does NOT cancel)
    • any scroll, anywhere (a moving page means the writer is reading past it)
    • pointerdown
    • focus moving to another row

fire (420 ms elapsed)
    ├── focusRow(i)  → data-focus, role/aria updated, reveal ONLY if outside the 18–82% band
    ├── buildFold(i) → author ol.finds LAZILY (first open only; findings sorted severity-first,
    │                  capped at MAX_FINDS_PER_FOLD = 6, remainder as one "N more" line — the
    │                  fold's maximum height is therefore bounded and known)
    ├── setFold(i, 'open')  → aria-expanded="true"
    └── rAF → measure the fold → overflowCorrection() → scrollBy ONLY the overflow
```

**Never `scrollIntoView`.** It moves the line the writer is reading. Two corrections exist instead, both pure and tested:

| `overflowCorrection` | Applied when the fold opens and its bottom exceeds the viewport — scrolls by the overflow only, so the line's own position is preserved. |
| `scrollCorrection` | Applied when a fold **above the focused line** collapses: the page would jump down by the collapsed height, so the scroll is nudged back by exactly that height. Collapse below the line needs no correction (returns 0). |

### 2.4 The two walks (why arrow keys and `n`/`p` both exist)

| Key | Walk | Lands on |
|---|---|---|
| `↑` `↓` | **the document walk** | every line, wet or dry — this is how a writer reads, and dry lines are most of a script |
| `n` `p` | **the working walk** | wet lines only, via `nearestWet(rows, from, dir)` |

`nearestWet` **steps off the current row first**, so pressing `n` on a wet line advances to the *next* wet line instead of re-firing the one you are on. At the extreme it returns `-1` and the app says `"No further wet lines below."` — an end, not a wrap.

A walk leaves exactly one fold open: the one you stopped on. Folds never accumulate down the page (asserted).

---

## §3 · THE INLINE TAKE-CASTING CONTROL

### 3.1 DOM tree while casting

```
div.rowgroup[data-index=2][data-fold=pinned][data-cast=active][data-delta="false"]
├── div.row[data-type=dialogue]          ← ONE text node, and it holds the WRITER'S text
│   └── "              You're late."            ← unchanged by every audition
└── div.fold
    ├── ol.finds                                 ← the finding, still there
    │   └── li.find[data-severity=critical][data-provenance=attributed] …
    └── div.casting[data-editing="false"]        ← the control, inside the fold
        ├── p.cast-ledger     "TAKE 01 / 03 ● ○ ○ +26 −00"
        ├── ol.cast-takes
        │   ├── li.take[data-original="true"]      b.tk-n "ORIG" · span.tk-text · em.tk-delta "+00 −00"
        │   ├── li.take[data-current="true"]       b.tk-n "01"  · span.tk-text (del/ins diff) · em.tk-delta
        │   └── li.take                            b.tk-n "02"  · span.tk-text · em.tk-delta
        ├── p.cast-scope      "scope: this passage"
        ├── p.cast-meta       the desk's own note, its basis, and any warning
        ├── p.cast-overlap    when two proposals touch the same words
        ├── p.cast-void       a refusal, kept until it is answered
        └── p.cast-keys       the keys that are live in THIS state
```

There is no overlay, no popover, no comparison panel, no checkbox grid. **The line is the
subject and the fold is the desk.** `data-cast` on the rowgroup drives its state:
`idle → busy → active → editing → applied`, plus the two terminal states `stale` (the guard
refused) and `idle` again after a cancel.

### 3.2 The frame model — why J→K→J cannot accumulate text

The only source of truth for a cast is a **frame captured once**:

```js
frameOf(text, target) → { prefix, target, suffix, original, ambiguous }   // null if absent
composeLine(frame, candidateText) → prefix + candidateText + suffix       // pure
restoreLine(frame)                → frame.original                        // byte-exact, by construction
```

```
VERA                     ┌ prefix ─┬─ target ─┬ suffix ┐
It wasn't.      ────────► "VERA\n" │"It wasn't."│  ""  │
                                 └────────┴──────────┴─────┘
composeLine(frame, "The door was open.")     → "VERA\nThe door was open."
composeLine(frame, "I heard you on the stairs.") → "VERA\nI heard you on the stairs."
composeLine(frame, "It wasn't.")             → "VERA\nIt wasn't."     ← byte-exact original
```

**The rule that makes this safe: never re-frame a line you have already composed.** Re-framing
against mutated text returns `null` (`frameOf(mutated, oldTarget) → null`), and any sloppy
fallback would double the line. The frame is captured once per line per cast session; every
reading composes from the original. Tested explicitly, including the three-step round trip.

**And the rule that makes it a trap frame: composition never reaches the document during an
audition.** `J`/`K` move a ring; the composed string is *rendered in the strip*, not written to
the row. The single write is the commit (§3.4). Contracts, §3.2: traversing candidates "must
never mutate the active DOM document".

Target precedence, in order: the take's own `old_text` → the verified `evidence` quote → **the
whole line**. (An unlocalisable critique therefore rewrites the whole line — which is exactly what
the fold's read-only diff then shows.)

### 3.3 The ledger and the take list — the ring, printed

`stepRing(i, len, delta)` **clamps by default**; wrap is opt-in and never used here. The ring
spans `len + 1` places, because position `-1` is not "nothing selected": it is **the writer's own
line**, the zero point the first take is reached from and returned to. At the ends the app says
`"Last take."` / `"Your own line."` rather than silently cycling.

The ring is not a hidden cursor: it is printed, as text, in two places.

```
p.cast-ledger   "TAKE 02 / 03"   ·   "● ○ ○"   ·   "+29 −00"
                                 position marks      arithmetic on the take
ol.cast-takes   ORIG          You're late.                        +00 −00
                01            You're late. The stairs gave you…  +26 −00
                02            I heard you on the stairs…         +33 −00
```

* **The ledger** is the readout: where this take sits, which takes exist, what this one does to
  the passage. The delta is the arithmetic of added and removed **characters** — a measurement,
  never a score — and it is tabular so it cannot jitter as the ring steps. A writer who prints
  the page still gets every fact. There is **no per-line finding count anywhere**, here or in the
  fold: a count on the sentence is the metric the agreement rejected.
* **The take list** is the reading: every take on its own line, the current one carrying its
  `del`/`ins` word diff, each with its size. It is **not interactive** — there is no click target,
  no hover, no list selection. `J`/`K`/`Enter` remain the only way onto the line, and the list is
  a rendering of the ring, never a second control. This deliberately **supersedes** the earlier
  version of this section, which said "a ring, never a list": a list that cannot be clicked is a
  reading of the ring, and hiding the comparisons is the thing the agreement actually forbade.
* The order of the strip is the order of the argument: **ledger → takes → scope → reason → keys**.
  Reasoning is never in front of the proposal; the ledger is an instrument head, not a rationale.

### 3.4 Event flow — the cast

```
Enter on a wet line          → fold.toggle → data-fold="pinned"
J (inside an OPEN fold)      → cast.begin.next
      └── routeKey: j is INERT on a bare page; alive only inside an open fold.
          Casting is never summoned — it grows out of the line that is already talking.
      └── startCast(i): POST /rewrite → normalizeRewrite → takeForRow → frameOf
          ├── unknown response shape? → nothing is cast; the strip says so (§3.5)
          ├── no candidates? → refuse, and say why (§3.6)
          ├── frame null?    → refuse ("candidates do not line up with the text")
          └── ok → data-cast="active", data-delta="false", strip authored into the fold,
                   ring set to take 1 (one keystroke from the critique to a proposal)

J / K (or → / ←)             → cast.next / cast.prev → stepRing → THE RING MOVES, NOTHING ELSE
      └── renderCastStrip(): the ledger's position and marks, the current take's diff, the keys.
          row.firstChild.nodeValue is NOT touched. data-delta stays "false": the line is holding
          no change and saying so. What Escape has to restore therefore does not exist.
          (This is the trap frame. The audition is a reading.)

E                            → proposal.edit → the current take's target becomes contenteditable
      └── the frame's prefix and suffix stay visible, read-only: the writer edits THE PASSAGE,
          and whatever they type lands in the hole the original left (editProposal), so a typed
          proposal can never accumulate a previous proposal.
      └── strip[data-editing="true"], row[data-cast="editing"], and the keys line changes to the
          editor's keys. Enter = commit the wording · Escape = abandon the edit (the take reverts
          to the desk's wording; the proposal stays open).

Enter                        → cast.apply → canApply()? → POST /edits/apply
                               body = applyPayload({ sceneNumber, take, frame, candidate })
                                    = { scene_number, replacements:[{ old, new }] }
                                      `old` is the frame's captured target — the exact bytes the
                                      take was cut from — which is what makes the route's
                                      verbatim guard meaningful.
                               → THE ONLY WRITE. The row's text node is replaced with what the
                                 strip showed, data-cast="applied", data-delta="true".
                               → the frame is spent: the strip is removed, because a diff drawn
                                 against a line that no longer holds that text is a picture of
                                 the past pretending to be the present.
                               → findings_status in the apply response patches the page
                                 (statusPatch); when the response carries none, GET /findings is
                                 asked instead → decorate() → radar repaint → GET /findings/summary
                                 → scheduleMeasure() (the text changed height).
                               → S.fixedOn.set(finding_id, row): an answered finding whose quote
                                 the fix overwrote is remembered as answered WHERE IT LANDED.

Escape                       → cast.cancel → the ring is dropped, nothing is restored because
                               nothing was ever changed; a line kept this way is dismissed on
                               the desk and goes dry by CHOICE (§3.8). The fold STAYS pinned:
                               abandoning a cast is not the same as folding the critique away.

↑ / ↓ / PageUp / PageDown    → cast.abandon → walk; no half-cast row is left behind.
⌘Z / Ctrl+Z (outside a caret) → POST /edits/undo → text restored → the finding re-opens → it re-wets
      └── while the proposal editor is open, Mod+Z belongs to the caret: routeKey checks the
          editor BEFORE the `editing` guard and passes every other key through. Nobody else's
          field, but the app's own.
```

### 3.5 Failure semantics — fail loudly, lose nothing

| Failure | Behaviour |
|---|---|
| Rewrite request fails | `data-cast="idle"`, announced with the server's own message. Nothing is written to the page. |
| Rewrite returns an **unrecognised shape** | `normalizeRewrite` reports `{unknown: true, reason}`; nothing is cast, and the strip says which fields it did not find. Guessing the structure of a reply is how a valid replacement ends up attached to the wrong text. |
| Rewrite returns nothing usable | Names the reason: `"No candidates came back for this line."` or the first `skipped` reason. |
| Frame cannot be found | `"Candidates do not line up with the text on the page. Nothing cast."` — refuses rather than guessing. |
| The quote matches two places | Castable, **with the ambiguity retained**: the strip carries `this quote matches more than one line`, the annunciator says it with the take it belongs to, and the take is never silently attached. |
| Two proposals touch overlapping text | Both are listed, `cast-overlap` states the dependency: each is applied on its own and re-checked, so applying one cannot silently carry another. |
| Apply fails (transport, 404, a dead studio) | Nothing was ever on the line, so nothing comes off it; the proposal stays open (`data-cast="active"`), announced with the reason, `Enter` can be pressed again. |
| Apply refused as **stale** (400, `stale: true`) | The strongest refusal, and a *state*: `data-cast="stale"`, the refusal printed in the fold and kept there until it is answered. Because the trap frame never writes, the writer's text is still on the page byte for byte — there is nothing to restore and nothing to apologise for, and the frame is re-cut against the live text before the next ask. `classifyApplyError` decides from `body.stale`, never by matching the sentence. |
| An edit that would delete the line | Refused with its reason ("the apply route takes a replacement, not a deletion"); the take keeps the desk's wording. |
| Apply returns partial | `applyReport`: `"Applied 2. 1 skipped."` |

### 3.6 The honesty path (the substrate's flag-don't-drop rule, expressed spatially)

An unverifiable finding still attaches to the scene's first line and still opens a fold — drawn
with a **dashed** rule, its evidence quoted with an explicit `(unverified — could not be matched
to the text)`. But when the writer presses `J`:

> `"Unverified finding: its quote could not be matched to the text, so there is nothing here to cast. It is still shown, not dropped."`

No candidate is invented for a claim the verifier could not land, and **no target is selected on
the writer's behalf**. Explicit selection is honoured: `R` on the passage the writer has chosen
casts it anyway, and the warning is retained in the strip's basis line (`writer-selected
passage`), because refusing assistance outright would block legitimate work on uncertain
diagnoses.

### 3.7 Rehearsal — the comparison mechanic, as a branch of this strip

`V` in an open fold. One branch, no second surface, and the mechanic is chosen by the
**material**, never by a setting:

| Row type | Mechanic | Why |
|---|---|---|
| `dialogue`, `character`, `parenthetical` | **temporal** — the ring moves on a beat (`REHEARSAL_BEAT_MS`, 1400 ms), opening on the writer's own line | the question is rhythm, and rhythm can only be judged in time |
| everything else | **spatial** — the takes stay as the stack of §3.3, each with its size, and `V` says why there is no beat | the question is magnitude, and a deletion that only passes on the beat is a deletion nobody noticed |

Rules that make it a mode rather than a toy: the beat moves the **same ring** `J`/`K` move, so
nothing new can reach the page; the reading **ends** rather than looping, and the end is announced
(`rehearsalStep` returns a sentinel, because "finished" and "never started" are different states);
**any key, and any pointer contact, stops it** — a reading that survives an unrelated keystroke is
a reading that keeps moving while the writer is doing something else; and it is *not* disabled
under reduced motion, because it is a reading pace, not an animation (only the strip's colour
steps collapse).

On a structural row the stack does not move at all when `V` is pressed: the sizes are already on
the page, so the writer's place is kept and only the explanation arrives.

### 3.8 Two inks: dry by evidence, dry by choice

A line that stops being wet does not stop saying why. `decorate()` is the single writer of ink
state, and it decides the reason in the same place:

| State | Means | Painted |
|---|---|---|
| `data-ink="wet"` | open findings on this line | rule in wet amber; width is severity |
| `data-ink="dry" data-dry="evidence"` | the desk closed the finding because the fix landed | change-star and rule in `--wet` |
| `data-ink="dry" data-dry="choice"` | the writer looked at the take, kept their own line, **and the desk recorded the decision** (`/findings/:index/dismiss`) | the same marks in brass |
| `data-ink="none"` | nothing on this line | nothing |

Keeping a line is a decision, not a non-event: the dismiss call goes to the desk *before*
anything is painted, and if it fails the row stays **open** and the failure is announced — the
page makes no claim the studio does not hold. Evidence outranks choice on a row where both
happened, because it is the stronger claim.

### 3.9 Identity is not location — the 0.72 gate

The contract is explicit: `line_start` is not stable. Every placement therefore goes through one
function, and nothing else may place a finding:

```js
ANCHOR_THRESHOLD = 0.72
fuzzyScore(quote, text)            // containment → 1, else Sørensen–Dice over character bigrams
anchorFinding(rows, finding, {threshold, tie: 0.04})
  → { rowIndex, score, exact, ambiguous, loose }
```

* A quote **contained** in a row is an exact anchor.
* A quote **rewritten** within the threshold still lands — that is the whole point of measuring
  instead of matching.
* A quote below the gate is **loose**: it is never pointed at a line it cannot prove it belongs
  to. An OPEN finding keeps the scene anchor it always had (shown, flagged, casting refused); an
  answered or dismissed finding uses `S.fixedOn` (where the fix landed) and otherwise **parks** —
  counted on the desk, claimed by no line.
* Two rows scoring within `tie` = **ambiguous**. `line_start` may break the tie, and the app says
  that it did.

The consequence for the writer: a finding is where its evidence is, and a line number is a hint,
never an address.

### 3.10 The three contextual controls

Each is one key, each is scoped to what is in front of the writer, and none of them opens a
surface:

| Key | Control | Rule it follows |
|---|---|---|
| `F` | **Context filter** — cycles `all → scene → category → status(open)` | it filters the CRITIQUE, never the prose: `quietRow` recedes a row's critique through the same opacity channel the ink threshold uses, and not one character of the manuscript moves. The scope is stated in the annunciator, and it is always about where the caret is. |
| `O` | **Visit the other scene a finding cites**, and come back | the cheap "where else does this matter?" — no graph, no edge the payload does not assert. The return is checked FIRST, because the place a visit lands is by definition a place with nothing on it. |
| `E` | **Edit the proposed wording in place** | the writer's words are the proposal (§3.4); the manuscript is untouched until `Enter` commits the take. |

---

## §4 · EVENT FLOW LOGIC — the whole input contract

One listener. One pure decision table. The DOM layer executes and never decides.

```
window.keydown ──► routeKey(ev, ctx) ──► action id ──► switch (the ONLY executor)
                        ▲
   ctx = { editing, editingProposal, casting, roaming, foldOpen, onHorizon }
```

**Precedence, highest first** — this order is the entire interaction model:

| Rank | Context | Effect |
|---|---|---|
| 0 | **`editingProposal`** (the writer is typing a proposal inside the strip) | The strip's own editor: `Enter` commits the wording, `Escape` abandons the edit, and **every other key passes through**, Mod chords included. Checked before the caret guard below, because this editor is the app's own field. |
| 0·5 | **`editing`** (caret in any other contenteditable/input) | **The caret is absolute.** Every key passes through, including `⌘Z`: while a caret exists, undo belongs to the words being typed, not to the app's edit stack. The app's undo only answers once the line is committed. |
| 1 | `Mod` chords | `⌘Z` → `edits.undo`, `⇧⌘Z` → `edits.redo` — survive every non-editing state |
| 2 | `Escape` | Peels exactly one layer: `cast.cancel` → `fold.close` → `focus.release` → `fold.closeAll` |
| 3 | `casting` | `j/k/→/←` own the ring (and only the ring — no write), `E` edits the take's wording, `V` rehearses, `Enter` commits, a traversal key abandons |
| 4 | `onHorizon` | The track behaves like a scrollbar (`↑↓ Home End Enter Esc`) |
| 5 | traversal | `↑↓` rows · `n/p` wet rows · `Enter` fold · `[ ]` ink floor · `a` annunciator · `g` ground · `v` rehearsal · `f` context filter · `o` visit-and-return |

Every action id the router can emit is enumerated in `HANDLED`, and a test proves the router never emits an id outside it — so the `switch` cannot accumulate dead arms or silently swallow a key.

**Pointer arbitration** (the only non-keyboard input):
`pointerover` on a wet rowgroup arms the dwell · `pointerout` to *outside the rowgroup* cancels it · `click` pins/unpins · `pointerdown` on the track scrubs. Nothing else in the document is clickable except the fold's own cast strip.

**Announcement** is not an afterthought: `say.*` builds every message and the annunciator is `role="status" aria-live="polite"`. Every state change — folding, take 2 of 3, applied, refused, threshold, scene reading — is announced in the same frame as the action. With the screen off, the architecture is fully operable.

---

## §5 · STRUCTURAL LAYOUT STRATEGIES (the seven rules)

1. **The manuscript owns the viewport.** One scroller, one column, one measure (`min(100%, 72ch)`), centred by margin — never by a layout that a sibling could steal space from.
2. **The radar is out of flow.** `position: fixed`, 12px, `z-index` above the text, and the *text* reserves the gutter with padding. The manuscript never reflows because the radar exists.
3. **The fold is in flow.** A critique that overlays is a critique that hides the sentence it is about. It gets a grid track, so opening it pushes.
4. **Width is severity, stroke is verification, rule-id is provenance.** Three non-colour channels, all structural, all available in the 12px track and on the row's left rule.
5. **Ghost, never hide.** The ink threshold recedes lines (`opacity`) and never removes them from the reading order; flagged findings are never dropped; the fold's remainder is a sentence, not a link.
6. **One text node per line, and it is written once per commit.** The manuscript's DOM text is the manuscript's text — an audition cannot reach it (the trap frame), the commit replaces it with exactly what the strip showed, undo restores it byte for byte, and export honesty is unaffected. It is also the reason `Escape` needs no restoration path at all: there is nothing to restore.
7. **The annunciator is the only text outside the script.** No HUD, no counters, no badges, no toolbar. Progress is the paper's own dryness and, when asked, one sentence.

**The screen-only line.** `@media print` collapses every fold, removes the radar and the annunciator, strips the ink rules and the change-stars, and restores `opacity: 1` on ghosted lines. Wetness must never reach the working copy — the ink layer is a rendering, and renderings do not print. (There is a test asserting these rules exist.)

---

## §6 · WHAT IS DELIBERATELY ABSENT

* **Colour, theme, typeface choice, shadows, motion curves.** The CSS is dimensions, flow, and state. Every ink channel is a width, a style, a position or an opacity — so a later colour pass *adds* a channel rather than carrying the meaning. Any palette that lands must keep: severity ≠ colour-only, verified ≠ colour-only, provenance ≠ colour-only.
* **Any second region.** No drawer, no dock, no tab strip, no popover, no modal, no list of findings — asserted structurally in the DOM tests (`aside`, `nav`, `dialog`, `[role=tablist]`, `[role=complementary]` must all be absent).
* **A framework, a bundler, a build step.** `core.js` + `ink-layer.js` + `ink-layer.css` load directly. The only build is `build-single.mjs`, and it exists solely to produce a single offline file for sandboxed viewing.
* **Redo.** `⇧⌘Z` is routed and announced, and deliberately not implemented in this prototype — the endpoint exists, and nothing in the spatial logic depends on it.
* **Focus mode / reading modes.** Separate feature; not part of these three mechanisms.

---

## §7 · HOW TO RUN

```bash
# the modular source, as shipped (needs a static server for ES modules)
python3 -m http.server 8000        # then open http://localhost:8000/?project=The+Late+Hour

# tests
node --test tests/core.test.mjs    # 60 tests, no dependencies
npm i jsdom && node --test tests/  # 103 tests, incl. the DOM suite that boots and drives the layer

# the offline single file (no server, no network)
node build-single.mjs > ink-layer-preview.html
```

**Try, in order:** `n` (walk to the first wet line — you land on the unverifiable finding, and `J`
refuses it with the reason) → `n` again → `Enter` (pin the fold and read the critique under its
own line) → `J` (the ledger takes take 1, and **the line does not move**: nothing is written until
you commit) → `J` `K` (audition; watch the line stay the writer's) → `E` (type your own wording
into the passage; `Enter` commits the wording) → `Enter` (commit the take; the line changes, the
fold closes, the radar's pip shrinks) → `⌘Z` (the line re-wets — the diagnosis answers back).
Then `V` (the takes are read on a beat — any key stops it), `V` on an action line (the sizes are
already stacked, and the strip says why there is no beat), `F` (filter the critique to this scene,
then this category, then what is still open), `O` on the beat finding (visit the scene it cites and
come back), `g` (the same instrument on the lifted bench), `a`, `Esc`.

## §8 · ACCEPTANCE CHECKLIST (structural)

- [x] One scroll context; the manuscript never gets its own `overflow`.
- [x] The Horizon is 12px, fixed, out of flow, true-proportion, ≥1px bands, integer-tiled, head void honest.
- [x] Zero-summary capability detected at boot; per-scene fallback never assumed.
- [x] The fold grows **between** rows, in the same column, and pushes content down.
- [x] Dwell 420 ms; the armed window is cancellable with no residue; line → own fold does not cancel.
- [x] Opening/closing never moves the focused line (only `overflow`/`collapse-above` corrections).
- [x] `J`/`K` move the ring and **never touch the document** (the trap frame); the frame is captured once; every reading composes from it; the commit is the only write and writes exactly what the strip showed.
- [x] `E` edits the passage inside the frame it was cut from, and a typed proposal cannot accumulate a previous one.
- [x] `Enter` applies through `/edits/apply`, the apply response patches the page (`statusPatch`), and the summary is re-read from the server.
- [x] Placement is `fuzzyScore` ≥ 0.72 over the evidence quote; `line_start` breaks ties and never predicts; an unplaceable finding is scene-anchored and never auto-targeted.
- [x] Severity is one canonical vocabulary on the page (`SEV_ALIAS`), stated where the desk's word differs; the ├─ mark is a width, the fold's is ▪ blocks.
- [x] The context filter recedes critique and never the prose; the scope is announced in context.
- [x] An unknown response shape casts nothing and says which fields it did not find.
- [x] The caret is absolute; `⌘Z` while editing never steals the writer's own undo.
- [x] Unverifiable findings are shown, never dropped, and **never given an invented candidate**.
- [x] Fails loudly, loses nothing.
- [x] Nothing prints but the script.
- [x] Colour pass (`detent.css`) — paints; the strip's geometry stays in `ink-layer.css` §C.
- [x] Verified in a real engine: the three severity widths, the strip's order, the editing state, the refusal state, and the filter's recession.
