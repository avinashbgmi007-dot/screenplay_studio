# Self-critique of the gap register — how genuine is each finding?

Written by me, about my own review. The purpose is to stop a long register from laundering weak findings into apparent severity, and to correct the ones this critique shows were wrong. Where a claim below contradicts an earlier entry, **the earlier entry is what gets amended** — see "Corrections applied" at the end.

Grades used throughout:

- **A — reproduced through a real interface** (real Flask routes, real orchestrator, real store, real CLI) with synthetic but valid data, and the mechanism is visible in source. Treat as real.
- **B — reproduced at module level with a stubbed collaborator** (fake client, forced clock, forced failure, forced barrier, monkeypatched transport). The mechanism is real; **reachability and frequency are not established**, and several of these would never occur without deliberate construction.
- **C — source-only inference.** Plausible, sometimes almost certainly true, but nothing was executed to prove the consequence. Must not be cited as a defect.
- **D — opinion, framing or product-preference, not a defect.** Valuable as design input; worthless as a bug list.
- **W — withdrawn or substantially downgraded** after this critique.

A finding can be real and still be *low consequence*; grade is about evidence, and each entry carries its own severity note.

---

## 1. The uncomfortable summary

Across the whole register, my honest estimate is:

| Grade | Count | Share |
|---|---|---|
| **A** — real-interface reproduction | ~28 | ~26% |
| **B** — stubbed/forced reproduction | ~24 | ~22% |
| **C** — source inference only | ~17 | ~16% |
| **D** — framing, docs, product opinion | ~13 | ~12% |
| **W** — withdrawn or fundamentally downgraded | 4 | ~4% |
| Disputed-in-part (mixed) | 7 | ~6% |
| Already-known/design-documented rather than new | ~15 | ~14% |

So roughly **half the register is evidence I would defend under questioning**, a quarter is inference or framing, and a meaningful minority is either already known to the team, already documented as a deliberate trade-off, or wrong. The register's length has been doing work that its evidence has not earned. That is the main finding of this critique, and it is a criticism of my process, not of the codebase.

Two structural biases I can name:

1. **Severity inflation by adjacency.** Because real release blockers (gaps 1, 3, 4, 21) sit in the same document as "the docs mention a port inconsistently" (gap 85), the document reads as if 108 comparable problems exist. They do not. There are roughly **nine things that would lose a writer's work or lie to them about it**, and then a long tail.
2. **Confirmation by construction.** With a fake client, a forced barrier and a monkeypatched transport I can make almost any store misbehave. Several entries (61, 68, 74, 75, 100) describe exactly that: a mechanism that is real in the abstract, unreachable or harmless in the shipped product, presented as a finding.

---

## 2. Corrections — entries this critique withdraws or downgrades

**W — Gap 103 ("the rule library is heavily skewed").** As written ("0 pacing rules, so grounded findings cluster…") this is **misleading**. Follow-up calls show the genre check receives 7,760–10,389 characters of genre-specific rules per detected genre, and `plot_thread` receives ~12,500. The zero counts were for pass names the pipeline never asks for. The real, narrower observation is: (a) there is no pacing rule file at all, and (b) the *pacing* pass is **deterministic only** — it calls no model, so "ungrounded pacing" is not a missing-grounding bug, it is a design choice. Downgraded to **D/C**: a content-completeness note about one category, not an analysis-quality defect.

**W — Gap 104 ("a category can pull dozens of rules without a budget").** Half right, half wrong. The oversized 39,923-character fragment came from a pass name (`"character"`) used only in a dynamic loop that resolves to the four real categories, and those render far smaller. The genuine point survives as a bounded question: **is any single rendered fragment large relative to a small local context, and is that share measured?** That belongs as a measurement task (**C**), not as a defect with a fix.

**W — Gap 91, as originally framed.** Verified again: the GET returns `branches` and the shipped SPA reads `branches`; the POST returns a top-level `messages`. That is an **API asymmetry** worth documenting (any third-party client or older preview lab can be misled) but it is **not** "a chat reply can be discarded by the read path the SPA depends on". Retitled and reduced to **C**, documentation-level.

