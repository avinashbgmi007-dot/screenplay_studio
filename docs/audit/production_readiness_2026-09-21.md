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
| Docs | 🟡 Drifting | Rich, but several "source of truth" claims are now false — see §8 (three of them were fixed in pass 7: `ARCHITECTURE.md`, `DEVELOPMENT.md` and `NOTES.md` all asserted "there is no `pyproject.toml`") |
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

### ✅ FE-H2 (HIGH) — CLOSED 2026-09-21 — the cache-bust guard was vacuous (it matched one of four token shapes)

`tests/e2e_browser_spark_wall.py:52` asserts:
```python
htmlBust: /v=hx1b1\d\d/.test(html),     # matches ONLY hx1b1xx
```
But the shipped tokens have moved on: `index.html:12` → `style.css?v=hx1b397`, `index.html:766` → `app.js?v=hx1b388` (both `hx1b3xx`, **outside** the asserted range). The check passes today only because `core.js?v=hx1b112` still happens to match.

**Blast radius.** The guard that is supposed to guarantee a writer never receives a stale SPA is now vacuous for the one asset that carries all the behaviour. A stale `app.js` in a browser cache becomes possible and undetected.
**Confidence:** ✅ executed + code-verified.

**Closed.** Widening the regex would have fixed the symptom; the cause is that a token nobody can be forced to bump is not a guarantee. `webapp_server._stamp_asset_versions` now rewrites every `?v=` in the served document to the asset's own content hash (`_asset_version`, sha256[:10]), so **editing a file invalidates its URL with no human step** — no build step, no discipline. Both guards now assert the token equals a hash computed independently from the bytes the server actually sends: `tests/test_asset_cache_bust.py` (5 checks, no browser, runs in CI) and the rewritten step 0 of `e2e_browser_spark_wall.py`. Mutation-verified: making the stamping a no-op turns the pytest guard red and the browser guard's four asset checks red — with the failure output being the exact pre-fix tokens (`hx1b397`, `ht4`, `hx1b114`, `hx1b390`). `Cache-Control: no-cache` remains the primary mechanism; this is the belt to that braces.

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

### REL-M1 (MEDIUM) — scratch files are tracked at repo root — **CLOSED, and it hid two real defects**
`_gen_wf.py`, `_wf_gen.py`, `_r2_a11y_guard.py`, `_r3_palette_probe.py`, `_p12_junit.xml` are all `git ls-files`-tracked, and the CI `lint` job runs `ruff check .` over the whole tree. ✅ executed.

**Root cause (found while fixing):** `.gitignore` already *intended* to ignore root scratch — it enumerated `/_*.png`, `/_*.log`, `/_*.json`, `/_*.txt` and had never been given `/_*.py` or `/_*.xml`. The list fell behind the shapes actually used. Fixed with one extension-agnostic rule, `/_*`; the five are untracked; `tests/test_repo_hygiene.py` holds it (3 checks, mutation-verified).

**Two of the five were not clutter — they were broken guards, and neither could be found by reading them:**

| File | Defect |
|---|---|
| `_r2_a11y_guard.py` | Called a *"permanent gate"* by `docs/design/R2_PRIMITIVES_SPEC.md`, but **nothing ran it** (not CI, not pytest, not the browser gate) **and it could not fail**. Its third compensation branch read `if re.search(re.escape(base), css) and ":focus-within" in css:` — but `base` IS the rule's own selector, so the first conjunct is always true and the branch collapses to `":focus-within" in css`, true because the sheet contains 13 of them. Executed proof: injecting `.zz-injected-bare-suppressor { outline: none; }` still printed `clean — 18 outline:none sites, all compensated/whitelisted`. |
| `_r3_palette_probe.py` | Nothing ran it (not named `e2e_browser_*.py`, so the gate never discovered it), and it **crashed rather than failed**: it filtered on `"script"`, which in a project-less studio matches nothing (the only such label, *"Search the script"*, is project-only by design), so `.palette-row` never rendered and `rows.first.evaluate()` raised a TimeoutError. It also hardcoded the **nocta** violet `rgb(126, 107, 255)` while `tungsten.css` — a cascade layer loading *after* `style.css` — re-pins the lamp to gold `#e8c56a`. |

