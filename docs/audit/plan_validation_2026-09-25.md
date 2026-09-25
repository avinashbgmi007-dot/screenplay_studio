# Validation — `ardent-oasis-swan.md` (third-party remediation plan)

**Validated:** 2026-09-25 · **Against:** branch `qoder/update`, HEAD `eccbdca`, working tree at the same
19-modified / 17-untracked state the plan describes.
**Method:** every file:line anchor read in the owning source; two independent verification agents
(live HTTP replay, concurrent-process race reproduction); a live chromium run against a real analysed
project — rendered-pixel contrast sampling in both registers, plus a real Escape-cascade focus probe;
full `pytest` and full browser fleet at this revision. **No product code was modified.** One file added
(this report); all probes ran under `.workbuddy-ai/scratch/`.

---

## 1. Verdict

**The plan is legitimate.** It is not fabricated, not stale, and not padded. Its snapshot is accurate
to the line, its anchors are unusually precise, its two highest-impact findings (P0-1, P1-3) are
**correct and I reproduced both**, and its four retractions are all well-founded.

**But it is not clean.** Four claims are wrong or unproven, one of them *backwards*, and it misses
several real doc-rot items. It also under-verified `pytest` by its own stated standard.

| Verdict | Count | Notes |
|---|---|---|
| Confirmed — anchor exact or substance proven | 22 | incl. both P0s and all of P1 |
| Confirmed in substance, imprecise in detail | 4 | line off-by-one, mechanism overstated |
| **Wrong or not reproducible** | **3** | §2.2 inverted · "1.67:1 night" · the red gate |
| Partly wrong — downgraded, not deleted | 1 | §8 `f` (corrected in §4.3) |
| Retractions | 4 / 4 correct | all four verified |

> **Amended 2026-09-25** after `fierce-vault-stoat.md`: §8 `f` moved out of "wrong" (the *string* does match
> the shipped palette; only the *behaviour* differs — see §4.3), and one further claim of this document —
> that `test_undo_redo_lock_race.py` asserts "never … `working.json` text" — was itself **wrong** and is
> corrected in §3.

**The single most important thing the plan says, and it is right:** the fixes it audits are
**uncommitted**, and the pushed branch is the pre-fix tree. Verified: `origin/qoder/update` = `eccbdca`
(`git ls-remote`), HEAD contains **zero** occurrences of `_host_header_is_local`, `syncRoute`,
`_empty_kb_message`, `test-windows`, `logsetup`, and HEAD's `_reject_cross_origin_writes`
(`webapp_server.py:201-203`) still early-returns for `GET`, so at HEAD reads carry no token and no Host
check exists. The exposure is real on the pushed branch.

---

## 2. Gate status — my measurement contradicts the plan's

| Surface | Plan says | I measured, same revision |
|---|---|---|
| Browser fleet | 48 suites; **46 passed / 1 failed** / 1 skipped; `deep_links` fails in-fleet | **48 suites: 47 passed / 0 failed / 1 skipped, 1175 checks, exit 0** — `deep_links` **passed in-fleet (24 checks)** |
| `pytest tests/` | *not run* — subsets only: 130 / 81 / 10 | **1749 passed / 3 skipped / 0 failed, 87% coverage, exit 0** |
| Documented baseline | 43 suites / 42 passed; 1669 passed | correct and correctly sourced — `NOTES.md:81-96`, **committed** (not part of the diff) |

The plan's red-gate row **did not reproduce**. `deep_links` was green in-fleet here and in two earlier
runs at this revision. Its diagnosis is still sound as *latent* fragility — `history.back()` followed by
a fixed `wait_for_timeout(1400)` (lines 114, 124) is a fixed-wait assertion whatever it does on a given
machine — so P0-2 is worth doing, but its **premise ("the gate is not green") is unconfirmed**, and the
plan's own §Verification already describes a green end state.

The plan's pytest evidence is the weakest part of the document: three subsets against a documented
"1669", never the full suite. The full suite is green, at **1749**.

---

## 3. Confirmed — the load-bearing findings

### P0-1 — uncommitted work / pushed branch still leaks · **CONFIRMED**
Branch, HEAD SHA, push state (`git ls-remote` = `eccbdca`), 19 modified files, and all five
zero-occurrence symbol checks are exact. `app.js` mtime is `2026-09-24 23:48:15`, matching the plan's
"last written 23:48 by a concurrent process" to the minute.

