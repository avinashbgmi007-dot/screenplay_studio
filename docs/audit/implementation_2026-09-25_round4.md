# Implementation — the round-3 ladder

**Date:** 2026-09-25 (round 4)
**Implements:** the recommended order at the end of
`docs/audit/e2e_production_readiness_2026-09-25_round3.md`
**Constraint honoured:** every claim below is either *executed* or *explicitly
marked as not verified*. Nothing here is inferred from reading source.

---

## 1. The ladder, in order

| # | Step | Status | Guard that can fail |
|---|---|---|---|
| 1 | **BE-2** push the six fix commits | **done** — remote `qoder/update` `eccbdca` → `cefe08a`, proven with `git ls-remote` | n/a (a delivery action, verified by the remote's own ref) |
| 2 | **BE-1** one critical section for `/edits/apply` | **done** | `tests/test_cycle_continuity.py` (deterministic) **and** `tests/test_apply_race.py` (behavioural) |
| 3 | **E2E-1** make the lock guard able to see acquire→release→acquire | **done** | the same `test_cycle_continuity.py`, plus 3 can-fail legs inside it |
| 4 | **UX-3** a suite that opens a second browser context | **done** | `tests/e2e_browser_two_contexts.py` |
| 5 | **UX-1** live regions for errors and replies | **done** | `tests/e2e_browser_live_regions.py` |
| 6 | **the `xss_inert` census** — a tripwire my change tripped, with two latent classifier bugs behind it | **done** | the census's own two assertions (§7) |

Everything was mutation-verified: **7 mutations, all detected, every mutated file
restored byte-identical** (`.workbuddy-ai/scratch/mutation_check_r4.py`).

### 1.1 Gates, measured at this revision

*Everything below is the ladder (§1–§8) **plus** the BE-3 (§11) and UX-2 (§12)
follow-ons, measured together at one revision.*

> **Superseded.** §13.9 measures the same gates after the five LOW findings, and
> **§17.8 is the current row** (2026-09-26: 1835 pytest / 55 suites / 1343 checks).
> This table is kept as the record of the revision the ladder landed at
> (`27bd576`): 1786 / 53 suites / 1319 checks.

| Gate | Command | Result |
|---|---|---|
| Unit + integration | `python -m pytest tests/ -q --cov` | **1786 passed, 3 skipped, 0 failed — 87%** (9751 statements, 1290 missed), exit 0 |
| Browser E2E | `python tests/run_browser_suites.py` | **53 suites: 52 passed, 0 failed, 1 skipped, 0 known-broken — 1319 checks**, exit 0 |
| Lint | `ruff check .` | **All checks passed** |
| JS unit | `node --test tests/js/core.test.js` | **16 / 16** |
| Mutation harness | `.workbuddy-ai/scratch/mutation_check_r4.py` | **13 / 13 detected**; tree restored byte-identical |

Two rows carry the weight:

- **The 1,235 browser checks that existed before this work are unchanged and all
  still pass.** That is the claim that needed proving: the edit cycle went from two
  critical sections to one, the SPA gained announcement plumbing, a security
  tripwire's classifier changed, the busy-store classification changed, and a touch
  media query changed — and nothing else moved. The 84 new checks are `live_regions`
  (14), `two_contexts` (8), `store_busy` (7) and `viewport_ladder` (55).
- The one skip is `gun_pen_audit`, printed with its reason: *"runs a real analyze —
  needs a llama-server, so E2E_BASE must point at a studio that has one"*.

Against the round-3 baseline (**1771 passed / 49 suites / 1235 checks**):
**+15 pytest tests** (4 cycle-continuity, 4 apply-race, 7 store-busy), **+4 suites**,
**+84 checks**.

The fleet was run **twice**: the first run came back **49 passed, 1 failed** on
`xss_inert`, which is the finding in §7. The figures above are from the run at the
final revision, after that fix.

---

## 2. BE-1 — `POST /edits/apply` is now one critical section

### The defect, restated

`webapp_server.py` called `load_working(m)` and then `save_working(m, doc, record)`.
`load_working` → `ensure_working` takes `lock_for(working.json)` and **releases it**
before returning; `save_working` takes it **again**. So the read and the write were
two critical sections with the whole document round-trip in between — the rule
AGENTS.md states in writing ("hold that lock across the read, not only the write"),
broken on the path a writer uses every time they accept a rewrite.

Commit `ab48b21` ("One write cycle, one critical section") had wrapped
`undo`/`redo`/`reset`/`ensure_working`. It did not wrap the route, which does its
own load. Measured with nothing slowed, before the fix: **295/300 across two
threads of one process, 126/300 across two OS processes, 40/40 through two real
browser contexts.**

### The fix

A new `revision.apply_edit(m, scene_number, replacements, record=None)` holds
`lock_for(working_path(m))` across load → apply → save, and returns JSON-safe
fields only (`{applied, skipped, scene_text_after}`) so a caller cannot
accidentally serialize the whole script into a response. The route is now three
lines and calls nothing else.

**This is not a new pattern — it is the repo's existing one.** Four sibling stores
already do exactly this, each with a comment saying why: `notes._locked`,
`stash_store._locked`, `ideas._modify`, and `screenplay_cowriter.store.save`,
whose comment names this hazard verbatim ("the load that produced `session`
happened OUTSIDE it, so a stale in-memory snapshot would overwrite … messages a
faster turn already saved"). The fix copies the house style rather than inventing
one. `apply_replacements` gained a docstring line pointing at `apply_edit`, so the
next reader meets the locked wrapper at the moment they meet the unlocked primitive.

The test fixture `_apply` and the cross-process `_APPLY_CHILD` in
`test_undo_redo_lock_race.py` now call `apply_edit` too. That matters: they used to
hand-roll the load-then-save pair, so every guard in that file was testing an
imitation of the route rather than the route's primitive.

### Scope, checked rather than assumed

An AST pass over `webapp_server.py` flags 19 mutating routes as "reads then
writes". I read each one's delegate:

| Route family | Delegate | Verdict |
|---|---|---|
| notes / stash / ideas | `notes._locked`, `stash_store._locked`, `ideas._modify` | lock held across the read |
| premise | `save_project_premise` holds `lock_for` itself | correct |
| session (`switch_branch`, `update_settings`, fork) | `screenplay_cowriter.store.save` — merges missing messages | see BE-6 below |
| **`/edits/apply`** | **was the only unfixed instance** | **now fixed** |

`beatboard.py` calls `load_working` three times but only ever writes
`beatboard.json`, so it is read-only on the cycle stores. That is why the fix is
small.

---

## 3. E2E-1 — a guard that can see the shape it exists to catch

`tests/test_lock_order.py` enforces acquisition **order**. It cannot see BE-1,
because acquire → release → acquire is two individually legal acquisitions, not a
nesting violation. That is how the defect survived the guard written to prevent its
bug class.

`tests/test_cycle_continuity.py` enforces the invariant the topology note states in
words — *"one cycle, one explicit acquisition, covering the whole read-modify-write
of the trio, never only the write"* — as three executable claims:

1. the document a recorded `save_working` persists must have been **read while the
   cycle lock was held**;
2. the cycle lock must **still be held** when that save runs;
3. one `apply_edit` must be **exactly one outermost acquisition** of the cycle lock.

It is deterministic — no timing, no iterations — and it is armed over the **real
route** through the Flask test client, not over a hand-built call.

Three can-fail legs sit in the same file, so the guard's teeth are asserted rather
than assumed: the BE-1 shape, a lock wrapped around only the write, and (via the
acquisition count) any second outermost acquisition whatever it is spelled as.

### How it observes, and why that changed

The first version kept a per-thread stack of enter/exit events over
`jsonio._lock_for`. **It did not stay in sync in this suite** — the recorded stack
grew by one after each `exit`, and two empirical traces (a standalone replica, then
the real guard with its stack printed) both reproduced the drift without explaining
it. I discarded that design rather than debug it into working, and rebuilt the
guard on the lock's **own** state: `_StoreLock._depth` plus RLock ownership. Asking
the object that owns the state cannot drift away from it. `_depth` is private, but
it is this repo's own attribute and the topology note already reasons about it by
name — that trade is deliberate and recorded in the file.

One consequence worth stating: a first attempt at `_lock_is_held` called
`jsonio.lock_for`, which the fixture had monkeypatched — so the guard introspected
its **own proxy**, found no `_depth`, and reported "never held" for every lock. The
two can-fail legs then passed for entirely the wrong reason. The guard now takes the
real `_lock_for` as a constructor argument, and the reason is in its docstring.

---

## 4. UX-1 — errors and replies now reach a screen reader

`#error-banner` and `#messages-scroll` were not live regions, so an error and every
chat reply were silent to assistive tech (WCAG 4.1.3 AA). `#a11y-status` existed for
exactly this and carried only the manuscript-load count. **No test asserted any live
region** — which is why it survived three audit rounds.

### What changed, and what deliberately did not

- `#error-banner` is `role="alert"`.
- A single `announce(message, target)` helper is the one writer pattern for
  announcements. It **reveals before writing** (a `role="alert"` that is
  `display:none` is not in the accessibility tree, so text written there is
  announced to nobody — the original `showError` wrote first and revealed second)
  and **clears before writing** (so a repeated error is a content change, not a
  same-string replacement).
- A completed chat reply announces a **bounded excerpt** (≤220 chars) through
  `#a11y-status`, only when it landed where the writer is still looking.
- **`#messages-scroll` is deliberately NOT a live region.** `renderMessages()`
  rebuilds it with `innerHTML = ""`, so a live region there would re-announce the
  entire conversation on every re-render — the same trap the manuscript region's own
  comment in `index.html` records. There is a check for the **absence**, not just
  for the presence of the fix.
- `announceManuscriptLoad` now routes through the same helper, so one status line
  has one writer and a stale write cannot outlive a newer one.

### The half that is not observable, stated rather than hidden

The **clear-first** behaviour has no guard, and the code says so. Measured:
`textContent = sameString` replaces the text node either way, so the mutation
records appear with or without the clear. The clear is there for screen readers that
diff *content* instead of re-reading the node — an AT behaviour no DOM assertion can
see. What the suite *does* pin is the observable consequence: the clear leaves an
intermediate empty-text write, and that is the check.

---

## 5. UX-3 — a second browser context, at last

**No suite had ever opened a second browser context.** Every other suite drives one
page; the multi-window workflow — a writer with their project open twice, which is
the shape `app.run(threaded=True)` makes two threads — had zero coverage. That is
the reason BE-1 was invisible to 1,235 checks.

`tests/e2e_browser_two_contexts.py` opens two real contexts (separate cookie jar,
separate storage), puts the same project in both, and races one edit per window
through the SPA's own `api()`, with every request's start/end recorded. Two
properties make it honest:

- **the dispatch is fire-and-forget.** `page.evaluate` does not return until its
  promise settles, so awaiting the first apply before starting the second serialises
  them and measures nothing. A scratch version of this probe did exactly that and
  reported a clean **0/40** while proving nothing.
- **every round asserts the two requests overlapped.** A green must mean "nothing was
  lost", never "nothing raced".

---

## 6. BE-2 — the push

`git ls-remote` (not the local tracking ref, which this sandbox does not persist)
before: `qoder/update = eccbdca` — the **pre-fix tree that leaks the screenplay on a
foreign `Host`**. After: `cefe08a`, matching local HEAD, and `git grep` against the
fetched commit confirms `_reject_foreign_host` and `syncRoute` are present. The
checkout was clean apart from the audit report, so the push carried the six fix
commits and nothing else.

**The round-4 push.** `e86ff62` (code + tests) and `2b38648` (docs) are pushed too:
`git ls-remote` reports `qoder/update = 2b38648`, and `git grep` against the fetched
commit confirms `apply_edit`, `announce`, `role="alert"` and all four new test files
are present in it.

### 6.1 Two environment hazards, neither a product defect

Recorded because both cost real time and both will recur.

1. **`git push` looked hung; it was the credential helper.** `GIT_TRACE=1` shows
   `git credential-helper-selector get` taking **68 seconds** before it even reaches
   `git-credential-manager.exe`, and three attempts — including one with a
   900-second budget — never completed. Bypassing the selector and calling GCM
   directly finished the push in **6 seconds**:
   `git -c credential.helper= -c 'credential.helper=!"…/git-credential-manager.exe"' push origin <branch>`.
   A push killed by `timeout` also wedges the next attempt for ~12 minutes, so the
   first two failures compounded.
2. **Every `git commit` in this checkout deletes the current branch's ref.** The
   Qoder `post-commit` hook runs the Qoder SDK, and `refs/heads/qoder/update`
   disappears — `HEAD` becomes unresolvable and `git status` reports the whole tree
   as staged-new. **The commit object and its reflog entry are written correctly**, so
   nothing is lost, but the recovery is not obvious:
   `TIP=$(tail -1 .git/logs/refs/heads/<branch> | awk '{print $2}')`, then write it to
   `.git/refs/heads/<branch>`. `git update-ref` returned **exit 0 without creating the
   ref**, so the direct write is the one that works. It happened on both commits here.

---

## 7. The `xss_inert` tripwire fired — and it had two bugs of its own

The first full fleet run at this revision came back **49 passed, 1 failed**:
`xss_inert` reported *"19 non-clearing of 68 innerHTML lines … vs expected 18"*.
That is the tripwire working as designed — it exists so a new non-clearing
`innerHTML` sink forces the payload sweep to be widened, and it refused to pass
silently.

It was a false positive, for a reason worth recording:

1. **The census recognised only `//` comments.** A line beginning ` * ` inside a
   `/** */` docstring was classified as a *sink*. UX-1's explanation of why
   `#messages-scroll` is deliberately NOT a live region mentions `innerHTML = ""` in
   prose — so documenting an accessibility decision failed a security gate. The
   function's own docstring already said "Comments describe sinks; they are not
   sinks"; the code simply did not implement that for block comments. Now it does,
   and the block state is tracked for every line rather than only for lines that
   contain `innerHTML`.
2. **`fn_re` used `.match()`, which anchors at column 0**, so it silently skipped
   every `async function` and credited their sinks to whatever earlier plain
   `function` preceded them. My stray line was attributed to `_tokenError`; its real
   owner is `async function streamChatTurn`. Fixing (1) then exposed a
   **pre-existing mis-attribution**: `checkConnection`'s fixed status string
   (`app.js:722`) was being counted under `setConnectionMode`. `EXPECTED_CENSUS` now
   reads `setConnectionMode: 1` + `checkConnection: 1` where it read
   `setConnectionMode: 2`, and the **sum is unchanged at 18** — so the tripwire is
   exactly as strong as before and now points at the right function.

Both are the same defect class this repo keeps producing — a **source-text assertion
whose classifier is incomplete** — and neither was a product defect. `xss_inert` now
passes **36/36**.

**Also corrected:** the round-3 report's "18 of 63". The non-clearing figure was
right; the total was not. My recount of that revision's `app.js` is **67** lines
(4 comments, 45 clearing, 18 non-clearing), and the worktree adds exactly one line —
the docstring mention above.

---

## 8. Where my own work failed review

This is the part worth reading. Seven things went wrong, in the order I found them.

1. **The first cycle-continuity guard used a design I could not make work.** A
   per-thread enter/exit stack over `jsonio._lock_for` drifted out of sync, and two
   empirical traces failed to explain why. I threw the design away rather than ship a
   guard I did not understand, and rebuilt it on the lock's own `_depth`. *A guard
   whose bookkeeping is a mystery is a guard that will one day pass for the wrong
   reason.*
2. **My instrumentation intercepted its own introspection.** `_lock_is_held` called
   the monkeypatched `jsonio.lock_for`, so the guard read its own proxy and reported
   "never held" for every lock — which made both can-fail legs pass for the wrong
   reason. Caught only because the two **green** legs failed while the red ones
   "passed". Fixed by handing the guard the real `_lock_for`.
3. **Two UX-1 checks were vacuous, and the mutation harness caught them.** My
   MutationObserver logged `textContent` on *every* mutation, so a style change
   looked like a text change — the "reveal before write" ordering check and the
   "written again" count both passed against the broken code.
4. **The re-framed check was still vacuous, and I only found out by measuring.**
   After fixing (3) I assumed `textContent = same` is a DOM no-op — it is not; it
   replaces the text node. So counting message writes still proved nothing. The
   observable signature of the clear is the **empty write** it leaves behind, and the
   check asserts that instead. **I then had to correct a comment I had written in
   shipped code** that stated the false version.
5. **My first apply-race assertion was wrong.** It compared the whole scene text to a
   bare value; the scene has a heading and other lines. Fixed to element-level
   membership, and the reason `in` on a substring would be too weak (`T1-2` matching
   a scene holding `T1-25` — exactly the stale value a lost update leaves) is in the
   helper's docstring.
6. **The mutation harness's first run matched 0 anchors on all four mutations** — the
   CRLF trap this project's own memory documents. The match-count assertion turned
   what would have been four silent no-ops into four `[SKIP]`s.
7. **I edited `app.js` after starting the fleet**, which invalidated the run in
   flight. I killed it and restarted from the frozen revision rather than quote a
   figure measured across two different trees. Cost: a full re-run.

I also had to **withdraw a claim from the round-3 report**: it lists
`docs/audit/FIX_TRACKER.md`'s gate figures as stale (34 suites / 702 checks / 1614
passed). They are not any more — the tracker now reads 1771 / 49 suites / 1,235
checks, which is accurate for the previous revision. That row of the round-3 report
should not be cited.

---

## 9. What is NOT fixed — the accounting

Every finding from round 3, so this document is not read as "all clear":

| Finding | Severity | Status |
|---|---|---|
| BE-1 apply route not atomic | HIGH | **fixed** |
| BE-2 fixes unpushed | HIGH | **fixed** |
| UX-1 errors/replies silent | MEDIUM | **fixed** (one half unguardable, §4) |
| UX-3 no second browser context | MEDIUM | **fixed** |
| E2E-1 lock guard blind | MEDIUM | **fixed** |
| **BE-3 `StoreLockTimeout` → 500** | MEDIUM | **fixed** — see §11 |
| **BE-4 403 recovery copy** | LOW | **open** |
| **BE-5 over-strict loopback spellings** | LOW | **open** |
| **BE-6 session metadata last-writer-wins** | LOW | **open** — `store.save` merges messages only |
| **UX-2 viewport breadth** | MEDIUM | **fixed** — and it found a real defect; see §12 |
| **UX-4 the 3 de-vacuumed checks sit in the skipped suite** | LOW | **open** |
| **UX-5 eight marker-only checks in `ui_batch`** | LOW | **open** |
| **E2E-2 residual in the wrong place** | LOW | **partly moot** — BE-1's residual is gone; the trio's non-transactional gap is still documented only in `revision.py` |

Residuals of this change set, stated plainly:

1. **The edit trio is concurrency-safe, not transactional.** `working.json`,
   `edits.json` and `edits.redo.json` still land as three separate atomic renames, so
   a crash between the text write and the log write still diverges them. That is
   documented in `revision.py`'s topology note and is unchanged by this work.
2. **The guard depends on a private attribute** (`_StoreLock._depth`). Deliberate,
   justified in the file, and the alternative was a bookkeeping design that did not
   work.
3. **`clear-first` in `announce()` has no guard** — see §4.
4. **The live-region work is asserted structurally, not with a real screen reader.**
   No AT was driven. What is proven is the DOM mechanism (role, reveal order, content
   change); whether a specific AT announces is not something this repo can test.

---

## 10. Files changed

**Product (4 modified, 0 new)**
- `screenplay_studio/revision.py` — `apply_edit()` (the locked cycle primitive)
- `screenplay_studio/webapp_server.py` — the route now calls it
- `screenplay_studio/webapp/app.js` — `announce()`, `announceReply()`, `showError` reveal-then-write, `announceManuscriptLoad` routed through `announce`
- `screenplay_studio/webapp/index.html` — `role="alert"` on the error banner

**Tests (2 modified, 4 new)**
- `tests/test_cycle_continuity.py` *(new)* — the deterministic invariant + 3 can-fail legs
- `tests/test_apply_race.py` *(new)* — threaded and cross-process apply races, each with a sequential control
- `tests/e2e_browser_two_contexts.py` *(new)* — two real contexts, with an overlap control
- `tests/e2e_browser_live_regions.py` *(new)* — live regions, including the absence of one
- `tests/test_undo_redo_lock_race.py` — `_apply` and `_APPLY_CHILD` now call `apply_edit`
- `tests/e2e_browser_xss_inert.py` — the census classifier (§7)

**Not touched:** the in-flight re-audit that was already in the tree (I re-ran it,
and it passes).

---

## 11. Follow-on: BE-3 — a busy store is 503, and the writer is told

The last MEDIUM from the round-3 report, and the only remaining finding where a
transient condition was reported to the writer as a crash.

### What it was

`jsonio.StoreLockTimeout` subclasses `RuntimeError` and had no
`@app.errorhandler`, so it fell through to `_unhandled`: a contended
`GET /script` or `/export` answered **500** after 10.018s with
`{"error":"Unexpected error: timed out after 10s waiting for another process to
release working.json"}` — no `Retry-After`, and no way for the writer or the SPA to
tell it apart from a real fault. `StoreUnreadable` already met the right standard
one layer over.

### What changed

1. **`@app.errorhandler(StoreLockTimeout)` → 503 + `Retry-After` + `busy: true`**,
   with a sentence that names the condition and says what to do. `busy` is what
   keeps it apart from a damaged store, which also answers 503 and must never be
   retried.
2. **The amplifier the round-3 report named.** `reset_working` holds the cycle lock
   while taking three leaf locks, and each used to start a **fresh**
   `LOCK_TIMEOUT_SECONDS` — so one stuck file could hold the cycle lock for ~3× the
   budget while every other request expired its own and was told the studio had
   broken. `jsonio.lock_deadline()` now puts **one** deadline over the whole
   removal, and `_acquire_os_lock` takes the tighter of that and its own.
3. **The half that makes the fix real: the writer is now told.** `openProject`
   wrapped `loadScriptData()` in `catch (_) { /* no parse yet */ }`, which swallowed
   **every** failure as "this project has no parse yet" — so a busy store (and any
   500) left the manuscript pane showing nothing and said nothing at all. The two
   other `loadScriptData` call sites already did
   `showError("Couldn't load the script: " + e.message)`; the project-open path was
   the odd one out, and it is the app's most important surface. **Without this the
   503 would have been invisible on exactly the route the finding names.**

### The same probe, re-run

The round-3 probe that measured the 500 (`.workbuddy-ai/scratch/lock_timeout_probe.py`)
was re-run against this revision with `LOCK_TIMEOUT_SECONDS` left at its real 10s:

```
GET /api/projects/The_Late_Hour/script WHILE THE LOCK IS HELD
  status  : 503
  elapsed : 10.1s
  body    : {"busy":true,"error":"The studio is busy — another window or process is
             writing to this project right now. Nothing was lost. Try again in a moment.",
             "retry_after":1}
GET script after release -> 200
```

Before: **500** / 10.018s / `{"error":"Unexpected error: timed out after 10s …"}`.
The `Retry-After: 1` header is asserted in `tests/test_store_busy.py`.

### A retry I wrote and then removed

My first version had the SPA retry a read once on `Retry-After`. I dropped it: it
would have been **unguarded** — making a studio answer 503 inside a browser suite
needs real contention plus the full 10s timeout — and its value is low, because the
round-3 reachability measurement puts a load-induced timeout at nil. It fires when a
holder is genuinely stuck, and a 1s retry does not help there. The header is there
for a client that wants it; the writer gets a sentence they can act on instead.

### Guards

- `tests/test_store_busy.py` (7) drives **real cross-process contention** — a child
  process holds the lock, because in-process contention cannot produce the timeout
  at all (the in-process `RLock` is acquired with no timeout, so two threads simply
  serialize). It asserts the status, the `Retry-After` header, the `busy` flag, the
  message, that an uncontended read still answers 200, and that a damaged store is
  **not** reported as busy. It also pins the budget composition with
  `LOCK_TIMEOUT_SECONDS` left at its real 10s default, so the assertion is about the
  block and not about a patched number.
- `tests/e2e_browser_store_busy.py` (7) is the end-to-end half: a real studio, a
  real holder child, and the writer actually seeing the banner.

### Not guarded, stated plainly

`reset_working`'s **use** of `lock_deadline` is not directly asserted. The
observable difference needs two contended leaves held across overlapping windows
inside one budget, which is a timing-margin test that would be flaky for little
assurance — and the mechanism it depends on *is* guarded. This is the same
judgement as UX-1's `clear-first` (§4).

---

## 12. Follow-on: UX-2 — the viewport ladder, and the defect it found

### What the audit said

The shared `launch()` helper hardcodes **1440×900** and only 6 of 49 suites
override it; `phase11_responsive` covers 1440 / 1024 / 390 well. The named gaps are
a different axis: **no short viewport** (1366×768, 1440×720), **no touch
emulation** — `set_viewport_size` changes the viewport but not `has_touch` /
`is_mobile`, which are *context* options, so no suite had ever run with a real touch
capability — and **no mobile landscape**.

### I measured before writing anything

Across 1440×900, 1366×768, 1440×720, 844×390 (touch) and 390×844 (touch), with the
dock and the partner drawer both **open**: zero horizontal overflow, the manuscript
keeps ≥50% everywhere, the status strip is never clipped, and every open panel's
close button stays inside the viewport. **The shell itself is sound.** One real
defect turned up on the axis nothing had ever run:

### The defect: a touch device wider than the mobile breakpoint got 24px rows

The stylesheet states its own minimum — `/* touch targets >= 44px: the index rows
and their toggle */` — but that rule lives inside `@media (max-width: 767px)`.
**Width is a proxy for the input device, and the wrong one:** a phone in landscape is
844px wide and unambiguously a touch device, so it fell into the *tablet* band and
got the compact strip's 24px rows. Measured with `has_touch` + `is_mobile`
emulation (`pointer: coarse` true):

| config | `pointer: coarse` | scene-index row |
|---|---|---|
| 1440×900 | false | 25px |
| 1366×768 | false | 25px |
| **844×390 landscape** | **true** | **24px** ← below the file's own 44px floor |
| 390×844 portrait | true | 44px |

### The fix

`@media (pointer: coarse) and (max-width: 1199px)` applies the 44px minimum to the
index rows and its toggle — keyed off the property that actually describes the
input device, and scoped to the compact strip so the wide desktop layout (where the
pointer is normally fine) is untouched. After it: **844×390 → 44px**, 390×844 → 44px
(unchanged), and every non-touch config unchanged at 24–25px, with no overflow and
identical manuscript widths. Verified across the ladder, not just at the one config.

### The guard

`tests/e2e_browser_viewport_ladder.py` (55 checks) runs the ladder with a **context
per config** — the only way to emulate touch — and asserts, per config: the
manuscript actually rendered, the emulation is real, no horizontal overflow, the
manuscript keeps ≥50%, the column is tall enough to read, and the status strip is
not clipped; then, with the dock and drawer **open**, that each opens and keeps its
close button in reach. The touch configs also check the 44px target.

The two non-vacuity checks are load-bearing: a blank page has no overflow, and a
"touch" config whose emulation silently failed would assert nothing about touch.
This shape of suite passes trivially without them.

**A mutation that did not reach the property, and why that is not the same as a
vacuous guard.** The first attempt at proving the 50% check could fail widened the
scene index (`#scene-index { width: 700px }`) — and the suite stayed **green**.
The guard was not at fault: `#scene-index` is a flex item, so the layout absorbed
the width and the manuscript never approached the floor. Re-pointing the mutation
at the manuscript's own `flex: 1` (`flex: 0 0 30%`) turns it red. The lesson is
worth keeping: **a green mutation result means "the guard cannot see this", and
"this" may be the mutation rather than the guard.** The harness now says so in the
entry itself.

---

## 13. Follow-on: the five LOW findings, as one pass

The round-3 audit closed with five LOWs. Four of them are the same defect class
this repo keeps producing — **a check that cannot fail**, or an assurance that
exists but is unreachable — so they were taken together.

| Finding | What it actually was | Guard added | Mutations |
|---|---|---|---|
| **UX-5** | 8 of the fleet's checks asserted nothing (`cond=True` default) | `tests/test_browser_check_hygiene.py` (3) — and the default removed | 2 / 2 |
| **UX-4** | 3 de-vacuumed checks live in the one suite that never runs | `tests/test_analyze_contract.py` (4) | see §13.2 |
| **BE-4** | one 403 message for two different 403s | `tests/e2e_browser_403_advice.py` (11) + 3 pytest | see §13.3 |
| **BE-5** | the loopback predicate over-rejected valid spellings | 6 pytest in `test_host_header_guard.py` | see §13.4 |
| **BE-6** | the store's merge covered messages, not the selection | `tests/test_session_selection_merge.py` (6) | 8 / 8 |

### 13.1 UX-5 — the eight checks that asserted nothing, and the default that let them

`Checks.ok` was `def ok(self, name, cond=True, detail="")`. Eight calls in
`e2e_browser_ui_batch.py` passed a name and nothing else, so they verified nothing
and still counted as passes.

The audit's own correction is the important part of the finding: the first sweep
inspected only `args[0]`, so it missed `check(name, True)`-shaped calls where the
constant is the **second** argument. **A vacuous-check sweep has to read every
argument position *and* the helper's default.** I ran that wider sweep over all
55 suites — 1,095 `ok`/`check` calls — and it found the eight, and only the eight.

Fixing the eight is fixing the symptom. The **cause** is the default: it is a trap
any future suite can walk into without noticing, and the failure mode is silent.
So `cond` is now required:

```python
def ok(self, name, cond, detail=""):   # no default, deliberately
```

Measured before changing it: **zero** callers in the fleet omit `cond` (I scanned
for the subtler `ok(name, detail=...)` shape too, which a positional check would
have missed). `e2e_browser_export_flush.py` has always declared its own
`ok(name, cond, extra="")` this way, so the correct signature was already the
house style. A marker-only call is now a `TypeError` at the moment it is written.

`test_browser_check_hygiene.py` guards both ends — the signature, and a scan for a
literal `True`/`None` condition — with a non-vacuity floor (≥40 suites, ≥500
calls) so a broken glob cannot pass while guarding nothing.

**One rule I deliberately did not write.** The sweep also found **33** calls
passing a literal `False`, and they are all legitimate: `ok("x", False, detail)`
inside an `except` block or a precondition-failure branch is the fleet's
established "record a failure with a reason" idiom. A guard that flagged those
would be wrong 33 times, and a guard that cries wolf gets deleted. Only the
`True`/`None` shape is flagged, and the reason is recorded in the file.

### 13.2 UX-4 — giving the three checks somewhere they actually run

`e2e_browser_gun_pen_audit.py` is the one skipped suite: it POSTs a real
`/analyze` and needs a live `llama-server`. Commit `25aacf8` replaced three
`check(name, True)` calls in it with real conditions, and those three have never
executed — in CI or locally. The work was correct; its value was zero.

The audit offered two ways out. I measured whether the demo model could carry
them, the same way as §12 — before writing anything:

```
POST /api/projects/<p>/analyze   -> 200, body has "project" and no "error"
GET  /api/projects/<p>/last-pass -> 6 findings
the arrival snapshot             -> all six fields present
```

It can. So the three guarantees now have a home in **`tests/test_analyze_contract.py`**
(4 tests, **2.6s**, no model, no browser): the analyze ack names the project, the
run produces findings, and the arrival snapshot carries its six fields. They run
on every `pytest` invocation now instead of never.

They also remain in the browser suite, where they will run when someone points
`E2E_BASE` at a studio that has a model. The pytest suite is what makes the
guarantee reachable by default.

### 13.3 BE-4 — two different 403s, one piece of advice

`app.js` showed *"The studio restarted since this page was opened. Reload this
page to keep writing."* for **any** non-retryable 403. But a 403 also comes from
the Host guard (`_reject_foreign_host`), where reloading cannot possibly help —
the writer would reload into the same refusal, forever, with the app confidently
telling them to.

The server now marks that refusal (`host_rejected: true`) and the SPA branches on
it, so the Host case gets advice that is true for it.

**A measurement that changed the guard's shape.** I checked whether a browser can
produce the host branch at all, rather than assuming it:

```
context with extra_http_headers={"Host": "evil.attacker.com"}
  -> page.goto() raises net::ERR_INVALID_ARGUMENT
```

**Chromium refuses to send a foreign `Host`.** So the SPA's Host branch is not
reachable over the wire from a browser, and a suite that tried to drive it that
way would assert nothing (or silently test the token path instead). That also
confirms the Host guard's real trigger is DNS rebinding — a resolved address, not
a forged header.

`tests/e2e_browser_403_advice.py` therefore injects the **real server-produced
bodies** for both branches and asserts the two messages differ, that the token one
still says "reload", and that the Host one does not. It carries the real capability
token (the fleet gate fails any suite that boots with the token switched off, and
it passed), and it sends a genuinely bad token to obtain the token 403 as a
measured precondition rather than a fabricated body.

### 13.4 BE-5 — the loopback predicate

`net_guard.is_loopback_host` accepted only the canonical textual forms
`ipaddress` understands, so `127.1`, `2130706433`, `0x7f000001` and `0177.0.0.1`
were all refused. No browser sends those, which is why this was a nit rather than
a defect — but the predicate's job is to answer "is this loopback?", and it was
answering "no" to four correct spellings of yes.

It now resolves the `inet_aton` forms and range-checks them, and strips the DNS
root label, so `localhost.` and `127.0.0.1.` are accepted. The range check is what
keeps it safe: measured, `3232235777` (= 192.168.1.1) is still refused, and so is
`127.0.0.1.evil.com`. Stripping dots can only remove characters, so it cannot turn
a foreign name into a loopback one.

**My own test was wrong, and the suite said so.** I first asserted that a `Host`
of bare `::1` was accepted. It is not, and should not be: an IPv6 literal in a
`Host` header must be bracketed (`[::1]:8500`), so bare `::1` is a malformed
header rather than a loopback spelling. The parametrisation now uses the form a
browser actually sends.

### 13.5 BE-6 — the selection was last-writer-wins

The store's `_merge_missing_messages` unioned branch **messages** (the H4 fix) and
nothing else, so `current_branch` and each branch's `active_persona` /
`active_mode` stayed last-writer-wins on the in-memory snapshot. A chat turn holds
a snapshot taken *before* the writer switched branches, so its save wrote the old
branch back and silently undid the switch. Nothing errored, nothing was lost — the
writer simply found themselves in the wrong room, and the store's own comment
claimed to have closed this class while having closed it for exactly one field
family.

The merge now keeps the message union and, for a save that is **not** about the
selection, takes those three fields from disk. The four routes whose whole purpose
*is* to change the selection (`fork_session`, `switch_branch`, both
`update_settings`) pass `owns_selection=True`. Scoped deliberately to those three
fields; the exclusions are choices, not oversights, and are stated in the code:
`server_url` / `model_id` / `title` are written where the snapshot *is* the source
of truth, and `awaiting_probe` is turn state the engine has just set.

**The guard has two layers, because they rot for different reasons.**
`test_session_selection_merge.py` pins the mechanism (a stale message-save
preserves disk's selection; an owning save applies its own; the union still runs
either way), and a **static check across both packages** asserts that every
function which changes the selection says so. A behavioural test cannot catch a
*fifth* writer that forgets the flag, because such a writer only misbehaves under a
race — so that half reads the source. It asserts the expected set of writers
exactly, so a renamed or added writer cannot make it pass silently. §13.6 is the
story of how the first version of that check was scoped too narrowly, and the gate
said so.

**One more thing the mutation run found.** The `except OSError` path is not the
only way a corrupt file can reach the merge, and a dangling `current_branch` on
disk would have been copied into a *healthy* in-memory session — turning the next
`session.branch` into a `KeyError`, a 500 caused by a save that only meant to
append a message. The merge now adopts disk's pointer only when it names a branch
we hold. That case has its own test.

### 13.6 The gate caught what my guard's scope missed

The first full `pytest` run at this revision came back **3 failed**. All three were
in `test_cowriter_server.py`, and all three were BE-6-shaped:

```
assert store.load(session_id).current_branch == "alt"   -> 'main'
assert store.load(session_id).branch.active_persona == "premise_doctor"
                                                        -> 'writing_partner'
assert store.load(session_id).branch.active_mode == "brainstorm"  -> 'peer'
```

The cause was mine. **`screenplay_cowriter/server.py` — the standalone cowriter
HTTP surface — has its own `fork`, `switch` and `settings` routes**, and they call
`store.save(session)` too. Making the selection preserve-by-default turned the flag
from an optimisation into a requirement, and I had marked only the four writers in
`webapp_server.py`: the file the audit happened to cite. A repo-wide AST sweep then
found **eight** writers, not four — the other three routes in `server.py`, and five
more inside `cli.py`'s `_handle_command` (`/fork`, `/switch`, `/delete`,
`/persona`, `/mode`).

