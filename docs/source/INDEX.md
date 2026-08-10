# Source File Documentation Index

This directory contains per-file documentation for all source files in the screenplay-studio project.

## screenplay_parser/ (4 files)
| File | Documentation |
|------|--------------|
| `models.py` | [Core data types](screenplay_parser_models.md) — ElementType, Scene, ScriptDocument, Element |
| `text_parser.py` | [Main parsing entry](screenplay_parser_text_parser.md) — parse_text, parse_fountain, parse_txt, parse_md |
| `heuristics.py` | [Pattern matching](screenplay_parser_heuristics.md) — looks_like_*, parse_scene_heading, normalize_character_name |
| `stats.py` | [Deterministic stats](screenplay_parser_stats.md) — character_stats, genre_signals, page_count_estimate |
| `knowledge_graph.py` | [Knowledge graph builder](screenplay_parser_knowledge_graph.md) — build_knowledge_graph, PropCandidate, PromiseCandidate |

## screenplay_analyzer/ (7 files)
| File | Documentation |
|------|--------------|
| `pipeline.py` | [Main analysis pipeline](screenplay_analyzer_pipeline.md) — analyze, build_scene_summaries, run_dialogue_analysis |
| `prompts.py` | [Prompt templates](screenplay_analyzer_prompts.md) — CITATION_INSTRUCTION, scene_summary_prompt, findings_prompt |
| `grammar.py` | [GBNF grammars](screenplay_analyzer_grammar.md) — findings_grammar, scene_summary_grammar |
| `verifier.py` | [Evidence verification](screenplay_analyzer_verifier.md) — verify_finding, _best_fuzzy_match (0.72 threshold) |
| `principles_engine.py` | [Principles engine](screenplay_analyzer_principles_engine.md) — _judge_candidate, Chekhov's Gun detection |
| `report.py` | [Report generation](screenplay_analyzer_report.md) — render_markdown, to_findings_json, save_report |
| `rules_context.py` | [Rules context](screenplay_analyzer_rules_context.md) — CATEGORY_TO_TAXONOMY_LEVELS, RulesContext |
| `llm_client.py` | [LLM client](screenplay_analyzer_llm_client.md) — LlamaServerClient, list_models, resolve_model, chat_json |

## screenplay_cowriter/ (6 files)
| File | Documentation |
|------|--------------|
| `engine.py` | [CoWriter engine](screenplay_cowriter_engine.md) — CoWriterEngine, send_message |
| `models.py` | [Session models](screenplay_cowriter_models.md) — Session, Branch, Message, fork, switch, delete_branch |
| `context.py` | [Context builders](screenplay_cowriter_context.md) — ScriptContext, ReportContext, build_system_prompt |
| `personas.py` | [Personas & modes](screenplay_cowriter_personas.md) — PERSONAS, MODES, DEFAULT_PERSONA, DEFAULT_MODE |
| `cli.py` | [CLI](screenplay_cowriter_cli.md) — cmd_chat, run_repl, slash commands |
| `store.py` | [Session store](screenplay_cowriter_store.md) — SessionStore, create, load, save, list, delete |
| `discovery.py` | [Model discovery](screenplay_cowriter_discovery.md) — resolve_model (explicit > inherited > loaded) |

## screenplay_studio/ (5 files)
| File | Documentation |
|------|--------------|
| `orchestrator.py` | [Main orchestrator](screenplay_studio_orchestrator.md) — Orchestrator, run_parse, run_analyze, start_chat, run_full |
| `manifest.py` | [Project manifest](screenplay_studio_manifest.md) — StageStatus, ProjectManifest, create, load, save |
| `webapp_server.py` | [Flask web app](screenplay_studio_webapp_server.md) — API endpoints |
| `cli.py` | [CLI](screenplay_studio_cli.md) — cmd_run, cmd_resume, cmd_status, main |
| `__init__.py` | [Package init](screenplay_studio_init.md) — exports ProjectManifest, StageStatus, Orchestrator, OrchestratorError |

## knowledge_base/ (2 files)
| File | Documentation |
|------|--------------|
| `knowledge_base.py` | [Knowledge base](knowledge_base_knowledge_base.md) — Rule, KnowledgeBase, for_taxonomy_level, render_for_prompt |
| `__init__.py` | [Package init](knowledge_base_init.md) — imports KnowledgeBase, Rule |

## Total: 24 source files documented
