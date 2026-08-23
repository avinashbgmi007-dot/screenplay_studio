# PROJECT_MEMORY.md — deep-read memory with file digests

**Purpose:** a prior session deep-read every source file in this repo and recorded the results here, keyed to an **md5 digest per file**. Before reading any source file again:

1. Run `md5sum <file>` (or `find … | xargs md5sum` for a batch).
2. If the digest matches this table → **do not re-read the file**; trust the summary below.
3. If it differs → the file changed; read it fresh, then update its digest + summary here.
4. Any session that edits a file must refresh that file's entry (digest + notes) in the same change.

Snapshot taken: 2026-08-22 · HEAD `0ef433f` ("Let go of the Pain_FD_4_scenes project") · full suite green at 566 tests.

---

## Digests

### screenplay_parser
| File | md5 |
|---|---|
| models.py | d1066336475f3a36ad3f80f1357f72e4 |
| text_parser.py | 669d10767e621fa1be97eaaf2374bec4 |
| heuristics.py | 0fdc4487295ed7c18633665799e69ee4 |
| knowledge_graph.py | 629af9937232ecd595616d7ce7d08b9c |
| pdf_parser.py | 229d6fc5e444627cc82b9a12e75ecb15 |
| fdx_parser.py | 58a144f68607a5163e5f36f55bac46c1 |
| structure.py | f3477a50bbf7c203ac19eb922f2f2eb7 |
| stats.py | ac666330d207d93a6e19fe8f18bb5c13 |
| export.py | 83ec58d4ebdad43d5a29e34462d7d2ee |
| __init__.py | 9dcc900e4a804f0491d8bb65793852e4 |
| cli.py | fb5038329185ffc8d3dafddc20334049 |

### knowledge_base
| File | md5 |
|---|---|
| knowledge_base.py | e5a26c6ae1a25a5bc13e230dea26efd2 |

### screenplay_analyzer
| File | md5 |
|---|---|
| pipeline.py | abe1b9f7b97052a3b967de01b4935f0b |
| llm_client.py | 4a2d4a80c1f589900d931223cbbcd67f |
| grammar.py | d0ac99e3aa0ccc9f6b26f51b0acefe2e |
| verifier.py | 7be56185938382f81230f5a98f087337 |
| prompts.py | 21a705302f837389f80ace8969bf3f64 |
| principles_engine.py | 14752b544bc455ae26e623a6a03bf07b |
| setup_payoff.py | f3ba76c004d3f44b74b2e64f2e646e56 |
| continuity.py | 4e14810c9aa57142d62835836cf59d71 |
| voice.py | 549033bdbd12ce2a28b3c0433519007e |
| dials.py | 2ac5c2d00af69eaa54271f541f7e3bd3 |
| pacing.py | 90ef9840cb2840eb3e135f1ce82049ff |
| formatting_check.py | 8e908ed1714bd4f380456da98234abd8 |
| genre.py | ec649f29fba399ac88d4a5990c635906 |
| feedback_filter.py | 8cb93b32ff82d769f65bfb6a0afc0214 |
| rules_context.py | 8a8b72e9d4e5ede357e7ca17059aa486 |
| report.py | 9bb73cb7cf1990b73ac0cc18d4a663af |
| cli.py | fe867babadd9e95283aa9fc4a63f6078 |

### screenplay_cowriter
| File | md5 |
|---|---|
| engine.py | 6beea1c80b7eb474ce314c8bd9a22c3d |
| context.py | 20151b9df599a5f698664e2ead1f7cb3 |
| language_mirror.py | c4c6a3d365c3b2125965da25dd432567 |
| personas.py | c54ca941ef6a7289fb0203852df669fe |
| models.py | 9d889ac1bc6f5deabb0e7ea5648c0083 |
| store.py | 49ab8d5422ef17da60ee228e3335e1f5 |
| memory.py | 3455eae73ba1d37a0f3faa1e25d74f64 |
| llm_client.py | d86900f9313672da7b4aae4da3a6900c |
| discovery.py | 6fd650e44f1764d95ec5c62973b044fd |
| language_meta.py | a71ceece6a7e3fa2a58e73319c18a7be |
| peer.py | 7e0a80b4a3ded773a52b4d09377d79a9 |
| writer_library.py | d116fb4ea24cb1d16f620836a280c54f |
| server.py | abd51d19148bad742d4aac37ea515fad |
| cli.py | cccf60ab12adb677ac5acbabcc41975d |