The lesson is not "I forgot a file". It is that **a guard's scope is part of the
guard.** The static check scanned exactly one module, so it certified a property of
one module and I read it as a property of the codebase — which is the same failure
as a check that cannot fail, arriving by a different route. It now scans both
packages, keyed by `(module, function)` because `fork_session`, `switch_branch` and
`update_settings` each exist in *both* servers, and it asserts the expected set
exactly so a new writer is a deliberate update rather than a silent omission.

**And the harness then caught a second defect, in my own test.** The CLI test was
named `test_the_cli_switch_command_survives_a_stale_chat_save` and drove `/fork`.
Mutating the `/switch` save left the suite **green** — the mutation was fine; the
test was lying about what it covered. It now drives `/fork`, `/switch` and
`/persona` (three separate save sites, and the three that touch all three fields),
and the `/switch` mutation goes red.

The residual, stated plainly: `/delete` and `/mode` are additional save sites in
the same dispatcher, and the static check can only prove the flag appears
*somewhere* in `_handle_command`, not that it is on each of the five calls. Two
are covered behaviourally; three are covered by presence. A per-call-site rule is
not expressible statically here, because a save inside a function that mutates the
selection may legitimately be a message-only save.

### 13.7 What the mutation harness caught in my own tests

Six mutations, six detected, tree byte-identical — but only after the harness
caught a defect in the test I had just written.

