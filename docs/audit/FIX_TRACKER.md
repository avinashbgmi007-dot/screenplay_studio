# Fix Tracker — production-readiness pass

**Live document.** Updated as each item lands, so the state of play is readable
without re-deriving it from `git log`. Source audit:
`docs/audit/production_readiness_2026-09-21.md`.

**Last updated:** 2026-09-21 (pass 14b — **a dropped connection was hiding a missing error
message.** The analyze pre-flight sat OUTSIDE the handler's `try`, so a refused
`os.remove(progress.json)` escaped it — and Werkzeug answers an exception it cannot convert by
closing the connection with **no reply**, which the caller sees as `RemoteDisconnected` and cannot
tell apart from a network fault. The pre-flight is guarded now and the heartbeat clear is
deliberately non-fatal. The audit's wait loop, which **manufactured an hour-long timeout** because
it waited on a trigger that had never been accepted, now fails fast and is bounded in both
directions. Found with `py-spy dump` after two wrong guesses.)
**Last updated (pass 14):** **the blocked frame is FIXED, not pinned**, and the desk
now has one Settings form for a local model *or* a remote API with a token. `_SPA_CSP` is
`frame-ancestors 'self'`: a foreign page still cannot frame the desk, which is what the directive
is for, and the app's own console can. The design-session suite asserts the frame **renders** and
that **zero** CSP refusals are logged. Remote access gained a real bearer token, threaded into
every client, never echoed back — and the mode stays a launch-time decision, not a permission.
**HEAD:** `c7a4b68` (passes 14 → 14d) — **pushed**; `git ls-remote origin main` agrees. The
tracker-stamp commit that follows carries the same content.
**Baseline for this pass:** `fdf431c`

---

## Gate status

| Gate | Command | Result at this pass |
|---|---|---|
| Unit + integration | `python -m pytest tests/` | **1614 passed, 4 skipped, 0 failed** (1618 collected; +4 in pass 14b: `tests/test_analyze_preflight.py`) |
| Lint | `ruff check .` | **clean** |
| JS unit | `node --test tests/js/*.test.js` | **16 / 16** |
| Browser E2E | `python tests/run_browser_suites.py` | **34 suites: 33 pass, 0 fail, 1 skip, 0 known-broken** — **702 checks** (pass 14: +1 suite, +32 checks). **Re-run in pass 14b** after the product change: unchanged, `GATE-EXIT=0` — the pre-flight guard only alters failure paths. `gun_pen_audit` remains the one skip, and its label was re-tested this pass and held. |

> **Pass 14 reversed pass 13's central decision, and that is the point of the entry.** Pass 13
> correctly found that `design_session`'s exclusion label was false — the console frames the SPA
> and the SPA shipped `frame-ancestors 'none'`, so no port could ever have made it pass — and then
> chose to **pin the block as a check**. Pinning a broken product surface documents the failure; it
> does not fix it. The directive's job is to stop a **foreign** page framing the desk and overlaying
> it with decoy controls, and `'self'` keeps every bit of that: the only origin allowed to frame the
> app is the app's own origin, which the writer already fully trusts (it is the same server handing
> out the capability token). So the relaxation is exactly one word wide, and
> `test_spa_security_headers.py` pins it as its own value (`== ["frame-ancestors 'self'"]`) and
> asserts it is not `*`/`http:`/`https:`/`data:`. The suite now asserts the frame **renders** — and
> covers the half that was dead for as long as the frame was blank: the dawn sync reaching the live
> app inside it.

> **Pass 13 un-skipped the last suite, and it was not gated on an environment — it was
> impossible.** `design_session` was excluded as *"drives a studio already running at
> `E2E_BASE` (default `:8500`)"*. The console frames the SPA, and the SPA ships
> `frame-ancestors 'none'`, so Chrome refused that frame on **every** port. It boots its own
> studio now, reports through named `check()`s instead of bare `assert`, and **pins the
> deliberate block** — if anyone relaxes `_SPA_CSP` to `'self'`, the suite fails and forces the
> decision into the open. The one remaining skip is `gun_pen_audit`, which genuinely needs a
> llama-server. **The lesson was about verification:** pass 12 claimed "everything is closed" and
> checked it by grepping this table — which compares the tracker against the tracker. The gate's
> own output is the evidence.

> Pass 10 closed **T1e**: the 21 vacuous browser checks are fixed, and the sweep
> that found them now returns **0**. The gate's check total went **660 → 650** —
> *down*, and finally true: 11 checks that asserted nothing are deleted, 9 that
> asserted nothing became checks that can fail. Mutation-verified **6/6**, every
> mutated file restored byte-identical.
>
> ✅ **Pass 12 closed the `library_delete` flake, and it was a defect rather than a
> timing artefact** — a Windows sharing violation that left the project
> half-deleted. Both `rmtree` sites now use `jsonio.retry_permission`. See the
> pass-12 section and the open-items table. No known-broken suites remain.

> Pass 9 repaired the two suites that were excluded as `KNOWN_BROKEN`, so the gate
> now *runs* them: **+2 suites, +127 checks** (`preview_next` 14 → 92 checks,
> `preview_redesigns` rewritten at 35). The only remaining exclusions are the two
> `REQUIRES_LIVE_STUDIO` suites, which need a studio already running at `E2E_BASE`.
> `KNOWN_BROKEN` is **empty** — and `test_browser_gate_runner_never_silently_drops_a_suite`
> now pins both repaired suites as runnable, so a future failure cannot be silenced
> by re-adding them.

> Re-run all four after any code change. A row above is only true for the
> commit named in "Last updated".
>
> ⚠️ `node --test tests/js/` (a bare directory) fails with `MODULE_NOT_FOUND`
> on Node 22 — it must be the file glob `tests/js/*.test.js`. That is an
> invocation trap, not a failing test.
>
> ⚠️ The browser suites spawn a **child process**, so `PYTHONPATH` must be
> exported for the child too — without it the suite dies with
> `ModuleNotFoundError: No module named 'flask'`, which looks like a product
> failure and is not.

---

## Closed (verified, committed, pushed)

| ID | Item | Commit | Proof |
|---|---|---|---|
| FE-C1 | Stored XSS via `innerHTML` sinks → token theft | `e3b283f` | `tests/e2e_browser_xss_inert.py` (21) + `test_spa_security_headers.py` (8) + strict CSP |
| R1 | Wheel shipped **zero** data files | `e3b283f` | `tests/test_packaging_data_files.py` (8, mutation-verified) |
| R2 | Browser gate script untracked → CI ran nothing | `e3b283f` | `tests/run_browser_suites.py` now committed |
| BE-H1 | `server_url` exfiltration to arbitrary host | `725e296` | `tests/test_server_url_guard.py` (48) + browser (14) |
| BE-H2 | Cross-process write tearing (358/508 edits lost) | `b60fc45` | `tests/test_store_concurrency.py` (12, real child processes) |
| BE-H3 | Shared fixed `.tmp` name between processes | `b60fc45` | unique `<store>.<pid>.<hex>.tmp` + fsync |
| BE-H4 | Transient read error reported as permanent damage | `b60fc45` | `load_json_store` retry budget (785 escalations → 0) |
| F4 | Finding-id hash divergence (UTF-16 vs code points) | `17f0757` | `tests/e2e_browser_finding_id_parity.py` (19 vectors) + `core.test.js` |
| F5 | Cache-bust guard matched 1 of 4 token shapes | `efb3dd5` | `tests/test_asset_cache_bust.py` (5) + rewritten browser step |
| BE-M1 | Corrupt `edits.redo.json` read as empty → 400 "Nothing to redo", then overwritten | `a5742d5` | `TestDamagedHistoryStores` (6) + `TestDamagedHistoryAPI` (1) + StoreCase `silent`→`guarded` |
| BE-M2 | `edits_log` read raw → 400 "bad request" for a damaged disk | `a5742d5` | `test_damaged_edit_log_is_reported_not_read_as_empty` + 503 API assertion |
| BE-M1b | Undo/redo mutated before discovering the other store was damaged | `a5742d5` | both pre-flight tests (one per direction) |
| R7 | CI ran `pip install ruff` unpinned | `a5742d5` | `test_ci_pins_its_linter_to_the_version_the_repo_uses` |

---

## Closed in this pass (2026-09-21, pass 14e) — the last two unguarded destructive calls, and a bug in the sweep that found them

Pass 12 swept every destructive filesystem call with an AST and split them by **blast radius**: the
two multi-file `rmtree` sites could leave a PARTIAL result, so they were fixed; the single-file
`os.remove` sites *"either happen or raise"*, so they were recorded and left alone. **That split was
right about state and wrong about reporting.** A raise is not free — the front-end reads `error` off
the response body, so an unguarded raise answers with Flask's HTML 500 and the writer is told nothing
they can act on. Both remaining sites are now guarded, and one was worse than recorded:

| site | call | what it did before |
|---|---|---|
| `reparse_project` | `os.remove(p)` over the stale analyze artifacts | escaped the handler → an HTML 500 instead of a sentence naming the file |
| `upload_draft` | `os.remove(tmp_path)` in a **`finally`** | **an exception in a `finally` REPLACES the in-flight exception** — so a failed temp-file cleanup discarded the clear `"Could not process new draft: …"` error returned just above and escaped as a generic 500. The writer lost the real reason. |

The two treatments differ on purpose, and the difference is the point:

- **`reparse_project` fails LOUDLY** (`"Re-parsed, but could not drop the stale analysis file
  report.md: …"`). The parse succeeded, so silently continuing would leave a stale report on screen
  against a fresh parse — the "stale state shown as current" lie this desk is built not to tell.
- **`upload_draft` is non-fatal** — cleanup is not the operation, the file is a temp upload the writer
  never sees, and the next upload overwrites it. It reports the refusal and carries on.

### And the sweep that produced the pass-12 table was itself buggy

Re-running the sweep flagged **five** route-handler sites as unguarded. Reading them showed **three
were already inside `try` blocks**. The bug: the guard test asked whether the line fell inside the
**first statement** of a `try` body (`in_span(lineno, sub.body[0])`) rather than inside the body's
span — and the first statement of a try body is one line, so only calls on that exact line looked
covered. Fixed, the sweep agrees with the pass-12 table exactly: **two** unguarded sites, the two
fixed here.