**W — Gap 67 ("process-wide diagnostics … cost scales with traffic").** Measured at ~7 ms with two subprocess spawns per analyze response, on a page-load-and-analyze operation that takes seconds to minutes. This is a code-hygiene remark, not a gap. **D.** I keep it only because the same helper is called on the analysis path while a lock is held.

**Downgraded — Gap 74/75 (manifest stage merge).** The mechanism is real and I reproduced a stale object reverting another writer's `parse` status. But the only path that holds a manifest for a long time is the analysis run, and its saves are the intended writer for those fields; there is no shipped flow where a writer's window and a run edit *different fields of the same stage*. Keep both, merge them into one entry, and label them **B with a "reachability unproven" note** — not the two separate findings I filed.

**Downgraded — Gap 100 (craft history one-sided).** Correct behaviour, honestly documented in the module, and arguably the *right* privacy/evidence trade. Keeping it as a gap blurs a design judgment with a defect. **D**, recommendation only.

**Downgraded — Gaps 83–86, 96.** Documentation drift and an unreachable directory index. Real, cheap to fix, and irrelevant to a writer's session. Group them as one **D/C "housekeeping"** item so they stop competing for attention with data-loss findings.

**Reframed — Gap 97 ("no recovery room").** This is not a defect I reproduced; it is a **product judgment** that the failure modes found elsewhere deserve a writer-facing surface. That judgment is mine, not evidence. **D**, and it should be approved or rejected as design, not scheduled as a bug.

**Reframed — Gaps 87–90, 92–93.** These came from the demo model, which is a canned stand-in. They are **not** statements about the product's real feedback quality. What is genuinely established: a report can contain a detail absent from the script (87, mechanism confirmed, demo-generated), rendering omits provenance and evidence tier (88–89, source-confirmed), and the pipeline completes end to end (90, 93, timing only). Everything about voice, taste and disagreement in those entries is **D**.

**Already known, not discovered — 15 entries.** Reading `NOTES.md`, `STATE_STORES.md` and the tests afterwards, several findings are documented in-repo as known behaviour or deliberate trade-offs: lock-sidecar visibility (76), FDX fidelity limits (22, documented in the export docstring), the design labs shipping (95–96, a deliberate decision), 10-second lock budgets (68, discussed at length in `jsonio`), and the demo fallback design (56, documented *and* documented wrongly — that part is real). I should have cross-checked `NOTES.md` first; presenting a known trade-off as a discovery wastes the reader's trust.

---

## 3. Where the register under-sells real problems

Self-criticism should cut both ways. Re-testing found that **some of my strong claims are stronger than I labelled them**:

- **Gap 1 (edits lost on draft switch) — verified again end to end, and worse than stated.** Applying an edit, uploading a draft and switching back restored the *original* text; the working copy and the edit log are gone, and the draft snapshot contains only `source.*` and `parsed.json` — no working copy, no history. A writer's revision work is destroyed by an action the UI presents as non-destructive ("switching preserves the current one" is literally the tooltip). This deserves to be the first item in any fix, above every concurrency finding.
- **Gap 21 (export merges adjacent speakers)** — reproduced: `AJAY/Hello.` + `VENU/Hi.` re-parses as `AJAY/Hello.`, `AJAY/VENU`, `AJAY/Hi.` Round-trip use of the exporter silently reassigns dialogue. My original note called this a "release blocker for round-trip use"; the reproduction supports exactly that, and it should be stated more plainly than it was.
- **Gap 23 (Indic normalization)** — reproduced: `కల` and `కాల` normalize equal, so a *different word* verifies as an exact quote. For a Telugu-first writer this is a false-evidence generator in the product's core claim.
- **Gap 62 (draft-name traversal)** — the most serious thing in the entire register and it is buried at position 62. A crafted `activate` name reads and overwrites another project's snapshot, and can reach outside `PROJECTS_DIR`. It is API-only, which is why it is not a remote vuln, but it is a **workspace-integrity** failure and should be numbered among the top five.

So the register is simultaneously inflated at the tail and **mis-ordered at the head**. The ordering is the more damaging error.

---

## 4. What a fair reading of the evidence actually supports

If I had to hand the writer three sentences instead of 108 entries:

1. **Your text and your revisions are not yet safe.** Swapping drafts deletes edits and history; a refused upload can strand you on an unreadable active draft; a damaged manifest blocks even the export that would rescue it; two uploads in flight can lose one. Everything else can wait behind this.
2. **What you are shown can silently describe something other than what you are editing.** An analysis can publish into a different draft than it read; a draft switch keeps the previous draft's characters; a report can name something absent from your script and the exported Markdown will not say so; the KB-grounded claim is true for some passes and silent for others.
3. **The two collaborators cannot yet hear what you meant.** The premise card you write is saved and never read by the analyzer, and there is nowhere to record scene intent. That is a product gap, not a bug, and it is the one worth redesigning around.

The remaining ~95 entries are a mix of real-but-rare, real-but-minor, inference, and opinion. They are still useful — as a checklist for whoever implements contracts — but **they are not 108 reasons the app is broken**, and I should not have let the count imply that.

---

## 5. What I am changing in how the remaining sweep is graded

- Every new entry gets an explicit grade (**A/B/C/D**), the interface it was reproduced through, and a one-line "would a writer hit this?" answer.
- No entry is filed from source reading alone unless it is labelled **C**; C entries are collected in a separate appendix and are **not** counted as gaps.
- Any finding I cannot state as "do X, observe Y, expect Z, got W" is not a finding.
- Before filing, grep `NOTES.md`, `STATE_STORES.md`, `CHANGELOG.md` and the module docstrings for prior acknowledgment; if it is known, it goes to "known trade-offs" instead.
- Concurrency and stubbing results carry a mandatory "constructed" marker in the title.
- The head of the register is re-ordered by consequence to the writer, not by the order I found things.

---

## 6. Sequencing correction

My earlier recommendation ("five contracts, then the journey") is still right, **but the order inside it was wrong**. On this evidence the order should be:

1. **Containment** (gap 62) — smallest change, closes a workspace-integrity hole.
2. **Stop destroying revisions on switch** (gap 1) and **restore the whole bundle** (gaps 63–64) — this is what makes drafts a safety net instead of a hazard.
3. **Never publish a report that describes a different snapshot** (gaps 2, 3, 4, 65) — the truthfulness contract.
4. **Make the intent brief real** (gaps 106–108) — the only item that changes how the product feels to write with.
5. Then provenance/rendering (87–89), then recovery surface (97), then the long tail.

Collaborator voice, grounding accuracy and performance stay behind the real-model gate regardless of ordering, because no amount of local probing can settle them.

---

## 7. Second pass — grading the earlier 1–15 and the batches I was most confident about

I re-ran the four highest-severity early findings through real interfaces rather than trusting my own notes.

**A, confirmed and promoted — Gaps 1 / 4 / 21 / 23.** Each was reproduced again through the real Flask routes or the real parser/exporter this pass:
- draft switch after an applied edit restores the original text and leaves no edits log, no working copy and no draft snapshot of either (**A**, worst item in the register);
- the export round-trip re-parses `AJAY/VENU` as three AJAY lines (**A**);
- `కల` vs `కాల` normalise equal (**A**).
These are not in doubt and should not have been interleaved with inference-grade entries.

**B — Gap 2 (re-analysis reads the wrong draft).** Reproduced originally with a stubbed analyzer and an edit applied outside the run. The mechanism (analysis loads `parsed.json`, not the working copy) is source-visible, and gap 65 shows the publication half through real routes. Grade **B**, reachability high.

**B — Gap 3 (failed runs overwrite reports).** Reproduced by injecting a total failure. The orchestrator's own comments claim a failed run preserves the previous report, so the reproduction contradicts an explicit intention — that makes it worth keeping at high severity even though the injection was constructed.

**B — Gap 5 (cancel/retry control).** Partly promoted: **66** now contains a real-route reproduction (`/analyze/cancel` answering 409 during an actual `retry-failed` run). The *UI* half (frontend reporting complete on a cancelled response) remains **C** — I traced it in source, I did not drive it in a browser this pass.

**B/C — Gap 6 / 7 (history divergence, cross-process runs).** Both were injected. Keep as B, but the register should say "requires two processes / injected failure", which it partly does.

**C — Gap 9 (incomplete context, low confidence).** The *symptoms* are measured on both PDFs (join char caps, observation stopping before the final scene); the *consequences for feedback quality* are inference. Split it: measured coverage facts stay **A**; "this causes worse notes" is **C**.