**The union assertion in the first BE-6 test was vacuous.** Disabling the message
union (`if (m.role, m.content) not in have:` → `if False:`) left the suite
**green**. The reason is worth stating precisely: the union copies **disk →
session**, and the message I was asserting on was the *session's own*. It was
present regardless. The test now seeds a message that exists **only on disk**,
which can reach the final state only through the merge — and that mutation goes
red.

**And one expectation of mine was wrong, not the test.** I expected the
dangling-pointer test to fail when the whole preserve path was disabled. It does
not, and it should not: with nothing adopted, a healthy session stays healthy, so
the test passes for the right reason. The guard itself is pinned by the mutation
that removes only the guard. A test that also failed when the feature was absent
entirely would be asserting the wrong thing — so the harness records that
distinction in the entry rather than quietly dropping it.

### 13.8 An observation I could not reproduce, and a correction to my own first reading

Not one of the five. Recorded because the first version of this section made a
claim that turned out to be **unsupported**, and the correction matters more than
the observation did.

**What I saw.** While checking the working tree before committing, `git status`
listed `script_doctor_studio-0.1.0/` at the repo root: a complete second copy of
the source tree (its own `tests/`, `knowledge_base/`, and
`script_doctor_studio.egg-info/`), untracked and **not covered by `.gitignore`**,
which lists `dist/`, `build/` and `*.egg-info/` but not the `<name>-<version>/`
pattern setuptools uses for sdist staging.