Both were **promoted into the gates** rather than deleted: `tests/test_a11y_outline_guard.py` (5 checks, mutation-verified 4/4) and `tests/e2e_browser_palette_restyle.py` (11 checks, auto-discovered by the browser gate, mutation-verified 4/4).

### REL-M2 (MEDIUM) — repo bloat — **measured, and it is ONE stale branch**
**476** tracked files, of which **69 are PNGs**; `.git` is **78 MB**; 38 untracked `tmp*` directories sit at the root (gitignored via `/tmp*/`). ✅ executed.
> **Self-correction:** I initially suspected the test suite leaked these. The only code path that creates a repo-root temp dir is `tests/test_writer_memory.py:502` (`tempfile.mkdtemp(dir=os.getcwd())`), and it **does** clean up in a `finally: shutil.rmtree(...)`. So the likely cause is interrupted runs, not a systematic leak. Downgraded to hygiene.

**Follow-up measurement (2026-09-21) — the headline number was right but attributed to the wrong thing.** `.git` is now **82 MB**, and **69.24 MB of it (84%) is two blobs**:

| Blob | Size | Path |
|---|---|---|
| `46fce9b0…` | **36.61 MB** | `.freebuff/desktop-v2.db` |
| `edc5d3a4…` | **32.63 MB** | `.freebuff/desktop-v2.db-wal` |

`.freebuff/` is runtime data and **is** gitignored now — but it was committed before that rule existed (`7aaaafa`, `34b3087`). Crucially, **it is not on `main` at all** (`git rev-list --objects main | grep .freebuff` → 0). It is reachable **only** from `refs/remotes/origin/legacy/pre-recovery`, and that branch **still exists on the remote** (`4f8d120`).

So the 69 MB is not history debt on the project's own line — it is one dead branch. The 69 PNGs (13.94 MB in the working tree) are **intentional** evidence, documented in `.gitignore` itself, and untracking them would not shrink `.git` anyway since history retains them. The 22 local `refs/cline/checkpoints/*` refs hold 1687 objects but **no large blobs**.

**Recommended (owner decision — it deletes a remote branch):**
`git push origin --delete legacy/pre-recovery` → `git update-ref -d refs/remotes/origin/legacy/pre-recovery` → `git reflog expire --expire=now --all && git gc --prune=now`. Reclaims ~69 MB, leaves `main`'s history untouched (no force-push, no rewritten commits). Deliberately **not executed**: it destroys a shared branch and is irreversible for those objects.

### REL-M3 (MEDIUM) — the CI browser gate is narrower than "~460 checks green" implies
`tests/run_browser_suites.py` excludes **4** suites, loudly:
- **Skipped unless `E2E_BASE` is set** (`REQUIRES_LIVE_STUDIO`): `gun_pen_audit`, `design_session`.
- **Known-broken** (`KNOWN_BROKEN`): `preview_next` ("crashes — `bounding_box()` is None for `[data-lab-composer-input]`"), `preview_redesigns` ("crashes — `page.evaluate` hits a null element").

So the 2 known-broken suites are dead coverage today, and the 2 live-only suites never run in CI. ✅ executed.
*(Credit: the harness prints all four on every run — the repo is honest about this. The defect is the coverage gap, not concealment.)*

