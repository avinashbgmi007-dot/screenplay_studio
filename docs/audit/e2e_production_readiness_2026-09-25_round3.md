# E2E & Production-Readiness Audit — Round 3

**Revision audited:** `cefe08a` on `qoder/update` (clean tree, 6 commits since the pre-fix `eccbdca`)
**Date:** 2026-09-25
**Scope:** the landed fix set (`eccbdca..HEAD`) — its e2e alignment, its guards, and the defects it
introduced or left behind.
**Code written:** none. Every probe ran from `.workbuddy-ai/scratch/`. No tracked file was modified.

---

## 1. Verdict

**The fix set is high quality and materially better than any previous round — and it leaves one
data-loss defect on the commonest write path, which I reproduced deterministically.**

The 6 commits close the two HIGH findings from the 2026-09-24 audit (the Host-header read exposure and
the unguarded loopback bind), rewrite the edit-cycle lock topology correctly, and add **14 test files**
(6 browser suites and 8 pytest modules — `git diff --diff-filter=A`). A mechanical sweep of every new
suite finds **no vacuous assertions among the new files** — a first, after two rounds in which "checks
that cannot fail" were the recurring defect. (A corrected sweep did find **8 pre-existing
marker-only checks in `e2e_browser_ui_batch.py`**, each echoing an assertion made on the line above —
see UX-5. My first sweep missed them because it only inspected the first argument; `check(name, cond)`'s
constant sits second.)
`tests/e2e_browser_xss_inert.py` even refuses to fake a payload for the two pacing-SVG sinks and
asserts the *convention* instead, documenting why.

But: **`POST /edits/apply` still performs its read-modify-write in two separate critical sections**, so
two concurrent applies lose one edit's text while both records stay in the log. Commit `ab48b21`
("One write cycle, one critical section") covered `undo`/`redo`/`reset`/`ensure_working` — it did not
cover the route, which does its own `load_working` outside `save_working`. I reproduced the divergence in
two threads of one process and in two OS processes, measured the rate with nothing slowed
(**295/300 = 98.3% for two tabs, 126/300 = 42.0% across two processes**), and then reproduced it **end to
end through the shipped product — two browser windows, the SPA's own request path: 40/40 = 100%**, with
the request overlap independently confirmed. This is the exact defect class the commit claims to close, on
the path a writer uses every time they accept a rewrite — and `/edits/apply` is the one route that fails
to follow a convention `notes`, `stash`, `ideas`, `revision` and the co-writer store all implement and
document.

A second, smaller point: the guard written to prevent this class of bug — `tests/test_lock_order.py` —
is **structurally incapable** of catching this instance of it, because it validates the *order* of
acquisitions and a two-section cycle never nests.

---

## 2. Gates, measured at this revision

| Gate | Result | vs. previous round |
|---|---|---|
| `pytest -q --cov` | **1771 passed, 3 skipped, 0 failed — 87%** (9722 stmts, 1287 missed), exit 0, 3m11s | 1749 → **1771** |
| `tests/run_browser_suites.py` | **49 suites: 48 passed, 0 failed, 1 skipped, 0 known-broken — 1235 checks, exit 0** | 48 suites / 1175 checks |
| `ruff check .` | clean (verified last round; unchanged) | — |
| New test files | **14 added** (6 browser suites + 8 pytest modules) | — |
| Vacuous-check sweep (AST, all 50 browser files) | **0 in the new files**; **8 pre-existing marker-only checks in `ui_batch`** (UX-5). 32 calls carry a literal `False` — all legitimate failure branches with a detail message | was 3 (`gun_pen_audit`, since replaced) |

The one skip is `gun_pen_audit`, with its reason printed: *"runs a real analyze — needs a llama-server,
so E2E_BASE must point at a studio that has one"*.

The two `RuntimeWarning`s are unchanged from last round and are documented trade-offs, not new defects:
the `character` KB fragment at 65,226 chars against a 40,000 soft ceiling, and a prompt budget of 8,513
that the irreducible context (~8k) cannot fit — the second is raised *by* a test that asserts the honest
warning.