### screenplay_studio
| File | md5 |
|---|---|
| orchestrator.py | 821515e6f49cdf8e7675f0b547aaf6f0 |
| manifest.py | 763ae4a08717f8af097e7d81ae823a24 |
| webapp_server.py | e18b17f2a8fbedcd4d952b2abf4e9982 |
| revision.py | 0486c34eee265ee70f6f4874003bf9b7 |
| diff.py | e4e32d7ebfbf77fbd00d3091b183abf7 |
| ideas.py | 817e9dc88ca04dfbf8ac814bb92b7b82 |
| beatboard.py | b563a235451da40a06e270cd0fabf845 |
| notes.py | eb71ff2e5c12e7306968f43499553b85 |
| metrics.py | 166decbd506ce601f9dd07106b4b2689 |
| stash_store.py | f16d6fc59639d8197e789b118635d147 |
| character_track.py | 37146373c44310c4e58d849e34556c61 |
| watch.py | 0654021683e35a1b542e39002ec8b2ed |
| sample.py | e84fac8fac63f9ccc3ba9eb1a4b3d81d |
| cli.py | bb2a54fe689ff7ff9430b95bcefd935e |
| webapp/index.html | d367fee53458ebdca4a09b9322dc606a |
| webapp/app.js | ed14aa4fd354ace8eaf48d53db46cbfe *(deep-read: structure + all edited regions; ~5.2k lines)* |
| webapp/style.css | c92d37195ebd338c43632a6b289c207b *(tail blocks = feature-batch + dashboard styles)* |
| demo_model.py | f6ab3136629923bddff895801a86a119 |
| webapp_demo.py | 0dea91a7354e5bf3921490974196e4ac |
| webapp/preview.html | 06e5999e9a8d38be20dc8838f20bcd4e *(legacy static mockup, not deep-read)* |

### tests
| File | md5 |
|---|---|
| conftest.py | d1a5848c9d22d11d8ef1089da4c1b78b |
| mock_unified_server.py | a31d2681dfa8c69ee692749b290a93a9 |

(All other `tests/test_*.py` files follow the documented layout below; digests available on demand — regenerate the table after any test edit.)

---

## Deep summaries (trust these instead of re-reading)

### screenplay_parser (Piece 1 — deterministic, no model)
- **models.py** — `Element(type,text,character,line_start)`, `Scene` (heading_raw/int_ext/location/time_of_day/page_start/end/elements/characters_present), `ParseWarning`, `ScriptDocument` (+`all_characters`, `scene_count`, `estimated_page_count`; `save/load/from_dict`). All formats converge here; downstream never knows the source format.
- **text_parser.py** — shared blank-line state machine `_parse_lines()` used by txt/fountain/md AND pdf. Fountain forced syntax (`.` scene, `@` cue, `>` transition, `#`/`=` skipped, `~` lyric). Multi-line parenthetical tracking; PDF layout bands close open dialogue when column position says action resumed. `THE END` always a transition. Confidence: medium (text), low (pdf).
- **heuristics.py** — regexes for headings (incl. Devanagari इंट/एक्सट and Tamil உள்/வெளி), transitions, time markers ("TWO MONTHS LATER"), shots, parentheticals. Character-cue rule: short, uppercase-after-extension-stripped, Unicode-aware (accents pass), underscore = space (GOON_ONE→GOON ONE), curly apostrophe accepted. Caseless scripts use next-two-lines lookahead. `parse_scene_heading()` splits location/time on last " - ".
- **knowledge_graph.py** — CANDIDATE GENERATOR only. Characters index (+trait mentions from intro parentheticals within 90-char window), prop candidates (ALLCAPS/article+noun phrases recurring ≥2 scenes), timeline w/ TIME_SKIP_RE markers, promise candidates (English PROMISE_RE + TELUGU_PROMISE_RE: cheptha/chupistha/nammuko/oka roju/tappakunda…), co-occurrence "A|B"→scenes.
- **pdf_parser.py** — pdfplumber paragraph-break detection (gap > 1.35× median line height) reconstructs lines + page_of_line + layout bands (left/dialogue/center/right at x0 ratios .22/.34/.60). Fixes glyph doubling (interleaved-char collapse), U+FFFD→apostrophe, page-number footers. Unrecoverable text layer ((cid:N)/glyph names >50%) → OCR fallback: tesseract then easyocr (env `SCRIPT_DOCTOR_OCR`, `SCRIPT_DOCTOR_OCR_LANG` default eng+tel+hin); no engine → loud actionable error, empty parse never returned.
- **fdx_parser.py** — XML `<Paragraph Type>` map, title/author from TitlePage ("by <name>"), confidence high.
- **structure.py** — page estimation (54 lines/page, 10 wpl action / 14 wpl dialogue), acts at 25%/75% of pages, pacing_curve (per-5-page dialogue/action words), character_arc (presence %, quiet gaps ≥2 scenes, appears_throughout ≥60%).
- **stats.py** — `full_stats_report()`: character_stats, dialogue_action_ratio, location_usage, scene_length_stats, int/ext+time breakdown, acts, pacing, arcs, per-scene estimates (~160 words/screen-minute).
- **export.py** — fountain/fdx/txt round-trip; dialogue blocks stay glued (blank closes block); fdx exact type mapping.
- **__init__.py** — extension dispatch `.fdx/.pdf/.txt/.fountain/.md` → `parse_screenplay()`.

