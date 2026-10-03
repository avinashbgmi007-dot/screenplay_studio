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

⚠️ **This is the design question the real script forces, and it is open.** A scene-anchored finding
currently draws the same severity mark as a line-anchored one, on the heading row. On this script
that is 12 marks on 22 headings — more than half the scene headings marked. Options, none chosen
here: (a) keep it (honest, but the top level looks busy); (b) show scene-level findings with a
quieter mark — the fold still opens, no severity border on the heading; (c) a distinct scene-level
mark that never claims a line. The recommendation is (b), because a severity border on a heading
implies the heading is the problem, and the finding is about the scene. This needs a writer's eye,
not more measurement.

### An unresolved gap, found by the same measurement

**1 of 16 findings is not shown by the page at all.** A finding with no `scene_refs` (category
`genre`, script-level by nature) is skipped by the dispatch: no band claims it, so it inks no row and
appears in no fold. The desk counts it; the page is silent about it. The Detent rule — *kept, never
dropped* — is not satisfied for this class. Proposed, **not implemented** (it is a copy decision):
one sentence in the annunciator when such findings exist, e.g. *"1 finding is about the whole script
— the desk's board holds it."* Nothing else in the page should move.

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