---

## 3. Backend findings, highest impact first

### BE-1 — HIGH (BLOCKER). `POST /edits/apply` is not atomic: an edit is lost and the log lies about it

**Location.** `screenplay_studio/webapp_server.py:1819-1827` —

```python
doc = load_working(m)          # takes lock_for(working.json), RELEASES it
result = apply_replacements(doc, scene_number, replacements)   # in memory
if result["applied"]:
    save_working(m, doc, record={...})   # takes lock_for(working.json) AGAIN
```

Two critical sections. `ensure_working` acquires and releases the cycle lock *inside* `load_working`,
so between the read and the write the lock is not held. This is the shape `AGENTS.md` forbids in
writing: *"a load-modify-write must hold that lock across the **read**, not only the write."*

**Reproduction — structural proof.** `.workbuddy-ai/scratch/apply_race_probe.py` puts a barrier between
the read and the write so both writers are guaranteed to have read before either writes:

```
--- TWO THREADS, one process (two tabs, threaded=True) ---
  edits.json ids        : ['eB', 'eA']
  scene 1 carries edit A: True
  scene 2 carries edit B: False
  VERDICT: DIVERGED — a record is in the log but its text is gone

--- TWO OS PROCESSES (the documented CLI + webapp case) ---
  edits.json ids        : ['pA', 'pB']
  scene 1 carries edit A: False
  scene 2 carries edit B: True
  VERDICT: DIVERGED — a record is in the log but its text is gone
```

**Reproduction — reachability.** A barrier I imposed would only prove the defect is *possible*, so I
re-ran it with **no barrier, nothing slowed, nothing widened**: just two concurrent applies, 300 times,
counting how often `edits.json` and `working.json` end up disagreeing
(`.workbuddy-ai/scratch/apply_race_calibration.py`):

```
TWO THREADS (two tabs, threaded=True): 295/300 diverged (98.3%)
TWO OS PROCESSES (CLI + webapp):       126/300 diverged (42.0%)
```

**98.3%.** The window is not narrow: `save_working` serializes the whole document to JSON, fsyncs and
renames while the *other* writer is already between its own read and its own write. Two tabs open on one
project is all it takes.

**Reproduction — end to end, through the product.** Both of the above call the library directly, so
neither proves a *writer* can hit it. `.workbuddy-ai/scratch/e2e_apply_race_probe.py` boots the shipped
studio, opens the sample project in **two independent browser contexts** (two cookie jars — two windows),
and has both pages accept an edit on a different scene at the same wall-clock instant, using the SPA's
own `api()` (token header, 403 retry and all):

```
TWO BROWSER CONTEXTS, SPA's own api(), 40 iterations
  requests genuinely overlapped: 40/40  (100%)
  diverged (an edit lost):       40/40  (100.0%)
  iter 0: A=LOST B=yes
  iter 1: A=yes B=LOST
  iter 2: A=yes B=LOST
```

**100%, every time, with the overlap independently confirmed** — so this is not a vacuous result reading
a serialised run as a clean one (see §7; my first version of this probe did exactly that). Two windows on
one project lose an accepted rewrite on essentially every concurrent pair.

**Why the thread leg matters.** `webapp_server.py` runs `app.run(threaded=True)`, so **two browser
tabs are two threads in one process** — no second process, no CLI, nothing unusual. The scenario is
"the writer has the desk open twice", which is exactly what a multi-monitor writer does.

**Consequence.** `edits.json` carries a record whose text is not in `working.json`. Undo of that record
cannot restore anything (`_replace_in_scene` finds no exact match, so it lands in `failed`), and the
writer is never told. The screenplay is irreplaceable and there is no server-side copy.

**Why no guard caught it.** `tests/test_undo_redo_lock_race.py` races an *undo/redo cycle* against an
apply; nothing races **apply against apply**. And `tests/test_lock_order.py` cannot see it — see E2E-1.

**The repo already has the fix, twice, with the reasoning written down.** This is not an unsolved design
problem; `/edits/apply` is the one route that does not follow a convention the rest of the codebase
implements and documents:

