# Fix Tracker — production-readiness pass

**Live document.** Updated as each item lands, so the state of play is readable
without re-deriving it from `git log`. Source audit:
`docs/audit/production_readiness_2026-09-21.md`.

**Last updated:** 2026-09-21 (pass 6 — T3b closed: all 33 browser suites audited
for the vacuous-check shape; the one genuinely unbacked check fixed; two of the
audit's own headline numbers corrected)
**HEAD:** `fa6e952` — **pushed**; `git ls-remote origin main` agrees (the push
needed the credential-helper workaround below)
**Baseline for this pass:** `c6656df`

---

## Gate status

| Gate | Command | Result at this pass |
|---|---|---|
| Unit + integration | `python -m pytest tests/` | **1559 passed, 3 skipped, 0 failed** |
| Lint | `ruff check .` | **clean** |
| JS unit | `node --test tests/js/*.test.js` | **16 / 16** |
| Browser E2E | `python tests/run_browser_suites.py` | **32 suites: 28 pass, 0 fail, 2 skip, 2 known-broken** — **522 checks** (measured; 504 of them genuinely failable) |

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
| **BE-M3** | `undo_last_edit` / `redo_last_edit` read-modify-write `edits.json` + `edits.redo.json` **without holding `lock_for` across the cycle** (each read and each write is locked; the gap between them is not) | 3 real children behind a file barrier: **two read `len=7`, both wrote `len=6`** — the log loses an entry relative to the reversals the working copy actually got. Script: `.workbuddy-ai/scratch/be_m3_instrument.py` | The fix needs either **two store locks held at once** (forbidden by `jsonio.lock_for`'s one-lock-at-a-time invariant, which exists to prevent deadlock) or a **CAS retry loop**. Both are design decisions. Harm is narrow (two *simultaneous* undos of one project) and non-destructive: the working copy is correct, only the history bookkeeping drifts. |

---

## Open (not started)

| ID | Item | Class | Owner |
|---|---|---|---|
| R7b | No lockfile (deps use `>=` floors) | supply chain | **owner decision** — changes the dependency workflow |
| R6 | No LICENSE / CHANGELOG | release | **owner decision** |
| R10 | Root scratch files tracked in git | hygiene | open |
| R11–R14 | 69 PNGs in `docs/audit/`; `.git` 78 MB from 22 cline checkpoint refs | hygiene | open |
| **T1e** | The 10 step markers above (documented, not defects) + the 2 in `gun_pen_audit` (need a live `llama-server`) | test integrity | open |

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