One precision fix: the plan says *"One `git clean -fd` deletes the fixes."* It would not. `git clean -fd`
removes only **untracked** paths — that deletes `logsetup.py` and the five new suites, but the **Host
guard lives in a modified tracked file** (`webapp_server.py`) and survives. Losing the guard needs
`git restore`/`git checkout -- .` or `git stash`. The risk is real; the command named is wrong.

### P1-3 — `working.json` has no lock of its own · **CONFIRMED, REPRODUCED**
An independent agent confirmed the code shape and then **produced the divergence**:
`save_working` (`revision.py:342-343`) writes `working.json` with no store lock held for the
load→save cycle; `undo_last_edit` writes it at `:470` while holding the **edits-log** lock; `redo_last_edit`
writes it at `:517` while holding the **redo** lock. `load_working` takes **no** lock
(`ScriptDocument.load`, `models.py:166-168`) — that is the decisive fact, and it holds.

Empirically, with barrier-synchronised workers and zero worker errors: **200/200 divergence** across two
OS processes (150-replacement edits), **200/200** on an ordinary 1-replacement edit, and **200/200 across
two threads in one process** — which matters because `app.run(..., threaded=True)`
(`webapp_server.py:4027`) makes two browser tabs sufficient. Serialised control: 0/200.

Two corrections to the plan's framing:
- *"deliberately writes outside any lock"* overstates it. `ScriptDocument.save` routes through
  `atomic_write_json`, which **does** take `lock_for(working.json)` for the write itself. The **cycle** is
  unlocked, not the write; JSON never tears. The defect is a **lost update**, not corruption. The plan's
  own P1-4 note calls this a "500 after the edit saved" — same class.
- *"two windows, or CLI + webapp — both documented"* — the CLI half is **wrong**. `cli.py` exposes only
  `run/resume/status/watch`; it has no edit/apply/undo, so it cannot be the second writer. "Two windows"
  is real and sufficient.

**Finding the plan missed:** `tests/test_undo_redo_lock_race.py` **passes** and is scoped to the wrong **axis**
— but not, as this document first claimed, to the wrong invariant.

> **CORRECTION (2026-09-25, after `fierce-vault-stoat.md`).** This section originally said the test "asserts
> the *log record* … never comparing `working.json` text to `edits.json` … its green is false assurance."
> **That is wrong for the undo leg.** `tests/test_undo_redo_lock_race.py:138-141` explicitly compares working
> text:
> ```python
> text = "\n".join(el.text for s in revision.load_working(m).scenes
>                  if s.scene_number == 2 for el in s.elements)
> assert LINE_2_NEW in text
> ```
> The accurate findings are narrower and were supplied by the revised plan:
> - the **redo** leg (`:159-163`) asserts only `redone["redone"]["scene_number"] == 1` and `e2 in ids` — **no
>   text comparison**;
> - the whole file is **single-process** (`threading.Thread` at `:106`, monkeypatched slow read at `:82-89`,
>   `:96`, `:113`), so it never exercises the cross-process OS byte-range lock that `AGENTS.md` names as the
>   failure mode.
>
> So: the file is scoped to the wrong *axis* (one process; text asserted on one of two legs), not to the wrong
> invariant. The recommendation is unchanged — extend it with a child-process leg and a text assert on the redo
> side — but the justification is the corrected one above.

### P1-4 — unlocked `clear_redo` · **CONFIRMED, REPRODUCED**
`revision.py:418-420` is a bare `exists()` + `os.remove`. Proof: while another process held
`lock_for(edits.redo.json)` for 3 s, `clear_redo` returned in **0.11 ms** and deleted the file — it
excludes nothing. Two concurrent `clear_redo` calls raised `FileNotFoundError` in **3996/20000 (20%)**
from the exists→remove TOCTOU, and undo ∥ clear_redo over 200 left the undone record in **neither** log
nor redo **49 times** — permanently unrecoverable.

### P1-5 / P1-6 / P1-7 — the SPA races · **CONFIRMED**
- `sendFvMessage` (`app.js:7413`) has **no** `sentFrom`/`samePlace` guard, and the assignment
  `state.branches[state.currentBranch] = …` is at **7455** (plan says 7456 — off by one). The M1 fix at
  `:3615-3628` is exact and genuinely not back-ported.
- The watchdog's "Keep waiting" button (`:3646-3648`) calls `attemptTurn()` with no disable and no
  re-entry guard in `attemptTurn` (`:3582`); the dialog is not removed, so N clicks = N turns.
