# Screenplay Studio — E2E Production-Readiness Audit

**Date:** 2026-09-20  ·  **Commit reviewed:** `4484844` (main)  ·  **Local state:** 5 unpushed commits + 1 uncommitted feature layer (P2.8 `craft_history`)  ·  **Mode:** read/audit only — **no file was modified.**

> Confidence tags: `✅ executed` (ran it), `✅ code-verified` (traced in source), `✅ expert-report` (teammate, not re-executed), `❓ UNVERIFIED`. Claims not matched by my own evidence are flagged — see self-critique.

---

## 0. Executive verdict (per deployment model)

| If you ship this to… | Verdict | Why |
|---|---|---|
| **One writer, local only** (the stated model) | ⚠️ Close, not first-run-ready | Runs offline via the demo model ✅, but that model ships canned placeholder findings (`"Sample dialogue finding."`) instead of analysis 🛑 |
| **Hosted / LAN-shared instance** | 🛑 Do not expose | `screenplay_studio/webapp_demo.py` binds `0.0.0.0` with no capability token |
| **A shipped / distributable release** | 🛑 Not shippable | CI red on `main`; 5 unpushed commits + uncommitted layer; no LICENSE; not `pip install .`-able |

The pipeline, the 1323-test suite, and the local first-run story are mature enough that the core is within sight of v1. Three independently-verified gates block the last mile: a dishonest offline fallback, a silent data-loss chain on the writer's own edits, and a CI/release gate that is red as you read this.

---

## 1. What was executed (not inferred)

### 1.1 Test suite — fresh run, cache disabled
```
python -m pytest tests/ -q -p no:cacheprovider
=> 1323 passed, 3 warnings in 49.65s   (CPython 3.14.3 on this machine; CI pins 3.12)
```
Warnings: `screenplay_analyzer/rules_context.py:182` KB fragment 65,226 chars > 40k ceiling; `screenplay_cowriter/context.py:596` prompt budget 8,513 chars unreachable (model would truncate silently). On a **clean virtualenv with only `requirements.txt`**: five production packages import cleanly (`IMPORTS OK`). `node --test tests/js/*.test.js` → 7/7 pass.

### 1.2 Full user journey, live, NO `llama-server` present
Demo-mode launch on an isolated temp `PROJECTS_DIR`, port 8599 (killed + temp removed post-run; repo untouched):
```
POST /api/sample                                 -> 200  parse=complete
POST /api/projects/The_Late_Hour/analyze         -> 200  analyze=complete, model_id="demo-craft-model"
GET  /api/projects/.../report                    -> 200  findings=6, evidence_depth{full_text:1, overview:2, overview+checkpoints:3, total:6, unknown:0}
GET  /api/projects/.../fixqueue                  -> 200  (acts split, queue items present)
POST /.../chat/sessions/<sid>/messages           -> 200  demo Sameer reply (reads scene map, cites finding count)
GET  /api/projects/.../export                    -> 200  1137-byte Fountain ("Title: The Late Hour")
```
No hop hard-crashes without a live LLM. The offline path runs; its defect is output **quality** (§3.4).

---

## 2. Measurement table (git-tracked files)

| Metric | Value | How |
|---|---|---|
| Production Python (excl. demos/previews) | 16,250 LOC | `Get-ChildItem` |
| Test Python | 20,653 LOC → **test:prod = 1.27 : 1** | `tests/` |
| SPA (`app.js`+`style.css`+`index.html`, shipped) | 15,695 LOC — `app.js` alone = 8,393 | — |
| Flask routes (`webapp_server.py`) | 88 | grep `@app.route` |
| Collected pytest tests | 1323 (100% pass locally) | `--collect-only` |
| `tests/e2e_browser_*.py` suites | 30 — **not collected by pytest; never run in CI** | naming |
| Tracked files / tracked PNGs | 470 / 69 | `git ls-files` |
| Repo object DB `.git` size | 75 MB | — |
| `ruff check .` on main | **15 errors** | executed |
| `check_safe_id` enforcement | on `name`+`idea_id`; **`sid` unvalidated × 14 routes** | grep |
| Raw `open("w")` writers | **18** (vs 17 `atomic_write_json`) | grep |
| Local commits ahead of `origin/main` | **5 unpushed** | `git log origin/main..main` |

---

## 3. Headline findings

### 🔴 A. Data safety — "no writer loses data" is NOT satisfied
Verified by code path (`revision.py`) + expert report, plus the non-atomicity census.

