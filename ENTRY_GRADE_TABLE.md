# Per-entry grade table — every numbered finding, graded individually

This file exists because the self-critique's grading lived in prose and in two aggregate tables that
did not sum to the register. That made "how strong is gap 47?" a judgement call instead of a lookup.
Here every entry gets one grade, on the scheme already published in
`SELF_CRITIQUE_OF_GAP_REGISTER.md` §1.

**The scheme, restated so this file stands alone:**

| Grade | Meaning |
|---|---|
| **A** | Reproduced through the real interface (real route, real CLI, real parser/exporter, real function on synthetic input). |
| **B** | Real mechanism, but the reproduction needed a constructed condition: concurrency, fault injection, a fake model or mock server, a fake clock, or a pre-damaged store. |
| **C** | Source inference or contract asymmetry — read in code, not driven. |
| **D** | Documentation drift, housekeeping, opinion, or an unvalidated-quality caveat. |
| **W** | Withdrawn after re-testing. |
| **–** | Tested and found **not to be a gap** (a reproduced negative). Kept visible so the negatives travel with the positives. |

**Rules I applied while filling this in, so the grades are auditable rather than asserted:**

1. A synthetic *document* (script, PDF, project directory) does not lower the grade — the interface was
   still real. A synthetic *failure* (injected exception, held lock, fake clock, stub client) does: that
   is **B**.
2. If the finding's content came from the demo craft model, the mechanism can be A but the claim about
   feedback quality is capped at B, and the row says so.
3. Anything I never drove at all, only read, is C — no exceptions, no "source-confirmed" euphemism.
4. Where this table disagrees with the aggregate rows in §11 of the critique, **this table wins**; §11
   has been regenerated from it and now says so in its own header.

---

## Entries 1–15 (consolidated table in the register)

| # | Grade | Driven through | Note |
|---|---|---|---|
| 1 | **A** | Real Flask routes: edit, upload, reactivate | Worst item in the register. Edits, edit log and working copy destroyed by an action the UI calls non-destructive. |
| 2 | **B** | Real orchestrator with a stubbed analyzer | Mechanism is source-visible; publication half is proven at A under 65. |
| 3 | **B** | Injected total failure | Contradicts the orchestrator's own comment that a failed run preserves the prior report — that is why it keeps high severity despite B. |
| 4 | **A** | Two-client HTTP test | A finding from draft A landed in the completed report for draft B. |
| 5 | **A** | Real `/analyze/cancel` + real `retry-failed` | The *UI* half (reporting complete on a cancelled response) is C, tracked separately inside the entry. |
| 6 | **B** | Injected edit-log write failure | Divergence between working text and history. |
| 7 | **B** | Two OS processes on one project | Constructed interleaving; no frequency claimed. |
| 8 | **B** | Controlled backup with a skipped file and a synthetic key marker | Two distinct claims in one entry: incompleteness (A-shaped) and credential retention (B-shaped). Graded at the weaker half. |
| 9 | **A**, consequence **C** | Both attached PDFs through the real parser | The *coverage facts* are measured. "This degrades feedback quality" is inference and is graded C inside the entry. |
| 10 | **B** | Controlled `analyze()` plus post-gate enrichment | A fabricated contradictory observation survived with a verified quote. |
| 11 | **B** | Synthetic note through the real filter | Plus a rule-inventory computation that is A-shaped; graded at the weaker half. |
| 12 | **B** | Two controlled findings forced to share category/quote/scene | ID collision and verdict leakage. |
| 13 | **C** | Read the accuracy formula and the serve path | Labelling critique; no run produces a wrong number I can point at. |
| 14 | **C** | Classifier calls on documented phrasings | Deterministic, but the *behaviour* claim ("interrogates a writer who stated intent") needs a real model; overlap with 98. |
| 15 | **D** | — | A caveat about unvalidated quality, not a defect. Belongs in the caveat block, not the count. |

## Entries 16–47

