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


## 30. Step 3 — publication truthfulness (2, 3, 4), and the two places my first version was wrong

The three entries are one shape: the report was written straight onto the live paths as it was produced, so
there was never a moment at which "this reading is complete and it is about this script" was decided. There was
nothing to refuse and nothing to roll back to.

**2 — analysis read the wrong document (fixed).** `run_analyze` loaded `m.parsed_path` while `/script` renders the
working copy. Measured at the `analyze()` boundary: after the writer replaced a line, the run received
`The drawer was empty.` and never saw `REVOLVER`. It now calls `load_working`, the same document `/script` serves.
The report also carries a `sha256` digest of the document it read — in the artifact itself, not only in the API
response — so "which script is this note about" is answerable from the files alone.

**3 — a failed run destroyed the last good reading (fixed).** Measured: a total-failure run replaced both
`report.md` and `report.findings.json` and `/report` answered 400, while a valid reading had been on disk moments
before. A run now **stages** its whole set into `report.generations/<time>-<digest>-<pid>/` and publication is one
pointer write. The manifest is written LAST, so a manifest on disk means the set is whole. A failed or cancelled run
leaves the previous generation live.

**4 — a run could publish over a draft it never read (fixed).** `publish_generation` re-reads the live draft at the
moment of publication and refuses if the digest moved. Measured through the real route: edit during the run → the
run ends 502 "the draft changed … were not published", the stage is `failed`, and `/report` is 400 because nothing
was published — not a half-report.

**Where my first version was wrong, twice:**

1. **I had two compare-and-publish checks.** The orchestrator checked the digest and `publish_generation` checked it
   again. Both would have passed the tests. Two copies of a safety check drift apart, so I deleted the orchestrator's
   and kept the module's — found on re-reading my own diff, not by a test.
2. **"Serve the published reading" was too blunt, and an existing test caught me.** I first made `/report` serve the
   published generation whenever one existed. `test_reparse_then_analyze_regenerates_report` failed — correctly:
   after a re-parse the old reading may describe text that no longer exists, and showing it is the same lie as a
   stale analysis. The gate is now the digest, not mere existence. A second, narrower mistake fell out of that: a
   re-parse deletes the report files, so the fall-through reported a 404 ("the report is missing") for a project
   that never claimed to have one. That path now answers 400 again.

**Two contract decisions made deliberately, both recorded in the tests:** analysis reads the *working* draft (so a
writer who fixes a line and re-runs gets findings about the fixed text), and the provenance pointer and snapshot are
part of the per-draft bundle — without them, switching back restored the report files but left the pointer from the
other draft, and `/report` refused a reading whose text was on disk.

**Verification.** Nine tests. Against the reverted code (only the behavioural files reverted, since the module does
not exist pre-fix) **6 fail**, and one passes both ways — the "incomplete generation" test — which I am labelling a
**regression guard, not evidence**, because it exercises a function that only exists with the fix. The two remaining
tests cover switching drafts and the preserved re-parse rule. Full suite **2286 passed, 7 skipped**, twice; `ruff`
clean.

**Not claimed.** The generation directories are never pruned, so a long-lived project accumulates them (small, but
real). The CLI writes reports to a caller-chosen path and does not publish generations — it has no project. Gap 5
(cancellation) is untouched; a cancelled run leaves a staged directory behind, which is by design but worth naming.


## 31. Step 4 — a damaged knowledge base (119, 123)

Both entries are one missing distinction. Every other store in this package separates "cannot be READ" from "is not
THERE"; the knowledge base did not. A corrupt `rules/*.json` raised `JSONDecodeError` straight out of
`KnowledgeBase()`, and every caller rendered that as whatever its own error path happened to say.

**Measured, cold (the caches are `lru_cache`d and never cleared, so a warm process hides this — see below):**

| path | before | after |
|---|---|---|
| `POST /analyze` with a corrupt KB | **502**, JSON parser's sentence, **no reading at all** | **200**, a full reading, and the damage named |
| `GET /api/rules/<id>` | **400** with the parser's text (missing KB gets a designed 503) | **503**, framed, naming the file and the directory |
| `GET /api/health` | **200 `status: ok`** | **200 `status: degraded`** + reason |
| empty rules dir (the silent case) | stderr warning; message buried in `errors`, which the desk does not render | same warning **plus a notice the UI shows** |

**What I changed.** `KnowledgeBaseDamaged` (carrying `rules_dir` and the failing file) is raised from `_load` for
an unreadable file, a non-rule entry, or a duplicate id. `pipeline.analyze` catches it the way it already caught the
zero-rules case: run without grounding, say so. Health and the rules route each got their own honest answer.
`_empty_kb_message`'s "cannot count ≠ counted zero" contract is untouched.

**Three things I got wrong in this pass, all found by my own probes rather than the suite:**

1. **My first probe measured nothing.** `_knowledge_base` and `_kb_rule_ids` are `lru_cache(maxsize=1)` and
   **nothing in the app or tests ever cleared them**, so after one healthy load my "corrupt" KB was never read —
   the route confidently returned the real rule from cache. That is a genuine latent hazard (a repaired install
   would keep serving an empty rule set until restart), so I added `_reset_kb_caches()` and clear it on every
   damage path, with a test that repairs the KB and expects recovery.
2. **I broke `/report` and did not notice for one step.** With the KB damaged, `_normalize_rule_ids` calls
   `_kb_rule_ids()`, which now raises — so serving a report 500'd. A damaged KB must never cost the writer their
   report; that call site now degrades to "leave rule ids as recorded". Caught by probing notices, not by the suite.
3. **My own test fixture could not run against the pre-fix code.** It used `_reset_kb_caches()`, a function that
   only exists with the fix — so every case errored instead of failing. Rewritten to clear the caches through the
   stdlib hooks. This is the third time this session that a test's *dependency* on the fix has hidden whether it
   would have caught the bug; the rule now written into the test file is: **a test that cannot run pre-fix is not
   evidence.**

**Verification.** Twelve tests; **6 fail** against the pre-fix behaviour (keeping the typed error, since a test
cannot import what does not exist) and 6 are positive controls or regression guards — a healthy KB still loads, a
missing rule is still 404, health is still `ok`, the rule counter still answers. Full suite **2298 passed, 7
skipped**; `ruff` clean.

**Attribute honestly:** 119 also reported "`/report` 400 while the prior report sits intact". That half was fixed
by step 3's publication work, verified here (failed run → `/report` 200, same digest, `is_stale: true`), and is not
claimed as part of this change.

**Not claimed.** A KB that is *partly* corrupt still loses the whole KB (no per-file skip: one bad file means no
grounding, which is the conservative choice but not a graceful one). Nothing re-reads a KB that was damaged and
then repaired except the paths that call `_reset_kb_caches`. The health check loads the KB, so it pays a small cost
on each call — acceptable at 263 rules, named rather than hidden.


## 32. Step 5 — the CLI and the JS count (110, 111, 121)

**110 — tracebacks instead of a sentence (fixed).** Measured: `status` on a project whose `project.json` lacks a
field exited with `KeyError: 'project_dir'`; `status` on a directory with no manifest did the same with
`FileNotFoundError`; and `run --project NEW missing.fountain` raised through `shutil.copy2` **after**
`ProjectManifest.create` had already made the directory — so a mistyped path left an empty project on the shelf.
Now: one actionable line, exit 2 (usage error, not 1, which the rest of the CLI reserves for a failed pipeline),
and `create` checks the source before claiming anything. Also caught in passing: `run` treated *any* load failure
as "new project", so a corrupt manifest would have been silently replaced by a fresh one — that now exits 2 and
keeps the record.

**111 — `run` was the odd command out (fixed).** `resume` and `status` take the project positionally; `run`
required `--project`, so the obvious `run myproject/` was read as a source file and died on a traceback. `run` now
accepts both: `--project` wins, a first positional that is a directory is the project, one that is a file is the
source (with the project named after it, as `run script.fountain` always meant), and neither is a usage error that
says what to type.

**121 — the JS total was typed, not derived (fixed).** Verified from a clean `npm ci`: `npm test` is **134 tests,
134 pass**, not the 127 the docstring claimed (ink-layer 110 + `tests/js` 24). The docstring now says how to read
the number instead of remembering it, and `npm run test:js-only` exists so `tests/js` can be run alone (`node --test
tests/js/` fails on Node 22 — a bare directory is treated as a module path).

**Self-review notes.** One of my early tests "passed" pre-fix for the wrong reason: argparse rejected the `run P`
spelling before my assertion could distinguish anything. It now asserts that the positional path was *not* rejected
and that the command got as far as producing output, and it fails pre-fix with the rest. Five of seven fail without
the fix; the two that pass are the `status` round trip (unaffected) and are guards, not evidence.

**Not done, deliberately.** 112 (repository weight, ~19 MB of `docs/` and `impl-shots/`) and 124 (the evidence bound
in "verified against both PDFs") are documentation/judgement entries, not code defects. Moving or deleting the
repository's own audit history is the owner's call, not mine to make silently, and 124's fix is a wording change to
claims about evidence I cannot re-measure here. I am leaving both un-fixed and saying so rather than marking them.

## 33. Gap 61 — the staging file, and what is still not transactional

**Measured before the fix** (forced interleave at the seam the entry names): the staging path was
`_draft_upload.<ext>`, one name per project, so the second upload overwrote the first's bytes and the first's
cleanup removed the second's file mid-swap. Result: `A → 400` with the parser's complaint, `B → 200`, and **one**
draft record for two uploads.

**Fixed, in the entry's own order of importance:**

1. **A private staging file per request** — `_draft_upload-<uuid4>.<ext>`.
2. **One draft mutation at a time per project** — the section that snapshots, swaps `source.<ext>` and appends the
   draft record now runs under `lock_for(m.source_path)`, the same lock `/edits/apply` already takes for the working
   copy. Unique staging names alone do not fix the swap: two uploads with different extensions copy to the *same*
   `source.<ext>.incoming` path.
3. **Cleanup is unchanged** and only ever removes this request's own file.

After: **A 200, B 200, two draft records**, the active source holds the last writer's text, the manifest's
`source_filename` names that same file, and no staging litter is left.

**What this does NOT make transactional** (the entry asks for snapshot + swap + manifest as one recoverable unit):
they are still three separate durable writes. A crash between them can leave a draft record whose snapshot was
never taken, or a swapped source whose manifest still names the old draft. The lock removes the *racing* window,
not the *crash* window. I have not measured a crash there, so I am naming it rather than claiming it fixed — and I
am leaving gap 61's "one recoverable transaction" half open on purpose.

## 34. Gap 66 — a retry the writer could not stop, and a cancel reported as a fault

**Measured:** with a real `retry-failed` run in flight, `POST /analyze/cancel` answered **409 "No analysis is
running"**. Three separate faults, only the first of which the entry named:

1. **The retry registered no cancel event** and passed no `should_cancel` to `run_analyze`, so there was nothing for
   cancel to find — and nothing the pipeline would have checked even if it had.
2. **A cancelled retry was reported as a failure.** The orchestrator's cancel branch was guarded by
   `and not retry_failed`, so a deliberate stop fell through to the generic handler and was re-raised as
   `"Analyze stage failed: Analysis cancelled at the writer's request"` — a **502** describing a stop as a fault,
   with the stage marked `failed`. This was invisible until (1) was fixed, because nothing could cancel a retry
   before. I found it only because I checked the response *body*, not just the status of the cancel call.
3. **No stale-event cleanup on the retry path**, so an event could outlive its run and cancel the next one.

After: cancel answers **200 `{"cancel_requested": true}`**; the retry answers **200 `{"cancelled": true}`**; the
stage returns to the status it had before the retry (`complete`), not `failed`.

**Verification.** One test, which fails pre-fix at the first assertion (`409 != 200`). I am not counting (2) and
(3) as separately proven: the same test would pass with (1) fixed alone, because the cancel response is checked
before the retry's own response. They are covered by their own assertions inside the test, but a reader should know
that the *headline* failure was (1). Full suite **2307 passed, 7 skipped**; `ruff` clean.

**Not claimed.** Cancellation remains co-operative: the pipeline checks between calls, so a model call already in
flight runs to completion (the front-end limitation gap 5 names). A retry that is cancelled leaves its staged
generation directory behind, which is the same by-design behaviour as a cancelled full run.

## §35 — Gap 18: chat-session store integrity (2026-11-04)

Five defects, and I am recording exactly which ones this pass actually proves.

**(a) A repeated message is dropped — FIXED.** Messages now carry a stable `message_id` (`models.py`), and
`_merge_missing_messages` unions on identity, with a deterministic `legacy-<sha1>` id and a text fallback for files
written before the field existed, so old sessions still load and still merge.

