# Screenplay Studio — Production-Readiness Implementation

**Date:** 2026-09-24 · **Implements:** `docs/audit/production_readiness_2026-09-24.md` §8
**Status:** all six ranked items closed, each with a guard that was **mutation-verified** (reverted, watched go red, restored by sha256).

> The audit found two HIGH gaps and four MEDIUMs. This document records what was actually changed, the evidence that it works, and the two places where my *own* claims did not survive review.

---

## 0. What shipped

| # | Finding | Change | Guard added | Mutation result |
|---|---|---|---|---|
| 1 | **E2E-1 (HIGH)** the loopback bind had no guard that could fail | `test_capability_token._launch` now **captures** `app.run(**kwargs)`; new test asserts `host == "127.0.0.1"` and `debug is False` | `test_the_shipped_launch_binds_loopback_and_nothing_else` | flip to `0.0.0.0` → **2 failed** |
| 2 | **BE-1 (HIGH)** any `Host` header accepted; a rebinding page read the screenplay | `@app.before_request _reject_foreign_host()` + `_host_header_is_local()`, 403 on any non-loopback `Host`, every method | `tests/test_host_header_guard.py` (45 assertions) | remove guard → **28 failed**; make predicate always-true → **23 failed** |
| 3 | **E2E-2 (MED)** packaging guard asserted archive *membership* | "Layer 4": `pip install --target` the wheel, import the KB from it, boot it from a **neutral cwd with the repo root off `sys.path`**, assert `GET /` + 4 assets are 200 | `test_installed_wheel_loads_the_whole_knowledge_base`, `test_installed_wheel_serves_the_spa` | drop the KB from `package-data` **and** `MANIFEST.in` → **5 failed** |
| 4 | **BE-2 (MED)** an empty knowledge base was silent | `RulesContext.rule_count()` + `pipeline._empty_kb_message()`; `analyze()` appends a visible `result.errors` entry | `tests/test_empty_kb_guard.py` | suppress the message → **2 failed** |
| 5 | **BE-3 (MED)** no logging anywhere in the shipped packages | `screenplay_studio/logsetup.py` (rotating file beside the projects dir) + wired into `main()` and the 500 handler | `tests/test_logsetup.py` | — (see §3.3) |
| 6 | **BE-4 (MED)** the shipping platform absent from CI | `test-windows` job running the store/lock/delete tests | — | selection **run on Windows locally**: 187 passed / 3 skipped |
| 7 | **UX-1 (MED)** no URL — no deep links, and Back exited the app | hash router derived from `state`, push on view/project and replace on scene, `openViewByName()` as the one dispatch table, `correctRoute()` for a stale address, `fromNavigation` for the empty route | `tests/e2e_browser_deep_links.py` (24 checks) | 4 mutations, all red: **28 / 6 / 4 / 2** failures |
| 8 | **UX-2 (LOW)** DPR never varied in the gate | DPR 1 vs DPR 2 layout invariance, with the DPR reading asserted so it cannot compare DPR 1 to itself | `tests/e2e_browser_render_scale.py` (13 checks) | a device-pixel-derived size → **2 failed** |
| 9 | **E2E-5 (LOW)** coverage never measured, no floor | `[tool.coverage.run] source` + `fail_under = 85`; CI runs `pytest -q --cov` | measured **87%**; verified a subset run exits 1 | — |
| 10 | **P-2 (LOW)** root scratch broke the lint job | `/.tmp_*/` in `.gitignore` | `ruff check .` now passes | — |

Plus: **E2E-3 #1** — the dead source-text assertion was replaced (it is item 1 above), and the redundant `status_code == 200` condition on the token cookie.

Not reached: **E2E-4** (a browser suite against a real/mock `llama-server`) — see §7.

---

## 1. Evidence (executed, not inferred)

| What | Before | After |
|---|---|---|
| `pytest tests/ -q` | 1684 passed / 3 skipped / 0 failed | **1749 passed / 3 skipped / 0 failed** |
| `pytest -q --cov` (what CI now runs) | not run anywhere | **87% (9699 statements, 1291 missed), floor 85 enforced** |
| `python tests/run_browser_suites.py` | 46 suites, 45 passed, 1138 checks | **48 suites — see §1.1** |
| `ruff check .` (the CI lint command) | 2 errors, from untracked scratch | **All checks passed** |
| Mutation harness | n/a | **10 / 10 mutations detected** |
| Independent exploit replay | `Host: evil.attacker.com` → **200 + full screenplay** | **403, no screenplay bytes** (see §4) |

