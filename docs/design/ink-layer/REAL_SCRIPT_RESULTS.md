# Real-script results — `Pain_3_updated_FULL.pdf` through the live desk

**What this is.** The prototype was pointed at a real script for the first time. The desk was run
from the repo's own entrypoint (`python -m screenplay_studio.webapp_demo --port 8500 --demo-model
--no-token`), the writer's 28-page short film was uploaded through `POST /api/projects`, parsed,
analysed, and every claim below is a recorded response or a measurement over real payloads. The
demo craft model stands in for llama-server — which is stated at every point where it matters.

**The script, as the desk measured it:** 28 pages · 30.4 min runtime · 22 scenes · 9 characters ·
parse confidence **low** (the PDF parser's own warning: *"layout-gap heuristics, not explicit
formatting tags … spot-check before trusting citations"*).

---

## 1 · The product's own baseline, reproduced

`docs/PAIN3_SESSION_RUN_CARD.md` records a previous session on this same script:
**17 findings · severity `{low:16, medium:1}` · 3 of 17 verified · quote scenes 6 / 14 / 18.**

This run, independently:

| | recorded | this run |
|---|---|---|
| findings | 17 | **16** (one fewer; the engine and script have both moved since) |
| severity | `{low:16, medium:1}` | `{low:15, medium:1}` — same shape, **no `high`, no fourth word** |
| verified | 3 | **3** |
| quote-bearing scenes | 6, 14, 18 | **6, 14, 18 — exact match** |

Categories: dialogue 9, continuity 3, plot_thread 1, theme 1, character 1, genre 1.

## 2 · What the Ink Layer can ink on this script — the number that matters

Measured with `tests/measure-anchors.mjs` (added in this pass; it mirrors the page's dispatch and
walks the **shipped** path, so it measures the product, not a friendlier one):

* **3 of 16 findings carry a quote at all** (19 %). The other 13 are `no_quote` with
  `evidence_quote: null` — the verifier's citation state, not a failure.
* **3 of 3 quote-bearing findings reached a line — every one at score 1.000 (exact substring).**
  Mean 1.000, min 1.000. The 0.72 gate was never stressed by this payload: no finding fell into the
  0.72–0.99 band, and none was loose.
* **12 findings landed scene-anchored** (the scene's first row — its heading), and **1 is
  script-level with no `scene_refs`**.

So on this real script the honest summary is: **3 lines of manuscript carry ink; 12 scene headings
carry a scene-level mark; 1 finding has no band to sit in.** The line-anchored layer addresses 19 %
of the report; the rest is scene-level by nature of the data. Ink is quote-dependent, exactly as the
run card says.

### The scene-level mark — implemented, and measured before and after

A scene-anchored finding opens on the scene's first row, which is its **heading**. Drawing the full
severity border there implies *the heading is the problem*; the finding is about the scene. On this
script that was 12 marked headings out of 22.

Implemented as recommended: a row whose open findings are **all** scene-anchored is marked
`data-placement="scene"` and draws a **hairline** — the severity width is dropped, the weight is
still stated in the fold's meta line, and the **Horizon still draws it** (the Horizon is
scene-scoped by construction, so no severity is lost anywhere). A row with **even one**
line-anchored finding is a `line` row and is unchanged: at least one finding really does claim the
line. The fold says the reason once — *"About this scene — the mark on the heading is the scene's,
not a line's."* — and a mixed row still says it per finding, where it distinguishes.

Measured on the live payload, after the change (`tests/measure-anchors.mjs`):

| | before (read-only) | now |
|---|---|---|
| rows carrying a severity border | 12 headings + 3 lines | **3** (the line-anchored ones) |
| rows marked scene (hairline) | — | **9** |
| scene-level claim on a heading, visually implied | 12 | **0** |

### The off-page gap — implemented

**1 of 16 findings was not shown by the page at all** (script-level, no `scene_refs`). The
implementation went one step further than proposed, because the audit found the class was larger than
the one case: **three** kinds of finding can be off-page — a **script-level** finding (names no
scene), a **missing-scene** finding (cites a scene this draft does not have), and a **parked** finding
(answered, and no row this session watched the fix land on). All three are now counted and said once
at boot, in the desk's own terms:

> `1 finding not on a line: 1 about the whole script, not a scene. The desk's board holds it.`

The parked case had **never been surfaced anywhere** — a comment in the code claimed "the
annunciator says so" and nothing did. It is, now.

## 3 · Defects the real payload exposed — both fixed, both invisible offline

### 3.1 Every scene heading was drawn twice

