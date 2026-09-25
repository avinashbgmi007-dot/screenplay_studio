# Validation — `fierce-vault-stoat.md` (the REVISED remediation ladder)

**Validator's position:** this document validates a plan that was written to correct an earlier plan, partly in
response to a validation I wrote. So it is a validation of a *revision*, and it includes adjudicating that
revision's criticisms of my own earlier work. Where the revision is right about me, I say so and correct my
document (§4). Where it is wrong, I show the measurement (§5).

**Method:** every `file:line` anchor printed from the owning file with `awk 'NR>=a && NR<=b'`; the full unit
suite and the full browser fleet run at this exact revision; the contrast claim re-derived arithmetically
*and* re-measured on the rendered pixel; the sink census recomputed with a parser rather than a grep.
**No product code was modified.** All probes ran under `.workbuddy-ai/scratch/`.

---

## 1. Verdict

**Legitimate, and a material improvement on its predecessor — but it carries four defective claims of its own
and one of them changes a priority ranking.**

The revision does the thing an audit revision is supposed to do: it re-derives rather than re-asserts. All
**9** of its self-retractions are correct (§3), including two I had not found (the `git clean`/`restore`
confusion, and the CLI-as-second-writer claim). Its P0/P1 spine survives line-by-line re-verification, and its
sharpest new find — that HEAD's commit message claims *"§2.2 corrected"* while touching **only `NOTES.md`** —
is exactly right and is the kind of claim only a careful reader finds (§6).

It is wrong in four places (§5). The two that matter:

1. **P3-9 is ranked as an unescaped-SVG XSS, and it is not reachable.** Both SVG sinks interpolate
   *parser-generated numbers*. The plan's own proposed verification — "seed a hostile `scene_number` through a
   `.fountain` fixture" — **cannot be built**, because a screenplay cannot set `scene_number`. This is a
   defence-in-depth hygiene item (the repo's own "escape at the render boundary" convention is genuinely
   violated), not a vulnerability, and it should not sit in P3 beside real ones.
2. **"Largest fixture is a 4-scene PDF" is false.** The largest fixture is `pain_tenglish.fountain` at **6
   scenes**; the PDF yields **0 scenes** without OCR; and the script the browser fleet actually drives is the
   **3-scene** sample. The *substance* ("the fixtures are far too small to exercise the product") is
   strengthened, not weakened — but the stated fact is wrong.

---

## 2. Fresh evidence — the plan's table vs mine

Every row re-measured at HEAD `eccbdca` + the working tree.

| Gate | The plan says | I measured | Verdict |
|---|---|---|---|
| `pytest tests/` | 1749 passed / 3 skipped / 0 failed, 2:04, exit 0 | **1749 passed / 3 skipped / 0 failed, 2:14, exit 0, 87%** (9699 stmts, 1291 missed) | ✅ exact |
| Browser fleet | 47 passed / 0 failed / 1 skipped | **48 suites: 47 passed / 0 failed / 1 skipped / 0 known-broken — 1175 checks, exit 0, 11m57s** | ✅ exact |
| Tree | +1,591/−216, 19 modified + 18 untracked | **+1591/−216, 19 modified, 18 untracked entries (50 paths expanded)** | ✅ exact |
| HEAD symbols | 0 occurrences ×5 | **0 ×6** (incl. `_reject_foreign_host`), `_empty_kb_message` = 0 in `pipeline.py` | ✅ exact |
| HEAD read leak | `_reject_cross_origin_writes` early-returns for GET at `:202` | **`:202-203` `if request.method in ("GET","HEAD","OPTIONS"): return None`**, no `before_request` Host guard | ✅ exact |
| `deep_links` in-fleet | green in two runs | **green again — `deep_links 24 passed (37s)`, 4th consecutive green** | ✅ exact |

`deep_links` passing in-fleet for the **fourth** time is the load-bearing row for the plan's P0-2 demotion. The
plan is right to demote it: a flake that will not reproduce in four runs is **latent fragility**, not a red
gate, and the plan now says exactly that.