**What I first concluded, wrongly.** That
`test_packaging_data_files.py`'s `setuptools.build_meta.build_sdist(out)` stages
`<name>-<version>/` in `cwd=ROOT` and leaves it behind, because
`_purge_build_state()` only clears `build/` and `*.egg-info/`. That reading was
wrong, and the test disproved it:

```
pytest tests/test_packaging_data_files.py -k sdist   ->  1 passed; no directory created
pytest tests/test_packaging_data_files.py            -> 10 passed; no build/, no dist/,
                                                         no <name>-<version>/
```

setuptools cleans up its own staging directory on a successful build. So there is
no defect here to fix, and the claim is withdrawn.

**What misled me.** The directory's mtime was 02:41 — during this session — which
looked like proof that something in this session had just written it. It was not:
`ruff check .` had descended into it and written `.ruff_cache/` **inside** it, and
writing a file inside a directory updates that directory's mtime. A timestamp is
not evidence of authorship. The directory itself carried files dated 2026-09-21 —
a leftover from an earlier session — and it was gone before I could move it aside
for a controlled experiment, most likely removed by setuptools' own staging
cleanup during the sdist build I ran to test the hypothesis.

**The one narrow thing that is true.** `.gitignore` does not cover the
`<name>-<version>/` staging pattern. Nothing in the current suite leaves such a
directory, so this is hardening rather than a fix: an *interrupted* build, or a
manual extraction, would land untracked-but-not-ignored, and `git add -A` would
commit a duplicate of the whole tree. It is worth one line in `.gitignore`, and it
is recorded here as a gap rather than dressed up as a finding.