**D — Gap 15.** As filed it is a statement about unvalidated quality, not a defect. It is the correct caveat for the whole document, not a numbered gap. Keep it as a caveat.

**A — Gap 62, and my ordering was wrong.** Re-verified through the real route with two synthetic projects: a relative draft name reached a sibling project's snapshot, returned 200, replaced the active source and report, and a later upload in that state wrote outside `PROJECTS_DIR`. This is the single most serious *security-shaped* finding and I filed it at 62 behind dozens of weaker entries. Grade **A**, severity high, ordering corrected in §6.

## 8. New entries from the two areas left ungraded — and their grades

**W — 109 (withdrawn before it was ever filed as a defect).** I suspected my "ruff clean" claim only covered four package directories while CI runs `ruff check .` at the root. I checked: **`ruff check .` at the root passes.** There is no gap. I am leaving the note in only because the discipline it demonstrates — verify the claim you already published — is the point of this document, and because a reader deserves to see a suspicion resolved rather than silently dropped.

**B — 110. A missing source file produces a raw traceback instead of a sentence.** `python -m screenplay_studio run missing.fountain --project …` exits 1 and prints `FileNotFoundError: [Errno 2] No such file or directory` as a traceback. The CLI's own contract (clean messages, machine-usable exit codes) is met on exit status but not on readability, and it is inconsistent with the web app, which turns the same condition into a JSON message. Reachable only by a scripted or mistyped invocation. **Recommendation:** catch the file error at the CLI boundary and print one actionable line naming the argument.

**A (good news) — 111. The CLI round-trips correctly when driven properly.** `run <source> --project <dir> --only parse` created a valid project (parse complete, analyze/chat pending), and `status <dir>` read it back with exit 0. Positional ordering matters: `status` takes the project positionally while `run` requires `--project`, so a symmetric invocation fails with argparse's exit 2. That asymmetry is worth one line in the CLI reference; it is **D** as severity. I note it because my first probe got it wrong and I would rather record my own mistake than let the "status is broken" impression stand.

**C — 112. Repository size is concentrated in audit evidence and screenshots.** `docs/` is 12 MB (including dated audit JSON/PNG evidence) and `impl-shots/` is 7.2 MB, with nine concept PNGs at the root. None of it affects the app, and the packaging tests exclude it — but the ledger's file count and any future clone/snapshot budget are dominated by material that is not the product. **Recommendation:** decide an evidence-retention convention (keep the JSON, move PNGs to external storage, or compress), and say so in `AGENTS.md`. Grade **D**, housekeeping.

## 9. Honest overall verdict after the second pass

- **Twelve entries carry real weight**: 1, 3, 4, 18, 21, 23, 62, 63, 64, 65, 87, 106. Eleven of them are data-safety or truthfulness; one (106) is the product gap.
- **About fifty are legitimate but conditional**: they need concurrency, a stubbed collaborator, a damaged store, an unusual API client, or a real model to matter.
- **About forty are inference, documentation, or opinion.** They belong in an appendix, clearly marked, so that nobody — including me — reads them as a bug count.
- **Five are withdrawn entirely** (103 as written, 104 as written, 91 as framed, 67 as filed, and 109 which never became a gap).

I would defend the twelve. I would caveat the fifty. I would not have written several of the forty. That is the standard I should have applied from the first batch, and it is the standard I will apply to the remaining sweep.

## 10. Third pass — three things the register got right, one it overstated, and the grade I had missed

**A — 113 (new). A writer-facing count includes findings the desk says it hides by default.** In a controlled project with two findings — one grounded and quoted, one `ungrounded` — `/fixqueue` reports `total_count: 2` and `/findings/summary` reports `open_count: 2`, `by_severity: {high: 1, low: 1}`, while the UI's own rule is that ungrounded rows are hidden behind a toggle. So the number the writer sees is the *internal* set, not what they can act on, and the ledger's mass strip and dawn meter are computed on it. This is a small, real, checkable inconsistency in the product's credibility surface, and it is the kind that matters more than its size: it is the number the writer uses to decide whether they are done. **Recommendation:** either count what is shown by default and label the hidden remainder, or state explicitly that the count includes unverified rows — and use one arithmetic for the strip, the meter and the queue.