A real payload carries the heading **twice**: `heading_raw` *and* a `scene_heading` entry inside
`elements[]` — 22 of 22 scenes on this script. `flatten()` pushed both, so the manuscript drew every
heading twice. Worse, a heading-quoting finding then **tied with its own duplicate** and the page
reported *"this quote matches more than one line"* on **3 of 3** real quotes — the ambiguous path,
meant for genuine disputes, firing on all of them. All three real quotes here are scene headings:
they come from the deterministic continuity pass (*"Unmarked time flip: Scene 5 ends in MORNING and
Scene 6 opens in NIGHT"*), whose evidence is the heading itself.

Fixed in `flatten()`: the heading is a row once; the `scene_heading` **element** is skipped when
`heading_raw` already provided the row, and kept when it did not. This matches the product's own
renderer — `app.js:5306`, `if (e.type === "scene_heading") continue;`.

Verified live: rows **1023 → 1001** (the 22 duplicates gone), **ambiguous 3 → 0**, all three quotes
still anchored at 1.000. Regression test added, and the demo fixture now carries the double explicitly
so the offline suite exercises the same shape.

### 3.2 `applied` is a list, not a count

`/edits/apply` answers `applied: [{old, new, similarity}]` and `skipped: [{old, new, reason}]`
(`revision.py:736`). The demo adapter returned **counts**, so against a real desk the annunciator
would have said *"Applied [object Object]"* — a defect no offline test could see, because the fixture
was a softer world than the desk. Fixed at all three layers: the copy reads both shapes and says
silence when everything landed; the caller now only says "Line N changed" when something actually
did; the demo returns the route's real shape so the offline build cannot drift again. Tests pin the
list shape and assert the announcement never contains `[object`.

## 4 · The writer's loop, end to end, on the real script

```
POST /rewrite {scene_number: 6}
→ {note: "Demo rewrite: replaced the first dialogue line.",
   replacements: [{old: "Comic books chaduthu, siddhu page turn chesthuntadu. Appude",
                   new: "[demo] The line lands quieter now — subtext doing the work."}],
   scene_text: 1992 chars}

POST /edits/apply {scene_number, replacements: [{old, new}]}
→ {applied: [{old, new, similarity: …}], skipped: [], scene_text_after: …,
   findings_status: {checked_at, findings: [16 rows]}}

POST /edits/undo
→ {can_redo: true, can_undo: false, findings_status: …}
```

`/rewrite` is scene-scoped and its `old` is verbatim scene text — the strip's scope sentence is
accurate. A flat `{old, new}` body is refused with *"replacements list is required"*, which is the
route teaching the client its own shape; the page's `applyPayload` already sent the correct one.

## 5 · What this pass did NOT establish

* **Craft quality, at all.** The findings are `[demo]` fixtures — one of them literally reads
  *"[demo] Sample dialogue finding. The built-in demo model is running, not a real analysis."* The
  demo engine emits placeholder issues (~9 repeated); whether a finding is *true* needs the writer's
  own llama-server. Judge the instrument here; judge the notes elsewhere — the run card's own words.
* **The 43-finding session.** `main`@`0fa814c` records a real-model analysis of this script
  ("the writer's own 43-finding analysis"). That payload would be the strongest Q10 evidence —
  40-odd findings with real quotes. It is not in the repo and was not available here.
* **Anti-aliasing the measurement.** Three quote-bearing findings is a sample, not a rate. On this
  script the gate was never stressed; that says *nothing* about a paraphrase-heavy report.
* **The capability-token path.** The desk ran with `--no-token`, so `core.js`'s `writeHeaders`
  cookie echo was not exercised against a token-required server. Unchanged from the audit's note.
* **A browser pass.** All of this is route-level plus a Node measurement harness. No human or
  Playwright session has looked at the prototype rendering these 22 scenes.

## Reproduce

```
pip install -c requirements.lock.txt -e .
python -m screenplay_studio.webapp_demo --port 8500 --projects-dir <dir> --no-token
curl -F "file=@Pain_3_updated_FULL.pdf" -F "title=Pain_3" http://127.0.0.1:8500/api/projects
curl -X POST http://127.0.0.1:8500/api/projects/Pain_3/analyze -H 'Content-Type: application/json' -d '{}'
cd screenplay_studio/webapp/preview-ink-layer && node tests/measure-anchors.mjs http://127.0.0.1:8500 Pain_3
```

---

## 6 · The browser pass — the first time this page ran in a real browser

Playwright was provisioned in the sandbox (chromium + the system libraries the headless shell
needs), and the prototype was loaded **against the live desk with the real script**:
`/preview-ink-layer/index.html?project=Pain_3`. Four defects surfaced that no offline assertion could
have caught, because **jsdom does not lay out**:

1. **Hollow quotation marks.** `.find-evidence` draws its curlys in `::before`/`::after`, so a
   quoteless finding rendered as a pair of empty quotation marks — and `no_quote` is the majority of
   a real payload (13 of 16 here). The element is now created only when it has something to hold; a
   quoteless finding shows its issue and its attribution, and no quotes at all.
2. **A stutter in the fold.** Three findings in one fold each repeated *"about this scene"*. The
   reason is now stated once per fold, and per finding only on a mixed row.
3. **The fold was 26 % air.** `.find-issue` and `.find-evidence` are `<p>` elements, so they arrived
   with the UA's `margin: 1em 0`; in a grid every margin adds to its **row**, so a 22px line made a
   51.5px row and `.find-sig` — spanning both rows — inherited the inflated height. Every finding
   occupied **53px for 22px of text**; a three-finding fold was **257px**. With the UA margins
   removed and the gap owning the rhythm: **190.7px**, items at 26.9 / 49 / 26.9.
4. **`/preview-ink-layer/` 404s.** The catch-all serves files, not directory indexes — the URL in the
   PR description and in `PUSH_INSTRUCTIONS.md` is wrong. It is
   **`/preview-ink-layer/index.html`**. (Same family as the audit's finding that the docs and the
   code can disagree; this one was mine.)

Everything else measured clean: 1001 rows, 9 scene-placed / 3 line-placed, 0 empty evidence
paragraphs after the fix, exactly one fold note, the boot sentence naming the off-page finding, and
**no console errors or warnings** on a real script.

## 7 · The capability-token path — closed

The desk was restarted **with the token required** (no `--no-token`) and the page's own helpers were
exercised against it, not a hand-written header:

* the server minted the cookie and issued it on the document (`_issue_token_cookie`,
  `webapp_server.py:239-243`);
* `tokenFromCookie()` read it out of the cookie string and `writeHeaders()` produced
  `X-Studio-Token: …`;
* a write **without** the header → **403 `{"error":"missing or invalid capability token"}`**;
* the same write **with** the header core.js produced → **200**, persisted to
  `finding_marks.json` on disk.

§5's item 4 is closed. What remains open from the audit is only the demo-vs-real *model*, not the
token path.