---

## 3. The nine self-retractions — all nine verified

| # | Retraction | Evidence | Verdict |
|---|---|---|---|
| 1 | "the gate is red" | fleet green, 4th run | ✅ |
| 2 | "night dot 1.67:1" | see §5.4 — right conclusion, and my arithmetic reproduces the plan's replacement range exactly | ✅ |
| 3 | §2.2 "fonts not bundled" is the false side | `UI_UX_SPECIFICATION.md:117` correct; the false text is the callout at **`:133-137`**; **14** real `.woff2`; `@font-face` at `style.css:111/119/127/135` | ✅ exact |
| 4 | P5-14 Escape-to-skip-link | `_dockFocusReturn` captured `:5354`, restored **`:5377-5378`** behind `document.contains()`; live probe → `restoredToOpener: True, isSkipLink: False` | ✅ exact |
| 5 | §8 `f` is "noise" | string at `app.js:8180`; handler `:8477-8480`; but `openFeedbackView()` (`:7359-7365`) does `setRoom("cowrite")` + `openDock("evidence")` — see §4.2 | ✅ |
| 6 | "19 sinks" → **18 of 63** | parser census: 64 `.innerHTML =` lines, **minus 1 comment at `:7803`** = **63**; 45 clearing + **18** content-bearing | ✅ exact |
| 7 | "CLI + webapp, both documented" | `cli.py` subparsers: `run:180`, `resume:196`, `status:208`, `watch:212` — **no apply/undo** | ✅ exact |
| 8 | "`git clean -fd` deletes the fixes" | `clean` removes the 11 untracked source files (incl. `test_host_header_guard.py`); the guard itself is in **modified tracked** `webapp_server.py` and survives → needs `git restore` | ✅ exact (count wrong, §5.2) |
| 9 | line-number drift | verified individually — see §3.1 | ✅ (one residual, §5.5) |

### 3.1 The corrected anchors — all checked

