# Screenplay Studio — E2E Implementation & Production-Readiness Audit

**Date:** 2026-09-24 · **Revision audited:** `qoder/update` @ `eccbdca` **+ an uncommitted working tree**
**Scope:** the e2e implementation itself (is the green suite real evidence?) and the product's alignment with production readiness, UI/UX and backend, ranked by impact.
**Method:** everything below is *executed* on this machine unless the finding says otherwise. Each finding carries an explicit evidence grade.

> **No product code was written or modified for this audit.** Probes ran from `.workbuddy-ai/scratch/` (gitignored). The working tree is byte-identical to how I found it.

---

## 0. Executive verdict

**The e2e suite is real evidence, and the product is close to production-ready. Two gaps are worth fixing before release, and both are *assurance* gaps rather than broken behaviour.**

1. **The suite is genuinely green and genuinely failable.** pytest **1684 passed / 3 skipped / 0 failed**; the browser gate **46 suites, 45 passed, 0 failed, 1 skipped, 1138 checks** in 11m57s. A mechanical AST sweep for the "always-true check" shape (`Checks.ok` with no condition, literal-constant conditions, `count() >= 0`, `x or True`) returns **zero hits** across all 47 suite files. The prior audit's T1/T1e closures hold.

2. **Two high-impact gaps, both about *what is not being watched* rather than what is broken:**
   - **`BE-1`** — the server accepts **any `Host` header**. A website the writer visits can DNS-rebind to `127.0.0.1:<port>` and read their entire screenplay. **Executed and proven.**
   - **`E2E-1`** — the **loopback bind has no guard that can fail**. The one test named for it reads a file that no longer contains an `app.run` at all. Change `host="127.0.0.1"` → `host="0.0.0.0"` and **both gates stay green** while the app exposes every project to the LAN. This is the same defect class the 2026-09-20 audit's B2 closed — the fix shipped, the guard did not.

3. **The single most valuable thing an owner can do next** is close those two, then commit the in-flight work (§6) — because right now the in-flight fixes are green on this machine and invisible to CI.

---

## 1. What I executed (evidence, not inference)

| # | What | Result |
|---|---|---|
| 1 | `pytest tests/ -q` (full backend/unit suite, cache disabled) | **1684 passed, 3 skipped, 0 failed** in 160s |
| 2 | `python tests/run_browser_suites.py` (all 46 suites, real chromium) | **45 passed, 0 failed, 1 skipped, 0 known-broken**, exit 0, **1138 checks**, 11m57s |
| 3 | Live Host-header probe against a booted studio | **foreign `Host` accepted, reads served 200** (§3 BE-1) |
| 4 | Live read-exposure probe (seeded project, no token) | **full screenplay returned** to `Host: evil.attacker.com` (§3 BE-1) |
| 5 | Live write probe under foreign `Host` + foreign `Origin` | **403 — writes are correctly blocked** |
| 6 | Path-traversal probe, 9 payloads (`..%2f`, `..%5c`, `%00`, `con`, `AUX`, 400-char name) | **all 400/404, none 200** |
| 7 | AST sweep for vacuous checks across 47 suite files | **0 hits** |
| 8 | Regex-vacuity probe on the bind guard | **assertion cannot fail; predicate is sound but aimed at a file with no `app.run`** |
| 9 | Mechanical search for a test asserting the shipped bind host | **none exists** |

Skipped by design, and named with a reason (never silent): `gun_pen_audit` — it runs a real analyze and needs a `llama-server`, which the gate does not have.

---

## 2. Production-readiness scorecard

| Dimension | Grade | Basis |
|---|---|---|
| Test-suite integrity (can the green suite fail?) | **A−** | 0 vacuous checks in the gate; but §4 E2E-1/E2E-2/E2E-3 are assurance holes |
| Security — write paths | **A** | token + `SameSite=Strict` + `hmac.compare_digest` + Origin check; traversal probe clean; XSS/CSP closed and re-verified |
| Security — read paths | **D** | any `Host` accepted; reads unauthenticated (BE-1) |
| Data integrity | **A−** | cross-process byte-range locks, unique+fsynced temp files, MISSING≠DAMAGED; fault-injection registry |
| Privacy contract ("nothing leaves the machine") | **B−** | outbound model/STT URLs correctly pinned to loopback; but the *inbound* read surface is open (BE-1) |
| Observability | **D** | no logging configuration anywhere in the shipped packages (BE-4) |
| Packaging / release | **B** | wheel+sdist carry every asset (guarded); the guard never installs and serves (E2E-2) |
| Platform assurance | **C** | the shipping platform (Windows) is absent from CI (BE-5) |
| UI/UX | **B+** | contrast/hit-targets/geometry/keyboard/reduced-motion all gated; no deep links (UX-1) |