**A1 — Corrupt `edits.json` silently reverts all the writer's edits, no error.** ✅ code-verified path
1. Kill mid-apply truncates `edits.json` (raw non-atomic write `revision.py:335-336`, `:370-372`; loaded `revision.py:457-461`).
2. `has_edits()` (`revision.py:341-350`) swallows `JSONDecodeError`/`OSError` → returns `False`.
3. Any later re-parse/analysis/new-draft rewrites `parsed.json` (`orchestrator.py:41` → `models.py:123-125`), mtime newer.
4. Next `load_working` (`revision.py:324-325`) → `ensure_working` (`revision.py:312-318`): `not has_edits(m)` and `parsed` newer ⇒ **overwrites `working.json` from `parsed.json`**.

`working.json` is the **only copy** of applied edits (`source.<ext>` is pre-edit; `drafts/` holds source/parse/report only — `diff.py:63-70`). Zero recovery, zero warning. Reached from `GET /script (:1001)`, `/export (:1238)`, `/fixqueue (:1384)`, `/report (:1556)`, `reparse (:826-828)`, `chat (:2105)`. Cheapest fix: `has_edits()` returns `True`/raises on decode error; route `edits.json`/`edits.redo.json` through `atomic_write_json`.

> ⚠️ Self-critique: I did **not** fault-inject a corrupt `edits.json` live (requires crashing a writer mid-edit). Verified by code reading + expert report; should be reproduced under forced truncation before release.

**A2 — The write itself is non-atomic; atomicity discipline is applied selectively.**
| Store | Writer | Atomic? |
|---|---|---|
| `report.md` / `report.findings.json` | `report.py:25` (tmp + `os.replace`) | ✅ |
| `findings_status`, `dismissed_findings`, `marks`, `last_pass`, `metrics`, `progress`, `beatboard` | `jsonio.atomic_write_json` | ✅ |
| **`working.json`**, **`parsed.json`**, `parsed.kg.json` | `models.py:123-125 ScriptDocument.save` (raw `open("w")`) | ❌ |
| **`edits.json`**, `edits.redo.json` | `revision.py:335-336`, `:370-372` (raw) | ❌ |
| **`writer_profile.json`** | `memory.py:590,600` (raw) | ❌ |
| `notes.json` | `notes.py:73` (`_save`) | ✅ |
| `stash.json` | `stash_store.py` (`_save` → `atomic_write_json`) | ✅ |

`docs/STATE_STORES.md:5-7` asserts *"every persistent slice is … written atomically via `jsonio.atomic_write_json`"* — **false**: 9 of its own 16 rows bypass it, including the three highest-value stores. **No `fsync`** anywhere (`grep fsync|FlushFileBuffers` → 0). **No cross-process lock primitive** (`grep fcntl|flock|msvcrt|filelock|portalocker` → 0) while `AGENTS.md` documents the CLI and webapp writing the same project dir.

### 🟠 B. Security — the offline/no-cloud promise is a default, not an invariant
Verified by execution where possible; the one expert filing error is corrected below.

**B1 — `sid` path traversal (verified by execution).** ✅ executed
`screenplay_cowriter/store.py:43` `SessionStore._path` = `os.path.join(sessions_dir, f"{session_id}.json")`, and `sid` is **never** passed through `check_safe_id`. Proven:
```
SessionStore._path("..\\..\\evil") -> C:\Users\...\Temp\evil.json   (escapes: True)
Flask <sid> converter: GET /s/..%5C..%5Cx  -> sid = "..\\..\\x"   (backslash accepted)
```
14 routes take `<sid>` (session load/send/fork/switch/delete/messages/translate). Composition ⇒ a writer with a second project can read and delete another project's session JSON by relative traversal. `entry_id`/`note_id`/`obs_id` are *safe* (list-membership match: `stash_store.py:70`, `notes.py:91`, `memory.py:624`). Cheapest fix: validate `sid` at the store; regression test that `..%5C..` → 400.

> ⚠️ Self-critique: the security-expert teammate initially filed this against `webapp_server.py`; I did **not** accept it. Grepping every `app.run` found the real offenders separately (B2). This is the class of claim I refused to pass through unchanged.

**B2 — the documented demo launcher exposes the entire LAN with no auth.** ✅ executed (grep + code)
`screenplay_studio/webapp_demo.py:24`:
```python
app.run(host="0.0.0.0", port=port, debug=False)
```
It imports `app` and runs it directly, **bypassing `main()`**, so the capability token is **never minted** (`_API_TOKEN` stays `None` at `webapp_server.py:65`; the `if _API_TOKEN:` guard at `:78/172` is skipped). `CLI_REFERENCE.md:38` documents `python -m screenplay_studio.webapp_demo` as a supported command. Docstring: *"Freebuff-style hosting."* Impact: analysis of the writer's full script, findings, sessions, and all `DELETE`s — reachable from the LAN with zero auth. The canonical `webapp_server.py:3236` is hardened (`127.0.0.1`, token-by-default, `SameSite=Strict`, `hmac.compare_digest`, 413 cap). The crack is the *demo* launcher, and it is documented.