| Anchor | Claimed | Actual | |
|---|---|---|---|
| `sendFvMessage` assignment | 7455 (fn at 7413) | `7455`, def `7413` | ✅ |
| `save_working` def / `doc.save` / log lock | 342 / 343 / 352 | `342` / `343` / `352` | ✅ |
| `undo_last_edit` | 435; writes working `:470` under log lock `:451-473` | def `435`; `with lock_for(log_path)` `451`, `doc.save(working_path(m))` **`470`**, `log.pop()` `472` | ✅ |
| `redo_last_edit` | 489; writes working `:517` under redo lock `:501-519` | def `489`; `lock_for(redo_path)` `501`, `doc.save(working_path(m))` **`517`** | ✅ |
| locks sequential, not nested | `:473`→`:474`, `:519`→`:520` | log lock closes `473`, redo lock opens **`474`**; redo lock closes `519`, log lock opens **`520`** | ✅ |
| `clear_redo` | 418-420 | `def` 418, `os.path.exists` 419, `os.remove` 420 | ✅ |
| `attemptTurn` / M1 guard / `keepBtn` | 3582 / 3615-3628 / 3646-3648 | `3582` / `sentFrom` 3615, `samePlace` 3620, `state.branches[sentFrom]` 3626 / `keepBtn.addEventListener` 3646 | ✅ |
| `openProject` | 2116 early set, 2193 bail, 2139/2151-2153/2167/2178-2185 paint between | `state.currentProject = name` **2116**; bail `if (state.currentProject !== name) return` **2193**; premise 2139, project bar 2151-2153, report-lang 2167, session 2178-2185 | ✅ |
| SVG sinks | `:4116` (`:4108` raw), `:4140` (`:4135-4136` raw) | `body.innerHTML = svg` **4116** with `${s.page_start}` **4108**; **4140** with `${r.scene_number}` into `data-scene=`/`<title>` **4135-4136** | ✅ |
| `_dockFocusReturn` | 5354 / 5377-5378 | `if (!dockIsOpen()) _dockFocusReturn = document.activeElement` **5354**; restore **5377-5378** | ✅ |
| `deep_links` fixed waits | `:113-114`, `:123-124`; 13 total | `history.back()` 113 + `wait_for_timeout(1400)` 114; `history.forward()` 123 + `wait_for_timeout(1400)` 124; **13** `wait_for_timeout` total | ✅ |
| `style.css` low dot | 3150 | `.sev-dot.low { background: #46a758; }` **3150** | ✅ |
| `tungsten.css` dawn | `:24` high+medium only; `--ok: #0f6b41` at `:3` | `body.dawn .sev-dot.high{background:#a03722}body.dawn .sev-dot.medium{background:#8a5a14}` **24** — **no `.low`**; `--ok:#0f6b41` **3** | ✅ |
| `Set-Cookie` | `:182`, no HttpOnly/Secure/Max-Age | `resp.set_cookie("studio_token", _API_TOKEN, samesite="Strict", path="/")` **182** | ✅ |
| `threaded=True` | `:4027` | `app.run(host="127.0.0.1", port=args.port, debug=False, threaded=True)` **4027** | ✅ |
| `atomic_write_json` lock | `jsonio.py:361` | `with _lock_for(path):` **361** | ✅ |
| `ScriptDocument.save` | `models.py:123-128` | `def save` **123** → `atomic_write_json(path, self.to_dict())` **128** | ✅ |
| packaging | `pyproject.toml:60`, `MANIFEST.in:17` | `"webapp/**/*.html"` **60**; `recursive-include screenplay_studio/webapp *.html *.js *.css *.woff2` **17** | ✅ |
| doc rot | `FIX_TRACKER.md:29-34`, `§4.4b:323-331`, `CONTEXT.md:57`/`:77`/`:110-111` | FIX_TRACKER gate table **29-34** (1614 passed, 34 suites/702 checks); §4.4b **323-331** names all four dead functions; CONTEXT "the rail lists them" **57** vs "Structure Rail — **RETIRED**" **109-111**; "Sameer (Sam)" **77** | ✅ |
| `fail_under` | 85 vs measured 87 | `pyproject.toml:124` `fail_under = 85` | ✅ |

That is a very high hit-rate on anchors that moved between revisions. It is the strongest single signal that
this revision was actually re-derived from the files.

---

## 4. Where the revision is right about my validation — and I am correcting my document

### 4.1 `test_undo_redo_lock_race.py` — **the plan is right, I was wrong**

My document said:

> "It asserts the *log record* (the H5 fix), never comparing `working.json` text to `edits.json` — so the very
> race it is named for is unguarded, and its green is false assurance."

**That is false for the undo leg.** `tests/test_undo_redo_lock_race.py:138-141`:

```python
    # and the working copy still holds that edit's text: the two stores agree
    text = "\n".join(el.text for s in revision.load_working(m).scenes
                     if s.scene_number == 2 for el in s.elements)
    assert LINE_2_NEW in text
```

It **does** compare working-copy text. The plan's correction is exact, and its replacement findings are the
right ones:

- the **redo** leg (`:159-163`) asserts only `redone["redone"]["scene_number"] == 1` and `e2 in ids` — **no
  text comparison**;
- the whole file uses `threading.Thread` (`:106`) with a monkeypatched slow read (`:82-89`, `:96`, `:113`) —
  **single process**, so it never exercises the cross-process OS byte-range lock, which is the failure mode
  `AGENTS.md` names.

So the correct statement is: *the file is scoped to the wrong **axis** (one process, and text asserted on only
one of two legs), not to the wrong invariant.* My "false assurance" framing overstated it. Corrected in
`plan_validation_2026-09-25.md`.

### 4.2 §8 `f` — **the plan's refinement is better than my rebuttal**