### 13.9 Gates, measured at this revision

*This table supersedes §1.1, which was measured at `27bd576` before the LOW pass.*

| Gate | Command | Result |
|---|---|---|
| Unit + integration | `python -m pytest tests/ -q --cov` | **1819 passed, 3 skipped, 0 failed — 87%** (9768 statements, 1278 missed), exit 0 |
| Browser E2E | `python tests/run_browser_suites.py` | **54 suites: 53 passed, 0 failed, 1 skipped, 0 known-broken — 1330 checks**, exit 0 |
| Lint | `ruff check .` | **All checks passed** |
| JS unit | `node --test tests/js/core.test.js` | **16 / 16** |
| Mutation harness | `.workbuddy-ai/scratch/mutation_check_be6.py` | **8 / 8 detected**; all four mutated files restored byte-identical |
| Mutation harness (UX-5) | inline, `.workbuddy-ai/scratch` | **2 / 2 detected**; both files restored byte-identical |

Two rows carry the weight, as in §1.1:

- **The 1,319 browser checks that existed before this pass are unchanged and all
  still pass.** The 11 new ones are `403_advice`. So the `ok()` signature change —
  which touches the harness *every* suite imports — moved nothing, and the four
  sources touched by BE-4/BE-5/BE-6 moved nothing either.