| Where | How it holds the cycle | Its own note |
|---|---|---|
| `notes.py:38-46` `_locked(m)` | lock across the read | *"hold it across the READ so a racing add/update/delete … cannot clobber a note it never saw. Measured before this: two concurrent adds left ONE note on disk"* |
| `stash_store.py:68-79` `_locked(project_dir)` | lock across the read | *"hold it across the READ so a racing save … cannot clobber an entry it never saw"* |
| `ideas.py:87-97` `_modify()` | `with lock_for(...)`: load → mutate → write | *"a racing save can't clobber fields the writer didn't send"* |
| `revision.py:409/525/578` apply · undo · redo | one `with lock_for(wp)` per cycle | the P1-3 topology note |
| `screenplay_cowriter/store.py:65-113` `save()` | lock, **re-read, union missing messages**, write | *"the load that produced `session` happened OUTSIDE it, so a stale in-memory snapshot would overwrite (lose) messages a faster turn already saved (H4)"* |

The last row is the closest analogue and it is the strongest evidence that the authors understood this
exact hazard: the co-writer store does not merely hold the lock, it **merges on write** so a stale
snapshot cannot drop a turn. `/edits/apply` has the same shape and neither defence.

I checked the other 19 routes an AST pass flags for "reads then writes" (`webapp_server.py`), and none of
them loses **script text**: `notes`/`stash`/`ideas` delegate to the locked helpers above,
`save_project_premise` holds `lock_for` itself, and the session routes go through `store.save`. So
`/edits/apply` is the only instance that can destroy the writer's pages — which also makes the fix small.
One narrower instance of the same class does remain, on session metadata rather than the script: see
BE-6.

**Fix.** Hold `lock_for(working_path(m))` across the route's load → apply → save, or (cleaner, and it
matches the module's existing shape) add a locked `apply_edit(m, scene_number, replacements, record)` in
`revision.py` and have the route call only that. The route must not call `load_working` itself. The
merge-on-write pattern from `store.py` is the alternative if you would rather not widen the critical
section.

**Guard.** A test that races two applies — with a control asserting the two requests actually overlapped,
so it cannot pass vacuously — asserting that every id in `edits.json` has its text in `working.json`. That
is the same assertion `test_undo_redo_lock_race.py` already makes, applied to the pair it does not drive.

---

### BE-2 — HIGH (delivery). The fixes are committed but **not pushed**; the remote branch still leaks

`git ls-remote` — the only trustworthy proof a push landed — reports:

```
f14fd04...  refs/heads/main
eccbdca...  refs/heads/qoder/update      <-- the PRE-FIX tree
```

Local `qoder/update` is `cefe08a` (6 commits ahead). So the branch others clone, review or deploy still
carries the unpatched server: `_reject_foreign_host` absent, `_reject_cross_origin_writes` still
early-returning for `GET`, and `GET /api/projects/<name>/script` with a foreign `Host` still returning
the writer's screenplay in full. This was flagged last round and is still open. One command fixes it;
nothing else in this report matters until it is done, because the fix is not the artefact anyone can see.

*(Also observed, and needing your confirmation rather than a verdict: local `main` is 15 commits ahead of
`origin/main`. That may be intentional branch strategy — I am not calling it a defect.)*

---

### BE-3 — MEDIUM. `StoreLockTimeout` has no error handler, so contention reads as a crash

`jsonio.StoreLockTimeout` is raised when a store lock is held past `LOCK_TIMEOUT_SECONDS = 10.0`. It
subclasses `RuntimeError`, and `webapp_server.py` registers handlers for `ValueError`, `StoreUnreadable`,
413 and `Exception` — **not** for `StoreLockTimeout`. So it lands in `_unhandled` (`:545`) and becomes a
generic 500.

Reproduced live (mine and independently by a second agent, raw output agreeing):