My document said the §8 row "matches the shipped product; nothing in it is misleading. This item is noise."
The plan replies that this is true only of the *string*, and it is right: in a project, `f` →
`openFeedbackView()` (`app.js:7359-7365`) → `setRoom("cowrite")` + `openDock("evidence")`. It does not switch
to a Feedback surface; it opens the Evidence dock inside the Co-write room.

One caveat the plan does not state: the code comment at `:7356-7358` records that this is a **deliberate
consolidation** — *"the dock's Evidence lens IS the ledger … the old 3-panel `#feedback-view` was deleted in
P0.1"*. So "Switch to Feedback (Consultant)" is a defensible *label* for a surface that was intentionally
folded, and "it does not switch to Feedback at all" overstates it. The honest finding is narrower and the
plan's own disposition (downgrade to info, don't delete) lands in the right place: **the doc describes a view
switch for something that is now a dock-open.**

### 4.3 The contrast method — not a defect, and the plan's floor is optimistic

The plan lists this as its third item under "the validation is itself wrong", which is where its own count
breaks down (§5.4). It is a method preference, and the plan itself says "same conclusion, different method".
I have now done both, and the rendered pixel is **lower** than the arithmetic floor — see §5.4.

---

## 5. Where the revision is wrong

### 5.1 P3-9 is not reachable — and its proposed test cannot be built *(material)*

The plan keeps P3-9 as a P3 item: *"unescaped SVG: `body.innerHTML = svg` at `:4116` … and `:4140`"*, and
proposes verifying it by *"seed[ing] a hostile `scene_number` through a `.fountain` fixture"*.

Every value interpolated into those two sinks is a **number**:

| Sink | Interpolated | Type | Source |
|---|---|---|---|
| `:4108` | `${s.page_start}` | int | `structure.py:111` — `{"page_start": i * segment_pages + 1, …}` |
| `:4135` | `${r.scene_number}` → `data-scene=`, `<title>` | int | `fdx_parser.py:75/86/89` — `scene_num = 0 … scene_num += 1` |
| `:4135` | `${r.pace_score}` | float | `pacing.py:73` — `round(100 * (…), 0)` |
| `:4135` | `${r.drag ? " (drag)" : ""}` | literal | — |

`scene_number` is declared `int` (`models.py:44`) and is assigned by a **counter in the parser**, not read from
the file. I confirmed it end-to-end by parsing the real fixtures and the shipped sample: `scene_numbers`
`[1, 2, 3]`, all `int`. A `.fountain` file has no way to set it. So:

- **the XSS is not reachable** through any screenplay, `.fdx`, `.fountain`, `.txt` or `.pdf`;
- **the plan's verification step cannot be written** as described.

This is still worth doing — `AGENTS.md` states the convention ("every `innerHTML` sink that interpolates
finding, script, chat or config text goes through `escapeHtml()`"), and these two sinks are the only
content-bearing ones that interpolate **nothing** through a helper. But it belongs as a **defence-in-depth /
convention** item (P5-tier), not beside P3's real ones, and the test should assert the *convention* (a shared
numeric formatter or an `escapeHtml` wrap) rather than a hostile screenplay that cannot exist.

**Note:** I nearly reported a second bug here — that a text-parsed script renders `undefined` in the pacing
axis labels because `page_start` is `None` for `.fountain` (`structure.py:16-19`). It does not: the *segment*
`page_start` is computed (`i * segment_pages + 1`), not taken from the scene. Withdrawn before writing.

### 5.2 "largest fixture is a 4-scene PDF" — false *(minor, but it is the claim P4 rests on)*

Measured with the shipped parser:

| Artifact | Scenes |
|---|---|
| `tests/fixtures/pain_tenglish.fountain` | **6** |
| `tests/fixtures/Pain_FD_4_scenes.pdf` | **0** in this environment — the parser returns an empty scene list (text-less PDF; needs the OCR fallback / tesseract). *(The `IndexError` in my probe came from my own `scenes[0]` access on that empty list, not from the parser.)* |
| the shipped sample the browser fleet drives (`The Late Hour`) | **3** |