- The M2 stale-flight guard is at **`:2193`** — exact — and the mechanism is confirmed: `openProject`
  sets `state.currentProject = name` at **`:2116`**, *before* the await, so a losing flight paints the
  wrong title (`:2152`), premise (`:2139`) and session (`:2177-2186`) before the guard can stop it.

### P2-8 — token after restart · **CONFIRMED at HTTP level**
Live: stale token → **403 `{"error":"missing or invalid capability token"}`** on both `POST /api/sample`
and `DELETE /api/projects/<name>`; a fresh `GET /` re-mints a working token; `GET /` is
`Cache-Control: no-cache`. And `api()` (`app.js:73-95`) has no 403 branch at all — it throws, and callers
surface `e.message` through `showError(...)`, so the writer does see the internal string. Confirmed.

### P3-9 — unescaped SVG interpolation · **CONFIRMED, anchors exact**
`:4116` and `:4140` are the two `body.innerHTML = svg` sinks; `s.page_start` is interpolated raw at
`:4108`, `r.scene_number` raw at `:4135` (into `data-scene=`) and `:4136`.

### P3-10 — XSS guard scope · **CONFIRMED, with an arithmetic error**
The suite is scoped to the evidence dock (`openDock('evidence')`) — confirmed. But the plan's own
breakdown *"19 content sinks (12 static, 4 escaped, 2 unescaped)"* **sums to 18, not 19**. My census of
`app.js`: 65 `innerHTML =` assignments, of which 18 assign non-empty content (the rest are `= ""` clears).
The connection card at `:684` **is** escaped (`escapeHtml` at `:685-687`), consistent with the "4 escaped"
bucket. The plan's *substance* (the guard probes far too little) is right; its count is not.

### P4-11 / P4-12 / P4-13 — coverage holes · **CONFIRMED**
Largest fixture is literally `tests/fixtures/Pain_FD_4_scenes.pdf`. `beatboard/reset` and `reparse` have
**0** browser call sites; `rename` matches only a comment; `writer-memory` has **0** browser call sites
(only `test_webapp_api.py`). Every server `terminate()`/`kill()` in the fleet is **teardown**, never
mid-session. Dialogs auto-accepted at `e2e_browser_common.py:497` — exact. `phase8_lifecycle.py:220` is a
conditional `else` branch — exact. The three vacuous `check(name, True)` are at **`799`, `844`, `901`** —
exact. `test-browser` is ubuntu-24.04 (`ci.yml:77-91`), `test-windows` is `:108-131`, floor `fail_under=85`
vs measured 87.

### P5-16 / P5-18 / P5-19 — confirmed
`renderManuscript` is `:5052-5126`; the debounce is **160 ms** at `:9220`; the per-note scan of every line
is `:5113-5126`. `MAX_CONTENT_LENGTH = 256 * 1024 * 1024` at `:477` — exact. The labs **are** packaged
surface (`pyproject.toml:60` `webapp/**/*.html` recursive + `MANIFEST.in:17` recursive-include), and the
`/<path:filename>` route (`:544-555`) hardens **only** `index.html`, with a comment at `:550-552` saying the
`preview-*` labs are "deliberately left alone" — while the cookie (`:180-182`) goes to any 200 `text/html`.
Confirmed.

### Retractions — 4 / 4 correct
- *"hard reload needed"* — `GET /` is `Cache-Control: no-cache` (measured live). ✓
- *"nests two store locks"* — undo/redo take them **sequentially** (`:451` then `:474`; `:501` then `:519`). ✓
- *"ruler tick sub-24px"* — `style.css:507` is exactly `::before { content:""; position:absolute; inset:-9px }`. ✓
- *"42/0 fleet is current"* — false against this tree. ✓

---

## 4. Wrong or not reproducible

### 4.1 §2.2 "fonts are bundled" — **the claim is backwards**
The plan lists §2.2 under *"Docs that mislead"* for saying fonts are bundled. **They are bundled.**
`screenplay_studio/webapp/fonts/` holds **14 `.woff2`** including `InstrumentSerif-*` and `DMSans-*`, and
`style.css` carries **18 `@font-face`** declarations with `InstrumentSerif` at `:116`/`:124` and `DMSans` at
`:132`/`:140`.

The actual rot in §2.2 is the opposite: its **"⚠ Known gap"** (lines 133-137) claims Instrument Serif and
DM Sans are "**not bundled** — there is no `@font-face` for them and no `.woff2` in `webapp/fonts/`". That
is false. The plan inverted the direction and pointed the fix at the wrong sentence.