| Route | Contended | Elapsed | Body |
|---|---|---|---|
| `GET /api/projects/<n>/script` | **500** | **10.018s** | `{"error":"Unexpected error: timed out after 10s waiting for another process to release working.json"}` |
| `GET /api/projects/<n>/export` | **500** | 10.015s | same |
| `POST /api/projects/<n>/edits/apply` | **500** | 10.018s | same |
| `GET /api/projects/<n>/fixqueue` | 200 | 0.005s | — |
| `GET /api/projects` · `/api/health` · `/` | 200 | ≤0.02s | — |

No `Retry-After`. The SPA retries only on 403 (`app.js:119`), so a 500 is terminal for that interaction.

**This exposure was created by the fix.** Pre-fix `save_working` wrote `working.json` with *no lock*
(`git show ab48b21^:revision.py:343`) and only then took the *edits* lock — so an apply never contended
with a read. Now apply and read share one lock, and `ensure_working` takes the **exclusive** lock on
every `load_working`, i.e. on a plain GET.

**Honest severity.** An independent measurement (separate agent, raw numbers) puts realistic-load
reachability at nil: a 1KB script holds the cycle lock ≈0.4s; a 5.7MB source (30MB working copy) 3.13s
for an apply and 5.49s for a rebuild; you need a ~50MB+ working copy (≈10MB source, ≈5000 pages) to
reach 10s by load alone. In-process contention cannot 500 at all — two threads serialize on the
in-process `RLock`, which is acquired with no timeout; the 500 requires a **separate process**. So this
fires essentially only when a holder is genuinely stuck, which is the case the timeout was designed to
bound. I have kept it at MEDIUM not because the trigger is likely but because the *classification* is
wrong, the blast radius includes the two routes that render the writer's script, and the fix is a few
lines: an `@app.errorhandler(StoreLockTimeout)` returning **503 + `Retry-After`** with a sentence the
writer can act on. That is the same standard the codebase already holds for `StoreUnreadable → 503`
("reported as damage, never as 'you have none'"). If you weigh reachability over classification, this
is a LOW.

**Amplifier worth fixing in the same pass:** `reset_working` (`revision.py:443-450`) holds the cycle
lock while calling `_remove_with_retry` on three stores, and each of those acquires its own leaf lock
with an *independent* 10s budget — so one call can hold the cycle lock for up to ~30s, and a leaf's
timeout raises uncaught out of a nested wait. The budgets are not composed.

---

### BE-4 — LOW. The 403 recovery copy is wrong for a Host-guard refusal

`app.js:139-146`: any non-retryable 403 shows *"The studio restarted… Reload this page."* But a 403 can
also come from `_reject_foreign_host` (`webapp_server.py:274`), where reloading cannot help. The advice
is confidently wrong for that case.

### BE-5 — LOW (NIT). The Host guard over-rejects some valid loopback spellings

`127.1`, `2130706433`, `0177.0.0.1`, `0x7f000001` are all legitimate `inet_aton` forms of loopback and
are refused (as is `0.0.0.0`). No modern browser emits these in a `Host` header, so this is a
completeness nit, not a defect. Everything that matters is right — see §4.

### BE-6 — LOW. The co-writer store's merge covers messages but not session metadata

`screenplay_cowriter/store.py:99-113` `_merge_missing_messages` unions **branch messages** only — keyed on
`(branch, role, content)`. Session-level metadata is not merged, so it is last-writer-wins on the
in-memory snapshot: `switch_branch` sets `session.current_branch` (`webapp_server.py:3021`) and
`update_settings` sets persona/mode, then both call `store.save(session)`. A concurrent pair — or either
racing a chat turn — can therefore lose the *selection*, because the stale snapshot's metadata overwrites
what disk holds.

Impact is low and I want to be precise about why: it loses a persona/mode/branch choice, never script text
or a chat message, and it self-corrects the next time the writer picks. It is worth recording because the
store's own comment claims to have closed this class (*"a stale in-memory snapshot would overwrite (lose)
messages a faster turn already saved"*) and it has closed it for exactly one field family. If the merge is
ever generalised, this is the case it needs to cover.

---

## 4. UI/UX findings, highest impact first

### UX-1 — MEDIUM. Errors and chat replies are never announced; the live region built for them is idle

