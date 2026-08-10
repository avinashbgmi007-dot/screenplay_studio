# Per-File Documentation

This directory contains detailed documentation for every source file in the screenplay-studio project.

## Quick Navigation

### Parser Module (`screenplay_parser/`)
- [models.py](screenplay_parser_models.md) — Core data types
- [text_parser.py](screenplay_parser_text_parser.md) — Main parsing entry
- [heuristics.py](screenplay_parser_heuristics.md) — Pattern matching
- [stats.py](screenplay_parser_stats.md) — Deterministic statistics
- [knowledge_graph.py](screenplay_parser_knowledge_graph.md) — Knowledge graph extraction

### Analyzer Module (`screenplay_analyzer/`)
- [pipeline.py](screenplay_analyzer_pipeline.md) — Main analysis pipeline
- [prompts.py](screenplay_analyzer_prompts.md) — Prompt templates
- [grammar.py](screenplay_analyzer_grammar.md) — GBNF grammars
- [verifier.py](screenplay_analyzer_verifier.md) — Evidence verification
- [principles_engine.py](screenplay_analyzer_principles_engine.md) — Principles detection
- [report.py](screenplay_analyzer_report.md) — Report generation
- [rules_context.py](screenplay_analyzer_rules_context.md) — Rules integration
- [llm_client.py](screenplay_analyzer_llm_client.md) — LLM client

### Cowriter Module (`screenplay_cowriter/`)
- [engine.py](screenplay_cowriter_engine.md) — CoWriter engine
- [models.py](screenplay_cowriter_models.md) — Session models
- [context.py](screenplay_cowriter_context.md) — Context builders
- [personas.py](screenplay_cowriter_personas.md) — Personas & modes
- [cli.py](screenplay_cowriter_cli.md) — CLI & REPL
- [store.py](screenplay_cowriter_store.md) — Session store
- [discovery.py](screenplay_cowriter_discovery.md) — Model discovery

### Studio Module (`screenplay_studio/`)
- [orchestrator.py](screenplay_studio_orchestrator.md) — Main orchestrator
- [manifest.py](screenplay_studio_manifest.md) — Project manifest
- [webapp_server.py](screenplay_studio_webapp_server.md) — Flask web app
- [cli.py](screenplay_studio_cli.md) — CLI
- [__init__.py](screenplay_studio_init.md) — Package init

### Knowledge Base (`knowledge_base/`)
- [knowledge_base.py](knowledge_base_knowledge_base.md) — Knowledge base
- [__init__.py](knowledge_base_init.md) — Package init

## Related Documentation
- [ARCHITECTURE.md](../ARCHITECTURE.md) — High-level architecture
- [PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md) — Project overview
- [SUMMARY.md](SUMMARY.md) — Three-piece architecture summary
- [GRAPH_ANALYSIS.md](GRAPH_ANALYSIS.md) — Knowledge graph analysis
- [INDEX.md](INDEX.md) — Complete index
