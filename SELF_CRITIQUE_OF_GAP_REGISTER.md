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

*(109 was withdrawn during this pass and its argument now lives in `ARCHIVE_NOT_GAPS.md` §4. The entries below it survive.)*

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
> **Superseded.** These aggregate rows were a reading aid and two of them were wrong. Every entry now
> has its own grade in **`ENTRY_GRADE_TABLE.md`**, counted by parsing rather than by memory: **128 entries,
> 51 A / 43 B / 12 C / 12 D, 6 withdrawn, 4 proven negatives**. Where these rows disagree with that table,
> the table wins. Kept for the record because silently deleting my own wrong numbers is the habit this
> document exists to criticise.

| **A** — defended under questioning | 23 | 1, 3(partly), 4, 18(store-level), 21, 23, 25, 44, 51, 52, 61, 62, 63, 64, 65, 70, 72, 77, 87, 113, 118, 119, 123 |
| **B** — real mechanism, constructed or conditional | 34 | the concurrency, credential, publication and provider families |
| **C** — source inference / contract asymmetry | 18 | 91, 94, 98(partly), 99, 104(bounded), 105, 107, 111, 115 |
| **D** — opinion, docs, housekeeping | 22 | 22(known), 67, 73, 74/75, 76, 79, 80(design), 81, 82, 83–86, 92, 95, 96, 97, 100, 103, 112 |
| **W** — withdrawn | 5 | 103 as written, 104 as written, 91 as framed, 67 as filed, 109 |

These rows do not sum to the numbered register, and I am not going to make them. Merged duplicates (74/75, 37–42), entries graded in the same prose as a neighbour, and the three proven non-gaps (120–121 and the SPA header check) mean the row counts are **approximate to within one or two**; the numbers listed in each row are the authoritative statement, the totals are a reading aid. Anyone who needs exact per-entry grades should count the lettered labels in §7–§17 rather than trust this table.

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

Your revisions are not safe yet: switching drafts deletes them, and that is the first thing to fix, ahead of every clever analysis finding in this document. A crafted draft name can read and overwrite another project — small fix, high value. Your report can describe a script you are not editing, and your exported Markdown will not tell you when a finding is unsupported. Your premise card, the one place you state what you meant, is saved and never read by the analyzer, which is why both collaborators feel like they are guessing. Everything else in these 124 entries — 43 of them reproduced only under constructed conditions, 21 by inference or opinion — is either conditional, cosmetic, or something the codebase already documents as a trade-off — and the codebase, on re-reading, is more careful than the length of this register suggests.

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

The repo sweep is complete on the corrected standard: 118 numbered entries, of which thirteen carry real weight, 34 are conditional, 18 inferential, 22 cosmetic or opinion, and 5 withdrawn. *(Superseded twice. §17–§18 added 119–122; §19 added 123–124. And the per-entry counts in this paragraph — 34 conditional, 18 inferential, 22 cosmetic — were wrong: recounted from `ENTRY_GRADE_TABLE.md`, the live register is 51 A / 43 B / 12 C / 12 D. I had been counting constructed-but-real entries as inferential, which made my own critique look stricter than it was.)* The coordinated fix order in §6 of this file and §9 of `INTEGRATED_PLAN_CRITIQUE.md` is what I would defend.

## 17. Sixth pass — the areas §13 named as remaining, now actually swept (with grades)

Continuing on the corrected standard, and grading each as I collect rather than afterwards.

**A — 119. A partially corrupted knowledge-base install fails the whole analysis instead of degrading it.** `KnowledgeBase._load` has no per-file error handling: one malformed JSON file among the 26 raises `JSONDecodeError`, one schema-invalid entry raises `TypeError` from `Rule(**e)`. Driving the real paths: an analyze run with a corrupted rules directory fails with `OrchestratorError: Analyze stage failed: Expecting property name…` and the webapp answers **502** with that parser message as the writer-facing text; calling `/api/projects/<name>/report` afterwards answers **400 "Analysis hasn't completed for this project yet."** even though the previous good report is still on disk and untouched. Zero rules (an empty directory) is accepted silently. So the failure modes are: **all**, **none**, or **one bad file kills everything** — and every one of those paths fails closed with a message about the writer's request rather than about the install. Meanwhile `rules_context.rule_count()` already distinguishes `None` ("cannot enumerate") from `0` ("grounding missing") and the pipeline can report the latter, so the components know how to do this. **Recommendation:** load per file, collect failures, keep the rules that loaded, and surface a one-line install warning ("N of 263 craft rules failed to load from …") in `analyze` and in `/api/health`; never turn a broken install into a failed analysis of the writer's script. Grade **A**, severity medium — it needs a corrupted install to trigger, but the recovery story is wrong when it does.