**B3 — "no cloud / nothing leaves the machine" is a default, not an invariant.** ✅ code-verified
- `grep 'https?://'` across all packages + SPA (excl. `localhost|127.0.0.1|w3.org`) → **no hardcoded external hosts** ✅.
- No telemetry/analytics wiring ✅. Fonts self-hosted (`style.css:2`) ✅.
- **BUT** `POST /api/config` accepts any `server_url` (`webapp_server.py:446-447`, propagated via `_sync_server_url_to_projects` `:281-282`) — after that, the writer's full screenplay is POSTed to that URL.
- Two first-use outbound requests: `stt.py:51` (no `local_files_only`/`HF_HUB_OFFLINE` → HF hub download); `pdf_parser.py:152` (`easyocr` downloads TE/HI models, per comment `:131`).
- STT localhost guard bypassable: `stt.py:97` `url.startswith(("http://localhost","http://127.0.0.1"))` defeated by `http://127.0.0.1@evil.com`. Operator env var → low exploitability; the only enforcement of the STT promise, and it does not hold.
- H7 (two-`system`-message → HTTP 500 chat crash) is fixed (`engine.py:258-266`); `test_capability_token.py:85-114` covers the token.

### 🟡 C. Release engineering / CI — red on `main`
Verified: `ruff check .` → 15 errors; clean-venv repro of the test-dep failure.

**C1 (lint job, red — deterministic).** `ruff check .` → **15 errors**: 4 in shipped Python (`screenplay_analyzer/llm_client.py:15,17` unused `requests`/`ModelNotFoundError`; `pipeline.py:22` unused `collections`; `cowriter/llm_client.py:11` unused `re`; `demo_model.py:589` E731), 2 from root scratch `.py` that are **tracked** (`_gen_wf.py`, `_r3_palette_probe.py` — `git ls-files`), 9 in tests. `ci.yml:15-18` runs `ruff check .` → fails for everyone.

**C2 (test job, red from the documented setup).** `tests/test_pdf_ocr.py` (`pdf_parser.py:77`) does a bare `import pypdfium2` with **no `importorskip` guard**; 2 siblings the same. `pypdfium2` is **not in `requirements.txt`** (only `requests, flask, pdfplumber`) nor in the `dev` extra CI never installs. Reproduced: a shadowing `pypdfium2` that raises → **3 failed, 1 passed**. So `pip install -r requirements.txt && pytest -q` → red. `pytest` itself is declared only under `[project.optional-dependencies] dev` (`pyproject.toml:13`), which CI never installs.
- ❓ UNVERIFIED: whether the GitHub runner image preinstalls `pytest` (the Ubuntu2604 pip list truncated when fetched). Does not change the verdict: absent → red; present → red on `pypdfium2`.

**C3 (not shippable as a package).** No `LICENSE`, no `CHANGELOG`; version `0.1.0` only in `pyproject.toml`; **no `[build-system]` and no `setup.py`** → `pip install .` expected to fail; the product runs only in-place via `python -m`.

**C4 (nothing is pushed).** `main` is **5 commits ahead of `origin/main`** (S5.2/P2.11/P1.7/P2.9/P2.13 passes, green) plus **one uncommitted layer** in the working tree: P2.8 `craft_history` (`screenplay_cowriter/craft_history.py` + `tests/test_craft_history.py` + wiring `webapp_server.py:2135,2762`) — green but uncommitted/unpushed. `git status`: `M cli.py/context.py/engine.py/webapp_server.py`, `?? craft_history.py/test_craft_history.py`.

**C5 (dated infra-drift risk).** `ci.yml` pins neither a runner (`ubuntu-latest`) nor a timeout. `ubuntu-latest` migrates `24.04 → 26.04` **between 2026-10-19 and 2026-11-19** (GitHub changelog), and `test-python` `apt-get install`s `tesseract-ocr-{eng,hin,tam,tel}` whose names may change. Unpinned → unattended breakage.

### 🟡 D. Offline quality — the demo craft model is a fixture, not an analyst
The 6 findings from the live report (`report.findings.json`):
| category | severity | issue | evidence |
|---|---|---|---|
| dialogue | low | "Sample dialogue finding." | `no_quote` |
| theme | low | "Sample theme finding." | `no_quote` |
| character | low | "Sample character finding." | `no_quote` |
| character | low | "Sample character finding." *(duplicate, un-merged)* | `no_quote` |
| plot_thread | medium | Setup left dangling: "The revolver" (real, derived) | — |
| genre | low | "Sample genre finding." | `no_quote` |
`demo_model.py:605-634` returns the `"Sample X finding."` literals. The amber "demo" banner (`test_demo_banner.py:16`) is honest *about the model*, but the findings render as real notes in the fix queue with severity + act placement — a first-run writer with no LLM sees four fabricated notes. Cheapest fix: drop the canned stubs or suppress findings/fix-queue in demo mode behind a clear "filler — run a real model" banner.