> **Superseded 2026-09-21 (pass 9).** Both known-broken suites are **repaired**, and `KNOWN_BROKEN` is
> now **empty** — the gate runs **33 suites: 31 pass, 0 fail, 2 skip, 0 known-broken**, **660 checks**
> (was 29 / 0 / 2 / **2** at 533). The word *"crashes"* understated the damage in both cases: one died
> on its **second of six worlds**, so the crash aborted the run and **four worlds were never exercised
> at all** (14 checks reached → 92); the other was not "one bug" but a **wholly dead contract** — it
> walked `welcome → desk → cowrite → feedback` via `.edge-tab` / `.spine-tab` / `.pane-pop`, and **zero
> of those selectors exist in any of the six worlds** any more, so it was rewritten around invariants
> that survive a redesign (35 checks). Repairing them surfaced **four real defects**, all fixed: the
> desk's composer bound to the landing thread (or left unwired) by document-order selectors; the desk's
> findings verbs wired by **one of six** worlds, leaving dismiss/locate/discuss inert in the other five;
> the Workbench button sitting under the review bar in three worlds; and a gallery script that died on
> `getElementById('viewbar')` because the markup carried only a *class*, killing the view switcher,
> the picker and the frame view. Both suites now fail with a **named check** instead of aborting.
> Mutation-verified 5/5. The 2 live-only suites remain the only exclusions, and they need a studio at
> `E2E_BASE`. Full detail: `docs/audit/FIX_TRACKER.md` §pass 9.

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

> **✅ CLOSED 2026-09-21 (pass 3) — all four are now real assertions, and each was mutation-verified.**
> A vacuous check is worse than no check: it inflates the count *and* silently retires the
> guarantee. Each was rewritten to test the behaviour its name claims, with the precondition
> folded in so the guard cannot go hollow again:
> - `ideas.py` — was `count("rain courier") == 0 or True` (and the literal was the *wrong
>   project's* title). Now reads the page's real auto-title from `#project-title` and asserts
>   the reply does not contain it, **and** that the title actually grew past `"Untitled idea"` —
>   so if auto-title regresses, the check fails instead of passing for the wrong reason.
> - `ideas_v3.py` — was `"Sameer co-writer" in page.content() or True`. Now asserts the
>   summon's observable effect: `#room-drawer` carries `.open` (nothing had summoned before
>   this point, so the assertion has teeth).
> - `phase6_evidence.py` ×2 — were `count() >= 0`. The setup/payoff check now asserts
>   **agreement with the report** (ledger present → section must render; absent → must stay
>   silent), and the dismiss check asserts the row **leaves** the queue (`after == before - 1`)
>   instead of merely that a count is non-negative.
>
> **Mutation-verified, 4/4 caught:** title never grows → red (`title='Untitled idea'`); summon
> does not open the drawer → red (`room-drawer class='drawer'`); Setup/Payoff section never
> renders → red (`report.setup_payoff=True sections=0`); dismiss is a no-op → red
> (`before=8 after=8`). Every mutated file restored byte-identical.
> **Honest check count: 476 total, and now all 476 are failable** (the four were converted 1:1,
> so the total did not move — only its meaning did). The two in `gun_pen_audit` are **located
> and still open** — see below; they were deliberately *not* edited because that suite needs a
> live studio against a real `llama-server` and cannot be executed here, and an unverified test
> edit is exactly the failure mode this section is about.
>
> **⚠️ SUPERSEDED (pass 5, 2026-09-21) — both numbers in that sentence were wrong.** The gate now
> runs **28 suites / 522 checks**, not 25 / 476 (three suites entered the gate after this report).
> And "all 476 are failable" is false: a full sweep of every suite found **22 vacuous checks**, of
> which one was genuinely unbacked (now fixed) and **21 remain** — 9 backed by a throwing call or a
> branch condition, 6 diagnostic dumps whose payload is the check's *detail* string, 3 conditional
> on a timing window or on nothing happening, and 3 in the gate-excluded `gun_pen_audit`. Measured
> composition: **504 failable of 522**. The property this section was actually chasing — a check
> that is unbacked *and* cannot fail — is now **zero** in every suite the gate runs. See
> `FIX_TRACKER.md` §T3b and §"The check count, honestly".
>
> **✅ FOUND WHILE FIXING THE FOUR — this section's own count was an undercount.**
> Sweeping for the same shape turned up **fourteen** hardcoded-`True` conditions
> (`check(name, True)`) across five suites, which the original T1–T11 inventory did not
> count. They are **not all the same defect**, and the difference decides what to do:
> - **10 are step markers** sitting immediately after a *throwing* call
>   (`expect(...).to_be_visible()` / `wait_for_selector(...)`). The guarantee **is** enforced —
>   by the throwing call — so these cannot hide a regression; the check is a redundant
>   count-inflater. Two of them (`phase8`, `phase14`) are additionally conditional on
>   `running_seen`, i.e. the demo model may finish before the observation window opens.
>   **Deliberately left as-is:** converting a marker into a re-read of the DOM would introduce
>   a *new* flake risk (the element can re-render between the wait and the check) for no added
>   assurance. The latent trap is recorded: if the preceding `wait_for_selector` is ever
>   deleted, the marker silently becomes the only guard and it is vacuous.
> - **2 were genuinely unbacked, and are now fixed:**
>   - `e2e_browser_selection_translate.py` — *"translation adds no new chat turns"* was
>     `check(name, True, f"{msgs} assistant msgs")`: it computed the count, printed it in the
>     detail, and asserted **nothing**. The comparison was simply never written. Now captures
>     the count before the translate action and asserts equality. **Mutation-verified:** making
>     translation append a turn → red (`before=1 after=2`).
>   - `e2e_browser_phase7_chat_lenses.py` — *"reopen re-adopts the SAMEER conversation"* was
>     `check(name, True)` with the comment *"whichever lens, it adopts"*, i.e. the author named a
>     contract the app does not promise. The real contract is asserted six lines below
>     (`adopted_any` — the reopened lens is never empty), so the check was **deleted rather than
>     converted**, which is the honest outcome: the count drops by one and the coverage does not.
>
> **✅ Also found and fixed — the failure that exposed it.** `library_delete` failed the 32-suite
> gate with `wait_for_selector("#library-list .empty-hint")` timing out, then passed **2/2
> standalone** — a flake, not a regression (no production code was touched in this pass). It
> exposed the fifth vacuous check: the real assertion was the *wait*, and the check behind it was
> `check(name, True)`. Rewritten as a bounded poll plus a real assertion, which fixes both halves:
> a slow re-render now yields a **clean FAIL** (`empty_hints=0 library_rows=2`) instead of an
> opaque crash, and the ghost-entry guarantee is actually asserted. **Mutation-verified** by
> dropping `loadLibrary()` from `deleteProjectFlow`.