So the largest fixture is the fountain, not the PDF, and the PDF yields nothing at all in this environment.
The **substance** survives and is in fact stronger — the fleet's whole world is a **3-scene** script — but the
stated fact is wrong, and a P4 item that justifies itself with a wrong measurement invites the reader to
discount the right conclusion.

### 5.3 "15 untracked test/`logsetup.py` paths" — it is **11**

```
?? screenplay_studio/logsetup.py          ?? tests/test_dead_surface_retirement.py
?? tests/e2e_browser_beatboard_drag.py    ?? tests/test_empty_kb_guard.py
?? tests/e2e_browser_deep_links.py        ?? tests/test_host_header_guard.py
?? tests/e2e_browser_modal_guards.py      ?? tests/test_logsetup.py
?? tests/e2e_browser_race_guards.py       ?? tests/test_undo_redo_lock_race.py
?? tests/e2e_browser_render_scale.py
```

11 source files (plus 33 `tests/_audit_shots/` artifacts and 3 docs). The `git clean`-vs-`restore` **point** is
correct and valuable; the count is not.

### 5.4 The contrast: the range is right for tokens, and the worst case is **below** it

The plan says *"Computed against the five actual dawn surfaces: 2.50 / 2.67 / 2.81 / 2.98 : 1"* and that the
token-based value *"gives 5.40–6.44"*. My independent arithmetic reproduces **both ranges exactly**:

```
dawn, shipped #46a758 on:  #f2e8d6 2.50 · #f4ecdb 2.58 · #f5edda 2.60 · #f6f0e2 2.67
                           #fbf6ea 2.81 · #fffdf5 2.98        -> 2.50 - 2.98   ✅ matches
dawn, --ok #0f6b41 on the same six surfaces               -> 5.40 - 6.44   ✅ matches
night, #46a758 on #150f0a: 6.27
```

But the plan's surfaces are the **opaque tokens**, and the dock dot does not sit on an opaque token. Re-running
the rendered-pixel probe (deterministic, reproduced twice):

```
--- dawn register ---
dock sev low    mark rgb (70,167,88)   backdrop rgb (237,229,209)   2.41   <-- below 3:1
dock sev medium mark rgb (138,90,20)   backdrop rgb (237,229,209)   4.71
--- night register ---
dock sev low    mark rgb (70,167,88)   backdrop rgb (34,26,17)      5.66
```

The rendered dock backdrop is `(237,229,209)` in dawn — not any of the six tokens — because the dock is a
**translucent panel over a gradient body** (`--glass: rgba(246,238,222,.72)` on a conic+radial body). So:

- the true worst case is **2.41:1**, i.e. **0.09 below the plan's floor**;
- the plan's advice — *"cite the range … rather than a single sampled pixel"* — would, taken literally, drop
  the **worst** measurement and replace it with an arithmetic floor that is 4% optimistic;
- night is likewise **5.66**, not the plan's 6.24, for the same reason (its figure is on the flat body, not the
  dock panel).

Both methods agree the dawn low dot is sub-3:1 and the cause is the one selector, so the finding stands and the
fix is right. The number to publish is **2.41–2.98**, not 2.50–2.98, and the *rendered pixel is the authority* —
arithmetic over tokens cannot see a composite backdrop.

*(My probe also reports `scene-index low = 1.0` in both registers. That is a **measurement artifact**, not a
finding: `.scene-index-dots .dot.low` is a **hollow ring** (`style.css:5358-5362`, `background: transparent;
border: 1.5px solid var(--ok)`), so sampling the interior returns the backdrop. Its border is `var(--ok)`, which
is 5.4–6.4:1 in dawn. Not a defect — recorded so the number is not mistaken for one.)*

### 5.5 Two nits