### 🟡 E. Documentation drift (safety-critical)
`docs/STATE_STORES.md:5-7` "every persistent slice … atomically via `jsonio.atomic_write_json`" — **refuted by A2**. Status board cites 1090/1273 historically; live tree is **1323**. `ARCHITECTURE.md` says "no threading" but `webapp_server.py:3236` is `app.run(threaded=True)`. `app.js` is **8,393 lines** single-file vanilla JS (docs round it 6.9–8.7k). **Good** duplication: `compute_finding_id` (`revision.py:65`) and `computeFindingId` (`app.js`) are algorithm-identical and test-pinned; single `jumpToScene` (`app.js:2816`) — duplicate removed per `c76cbe5` + `test_app_symbol_integrity.py`.

---

## 4. What's genuinely solid (do not unship)

- Manifest-driven resume (`pending/complete/failed`); partial-category retry (`--retry-failed`) preserving the prior partial record.
- Flag-don't-drop verification (0.72 threshold; GAP-6 closed, measured `contradictions 6→0`).
- Setup/payoff ledger; cross-rule dedup (`dedupe.py`, 31 tests).
- Secure canonical launch: loopback bind, token-by-default, `SameSite=Strict`, `hmac.compare_digest`, 413 cap, strict `check_safe_id` on names, no RCE primitives.
- `jsonio.atomic_write_json` + per-path `RLock` + `retry_permission` (WinError 32) where applied; `_NullRulesContext`; zero-arg deferred providers (P2.8 reused the shelf-provider pattern).
- The gun_pen audit retired its last filed gap (`18/0` matrix, `9/0` pass2).

## 5. Blind spots (self-critique)

| Unverified | Impact |
|---|---|
| The 30 Playwright browser suites (`tests/e2e_browser_*.py`) — never executed (need `playwright install chromium`, a state change refused in audit mode) | The SPA (`app.js`, 8,393 LOC) is effectively untested outside 7 `core.js` tests + API tests |
| Real-model analysis quality | No live `llama-server` here; no eval harness. Demo placeholders are the one *demonstrable* quality defect |
| Fault-injected corruption (A1/A2) and NTFS power-loss atomicity | Asserted structurally (no `fsync`, no cross-process lock), not reproduced |
| Whether GitHub runners preinstall `pytest` | C4 — does not change the red verdict |
| Full product-UX & architecture expert reports | **product-expert** & **architecture-expert** sub-agents were killed by a daily model-quota 429 and returned nothing; their domains were covered from my own code evidence + the status board, which is why those sections carry fewer execution ticks than §3 A/B/C |

## 6. Ordered backlog (no code written yet — awaiting approval)

1. **Unblock CI** (gate 0): clean lint (drop unused imports incl. root scratch files, or untrack them; fix `demo_model.py:589`); add `pyproject.toml` `[project.optional-dependencies] ci = ["pytest>=8.0","pytest-asyncio","playwright","pypdfium2>=…"]` and install it in `ci.yml`; prove lint+tests green on `main`.
2. **Harden/remove the demo launcher** (B2 — the actual exploitable surface): route `python -m screenplay_studio.webapp_demo` through `main()` (token + `127.0.0.1`), or delete the module and its `CLI_REFERENCE.md` line. Ships harm if anyone follows the documented command on a shared network.
3. **Close `sid` traversal** (B1): validate `sid` at `SessionStore`/`_load_session_and_engine`; regression test that `..%5C..` → 400.
4. **Crash-safe the writer's working copy** (A1/A2 — highest-stakes for the product promise): atomic writes on `edits.json`/`edits.redo.json`/`working.json`/`parsed.json`/`writer_profile.json`; `has_edits()` distinguishes missing from unreadable; `.bak` snapshot per edit-apply.
5. **Honest offline content** (D): drop the canned `"Sample X finding."` stubs or suppress findings/fix-queue in demo mode behind a clear "filler — run a real model" banner.

---

**Bottom line:** audited, locally green, and structurally coherent — but **not shippable as-is**. Fix #1 (CI) first so the green suite is real again; then resolve #2/#3 (security, do-not-ship) and #4 (data safety) before any release.
*Report authored 2026-09-20 from a read-only audit; repo state unchanged from audit start.*
---

## 7. Implementation tracker (2026-09-20, post-audit)

Greenlit after the audit. Implemented with TDD (failing regression tests in `tests/test_production_readiness.py` before any fix; watched 5/5 fail RED against unpatched code, then pass GREEN after).