**⚠️ Reported, not independently re-executed by me** — the sharper claims, which the fix plan should assume are true until checked:
- **Source-text assertions instead of behaviour.** ~8 test files, including `tests/test_production_readiness.py` — the very suite whose "21/21" closed the previous audit — are said to assert on the *text of the source file* rather than on runtime behaviour. If so, they prove a string exists, not that a mechanism works. **This is the highest-value item to verify before trusting the readiness suite.**
- **`retry_permission` re-scribe.** The `_is_transient_lock_error` helper is now dead code after the retry-every-`PermissionError` decision, and a test class still carries the name of the behaviour it no longer checks — a test describing a contract that has since changed.
- **HTTP reach is thin.** Only a small minority of tests appear to drive a real Flask test client; ~85 routes exist. `screenplay_cowriter/server.py` (8 documented routes) is reported to have **zero** tests.
- **Silent skips.** Two triage tests reportedly skip rather than fail, hiding their own absence.

> **✅ T2 VERIFIED 2026-09-21 (pass 3) — the claim is true in form but materially overstated, and the one genuinely hollow check is now behavioural.**
> I read `tests/test_production_readiness.py` (431 lines) in full and classified every source-text
> assertion in it. They are **not** one thing:
> - **Legitimate structural / convention guards** that *cannot* be behavioural: asserting the
>   **absence** of a dangerous pattern (`webapp_demo.py` has no live `app.run(host="0.0.0.0")`),
>   the absence of a raw `open("premise.json", "w")`, a CSS container-query contract, and a
>   duplication guard ("there is ONE `inFindingFilter` predicate"). You cannot exercise a *non-existent*
>   call, and a CSS `@container` rule has no runtime to assert against.
> - **Behavioural already, contrary to the claim**: `TestAtomicWrites` does not read source — it
>   patches `jsonio.atomic_write_json` and asserts the real code path **called** it.
> - **Source-side companions** to real browser checks, and they say so in their own docstrings
>   (`TestManuscriptMarginContract`: *"These are the source contracts behind the live geometry
>   checks in e2e_browser_phase13_legacy_cleanup.py"*). The behavioural counterpart exists.
> - **One genuinely hollow check** — `TestDemoHonesty` regexed `demo_model.py` for `"issue": "…"`
>   literals, which proves a label string exists in a file, **not** that the model emits it.
>   **Now behavioural:** it drives the model's own dispatch (`_decide_reply`, the same function
>   the demo server's `/v1/chat/completions` calls) with the four trigger phrases the analyzer
>   actually sends (`screenplay_analyzer/prompts.py`, confirmed) and asserts every emitted finding
>   is labelled and correctly categorised. One test became four.
>   **Mutation-verified, 4/4:** stripping the whole label from the dialogue / genre / theme pass →
>   red **one case each** (proving it is per-pass, not aggregate); miscategorising the genre pass → red.
>   *An honest note on the first attempt:* my initial mutation dropped only the `[demo]` tag and the
>   check still passed — because the label contract is an **OR** (`[demo]` **or** "demo model"), and
>   the sentence still carried "demo model". That was the mutation being wrong, not the test; the
>   contract is "labelled somehow", and stripping one of two tokens is not a violation.
>
> **Revised verdict:** the unit suite's assurance is **not** "hollow-core". Its source-text
> assertions are mostly structural guards of the only kind possible, several are explicitly paired
> with behavioural browser checks, and the single hollow instance is now behavioural and
> mutation-verified. The two "silent skips" and the thin HTTP reach remain **unverified** and stay
> on the open list as the honest remainder of T2.

> **✅ T2b ADJUDICATED 2026-09-21 (pass 4) — both remaining claims are now measured. One is disproven, the other is half-true and its true half is closed.**
> **"Two triage tests skip rather than fail, hiding their own absence" → DISPROVEN.** Measured
> with `-rs`: the only 3 skips in the whole suite come from **one** site,
> `test_store_fault_injection.py:489`, and they are deliberate — a store that is not
> load-modify-write structurally cannot clobber what it never read. **Zero triage tests skip.**
> The three triage guards were nonetheless a **latent trap** (`pytest.skip` on "the analysis
> produced no findings"), and that is precisely the signature of the R1 bug — a wheel with zero
> craft rules, hence empty reports. A silent skip would have hidden that class of regression as
> "not run". All three now `assert`; **mutation-verified 3/3** (each fails loudly, none SKIPs).
> `pyproject.toml` also gained `addopts = "-rs"` so a skip is never a bare count again.
> **"Only a minority of ~85 routes are driven; `screenplay_cowriter/server.py` has zero tests"
> → HALF FALSE, HALF TRUE.** The webapp is **not** thin: 71 distinct routes, **64 referenced by
> tests (90%)**. The cowriter's standalone server, however, genuinely has **zero** coverage —
> nothing in the repo imports it but its own docstring.
> **Self-correction worth recording:** the route-reach sweep was wrong in *both* directions. It
> flagged `/beatboard/reset` as unreached when `test_beatboard.py::test_reset_endpoint` drives it
> (the path is composed as `f"{base}/reset"`), and it credited the cowriter server with the
> webapp's `/api/…/chat/sessions` paths. It was wrong in the *optimistic* direction for exactly
> the module the audit was right about.
> **Closed:** new `tests/test_cowriter_server.py` (**20 tests**) drives all 7 routes through the
> Flask test client, the two model-dependent ones against the repo's shared mock llama-server.
> **Mutation-verified 6/6.** *Honest note:* the first 502 mutation deleted the `except` clause,
> leaving a dangling `try` — a SyntaxError, so pytest reported a **collection error** (rc=4) that
> my harness mis-scored as "caught". Redone as `502 → 500` it fails properly (`assert 500 == 502`).


**Verdict (mine, calibrated):** the browser gate is **real** — 472 failable checks across 25 suites, and I watched them pass against the real SPA. The *unit* suite is **partial**: 1419 green is verified as green, but a meaningful slice of it is reported to assert on source text rather than behaviour, so treat its assurance value as **partial, with a hollow core** until the source-text assertions are converted to behavioural ones. This does **not** change the verdicts in §0 — the CRITICAL findings were reproduced by execution, not by tests.

*Superseded 2026-09-21 (pass 3): the "hollow core" wording above was based on a claim I had not
checked. Having checked it, the accurate statement is in the T2 block directly above — most
source-text assertions are structural guards of the only kind available, one was genuinely hollow
and is now behavioural + mutation-verified. The original sentence is left standing so the
correction is visible rather than quietly edited.*

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

## 8. Recommended sequence — and where it stands

| # | Action | Why first | Status |
|---|---|---|---|
| 1 | **Fix the XSS** — one `escapeHtml()` at every interpolating sink, then a browser check that a `<script>`-bearing finding renders inert | It is the root of the only CRITICAL chain; nothing else security-wise matters until it is closed | ✅ **done** `e3b283f` — `tests/e2e_browser_xss_inert.py` (21 checks) + a strict `script-src 'self'` CSP |
| 2 | **Fix wheel packaging** — `package-data` / `MANIFEST.in` + a packaging test asserting ≥26 rule files and `app.js` in the wheel | Converts a broken `pip install` into a real one; also correct the §7 "C3 DONE ✅" record | ✅ **done** `e3b283f` — 163 files / 1.3 MB, 263 rules, `GET /` 200; mutation-verified |
| 3 | **Restrict `/api/config` `server_url` to loopback** by default | Removes the exfiltration destination; closes the chain's second half | ✅ **done** `725e296` — one predicate (`net_guard`), six entry points, process-level opt-in only |
| 4 | **Close cross-process write safety** — unique temp name + `fsync`; a cross-process lock or a documented single-writer rule | Protects `working.json`, the only copy of the writer's edits | ✅ **done** `b60fc45` — OS byte-range lock + unique temp + `fsync`; `tests/test_store_concurrency.py` spawns real processes |
| 5 | **Fix the notes/stash lost update** — hold `lock_for` across load-modify-write (mirror `ideas.py`) | Silent data loss on ordinary actions | ✅ **done** `b60fc45` — plus `revision`'s four cycles, which had the same shape |
| 6 | **Fix the finding-id hash divergence** (`charCodeAt` → code points, or server-authoritative) | Silent loss of the writer's marks | ✅ **done** `17f0757` — one line; ids that already agreed are unchanged |
| 7 | **Fix the cache-bust guard** to cover `app.js` | Restores the stale-SPA guarantee | ✅ **done** — tokens are now derived from content, so there is nothing left to bump |
| 8 | **Push; add LICENSE + CHANGELOG; untrack the 5 root scratch files** | Release hygiene; unblocks everything downstream | 🟡 **partly** — everything through #7 is pushed; LICENSE/CHANGELOG (R6) and root scratch (R10) are open, and both are owner calls |

### Pass 2 (2026-09-21) — the store-contract leftovers

| ID | Action | Status |
|---|---|---|
| **BE-M1** | `revision._load_json_list` collapsed a damaged `edits.redo.json` into `[]` | ✅ **done** — `load_json_store` + shape check; MISSING → `[]`, DAMAGED → `StoreUnreadable` (503). The executed pre-fix symptom was `400 {"error":"Nothing to redo."}` about a stack sitting on disk |
| **BE-M2** | `revision.edits_log` read raw → bare `JSONDecodeError` → **400 "bad request"** for a damaged disk | ✅ **done** — same reader; now 503 + `unreadable: true` |
| **BE-M1b** | Undo/redo mutated the working copy before discovering the other store was damaged | ✅ **done** — both pre-flight the other store first, so damage *declines* the operation instead of consuming it |
| **R7** | CI ran `pip install ruff` unpinned | ✅ **done** — `ruff==0.16.8` in `ci.yml` + both extras, guarded by a test asserting all three agree. The **lockfile** half is an owner decision |
| **BE-M3** | Undo/redo read-modify-write without holding `lock_for` across the cycle | 🔵 **proven, deliberately NOT fixed** — 3 real children: two read `len=7`, both wrote `len=6`. The fix needs two locks at once (forbidden) or a CAS loop. Evidence in `FIX_TRACKER.md` |

**Guards added this pass:** 7 in `tests/test_undo_redo.py`, 1 `StoreCase` in
`tests/test_store_fault_injection.py` (flipped `silent` → `guarded`), 1 in
`tests/test_production_readiness.py`. **Mutation-verified: 6 mutations, 6 caught**
(4 for the store contract, 2 for the ruff pin).

**Gates after pass 2:** pytest **1520 passed / 3 skipped / 0 failed**, ruff clean,
`node --test` **16/16**. Browser gate unchanged (32 suites: 28 pass, 0 fail, 2
skip, 2 known-broken) — no frontend file was touched.

**Closed beyond the original list:** BE-H4 (a *transient* read error reported as permanent damage) was found while fault-injecting #4, and BE-M1/BE-M2 were the last two open instances of the A2/A3 shape.

**Still open at the time of writing, and none of it destructive or exploitable:** R10–R14 (repo hygiene: tracked scratch, 69 PNGs, 78 MB `.git` from 22 cline checkpoint refs) and **T1e** (the 21 remaining vacuous browser checks). **Both are now closed** — see the two notes that follow and the tracker's open-items table.

> **Superseded 2026-09-21 (pass 10). T1e is CLOSED.** All 21 are fixed and mutation-verified
> **6/6**, and the sweep that found them now returns **0**. The conversions assert the half of
> each check's *name* that the throwing wait never covered (the editor is blank; the scene page
> has rendered text; the modal is *armed*; the drawer is open; the chip is *positioned*; the
> bubble echoes the sent text; the ghosted mark's colour is not `--danger`). The gate's browser
> total went **660 → 650** — **down**, because 11 checks that asserted nothing are deleted and 9
> that asserted nothing became checks that can fail. Two more crash-shaped failure modes were
> found by the mutations and fixed. Separately, the gate surfaced an **intermittent
> `library_delete` failure** (not caused by this pass) whose two candidate causes — a 5 s poll
> budget, or a `shutil.rmtree(..., ignore_errors=False)` returning 500 on Windows `WinError 32`
> — are now distinguishable in the check's own detail; the `rmtree` retry is a production change
> left **open** rather than shipped unverified. See the tracker's pass-10 section and
> open-items table.

> **Superseded 2026-09-21 (pass 12). The `library_delete` defect is CLOSED — and it was a real
> defect, not a slow poll.** The pass-10 note left the `rmtree` retry open rather than ship it
> unverified, which was the right call at the time. It is now fixed and mutation-verified **4/4**,
> because the mechanism turned out to be **deterministically reproducible** after all: hold one
> `open()` on one file inside the tree and `shutil.rmtree` raises `PermissionError` (errno=13,
> `winerror=32`) — and, crucially, it does **not** fail cleanly. `rmtree` deletes as it walks, so
> the measured result was `['project.json']` remaining while `parsed.json` was gone: the shelf
> goes on listing the script while the writer's library has silently dropped it. That is exactly
> the observed symptom (the row survives, so the disk never "empties"). Both `rmtree` sites —
> `delete_project`, and `IdeaStore.delete`, which the original item never named — now run inside
> `jsonio.retry_permission`, the project's ONE bounded retry for this race, and answer with a clear
> JSON error instead of a raw 500. **R10–R14 are closed as well** (pass 8 and pass 11): the stale
> `legacy/pre-recovery` remote branch was deleted (`.git` 83M → 22M) and the 25 orphaned
> `preview-redesigns/shots/` PNGs were untracked. **Nothing this report opened is left open** —
> what remains is owner decisions (licensing, the dock-density and idea-room design passes, the
> `app.js` split and hash router, two prompt-budget defaults), not defects.

**Closed in pass 7 (the three owner decisions):** **R6** — decided **private**, so the artifact is a proprietary `LICENSE` (no rights granted, scoped so it does not appear to cover third-party dependencies) plus a `CHANGELOG.md`; both in `MANIFEST.in`. **R7b** — decided **lock it**: `requirements.lock.txt` pins the whole declared closure (32 packages) and CI installs with it as a **constraints** file (`-c`), which is the correct shape here because the lock is derived on Windows/3.13 while CI runs ubuntu-24.04/3.12. Five guards, **mutation-verified 7/7**, including the anti-decoration check that CI actually applies it. **BE-M3** — decided **not required**; recorded as accepted-as-is with the fix shape (CAS retry loop, never two `lock_for` locks) so it is not re-litigated. Also fixed, while doing R7b, **three stale doc claims** this report's §4 had flagged as drifting (`ARCHITECTURE.md`, `DEVELOPMENT.md`, `NOTES.md` all asserted "there is no `pyproject.toml`").

**Closed in pass 3:** **T1** — all four vacuous browser checks rewritten as real assertions and mutation-verified 4/4; the honest browser-check count is now **476 total, all failable** (was 472 failable of 476).

**Closed in pass 5:** **R9** — the "125-min worst case" was an unverified figure and unreachable by construction (a job-level `timeout-minutes` is a hard cap; measured runtime is **5.05 min for 28 suites** against a 45-min budget). The real hole — nothing guarded the *declaration*, so a job without one inherits GitHub's **360-minute** default — is now a test. **T2c** — route coverage is now a **gate**, not a hand sweep: `test_route_coverage.py` requires every route in `app.url_map` to be exercised (measured by a `before_request` recorder, not a source grep) or declared with a reason, and rejects stale declarations. It found 7 blind spots on its first run; `test_route_smoke.py` now drives 6 of them.

**Closed in pass 6:** **T3b** — all 33 browser suites audited for the `library_delete` throwing-wait shape. Of 22 vacuous checks found, exactly **one was genuinely unbacked** (`phase14:87`, "the structure card saves beside the idea", backed by nothing but a 600 ms sleep) and now asserts the button's own `"Saved ✓"` confirmation — mutation-verified. The other 21 are classified by class in the tracker rather than churned. **Two corrections to this report's own numbers came out of it:** the gate runs **28 suites / 522 checks** (not 25 / 476), and "all 476 failable" is false — the measured composition is **504 failable of 522**, with the property this section was chasing (unbacked *and* unfailable) now at **zero** in every gate suite.

**Live tracker:** `docs/audit/FIX_TRACKER.md` — kept current so the state of play is readable without re-deriving it from `git log`.

**Explicitly out of scope / owner decisions:** the licensing choice; the dock-density and idea-room design passes; the `app.js` module split and hash router; the two prompt-budget defaults (documented in `.env.example`, currently left at their working values). *The two known-broken preview suites were on this list and have since been **repaired** (pass 9) — see the REL-M3 superseding note above.*

---

*Audit authored 2026-09-21 from a read-only rescan. No product file was created, modified, or deleted. All build/test artifacts were written under the gitignored `.workbuddy-ai/` directory.*