**That is the third instrument to lie in this session** — a proxy, a blocked port, and now my own AST
walk. Each correction came from reading the code the instrument pointed at, which is worth noting as
the habit rather than the exception.

### Verified
- `tests/test_destructive_paths.py` (new, 3 tests), **mutation-verified 2/2** as named failures with
  the source restored byte-identical (`.workbuddy-ai/scratch/destructive_mutation.py`).
- The `finally` test pins the information-loss property, not just the status code: it asserts the
  response still carries `Could not connect to llama-server`, which is exactly what the unguarded
  version discarded.

---

## Closed in this pass (2026-09-21, pass 14c) — the audit's own output was lying in three more places

Once the harness stopped hanging, the full `gun_pen_audit` ran to completion against a live model and
reported `41 passed, 1 failed, 2 gaps`. **All three were the harness's fault, and all three have the
same shape: a check asserting something the product never promised.**

### The failure: loopback was going through a proxy

```
FAIL  pass2: force re-analysis accepted
      [HTTPConnectionPool(host='127.0.0.1', port=38949): Max retries exceeded
       with url: http://127.0.0.1:8517/api/projects/gun_pen_2/analyze (ProxyError)]
```

The environment exports `HTTP_PROXY`/`HTTPS_PROXY` pointing at a local proxy, and **`requests`
honours them for loopback** — unlike `curl`, which bypasses localhost automatically. So every call
this harness made to the studio it had just booted on `127.0.0.1` went out through a proxy that
refuses under load. I had dismissed this theory an hour earlier because three GETs through it
happened to succeed. That was wrong, and the failure mode is worth naming: **a `ProxyError` against a
studio that is answering every other request looks exactly like a product fault.**

`e2e_browser_common.py` now adds `127.0.0.1,localhost,::1` to `no_proxy`/`NO_PROXY` at import, before
any suite makes a request. Proof: `Session().merge_environment_settings(...)['proxies']` is
`OrderedDict()` for a loopback URL.

**And the guard added in pass 14b did its job:** the trigger was not accepted, so the stage failed in
seconds and skipped its derived assertions — instead of waiting 3600 s for a run that never started.
That is precisely the behaviour the earlier version lacked.

### The mechanism, confirmed: the hook raises `SystemExit`

The proxy was the *transport* problem. The refusal underneath it was the sandbox hook, and its
exception type is now known: the same hook landed on two ordinary tests as **`SystemExit: 1`**
(`test_sdist_ships_the_data_files` errored on setup; `test_entity_scope_map_resolves_relative_projects_dir`
failed) — and run in isolation the first **skips** (no `setuptools` installed) and the second
**passes**. `SystemExit` is a `BaseException`, which is exactly consistent with the dropped
connection (an unhandled `Exception` would have been converted into a 500) and exactly why the
`except OSError` guard could not catch it. It also explains the earlier `EEEEE` + `F` run whose
failure summary was never written: the hook killed the session during teardown.

