# Data Formats

The pieces communicate through JSON files written to the project directory — they read each other's output as plain dicts and never import each other at module load. This page documents every file format in the pipeline.

## Project directory layout

Every project is a self-contained directory (created by `screenplay_studio run`):

```
my_project/
├── project.json            <- manifest (stage status, resume state)
├── source.fountain          <- copy of the original screenplay
├── parsed.json              <- Piece 1: ScriptDocument
├── parsed.kg.json           <- Piece 1: knowledge graph (candidates)
├── report.md                <- Piece 2: human-readable report
├── report.findings.json     <- Piece 2: structured findings
├── progress.json            <- live per-stage analysis progress
├── sessions/                <- Piece 3: one JSON per chat session
└── drafts/                  <- draft snapshots (name -> files)
```

> **Writer-level (outside any project):** `studio_projects/writer_profile.json` is the writer
> relationship memory shared across all projects (see below).

## writer_profile.json — writer relationship memory (v2)

Writer-level file (sibling of the project directories, read/written by the webapp; the cowriter
CLI/server opt in via `--memory-path`). Sam's gradually-learned sense of how the writer likes to
work. See `docs/superpowers/specs/2026-08-12-writer-relationship-memory-design.md` for the full
rationale.

```jsonc
{
  "version": 1,
  "dimensions": {                        // one per learnable dimension
    "detail_level": {
      "value": "short",                  // learnable pole ("balanced"/"medium" = neutral, never gates)
      "confidence": 0.71,                // (pos + 2) / (pos + neg + 4); gates behavior at >= 0.6 with >= 3 evidence
      "evidence": { "pos": 5, "neg": 1 },
      "last_updated": 1754980000
    },
    "directness": { ... },
    "probe_appetite": { ... },
    "pushback_appetite": { ... }
  },
  "topic_gravity": { "character": 12, "structure": 6, "dialogue": 3, "craft": 1 },
  "observations": [                      // the editable trail shown in "Sam's notes on you"
    { "id": "obs_1a2b3c", "text": "You want the note straight — no softening.",
      "dimension": "directness", "confidence": 0.71, "source": "rules",
      "contradictions": 0, "suppressed": false, "created": 1754980000, "updated": 1754980000 }
  ],
  "meta": { "total_turns_observed": 214, "turns_at_last_refresh": 204,
            "last_refresh": null, "refresh_count": 0 }
}
```

- `source` is `"rules"` (auto-template when a dimension first gates) or `"refresh"` (LLM session refresh).
- `suppressed: true` is the permanent "forget this" (explicit override outranks inference).
- The relationship card injected into the system prompt is built from gated dimensions only.

## parsed.json — ScriptDocument (Piece 1)

```jsonc
{
  "title": "My Script",
  "author": "Me",
  "source_format": "fountain",          // fdx | pdf | txt | fountain | md
  "source_filename": "script.fountain",
  "parse_confidence": "high",           // high | medium | low (OCR = low)
  "scene_count": 12,
  "estimated_page_count": 25.0,         // null when unknown
  "all_characters": ["MARA", "DEREK"],
  "front_matter": [],                    // title-page / unclassified elements
  "scenes": [
    {
      "scene_number": 1,
      "heading_raw": "INT. STUDY - NIGHT",
      "int_ext": "INT",                  // INT | EXT | INT/EXT | null
      "location": "STUDY",
      "time_of_day": "NIGHT",
      "page_start": 1.0,
      "page_end": 1.5,                   // float | null
      "characters_present": ["MARA"],
      "elements": [
        {
          "type": "scene_heading",       // scene_heading | action | character | dialogue |
          "text": "INT. STUDY - NIGHT",  //   parenthetical | transition | shot | general
          "character": null,             // set for dialogue/parenthetical
          "line_start": 1                // source line number | null
        }
      ]
    }
  ],
  "warnings": [
    {"message": "…", "scene_number": 2, "severity": "warning"}  // info | warning | error
  ]
}
```

## parsed.kg.json — knowledge graph (Piece 1, candidate generator)

```jsonc
{
  "characters": {
    "MARA": {
      "name": "MARA",
      "scenes_present": [1, 2, 3],
      "scene_dialogue_counts": {"1": 2, "2": 1},
      "first_scene": 1,
      "last_scene": 3,
      "trait_mentions": [
        {"scene_number": 1, "text": "30s, unshaven", "kind": "age"}  // age | descriptor
      ]
    }
  },
  "prop_candidates": [
    {
      "name": "REVOLVER",
      "scenes_mentioned": [1, 3],       // must recur in 2+ scenes to qualify
      "mention_count": 3,
      "mention_texts": [{"scene": 1, "text": "…an old REVOLVER…"}]
    }
  ],
  "timeline": [
    {
      "scene_number": 1,
      "int_ext": "INT",
      "time_of_day": "NIGHT",
      "explicit_markers": ["LATER"]       // time-skip / date markers found
    }
  ],
  "promise_candidates": [
    {
      "scene_number": 1,
      "character": "MARA",
      "text": "I'll tell you everything when this is over.",
      "pattern_matched": "I'll tell"
    }
  ],
  "character_cooccurrence": {
    "DEREK|MARA": [1]                     // "A|B" -> scenes where both appear
  }
}
```

## report.findings.json — structured analysis (Piece 2)

This is what Piece 3 loads to discuss findings. `report.md` renders the same content for humans.