### 4.2 "night scene-severity dot computed **1.67:1**" — **wrong, but it points at a real defect**
The plan leads its gate table with this number as proof the documented "worst 4.81:1" baseline is
optimistic. I measured the **rendered pixel** on a live studio (demo analysis, real project, both
registers) — backdrop sampled outside each mark, mark sampled as the interior pixel furthest from it:

| target | night | dawn |
|---|---|---|
| scene-index medium (`.scene-index-dots .dot.medium`) | 7.47 | 4.85 |
| dock medium (`.sev-dot.medium`) | 8.47 | 4.71 |
| **dock low (`.sev-dot.low`)** | 5.66 | **2.41** |

Worst = **2.41:1, dawn register, dock low-severity dot** — below the 3:1 non-text threshold. So the plan's
*substance* **holds** (the documented 4.81:1 baseline does miss a sub-AA severity surface), but both of its
specifics are wrong: the register is **dawn**, not night — and `body.dawn` is explicitly the **light** theme
(`style.css:379` "Nocta dawn — daylight glass"; `:439` "dawn is a LIGHT theme") — and the value is
**2.41:1**, not 1.67:1.

**And the plan missed the actual defect, which is one line and precisely locatable.** `.sev-dot.low` is
**hardcoded** `background: #46a758` (`style.css:3150`) — it never reads `var(--ok)`. Dawn *does* fix `--ok`
(`:436` → `#14784a`, with a comment at `:434-435` recording that the old `#2eb87a` "scored 2.18 on the
#f1ede4 body"), and `tungsten.css:24` overrides `.sev-dot.high` and `.sev-dot.medium` for dawn — but **not
`.sev-dot.low`**. So the low dot paints the *night* green on dawn's light surface.

The scene-index dots do **not** have this bug, because they use the token
(`.scene-index-dots .dot.low { border: 1.5px solid var(--ok) }`, `:5350`/`:5360`) — which is exactly why the
asymmetry is invisible unless you measure both. Fix: `body.dawn .sev-dot.low { background: var(--ok); }`, or
better, drop the hardcoded hex and read the token as the scene-index dot already does.

### 4.3 §8 `f` description — **partly unsupported; downgraded, not deleted**
§8's table reads `| f | Switch to Feedback (Consultant) |` (`UI_UX_SPECIFICATION.md:582`). The app's own
shortcut palette prints the identical string (`app.js:8180`), and the handler (`:8477-8480`) does
`if (state.currentProject) openFeedbackView(); else openFeedbackRoom();`.

> **CORRECTION (2026-09-25, after `fierce-vault-stoat.md`).** This section originally concluded "§8 matches
> the shipped product; nothing in it is misleading. This item is noise." That was too strong, and the revised
> plan is right to refine it: the **string** matches, but the **behaviour** does not. In a project,
> `openFeedbackView()` (`app.js:7359-7365`) does `setRoom("cowrite")` + `openDock("evidence")` — it opens the
> Evidence dock *inside the Co-write room*; it never switches to a Feedback surface.
>
> One qualifier the revised plan omits: `app.js:7356-7358` records this as a **deliberate consolidation**
> ("the dock's Evidence lens IS the ledger … the old 3-panel `#feedback-view` was deleted in P0.1"), so the
> label is defensible for a surface that was intentionally folded. The correct disposition is therefore the
> plan's own: **downgrade to info, do not delete** — the doc describes a view switch for what is now a
> dock-open.

### 4.4 P5-14, second half — **refuted live**
*"Escape from the dock drops focus to the skip-link instead of the opener."*

Read statically this looked unlikely, and a live run settles it. With the real studio open on an analysed
project, focusing `#right-edge-affordance`, clicking it, and dispatching the real Escape cascade:

```
before        : right-edge-affordance
after open    : dock-tab-evidence        <- openDock() moves focus INTO the dock tab (:5365)
dock open     : True
after Escape  : right-edge-affordance    <- restored to the opener
restoredToOpener: True   isSkipLink: False   isBody: False
dock open after: False
```

**Focus returns to the opener. It is not the skip-link, and not `body`.** The mechanism is explicit:
`_dockFocusReturn` is captured at `app.js:5354` and restored at `:5377-5378`, and Escape routes straight
into `closeDock()` at `:8433`.

There *is* a narrower real defect in the same area, which the plan did not identify: `:5354` captures the
opener only `if (!dockIsOpen())`, so switching lenses or re-opening an already-open dock does **not**
re-capture, and Escape then returns focus to the *first* opener rather than the most recent control. And if
the opener was detached by a re-render, `document.contains()` fails and focus is not restored at all.
Neither is "drops focus to the skip-link". As stated, the claim is refuted.

*(The first half of P5-14 is exact: `index.html:401` has no `aria-live` on `#messages-scroll`, and
`:23` has no `role="status"` on `#error-banner`.)*

---

## 5. What the plan missed

1. **The real cause of the contrast defect** — `.sev-dot.low` is hardcoded `#46a758` and the dawn override
   block covers high and medium but not low, so dawn paints the *night* green on a light surface
   (measured **2.41:1**). One line; see §4.2. The plan saw a symptom, mislabelled it, and gave a wrong
   number, when the defect was locatable to a single missing selector.
2. **§12's line counts are badly stale** — the plan flags only the `?v=` line. Documented vs actual
   (worktree / HEAD): `index.html` ~770 vs **722**/723 · `app.js` ~8,530 vs **9,711**/9,420 ·
   `core.js` ~96 vs **171**/171 · `style.css` ~6,520 vs **6,251**/6,259 · `webapp_server.py` ~2,805 vs
   **4,085**/3,968. `core.js` is documented at 96 lines and is 171 — 78% wrong. Stale at HEAD too, so it
   is not a diff artefact.
3. **`test_undo_redo_lock_race.py` is scoped to the wrong axis** (§3, P1-3) — a green test whose **redo** leg
   never compares working text, running **single-process** so it cannot exercise the cross-process lock.
   *(Originally written here as "false assurance … asserts the log record, never comparing `working.json`
   text" — corrected in §3: the undo leg does compare text at `:138-141`.)*
4. **§4.4b names four functions that no longer exist** — `renderFeedbackView`, `switchFvTab`,
   `initFvDividers`, `initFvScrollSync` all return **nothing** from `app.js`, and `#feedback-view` is gone
   from `index.html`. The plan correctly flags the §4.4b ↔ `CODEBASE_MAP.md:88` contradiction but does not
   say which side wins: **CODEBASE_MAP is right, §4.4b is stale**, and §4.4b's "remains in the DOM
   dormant, unreachable — not deleted" is simply false. (`sendFvMessage` does survive, so §4.4b is only
   partly wrong.)
5. **`Set-Cookie` carries no `HttpOnly`, `Secure`, or `Max-Age`.** Relevant to P2-8: JS reads the cookie
   (`_studioToken()`), which is what makes the SPA's header path work, but it also means any script in the
   app origin can exfiltrate the write token. Worth a deliberate note rather than silence.
6. **The P1-3 fix is necessary but not sufficient.** With the plan's own "never hold two store locks at
   once" invariant, the log and the text are written in two separate critical sections, so a crash between
   them still leaves them divergent. Adding a `working.json` lock removes the *concurrent* lost update; it
   does not make the pair transactional. The plan should say so.
7. **Untracked count is 17 collapsed entries / 49 paths expanded**, not 18; and the diff is **+1591/−216**,
   not +1,587/−216 (4 lines — consistent with the plan's own note that a concurrent process was writing
   `app.js`).

---

## 6. Bottom line

**Act on it.** The P0/P1 items are the right items in the right order, and the two most consequential
claims — the uncommitted fixes with a leaking pushed branch, and the unlocked `working.json` — are both
correct and both reproduced here. P0-1 alone justifies treating the plan as real work.

**Before you cite it, fix four things:** the §2.2 font direction (it is inverted), the 1.67:1 figure
(replace it with the measured **2.41:1 in the dawn register**, and the real cause — the hardcoded
`.sev-dot.low` that dawn never overrides), the §8 `f` item (delete it), and the "gate is red" premise (it
is green in three runs — keep the fix, change the justification). The P5-14 Escape claim should also go:
it is refuted by a live focus probe. Then add the §12 line counts and the
`test_undo_redo_lock_race.py` false-assurance note, which the plan should not have missed.

**Suggested order** — unchanged from the plan, with one substitution:

1. **Commit the working tree** (P0-1), on the exact commit, after re-running the fleet. Nothing else is
   safe until this is done.
2. **P1-3** — one lock across the whole `working.json` read-modify-write, and fix
   `test_undo_redo_lock_race.py` to compare text against log, not just the log record.
3. **P1-4**, then **P1-5/6/7**, then **P2-8**.
4. **P3-9** is a two-line `escapeHtml()` fix; take it while the file is open.
5. **The dawn low dot** — one selector, measured at 2.41:1, below the 3:1 non-text floor. Cheapest real
   a11y fix in the whole list, and the plan's version of it is unusable as written.
6. Re-run the live focus probe before repeating anything about Escape and focus.