**A — good news worth stating, 114.** `/findings/summary` derives `open_count`, `done_count`, `dismissed_count`, per-category and per-severity counts from the serving path in one place, and the fix queue and summary agree on the same two rows in this probe. Several of my earlier "stale statistics" concerns (gap 13) belong to *retry-merge* paths and historical reports, not to the ordinary serve path — a distinction I should have drawn the first time.

**B — 115 (down-graded from my own framing).** Acts appear as three buckets with `scene_count: 0` for a one-scene script even though beat bucketing works for both attached features (7/11/4 and 1/7/3). Combined with gap 81 this is a **display** behaviour on tiny scripts, not an analysis defect; my original wording implied the act model was broken. Grade **B**, severity cosmetic.

**Where I was too kind to myself:** I described the demo-run findings (87–89) as "source-confirmed" when the underlying report content came from a canned stand-in. Only 87's *mechanism* (a detail absent from the script reaching the rendered report) is demonstrated independently of model quality; 88 and 89 are renderer omissions confirmed by source reading, which is **C**, not A. Correcting that here rather than letting the earlier paragraph imply stronger evidence.

**Where I was too harsh on the code:** the same pass showed the summary/queue/`/report` arithmetic agreeing, the parser surviving both real PDFs for the third time, the CLI creating and reading a project cleanly, and root lint passing. The codebase is more disciplined than my register's tone suggests. Almost every defect I found is a *composition* failure — two honest components disagreeing at a seam — rather than sloppy local logic. That is worth saying plainly, and it also explains why the fixes are contracts rather than patches.

## 11. Final grading ledger for the register as it stands

After all three passes, with duplicates collapsed and withdrawals applied:

| | Count | What they are |
|---|---|---|
| **A** — defended under questioning | 20 | 1, 3(partly), 4, 18(store-level), 21, 23, 25, 44, 51, 52, 61, 62, 63, 64, 65, 70, 72, 77, 87, 113 |
| **B** — real mechanism, constructed or conditional | 34 | the concurrency, credential, publication and provider families |
| **C** — source inference / contract asymmetry | 18 | 91, 94, 98(partly), 99, 104(bounded), 105, 107, 111, 115 |
| **D** — opinion, docs, housekeeping | 22 | 22(known), 67, 73, 74/75, 76, 79, 80(design), 81, 82, 83–86, 92, 95, 96, 97, 100, 103, 112 |
| **W** — withdrawn | 5 | 103 as written, 104 as written, 91 as framed, 67 as filed, 109 |

The twelve "carry real weight" items from §9 stand, with **113** added as a thirteenth. Nothing in this critique changes the recommended order in §6; it changes my confidence labels, which is what the user asked for.

**One-line answer to the user's question:** the serious findings are genuine and independently reproduced; roughly half the register is conditional or inferential and should never have been presented with the same weight; four entries were wrong and are withdrawn; and the single biggest real gap was mis-numbered and under-weighted until this critique. The remaining repo sweep continues on the corrected standard.

## 12. Fourth pass — the frontend/security surface, graded before filing

Continuing on the corrected standard, I checked the one large ungraded surface (the SPA document, its headers and the demo app) and am recording results *including the negatives*, because a sweep that only reports problems distorts the picture.