- **`pytest` went from 1786 to 1819** (+33): `test_analyze_contract.py` 4,
  `test_browser_check_hygiene.py` 3, `test_session_selection_merge.py` 6,
  `test_host_header_guard.py` 20.

The `pytest` figure is from the **second** run at this revision. The first run came
back **3 failed** — the `screenplay_cowriter/server.py` writers I had missed
(§13.6). That is worth stating rather than quietly reporting the green run: the
red one is the evidence that the fix was incomplete, and the gate is what caught
it.

---

## 14. Closing the two things §13 left open — and the defect found on the way

### 14.1 `.gitignore` did not cover the sdist staging pattern

§13.8 withdrew the claim that the packaging tests leave a staging directory, but
kept one narrow gap: `.gitignore` lists `build/`, `dist/` and `*.egg-info/` — not
the `<name>-<version>/` directory setuptools stages in the repo root. Nothing in
the suite leaves one today, so this is hardening, not a fix: an *interrupted*
build, or a manual `tar -xzf dist/*.tar.gz`, lands untracked-but-not-ignored, and
`git add -A` commits a duplicate of the whole source tree — which carries its own
`.egg-info`, the exact thing `_purge_build_state()` exists to purge.

The rule is `/script?doctor?studio-*/`: `?` spans the underscored sdist name *and*
the hyphenated project name, `*` spans the version. The guard asserts **two
spellings and two versions**, because the defect this file exists to catch was a
rule that enumerated today's shapes. Mutation-verified both ways — removing the
rule goes red, and narrowing it to `/script_doctor_studio-0.1.0/` (today's
version, i.e. the enumeration mistake) goes red too.

**A newline hazard, caught by an assertion rather than by luck.** The first
mutation attempt matched **zero** times and wrote nothing: `.gitignore` is CRLF and
my anchor was LF. The match-count assertion in the harness — the one this repo's
notes insist on — is what turned a silent no-op into a visible error.

### 14.2 `/mode` closed; `/delete` is a real defect, and it is filed rather than rushed

`/mode`, the fifth selection-owning save in `_handle_command`, now has behavioural
coverage: a stale chat turn cannot revert it.

`/delete` is the fourth, and **measuring before asserting anything turned up a
pre-existing defect**. The command reports success and the branch is still there:

```
/fork alt      -> current=alt   branches=['alt', 'main']
/delete alt    -> "Deleted branch 'alt'."
                  current=main  branches=['alt', 'main']     <- still present
```

The store's message union re-adds a whole branch the session no longer has,
because it cannot tell *"this snapshot deliberately removed it"* from *"another
process just forked it"*. **Causal proof, not inference**: mutating the union's
`session.branches[bname] = dbranch` line to `pass` makes the delete persist
(`branches=['main']`). And it is **not** mine — the line is unchanged and present
at `HEAD~1`. Reach is narrow: `delete_branch` has exactly one caller
(`cli.py:172`) and no HTTP route deletes a branch.

**Why this is filed rather than fixed in the same pass.** The fix is not the
one-line change it looks like. The union genuinely needs to keep a branch another
process just forked, so the session has to record its own deletions —
`Session.deleted_branches`, appended by `delete_branch`, discarded by `fork` when a
name is reused, serialized additively so old files still load, and skipped by the
union. That is a change to a cross-process on-disk format.

**And the obvious fix is a trap.** Suppressing the union's branch re-add for
`owns_selection=True` saves would make a stale selection-owning save *drop* a
branch another process had just forked — losing that branch's messages. That is
worse than the bug it fixes, which is why the shape is written down in the tracker
(`DEL-1`) instead of being improvised at the end of a long pass. Impact is low and
non-destructive: a stale branch lingers; nothing is lost or corrupted.

I did **not** add a test asserting the broken behaviour. Pinning a broken product
surface as a check is the mistake pass 13 made with `design_session`, and the
tracker's own gate note records the reversal. The test that will exist is the one
that fails today and passes after the fix.

---

## 15. DEL-1, fixed — the deletion that was undone, and why the fix is not the obvious one

### What it was

`/delete <branch>` printed `Deleted branch 'alt'.` and the branch was still there
on the next load. The store's message union (H4) copies a whole branch from disk
when the session does not have it — which is normally a concurrent **fork**, where
losing it would lose messages. But a deliberate **deletion** looks identical from
inside the merge, so every `/delete` was silently undone while the CLI reported
success.

Causal proof rather than inference, as in §14: mutating the union's
`session.branches[bname] = dbranch` line to `pass` made the deletion persist. The
line is unchanged and present at `HEAD~1`, so this was **pre-existing**, not a
BE-6 regression, and `delete_branch` has exactly one caller (`cli.py:172`) with no
HTTP route — CLI-only reach.

### Why it was filed in §14 instead of fixed there

Because the obvious fix is a trap. The tempting change is to stop the union
re-adding branches for `owns_selection=True` saves. That would make a stale
selection-owning save **drop a branch another process had just forked** — losing
that branch and its messages, which is worse than the bug it fixes.

The union genuinely has to keep doing its job. So the *deletion* is what has to be
recorded, not the merge narrowed.

### The fix

`Session.deleted_branches` — a tombstone list.

- `delete_branch` appends the name. This is what the union consults.
- `fork` clears the name, because the branch exists again. Without this the
  tombstone would outlive the name and the store would refuse to merge the
  re-forked branch back in — the fork would work in memory and vanish on the next
  load.
- `to_dict` writes it; `from_dict` reads it **with a default**, because every
  session file on disk predates the field. Opening an existing conversation is the
  one thing that may never break.
- The union skips a missing branch whose name is tombstoned, and otherwise
  behaves exactly as before.

### The guard, and the one that carries the weight

Five mutations, all detected, five files restored byte-identical:

| Mutation | Test that goes red |
|---|---|
| `delete_branch` stops recording the tombstone | `test_the_cli_delete_command_persists` |
| the union stops respecting the tombstone | `test_the_cli_delete_command_persists` |
| `fork` stops clearing the tombstone | `test_reforking_a_deleted_name_clears_the_tombstone` |
| `from_dict` requires the field (breaks old files) | `test_a_session_file_written_before_the_tombstone_field_still_loads` |
| **the union never re-adds a missing branch — the tempting wrong fix** | **`test_a_concurrent_fork_is_still_kept_by_a_stale_save`** |

The last row is the one that matters. It is the regression test for the trap
described above: it fails for exactly the shortcut it exists to forbid. **Without
it, that shortcut looks correct** — every other test in the file still passes,
including all of §13's. A guard written after the fact would have been written
against the fix I chose; this one was written against the fix I rejected, which is
the only reason the rejection is durable rather than a note in a report.

The fifth CLI save site is now covered too, so all five of
`_handle_command`'s selection-owning saves have behavioural coverage — the
residual §13.6 recorded as a limitation is closed.

### 15.1 Gates, measured at this revision

| Gate | Command | Result |
|---|---|---|
| Unit + integration | `python -m pytest tests/ -q --cov` | **1825 passed, 3 skipped, 0 failed — 87%** (9775 statements, 1262 missed), exit 0 |
| Browser E2E | `python tests/run_browser_suites.py` | **54 suites: 53 passed, 0 failed, 1 skipped, 0 known-broken — 1330 checks**, exit 0 |
| Lint | `ruff check .` | **All checks passed** |
| JS unit | `node --test tests/js/core.test.js` | **16 / 16** |
| Mutation harness | `.workbuddy-ai/scratch/mutation_check_be6.py` | **13 / 13 detected**; all five mutated files restored byte-identical |

**The fleet is unchanged at 1,330 checks, and that is the informative part.** This
revision touches `models.py` — the on-disk session format — and the browser fleet
does not exercise a branch deletion, so a green fleet says the format change
disturbed nothing it covers, not that the change is exercised end to end. The
evidence for DEL-1 is the pytest suite and the mutation harness; the fleet is the
evidence that nothing else moved.