| # | Grade | Driven through | Note |
|---|---|---|---|
| 16 | **A** | Isolated temp directory, real `ProjectManifest` and watch path | Release-blocker framing was mine; the reproduction is real. |
| 17 | **A** | Existing live-region suite, run | Browser suite behaviour; not re-run this session (playwright absent), so the grade rests on the suite's own recorded failure. Flagged. |
| 18 | **B** | Concurrent session saves in isolation | Both concurrency and forced-failure variants used. |
| 19 | **A** | Real `add_to_stash` with 4,004 characters | Saved 4,000, dropped the tail silently. |
| 20 | **B** | Mocked current scene numbers | Staleness is real; the mock is what makes it visible. |
| 21 | **A** | Real exporter, then re-parse | `AJAY/VENU` becomes three AJAY lines. Round-trip use reassigns dialogue. |
| 22 | **A** | Synthetic FDX through the real parser/exporter | Fidelity limits are also documented in the export docstring — known trade-off, still tested. |
| 23 | **A** | Real `quotematch.normalize_text` | `కల`/`కాల` collide; a different word verifies as an exact quote. |
| 24 | **A** | Synthetic Fountain with a Telugu cue | Native-script speaker cue missed. |
| 25 | **B** | Constructed PDF with a page missing | Global completeness check; the artefact had to be manufactured. |
| 26 | **A** | Synthetic screenplay through real character analytics | Silent presence read as absence. |
| 27 | **A** | Controlled document through the real pacing pass | Segments misplaced at page boundaries. |
| 28 | **B** | Fake model returning a short reply | Crash precedes any model call in the real path. |
| 29 | **B** | Fake model returning a direct answer | Filter erases it. |
| 30 | **A** | Synthetic 30k-char scene, `prompt_budget=2048`, payload measured | No model needed; the number is computed. |
| 31 | **B** | Fake model plus the real library provider | Cross-project bleed into a prompt. |
| 32 | **B** | Fake SSE stream | Guards run after streaming begins. |
| 33 | **B** | Real `BaseLlamaClient` against a mock redirector | SSRF-shaped; constructed. |
| 34 | **B** | Isolated save with umask 022 | Credential and archive boundaries; two claims, graded at the weaker. |
| 35 | **A** | Disposable project with a malformed manifest | Sample-open overwrites it. |
| 36 | **B** | Mock server advertising new limits | Global context cached stale. |
| 37 | **B** | Held-open file during watch | Timing-dependent. |
| 38 | **B** | Telugu filename plus a fake orchestrator | Project the desk cannot open. |
| 39 | **A** | Real CLI, `watch --once` | Prints FAILED, exits 0. |
| 40 | **B** | Mock server advertising one model | Silent fallback to a different model. |
| 41 | **B** | Mock server implementing `/v1/models` | `/v1` duplication in URL construction. |
| 42 | **B** | Injected manifest write error | Partial settings application. |
| 43 | **A** | Synthetic scene through the real subtext pass | Direct emotion declared missing subtext. |
| 44 | **A** | Two-scene synthetic script, real continuity pass | Day/night reported as a dropped transition. |
| 45 | **A** | Two synthetic scripts, equal counts, different wording | Numeric proxy stated as diagnosis. |
| 46 | **B** | Real subtext pass, **demo model** | Mechanism A; the "two findings" are demo content. |
| 47 | **A** | Rendered a synthetic `AnalysisResult` | "No significant findings" printed for a failed category. |

## Entries 48–76