---

## 3. BACKEND — findings, high → low

### 🔴 BE-1 (HIGH) — no `Host` validation: a website can read the writer's screenplay
**Evidence: EXECUTED.**

`webapp_server.py` sets no `app.config["TRUSTED_HOSTS"]` and never inspects `request.host`. Flask accepts any `Host`. Executed against a studio booted exactly as shipped (secure by default, token minted):

```
GET /                                     Host: evil.attacker.com   -> 200
GET /api/projects                         Host: evil.attacker.com   -> 200  (project list, server_url, model_id)
GET /api/projects/The_Late_Hour/script    Host: evil.attacker.com   -> 200  (the screenplay, in full)
GET /api/health                           Host: evil.attacker.com   -> 200
DELETE /api/projects/The_Late_Hour        Host+Origin: evil...      -> 403  (correctly refused)
```

**Why this matters.** The threat model in the code ("the threat model is a foreign *page*, not a local tool") assumes a foreign page is cross-origin and therefore blocked. **DNS rebinding defeats that assumption**: the attacker serves a page from a hostname they control, then re-points that name at `127.0.0.1`. The browser now treats `http://evil.attacker.com:8500` as the attacker's own origin, sends `Host: evil.attacker.com`, and **the read is same-origin — no CORS, no preflight, no `Origin` mismatch**. Because `_reject_cross_origin_writes` returns early for `GET`/`HEAD`/`OPTIONS`, and because the token guard sits *after* that early return, **reads carry no token requirement at all**. Port 8500 is not on Chromium's blocked-port list, so it is reachable from a page.

The product's one promise is that nothing leaves the machine. This is the path by which the writer's unpublished screenplay does.

**Writes are safe and I verified it** — the `Origin` check rejects `http://evil.attacker.com` with 403 even under rebinding, so this is a *read* exposure, not a read-write one. That distinction is load-bearing and I am not overstating it.

