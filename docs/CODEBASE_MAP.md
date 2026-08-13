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
| `pipeline.py` | `analyze(...)`, `AnalysisResult` (incl. `category_outcomes`), `ALL_CATEGORIES`, `resolve_categories`, `build_scene_summaries`, `build_scene_overview_text`, `run_dialogue_analysis`, `run_script_level_category`, `run_coverage`, `run_character_reads`, `run_logline_test` | The 11-pass pipeline orchestrator (see ARCHITECTURE.md) |
| `llm_client.py` | `LlamaServerClient`, `LlamaServerError`, `ModelNotFoundError` | HTTP client, GBNF-constrained JSON, `_with_chunk_backoff` handles context exhaustion |
| `grammar.py` | `findings_grammar`, `scene_summary_grammar`, `principle_judgment_grammar`, `replacements_grammar`, `logline_test_grammar`, `character_reads_grammar`, `coverage_grammar` | Hand-written GBNF grammars |
| `verifier.py` | `verify_findings`, `verification_summary` | Fuzzy matching (SequenceMatcher, 0.72), sliding-window quote verification |
| `principles_engine.py` | `run_principles_engine` | Two-stage Chekhov's Gun (KG candidates → model significance) |
| `formatting_check.py` | `check_formatting(doc)` | Deterministic formatting rules |
| `voice.py` | `run_voice_analysis`, `run_subtext_analysis` | Deterministic craft passes (voice-bleed, on-the-nose) |
| `genre.py` | `run_genre_check`, `conventions_for` | Genre-convention check against coverage genre |
| `feedback_filter.py` | `filter_findings` | Drops non-writing meta-commentary (dialect/subtitle noise) |
| `rules_context.py` | `RulesContext` | Injects knowledge-base rules into prompts; `_NullRulesContext` fallback |
| `prompts.py` | `scene_summary_prompt`, `dialogue_analysis_prompt`, `theme_analysis_prompt`, `character_analysis_prompt`, `structure_analysis_prompt`, `scene_function_prompt`, `logline_test_prompt`, `character_reads_prompt`, `principle_judgment_prompt`, `genre_check_prompt`, `coverage_prompt`, `language_instruction` | Two-tier citation prompts |
| `report.py` | `render_markdown`, `to_findings_json`, `save_report` | `.md` + `.findings.json` output |
| `cli.py` | `main` | `analyze <parsed.json> --server ... -o report.md` |

## screenplay_cowriter — Piece 3 (LLM, requires llama-server)

| File | Public API | Purpose |
|---|---|---|
| `models.py` | `Session`, `Branch`, `Message` | Session model with `fork`/`switch`/`delete_branch`/`save`/`load` |
| `store.py` | `SessionStore` | File-backed session store (one JSON per session) |
| `engine.py` | `CoWriterEngine` | `send_message()` — one grounded chat turn; saves the session itself when constructed with `store=` |
| `context.py` | `ScriptContext`, `ReportContext`, `build_system_prompt`, `build_scene_context_block`, `extract_scene_refs`, `load_json` | Context + scene injection |
| `personas.py` | `PERSONAS`, `MODES`, `persona_text`, `mode_text` | 6 personas × 3 modes |
| `discovery.py` | `resolve_model` | explicit > inherited > loaded |
| `llm_client.py` | `LlamaServerClient`, `LlamaServerError`, `ModelNotFoundError` | Lightweight free-text chat client |
| `language_meta.py` | `strip_language_meta` | Strips wrapper-language markers from replies |
| `server.py` | `main` + Flask routes | Standalone Flask API (port 8300) |
| `cli.py` | `main`, `run_repl`, `cmd_chat`, `cmd_list` | `chat`/`list` subcommands + slash commands |

## screenplay_studio — orchestrator + web UI

| File | Public API | Purpose |
|---|---|---|
| `manifest.py` | `ProjectManifest`, `StageStatus` | `project.json`; resume semantics (pending/running/complete/failed/skipped) |
| `orchestrator.py` | `Orchestrator`, `OrchestratorError`, `_merge_analysis` | `run_parse` → `run_analyze` → `start_chat`; total-vs-partial failure handling; `retry_failed=True` resumes failed categories only |
| `revision.py` | `ensure_working`, `load_working`, `save_working`, `has_edits`, `reset_working`, `redo_stack`, `clear_redo` | Working copy rewrite/apply/undo/redo/export loop |
| `diff.py` | `snapshot_active`, `upload_new_draft`, `activate_draft`, `diff_scenes`, `diff_findings`, `compare_drafts`, `diff_drafts` | Draft snapshots + cross-draft diffing |
| `beatboard.py` | `get_order`, `set_order`, `reset_order`, `has_board`, `export_reordered`, `board_view` | Scene reordering / beat board |
| `notes.py` | `load_notes`, `notes_for_scene`, `add_note`, `update_note`, `delete_note` | Per-project notes |
| `watch.py` | `process_pending`, `watch_loop` | Watch-folder auto-analysis |
| `sample.py` | `SAMPLE_TITLE`, `SAMPLE_SCRIPT` | Bundled 3-scene sample ("The Late Hour") |
| `webapp_server.py` | Flask app + `main`, `ServerConfig`, `_import_cowriter`, `CowriterUnavailableError` | Web UI backend (port 8500); serves `webapp/` static + JSON API; `/api/config` exposes personas/modes |
| `cli.py` | `main`, `cmd_run`, `cmd_resume`, `cmd_status`, `cmd_watch` | `run`/`resume`/`status`/`watch` subcommands |
| `webapp/` | `index.html`, `app.js`, `style.css` | Vanilla JS SPA (no build step) |

## knowledge_base — craft rules (no model)

| File | Public API | Purpose |
|---|---|---|
| `knowledge_base.py` | `KnowledgeBase`, `Rule` | Loads `rules/*.json`; `for_taxonomy_level`/`render_for_prompt` |
| `rules/*.json` | — | 34 attributed rules: story_macro, structure_pacing, plot_thread, character, relationship, scene, dialogue, continuity |
| `schema.json` | — | Rule JSON schema (confidence_tier, requires, related_rules, …) |

## tests

- `conftest.py` — session-scoped mock llama-server fixture (port **8196**) + `sample_fountain` fixture
- `mock_unified_server.py` — Flask mock handling Piece 2 (grammar JSON) + Piece 3 (chat echo) + revision-loop request shapes
- `fixtures/pain_tenglish.fountain` — small Tenglish sample
- `test_*.py` — one file per feature area (see TESTING.md); 281 tests collected