`#error-banner` (`index.html:23`) has no `role="status"` and no `aria-live`. Neither does
`#messages-scroll` (`:401`). So a blind writer is told nothing when a save fails or a reply arrives.

The infrastructure exists and is under-used. `#a11y-status` (`:241`) is a dedicated
`role="status" aria-live="polite"` region, and `index.html:235-239` states the design intent
explicitly: the manuscript container is *not* a live region because re-announcing the whole manuscript
on every edit was wrong, and *"status feedback lives in the dedicated `#a11y-status` region below."* In
fact `#a11y-status` is written by exactly one function — `announceManuscriptLoad()` (`app.js:5125-5134`)
— and carries only the scene count. Errors and incoming chat never route to it.

WCAG 4.1.3 (Status Messages) is Level AA. This is the one AA gap I found that is both real and
reachable, and it is unguarded: **no test in the repo asserts any live region** (`#error-banner` is
widely *read* by suites for its text and visibility, never for its announcement semantics). It was
flagged in the previous round's P5-14 and the contrast half was fixed while this half was not.

**Fix.** `role="status"` on `#error-banner` (or route `showError()` through `#a11y-status`), and a
polite live region for the chat stream. **Guard.** An assertion that the region carries the attribute
*and* that a failed write populates it — a presence check alone would be the vacuous shape this repo
forbids.

### UX-2 — MEDIUM. Responsive coverage is thin: one viewport for the whole fleet

`tests/e2e_browser_common.py:485-498` — the shared `launch()` helper every suite goes through —
hardcodes **1440×900**. Only **6 of 49 suites** call `set_viewport_size` to override it;
`phase11_responsive` is the only suite that covers a breakpoint ladder (1024 and 390). Consequences:

- No suite runs a **short viewport** (a 1366×768 laptop, or 1440×720) — the layout most likely to clip
  the dock, the status strip or the manuscript's vertical rhythm.
- No **touch / `pointer: coarse`** emulation, so no mobile gesture path is exercised at all.
- No mobile **landscape**.

The product is a writing desk that advertises a three-zone shell and a docked room panel; those are
precisely the things that break at narrow widths and short heights.

### UX-3 — MEDIUM. No e2e test has ever opened a second browser context

`launch()` creates exactly **one** context and one page, and no suite creates a second. So the
multi-writer reality — two tabs, or the documented CLI + webapp over one project directory — is
untested at the browser level. `race_guards` is genuinely good, but it simulates its races by holding a
request on the wire inside a single page; it tests the SPA's *state* races, not server-side contention.

This is the coverage reason BE-1 survived: the defect needs two writers, and no test has two.

**Recommendation.** One suite, two contexts on one project, driving an edit from each, asserting the
script and the log agree afterwards. It would have caught BE-1 and would catch its regression.

### UX-4 — LOW. The three de-vacuumed checks live in a suite that never runs

Commit `25aacf8` replaced three `check(name, True)` calls in `tests/e2e_browser_gun_pen_audit.py` with
real conditions (`check("pass2: analysis completed", completed)`, etc.). That file is the **one skipped
suite**, so those three checks have never executed — in CI or locally. The replacement is verified by
reading, not by running. The work is correct; its *value* is currently zero. Either provide a
`llama-server` path for it or move those three assertions into a suite that runs.

### UX-5 — LOW. Eight checks in `e2e_browser_ui_batch.py` assert nothing

`Checks.ok` is `def ok(self, name, cond=True, detail="")` (`e2e_browser_common.py:77`) — **`cond`
defaults to `True`**. Eight calls in that suite pass only a name:

```
tests/e2e_browser_ui_batch.py:65,68,77,90,95,114,123,132
  ok("flyouts collapsed on load")   ok("hover opens the Ideas flyout")   ... etc.
```

I read each one in context, and **none is a coverage hole**: every one is immediately preceded by a real
`expect(...)` or `assert` that would fail loudly (`:64` `expect(...).to_be_hidden()` → `:65`; `:76`
`assert "brass key" in val` → `:77`; and so on). So the guarantee is intact.