| # | Grade | Driven through | Note |
|---|---|---|---|
| 48 | **C** | Source read of prompt assembly | Untrusted text in instruction context; explicitly needs a real model to weigh. |
| 49 | **B** | Forced identical UUID prefixes | Ideas and chats overwritten. |
| 50 | **A** | Disposable directory, real CLI create | Orphaned source data replaced. |
| 51 | **A** | Real Flask routes | Undo reports success while failing. |
| 52 | **A** | Temp-project API test | Structure and exports left inconsistent. |
| 53 | **B** | Synthetic screenplay, **demo model** | The promoted "fact" is demo output; mechanism is the promotion rule. |
| 54 | **A** | Controlled two-scene script, real pass | Setup recurrence read as payoff. |
| 55 | **B** | Injected `IdeaStore` failure | Graduation claims a transfer that failed. |
| 56 | **A** | Separate process, default model unreachable | Real startup paths disagree with the documented opt-out. |
| 57 | **B** | Synthetic saved token, remote enabled | Credentials follow a changed endpoint without a new trust decision. |
| 58 | **B** | Isolated Flask test with injected disk error | Partial application; local-only switch leaves a remote destination. |
| 59 | **A** | Temporary project with an analysis-complete manifest | Banner follows current demo mode, not report origin. |
| 60 | **B** | Fake clock | Nested busy retries past the logical deadline. |
| 61 | **B** | Two synchronized concurrent uploads | Shared temp file and swap target. |
| 62 | **A** | Real route with two synthetic projects | **Most serious item in the register.** Read and overwrite a sibling project; reached outside `PROJECTS_DIR` on a later write. |
| 63 | **A** | Draft activation on a real project | Derived artefacts stay bound to the outgoing draft. |
| 64 | **A** | Real upload of an invalid FDX, then reactivation | Writer stranded on a broken active draft. |
| 65 | **A** | Stubbed long run plus a real draft switch | Report published for the draft the run started on. |
| 66 | **A** | Real `/analyze/cancel` during a real `retry-failed` | 409; the analysis lock is not taken by upload/activation. |
| 67 | **W** | Measured | ~7 ms of subprocess work on a seconds-long operation. Withdrawn. |
| 68 | **B** | Held `lock_for`, 0.05 s deadline, same-process waiter | In-process contention only. |
| 69 | **B** | Completed report plus a busy store | Transient warning replaces a good result. |
| 70 | **A** | Corrupted `idea.json`, real routes | Shown, unrepairable, saves fail as request errors. |
| 71 | **B** | Synthetic library archive | Idea store labelled a project; relationship memory omitted. |
| 72 | **A** | Both backup routes with a forced `OSError` | Archive silently incomplete, 200 returned. `except OSError: continue`. |
| 73 | **A** | Real export with a leftover `source.pdf` beside the active one | No provenance disclosure. |
| 74 | **B** | Two loaded manifests writing one stage | Merged with 75; whole-stage overwrite from a long-held object. |
| 75 | **B** | Concurrent nested-stage saves | Last-writer-wins at field level. Merged into 74 as one finding. |
| 76 | **D** | Listing a project directory | Lock sidecars visible; excluded inconsistently. Housekeeping. |

## Entries 77–108

| # | Grade | Driven through | Note |
|---|---|---|---|
| 77 | **A** | Two-scene synthetic script, real continuity | Day/night cut under an action heading flagged as dropped. |
| 78 | **B** | Controlled speaker-name pairs | 2-edit-distance guess produces confident nonsense. |
| 79 | **A** | Real export then revision | No provenance line; reconstructed indistinguishable from original. |
| 80 | **A** | Damaged project on the real shelf routes | "Unreadable", then refuses to open, no recovery path. |
| 81 | **B** | Three-scene excerpt | Act bucketing collapses for short scripts. Display behaviour, overlaps 115. |
| 82 | **A** | Both shelf responses compared | Project shelf says `unreadable`, idea shelf says something else for the same damage. |
| 83 | **A** | Real `--help` versus the documented surface | Top-level commands disagree. |
| 84 | **A** | Live Flask `url_map` compared mechanically with the doc | Stale in both directions. |
| 85 | **A** | Doc header claims checked against behaviour | Port and process model wrong. |
| 86 | **A** | Package listing | `graph.json`, `graph_output…` ship inside importable packages. |
| 87 | **A** (mechanism) | Demo run end to end | A detail absent from the script reached the rendered report. The *content* came from the demo stand-in, so no claim about real-model fabrication. |
| 88 | **C** | Renderer source | Demo output disclosed by name, not by nature. |
| 89 | **C** | Renderer source | Deterministic and model findings indistinguishable. |
| 90 | **B** | Refresh after a complete analysis, timed | Second full pass; demo server outlives the run. |
| 91 | **W** | Real POST/GET | GET returns `branches`, POST returns `messages` — API asymmetry, not a discarded reply. |
| 92 | **D** | Demo transcripts | Canned first-meeting lines. A statement about the stand-in, not the product. |
| 93 | **A** | Demo over both attached screenplays, timed | Fast, zero checkable evidence. |
| 94 | **B** | Route reads plus the 113 probe | "What the writer sees" is assembled per request from several stores. |
| 95 | **D** | Route reachability | Design lab is a deliberate shipping decision. |
| 96 | **D** | Filename serving | Dead labs; housekeeping. |
| 97 | **D** | — | A design proposal for a recovery room, not a reproduced defect. |
| 98 | **A** | Real intent classifiers, writer's own phrasings | A statement of intent classified as a bare idea. |
| 99 | **C** | Prompt text read | The safety contract lives only in prompt text. |
| 100 | **C** | `craft_history` source | Only still-applied edits are citable. |
| 101 | **B** | Substring rules traced and exercised | Persona-visible behaviour decided by `has_embedded…`-style rules. |
| 102 | **W** | Probe re-keyed | Mis-keyed pass name in my own probe; two categories do get grounding. Withdrawn. |
| 103 | **W** | Measured | Genre fragment 7,760–10,389 chars; pacing pass deterministic by design. Withdrawn. |
| 104 | **W** | Re-traced | The 39,923-char fragment came from a pass name the pipeline does not call. Withdrawn. |
| 105 | **C** | Rule-id plumbing read | Nothing verifies a `rule_id` came from the fragment supplied to that pass. |
| 106 | **C** | Analyzer entry signature, prompt vocabulary | The premise card is saved, carried, never read. **The product gap.** |
| 107 | **D** | — | Design proposal: scene-level intent has nowhere to live. |
| 108 | **C** | Both collaborator prompt builders | Intent absent from both personas' inputs. |