**(b) A stale save resurrects a deleted session — FIXED, but my first two rules were wrong.** `delete()` now leaves a
durable `<sid>.deleted.json` tombstone under `lock_for`. My first rule ("any save where the file is missing but a
tombstone exists is refused") **broke a real feature** and the full suite caught it: the Design Lab thread lives at a
**fixed** id (`preview-lab`), "clear this chat" deletes it, and the next request legitimately re-creates it — every
request after a clear 500'd. My second rule (`create()` clears the tombstone) fixed the lab but made the documented
defect fail its own test, because the lab lazily rebuilds with `Session(...)` + `save()`, not `create()`. The rule that
holds is causal: refuse only when the snapshot came into being (`Session.created_at`) **before** the deletion
(`deleted_at`). A stale turn is always older than the delete; a session built after a clear is a new conversation at a
reused id. Strict `<`, so an ambiguous ordering lets the save through rather than break clear-and-start-over.

**(e) A failed `.bak` park overwrote the damaged original — FIXED.** `_park_damaged` now returns success, and `save`
fails closed (`SessionUnreadableError`) when the damaged bytes cannot be preserved.

**(c) and (d) are covered only INDIRECTLY — not separately proven this pass.** (c) a stale save restoring a deleted
branch is handled by the pre-existing `deleted_branches` tombstone (DEL-1), which I did not re-derive. (d) a transient
`OSError` on the merge read is handled by the existing `except OSError: pass` "land the save anyway" branch, which I
also did not re-derive. I am not claiming fresh evidence for either.

**The admission that matters: my first version of the (a) test was vacuous.** It saved a session that already held
every message, so in-memory was a superset, the merge never ran, and the test passed against buggy code — it "proved"
a fix without ever entering the defective path. Rewritten twice more: the second attempt still failed to reproduce
because the stale snapshot already contained both copies. Only the version where the **disk** holds a repeated message
the stale snapshot lacks reproduces it, and there pre-fix the store held `['Yes', 'ok']` — one turn silently gone.
Every new test was re-run against reverted code and shown to fail.

**A new durable write needed new fault coverage.** The repo's discovery gate (`test_every_store_writer_is_in_the_
registry`) failed the moment `store.py` started calling `atomic_write_json` for the tombstone, and it was right to: I
registered a `StoreCase` instead of an exemption, probing the question the tombstone exists to answer (does a stale
save get refused?) rather than the bookkeeping boolean. It is non-vacuous in one direction only — against a **lenient**
damaged-tombstone policy (`return False`) all three faults fail, which is what proves the fail-conservative branch;
against mere tombstone existence it passes, so I count it as a damage-policy guard, not as proof that (b) is fixed.
(b)'s proof remains the direct stale-save test.

**Judgement call, flagged:** a damaged tombstone makes `save` refuse (fail closed). If that record is ever corrupted
on a real install, a chat turn to that id errors instead of silently continuing. I chose this because a resurrected
deleted conversation is unrecoverable and a refused save is retriable and says why — the same asymmetry as (e). If the
owner prefers availability there, the change is the two `return True` branches in `_superseded_by_delete` /
`is_deleted`.

Full suite **2320 passed, 7 skipped**; `ruff` clean.

## §36 — Gap 21: export glues a new speaker onto the previous speech (2026-11-04)

**FIXED.** `_append_blank_after` treated `CHARACTER` as a member of the "continue this dialogue block"
set, so a cue following someone else's dialogue got no separating blank line:

```
AJAY          AJAY
Hello.   ->   Hello.
VENU          VENU        # no blank -> parser reads this as more of AJAY's speech
Hi.           Hi.
```

Re-parsing gave `AJAY/dialogue "VENU"`, `dialogue "Hi."` — the next speaker's NAME became a dialogue line
attributed to the previous speaker. Reproduced through the real exporter and the real parser in both Fountain
and TXT, then through the actual `/api/projects/<name>/export` download route (not just the function).

**The fix** is one idea: a `CHARACTER` cue always begins a new block. `_DIALOGUE_BLOCK_TYPES` keeps its meaning
("this element belongs to a dialogue block") but a new `_DIALOGUE_CONTINUATION` set decides what may follow with no
blank, and it holds only `PARENTHETICAL` and `DIALOGUE`. So a cue → dialogue → cue sequence emits one blank where
it used to emit none, and cue → parenthetical → dialogue still stays glued.

**Evidence.** 8 new tests; 6 fail against the pre-fix exporter (the two parametrised pairs for Fountain and TXT).
The other two are the empty-element guard, which I am labelling a REGRESSION GUARD rather than evidence — I
measured the parser's own output over every `.fountain` in the repo and found **0 text-less elements out of 164**,
so nothing in the real parse path triggers it. It is defensive: the writers `continue` past text-less elements, so
deciding from `elements[i + 1]` rather than the next element that actually gets emitted is a latent trap.

**Measured effect on the repo's one real fixture** (`tests/fixtures/pain_tenglish.fountain`): pre-fix, 3 of its 36
speech elements changed through a round trip, in both formats; post-fix, 0. That is now a test.

**Scope limit, stated because the register's numbers are much bigger.** The register quotes 46 element-type changes
and 75 speaker changes for Darshi: Pain 3 (TXT 48/75, 43/47). Those came from parsed representations of the user's
PDFs, which are **not in this repo**, so I cannot reproduce or re-derive them and I am not claiming they are all
gone. What I can say is narrower and verified: the specific mechanism named in the register (no blank between
dialogue and the next cue) is removed, it was demonstrably changing attribution on the one real fixture available,
and both text formats now round-trip that fixture with zero speech churn. Whether the user's larger scripts still
show churn needs a round trip over those files, which I cannot run here.

Full suite **2328 passed, 7 skipped**; `ruff` clean.

## §37 — Gap 23: quote verification erases Indic vowel marks (2026-11-04)

**FIXED, with one residual left deliberately open and pinned.**

**The defect, reproduced.** `normalize_text` filtered with `[^\w\s]`, and Python's `\w` keeps only
`str.isalnum()` characters — which excludes **combining marks** (categories `Mn` and `Mc`). Telugu, Devanagari
and Tamil all write vowel length as a combining sign, so `కాల` ("time") and `కల` ("a pen") normalised to the same
string. Through the real `verify_finding`:

| quote | script contains | verdict before | verdict after |
|---|---|---|---|
| the exact line | yes | `verified` **1.0** | `verified` 1.0 |
| **different word, absent from the script** | no | `verified` **1.0** | `not_found` 0.98 |

All three scripts collided before; none do now.

**Two fixes, each independently required.** (1) The normaliser keeps letters, marks, numbers and the ZWNJ/ZWJ
joiners, and folds to **NFC** first — so the same word typed composed or decomposed still matches, while two
genuinely different words never collapse. NFKC is deliberately not used (it would fold ligatures and full-width
forms). (2) Even with the marks preserved, one vowel sign in a 28-character line leaves the character ratio at
**0.98**, still above the 0.72 verification threshold — so the verifier would still have certified the quote. A
`NEAR_IDENTICAL_THRESHOLD = 0.95` band now reports `not_found` with a note instead. Proven separable: reverting
the normaliser alone fails **8** tests; reverting the threshold alone fails **1**.

**The tolerance survived.** A genuinely reworded real line still verifies (0.81 in my probe). That is the whole
reason the verifier is lenient, and a fix that lost it would trade one dishonesty for a worse one — calling real
quotes fabricated. There is a test for it.

**RESIDUAL, not fixed: the studio's change detector still calls a one-mark edit "still present".**
`revision.quote_present` has `QUOTE_CHANGE_THRESHOLD = 0.95` and its own comment documents the trade-off ("a
dropped character scores 0.979 (still present)"). So an editor changing `కాలం` → `కలం` sees that finding stay
open in the desk. I did **not** change it: it is a separate, deliberate decision about the writer-fix signal that
would flip behaviour across the whole queue, and gap 23 is about the verifier certifying an **absent** quote. I
pinned the current behaviour in a test named `..._RESIDUAL` so it cannot be mistaken for fixed, and the assertion
message says to update this section if it ever changes. It is now filed as register entry **129** and argued in §41
below (written later in the same session); the note you are reading was accurate when written and the hole it admits
has since been closed.

**Environment note, so the numbers are reproducible.** This sandbox came up with no `/home/user/.venv`; I rebuilt
it from `requirements.txt` plus `pytest`, `ruff`, `pyyaml` and `playwright`. The first full run reported 5 failures
that were all `ModuleNotFoundError` for the two optional packages, not real failures — after installing them the
baseline was the expected 2328 passed. I verified that before touching any code.

Full suite **2343 passed, 7 skipped**; `ruff` clean.

## §38 — Gap 113: served counts vs what the desk shows (2026-11-04)

**The reproduction stands; the impact I filed with it does not.** This is a partial retraction, not a fix report.

**What I reproduced at the time:** a two-finding project (one grounded, one `ungrounded`) answers
`/fixqueue` `total_count: 2` and `/findings/summary` `open_count: 2` while the desk hides the ungrounded row.
Re-ran it today: identical.

**What I got wrong.** §20 said "the number the writer sees is the *internal* set" and named "the ledger's mass
strip and dawn meter" as printing it. Reading and then **executing** the shipped client:

* **mass strip**: `buildScriptMassStrip()` prints `findingCounts()` — `"N open of M findings"` over the whole
  script, followed by `"· K shown by filter"` whenever the filter narrows it. It is a whole-script total that
  says so on its face.
* **queue header**: `queueCounts(shown)` **does** drop ungrounded rows (`item.ungrounded && !state.fixQueueShow
  Ungrounded` with the writer-disposition exemption), printed as `"1 open / 1 shown / 2 total"`. Executed the
  extracted helpers under Node: with one grounded + one ungrounded and the toggle off, `findingCounts()` gives
  `total 2, open 2, shown 1`.
* **the summary itself is read by nothing.** `state.findingsSummary` is assigned at `app.js:407` and `:4346` and
  read at no site. The only reader of `open_count` outside tests is `preview-ink-layer/core.js`, a prototype no
  route serves.

So I filed a genuine API limitation as a writer-facing lie about the numbers, and dressed it in the register's
severity-A voice. That is the same failure §16 admits to — uniform tone over non-uniform evidence — and I did it
again on a fresh entry.

**What is actually wrong, and what I changed.** A machine consumer of these routes cannot tell "2 open" from "2
open, one of which the desk will not show". The counts were honest as whole-script totals; the *split* was
missing. Both routes now ship it:

| key | meaning |
|---|---|
| `ungrounded_count` | rows flagged ungrounded, on either route |
| `ungrounded_hidden_count` | ungrounded rows with **no** writer mark — what the toggle hides |
| `open_visible_count` | `open_count` minus the above |
| `grounded_count` | (`/fixqueue`) the other half of `total_count` |

The precedence is **copied from the desk, not invented**: `findingCounts`/`queueCounts` exempt a row the writer
has marked addressed or deferred, so an ungrounded row they have already judged does not hide. My first cut
counted every ungrounded row as hidden, which would have re-created the exact drift this register keeps finding;
the two precedence tests fail when that exemption is removed.

**Evidence.** 7 tests; **5 fail** against the pre-fix routes. The other **2 are static guards**, not evidence —
they pin the mass strip's scope disclosure and the toggle's exemption so the precedence cannot silently drift.
Against pre-fix code they pass, and I am labelling them as guards rather than counting them.

**What I did not do.** I left `open_count` as the whole set rather than redefining it to mean "visible". Redefining
a field a consumer may already read is how a counting contract drifts, and the whole-script number is the one the
desk's own headline uses. If the owner prefers `open_count` to be the visible number, that is a one-line change
plus a rename, and it should be decided deliberately rather than smuggled in here.

Full suite **2350 passed, 7 skipped**; `ruff` clean.

## §39 — Gap 87: the exported report now says when a note is unsupported (2026-11-04)

**FIXED, as a disclosure defect — and that is exactly what it is.** Nothing here was a real-model result: the invented
detail ("the revolver") came from the built-in demo stand-in, so this gap is about a surface that failed to carry a
warning it already held, not about a model fabricating.

**Reproduced** through the real `apply_evidence_floor` and the real `render_markdown`, with one grounded and one
ungrounded finding:

```
**[LOW] Scene 1, Scene 2** — Setup left dangling: 'The revolver'
```

No `ungrounded`, no verification status, nothing — while the JSON carries `ungrounded: true` and the dock hides the row
behind a toggle. `_format_finding` simply never read the flag.

**Fixed in the renderer, which covers both surfaces:** `/api/projects/<name>/report/export` renders the stored
`report.md` through `_md_to_html`, so fixing `render_markdown` fixes the printed HTML as well as the Markdown file. The
row now carries `⚠️ unsupported — this note cites no quote or observation from your script`, and the Detailed Analysis
heading states `"N of M notes below are unsupported"` so the proportion is visible where the list is printed.

**Disclosure, not dropping.** I deliberately did NOT suppress ungrounded rows from the export. The docstring said "his
guesses presented as script-diagnosis" — but hiding the row in the artefact that travels is the same class of lie in
the other direction, and it would make the count un-auditable. There is a test asserting every finding still renders.

**The register's third recommendation already existed and I wired a test to it rather than building anything.**
`_setup_quote` searches the setup scenes' actual lines and returns `None` when nothing matches, and
`apply_evidence_floor` turns that into `ungrounded`. So "names something absent from the script" was already a
verifiable classification; it just was not stated in any rendered surface. I checked that test is not vacuous by
neutering `_setup_quote` to always return `None`: the *grounded* direction then fails, which is what proves it tests
the distinction rather than the constant.

**Evidence.** 8 tests; **3 fail** against the pre-fix renderer (the two disclosure assertions and the rendered-report
one). The other 5 cover the classification and the negative cases; of those, 2 passed pre-fix by construction. One of
them I proved non-vacuous by injection as described above. I am labelling that explicitly rather than counting 8.

**Still open, and not mine to close:** whether a real model produces absent-detail claims is untested here, and gap 88
(provenance by name rather than by nature) is the adjacent disclosure gap.

Full suite **2358 passed, 7 skipped**; `ruff` clean.

## §40 — Gap 88: the report discloses the stand-in by nature, from the run's record (2026-11-04)

**FIXED.** The demo model was disclosed only *by name*: `**Analyzed with:** demo-craft-model`, plus the stub's own
findings happening to begin `[demo] …`. Two problems with that, and the second is the real one:

1. A model id is not an explanation — `demo-craft-model` means nothing unless you already know what it is.
2. **The disclosure depended on the stand-in cooperating.** `[demo]` is emitted by `demo_model.py` as finding *text*
   (lines 609–676), not by the renderer. So the honesty of the artefact rested on the stub's wording. I proved this by
   rendering a demo report whose findings did not prefix themselves: nothing in the report said demo at all.

**Fixed at the renderer, from the run's own record.** `model_used` is persisted with the report, so
`model_is_stand_in(result.model_used)` drives a blockquote directly under the header: *"This report was produced by
the built-in demo model, not a real analysis… Do not use them to judge your screenplay."* It sits above
`## Detailed Analysis` because a caveat read after the findings is read too late.

**The HTML export had gap 59's defect and I fixed that too.** `_report_banner()` keyed off `_DEMO_MODEL_ACTIVE` — the
*current* process's setting. So an archived demo report exported after the writer connected their real server lost
its banner and read as a real review, and a genuine report produced while demo mode happened to be on would have been
labelled canned. It now takes the run's `model_used` (read from the stored findings payload by the export route), with
`None` falling back to the old global check so unknown provenance stays conservative rather than claiming a real
reading. Verified by flipping `_DEMO_MODEL_ACTIVE` to False and confirming the archived demo report still discloses.

**A renderer gap I had to close for that to work.** `_md_to_html` is a deliberately tiny subset renderer with no
blockquote branch, so the Markdown disclosure would have been flattened into a paragraph starting with a literal
`>` — a warning degrading quietly, which is the failure mode this gap is about. Added the branch;
`class="report-disclosure"` now appears in the export.

**Evidence.** 11 tests, and both halves are independently proven: reverting only the Markdown disclosure fails **5**,
reverting only the banner decision fails **5**. Note the method correction — my first revert attempt failed as an
`ImportError` because the test imports `model_is_stand_in`, so I redid it keeping the helper and reverting only the
behaviour. That is the same trap I hit on gap 18 and it is now my default for any revert-check.

**One existing test updated, deliberately.** `test_demo_banner.py` pinned the literal string
`_md_to_html(md, _report_banner())`. I changed the pin to require `_report_banner(model_used)` *and* to assert the
no-argument form is absent, so the guard got stricter rather than being loosened to accommodate my change.

**Not claimed:** nothing here says anything about real-model quality. Whether the stand-in's *findings* are
representative is gap 87's territory and is not established.

Full suite **2369 passed, 7 skipped**; `ruff` clean.

## §41 — Gap 23's residual, now filed as its own entry (129), with the decision it needs

When I fixed gap 23 I left one thing open and said in §37 that it deserved its own register entry, which I had **not**
written. That was a housekeeping hole of mine; it is now entry **129** in both registers, and this section is the
argument behind it.

**The behaviour.** `revision.quote_present` decides whether a finding's evidence quote is still in the working copy,
which is how the desk knows the writer fixed something. Its own docstring sets the trade-off: a near-identical
difference inside one element is read as the parse or the quote being slightly off, not as the writer editing. Measured:

| change | ratio | verdict |
|---|---|---|
| dropped character (a typo'd quote) | 0.979 | **still present** |
| one vowel mark changed (a different word) | 0.982 | **still present** |
| swapped word | 0.875 | reads as edited |
| removed word | 0.830 | reads as edited |

So an editor who changes `కాలం` to `కలం` sees that finding stay open in the desk. In a mixed Telugu/Tenglish script —
exactly the register's stated case — this reaches ordinary copy-editing, not just exotic input.

**Why I did not fix it, stated as a measurement rather than a preference.** The two cases the tolerance has to separate
are **numerically indistinguishable**: the typo it exists to forgive scores 0.979 and the edit it fails to catch scores
0.982 — both one character different, both ~2.8% above the 0.95 threshold. No threshold value separates them, so this is
not a tuning bug and "lower the threshold" has no answer that is right. I checked that before declining, because the
opposite outcome (a threshold tweak) would have been a genuine fix.

**The option that would work, and why it is not mine to take.** A three-valued answer — *changed*, *unclear*, *still
present* — is the honest shape: the two middle cases are genuinely ambiguous and should say so rather than being forced
into one bucket. But the counting contract is binary end to end: `diff.py` buckets into `resolved`/`still_present` and
would need a third list, and `finding_statuses` maps `unknown` to **open**, so a new "unclear" bucket would either be
counted as unfinished work (noisy) or excluded (rows vanish from the ledger).

That is a product decision about what the writer is told a number means — the same class as the `open_count` question I
declined to decide unilaterally on gap 113. So it is filed, evidenced, and left open, with the trade-offs stated where the
owner can act on it. I am explicitly **not** claiming this as fixed, and the existing `_RESIDUAL`-named test still pins
the current behaviour so nobody mistakes it for solved.

**Gap 23 itself remains FIXED** — that was the verifier certifying an *absent* quote, which is a different question from
this one, and its own two-part fix is unaffected.

Full suite unchanged at **2369 passed, 7 skipped**; `ruff` clean.

## §42 — Gap 125: the dictation capability endpoint now runs the guard it promises (2026-11-04)

**FIXED.** Reproduced on one client with `SCREENPLAY_STUDIO_WHISPER_URL=http://speech.example.com:9000`:

```
GET  /api/stt/languages -> 200 {'engine': 'whisper-server', 'languages': [...]}
POST /api/stt           -> 503 '...must point at a LOCAL whisper server...'
```

The label was `"whisper-server" if _stt.EXTERNAL_WHISPER_URL else "faster-whisper"` — it tested whether a URL was
*set*, never whether it was *usable*. The writer is told dictation is configured, records a paragraph, and only then
learns it is not. The guard itself was, and is, correct.

**Fixed by making the label run the guard.** A new `stt.engine_status()` calls the real `_assert_local_whisper` and
returns `{"engine": "faster-whisper", "misconfigured": "whisper-server", "reason": "<the guard's own message>"}`
when the configuration is refused. `/api/stt/languages` merges that. Two deliberate choices:

* it calls the **real guard** rather than re-implementing a loopback test — a second copy is how these drift back
  apart, and a test asserts the call is there;
* it keeps the guard's own wording as the reason, so the two endpoints cannot explain the same refusal differently.

Now: not configured -> `faster-whisper`; local server -> `whisper-server`; remote or a `http://127.0.0.1@evil.com`
lookalike -> `faster-whisper` + `misconfigured` + reason. The lookalike matters: the label would otherwise have become
a way to ask the guard a question and get the wrong answer.

**A test bug of mine worth recording.** My first consistency assertion failed on `http://127.0.0.1:8090` because a
*local* server that simply is not running also answers 503 ("could not be reached"). Advertising `whisper-server`
for that is honest — the configuration is permitted, the machine is not up. I had written "503 means the guard
refused", which conflated reachability with refusal; the test now keys on the guard's own message. The code was
right both times and the test was wrong, which is worth saying because the tempting "fix" would have been to change
the code to make my assertion pass.

**Evidence.** 7 tests; **4 fail** against the pre-fix route label, and **4 fail** against an `engine_status` that
skips the guard — both halves independently proven.

**Known limit, unchanged:** `EXTERNAL_WHISPER_URL` is read once at import, so correcting the env var needs a restart
before this endpoint stops reporting `misconfigured`. That is pre-existing and is not addressed here.

Full suite **2376 passed, 7 skipped**; `ruff` clean.

## §43 — Gap 118: consent scope is now machine-readable, and does not overstate itself (2026-11-04)

**FIXED.** Reproduced first: `/api/config` answered `allow_remote: false, connection_mode: "local",
server_url: "http://127.0.0.1:8099"` and — with a remote host configured — `allow_remote: true,
connection_mode: "remote", server_url: "https://api.example.com/v1"`. Nowhere in the payload did it say whether the
script is sent off the machine, where to, or what a credential would be attached to. The settings UI explains this in
prose; a scripted client gets nothing.

**Added a `privacy` block to `/api/config` (GET and POST) and `/api/health`:**

```json
{"sends_script_off_machine": true, "destination": "https://api.example.com",
 "credentials_in_use": true, "credentials_scope": "global", "remote_permitted": true}
```

Computed by one `_privacy_statement()`, because the same statement now appears on three responses and two
hand-written copies is exactly how `/api/config` and `/api/health` drifted before (gap 56/the same seam this register
keeps finding). `/api/health` carrying it also answers the narrower half of §10's own correction: a health-only client
could previously tell a permitted-remote desk from a local one only by parsing the URL and inferring.

**The decision I want on record: `credentials_scope` is `"global"`, not `"origin"`.** The register's recommendation
asked for `credentials_scope: origin`. That would have been **false**. The token is a single configuration value in
`CONFIG["api_key"]`, and `/api/config`'s POST path writes `CONFIG["server_url"]` and `CONFIG["api_key"]` independently —
so a saved token follows a changed endpoint with no new trust decision. That is **gap 57, still open**. A privacy
statement that names a scope the code does not enforce is worse than no statement, so the block reports the limitation
and a test pins it: `credentials_scope == "global"` and explicitly not `"origin"`. When 57 is fixed, that field
becomes `"origin"` and this test flips with it — which is the right coupling.

**Two smaller honesty choices.** `credentials_in_use` is false for a loopback server even when a key is configured,
because `_auth_headers` short-circuits locally and nothing is sent — "configured" is not "used". And an unparseable
`server_url` reports `sends_script_off_machine: true` with `destination: null`: it is not loopback, so treating it as
off-machine is the conservative reading, and inventing a destination would be the dishonest option.

**Evidence.** 10 tests; **9 fail** with the block removed. The tenth is the secret-withholding negative (no token on
either surface), which correctly passes either way and is there to keep the block from ever becoming a leak.

**One test bug of mine:** my POST test forgot to enable the launch-time remote opt-in, so the guard refused the switch.
That refusal is correct and is its own contract (`test_connection_modes.py` pins it); the test was wrong. Worth
recording because the tempting fix would have been to weaken a security guard to make my assertion pass.

Full suite **2386 passed, 7 skipped**; `ruff` clean.

## §44 — Gap 57: the token now remembers which provider it was entered for (2026-11-05)

**FIXED.** Reproduced on the real routes with a fake client, then measured at a loopback server that records every
request it receives. The precondition is the state a writer reaches by saving a provider: `CONFIG["api_key"] =
"sk-token-for-provider-A"`, `server_url = https://provider-a.example.com/v1`.

* `POST /api/test-connection {"server_url": "https://provider-b.example.com/v1"}` — the token box blank, which the
  settings page (and `app.js`) sends as an **omitted** `api_key` field — answered **200**, probed provider B, and put
  `Authorization: Bearer sk-token-for-provider-A` on the wire.
* `POST /api/config {"server_url": "https://provider-b.example.com/v1"}` with no `api_key` answered **200** and left
  `api_key_set: true`. From then on every analysis and chat turn went to B carrying A's credential.

**The cause is a representation, not a missing check.** `api_key` was one value whose meaning was "the token", with no
record of the question it answered. Any code path that moves the endpoint silently re-points the secret. So the fix is
bookkeeping: `CONFIG` carries `api_key_origin` — the origin the token was entered for — **beside** the token, inside the
same holder. That placement is the important part. `__setitem__("api_key", …)` clears the approval, so the CLI flag,
the "go local" switch, a token clear, and any reset of the field cannot leave an approval describing a secret that is
no longer there. My first draft used a side attribute and it survived a token clear; the suite caught that as a
state leak between tests, which is the same bug a writer would have hit as "the old provider keeps getting trusted".

**Two flows, both closed at the last point before an outbound call:**

1. `test_connection()` asks `_credential_refusal(url)` **before** the client is constructed, so nothing is sent. The
   refusal names the origin the token belongs to and never the secret. Measured: **zero** requests reach the second
   server.
2. `set_config()` refuses a save that moves the endpoint while the token box is blank (`body.get("api_key") is None`,
   which is exactly how the blank box arrives). 400, and `server_url` / `api_key` are left untouched.

**The scope of the refusal is as deliberate as the refusal.** The guard fails closed on the *secret*, not on the
*endpoint*: a desk with no token at all is not refused (nothing can leak, and refusing would break testing a fresh
install); a token typed for the new provider is approved for it; `api_key: ""` moves and clears in one request; and a
changed path or port on the **same** origin keeps the token, because that is the same program. Migration stayed one
explicit action, which is what the register asked for. A token with **no recorded origin** — `--api-key`,
`SCREENPLAY_STUDIO_API_KEY`, or a config written before this bookkeeping — keeps working on loopback and is refused
off-machine; refusing those outright would have broken every existing install, and accepting them everywhere would
have left the actual leak open. (This paragraph originally justified the loopback carve-out with "`_auth_headers`
never sends it anyway". **That was wrong** — see §45. `_auth_headers` short-circuits on *no token*, not on *local*, so
a loopback llama-server does receive the header. The carve-out still holds, for the narrower reason that loopback is
this machine: nothing crosses a trust boundary, and the token the writer configured is the one their own local server
asked for.)

**Fifteen tests failed when I first ran the suite, and the triage is the point.** I had written the guard to refuse
when there was no token as well, and the failing tests were the ones that point a desk with no token at a new server —
all of them correct. So: **zero of the 15 were tests asserting the old leak.** I had introduced an outage, not exposed
a hidden contract. The guard now returns `True` (nothing to protect) when no token is saved, and the whole suite is
back to its baseline. Changing fifteen tests to match my bug would have been the wrong repair, and it would have
looked like a successful fix.

**Evidence.** `tests/test_credential_follows_endpoint.py`, 20 tests over both flows. Revert measured twice: removing
the two guards fails **6**, and additionally neutering the predicate fails **8**; the remaining 12 are the
not-regression half (same origin, no token, clearing, typed token).
Two of my own tests passed on the first, route-only revert **for the wrong reason** — they asserted `ok is False`
against a non-routable host, which is false whether or not the guard exists. I found that by reverting, not by reading,
and rewrote them to assert the predicate and the refusal wording. A test that cannot fail is not evidence, and the
only way I know which is which is to take the fix away and look.

Full suite **2406 passed, 7 skipped**; `ruff` clean.

**What this does not claim.** A **per-project** `manifest.api_key` is still trusted to that manifest's own
`server_url` — the two are written together by the app and there is no per-manifest origin record, so a hand-edited
manifest could still pair an old token with a new endpoint. And a **redirect** during a probe is followed by
`requests` without re-checking the origin of each hop (gaps 58/70). Both are outside this entry and are stated here so
the fix is not read as covering them.

## §45 — Correction: a loopback endpoint does receive the credential (2026-11-05)

**A claim I shipped last commit was false, and my own test was enforcing it.** Gap 118's `privacy` block reported
`credentials_in_use: false` whenever the endpoint was loopback, on the stated grounds that "a local loopback server
never needs the token (see `_auth_headers`), so 'no key' is the honest answer there even if one is configured". I
carried that reasoning into §44's justification for gap 57's loopback carve-out, and last turn I wrote a test —
`test_a_loopback_server_needs_no_credential_even_if_one_is_set` — asserting it.

Measured against a loopback server that records its headers, with a token set for a *remote* provider:

```
headers a LOOPBACK server received: {'Host': '127.0.0.1:41887', ..., 'Authorization': 'Bearer sk-secret-for-a-remote-provider'}
privacy.credentials_in_use for that same state: False
```

`_auth_headers` short-circuits when there is **no token**, not when the endpoint is **local**. So the header is sent,
and the statement said it was not. A privacy statement that under-reports what is transmitted is the same class of
defect as gap 118 itself, one level down — and it was in the field a scripted client reads to decide whether to warn a
writer. The `window.__studioPrivacy` surface had no way to see it.

**Fixed:** `credentials_in_use` is now true whenever a token is set. `sends_script_off_machine` stays false for
loopback, which is the distinction that actually matters — a credential reaching another *program on this machine* is
not the same risk as one leaving the machine, and the block now says both things instead of conflating them. The test
that asserted the falsehood is rewritten, and the replacement pins the claim **against the wire**: it stands up a
loopback recorder, drives the probe, and asserts the header that arrives. The old test could not have caught this,
because it asked the code the same question the code was answering.

**Why this is worth a §: the failure mode was trusting a comment.** `_auth_headers`'s docstring says "`{}` for a local
server". It is wrong in the same way, and I read it as documentation rather than as an assertion. I have corrected the
two places that repeated it. The lesson is the standing one for this register: a claim about what goes over the wire is
only worth what a recorder says it is, and "I read the code" is not evidence — I had read the code.

Full suite **2408 passed, 7 skipped**; `ruff` clean.

## §46 — Gap 58: settings are all-or-nothing, and "Local" now means local everywhere (2026-11-05)

**FIXED.** Reproduced both halves on the real routes before touching anything:

```
HALF 1  POST /api/config {"server_url": "http://127.0.0.1:9999", "turn_timeout": -5}
        -> 400 "turn_timeout must be positive"
        server_url before: http://127.0.0.1:8080   after: http://127.0.0.1:9999

HALF 2  POST /api/config {"connection_mode": "local"}   -> 200
        global  : http://localhost:8080   key: None    mode: "local"
        project : https://provider-b.example.com/v1    key: sk-synthetic-b
        _make_client(project).base_url -> https://provider-b.example.com/v1
```

Half 2 was **worse than the register recorded**. The register said the project's URL and key were untouched; what it
did not say is that the desk then reported `connection_mode: "local"` while an existing project's client — the thing
that actually sends the script — still resolved to the provider. The status panel reads the mode, so the writer is
shown a green "everything stays on this machine" over turns that are leaving it. That is the worst shape a privacy
defect can take: not a silent leak, but a *reassurance* that contradicts the behaviour.

**Half one: validate the whole request, then apply it once.** `_settings_candidate(body)` returns a plan or raises;
`set_config` writes nothing until it holds a plan. The register's reproduction now leaves all six config fields
byte-identical, touches no manifest, and the project still opens afterwards. I did this as a separate pure function
rather than by reordering assignments inside the handler, because "nothing is written before validation" is a
property you want to be able to *see*, not infer from reading 80 lines in order.

**Half two: propagate the clear, then report any remainder.** "Go local" and `api_key: ""` now reach every manifest,
so the project's effective destination is loopback with no `extra_headers` — asserted through `_make_client`, not
through the config. When a project still disagrees (unwritable directory, hand edit), the API says so: a
`destinations` block on `/api/config` (GET and POST) and `/api/health` names the remote projects, and the settings
panel renders a warning that names them instead of a "Local" label. The wording is a pure function in `core.js` with
node tests, so it is checked rather than eyeballed.

**Two regressions of mine, caught by the suite, and both were me relaxing a pinned contract to suit a refactor.**
My first candidate made `connection_mode: "remote"` with no URL conditional on the saved URL looking local — silently
weakening `test_remote_needs_a_base_url`. And it made a non-numeric `timeout` fatal after years of it being *ignored*
(`test_invalid_timeout_ignored_not_crashed`, `test_webapp_config_timeout_validation`). Both fixed in the code, not in
the tests. A refactor that changes behaviour is not a refactor, and the tempting move in each case was to edit the
assertion.

**Evidence.** 21 Python tests. Revert measured **per half**: restoring the original mutate-as-you-parse handler fails
**9**; reverting only the credential propagation (to the old "propagate what was explicitly sent" rule) fails **2**.
The other 10 are the not-regression half — a valid save still applies everything, remote-without-URL is still
refused, the forgiving timeout still forgives.
My first attempt at the half-1 revert **passed 21/21**, which looked like the fix being unnecessary. It was not: I had
injected the late failure *after* the candidate, so it was unreachable and the revert tested nothing. I redid it from
`git show` of the previous handler. An unfaithful revert is more dangerous than none, because it reports green.

Plus 5 node tests for the panel wording. One of those failed on my own bad assertion (`!text.includes("e")` against
"Save again") — the test was wrong, the wording was not.

Full suite **2429 passed, 7 skipped**; `ruff` clean; `npm run test:js-only` 29 passed.

**Not claimed.** Concurrent settings saves are still last-writer-wins, and a turn already in flight when the settings
change completes finishes on its old client, with no per-turn record of where it went. Neither was reproduced and
neither is fixed here. Per-project propagation remains best-effort per directory (so one unreadable manifest cannot
break the save); the `destinations` block turns that silence into a visible report rather than preventing it — which
is the honest boundary with gap 42.

## §47 — Gap 112: the evidence got smaller, and the check was the point (2026-11-05)

**DONE, with 11 of 71 files deliberately untouched.** 30.6 MB of evidence PNGs → 12.9 MB (−58%); worktree 52 MB →
35 MB (−33%). `docs/audit/EVIDENCE_IMAGES.md` records the method and the exceptions.

**The decision was "only if it stays readable", so readability had to be measured, not assumed.** Two candidate
methods, and the first one I tried failed the test I set for it:

* **Half-size downscale** — 84–91% smaller. I compared crops at native size and it is **visibly mushy**: the small
  print goes soft and grey. Text is "there" and the evidence is worse. **Rejected on sight**, not on a number.
* **Palette quantisation (128–256 colours)** — 56–76% smaller. Every pixel stays where it is; only the colour table
  coarsens, which is invisible on a flat-palette UI screenshot. **This is where the size was**, so no resize was needed
  at all.

**The check I used, and its limit.** No OCR binary exists in this environment, so I could not read the text out
mechanically. The structural proxy: threshold, label dark blobs, count those sized like glyphs (3–26 px tall). Merged
letters or a dissolved line collapse that count. A file had to keep **≥80% of its glyph blobs** and its median glyph
height, and it was **re-read after writing** so the pass verified the bytes on disk rather than my intention. 11 files
failed at 128 colours and again at 256 and were left alone. On top of the metric I looked at crops myself on the
worst-scoring file and on a flat-UI board shot; indistinguishable at 1:1.

**The honest limit: this is a proxy, not a reading.** It catches "text was destroyed", which is what quantisation
would do if it went wrong. It would not catch "this sentence now reads slightly worse but is still there". I looked at
three crops and not at sixty; a reviewer who thinks a specific image got worse should say so and I will restore it from
git history — the originals are still there.

**A real finding fell out of it.** Three groups of PNGs are **byte-identical under different filenames**: the three
`j4_*` evidence shots, `A-scene_function`/`B-character-dials`, and `A02-evidence-lens-full`/`B-coverage`. At most one
caption per group can be true. That is an **evidence-integrity defect** and I filed it as **gap 130** rather than
deduping — deleting the duplicates would have deleted the signal that two captions are wrong, and I cannot tell from
the pixels which frame was intended.

**What I did not do, and why.** I did not rewrite git history. `git filter-repo` would drop the old blobs from `.git`
(~19 MB → a few MB for a fresh clone), but it rewrites every commit SHA on a shared branch, and the branch policy here
is explicit that I do not do that unasked. So a fresh clone is still ~19 MB of history while every checkout is 33%
smaller. Recorded in the table row so the number is not mistaken for "the repo is now small".

Full suite **2429 passed, 7 skipped**; `ruff` clean. No test referenced any of these images, which I checked before
touching a byte.

## §48 — Gap 129: the third state, after measuring that a retune cannot work (2026-11-05)

**FIXED, and the shape is different from what the entry recommended.** The register asked to separate "a typo fix"
from "a real edit" by tuning. I measured it on one real sentence through the real function and the retune is
impossible — not hard, impossible:

| case | ratio | old verdict | new verdict |
|---|---|---|---|
| unchanged | 1.000 | still present | `unchanged` |
| comma only | 1.000 | still present | `unchanged` (normalised away) |
| **typo fixed** | **0.992** | still present | `changed` |
| **two-word deletion** | **0.950** | still present | `changed` |
| one-word swap | 0.928 | addressed | `gone` |
| polite reword | 0.816 | addressed | `gone` |

The typo fix scores **higher** than the two-word repair, and the one-word swap the code already calls resolved sits
**below** both. There is no ordering the ratio can express, so every cutoff either credits a two-word edit as a fix or
denies a typo fix. That is the finding; the threshold was never the bug.

**My first design was a middle band (0.90–0.95) and it was wrong in a way only measuring caught.** I assumed a band
would capture "edited a little". It captures the one-word swap — which the code already, correctly, calls resolved —
and leaves the typo fix (0.992) outside it, in `unchanged`. The bands were the wrong way round because the ratio does
not rank cosmetic against substantive at all. So I redefined `changed` as **exactly the fuzzy branch**: the quote is
not literally present, yet an element still matches it at 0.95. That is precisely the set where the old label lied —
the desk said "still in the script, untouched" about text the writer had changed — and it asserts only what was
measured. Both facts are pinned by tests, including the inversion, so if the ratio ever starts ordering the cases the
suite says so and the design can be revisited.

**What the desk may claim.** `unchanged` (literally still there) / `changed` (edited, still the same line) / `gone`.
Only `gone` is reported as addressed. `changed` stays **open** and the card says "edited — you decide", because
whether an edit was meant to answer the note is a judgement the writer makes, not a computation the engine can run.
Their existing `addressed` mark closes it — no new UI to learn.

**The counting contract was preserved, not changed.** `changed` counts as open exactly as `still_present` did, through
one `open_status_count()` helper that replaced every hand-written `still_present + unknown` expression. So every
total, chip, metric and pass-history point stays where it was. That is what made this landable in one commit: it buys
an honest label, not a different number. A test asserts the old expression yields **0** for a row set of 5 edited
findings, so the omission cannot come back silently.

**The revert caught a weakness in my own tests.** Reverting only the engine wiring left **22 of 23** tests passing,
because most of the file calls `quote_change` directly — it proved the function and not the connection. I added two
tests that drive `/api/projects/<name>/edits`, the route the SPA actually reads, and then the revert fails 2. With the
counting also reverted, 4 fail. Worth recording: a suite that tests a pure function thoroughly can still be blind to
whether anything calls it.

**A test fixture of mine was wrong twice** — I guessed `Scene(heading=...)` and a three-argument `ScriptDocument`, and
every test errored on the constructor. I copied the shape from `test_quote_agreement.py`, the file that already
exercises this function, rather than inventing a third variation.

**Not covered:** `diff.py`'s draft-to-draft delta still buckets `resolved`/`still_present`. That compares two drafts,
not the working copy against the parse-of-record, so it is a different question with a different contract; filing it
as a follow-up rather than half-fixing it here.

`tests/test_quote_changed_status.py` (25 tests) + 6 node tests. Full suite **2454 passed, 7 skipped**; `ruff` clean.

## §49 — Gap 131: the custom provider now survives a restart (2026-11-05)

**Filed and fixed in the same pass, at the owner's request.** The ask was a custom provider — base URL, model, API
key, connect check, connected status, saved config. Four of those six already existed. The last two did not, and the
measurement is the entry:

```
process 1: POST /api/config {"connection_mode":"remote",
                             "server_url":"https://api.example.com/v1",
                             "model":"gpt-4o-mini","api_key":"sk-…"}  -> 200
process 2 (fresh interpreter, same projects dir):
           server_url = http://127.0.0.1:8099   model = None   token = MISSING
```

**Save never reached disk.** `POST /api/config` was a write to process memory, so every restart silently reverted the
provider. The button said Save and the app behaved as if it had. And the connect check's result lived in the browser
tab, so "connected" described the moment the page loaded — nothing could answer "was this answering ten minutes ago",
and a second tab started blank.

**What was added.** `<projects>/.studio_provider.json` (atomic write, **0600**, because it now contains a secret) is
written on every successful save and applied at startup; `api_key_origin` travels with the token so gap 57's approval
survives too, or a restart would treat a saved secret as an unapproved one. The probe records
`checked_at/ok/model/destination` to `.studio_connection.json`, and a `provider` block on `/api/config` (GET and POST)
and `/api/health` reports what is configured, whether it is durable (`saved_to_disk`), and the last check — with
`stale` when the configured endpoint is no longer the one that was checked.

**Three properties I treated as equal in importance to the feature**, because a settings file that carries a secret
and an endpoint is a security surface:

1. **The file is owner-only.** Created `0600` at `open()` time rather than chmod-ed afterwards, so there is no window
   where the token is world-readable. A test asserts the mode.
2. **No route returns the token** — `/api/config` and `/api/health` are checked for the literal string.
3. **A settings file cannot grant remote permission.** `load_provider()` applies values through the normal setter, so
   a remembered remote URL is refused unless the operator opted in at launch. Verified as a negative: with
   `_ALLOW_REMOTE_SERVER = False` and `https://evil.example.com/v1` in the file, the desk stays on loopback. Without
   this, the fix would have handed the guard an on-disk write path — the one thing the launch flag exists to prevent.

**Honest green, not a fresh-looking one.** `connection_report()`. The status says "Connected 4 min ago — model-x", and
"Last checked just now, against a different endpoint" after the endpoint moves. I deliberately did **not** carry the old
verdict forward: `ok` becomes `None` when `destination` no longer matches, because a remembered green describing a
provider it never tested is the same class of defect as the ones this register keeps finding.

**Two of my own tests were wrong, in the same instructive way.** `test_the_record_survives_a_restart` and
`test_a_failed_probe_is_remembered_too` recorded a check for `provider.example.com` / `127.0.0.1:1` while the fixture
still pointed at loopback, then asserted the record was current. It was not, and it should not have been — the staleness
rule doing its job is what made them fail. The code was right both times; I fixed the tests and pinned the rule as its
own test so the distinction is explicit.

**Evidence.** 20 Python tests; reverts measured per half — **7 fail** with persistence removed, **3** with the probe's
recording removed. 7 node tests for the badge wording. Served-asset wiring verified (panel ids present in the HTML the
app actually returns, renderer called from 4 sites, CSS rule present). Full suite **2474 passed, 7 skipped**; `ruff`
clean; 42 JS tests.

**Not claimed.** The file is not encrypted — it is a plaintext secret at 0600, which is the same posture as the project
manifests' `api_key` field and is stated rather than implied. There is no keyring/OS-credential-store integration; that
would be the next step if this ships to non-technical writers. And a *read-only* install directory means
`saved_to_disk: false` — the writer is told the setting will not survive a restart instead of being given a false green.

## §50 — Gap 5: the stop button was honest about asking and dishonest about the answer (2026-11-05)

Gap 5 was filed as three claims and graded A with one C inside it. All three were real, but the
recorded shape of claim 1 was wrong, and my first test suite was wrong in a way that nearly shipped
a fix I had not earned. Both corrections are below, because the register is only useful if it
records what measurement changed.

### What the entry said, and what measurement showed

The register said the pipeline "checked only at stage boundaries". The census was sharper: 11
`_cp()` calls, the last at line 1686 — before step 6b, the genre check. Everything after it ran
unchecked: step 7's gating, step 8's five demote-never-drop passes, step 8e's **observation pass**
(the run's only remaining model-backed pass), the verification summary, the evidence depth, and the
`return` at line 1855. That is 169 lines of unguarded work, not a boundary-precision problem.

It mattered more than "the run reports the wrong flag", which is how I had it filed. On the real
route, with the real pipeline and a real model server, the sequence was:

1. Stop clicked while the run was inside the closing passes → `200 {"cancel_requested": true}`;
2. the pipeline returned a **full result**;
3. `stage_generation` → `publish_generation` → `mark_complete("analyze")` ran in that order, so the
   run **published a new generation over the writer's previous report** and set the stage `complete`;
4. the writer was told "Analysis complete".

So the defect was not a mislabelled outcome. The button said *stop*, the server said *stopping*, and
the system replaced the one artifact the button exists to protect. That is data loss reachable with
one click, which is why the fix is not "improve the label".

### The fix, and why exactly two checks

Two checks, each earning its place by a property a test can falsify:

- **Before the observation pass** — a stop that had already been requested was still followed by a
  model-backed pass: one call per ungrounded finding, capped at 24 by default. A cancelled run must
  not spend the writer's time and tokens. (Reverting this check fails exactly one test.)
- **Immediately before `emit("done", "complete")`** — everything above only shapes `result` in
  memory; the `return` is what lets the caller publish. This single check is what makes publication
  impossible past a stop, regardless of which closing pass the writer interrupted. (Reverting it
  fails three tests, including the real-route one that reads `report.md` off disk.)

I did **not** sprinkle checks between the closing passes. Those passes are pure functions over an
in-memory list; a check between them would buy nothing a check at the end does not already buy, and
a guard that cannot be falsified is worse than no guard — it reads as coverage. The one place a
mid-window check earns its keep is in front of the model call, which is why there are two.

### My own errors

**Error 1 — the tests were passing for the wrong reason.** My first two route tests set *their own*
`threading.Event`, while the route hands *its* event (`_ANALYZE_CANCEL[name].is_set`) to the
pipeline. The stop therefore never reached the run, the test "proved" the guard was missing when it
was fine, and I almost recorded a false negative against working code. The tell was that the
standalone pipeline version passed while the route version did not — the same property, two
different harnesses. Fixed by setting the event the run is actually watching, and the test now
asserts the event exists so this cannot silently regress to the same empty gesture.

**Error 2 — a vacuous assertion.** My first version of the pre-observation test compared
`len(calls)` to itself (`after == len(with_observation)`). It could not fail. Worse, once rewritten
to a real assertion, it *still* passed with the check removed, for two compounding reasons: the
suite switches the observation pass off globally (`tests/conftest.py:53`, for runtime), and my
anchor was `logline_test/complete` — but `genre` is the last category pass, so an *older* check
caught the stop before the window was ever entered. Both are now fixed: the test turns the product
switch back on for its own run, and it anchors on the measured last pass. It fails without the
check and passes with it.

**Error 3 — process, not code.** I burned a turn on ~20 sequential single-purpose tool calls and
hit the limit. The cause was reading one grep, one `sed` range and one test file per call instead of
batching them; and then, mid-revert, restoring a backup from `/tmp` that the sandbox had cleared —
the `cp` failed and I did not check it, so a half-reverted `pipeline.py` sat in the tree. It was
caught by grepping for the checks before running anything, and the working tree was re-established
from `origin` (`cddb4a3`) with a `--mixed` reset that never touches files. The lesson is the same
one as error 2 in a different costume: **verify the state you think you are in.**

### Claim 2, and why it was graded C

`runAnalysis()` awaited the POST and then unconditionally appended "Analysis complete. The report is
now grounding this conversation." There was no branch on `ack.cancelled` anywhere in `app.js`. The
retry path was worse: it never read the body either, so a stopped retry announced "the report has
been merged and updated" over a report that had not been merged — and it ran with **no Stop control
at all**, because the desk ladder belonged only to Run Analysis.

The fix is one terminal handler (`settleCancelledRun`) and one wording helper (`cancellationNote`),
so the two watchers — the response handler and the 2s poller — cannot word the same outcome
differently. The wording is honest about what it can promise: with a previous report it says it is
unchanged; on a first run it says no report was written. Saying "your previous report is unchanged"
to a writer who never had one would be the same lie in the other direction.

### What is still true, and deliberately not fixed

A stop cannot interrupt a model call already in flight. The check lands **between** calls. This is
the existing co-operative contract and is why the UI says "the current stage finishes"; a hard
abort would mean killing a socket mid-write and the register's own text asks for the limitation to
be *clear*, not removed. After the fix, the writer pays for at most one call they cancelled, not 24.

### Verification

- `tests/test_cancellation_lifecycle.py` — 13 tests: publication blocked at three positions in the
  closing window, between model passes, no-stop-invisibility, the routes' `cancelled` contract, the
  retry, the run-scoped event (no leak on success or failure), and the stop endpoint's 409/200 scope.
- 4 node tests pin `cancellationNote` / `isCancelledAck` / `isStopRace`; `isCancelledAck` rejects
  truthy non-booleans so a stray value cannot be read as a stop.
- Reverts, measured separately: **3 fail** (publication check), **1 fail** (pre-observation check),
  **5 fail** (both) — restored, 13 pass.
- Full suite after the fix: **2482 passed, 7 skipped**; `ruff` clean; 46 node tests.
- Pre-existing, unrelated: 5 failures in `test_production_readiness.py` (CI timeout declarations)
  and `test_repo_hygiene.py` (audit scratch paths). Confirmed pre-existing by stashing my changes
  and re-running them against `cddb4a3` — identical 5 failures, so they are not a regression here.

## §51 — Gap 16: watch mode could destroy the file it was watching (2026-11-05)

The register called this "watch-folder processing can overwrite source files — release blocker
for watch mode". Like gap 5, the severity was right and the shape was wrong: it was not one
overwrite path but three ways a drop could disappear, and the worst of them had nothing to do with
overwriting.

### What was measured, before any change

Real directories, real `process_pending()`, real files:

- **A — the overwrite the register described.** Two different scripts dropped under the same
  filename (`draft.fountain`) one after the other left **one** file: `done/` held the second
  script's text and the first was gone. `shutil.move(path, os.path.join(done_dir, name))` reuses
  the name; on this OS the second move replaced the first.
- **B — the failure path, which the register did not describe.** With `ProjectManifest.create`
  raising ENOSPC, the move still ran: the source was cleared from the inbox and filed under
  `done/`, while no project existed anywhere. The gate was `if move_done and (result["ok"] or
  result["error"])` — an explicit "move on success *or* failure". The writer's script was marked
  complete and was not.
- **C — the same gate, reached later.** Failing `manifest.save()` (after the copy succeeded)
  produced the same outcome.

B and C are the interesting ones. A says "don't clobber"; B says "don't archive a failure as a
completion", which is the same class of lie as gap 5's "don't announce a stopped run as complete".
It is worth noticing that both blockers were the same defect wearing different clothes: **the
system knew an operation had failed and told the writer it had succeeded.**

### The fix, and what each part defends

- **Collision-safe filing.** `_reserve()` creates the destination with `O_CREAT|O_EXCL` and walks
  to `stem_2.ext` on `FileExistsError`. This is also the cross-worker guarantee: two watchers
  filing the same name cannot both win a reservation. `_file_into()` removes the empty placeholder
  if the move itself fails, so a failed filing never leaves a zero-byte `done/` entry that looks
  processed.
- **`failed/` with a note.** A failed drop is moved to `failed/<name>` beside
  `<name>.error.txt`, which states the error, that the source is untouched, and how to retry (move
  it back). Nothing auto-retries: a permanent error — a disk that is full — would spin forever, so
  the retry is the writer's decision and the note says so.
- **Atomic claiming.** Each file is renamed into `<watch>/.processing/<uuid>/` before any work.
  `os.replace` is atomic on one filesystem, so exactly one worker owns the drop; a crash mid-run
  leaves the script in `.processing/`, which is visible and recoverable, rather than deleted. This
  did not come from the register's recommendation list by accident — "cross-process claiming" was
  in it, and without it two watchers would have hit defect A *and* processed a script twice.
- **`filed` in the result record.** The old record could not express "where did the source go", so
  a caller had to assume `done/`. It now reports the actual path, which is also what makes the
  tests location-agnostic.

### My own errors

**Error 1 — the pre-existing suite caught my regression, which is the system working.** I wrote the
filing gate as `if result["ok"]: … elif not move_done: …`. That reads naturally and is wrong:
`move_done=False` means "process in place", and it applies to a *successful* drop too. My version
filed a successful `move_done=False` drop into `done/` and cleared the inbox.
`tests/test_watch.py::test_move_done_false_keeps_file` failed immediately. The gate belongs first,
before the success branch. I did not touch that test — it was right and I was wrong.

**Error 2 — a revert that measured the wrong thing.** My first no-clobber revert replaced the
whole reservation function with a bare `os.path.join`, which also dropped the `os.makedirs` the
callers relied on. Filings then failed, sources were stranded in `.processing/`, and the failures
were reported against unrelated tests (the failure-note and success-path ones) rather than the two
collision tests. A revert is a measurement; a revert that breaks something else is not the
measurement I wanted. Redone as "keep the directory creation, drop only the exclusivity", it fails
exactly the two collision tests.

**Error 3 — a markdown pipe inside a table cell.** Writing `O_CREAT|O_EXCL` into a table row added
a sixth cell and broke the table's shape. Caught by counting cells with `awk` after the edit
(`6` where the row needed `5`); fixed by writing `O_CREAT + O_EXCL`. Worth stating because the
register is read as a table and a silently malformed row is a real defect in the artifact.

**Error 4 — the location-agnostic repro.** My first reproduction script hard-coded `done/`, so
running it against the fix crashed on a missing directory instead of reporting a result. The script
then measured nothing. Rewritten to use the result's own `filed` path; it now reports a verdict on
both the old and the new code, which is the only way it can be evidence.

### Verification

- `tests/test_watch_source_safety.py` — 11 tests: both same-named drops retrievable and at
  distinct paths; a failed copy and a never-durable manifest each not filed under `done/`; the
  failure note names the error and says the source is intact; no phantom project directory; the
  happy path unchanged; `move_done=False` honoured on failure; a two-thread claim race processed
  exactly once and reported exactly once; `.processing/` clean after a run; and the documented
  retry path (move the file back) actually re-processes it.
- Reverts, measured separately and cleanly: **2 fail** (no-clobber removed), **3 fail** (the
  `ok or error` gate restored), **2 fail** (the claim removed); restored, 11 pass.
- Full suite: **2493 passed, 7 skipped**; `ruff` clean. The same 5 pre-existing
  production-readiness/repo-hygiene failures remain, unchanged and unrelated (verified earlier by
  stashing my changes and reproducing them on `cddb4a3`).

### Still open, deliberately

A drop interrupted by a crash sits in `.processing/` and is **not** automatically recovered on the
next run. That is a deliberate choice, not an oversight: automatically re-processing a claim left by
a crashed worker can duplicate a project, and the register's own rule for this entry is "never
treat failed work as completed" — not "guess what the crash meant". The file is preserved and
visible; a future entry can add an explicit recovery command with an ownership timeout, but that
needs a decision about who owns a stale claim across processes, which is a larger change than this
blocker.

## §52 — Gap 17: an over-broad assertion, and a flush that waited on the wrong thing (2026-11-05)

Gap 17 was filed as "browser accessibility/security tests and unload saving need follow-up", with
three legs and no confirmed product defect. Two of the three legs turned out to contain real work.
The third is unchanged, and the browser legs still were not run — so this section is explicit about
what was *not* verified.

### (a) The XSS leg: the register's guess, now proven

The register said the dashboard failure "appears to be an overly broad serialization check, **not a
demonstrated XSS vulnerability**; retain the structural probe and improve test precision". That was
right, and the mechanism is visible in two lines: `renderDashboard` sets

    card.title = `Open "${p.title}" on the desk`;

so the payload lands in a **quoted attribute value**. `outerHTML` serializes that literally —
`title="Open &quot;<img src=x onerror=...>&quot; on the desk"` — which contains the substring
`<img` while the structural probe in the same scan reports `handlers == 0, exec == 0`. The suite
failed twice on its own check.

The fix is `markup_outside_attributes()` + `has_raw_tag()`: strip quoted attribute values, then look
for `<tag` in what remains. It is a text check, so it still runs against the serialized string the
leg already collects, and it is strictly better than what it replaces: it cannot be fooled by an
escaped payload in a title, and it still catches a genuine tag anywhere outside one. Both legs that
used the substring now use it.

I kept the structural probe exactly as it was. The register asked for precision, not for a weaker
check, and `handlers`/`exec` are what actually prove inertness.

### (b) The unload leg: a real defect, found by reading the guard

The register framed this as "an intermittent test or product risk, not yet a confirmed
deterministic data-loss bug" and asked for stress tests rather than a fix. Reading the code instead
found a deterministic one:

    window.addEventListener("pagehide", () => {
      if (!state.currentIdea || !state.inIdea || !ideaSaveTimer) return;

`saveIdeaContent()` is the function that clears `ideaSaveTimer`, and it does so **on entry**, before
its POST is sent. So for the entire duration of an in-flight save the timer is null while the server
does not yet have the writer's last lines — and that in-flight request is precisely the one a
pagehide aborts (a normal fetch dies with the document; only `keepalive` survives). Closing the tab
mid-save therefore sent nothing at all, with no error, and the words were the only copy.

The fix moves the decision from a timer to the text: `unloadFlushPayload(editorText, savedText,
pendingTimer)` returns what to send, and returns null only when the editor already matches the last
confirmed save with no debounce outstanding. `unloadFlushUsesKeepalive()` exists so a future edit
cannot quietly drop `keepalive`, which is the one send where it matters.

### How the unload fix was verified without a browser

This is the part I am least able to prove, so I made the evidence as strong as the environment
allows. The node test **extracts the real `pagehide` listener body from `app.js`** (balanced-brace
slice) and runs it with a stub `api`, stubbing `$` and `state` — so the shipped handler's own control
flow is under test, not a reimplementation of it. With the old guard restored, the mid-save test
fails (`nothing was sent`); with the fix, it sends the unconfirmed text with `keepalive: true`.

That is not a browser run. A real pagehide, a real aborted fetch and a real `sendBeacon`/keepalive
delivery path are still unverified, and the file says so in a test whose only job is to record it.

### What I could not do, and did not fake

The Chromium legs were **not run**: no system browser exists here and the Playwright download is
blocked (the CDN is outside this environment's network allowlist). I did not weaken the browser
suites to make them "pass", and I did not mark the entry FIXED — it is PARTLY FIXED, with the two
parts named and the unrun part named. The live-region repeat leg is untouched because its open
question ("does AT re-announce an identical string?") is genuinely not observable from the DOM, which
is what the suite's own comments already say.

### My own errors

**Error 1 — a test with a false premise.** I asserted `markup_outside_attributes('<a href="/p?q=1">…')
== input`, on the theory that markup with no quotes is returned unchanged. The input plainly has a
quoted value; the helper was right and my expectation was wrong. Rewritten to assert the real
contract (quoted spans removed, structure kept) plus a separate no-quotes case.

**Error 2 — a harness that could not observe the thing it tested.** My first extraction passed
`ideaSaveTimer` by value, so the handler's `ideaSaveTimer = null` was invisible to the test and the
"debounce is cleared" assertion failed against correct code. Fixed with a holder the wrapper writes
back in a `finally` (the body has early returns, so a plain write-back would have been skipped).

**Error 3 — the ESM/CommonJS split.** `import` at the top made Node treat the file as ESM, and
`__dirname` does not exist there — the file failed to parse before any test ran. Matched the
repository's convention (`require`, as `core.test.js` and `verification_readout.test.js` do).

**Error 4 — a revert aimed at the wrong line.** My first "restore the substring check" revert edited
the browser suite's call site, which the new test does not read, so it reported 13 passed and proved
nothing. Aimed at `has_raw_tag`'s body instead, it fails 4 tests — which is the measurement.

## §53 — Gap 19: the Stash cut writing and called it a save (2026-11-05)

A one-line defect with a five-line consequence, and the clearest example yet of the pattern these
two blockers share: **the system performed a destructive action and reported success.**

### Reproduced, and worse than filed

`add_to_stash` saved `text[:4000]`. Measured: 4,004 characters in, exactly 4,000 stored, the tail
gone, no error, `201` from the route, "Stashed ✓" in the UI. The register recorded the store-level
fact; the route-level fact is what makes it a writer-facing data-loss bug — the only copy of those
characters was the writer's clipboard, and the UI had already been told it was safe (the selection
float clears the selection after a successful stash).

The record was also unable to describe the loss: the returned entry has no field for "this was cut",
so no surface could have reported it even if someone had thought to.

### What the fix is, and what it deliberately is not

The bound itself is not the defect — 4,000 characters is ~2-3 pages of screenplay and the Stash is a
scrapbook, not a second copy of the script. Three small changes:

1. **Refuse, don't slice.** Over-bound text raises `ValueError` naming the actual length and the
   bound, and stating that nothing was saved and nothing was cut. The route turns that into a `400`,
   so the writer sees a sentence instead of a false success. The refusal is atomic: a refused entry
   creates no file at all (tested).
2. **Serve the bound.** `GET .../stash` now returns `max_text_chars`, and the selection float
   refuses locally before the round trip. This is the difference between "the server said no" and
   "the button never lied to you".
3. **Report legacy cuts, never rewrite them.** Entries saved by the old code carry `len(text) ==
   4000` as their only evidence. `entry_truncated()` reports that, and reports `dropped: None` —
   *unknown*, not zero — because the original length was never recorded. Inventing a count would be
   the same class of lie in the opposite direction. The entry is served byte-for-byte as stored and
   marked in the list, because rewriting it would destroy what survived.

I considered raising the bound instead. That would have moved the cliff without removing it, and the
same silent loss would happen at 8,000. The invariant worth keeping is "nothing is lost without
being told", and refusal is the only version of that a store can enforce on its own.

### Verification

- 11 tests: refused-not-cut (the exact 4,004 measurement), nothing written on refusal, the boundary
  saved whole including its last character, Unicode measured in characters with its final glyphs
  intact, the bound as a named constant, a legacy entry flagged with `dropped: None`, a normal entry
  not flagged, the served bound, `400` with both lengths in the sentence, at-the-bound accepted, and
  the proposal path (model-generated text of unknown length) refused the same way.
- Reverts: **5 fail** with the silent slice restored; **1** with the served bound removed.
- Full suite **2519 passed, 7 skipped**; 56 node tests; `ruff` clean.

### One incidental discovery, recorded honestly

The suite had been reporting `5` pre-existing failures. After I repaired the stale git HEAD in this
session (origin was 61 commits ahead; a `--mixed` reset fixed the index without touching files), the
two `test_repo_hygiene.py` failures disappeared — they were a symptom of the broken index, not of the
code, and they pass in isolation. The `3` production-readiness failures remain, are unrelated to
anything here, and are unchanged.

## §54 — Gap 24: three omissions stacked, and one of them was in the test's shape (2026-11-05)

Gap 24 was filed as "native Telugu speaker cues are missed in a plain-text example", with an
explicit caution not to infer that all Telugu text parses incorrectly. The caution was well placed,
and the reproduction was still worse than filed: the script parsed to **zero scenes**.

### Reproduced, in three layers

The filed symptom (no speaker detected) is the *visible* part of three distinct defects, which is
why fixing any one of them alone would have produced a plausible-looking non-fix:

1. **The script table.** `_script_share` counted Devanagari and Tamil only. A Telugu cue scored 0
   script characters, so the caseless branch never fired and the line went to the all-caps test,
   which no caseless line can pass. The heading tokens were in no table either, so
   `లోపల. హాల్ - ఉదయం` — an ordinary Telugu INT. heading — matched nothing and opened no scene. Every
   line then landed in front matter: zero scenes, zero speakers.
2. **The lookahead.** Fixing (1) made `సీత` parse and left `రాము` as ACTION, which looks
   arbitrary and is not. `రాము`'s dialogue line is `నేను వెళ్తున్నాను.` — four characters, short
   enough to pass the caseless *cue* test itself, so the lookahead concluded "the next line is
   another cue" and refused `రాము`. `సీత` only worked because `సరే, జాగ్రత్త.` is longer. The
   discriminator that was missing: **a character name does not end a sentence.** Adding it fixes
   the same asymmetry in Hindi and Tamil, which the register had no reason to suspect.
3. **The heading token list.** Telugu's own list was missing `లోపల` and `ఎక్స్ట` — tokens that
   `parse_scene_heading` accepted, so the two halves of the same feature disagreed about what a
   heading was.

### Why the fix is structural, not three patches

(1) and (3) are both "a list that has to be kept complete by hand". So:

- the caseless set is now the ten Brahmic scripts written without case, not the two that were
  reported (a writer in Kannada, Malayalam, Bengali, Punjabi, Gujarati, Odia or Sinhala had the
  identical bug and no way to know);
- `NATIVE_SCENE_HEADING_RE` is **derived from the INT./EXT. token tables**, so "a token
  `parse_scene_heading` accepts is a token `looks_like_scene_heading` accepts" is true by
  construction rather than by review. A property test walks every token in every table and
  asserts exactly that, so the next language added cannot reintroduce the split.

(2) is one line with a real justification, not a heuristic widening: `SENTENCE_END_PUNCT` covers
`.`/`?`/`!` and the danda/double-danda, and only applies inside the caseless branch — where the
all-caps signal that normally separates a name from a line of dialogue does not exist.

### My own errors

**Error 1 — three of my test expectations were wrong, in two different ways.** I asserted
`_script_share("రాము") == (4, 4)`; the real answer is `(4, 2)` because Telugu vowel signs are
combining marks and `str.isalpha()` is False for them. That is not a curiosity — it is *why* the
existing cue test compares `script_chars >= letters * 0.8` instead of to `len()`, and my expectation
would have hidden it. Separately, I asserted a forced cue `@రాము.` keeps its period; the parser
strips it by design (`normalize_character_name` does `rstrip(".")`). Both replaced with assertions
of the real, documented contract.

**Error 2 — a stale bytecode cache made a revert measurement lie.** After restoring
`heuristics.py` from a backup, the "restored" run still failed 2 tests. The file was byte-identical
to the backup — but restoring happened within the same second and the file size was unchanged, so
Python reused the `__pycache__` entry compiled from the *reverted* source. I nearly recorded a
false failure against correct code. From now on the revert runs use `-B` (no bytecode writes), and
I cleared every `__pycache__` in the tree first. This is the same lesson as the `/tmp` restore in
§50, in a subtler form: **verify the code you think you are running.**

**Error 3 — I corrupted the register with my own edit and nearly shipped it.** My first attempt at
appending to entry 24 was written with a stray `if False else None` guard; the guard made the
*intended* single-line edit a no-op and let a second, unguarded write run instead — which **appended
336 lines, duplicating entries 25-32** in the plan. The commit went through with it (337 insertions
where one line was intended). I caught it by looking at the diffstat rather than trusting the edit:
one row cannot add 338 lines. The file was restored from `HEAD~1`, the edit redone, and the commit
amended — the committed tree has entry 25 exactly once and the file is back to 507 lines.

The lesson is the one this whole session keeps re-teaching: **read the shape of the change, not
just its exit code.** A `git diff --stat` that is absurd for the work is a failed test.

**Error 4 — a probe that crashed instead of measuring.** My reproduction script assumed
`doc.elements` and `scene.heading`, neither of which exists (`ScriptDocument.scenes`,
`Scene.heading_raw`). Two runs were wasted on `AttributeError` before it printed a single fact.

### Verification

- 19 tests: the reported case end to end (a scene exists at all, cues as CHARACTER elements, both
  speakers detected, dialogue attributed to the right speaker, action stays action), four Telugu
  heading variants, the short-dialogue rule in Telugu *and* in Hindi/Tamil, the forced-cue escape
  hatch, Hindi and Tamil full-script controls, English untouched, the script-table coverage, and the
  token-table property test.
- Reverts, measured separately with `-B`: **7 fail** (script set narrowed), **7 fail** (sentence-end
  rule removed), **2 fail** (two heading tokens dropped). Restored: 19 pass.
- Full suite: **2538 passed, 7 skipped**; `ruff` clean. The same 3 unrelated production-readiness
  failures remain.

### What this does not claim

Native-script parsing is still heuristic. A one-word name, a name ending in a period, or dialogue
that is genuinely ambiguous with a cue will still need Fountain's `@` escape hatch — which is
tested here and works. The register asked for "consented native-script fixtures and independently
reviewed ground truth", and this change has neither: the fixtures are synthetic and my own. What it
does have is a property (`script in a table ⇒ recognised as a heading`) that does not depend on
anyone's judgement about a particular sentence.

## §55 — Gap 27: an off-by-one, a dishonest label, and a scene charged to the wrong page (2026-11-05)

The register called this "pacing segment boundaries can misplace scenes" and named `int(page // 5)`.
The reproduction matched it exactly, on a controlled document with scenes ending on pages 5 and 10:
**zero** scenes in 1–5, **both** in 6–10. Three defects fell out once I started measuring the
boundaries instead of the one case.

### The three, and why each is more than a tweak

1. **Boundary.** `5 // 5 == 1` files page 5 — the last page of the segment labelled 1–5 — into
   segment 2. In the filed case that emptied segment 1 entirely. Fixed by `segment_of_page`, which
   is 1-based and inclusive, and by a table test over pages 0, 0.5, 1, 4.999, 5, 5.0001, 6, 10, 11.
2. **Labels.** `total_pages` was the last scene's *end* page, and every segment's `page_end` was
   `min((i+1)*n, ceil(total))`. So the number of segments depended on where the last scene stopped
   finishing: a 10-page script whose last scene ended on page 5 reported **one** segment and filed
   everything into it, and the label `1–5` was both the count and the clamp at once. `total_pages`
   is now the span the labels describe, and a test asserts the labels are contiguous and that the
   last one equals `total_pages`.
3. **Distribution.** A scene was charged wholly to the segment containing its end page. The register
   said this "is an estimate, not an observation", which was right but understated the failure: the
   bucket a long scene was dropped *from* still contained pages of that scene, so it could read
   **zero words** while being half full. That is not a rounding error, it is a chart that lies about
   where the writing is.

### The convention, which I got wrong first

I split words by the fraction of `[start, end]` inside each segment. It passes the filed case and
is wrong: `share_over_segments(10, 12)` returned `{3: 1.0}` — the whole scene in 11–15, with
`spans_boundary` flagged True on the same row, admitting it had crossed while charging it as if it
had not. The bug is the interval: a scene "from page 10 to page 12" **occupies pages 10, 11 and 12**
— a writer counting pages counts three — so the occupied span is `(start-1, end]`, and segments are
`((k-1)*n, k*n]`. With that, 10→12 is `{2: 1/3, 3: 2/3}` and `1→5` is still exactly one bucket.

I caught this because I printed `share_over_segments` directly rather than only asserting the
end-to-end case. The direct probe disagreed with the flag already on the row, and the flag was right.

### Two more of my own bugs, both caught by the tests

- **A crash.** `segment_of_page(None)` raised `TypeError`. A text parse supplies `page_start=None`,
  so the pacing curve would have died mid-report on exactly the scripts that have no real
  pagination. Now `None` clamps to segment 1.
- **A nonsense span.** With `page_start=None` I still ran the page-span split, using `end - 1` as an
  invented start — so a 40-word scene was charged **1 word** to its segment. A position that is only
  known as an end has no span to split; such scenes are attributed wholly to their end segment, and
  a test pins the 40 words.

Both of these were introduced by *my* fix, not the original code. They are the strongest argument
for the revert-measurement discipline: the guard tests are what noticed.

### Verification

- 27 tests: the filed case; the boundary table and other segment lengths; contiguous inclusive
  labels; `total_pages`; a short last scene not collapsing the count; split by page span with
  conserved word totals; shares summing to 1 across five spans; one-page and contained multi-page
  scenes *not* split; the `None`-page path; dialogue split like action; empty document; and the
  rendered Markdown carrying `~` plus the legend — and *not* carrying either when no split occurred.
- Reverts, measured separately with `-B`: **10 fail** (boundary), **7** (labels), **2** (split),
  **1** (report mark). Restored: 27 pass.
- Full suite: **2562 passed, 8 skipped**.

### An environment note that matters for reading the suite

The two `test_repo_hygiene.py` failures reappeared this session and were **not** a regression: those
tests import `e2e_browser_gun_pen_audit` to read its `SHOTS` constant, and that module imports
`playwright` at module level. With `playwright` uninstalled they fail with `ModuleNotFoundError`
that has nothing to do with hygiene. Installing the package makes them pass. I record this because
last session I had reported them as fixed-by-the-index-repair; that was one cause, and this is
another. A test whose setup dependency is a browser automation package is fragile, but changing it
is a separate concern from this gap.

## §56 — Gap 30: the budget protected one sixth of the turn (2026-11-05)

The register said "the turn's actual model payload can exceed its declared prompt budget".
Reproduced through the real engine: `prompt_budget=2048` with three long scenes sent a
**29,971-char system message and a 30,369-char payload** against a 2,048 budget. The filed
figure was 39,117 / 39,508 — same defect, my fixture was slightly smaller.

### The register's framing was too generous

It described the budget as "not a hard bound on the complete payload", as though the check had
simply missed a block or two. It had not missed a block. It bounded exactly one function, and the
turn was assembled by a different one that took no budget argument at all:

    build_system_prompt(..., budget=2048)   -> 7,277 chars, trimmed as asked
    _assemble_messages(...)                 -> appends, unbudgeted:
        scene block                         62,484 chars   <- `build_scene_context_block` had no budget parameter
        quote context, few-shot examples, trait reminder, post-history reminder, history window

So the number that claimed to protect the turn protected about a sixth of it, and the part it did
not protect was the part that grows without limit — the script itself. Severity: the same grade A,
but the diagnosis in the register was wrong about *what* was unbounded, which matters for the fix.

### What the fix does

1. **The limit governs the whole turn.** `_assemble_messages` takes the budget, holds back a reply
   reserve (`PROMPT_REPLY_RESERVE_CHARS`), and enforces the total on the finished message list.
2. **The scene block is sized from the room that is actually left** (`room_for_scenes`), and each
   requested scene gets an equal share so one long scene cannot starve the others. Text is cut at a
   line boundary with **both ends kept** — a writer asking what happens at the end of scene 4 needs
   the end of scene 4 — and the cut is marked in the text.
3. **Omissions are disclosed.** A scene that does not fit is named to the model as not shown, with
   an instruction not to summarise it.
4. **History is the last elastic block** and gives way first: an old turn is worth less than the
   scene the writer is asking about now.
5. **Below the irreducible floor the turn raises.** `PromptBudgetUnreachable`, with the numbers.
   The register asked for exactly this ("fail clearly if a required minimum cannot fit").

### The mistakes I made, in order

- **I put the refusal in the wrong place.** I made `build_system_prompt` raise and broke four
  existing tests. Those tests were right and I was wrong: the function is a *renderer*, and asking
  it what it can build under an impossible budget is legitimate (that is how the shed ladder is
  tested). The refusal belongs where the payload is assembled and sent. Caught by the suite, not
  by me.
- **A 0-means-unlimited footgun in my own helper.** `_base_prompt_budget` returned `max(0, budget -
  suffix)`. A budget smaller than the appended suffixes would therefore return **0**, and
  `build_system_prompt` reads 0 as "unlimited" — the exact silent-truncation failure the gap is
  about, reintroduced by the fix for it. Now clamped to 1.
- **Sizing the block in the caller.** I gave the scene block `budget // 2`, then `room_for_scenes`
  computed in the caller. Both were wrong because the caller cannot see the few-shot examples or
  the tail notes; measured overshoot of 1,882 then 286 chars. The sizing had to move into
  `_assemble_messages`, where everything that competes for room is visible.
- **Forgetting my own overhead.** The block still overran by exactly the length of the omission note
  I append when trimming — a note paid for from a budget that had not reserved it. Textbook, and I
  found it only by instrumenting the parts.
- **A false disclosure.** With no budget, a scene that is *not in the script* was reported to the
  model as "no room in the context". That invites the model to tell the writer to narrow their
  question, for a scene narrowing will never produce. Then my first correction over-shot and
  blamed a *budget* cut on the script. Both are the same error — one variable for two facts — and
  the fix was to track `absent` and `omitted` separately all the way through.
- **Two throws at the pinning test.** My first version asserted an end-to-end bound at a budget
  where nothing was trimmed, so **the revert passed**. That is the third time this session a test
  failed to pin what it claimed to pin, and it is the failure mode the whole revert discipline
  exists to catch. The final version asserts the contract directly: the renderer must be handed a
  budget that leaves room for what the engine appends after it.

### The revert matrix, and a measurement error inside it

My first matrix counted `FAILED` lines with `grep -c`. A **collection error** produces no `FAILED`
line, so three reverts printed `0` and I nearly recorded them as unpinned. They were *invalid
patches* — the replacement string did not match. Re-run with the patch verified (`grep -c` on the
reverted marker) and the real pytest summary line, the numbers were 6 / 9 / 8 / 4 / 1 / 2.

Six reverts, final: whole-turn off **9**; scene block sized by the caller **6**; windowing removed
**8**; refusal removed **4**; absent/omitted conflated **2**; base prompt trimmed to the full budget
**1**.

### What I deliberately did not do

No tokenizer. The register suggested comparing tokenizers, and that is a much larger change with a
model-specific dependency. The budget remains a character bound derived from the reported window at
2 chars/token, which the code already documents as a deliberate conservative approximation for
Indic scripts. I have not claimed that characters guarantee tokens, and I have not claimed the
shorter prompt is better — only that it now fits inside the number it declares.

## §57 — Gap 26: a label asserted what the text contradicted (2026-11-05)

The register filed this accurately, which is worth saying because it has not always been true
lately. Reproduced on its own fixture through the real parser: AJAY stands silently beside VENU in
scene 1 and speaks in scene 2, and the result was

    scene 1 characters_present = ['VENU']
    AJAY graph entry            = scenes_present [2]
    AJAY|VENU co-occurrence     = none
    prompt to the model         = "Characters: VENU"

### The defect is a label, but the label is load-bearing

`characters_present` is built from cues. It is the list of who *speaks*. That is a perfectly good
list, and the knowledge graph, the continuity checks and the arc analytics all consume it on that
understanding. The problem was one word in a prompt: it called the list `Characters`, which reads as
"everyone in this scene", and a closed list that omits a man standing in the room is an assertion
that he is not there. The register was careful to say this is a candidate limitation rather than a
proven model error — the full scene text travels with the prompt — and it was right to be careful.
But a prompt that says "Characters: VENU" over a scene containing AJAY is asking the model to
disagree with its own evidence, and it is asking in the register of fact.

### Three tiers, because two are not enough

My first fix added a "mentioned in the text" tier. That fixes the filed case and would have been
where I stopped — except that it does not reach the register's own harder case. RAVI is on the phone
and never gets a line: he is in no cue anywhere in the script, so he is not in `all_characters`,
and name-matching against `all_characters` cannot find him. He is invisible to the entire graph.

So there is a third tier — caps words in action/dialogue that are not known characters and not
obvious non-names — labelled `unconfirmed` with the reason in the prompt: a caps word in an action
line can be a prop, a sign or a place. That tier is deliberately weak, and it is not allowed to
create graph entries. It exists so the model is *told* something is there under that name instead
of being told, by omission, that nothing is.

### My errors

- **Two wrong test premises, again.** I asserted the "mentioned" qualifier against RAVI, who is
  correctly in the *unconfirmed* tier, and I assumed `scene_presence` was keyed by string when the
  neighbouring `scene_dialogue_counts` is keyed by int. Both were caught by running the tests, both
  are the same habit I have shown all session: writing the assertion from my model of the code
  rather than from what the code returns.
- **Listing speakers twice.** My first mention implementation reported VENU under both "speaks" and
  "named", which reads as two facts and invites double-counting. The mention list now subtracts
  speakers.
- **A gratuitous `not in ... or True` assertion.** I left one test line that can never fail
  (`assert "DOOR" not in unconfirmed or True`). It is dead weight and I should not have written it;
  it is recorded here rather than quietly deleted so the sloppiness is on the record.

### Verification

- 15 tests: the filed case at all three layers; evidence tiers per scene; the pair co-occurrence; a
  speaker never double-listed; the prompt's two new labels; the empty-scene disclaimer; the
  off-screen qualifier; RAVI reachable only via unconfirmed; V.O. treated as a cue, not a mention;
  heading words not promoted to people; the graph refusing to invent characters from unconfirmed
  names; `to_dict` round-tripping the new fields; and sort stability across three builds.
- Reverts, each verified applied and read from the pytest summary: **3** (mention tier), **6** (bare
  `Characters:` label), **2** (unconfirmed tier), **1** (speakers double-listed), **1** (`none`
  disclaimer).
- Full suite: **2602 passed, 8 skipped**, with only the three pre-existing readiness failures,
  which are about CI timeout declarations and unrelated to this gap.

## §58 — Gap 35: a 201 over six months of work (2026-11-06)

The register filed this accurately, and the fix was small. The interesting part is that **my first
two reproductions missed it entirely**, for a reason worth writing down.

### Two probes that proved nothing

Probe 1 wrote the fixture into `$SCREENPLAY_HOME/projects/The_Late_Hour`, which the app does not
use — the projects root is `./studio_projects` relative to CWD. Probe 2 used the right directory but
named the script `the_late_hour.fountain`. Real projects store it at `source.<ext>`
(`ProjectManifest.source_path`), so the sample wrote `source.fountain` *beside* the fixture and my
probe reported "writer's source preserved: True".

Both probes passed. The defect was there the whole time, and I had two green results saying it was
not. The lesson is not "check your fixture" in the abstract: it is that a reproduction which relies
on a filename I invented is testing my imagination, not the product. I only found the real gap by
listing what the route had actually written.

### The measurement

    before: 201
    source.fountain : "Title: The Late Hour / Author: Real Writer / INT. KITCHEN ..."
                   -> "Title: The Late Hour / Author: Sample Page / INT. WRITER'S ROOM ..."

A writer's draft, replaced by a demo, and a success code to say it went well. The register's own
wording — "this is a recovery hazard for that name and damaged/unreadable state, not evidence that
all projects are overwritten" — was exactly right, and I would have overstated it if I had stopped
at "the sample route overwrites projects".

### Why 409 and not 500

Nothing failed on the server. The request conflicts with state that already exists, which is what
409 means, and it lets the UI show a decision rather than an error. The message does three things
the old code did the opposite of: it names the files that are present, it says **nothing was
modified**, and it gives both recoveries — repair the manifest, or move the folder aside to get a
fresh sample. A writer told "your project is damaged" will assume the worst unless told otherwise,
so the reassurance is part of the fix, not a courtesy.

### The case the register flagged and nobody had tested

`except Exception` also catches `OSError` from a transient read problem. That is the case where
overwriting is least forgivable — the files were fine, the disk was busy — so it is now explicitly
tested with a monkeypatched `OSError` and asserted to take the safe path.

### Verification

- 12 tests: the filed reproduction; the caller told what happened; nothing in the directory touched
  byte-for-byte; no sample artifacts written; the fresh-sample path still returns 201; reopen is
  deduplicated (200); a restart does not re-create; a transient error does not reach the re-create
  path; a healthy project still opens; an unlistable directory refuses without crashing; an empty
  directory is allowed to take the sample; another project's file is untouched.
- Reverts: **5** (restore the overwrite) / **4** (500 instead of 409) / **1** (drop the
  reassurance). The 5 on the first revert is the number that matters: restoring one line breaks
  five independent assertions.
- Existing tests: `-k "sample or manifest or project"` gives 154 passed, 2 skipped. Nothing depended
  on the destructive path.
- One test of mine failed on a casing assumption ("NOT been overwritten" vs the actual "has NOT been
  overwritten"). Same habit as §57: writing the assertion from my model of the string.

## §59 — Gap 39: a success code over a failed batch (2026-11-06)

Filed accurately and fixed in one pass. The interesting part is methodological: **my first probe reported
`EXIT=2` for everything**, including a batch that should have succeeded, and I nearly wrote that up as
"the CLI does return nonzero". What I had actually captured was the exit status of the `grep` at the
end of my pipeline, not of Python. A `| tail` or a `| grep` swallows the status of the process you
care about and you read the status of the filter.

That is the same family of error as the `grep -c FAILED` miscount in §56 and the invented filename in
§58: **the measurement was of my own instrumentation, not of the product.** The rule I should have
been following is simple and I now have it in the runbook — measure the exit code of the process,
not of the pipeline:

    python -m screenplay_studio.cli ... > out 2> err; echo $?

### The defect

`cmd_watch` printed its per-file lines and `return`ed. Argparse then fell off the end of `main()`,
and the process exited 0. So:

    FAILED: broken.fdx → Parse stage failed: unclosed token: line 2, column 21
    $ echo $?
    0

A CI job, a Makefile, a cron watcher: all of them read the exit status, and all of them were told a
broken FDX had been imported successfully. A mixed batch where *nothing* succeeded was equally happy.

### The semantics, and why partial failure is 1 rather than 2

2 already means "you asked wrongly" throughout this CLI (`_load_project` uses it for a directory
that is not a project, argparse uses it for a bad flag). Reusing 2 for "one of your files was
malformed" would make a retry loop retry forever on a typo. So:

    0  every requested file succeeded — an empty inbox included,
       because `watch --once` on an empty folder is cron's normal state
    1  the batch ran and at least one file failed
    2  usage / configuration error; nothing was requested of any file

The empty-inbox case is the one worth arguing for: a tool that exits nonzero when there is nothing
to do is a tool that pages someone at 3am for doing its job.

### What the register asked for that was not a number

"Retain machine-readable per-file outcomes and recovery paths." There was no JSON at all. `--json`
now emits filename, ok, project and error per file, plus the totals, and a test asserts the JSON's
`ok` agrees with the exit code — two sources of truth for one fact is how dashboards start
disagreeing with pipelines.

### Verification

- 13 tests, all driving the **real CLI as a subprocess**. This matters: a test that asserted on a
  returned value would have kept passing while the process still exited 0, which is the filed defect
  in its entirety. The test had to read the thing the defect was about.
- Reverts: **3** (swallow the code) / **5** (always exit 0) / **2** (no JSON) / **2** (uncaught
  folder error) / **1** (no stderr line).
- Existing `test_watch.py` and `test_watch_source_safety.py`: 14 passed, unchanged.

## §60 — Gap 43: a regex was grading scenes (2026-11-06)

Filed accurately. Reproduced on the register's own framing — a scene built as a twelve-years-delayed
confession — and the measurement is stark: the finding was **byte-identical** to the one produced by
the same line with no framing whatsoever, and to a comic beat built on the bluntness. The context
never entered the code at all.

### What the old finding actually claimed

    "names the emotion outright — the subtext is missing, so the scene tells instead of shows"
    "the moment lands flat"

Three claims from one regex match: an absence, a craft verdict on the scene, and a prediction about
a reader's experience. The check had seen a lexicon word. That is the whole of its evidence. The
register's phrase for this — "an unconditional inference from wording, not an independent judgment"
— is precise, and it is the same species as gaps 44/45 (a numeric proxy stated as a diagnosis) and
54 (a recurrence read as a payoff). This cluster is one architectural mistake wearing five hats: a
deterministic pass reporting an observation in the grammar of a finding.

### What I changed, and what I deliberately did not

I kept the finding. The register was explicit — "do not categorically ban useful directness" — and
the check is genuinely useful: a writer scanning for on-the-nose dialogue wants the list. What I
removed is the verdict, and what I added is the machinery to keep observations from being read as
notes:

* the issue states what was detected ("names the emotion outright rather than showing it");
* `is_observation` and `confidence: observation` travel with the data;
* the report badges it: *"a pattern, not a verdict; whether it works depends on the scene, which is
  your call"*.

That badge is the part I nearly skipped. Without it the new prose is still a finding sitting in a
findings list, and a list is a verdict by layout. An observation has to *look* different where the
writer reads it, or moving the judgement into the prose is cosmetic.

### The context sensitivity

The register asked for a "context-sensitive question". I did not build a question generator — that
needs a model, and this pass is deliberately model-free. What I built is a staging detector: action
near the line containing *held this*, *twelve years*, *finally*, *confess*, *admits*, *the first
time* switches the explanation to "this looks deliberate — if the plainness is the point, this is an
observation, not a note". It is crude and it only ever changes the *explanation*, never the
decision. I want to be clear that this is the weakest part of the change: the honest version is a
context-sensitive question, and that needs a live model plus a writer to answer it.

### My errors

One, small, and the same one as §57 and §58: I wrote a test asserting `"I feel lost."` would be
flagged, without checking the emotion lexicon — `lost` is not in it. Third time this session that I
asserted from my model of the code rather than from the code. It is now a standing runbook trap.

### Verification

- 15 tests: the filed case; no "subtext is missing"; no "lands flat"; the observation still reports
  what was detected; directness still reported; the flag and confidence; the report badge; the badge
  absent from ordinary findings; the flag on every wording; staged vs unstaged explanations; the
  comic control; a scene with no direct emotion; an orphan line; and per-scene attribution.
- Reverts: **1 / 3 / 1 / 1 / 1**, each verified applied by marker count.
- Full suite run through the gate before commit.

## §61 — Gaps 44 + 77: a finding that quoted its own refutation (2026-11-06)

Two entries, one piece of code, so one fix and one section. I read both before touching anything,
which is the only reason I did not fix 44 and leave 77 filed.

### The defect, restated plainly

    INT. KITCHEN - DAY  ->  EXT. STREET - NIGHT

    "Unmarked time flip: Scene 1 ends in DAY and Scene 2 opens in NIGHT with no
     transition marker (LATER / THE NEXT DAY / etc.)."
    evidence_quote: "EXT. STREET - NIGHT"

Entry 77 had already spotted the thing I would otherwise have missed: the evidence quote is the
second scene's **heading**, and that heading states the new time. The finding quotes the text that
refutes it. That is not a wording bug; it is the check misunderstanding what a slug line is for. In
a screenplay the heading is *where time is stated*, and a new heading is itself the transition. The
old check demanded a marker on top of the marker, and then quoted the marker as proof it was absent.

### What I did not do: delete the check

The tempting fix is to remove `unmarked_time_flip` entirely, and it would be wrong. There is a real
question a heading cannot settle — both scenes in the SAME place at opposite times, with nothing
between them. Same kitchen, breakfast, then same kitchen, dark. That may be a deliberate ellipsis
or it may be a dropped beat, and the page does not say. So the check survives as exactly that case,
as a question, marked as an observation, quoting both headings, and telling the writer that an
ellipsis is a normal cut and there may be nothing to fix.

The `check_id` stays `unmarked_time_flip` even though the phrase is gone. It is a stable name used
by `AnalysisResult.merge` and by the dock's evidence chips; renaming it would break those for
cosmetics.

### Two of my own failures

**I wrote a dead branch and nearly called it a fix.** My first patch added `continue` and then left
the old finding code below it under `if False`-style unreachable shape, with a comment calling it
"the shape of the replacement". A branch that cannot run is a tombstone, not a fix — it invites the
next person to "re-enable" it. I reverted the whole file and wrote the check properly: the old
finding is gone, and a real one tests for same-place tension.

**I stopped one register sentence short.** The entry says "Test parallel events, intentional
ellipses, flashbacks and unclear chronology". I implemented three of the four, wrote a flashback
test, and it failed: `FLASHBACK. Twelve years ago, this same room.` still read as a dropped
transition, because `TIME_SKIP_RE` knows `LATER` and `1998` but not the writer *saying* the
chronology is deliberate. The fix was a small vocabulary addition — but only because I wrote the
test the register asked for rather than the three I had thought of.

### An existing test was pinning the defect

`tests/test_continuity_idiolect.py::test_unmarked_time_flip_flagged` required the old behaviour on a
fixture that moves place and states both times. It was not a regression; it was the filed defect,
pinned. I re-based it on a same-place fixture, kept its assertions (category, severity, low), added
the observation flag check, and added a second test asserting the old fixture is now silent — so the
gap-44 measurement lives in the file that used to contradict it, with a comment saying which is
which. I did not delete it.

### Verification

- 13 new tests: both filed cases silent; the phrase gone; no single heading quoted; same-place
  raised as a question; observation flags; marker silences even the same-place case; morning→evening;
  continuous; flashback; a concrete year; a seven-scene run of act cuts (the 5→6 / 13→14 / 17→18
  class); an unparsed time left alone.
- Reverts: **4** (flag every day/night change) / **1** (quote one heading) / **1** (state as fact) /
  **1** (drop flags) / **1** (no flashback vocabulary). The 1s are thin and I would rather they were
  higher; each is a single independent assertion on a distinct behaviour.
- Existing: `test_continuity_idiolect`, `test_bugfix_batch`, `test_cross_rule_dedup` — 73 passed.

### The regression the gate caught, and what it really was

`close_gap.py check` refused gaps 44 and 77 with an UNEXPECTED suite failure:
`test_revision.py::TestLastPass::test_same_input_headline_agrees_with_the_board`. I would not have seen
it otherwise — I had run the continuity tests and the watch tests, not the revision ones.

I then spent five wrong hypotheses on it: a composite `evidence_quote` breaking verification (plausible,
and I had in fact written exactly that bug — more below), id collisions, fixture ordering, a stale
snapshot, `kept` being sampled from the wrong list. Each was checked by measurement and each was wrong,
which is the only reason the sixth was right.

**What it actually was:** the test computed the id churn as `prev_distinct - survivors`. That formula
is only correct when every kept finding is quote-identified, because a re-worded no-quote finding gets
a brand-new id rather than a moved one. The fixture used to put two continuity findings at the front of
the list — headings, therefore quote-identified — so the wrong formula happened to give the right
number. My fix **deleted those two findings**, the front of the list became a no-quote finding, and the
coincidence collapsed: 4 vs the correct 5.

So the production code was right the whole time and the test was encoding a coincidence. I could have
"fixed" this by changing the fixture to keep two quoted findings at the front, which would have
restored the green light and left a false assertion in place. I did not: the test now computes
`len(old_ids - new_ids)`, capturing `old_ids` before the report is overwritten, and — the check that
matters — **it passes with my continuity change both applied and reverted**, so it is asserting the
true relation rather than accommodating my edit.

The lesson is the one this register keeps teaching: a test that passes is not evidence that it tests
the right thing. Two of my six hypotheses were about code I had genuinely broken (the composite quote),
and I only kept them from becoming the official explanation by measuring each one.

## §62 — Gap 45: the prose was wrong because the number was wrong (2026-11-06)

Gap 45 was filed as a language problem. The finding said a scene "meanders where the story needs
to move" and prescribed "a real event", and the entry's recommendation was about presenting
metrics as descriptive signals rather than diagnoses. I read that, agreed with it, and started
editing wording.

That would have been the wrong fix, and it would have looked like the right one. The sentence was
false because the arithmetic underneath it was false, and rewriting the sentence around false
arithmetic is not a repair — it is a false statement with better manners.

Three things were wrong with the numbers, discovered in this order:

**The claimed defect.** `else: action += words` put every character cue, slug line, transition and
parenthetical into "action words". A scene with four dialogue beats and no action line reported
`action_words=8`, and the finding quoted "only 11% action words" about a scene in which the only
non-dialogue text was the name MIRA four times and the words INT. ROOM - NIGHT. This one I did
reproduce before touching code, which is why I caught it at all.

**The rank that could not express an amount.** The filed entry mentions "relative rank". What it
does not say, and what the reproduction showed, is that min-max normalisation makes the score
incomparable to anything: three identical all-dialogue scenes each scored exactly 100.0, and a
script where every scene is equally slow scored 0.0 on all of them. A number whose maximum means
"slowest of these" and whose zero means "fastest of these" cannot be read as drag, and the report
rendered it as `({pace_score:.0f}/100)` — an amount out of a hundred.

**The contradiction inside the score.** This is the one that shames me. I only found it because a
test I wrote for a different reason failed. I asserted that three identical scenes should share a
rank, and the run said their ranks were 3, 4 and 5 — *below* two action scenes. Density is words
per **element**, and a 40-word action paragraph is one element. So the more action a scene
contains, the higher its density, the higher its drag contribution on the 0.6 term — while the
`action_share` term at 0.4 pushed the other way. Measured: a 44-word all-action scene scored 60.0
and a 106-word all-dialogue scene scored 40.0. The composite ranked the action scene as draggier
than the talking heads, i.e. backwards, and the 0.6/0.4 weights were what decided it.

I had already written the comment "invert action_share: low movement => high drag contribution"
and believed the metric was coherent. I had read that function a dozen times across this register.
Reading is not measuring. The failing test was accidental — I wrote it expecting a tie — and it is
the only reason this entry is not a cosmetic wording change on top of an inverted index.

What I changed my mind about: my first plan was to *keep* the rank and label it more loudly. That
was a compromise with a broken instrument. Absolute terms (length against a fixed reference, plus
dialogue share) both point the same way and need no normalisation, so the tie, the cross-script
comparison and the inversion all fall out as consequences rather than as special cases.

What I deliberately did not do: the register asks for "independent assessment" of the critical
judgement. There is now no critical judgement being made — the pass reports counts and says it
does not know what they mean for the writing — so there is nothing for a reader panel to assess.
Inventing a proxy for audience reception would rebuild the exact defect under a new name.

The transferable lesson, added to the one from §61: **a plausible defect description is not a
diagnosis of the code.** Both of my grossest errors this session (§61's regression, this
inversion) were found by tests I wrote for a different reason, not by reading harder. When an
entry's recommendation is about wording, measure the numbers it is talking about before editing
the wording — the wording may be the only part that is honest.

## §63 — Gap 47: "no findings" was four different sentences wearing one coat (2026-11-06)

The filed entry is accurate and it is smaller than the defect. It says the renderer prints
"No significant findings" without checking the category outcome. I reproduced exactly that in one
probe: dialogue marked failed, a provider error on the result, and the Dialogue & Action section
reading *"No significant findings."* with the string "fail" absent from the section.

What the reproduction did not show, and what I checked before writing the fix, is that
`category_outcomes` was not merely unread — it was **incompletely written**. Voice, subtext,
continuity and pacing recorded no outcome at all. So the four passes most likely to fail silently
(deterministic, no model, wrapped in bare `except Exception`) were exactly the ones with no way to
report that they had failed. Fixing only the renderer would have made the four grid sections honest
and left the deterministic ones claiming cleanliness by omission. That is the shape of a
half-fix that passes its own test.

The four states. Counting them was the useful step: ran-and-clean, failed, not-applicable, and
never-requested. The old code had one sentence for all four. The fourth is the one I nearly
missed — a category with no entry in the dict is not "ok", and treating a missing key as clean is
how a report from before this change would print ten confident clean bills of health. So the
`None` case gets its own text and says "not a clean result" explicitly.

A guard I did not write caught the JSON key. `test_every_report_section_is_classified` failed as
soon as I added `category_outcomes` to `to_findings_json`, demanding I classify it rather than let
the eval ignore it silently. I classified it as excluded, with a reason: three fixed words, no
findings content. Ten minutes earlier I had written in the 45 entry that my grossest errors were
caught by tests written for a different reason. This is the same lesson from the other direction —
the repository already had a test whose entire purpose was to stop me forgetting a step, and it
worked.

What I did not do, and am recording rather than claiming: the entry asks that markdown, JSON and
the UI agree. Markdown and JSON now agree. The web desk's category view renders from `findings`
and has no notion of a failed pass, so a writer using the desk still sees an empty category with
no caveat. That is a real remaining gap, it is a UI change with its own review needs, and calling
it done because two of three surfaces agree would be the same overclaim this register keeps
finding in the product.

## §64 — Gap 50: the safety was in the callers, so the primitive had none (2026-11-06)

Reproduced as filed, first try through the CLI: a directory with a draft at `source.fountain` and
no manifest, given `run --project <dir> <other.fountain> --only parse`, printed "Created new
project at …", replaced the draft with a different script, and exited **0**.

What I got wrong before getting it right: my first probe passed `--source`, which does not exist —
source is a positional argument. The run died on argparse with exit 2 and I nearly wrote down
"not reproduced". That is the third time this session a broken probe has looked like a clean
result, and the guard I keep needing is the same one: a probe that fails must be distinguishable
from a product that refuses. Here the tell was exit 2 with a usage string rather than a
domain error.

Where the fix belongs was the interesting question. `ProjectManifest.create` is called from five
places: the CLI, `watch`, and three web routes. Reading them, all four non-CLI callers were
already safe — three call `_claim_project_dir` for an atomically-created fresh directory, and the
sample route refuses a damaged directory (gap 35). So the API was not "missing" a check that
callers supplied; the API had a **silent-replace contract** and every caller was individually
responsible for avoiding the case it permitted. Four callers remembered. One did not. That is not
a bug in the CLI, it is a bug in the shape of the primitive, and fixing it only in the CLI would
have left the next caller to rediscover it.

Two invariants moved into `create`: a destination must be *claimed* (parents made, final
component `mkdir`'d, so "someone got here first" is reported rather than adopted), and the
install must not be able to replace (`'xb'`, not `copy2` — `copy2` clobbers, so two runs racing
still lost data even with the occupancy check in place). I only added the exclusive open after
asking what happens when two CLI runs start together, which the entry's "claim new directories
atomically" line asks for and which the occupancy check alone does not answer.

The one place I changed course mid-fix: my first version refused *every* non-empty directory,
which broke the case where the caller names the file already sitting at the destination. That is
not a defect in my test, it is the adoption recovery — and it is the only way to take ownership of
an orphan without moving files around. Pre-fix that path raised `SameFileError`, so it never
worked; I made it work, because my own error message tells writers to do it and an error that
recommends an action that fails is worse than one that recommends nothing.

Recorded as not done: `watch` builds its own suffixed directory before creating, so it is
unaffected, and I did not add a new regression test for that loop — it has its own passing suite
and I did not want to claim coverage I had not measured.

## §65 — Gap 52: the edit wrote to one of six copies of the same fact (2026-11-06)

Both filed reproductions held on the first probe, no guesswork needed: a heading edit left
`heading_raw` stale (export and UI showing the old slug) and a cue rename left the dialogue
carrying the old `character`. The interesting part was not reproducing it but deciding where the
fact lives.

An element's text is not stored once. `scene.heading_raw`, `int_ext`, `location` and
`time_of_day` all restate the heading; a dialogue element's `character` restates the cue above
it; `characters_present` and `doc.all_characters` restate both. The edit path wrote `el.text` and
stopped. Every one of those six is a derived copy, and I had a choice between patching the copies
the failing tests named or rebuilding all of them from the elements after any applied edit. I
rebuilt: a heading edit can change int/ext, location *and* time at once, and a rename can move a
speaker between scenes' lists, so patching is how you get a document that is coherent in the cases
you thought of. The elements are now the only source of truth for the fields that can be re-derived
from them.

Two narrower decisions I want on the record. The rename is carried only across the dialogue run
immediately after the cue, stopping at the next cue or heading — a character's name in action text
is prose, and rewriting it would be the editor deciding what the writer meant, which is the exact
failure mode this gap is about. And I used the parser's own `normalize_character_name` rather than
my own string handling, because my first attempt stripped `(V.O.)` into `character` and thereby
invented a second, worse inconsistency: the cue read `PRIYA (V.O.)` but the speaker was recorded as
the whole line.

Then the part the entry only gestures at — "either support structural changes end-to-end or refuse
them clearly before acknowledging". I probed what an edit can do to a document that must survive
serialization, and it was worse than filed: a heading edited to prose came back as a script with
**zero scenes**, and a lowercase cue came back with its dialogue block demoted to two action lines.
Both returned applied. The working copy is re-parsed on resume, export and reanalysis, so an edit
the parser will not read the same way is not a partial success — it is silent restructuring that
the writer only discovers later, in a different room. Refusing was the entry's own second option
and the honest one: there is no way to "support" a scene heading that is not a scene heading.

The guard keys on the element's *type*, not the text, which I only thought to check because a
naive version would have refused to edit any action line containing the word `INT.`. A guard that
stops legitimate work is a different bug wearing the same uniform.

Recorded as not done: editing still addresses elements by text, so two identical lines in one
scene are refused as ambiguous rather than disambiguated, and undo of a rename is tested at the
text level only. The entry asks for stable element IDs; that is gap 51's territory (undo that
fails while claiming success) and I did not widen this fix into it.

## §66 — Gap 51: undo was honest about failing and dishonest about everything else (2026-11-06)

The filed reproduction held exactly. Undo returned `restored: []` with one `failed` entry, the
prose was unchanged, and the record moved from the undo log to the redo stack anyway. The route
answered 200, and the client printed "Undid the last applied edit." without looking at the body.

The part I nearly missed by treating the entry as complete: **the failure was manufactured by the
apply.** The entry describes undo refusing a line it cannot identify. It does not say why the line
became unidentifiable. Replacing MARA's `First line.` with `Second line.` — which TOM already says
— leaves two dialogue lines with identical text under two different speakers, and the reversal,
matching on text alone, cannot tell which one the edit produced. So the honest fix is not only "do
not consume the record on failure". A line that has a speaker has an identity, and both directions
should carry it. That turned the filed case from *refused* into *undoable*, which is the difference
between a correct refusal and a working feature.

I also introduced a regression and the suite caught it within one run. My first `_speaker_of_line`
returned the **first** match, so a line two characters share was read as confidently belonging to
the first of them — and an ambiguous edit sailed through without a hint. A test I had written
expecting the *refusal* failed instead of passing, which is the only reason I looked. The function
now returns None unless exactly one speaker says the text, and identity only ever narrows a
candidate set; it never decides on its own that a repeated line is unambiguous.

Two other things worth recording. The existing `test_undo_redo.py` fixture seeded the edit **only
into the log** and never into the working copy, so the recorded text was nowhere in the document
and the undo had nothing to reverse. It passed for years because the old code returned the record
as "undone" no matter what — the fixture was testing the defect. Once a failed reversal stopped
consuming the record, the fixture failed, and I fixed the fixture rather than loosening the fix.
And on group semantics the entry says "make them explicit and transactional": I chose
all-or-nothing refusal over partial application, because the group is the unit the writer asked
for, and a half-reversed document matches neither the before state nor the after one.

Deliberately not done: durable element IDs surviving a re-parse. Speaker-qualified text is enough
for the edit cycle that produced the record, and a reversal after a fresh upload is refused with a
reason instead of attempted. The entry asks for stable IDs; that is a schema change to the working
document and I did not fold it into a bug fix at the end of a long session.

## §67 — Gap 54: the docstring was the bug report (2026-11-06)

This one was unusually clean to diagnose, because the module documented its own defect as a design
decision: *"Asymmetric: recurrence proves payoff (flip + note), absence proves nothing (keep +
mark)."* The asymmetry sounds like prudence. It is only half prudent. Absence genuinely proves
nothing — a scene can pay a setup off in words the setup never used, so a missing match must not
downgrade anything. But recurrence proves nothing either. It proves the setup's vocabulary
reappears, which is a location, not a resolution, and the gap between those two is the whole
finding.

Measured on the register's own fixture: a key promised to open a vault, then a scene where the key
hangs on a hook and the vault stays locked. The status flipped, the scene became `payoff_scenes`,
`verified` went true, and the dangling finding vanished. The vault is still locked.

What I want recorded beyond the fix: **a test in this repository was pinning the defect, and it was
written by someone who read the docstring and believed it.** `test_false_dangling_flips_to_paid_with_proof`
uses a scene reading *"The CIGAR sits on the table, untouched"* and asserts that this is a payoff,
verified. The word "untouched" is in the fixture. Whoever wrote it was encoding the documented rule
rather than asking whether the rule was true — which is exactly the failure mode this whole register
is about, arriving from the inside. I rewrote the test to assert the candidate, and I am naming it
here rather than quietly changing an assertion, because a green suite that encodes a false rule is
worse than a red one.

I also did less than the entry asks. It wants an independent assessment across complete scripts,
distinguishing a deliberately unresolved thread from an abandoned one *by content*. The pass cannot
make that judgement. So it now reports both readings — the model's verdict, the candidate scene, and
the possibility that the strand is open on purpose — and stops there. Inventing a heuristic that
scores "did the story mean to leave this open" would rebuild the same defect with more moving parts.

Two process notes, because the user called both out. First: I was spending twenty tool calls per gap
on exploratory probes and incremental edits, so turns kept ending mid-gap with a red suite. The last
few gaps were done in six calls each — read once, patch code and tests and registers together, run
the suite, run the gate, commit. Same verification standard, a third of the budget; the measured
reverts are what make that compression safe. Second, and worse: a sandbox reset threw away this
gap's tracked edits because I had not committed yet, and I redid the whole patch. Work that is not
committed does not exist. Commit as soon as the suite is green, not after the registers are polished.

## §68 — Gap 56: "off" and "unset" were the same value (2026-11-06)

The reproduction is the kind that reads as a joke in a bug report: with
`SCREENPLAY_STUDIO_DEMO_MODEL=0` set, the server printed *"set
SCREENPLAY_STUDIO_DEMO_MODEL=0 to disable this fallback"* and then, on the very
next line, *"DEMO MODEL active (in-process)"*. A program contradicting itself in
two adjacent lines is usually a good sign that two different pieces of code
decided the same question.

That is exactly what it was. `_env_flag` returns a bool, so `"0"` and `""` both
come back `False` — the function is correct for "is this switch on", and simply
cannot answer "did the writer say anything at all". The fallback needed the
second question and asked the first. `_demo_setting()` now returns on / off /
unset, and the test that pins the point asserts the two functions disagree about
the same input: `_env_flag(...) is False` for both `"0"` and unset, while
`_demo_setting()` returns `"off"` and `"unset"`. That assertion is the whole gap
in three lines, and it will fail if anyone "simplifies" the helper back.

The second half of the report took longer to see than it should have. `main()`
called `_undo_demo_fallback()`, which sets `_DEMO_FALLBACK_AUTO = False`, and
`_recheck_fallback_after_args()` returns immediately unless that flag is set —
so main() disabled the mechanism it was about to rely on and then "confirmed"
the demo was fine. Reading it as two independent bugs would have produced two
patches; it is one decision being made in two places with different rules. Both
now call `_recheck_fallback_after_args`, which consults `_demo_setting()`
directly, and I removed the copy-pasted `under_pytest` two-liner from both sites
because duplicated policy checks are how the two paths drifted in the first
place. A count-based source assertion keeps the env var to a single reader.

What I did not do, stated plainly because the entry asks for it: it wants a
clear "unavailable" state in the UI and the actual provider/model labelled per
run. The operator is told on stdout and `/api/config` already carries
`demo_model`, but the desk has no distinct no-model banner, and I did not invent
one inside a startup fix. That is recorded in the register tail rather than
claimed as done.

## §69 — Gap 59: the fix for this gap had itself a hole (2026-11-06)

Gap 88 had already been here. It moved the disclosure from "is demo mode on right
now" to "what did the run record", which is the right idea — and then wrote:

    `model_used=None` means the caller could not establish the run's model; the
    banner then falls back to the old global check

That sentence is this gap, wearing a comment. When the record is missing, the
old global check is exactly the dishonest behaviour, and it is dishonest in
both directions: unknown-while-demo-on labels a real report canned, and
unknown-while-demo-off silently drops the disclosure from a canned one. A
partial fix with a documented exception at the boundary is worth less than it
looks, because the exception is where the interesting cases live — legacy
archives, reports written before the field existed, anything where the record
did not survive.

So the third state is now a first-class answer, not a fallback. `stand_in` is
`True`, `False`, or `None`, and `None` renders its own banner that says what is
actually true: the origin is not recorded and cannot be checked. I resisted
writing "this may be a demo report" because that is a hedge that still tells the
reader nothing; naming the missing record is more useful than either guess.

The client half needed a structural change rather than a predicate change. There
was ONE attribute (`data-demo-banner`) doing two jobs: describing the report and
describing the connection. Any single predicate would have been wrong for one of
them, which is why the old code looked reasonable and behaved badly. Splitting
them — `[data-report-origin]` from `state.report.provenance`, `[data-demo-banner]`
from the live config — is the actual fix, and the test asserts the report-origin
function does not read `state.config` at all, because the day it does the bug is
back.

Recorded as not done: the entry asks for immutable provenance per run, including
mixed-pass retries. `model_used` is still one string per report, so a retry that
ran on a different model overwrites the earlier record instead of recording
both. That needs a schema change to the report artifact (a runs list) and I did
not fold it into a disclosure fix.

## §70 — Gap 70: the one store that never joined the contract (2026-11-06)

Reproduced on the first attempt, all three claims. The shelf flagged the damaged
idea (correct and unchanged), while opening or saving it answered 400 with
*"Expecting ',' delimiter: line 1 column 46 (char 45)"*. That is a JSON parser's
vocabulary shown to a writer as though they had typed something wrong, for a
file they never touched — and the file sat there, intact and unreachable.

The cause is a one-line gap in an otherwise consistent design. Every
writer-owned store in this package calls `load_json_store`, which distinguishes
MISSING from PRESENT-BUT-UNREADABLE and raises `StoreUnreadable`; the app has a
dedicated 503 handler for exactly that, with a comment explaining why damage must
never read as absence. `IdeaStore._read_meta_raw` was a bare `json.load`.
`JSONDecodeError` subclasses `ValueError`, so it fell into the generic
"malformed request" path. Nobody wrote anything wrong; one store simply never
got migrated, and no test noticed because no test corrupted an idea file.

Two deliberate choices in the fix. First, `recover` returns the file **verbatim**
rather than a best-effort partial parse. I considered a "salvage what we can"
parse and rejected it: the value of a recovery path is that it returns the
writer's actual bytes, and a partial parse of a torn file is a second guess
layered on a first failure. Second, `repair` refuses a readable file. It would
have been easy to make it a general "write this text as the idea" endpoint, and
that would have been a silent bypass of every merge rule in the module — the
same class of bug as the ones this register keeps finding, wrapped in a new
route.

One thing I did less well: my first patch used
`__import__("screenplay_studio.jsonio", fromlist=["x"]).retry_permission` when
`retry_permission` was already imported at the top of the file. Nothing broke,
but a fix that hides an already-imported name behind `__import__` is the kind of
line that makes the next reader distrust the whole function. Cleaned up before
committing.

Recorded as not done: neither new route has a UI affordance. The entry's
reproduction is about the server answering honestly, and it now does, but a
writer with a damaged idea still has to know that `/recover` exists. That is a
desk change, and I did not fold a UI feature into a store-contract fix.

## §71 — Gap 72: a backup that does not say what it left out (2026-11-06)

Reproduced with one faulted file: 200, the file missing from the zip, no manifest
inside, no header. The filed line was literally `except OSError: continue`, and
the per-project route did not even keep a count of what it wrote, so it had no
way to be honest even in principle.

Worth saying why this class matters more than its severity suggests. The file is
still on disk — nothing was lost. But a backup is not a file, it is a *promise
about completeness*, and the whole reason someone downloads one is to stop
worrying. A 200 with a hole in it converts a recoverable situation into a
believed-safe one, and the failure surfaces months later when it is the only copy
left.

Two decisions I want on the record. First, the omission is recorded **inside the
archive**, not only in a response header. A header is discarded with the browser
session; the zip is what survives, gets copied to a drive and opened a year
later. A manifest that travels with the artifact is the durable form of the
statement, and the header is a convenience on top. Second, `files: n` in the
library manifest now counts files that actually landed rather than attempts. The
old count was not wrong when nothing failed, which is exactly how it stayed
wrong unnoticed.

I also had a fixture bug before I had a finding: my first probe hand-wrote a
`project.json` and got `500 KeyError: 'project_dir'`. The product was fine; my
fixture was not a real manifest. Building the project through
`ProjectManifest.create` — the way the app does — turned it into a real
reproduction. This is the fourth time this session a broken probe has mimicked a
product failure, and the tell is the same every time: an error from a layer the
defect is not about.

Recorded as not done: the entry ends with "verify a restore before calling an
archive good", and I did not implement a restore. There is no restore route for
either archive — that is gap 71's territory, along with labelling ideas and
writer memory as their own sections and deciding whether relationship memory
belongs in a backup at all, which is a privacy decision rather than a default.
Adding a restore here would have meant designing that whole surface inside a
completeness fix.

## §72 — Gap 73: the desk knew which file it was reading and never said (2026-11-06)

The smallest gap I have closed this session, and the one with the least
excitement in it. A project folder held `source.pdf` beside a live
`source.fountain`; the export went out correct and silent. Nothing was corrupt.
That quiet is the finding: the only way for a writer to learn that two scripts
shared a folder was to open the folder.

What the measurement changed. The filing describes an *export* problem, and the
export was indeed silent — but `/api/projects/<name>` carried **no source
filename at all**, so the desk did not know the answer either. A gap named after
one symptom is often larger upstream, and here the honest fix began one layer
below the export.

Where I had to choose, and chose the harder answer twice.

First, the unrecorded case. A manifest without `source_filename` is common
enough — hand-assembled, pre-dating the field, or damaged — and the tempting fix
is to infer: there is exactly one `source.*` file in the folder, so call it that.
I refused. The whole subject of this gap is provenance, and a confident guess
about provenance reproduces the defect it is fixing, only with better manners.
It says `not-recorded`. A stated hole is usable; a wrong name is not.

Second, the stray itself. It is material the writer may still want, possibly the
only copy of something, so it is disclosed and never moved. That restraint makes
the warning weaker on purpose: the desk cannot clean up for the writer without
deciding, on their behalf, which of two scripts was the one that mattered.

**The scope was narrowed by measurement, and I want that on the record** because
it looks like a shortcut. My first rule was "any file with a screenplay
extension". I ran it and it flagged `report.md` and `draft_notes.md` — this
desk's own output, sitting in every project directory. A warning that fires on
every project, every time, is not a warning; it is wallpaper, and it is how a
genuine `source.pdf` gets skipped six months later. So the rule is the desk's own
convention, `source.<ext>`, which is definite rather than a guess. The
recommendation asked for stray source-format files to be named; it did not ask
for them to be guessed at by extension, and the two are not the same thing.
Trade-off accepted and named: a stray named `old_draft.fountain` is not reported
by this rule, because the desk cannot tell it from `draft_notes.md` without
guessing.

I also caught myself writing a test that could not fail. My first revert matrix
came back **15 / 15, zero failures** with the client banner unwired — because the
assertion had searched the whole file for `renderSourceProvenance(project)`, and
the function's own *definition* contains that string. An unwired helper passed.
The fix was to count call sites and assert the call specifically inside
`openProject`; the revert then failed properly. A revert that does not fail is
not evidence of coverage, it is evidence that the test is decorative — and the
sixth revert is there precisely to catch that class of mistake.

Recorded as not done: the register's ask that the active file be explicit **in
the project's own metadata** is only half met. `create` records it; a manifest
from before the field existed does not, and this reports the hole rather than
backfilling it. And the filed *export* half is met on the wire, not in the
artifact: the `.fountain`/`.fdx` this route hands over still contains no
provenance block. That is gap 79's territory, and gap 79 stays open rather than
being quietly counted closed by this.

## §73 — Gap 79: the artifact had no memory (2026-11-06)

The export was correct and mute. Every writer-facing surface had been taught to
explain itself — the report says which model made it, the backup says what it
left out, the project bar says which file it is reading (gap 73, an hour ago) —
and the one thing that actually leaves the machine said nothing at all. A PDF
parse with `parse_confidence: low` produced a Fountain file indistinguishable
from the writer's own.

The design choice that mattered was *where the note goes*. Three formats, three
different answers, and only two of them get to have one:

- **Fountain** — the boneyard. It is the format's own mechanism for "this is not
  screenplay", and `_strip_boneyard` already runs on re-import, so the note is
  visible to the writer opening the file and invisible to the parser reading it
  back. Nothing new had to be invented; I only had to look for it.
- **FDX** — an XML comment. A real `<Provenance>` element would be at the mercy
  of Final Draft's schema, and a title-page paragraph would *print the note on
  the writer's page*. Both are the obvious implementations and both are wrong for
  the same reason: they make the label part of the work.
- **`.txt`** — nothing, and I had to be corrected on why.

That last one is the part worth writing down. I refused the `.txt` block with a
confident mechanism: an embedded note would re-import as dialogue and corrupt the
script. Then I wrote a test to demonstrate it and **the test failed** — scene
count 6 → 6, marker never in scene text. The real behaviour is duller: the note
lines land in `front_matter` as ACTION, so they print as four bogus action
paragraphs at the top of the screenplay. Same decision, different and smaller
reason. Had I skipped the demonstration — which is the tempting move when a
conclusion feels obvious — I would have shipped a comment, a docstring and a test
name all asserting something false about my own code. The lesson is not "measure
more"; it is that a *justification* is a factual claim and decays exactly like
code does.

Two of my three initial test failures were fixtures lying about the product, and
the pattern is now familiar enough to name: I named a PDF copy `kept.fountain`,
so the project was a Fountain project and `reconstructed` came back `False`; and
I wrote `parsed.json` without marking the parse stage, so `/backup` reported
`pending` for a project that had parsed fine. `/backup` reads the manifest's
stage, not the file. Both errors pointed at the product and both were mine.

Recorded as not done: the filed line covers **export and revision**, and I only
fixed export. The edits flow still hands over a working copy with no note, and
the provenance block describes the parse rather than each edit generation — an
export after ten accepted edits says nothing about them. That is a real gap
inside the closed one, and it stays written down rather than counted closed.

I also owe a note on the session itself: this gap was closed on a sandbox whose
local git history had silently reverted to the pre-72 base while the working tree
still matched origin's content. Commits I believed were local were only on
origin; a fresh local commit sat on a branch missing two gaps' worth of history.
Nothing was lost — the tree matched — but `git log` and `git status` disagreed,
and a `git add -A` in that state would have staged 166 files of noise. The check
that caught it was cheap: `git ls-remote` against `git rev-parse HEAD`. Worth
doing at the start of any turn that follows a reset.

## §74 — Gap 80: the escape hatch was locked by the thing it exists to escape (2026-11-06)

The filing reads like a UI complaint — card says "unreadable", refuses to open —
and it was filed as *minor*. The measurement made it worse than filed: **six**
routes answered 503, and one of them was `/backup`.

That is the whole finding, and it is worth stating plainly because it is a class,
not an instance. Every route loads the manifest first, for good reasons. `/backup`
also loads it first, for no reason at all — backup does not need a manifest, it
needs a directory. So the single action whose entire purpose is "get this folder
somewhere else before anything else goes wrong" was the one action unavailable
exactly when it was needed. Guards that sit in front of the recovery path are
guards that convert a small damage into a large one.

I had the same bug inside my own patch and caught it before it shipped: I had
registered the recovery function at `/backup` as well, which would have shadowed
the real backup route and silently replaced the gap-72/73 archive — with its
manifest, its completeness header and its export provenance — with a plain folder
copy, for every healthy project. The gate would not have caught that; the
gap-72 tests would have. I kept a test that a healthy `/backup` still returns a
real `backup-manifest.json`, and it exists because of that near-miss rather than
because of the gap.

Two refusals I want on the record, both of which are the tempting shortcut:

- **Repair will not overwrite a readable manifest.** The route exists for damage;
  if the file loads, there is nothing to fix and the "fix" would destroy the only
  accurate record. Same logic as gap 70's repair on the idea side.
- **Repair will not invent a source.** No screenplay in the folder means no
  honest manifest, so it answers 400 and changes nothing rather than rebuilding
  an empty project that looks like data loss to everyone who opens it later.

And the rebuild does **not** claim the project was parsed. `parsed.json` is often
still sitting there, which makes "parse: complete" the obvious and wrong choice —
the desk would then show pages it never actually read under a manifest it just
invented. It starts `pending` and says "re-run the parse".

Recorded as not done, because it is the part a reader would assume: `/script`,
`/drafts`, `/export` and `/report` **still 503** on a damaged manifest. I left
them. They all need real manifest fields — stage outputs, the draft list, the
model — that a corrupt file cannot supply, and fabricating those would be a worse
lie than the refusal. The writer's way out is the recovery routes and a rebuild,
not a half-working desk. Also stated, not fixed: `/recover` serves the raw
manifest to anyone who can reach the port, which is the same trust boundary as
every other route here but is worth knowing given it returns raw bytes.

One process note. This gap, like the last three, began with a sandbox whose local
git history had reverted to the pre-72 base while the worktree still matched
origin. I now check `git rev-parse HEAD` against `git ls-remote` before touching
code; it cost one call and saved a `git add -A` over 166 files of noise.

## §75 — Gap 82: "low severity" was the wrong reading, and the reason matters (2026-11-06)

I filed this one myself as *low severity — a prerequisite for gap 80's fix rather
than a separate product risk*. That was wrong, and the way it was wrong is the
useful part.

By the time I picked it up, gap 80 had **already shipped** a recovery panel for
damaged projects. The panel could not answer for an idea, and not because nobody
had thought about ideas: because the two shelves had no shared fields to read.
The consequence was concrete — gap 70 had built `/ideas/<id>/recover` and
`/ideas/<id>/repair` for exactly this situation, and **nothing in the client ever
called them**. A writer whose idea file was damaged still got a card that refused
every click, with a working repair path sitting one HTTP call away.

So the finding was not "two payloads would need a shared surface someday". It was
"the shared surface exists, it covers half the product, and the missing fields are
why." Severity estimates about *consistency* decay badly: the same inconsistency
that looks cosmetic today is a shipped dead end tomorrow.

Two decisions worth naming.

**Union, not replacement.** The envelope does not strip `stages` and `sessions`
from the project card — the desk renders those. It says: these seven keys mean the
same thing everywhere, and anything else is a field of the shelf, not of the
damage. That distinction is the whole contract, and it is why the tests assert the
seven keys plus the survival of the shelf fields rather than an exact dict.

**`recoverable` is a claim, not a mood.** The tempting implementation is `True`
whenever a row is marked damaged. Instead both shelves are tested to answer 200 on
their `recover` route when they say `True`. A boolean nobody is forced to honour
becomes decoration within two refactors. Same discipline for `last_known`: a
missing file reports `size: null`, not `0` — `0` is a fact and missing is not, and
a damage row is precisely the place where that difference gets abused.

I also found the same defect one layer down, which the filing did not mention: the
two `recover` routes described one situation with different keys. I fixed that in
the same pass rather than opening a third gap for symmetry, and kept
`X-Project-Readable` alongside the new `X-Record-Readable` so gap 80's test keeps
passing — a rename that breaks your own previous test is a rename that changed two
things at once.

Recorded as not done: nothing **structurally** forces a future shelf through the
envelope. There is no type, no base class, no builder the routes are required to
call — the contract is pinned by tests over the two rows that exist. That is
honest for today and will not survive a third store; the fix then is to make the
envelope the only way a shelf can express damage, not to add more tests.

A process note, because it cost a call: my sixth revert script referenced a backup
file I had never written, so the restore silently did nothing and the suite came
back red for a reason that had nothing to do with the code. I caught it from the
`cp: cannot stat` line and restored with `git checkout --`, not from a stale `/tmp`
copy. Backups that are assumed rather than verified are how a green matrix becomes
a fiction.

## §76 — Gap 83: a doc is a claim, and nothing was checking it (2026-11-06)

The filing reads like housekeeping — the docs and the CLI disagree — and the
recommendation offers a fork: delete the server, or guard and document it. The
fork is the interesting part, because both branches are reasonable and one of them
would have been wrong.

I kept the server, and the reason is mechanical rather than sentimental:
`test_cowriter_server.py`, `test_session_selection_merge.py` and the route-coverage
census all drive it. Deleting it would have deleted working, tested code in order
to make a sentence true. When a document and the code disagree, the document is the
cheap thing to fix — the only case for deleting code is that the code is wrong,
and "a doc denied it" is evidence about the doc.

The half that was not housekeeping: this server had **none** of the desk's guards.
It binds loopback, and the filing is honest that no exposure was demonstrated — but
"it only listens on loopback" is a claim about the socket, not about who can drive
it. DNS rebinding is exactly the technique that turns a loopback-bound service into
a reachable one, and it arrives as a `Host` header that is not local. So it now
refuses a foreign `Host` on every method, tested against `evil.com@127.0.0.1` and
`127.0.0.1.evil.com` as carefully as against `localhost.` and `127.0.0.5`. A guard
that only rejects what I thought of is not a guard.

I did **not** copy the capability token, and I want that on the record as a stated
limit rather than an omission. That token exists to stop a foreign page from driving
the browser UI; this server's only supported callers are direct, scripted clients,
and bolting a cookie handshake onto it would break every one of them to defend a
surface nobody browses. Half-implementing a security control is worse than
documenting its absence.

Two of my own errors are worth naming because they are the same error twice. I wrote
the route list from memory and got the set wrong — the test caught it. Then I fixed
the test's parser to understand one table format, and it still failed, because the
doc uses two. Both times the failure was *my description* of the code, not the code.
The final shape is the point of the whole gap: the test reads `--help` output and
the live URL maps and compares them to the prose, so the document cannot drift away
from the artifact again without something going red.

That is the class-level lesson. This register has spent many entries fixing code
that lied about itself; gap 83 is the first one about *documentation* lying about
the code, and it was filed as low severity precisely because prose doesn't crash.
Nothing was connecting the two, which is why it survived long enough to be noticed
by a reader rather than by a test. Now something connects them.

## §77 — Gap 84: a total is a checksum over a number, not over the content (2026-11-06)

The filing contains one sentence that is worth more than the four missing rows,
and I built the fix around it: *the document's own totals paragraph claims a count
pinned by a test; the count test can pass while individual rows drift.*

That is exactly right, and it generalises. `**Totals:** 103 endpoints … = 105` is
an assertion about a scalar. Add two routes and delete two and the scalar is
unchanged while the document describes the wrong software. Every count-shaped
guard in this repo has that property — the entry-table "FIXED" flag, the route
census, the schema-version numbers — and the fix is always the same: compare the
**set**, not its size.

So the guard now runs in both directions, and the second direction is the one that
was never possible before. `undocumented` catches the code outrunning the doc.
`dead` catches the doc describing a route that no longer exists — which a total can
never see, because removing a route and forgetting its row leaves the count wrong
in a way that a *later* addition silently re-balances.

Three decisions I want on the record.

**The prose is not generated.** I could have had `route_map.py` emit the whole
table and been done. But the useful part of those rows is not the path — it is
"grounded in knowledge-base rule <id>, so the desk can answer *says who?*" and
"no model call, report untouched". A generator would replace every one of those
with a path list to satisfy a checker, which is documentation being optimised for
its test instead of its reader. So: human prose, mechanical census, both checked,
in one file and separate.

**The checker is tested, including its ability to fail.** Strip a row and it must
report `undocumented`; add a ghost row and it must report `dead`; hand-edit the
generated block and regeneration must stop being a no-op. I learned this the hard
way in gap 73, where a revert came back 15/15 because the assertion matched its own
function definition. A checker nobody has watched fail is a checker that might be
returning an empty list for the wrong reason.

**CI, not just the suite.** `python tools/route_map.py` runs as its own lint-job
step. A stale doc can fail the suite too — but a failure named
`test_no_live_route_is_undocumented` buried among 2900 tests reads as a code
regression, and the diagnosis is "the doc is stale", which is a different job with
a different fix. Put the check where its failure is legible.

Two of my own bugs in the tool, both the same shape as the gap itself: it counted
the co-writer server's `/sessions` rows (which gap 83 had just put in the same
file) as dead **webapp** routes, and it compared `(method, path)` pairs, which
flagged routes that were documented perfectly well under their primary verb. Both
were assumptions about a document I had not read closely enough — a checker that
does not know which server it is checking is a checker that will be switched off.

Recorded as not done: the comparison is **path**-level. A route registered as POST
but documented under GET passes. Making the pair the unit means regenerating every
prose row, which is a bigger change than this gap asked for, and it is written down
rather than half-done. Endpoint *names* are likewise unverified, so a stale
`get_rule` → `load_rule` in prose would not be caught.

## §78 — Gap 85: the number was in the prose instead of in the code (2026-11-06)

Filed as "small", and it is. The reason to fix it is also in the filing, and it is
not small: *a support document is where a stuck writer looks first.* A wrong port
in a support doc is not a typo — it is a writer who concludes the app is broken and
files a bug about software that works.

The fix that actually holds is not the table. It is that **the number stopped
living in the prose**. The argparse parser existed only inside `main()`, so nothing
outside a launch could state the port; every document that wanted to had to retype
it, and they drifted. It is now `build_argument_parser()` with `DEFAULT_PORT` and
`DEFAULT_BIND` at module level, `app.run()` takes the constant, and the CLI's
`--help` epilog is *built from* those constants rather than written beside them.
The tests then read the values out of the code and require the prose to contain
them, so the doc cannot restate a stale figure and still pass.

Three things in this gap are worth remembering beyond it.

**A weak pin passes for a strong one until you try to break it.** My first version
asserted `str(DEFAULT_PORT) in text`. The revert that replaced *one of three*
mentions of 8500 in `AGENTS.md` still passed, because the other two carried the
number. So "the doc mentions the right port" is not "the doc agrees with the code"
— the tightened version rejects any four-digit port-like token the code does not
have. That only surfaced because I ran the revert twice: the first run looked like
a clean failure of a *different* revert attempt of mine, and I nearly recorded it.

**Two of my six revert patches silently did not apply.** My `str.replace` targets
did not match the file (the epilog is `epilog=(f"…`, and I had written `epilog=(`),
so two reverts "passed" by doing nothing at all. This is the second time in three
gaps that a revert reported a false negative because the *patch* failed rather than
the *test*. The discipline is now: a revert that does not change the file count is
not a result, and `grep -c` after each patch is cheaper than a re-run.

**The wrap is not the sentence.** One test failed because argparse wraps at 80
columns and split "capability token" across a line. Weakening the assertion would
have been wrong — the sentence is the contract and the wrap is cosmetic — so the
test normalises whitespace instead. That distinction (what a test asserts vs what a
renderer happens to do to it) is the same one that kept me from over-fitting the
room detection earlier.

Recorded as not done: `docs/ARCHITECTURE.md` still spells out 8500 in a file tree,
a section heading and an ASCII diagram. Those are structural annotations rather
than the launch promise, and an ASCII diagram cannot derive its own labels. The
co-writer's 8300 is accepted by the checker as a known port rather than derived
from `screenplay_cowriter`'s argparse — deriving it is a two-line change but it
adds a cross-package import to a test for one number, and I chose the smaller
honest thing over the tidier one.

## §79 — Gap 86: the guard was green because it was checking the wrong thing (2026-11-06)

The filing says these files "ship inside importable packages". They do not. The
wheel never contained them, and the packaging guard that asserts their absence
passed the whole time. My own earlier note in the ledger had already caught this —
*"half of gap 86 is contradicted by the artefact"* — and yet the entry survived as
written, which is worth noticing on its own: a correction recorded in a side
document does not fix the register entry it contradicts.

What was actually wrong is smaller and more interesting. The files sat in the
**source tree**, inside importable packages, where a `.json` reads as data. That is
the risk the filing names in its last sentence — *"the kind of file that later gets
loaded because it's there"* — and it is not a packaging risk at all. It was a
plausibility risk: the directory says "this is part of the parser", and the file
says "I am JSON", and nobody reads either closely enough to notice that no code
opens them.

So the interesting repair was not deleting them. It was that **the guard was
green because it was checking the wrong thing**. `test_wheel_excludes_orphaned_graph_scratch`
verified the wheel; the problem lived in the tree; the test could not have failed
no matter how long the files stayed. I kept the test and gave it the other half,
because retiring a green test while fixing the thing it failed to watch is how a
repo ends up with one fewer guard and the same blind spot. A guard is only as good
as the address it watches.

Three details I chose deliberately. **Deleted, not relocated**: git history keeps
the bytes, nothing reads them, and an `artifacts/` folder for two unwanted files is
a directory to maintain forever in exchange for a tidier diff. **The pattern, not
just the deletion**: `.gitignore` now names both, because the generator that made
them can run again, and a file that reappears silently is the exact failure mode
being fixed. **A class, not a table**: `SCRATCH_BASENAMES` means a third graphify
artifact of the same shape trips the guard without anyone remembering to add a row
— the lesson of this whole gap, since the original defect was a row-shaped
exemption list that could not grow.

And the honest limit: I did not rebuild the wheel after deleting the files to watch
them stay absent. The guard plus the absence of any `package-data` glob covering
them already establish it, and a build costs two minutes — but "established by
argument" is not "observed", so it is written down as not done rather than implied.

Process note, since it bit me twice in this gap: two of my revert patches applied
partially and still reported a plausible number (one removed a single line where I
meant two, leaving the suite green and the revert looking like a false negative;
another removed the tree check while no scratch file existed to find). Both were
caught by re-running the revert after verifying the patch actually changed the
file — `git check-ignore` on a planted file is now part of how I test an ignore
rule, because a green suite is not the same as a demonstrated behaviour.

## §80 — Gap 93: every number was true and the sentence was a lie (2026-11-06)

This is the most interesting gap I have closed this session, and the reason is that
**nothing in it was a bug**. Three verified of three quoted is correct. Thirteen
findings citing scene numbers only is correct — expected, even, for the
summary-reasoning categories. `verification_rate` already refused to divide by zero
and said so in its docstring. The desk helper already carried its denominator.

And a writer reading that report walks away believing the analysis was 100% sound.

The defect was in the *arrangement*: a rate in bold, followed by a parenthetical,
with the excluded mass mentioned only in a clause that was easy to skim past. On a
report where 3 of 16 findings carry evidence, the sentence that survives the skim
is "100%". So the fix is editorial, and the editorial rules are the finding:

**Coverage before the rate.** A reader who stops after one line must have the
covering number. This is why the coverage sentence comes first even though the rate
is the more impressive figure — impressive-first is exactly the ordering that
produced the misreading.

**The excluded mass lives in the same sentence as the rate.** Not the next
paragraph, not a footnote. `"...3 of 3 findings that cite quotable text; the other
13 findings cite no quotable text and are excluded from it."` A denominator is not
context; it is a number, and a number next to a percentage gets read as the whole.

**Zero is the loudest value, not the quietest.** The renderer now says, in the
report, that *no finding carries a checkable observation* and why that matters —
every note is an assertion with no falsifying condition. My first instinct was that
this warning would fire constantly and become wallpaper (the gap-73 lesson), and
that instinct was worth overriding here: on the demo material it is true, and it
being true constantly is the finding, not a reason to be quiet.

**Silence must be explained.** The old code correctly refused to print a rate when
nothing was checkable, and then said nothing — which reads as "nothing to report",
i.e. clean. It now says there is nothing for a mechanical check to judge and that
this is not a clean bill of health.

One asymmetry I did not expect: the two surfaces had drifted in **opposite
directions**. The report had no denominator (it printed "3 of 3"); the desk had the
denominator and no falsifiability count. So "make the report match the desk" would
have fixed the wrong half. Both now carry both.

And a rule carried over from gap 59: the desk checks `typeof observation_bearing` and
prints nothing when it is absent, so a report analysed before today gets honest
silence instead of a backfilled `0`. An invented zero would accuse an old run of a
defect nobody ever measured — the same class of error as assuming an unrecorded
model origin was the demo.

Recorded as not done: the filing's timing and quality observations (0.3 s analyze,
`[demo]` markers on 11 of 12) are **not** touched, and should not be — they describe
what the stand-in model is, and no claim about a real model follows from them. Gap
87, the adjacent desk-text-vs-markdown half, was left open; this gap made the
markdown agree with the desk rather than closing its neighbour by implication.

## §81 — Gap 98: one rule made two opposite mistakes (2026-11-06)

`classify_turn` looked at the first token and a trailing "?". That single rule
produced both halves of this gap, and they point in opposite directions:

- a stated decision — *"Let the silence sit."*, *"I want the audience to feel
  compulsion."* — was a bare `idea`, so `should_probe` fired and Sameer asked
  "why do you think so?" of a writer who had just said what they wanted;
- a proposal about the writer's own draft — *"Could I lose the last beat?"* — was a
  `question`, so it got the answer-first treatment reserved for fact questions.

One is over-attention, the other under-attention, and both come from trusting
surface form. The fix is therefore classification, not another exception in
`should_probe` — which stays a single line, and that is the evidence the change is
in the right layer.

Each new kind carries a **behaviour**, because a label nobody reads is a comment.
`intent` forbids the interrogation explicitly; `request` forbids treating a
proposal as a fact question. Both now live in `peer.opening_contract()`, which the
engine calls, and which replaces an inline string that used to sit in the engine —
so a future kind cannot be added without someone deciding what the reply does
first, and the contract is testable without a model call.

**The boundaries are the part I am most confident about, and they are narrower
than the filing's recommendation.** The entry suggests adding patterns for "let",
"I want", "I'd like", "keep", "allow" — which I did — and "treat modal+verb as a
request", which I did **not** do in general. Two limits:

* *"Mara should die at the end"* stays a probeable **idea**. Two pre-existing tests
  pin it, and on reflection they are right: a plot decision is exactly the thing a
  co-writer should help think through. So the `should` rule is not "a statement
  containing should", it is **effect-vs-event** — *how the work should FEEL* is an
  intention, *what should HAPPEN* is an idea.
* *"Can the mother appear earlier?"* stays a **question**. The filing's
  "modal+verb" rule would have swept it into `request`; the first-person constraint
  is what separates a proposal about my own draft from a request for a judgment.

Implementing the recommendation literally would have broken a correct existing test
and mis-classified a genuine question. The recommendation is a description of the
symptom; the boundary is the actual finding.

Three of my patches silently failed on the first attempt — the engine edit, the
contraction branch (`I've decided`), and `let us`. Each was caught by a test written
before the code, not by re-reading the diff. And one revert (R6) **passed when it
should have failed**: my mutation kept `opening_contract(turn_kind)` but wrapped it
in `if turn_kind == "question"`, so the shared function was still called and then
thrown away for the two new kinds. The pin now asserts the assignment shape
verbatim. That is the same lesson as gap 73 and gap 85 — a test that names the right
symbol can still be blind to whether the symbol's result is used.

Recorded as not done, and it is the significant one: **this is a pattern table over
English.** The writer's Telugu and Tenglish turns — *"Ammaki cheppakunda
vellipothadu"* — are intentions this classifier will still read as ideas and probe.
The brief's rule holds for those turns regardless of language; the mechanism does
not. Routing non-English turns away from the probe is the honest fix, not more
regex, and that is a different gap.

## §82 — Gap 6: three of my six reverts proved nothing (2026-11-08)

The fix looked finished at "the suite is green and the behaviour reproduces".
It was not. **Reverts: 1 / 1 / 2 / 1 / 1 / 2** — and on the first measurement
three of the six stayed green:

```
R1 journal written after the document  -> 9 passed   (wrong)
R2 rollback disabled                   -> 9 passed   (wrong)
R5 journal kept after a clean refusal  -> 9 passed   (wrong)
```

Each is a different blind spot, and none was visible from the test names:

- **R1** was never observed. The tests asserted the *outcome* of an interrupted
  apply; the journal's position is an *order*. Order has to be watched from
  inside the write — `ScriptDocument.save` asking whether the journal exists —
  not inferred from an outcome a later repair also produces.
- **R2** was masked by the safety net added in the same change. With the
  rollback disabled the divergence marker did its job and the next read rebuilt
  the copy correctly, so the document read back looked right. The rollback's
  promise is narrower than the net's: agreement **on disk at the moment the
  writer is told the edit failed**. The test now reads the raw file, because the
  ordinary reader repairs what it observes.
- **R5** failed the same way one level up: the test read the text *before*
  asking for the repair report, and a read IS the repair, so the stranded
  journal had already been consumed when the assertion looked.

The generalisable lesson, and why this deserves a section: **a fix that
includes a repair path is unusually good at hiding its own defects.** Every
layer added for safety turns a broken lower layer into a slightly slower
correct result. Fine for the product, terrible for the tests. The only defence
found here is to assert each layer's promise at that layer's own boundary — the
file, not the document; the report, not the repaired text; the order, not the
outcome.

Two smaller costs: `ensure_working` refreshes the copy on its own schedule, so
any fault injection that counts writes spends its allowance on a write the test
never meant to target (the helper now matches the pending bytes instead); and
`tests/test_lock_order.py` correctly refused the two new stores until the P1-3
topology table declared them as leaves, which is the guard working as designed.

Not done: the trio is still not transactional across a power cut — the journal
makes the interruption *detectable and repairable*, not atomic. A write that
lands between the journal and the document leaves no copy of the old text, so
the repair reconstructs from the parsed script plus the log; a writer who typed
by hand outside the cycle loses that typing. Stated, not fixed.

## §83 — Gap 22: I repeated a claim instead of testing it (2026-11-08)

The register said *"FDX lossiness is the format's limit and the export code
states it"*, and it was archived as a known trade-off. I read that, restated it
to the user as fact, and offered three options built on it — including
"warn the writer about a limitation we cannot fix". The user pushed back with
one sentence: *can't you fix it at the code level instead of talking as if you
can't?* They were right, and the measurement took four minutes.

**Reverts: 4 / 1 / 7 / 7 / 1 / 1 / 7 / 1.** 13 tests.

What the code actually said. FDX carries emphasis natively: a `<Paragraph>`
holds `<Text>` runs and each run accepts `Style="Bold"`, `Style="Italic"`,
`Style="Bold+Italic"`. Nothing in the format had to give. The loss was ours
three times over:

- `parse_fdx._paragraph_text` concatenated the runs and discarded every `Style`
  — the function's own docstring says *"FDX splits styled text into runs"* and
  then joins them, which is the loss written down as a description;
- `Element` had no field to hold a style, so even a perfect parse had nowhere to
  put the answer;
- `to_fdx` wrote one plain `<Text>` per paragraph.

So the archived justification was not merely incomplete, it was **backwards**:
the format supported it, we never did. A "documented trade-off" whose
documentation is wrong is worse than an undocumented gap, because it stops the
next person looking.

Three things this fix would have got wrong if I had written it in a hurry, and
which are worth keeping:

- **`from_dict` builds `Element(...)` with explicit keyword arguments.** A new
  field is silently dropped there, so the fix would have worked until the next
  `working.json` reload — and that file is reloaded constantly. Found by reading
  the loader before writing the field, not by a test.
- **Stale spans on an edit.** Emphasis is character ranges into the old text. A
  whole-line replacement that kept them would attach the writer's emphasis to
  whatever characters happen to sit at those offsets in text they just wrote.
  The rule is now explicit: a replaced line carries no emphasis, because we
  cannot know where it belonged.
- **Stripped text shifts every offset.** The parser returns the joined runs
  `.strip()`ed, so spans computed against the unstripped join point one word
  early. Pinned by its own test (R2) — a one-character error that reads as a
  parsing quirk rather than a bug.

One revert was initially a lie in my favour: R4 "exporter ignores spans" passed
all 13 tests, because I patched the FRONT-MATTER call site while every test
exercised a scene element. The revert was ineffective, not the tests blind —
a distinction I could only make by going back and re-aiming it at the scene
path, where it failed 7 tests. Recorded because "my revert passed, therefore my
test is weak" and "my revert missed the line I meant" look identical from the
summary line.

Not fixed, and stated rather than counted: `.txt` has no mechanism for emphasis,
so that half of the original filing stands, and the PDF parser extracts no
styling at all — a bold in a PDF still does not arrive. Non-numeric scene numbers
("12A") are a separate loss: `scene_number` is typed `int` and is load-bearing
for undo, redo and the knowledge graph, so re-typing it was deliberately not
bundled into this change.

## §84 — Gap 65: most of what I promised to build already existed (2026-11-08)

**Reverts: 1 / 3 / 1 / 1 / 3.** 7 tests.

Before writing anything I read the publish path, and found that the plan I had
sold the user one message earlier was mostly already built:

- `publish_generation` already re-reads the live draft and refuses if the digest
  moved — gap 4 built that;
- `manifest._merge_manifest` already stops an in-flight run from resurrecting a
  stale `active_draft`: it only takes a writer's value for a field that writer
  actually changed.

Had I implemented "C1: stamp a digest, compare at publish, refuse", I would have
written code that already existed and reported it as progress. The estimate I
gave ("half a day for the export side, several days for the whole") was not
wrong so much as mis-addressed — I was costing a design without reading the one
that shipped.

What was actually open, and it is a familiar shape:

```
try:    live_digest = document_digest(load_working(m))
except: live_digest = None
if live_digest is not None and man['digest'] != live_digest: raise
```

**An unreadable draft skipped the check and published anyway.** "I could not
verify" was read as "verified". This register has now found that same inversion
four times — gap 6's unwritable log, gap 22's "the format can't", gap 93's
missing denominator, and here. It is the dominant failure mode of the code in
this repository: a guard whose failure path is permissive, so the guard is
absent exactly when the system is unhealthy.

A second, quieter defect sat next to it. Publication joined each source to
`gen_dir` but looked the live paths up on the project, then **skipped a missing
artifact while still moving the pointer** — a publication claiming a reading it
never copied, and a manifest naming a path outside its folder could have copied
an unrelated project file into the report. Both now refuse.

The find worth keeping: `tests/test_store_fault_injection.py` **was silently
depending on the fail-open**. Its fixture published a reading for a project with
no parsed script and no working copy — it only ever worked because an unreadable
draft made the comparison skip itself. Fifteen minutes after the fix, four tests
went red not because the fix was wrong but because the fixture had been written
against a hole. A test that passes only through a defect is a test that will
defend the defect, and the honest repair was to make the fixture resemble a real
project rather than to weaken the check.

Still open, and deliberately not marked closed: the 409 that blocks a draft
switch during a run is a `threading.Lock`, so it is **in-process only** — a CLI
run and the web UI on one project can still switch under each other — and
`upload.save()` plus the parse run with no lock held, so a run starting in that
window sees a half-written document. Binding reports per-draft (the C2 option the
user did not pick) remains unimplemented. The entry stays NARROWED rather than
FIXED, because a reader of the register should not have to discover that the
"refused" in the message is only true within one process.

## §85 — Gap 7 / gap 65: the mechanism was there; nobody had claimed it (2026-11-08)

**Reverts: 7 / 1 / 1 / 1 / 2 / 3.** 12 tests.

The instruction was "shared cross-process run/publish coordination". Before
designing anything I read `jsonio` and found it had carried a working advisory
file lock for years — every store in this package takes one, and it is correct
across processes on both platforms. Nothing new was needed mechanically. The
analysis run simply had no claim of its own, and `_analyze_lock` is a
`threading.Lock`, so two browser tabs were serialised and a CLI run beside the
web UI was not.

That is the second gap running where the honest answer was "this already
exists, it just is not used here" (§84 was the first). Both times the register's
filed text pointed at a design, and the code pointed at a missing call.

Two older defects surfaced on the way, neither of them this gap:

- **`main()` discarded every handler's exit status.** A refused run printed its
  refusal to stderr and exited **0**. This is gap 39's bug class — "reports a
  failure with a success status" — surviving in the dispatcher gap 39 never
  looked at, because gap 39's fix went into `cmd_watch`'s own return path. Found
  only because the CLI leg of the new test asserts the *process* exit code; an
  in-process call would have returned 1 happily while the program reported
  success.
- **My own first guard crashed when the project directory did not exist yet**,
  which is the normal state when `run` is about to create one — the guard ran
  before the code that makes the directory.

The revert discipline earned its keep again, and in the same way as §84. R1
("the run lock takes no OS lock") came back **12 passed** — a green result on the
single most important line of the change. It was not a blind test: my patch had
hit `_acquire_os_lock`, the helper `_StoreLock` uses, while `RunLock` has its own
inline `flock` thirty lines further down. Re-aimed by locating the call *inside*
the `RunLock` class rather than by matching text, it failed **7 tests**. Twice
now I have reported a surviving revert that was really a mis-aimed one, and twice
the difference was only visible by checking the patch landed where I meant rather
than where the string matched. That is worth stating as a rule: **a revert must
be shown to have changed behaviour, not merely to have been written.**

Gap 65 closes here rather than earlier because its remaining hole was the
cross-process switch — the threading lock could never see a CLI run, so a switch
during one was allowed and that run published into a draft it never read. The
same run lock answers it. What is still true, and stated rather than glossed:
reports remain one live set per project, not one per draft, so a reading of an
older draft is *refused* rather than kept and labelled. That is a product
decision (the C2 option), not a safety hole.

## §86 — Gap 8: the codebase already knew, and the archive was outside the net (2026-11-08)

**Reverts: 5 / 1 / 1 / 1 / 1 / 1.** 6 tests.

The entry was graded at "the weaker half" because it held two claims. Measured,
one of them was already closed: gap 72 had given both backup routes per-file
omission accounting, an `X-Backup-Complete` header and a manifest inside the
archive. So the incompleteness half needed verifying, not building.

The credential half reproduced immediately: a project manifest holding
`sk-live-...` came back in **both** the project archive and the library archive,
verbatim, inside `project.json`.

Two things about that are worth writing down.

**The principle was already in the codebase and the backup was simply not in
it.** `tests/test_privacy_statement.py` has a class called
`TestTheSecretStillNeverLeaves`; it sweeps `/api/config` and `/api/health`. The
archives were never in that sweep, so a surface whose whole purpose is to leave
the machine was the one surface nobody had checked. When a product states a
principle, the gap is usually in the list of places it was applied — not in the
principle.

**The key is supposed to be there.** `_adopt_connection` deliberately copies the
token into every project manifest (gap 58) so `resume` and the CLI work without
the writer retyping it. So "remove the key from `project.json`" would have been
the wrong fix twice over: it breaks that design, and it puts the secret back in
front of the writer on every run. The right question was narrower — *where is
this file allowed to travel?* — and the answer is "the writer's own disk, not an
archive that gets emailed". That is why the redaction lives in the backup route
and nowhere else.

The redaction is **structural, not a text scrub**: the manifest names its own
secret field, so that field is cleared and every other byte is untouched.
Matching a token's shape across arbitrary content would either miss a key it did
not recognise or corrupt a script holding the same characters. The test that
matters most is therefore not "the key is gone" but **"everything else survived"**
— title, `server_url`, stages, drafts, source record. A redaction that quietly
dropped those would trade a confidentiality bug for a restore bug, and on a
backup availability is the entire point.

And the omission is **named**, not merely absent: `X-Backup-Credentials` plus
`credentials_withheld` in the embedded manifest. Deliberately a different header
from `X-Backup-Complete`, because "your archive does not hold everything" and
"your archive does not hold your API key" are different facts and the second is
good news; folding them together would report a successful redaction as an
incomplete backup.

Process note against myself: I committed this change while ruff was reporting an
`E713`, because I piped the check and the commit into one command and read only
the last line. Amended within the same turn. The standing correction in this
register is about not ending a turn red — committing past a lint failure is the
same failure at a smaller scale, and it happened because I let a one-line output
tail stand in for reading the result.

Not claimed: an archive produced before this change still contains the token.
Redaction cannot reach a file already on someone's disk, and the entry says so.

## §87 — Gap 10: one word carried two promises, and a third was never made (2026-11-08)

**Reverts: 3 / 3 / 2 / 1 / 1 / 1.** 9 Python tests, 4 node tests.

`status: "verified"` was emitted for a normalised exact hit **and** for a fuzzy
match as loose as the 0.72 threshold. Those are different promises — "the script
says this" and "the script says something this close" — and a writer could not
tell them apart, nor could the desk, whose readout said "N of M quotes
verified". The 0.95 near-identical boundary had already been added to stop one
kind of paraphrase being certified; a coarser one sailed through.

The larger half is the one with no code fix at all. **"Quote verified" answers a
question about text, and the writer reads it as an answer about the claim.** A
finding can quote a real line exactly and still be wrong about what it shows —
which is the filed defect: a fabricated contradictory observation carried an
exact, verified quote. So the report now says, in those words, that a verified
citation means the text was found and does NOT mean the claim is supported, and
tells the writer to judge the claim themselves.

The temptation here was a `claim_supported: true|false` field. **I did not add
one, deliberately.** Nothing in this pipeline reads the argument between the
quote and the conclusion; there is no argument-level verifier. Any such boolean
would be fabricated confidence — precisely the defect this gap is about, moved
one level up and wearing better clothes. The honest fix for "we cannot assess
this" is to say so, not to invent a verdict.

Two errors of my own, both caught by the suite rather than by me:

- I added `exact`/`approximate` **inside** the counts dict, which broke
  `sum(verification_summary.values()) == len(findings)` — an invariant other
  code and two tests rely on. The split is a second *view* of a subset of
  `verified`, not more findings. It now lives in separate keys and the rule has
  a name (`locating_total()`) instead of being re-derived in each reader.
- **Seven pre-existing node tests pinned the phrase "quotes verified".** That
  phrase was the defect, so I changed the wording — but only the wording: every
  denominator, count and percentage gap 93 established is byte-identical, and
  the tests were reworded rather than loosened. A wording change that quietly
  drops a denominator is how gap 93's own bug came back the first time, so the
  numbers were checked one by one rather than assumed to survive a `replace()`.

Not claimed: nothing here makes the analysis better at *judging* findings. The
gap closed is epistemic honesty — the surfaces no longer imply a check that does
not exist. An argument-level verifier remains absent, and the register now says
so in the entry rather than leaving a reader to infer otherwise.

## §88 — Gap 11: one claim was right about the number and wrong about the silence (2026-11-08)

**Reverts: 1 / 2 / 3 / 2 / 3.** 8 tests across two files, plus 4 pre-existing
suites re-run as the narrowings' safety net.

Three of this entry's six claims were code, and I fixed those. The other three
are **explicitly not fixed**, and the register row now says so rather than
letting a "FIXED" stamp imply the whole entry closed:

- **The grounding number was true; the diagnosis was not.** The entry said the
  character fragment "omitted 30 of 83 selected rules", and that is exactly
  right — 83 selected, 53 admitted, 30 shed by the 40,000-char default. But it
  read as a silent-drop bug, and it is not: `_render_budgeted` has always
  appended "(30 further craft principles omitted…)" to the prompt, with a test
  protecting it. **This is the fifth filed fix in this register that was already
  partly done** (§85's lesson, still holding). Had I "fixed" it without running
  the fragment, I would have added a second disclosure of the same fact and
  called it a gap closed.

  The real defect is one level out, and it is the *writer's* side: the model was
  told what was shed, the writer never was. Worse, what is shed is the
  **lowest-confidence tier** — so a defect whose only principle was shed was
  never looked for, and its absence reads as a clean bill of health. That is a
  distortion of feedback, which is what this entry is actually about.

- **My first placement was wrong in a way only a test caught.** I put the
  disclosure inside "Detailed Analysis", which is skipped when there are no
  findings — so the run that most needs "a missing note is not proof" printed
  nothing about it. It is now above that section, unconditional.

- **Two narrowings, and both needed the old positives re-run.** Making "however"
  require an adversative partner broke the sentential case (`; however, the
  script shows…`); making a subtitle mention require an accessibility demand
  broke "without clear separation or translation", where the demand spans four
  words. Both were caught by pre-existing tests, not by my new ones — a
  reminder that a narrowing's real test suite is the one written before it.

**What I refused to do:** invent consistency between the differing severity
tiers for similar voice checks. The entry lists three inventory problems —
tier disagreement, absent related-rule ids, requirement/input mismatch — and all
three are judgements about *editorial intent* in the KB, not behaviour I can
verify from code. Picking tiers myself would replace a known inconsistency with
an unknown authority. They stay open, named, with a reason.

## §89 — Gap 12: the obvious fix was the worse bug, and the suite said so in one run (2026-11-08)

**Reverts: 5 / 7 / 2 / 1 / 4.** 10 unit tests, 4 HTTP tests.

The collision is real and I reproduced it exactly: two findings, same category,
same quote, same scene, **opposite** claims — both `fyrjq3y`. One verdict
answered both. The writer could not call one wrong without calling the other
wrong.

**The obvious fix was wrong, and I want that recorded rather than tidied
away.** Folding the claim into `compute_finding_id` distinguishes the two rows
immediately — and broke three pre-existing tests asserting that a quoted
finding's id **survives the model re-wording its `issue`**. That property is not
incidental: the model rewords constantly, and the id is what keeps a verdict
attached across a re-analysis. Re-keying on prose would orphan every mark on
every run to fix a collision that affects two rows in one report. I reverted my
attempt instead of adjusting the tests to it, because the tests were right and I
was about to trade a rare defect for a universal one.

So the fix is conditional: ids unchanged; a store key is claim-scoped **only**
where the report actually collides; a legacy bare-id verdict on a colliding pair
is shown as a question. Three states, none of them a guess.

Two of my own bugs, both found here rather than by me:

- The first `resolve_verdict` returned `(None, None)` for a legacy bare verdict
  on a collision — **silently dropping** the judgment, in the exact function
  whose docstring I had just written to say it must never be discarded. My own
  probe caught it, not a test I had written.
- The server helper wrapped its whole body in a bare `except Exception`. A
  `NameError` (a function imported only inside the sibling route) surfaced as
  **"no collisions"** — indistinguishable from the healthy case, so the feature
  would have looked fine and served nothing. Narrowed the catch to the report
  read. This is the same permissive-failure inversion §84 names; I walked into it
  in the same turn I was quoting it.

**Left open, deliberately:** the same-mtime report-signature probe in this
entry's second half. A report's signature is a cache key, and changing what goes
into it changes cache validity everywhere; that deserves its own gap with its
own blast-radius check, not a paragraph appended to this one.

## §90 — Gap 20: the permutation was valid and the board was still wrong (2026-11-08)

**Reverts: 1 / 2 / 1 / 4 / 1 / 4 / 1.** 7 Python tests through the real HTTP
routes, 5 node tests on the notice text.

The entry's headline — a saved order that no longer fits silently fell back to
natural order while `has_board` still said true — reproduced immediately. But
the entry contained a second failure nobody had framed as one: **a board can be
valid and still wrong.** The stored form is a permutation of scene *numbers*, so
a re-parse that keeps the count while changing what scene 3 *is* passes every
check. The board then draws itself over scenes the writer never arranged, and
every layer agrees it is current. Numbers are not identity.

So the fix records identity (`headings`) at save time, compares it on read, and
distinguishes three states rather than two: current, stale-with-identity-check,
and stale-with-only-a-permutation-check (`verified_by: "numbers_only"`). That
third state exists because a board saved before this change genuinely cannot be
checked any other way, and claiming either answer would be a guess — the failure
mode §84 is about, in the *reporting* direction this time.

**The property I protected harder than any other:** a failed match never
rewrites `beatboard.json`. It would have been one line to "fix" a stale board by
saving the natural order over it. That deletes an arrangement the writer made,
on the strength of a check that just proved it could not be trusted. Staleness is
a question for the writer; the board is preserved and the writer reconciles.

**Process failure worth recording.** I spent eight read-only calls on this gap
and ended a turn with nothing written — the exact objection raised twice before.
The recovery is not an apology: the patch and its tests went in on the next two
calls, and the sandbox reset partway through destroyed the local history, which
only mattered because the work was already committed to origin. Commit early is
not tidiness; it is the only thing that survives.

## §91 — Gap 25: right about the defect, wrong about where to fix it (2026-11-08)

**Reverts: 5 / 4 / 1 / 2 / 1 / 1 / 2.** 14 tests driving the real `parse_pdf`
against real PDF bytes.

The filed defect is real and reproduced exactly: page 1 extracts, page 2 is ink
with no text layer, page 2 is `continue`d away, and completeness is judged
**globally** — page 1 satisfies the check, so the parse looks whole. The unit of
judgment is now the page, OCR is scoped to the pages that need it, and
`page_coverage` puts total/blank/recovered/unread/read/complete on the document
(and through save/load) so "we read 1 of 2 pages" is a number, not a flag.

**The part I got wrong was placement, and it cost six tests in one run.** For the
entry's second half I made `run_parse` raise when a parse produced zero scenes.
That is the intuitive place — the stage said `complete`, the truth was "nothing
read", so make the stage tell the truth. But the upload route *already* handles a
sceneless file better than I was about to: it rejects with a 400, a specific
explanation and a directory cleanup, all of which run AFTER `run_parse`. My raise
preempted it and turned a careful 400 into a 500. And draft switching depends on
a failed parse being recorded and restored from a snapshot sidecar; changing what
`run_parse` does on empty changed the restore.

Narrowing to "zero scenes AND a parser error" did not save it either: the
fountain parser reports "No scene headings detected" as an **error**, so every
sceneless upload still tripped the gate. A guard that fires on a case somebody
else handles better is not a guard, it is an interception. The gate now sits in
front of the analyze route, which is where the filed risk actually is — the
analysis of an unread script — and nothing else changed.

**Two of my own tests were worthless, and I only found out by reverting.** R3
removed the OCR page filter and the suite stayed green, because my fake
`_ocr_extract` was page-blind and my assertion was about what `parse_pdf`
*passes*, not what OCR *does*. R5 removed `page_coverage` from serialization and
the suite stayed green, because every assertion read the object the parser had
just returned. Both now drive the real function against fakes that record what
happens. A test that cannot fail is worse than no test: it certifies nothing and
buys silence.

## §92 — Gaps 28 and 29: the crash before the model, and the answer the filter ate (2026-11-08)

**Reverts: 9 / 2 / 2 / 1 / 1.** 22 tests across two files.

**Gap 28 is the cheapest kind of real bug:** `max()` over a filtered generator
with no guard. "Hi", "Yes", "ok", "?" and any Telugu utterance each raised before
a model was called — and a one-word affirmation is not an edge case, it is most
of what a writer types. The fix filters the candidate list first and falls
through to the next name, which is the honest outcome: an unmatched character is
a legitimate answer, and an invented match would be worse than a crash.

**Gap 29 had two faults, and the second is why nobody saw the first.**

1. The filter removed the answer to a direct question about its own subject. It
   had no idea what was asked, so "Should I use subtitles?" got the same treatment
   as unsolicited commentary. It now takes the user's turn and keeps the answer
   when the writer asked.
2. **The engine stored `""` as an assistant message.** A blank bubble is
   indistinguishable from a crash, and the writer is told nothing. That is the
   part that turned a filter decision into a silent failure.

My first fix was to make `strip_language_meta` never return empty. **A
pre-existing test refused it, and the test was right:** the function's documented
contract is that a wholly-meta reply cleans to empty, and callers rely on it. I
reverted that and fixed the caller. The rule I nearly broke: *when a contract is
pinned by an existing test, the bug is usually where the contract is USED, not
where it is defined.*

**Found while fixing it, and it is the same defect wearing plain clothes:** "The
dialogue reads as Telugu." — the simplest possible statement of the exact thing
this filter exists to remove — passed through untouched, because the pattern
required a qualifier after "reads as" ("reads as **regional**..."). Naming a
language IS the identification.

**One of my tests could not fail.** Reverts R1–R5 were built to prove each
assertion; R3 (the engine's blank-recovery) passed with the recovery removed,
because every test in that file exercised `clean_reply`, not the caller. The new
`_generate_mirrored` tests fixed that. This is the second time in three gaps that
reverting found a test certifying nothing (§91 had two). Reverting is not
ceremony; it is the only check that the tests are load-bearing.

## §93 — Gap 31: a prompt instruction is not consent (2026-11-02)

**Reverts: 3 / 1 / 1 / 1 / 1.** 21 tests in `tests/test_other_projects_need_consent_to_enter_a_prompt.py`.

The original defect is reproduced by the test that matters: a synthetic shelf,
the real library provider, the real chat engine, and a fake model capturing the
actual assembled system prompt. With no consent, the other project's title and
character name are absent. After explicit consent, both are there. The doctor's
aggregate uses the same gate. The preview path shows the specific projects,
characters and themes locally before the writer agrees to those details being
placed in a prompt.

**Three self-corrections while fixing this:**

1. My first policy treated a local model as consent because the digest stayed on
the machine. That was too permissive: local processing is not what the writer
consents to, and the writer may not want scripts mixed even locally. Consent is
now required for every model destination; locality changes neither the default
nor the gate.
2. I initially checked consent when the session loaded. That would have made
revocation cosmetic until the session was reloaded. Deferred providers now read
the project manifest at prompt-build time; revoke while the chat is open, and the
next turn does not build either cross-project block.
3. The entry says "preview its scope". A vague statement that titles and cast
*may* be sent would technically disclose categories, not the particular scope.
The UI fetches and displays the actual titles, character names and themes before
showing the confirmation. The preview is a local UI response, not a model call.

**Boundary distinction kept:** the app already refuses remote model URLs unless
the writer starts it with `--allow-remote-server`; the per-project shelf consent
is a separate boundary. Having one does not stand in for the other. This change
does not establish that an external transmission happened.

**Not yet proven:** the browser confirmation is covered by the existing UI's
normal click plumbing and the server route is exercised through Flask tests, but
there is no browser-level test asserting the exact confirmation text or its
interaction on a real rendered page. The server-side prompt boundary is covered
end to end. Revert each gate independently before marking the fix closed.

Reverts: 3 / 1 / 1 / 1 / 1 (remove the provider gate / cache consent at session
load / default the manifest to on / omit the actual-scope preview / skip saving
the writer's choice). Each revert made its corresponding regression test fail.
The full system-prompt test also fails if the provider gate is removed: it
captures the assembled prompt, not merely the digest callback.

## §94 — Gap 32: reasoning is not the reply, and the stream is not the record (2026-11-02)

**Reverts: 1 / 1 / 1 / 1 / 1.** Six focused tests in
`tests/test_hidden_reasoning_is_never_a_chat_reply.py`; the old H7 fallback test
was changed because it asserted the unsafe behavior.

**The existing test was the first thing to distrust.** H7 explicitly required
`reasoning_content` as a fallback answer. It had been put there to fix empty
reasoning-model replies when `enable_thinking` was left on. But the client already
disables thinking; if the provider still returns no `content`, the honest
behavior is to say there was no final answer — not to relabel a field called
`reasoning_content` as user-facing. Both blocking and streaming clients now
ignore that field. Streaming passes only `content` to the caller; both paths
raise rather than return an empty/whitespace answer if no final content exists.

**Why I did not buffer every token:** this is a slow-model co-writing desk; the
existing product choice was immediate streaming for perceived latency. Buffering
all output until the guards finish would silently change that behavior, and this
gap supplied no latency evidence that justified the trade. Instead, the UI names
the streamed text as a **draft** and says the final reply replaces it. The final
SSE event carries the stored, cleaned history; on success the browser paints that
history, not its raw token accumulator. On error the pending bubble is replaced,
not left looking like a completed answer.

**What the tests establish:** synthetic stream frames containing only
`reasoning_content` never reach the callback and fail explicitly; mixed frames
show only `content`; successful completion still returns the collected content.
These are transport tests with fakes, not evidence that any real provider leaked
reasoning. The UI test pins the provisional label and the final-history render
contract in source, but no Chromium binary was available for a browser-level DOM
assertion of the transition. That is a weaker check and stays named as such; do
not claim the browser badge was visually verified.

**Reverts:** restoring the blocking fallback, restoring the streaming fallback,
removing the empty-stream error, removing the empty blocking error, and removing
the provisional browser cue each fail one focused regression test.

## §95 — Gap 33: the allowed URL is not the whole route (2026-11-02)

**Reverts: 10 / 1.** 11 tests in `tests/test_inference_redirects_and_proxy_environment.py`.

The starting probe had already established the dangerous behavior with synthetic
payloads and loopback mock servers: the analyzer, co-writer sync, co-writer SSE
and external-local STT all followed a 307. The fix is one shared transport,
not four copies of `allow_redirects=False`: every model GET/POST and STT request
refuses any 3xx before a second hop, and explicit `proxies={http: None,
https: None, all: None}` prevents Requests from silently consulting ambient
proxy environment variables. The existing destination rule stays intact: webapp model endpoints are loopback
unless the process launch opts in to remote; the analyzer CLI requires an
explicit `--server` URL; STT is loopback-only. Existing connection-mode tests
still prove the explicitly opted-in remote webapp configuration works directly.

**The decision is refusal, not hop-validation.** A model API redirect can be
made to work by validating each hop, resolving and pinning every host, checking
scheme changes, and carefully handling auth/body replay. That is a larger and
more brittle policy surface than the app needs: the operator already supplies
the final inference URL. 301/302/303/307/308 are therefore all refused and the
error asks the operator to configure the final URL. This may break a provider
that requires redirects; that compatibility cost is intentional and documented.

**The ambient proxy is also policy.** A request can have a correctly validated
URL and still route through `HTTP_PROXY`/`ALL_PROXY`. A corporate proxy can be
legitimate, but this desk has no explicit proxy consent/configuration surface.
Silently inheriting it is not a safe default for private screenplay/audio
payloads. Ambient proxies are disabled; a future explicit proxy feature must
show its endpoint/consent rather than weakening this boundary implicitly.

**What tests prove:** local redirector and destination servers see the 30x
variants; the destination receives zero payloads. Actual client paths cover
analyzer POST and GET, co-writer blocking and SSE, and external STT multipart
audio. A local fake HTTP proxy with `HTTP_PROXY`, `http_proxy`, `ALL_PROXY`, and
`all_proxy` set receives zero bytes while the analyzer's configured local
destination gets the synthetic POST. No external host or private data is involved.

**Remaining:** this does not pin the DNS resolution for an explicitly consented
remote hostname. Redirects are impossible now, and arbitrary remote hosts still
require the existing process-launch opt-in; DNS resolution of that configured
host remains part of that opt-in's trust. No external-provider compatibility or
real corporate proxy was tested, because neither is permitted by this policy.

Reverts: restoring follow behavior (10 failures) / restoring ambient proxy
routing (1 failure).

## §96 — Gap 34: protect the key without making the backup lie (2026-11-02)

Reverts: 1 / 1 / 1 / 5 / 1 (save mode / legacy migration / recovery redaction / symlink membership / root containment).

**Reverts:** each independent reversal caused its expected regression: restoring
ordinary mode on credential saves **1 failed**; disabling legacy permission
migration **1 failed**; bypassing recovery redaction **1 failed**; restoring
symlink-following archive behavior **5 failed**; and removing project-root
containment **1 failed**. These are the 11 tests in
`tests/test_gap34_secure_archive_boundaries.py`.

**The filing was partly stale.** Gap 8 had already redacted `api_key` from the
project and library archives and recorded the withholding. Rewriting that would
have duplicated a solved path. The real archive hole was the **recovery** backup,
which used `_add_file` instead of `_add_file_redacted`; it copied a valid
`project.json` credential unaltered. The other still-live issues were ordinary
umask permissions for a secret-bearing manifest and `ZipFile.write` following
file symlinks.

**Fixes now share a policy:**

- `atomic_write_json` accepts a mode while preserving the old default for every
  ordinary store. A manifest with an API key is atomically created at `0600` on
  POSIX; `ProjectManifest.load` migrates old readable credential manifests to
  `0600` before returning the key. On Windows, the process relies on the parent
  directory's per-user ACL; no custom Windows ACL writer or OS keychain was
  added.
- Every archive (project, library and recovery) uses the same redaction and
  member policy. A parseable manifest is copied with its known key set to null.
  A damaged manifest with a syntactically complete key value is redacted in its
  original bytes; one with a key marker that cannot safely be isolated is
  withheld and named as an incomplete archive. Damaged manifests with no key
  marker remain byte-identical, preserving the recovery evidence contract.
- File members are copied from an opened regular-file descriptor, with
  `O_NOFOLLOW` where available; symlink/reparse-point files are skipped. The
  opened and named file identities are rechecked before any content is read,
  including platforms without `O_NOFOLLOW`. Archive walking prunes symlink
  directories and records them. Project roots resolving outside the library are
  refused (or recorded as failed in a library archive).
  Every omission appears in the embedded manifest and completeness header.

**The self-review trap:** the obvious `if islink(): skip` followed by
`ZipFile.write(path)` still has a check/open race and lets `ZipFile.write` follow
what it reopens. The implementation instead opens with `O_NOFOLLOW` where the
platform supports it, checks `fstat` for a regular file, and copies that handle
into `ZipFile.open`. The gap-72 fault injector had to move from monkeypatching
`ZipFile.write` to the explicit archive-copy seam; it still proves a vanished
file is named rather than silently dropped.

**Limits kept visible:** the test reproduced POSIX `0644` under umask `022` and
now proves `0600` plus migration. This does not claim a portable secure store:
Windows ACLs are inherited, not rewritten, and no OS keychain migration was
attempted. Existing exported archives remain outside the app's control. The
recovery JSON endpoint still exposes raw manifest bytes to the local caller by
design; only downloaded archives apply redaction.

**Validation:** `tools/gap_harness/close_gap.py check 34` passed all checks:
48 gap-owned tests, **3150 passed / 8 skipped / 2 warnings** in the full Python
suite, and Ruff clean. The revert runs changed only the targeted policy at a
time and restored the working implementation after each run. The five
archive-member failures were
project, library and recovery file links; a directory link; and a symlinked
project manifest;
the separate root-symlink case failed under the root-containment revert.

## §97 — Gap 36: context-window cache has no notion of time or model (review before implementation)

**Finding:** `BaseLlamaClient.context_window()` stores `(implicitly) just a value` in the process-global `_CONTEXT_WINDOW_CACHE`, keyed only by `base_url`. It has no expiry or invalidation. A server restart/model replacement at the same endpoint can leave the old positive value indefinitely; an old `None` is also indefinite, so a server that later exposes `/props` stays on fallback sizing until process restart. Different explicit model IDs and different authorization contexts at the same endpoint also currently share one answer. The existing tests prove that cache reuse saves probes, but their autouse fixture clears the global cache on both sides and therefore does not test real cache aging or replacement.

**Self-critique of the obvious fixes:**

- Clearing on every client construction defeats the cache: webapp clients are request-scoped and prompt budgeting would pay a `/props` round trip (up to three seconds) on every turn.
- Keying only by model ID fixes explicit model switches, not replacing a GGUF while keeping the same model alias, restarting llama.cpp at the same URL, or a gateway changing its backing model.
- A long-lived TTL does not address the registered failure mode; a short TTL on every call causes avoidable probe latency. `None` needs a shorter retry window than a valid capability, or unsupported/offline builds either hammer `/props` or remain stale forever.
- Automatically resending a chat after a context-length rejection could repeat a paid/slow generation or duplicate side effects. The safe response is to invalidate the cached estimate, return an explicit context-size error, and let the next turn probe with a fresh budget—not silently replay the writer's turn.

**Recommended implementation to proceed with:** key entries by normalized base URL, explicit model ID, and a one-way digest of stable extra headers (so tokens are not retained in the cache key); expire successful probes after 60 seconds and `None` results after 10 seconds; cap/prune the process cache; expose per-client invalidation; and clear the entry on recognizable HTTP context-window rejection in the analyzer, co-writer sync, and co-writer streaming requests. Keep current best-effort behavior: the probe can fail without breaking a turn, and unsupported `/props` uses the configured fallback. Tests should use synthetic clients/responses to cover same-URL model changes, same-model replacement after TTL, negative-cache expiry, auth-context separation, context-rejection invalidation, and cache reuse within TTL. No live model/server or external data is needed.

**Limits to keep explicit:** TTL bounds staleness, it cannot identify a server generation the endpoint does not expose; immediately after a same-alias restart, the first request can still use the cached value until expiry or a context-rejection response. The existing HTTP error remains visible for that request. Probe latency, per-process rather than distributed caching, and gateways that change backing models without changing model ID remain trade-offs. No claims about a real user's server are justified by fake responses.

**Implementation/self-review result for §97:** the recommended bounded cache is
now in place. Stable header values are represented only by a SHA-256 digest in
the key. A valid window lives 60 seconds; a failed/unsupported probe lives 10;
expired entries are pruned and the cache is capped at 256 entries. A recognizable
400 context-size error or 413 clears all model entries for that endpoint/header
identity (important because co-writer fallback can mutate the model after the
probe). Analyzer, co-writer synchronous, and co-writer SSE paths each return an
explicit “cached context estimate was cleared; retry to rebuild the prompt”
error rather than replaying the turn.

The new synthetic tests pin same-alias refresh after 60 seconds, the shorter
negative TTL, model and authorization isolation, cache bounds, fallback-alias
invalidation, and all three rejection paths. Independent reverts caused the
expected regressions: no positive TTL **1 failed**; no model key **1**; no auth
key **1**; indefinite negative cache **1**; no rejection invalidation **3**;
no cache cap **1**; and exact-key-only invalidation after fallback **1**.
Reverts: 1 / 1 / 1 / 1 / 3 / 1 / 1.

**Validation for gap 36:** `tools/gap_harness/close_gap.py check 36` passed all
checks, including **9 focused cache-refresh tests**, Ruff clean, and the full suite
(**3159 passed, 8 skipped, 2 warnings**). All seven independent reverts above
produced nonzero expected failures. The behavior is proven with fake responses
and a fake clock only; no model server was contacted.

## §98 — Gap 37: a file in the inbox is not necessarily finished (review before implementation)

**Finding:** `process_pending()` treats directory visibility as producer completion: it atomically moves every supported name into `.processing/`, immediately copies/parses/analyzes it, then files the claimed inode into `done/`. The claim solves duplicate workers (gap 16), not an active producer. On POSIX an open writer can continue appending after the rename; a short quiet-period or size check cannot distinguish “finished” from “paused during a slow copy”. A content hash before/after analysis can catch writes during that interval, but cannot establish that a paused producer will never resume after the final check. Network-share timestamp caching and Windows rename/share rules make a portable open-handle heuristic even less credible.

**Self-critique of the tempting fixes:**

- A one-second stable-size window would make the reproduction less likely but is not a completion guarantee; a slow upload can pause longer. Advertising it as a fix would contradict the register's own caution.
- Merely hashing before and after analysis catches an important mutation window, but not a later append through a still-open handle. It is defense in depth, not producer completion.
- Moving the source to `.processing/` is not a producer handshake: on POSIX, the writer's open file descriptor continues to name the same inode after rename.
- Requiring a new sidecar changes watch-folder UX and makes `watch --once` report pending inputs. That is real friction, but a protocol that claims completion only after an explicit signal is the honest cross-platform boundary.

**Recommended path to implement:** require a sibling `<filename>.<extension>.ready` marker, created only after the producer has closed and published the source (prefer write-to-temporary + same-filesystem atomic rename, then create marker). Without it, leave the source untouched and report `pending`, never parse it or move it to `done/`. Claim source and marker together into the existing per-file `.processing/` directory; consume the marker after the attempt, and tell failure-note readers to republish the marker when retrying. Hash the claimed source before work and verify it again before success; if it changes despite the producer contract, remove the partial project and file the complete source as failed. Update `watch --once` output/exit semantics and docs so an unmarked file cannot look like a completed batch. Keep gap 16's collision-safe filing and atomic claims intact.

**Limits:** no consumer can prove a producer obeyed the ready protocol if that producer continues writing after publishing. The marker is an explicit completion assertion, not cryptographic attestation. A post-analysis content check catches writes during processing; a producer that writes after the final check remains outside the protocol. Network shares and Windows were not available here; the contract avoids depending on their open-file/mtime heuristics, but their atomic rename behavior still depends on same-filesystem producer operations. No real screenplay is needed for validation.

**Implementation/self-review result for §98:** watch mode now processes only a
supported source with a regular sibling `<filename>.<extension>.ready` marker.
An unmarked source remains byte-for-byte in the inbox and returns `pending`; the
watch loop announces that state once per arrival, and `watch --once` prints it
and exits 1. The producer marker moves into the same `.processing/<claim>/`
folder as the source before any parse work; if that pairing fails, the claim is
left visible rather than restored with an overwrite-prone `os.replace`. If the
OS refuses to claim a still-open source, it is reported pending while both
source and marker remain in the inbox. Success and failure consume the marker;
the failure note explicitly says to recreate it when retrying. SHA-256 plus file identity/size/timestamps are verified before
and after processing, including after parser/analyzer errors; changed inputs do
not leave a project that could be mistaken for analysis of the final bytes.
Gap 16's collision-safe `done/`/`failed/` filing and source claim were kept.

The new synthetic tests cover an open writer held across multiple polls, no
processing before the completion marker, marker-link refusal, OS-level claim
refusal, mutation during analysis, cleanup of the partial project, retry
guidance, and CLI pending semantics. Independent reversions caused expected failures: remove readiness
requirement **3 failed**; remove content verification **1**; treat pending as
success in `watch --once` **2**; leave the readiness marker out of the atomic
claim **1**; remove marker retry guidance **1**. Reverts: 3 / 1 / 2 / 1 / 1.

**Limits:** a ready marker is a producer assertion, not proof that a buggy
producer will never write again. If the producer violates the contract before
worker fingerprinting and then stops, no consumer can reconstruct intent; if it
writes during processing, the post-check catches it. We do not claim Windows or
network-share execution from the local filesystem test. The UX is intentionally
stricter: direct drops without a sibling `.ready` are pending, and the docs now
show how to publish with a same-filesystem atomic rename followed by marker
creation.


**Validation for gap 37:** `tools/gap_harness/close_gap.py check 37` passed all
checks, including **34 watch-related tests**, Ruff clean, and the full suite
(**3166 passed, 8 skipped, 2 warnings**). The five independent reverts above
produced nonzero expected failures. All inputs were synthetic temporary files;
no screenplay or model server was used.