Two reasons it still matters. First, it **inflates the reported total** — 8 of the fleet's 1235 checks
verify nothing. Second, it is the *same shape* as the three checks commit `25aacf8` had to fix in
`gun_pen_audit`, where the author's own note says the check "merely echoed the loop condition". Delete
the preceding `expect()` and these eight stay green while the behaviour goes unchecked. The cheap fix is
to fold the condition in (`ok("flyouts collapsed on load", page.locator("#idea-list").is_hidden())`) or
drop the marker.

*(This is also a correction to my own first sweep: it inspected only `args[0]`, so it missed
`check(name, True)`-shaped calls where the constant is the second argument. A vacuous-check sweep has to
read every argument position **and** the helper's default — otherwise it reports a clean bill of health
it has not earned.)*

---

## 5. E2E alignment: why the guard did not catch the bug

### E2E-1 — MEDIUM. The new lock-order guard is blind to a two-section cycle

`tests/test_lock_order.py` is well built: it monkeypatches `jsonio._lock_for` with a traced wrapper,
asserts the permitted nesting pairs, asserts the forbidden `log → working` direction, asserts same-path
reentrancy stays legal, asserts nothing is left held, and **self-tests** (it turns red on a deliberately
forbidden nesting). That last property is the mark of a real guard.

But it enforces the **order** of acquisitions. A route that acquires `working.json`, releases it, and
acquires it again later produces two legal sequential acquisitions — no nesting, so no violation, and
`test_lock_order.py:204` drives exactly that shape through `_apply()` without complaint. The invariant
that was actually broken is *"the read and the write are in the same critical section"*, and no test
asserts it.

**Recommendation.** Add an assertion that spans the route: trace `_lock_for` across a real
`POST /edits/apply` and assert that one continuous hold of `working.json` covers both the load and the
save (e.g. no `working.json` acquisition occurs while the document is "between" a load and a save).
Stating the invariant in `AGENTS.md` is not enough — the repo's own standard is that a guard which
cannot fail is a defect.

### E2E-2 — LOW. The residual is documented in the wrong place, against the repo's own convention

`tests/test_undo_redo_lock_race.py:203-207` records that *"an apply whose stale whole-file write
resurrects already-undone text — is a caller-level load-then-save hazard this fix does not claim to
close."* That is honest, and it is the same hazard I reproduced (I proved the apply-vs-apply direction;
the comment covers the apply-vs-undo direction). But:

- `docs/audit/FIX_TRACKER.md` states the convention: *"An item that is real but needs a design decision
  goes to **Proven, deliberately NOT fixed** with its evidence — never quietly implemented inside
  another fix"* and *"Findings discovered while fixing an item are added as new rows, never folded
  silently into the item that surfaced them."*
- The hazard appears in no residual list, no audit doc and not in `AGENTS.md`. A test comment is not
  where a data-loss residual belongs — nobody reading the tracker or the report will find it.

By the repo's own rules this is a process defect, independent of the code fix.

### Coverage that is genuinely good, and should be left alone

- `e2e_browser_xss_inert.py` plants distinct payloads per sink and asserts each renders as text, and
  refuses to fake a payload where one is unreachable (the two pacing SVGs) — asserting the convention
  instead and saying why. My own census flagged 17 "possibly unescaped" sinks; reading them showed
  almost all are **static string literals** (`EXPLORE_CHIPS` at `app.js:3785` is a hardcoded array,
  `api-key-hint`, the chat empty-state copy). No live XSS. I am recording the false positive so nobody
  re-derives it.
- `e2e_browser_session_breaks.py` covers mid-session server death, token re-mint recovery with no
  writer-facing error, the cookie updating, a write against a dead server producing a readable sentence
  rather than the internal token string, and `confirm()`-Cancel leaving `notes.json` byte-identical.
- `e2e_browser_modal_guards.py` covers focus traps, one-Escape-one-rung, and file-drag defaults.
- `test_security_hardening.py` covers the 304 cookie re-issue, non-ASCII and lone-surrogate tokens,
  and the stream route's 403 JSON contract.