**Fix direction (owner's call, not written):** set `app.config["TRUSTED_HOSTS"]` (Flask 3.1.3 is pinned, so the feature is available) to the loopback names/addresses, or reject in `before_request` when `request.host` is not loopback. Either closes rebinding for reads *and* writes in one place.

### 🟠 BE-2 (MEDIUM) — no runtime detection of a degraded (empty) knowledge base
**Evidence: CODE-VERIFIED.**

The repo's own worst failure mode, documented in `rules_context.py:26` — *"ledger with ZERO grounding (no error, just an empty fragment)"* — is guarded only at **build time** (`test_packaging_data_files.py` asserts ≥26 rule files are inside the wheel). There is **no runtime guard and no test**:

- `KnowledgeBase._load()` globs `rules/*.json` and silently yields `{}` if the glob finds nothing — no exception, no warning.
- `pipeline.py` handles `ImportError` (package absent) and appends a visible `result.errors` entry — but **not** "package present, zero rules loaded". That path constructs `RulesContext()` normally and analyses ungrounded.
- Every `KnowledgeBase()` call in the suite uses the default constructor; nothing constructs one with an empty `rules_dir`.

**Impact:** any non-packaging cause of an empty rules directory (a permissions problem, a path refactor, a renamed file) degrades every report — silently dropping each finding's "grounded in rule X" attribution — with nothing in the UI or the logs to say so. MEDIUM because the build-time guard covers the most likely cause.

### 🟠 BE-3 (MEDIUM) — no logging or observability in the shipped product
**Evidence: CODE-VERIFIED.**

A repo-wide search for `logging.basicConfig` / `getLogger` / `RotatingFileHandler` across all four shipped packages returns **exactly one incidental hit** (`screenplay_cowriter/memory.py:661`). There is no log file, no rotation, no level configuration, and no error sink.

**Impact:** a writer whose session fails has no artifact to send and nothing to inspect; the only output is werkzeug's stderr, which is not captured when the app is launched from a desktop shortcut. For a local-first product with no telemetry (correctly), the local log *is* the support channel — and it does not exist. The e2e harness already hit the sharp edge of this: its own comment records that an unread pipe wedges the server mid-suite.

### 🟠 BE-4 (MEDIUM) — the shipping platform is absent from CI
**Evidence: CODE-VERIFIED.**

CI runs `ubuntu-24.04` for all four jobs. The product's platform-specific code is the **Windows** branch:

- `jsonio.py:91-113` — the cross-process lock is `msvcrt.locking` on Windows, `fcntl.flock` elsewhere. **Only the `fcntl` branch ever runs in CI.**
- `test_delete_project.py:97` — `TestDeleteSurvivesAWindowsLock` is `@pytest.mark.skipif(os.name != "nt", ...)`. The reason is legitimate (POSIX unlinks open files, so the race genuinely does not exist there) — but the consequence is that **the one test covering the Windows delete-retry defect is permanently skipped in the only place the suite runs automatically.** That defect (`WinError 32`, `rmtree` deleting as it walks, shelf row surviving a half-deleted project) is real and was measured by a prior pass.

The retry *primitive* is still covered platform-independently by `TestRetryPermissionBudget`, which is why this is MEDIUM and not HIGH. What is unguarded in CI is the Windows-specific mechanism end-to-end.

### 🟢 BE-5 (LOW) — `/api/health` discloses the model server URL on an unauthenticated GET
`GET /api/health` returns `{"status","server_url","demo_model"}` with no token. On its own this is minor; it is listed because it is one of the surfaces BE-1 makes remotely readable, and it is the cheapest of them to close.

### 🟢 BE-6 (LOW) — accepted trade-offs, recorded so they are not re-litigated
- **Werkzeug development server** (`app.run(threaded=True)`) rather than a WSGI server. Correct for a single-user desktop app and consistent with "boring is good". `debug=False` is set.
- **600 s default LLM timeout.** Generous, but a hung model holds a request thread. Bounded, and deliberately so.
- **`MAX_CONTENT_LENGTH` cap + JSON 413 handler** is present, so a huge upload is refused rather than OOMing.

---

## 4. E2E IMPLEMENTATION & ALIGNMENT — the core question

**Verdict: the gate is honest and worth its runtime. Its weakness is coverage of *assurance properties*, not of features.**

### 🔴 E2E-1 (HIGH) — the loopback bind has no guard that can fail
**Evidence: EXECUTED (predicate probe) + CODE-VERIFIED.**

`webapp_server.py:3942` is `app.run(host="127.0.0.1", port=args.port, debug=False, threaded=True)`. This single argument is the whole privacy promise. Nothing observes it:

- `test_webapp_demo_binds_loopback_not_all_interfaces` (`test_production_readiness.py:51`) reads **`webapp_demo.py`**, applies `run\s*\(\s*host\s*=\s*["']0\.0\.0\.0`, and asserts no match. Measured: **`webapp_demo.py` contains zero occurrences of `app.run`** — it now delegates to `webapp_server.main()`. The regex therefore cannot match, and the assertion **passes unconditionally**. The predicate itself is sound (it does fire on a file that really binds `0.0.0.0`); it is simply aimed at a file that no longer contains the construct.
- `test_capability_token.py::_launch` — the only test that calls `main()` — does `monkeypatch.setattr(ws.app, "run", lambda **_kw: None)`, so the `host` argument is **discarded, never asserted**.
- A search of all 106 pytest files for an assertion on the shipped bind host returns **only** the mock server's own `app.run(host="127.0.0.1")` and the two comment lines inside the obsolete test.

**Mutation consequence:** change `host="127.0.0.1"` to `host="0.0.0.0"` and **1684 pytest tests and 1138 browser checks all stay green**, while the app binds every interface — exposing the writer's projects to the LAN and, because the token cookie is handed to *any* client that fetches `/`, exposing writes too. This is precisely the 2026-09-20 B2 defect, whose fix shipped without a durable guard.

This is the one finding I would fix first, because it is the difference between "secure" and "secure until someone edits one line".

### 🟠 E2E-2 (MEDIUM) — the packaging guard asserts membership, never that the install *works*
**Evidence: CODE-VERIFIED.**

`test_packaging_data_files.py` builds a real wheel and a real sdist — genuinely good — but every assertion is a **name-membership check** on the archive (`assert rel in names`, `assert len(rules) == len(on_disk)`, `assert not pngs`). Nothing installs the wheel and serves from it.

The repo's own recorded standard is the opposite: *"Verify by installing the wheel and serving from it, never by reasoning."* Membership is a proxy. It cannot catch a loader that resolves assets relative to the **current working directory** rather than the package (which passes from a source checkout and fails after `pip install`), nor a wheel that carries a file the runtime cannot read.

**Mitigating fact I verified:** the two loaders that matter *are* package-relative — `knowledge_base.py:28` uses `os.path.dirname(os.path.abspath(__file__))`, and `webapp_server.py:41` sets `WEBAPP_DIR` the same way. So there is no bug today. The finding is that the guard would not have caught one, and the fix is cheap: one test that `pip install`s the built wheel into a temp target, boots it, and asserts `GET /` is 200 with a non-empty KB.

### 🟠 E2E-3 (MEDIUM) — 8 tests in the readiness suite assert on source text, not behaviour
**Evidence: EXECUTED (enumerated by reading all 32 test functions).**

The 2026-09-21 audit left this claim explicitly unverified and named it *"the single highest-value thing to check before trusting the readiness suite."* Verified now — the count is **8 test functions across 4 classes**, not "~8 files":

| # | Test | File read |
|---|---|---|
| 1 | `test_webapp_demo_binds_loopback_not_all_interfaces` | `webapp_demo.py` — **vacuous, see E2E-1** |
| 2 | `TestFeedbackLedgerDefaults::test_default_filter_admits_every_severity` | `app.js` |
| 3 | `TestFeedbackLedgerDefaults::test_the_mass_strip_labels_its_scope_when_the_filter_narrows` | `app.js` |
| 4 | `TestFeedbackLedgerDefaults::test_the_fix_queue_reuses_the_one_filter_predicate` | `app.js` |
| 5 | `TestManuscriptMarginContract::test_default_layout_is_in_flow_not_an_overlay` | `style.css` |
| 6 | `TestManuscriptMarginContract::test_the_gutter_column_is_gated_on_real_room` | `style.css` |
| 7 | `TestManuscriptMarginContract::test_margin_pins_are_read_only_pointers` | `app.js` |
| 8 | `TestPremiseStoreIntegrity::test_premise_writers_are_atomic` | `ideas.py`, `webapp_server.py` |

**Severity, honestly calibrated: MEDIUM overall, HIGH for #1.** A regex on `app.js` proves a *string exists* — it can be satisfied by a comment, and it survives a rename that keeps the old name in a docstring. The remaining seven are, however, **backed by real browser checks**: `e2e_browser_phase13_legacy_cleanup.py` walks the margin's geometry and asserts *"no margin pin covers a line of script"* and that a pin carries no judgment controls, so #5–#7 are belt-and-braces rather than the only guarantee. #2–#4 have only partial behavioural backing (the readiness gate asserts severity chips render and the mass strip prints). #1 has none at all.

The rest of `test_production_readiness.py` is genuinely behavioural and good — the store-integrity, whisper-guard, retry-budget, demo-honesty, gate-retry and route-coverage tests all drive real code. The suite is **not** hollow; it has eight soft spots and one dead one.

### 🟠 E2E-4 (MEDIUM) — the browser gate only ever exercises the demo model
**Evidence: CODE-VERIFIED.**

`e2e_browser_common.start_studio()` forces `SCREENPLAY_STUDIO_DEMO_MODEL=1` and passes `--demo-model`, and the gate runs with no `E2E_BASE`. The single suite that needs a real model — `gun_pen_audit` — is the one suite skipped.

So **the browser journey is never exercised against a real (or mock) `llama-server` in CI.** pytest covers the pipeline against `tests/mock_unified_server.py`, which is genuinely valuable, but it is a different transport and a different code path from the SPA's fetch → SSE → render loop. A regression in the *browser's* handling of a real model's streaming, error or timeout responses would not be seen.

**Mitigating fact:** the demo model is deliberately shaped as a llama-server look-alike and the pipeline is shared, so this is a narrowing, not a hole. It is still the largest single coverage asymmetry in the gate.

### 🟢 E2E-5 (LOW) — no coverage measurement, and the gate is 12 minutes
`pytest-cov` is declared in the `ci` extra and installed, but no job runs with `--cov` and there is no coverage floor. The browser gate is 46 sequential suites at ~12 min — well inside the 45-minute job budget, but it means a full-fidelity local gate is a coffee break, which is how manual-only habits start. Neither is a defect; both are the obvious next levers.

### ✅ What I verified is *solid* in the e2e implementation (do not unship)

- **Zero vacuous checks.** The AST sweep for the `always-True` shape returns nothing across 47 files. The prior passes' work held.
- **Failure-shaped preconditions are handled as facts, not crashes.** `seen_visible` / `clicked` / `filled` / `send_chat` are bounded and never raise, so one broken precondition cannot abort a run and mask every later check. This is a genuinely good harness design and it is why the gate reports 1138 named results instead of dying at suite three.
- **Skipped suites are never silent.** `run_browser_suites.py` prints every exclusion with its reason, and `KNOWN_BROKEN` is empty with a written instruction to keep it that way.
- **The gate refuses to boot with the token switched off** — a source-text check that a suite cannot go green against a non-shipped configuration. That is the right shape for a rule that cannot be expressed behaviourally.
- **`finding_id_parity` compares live JS to live Python** and drives a real `/fixqueue` round trip, rather than asking either side to agree with itself.
- **`readiness_gate` measures computed contrast and real hit areas in both themes**, with a properly-implemented oklab/oklch conversion and an alpha-composite walk. This is far beyond typical e2e visual testing.
- **Traversal is genuinely closed** — 9 payloads, all 400/404.

---

## 5. UI/UX — findings, high → low

### 🟠 UX-1 (MEDIUM) — no URL or history routing
**Evidence: CODE-VERIFIED.**

`app.js` contains **no** `location.hash`, `hashchange`, `pushState` or `popstate` anywhere. Consequences:

- A writer cannot bookmark or share a link to a scene or a finding.
- **Browser Back exits the application** rather than stepping back a view — from inside a review pass, one Back press leaves the whole session.

**Honest downgrade of a prior finding:** the 2026-09-21 audit rated this MEDIUM and I initially expected to raise it, because a lost place on refresh would be severe for a long working session. **That is not the behaviour.** `restoreSession()` (app.js:1912) persists project, view, idea-room id *and the scroll-anchored scene number*, and `app.js:9003` re-opens the project on load; `dock_sections`, `phase14` and `ideas_v3` all exercise `page.reload()`. So refresh is genuinely handled. What remains is deep-linking and Back — real, but MEDIUM is the correct grade, not HIGH.

### 🟢 UX-2 (LOW) — WCAG 1.4.4 (Resize text) and device-pixel-ratio are untested
No suite sets `deviceScaleFactor` or drives a 200% text zoom. Every viewport sweep runs at DPR 1 (1440/1280/1024/1000/480/390 px). The app uses `rem`-ish tokens and container queries, so this is unlikely to be broken — but "unlikely" is the standard this repo does not accept elsewhere. One added viewport assertion would close it.

### 🟢 UX-3 (LOW) — four abandoned design labs still ship in the served tree
`preview-design/`, `preview-next/`, `preview-r4/`, `preview-redesigns/` — **26 HTML files** — are still served by the `/<path:filename>` route. They are correctly excluded from the CSP (they carry their own inline scripts), and `test_preview_lab.py` plus two browser suites keep them working, so this is deliberate rather than rot. It is still 26 documents of non-product surface reachable on the same origin as the writer's data, and it enlarges the BE-1 read surface.

### ✅ What I checked and found genuinely good in UI/UX (recorded so it is not re-litigated)

- **`prefers-reduced-motion` is properly honoured** — 18 guard blocks in `style.css` plus two in `tungsten.css`, including `animation: none` on the severity blip and the palette modal. I initially suspected a gap here and **withdrew it after checking**; the earlier grep had scoped the wrong files.
- **Keyboard paths are real and gated** — `e2e_browser_keyboard_edit.py` (14 checks) and the new `modal_guards` (22 checks) cover focus trapping, Escape cascade depth and the dialog owning the keyboard.
- **Severity is never colour-alone** (jagged rim + mass + label), and the readiness gate now measures contrast on the **rendered pixel** in both themes.
- **Hit targets** are measured on the real hit area (transparent `::before` pads included), not on markup.

---

## 6. Process & release risk

### 🟠 P-1 (MEDIUM) — the in-flight work is green locally and invisible to CI
**Evidence: EXECUTED.**

The working tree carries an uncommitted re-audit: 6 modified product files (`app.js` +308 lines, `revision.py`, `webapp_server.py`, `beatboard.py`, `index.html`, `style.css`) and **5 untracked test files** — three new browser suites and two new pytest files.

**The good news, measured:** those new suites **ran in my gate and all passed** — `beatboard_drag` 12, `modal_guards` 22, `race_guards` 11 — and the new pytest files were collected in the 1684. So the work is verified *here*.

**The risk:** none of it is committed, so CI has never seen it, and untracked files are one `git clean` away from being lost. Three of the new suites carry `re-audit 2026-09-24` findings (H3–H5, M1–M7, L7–L9) that would silently reopen if the tests do not land with the fixes. **Commit the fixes and their tests together.**

### 🟢 P-2 (LOW) — 44 evidence PNGs remain tracked at the repo root
`_browser_*.png`, `_ui_cap.txt`, `_t6_*.txt`, `_p6_out*.txt` and similar scratch files sit untracked-or-tracked at the root. The wheel correctly excludes PNGs; this is repository hygiene only.

---

## 7. Self-critique of this audit

Stated plainly, because the failure mode I am trying to avoid is relaying a claim I have not checked.

1. **I withdrew a finding after verifying it.** I initially flagged "the SPA does not honour `prefers-reduced-motion`" from a grep that had scoped `tests/` and two lab files rather than the shipped stylesheet. Re-checking `style.css`/`tungsten.css` found 20 guard blocks. **Withdrawn.** It is recorded here rather than deleted so the correction is visible.
2. **I downgraded a finding against my own prior.** I expected the missing hash router to be HIGH (losing your place on refresh is severe). Reading `restoreSession()` showed project, view, idea and scene *are* restored, and three suites already exercise `page.reload()`. **UX-1 is MEDIUM, not HIGH** — the residue is deep-linking and Back, not data loss.
3. **BE-1 is read-only and I say so.** I proved writes are refused (403) under rebinding. A less careful write-up would have claimed full compromise. It is a read exposure, which is still enough to break the product's central promise.
4. **E2E-1 is proven by inspection plus a predicate probe, not by mutation.** I did not modify `webapp_server.py` (the user forbade code changes), so I did not literally flip the bind and watch the suite stay green. What I proved is that the guard's predicate cannot match its target file (executed), and that no test anywhere observes the bind host (exhaustive search). The mutation consequence follows, but it is an inference from those two facts, not an execution.
5. **E2E-3's severity is deliberately split.** Seven of the eight source-text tests are backed by real browser checks, so calling the suite "hollow" would be wrong. Only #1 is genuinely dead. The prior audit's "~8 files" was really 8 tests in 4 classes.
6. **What I did not do:** I did not run the gate with `E2E_BASE` against a live `llama-server`, so `gun_pen_audit` remains unexercised here exactly as in CI. I did not measure coverage. I did not test on Linux or on a second Windows machine, so the `fcntl` branch and cross-machine reproducibility are unverified by me.
7. **One number moved from a prior report and I am recording it:** tracked PNGs are **44**, not the 69 that appears in earlier notes.

---

## 8. Recommended sequence — owner decides; nothing here is written

| # | Action | Why in this position |
|---|---|---|
| 1 | **Close E2E-1** — assert the shipped bind host, or better, make `_launch` capture `app.run`'s kwargs and assert `host == "127.0.0.1"`. Replace the obsolete `webapp_demo` regex with a behavioural check. | One line of test code protects the product's entire privacy promise. Highest value per unit of effort in this report. |
| 2 | **Close BE-1** — set `TRUSTED_HOSTS` (or a `before_request` Host check) to the loopback set. | Closes remote read of the writer's material *and* hardens the write path in the same change. |
| 3 | **Commit the in-flight re-audit with its tests** (§6). | Verified green here, invisible to CI, and three suites encode findings that would silently reopen. |
| 4 | **Add the install-and-serve packaging test** (E2E-2). | Cheap; converts a proxy guard into a real one. |
| 5 | **Add a runtime guard for an empty KB** (BE-2) — one assertion at startup, surfaced in `result.errors`. | Turns the repo's own documented worst case from silent to loud. |
| 6 | **Add a Windows CI job** for the lock and delete-retry paths (BE-4). | The shipping platform is currently unassured. |
| 7 | **Introduce logging** (BE-3) — one `basicConfig` to a rotating file in the project root. | The support channel for a no-telemetry product. |
| 8 | *Optional:* coverage floor (E2E-5), a resize-text check (UX-2), deep links (UX-1). | Quality levers, not blockers. |

---

## 9. Bottom line

The engineering here is unusually disciplined: cross-process locks, content-derived asset versions, a cross-language id contract, a real contrast gate, and a suite that refuses to go green against a non-shipped configuration. **The e2e implementation is real evidence — 1684 + 1138 checks, zero vacuous assertions, zero failures on this machine.**

The gaps that remain are not sloppiness; they are the places where the suite is *confidently looking at the wrong thing*. The loopback bind is guarded by a test pointed at a file that no longer binds. The wheel is checked for contents but never installed. The `Host` header is trusted. Each is small to fix and each is load-bearing for a product whose single promise is that the writer's script stays on their machine.
