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

| Gate | Command | Result |
|---|---|---|
| Unit + integration | `python -m pytest tests/ -q --cov` | **1779 passed, 3 skipped, 0 failed — 87%** (9730 statements, 1287 missed), exit 0 |
| Browser E2E | `python tests/run_browser_suites.py` | **51 suites: 50 passed, 0 failed, 1 skipped, 0 known-broken — 1257 checks**, exit 0 |
| Lint | `ruff check .` | **All checks passed** |
| JS unit | `node --test tests/js/core.test.js` | **16 / 16** |
| Mutation harness | `.workbuddy-ai/scratch/mutation_check_r4.py` | **7 / 7 detected**; tree restored byte-identical |

Two rows carry the weight:

- **The 1,235 pre-existing browser checks are unchanged and all still pass.** That
  is the claim that needed proving: the edit cycle went from two critical sections to
  one, the SPA gained announcement plumbing, and a security tripwire's classifier
  changed — and nothing else moved. The 22 new checks are `live_regions` (14) and
  `two_contexts` (8).
- The one skip is `gun_pen_audit`, printed with its reason: *"runs a real analyze —
  needs a llama-server, so E2E_BASE must point at a studio that has one"*.

Against the round-3 baseline (**1771 passed / 49 suites / 1235 checks**):
**+8 pytest tests** (4 cycle-continuity, 4 apply-race), **+2 suites**, **+22 checks**.

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
| **BE-3 `StoreLockTimeout` → 500** | MEDIUM | **open** — should be 503 + `Retry-After`; the fix that introduced the contention also made this reachable |
| **BE-4 403 recovery copy** | LOW | **open** |
| **BE-5 over-strict loopback spellings** | LOW | **open** |
| **BE-6 session metadata last-writer-wins** | LOW | **open** — `store.save` merges messages only |
| **UX-2 viewport breadth** | MEDIUM | **open** — most suites still run at one viewport |
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
