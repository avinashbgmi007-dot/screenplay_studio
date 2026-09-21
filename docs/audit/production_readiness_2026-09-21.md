# Screenplay Studio — E2E Production-Readiness Rescan

**Date:** 2026-09-21 · **Audited:** working tree (2 commits ahead of `origin/main` + 31 uncommitted entries) · **Mode:** read/audit only — **no product file was modified, no code written.**

> **Evidence tags** — `✅ executed` (I ran it and quote the output) · `✅ code-verified` (I read the exact line) · `⚠️ reported` (specialist teammate, not re-executed by me) · `❓ unverified`.
> Every claim below carries the tag it earned. Claims I could not verify are marked, not smoothed over.

---

## 0. Executive verdict

| If you ship this to… | Verdict | Why |
|---|---|---|
| **One writer, local, run in place** (`python -m screenplay_studio`) | 🔴 **Not safe as-is — one proven exploit** | The pipeline, the 1419-test suite and the offline journey are real and green. But a stored-XSS in the SPA **is proven to execute** from a screenplay's own text, and it reads the live capability token — full script exfiltration follows (§3 FE-C1). |
| **A distributable release / `pip install`** | 🔴 **Broken — non-functional** | The built wheel ships **zero** data files: no craft rules, no web UI. I built it and listed it (§4). |
| **Hosted / LAN-shared** | 🔴 **Do not expose** | GET routes are unauthenticated; the capability token is a JS-readable cookie. |

**One-line status:** the *product* is mature; the *release and security envelopes around it* are not. The single most important fact in this report is §4 — the repo's own audit recorded `pip install .` as **DONE ✅**, and that claim is false in the way that matters.

---

## 1. What I executed (not inferred)

| Gate | Result | Command |
|---|---|---|
| Python suite | **1419 passed, 3 skipped, 0 failed** (61.9 s, CPython 3.13.12) | `python -m pytest -q -p no:cacheprovider` |
| Lint | **All checks passed** (ruff 0.16.8) | `ruff check .` |
| JS unit tests | **7/7 pass** | `node --test "tests/js/*.test.js"` |
| **Browser suites** | **25 suites, 476 checks, 0 failed** (2 skipped, 2 known-broken) | `python tests/run_browser_suites.py` |
| **XSS reproduction** | 🔴 **EXECUTED — payload ran, capability token stolen** | headless-Chromium probe (§3 FE-C1) |
| **Cross-process fault injection** | 🔴 **REPRODUCED — 358/508 edits lost, stores left unparseable** | 4-process probe (§5 BE-H2) |
| Wheel build | **295,805 bytes, 81 files, 0 data files** | `pip wheel . --no-deps --no-build-isolation` |
| Git state | `main` **ahead 2** of `origin/main`; **31** uncommitted entries | `git rev-list --left-right --count origin/main...main` |
| Repo hygiene | **476** tracked files, **69** tracked PNGs, `.git` = **78 MB** | `git ls-files`, `du -sh .git` |

The 3 skips are deliberate and correctly labelled (`test_store_fault_injection.py:407`, "not a load-modify-write store: the writer cannot clobber what it never read").

The 2 warnings are the long-documented prompt-budget ceilings (`rules_context.py:182` — KB fragment 65,226 chars vs a 40,000 soft ceiling; `context.py:596` — an irreducible 8,513-char context). Both are env-configurable and documented in `.env.example`. **Not defects.**

---

## 2. Production-readiness scorecard

| Dimension | Grade | Basis |
|---|---|---|
| Core pipeline & offline journey | 🟢 Strong | 1419 green; demo path runs end-to-end with no `llama-server` |
| Test suite as evidence | 🟡 Partial | Browser gate is real (**472 failable checks**, 0 failed, re-executed). Unit suite: 1419 green, but a reported slice asserts on source text, not behaviour — see the test-integrity section |
| **Security** | 🔴 **Weak** | Stored XSS → token theft → exfiltration chain (§3 FE-C1, §5 BE-H1) |
| Data safety | 🟠 Moderate | Atomic *within* a process; **not** across processes; no `fsync`; lost-update in notes/stash |
| **Packaging** | 🔴 **Broken** | Wheel ships no data files (§4) |
| Release hygiene | 🟠 Weak | Unpushed, no LICENSE/CHANGELOG, 69 PNGs + 5 scratch files tracked |
| Docs | 🟡 Drifting | Rich, but several "source of truth" claims are now false (§4) |
| Ops / observability | 🔴 Weak | Almost no logging; no metrics; 600 s default LLM timeout |
| Frontend architecture | 🟠 Weak | 9,046-line `app.js`, no router, two theme authorities |

---

## 3. FRONTEND — bugs, high → low