The +65 tests are the new guards. Nothing regressed: the three skips are the pre-existing `test_store_fault_injection` ones.

### 1.1 Browser gate
**48 suites: 47 passed, 0 failed, 1 skipped, 0 known-broken — 1175 checks, exit 0, 12m19s.**

| | Suites | Checks |
|---|---|---|
| Pre-existing | 45 | 1138 — **unchanged, all passing** |
| `deep_links` (new) | 1 | 24 |
| `render_scale` (new) | 1 | 13 |
| **Total** | **47 passing + 1 skipped** | **1175** |

The load-bearing part is the first row: a `before_request` hook now runs on **every** request and the SPA gained a router, and all 1138 pre-existing checks still pass in both themes. The one skip is `gun_pen_audit`, printed with its reason — *"runs a real analyze — needs a llama-server, so E2E_BASE must point at a studio that has one"*.

---

## 2. The two fixes that mattered

### BE-1 — Host validation
`_host_header_is_local()` parses the header (never prefix-matches) and hands the host to **`net_guard.is_loopback_host`** — the repo's one canonical "is this local?" predicate. It rejects userinfo, path characters and whitespace *before* parsing, because `urlparse` reads `evil.com@127.0.0.1` as the loopback host. A trailing dot is stripped **from the parsed host**, so `localhost.:8500` (what a browser actually sends) is served while `evil.com.` is still refused.

Deliberately **not** Flask's `TRUSTED_HOSTS`: that setting takes a static list of literal names, which would need a *second* enumeration of "what counts as local" — the exact duplication `net_guard` exists to prevent (BE-H1) — and still could not express "any `127.0.0.0/8` address". `test_every_loopback_literal_is_accepted_by_the_predicate` pins that difference with `127.0.0.2`.

The guard is registered **before** the write guard so a foreign-`Host` POST is refused for the reason that actually applies, and it runs on every method — reads included, which is where the exposure was.

### E2E-1 — the bind, measured
Two layers, because the audit's complaint was that the old guard *could not fail*:

1. **Cheap and always-on** — `_launch` captures `app.run`'s kwargs. Flipping one string in `main()` now turns a test red immediately.
2. **Behavioural** — `TestTheShippedServerIsLoopbackOnly` boots the shipped server in a subprocess and asserts it is **not reachable on the machine's non-loopback IPv4** (measured here: `10.235.17.90`, `ConnectionRefusedError`).

Layer 2 carries a **control probe**: a socket bound to `0.0.0.0` on the same address must be reachable first. Without it the test would pass on a machine where the probe itself is firewalled — the vacuous-assertion failure mode this repo explicitly forbids. When the control probe cannot work, the test **skips with that reason** rather than failing, because a failure would blame the product for the host's network policy.

---

## 3. Self-critique — where my own claims did not survive

An independent reviewer was given the diff and told to falsify it. It found four things worth fixing. Three were mine.

### 3.1 I wrote a comment that was false, and a test that verified nothing
I claimed the `status_code == 200` cookie condition stopped the token cookie being handed to a Host-guard refusal. **It did not.** That refusal is `jsonify(...)` → `application/json`, so the pre-existing `mimetype == "text/html"` test already excluded it. My test passed identically before and after the change — a non-discriminating assertion, which is the exact defect class this repo has a standing rule against.

**Fixed:** the comment now states what actually changed (HTML error pages), and the test asserts the case that *does* flip — a 404 HTML page carries no cookie while `/` still does — with a docstring that says explicitly what it does not claim.

### 3.2 I collapsed two different facts into one number
`rule_count()` returned `0` both for "the KB is empty" and for "the KB could not be enumerated". `_empty_kb_message` then reported the second as the first, so a transient read error on a healthy 263-rule KB would have produced *"the knowledge base loaded ZERO rules"*. My own docstring claimed the opposite.

**Fixed:** `rule_count()` returns `int | None`; `None` means "cannot count" and is never reported as empty. Covered by `test_a_kb_that_cannot_be_enumerated_reports_none_not_zero`.

### 3.3 A leak the reviewer demonstrated, that I had not seen
`main()` configures the **root** logger, and `test_capability_token` calls `main()` six times. The handler outlived each test — writing later tests' records into a stale directory, and on Windows holding an open handle that makes that directory unremovable (`[WinError 32]` — the very failure the delete-retry tests exist for). This is a direct consequence of adding logging, i.e. a regression *I* introduced.

**Fixed:** an autouse fixture in `tests/conftest.py` resets the module's handler and restores the root level after every test.