- **`:533` echoes the error → it is `:532`.** `@app.errorhandler(Exception)` is at `:504`, `def _unhandled` at
  `:505`, and the return is at **`:532`**; `:533` is blank. The plan corrected five other line numbers to exact
  and left this one off by one.
- **"there is no skip-link element anywhere in app.js"** — true of `app.js` (0 hits), but the element **exists**
  at `index.html:21` (`<a class="skip-link" href="#main">`). The refutation of P5-14 is sound and I reproduce it
  live (`restoredToOpener: True, isSkipLink: False`), but it rests on the **restore code** (`:5377-5378`) plus
  the probe, not on the element's absence. As written the supporting argument is the weakest part of a correct
  conclusion. (The plan's own "2 defects" count, which lists 3 items of which one is a method note, is the same
  kind of arithmetic slip it criticises in others.)

---

## 6. What the revision gets right that is easy to miss

1. **The commit-message catch.** HEAD is *"Close out the production-readiness audit: same gate re-run at HEAD,
   and §2.2 corrected"* — and `git show --stat HEAD` is **`NOTES.md | 24 +++`, 1 file changed**. The
   correction never touched the spec. This is the single best new finding in the revision: it turns a
   documentation error into a **process** error (a commit that claims work it did not do), and it is only
   visible if you read the stat rather than the message.
2. **The §2.2 direction.** It correctly identifies that the *header* at `:117` is right and the **"⚠ Known
   gap" callout at `:133-137`** is the false side — the opposite of what a grep-first reading suggests.
3. **The dawn low-dot cause, exactly.** `.sev-dot.low` hardcodes `#46a758` (`style.css:3150`); dawn overrides
   `.high` and `.medium` (`tungsten.css:24`) but **not `.low`**; the scene-index dots are immune because they
   read the token (`:5350`). One selector, and the asymmetry is invisible unless you measure **both** surfaces.
4. **The P1-3 lock topology.** "Three writers, three different (or no) locks over one file", "locks are
   sequential, not nested", and "**lost update on a read-modify-write cycle, never a torn file**"
   (`atomic_write_json` holds `lock_for` — `jsonio.py:361`). Every one of those clauses is exactly right, and
   the last one is the clause that stops a reader chasing a torn-file theory.
5. **"Concurrency-safe, not transactional."** The plan states that the fix leaves log and text in two critical
   sections, so a crash between them still diverges — and files that as a follow-up decision. That is the
   correct boundary to draw and most audits would not draw it.
6. **`Set-Cookie` has no `HttpOnly`/`Secure`/`Max-Age` _by design_.** The plan checked *why* before flagging it
   — `_studioToken()` (`app.js:68-71`) reads the cookie to echo the header — and concluded the action is a
   comment, not a flag flip. Correct.

---

## 7. What the revision still misses

1. **The P1-3 fix as written conflicts with the repo's own one-lock rule.** The plan says *"one lock across the
   whole `working.json` read-modify-write"*. But `undo_last_edit` writes `working.json` **inside**
   `lock_for(edits.json)` (`:470` within `:451-473`), and `redo_last_edit` writes it **inside**
   `lock_for(redo)` (`:517` within `:501-519`). So a `working.json` lock taken inside `save_working` would nest
   **log→working** — the exact thing `revision.py:445` and `jsonio.lock_for` forbid in writing
   (*"holding two store locks at once is the one thing `jsonio.lock_for` must never be asked to do"*,
   `revision.py:349-351`). The fix therefore requires **reordering** undo/redo so the working write happens in
   its own critical section, released before the log lock is taken. That is a design constraint, not a detail,
   and the plan does not state it.
2. **§12 lists three preview folders; there are four.** The spec names `preview-redesigns/`, `preview-next/`,
   `preview-r4/` (`:830-831`); on disk there is also **`preview-design/`**.