- `test_route_coverage.py` still asserts every route is exercised or declared, with a self-test that
  the recorder is wired.

---

## 6. Verified fixed (so the report is not read as uniformly negative)

| Previous finding | Verification |
|---|---|
| **BE-1 (2026-09-24)** DNS-rebinding read exposure | `_reject_foreign_host` refuses foreign `Host` on **every** surface I could reach: the SPA document, a static asset, an **unmatched path** (403 before 404 — so `before_request` does run pre-dispatch), an API read, and the script route. 12 `Host` variants: `evil.attacker.com`, `evil.attacker.com:8661`, `localhost.evil.com`, `127.0.0.1.evil.com`, `evil.com@127.0.0.1`, `0.0.0.0` → all 403; `localhost`, `localhost.`, `localhost.:8661`, `127.0.0.1:8661`, `[::1]:8661`, `127.0.0.2` → all 200. The guard parses (`urlparse`) rather than prefix-matches, and defers to `net_guard.is_loopback_host` — no second enumeration of "local". |
| **E2E-1 (2026-09-24)** the bind had no guard that could fail | `_LAST_RUN_KWARGS` now captures `app.run(**kw)` and asserts `host == "127.0.0.1"`, `debug is False`; a behavioural test boots the shipped server and asserts it is unreachable on the LAN address, with a `0.0.0.0` control socket so it cannot pass vacuously. |
| **dawn `.sev-dot.low` contrast** | `style.css:3150` now reads `var(--ok)` instead of the hardcoded `#46a758`, and the stale override line is gone from `tungsten.css`. Re-measured arithmetically over the same four dawn backdrops: **5.23 / 5.40 / 6.44 / 6.09 : 1** — all pass 3:1. The old literal measures **2.41 / 2.50 / 2.98 / 2.81 : 1**, i.e. this method reproduces the previously rendered-pixel 2.41 exactly, so the fix is real and the 3:1 failure is gone. (Not re-sampled on the painted pixel this round — arithmetic only, and the dock backdrop is the value the pixel probe returned last round.) |
| **The three vacuous checks** | Replaced with real conditions — though see UX-4: they live in the skipped suite. |
| **Lock topology** | Sound. `lock_for(working.json)` is the single cycle anchor; `edits.json`/`edits.redo.json` are reached only as leaves via `atomic_write_json`/`load_json_store`/`_remove_with_retry`, and nothing acquires `working` while holding a leaf. No wait-for cycle. `AGENTS.md`'s rule was rewritten to match reality rather than the code being bent to a wrong doc — the correct call, and the new wording is testable. |
| **`has_edits()` unlocked read** | Benign. `edits.json` is only ever written under the `working.json` lock and by atomic rename, so the read cannot tear, and both failure branches are conservative (`→ True`, preserving the working copy). |
| **The SPA's 403 retry** | Safe. Every 403 originates in a `before_request` guard, so no view body can have mutated state before the retry; the retry re-sends an identical body. This rests on "no view ever returns 403" — true today, worth a comment. |
| **`set_order` schema tightening** | No caller breaks: the SPA sends `bbOrder.slice()` from a list of ints. |
| **`innerHTML` escaping** | No live XSS found. 64 assignments, 19 content-bearing, and the data-bearing ones carry `escapeHtml`/`formatMessageContent`; the rest are static literals. |

---

## 7. What I did not verify — stated plainly

1. **I did not mutation-test the new guards this round.** You forbade writing code, and mutation
   testing requires temporarily reverting a fix. So "each new guard can fail" is supported by reading
   (`test_lock_order.py` self-tests; `test_host_header_guard.py` asserts behaviour, not source text; my
   sweep found no vacuous conditions) and by my own live probes — but not by a red-witnessed mutation.
   That is the one assurance step I would add next.
2. **The `gun_pen_audit` suite remains unexercised**, so anything only it asserts is unproven.
3. **`test-windows` in CI has still never run.** I cannot execute GitHub Actions. Its selection passes
   on this Windows machine.
4. **The lock-timeout reachability numbers are the second agent's measurements**, not mine; I
   reproduced the 500 and the elapsed time, and I am reporting their load-scaling figures as theirs.
