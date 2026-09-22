# Codebase Map

Symbol-level index so you can answer "where is X?" without scanning the whole repo. Read this first, then open only the files you need. Regenerate when public APIs change (the `grep -nE "^(def|class) "` pattern works per package).

## screenplay_parser — Piece 1 (deterministic, no model)

| File | Public API | Purpose |
|---|---|---|
| `models.py` | `ElementType` (enum), `Element`, `Scene`, `ParseWarning`, `ScriptDocument` | Core data model all formats converge on; `to_dict`/`from_dict`/`save`/`load` |
| `text_parser.py` | `parse_text(path, source_format)` | Shared state machine for `.txt`/`.fountain`/`.md` |
| `fdx_parser.py` | `parse_fdx(path)` | Final Draft `.fdx` XML parser |
| `pdf_parser.py` | `parse_pdf(path)` | PDF → text → Element stream, with OCR fallback (`_get_ocr_engine`) |
| `heuristics.py` | `looks_like_*` (heading/time/transition/shot/parenthetical/character cue), `parse_scene_heading`, `normalize_character_name` | Classification rules (script-aware for Tenglish/Hindi/Tamil) |
| `structure.py` | `estimate_scene_pages`, `assign_acts`, `act_for_scene`, `pacing_curve`, `character_arc` | Act/page/pacing analytics |
| `stats.py` | `scene_estimates`, `character_stats`, `dialogue_action_ratio`, `location_usage`, `scene_length_stats`, `int_ext_and_time_breakdown`, `full_stats_report` | Deterministic analytics |
| `knowledge_graph.py` | `KnowledgeGraph`, `CharacterEntry`, `PropCandidate`, `TimelineEntry`, `PromiseCandidate`, `TraitMention`, `build_knowledge_graph` | **Candidate generator** (props recurring 2+ scenes, promises, timeline, co-occurrence) |
| `export.py` | `to_fountain`, `to_txt`, `to_fdx`, `export`, `export_to_path` | Re-export parsed doc |
| `cli.py` | `main`, `cmd_parse`, `cmd_stats` | `parse`/`stats` subcommands |
| `__init__.py` | `parse_screenplay`, `parse_fdx/txt/fountain/md/pdf`, `build_knowledge_graph`, `KnowledgeGraph`, `export*` | Extension dispatch by file suffix |

## screenplay_analyzer — Piece 2 (LLM, requires llama-server)

