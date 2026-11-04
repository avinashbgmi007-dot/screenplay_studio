# Archive of entries removed from the register — not genuine gaps

Created during the file-by-file authenticity review (2026-11-04). Nothing is deleted: every entry removed
from `GAP_REGISTER_AND_EXECUTION_PLAN.md` or demoted out of `SELF_CRITIQUE_OF_GAP_REGISTER.md` is reproduced
here in full, with the reason and the check that produced that reason.

**Why this file exists.** The register grew to 128 entries, and the instruction was to keep only genuine gaps.
Removing an entry is a claim ("this is not a real problem"), and a claim deserves the same evidence standard as
an entry. So each removal names what I checked, where, and what I saw. If I am wrong about one of these, this
is the place to find the argument I used.

**Three things are kept in the register and are NOT in this archive**, because they are genuine even though
they are not defects: the reproduced negatives (114, 116, 117, 120), the withdrawn-but-instructive entries the
user has seen throughout this session (67, 91, 102, 103, 104, 109 — see below for which moved), and every
finding with a real mechanism regardless of severity.

---

## 1. Moved to "known trade-offs" — not defects

### 22. FDX export is not a full-fidelity backup of an original FDX (was grade A)

**Reason:** the lossiness is documented by the exporting code itself, and no behaviour is contrary to a stated
contract. Final Draft's format carries style runs, revision marks and numbering schemes that this project's
element model does not represent; a conversion that preserved them would be a different product decision, not a
bug fix. What remains true and worth saying is the *wording* risk — calling a reconstructed export a "backup" —
so that sentence moves to the known trade-offs list.

**Checked:** parse → FDX export of a synthetic fixture with heading number `42A` and a bold run returned the
plain words, heading `1`, no bold. Correct behaviour for the declared model; the finding is the label.

### 76. Lock sidecars remain visible as project files and are excluded inconsistently (was grade D)

**Reason:** `*.lock` sidecars appearing beside project files is how the lock works; `jsonio`/`NOTES.md` discuss
it at length as a deliberate choice. The inconsistent exclusion (backups exclude them, the folder view does not)
is a display nit at D grade, not a gap.

**Checked:** `project.json.lock` present while the app runs; backup code filters `*.lock`.

### 127. The ten packaging tests inspect the source tree rather than the wheel (was grade D)

**Reason:** this is true, and I proved the wheel is correct by building and booting it (180 files, 4.04 MB, 263
rules, `/` → 200 from a clean `--target`). What is left is "CI could catch a future mistake it currently does
not" — an improvement to test strength, not a gap in the product. Moved to the guard-strength list.

**Checked:** built the wheel, installed it outside the repo, imported from there, hit four routes.

### 128. The XSS guarding convention has no test behind it (was grade D)

**Reason:** the escaping is correct at every sink I could find, so there is no behaviour to fix. The remaining
statement — *a future commit could introduce a raw interpolation* — is a speculation about code that does not
exist yet. It belongs in the guard-strength list with 127.

**Checked:** enumerated all 63 `innerHTML` assignments in `app.js`/`core.js`; unescaped interpolations are a
developer-authored chip array, numeric counts and SVG geometry only. No `eval`, no `document.write`.

---

## 2. Demoted to "product direction" — intent is not a defect

These are the entries I have called "the product gap" throughout, and the phrase was doing too much work. A gap
in this register means *the software does not do what it promises*. On this evidence the software promises an
analysis of the script you give it; it does not promise to hear your intent. What these entries describe is a
**capability the product should have**, and grading them C while listing 106 among the severe items was
inconsistent with my own severity rule.

### 106. The premise card the writer wrote is saved, carried and never read by the analysis

**Checked:** `save_project_premise` persists `premise.json`; the graduation route carries it; the collaborator's
prompt builder accepts `premise=`. `Orchestrator.run_analyze` → `pipeline.analyze` takes only document, client
and language options. In `pipeline.py` and `prompts.py` the words "premise" and "intent" appear only as output
concepts. All of that is accurate.

**Why it is not a gap with a fix:** making the analyzer read the premise card is a design change with its own
risks (a model told what the writer meant grades the intention instead of the page), and it cannot be validated
here without a real model. Fixing it is not "repair"; it is "build".

### 107. Scene-level intent has nowhere to live

**Checked:** notes and stash are free text with an optional scene number; there is no intent field, and
dismissal records a judgment that feeds back only as a hidden row. Accurate as a description of the schema.

**Why it is not a gap:** a missing feature that was never claimed. This is the strongest *product* argument in
the review and the weakest *finding* in it.

### 108. Because intent is absent, the two collaborators cannot honour their distinct roles

**Checked:** both prompt builders receive script, report, memory and craft history; neither receives declared
intent. Accurate.