---

## 16. E2E-4 — the chat pane finally has a transport

The 2026-09-24 audit's remaining MEDIUM: *"the browser gate only ever exercises the
demo model"*, which it called **the largest single coverage asymmetry in the gate**.

### Why the gate could not see it

`e2e_browser_common.start_studio()` forced `SCREENPLAY_STUDIO_DEMO_MODEL=1` and
passed `--demo-model`, and the demo craft model runs **in-process**. So no suite had
ever put an HTTP model transport under the chat pane at all. pytest does cover the
pipeline against `tests/mock_unified_server.py` — but that is `requests`, and
non-streaming, which is a different transport *and* a different code path from the
SPA's `fetch(/messages/stream)` → SSE → render loop. A regression in the browser's
handling of a real model's streaming would have been invisible.

### Two things had to exist first, and they are the finding's real content

**1. The mock had no SSE to give.** Every route answers with a single JSON body —
the shape the pytest suite drives — while `chat_stream` parses `data:` frames. A
streaming request therefore got **zero** tokens and the reply came back **empty**:

```
LlamaServerClient.chat_stream(...) -> on_token fired 0 times, full text: ''
```

So the mock could not stand in for the transport even if a suite asked it to. Fixed
with an `after_request` hook that converts a completion to SSE **only when the
request asked to stream**, which leaves the non-streaming path byte-identical —
that is what the existing tests assert against, and they still pass. Verified with
the *real* client rather than by inspecting frames: `on_token` now fires 5 times and
the assembled text carries the mock's marker.

**2. `start_studio` had no way to boot without the demo.** Added
`demo_model=True`, defaulted so every existing suite is unchanged. `False` requires
a `server_url` — otherwise there would be no model at all — and suppresses both
import-time demo paths, so `main()` points `CONFIG["server_url"]` at the mock and
never activates the demo.

The readiness loop also had to change: it waited for `demo_model` to be **truthy**,
which would hang a real-transport boot. It now waits for the demo state that was
*asked for* — and that matters beyond the hang, because accepting either state
would let a silent fallback back to the demo model satisfy the suite.

### The suite

`tests/e2e_browser_real_transport.py` (13 checks). A turn now really travels:

```
SPA fetch -> studio /messages/stream -> HTTP -> mock -> SSE frames -> studio -> SPA render
```

The checks are written so this cannot pass by accidentally testing the demo path
again — which is the failure mode that would make the whole exercise worthless:

- `/api/config` must report `demo_model: false`;
- the studio's `server_url` must be the mock's;
- the reply must be non-empty **and** carry the mock's `[mock chat reply]` marker;
- the mock must have received the turn, and received it with `stream: true`.

### Mutation-verified

| Mutation | Result |
|---|---|
| the mock stops streaming SSE | **red** — `reply=''`, exactly the pre-fix behaviour |
| `start_studio` ignores `demo_model=False` | **red** — **six** checks, including *"the mock received the turn: 0 completion(s) seen"* |

The second is the one that carries the weight. It proves the suite **cannot pass
while the demo model is in the path**, which is the entire point of the finding. A
green run against a suite that quietly fell back to the demo model would have
looked like coverage and been none.

---

## 17. The 2026-09-21 audit's four open findings — and three corrections to my own work

I said I would close FE-M2 and FE-M3 first because they were small. Measuring them
first was the right order and the wrong expectation: **one was a real defect, one
was not a defect at all, one was mis-framed, and one had a sub-claim that is simply
false.** And three of the mistakes this pass found were in work I had already
written down as verified.

The method was the one from the `audit-claim-validation` skill: read the anchor, not
the summary; decide the claim's type; then try to falsify it. Every verdict below is
a measurement, and each one names the command or the file:line that decided it.

### 17.1 The four, measured