## Entries 125–128 (eighth to tenth passes — last modules, packaging, frontend)

| # | Grade | Driven through | Note |
|---|---|---|---|
| 128 | **D** | Static read of every `innerHTML` sink in `app.js`/`core.js` | Escaping is correct everywhere today; the invariant is enforced by convention only — no test, lint rule or escaping-by-construction wrapper. Regression guard for a future commit, not a live defect. |

## Entries 125–127 (eighth and ninth passes — last modules, and packaging)

| # | Grade | Driven through | Note |
|---|---|---|---|
| 127 | **D** | `python -m build --wheel`, then install into a clean `--target` and boot it | Wheel is correct: 180 files, 4.04 MB, 263 rules, SPA and fonts present, no tests or scratch files, `/` → 200. The only weakness is that CI's packaging tests inspect the source tree, not the wheel, so they could pass while an installed copy broke. |

## Entries 125–126 (eighth pass — the last modules at "inventory only")

| # | Grade | Driven through | Note |
|---|---|---|---|
| 125 | **A** | Real `/api/stt/languages` + `/api/stt`, remote whisper URL | Capability endpoint advertises `engine: whisper-server` (200) for a configuration the guard refuses (503). The guard itself is correct; the label is not. Low severity, hand-edited config only. |
| 126 | **C** | Real `/api/stt`, 3 MB and empty blobs | No magic-byte or duration check, 256 MB ceiling inherited from uploads. **Downgraded B→C in §22**: the external-server half is the user's own machine, and the inherited ceiling is defensible. Informational; I would not schedule it. |

## Entries 109–124 (collected in the critique file, graded there and here)