5. **The `fcntl` branch of `_acquire_os_lock` is untested here** — this is a Windows host, so only the
   `msvcrt` path executed.
6. **BE-2 rests on `git ls-remote`**, which is authoritative for what the remote holds. I did not test
   whether anything actually consumes that branch.

### Corrections I made to my own work while writing this

- **I nearly under-called BE-1.** My first reproduction used a barrier I imposed between the read and
  the write, which proves a defect is *structurally possible* but says nothing about how often it
  happens. I then measured it with nothing slowed and nothing widened: **98.3%**. Had I stopped at the
  barrier, I would have described a certain, near-always data loss as a theoretical race.
- **I miscounted the new tests.** I wrote "8 browser suites + 12 pytest files" from the diff stat
  before checking. `git diff --diff-filter=A` gives **14 added test files: 6 browser suites and 8
  pytest modules.** Corrected above.
- **I overstated the viewport claim** as "43 of 49 suites run at 1440×900" before confirming that the
  remaining suites all route through the same helper. The defensible statement is that `launch()`
  hardcodes it and only 6 suites override — corrected above.
- **A census false positive I am recording so nobody re-derives it.** My `innerHTML` sweep flagged 17
  "possibly unescaped" sinks. Reading each one showed they are **static string literals** — the
  `EXPLORE_CHIPS` array at `app.js:3785` is hardcoded markup, as are the API-key hint and the chat
  empty-state copy. There is no live XSS. A grep-first census over-reports; this is the second time in
  this repo that pattern has produced a wrong number.
- **My vacuous-check sweep was wrong in the other direction.** I first reported "0 hits" from a sweep
  that only looked at the *first* argument — so it could not see `check(name, True)`, where the constant
  is second, which is exactly the shape the previous round had to fix. The corrected sweep (every
  argument position, plus the helper's default) found 8 marker-only checks in `ui_batch` and 32
  legitimate failure branches. **A sweep that cannot see the defect shape it is looking for is the same
  defect it is looking for.** Recorded as UX-5.
- **My first end-to-end race probe was itself vacuous, and it reported a clean result.** It called
  `page.evaluate(APPLY_JS, …)` for page 1 and then page 2 — but `evaluate` does not return until its
  promise resolves, so page 2's request started only after page 1's had finished. The two applies were
  serialised and the probe printed **0/40 diverged** on a defect that is otherwise 98% reproducible. I
  caught it only because a 0% result was implausible next to the library measurement. The fix — dispatch
  without awaiting, then poll — also needed a **control**: the probe now records each request's start and
  end and reports `requests genuinely overlapped: 40/40`, so a future 0% cannot be read as "no bug" when
  it means "no race". This is the third time in this repo that a probe's *shape* was the finding.

---

## 8. Recommended order

1. **Push** (`BE-2`). The fix is not the artefact anyone can see, and the remote branch is the
   vulnerable tree. One command; nothing below matters until it is done.
2. **`BE-1`** — one lock across the apply route's read-modify-write, plus the apply-vs-apply race test.
   This is data loss on the writer's irreplaceable script and it is reachable from two tabs.
3. **`E2E-1`** — an assertion that a route's read and write share one critical section. Without it the
   same bug returns the next time someone adds a route.
4. **`UX-3`** — a two-context suite. It is the guard that would have caught BE-1 and the one the
   product's own multi-writer model needs.
5. **`UX-1`** — the live regions, with a guard that asserts announcement, not presence.
6. **`BE-3`** — the `StoreLockTimeout` handler (503 + `Retry-After`) and composed leaf budgets.
7. **`E2E-2`** — move the apply-route residual into `FIX_TRACKER.md` and the audit report, where the
   repo's own convention says residuals belong.
8. **`UX-2`, `UX-4`, `UX-5`, `BE-4`, `BE-5`, `BE-6`** — viewport breadth, the skipped suite's three
   checks, the eight marker-only checks in `ui_batch`, the recovery copy, the over-strict loopback
   spellings, and the metadata half of the co-writer merge.