**Headline security posture is better than my register's tone implied — grade: no gap.** The root document carries a strict CSP (`default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'`), `nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-cache`, zero inline event handlers in `index.html`, and no external origins except the SVG namespace and localhost. Combined with the Host guard, the capability token and the loopback bind already traced earlier, this is a deliberately hardened local app, not a naively exposed one. I should have said so the first time I wrote about security rather than listing the exceptions only.

**C — 116. `X-Frame-Options` is absent, and the CSP's `frame-ancestors 'self'` covers the same need in modern browsers.** This is not a defect: CSP frame-ancestors supersedes XFO where supported, and the app targets a local modern browser. I note it only so nobody "fixes" it by adding a header that contradicts the CSP. No action; **no gap**.

**A — 117. The coverage gap I can still prove is the one that matters least often but most visibly: a page that fails to parse shows a numeric badge with no explanation in one surface.** Already recorded as 47/87 in spirit; not filing a duplicate. The pattern from this pass is that my remaining findings are mostly duplications of the composition seam, which is itself evidence that the register is close to saturated for *code-level* issues.

## 13. Stop rule — what "swept" means now, stated honestly

I have now walked every Python module, both attached screenplays, the JSON stores under fault injection, the Flask routes under concurrency, the CLI, the packaging/CI config, the knowledge base inventory, the frontend document and headers, and the demo model end to end. Re-reading my own findings, the last several batches produced **no new mechanism** — only new instances of the same handful of seams. That is the practical signal that a code sweep is saturated: not that nothing more can be found, but that findings stop being independent.

What genuinely remains, and why I am not going to fake completeness on it:

1. **Real-model behaviour** — accuracy, latency, Sameer/Sushruta voice, disagreement quality, multilingual output. Requires an endpoint the user runs. No local probe substitutes, and the demo model must never be presented as evidence.
2. **Audience reception** of Darshi and Pain 3 — the user's own open question. A code sweep cannot answer it, and I will not infer it from structure.
3. **Assistive-technology behaviour** — screen-reader output specifically, as opposed to the DOM assertions the browser suites make.
4. **Non-Linux platforms** — the Windows-specific paths are well-commented in source but every failure I could reproduce was on Linux; file-locking, sharing-violation and path-case behaviour remain untested here.
5. **Preview-lab HTML internals** and the design archive — prototype code, explicitly not the product.

## 14. What I would now tell the writer in one paragraph

Your revisions are not safe yet: switching drafts deletes them, and that is the first thing to fix, ahead of every clever analysis finding in this document. A crafted draft name can read and overwrite another project — small fix, high value. Your report can describe a script you are not editing, and your exported Markdown will not tell you when a finding is unsupported. Your premise card, the one place you state what you meant, is saved and never read by the analyzer, which is why both collaborators feel like they are guessing. Everything else in these 117 entries is either conditional, cosmetic, or something the codebase already documents as a trade-off — and the codebase, on re-reading, is more careful than the length of this register suggests.

## 15. Fifth pass — secrets exposure, verified negative, and the final grade

**No gap — the config surface withholds secrets correctly.** With a synthetic API key and capability token set in the process, `GET /api/config` returned `api_key_set: true` and no key, no token, and no field that could be mistaken for one (`api_key`, `token` absent from the payload entirely). This corroborates the in-repo claim rather than contradicting it, and it is the sixth reproduced *negative* in this critique. Filing it here matters: a register that lists only failures gives a reader a false picture of risk, and this project's secret handling on the read path is deliberate and correct.

**A — 118 (final new finding, low severity, kept because it is real).** `/api/config` returns `allow_remote` and `connection_mode` as plain booleans, while the settings UI explains the privacy consequence in prose. A scripted client can enable remote use and learn nothing about what leaves the machine from the API alone. This is not a defect in the app's behaviour — the UI does explain it — but any future client that is not this SPA gets no machine-readable statement of consent scope. **Recommendation:** add a `privacy` block (`{sends_script_off_machine: bool, destination: origin, credentials_scope: origin}`) so the promise travels with the configuration surface. Grade **A**, severity informational.

## 16. Closing statement on genuineness

Asked to be a self-critique of how genuine these gaps are, the honest answers are:

- **The data-safety findings are genuine and I re-proved four of them this session** through the real application, not through stubs. Nothing in the critique weakens them.
- **The most serious finding was under-weighted for most of this review.** Draft-name containment (62) lets one project read and overwrite another; it sat behind dozens of weaker entries. That is a failure of judgement, not of evidence.
- **Roughly half the register is conditional or inferential** and was written in the same voice as the release blockers. That was the register's real defect: uniform tone over non-uniform evidence.
- **Four entries were wrong** (103, 104, 91 as framed, 67 as filed) and are withdrawn; a fifth (109) dissolved on verification. I would rather show those than quietly delete them.
- **Six reproduced negatives** (CI-parity lint, chat read shape, CLI round-trip, secret withholding, header posture, summary/queue arithmetic agreement) belong in the record too, because they bound how bad the codebase actually is.
- **The remaining gaps are not code-level.** They are model quality, audience reception, assistive technology and non-Linux behaviour — all of which need the writer's own environment, and none of which I can manufacture here.

The repo sweep is complete on the corrected standard: 118 numbered entries, of which thirteen carry real weight, 34 are conditional, 18 inferential, 22 cosmetic or opinion, and 5 withdrawn. The coordinated fix order in §6 of this file and §9 of `INTEGRATED_PLAN_CRITIQUE.md` is what I would defend.

## 17. Sixth pass — the areas §13 named as remaining, now actually swept (with grades)

Continuing on the corrected standard, and grading each as I collect rather than afterwards.

**A — 119. A partially corrupted knowledge-base install fails the whole analysis instead of degrading it.** `KnowledgeBase._load` has no per-file error handling: one malformed JSON file among the 26 raises `JSONDecodeError`, one schema-invalid entry raises `TypeError` from `Rule(**e)`. Driving the real paths: an analyze run with a corrupted rules directory fails with `OrchestratorError: Analyze stage failed: Expecting property name…` and the webapp answers **502** with that parser message as the writer-facing text; calling `/api/projects/<name>/report` afterwards answers **400 "Analysis hasn't completed for this project yet."** even though the previous good report is still on disk and untouched. Zero rules (an empty directory) is accepted silently. So the failure modes are: **all**, **none**, or **one bad file kills everything** — and every one of those paths fails closed with a message about the writer's request rather than about the install. Meanwhile `rules_context.rule_count()` already distinguishes `None` ("cannot enumerate") from `0` ("grounding missing") and the pipeline can report the latter, so the components know how to do this. **Recommendation:** load per file, collect failures, keep the rules that loaded, and surface a one-line install warning ("N of 263 craft rules failed to load from …") in `analyze` and in `/api/health`; never turn a broken install into a failed analysis of the writer's script. Grade **A**, severity medium — it needs a corrupted install to trigger, but the recovery story is wrong when it does.

**A/no-gap — 120. The Python floor is honest.** Every module parses under `feature_version=(3,10)` except one test file, which begins with a UTF-8 BOM: `tests/test_h7_chat_fix.py`. That is **not a compatibility bug in the product** — pytest reads it and the 5 tests pass in a clean install — it is a portability wrinkle (a BOM in a source file is legal for `ast.parse(open(..., encoding='utf-8-sig'))` and for CPython's importer, and some editors strip it). Withdrawn as a gap; recorded as a one-line hygiene note. The declared `requires-python = ">=3.10"` matches the code.

**A/no-gap — 121. The JS test story is reproducible from a clean checkout, with one documentation trap.** `node --test tests/js/` fails (Node 22 treats a bare directory as a module path — the suite's own header warns about exactly this), `npm ci && npm test` passes **134/134** across both JS suites after installing `jsdom` from the lockfile, and `tests/js/*.test.js` alone passes 24/24. The docstring inside `preview-ink-layer/tests/dom.test.mjs` claims "127 tests"; the real total is **134**. So: reproducible, but the number in the docs has already drifted, and the obvious way to run the suite (`node --test tests/js/`) fails. **Recommendation:** point the docs at `npm test` only, and derive the count from the run rather than typing it. Severity **D**.

**C — 122. The four remaining "ungraded" areas are ungradable here, and I am not going to invent activity for them.** Real-model behaviour, audience reception of Darshi and Pain 3, screen-reader output, and non-Linux filesystem semantics each need something this sandbox does not have (a model endpoint, a reader panel, a Windows host). Preview-lab HTML internals I did read at the level that matters (routes, data exposure, session writes — gaps 95–96). Naming them again here, after grading everything else, is the honest terminus: the sweep is complete as a **code and behaviour** review, and incomplete as a **quality** review by construction.

## 18. Where this leaves the count

- Register: **118 numbered entries + 119–122 collected in this file**; 5 withdrawn, 3 re-graded, 13 carrying real weight (now 14, with 119).
- Evidence mix after six passes: **~21 A**, **~34 B**, **~19 C**, **~22 D**, **5 W**.
- New graded negatives this pass: Python floor (**no gap**, one BOM in a test), JS reproducibility (**no gap beyond docs**, 134 not 127), KB zero-rule state deliberately distinguishable (good design), and the empty-rules case accepted silently (part of 119).
- One genuinely new class of risk found: **a corrupted rules install converts into a failed analysis and a refused report**, which belongs in the fix order immediately behind containment and revision safety, because it is cheap to fix and it is the difference between "your install needs repair" and "your script cannot be analysed."