| # | Item | Status | Evidence |
|---|---|---|---|
| C1 | Lint green | ✅ DONE | `ruff check .` → **All checks passed!** (was 15). Fixes: removed truly-unused `import collections` (pipeline), `import re` (cowriter/llm_client); `demo_model.py` lambda→def; 2 root scratch + tests auto-fixed/manual (E401/E701/E731). **Self-critique caught:** the audit's "`ModelNotFoundError` unused" was WRONG — it's re-exported via `screenplay_analyzer/__init__`; removed it → ImportError on import. Restored with `# noqa: F401` (re-export contract documented). |
| C2 | Test job deps | ✅ DONE | `pyproject.toml` gained `ci` extra (`pytest, pytest-asyncio, pytest-cov, playwright, pypdfium2, ruff`); `ci.yml` now installs `pytest pytest-asyncio playwright pypdfium2` (was only `requirements.txt` → `pypdfium2` collection error). |
| C5 | Runner pinning | ✅ DONE | `ci.yml` `ubuntu-latest` → `ubuntu-24.04` (both jobs); avoids the 2026-10/11 `26.04` migration + tesseract package-name drift. |
| C3 | `pip install .` works | ✅ DONE | `[build-system]` (setuptools>=68) + `[tool.setuptools] packages = […5 real packages…]`. Root cause: flat-layout auto-discovery failed on ~40 junk root dirs (`tmp*/`, `preview_shots/`). Verified: `pip install .` exit 0 in a clean venv; all 5 packages import from the installed dist. **Not done:** no LICENSE/CHANGELOG (a product/legal decision, not engineering). |
| B1 | `sid` traversal | ✅ DONE | `SessionStore._path` now validates `check_safe_id(session_id, "session id")` (lazy import keeps cowriter↔studio lazy-import contract). `..\..\evil` now raises; delete of a traversal id can't reach outside. |
| B2 | demo launcher bind | ✅ DONE | `webapp_demo.main` now delegates to `webapp_server.main` (`--demo-model` forced, `PORT`→`--port`) → token minted by default, loopback bind, arg parity. Old direct `app.run(host="0.0.0.0")` gone. Regression test asserts no live `run(host="0.0.0.0")` bind remains. |
| A1 | `has_edits` corrupt-log | ✅ DONE | `has_edits()` now returns `True` on `JSONDecodeError`/`OSError` (corrupt/transient ≠ empty), so a bad `edits.json` can no longer make `ensure_working()` overwrite the writer's only edited copy. |
| A2 | non-atomic writers | ⏳ PARTIAL | The *trigger* (A1) is closed; the raw `open("w")` writers that produce a corrupt `edits.json` are still non-atomic (`models.py`, `revision.py`, `memory.py`). Not routed to `atomic_write_json` yet — needs the recovery-semantics decision flagged below. |
| D  | demo placeholder findings | ⏳ NOT DONE | `"Sample X finding."` stubs still ship; requires a product call (drop vs. banner). Deferred to the user. |

**Regression evidence:** `tests/test_production_readiness.py` — 6 tests, watched all 5 behavior tests fail RED, pass GREEN. Full suite after: **1329 collected** (1323 prior + 6 new). See §8 for the final number.

**Deliberately NOT changed (out of scope of the greenlight):** the stale path `E:\AI_workspace\screenplay-studio_1` appears in the *source comments* of `tests/test_audit_hardening.py` — cosmetic, points at a sibling clone, does not affect the running test (module resolves from the real cwd). Left alone.

**Self-critique during impl:**
- The audit's "unused import" claim (`ModelNotFoundError`) was a false positive — removing it broke the package's public `__init__` re-export. Restored with a `# noqa: F401` so CI stays green AND the contract is documented. The audit file overstated "4 unused in production"; the true count was 3.
- The `test_webapp_demo` failure in the first full run was **my own race**: the full suite launched before my docstring edit landed, so it read a half-updated `webapp_demo.py`. Isolated re-run passes; the regex test is correct.
- `test_save_rename_race_never_tears_json` failing in the full run = the repo's **documented Windows `os.replace` flake** (self-contention with a live probe), reproduced 6/6 passing in isolation. Not my change.



## 8. Final verification (post-implementation)

- **Lint:** `ruff check .` → **All checks passed!** (was 15 errors). The two residual lint hits after `pip install .` were build byproducts (`build/`, `*.egg-info/`) — removed, and both added to `.gitignore` so they never re-enter.
- **Full suite (clean, no probes running):** `1329 passed, 0 failed in 52.49s` — 1323 prior + 6 new regression tests. The known `test_save_rename_race_never_tears_json` flake did not recur (it's the documented Windows `os.replace` sharing-violation race, ~12% under isolation; flagged as pre-existing, not introduced — needs its own hardening, out of this greenlight's scope).
- **Packaging:** `pip install .` → exit 0 in a clean venv; all 5 packages import from the installed dist.
- **New regression tests:** `tests/test_production_readiness.py` (6) — B1 traversal rejected (4 variants), B2 no live `0.0.0.0` bind, A1 corrupt-log → edits-present.

