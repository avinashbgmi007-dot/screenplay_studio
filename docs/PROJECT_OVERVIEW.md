# Project Overview — screenplay-studio

## Purpose
A three-piece screenplay analysis and co-writing system for writers who want structured feedback and conversational assistance on their screenplays.

## What It Does
- **Parses** screenplays in multiple formats (Fountain .fdx, .fountain, plain text, .md, PDF)
- **Analyzes** them across 6 dimensions using an LLM (grammar-constrained JSON output)
- **Co-writes** with the screenplay via a conversational interface with persona/mode switching and branch-based sessions

## Core Design Principles
- **Boring is good** — no database, no threading, no framework
- **Pieces are independently usable** — each piece can be imported and run standalone
- **Diagnose/prescribe split** — analysis diagnoses, co-writer prescribes
- **Model-agnostic** — works with any llama.cpp-compatible model
- **Evidence-first** — findings are verified against actual text

## Three Pieces

| Piece | Name | Responsibility | Model Dependency |
|-------|------|----------------|------------------|
| 1 | Parser | Deterministic structural extraction | None |
| 2 | Analyzer | LLM-powered analysis with grammar-constrained output | Required |
| 3 | Co-writer | Conversational co-writing with persona/mode switching | Required |

## Orchestrator
A thin glue layer (`screenplay_studio`) that runs the three pieces in sequence, manages a manifest for resume/retry semantics, and serves a Flask web UI on port 8500.

## Key Files
- `screenplay_studio/orchestrator.py` — single entry point
- `screenplay_studio/manifest.py` — state management
- `screenplay_analyzer/pipeline.py` — full analysis pipeline
- `screenplay_cowriter/engine.py` — chat engine
- `webapp_server.py` — web UI server

## Strengths
- Well-considered find-candidates → judge → suggest split
- Error isolation through manifest
- Chunk+backoff for model calls
- Thorough evidence verification

## Known Issues
- Module-level mutable `CONFIG` dict in webapp_server.py
- Silent fallback in RulesContext
- Hardcoded persona list in frontend
- Conversation history not persisted