| File | Public API | Purpose |
|---|---|---|
| `pipeline.py` | `analyze(...)`, `AnalysisResult` (incl. `category_outcomes`, `merge`), `ALL_CATEGORIES`, `resolve_categories`, `build_scene_summaries`, `build_scene_overview_text`, `run_dialogue_analysis`, `run_script_level_category`, `run_coverage`, `run_character_reads`, `run_logline_test` | The pipeline orchestrator — 12 model categories + deterministic passes (see ARCHITECTURE.md) |
| `llm_client.py` | `LlamaServerClient`, `LlamaServerError`, `ModelNotFoundError` | HTTP client, GBNF-constrained JSON, `_with_chunk_backoff` handles context exhaustion |
| `llm_client_base.py` | `BaseLlamaClient`, `LlamaServerError`, `ModelNotFoundError`, `auth_headers`, `busy_retry_delay` | Shared base client (re-exported through both packages' `llm_client`). `auth_headers(api_key)` is the ONE construction of the bearer credential (`{"Authorization": "Bearer …"}` for a token-protected endpoint, `{}` for a local llama-server) — both clients thread it through `extra_headers` on every request. It lives here, not in either consumer, because a wrong auth header is indistinguishable from a wrong token and the two would drift silently (`net_guard.py` exists for the same reason) |
| `grammar.py` | `findings_grammar`, `scene_summary_grammar`, `principle_judgment_grammar`, `replacements_grammar`, `logline_test_grammar`, `character_reads_grammar`, `coverage_grammar`, `setup_payoff_ledger_grammar`, `character_dials_grammar` | Hand-written GBNF grammars |
| `verifier.py` | `verify_findings`, `verification_summary` | Fuzzy matching (SequenceMatcher, 0.72), sliding-window quote verification |
| `principles_engine.py` | `run_principles_engine` | Two-stage Chekhov's Gun (KG candidates → model significance) |
| `formatting_check.py` | `check_formatting(doc)` | Deterministic formatting rules |
| `voice.py` | `run_voice_analysis`, `run_subtext_analysis`, `run_idiolect_analysis` | Deterministic craft passes (voice-bleed, on-the-nose, idiolect) |
| `genre.py` | `run_genre_check`, `conventions_for` | Genre-convention check against coverage genre |
| `feedback_filter.py` | `filter_findings` | Drops non-writing meta-commentary (dialect/subtitle noise) |
| `continuity.py` | `run_continuity_analysis` | Deterministic continuity pass: unmarked time-of-day flips, character-name variants |
| `pacing.py` | `per_scene_pace`, `drag_findings` | Deterministic per-scene pace index + drag flags |
| `dials.py` | `run_character_dials` | Model-scored per-character dials (grammar-constrained) |
| `setup_payoff.py` | `run_setup_payoff_ledger`, `dangling_findings` | End-of-pipeline whole-script setup/payoff audit; dangling entries feed Plot Economy |
| `rules_context.py` | `RulesContext` | Injects knowledge-base rules into prompts (a `_NullRulesContext` fallback lives in `pipeline.py`) |
| `prompts.py` | `scene_summary_prompt`, `dialogue_analysis_prompt`, `theme_analysis_prompt`, `character_analysis_prompt`, `structure_analysis_prompt`, `scene_function_prompt`, `logline_test_prompt`, `character_reads_prompt`, `principle_judgment_prompt`, `genre_check_prompt`, `coverage_prompt`, `character_dials_prompt`, `setup_payoff_ledger_prompt`, `language_instruction` | Two-tier citation prompts |
| `report.py` | `render_markdown`, `to_findings_json`, `save_report` | `.md` + `.findings.json` output |
| `cli.py` | `main` | `analyze <parsed.json> --server ... -o report.md` |

## screenplay_cowriter — Piece 3 (LLM, requires llama-server)

| File | Public API | Purpose |
|---|---|---|
| `models.py` | `Session`, `Branch`, `Message` | Session model with `fork`/`switch`/`delete_branch`/`save`/`load` |
| `store.py` | `SessionStore` | File-backed session store (one JSON per session) |
| `engine.py` | `CoWriterEngine` | `send_message()` — one grounded chat turn; saves the session itself when constructed with `store=` |
| `context.py` | `ScriptContext`, `ReportContext`, `build_system_prompt`, `build_scene_context_block`, `extract_scene_refs`, `load_json` | Context + scene injection |
| `personas.py` | `PERSONAS`, `PERSONAS["*_examples"]`, `MODES`, `persona_text`, `mode_text`, `DEFAULT_PERSONA`, `DEFAULT_MODE`, `post_history_reminder`, `trait_reminder` | Persona bible — 8 personas (writing_partner/premise_doctor/script_consultant/producer/dev_exec/teacher/audience/genre_specialist) × 5 modes (peer/evidence_discussion/concept_validation/brainstorm/character_interview); `_examples` keys are prompt-only, never exposed via /api/config |
| `discovery.py` | `resolve_model` | explicit > inherited > loaded |
| `llm_client.py` | `LlamaServerClient`, `LlamaServerError`, `ModelNotFoundError`, `WatchdogTimeoutError` | Lightweight free-text chat client (turn watchdog) |
| `language_meta.py` | `strip_language_meta`, `strip_repetition_lines`, `strip_repeated_blocks`, `strip_json_wrap` | Strips wrapper-language markers + repetition/JSON noise from replies |
| `language_mirror.py` | `detect_register`, `mirror_instruction` | Mirrors the writer's register (Tenglish/Hindi/Telugu/English) in replies |
| `peer.py` | `classify_turn`, `should_probe`, `ensure_forward_momentum`, `cap_suggestions`, `has_embedded_reasoning` | Peer-mode guardrails: probe instead of parrot, forward momentum, suggestion cap |
| `memory.py` | `WriterMemory`, `build_relationship_card`, `merge_refresh`, `extract_signals`, `apply_signals`, `dimension_gate`, `_migrate_v2` | Writer relationship memory (scoped global/project/idea), notes-on-you card, refresh sync |
| `writer_library.py` | `build_library`, `library_digest_text` | Past-work digest from every parsed project; rides every turn as PAST WORK (firewalled from current script) |
| `server.py` | `main` + Flask routes | Standalone Flask API (port 8300) |
| `cli.py` | `main`, `run_repl`, `cmd_chat`, `cmd_list` | `chat`/`list` subcommands + slash commands |

## screenplay_studio — orchestrator + web UI

| File | Public API | Purpose |
|---|---|---|
| `manifest.py` | `ProjectManifest`, `StageStatus` | `project.json`; resume semantics (pending/running/complete/failed/skipped). Also snapshots the CONNECTION (`server_url`, `model_id`, `fast_model`, `timeout`, `api_key`) so `resume` and the CLI can reach the same model without re-typing it — which is why `api_key` rides here and not only in the process config |
| `orchestrator.py` | `Orchestrator`, `OrchestratorError` | `run_parse` → `run_analyze` → `start_chat`; total-vs-partial failure handling; `retry_failed=True` resumes failed categories only (merge via `AnalysisResult.merge`) |
| `revision.py` | `ensure_working`, `load_working`, `save_working`, `has_edits`, `reset_working`, `edits_log`, `redo_stack`, `clear_redo` | Working copy rewrite/apply/undo/redo/export loop. The edit log and redo stack follow the store contract — MISSING → `[]`, DAMAGED → `StoreUnreadable` (503, never a silent empty list; BE-M1/BE-M2), and `undo_last_edit`/`redo_last_edit` pre-flight the *other* store before mutating so damage declines the operation rather than half-applying it. `has_edits` is the deliberate exception: it answers a coarse "is there anything I must not overwrite?", so damage reads as a conservative `True`. GO 1/2: `compute_finding_id` (content-hash finding identity: category + evidence_quote; djb2→base36 — twin of `core.js` `computeFindingId`, proven byte-identical by `tests/e2e_browser_finding_id_parity.py`), `dismissed_finding_ids`, `finding_intents`/`set_finding_intent` (`finding_marks.json` intent store: mark-addressed + defer, id-keyed, survives regeneration), `last_pass_snapshot` ((mtime, content-signature)-guarded `last_pass.json` diff: last_total/still_live/fixed/new/ghosted_marks — ALL distinct-id counts, duplicates counted once; one generation back, honest None on first pass; `report_sig` closes the same-tick-rewrite hole the mtime alone cannot — drives the arrival strip's pass line, which measures analysis-pass drift, NOT writer edits) |
| `diff.py` | `snapshot_active`, `upload_new_draft`, `activate_draft`, `diff_scenes`, `diff_findings`, `compare_drafts`, `diff_drafts` | Draft snapshots + cross-draft diffing |
| `beatboard.py` | `get_order`, `set_order`, `reset_order`, `has_board`, `export_reordered`, `board_view` | Scene reordering / beat board |
| `notes.py` | `load_notes`, `notes_for_scene`, `add_note`, `update_note`, `delete_note` | Per-project notes |
| `watch.py` | `process_pending`, `watch_loop` | Watch-folder auto-analysis |
| `ideas.py` | `IdeaStore` | Idea room store: free-form page + premise card + auto-title, graduation into projects; ids validated by jsonio; `save_content`/`rename`/`save_card` merge under a locked load-modify-write (`_modify`) so a racing save never clobbers fields it didn't see |
| `stt.py` | `transcribe`, `supported_languages`, `STTUnavailableError` | Local dictation (faster-whisper lazy import or localhost whisper server); never off-machine. The localhost check is `net_guard.is_loopback_url`, shared with the model-server guard |
| `character_track.py` | `build_character_tracks` | Per-character presence/traits/interactions rail from KG + report |
| `metrics.py` | `load`, `record_analysis`, `record_reply`, `record_findings` | Quiet local writing-loop metrics (status strip ⚡) |
| `stash_store.py` | `stash_path`, `load_stash`, `add_to_stash`, `remove_from_stash` | The Stash: saved snippets per project |
| `demo_model.py` | `start_demo_server` | In-process demo craft model (rule-based) so the desk works without llama-server; a reachable real server always wins |
| `webapp_demo.py` | `main` | Launcher alias: webapp_server with the demo model forced on |
| `sample.py` | `SAMPLE_TITLE`, `SAMPLE_SCRIPT` | Bundled 3-scene sample ("The Late Hour") |
| `webapp_server.py` | Flask app + `main`, `ServerConfig`, `_validate_server_url`, `_import_cowriter`, `CowriterUnavailableError` | Web UI backend (port 8500); serves `webapp/` static + JSON API; `/api/config` exposes personas/modes; GO 2 route: POST `/api/projects/<name>/findings/intent` (the intent store). **Model-server trust boundary:** `_validate_server_url` gates every point a `server_url` can enter (config setter, `/api/config`, `/api/test-connection`, manifest propagation) or be used (`_make_client`, `_engine_base_url`); loopback-only unless `--allow-remote-server` / `SCREENPLAY_STUDIO_ALLOW_REMOTE_SERVER=1` — a process-level opt-in, never grantable over HTTP. **Local vs remote API (one form, two modes):** `connection_mode(url)` DERIVES `"local"`/`"remote"` from the URL rather than storing it (no drift); `_require_remote_optin()` raises the actionable refusal; `_auth_headers`/`_api_key_for(manifest)` resolve the token (project-first, then process-wide) and are threaded into all nine client-construction sites; `_adopt_connection(m)` stamps `server_url` + `api_key` onto a manifest at every creation point so `resume`/CLI reach the same endpoint. `api_key` is a `ServerConfig` default and a manifest field, and **never leaves over HTTP** — `/api/config` reports `api_key_set` (bool) + `connection_mode` + `allow_remote` instead (`tests/test_connection_modes.py`, `tests/e2e_browser_connection_modes.py`). **Analyze pre-flight:** `_analyze_locked`'s pre-flight (manifest rewrite + heartbeat reset) is wrapped so any failure returns a clear JSON 500 — an exception escaping a handler makes the Flask dev server close the connection with NO reply, which the caller sees as `RemoteDisconnected` and cannot tell apart from a network fault. `_start_progress_heartbeat(m)` **writes** a fresh `running` heartbeat where an `os.remove(progress.json)` used to be: the delete was never load-bearing (the pipeline's first event overwrites the file within seconds) and it was the one operation an environment could refuse (`tests/test_analyze_preflight.py`). **Error contract:** `_error(msg, status)` returns `{"error": …}` for every route's own failure path, and `@app.errorhandler(Exception)` (`_unhandled`) is the floor beneath them — any unhandled error answers as JSON too, with `HTTPException` passed through so 404/405/413 keep their codes (`tests/test_destructive_paths.py`)
 **Asset versions:** `_serve_spa_document` = `_harden_spa_document` (CSP) + `_stamp_asset_versions`, which rewrites every `?v=` in the served document to that asset's content hash, so a stale token cannot exist (`tests/test_asset_cache_bust.py`) |
| `jsonio.py` | `atomic_write_json`, `lock_for`, `retry_permission`, `check_safe_id`, `StoreUnreadable`, `StoreLockTimeout` | Shared atomic JSON persistence (unique tmp + fsync + os.replace) + ONE per-path lock that is BOTH an in-process RLock and an OS byte-range lock on a `<store>.lock` sidecar, so the CLI and the webapp can hold it across a load-modify-write together + bounded retry for Windows sharing violations + the safe-id contract that blocks path traversal at every store |
| `net_guard.py` | `is_loopback_host`, `is_loopback_url` | The ONE answer to "is this URL on this machine?", parsed (urlparse + `ipaddress.is_loopback`) rather than prefix-matched — `http://127.0.0.1@evil.com` and `http://localhost.evil.com` both satisfy a prefix check while resolving remotely. Used by the model-server guard, the dictation guard, and the cross-origin `Origin` check |
| `cli.py` | `main`, `cmd_run`, `cmd_resume`, `cmd_status`, `cmd_watch` | `run`/`resume`/`status`/`watch` subcommands |
| `webapp/` | `index.html`, `app.js`, `core.js`, `style.css`, `tungsten.css` | Vanilla JS SPA (no build step); `core.js` holds the DOM-free pure helpers (unit-tested in `node --test tests/js/`) — including `computeFindingId`/`_strHash`, the content-hash finding identity that MUST stay byte-identical to `revision.py:compute_finding_id` (it is the key for the writer's marks, dismissals, ghost detection and the doctor's case file; parity is proven live by `tests/e2e_browser_finding_id_parity.py`); `tungsten.css` is the frozen visual system override (night + dawn registers, loads after style.css). **XSS contract:** `core.js:escapeHtml` is the ONE helper every `innerHTML` sink must route untrusted text through (finding text is model output derived from the writer's script — a screenplay is a file a collaborator can send you); row wiring is DELEGATED via `data-*` (never `onclick="…"` built from data) so the SPA document can keep `script-src 'self'` (`webapp_server.py:_SPA_CSP`). GO 1/2 client symbols in `app.js`: the counting contract `findingDisposition`/`findingOpen`/`findingStatusOf` (every surface reads it — N3 law), `openFeedbackView` (the fold: routes to the workspace + dock Evidence lens; the `#feedback-view` clone is dormant/unreachable), the ONE filter state `state.findingFilter` (severities · category · `scene`) + `buildFindingFilterRow`/`syncSceneFilterChip` (P1.7: the scene is a filter DIMENSION, never a surface — `findingOnScene`/`openFindingsOnScene` are its one matching rule and its count through `findingDisposition`; the chip always prints its scope), the scene rail's clean-scene ✓ (`sceneIndexSeverity().live`, spec §14.3 — a scene with zero live findings shows a quiet labelled ✓ where its severity dots would be), ink `inkAnchorsFor`/`decorateLineWithInk`, the keyboard fix loop `startLoop`/`stepLoop`/`exitLoop`/`renderLoopBar` (contextual n/p/esc), intent buttons via `setFindingIntent`, `buildArrivalStrip` (scorekeeping + trust + retry + ghosted), `copyFindingEvidence` |

## knowledge_base — craft rules (no model)

| File | Public API | Purpose |
|---|---|---|
| `knowledge_base.py` | `KnowledgeBase`, `Rule` | Loads `rules/*.json`; `for_taxonomy_level`/`render_for_prompt` |
| `rules/*.json` | — | 263 attributed rules across 26 files: story_macro, structure_pacing, plot_thread, character, relationship, scene, dialogue, dialogue_advanced, scene_design, continuity, genre (action/comedy/drama/horror/mystery/romance/scifi/thriller), pitch, psychology, body_language, power_dynamics, visual_storytelling, writing_habits, revision, theme, … |
| `schema.json` | — | Rule JSON schema (confidence_tier, requires, related_rules, …) |

## tests

- `conftest.py` — session-scoped mock llama-server fixture (port **8196**) + `sample_fountain` fixture
- `mock_unified_server.py` — Flask mock handling Piece 2 (grammar JSON) + Piece 3 (chat echo) + revision-loop request shapes
- `fixtures/` — `pain_tenglish.fountain`, `Pain_FD_4_scenes.pdf`, `Pain_FD_4_scenes_recoverable.pdf`
- `js/` — node tests for the DOM-free `core.js` helpers (`node --test`)
- `e2e_browser_*.py` — Playwright browser suites (share `e2e_browser_common.py`)
- `test_*.py` — one file per feature area (see TESTING.md); 670+ tests collected