| ID | The audit said | Measured 2026-09-26 | Verdict |
|---|---|---|---|
| **FE-M2** | `state.view` union drifted; `"fv"` dead but still consulted | `app.js:18` read `// "chat" \| "script"` — two legacy aliases, **none of the six live names**. But `"fv"` is documented at `app.js:2140-2142` as a legacy alias that "keeps its ORIGINAL destination", reachable from the URL parser (`app.js:2124`) and a saved payload (`app.js:2047`), with `openFeedbackView()` live at `app.js:7562` | **half right** — comment real, `"fv"` claim refuted |
| **FE-M3** | Undo/Redo unreachable by mouse; `✅ code-verified` | True as an observation, and **intended**. `index.html:206-208` documents it; `git log -S` dates that comment to `f648506` (**2026-09-10**) — eleven days *before* the audit | **not a defect** |
| **FE-L3** | Four abandoned design labs ship, ~26 HTML | 26 is exact (7+7+8+4). But `preview-next/` is **live**: 2 pages call `/api/preview/*`, which has 5 routes and 14 tests. The other three reference it zero times. Shipped cost **660 KB** (33.5%), not 4 MB | **count right, framing wrong** |
| **FE-L4** | ~69 `!important`, ~58 `z-index`, two `:root`, dawn twice | **80** `!important` at HEAD — but **82 at the audit's own revision** (`git show e3b283f:…style.css`), so the audit undercounted by 13 and the debt has gone flat-to-down since. **51** `z-index` (overstated by 7). **2** `:root` (the second self-documenting at `style.css:4770`). `grep -E '^body\.dawn *\{'` → **exactly one** hit | **numbers off both ways, one sub-claim refuted** |

### 17.2 FE-M3 is not a defect, and the proof is a date

The audit labelled this `✅ code-verified`, which is its strongest evidence mark. It
verified the code. It did not read the comment three lines above it:

```html
<!-- Undo/Redo: no visible surface on purpose — keyboard parity
     (Ctrl+Z / Ctrl+Shift+Z) is the contract; the hidden buttons
     stay because the edit-state refreshers drive their .disabled. -->
```

`git log -S "no visible surface on purpose"` returns **one** commit: `f648506`,
2026-09-10 — the baseline, and eleven days before the audit. So the hiding was
documented intent before the audit was written, not an oversight it discovered.

The code agrees. `app.js:5342-5344`, three adjacent lines in one function:

```js
$("#reset-edits-btn").style.display = hasEdits ? "inline-block" : "none";
$("#undo-btn").disabled = !hasEdits;
$("#redo-btn").disabled = !(state.editsData && state.editsData.can_redo);
```

`#reset-edits-btn` starts from the *same* inline `display:none` and JS reveals it.
Undo/redo get only `.disabled`. An author editing those lines in one sitting and
choosing differently is not an oversight — and `app.js:8627` binds Ctrl/⌘ Z to
`undoEdit()` in the views that hold edits, so the keyboard really is the contract.

**And that asymmetry is observed, not inferred.** I read it out of the source first,
which is the weaker proof, so I measured it: seed a project, apply a real edit
through `/edits/apply`, then read the computed styles in one browser.

```
#undo-btn             display=none         box=0x0  HIDDEN
#redo-btn             display=none         box=0x0  HIDDEN
#reset-edits-btn      display=inline-block box=0x0  VISIBLE
#print-btn            display=flex         box=0x0  VISIBLE
```

One toolbar, one starting state, one edit present: JS un-hides `#reset-edits-btn` and
leaves undo/redo hidden. (The `0x0` boxes are the closed overflow menu — the parent
is `display:none` until it opens. The element's *own* computed display is what proves
the reveal, which is the property the guard asserts.) Script:
`.workbuddy-ai/scratch/contrast_runtime_probe.py`.

**The correction to the finding is not "it is fine".** It is that the audit
classified a decision as a bug, and the *next* reader will do the same, because
nothing in the tracker said otherwise until now. So the decision is now pinned:
`tests/test_spa_contract.py` fails if the controls become visible *or* if the comment
explaining why they are hidden is deleted.

### 17.3 The defect the audit missed, in the same feature

The buttons are hidden. The product then told the writer to look at them:

```js
status.textContent = "Applied to the working copy — Undo is in the script toolbar.";
```

`#undo-btn` lives in `#desk-toolbar` — the script toolbar — and is `display:none`.
So the confirmation message for an applied rewrite sent the writer to the one place
the code deliberately never renders. A second site (`app.js:370`) referenced the
hidden button's own glyph (`↶ Undo takes it back`). Both now name the keyboard.

This is the highest-value thing this pass produced, and it is exactly the shape the
skill warns about: **a wrong claim can still point at a real defect — just not the
one it names.** The audit's `file:line` was right and its diagnosis was wrong, and
the real defect sat two thousand lines away in the copy.

### 17.4 FE-L3: I nearly deleted a live feature

I measured the four lab directories at 4.07 MB, computed 76% of the webapp tree, and
started reading `EXCLUDED_FROM_SHIPPING` to reclaim it. Two checks stopped me.

**First, the number was inflated.** 4.07 MB counted 25 + 17 PNG screenshots. The
packaging config excludes PNGs on purpose (`pyproject.toml`: *"Screenshots (\*.png)
are deliberately excluded: they are evidence artifacts, not app assets"*). The honest
figure is **660 KB**, and the honest share is **33.5%**.

**Second, and worse, the premise was false.** `pyproject.toml:53-56` ships them
*deliberately* and says why: the recursive glob exists because *"the preview-\* design
labs are still served by the `/<path:filename>` route and are exercised by
`test_preview_lab.py`"*. `GET /preview-next/index.html` returns **200**. And
`preview-next/` is genuinely live — `webapp_server.py` carries five `/api/preview/*`
routes and `test_preview_lab.py` has 14 tests over them.

Adding all four to `EXCLUDED_FROM_SHIPPING` would have **broken the only consumer of
a tested API**, to save 660 KB. What saved it was checking the *producer* of the
"abandoned" framing rather than the framing: the phrase came from
`CRITICAL_REVIEW_2026-09-18.md:458` — *"not shipped surface"* — which is simply
wrong, and which nothing had re-read in eight days. That claim is now corrected in
place with a dated block, original text left visible.

### 17.5 Three errors in my own work

**1. I reported 4.07 MB / 76% for something that ships 660 KB.** The inflated figure
counted files the packaging excludes. I published it in the previous turn's summary
before checking what actually ships.

**2. My first literal scanner was unsound.** To find copy mentioning undo I ran a
regex for `'...'` over `app.js`. It matched from the apostrophe in a prose comment
(`"the writer's line"`) to the next apostrophe hundreds of lines away and reported
whole code blocks as string literals. It produced a list of "offenders" that were not
copy. **A scan that does not strip comments cannot measure copy** — this is the same
grep-vs-parser error the skill names, and I made it while using the skill. The
scanner is now a small state machine, with `test_the_literal_scanner_does_not_read_comments`
as its own regression test.

**3. My first "permanently hidden" detector was unsound in the other direction.** It
subtracted `.style.display` assignments from inline-hidden ids and reported **20**
controls as permanently hidden. The true answer is **2**: modals are revealed by
`classList` toggles (131 calls), `.hidden` writes (23), and the `openModal` helpers.
An unsound detector is worse than none, so the guard no longer computes the set — it
declares `HIDDEN_BY_DESIGN` and checks each member against every reveal mechanism the
SPA actually uses, plus the stylesheet. `#reset-edits-btn` is kept as the contrast
case that proves the reveal-detection works at all.

**A fourth, smaller one:** my `VIEWS:` extractor first scraped `|`-separated tokens
out of the whole prose comment and got a union missing `compare` and `fv` — because
the joined lines put a `//` in front of one token and an em-dash sentence swallowed
the other. The fix was to stop parsing prose: the comment now carries one
machine-readable `// VIEWS:` line, because **prose is not a data format**.

### 17.6 The guards

`tests/test_spa_contract.py` — 8 tests, 0.1 s, no browser:

| Test | Guards |
|---|---|
| `test_the_view_union_comment_matches_the_source` | FE-M2 — the `VIEWS:` line equals `openViewByName()`'s own literals, plus the else-branch default |
| `test_the_view_union_guard_can_fail` | non-vacuity: a comment missing `compare` is detected |
| `test_the_deliberately_hidden_controls_are_still_hidden[undo/redo]` | FE-M3 — still inline-hidden, unrevealed by JS, and untouched by any non-print stylesheet rule |
| `test_the_hidden_control_detector_can_see_a_revealed_control` | non-vacuity: `#reset-edits-btn` (same inline hiding, *is* revealed) is detected |
| `test_the_reason_for_hiding_travels_with_the_code` | the intent comment cannot be deleted without a red test |
| `test_the_literal_scanner_does_not_read_comments` | the scanner regression above |
| `test_no_user_facing_copy_names_a_location_for_undo_or_redo` | FE-M3b — no copy names a location, **and** the post-apply hint still names the keyboard |

That last pair is deliberate: "no copy names a location" is satisfied by *deleting the
hint*, which would be a regression dressed as a pass. So the test also asserts the
confirmation still tells the writer how to undo.

**No browser check for the hiding, and that is a finding too.** An inline
`display:none` is defeated only by an `!important` rule, so I enumerated all 19
`display:…!important` declarations: 13 are inside `@media print` (they hide, they do
not show) and the six outside it target `.gutter`, `.script-level-notes`,
`.finding-summary` and `#cowrite-panel`. The only rule naming `#undo-btn`/`#redo-btn`
is `style.css:3572`, inside `@media print`. The computed value is therefore
determined by the markup, and a browser would confirm a constant. Saying so is better
than adding a suite that cannot fail.

### 17.7 Mutation-verified

Six mutations, all detected, three files restored byte-identical
(`.workbuddy-ai/scratch/mutation_check_spa_contract.py`):

| Mutation | Result |
|---|---|
| the copy names the toolbar again (the exact defect) | **red** |
| the `VIEWS:` line loses `compare` (the original FE-M2 drift) | **red** |
| `app.js` starts revealing `#undo-btn` | **red** |
| the reason-for-hiding comment is deleted from `index.html` | **red** |
| the post-apply hint is deleted instead of corrected | **red** |
| the literal scanner stops skipping comments | **red** |

M5 is the one worth keeping: it proves the copy rule cannot be satisfied by removing
the message, only by fixing it.

### 17.8 Gates at this revision

| Gate | Result |
|---|---|
| `python -m pytest tests/ -q --cov` | **1835 passed, 3 skipped, 0 failed — 87%** (9775 statements, 1262 missed), exit 0. **+8** over the previous row, all of them `tests/test_spa_contract.py` |
| `python tests/run_browser_suites.py` | **55 suites: 54 passed, 0 failed, 1 skipped — 1343 checks**, exit 0 — **unchanged from the previous row** |
| `ruff check .` | All checks passed |
| `node --test tests/js/core.test.js` | 16 / 16 |
| Mutation harness | **6 / 6 detected**, three files restored byte-identical |

`app.js` is product code that all 55 browser suites load, so **the unchanged fleet
is the load-bearing result here**, not the pytest count: it is the evidence that a
comment rewrite and two copy strings moved nothing else. The static guards are the
cheap always-on half — 0.1 s, no browser — and the fleet is the expensive half that
covers the paths a source check cannot see.

### 17.9 What this pass does not settle

Five things, stated so they are not read as closed:

1. **FE-M3's underlying worry is legitimate even though its diagnosis was not.** The
   audit said "undiscoverable", and I disproved the *bug* framing — but I did not
   measure discoverability. The buttons stay invisible by design, so finding undo now
   rests entirely on the SHORTCUTS table in the command palette. Whether a writer
   actually looks there is a UX question, and "the keyboard is the contract" is a
   design assertion, not a measurement. The copy fix helps only *after* an edit.
2. **The runtime evidence for FE-M3 is not in CI.** The contrast table above comes
   from `.workbuddy-ai/scratch/contrast_runtime_probe.py`, a scratch script. The
   committed guard is a source check. That is the right call for the *hiding* (see
   §17.6 — the computed value is determined by the markup), but it does mean the
   runtime observation would not fail a future build. If the hiding ever becomes
   contentious, the probe belongs in a suite.
3. **FE-L3's three inert labs are still served.** They are unreferenced by the app,
   but `GET /preview-r4/…` answers on loopback. I measured their size and their
   API-reachability, not whether serving them is acceptable. The risk is low — static
   mockups, no API calls — but "unreferenced" and "unreachable" are different words
   and only the first is true.
4. **FE-L4's count is not the same as its cost.** Some of the 80 `!important`
   declarations are load-bearing (the 13 inside `@media print` hide print chrome by
   design). A pay-down plan needs to know *which* are removable; I measured the total
   and the trend, which is the input to that question rather than the answer.
5. **Mutation M6 mutates the test file, not the product.** It proves the literal
   scanner's comment-skipping is load-bearing. It is legitimate — that scanner is the
   thing measuring copy — but "6/6 detected" should not be read as six mutations of
   product behaviour. Five are.