### 3.4 Two process errors of my own
- I sent **two edits to the same file in one message**; one silently overwrote the other, and a missing `from urllib.parse import urlparse` reached a test run as a `NameError` (47 failures). Caught by running the suite, fixed, re-verified.
- My first trailing-dot fix stripped the raw header, which does **not** fix `localhost.:8500` — the form a browser sends. Caught by a test I had written expecting it to work; the fix moved to the parsed host.

### 3.5 One expectation of mine was simply wrong
I asserted `[::1].` should be served. It is not a valid authority — `urlparse` raises on it — and no browser sends it. The test was corrected to assert refusal, not the guard.

---

## 4. Independent verification (not by me)

A separate agent was told to replay the audit's original attack against a freshly booted server, without reading the new tests.

| Host header | `/api/projects` | `/script` | screenplay leaked |
|---|---|---|---|
| `evil.attacker.com` | 403 | 403 | no |
| `evil.attacker.com:8631` | 403 | 403 | no |
| `localhost.evil.com` | 403 | 403 | no |
| `127.0.0.1.evil.com` | 403 | 403 | no |
| `evil.com@127.0.0.1` | 403 | 403 | no |
| `0.0.0.0` | 403 | 403 | no |

Normal use is unaffected: real `Host` + token → 200 for both the project list and the script; `Host: localhost:8631` → 200; the cookie flow → 200. The bind probe refused on `10.235.17.90` while the `0.0.0.0` control connected. The log file was written. **Verdict: the read exposure is closed.**

---

## 5. Round 2 — the remaining findings

### UX-1 (MED) — the desk has a URL now
`#/<project>/<view>[/<scene>]`, with `#/` being the welcome desk.

The design decision that matters: **the hash is derived from `state`, never the source of truth.** `syncRoute()` rides on `saveSession()` — which every project, view and edit already goes through (14 call sites) — plus a debounced scroll sync, which was needed because *nothing* persisted on scroll, so the scene anchor would otherwise only ever be captured at the last view change. No caller has to remember to update the URL, which is why it cannot drift.

Push vs replace is split on purpose:

| Change | History | Why |
|---|---|---|
| project or view | `pushState` | Back must undo it — this is the finding |
| scene within a view | `replaceState` | otherwise Back would walk through every scene the writer scrolled past |

`openViewByName()` is now the ONE place a view name becomes a view, used by both the saved session and the URL — so "revision" cannot come to mean two different things. The legacy aliases (`chat`/`script`, `fv`) keep their original destinations rather than being collapsed, so restoring an old session behaves exactly as it did.

One listener, not two: traversing between hash entries fires `popstate` **and** `hashchange`, so `hashchange` alone covers Back/Forward. (See §6.1 — I shipped the twin, and the mutation harness caught it.)

A stale address is corrected rather than left lying: `correctRoute()` rewrites the bar to what is actually on screen when a link names a project this desk does not have. And because the **empty** route means two different things — "no deep link" on a fresh load (refresh must still restore the session) versus "I asked to leave" when it arrives by traversal — `applyRoute()` takes a `fromNavigation` flag. Without it, Back out of a project bounced straight back in (§6.6).

### UX-2 (LOW) — HiDPI
`tests/e2e_browser_render_scale.py` (13 checks). No suite in the gate had ever set `deviceScaleFactor`; every viewport sweep ran at DPR 1.