**Why it is not a gap:** it is a consequence of 106/107, not an independent defect, and any claim about how this
makes the collaborators *feel* requires the real-model gate this sandbox cannot open.

**What replaces these three in the register:** one paragraph, under product direction, stating that the analysis
is intent-blind and that making it intent-aware is the change worth evaluating first — with the same trace
evidence, and without a gap number.

---

## 3. Design proposals — not reproduced defects

### 97. There is still no writer-facing recovery room anywhere in the product (was grade D)

**Reason:** I described a surface that does not exist and recommended building it. Each underlying failure is
already a numbered finding (80, 82, 70, 64, 72), so 97 adds no mechanism of its own; it adds a feature request
in the grammar of a defect. Moved to product direction.

**Checked:** read the shelf, idea-shelf and error paths; every one returns an honest status with no next action.
The absence is real; the classification was wrong.

---

## 4. Withdrawn after re-testing (these never were gaps)

Kept here rather than deleted, because a review that only shows its survivors is not a review. All six were
already marked W in the register; this is the consolidated record now that the register no longer carries them.

### 67. Process-wide diagnostics are called inside request handlers

`_stale_code_warning` shells out to `git rev-parse`/`git status`. Measured at **~7 ms** against operations that
take seconds. Cost is not a defect at that ratio.

### 91. A chat reply can be discarded by the read path the SPA depends on

`POST /messages` returns 200 with top-level `messages`; `GET /session` returns `branches`. The SPA reads
`branches` and gets the reply. The observation was an **API asymmetry between two endpoints**, not a discarded
reply, and the entry's own framing collapsed the two.

### 102. Two analysis categories receive no knowledge-base grounding

My probe keyed `fragment_for_pass("pacing")` and `("genre")` against names the pipeline does not use directly.
`RulesContext.rule_count()` distinguishes `None` from `0` and the pipeline reports the latter. A mis-keyed
probe, not a coverage hole.

### 103. The rule library is heavily skewed

The genre fragment is 7,760–10,389 characters and the pacing pass is deterministic with no model call. A
distribution observation with no consequence; nothing to fix.

### 104. Rule selection pulls dozens of rules into one prompt without a budget

The 39,923-character `character` fragment came from a pass name the pipeline does not call directly. The
measurement did not describe a real prompt.

### 109. Root `ruff check .` may not be clean

It is clean. Suspicion tested and dissolved before it was ever filed as a defect; kept here so the discipline of
checking a published claim is visible.

---

## 5. Sub-claims removed from entries that stay

Several entries were compound, and one clause in them was not a gap. The parent entries stay; the clauses do not.

| Entry | Clause removed | Why |
|---|---|---|
| **83–85** (documentation drift, CLI surface) | The "deprecated standalone server" framing | `screenplay_cowriter/server.py` exists and runs; calling it deprecated was my inference from the docs, not a statement in the code. The route-map drift and the CLI/document mismatch stay. |
| **86** (scratch files shipped in packages) | "…and they ship in the installed package" | They are tracked in git and inside importable packages (true), but the **wheel does not contain them** — I built it and checked. Half the finding was false. |
| **92** (demo collaborator gives canned answers) | Any claim about Sameer/Sushruta quality | The replies are the stand-in's; the statement is about the demo model, not the product. Kept only as a description of what the demo can and cannot show. |
| **95** (design lab carries project data) | "Fully-data-bearing API surface with no separation" | The routes share the Host guard and capability token, and `_preview_lab_session` is isolated from the writer's thread. No cross-writer or unauthenticated exposure was demonstrated — the entry already said so, but its headline overstated it. Kept, restated, as a scope/packaging question. |
| **113** (summary counts hidden rows) | The by-severity numbers | `total_count 2`, `open_count 2` and `by_severity {high: 1, low: 1}` are all consistent with each other. The finding is that ungrounded rows are counted while the desk hides them — the arithmetic itself is fine. |
| **115** (acts show `scene_count: 0`) | Any implication the act model is broken | Beat bucketing works for both attached features (7/11/4 and 1/7/3). This is a display behaviour on a one-scene script. |
| **126** (no ceiling on dictated audio) | "Sends recordings off-machine" | The external whisper server is one the user started, and the guard proves it is loopback. The inherited 256 MB ceiling is defensible. Downgraded B→C; only the missing magic-byte check remains. |

---

## 6. What this archive is not

It is not a claim that the register is now correct. It is a record of what I decided was not a gap **and why**,
so that the next reader can disagree with a specific argument instead of a tone. Two of these I would defend
strongly (22, 92); two I would defend weakly (96, 128) and only as "would not schedule"; one (95) I had already
partly retracted inside its own text before this review started.