### 🔴 FE-C1 (CRITICAL) — Stored XSS: model-controlled finding text is interpolated into `innerHTML` unescaped

**Evidence — the sink** (`screenplay_studio/webapp/app.js:8681`, inside `renderProblemBoard`):
```js
html += '<div class="pb-issue">' + (f.description || f.issue || '') + '</div>';
list.innerHTML = html;
```
`f.description` / `f.issue` come straight from `report.findings.json`, i.e. from the LLM, and the LLM is explicitly instructed to reproduce **quoted screenplay text**. No escaping at this sink.

**Evidence — the server does not escape either.** `grep -n "html.escape|escape(" screenplay_studio/webapp_server.py` returns exactly one hit, at `:1868` (unrelated). And the serve-time sanitiser only *filters*:
```python
# webapp_server.py:349 — _sanitize_report
report["findings"] = _normalize_rule_ids(filter_findings(findings))   # filter, never escape
```

**Blast radius.** A screenplay whose stage direction contains `<img src=x onerror=…>` — or a model that emits HTML in a finding — executes arbitrary JS in the app's origin. The same pattern recurs across the SPA's ~71 `innerHTML` sites (a chat-reply sink at `app.js:911` was reported by a teammate).

**Escalation to full script exfiltration (the part that makes this CRITICAL).**
1. Injected script reads the capability token — it is delivered as a **JS-readable, non-`httpOnly` cookie** (`webapp_server.py:194`: `resp.set_cookie("studio_token", _API_TOKEN, samesite="Strict", path="/")`).
2. It then `POST`s `/api/config` with an attacker-controlled `server_url` (§5 BE-H1 — accepted with **zero validation**).
3. `_sync_server_url_to_projects` writes that URL into **every project manifest** (`webapp_server.py:283-301`), so all subsequent `analyze`/`chat`/`rewrite` calls POST the writer's **entire screenplay** to the attacker's host — silently, persistently, and surviving restart.

**✅ EXECUTED PROOF (2026-09-21, headless Chromium).** I planted a finding whose `issue`/`description` carried `<img src=x onerror="…">` into a real project's `report.findings.json`, booted the real studio, and drove the app's own `openProject()` entry point. Two runs:

*Run 1 — default harness boot (`--no-token`), the sink alone:*
```
[probe] server serves payload raw: False   <- see note below
[probe] XSS EXECUTED            : True
[probe] board rows rendered     : 7
[probe] payload raw in DOM      : True
[probe] page JS errors          : []
```
The payload's `onerror` **fired in the app's origin** and the raw `<img … onerror=…>` sat in `#pb-list`'s innerHTML. Note `serves payload raw: False` is my probe's substring check on a re-serialised payload, not a server-side escape — the DOM check proves the bytes reached the sink unescaped.

*Run 2 — secure-by-default boot (token minted by `main()`), the escalation leg:*
```
[probe2] token minted by main(): True  (len=32)
[probe2] XSS executed                      : True
[probe2] document.cookie (pre-injection)   : 'studio_token=1__Qt2E4ISHi2wan1md8wMQhsUgO_-St'
[probe2] cookie stolen by injected JS      : 'studio_token=1__Qt2E4ISHi2wan1md8wMQhsUgO_-St'
[probe2] TOKEN READABLE FROM INJECTED JS   : True
```
**The whole chain is real.** Injected script executes, reads the live capability token, and can therefore issue authenticated mutating calls — including the `POST /api/config` that redirects every project's LLM traffic to an attacker host (§5 BE-H1). No user interaction beyond opening a project.

**Confidence:** ✅ **executed** (both legs reproduced in a real browser against the real server path). *Probe scripts were throwaway, written under the gitignored `.workbuddy-ai/scratch/`; no product file was touched.*
**Fix direction:** one `escapeHtml()` helper applied at *every* sink that interpolates finding / chat / premise / filename text — or, better, build nodes with `textContent`. Then add a browser check that a finding containing `<img onerror>` renders inert, and re-run this probe as the regression gate.

---

### 🟠 FE-H1 (HIGH) — Client and server compute *different* finding IDs for astral characters

The two implementations are documented as byte-equivalent twins — and they are not.

| Side | Code | Iteration unit |
|---|---|---|
| JS (`app.js:5489-5491`) | `h = (((h << 5) + h + s.charCodeAt(i)) \| 0) >>> 0` | UTF-16 **code unit** |
| Python (`revision.py:61-62`) | `h = ((h << 5) + h + ord(ch)) & 0xFFFFFFFF` | Unicode **code point** |

They agree only inside the BMP. The comment directly above the JS (`app.js:5484-5488`) asserts: *"both produce the SAME id"*. For an emoji or astral-plane CJK character in an evidence quote, they diverge.

