# Screenplay Studio — Three-Piece Architecture Summary

## Architecture Overview

The screenplay-studio project implements a **Three-Piece Architecture**:

### 1. screenplay_parser (Deterministic)
Pure Python, no LLM calls. Parses screenplay text into structured `ScriptDocument` objects.
- Supports Fountain, plain text, and Markdown formats
- Heuristic-based element detection (scene headings, character names, dialogue)
- Deterministic statistics (character counts, genre signals, page estimates)
- Knowledge graph extraction (556 nodes, 1325 edges from codebase analysis)

### 2. screenplay_analyzer (LLM-Based)
Uses a local Llama server for analysis. Produces findings with evidence verification.
- Scene summary generation (GBNF-grammar constrained)
- Dialogue analysis
- Findings generation with citation requirements
- Evidence verification (fuzzy matching, 0.72 threshold)
- Principles engine (Chekhov's Gun, promise/payoff detection)
- Rules context integration (craft knowledge base)

### 3. screenplay_cowriter (Interactive)
Interactive writing assistant with session management.
- Conversational interface (CLI REPL)
- Session/branch management (fork, switch, delete)
- Persona and mode switching
- Context-aware responses (script + analysis report)
- Model discovery (explicit > inherited > loaded)

## Key Design Decisions

### GBNF Grammar Constraints
All LLM output is constrained by GBNF grammars to ensure structured, parseable results.

### Evidence Verification
Every finding must be verified against source text using fuzzy matching (0.72 threshold). This is the core trust mechanism.

### Chunking with Backoff
Large scripts are chunked for analysis, with backoff for failed chunks.

### Principles Engine
Chekhov's Gun and other craft principles are detected automatically.

### Stage-Based Manifest
The pipeline is resumable — each stage (parse, analyze, chat) has its own status.

## Knowledge Graph Statistics
- **556 nodes** extracted from 49 code + 5 doc files
- **1325 edges** (relationships between entities)
- **22 communities** detected and labeled
- **God nodes**: ProjectManifest (51 edges), Orchestrator (40 edges), ScriptDocument (39 edges)

## File Structure
```
screenplay-studio_1/
├── screenplay_parser/        # Deterministic parsing
│   ├── models.py
│   ├── text_parser.py
│   ├── heuristics.py
│   ├── stats.py
│   └── knowledge_graph.py
├── screenplay_analyzer/      # LLM-based analysis
│   ├── pipeline.py
│   ├── prompts.py
│   ├── grammar.py
│   ├── verifier.py
│   ├── principles_engine.py
│   ├── report.py
│   ├── rules_context.py
│   └── llm_client.py
├── screenplay_cowriter/      # Interactive writing
│   ├── engine.py
│   ├── models.py
│   ├── context.py
│   ├── personas.py
│   ├── cli.py
│   ├── store.py
│   └── discovery.py
├── screenplay_studio/        # Orchestrator & CLI
│   ├── orchestrator.py
│   ├── manifest.py
│   ├── webapp_server.py
│   ├── cli.py
│   └── __init__.py
├── knowledge_base/           # Rules & principles
│   ├── knowledge_base.py
│   └── __init__.py
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PROJECT_OVERVIEW.md
│   └── source/               # Per-file documentation (24 files)
├── tests/
├── pyproject.toml
└── README.md
```

## Graph Analysis Highlights

### Surprising Connections
- `KnowledgeBase` is wired into analyzer prompts (the actual fix for rules integration)
- Evidence verification connects to `ScriptDocument` (the single biggest trust problem)
- Sliding-window fuzzy match compares quotes against haystack text

### Suggested Questions
- Why does `ScriptDocument` connect Parser & Knowledge Graph to CLI & Formatting? (High betweenness: 0.244)
- Why does `ProjectManifest` connect Studio Manifest & Tests to Docstrings & Comments? (High betweenness: 0.180)
- Why does `Orchestrator` connect Docstrings & Comments to Parser & Knowledge Graph? (High betweenness: 0.136)

### Inferred Relationships Needing Verification
- `ProjectManifest`: 41 inferred edges
- `Orchestrator`: 33 inferred edges
- `ScriptDocument`: 34 inferred edges
- `LlamaServerClient`: 20 inferred edges