3. **`UI_CHANGES_DEFERRED.md` item 1 says "146 craft rules"**; the shipped KB loads **263** (`KnowledgeBase.all()`
   → 263, 26 files). Another stale figure in a file the plan already flags.
4. **The dawn fix is a *global* change, not a dawn-only one.** `style.css:3150` is not inside any
   `body.dawn` scope, so replacing `#46a758` with `var(--ok)` also changes **night** (`--ok: #7fc98a` →
   9.62:1 vs the literal's 6.27:1). Both pass 3:1, so the change is safe — but the plan's phrasing ("read
   `var(--ok)` the way the scene-index dot already does") reads as dawn-scoped and should say it is a
   night-affecting edit that happens to improve night too.
5. **`.high` and `.medium` are hardcoded literals too.** `style.css:3148-3149` are `#e5484d` / `#f5a623`, and
   `tungsten.css:24` duplicates the dawn values that already exist as `--danger` / `--sev-mid`. The
   token-consistent fix makes all three read tokens and deletes the dawn duplicate; the plan only mentions
   `.low`.

---

## 8. Bottom line

**Act on it.** The P0/P1 spine is correct, the revision's self-corrections are honest and mostly right, and its
two headline claims — the uncommitted fixes with a leaking pushed branch, and the unlocked `working.json`
read-modify-write — are verified. The ladder's order (P0-1 commit → P1 locks → P2 → P3) is the right order.

**Fix four things before citing it:**

| # | Fix | Why |
|---|---|---|
| 1 | **Re-rank P3-9** to defence-in-depth and delete the "hostile `scene_number` fixture" test step | not reachable; the test cannot be built |
| 2 | **Correct the P4 fixture claim** — 6-scene fountain, 3-scene sample, PDF yields 0 without OCR | the claim is the P4 item's own justification |
| 3 | **Correct the untracked count** 15 → **11** | verifiable in one command |
| 4 | **Publish the contrast as 2.41–2.98** and state that the rendered pixel is the authority | the arithmetic floor is 4% optimistic and would drop the worst case |

**Then add the two things it missed:** the **lock-nesting constraint** on the P1-3 fix (which changes how that
fix is written, not just how it is described), and the **`preview-design/`** / **"146 rules"** doc errors.

**Suggested order, amended from the plan:**

1. **P0-1 — commit the working tree.** Re-run both gates on the exact commit and cite those numbers.
2. **P1-3** — restructure so the `working.json` write is its own critical section (release the log lock first),
   then extend `test_undo_redo_lock_race.py` with a **child-process** leg and a **text assert on the redo side**.
3. **P1-4**, then **P1-5/6/7** (P1-5 is the strongest of the three: the `samePlace` guard exists in
   `attemptTurn` and is simply not back-ported to `sendFvMessage`).
4. **Dawn low dot** — one line, and while there make all three `.sev-dot` tiers read tokens.
5. **P3-9** as hygiene, with a convention test rather than a hostile screenplay.

---

### Appendix — reproduction commands

```bash
export PYTHONPATH="E:\screenplay-studio_1_qoder\.workbuddy-ai\pydeps"
export PLAYWRIGHT_BROWSERS_PATH="E:\screenplay-studio_1_qoder\.workbuddy-ai\ms-playwright"
PY="C:\Users\Avinash-Pro\.workbuddy-ai\binaries\python\versions\3.13.12\python.exe"

"$PY" -m pytest tests/ -q -p no:cacheprovider --cov --cov-report=term   # 1749 / 3 skipped / 87%
"$PY" tests/run_browser_suites.py                                       # 48 suites / 47 pass / 1175 checks
"$PY" .workbuddy-ai/scratch/live_probe.py                               # the rendered-pixel contrast + focus probe
git show --stat HEAD                                                     # NOTES.md only — the §2.2 claim
git status --short --untracked-files=all | grep -c '^??'                 # 50 paths / 18 entries
```

**Scope note:** the only file added to the tracked tree by this validation is this report. Nothing was
modified; no product code was touched.