### Remaining (needs your decision — not in the greenlit scope)
- **A2 (full fix):** route the raw `open("w")` writers (`models.py`, `revision.py`, `memory.py`) through `atomic_write_json`. The *trigger* (A1) is closed, but the crash-truncated `edits.json` is still producible. This is a recovery-semantics decision (where to `.bak`, how undo/redo reads a healed log) — recommend pairing on it.
- **D (demo placeholders):** the canned `"Sample X finding."` stubs still ship. Product call: drop them or gate findings/fix-queue behind an honest "demo = filler" banner.
- **The flake:** `test_save_rename_race_never_tears_json` is the documented Windows flake; consider `pytest.mark.flaky`/raising `retry_permission` attempts. Out of scope here.

*Implementation completed 2026-09-20. All gates verified green. Nothing pushed (5 pre-existing unpushed commits remain, unchanged).*

---

## 9. Second implementation pass (A2 full + D demo-honesty + flake)

Continued greenlight. TDD (RED→GREEN): 4 new behavior tests failed RED before the fix; the two flake-budget tests added in the same pass.

| # | Item | Status | Evidence |
|---|---|---|---|
| A2 | Non-atomic writers → atomic | ✅ DONE | All writer-owned stores now route through `jsonio.atomic_write_json`: `models.py:ScriptDocument.save` (working.json/parsed.json chokepoint), `revision.py` (edits.json + edits.redo.json via `_save_json_list`, dismissed, undismissed, finding_intent, last_pass ×2, **and the ensure_working inline copy** — see self-critique), `memory.py` (WriterMemory.save + the v2-migration write). Verified by spy tests. **Deliberately left raw:** `knowledge_graph.save` (KG is regenerable), `report.py` (already atomic), `export.py` (creates new files). |
| D | Demo placeholder honesty | ✅ DONE (content) | The four canned findings now carry an explicit tag: `"[demo] Sample dialogue finding — the built-in demo model is running, not a real analysis."` (theme/character/genre likewise). The `plot_thread` "Setup left dangling: The revolver" finding is genuinely derived (REVOLVER/GUN branch) and stays. The fix-queue severity/act placement still shows, but each row now names itself as demo output. **Not done:** emptying the demo fix queue outright (a product call — would leave demo mode with nothing to show; flagging beats hiding). |
| Flake | Windows `os.replace` races | ✅ DONE (user decision) | `retry_permission` widened 3→6 attempts, capped 50–600ms equal-jittered. Root cause found: the hammer surfaces `PermissionError(13, "Access is denied")` with NO winerror under full-suite AV/indexer pressure — the winerror-only filter correctly read it as a genuine denial and refused to retry. **User decision (2026-09-20): retry EVERY PermissionError for the bounded window** (documented risk: a genuine read-only-disk denial is now retried ~1s before raising — it still raises, never swallowed). Implemented in `jsonio.py`; the two c10 tests asserting the old fail-fast contract re-scribed (bounded-retry-then-raise, never-swallowed); a new test guards that non-PermissionErrors still fail immediately. |

**New tests in `test_production_readiness.py` (12 total):** B1 traversal (4), B2 demo-bind, A1 corrupt-log, A2 atomic-writes (3: edits_log, writer_profile, working_copy), D demo-tag, retry-budget (2: default>=6, genuine-denial-fails-fast).

**Self-critique this pass (things I got wrong and fixed):**
- My `test_working_copy_is_atomic` missed `working.json` because `ensure_working()`'s **first-use inline copy** (`revision.py:307-308`) still wrote raw — I'd only atomized `ScriptDocument.save`. The spy test caught a real gap the audit missed; fixed.
- The first spy tests failed on my own bugs (wrong class name `WriterProfile`→`WriterMemory`; missing parse step so `save_working` correctly refused with FileNotFoundError). Not code regressions — test bugs, fixed.
- **Widening `retry_permission` alone did NOT eliminate the two flakes** — the failing signature was a bare `PermissionError(13)` (no winerror), which the winerror-only filter correctly refused to retry. **Resolution (user-approved):** retry every PermissionError for the bounded window; documented risk accepted. Re-scribed the two c10 tests that asserted the old fail-fast contract (now assert bounded-retry-then-raise) rather than deleting them; a new test guards non-PermissionErrors still fail immediately. Full suite after: **1336 passed, 0 failed**.

**What I did NOT do and why:** I did not delete or `@pytest.mark.flaky` the two flaky tests to force green — they were re-scribed to the decision's actual contract. I did not broaden the transient set silently; the trade (a genuine denial is retried ~1s) is documented in `jsonio.py` and here, because the user explicitly accepted it.