**So the fix is to stop deleting.** `_start_progress_heartbeat(m)` now *writes* a fresh `running`
heartbeat where `os.remove(progress.json)` used to be. The delete was never load-bearing — the
pipeline's first event overwrites the file within seconds — so this keeps the whole guarantee (no
poller can read the previous run's `done`) and removes the failure mode, using the same
`atomic_write_json` the pipeline itself uses. Mutation-verified **3/3** (the write removed, the
timestamp made stale, the pre-flight's exception type swapped), source restored byte-identical.

### Gap 1 (false): "the mass strip says 29 open of 31"

The check demanded `open == total` on the grounds that the script was unedited. But **an unedited
script can still carry the writer's MARKS** — edits and marks are different stores, and the server's
`findings_status` counts *edits* (`addressed=0` here) while the strip counts *marks*. The project had
2 findings marked `addressed`, so `29 = 31 - 2` is exactly right. The check now asserts the two things
that are actually true: the total equals the report's finding count, and the open count agrees with
the counting contract the strip is built from.

### Gap 2 (false): "the 'Continuity' section is absent from the board"

Filed as a PRODUCT gap — a finding the writer never sees. It is not one. The dock's section list is
**dynamic** (`app.js` groups `state.report.findings` through `findingPassesFilter`), and that filter
drops any finding whose disposition is not `open` (or `deferred` with that toggle on). Measured live
in the page:

```
excluded by the filter: 3 of 31
  index=0 cat=continuity sev=low    disp=addressed id=f1atq8x7
  index=1 cat=structure  sev=medium disp=addressed id=fc8epm4
  index=2 cat=dialogue   sev=high   disp=deferred  id=f3etlxt
```

The single continuity finding is one of the two the writer marked `addressed` (`f1atq8x7` is in
`finding_marks.json`), and all three severity chips were already ON — so the filter was wide open and
the absence is correct. The check now asks the app which categories the **active filter admits** and
requires a section only for those, so it still catches a render that drops an admitted category
without inventing gaps for findings the writer has closed.

### And one more: a check that could never fail

`widen: Medium+Low reveal every finding card` asserts `wide_cards >= default_cards`. On a project
whose default filter already admits every severity the widen is a **no-op**, so it asserted `x >= x`.
`widen_filter` now returns what it toggled — read from the chips' own `aria-pressed`, not guessed from
a card count — and the suite **says so** when it did nothing, instead of passing quietly.

### And the gate itself was flaky by construction (pass 14d)

Re-running the 34-suite browser gate after the shared-harness change came back
`34 suites: 32 passed, 1 failed, 1 skipped` — with the failure being:

```
ERROR   smoke   Page.goto: net::ERR_UNSAFE_PORT at http://127.0.0.1:2049/
```

Nothing to do with the change. `free_port()` picked a random free ephemeral port, and **Chromium
refuses to navigate to a list of ports it considers unsafe for the web** (2049 is the NFS port). The
port was free and unusable, and the suite died with a message that reads like a broken product.
`free_port()` now draws until it gets a port that is free **and** not on Chromium's blocked list —
200 draws verified safe. Same failure shape as everything else in this pass: **a harness accident
wearing the costume of a product defect.**

### Verified
The full suite now runs to completion against the live model: **`51 passed, 0 failed, 0 gaps filed`**
(was `41 passed, 1 failed, 2 gaps`), with **zero `safe-delete` events** in the studio log — removing
the delete removed the hook's trigger entirely. The four `NOTE`s are the suite volunteering what it
did *not* exercise: the widen was a no-op, no continuity section was expected, no Principles section
appeared, and `ghosted marks` were not rendered (so "never red" went untested).

---

## Closed in this pass (2026-09-21, pass 14b) — a dropped connection was hiding a missing error message

**How it was found is the finding.** A `pass2` re-run sat for 20 minutes producing nothing at all.
The first two explanations were both wrong — a dead sandbox proxy (it forwards fine) and the
unguarded `os.remove`. `py-spy dump` on the hung process ended it in one line:

```
_start_analysis_and_wait (e2e_browser_gun_pen_audit.py:705)   # time.sleep(10)
step_pass2 (e2e_browser_gun_pen_audit.py:734)
```

It was inside the 3600 s wait **added in pass 14**, waiting on a trigger that had never been
accepted.

### The product defect: an unguarded pre-flight

`POST /api/projects/<name>/analyze` with `{"force": true}` closed the connection with **no reply**
(`RemoteDisconnected`, 0.17 s), while the identical POST with no body returned 200. The studio's own
stderr said why:

```
[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] {"count":4719,"threshold":50,"scope":"turn",
  "targets":["...\gun_pen_2\progress.json"],"targetCount":1}
```

`_analyze_locked`'s pre-flight — manifest rewrite, stage reset, heartbeat clear — sat **outside** the
handler's `try`, and the refusal escaped it. Proof the delete never ran: `progress.json` still held
its old 21:12:08 stamp and the stage reset was never persisted.

**Correction, made in the same pass after the fix was already written — and it changes what the fix
is worth.** I first wrote this up as "an exception the handler could not convert", assuming an
`OSError`. A three-route probe settles what a Flask dev server actually does:

| route raises | `curl` | `requests` |
|---|---|---|
| `OSError` (an `Exception`) | **HTTP 500** | HTTP 500, HTML body |
| `SystemExit` (a `BaseException`) | **HTTP 000** | `RemoteDisconnected` |

An ordinary error is **already** converted into a 500 — Flask's handler catches `Exception`. Only a
throwable *outside* `Exception` reaches Werkzeug and closes the socket. So **`RemoteDisconnected`
from a Flask dev server means a BaseException, not a normal error** — which means the refusal was
**not** an `OSError`, and `except OSError` / `except Exception` do **not** catch it. The guard below
is real and worth keeping, but it is **not** what made the re-run pass: the refusal simply stopped
recurring (a fresh studio process, a fresh delete counter), so the live path never exercised it. What
proves the guard is its **unit test**, not the green run — and the underlying drop is an environment
behaviour the product cannot legitimately catch, because the only way to catch a BaseException is to
swallow `SystemExit` and `KeyboardInterrupt` with it.

Two changes (kept, with their justification corrected):
- the pre-flight is inside its own `try` and returns a **JSON** 500. Flask's own 500 is an HTML page
  and the front-end reads `error` off the body, so this is about the writer getting a sentence they
  can act on rather than a stack trace they cannot;
- `_clear_progress(m)` drops the heartbeat **non-fatally**. `progress.json` is a heartbeat, not the
  writer's data: the pipeline's first event overwrites it within seconds, and failing a whole
  re-analysis over a transient cache file costs the writer a run and tells them nothing. It
  **prints** the refusal rather than swallowing it.

**What actually made the re-run green** was neither of the above: it was the harness fix below plus
the trigger simply not being refused again. Recorded plainly because the difference matters — a green
run that does not exercise the fix is not evidence for the fix.

### The harness defect: a wait loop that manufactured the timeout it was built to prevent

`_start_analysis_and_wait` was added in pass 14 so the stage could not report findings against a
baseline that had never been verified. It did that — and then waited the full 3600 s for a run that
never started. **A wait loop whose precondition failed does not wait for completion, it manufactures
a timeout** — and a timeout is indistinguishable from a slow model, so the real error stays hidden
for the entire budget. Now:
- a trigger that is not accepted returns **immediately**;
- an accepted trigger must produce a heartbeat within `FIRST_BEAT_S = 300`;
- a running one must not go quiet for `STALL_S = 1200`.

"Still working" and "never started" are different failures and now say so differently.

### Verified
- pytest **1614 passed / 4 skipped / 0 failed** (1618 collected), ruff clean.
- `tests/test_analyze_preflight.py` (new, 4 tests) — mutation-verified **2/2** as **named** failures,
  source restored byte-identical (`.workbuddy-ai/scratch/preflight_mutation.py`).
- The trigger holds **in practice**: `POST /analyze {"force": true}` keeps the connection open and the
  run actually starts (`stage: dialogue` → `theme` → `character` → `coverage` → `logline_test`, with
  live model connections). **But per the correction above, this run never hit the refusal** — so it
  is evidence the path works, not evidence the guard works.
- **`pass2` is GREEN: `9 passed, 0 failed`, 0 gaps filed** — against a real 12-pass analysis on the
  live 35B model, and with the arrival arithmetic **exact** (`Pass: 31 → 31 still live · 0 no longer
  flagged · 0 new` vs the board's own count of 31). That is the check that reported a false failure
  before the harness bugs were fixed. One honest note from the suite: `ghosted marks not rendered —
  no moved marks on this run, so 'never red' was NOT exercised`.

**Caveat, and it matters for reading any gate result from this session:** the first full-suite run
reported `EEEEE` + `F` with its output truncated mid-progress, and a clean re-run of the *same* tree
was green. The cause is the same environment hook — it fires on pytest's own tmp-directory garbage
collection (`[safe-delete] … targets:["…\\Temp\\pytest-of-…\\garbage-…"]`), and it killed the
session during teardown so the failure summary was never written. **A red run from inside the agent
sandbox is not evidence of a regression, and neither is a green one** — which is precisely why this
pass records the *mechanism* and not just the verdict.

### Also answered: `gun_pen_audit`'s exclusion label is TRUE
Its reason — *"runs a real analyze — needs a llama-server"* — was tested against a live model on
`:8080` and held: the suite drives a real 12-pass analysis. Unlike `design_session`'s label (pass 13),
this one is honest, so the exclusion stays.

---

## Closed in this pass (2026-09-21, pass 14) — the blocked frame is FIXED, and the desk speaks both local and remote

### Two requested items

**1. The design console's blank cell.** Pass 13 found that `design_session`'s exclusion label was
false and responded by **pinning the block as a check**. That documented the failure instead of
fixing it. The directive's purpose is to stop a **foreign** page framing the desk; the only origin
allowed to frame it under `'self'` is the app's own origin — which the writer already fully trusts,
because it is the same server handing out the capability token. So:

- `_SPA_CSP`: `frame-ancestors 'none'` → `'self'`. Exactly one word wide, and pinned as its own
  value so a future edit has to argue with an assertion.
- `webapp/design_session.html`: its live frame was pinned to `http://127.0.0.1:8500/` — the **only**
  hardcoded host:port anywhere in `webapp/` — while the three prototype frames beside it were
  relative. It is `src="/"` (pass 13) and the stale `:8500` cell label is now gone too.
- The console drives the live app through the app's **own** `applyDawn()` instead of toggling
  `body.dawn` behind its back. The old shortcut repainted the frame correctly while leaving the
  framed app's button label and internal state believing the opposite theme — the console's headline
  claim is "across ALL four surfaces", and a frame that looks right while disagreeing with itself
  is not that.
- The suite now asserts the frame **renders** (`contentDocument` non-null **and** the document
  carries the SPA's own chrome, so a same-origin 404 cannot satisfy it), that **zero** CSP refusals
  are logged, and — new coverage for the half that was dead for as long as the frame was blank —
  that the dawn sync reaches the live studio inside it.

**2. Local model OR remote API, through one form.** The desk was loopback-only, which is a real
privacy property, but it had **no bearer header anywhere in the codebase** — so a token-protected
endpoint was not a supported setup, it was a setup that half-worked and then 401'd in a way that
looked like the model was broken.

| Concern | Decision |
|---|---|
| Where the header format lives | `auth_headers()` in `screenplay_analyzer/llm_client_base.py` — the shared base `screenplay_cowriter` **already** imports, so there is no new studio→analyzer dependency and no second copy to drift. `webapp_server._auth_headers` is a lazy, short-circuiting accessor. |
| Every call site | 9 client constructions in the webapp, both in the orchestrator, and both standalone CLIs. |
| Where the token is stored | `ServerConfig["api_key"]` **and** `ProjectManifest.api_key`. It rides in the manifest for the same reason `server_url` does — so `resume` and the CLI reach the same endpoint without the writer re-typing it. |
| How a manifest gets it | `_adopt_connection(m)` at every creation point, plus the existing settings sync (which now fires on a token change alone — rotating a credential used to leave every project holding the old one, which is exactly the shape of a silent auth failure that looks like the endpoint went down). |
| Is the mode a permission? | **No.** `connection_mode` is *derived* from the URL (`local`/`remote`), never stored, so it cannot drift. It is accepted as an INPUT only so "go local" can reset the URL and clear the token, and so "go remote" is refused loudly while the process opt-in is off — the opt-in stays a launch-time decision, because a request that could grant it would authorise sending the script to the host it names. |
| Does the token come back? | **Never.** `/api/config` reports `api_key_set` (bool) + `connection_mode` + `allow_remote`. A page that can read config still cannot read the secret out of it. |
| Is the token field hidden in local mode? | **No** — a local llama-server can legitimately require one (`--api-key`). Hiding the field would make that setup unreachable while a stored token kept being sent anyway. |

### Two real defects the new browser suite found — neither by review

- The disabled Remote option carried its reason **only in a hover `title`**. A greyed-out control
  with no visible explanation is indistinguishable from a broken one; the hint now states it in text.
- Reopening Settings after saving showed the **pre-save world**, because the form was only filled at
  page load. "I saved a token" read as "my save didn't work". `fillSettingsForm()` now runs on open.

### Evidence

The transport proof is a **real loopback HTTP server that records what it was sent** — not a mocked
`requests`, which would prove the call was made and prove nothing about the header. The browser
suite boots the studio **twice**, with and without the opt-in, because "remote is refused" and
"remote works" are two genuinely different states of the same product.

**Gates:** pytest **1610 passed / 4 skipped / 0 failed** (+34), ruff clean, node **16/16**, browser
gate **34 suites — 33 pass, 0 fail, 1 skip, 0 known-broken — 702 checks** (was 33/32/1/670).

### The lesson

Pass 13 was right about the *label* and wrong about what to do with it. Documenting a dead surface
is not a fix — it is a more honest-looking version of the same failure. When the blocker is a
security header protecting the *shipped* app and the thing it blocks is the app's **own** page, the
answer is the narrow relaxation, not a pinned assertion.

---

## Closed in this pass (2026-09-21, pass 13) — the last skipped suite was not gated on an environment, it was impossible

Pass 12 signed off with "every item this audit opened is closed" and verified it by grepping the
open-items table. **That check was circular** — it compared the tracker against the tracker. The
gate has a second exclusion list that no tracker row ever covered:

```
KNOWN_BROKEN = {}                                          # emptied in pass 9
REQUIRES_LIVE_STUDIO = {"gun_pen_audit", "design_session"}  # skipped every run
```

So `33 suites: 31 passed, 0 failed, 2 skipped, 0 known-broken` counted **31 of 33 suites**. The
coverage gap had not closed in pass 9 — it had **moved from one list to the other**, which is the
same "dead coverage looks like safety" failure that pass was written to fix.

### The label was false, and that is the whole finding

`design_session` was excluded with the reason *"drives a studio already running at `E2E_BASE`
(default `:8500`)"*, which reads as an environment requirement. It was not one. The console's fourth
cell frames the studio's own SPA, and the SPA ships `frame-ancestors 'none'`, so Chrome refuses the
frame outright:

```
Framing 'http://127.0.0.1:<port>/' violates the following Content Security Policy
directive: "frame-ancestors 'none'". The request has been blocked.
```

**No port would ever have made it pass.** The live cell has been blank for as long as that header has
existed, and because the suite was skipped in every gate run, nothing ever said so.

### The fix is NOT to relax the header

`docs/CRITICAL_REVIEW_2026-09-18.md` already classifies the console as a **lab artifact, not shipped
surface** — nothing in the app links to it, and no product doc mentions it.
`frame-ancestors 'none'` protects the *shipped* SPA, and the only thing it blocks is that unlinked
lab page. **Trading a real security property for a dead artifact is the wrong direction**, so the
header is untouched and the block is **pinned as a check**: if anyone ever relaxes `_SPA_CSP` to
`'self'` so the console can frame the app, the suite fails and forces that decision into the open.

One small production fix did land: `design_session.html` pinned its live frame to
`src="http://127.0.0.1:8500/"` — the **only** hardcoded host:port anywhere in `webapp/` — while the
three prototype frames beside it used relative paths. It is `src="/"` now, so the lab works on
whatever port the studio actually runs on.

### What changed

| File | Change |
|---|---|
| `tests/e2e_browser_design_session.py` | boots its own studio (`open_studio`) like the rest of the gate; every bare `assert` became a named `check()`; **20 checks**, was 0 |
| `tests/run_browser_suites.py` | `design_session` removed from `REQUIRES_LIVE_STUDIO`; `gun_pen_audit`'s reason corrected — it is excluded because it needs a **llama-server**, not because it needs a port |
| `tests/test_production_readiness.py` | `design_session` pinned as runnable, so re-adding it to either exclusion list is itself a test failure |
| `screenplay_studio/webapp/design_session.html` | the hardcoded `http://127.0.0.1:8500/` frame → `src="/"` |
| `docs/TESTING.md`, `tests/_run_e2e_sweep.py` | the stale "needs a studio on :8500" claim corrected in both |

### The lesson, and it is about verification

**Verify a closure claim against the artefact that decides, not against the list you wrote.** A
tracker table is a summary; the gate's own output is the evidence — and a summary can be complete
about what it lists while being silent about a second list. Grep the thing that makes the decision,
then compare its count to the count you are claiming.

---

## Closed in this pass (2026-09-21, pass 12) — the Windows `rmtree` race, and a duplicate helper caught before it shipped

**The last open item was a defect, not a flake.** `library_delete` had failed one gate run and
then passed 3/3 standalone, so pass 10 filed it open with its fix shape but not the fix: a
production change for a flake that could not be reproduced would have shipped unverified. That was
the right call. What changed is that the mechanism turned out to be **deterministically
reproducible** — and reproducing it turned "a slow poll" into a corrupted project.

### The reproduction (measured, not reasoned)

Hold one real `open()` on one file of a two-file tree, then `shutil.rmtree` it:

| | |
|---|---|
| Exception | `PermissionError`, `errno=13`, **`winerror=32`** — "being used by another process" |
| Tree afterwards | **`['project.json']`** — `parsed.json` was already deleted |
| After releasing the handle | `rmtree` **succeeds** (so the lock really is transient) |

`rmtree` deletes as it walks, so the failure **does not fail cleanly**. For a project that means
`parsed.json` gone while `project.json` stays — and `delete_project`'s own guard requires
`project.json`, so **the shelf keeps listing the script while the writer's library has silently
dropped it**. That is exactly the observed symptom: the row survives, so the disk never "empties"
and the suite's check stays red. **It was never a timing artefact.**

### Two call sites, not one

The item named `delete_project`. A sweep of every route for destructive filesystem calls (done by
parsing the handler bodies with `ast`, not by grepping) found the same unbounded call one module
away:

| line | route | call | guard |
|---|---|---|---|
| `webapp_server.py:822` | `DELETE /api/projects/<name>` | `shutil.rmtree(project_dir, ignore_errors=False)` | **unguarded** |
| `ideas.py:172` (`IdeaStore.delete`) | `DELETE /api/ideas/<id>` | `shutil.rmtree(self._dir(idea_id))` | **unguarded** |
| `webapp_server.py:1038`, `:2186` | reparse / drafts | `os.remove(tmp_path)` | unguarded, but **single file** — noted in pass 12, **fixed in pass 14e** |
| `:749`, `:782`, `:1574`, `:3377` | sample / upload / progress / graduate | `os.remove(...)` | already inside a `try` |

Only the two `rmtree` calls can leave a **partial** result; a single-file `os.remove` either
happens or raises. So those two are fixed and the rest are recorded.

**That split was right about STATE and wrong about REPORTING — corrected in pass 14e.** "Either
happens or raises" is not the same as "raises safely": the front-end reads `error` off the response
body, so an unguarded raise answers with Flask's HTML 500 and the writer is told nothing they can act
on. Worse, one of the two was a `finally`, where a raise **replaces the in-flight exception** — so a
failed temp-file cleanup discarded the real error and escaped instead. Both are now guarded, and the
pass-12 sweep that produced this table turned out to have a bug of its own (it tested whether a line
fell inside the FIRST statement of a `try` body rather than inside the body's span, so it reported
four *already-guarded* call sites as unguarded).

### The fix is a REUSE — and that is the part worth reading

The first version of this fix added a new helper, `fsutil.rmtree_with_retry`, whose rule was
*"retry only `winerror` 32/33"*. **That was wrong twice over.** `jsonio.retry_permission` already
exists — the project's ONE bounded retry for this race, already used by the store paths and
already tested — and `jsonio.py` carries an explicit **2026-09-20 user-approved decision**:

> retry EVERY PermissionError, not only the winerror 32/33 set. The concurrent save/rename hammer
> surfaces `PermissionError(13, "Access is denied")` with **NO winerror** under full-suite
> antivirus/indexer pressure — a signature the winerror-only filter read as a genuine denial and
> (correctly) refused to retry, leaving the suite red.

So the new helper was **the rejected filter, re-introduced**, and one of its tests
(`test_a_real_permission_error_is_not_retried`) **pinned the rejected behaviour as correct**. Both
were deleted. What shipped is a one-line reuse per site plus a clear error:

```python
try:
    retry_permission(lambda: shutil.rmtree(project_dir))
except OSError as exc:
    return _error("Could not remove the project — it may be only partly removed. "
                  f"Close anything using it and try again. ({exc})", 500)
```

The message says "may be only partly removed" because that is what a mid-walk failure leaves. The
old shape returned Flask's HTML traceback; the front-end reads `error` off the body.

### Tests — 4 new, all mutation-verified

`tests/test_delete_project.py` (2): a **real held handle**, released mid-flight, still deletes
(Windows-only — POSIX unlinks open files, so the race does not exist there); and a lock that never
clears answers **500 with JSON** naming the partial state, having used its whole retry budget.
`tests/test_delete_retry.py` (2): the **idea-store** site retries, and a denial that never clears
still raises after the budget. Both use a `PermissionError` with **no winerror** — deliberately,
because that is the real-world AV signature, and a test written against `winerror=32` would pass
under the rejected filter and prove nothing.

**Mutation-verified 4/4**, every one a **named** failure, every mutated file restored
byte-identical: retry dropped at either site, the error contract removed, and the retry neutered
(`attempts=1`).

### Gates after pass 12

pytest **1576 passed / 3 skipped / 0 failed** (+4), ruff clean, node **16/16**, browser gate
**33 suites — 31 pass, 0 fail, 2 skip, 0 known-broken — 650 checks**, with **`library_delete`
8 passed**. `GATE-EXIT=0`.

---

## Closed in this pass (2026-09-21, pass 10)

**T1e — the 21 vacuous browser checks. Closed: the sweep now returns 0.**

Pass 9's closing note said the remaining queue was "decisions and cosmetics". That
was wrong about one entry, and it was the only item still *mine*. Those 21 checks
could not fail, and they sat **inside** the "660 checks" number this tracker
quotes — so every citation of that number was ~3% fiction. Fixing it makes the
number *smaller* and true.

**The sweep was rebuilt, and independently reproduced the 21.** The pass-5 sweep
could not be trusted as-is: it matched `check(...)`/`ok(...)` by regex and missed
every **bare** `check(name, True)` — no leading `checks.` — which is how two of the
suites import the helper. The rebuilt sweep parses the call and inspects the
**second positional argument**, then applies all three known false-positive
corrections: `>= 0(?![.\d])` so `>= 0.7` is not a tautology; comment lines are
blanked; and **docstrings are blanked via `ast`** (the new helpers document the
anti-pattern with `check(name, True)` examples, and a naive sweep reports its own
documentation as a defect). It returns **21** — the same number, now from a method
that cannot miss the bare form.

**The 21, by what actually backed them:**

| Class | Sites | Action |
|---|---|---|
| Backed by a **throwing** wait (`wait_for_selector` / `expect().to_be_visible()`) | 9 | **converted** → bounded poll (`seen_visible`) + a real assertion |
| **Diagnostic dumps** — payload `print()`ed, check asserted nothing | 6 | **deleted / demoted** to `note()` |
| **Timing-conditional** — inside `if running_seen:` | 2 | **demoted** to `note()` |
| Conditional on **nothing happening** — and **dead** in the gate | 1 | **deleted**, the coverage gap recorded as a `note()` |
| In the gate-excluded `gun_pen_audit` | 3 | 2 demoted to `note()`, 1 **converted** (flagged unverified) |

**Each conversion now asserts the half its NAME promised, not just visibility.**
A throwing wait proves an element appeared; the check claimed more:

| Check | The half the wait never covered |
|---|---|
| `idea: blank page opens (writing-first)` | the editor is **blank** |
| `sameer: one streamed turn answers` | the reply is **substantive**, not error copy |
| `script: idea graduates into a script` | the scene page **has rendered text** |
| `inline edit: rewrite modal opens from the finding card` | the modal is **armed** — `is_visible()`, *not* `count() > 0`, since presence is satisfied by a hidden button |
| `room opens via summon` | the **drawer** is open, not just that a context card painted |
| `selection chip floats over the idea page` | the chip is **positioned** (non-zero box), not merely present |
| `user message rendered` | the bubble **echoes the text that was sent** |
| `pass2: ghosted marks render honestly (never red)` | the computed colour is not `--danger`, **resolved through the browser** so both sides are `rgb()` |

**The diagnostic dumps were worse than the tracker thought.** `Checks.ok` prints
`detail` **only on failure** — so those 6 checks showed neither the payload nor an
assertion on a green run. The `layout_audit` census ran **6 times per suite run**
and was invisible every time. `note()` prints unconditionally, so demoting them
*adds* information while removing the inflation.

**One more site, found while fixing them.** `selection_translate` guarded its
needle with a bare `assert ok, "needle line not found on the page"` — a crash-shaped
precondition. The trap: `finish()` sits at the **END** of `run()`, so the obvious
fix (a plain `return`) would have exited **0** and *swallowed* the failure. It now
records a named failure and calls `finish()`.

### A crash is not a verdict — and the mutations proved these suites still had one

Mutation verification started at **4/6**: two mutations produced a *crash* instead
of a named failure. Both were the pass-9 pattern, and both were real defects in
the **tests**:

1. **An unarmed modal left the overlay up.** With `#rewrite-generate` hidden, the
   check correctly FAILED — then `page.locator("#rewrite-generate").click()` timed
   out, aborted the run, and **the named failure never printed**. Worse, the
   never-completed modal stayed open and blocked the *next* section, which died on
   a dock click. Fixed with a bounded `clicked()` helper, an `Escape` on the
   un-armed path, and a bounded notes step.
2. **`last_reply()` raised when no bubble existed.** With the drawer-open class
   removed, the send failed, so there was no assistant bubble and
   `.last.inner_text()` raised — killing the suite before its summary. `send_chat`
   was unbounded for the same reason (a hidden composer). Both are now bounded and
   return a bool/`""`.

**Final verdict: 6/6 caught as NAMED failures, zero crashes, every mutated file
restored byte-identical** (sha256 compared after each restore). Three shared
helpers were made non-raising to get there — `clicked()`, `filled()`, `send_chat()`,
`last_reply()` — each returning a value the caller can assert, because *an action
whose precondition failed is a fact to check, not a timeout that aborts the run.*

### The count, honestly

| | Before | After |
|---|---|---|
| Vacuous checks (the sweep) | **21** | **0** |
| `identity_forensics` | 6 checks (5 vacuous) | **1 check** (all 5 markers deleted; the payload is the `print`) |
| `layout_audit` | 30 checks | **24** (the 6-run census is now a `note`) |
| `selection_translate` | 9 checks | **10** (the 9 include one *new* real check) |
| In-gate browser total | **660** | **650** |

The total *falls* by 10 and is now true. Eleven checks that asserted nothing are
gone; nine that asserted nothing became checks that can fail.

### The gate run also caught a flake — in a suite this pass never touched

The first full gate after these changes came back **30/31, exit 1**: `library_delete`
failed `shelf delete emptied the disk`, with the doomed project still listed.

**It is not this pass's doing.** That suite imports `Checks, assert_no_js_errors,
launch, open_studio` — none of the helpers changed here — and `git status` shows no
production file touched. It then passed **3/3 standalone** and the gate's **second
run was clean (31/31, exit 0)**.

It is, however, the **second** time this suite has flaked in the gate (pass 3's T3
was the first), so it was worth narrowing rather than shrugging at. Two candidates,
and the old failure detail could not tell them apart:

1. **The budget was too thin.** The poll allowed `20 × 250 ms = 5 s` for a
   **directory removal** that is O(files), with 33 suites running back-to-back.
2. **The server errored.** `delete_project` calls
   `shutil.rmtree(project_dir, ignore_errors=False)` with **no retry** — and on
   Windows that raises `WinError 32` whenever a handle is still open, which
   surfaces as a **500** and leaves the row exactly as observed.

Both are now *distinguishable*: the poll is time-based (30 s) and the check's
detail reports the **HTTP status**, so the next occurrence names its own cause.
**The (2) fix is a production change and was deliberately not made blind** — the
flake could not be reproduced locally, so a retry loop around the `rmtree` would
ship unverified. It is filed as open, with the evidence and the fix shape.

That is the honest trade: make the *diagnosis* better now, and refuse to guess at
a *fix* that cannot be tested.

---

## Closed in this pass (2026-09-21, pass 9)

**The two "known-broken" browser suites are repaired. `KNOWN_BROKEN` is empty.**

The gate's own comment was the mandate: *"a skipped suite is dead coverage — and dead
coverage is worse than none, since it looks like safety. Repair or delete them."* Both
entries were excluded as *"crashes"*, and the word hid the real damage.

| Suite | What it actually was | Disposition |
|---|---|---|
| `preview_next` | Died on its **second of six worlds** (`bounding_box()` was `None`). The crash aborted the run, so **four worlds were never exercised at all** — and once it ran, every one of them failed a different way. | **Repaired.** 14 checks reached before the crash → **92 checks across all six worlds.** |
| `preview_redesigns` | **Not "one bug".** It walked `welcome → desk → cowrite → feedback` via `.edge-tab` / `.spine-tab` / `.pane-pop` and read `a.card` in the gallery. **Every one of those selectors is absent from all six worlds** — the worlds were redesigned to `upload/pages/verdict/debate/spark`, the pane mechanism was replaced, and the gallery became a JS-built card grid. | **Rewritten** around the invariants that survive a redesign. **35 checks.** |

**Why `preview_redesigns` was rewritten rather than repaired 1:1:** 48
selector-coupled checks against a frozen prototype would recreate the same trap for the
next redesign. The new suite asserts only what a redesign cannot invalidate — exactly one
active screen, no inactive screen left visible, no horizontal overflow, zero uncaught JS
exceptions, real `[data-go]` navigation (or, for a single-screen world, that it declares
none), and gallery ↔ `DESIGNS` agreement so the two cannot drift silently. Screen *names*
are deliberately not asserted.

### Four real defects the repair surfaced — all fixed

| # | Defect | Root cause |
|---|---|---|
| 1 | The desk's composer wrote to the **wrong thread** — in chat-first it had **no listener at all** | `wireComposer` used document-order `$()` selectors. A world shipping its own landing (chat-first) precedes the desk in the DOM, so the bare selectors bound the *landing* composer/thread. Now scoped: the desk's composer → `#lab-thread`, the landing's → its own. |
| 2 | The desk's findings verbs (dismiss / locate / discuss) were **inert in five of six worlds** | Only `report-first` called `wireFindingVerbs("[data-desk]", …)`. The pane is shared chrome — *"injected identically into every world"* — so the wiring now lives in `mountDesk`, and report-first's duplicate call was removed (it would have double-fired). |
| 3 | The Workbench button sat **under the review bar** in three worlds | `#pv` is a full-width bottom bar (`position:fixed; bottom:0; z-index:950`, ~51px). The button was at `bottom:18px` with `z-index:520`, so its centre was covered and Playwright's click was intercepted. chat-first's working `bottom:60px` proved the intended clearance; the three outliers were raised to match. |
| 4 | The gallery's view-switching script **died on load** | The markup had `<div class="viewbar">` (a *class*) while the script called `getElementById('viewbar')` — so the Cards/Live switcher, the design picker **and** the frame view were all dead, and the failure was an uncaught `TypeError` on a page that otherwise looked fine. Added the id. |

Also: `[data-open-desk]` is now **delegated** on `document` rather than bound per element.
A one-shot `$$(...).forEach(bind)` only ever saw the static markup, so canvas-first's
boot-injected scene cards — each carrying `data-open-desk` — were silently dead.

### Both suites now fail cleanly

The old suites **crashed on the first break**, which aborts the run and masks every later
check — precisely how four worlds hid behind one. Each interactive step is now bounded and
guarded, so a break is a **named `FAILED:` line** and the remaining worlds still run. If a
desk never opens, the suite records two named failures and moves on rather than dying.

**Mutation-verified 5/5, each a named check failure (not a crash), every file restored
byte-identical:** one-shot `[data-open-desk]` → `canvas-first: desk reachable + both-open`;
bare composer selectors → `chat-first: REAL Sameer reply arrived`; unwired desk verbs →
`canvas-first: dismiss persists across reload`; `#viewbar` id removed → `gallery: Live view
swaps the grid for the frame`; a second active screen → `noir: exactly one active screen`.

**One thing found and deliberately NOT done.** `preview-redesigns/shots/` still holds **25
tracked PNGs** — `*-welcome.png`, `*-cowrite.png`, `*-feedback.png`, `*-desk.png` × six
designs, plus `gallery-live.png`. Those are screenshots of the **screen model the worlds no
longer have**. The old suite regenerated them on every run; the new one deliberately writes
no artifacts (a test should assert, not churn tracked files). They are excluded from the
wheel by design (*"evidence artifacts, not app assets"*), so this is not product bloat — but
they are now orphaned, and a reader would reasonably take `noir-welcome.png` for a current
screen. Deleting tracked files is the owner's call:

```bash
git rm -r screenplay_studio/webapp/preview-redesigns/shots/
```

---

## Closed in this pass (2026-09-21, pass 8)

**R10 — filed as "scratch files tracked at the repo root". It was not hygiene.**

The root cause was a `.gitignore` rule that enumerated extensions
(`/_*.png`, `/_*.log`, `/_*.json`, `/_*.txt`) and had never been given
`/_*.py` or `/_*.xml`. The list fell behind the shapes actually used, and five
files leaked. Fixed with one extension-agnostic rule, `/_*`.

**Two of the five were broken guards, and neither defect is visible by reading the file:**

| ID | What it was | Executed proof |
|---|---|---|
| **REL-M1a** | `_r2_a11y_guard.py` — a WCAG 2.4.7 focus-visibility guard that `docs/design/R2_PRIMITIVES_SPEC.md` calls a *"permanent gate"*. **Nothing ran it**, and **it could not fail**: its third compensation branch was `if re.search(re.escape(base), css) and ":focus-within" in css:`, where `base` IS the rule's own selector, so the first conjunct is always true and the branch collapses to `":focus-within" in css` — true, because the sheet has 13. | Injecting `.zz-injected-bare-suppressor { outline: none; }` still printed `clean — 18 outline:none sites, all compensated/whitelisted`. |
| **REL-M1b** | `_r3_palette_probe.py` — a Ctrl+K palette restyle probe. **Nothing ran it** (not named `e2e_browser_*.py`, so the gate never discovered it), and it **crashed rather than failed**: it filtered on `"script"`, which matches nothing in a project-less studio (the only such label, *"Search the script"*, is project-only by design), so `.palette-row` never rendered and `rows.first.evaluate()` raised a TimeoutError. It also hardcoded the **nocta** violet `rgb(126, 107, 255)` while `tungsten.css` — a cascade layer loading *after* `style.css` — re-pins the lamp to gold `#e8c56a`. | Reproduced: `TimeoutError: Locator.evaluate: Timeout 30000ms exceeded … waiting for locator(".palette-row").first` |

**Both were promoted into real gates rather than deleted:**

| New gate | Checks | Mutation-verified |
|---|---|---|
| `tests/test_a11y_outline_guard.py` | 5 (the gate, a parser-sanity check so a silent parse failure cannot make it vacuous, an anti-stale whitelist check, an injection self-test, and an inverse check that a *compensated* suppressor is not flagged) | ✅ **4/4** |
| `tests/e2e_browser_palette_restyle.py` | 11 — auto-discovered by the browser gate | ✅ **4/4** |

The palette suite is now **theme-independent**: instead of naming a colour it compares the
focus ring against the input's own `border-color`, which the same rule sets to `var(--accent)`.

**R11–R14 — measured, and reduced to one owner decision.** `.git` is 82 MB, and **69.24 MB
of it (84%) is two blobs**: `.freebuff/desktop-v2.db` (36.61 MB) and `.freebuff/desktop-v2.db-wal`
(32.63 MB). They are **not on `main`** — `git rev-list --objects main | grep .freebuff` returns 0 —
and are reachable only from `refs/remotes/origin/legacy/pre-recovery`, which still exists on the
remote. So the bloat is one dead branch, not history debt on the project's own line. Not executed:
deleting a shared remote branch is irreversible and is the owner's call. Full detail and the exact
commands are in §REL-M2 of the audit.

### The harness bug this pass, worth keeping

The first M4 mutation removed *both* focus mechanisms (the palette's own `input.focus()` and
`openModal`'s), yet the suite still passed — and the mutation harness printed `GUARD MISSED`.
It was the **harness** that was wrong: it wrote `ORIG[path].replace(old, new)` once per edit, so
the second write **discarded the first**, silently reducing a two-edit mutation to one. Edits are
now applied cumulatively to an in-memory copy and written once.

Two more traps this pass, both the same shape as ones already recorded:
* **Check your mutation is a violation.** The first attempt removed only `openPalette`'s
  `input.focus()`. `openModal` already focuses the first `input|textarea|select` in the overlay
  (`app.js:7653-7655`), so that alone is a **behavioural no-op** and the suite was right to pass.
* **A crash is not a caught mutation, and a pass is not a guarded check** — the promoted palette
  suite had to be verified *both* ways.

---

## Closed in this pass (2026-09-21, pass 7)

Three items had been sitting on the list marked *owner decision* rather than
*engineering*. The owner decided all three in one go.

| ID | Decision | What landed |
|---|---|---|
| **R6** | **Keep it private** | `LICENSE` — a proprietary, all-rights-reserved notice. This is the private answer *made explicit*: with no file at all the position is ambiguous (and some tooling and would-be readers assume "no licence" means "open source"), whereas the notice states plainly that no rights are granted, names the four things that are not permitted, and scopes itself so it does **not** appear to cover third-party dependencies. `CHANGELOG.md` — a Keep-a-Changelog file, dated rather than versioned (there are no release tags), summarising the audit work at product level and pointing at `docs/audit/` for the evidence. Both added to `MANIFEST.in` so the sdist carries them. |
| **R7b** | **Lock it** | `requirements.lock.txt` — exact pins for the **entire declared dependency closure** (32 packages), and CI now installs with it as a **constraints** file. |
| **BE-M3** | **Not required** — accepted as-is, with the fix shape recorded | No code change. See below. |

### R7b in detail — why a *constraints* file and not a `pip freeze` dump

`requirements.txt` and `pyproject.toml` declare **floors** (`requests>=2.31.0`).
Two people installing the same repo can therefore resolve different versions of
the same dependency, and "green on my machine" stops meaning anything — the same
class of hole as the floating `ruff` pin closed in pass 2.

The lock is applied with `-c`, never as a second requirements list:

```
pip install ".[ci]" -c requirements.lock.txt        # CI + dev
pip install -r requirements.txt -c requirements.lock.txt
```

The distinction matters because this file is **derived on Windows / Python 3.13
while CI runs ubuntu-24.04 / Python 3.12**. `-c` only constrains packages pip
was already going to install, so an entry nothing needs is inert — `colorama`
(pytest's win32 dependency) is a genuine pin here that simply never installs on
the runner. A flat `pip freeze` would have hard-coded this machine's resolution
and, in the other direction, would have dragged in every package's *own* dev
extras (walking `requires_dist` naively pulls in setuptools' sphinx / tox /
mypy / jaraco-\* test stack — 127 names instead of 32).

**Five guards** in `tests/test_production_readiness.py`:

| Guard | The promise it enforces |
|---|---|
| `test_the_lockfile_is_a_lock_and_not_a_wish_list` | every line is an exact `==` pin — a `>=` here re-opens the drift the file exists to close |
| `test_every_declared_dependency_is_pinned_or_explained` | every declared dep is pinned **or** on a documented exception list, and the list may not go stale |
| `test_no_pin_is_older_than_the_floor_it_has_to_satisfy` | no pin contradicts its own declared floor |
| `test_the_lockfile_has_no_duplicate_entries` | the file does not say two things about one package |
| `test_ci_installs_from_the_lockfile` | **the anti-decoration check** — wherever CI installs the full environment it must apply the lock |

**Mutation-verified 7/7**, all restored byte-identical: a `>=` sneaks in · a
declared dep loses its pin · a pin drops below its floor · a package is pinned
twice · the test-python job stops applying the lock · the test-browser job
stops applying the lock · a pin is added for something still listed as an
exception.

**Honestly not pinned** (stated in the file's header, not hidden): `faster-whisper`
(the opt-in `stt` extra — no measured version exists) and `pytest-cov` (CI installs
it, no development environment here has, so any pin would have been *invented*).
Four more names are absent for a good reason: `importlib-metadata`,
`exceptiongroup`, `tomli`, and `backports-asyncio-runner` are all gated by
`python_version < "3.10"` / `< "3.11"` markers and are correctly not installed on
3.12+.

### BE-M3 — accepted, not fixed (owner call: *"not required"*)

Recorded so a future session does not re-litigate it: **if** it is ever fixed,
the shape is a **CAS retry loop** (read, re-check the store is unchanged, write,
retry on conflict) — *not* two `lock_for` locks held at once, which
`jsonio.lock_for`'s one-lock-at-a-time invariant forbids because that is the one
way to deadlock them. The defect stays proven and reproducible
(`.workbuddy-ai/scratch/be_m3_instrument.py`: two children read `len=7`, both
write `len=6`); the harm is narrow (two *simultaneous* undos of one project) and
non-destructive (the working copy stays correct, only history bookkeeping drifts).

### Found while doing R7b: three stale doc claims

The audit's §4 rated Docs **🟡 Drifting** for "source-of-truth claims that are now
false". Two of them were the same sentence in two files, and fixing them was
one line each — so they are done rather than re-listed:

- `docs/ARCHITECTURE.md` §4 said *"requirements.txt — project dependencies (no
  `pyproject.toml`)"*. `pyproject.toml` exists and is the build's source of truth.
- `docs/DEVELOPMENT.md` said *"There is no `pyproject.toml` — `requirements.txt`
  is the source of truth."* Same fix, plus the lock in the install command.
- `NOTES.md`'s **Decisions** section still carried the original false decision.
  Left in place with a *superseded* note rather than deleted, so the correction
  is visible — the same treatment the audit's own "hollow core" sentence got.

---

## Closed in this pass (2026-09-21, pass 5)

| ID | Item | Proof | Mutation |
|---|---|---|---|
| **R9** | The audit's *"45-min CI budget vs a 125-min worst case"* was an **unverified teammate figure**, and the wrong thing was being watched | Measured: the browser gate is **303 s (5.05 min) for 28 suites**, sequential, against the job's `timeout-minutes: 45` — ~9× headroom. The "125 min" is unreachable **by construction**: a job-level `timeout-minutes` is a hard cap, so no run can exceed 45 min; 125 reads as a sum of per-suite worst-case *waits*, which the job timeout pre-empts. The actual hole was that **nothing guarded the declaration** — a job without `timeout-minutes` inherits GitHub's **360-minute** default, so one hung suite burns six hours. `test_every_ci_job_declares_a_timeout` now parses `ci.yml`'s `jobs:` block and refuses an unbounded job. | ✅ **2/2** — removing the browser job's timeout, then the lint job's, each turns the guard red. It is **per-job**: it does not settle for "at least one job has one" |
| **T2c** | No test enforced route coverage, so the next untested route would be found only by another hand sweep — and the pass-4 sweep was **wrong in both directions** (it missed a composed path, and credited the cowriter server with the webapp's paths) | New gate: `tests/route_recorder.py` (a `before_request` hook on both module-level Flask apps) + `tests/test_route_coverage.py`, which requires every route in the **authoritative** `app.url_map` to be exercised **or** declared with a reason, and rejects **stale** declarations. It found **7 blind spots on its first run** (6 webapp + the cowriter's auto `/static`). `tests/test_route_smoke.py` (11 tests) now drives 6 of them at their real contracts — the health probe, the metrics view behind the status strip, the finding-intent store, and the validation paths of the two SSE routes and translate. The 7th is declared: Flask auto-registers it against a `static/` folder that does not exist. | ✅ **4/4, delta-verified** — a route loses its only test → reported undeclared; a **new** route added with no test → caught; the recorder detached → the wiring check reports itself; a **stale** declaration → the registry-rot check fires |

| **T3b** | The audit's last test-integrity item — *"no other suite was audited for the same throwing-wait shape"* | Audited all 33 browser suites: **21 vacuous checks remain**, classified by class (see the T3b section). The one genuinely unbacked check — `phase14:87`, "the structure card saves beside the idea", backed by nothing but a 600 ms sleep — now asserts the button's own `"Saved ✓"` confirmation. | ✅ making the save never confirm turns the check **FAIL** (`the save button never showed its confirmation`); suite green at baseline (47 passed), `app.js` restored byte-identical |

**The pass-5 harness lesson (worth keeping).** The first mutation run reported
"4/4 caught" and was **not trustworthy**: it ran only a two-file subset, and the
gate legitimately fails a partial run (it asserts *"every route was exercised by
this session"*), so `rc != 0` was already true at baseline. The verdict was
rewritten to a **delta** — each mutation's signature must be **absent in the
baseline run of the same scope and present under the mutation** — which also
revealed that one mutation (a stale declaration) *cannot* be observed in a subset
at all, because the undeclared-route assertion fires first. It now runs the full
suite. `rc != 0` is not evidence; a signature that moved is.

---

## T3b — the throwing-wait shape, audited across all 33 browser suites

The audit's last test-integrity item: `library_delete`'s flake was retired in pass
3, but *no other suite had been audited for the same shape*. Swept every suite for
checks whose condition cannot fail (literal `True`, `>= 0`, `or True`,
`isinstance`) and classified each by what actually backs it.

**The sweep needed two corrections before its numbers could be trusted — both
false positives, both in the direction of over-reporting:**

- `>=\s*0\b` also matches `>= 0.7` (a digit→dot transition *is* a word boundary),
  so real width assertions (`pw / cw >= 0.7`, the manuscript-width checks) were
  flagged as tautologies. Fixed with `(?![.\d])`.
- A `check(name, True)` sitting inside a **comment** was counted as a check.
  Fixed by skipping comment lines.

**Result: 21 vacuous checks remain across 8 suites.** They are not one defect, and
the difference decides the action:

| Class | Count | Where | Action |
|---|---|---|---|
| Backed by a **throwing** call | 9 | `phase14` ×4, `smoke` ×2, `selection_translate` ×2, `rewrite_loop` | benign — the wait throws, so the guarantee **is** enforced; a count-inflater, same class as the 10 documented in pass 3 |
| **Diagnostic dumps** | 6 | `identity_forensics` ×5, `layout_audit:215` | the payload is in the check's *detail* string ("token truth dumped", "scroll census: …"). Not assertions by intent |
| **Timing-conditional markers** | 2 | `phase14:121`, `phase8:81` | inside `if running_seen:` — the branch condition **is** the observation. Asserting harder would be **flaky** (the demo model is fast; the running window can be missed) — the `library_delete` trap in reverse |
| **Conditional on nothing happening** | 1 | `layout_audit:317` | "fix loop skips cleanly with no findings" — vacuously true when there are no findings |
| In a suite the gate **does not run** | 3 | `gun_pen_audit` ×3 | needs a live `llama-server` (T1e, unchanged) |
| **Genuinely unbacked — FIXED** | 1 | `phase14:87` | below |

**The one real gap.** `check("premise: structure card saves beside the idea", True)`
was backed by nothing but `page.wait_for_timeout(600)`. A sleep cannot fail, so the
check passed **even if the POST never happened** — while its name made a specific,
checkable promise. `saveIdeaStructure()` sets the button to `"Saved ✓"` and reverts
it 1400 ms later, so the confirmation *is* observable. The check now waits for that
confirmation and asserts it (the button's resting text is `"Save structure"`, so the
"Saved" prefix cannot be satisfied by the idle state). **Mutation-verified:** making
the save never confirm turns the check **FAIL** with
`the save button never showed its confirmation`; the suite is green at baseline
(47 passed) and `app.js` was restored byte-identical.

**Why this stays an audit and does not become a third gate.** "Backed by a throwing
call" measures **proximity, not semantics** — a `wait_for_selector` for element A
five lines earlier does not back a claim about element B. So the count of
genuinely-unbacked checks *cannot* be settled by a sweep, and the classification
above required reading all 21 sites. Route coverage could become a gate because "was
this route exercised" is a runtime fact the recorder answers objectively; "is this
check meaningful" is a judgement, and a gate over a judgement is a gate that lies.

---

## Closed in this pass (2026-09-21, pass 3)

| ID | Item | Proof | Mutation |
|---|---|---|---|
| **T1** | 4 browser checks that could not fail: `ideas.py` (`... or True`, and the literal was the *wrong project's* title), `ideas_v3.py` (`... or True`), `phase6_evidence.py` ×2 (`count() >= 0`) | rewritten as real assertions with the precondition folded in; suites green (14 / 14 / 33) | ✅ **4/4** — title never grows (`title='Untitled idea'`); summon doesn't open the drawer (`room-drawer class='drawer'`); Setup/Payoff never renders (`report.setup_payoff=True sections=0`); dismiss is a no-op (`before=8 after=8`) |
| **T1b** | `selection_translate.py` — *"translation adds no new chat turns"* computed the count, printed it in the detail, and asserted **nothing** (`check(name, True, …)`). The comparison was never written | captures the count before the action, asserts equality | ✅ making translation append a turn → red (`before=1 after=2`) |
| **T1c** | `library_delete.py` — the ghost-entry guarantee rested entirely on a `wait_for_selector`; the check behind it was `check(name, True)`. **This is the suite that failed the gate** (timeout) and then passed 2/2 standalone | bounded poll + real assertion; a slow re-render now yields a clean FAIL, not a crash | ✅ dropping `loadLibrary()` from `deleteProjectFlow` → red (`empty_hints=0 library_rows=2`) |
| **T1d** | `phase7_chat_lenses.py` — *"reopen re-adopts the SAMEER conversation"* was `check(name, True)` naming a contract the app does not promise; the real contract is asserted 6 lines below (`adopted_any`) | **deleted**, not converted — coverage unchanged, count honest | n/a (deletion) |
| **T3** | `library_delete` flaked in the 32-suite gate (1 failure) and passed **2/2 standalone** — a flake, not a regression (no production code changed this pass) | fixed by the T1c rewrite: the throwing `wait_for_selector` became a bounded poll | ✅ re-ran the full gate: **28 pass, 0 fail** |
| **T2** | *"~8 test files assert on source text, not behaviour"* — the audit called this the highest-value unverified claim | **verified and downgraded** — see below | ✅ for the one hollow check (4/4) |

**All of the above is test-only** — no production code was touched in pass 3
(`git diff --stat screenplay_studio/` is empty). 6 mutations, 6 caught; every
mutated file restored byte-identical.

---

## T2 — the verdict (this was the audit's highest-value open claim)

The audit reported that ~8 test files, including `test_production_readiness.py`,
"assert on the *text of the source file* rather than runtime behaviour", and
called it the single highest-value thing to check before trusting the suite.
**I read the file in full and classified every source-text assertion.** The claim
is true in form and materially overstated in implication:

- **Legitimate structural guards** that *cannot* be behavioural — asserting the
  **absence** of a dangerous pattern (no live `app.run(host="0.0.0.0")`; no raw
  `open("premise.json", "w")`), a CSS `@container` contract, and a duplication
  guard ("there is ONE `inFindingFilter` predicate"). You cannot exercise a
  non-existent call; a CSS rule has no runtime.
- **Already behavioural** — `TestAtomicWrites` patches `jsonio.atomic_write_json`
  and asserts the real code path called it. That is not a source read.
- **Source-side companions** to real browser checks, and they say so in their own
  docstrings (`TestManuscriptMarginContract` names
  `e2e_browser_phase13_legacy_cleanup.py` as the behavioural counterpart).
- **Exactly one genuinely hollow check** — `TestDemoHonesty` regexed
  `demo_model.py` for `"issue": "…"` literals, proving a label string exists in a
  file, not that the model emits it. **Now behavioural:** it drives the model's
  own dispatch (`_decide_reply`) with the four trigger phrases the analyzer
  actually sends (confirmed against `screenplay_analyzer/prompts.py`) and asserts
  every emitted finding is labelled and correctly categorised. 1 test → 4.
  Mutation-verified 4/4, each failure hitting **one case** (so it is per-pass,
  not aggregate).
  *Honest note:* my first mutation dropped only the `[demo]` tag and the check
  still passed — the label contract is an **OR** (`[demo]` **or** "demo model"),
  and the sentence still carried "demo model". The mutation was wrong, not the
  test.
- **Still unverified, and staying open:** the "two silent skips" and the thin
  HTTP reach (~85 routes, only a minority driven).

---

## T2b — the two remaining claims, adjudicated

The audit left two claims in this section unverified. Both are now measured.

### Claim 1 — *"two triage tests skip rather than fail, hiding their own absence"* → **DISPROVEN**

Measured with `-rs`: the only 3 skips in the entire suite come from **one** site —
`test_store_fault_injection.py:489` — and they are deliberate and justified: a store
that is not load-modify-write structurally cannot clobber what it never read, so the
overwrite scenario does not apply to those cases. **Zero triage tests skip.**

But the three triage guards were a **latent trap**: `pytest.skip("mock analysis
produced no findings")` in `test_feature_batch.py` ×2 and `test_preview_lab.py`. They
do not fire today — but *"the analysis produced no findings"* is exactly the signature
of the **R1 bug** (a wheel that shipped zero craft rules, so every report came back
empty). A silent skip there would hide that whole class of regression as "not run".
All three now `assert` instead, with the reason in the message.
**Mutation-verified 3/3** by forcing an empty fixqueue: each fails loudly with the
assertion text, and **none** reports SKIPPED.

Also: `pyproject.toml` gained `addopts = "-rs"`, so skips are itemised on every run
with their reason. This repo's rule for the browser gate is already "a skipped suite is
never hidden" (`run_browser_suites.py` prints every exclusion loudly); pytest was the
one place a skip showed up as a bare count.

### Claim 2 — *"only a minority of ~85 routes are driven by a real Flask test client; `screenplay_cowriter/server.py` has zero tests"* → **HALF FALSE, HALF TRUE**

A route-reach sweep (regex per route, `<placeholder>` → one path segment, searched
across `tests/`) gives:

- **`webapp_server.py`: 71 distinct routes, 64 referenced by tests (90%).** Not a minority.
- **`screenplay_cowriter/server.py`: 7 distinct routes, 0 reachable.** The "zero tests" claim is **TRUE**.

**Self-correction — the sweep produced false positives in BOTH directions, and I
checked each rather than trusting the number:**

- `/api/projects/<name>/beatboard/reset` showed as *unreached*, but
  `test_beatboard.py::test_reset_endpoint` **does** drive it — the test composes the
  path as `f"{base}/reset"`, so the full string never appears contiguously.
- Conversely the sweep's "6/7 cowriter routes reached" was **false**: those matches were
  the *webapp's* own `/api/…/chat/sessions` paths. Nothing in the repo imports
  `screenplay_cowriter.server` — only its own docstring names the module.

So the heuristic was wrong in the *optimistic* direction for exactly the module the
audit was right about. Treat "reached" as a question, not a finding.

### The one true finding — closed

`screenplay_cowriter/server.py` is a documented entry point (`python -m
screenplay_cowriter.server`; AGENTS.md's "each piece runs its own local server"
architecture) with **zero coverage** — no test, and no other module imports it, so a
break would ship silently. New `tests/test_cowriter_server.py` (**20 tests**) drives
all 7 routes through the Flask test client, with the two model-dependent ones
(`POST /sessions`, `POST /sessions/<id>/messages`) pointed at the repo's shared mock
llama-server — no real model needed. Error paths included: 502 for a dead model
server, 404 for unknown sessions, and 400 for a missing fork name / unknown branch /
unknown persona / empty message text.

**Mutation-verified 6/6:** wrong `/health` payload; 502 → 500; empty text accepted;
`/fork` leaking `ValueError` as a 500 instead of translating it to 400; `/switch` the
same; persona validation removed.

*Honest note:* the first 502 mutation deleted the `except` clause outright, leaving a
dangling `try` — a SyntaxError, so pytest reported a **collection error** (rc=4) and my
harness scored it "caught". That was the mutation being wrong, not the guard holding.
Redone as a clean `502 → 500` change it fails properly (`assert 500 == 502`).

---

## The check count, honestly

> **SUPERSEDED 2026-09-21 (pass 10).** Every vacuous check below is now **fixed**:
> the sweep returns **0**, and the two suites whose totals were inflated
> (`identity_forensics` 6 → **1**, `layout_audit` 30 → **24**) shrank. The gate's
> browser total went **660 → 650** — *down*, because 11 checks that asserted
> nothing are gone and 9 that asserted nothing became checks that can fail.
> See the pass-10 section. The analysis below is kept because its classification
> is what decided each action, and because the reasoning it corrects is the
> reason this took three passes to close.

The audit's headline correction was "4 of 476 browser checks cannot fail → 472".
Sweeping for the same shape found **more than four**, and they are **not all the
same defect** — the difference decides the action.

**Pass 3 fixed 7 of them:**

| Kind | Count | Action |
|---|---|---|
| Value-shaped tautologies (`x or True`, `count() >= 0`) — *look* like assertions on a value | 4 | ✅ fixed 1:1, mutation-verified |
| Unbacked `check(name, True)` — the assertion was never written | 2 | ✅ fixed (1 converted, 1 deleted) |
| `check(name, True)` behind a throwing wait, where the wait *was* the assertion | 1 | ✅ fixed (T1c) |

**Pass 5 widened the sweep to every suite** (see T3b): **22 vacuous checks in
total, 1 of them genuinely unbacked and now fixed.** The remaining 21 are classified
by what backs them, and only 18 of those are in suites the gate actually runs
(`gun_pen_audit`'s 3 are excluded without `E2E_BASE`).

**And the headline total itself was wrong — in the *conservative* direction.** The
gate now reports **28 suites / 522 checks / 0 failed** (measured from
`run_browser_suites.py`), not the audit's "25 suites / 476 checks", which predates
three suites entering the gate. The honest composition:

| Kind | Count | Failable? |
|---|---|---|
| Real assertions | ~504 | ✅ yes |
| Step markers whose guarantee is enforced by a **throwing** call or a **branch condition** | 9 (in-gate) + 10 (documented in pass 3) | ⚠️ the *guarantee* is real; the check itself cannot fail |
| Diagnostic dumps — the payload is the check's *detail* string | 6 | ❌ no |
| Conditional on a timing window / on nothing happening | 3 | ❌ no |
| In `gun_pen_audit` (the gate does not run it) | 3 | n/a |

So the audit's "476, all failable" became "472 failable of 476" and is now, measured,
**504 failable of 522**. The number the audit was really chasing — a check that is
**unbacked *and* cannot fail** — is **zero** across every suite the gate runs. The
remaining 18 are backed by something that can fail, or are reporting steps by design.

**Why the 10 markers from pass 3 are left alone:** they cannot hide a regression —
the preceding throwing call fails the suite — so converting them adds no assurance,
while turning a marker into a DOM re-read introduces a *new* flake risk (the element
can re-render between the wait and the check). The **latent trap is recorded**: if
the preceding `wait_for_selector` is ever deleted, the marker silently becomes the
only guard, and it is vacuous.

**Why the 3 in `gun_pen_audit` are not fixed blind:** that suite requires a live
studio pointed at a real `llama-server` and a pre-seeded `gun_pen_2` project, so it
cannot be executed here. An unverified test edit is exactly the failure mode this
whole section is about.

---

## Proven, deliberately NOT fixed

| ID | Item | Evidence | Why deferred |
|---|---|---|---|
| **BE-M3** | `undo_last_edit` / `redo_last_edit` read-modify-write `edits.json` + `edits.redo.json` **without holding `lock_for` across the cycle** (each read and each write is locked; the gap between them is not) | 3 real children behind a file barrier: **two read `len=7`, both wrote `len=6`** — the log loses an entry relative to the reversals the working copy actually got. Script: `.workbuddy-ai/scratch/be_m3_instrument.py` | **Owner decision (pass 7): not required.** Accepted as-is, and the fix shape is now recorded so it is not re-litigated: a **CAS retry loop** (read → re-check the store is unchanged → write → retry on conflict), *not* two `lock_for` locks held at once (forbidden by the one-lock-at-a-time invariant, which exists to prevent deadlock). Harm is narrow (two *simultaneous* undos of one project) and non-destructive: the working copy is correct, only the history bookkeeping drifts. |

---

## Open (not started)

| ID | Item | Class | Owner |
|---|---|---|---|
| **R11–R14** | **CLOSED (pass 11).** The stale `legacy/pre-recovery` remote branch was deleted (`git push origin --delete`); the local stale tracking ref was dropped and `git gc --prune=now` reclaimed **83M → 22M** (~61 MB). Before deletion `.git` was 82 MB with 69.24 MB (84%) in two blobs reachable only from that branch. The 22 cline checkpoint refs hold no large blobs. | hygiene | **closed — pass 11** |
| **T1e** | ~~The 21 remaining vacuous browser checks~~ — **CLOSED (pass 10).** All 21 audited, fixed, and mutation-verified: **0 vacuous checks remain** (the sweep that found 21 now returns 0). See the pass-10 section. | test integrity | ✅ done |
| **NEW (pass 10)** | **CLOSED (pass 12).** `library_delete` flaked in the gate once (`shelf delete emptied the disk`, 30/31 suites green), then passed **3/3 standalone** and on the gate's second run. Pass 10 filed it open because the flake was not reproducible and a production fix would have shipped unverified — the right call at the time. It turned out to be a **real defect, not a slow poll**: `delete_project` called `shutil.rmtree(project_dir, ignore_errors=False)` with **no retry**, and on Windows that raises `PermissionError` (errno=13, **winerror=32**) while any handle to a file inside the tree is open. And because `rmtree` deletes as it walks, the failure did **not** fail cleanly — it left the project **HALF-DELETED**. Reproduced deterministically by holding one real `open()` on one file of a two-file tree: `['project.json']` remained while `parsed.json` was gone — which is exactly the observed symptom (the shelf row survives, so the disk never "empties"). Both `rmtree` sites — `delete_project` *and* `IdeaStore.delete`, which the item never named — now go through **`jsonio.retry_permission`** and answer with a clear JSON error instead of a raw 500. | robustness | ✅ **done — pass 12** |
| **NEW (pass 9)** | **CLOSED (pass 11).** The 25 orphaned `preview-redesigns/shots/` PNGs were untracked via index-only `git rm --cached -r` (after a `git rm -r` incident that wiped 91 sibling files and was recovered with `git reset --hard`), committed + pushed in `91a11b1`. The dead `.gitignore` rule was fixed to the real nested path. Disk copies remain, now gitignored. | hygiene | **closed — pass 11** |
| **NEW (pass 13)** | **CLOSED (pass 14).** Pass 13 "closed" `design_session` by **pinning** the `frame-ancestors 'none'` block as a check — which documented a dead product surface instead of fixing it. Pass 14 relaxed the directive to `'self'` (a foreign page still cannot frame the desk; the app's own origin can), removed the console's last hardcoded host:port, made it drive the framed app through the app's **own** `applyDawn()`, and flipped the suite to assert the frame **renders** with **zero** CSP refusals. | product surface | ✅ **done — pass 14** |
| **NEW (pass 14)** | **CLOSED (pass 14).** The desk had **no bearer header anywhere in the codebase**, so a token-protected OpenAI-compatible endpoint was not a supported setup — it half-worked and then 401'd in a way that looked like the model was broken. Now one Settings form covers both (Local / Remote over shared fields), with the mode *derived* from the URL, `api_key` on `ServerConfig` + `ProjectManifest`, `auth_headers()` threaded into every client, `--api-key`/`$SCREENPLAY_STUDIO_API_KEY` on the studio and both CLIs, and the token **never** echoed back over HTTP. Remote stays a launch-time opt-in. | feature / security | ✅ **done — pass 14** |

**R10 is closed** — see the pass-8 section below. It was filed as hygiene and turned out to
hide two broken guards.

**The two `KNOWN_BROKEN` suites are closed** — see the pass-9 section above. Both were filed
as *"crashes"*, and in both cases the crash was concealing far more than itself.

---

## Pushes from this sandbox: diagnosed, and worked around

Passes 5 and 6 hung on push for **3–12 minutes each, four times**, with `git push -v`
printing `Pushing to …` and nothing more. It is an **environment** fault, not the
repo. Bisected to the line:

| Probe | Result |
|---|---|
| `git ls-remote origin main` (upload-pack) | **200** in 0.4 s — the network is fine |
| `curl` GET / POST to github.com | 200 / 404, both < 0.4 s — **outbound POST is not blocked** |
| `/info/refs?service=git-receive-pack` | **401** in 0.3 s — reachable; the stall is **auth**, not transport |
| `printf 'protocol=https\nhost=github.com\n\n' \| git credential fill` | exit **0** — the helper *does* answer `fill` |
| `GIT_TRACE=1 GIT_CURL_VERBOSE=1 git push` | **the smoking gun** — see below |

The trace ends like this:

```
=> Send header: Authorization: Basic <redacted>
<= Recv header: HTTP/1.1 200 OK
<= Recv header: Content-Type: application/x-git-receive-pack-advertisement
== Info: Connection #0 to host github.com:443 left intact
trace: run_command: 'git credential-helper-selector store'      <-- never returns
```

So: the 401 is answered, the helper supplies a credential, GitHub returns **200 with
the ref advertisement** — and then git calls the helper's **`store`** action, which
**hangs forever**. The pack POST is never sent. `fill` works; `store` blocks. Neither
`GCM_INTERACTIVE=never` nor `GIT_TERMINAL_PROMPT=0` prevents it. A push can also land
early in a session and stop later (the cached credential expires mid-session — here
`c6656df` pushed fine, then everything after it hung).

**The workaround: intercept the helper so `store` is a no-op and everything else
passes through.** Nothing about the credential changes — the `fill` path is untouched
and nothing is printed.

```bash
HELPER="C:/Users/<you>/.workbuddy-ai/binaries/PortableGit/versions/<v>/mingw64/bin/git-credential-helper-selector.exe"
git -c credential.helper= \
    -c "credential.helper=!f() { [ \"\$1\" = store ] || \"$HELPER\" \"\$@\"; }; f" \
    push origin main
```

With it, the same push that had hung for 12 minutes completed in **11 seconds**
(`c6656df..fa6e952  main -> main`). A ready-made script is at
`.workbuddy-ai/scratch/push_wrapper.sh`.

**Verify with `git ls-remote`, never with the push output** — see the repo's
long-standing tracking-ref caveat at the top of this file.

---

## Conventions for this tracker

- An item moves to **Closed** only when it has a commit hash, a guard test, and
  a mutation check proving the guard fails on the pre-fix code.
- "Executed" beats "inferred": a claim backed by a run outranks one backed by a
  reading of the source.
- Findings discovered while fixing an item are added as new rows, never folded
  silently into the item that surfaced them.
- An item that is real but needs a design decision goes to **Proven, deliberately
  NOT fixed** with its evidence — never quietly implemented inside another fix.
- A check that cannot fail is a **defect**, not a style nit: it inflates the
  count and silently retires the guarantee.