**A/no-gap — 120. The Python floor is honest.** Every module parses under `feature_version=(3,10)` except one test file, which begins with a UTF-8 BOM: `tests/test_h7_chat_fix.py`. That is **not a compatibility bug in the product** — pytest reads it and the 5 tests pass in a clean install — it is a portability wrinkle (a BOM in a source file is legal for `ast.parse(open(..., encoding='utf-8-sig'))` and for CPython's importer, and some editors strip it). Withdrawn as a gap; recorded as a one-line hygiene note. The declared `requires-python = ">=3.10"` matches the code.

**A/no-gap — 121. The JS test story is reproducible from a clean checkout, with one documentation trap.** `node --test tests/js/` fails (Node 22 treats a bare directory as a module path — the suite's own header warns about exactly this), `npm ci && npm test` passes **134/134** across both JS suites after installing `jsdom` from the lockfile, and `tests/js/*.test.js` alone passes 24/24. The docstring inside `preview-ink-layer/tests/dom.test.mjs` claims "127 tests"; the real total is **134**. So: reproducible, but the number in the docs has already drifted, and the obvious way to run the suite (`node --test tests/js/`) fails. **Recommendation:** point the docs at `npm test` only, and derive the count from the run rather than typing it. Severity **D**.

**C — 122. The four remaining "ungraded" areas are ungradable here, and I am not going to invent activity for them.** Real-model behaviour, audience reception of Darshi and Pain 3, screen-reader output, and non-Linux filesystem semantics each need something this sandbox does not have (a model endpoint, a reader panel, a Windows host). Preview-lab HTML internals I did read at the level that matters (routes, data exposure, session writes — gaps 95–96). Naming them again here, after grading everything else, is the honest terminus: the sweep is complete as a **code and behaviour** review, and incomplete as a **quality** review by construction.

## 18. Where this leaves the count

- Register: **128 numbered entries**; 6 withdrawn, 4 re-graded, 14 carrying real weight (1, 3, 4, 18, 21, 23, 61–65, 87, 106, 113, 119), graded one by one in `ENTRY_GRADE_TABLE.md`: 51 A / 43 B / 12 C / 11 D.
- Evidence mix after six passes: **~21 A**, **~34 B**, **~19 C**, **~22 D**, **5 W**.
- New graded negatives this pass: Python floor (**no gap**, one BOM in a test), JS reproducibility (**no gap beyond docs**, 134 not 127), KB zero-rule state deliberately distinguishable (good design), and the empty-rules case accepted silently (part of 119).
- One genuinely new class of risk found: **a corrupted rules install converts into a failed analysis and a refused report**, which belongs in the fix order immediately behind containment and revision safety, because it is cheap to fix and it is the difference between "your install needs repair" and "your script cannot be analysed."

## 19. Seventh pass — consistency and the two surfaces I had flagged but not fired

Two things to record before this file is treated as finished.

**The grades in §11 were one pass stale, and I have corrected them rather than leaving the contradiction.** §11 is the table a reader will use; it was written before 113 and then before 119, so it said 20 grade-A entries while §10 and §17 each argued a new one. It now carries **23** (113, 118, 119 and 123 added without the table being rewritten) and a note that the row totals do not sum to the numbered register, because merged duplicates and non-gaps make them approximate. A ledger that disagrees with itself is worse than one with fewer rows, and I was doing the exact thing I faulted the register for: appending new confidence at the tail without reconciling the head.

**A — 123. `/api/health` answers `{"status": "ok"}` for a corrupted rules install, and the one route that reads the rules fails with a raw parser string instead of the message it was designed to give.** Reproduced in a single run: I copied `rules/` (26 files, 263 rules) to a temp directory, added one malformed file, pointed the app at it and cleared the loader cache. `/api/health` → **200** `{'status': 'ok', 'demo_model': True, 'server_url': 'http://127.0.0.1:8099', 'code_rev': '…'}` — nothing about the install. `/api/rules/<any-id>` → **400** `Expecting property name enclosed in double quotes: line 1 column 3 (char 2)`, i.e. the parser's text handed to the caller, when the route already has a designed answer for a *missing* install (503, "The knowledge base isn't installed, so this rule cannot be looked up"). So the failure is not merely ungraded, it is **the wrong failure**: absent KB is explained, broken KB is a JSON error.

Where I overstated this before correcting it in the same pass: I wrote that the health check "says nothing about the model destination". It does report `server_url` and `demo_model`. What it does not report is the rules state, and `allow_remote`/`connection_mode` live only on `/api/config` (gap 118), so a health-only client cannot tell a permitted-remote desk from a local one without parsing the URL. That is the accurate, narrower claim. The analyze-and-report half of this story was reproduced in a **separate** earlier run and belongs to **119**; I am not merging two runs into one sentence. **Recommendation:** add `rules: {loaded, expected, failures}` to `/api/health` from the fault-tolerant loader 119 asks for, and let `/api/rules/*` answer 503 for a broken install exactly as it does for an absent one. Grade **A**, severity low — it degrades diagnostics, not the script — but it is the cheapest place to see 119 and it makes 119 visible before the writer runs anything.

**D — 124. The two attached PDFs are asserted as the real material but the register never states what "verified against them" means for a reproduction.** Every parse claim here was checked on those two documents, and that is a synthetic-and-single-source basis: two features, one writer, one language mix. It is enough to say the parser survives real input; it is not enough to say it survives *screenplays*. I am recording the bound rather than letting "both attached scripts" read as a corpus. No action; this belongs in the caveat block, not the fix list.


## 20. Eighth pass — the last three modules the ledger still marked "inventory only"

`stt.py`, `webapp_demo.py` and the whisper server were the only product modules left at `[I]`. Reading them
and driving the real routes, in the same pass as grading.

**A — 125. `/api/stt/languages` advertises an external transcription engine the guard will then refuse.** With `SCREENPLAY_STUDIO_WHISPER_URL` set to a remote host, `GET /api/stt/languages` answers **200** `{"engine": "whisper-server", "languages": [...]}` — a plain statement that dictation will go to a whisper server. `POST /api/stt` then answers **503** `SCREENPLAY_STUDIO_WHISPER_URL must point at a LOCAL whisper server`. Both were reproduced back to back on one client. The guard itself is **correct and well built** (`net_guard.is_loopback_url`; I confirmed `http://127.0.0.1@evil.com` is refused, which the old prefix check would have allowed) — the defect is that the *capability* endpoint never calls the guard, so the writer is told the engine is the whisper server even when that configuration is unusable, and the message explaining why arrives only after they have recorded a paragraph. `EXTERNAL_WHISPER_URL` is also read once at import, so a fix that rewrites the env var at runtime changes nothing until restart. **Recommendation:** run `_assert_local_whisper` when computing the engine label, report `engine: "faster-whisper"` plus an explicit `misconfigured: <reason>` instead of naming a server it will refuse, and surface that in the dictation UI before the microphone is offered. Grade **A**, severity low: it costs one wasted dictation attempt, and only in a hand-edited configuration.

**B — 126. There is no ceiling on the audio that reaches the transcriber, and no check that it is audio.** `MAX_CONTENT_LENGTH` is 256 MB, chosen for screenplay uploads, and `/api/stt` inherits it: a 3 MB byte blob was accepted to the transcription path without complaint (it only stopped at the missing engine), and with an engine installed it would be written to a tempfile and decoded. Nothing inspects the container or duration first, and the failure the writer eventually sees is the decoder's. Related and worse in principle: if `SCREENPLAY_STUDIO_WHISPER_URL` points at an external process, the **whole file** is POSTed to it with a 120-second timeout before any size or format check. Grade **B** — the "wrong file" hazard is real, the "sends recordings off-machine" hazard requires pointing the env var at a local server the user themselves started, and my probes could not get past the engine check to measure the decode path. **Recommendation:** reject non-audio containers by magic bytes, cap the upload at a stated duration/byte limit with its own message, and decode with a timeout. Severity low.

**Negatives from the same pass, recorded because a module review that only lists faults distorts the picture:**

- **The whisper URL guard survives the exact bypasses that motivated it.** `http://127.0.0.1@evil.com` and a suffix-attack host are both refused before any request is made; the comment in `stt.py` describing the old prefix-check bug is accurate and the fix is real.
- **`/api/stt` fails with a sentence in every state I could create**: no `audio` part → 400 with instructions; unknown language → 400 listing the four supported; zero-byte blob → 400 "No audio data received."; engine absent → 503 naming the exact `pip install`; unreachable local server → 503 naming the URL and the fix. Five distinct, actionable failures, no tracebacks, no parser output. This is the standard 110 and 119 fall short of, in the same codebase.
- **`webapp_demo.py` is exactly as safe as its docstring claims.** Driving `main()` with a stub shows `['--demo-model', '--port', '8123']` handed to the canonical `main`, so the capability token is minted, the bind stays loopback, and `PORT` maps correctly. The audit comment describing the old ALL-interfaces bug is honest, and the bug is genuinely fixed.
- **The forced-language retry is deliberate and tested** — an empty transcript under a forced language retries once with auto-detect, and genuinely silent audio still returns empty. Two tests cover both halves.

The consequence for the ledger: after this pass, **no product module remains at `[I]`**. What remains unreviewed is what §13 already listed — real-model behaviour, audience reception, assistive technology, non-Linux platforms, preview-lab internals — and one environment gap I can now state precisely: **playwright is not installed here, so all 30 `e2e_browser_*.py` suites have never been executed by me. Every UI-behaviour claim in this register is source-, DOM- or test-client-based, never a rendered page.** That is gap 17's grade resting on recorded results rather than a run of mine, and it is the last thing standing between this sweep and a clean claim.


## 21. Ninth pass — packaging and CI, and the one gate this sandbox cannot open

The last mechanical item I had listed as pending was packaging execution. Done, by building and installing
rather than reading.

**D — 127. The wheel is correct; the only weakness is how CI reaches that conclusion.** `python -m build --wheel`
now takes the step every guard test assumes, and the result holds up: **180 files, 4.04 MB**, 26 rule files
(263 rules) and `knowledge_base/index.json`/`schema.json` present, the whole SPA present under
`screenplay_studio/webapp/`, `app.js`, `core.js`, both CSS files and the fonts with it, **no** tests, no PNGs and
no analysis scratch files (`graph.json` is genuinely gone, which closes half of gap 86 — that finding's
"shipped inside importable packages" claim is false for the built artefact and true only for the source tree).
Installing that wheel into a clean `--target` and importing it from outside the repo: `/` → **200, 48 KB**,
`/api/health` → 200, `/api/config` → 200, `/api/stt/languages` → 200, and `KnowledgeBase()` loads **263 rules
from the wheel**. So the packaged app boots. The gap is that the ten `test_packaging_data_files.py` tests inspect
the source tree, not a wheel, so a `MANIFEST.in` or `package-data` mistake could pass them and still break an
installed copy — the suite's confidence is one step stronger than its evidence. **Recommendation:** make one CI
job install the wheel into a temp prefix and hit `/` plus `/api/health`, which is ~8 lines and converts gap 86
from "checked in source" to "checked as shipped." Grade **D**, severity low.

**Negative worth stating:** `_API_TOKEN` is `None` in this probe *by my own choice* to allow scripted reads; the
canonical launch mints a token, and I did not re-verify that in the installed-wheel case. So this pass proves
the artefact is complete and bootable, not that the installed copy's security posture matches the source one.

**The browser gate cannot run here, and now I can say why precisely.** `playwright` installs, but
`python -m playwright install chromium` fails: `cdn.playwright.dev` is unreachable from this sandbox ("Client
network socket disconnected before secure TLS connection was established"), and there is no system Chromium or
Firefox to point at instead. That is a hard environment limit, not a decision I made, and it is the honest end
of what a sweep can do here: **all 30 `e2e_browser_*.py` suites remain unexecuted by me**, so every UI claim in
this register is source-, DOM- or test-client-based, and gap 17's grade rests on the suite's recorded results
rather than a run of mine. Anyone with network access can close this in one command; I cannot manufacture the
output.


## 22. Self-critique of §20–§21, applied before this file was pushed

Grading as I collect only helps if I also argue with the grades I just gave. Three things:

**126 is weaker than I wrote it, and I am downgrading it on the spot.** "No ceiling on the audio that reaches the
transcriber" is true, and it is also how most local dictation endpoints behave; the 256 MB ceiling is inherited
from uploads, not chosen badly for audio. The part with real substance is narrower: nothing checks magic bytes, so
whatever the writer selects is written to a tempfile and handed to a decoder, and the failure they eventually see
is the decoder's rather than "that isn't an audio file". The "whole file POSTed to an external server" half is not
a privacy hole — the user started that server themselves and the guard proves it is on this machine. **Revised
grade: C/D, severity informational, and I would not schedule it.** It stays in the table because it was
reproduced, and the table is not a fix list.

**125 stays A but is small.** Two endpoints disagreeing about whether dictation is configured is a real
inconsistency I drove back to back, and the fix is three lines. Calling it "low severity" is right; calling it
anything more would be the uniform-tone failure this document exists to criticise.

**127 is the one that would actually change behaviour in CI, and it is graded D only because nothing is broken
today.** A packaging guard that inspects the source tree instead of the artefact is a guard that can pass while
the product is uninstallable. I verified the artefact by hand this pass; CI does not. That is worth eight lines of
workflow, and it is the only finding from the last three passes I would put on a schedule.

**And the uncomfortable summary of this whole review, now that it is finished:** 128 numbered entries, 118 live,
51 of them reproduced through a real interface — and **not one of them is new since 119.** Passes eight and nine
produced two low-severity findings and one CI improvement. That is the stop rule working as designed, and it is
also the point at which continuing to search would be manufacturing activity rather than doing work. What remains
is a **fix campaign** (§6/§9 order, starting with 62, then revision safety), not more sweeping.


## 23. Tenth pass — the frontend, read rather than rendered (because I cannot render it)

`app.js` is 10,865 lines and `core.js` 206; together with the CSS they are the largest surface this sweep had
still only touched through headers and route reachability. With the browser gate closed (§21), the honest way to
review them is a static read plus the project's own test suites, and to say which of the two produced each
statement.

**No gap — the XSS posture is real, and it is documented in the code rather than in a write-up.** I enumerated
every `innerHTML` sink (63 assignments) and every `${…}` interpolation that reaches one. What I found:

- Assistant replies go through `formatMessageContent` in `core.js`, which **escapes `&`, `<`, `>` first** and only
  then applies `**bold**` and `- ` bullets. The ordering matters and the code comments say why.
- Anything carrying writer or model text goes through `escapeHtml`, which escapes `&` first and covers **both**
  quote characters, so it is safe in an attribute as well as an element body. The docstring names the exact
  historical bug (`<img src=x onerror=…>` in a dialogue line) it was written to close.
- The handful of **unescaped** interpolations are safe and I checked each one rather than trusting the pattern:
  a static `EXPLORE_CHIPS` icon/label array (developer-authored SVG), numeric `count`/`length` values in the
  stage stepper, and geometry numbers (`W`, `H`, `pad`) inside a generated bar-chart `<svg>`. No model output,
  no project name and no screenplay text reaches `innerHTML` unescaped anywhere I could find.
- `eval` and `new Function` do not appear at all. There is no `document.write`, no `outerHTML`,
  no `insertAdjacentHTML`.
- The streaming path appends tokens with `textContent`, not `innerHTML` — the one place a half-written,
  unguarded model token could land actually uses the safe sink.
- Deep-link routing (`#/project/view/scene`) decodes each segment with `decodeURIComponent` and then only
  **compares** the project against the known project list; it never renders the hash. A hostile link cannot
  inject markup, and `correctRoute()` rewrites the address bar when the project is not one the desk has.

**D — 128. The one real weakness is that the XSS posture is enforced by convention, not by a test or a type.** The
code comments say `escapeHtml` is "the ONE helper every `innerHTML` sink must route untrusted text through", and
today that holds — but nothing fails when a future commit interpolates `finding.issue` or an idea title directly
into a template string. There is no lint rule, no wrapper element that escapes by construction, and no test that
greps for `${` inside a template assigned to `innerHTML`. This is the same shape as gap 127: the discipline is
real and the guard is missing, so a correct codebase has an unenforced invariant. **Recommendation:** add one test
that asserts no `innerHTML` assignment in `app.js`/`core.js` contains an unescaped `${…}` outside an allowlist
(the chip mark-up and the SVG geometry), or move the two remaining raw sinks behind a tiny `safeHtml` tag
function. Grade **D**, severity low — nothing is exploitable today; it is a regression guard for the commit
that has not been written yet.

**What I still cannot say.** Reading 11,000 lines is not rendering them. Layout at 1440×900, focus order under a
real screen reader, the hover-revealed toolbar timing that `NOTES.md` describes at length, and whether the
manuscript-first desk actually feels like a manuscript are all outside what a static read can establish. The two
findings from this pass are about *structure and invariants*; the journey itself remains unaudited, and the visual
concepts remain unapproved, which is where this review started.


## 24. Eleventh pass — file-by-file authenticity review, and the register pruned

The user's instruction changed the job: not "find more" but "go through what is noted, check it against the repo
entry by entry, and leave only genuine gaps". Done, and the result is a smaller register that I trust more.

**Method.** Every numbered entry was re-read against the code it names, and where a claim could be cheaply
re-run it was: `quotematch.normalize_text` (23), the Telugu cue ranges in `heuristics.py` (24), the `int(page//5)`
segment index (27), the "No significant findings" branch in `report.py` (47), `add_to_stash`'s `text[:4000]` (19),
`beatboard.has_board`/`get_order` (20), `activate_draft` and `draft_dir` (62), and the tracked scratch files (86).
All of those hold on re-test today. Findings 106/107/108 were re-traced to the analyzer entry signature; they
also hold — which is exactly why the classification question below matters.

**The distinction the register had stopped making.** Two axes were collapsed into one. *Grade* answers "how sure
am I that I saw this?" The new axis answers "**is this a gap at all?**" Four entries were excellently evidenced and
still not gaps: **22** (FDX lossiness is the format's limit and the exporter documents it), **76** (lock sidecars
are how the lock works), **127** (the wheel is correct; CI merely does not prove it), **128** (escaping is correct;
nothing enforces the convention). Four more were capability wishes, not defects: **97** (recovery room) and
**106–108** (intent never reaching the analyzer). Deleting evidence would have been wrong; leaving them numbered
as defects was also wrong. They are archived, in full, with the check that justified each removal.

**What I was most wrong about, stated plainly.** I have called 106 "the single most consequential product gap in
the review" and put it in the severe list beside a containment hole that lets one project read another. That
comparison was not a judgement about severity; it was an accident of the word *gap* covering two different things.
A writer cannot hit 106 the way they hit 62: 62 corrupts their work, 106 means the tool never asked them what they
meant. The register now says so — 106 is product direction, and the severe list is 1, 3, 4, 18, 21, 23, 61–65, 87,
113, 119. That is a genuine correction, not a rewording.

**Numbers after pruning** (computed from `ENTRY_GRADE_TABLE.md`, not typed): **126 entries — 108 genuine gaps,
4 known trade-offs, 4 product-direction, 6 withdrawn, 4 tested non-defects.** Of the 108 genuine: **48 grade A, 43
B, 10 C, 7 D.** Eight entries left the register, one (75) merged into 74, and three titles were corrected where the
headline claimed more than the body supported: 86 no longer says the scratch files ship in the package (they do
not — I built the wheel), 92 no longer implies the demo's canned replies say anything about the collaborators, and
95 no longer claims the Design Lab has "no separation" from the writer's desk (it shares the Host guard and token,
and its session is isolated).

**What this changes about the plan.** The fix order is untouched — 62, then revision safety, then publication
truthfulness, then 119. The intent work is still the thing worth evaluating first, but it is now filed as a
decision the writer and the collaborator designs should take, not as defect 106. And the two guard-strength items
(127, 128) are the only entries that would prevent a regression rather than repair anything, which is why they sit
at the bottom of the fix order rather than the top.


## 25. What the prune does not fix — honest closing note

Pruning made the register shorter and more honest. It did not make the remaining entries better evidenced, and
three limits survive intact:

1. **Ten entries are still grade C** — read in code, never driven. They are the ones most likely to be wrong, and
   nothing about this pass changed that. They are now marked as such per entry instead of being averaged away.
2. **Every UI claim still rests on source, DOM or test-client reading.** The browser gate cannot open in this
   environment (`cdn.playwright.dev` unreachable, no system browser), so 17 and the browser half of 5 remain
   unverified by me. A networked machine settles that in one command.
3. **Four areas cannot be graded here at all** (122): real-model behaviour, audience reception of Darshi and Pain 3,
   screen-reader output, non-Linux filesystem semantics. No amount of further pruning reaches them.

What I would now defend, in one sentence: **the software is careful in the small and inconsistent at the seams** —
fourteen places where two honest components disagree about which draft, run or generation a claim belongs to, plus
one containment hole (62) and one privilege-free but real evidence falsehood (23, where a different Telugu word
verifies as an exact quote). Everything else in the 108 is either conditional, cosmetic, or a documentation
mismatch, and it says so per entry now.


## 26. First fix landed — 62, verified, with what self-critique caught on the way

Containment is closed. `screenplay_studio/diff.py:40` — `draft_dir()` — now validates the draft name at the single
chokepoint every path construction goes through, using `jsonio.check_safe_id`, the ASCII-id rule the project and
idea stores already used. Sentinels (`None`, `""`, `"active"`) are rejected explicitly because they mean "the live
root files", not a stored snapshot. Five tests were added to `tests/test_diff.py`.

**The fix is one function; the verification is where the work was.** Four things I had to catch in myself:

1. **My first four tests were vacuous and I only found out by reverting the fix.** With `diff.py` restored to its
   pre-fix state, `1 failed, 4 passed` — which means four of my five new tests would have passed against the bug
   they were written to catch. Cause: project titles become directory names (`Other Project` → `Other_Project`), and
   I had hardcoded `../../Other/drafts/v2`, so those tests asserted 400 for a path that never existed. A test that
   cannot fail is worse than no test, because it advertises coverage.
2. **The second attempt was still vacuous, for a subtler reason.** Even with the right name, an activation probe
   returned 404 — because `<project>/drafts` **did not exist**, and `drafts/..` cannot resolve through a
   non-existent directory. A project that has never been revised is not traversable; every writer past their first
   revision is. The helper now uploads a second draft first, which is the ordinary state, and asserts the attack
   target exists before asserting anything about it.
3. **The `/diff` and `/compare` vector was worse than my register entry said.** The entry described a traversal
   *write* via activate. In fact both diff routes took the name in a query parameter and returned **200 with the
   other project's script** — a read, no activation needed, and a live pre-fix reproduction showed
   `leaked=True` for both. That is now covered by its own test, and the entry says so.
4. **An already-poisoned manifest is survivable but not repaired.** A project whose `project.json` already holds a
   traversal string in `active_draft` still lists and opens (200), and `draft_dir` only raises when that name is
   actually resolved. Reads that do not resolve it are unaffected; the bad name is inert rather than repaired. I did
   **not** add a migration, because writing one would touch writer-owned manifests on upgrade and I cannot test that
   against real archives. This is a deliberate limit, not an oversight, and it belongs in the fix notes.

**Verification, stated exactly:**

- The attack, at the correct relative depth, through the real route: `400` for `../../Other/drafts/v2`,
  `../Other/drafts/v2`, `..`, `/etc/passwd`, `draft 1`, `a/b`, `drafts/v2`; the whole workspace tree was
  **byte-identical** afterwards (md5 of every file before and after).
- `/diff` and `/compare` with the same names: `400`, no other-project text in the body; pre-fix both were `200`
  with it.
- The flows the fix protects still work, compared **before and after** the change with the same script:
  upload → `draft-1`, activate `original` → 200, activate `draft-1` → 200, unknown name → old 400, `/diff` and
  `/compare` → 200, and the restored source text is the right draft's.
- Against pre-fix code the five new tests give **3 failed, 2 passed**; with the fix, 20/20 in that file.
- Full suite: **2253 passed, 4 skipped**, three consecutive runs; `ruff check .` clean.

**One failure I am not going to wave away.** The first full-suite run reported `1 failed, 2252 passed`, and the
traceback line I captured pointed at a log-reading assertion in the packaging/readiness area. Four subsequent
full runs are green, both affected files pass 3/3 in isolation, and I could not reproduce it with the output I
had. I think it is a timing-sensitive test unrelated to this change — but I have not proven that, and a fix note
that says "flaky, moving on" is exactly the kind of claim this review exists to distrust. Recorded as observed,
not explained.

**What this changes in the plan:** step 1 of the fix order (§6) is done and the register's most serious item is
closed. Step 2 — revisions surviving a draft switch (1, 63, 64, 65) — is untouched and is now the top of the list.


## 27. Second fix — gap 1, the writer's revisions now survive a switch

**What was wrong.** `_reset_derived_state` deleted `working.json`, `edits.json` and `edits.redo.json` on every
draft switch. The UI calls switching non-destructive — the tooltip says it preserves the current draft — and for
applied edits it did not. Edit, switch away, switch back: original text, no undo, no redo.

**The change** (`diff.py`, ~85 lines): `snapshot_active` now copies the three cycle files into the draft's own
snapshot directory under `_working.json` / `_edits.json` / `_edits.redo.json`, and a new `restore_edit_cycle` puts
them back when the writer returns. Deliberately in `snapshot_active` rather than in `upload_new_draft`, so the
guarantee holds for **both** exits from a draft — a new upload and a switch to an older draft. A draft that was
never edited restores nothing and has any inherited cycle member removed, so an undo can never apply to text the
draft never had.

**Self-critique of the fix, before claiming it:**

1. **My first three tests failed for the wrong reason and I fixed them, not the code.** `apply_edit` returns
   `applied` as a *list of replacement dicts*, not a count; `undo_last_edit` returns `undone` as the whole record,
   not a number. Two assertions in my own tests were wrong about the API they were testing. A test that encodes a
   guess about an interface is worth nothing, so I read both functions and asserted on `len(applied)` and on
   `restored`/`failed` instead.
2. **One of the three new tests is not doing what its name suggests, and I left it in knowingly.**
   `test_a_never_edited_draft_does_not_inherit_an_undo_stack` passes **both** before and after the fix, because the
   old code deleted the log and the new code removes it — both give "no edits". It is a guard against a future
   fix regressing the invariant, not evidence for this one. I would rather label it than let a count of "3 tests"
   imply three proofs. The two that matter fail without the fix: `2 failed, 1 passed`, verified by reverting.
3. **I nearly reported a false negative from my own harness.** The end-to-end script posted to
   `/api/projects/<p>/edits` (405 — the real route is `/edits/apply`) and then printed "edit survived: False",
   which looks exactly like the bug. The status code was sitting in the output I had already captured. Reading the
   route table before writing the probe would have saved a round trip; assuming a route name cost more than
   checking it.
4. **Switching is now "restore", not "merge".** If the same draft is edited in two places the whole cycle is
   replaced, not reconciled — the same last-writer-wins shape as gap 74, and I have not changed that. Stated so a
   later reader does not read more into this fix than it does.

**Verification, exactly:**

- Through the real routes: apply an edit (200) → upload a second draft → activate `original` (200) → the edited
  line **is** in the served script → `/edits/undo` (200) → the original line is back.
- The identical script against pre-fix code: edit **gone**, undo answers `400 Nothing to undo`. Same script, same
  server, only `diff.py` changed.
- Full suite **2256 passed, 4 skipped** (three more than before this fix, i.e. exactly the new tests); `ruff` clean.
- The environment reset mid-pass — `/home/user/.venv` vanished — and was rebuilt with `pip install -e ".[ci]"`
  before any of the above was measured. Worth recording because it is the second time, and because a suite run in
  a half-built environment would have been meaningless.

**What is still open in this area, unchanged:** 63 (derived artefacts other than the cycle — the knowledge graph and
character analytics — still stay bound to the outgoing draft), 64 (a failed upload can become the active draft),
65 (a running analysis can publish into a draft the writer has since left). Those are the rest of the step-2
bundle contract; gap 1 was the part that destroyed work in the ordinary case, and it is closed.


## 28. Third fix — 63 and 65, and the limits I am not going to paper over

**63: the bundle, not three files.** `snapshot_active` and activation now move every per-snapshot file, not just
`parsed.json` + the report pair: the knowledge graph, the dismissed-findings store, finding marks, the ambiguous
marks and the last-pass dedup snapshot. A member the snapshot lacks is **removed** from the live project on switch
rather than left behind, because a file that survives a switch is a claim about the draft the writer is now
looking at.

The reproduction was worse than the entry said. The entry described a stale cast appearing; in fact after
uploading a new draft and switching back, `/characters` returned **`[]`** — the graph on disk belonged to the new
draft, and the restored parse no longer matched it, so the writer's original draft lost its cast entirely. Post-fix,
`['ALPHA']` both before and after the round trip.

What is deliberately **not** in the bundle, and why: `sessions/` (a switch does not end a conversation, and chat
threads have their own scope), stash/notes (the writer's material *about* the work, not a product of one
snapshot), and the lock files. The list is "per-snapshot state", not "everything in the directory" — and it is one
function, `_bundle_files`, so the next person can audit the boundary in one place instead of guessing.

**65: the honest fix is a closed door, not a generation tag.** An analysis keeps publishing into whatever the
active draft becomes. Tagging every write with a generation id and refusing a publish whose generation has moved
is the thorough answer — and it changes what "publish" means for every caller, in a module I cannot exercise
against a real model. So I closed the window instead: `/drafts` and `/drafts/activate` answer **409** while the
per-project analysis lock is held, and work again the moment the run ends. That is the same lock `/analyze` and
`/retry-failed` already take, so the check and the run cannot interleave.

**Three limits, stated rather than hidden:**

1. **A lease, not a proof.** If a publish happens just after a switch that raced the lock — a second process, or a
   future worker that does not take this lock — the wrong-draft publication is still possible. Gap 65's mechanism
   is narrowed, not eliminated. The register entry says so rather than claiming it fixed.
2. **The UI has to cope.** A 409 on a draft picker is new behaviour; before, the switch appeared to succeed. Until
   the SPA shows "analysis running — wait", the writer will see a picker that silently refuses. I did not change
   the front end, so this is a real, deliberate follow-up rather than something the backend fix completed.
3. **A switch still races a *completed* run's tail.** `record_analysis` and `_record_pass` run after the lock is
   released in `finally`, so a switch landing in that window can attribute history to the draft the writer moved
   to. Small, and I have not measured it — so I am naming it, not fixing it.

**Verification:**

- Through the real routes: original cast `['ALPHA']` → upload + analyze a second draft → switch back → `['ALPHA']`,
  with `BETA STRANGER` absent. Before the fix the same sequence ended at `[]`.
- With the analysis lock held: activate **409**, upload **409**; after release, activate **200**.
- Five new tests; **three fail without the fixes** and two are positive controls that pass in both states (the
  same discipline as §27 — I am not counting guards as proofs).
- Full suite **2261 passed, 4 skipped**; `ruff` clean. The environment was rebuilt again first — third reset this
  session — because a suite run in a broken environment proves nothing.

### 28b. A test of mine was wrong, and it was the one calling the product a liar

The full suite after this fix reported **1 failed** twice in six runs:
`test_production_readiness.py::TestTheShippedServerIsLoopbackOnly::test_not_reachable_on_a_non_loopback_address`.
The previous pass had already seen this same test fail once and recorded it in §26 as *observed, not explained*. That
was not good enough, so I chased it this time. The answer is not a product regression — it is a broken test, and it
is worth writing down because of what it says about how it broke.

**Measurement.** On this host, a socket bound to `127.0.0.1` and nothing else — the exact shape the product is
supposed to have — refuses a connection to `169.254.0.21` at +0s, +0.05s and +0.2s, and then **accepts** it at
+0.5s. This sandbox runs a proxy that mirrors a local listener onto the host's LAN address. `ss` shows the mirror:
an owned `127.0.0.1:PORT` listener (the shipped server) alongside an unowned `169.254.0.21:PORT` one.

**Consequence for the test.** "The server answered on the LAN address" cannot distinguish a loopback bind from a
wildcard bind on this host. The test failed 4 times in 15 runs while the product was bound to loopback every single
time — `main()` has no `--host` flag and calls `app.run(host="127.0.0.1")`. A test that reports a security failure
for a safe product is worse than no test: it trains the reader to discount the one signal that matters.

**The first hypothesis was wrong, and I say so.** I initially blamed a port collision: `_free_port()` only asks for
a port free on loopback, so something already bound to the LAN address could sit on the same number. I patched a
pre-launch skip for contaminated ports, and it still failed 1 in 8. The `ss` line I read as proof of a collision
was actually the proxy mirroring the server's own port — the same number, a different owner. Recorded because the
wrong explanation was plausible enough to ship.

**What the fix does.** A negative control, re-measured *at the moment of the assertion* rather than seconds
earlier: bind a loopback-only socket, and for two seconds ask whether the LAN address reaches it. If it does, the
probe cannot tell the bindings apart, so the test **skips** with the measurement in the message. It does not pass
(that would hide a real wildcard bind on a host where the probe works) and it does not fail (that would blame the
product for the host's forwarding). Result: 12/12 runs of the file now report `46 passed, 1 skipped`, and three
consecutive full-suite runs report **2260 passed, 5 skipped**. The skip is honest, the reason travels with it, and
the same test still catches a wildcard bind on any host that does not forward.


## 29. Gap 64 — and three tests of mine that were quietly worthless

**What was fixed.** Two defects, not one, because the entry described a symptom with a second cause underneath.

1. **A parse gate before the swap.** `_validate_draft_upload` parses the upload from its temp file while the project is
   still untouched. A file that cannot become a screenplay is a **400** and the project is byte-identical. Measured
   before: the same upload returned **500** after it had already replaced the active source.
2. **A rollback if the post-swap parse fails anyway.** The gate makes that rare, not impossible (a file that changes
   between reads, a full disk), so the handler restores the previous draft with `activate_draft` and says which draft
   the writer is back on — or says BOTH failures if the rollback fails, because a writer told only "could not
   process" does not know where they are.
3. **The parse stage travels with the snapshot.** `snapshot_active` now writes `_stages.json`, and activation restores
   from it. Before, activation restored `parsed.json` and left the stage saying `failed`, so `/script` refused a draft
   whose parse was right there — the "only a manual reparse restored it" half of the entry.

**Three test mistakes, in order of embarrassment:**

1. **I asserted on a field that does not exist.** `/drafts` returns `{active_draft, drafts}` — no stage map. My stage
   test read `.get("stages", {})` and got `{}`, so `!= "failed"` passed vacuously. The real endpoint is
   `/api/projects/<name>` (`stages.parse`). A test whose key is missing cannot fail, so it cannot test.
2. **I asserted that every format rejects an empty file.** Measured: `.fdx` and `.pdf` reject garbage; empty
   `.fountain`/`.txt`/`.md` parse as **zero-scene scripts** and are accepted. That is a product decision older than
   this gap (a blank file is a valid blank screenplay). The parametrised test now covers the two formats that really
   reject, and the comment records the other three rather than asserting them away.
3. **The fault-injection registry caught a defect I had just written.** My first loader was
   `except ValueError: return None` — folding "unreadable" into "no record", the exact A3 shape that registry exists
   for. It refused to let `diff.py` count as a store writer without an entry. The loader now raises, the switch is
   refused **before** the writer is moved, and the case is registered (`load_modify_write=False`, since the snapshot
   rewrites its own record wholesale).

**Verification.** Six new tests: **five fail without the fixes**, one (the temp-file cleanup) passes both ways and is
labelled a regression guard, not evidence. The damaged-record test was confirmed by hand too: 400, script unchanged,
still on `draft-1`. Full suite **2272 passed, 6 skipped**, twice; `ruff` clean. The sixth skip is the honest
loopback skip from §28b.

**Not claimed.** `.pdf` and `.fdx` rejection is proven; a `.fountain` that parses into zero scenes is accepted and
still becomes the active draft — that is a different entry's argument, not this one's.
