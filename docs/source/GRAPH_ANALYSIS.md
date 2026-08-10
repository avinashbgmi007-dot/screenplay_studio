# Knowledge Graph Analysis

## Extraction Results
- **AST extraction**: 527 nodes, 1214 edges (from 49 code files)
- **Semantic extraction**: 29 nodes, 111 edges (from 5 doc files)
- **Merged graph**: 556 nodes, 1325 edges, 22 communities

## God Nodes (Most Connected)
| Rank | Node | Edges |
|------|------|-------|
| 1 | ProjectManifest | 51 |
| 2 | Orchestrator | 40 |
| 3 | ScriptDocument | 39 |
| 4 | LlamaServerClient | 28 |
| 5 | OrchestratorError | 24 |
| 6 | ElementType | 23 |
| 7 | $() | 23 |
| 8 | LlamaServerError | 21 |
| 9 | SessionStore | 18 |
| 10 | CoWriterEngine | 17 |

## Cross-Community Bridges (High Betweenness)
| Node | Betweenness | Bridges |
|------|-------------|---------|
| ScriptDocument | 0.244 | Parser → Knowledge Graph → CLI → Formatting |
| ProjectManifest | 0.180 | Studio Manifest → Docstrings → E2E Tests → Web Tests |
| Orchestrator | 0.136 | Docstrings → Parser → Knowledge Graph → E2E Tests |

## Inferred Relationships (Need Verification)
| Node | Count | Examples |
|------|-------|----------|
| ProjectManifest | 41 | "CLI for screenplay_studio", "Hands off to interactive loop" |
| Orchestrator | 33 | "CLI for screenplay_studio", "Hands off to interactive loop" |
| ScriptDocument | 34 | "CLI for screenplay_studio", "Formatting & compliance checks" |
| LlamaServerClient | 20 | "CLI for screenplay_studio", "_NullRulesContext" |

## Surprising Connections
- `Wires the craft knowledge base into analyzer prompts` — KnowledgeBase → RulesContext
- `Evidence verification` — verifier.py → ScriptDocument
- `Sliding-window fuzzy match` — verifier.py → ScriptDocument
- `Mutates finding dict with verification block` — verifier.py → ScriptDocument
- `Lightweight listing` — store.py → Session

## Visualization
- HTML visualization: `graphify-out/graph.html`
- Graph data: `graphify-out/graph.json`
- Analysis: `graphify-out/GRAPH_REPORT.md`