```jsonc
{
  "title": "My Script",
  "source_filename": "script.fountain",
  "model_used": "model.gguf",
  "coverage": {                           // null if the coverage pass failed
    "logline": "…",
    "genre": "Drama",
    "tone": "Serious",
    "one_page_synopsis": "…",
    "strengths": ["…"],
    "weaknesses": ["…"],
    "comparable_films": ["Example Film"],
    "recommendation": "consider"          // consider | recommend | pass
  },
  "character_reads": [                    // character-perception pass
    {
      "character": "MARA",
      "how_reads": "Resolute and guarded.",
      "apparent_intent": "…",
      "gap": "…",
      "scene_refs": [1],
      "evidence_quote": "…",
      "verification": {"status": "verified", "score": 0.95, "note": null}
    }
  ],
  "logline_test": {
    "logline": "…",
    "signal": "workable",                 // strong | workable | muddled
    "what_works": "…",
    "what_muddles": "…",
    "missing": "…",
    "tightened": "…"
  },
  "findings": [
    {
      "category": "dialogue",             // theme | character | structure | dialogue |
      "issue": "…",                       //   scene_function | plot_thread | genre
      "why_it_matters": "…",
      "severity": "low",                  // low | medium | high
      "scene_refs": [1],
      "evidence_quote": "I'll tell you everything when this is over.",  // null when reasoning-only
      "rule_id": null,                    // knowledge-base rule id when grounded
      "verification": {
        "status": "verified",             // verified | not_found | no_quote | scene_not_found
        "score": 0.95,
        "note": null
      }
    }
  ],
  "formatting_findings": [
    {"severity": "low", "scene_refs": [2], "message": "Missing time-of-day"}
  ],
  "stats": {                              // deterministic analytics (see screenplay_parser.stats)
    "acts": [{"name": "Act One", "scene_count": 4, "page_start": 1.0, "page_end": 10.0, "scene_numbers": [1,2,3,4]}],
    "pacing": {"segments": [{"page_start": 1, "page_end": 10, "dialogue_words": 120, "action_words": 300, "scene_count": 4}]},
    "character_arc": [{"character": "MARA", "first_scene": 1, "last_scene": 3, "scene_count": 3, "dialogue_lines": 4}],
    "character_stats": {"characters": [{"character": "MARA", "dialogue_lines": 4, "dialogue_words": 40, "scenes_present": 3, "dialogue_share_pct": 66.7}]},
    "dialogue_action_ratio": {"dialogue_pct": 40.0, "action_pct": 60.0},
    "location_usage": {"unique_locations": 2, "usage": {}},
    "int_ext_and_time_breakdown": {"night_scene_pct": 50.0}
  },
  "verification_summary": {"verified": 3, "not_found": 0, "no_quote": 2, "scene_not_found": 0},
  "errors": []
}
```

## project.json — manifest (screenplay_studio)

```jsonc
{
  "project_dir": "./proj",
  "title": "My Script",
  "source_filename": "script.fountain",
  "source_format": ".fountain",
  "server_url": "http://localhost:8080",
  "model_id": null,                       // set after first successful analyze
  "timeout": 600,
  "stages": {
    "parse":   {"status": "complete", "output_paths": {"parsed": "./proj/parsed.json", "kg": "./proj/parsed.kg.json"}, "error": null, "updated_at": 0.0},
    "analyze": {"status": "complete", "output_paths": {"report_md": "./proj/report.md", "report_findings": "./proj/report.findings.json"}, "error": null, "updated_at": 0.0},
    "chat":    {"status": "pending", "output_paths": {}, "error": null, "updated_at": 0.0}
  },
  "cowriter_session_id": "abc12345",
  "drafts": [{"name": "draft-1", "source_filename": "draft-1.fountain", "uploaded_at": 0.0}],
  "active_draft": null,
  "report_language": "eng",               // eng | tenglish | hindi | tamil
  "created_at": 0.0,
  "updated_at": 0.0
}
```

Stage `status` values: `pending | running | complete | failed | skipped`.

Resume semantics:
- `complete` stages are never re-run.
- A **total** analyze failure (nothing usable produced) → `failed` → rerun on next `run`/`resume`.
- A **partial** analyze failure (some categories succeeded) → `complete` with `partial_errors` in `output_paths`; the report is still usable.

## progress.json — live analysis progress

Written by the analyzer's callback during `analyze`; overwritten at each stage boundary:

```json
{"stage": "dialogue", "status": "running", "detail": "Reading dialogue & action"}
```

Final states: `{"stage": "done", "status": "complete", "detail": "Analysis complete"}` or `{"stage": "failed", "status": "failed", "detail": "<error>"}`.

## sessions/<id>.json — co-writer session (Piece 3)

```jsonc
{
  "session_id": "abc12345",
  "title": "My Script",
  "report_path": "./proj/report.findings.json",
  "script_path": "./proj/parsed.json",
  "server_url": "http://localhost:8080",
  "model_id": "model.gguf",
  "branches": {
    "main": {
      "name": "main",
      "parent_branch": null,
      "forked_at_index": null,
      "active_persona": "script_consultant",
      "active_mode": "evidence_discussion",
      "created_at": 0.0,
      "messages": [
        {
          "role": "user",                // user | assistant | system
          "content": "…",
          "timestamp": 0.0,
          "mode": "evidence_discussion",
          "scene_refs": [1]              // scenes injected into context this turn
        }
      ]
    }
  },
  "current_branch": "main",
  "created_at": 0.0,
  "updated_at": 0.0
}
```
