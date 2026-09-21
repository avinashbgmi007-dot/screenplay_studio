# Fix Tracker — production-readiness pass

**Live document.** Updated as each item lands, so the state of play is readable
without re-deriving it from `git log`. Source audit:
`docs/audit/production_readiness_2026-09-21.md`.

**Last updated:** 2026-09-21 (pass 2 — BE-M1/BE-M2/R7 closed, BE-M3 proven)
**HEAD:** `a5742d5` (pushed; `git ls-remote origin main` agrees)
**Previous baseline:** `efb3dd5`

---

## Gate status

| Gate | Command | Result at this pass |
|---|---|---|
| Unit + integration | `python -m pytest tests/` | **1521 passed, 3 skipped, 0 failed** |
| Lint | `ruff check .` | **clean** |
| JS unit | `node --test tests/js/*.test.js` | **16 / 16** |
| Browser E2E | `python tests/run_browser_suites.py` | 32 suites: 28 pass, 0 fail, 2 skip, 2 known-broken |

> Re-run all four after any code change. A row above is only true for the
> commit named in "Last updated".
>
> ⚠️ `node --test tests/js/` (a bare directory) fails with `MODULE_NOT_FOUND`
> on Node 22 — it must be the file glob `tests/js/*.test.js`. That is an
> invocation trap, not a failing test.

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

---

## Closed in this pass (2026-09-21, pass 2)

| ID | Item | Proof | Mutation |
|---|---|---|---|
| **BE-M1** | `revision._load_json_list` swallowed a corrupt `edits.redo.json` into `[]` — the writer was told **400 "Nothing to redo."** about a stack on disk, and `undo_last_edit` then overwrote the only recoverable copy | `TestDamagedHistoryStores` (6) + `TestDamagedHistoryAPI` (1) + `redo stack` StoreCase flipped `silent`→`guarded` | ✅ lenient reader restored → **10 red** |
| **BE-M2** | `revision.edits_log` read raw → bare `JSONDecodeError` (a `ValueError`) → **400 "bad request"** for a damaged disk | `test_damaged_edit_log_is_reported_not_read_as_empty` + the 503 API assertion | ✅ raw read restored → **2 red** |
| **BE-M1b** | Undo/redo mutated the working copy *before* discovering the other store was damaged, leaving a half-applied reversal | `test_damaged_redo_stack_refuses_before_consuming_the_undo`, `test_damaged_edit_log_refuses_before_consuming_the_redo` | ✅ pre-flight moved back → **1 red** each (M3, M4) |
| **R7** | CI ran `pip install ruff` unpinned — a floating linter can fail a green build, or disagree with the local `ruff check .` | `test_ci_pins_its_linter_to_the_version_the_repo_uses` (asserts ci.yml + both extras agree) | ✅ both directions → red |

**All of the above landed in `a5742d5`** (pushed). 6 mutations, 6 caught.

---

## Proven, deliberately NOT fixed

| ID | Item | Evidence | Why deferred |
|---|---|---|---|
| **BE-M3** | `undo_last_edit` / `redo_last_edit` read-modify-write `edits.json` + `edits.redo.json` **without holding `lock_for` across the cycle** (each read and each write is locked; the gap between them is not) | 3 real children behind a file barrier: **two read `len=7`, both wrote `len=6`** — the log loses an entry relative to the reversals the working copy actually got. Instrumented script: `.workbuddy-ai/scratch/be_m3_instrument.py` | The fix needs either **two store locks held at once** (forbidden by `jsonio.lock_for`'s one-lock-at-a-time invariant, which exists to prevent deadlock) or a **CAS retry loop**. Both are design decisions. Harm is narrow (two *simultaneous* undos of one project) and non-destructive: the working copy is correct, only the history bookkeeping drifts. |

---

## Open (not started)

| ID | Item | Class | Owner |
|---|---|---|---|
| R7b | No lockfile (deps use `>=` floors) | supply chain | **owner decision** — changes the dependency workflow |
| R6 | No LICENSE / CHANGELOG | release | **owner decision** |
| R9 | 45-min CI budget vs a 125-min worst case | CI | open |
| R10 | Root scratch files tracked in git | hygiene | open |
| R11–R14 | 69 PNGs in `docs/audit/`; `.git` 78 MB from 22 cline checkpoint refs | hygiene | open |
| T1 | 4 vacuous browser checks inflate the check count (476 → honest 472) | test integrity | open |
| T2 | `tests/test_production_readiness.py` asserts on **source text** in places; the audit calls it the highest-value thing to verify before trusting the readiness suite | test integrity | open |

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