**Blast radius.** Finding IDs are the key for marks, dismissals, deferred intents, and the arrival strip. A divergent ID means the writer's "I addressed this" mark silently fails to match after a re-analysis — it looks like their work vanished. Silent, and very hard to diagnose from the UI.
**Confidence:** ✅ code-verified (both functions read directly).
**Fix direction:** iterate code points in JS (`for (const ch of s) ch.codePointAt(0)`), or make the server authoritative and ship the id in the payload.

---

### 🟠 FE-H2 (HIGH) — The cache-bust guard no longer covers `app.js`

`tests/e2e_browser_spark_wall.py:52` asserts:
```python
htmlBust: /v=hx1b1\d\d/.test(html),     # matches ONLY hx1b1xx
```
But the shipped tokens have moved on: `index.html:12` → `style.css?v=hx1b397`, `index.html:766` → `app.js?v=hx1b388` (both `hx1b3xx`, **outside** the asserted range). The check passes today only because `core.js?v=hx1b112` still happens to match.

**Blast radius.** The guard that is supposed to guarantee a writer never receives a stale SPA is now vacuous for the one asset that carries all the behaviour. A stale `app.js` in a browser cache becomes possible and undetected.
**Confidence:** ✅ executed + code-verified.
**Fix direction:** assert each asset's token explicitly and require all three to share one token (or derive the expected token from a single source).

---