**Final state (post-decision):** `ruff check .` → All checks passed; full suite → **1336 passed, 0 failed, 3 warnings** in ~73s. Readiness suite 13/13. All greenlit items closed; nothing pushed.

---

## 10. Third pass (2026-09-20, post-rescan): the fork, the last silent store, and a real CI gate

Triggered by a full re-scan of the tree. Five items, each verified by execution.

| # | Item | Status | Evidence |
|---|---|---|---|
| F0 | **The count contradiction resolved as a SCOPE problem, not a default problem** | ✅ DONE | The dock's mass strip said `6 open of 6 findings` (whole script) above a fix queue saying `0 shown / 6 total` (filtered). Neither labelled its scope. The N3 counting contract owned *disposition* but not *scope*: added `inFindingFilter()` (ONE predicate) + `findingCounts()` (`total`/`open`/`shown`/`openShown`), the strip now appends `· N shown by filter` when narrowed, and the fix queue's private predicate was deleted. `e2e_browser_phase6_evidence` **31/1 → 33/0**: its pinned "honest empty hint" check is re-scribed to the *new* contract (default shows the ledger whole; the empty state is reached by narrowing), not deleted. |
| A3 | **The last writer-owned store with a raw write + a swallowing reader** | ✅ DONE | `premise.json` was still `open(...,"w")` at two sites and BOTH readers collapsed every error into "no premise card", so a torn file erased the writer's title/logline/premise/open-questions silently. Now atomic via `atomic_write_json`; `_load_premise()` distinguishes MISSING from UNREADABLE; `POST /premise` returns **409 and refuses to overwrite** a damaged card; `GET` surfaces `premise_error`. Also `metrics.json` (raw → atomic + load-modify-write under `lock_for`). 3 new tests, each shown to fail against the pre-change source (regex matched OLD=True / NEW=False; the old file had 8 blanket `except Exception: pass`). |
| B1 | **~460 browser checks were never run by CI** | ✅ DONE | New job `test-browser` in `ci.yml` (install chromium, run `tests/run_browser_suites.py`); `test-js` pinned `ubuntu-latest` → `ubuntu-24.04`; every job given a `timeout-minutes`. New `tests/run_browser_suites.py` runs all runnable suites and fails on any failure/crash. The 4 unrunnable suites are named exclusions printed on every run (2 need a live `E2E_BASE`; 2 crash inside the Design-Lab previews). |
| B4 | **The STT "never off the machine" guard was prefix-bypassable** | ✅ DONE | `url.startswith(("http://localhost","http://127.0.0.1"))` accepted both `http://127.0.0.1@evil.com` (userinfo) and `http://localhost.evil.com` (suffix), both resolving remotely. Now parsed with `urlparse` and the hostname compared against `{localhost, 127.0.0.1, ::1}`. 7 new tests (4 refused, 3 accepted). |
| F10 | **Palette offered project-only commands in the idea room** | ✅ DONE | They were listed as guarded no-ops, so clicking did nothing. Now hidden entirely without a project (`hasProject` gate). Also removed a duplicate `b` binding — the palette advertised `b` for both Beat Board and Problem Board while the keydown handler only ever opened the Beat Board. 2 new browser checks in `phase9` (**14 → 16/16**). |

**Deliberately NOT changed (with reasons):**
- **F2/F3 — one finding rendering 4× and floating cards occluding the manuscript.**
  > **SUPERSEDED — closed in §11.** The paragraph below records the call made
  > before anyone measured the geometry. A probe then showed 164px of every
  > finding card lying on the script, so the "needs visual review" deferral was
  > withdrawn and the occlusion half was fixed and pinned. Kept for the audit
  > trail; do not read it as current.
  `e2e_browser_phase13_legacy_cleanup.py:182-193` **pins** the current design: the
  Problem Board and the Context Dock are meant to coexist, with the board bowing left
  of an open dock. Making them mutually exclusive would break two deliberate checks,
  and the per-scene float lives under the frozen visual system (6.5k lines of CSS).
  Which surface *wins*, and whether the float becomes ink-only, is a product call that
  needs visual review — not a blind patch. **Recommended:** desk shows ink only; the
  board and dock carry the cards; then delete the duplicate float.
- **B5 — the two prompt-budget warnings** (`rules_context.py:182` 65k chars vs a 40k
  soft ceiling; `context.py:596` an 8.5k irreducible context over an 8.5k budget).
  Both are already env-configurable; raising the defaults silently would trade
  correctness for quiet. Both are now documented in `.env.example` with the exact
  trade-off, so the operator can decide.
- **B9 — LICENSE / CHANGELOG.** A licensing choice is the owner's, not an agent's.

**Verified after this pass:** `ruff check .` → All checks passed. Full suite →
**1351 passed, 0 failed, 3 warnings**. Readiness suite 21/21. Browser gate → all
**25 runnable suites green, 463 checks, 0 failures** (2 skipped by design, 2
known-broken), every one of them re-run after the final change in this pass.
Nothing pushed; working tree still uncommitted.