### knowledge_base
- **knowledge_base.py** — loads `rules/*.json` into `Rule` dataclasses (id/taxonomy_level/category/source/definition/detection_signal/counter_considerations/severity_default/confidence_tier/requires/related). `to_prompt_fragment()` renders definition + look-for + do-NOT-flag + tier framing (high=near-certain / medium=judgment / low=discussion prompt). Lookup: get/all/for_taxonomy_level/for_category/requiring/by_confidence_tier/render_for_prompt/stats. Duplicate ids raise. 34 rules across story_macro, structure_pacing, plot_thread, character, relationship, scene, dialogue, continuity.

### screenplay_analyzer (Piece 2)
- **pipeline.py** — `analyze(doc, client, run_categories, progress_cb, report_language)` order: (1) deterministic formatting+stats; (1b) voice/subtext/idiolect; (1c) continuity; (1d) pacing (drag_findings→structure); (2) scene summaries (fast=True tier, chunk_size 6); (3) dialogue pass (chunk 3, full text); (4) script-level theme/character/structure/scene_function (overview-based, evidence_quote=null contract); (4b) principles engine (KG-driven); (4c) char reads; (4d) setup/payoff ledger LAST, dangling folded into plot_thread findings deduped vs principles; (4e) character dials; (5) verification; (6) coverage → logline_test (needs coverage.logline) → genre (needs coverage.genre, re-verifies combined set); step 7 marks overview-gated categories failed when prerequisites broke; (8) feedback_filter. Budget constants: TOKEN_BUDGET=1400 prompt, COMPLETION_RESERVE=1400, CHARS_PER_TOKEN=3, MAX_SCENE_CHARS=2200, MAX_OVERVIEW_CHARS=6000. `_chunk_by_budget` + recursive `_with_chunk_backoff` (halve on LlamaServerError). `_extract_items` tolerates bare-array model output. `_normalize_findings` fills null severity/category. `ALL_CATEGORIES` 12-tuple incl. principles/setup_payoff/char_reads/character_dials/genre/logline_test. `AnalysisResult.category_outcomes` drives partial-resume.
- **llm_client.py** — `chat_json(system,user,grammar,max_tokens,temp,retries,fast)`: GBNF `grammar` field + response_format json_object; `enable_thinking:false` under grammar so reasoning models emit constrained JSON into `content`; busy-retry loop (400-with-busy-body/429/503, max 6, linear backoff); two-tier routing via `fast_model` + `resolve_model_id` honoring `fallback_to_loaded` (never mutates self.model). `_extract_json`: direct parse → code fence → balanced-bracket scan. Empty-content diagnosis explains ctx-window exhaustion (finish_reason=length/completion_tokens=0).
- **grammar.py** — hand-written GBNF compatible with BOTH classic and PEG-era parsers (single-line rules; no `\/`,`\b`,`\f`,`\uXXXX`). Grammars: findings (category enum: theme/character/structure/dialogue/scene_function/plot_thread/genre/continuity; severity low/med/high; issue+why_it_matters split), scene_summary, principle_judgment (significant/paid_off/reasoning — NO suggested_resolution by design), replacements (old/new exact-line), logline_test (strong/workable/muddled), character_reads, setup_payoff ledger (paid/dangling/abandoned/red_herring), character_dials (5 traits 1–10), coverage (recommendation pass/consider/recommend).
- **verifier.py** — threshold 0.72; normalize→exact substring→sliding-window fuzzy (window ≈ quote length, step half)→whole-script rescue that CORRECTS wrong-scene citations with a note. Statuses verified/not_found/no_quote/scene_not_found; flag-don't-drop policy.
- **prompts.py** — two citation contracts: full-text passes quote verbatim (<15 words, CITATION_INSTRUCTION); summary-based passes cite scene numbers only, evidence_quote=null (CITATION_INSTRUCTION_SUMMARY — prevents fabrication). CONFIDENCE_TIER_INSTRUCTION. REPORT_LANGUAGES suffixes: eng/tenglish/hindi/telugu/tamil (quotes exempt). LANGUAGE_META_INSTRUCTION (never comment on the script's language). Structure prompt runs 5 explicit checkpoints (act-one commit/midpoint/act-two escalation/darkest hour/climax). Scene-function uses WANT/OBSTACLE/CHANGE. Dials: Proactive-Passive/Warm-Cold/Articulate-Terse/Emotional-Stoic/Grounded-Dreamy. Ledger prompt: seeds are leads-not-verdicts, four statuses defined.
- **principles_engine.py** — stage 2 of candidate→judge; one call per candidate, capped 15 (props by mention count first, promises fill remainder). Finding only if significant AND NOT paid_off. Diagnosis-only (no fix suggestions — Piece 3's job).
- **setup_payoff.py** — whole-overview single call, ≤12 entries sorted dangling-first; unknown status→dangling (flag don't drop). `dangling_findings()` dedupes vs existing plot_thread by 40-char lowercase prefix containment.
- **continuity.py** — unmarked opposite time flips (NIGHT↔DAY/MORNING; CONTINUOUS clears) + name variants (Levenshtein≤2 or prefix≥4 chars with ≤3 extra, never share a scene, both speak). Evidence quotes are verbatim headings/lines so verification passes.
- **voice.py** — voice-bleed: fingerprints (top-40 word freq cosine ×0.7 + style distance ×0.3) over ≥3-line characters, threshold 0.72, shared-scene requirement, cap 6 pairs. Subtext: on-the-nose regex ("I'm so angry", "I love you", "I'm in love"). Idiolect: mean-line-length shift ≥45% between halves (≥6 lines total, ≥3/half).
- **dials.py** — one call whole cast (≤8 chars), clamps scores 1–10, trims note 200.
- **pacing.py** — pace_score = 100×(0.6·density_norm + 0.4·inverted action_share_norm); drag ≥68 & ≥20 words, cap 4; drag_findings category structure/rule pacing_drag.
- **formatting_check.py** — deterministic heading checks (missing INT/EXT, missing time-of-day; more rules further down the file — read before editing).
- **genre.py** — 10 genre convention sets as expectations-to-test; substring then word-overlap match, default drama.
- **feedback_filter.py** — drops dialect-ID/subtitle meta-commentary from issue+why_it_matters (quote exempt). Conservative sentence-level sibling lives in cowriter/language_meta.py — keep pattern sets in sync.
- **rules_context.py** — category→taxonomy-level map (theme→story_macro, character→character+relationship, structure→structure_pacing, scene_function→scene, dialogue→dialogue); `prompt_fragment_for_rule("chekhovs_gun")` rides the dialogue pass.
- **report.py** — render_markdown (verification badges ⚠️, CATEGORY_TITLES, Setup/Payoff section w/ status emoji, pacing drags, dials, acts/pacing/arcs tables, analytics, verification summary prose) + to_findings_json (carries setup_payoff, character_dials, pacing keys — regression-tested) + save_report(md,json).

### screenplay_cowriter (Piece 3)
- **engine.py** — `send_message(session, user_text, quote=None)`: turn classify (idea/question/directive via peer.py) → probe phase if idea without embedded reasoning (reflect+one question, awaiting_probe flag, cleared by any reply; capture was_pending BEFORE clearing to avoid re-probe loop) else full turn; memory.observe each turn + cold_start_line captured pre-observe; relationship card scope-filtered; scene refs = explicit "scene N" + character-name mentions (4-tier matching) + quote's scene; quote rides BOTH as system context and inside the user turn; history window 16; reply hygiene pipeline clean_reply = strip_language_meta∘strip_repeated_blocks∘strip_repetition_lines∘strip_json_wrap; repeat_penalty 1.3; max_tokens 600; `_ground_reply` appends an honest flag for invented scene numbers; `_persona_register` post-guard (script_consultant → '!'→'.', both turn paths); engine params mood_text/doctor_case_text ride into every system prompt; ensure_forward_momentum (short replies get a nudge) + cap_suggestions (max 1 bullet) on full turns; saves via store itself. `send_message(..., on_token=)` streams RAW pieces via `self._generate()` (falls back to blocking chat for clients without chat_stream); hygiene pipeline still runs on the full text — streaming never changes what is stored.
- **context.py** — ScriptContext (script_map standing block: headings + top-24 character presence), ReportContext.compact_summary (coverage + ALL findings w/ [UNVERIFIED QUOTE] flags + formatting notes), build_system_prompt (persona+mode+examples+grounding/language/plain-text instructions; premise branch swaps in THE PAGE ≤6000 tail-kept; appends mood_text → doctor_case_text ONLY when persona==script_consultant → relationship card/cold start/writer library; new params default None = byte-identical), SCENE_REF_RE, resolve_referenced_scenes (cap 4), extract_character_refs tiers: whole-name → token(≥4) → prefix either direction → fuzzy best-match ≥0.58.
- **personas.py** — HUMAN_VOICE_RULES (anti-AI-pattern list) appended to human-facing personas. PERSONAS (v2 humanized): writing_partner (**Sameer** — bio: sold-one-scene ex-writer; stance: script's defense attorney; quirk budget: ONE dry aside; friction + never-blur lines vs the doctor; honest-memory rule), script_consultant (**Dr. Sushruta** — bio: 20 yrs/4000 scripts/liked 9; stance: guilty until proven innocent; verdict-first; NO exclamation marks; diagnosis-vs-prescribe boundary; friction vs Sameer), premise_doctor (+examples), producer, dev_exec, teacher, audience, genre_specialist. Both bibles keep all v1 pinned anchors. MODES: evidence_discussion, concept_validation, brainstorm, character_interview, peer (7 non-negotiable peer rules). Defaults writing_partner/peer.
- **models.py** — Session/Branch/Message; fork deep-copies messages + records parent/fork point; branch carries active_persona/mode + awaiting_probe; Message carries mode, scene_refs, quote dict.
- **store.py** — one JSON per session under sessions_dir; list() tolerant of corrupt files. save() is per-path LOCKED (module `_LOCKS` registry) AND atomic (`.tmp` + `os.replace`) — concurrent turns/readers never clobber or tear a session file.
- **memory.py** (writer relationship memory, v2 profile) — 5 dimensions (detail_level short/deep, directness gentle/direct, probe_appetite, pushback_appetite, support_style generate/discuss); per-turn regex signals (TONE_RULES, PUSHBACK_ARGUE/AGREE, PROBE_REASON, probe engagement by reply shape) → Laplace confidence `(pos+2)/(pos+neg+4)`; gate BEHAVIOR_GATE 0.6 needs MIN_EVIDENCE 3 and flips only when opposite pole leads; contradictions auto-suppress template observations but the flipped NEW belief keeps steering; suppressed belief drops out of gate until re-learned (reversible forgetting); topic_gravity counters; LLM refresh every 10 turns merges higher-confidence updates, forbids script facts, auto-scopes observations naming current-script entities; scopes: global | project:X | idea:Y — card_text(scope=) injects global + current scope only. Writer is editor: suppress() reversible, card visible.
- **llm_client.py** — free-text chat client (no grammars); WatchdogTimeoutError distinct subclass on requests timeout (webapp maps to 408 still_working); same busy-retry pattern; optional presence/frequency penalties (None = untouched sampling). `chat_stream(messages, on_token, ...)` = SSE streaming variant (stream:true, parses `data:` frames, [DONE]-terminated, busy 429/503 fails fast, returns FULL raw text).
- **discovery.py** — explicit model > report's model_used if currently loaded > whatever's loaded.
- **language_meta.py** — strip_language_meta (sentence-level surgical removal), strip_repetition_lines (single-char separator lines, leaked end-turn tags, HTML-ish tags glued anywhere), strip_repeated_blocks (paragraph-opening fingerprint dedup incl. question-echo-before-repeated-answer), strip_json_wrap (fenced or pure-JSON unwrap via content/answer/reply/response/text/message/output keys).
- **peer.py** — pure guardrails: classify_turn, should_probe (idea without reasoning), PROBE_SYSTEM_PROMPT, ensure_forward_momentum (STRANDED_THRESHOLD 120), cap_suggestions (bullets beyond 1 cut + "one at a time" note).
- **writer_library.py** — deterministic digest of parsed projects (skip `ideas` dir + excluded current): title/format/scenes/pages/top-8 chars/top-4 theme findings; library_digest_text wraps in PAST WORK + grounding guard.
- **server.py / cli.py** — standalone Flask API (port 8300) and REPL CLI (/fork /switch /persona /mode /history etc.). Both construct CoWriterEngine directly; webapp does NOT use them (it lazy-imports cowriter modules itself).

### screenplay_studio (orchestrator + webapp)
- **manifest.py** — ProjectManifest(project.json): stages parse/analyze/chat StageStatus(pending/running/complete/failed/skipped) w/ output_paths+error; paths derived (parsed.json, parsed.kg.json, report.md, report.findings.json, sessions/, progress.json, working.json, edits.json…); drafts[] + active_draft; report_language; fast_model; timeout.
- **orchestrator.py** — run_parse (short-circuit on complete); run_analyze: retry_failed path re-runs only failed categories and MERGES via `_merge_analysis` (keep prev findings for non-rerun categories, drop always-regenerated voice/subtext, keep prev coverage/reads/etc., recompute verification; genre/logline failures pull coverage into the rerun set; empty rerun outcome raises instead of corrupting; failed retry restores prev output_paths); total failure (errors && nothing produced) → failed stage raise; partial success → complete w/ visible errors + failed_categories record. progress_cb writes progress.json heartbeat w/ ts. start_chat recovers when manifest's session was deleted.
- **demo_model.py** — built-in DEMO craft model (llama-server look-alike, Flask `demo_app`): /v1/models → `demo-craft-model`; /v1/chat/completions non-streaming AND SSE-streaming (word-chunks). Analyzer branches mirror tests/mock_unified_server.py category-for-category (full real report); conversational turns are PERSONA-DISTINCT: `_sameer_reply` (warm, constructive formula, mood facts, dry aside at the doctor's margins) vs `_sushruta_reply` (verdict-first, case-file citations, no '!'); persona detected via the card OPENING LINE ('you are dr. sushruta') — never bare-name mentions (Sameer's bible names the doctor and would misroute). `_mood_facts`/`_case_facts` parse the injected blocks so demo replies ground on real injected facts. `start_demo_server()` prefers STABLE port 8099, falls back to ephemeral (catches OSError AND werkzeug's SystemExit on busy port); idempotent per process. NOT shared with tests/mock_unified_server.py (that file's shapes are pinned by tests). `webapp_demo.py` = entrypoint binding 0.0.0.0:$PORT with demo forced. Idea-room turns: `_idea_probe_reply` extracts page content from the PREMISE block (terminates at the next top-level section — GROUNDING/language rules — never leaks boilerplate; focus candidates rejected if they match language_meta patterns or grounding words). PROBE posture: never recites the page/title, asks one sharp question about a concrete element (labeled details > quoted > capitalized > longest line). Conversation continuity: longest user-word n-gram verbatim on the page triggers an engagement reply about THAT element (gate: multi-word phrase or word >= 7 chars, stopword-filtered) instead of re-probing generically. NO pipeline tags in any conversational reply ('(demo craft model...)' removed — robot voice).
- **webapp_server.py** (port 8500) — DEMO MODE: `_use_demo_model()` + `_DEMO_MODEL_ACTIVE` flag + `_engine_base_url(session)` (in demo mode chat sessions IGNORE their pinned server_url and follow live CONFIG — demo port changes across restarts); startup gating at import: SCREENPLAY_STUDIO_DEMO_MODEL=1 forces demo; otherwise auto-fallback to demo when the configured server is unreachable at startup (skipped under pytest; a reachable llama-server ALWAYS wins). FEATURE-BATCH additions: `POST /analyze/retry-failed` (orch.run_analyze(retry_failed=True); 400 unless analyze complete; copies CONFIG like analyze); `GET /backup` (whole project dir → zip attachment); `POST|undismiss /findings/<i>/dismiss`; fixqueue flags+filters dismissed by default (`?include_dismissed=1`, returns dismissed_count+total_count); `_manifest_summary.failed_categories` from analyze output_paths; `_sse_chat_stream(engine, session, store, text, quote, manifest)` shared SSE generator; HUMANIZATION v2: `_mood_fragment(m)` (deterministic room state: visit recency/drafts/edits/analyze-status) + `_doctor_case_file(exclude)` (cross-project PATTERNS via manifests+findings+finding_statuses: shelf count, followthrough %, recurring open HIGH categories, per-script numbers — never passages) wired into the project chat engine only (worker thread + queue → token frames → done frame w/ CLEANED reply + messages; error frame w/ still_working) at `/chat/sessions/<sid>/messages/stream` for BOTH projects and ideas — serves webapp static (no-cache) + full JSON API. ServerConfig (validated dict-holder: server_url/model/fast_model/timeout/turn_timeout=120). Routes: projects CRUD (+sample dedup, delete guarded inside PROJECTS_DIR, premise.json serve/save), analyze (?force resets analyze + drops artifacts; copies CONFIG incl fast_model), **reparse** (resets parse, regenerates KG, invalidates analyze + drops report artifacts, ensure_working refresh), report (sanitized via filter_findings at SERVE time), characters track, notes CRUD (PATCH update), stash CRUD, script (working copy + per-scene estimates), edits GET/apply/undo/redo/reset (+metrics recording), rewrite (candidates only, finding_index grounding best-effort), export fountain/fdx/txt, beatboard GET/PUT/reset/export, progress (30-min stall heal → mark_failed), fixqueue (severity→act→order sort w/ status join), report/export (tiny md→HTML renderer), drafts upload/activate/list, diff + compare (default pair = previous draft → active), chat sessions GET (retroactive language-meta strip)/DELETE (keeps writer_profile.json)/messages (watchdog → 408 {still_working:true})/fork/switch/settings, writer-memory GET/suppress/refresh (scope-aware), ideas CRUD/content(rename stops auto-title)/card/chat(start/get/delete/messages/settings)/graduate (carries premise.json + sessions, pins latest session id), config GET/POST, writer-library, test-connection. `_import_cowriter` converts ImportError → CowriterUnavailableError (503) so shelf works without Piece 3. Chat uses working copy when edits exist; turn_timeout for chats, long timeout for analysis; idea engines get writer_library_text=None (isolation) + memory_scope=idea:<id>.
- **revision.py** — working copy lifecycle (ensure_working self-heals stale copy only when no edits; preserves edits otherwise), apply_replacements (exact match; unique fuzzy ≥0.8; ambiguity skips), undo/redo stacks (records move between edits.json and edits.redo.json), rewrite_scene (grammar-constrained old/new candidates, review-before-apply), quote_present (exact then fuzzy ≥0.95 — any edit counts as addressed), finding_statuses (addressed/still_present/unknown); finding TRIAGE helpers (dismissed_path/dismissed_issues/dismiss_finding/undismiss_finding) storing (index, issue) pairs in dismissed_findings.json — a dismissal only sticks while the report says the same issue at that index; a regenerated report re-opens changed findings.
- **diff.py** — snapshot_active/upload_new_draft (snapshots current, resets parse/analyze/chat stages)/activate_draft (restores snapshot incl. report, marks analyze complete if report present); diff_scenes (SequenceMatcher opcodes on element signatures), diff_findings (resolved/still_present via quote_present; carried ≥0.7 issue similarity vs new), compare_drafts (aligned same/changed/added/removed rows per common scene), character presence diff.
- **ideas.py** — IdeaStore under PROJECTS_DIR/ideas/<id>/idea.json; EMPTY_CARD + free-form content primary; auto_title_from(first line ≤48) while auto_title=True; rename sets auto_title=False; save_card merges partial; carry_into_project writes premise.json (content included) + copies sessions.
- **beatboard.py** — permutation-of-scene-numbers board (stale-order guard falls back to natural), export_reordered renumbers 1..N via parser export, board_view cards (heading/runtime/words/note count).
- **notes.py / stash_store.py / metrics.py** — plain JSON stores (notes.json w/ anchor field, stash.json newest-first, metrics.json rolling 40 reply timings + analysis_seconds + discussed + findings fixed counts).
- **character_track.py** — importance main/supporting/bit by scene share (≥.25/.08) or dialogue share (.15); merges KG presence/co-occurrence/trait mentions + report dials/reads; graceful degradation on missing inputs.
- **watch.py / sample.py / cli.py** — watch-folder batch (moves to done/, name collision _N suffix), bundled sample "The Late Hour" (3 scenes), studio CLI run/resume/status/watch (--retry-failed, --lang).

### Webapp frontend
- **index.html** — SPA shell: sidebar (brand+connection dot, new-project, Ideas list +new, project shelf, Your library, Dawn/Settings footer), welcome view (lamp/window/shelf decor, dropzone, idea/sample buttons, shortcut hint), project bar (⌂ home, room toggle, ⌘K palette btn), workspace: struct rail (scenes/characters/stash/notes + form, beats/compare buttons, edge tab), desk (script-pane: premise-pane [hidden in idea mode], **idea-canvas** [title input, content textarea, ▸Structure panel, First pages, Sameer pill], toolbar [search/focus/reader/undo/redo/✎Revise/📋/🗂/exports/print], draft-bar, #script-scenes, three selection floats Ask/Stash/Note), pane-divider (display:none legacy), drawer (#room-drawer: co-write panel w/ partner-card/messages/#idea-explore chips/composer; feedback panel w/ lang select, progress, Run Analysis, ↻Re-parse, tabs Report/FixQueue), gutter tabs (Sameer pulsing dot / Consultant), status strip (project · model · conn · ⚡metrics · sprint timer · elapsed · Dawn), full-screen views (beatboard/compare/**revision-view**: nav|script|findings + status), modals (sam-notes, settings, rewrite, palette, fork). Cache-bust `?v=` on style.css/app.js — bump both when editing them.
- **app.js** (structure; ~4.9k lines — consult on first edit) — per NOTES: Manuscript Stage layout (drawer summoned via gutter, rail collapsed by default w/ pref persistence), keyboard cascade Esc drawer→shelf→rail; shortcuts c/f/a/r/s/b/d/z/?; fuzzy command palette (fuzzyScore adjacency/word-start bonuses) + Spotlight mode (total chrome removal, auto-exits when opening full-screen tools); renderScriptView w/ Craft shelf (collapsed by default, craft_open pref) hosting fix queue/pacing/dials/mirror panels; renderScenePage reused by revision view; severity dots shared `.sev-dot`; select-to-ask/stash/note floats; focus mode marks current scene+line (typewriter); sprint timer persists via localStorage; watchdog "still working" bubble w/ Keep waiting/Give up; idea canvas autosave debounced 1.2s + blur, /sameer first-line command, pill reuses the idea's single session; session restore branches for all views. Known gotcha: hardcoded FALLBACK_PERSONA_LABELS (doesn't sync with server PERSONAS).
- **style.css** — not deep-read; sections ordered roughly: shell/sidebar/welcome/workspace/drawer/gutter/rail/rooms/report cards/craft-shelf/beatboard/compare/revision/modals/status-strip/theme tokens/Dawn light mode/spotlight+idea-mode body classes/print CSS.

### Tests
- **conftest.py** — session-scoped real-HTTP mock server fixture on 127.0.0.1:8196 (werkzeug make_server thread) + `sample_fountain` fixture (REVOLVER/"I'll tell you everything" script — the canonical E2E fixture).
- **mock_unified_server.py** — one Flask app handling ALL request shapes by system-prompt keyword: memory refresh, revision rewrite (replaces the tell-you-everything line with "[fixed] …"), analyzer passes (summaries/dialogue/principles REVOLVER=dangling gun/theme/character/structure/scene_function/genre/coverage/logline/reads/dials/ledger), else conversational echo reporting persona/findings_seen/injected_scenes for grounding assertions.
- Layout: one file per feature area (see names in digest table); webapp API tests drive `webapp_server.app.test_client()` with `PROJECTS_DIR` pointed at tmp_path.

---

## Cross-cutting invariants (don't violate)
1. Pieces communicate via JSON files as plain dicts; cross-package imports are lazy inside methods (cowriter stays standalone; webapp lazy-imports cowriter with clean degradation).
2. Candidate generation ≠ judgment (KG proposes, model judges); diagnose/prescribe split (analyzer never prescribes fixes; rewrites happen conversationally in Piece 3 / the rewrite endpoint).
3. Flag, don't drop — unverifiable quotes downgraded w/ ⚠️; unknown ledger status→dangling; findings filtered only for language meta-commentary (both filters kept in sync).
4. Evidence-first — verbatim quotes only from full-text passes; summary passes cite scene numbers and MUST set evidence_quote=null.
5. Resume semantics: complete stages short-circuit; explicit re-run (analyze?force, reparse) resets the stage first; retry_failed merges; partial ≠ failed.
6. Writer data survives everything: notes/stash/memory/premise live outside parse artifacts; Clear chat keeps writer_profile.json; ensure_working never overwrites edits.
7. Language respect: never comment on the script's language (prompt instruction + serve-time + reply-time stripping, report sanitization at serve time).
8. Boring tech only: files not DBs, stdlib-first, Flask JSON API, vanilla JS SPA, cache-bust `?v=` bumps on frontend edits.