It asserts **layout invariance** — the same document metrics at DPR 1 and DPR 2 (overflow, scene count, body font size, line height, scene width, pane height, a control's hit area) — and asserts the DPR reading too, so the comparison cannot pass by the emulation silently not applying. Layout invariance is a real invariant (the CSS pixel is defined independently of the device pixel ratio) and it is what a scale-dependent mistake would break.

**Deliberately not asserted: "text resizes to 200%".** The type scale is px by an explicit product decision (`style.css` `:root`; user call 2026-09-12 — *"keep 13px script body; v2.1's 16px declined"*), so the app does not follow the browser's default font size and WCAG 1.4.4 is met through **browser zoom**, which is how the resize is actually performed. A test asserting that text scales would assert against the design; a test asserting nothing would be the vacuous shape this repo forbids. Recorded here instead of shipped as a check.

### E2E-5 (LOW) — coverage is now measured and floored
`pytest-cov` was declared in the `ci` extra and installed, but no job ran with `--cov` and there was no floor.

Measured at this revision: **87% — 9699 statements, 1291 missed — over 1749 tests.** `[tool.coverage.run] source` is the one place "what do we measure" is decided (so CI's bare `--cov` and a developer's local run produce the same number), and `[tool.coverage.report] fail_under = 85` is the ratchet. Verified enforced: a subset run exits 1 with *"Required test coverage of 85.0% not reached"*.

### P-2 (LOW) — root scratch no longer breaks the lint job
`ruff check .` — the exact command the CI `lint` job runs — failed with two `E402`s from `.tmp_livecheck/`, an untracked scratch directory. `.gitignore` gained `/.tmp_*/` beside the existing `.tmp/` and `/tmp*/` rules, and `ruff check .` now passes. Nothing was deleted.

---

## 6. Round-2 self-critique

### 6.1 The mutation harness caught a guard of mine that could not fail
I wrote **two** listeners — `popstate` and `hashchange` — both calling the same handler. The harness reported `[GREEN (guard is VACUOUS!)]` for "delete the popstate listener": traversing between two history entries that differ only in the fragment fires **both** events, so `hashchange` already covered Back/Forward and the `popstate` twin was dead weight.

That is precisely the defect class this repo forbids, and I had introduced it while fixing it. Removed; the mutation now targets `hashchange` and goes red (**16 passed, 5 failed**). The comment records the finding so the twin is not "helpfully" re-added — and notes that a future *path*-based route would need `popstate` again.

### 6.2 Two of four deep-link failures were my assertions, not the app
- I asserted `hash.endswith("/feedback")` when the route legitimately carries a scene anchor (`/feedback/1`) — feedback is a script view.
- I deep-linked to the **last** scene, which cannot be scrolled to the top because nothing is below it. On a healthy app that check fails. Changed to a middle scene.

### 6.3 One was a real defect
A hand-edited address naming a project that does not exist left the bar claiming it while the page showed something else. The bar and the page disagreeing is a bug in its own right, so `correctRoute()` now fixes it.

### 6.4 I asserted the wrong invariant about scrolling
My first check was "the hash changes when you scroll" — which is false on a short script that does not scroll at all, so it tested the fixture, not the feature. Replaced with the invariant that actually matters: **the scene in the address bar is the scene at the top of the page.**

### 6.5 And I wrote a gate figure before the gate finished — twice
The same premature-claim error I criticised in §3, committed again in this very document. Both instances were caught and replaced with an honest "run in progress" marker before the numbers were verified. Recorded because the pattern, not the instance, is the problem.

### 6.6 A real bug my own router had, found by re-reading it rather than by a test
`correctRoute()` fires whenever `applyRoute()` returns false — and an **empty** route returned false. So: writer opens a project, presses Back to the entry before it (no fragment) → `hashchange` → `applyRoute()` false → `correctRoute()` writes the project's address straight back → **Back appears to do nothing.** A writer could not Back out of a project at all.

The root cause was conflating two different meanings of the same URL. The empty route means *"no deep link, use the remembered session"* on a fresh load (which is how refresh lands you back in your script — three suites depend on it) and *"I asked to leave"* when it arrives by traversal. `applyRoute(opts)` now takes `fromNavigation`, and only the traversal path treats an empty route as "leave the desk".

The guard is `e2e_browser_deep_links.py`'s last two checks, mutation-verified (**22 passed, 2 failed** when the branch is disabled). Writing it also taught me something about the test: my first version used `page.goto(base)`, which is a **reload** — and a reload *legitimately* restores the session, so it failed for the right reason against the wrong stimulus. Only `history.back()` is the case under test.

### 6.7 What this round says about the first round
Every one of §6.1–6.6 is a defect I introduced *while fixing* something else, and every one was caught by an independent mechanism — the mutation harness, an assertion that failed, or a re-read — not by my own confidence. That is the argument for building the harness before the fix, which is what §8's first item should be on any pass after this one.

---

## 7. What I deliberately did NOT do

| Item | Why not |
|---|---|
| **Require the token on reads** | The residual the replay agent also noted: reads on an *allowed* Host still need no token. It is not reachable by the attacker — the package sends **zero** `Access-Control-*` headers, so cross-origin JS cannot read the body, and the allowlist admits only names an attacker cannot own. Making reads token-gated would change the API contract for every GET (the SPA, the design labs, the `--no-token` harness) for no demonstrable gain. Recorded, not taken. |
| **Cap the `character` KB fragment by default** | Measured: that pass renders **65,408 chars (~16k tokens)** of craft rules against a 40,000 soft ceiling, and the hard cap (`SCREENPLAY_KB_BUDGET`) defaults to **0 = unlimited**. This is a documented, deliberate trade-off with an opt-in knob, and the code says the size is surfaced precisely so the server's silent truncation is not invisible. Choosing a default is a *quality* change that cannot be validated without a live model — the repo's own stated standard. The number is recorded here so the owner can decide. |
| **The other 7 source-text assertions** (E2E-3) | All seven are backed by real browser geometry checks (`phase13` walks the margin and asserts no pin covers a script line), so they are belt-and-braces rather than the only guarantee. Replacing them is churn without new signal. Only #1 was dead, and it is now gone. |
| **A "text resizes to 200%" assertion** (UX-2) | The type scale is px by explicit product decision, so the app does not follow the browser's default font size; WCAG 1.4.4 is met through browser zoom. Asserting otherwise would assert against the design. See §5 UX-2. |
| **E2E-4 — a browser suite against a real/mock `llama-server`** | Still the largest coverage asymmetry in the gate (the browser journey only ever runs the demo model). It needs a suite that boots a studio pointed at `tests/mock_unified_server.py` and drives the SPA's fetch → SSE → render loop; that is a new harness capability, not a guard on existing behaviour, and it is the one audit finding this pass did not reach. |
| **Committing anything** | §6 P-1 of the audit recommends committing the in-flight re-audit *with* its tests. That is the owner's call — the working tree now also carries this change set, and I will not stage or commit someone else's uncommitted work under my own message. |

---

## 8. Residual risks (stated plainly)

1. **The Windows CI job has never run.** I cannot execute GitHub Actions. Its test *selection* was run on this Windows machine (187 passed / 3 skipped, and the `nt`-gated delete-retry test ran rather than skipping), and the YAML was parsed, but the job itself may need a first-run adjustment. It is scoped to the store/lock/delete files rather than the whole suite for exactly that reason.
2. **The coverage floor is 85 against a measured 87, and it has never run on CI.** Two points is deliberate margin for platform differences (the `msvcrt` branch runs here and `fcntl` there, so each platform covers the other's lines), but the first CI run is the real check. If it trips, the honest response is to look at *what* lost coverage, not to lower the number.
3. **The audit's `gun_pen_audit` suite remains unexercised** here exactly as in CI — it needs a real `llama-server`.
4. **BE-3 is a foundation, not a retrofit.** Logging is configured and wired into startup and the 500 handler; the four shipped packages still do not emit structured records at their own decision points. That is a larger change than this pass.
5. **The empty-KB guard is new, so it has never fired in the wild.** Its false-positive surface is now `None`-aware (§3.2), but the message has only ever been seen in a test.
6. **`/.tmp_*/` was added to `.gitignore`.** Nothing was deleted, but that is a change to a file that governs what the repo tracks — revert it if the directory is meant to be versioned.
7. **The router is the first history interaction the SPA has ever had.** 1172 browser checks pass, and the push/replace split is mutation-verified, but a long working session with many Back presses is not something a 12-minute gate can simulate.

---

## 9. Files changed

**Product (4 modified, 2 new)**
- `screenplay_studio/webapp_server.py` — Host guard, cookie condition, logging wiring, module `urlparse` import
- `screenplay_studio/webapp/app.js` — the router (`syncRoute`/`buildRoute`/`parseRoute`/`applyRoute`/`correctRoute`/`openViewByName`/`currentSceneAnchor`/`scheduleRouteSync`), the single `hashchange` listener, and the boot path's deep-link-first restore
- `screenplay_studio/logsetup.py` *(new)*
- `screenplay_analyzer/pipeline.py` — `_empty_kb_message()` + the `analyze()` branch
- `screenplay_analyzer/rules_context.py` — `rule_count()`

**Tests (6 modified, 5 new)**
- `tests/e2e_browser_deep_links.py` *(new — 24 checks)*
- `tests/e2e_browser_render_scale.py` *(new — 13 checks)*
- `tests/test_host_header_guard.py` *(new — 45 assertions)*
- `tests/test_empty_kb_guard.py` *(new)*
- `tests/test_logsetup.py` *(new)*
- `tests/test_capability_token.py`, `tests/test_production_readiness.py`, `tests/test_packaging_data_files.py`, `tests/conftest.py`

**Config / CI (3 modified)**
- `.github/workflows/ci.yml` — `test-windows` job; `--cov` on the python job
- `pyproject.toml` — `[tool.coverage.run] source` + `fail_under = 85`
- `.gitignore` — `/.tmp_*/`

Line endings were preserved per file (the repo is mixed CRLF/LF): every edit was checked against the file's own newline, and the mutation harness is newline-aware after a `\n` anchor against a CRLF file silently matched zero times on its first run.