| # | Grade | Driven through | Note |
|---|---|---|---|
| 109 | **W** | Root `ruff check .` | Passes. Withdrawn before it was ever filed as a defect. |
| 110 | **B** | Real CLI, missing source file | Traceback and exit 1 instead of one actionable line. |
| 111 | **A** | Real CLI create + `status` | Round-trip works; positional asymmetry (`--project` versus positional) is the only defect. |
| 112 | **D** | `du` over the repo | `docs/` 12 MB, `impl-shots/` 7.2 MB. Housekeeping. |
| 113 | **A** | `/fixqueue` and `/findings/summary` on a two-finding project | `total_count 2`, `open_count 2` while the desk hides the ungrounded row. |
| 114 | **–** | Same probe | **Negative:** summary, queue and `/report` agree on the ordinary serve path. |
| 115 | **B** | One-scene script | `scene_count: 0` in act buckets. Cosmetic display. |
| 116 | **–** | Headers read | `X-Frame-Options` absent but CSP `frame-ancestors 'self'` covers it. Not a defect; do not "fix" it. |
| 117 | **–** | Demo run | A page that fails to parse shows a bare numeric badge — already 47/87 in spirit. Not filed twice. |
| 118 | **A** | `/api/config` with synthetic key and token | No key, no token — **negative on secrets**. `allow_remote`/`connection_mode` are plain booleans with no machine-readable consent scope. Informational. |
| 119 | **A** | Corrupted rules dir through the real pipeline and webapp | Analyze fails `OrchestratorError`, webapp 502 with parser text, then `/report` 400 "Analysis hasn't completed" while the prior report sits intact. Empty rules dir accepted silently. |
| 120 | **–** | `ast.parse(feature_version=(3,10))` over every module | Python floor honest. One UTF-8 BOM in `tests/test_h7_chat_fix.py`; 5 tests pass. Hygiene note. |
| 121 | **D** | `npm ci && npm test` | 134/134. Docstring says 127; `node --test tests/js/` fails on Node 22. Documentation and invocation trap only. |
| 122 | **C** | — | The four areas I cannot test here, named rather than faked: real model, audience reception, screen reader, non-Linux. |
| 123 | **A** | Corrupted rules dir, hit `/api/health` and `/api/rules/*` | Health 200 `status: ok`; rules lookup 400 with raw `JSONDecodeError` text, where a *missing* install gets a designed 503. |
| 124 | **D** | — | "Verified against both PDFs" means two features, one writer, one language mix. A bound on the evidence, not a gap. |

---

## Counts, computed from the rows above rather than typed

Counted by parsing this file, not from memory. **128 numbered entries**, 6 withdrawn, 4 proven negatives,
**118 live findings**.

| Grade | Count | Share of the 118 live |
|---|---|---|
| **A** — reproduced through a real interface | 51 | 43% |
| **B** — real mechanism, constructed condition | 43 | 36% |
| **C** — source inference only | 12 | 10% |
| **D** — docs, housekeeping, opinion | 12 | 10% |
| **W** — withdrawn | 6 | — |
| **–** — tested, not a gap | 4 | — |

Five things worth stating plainly, including the two where I had it wrong:

1. **My own earlier summary was wrong, and in the direction that flattered the critique.** I said "roughly
   half the register is conditional or inferential" (that part holds: 47%) but I also said "about forty are
   inference, documentation, or opinion" and "22 cosmetic or opinion". The honest figure is **21 entries**
   (12 C + 11 D). I had been double-counting constructed-but-real entries as inferential. The register is
   *more* evidenced than my self-critique claimed — which means my self-criticism was itself unsupported
   in one of its central numbers.
2. **The severe list does not move.** 1, 3, 4, 18, 21, 23, 61–65, 87, 106, 113, 119. Grades answer "how
   sure am I?", never "how much does it matter?", and severity still drives the fix order in §6.
3. **Grade A ≠ ship blocker.** 30, 39, 45, 86, 93, 111 and 123 are all A and minor. Conversely 3, 106 and
   13 are the entries whose *severity* outruns their grade.
4. **Six withdrawals, not five.** 67, 91, 102, 103, 104, 109. Earlier files listed five because 102 was
   folded into 103; it is a separate mis-keyed probe and is listed separately here.
5. **Four proven negatives stay in the table** (114, 116, 117, 120) plus 118's secrets half, because a
   register that carries only failures gives a false picture of the codebase. The codebase on re-reading
   is more careful than the register's length suggests, and this table is where that becomes visible.

## What this table still cannot do

- It does not make C entries into evidence. Twelve findings remain read-not-driven, and no amount of
  tabulation changes that. They are the least likely to survive contact with a real user.
- It does not touch the four permanently unclosed areas (122). Real-model behaviour, audience reception
  of Darshi and Pain 3, screen-reader output and non-Linux filesystem semantics need the writer's own
  environment.
- The 17 entries graded **A** on behaviour observed in a browser suite that is not installed here (17,
  and the browser half of 5) rest on recorded suite results, not on a run I performed this session. They
  are marked as such rather than upgraded silently.