---

## 11. Fourth pass (2026-09-20, second scan): the occlusion was measurable, and the store class

Two threads. The first closed what §10 deliberately left open (F2/F3) once the
question was answered with a measurement instead of an opinion; the second
attacks the *class* of bug behind A2/A3 instead of the next instance.

| # | Item | Status | Evidence |
|---|---|---|---|
| R6 | **The floating finding cards occluded the manuscript** | ✅ DONE | `.scene-notes` was `position:absolute; right:-18px`, i.e. 196px of the 214px column lay ON the paper. A Playwright probe at 1440x900 measured **6 of 6 cards overlapping script text, worst 164px** — action lines clipped mid-word, exactly as the UI walk's screenshots showed. The margin is now **in-flow by default** (the failure is impossible by construction) and is promoted to the paper's gutter only when a **container query** says the paper has the room — a container query because the dock takes 380px *without changing the viewport width*, which is why the old `@media (max-width: 1100px)` escape never fired with the dock open. Gated on the Problem Board not being an open overlay (it is a `position:absolute` 300px panel sharing that gutter). Re-measured across four states (board expanded / collapsed / hidden, dock open): **0 overlapping cards, 0px**, and the pin is never under the board. |
| R6b | **A margin finding was a fourth full card with controls** | ✅ DONE | `e2e_browser_phase13_legacy_cleanup` has pinned board+dock coexistence since Phase 13, so surface *removal* was not the fix. Instead the margin aligned with `findingNoteEl`'s own stated contract — "margin pins stay read-only" — which the code did not honour: a pin now carries `Locate` and nothing else, while Rewrite/Discuss keep their homes on the dock's deep cards (asserted by `phase6_evidence`). 6 new live checks in `phase13` (**26 → 32**), plus source-contract guards in `test_production_readiness.py`. |
| R7 | **The A2/A3 class: "unreadable" reading as "you have nothing"** | ✅ DONE | New `tests/test_store_fault_injection.py` drives **every** writer-owned store through three injected faults (crash-truncated, flipped-byte, zero-byte) and requires, per store: MISSING → its default, VALID → data, DAMAGED → **an error, never the default**, and a load-modify-write must not replace a damaged file's bytes. It found **6 stores still silently degrading**: margin notes, stash, beat board, metrics, finding intents, dismissed findings — each of which not only hid the writer's data but then *overwrote the damaged file* on the next mundane action (add a note, stash a line). All six now read through one shared `jsonio.load_json_store` / `StoreUnreadable`: MISSING → default, PRESENT-BUT-UNREADABLE → raise, so the load-modify-write refuses instead of finalising the loss. The HTTP half is a `StoreUnreadable` handler answering **503 with the store name and the byte-level reason** instead of an empty list. |
| R7b | **The old test asserting the defect** | ✅ RE-SCRIBED | `tests/test_stash.py::test_load_tolerates_missing_or_bad_file` pinned "missing OR bad → `[]`" — the exact silent-loss contract. It is now `test_load_distinguishes_missing_from_damaged`, with the rationale in the docstring. This is a deliberate contract change, not a flake fix. |
| R7c | **Discovery: a new store could ship untested** | ✅ DONE | The harness greps every `atomic_write_json(` caller and fails when a module has no registry entry, so the next store cannot be added without fault coverage. Two exemptions are recorded *with reasons* (`orchestrator.py` progress telemetry — transient and fail-soft; `screenplay_parser/models.py` — regenerable from the source, with the unregenerable part covered by the edit-log case). |

**RED-validity, checked rather than assumed:** the harness was run against the
pre-fix readers first — **36 checks failed** across exactly the six stores above.
Then one fixed reader (`stash`) was temporarily reverted with the rest in place:
**exactly 4 checks failed** (3 faults + the overwrite test) and went green again
when restored. The suite is not vacuous.

**Verified after this pass:** `ruff check .` → All checks passed. Full suite →
**1419 passed, 0 failed, 3 warnings**. JS → 7/7. Browser gate (`tests/run_browser_suites.py`)
→ **25 suites, 0 failed, 2 skipped by design, 2 known-broken** (the Design-Lab
previews, named on every run). Nothing pushed; working tree uncommitted.

**Still open from §10:** B5 (the two prompt-budget warnings — documented in
`.env.example`, defaults not raised), B9 (LICENSE/CHANGELOG — an owner decision), and
the UI-walk items that are layout/idea-room work rather than defects: dock density
(#4), the cryptic scene rail (#5), the idea canvas dead end (#6), idea-room chat
discovery and input routing (#7), and the narrow-width drawer (#9). See
`ui_evidence_findings_2026-09-20.md` for the per-defect table.