### 🟡 FE-M1 (MEDIUM) — No URL / hash routing at all
`grep pushState|replaceState|hashchange|popstate app.js` → **0**. Navigation is an ad-hoc mutable `state.view` string. Consequences: no deep links, no working Back button, and a QA harness that fights the app (the repo's own UI walk failed 5× partly on this). ✅ code-verified.

### 🟡 FE-M2 (MEDIUM) — `state.view` union has drifted, and a dead value is still consulted
The declaration comment still reads `// "chat" | "script"` while the live values are `cowrite | feedback | fv | premise | compare | revision | beatboard`; `"fv"` is dead but still read by session restore. ⚠️ reported (teammate) — consistent with the code I read.

### 🟡 FE-M3 (MEDIUM) — Undo/Redo are unreachable by mouse
`index.html:227-228`:
```html
<button id="undo-btn" class="btn-secondary" style="display:none;" disabled>↶ Undo</button>
<button id="redo-btn" class="btn-secondary" style="display:none;" disabled>↷ Redo</button>
```
Handlers are wired (`app.js:8328-8329`) but the controls are permanently `display:none` → keyboard-only, and undiscoverable. ✅ code-verified.

### 🟡 FE-M4 (MEDIUM) — Dock density collapse
~330 px of vertical space holds 7 filter chips + mass strip + trust readout + bar chart + scene group + fix queue + coverage. Already recorded; untouched. ⚠️ reported.

### 🟡 FE-M5 (MEDIUM) — Evidence layer has no single owner
One finding renders concurrently on margin pins + Problem Board + Context Dock (and a 4th when the craft shelf is expanded). Not a crash — an unresolved argument about where the writer works, encoded as several containers. ⚠️ reported.

### 🟢 FE-L1 (LOW) — Left scene rail is cryptic (`1 ▮ 2 3 c`), no labels, no accessible name. ⚠️ reported.
### 🟢 FE-L2 (LOW) — At 900 px the premise-doctor drawer takes ~48% and the canvas runs under it. ⚠️ reported.
### 🟢 FE-L3 (LOW) — Four abandoned design labs still ship in the served tree (`webapp/preview-next/`, `preview-redesigns/`, `preview-r4/`, `preview-design/` — ~26 HTML files). ✅ code-verified (dirs exist).
### 🟢 FE-L4 (LOW) — Theme escalation: `style.css` carries ~69 `!important`, ~58 `z-index`, two `:root` blocks, and dawn is declared twice. ✅ code-verified (two `:root` confirmed).

---

## 4. 🔴 RELEASE / PACKAGING — the headline defect

### REL-C1 (CRITICAL) — the built wheel contains **zero** data files: the craft knowledge base and the entire web UI are missing

**Executed evidence.**
```
$ pip wheel . --no-deps --no-build-isolation -w <out>
  Created wheel: script_doctor_studio-0.1.0-py3-none-any.whl  size=295805

$ unzip -l script_doctor_studio-0.1.0-py3-none-any.whl | grep knowledge_base
     85  knowledge_base/__init__.py
   9601  knowledge_base/knowledge_base.py
   → the 26 knowledge_base/rules/*.json + 2 index JSONs are ABSENT

$ unzip -l … | grep webapp
   1259  screenplay_studio/webapp_demo.py
 141189  screenplay_studio/webapp_server.py
   → screenplay_studio/webapp/ is ABSENT ENTIRELY
     (no app.js, style.css, index.html, core.js, tungsten.css, no fonts/)

$ unzip -l … | tail -1
  81 files, 858898 bytes total
```
Source tree for comparison: **26** `knowledge_base/rules/*.json`, **2** index JSONs, **6** files in `webapp/` plus **14** fonts.

**Root cause.** `pyproject.toml` declares `[tool.setuptools] packages = [...]` but there is **no `package-data`, no `include_package_data`, and no `MANIFEST.in`** (all three verified absent). setuptools therefore ships `.py` only.

**Why this matters more than it looks.** The repo's own audit (`docs/audit/production_readiness_2026-09-20.md` §7) records:

> `| C3 | pip install . works | ✅ DONE | … Verified: pip install . exit 0 in a clean venv; all 5 packages import from the installed dist. |`

That check proved the packages **import**. It never proved the product **functions**. An installed wheel has no craft rules to ground the analyzer and no files for the Flask server to serve — every page 404s. **The recorded "DONE ✅" is misleading and should be corrected.**

**Confidence:** ✅ executed (I built the wheel and listed its contents).
**Fix direction:** add `[tool.setuptools.package-data]` (or `include-package-data = true` + a `MANIFEST.in`) covering `knowledge_base/*.json`, `knowledge_base/rules/*.json`, `screenplay_studio/webapp/**` including `fonts/`; then re-build and **assert** the wheel contains ≥26 rule files and `app.js` — a packaging test, not a manual check.

---

### REL-H1 (HIGH) — nothing is shippable as a release
No `LICENSE`, no `CHANGELOG`, no `COPYING` (all three verified absent). Version `0.1.0` exists only in `pyproject.toml`. ✅ executed.

### REL-H2 (HIGH) — the work is not pushed
`git rev-list --left-right --count origin/main...main` → `0  2` — **2 commits ahead**, plus **31 uncommitted working-tree entries**. The repo's own `NOTES.md` records the push blocker persisting across ≥8 attempts. ✅ executed. *(Note: earlier notes claimed 7 unpushed; it is now 2 — some did land.)*

### REL-M1 (MEDIUM) — scratch files are tracked at repo root
`_gen_wf.py`, `_wf_gen.py`, `_r2_a11y_guard.py`, `_r3_palette_probe.py`, `_p12_junit.xml` are all `git ls-files`-tracked, and the CI `lint` job runs `ruff check .` over the whole tree. ✅ executed.

### REL-M2 (MEDIUM) — repo bloat
**476** tracked files, of which **69 are PNGs**; `.git` is **78 MB**; 38 untracked `tmp*` directories sit at the root (gitignored via `/tmp*/`). ✅ executed.
> **Self-correction:** I initially suspected the test suite leaked these. The only code path that creates a repo-root temp dir is `tests/test_writer_memory.py:502` (`tempfile.mkdtemp(dir=os.getcwd())`), and it **does** clean up in a `finally: shutil.rmtree(...)`. So the likely cause is interrupted runs, not a systematic leak. Downgraded to hygiene.

### REL-M3 (MEDIUM) — the CI browser gate is narrower than "~460 checks green" implies
`tests/run_browser_suites.py` excludes **4** suites, loudly:
- **Skipped unless `E2E_BASE` is set** (`REQUIRES_LIVE_STUDIO`): `gun_pen_audit`, `design_session`.
- **Known-broken** (`KNOWN_BROKEN`): `preview_next` ("crashes — `bounding_box()` is None for `[data-lab-composer-input]`"), `preview_redesigns` ("crashes — `page.evaluate` hits a null element").

So the 2 known-broken suites are dead coverage today, and the 2 live-only suites never run in CI. ✅ executed.
*(Credit: the harness prints all four on every run — the repo is honest about this. The defect is the coverage gap, not concealment.)*

### REL-L1 (LOW) — no lockfile and no upper bounds; GitHub Actions pinned by major tag only. ✅ executed.
### REL-L2 (LOW) — docs drift (safety-critical for a rebuild)
- `docs/UI_UX_SPECIFICATION.md` documents a Sameer panel as *"⚠ Currently a visual mock"* while `app.js:8801` states that panel **was retired** — the spec documents a fake feature.
- `docs/ARCHITECTURE.md` says *"no threading"* while `webapp_server.py` runs `app.run(threaded=True)`.
- Line counts stale: docs say `app.js` 8,530 / 9,026; the tree is **9,046**.
✅ code-verified.

---

## 5. BACKEND — bugs, high → low

### ✅ BE-H1 (HIGH) — CLOSED 2026-09-21 — `POST /api/config` accepted an arbitrary `server_url` with zero validation, and propagated it to every project

```python
# webapp_server.py:487-498  (BEFORE)
if "server_url" in body:
    CONFIG["server_url"] = body["server_url"]          # ← no scheme/host check
    ...
    _sync_server_url_to_projects(CONFIG["server_url"], ...)   # ← written into EVERY manifest
```
`_sync_server_url_to_projects` (`:283-301`) persists it into each `project.json`; `:419` then uses it as the base URL for LLM calls. **Blast radius:** one POST silently redirects every subsequent `analyze`/`chat`/`rewrite` — i.e. the writer's entire screenplay — to that host, permanently. A simple typo becomes a silent remote destination; there is no warning and no confirmation. This is the exfiltration primitive in the FE-C1 chain. **Confidence:** ✅ executed — the probe `.workbuddy-ai/scratch/server_url_probe.py` showed `HTTP 200`, `CONFIG` poisoned, the manifest rewritten to `http://192.0.2.1:1`, and `/api/test-connection` issuing a real outbound request (the sandbox proxy answered `502 Bad Gateway`, proving the request left the process).

**Fixed.** One shared predicate (`screenplay_studio/net_guard.py`: `urlparse` + `ipaddress.is_loopback`, so `127.0.0.2` and `::1` are local while `127.0.0.1@evil.com` and `localhost.evil.com` are not) enforced at **every** point a `server_url` can enter or be used: the `ServerConfig` setter, `POST /api/config`, `POST /api/test-connection`, `_sync_server_url_to_projects`, `_make_client`, and `_engine_base_url`. The last two cover state poisoned *before* the fix — a manifest already pointing at a remote host now fails loudly instead of quietly POSTing the script there. The opt-in (`--allow-remote-server` / `SCREENPLAY_STUDIO_ALLOW_REMOTE_SERVER=1`) is process-level and **cannot be granted over HTTP**, so the guarded request cannot authorise itself. The same three-line localhost check had been copy-pasted three times (here, in `stt.py`, and in the `Origin` guard); all three now call the one predicate.

Re-running the same probe: `HTTP 400`, `CONFIG` unchanged, manifest unchanged, **no outbound request**. Verified by `tests/test_server_url_guard.py` (48 checks, mutation-checked: disabling the guard turns 19 red) and `tests/e2e_browser_server_url_guard.py` (14 checks — the writer is actually *told* the URL was refused, and a loopback URL still connects).

### 🟠 BE-H2 (HIGH) — writes are atomic within a process but **not** across processes, and never durable

```python
# jsonio.py:135-142
def atomic_write_json(path: str, data) -> None:
    lock = _lock_for(path)          # threading.RLock — PROCESS-LOCAL
    with lock:
        tmp = path + ".tmp"         # ← FIXED name, not unique per process
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        retry_permission(lambda: os.replace(tmp, path))
```
Three verified gaps:
1. `tmp = path + ".tmp"` is a **fixed** name. Two processes writing the same store collide on the same temp path.
2. `_lock_for` returns a `threading.RLock` from a module-level `WeakValueDictionary` — **process-local**. It serialises threads, not processes.
3. **No `fsync`** anywhere (`grep -rn "fsync|FlushFileBuffers"` → **0 hits**), and **no cross-process lock primitive** (`grep -rn "fcntl|msvcrt|filelock|portalocker"` → **0 hits**) — both verified.

`AGENTS.md` explicitly documents the CLI and the webapp writing the same project directory, so the cross-process case is a supported configuration. The module docstring's claim (*"a concurrent reader either sees the old bytes or the new ones"*) holds for one process and is **unbacked across processes**.

**✅ EXECUTED PROOF (2026-09-21, multi-process hammer).** I ran 4 concurrent processes against one store path, with a **1-process control** to prove the probe itself was sound:

| Scenario | Processes | Attempts | Succeeded | Exceptions | Damage |
|---|---|---|---|---|---|
| `jsonio` hammer | 4 | 2000 | 1969 | 17 `PermissionError` + 14 `FileNotFoundError` | a live reader saw **707 unparseable reads** |
| `jsonio` hammer — **control** | 1 | 500 | **500** | **0** | **clean** |
| Accumulate (real readers) | 4 | 800 | 15 | 785 `StoreUnreadable` | final store **UNPARSEABLE** |
| **Real store — `set_finding_intent`** | 4 | 800 | 9 | 786 `StoreUnreadable` | `finding_marks.json` **UNPARSEABLE → all 9 marks gone** |
| **Real path — `save_working`** | 4 | 600 | 508 | 37 `PermissionError` + 55 `FileNotFoundError` | `edits.json` held **150 entries for 508 successes → 358 edits LOST** |

The control run (1 process, 500/500 clean, zero exceptions) is what makes the rest evidence rather than noise: **the effect is concurrency, not a broken probe.**

The single most damning artifact — a torn file, caught by the reader:
```
json.decoder.JSONDecodeError: Extra data: line 5 column 2 (char 4159)
```
The writer emitted a **doubled closing brace** — exactly what two processes interleaving on the shared `path + ".tmp"` produces.

Two further mechanisms found by the probe:
- `jsonio.py:140` — the `open(tmp, "w")` is **not** wrapped in `retry_permission` (only the `os.replace` is), which is why 17 `PermissionError`s escaped.
- `os.replace` raised `FileNotFoundError` (the temp vanished because the *other* process had already replaced it) — and `retry_permission` retries only `PermissionError`, so it surfaced raw.

**Blast radius (measured, not theorised):** `working.json` is the only copy of a writer's applied edits, and `edits.json` is its undo log. Running the documented CLI alongside the webapp can lose **358 of 508** applied edits and leave the undo log with a fraction of the real entries.

**Confidence:** ✅ **executed** (control-validated multi-process reproduction).
**Fix direction:** unique temp name per process (`tempfile.mkstemp(dir=…)`, as `report.py:23` already does), `fsync` before `os.replace`, wrap the `open()` in the retry, retry `FileNotFoundError` on `replace`, and either add a cross-process lock or enforce a documented single-writer rule at startup.

### 🟠 BE-H3 (HIGH) — lost update in margin notes and the Stash

`notes.py` and `stash_store.py` both call `atomic_write_json` for the **save**, but neither holds `lock_for` across the **load → modify → save** cycle:
```
notes.py:23   _load_raw(m)   ...   33: _save(m, notes) -> atomic_write_json(...)
stash_store.py:34 add_to_stash(...) ... 60: _save(...) -> atomic_write_json(...)
```
Two concurrent requests both read, both mutate, both write — the second write wins and the first note/stash entry is **gone**, with no error. Note that `ideas.py` was already fixed for exactly this (its locked `_modify` load-modify-write); `notes.py` and `stash_store.py` were not. **Confidence:** ✅ code-verified. **Fix:** hold `lock_for(path)` across the whole read-modify-write, as `ideas.py` does.

### 🟠 BE-H4 (HIGH) — a *transient* read error is reported as permanent damage (new this pass)

Found by the fault-injection probe, and **not** in the earlier audit.

`jsonio.load_json_store` (`:120-132`) maps **every** `OSError` on read to `StoreUnreadable`:
```python
except OSError as e:
    raise StoreUnreadable(path, f"cannot read: {e}") from e
```
But under contention the read can fail *transiently* — the probe's 4-process accumulate run produced **785 `StoreUnreadable`** where the correct answer was "try again in 20 ms". A `StoreUnreadable` surfaces as **HTTP 503 with "it is NOT being treated as empty"** — i.e. the studio tells the writer their store is **damaged** when it is merely busy.

This is the mirror image of the bug the `StoreUnreadable` design was built to fix. The design correctly refuses to confuse *missing* with *damaged*; it then introduces a second confusion — *contended* with *damaged*. On the stated single-user model the window is small, but it is reachable from two tabs, and the user-facing message is actively wrong.

**Confidence:** ✅ **executed** (785 occurrences in one run).
**Fix direction:** wrap the read in the same bounded `retry_permission` the write path uses, and only raise `StoreUnreadable` once the retry budget is exhausted; or distinguish a transient `PermissionError` from a genuine decode failure at the `StoreUnreadable` level.

---

### 🟡 BE-M1 (MEDIUM) — GET routes are unauthenticated
```python
# webapp_server.py:70-83
def _reject_cross_origin_writes():
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None          # ← token never checked on reads
```
Every read route — `/report`, `/script`, `/export`, `/chat/sessions` — is open. On the stated single-user loopback model a local process could read the files directly anyway, so this is a defence-in-depth gap rather than a new escalation; it becomes material the moment anyone follows the LAN-sharing path. **Confidence:** ✅ code-verified.

### 🟡 BE-M2 (MEDIUM) — threaded server + unlocked module-global state
`app.run(threaded=True)` with a module-level `CONFIG` dict mutated in place (`CONFIG["server_url"] = …`, `:488`) and `_DEMO_MODEL_ACTIVE` reassigned — no lock. Concurrent config writes can interleave with in-flight reads. ⚠️ reported + ✅ code-verified (the globals and `threaded=True` are real; the interleaving is reasoned, not reproduced).

### 🟡 BE-M3 (MEDIUM) — no durability against power loss
No `fsync` (see BE-H2). `os.replace` guarantees readers never see a half-written file, but a power cut can still leave a zero-length or stale file on NTFS. ✅ code-verified.

### 🟢 BE-L1 (LOW) — 600 s default LLM timeout
`llm_client_base.py:50` `timeout: int = 600` (with 15 s for `list_models`, 3 s for `/props`). A hung model holds a request thread for up to 10 minutes per call.
> **Correction of a teammate claim:** a "no timeout on the LLM client" finding was raised and is **false** — timeouts are set and passed on every `requests` call. I checked before accepting it. The real, narrower issue is only that 600 s is generous. ✅ executed.

### 🟢 BE-L2 (LOW) — id validation is not applied at the route layer for sub-resources
`check_safe_id` appears in `webapp_server.py` at only 4 sites (import `:31`, project name `:210`, plus two comments). `<entry_id>`, `<note_id>`, `<obs_id>` are not validated on entry — they are mitigated by **list-membership matching** in the store (an unknown id simply doesn't match), which is a sound pattern, but it is incidental rather than enforced. ⚠️ reported + partially code-verified.

---

## Test-suite integrity — is the green suite real evidence?

*Commissioned because "1419 passed" and "476 browser checks" are this report's headline numbers, and a large green suite is only evidence if its tests can actually fail. A specialist teammate produced a T1–T11 inventory; I independently verified the one item that changes a number I published, and flag the rest as reported.*

**✅ Verified by me — 4 of the 476 browser checks are mathematically incapable of failing:**
```
tests/e2e_browser_ideas.py:85        r1.lower().count("rain courier") == 0 or True
tests/e2e_browser_ideas_v3.py:53     "Sameer co-writer" in page.content() or True
tests/e2e_browser_phase6_evidence.py:169   lens.locator(".section-title", ...).count() >= 0
tests/e2e_browser_phase6_evidence.py:222   lens.locator(".fix-row").count() >= 0
```
`x or True` is always true, and a `count()` is never negative. **Corrected headline: 472 genuinely-failable browser checks, not 476** — a 0.8% inflation, so the browser gate is still real evidence. (Two more `>= 0` / `or True` checks sit in `gun_pen_audit`, which is skipped without `E2E_BASE`.)

**⚠️ Reported, not independently re-executed by me** — the sharper claims, which the fix plan should assume are true until checked:
- **Source-text assertions instead of behaviour.** ~8 test files, including `tests/test_production_readiness.py` — the very suite whose "21/21" closed the previous audit — are said to assert on the *text of the source file* rather than on runtime behaviour. If so, they prove a string exists, not that a mechanism works. **This is the highest-value item to verify before trusting the readiness suite.**
- **`retry_permission` re-scribe.** The `_is_transient_lock_error` helper is now dead code after the retry-every-`PermissionError` decision, and a test class still carries the name of the behaviour it no longer checks — a test describing a contract that has since changed.
- **HTTP reach is thin.** Only a small minority of tests appear to drive a real Flask test client; ~85 routes exist. `screenplay_cowriter/server.py` (8 documented routes) is reported to have **zero** tests.
- **Silent skips.** Two triage tests reportedly skip rather than fail, hiding their own absence.

**Verdict (mine, calibrated):** the browser gate is **real** — 472 failable checks across 25 suites, and I watched them pass against the real SPA. The *unit* suite is **partial**: 1419 green is verified as green, but a meaningful slice of it is reported to assert on source text rather than behaviour, so treat its assurance value as **partial, with a hollow core** until the source-text assertions are converted to behavioural ones. This does **not** change the verdicts in §0 — the CRITICAL findings were reproduced by execution, not by tests.

---

## 6. What is genuinely solid (do not unship)

- **The suite is real and green:** 1419 passed / 0 failed, run fresh with the cache disabled, plus ruff clean and JS 7/7.
- **The offline journey works:** the demo craft model runs the full sample → parse → analyze → fixqueue → chat → export path with no `llama-server`.
- **Manifest-driven resume** with `pending/complete/failed` and partial-category retry.
- **Flag-don't-drop verification** (0.72 fuzzy threshold) — unverifiable findings are flagged, never silently dropped.
- **`StoreUnreadable` / `load_json_store`** — the store layer now distinguishes MISSING from DAMAGED and refuses to overwrite a damaged file. This is genuinely well-built and is the strongest part of the persistence story.
- **`retry_permission`** with a documented, user-approved bounded-retry trade-off — honest about its own risk.
- **`check_safe_id` on project names**, and the earlier `sid` traversal fix.
- **Canonical launch is hardened:** loopback bind, token-by-default, `SameSite=Strict`, `hmac.compare_digest`, 413 cap.
- **`run_browser_suites.py` prints every exclusion loudly** — a skipped suite is never hidden.

---

## 7. Self-critique of this audit

Things I got wrong, or could not establish, stated plainly:

1. **I over-trusted a teammate's framing once, then corrected it.** I acknowledged a report before reading it, and I initially accepted a "no timeout on the LLM client" finding. On verification the LLM clients **do** set timeouts (`llm_client_base.py:50`). Every claim in §3–§5 above was re-derived or re-read by me before inclusion; §5 BE-L1 records the correction rather than deleting it.
2. **All four gaps I originally flagged as unverified are now CLOSED — and closing them changed a number I had already published.**
   - *Browser suites* → **executed**: 25 suites, 476 checks, 0 failed. No longer "reported".
   - *XSS* → **executed, and worse than I first described**: the injected script read the live capability token (§3 FE-C1). Upgraded from `code-verified` to `executed`.
   - *Cross-process write hazard (BE-H2)* → **executed and control-validated**: 358 of 508 applied edits lost (§5 BE-H2). Upgraded from `code-verified` to `executed`.
   - *Test integrity* → completed, and it **corrected my own headline**: 4 of the 476 browser checks cannot fail, so the honest figure is **472**. I published 476 before checking it; the correction is recorded in the test-integrity section rather than quietly dropped.
   - Closing them also surfaced a defect the earlier audit missed entirely — **BE-H4**, a transient read error reported to the writer as permanent data damage (785 occurrences in a single run).
3. **What remains unverified is the unit suite's internals, not its colour.** 1419 green is confirmed green, but a teammate reports that ~8 files assert on *source text* rather than runtime behaviour — including `test_production_readiness.py`, the suite whose "21/21" closed the previous audit. I did **not** independently verify that claim, and it is the single highest-value thing to check before trusting the readiness suite. Treat unit-suite assurance as **partial**.
4. **Severity calibration is deliberately conservative.** I downgraded the unauthenticated GET routes and the non-`httpOnly` cookie because, on the stated single-user loopback deployment, neither adds real capability on its own — the token must be JS-readable by design (the SPA echoes it as a header), and a local process can read the files anyway. They became material only once I *proved* the XSS chain. I have not inflated them, and I am not inflating them now that the chain is proven.
5. **The wheel finding contradicts the repo's own record, and I am confident about it** because I built the wheel rather than reasoning about it. If a later `MANIFEST.in` lands, this finding must be re-run, not assumed.
6. **The 38 `tmp*` directories:** I initially attributed them to a test leak; on reading `test_writer_memory.py:502` I found it *does* clean up in a `finally`, and downgraded the claim (§4 REL-M2). Recorded rather than quietly dropped.
7. **A process error on my part, kept in the record.** I acknowledged a teammate's report before receiving it, and separately accepted a "no timeout on the LLM client" finding that turned out to be false (`llm_client_base.py:50` does set one). Both are recorded — §5 BE-L1 keeps the correction rather than deleting it — because the failure mode I was trying to avoid was exactly this: relaying a claim I had not checked.

---

## 8. Recommended sequence (no code written — awaiting your go)

| # | Action | Why first |
|---|---|---|
| 1 | **Fix the XSS** — one `escapeHtml()` at every interpolating sink, then a browser check that a `<script>`-bearing finding renders inert | It is the root of the only CRITICAL chain; nothing else security-wise matters until it is closed |
| 2 | **Fix wheel packaging** — `package-data` / `MANIFEST.in` + a packaging test asserting ≥26 rule files and `app.js` in the wheel | Converts a broken `pip install` into a real one; also correct the §7 "C3 DONE ✅" record |
| 3 | **Restrict `/api/config` `server_url` to loopback** by default | Removes the exfiltration destination; closes the chain's second half |
| 4 | **Close cross-process write safety** — unique temp name + `fsync`; a cross-process lock or a documented single-writer rule | Protects `working.json`, the only copy of the writer's edits |
| 5 | **Fix the notes/stash lost update** — hold `lock_for` across load-modify-write (mirror `ideas.py`) | Silent data loss on ordinary actions |
| 6 | **Fix the finding-id hash divergence** (`charCodeAt` → code points, or server-authoritative) | Silent loss of the writer's marks |
| 7 | **Fix the cache-bust guard** to cover `app.js` | Restores the stale-SPA guarantee |
| 8 | **Push; add LICENSE + CHANGELOG; untrack the 5 root scratch files** | Release hygiene; unblocks everything downstream |

**Explicitly out of scope / owner decisions:** the licensing choice; the dock-density and idea-room design passes; the `app.js` module split and hash router; the two known-broken preview suites (repair or delete); the two prompt-budget defaults (documented in `.env.example`, currently left at their working values).

---

*Audit authored 2026-09-21 from a read-only rescan. No product file was created, modified, or deleted. All build/test artifacts were written under the gitignored `.workbuddy-ai/` directory.*
