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
├── working.json             <- edit working copy (ScriptDocument schema)
├── edits.json               <- undo log of applied edits
├── edits.redo.json          <- redo stack
├── dismissed_findings.json  <- finding triage (dismissed indexes)
├── finding_marks.json       <- GO 2 writer-intent store (mark-addressed / defer)
├── last_pass.json           <- GO 2 scorekeeping snapshot (mtime-guarded diff)
├── notes.json               <- margin notes (writer's)
├── stash.json               <- saved passages (the Stash)
├── beatboard.json           <- saved scene order
├── metrics.json             <- desk metrics (reply/analysis timings, fix counts)
├── premise.json             <- premise card (when graduated from an idea)
├── sessions/                <- Piece 3: one JSON per chat session
└── drafts/                  <- draft snapshots (name -> {source copy, parsed.json,
                                report.findings.json, report.md}; includes "original")
```

> **Writer-level (outside any project):** `studio_projects/writer_profile.json` is the writer
> relationship memory shared across all projects (see below).

## writer_profile.json — writer relationship memory (v2)

Writer-level file (sibling of the project directories, read/written by the webapp; the cowriter
CLI/server opt in via `--memory-path`). Sam's gradually-learned sense of how the writer likes
to work. See `docs/superpowers/specs/2026-08-12-writer-relationship-memory-design.md` for the full
rationale.

```jsonc
{
  "version": 2,
  "dimensions": {                        // one per learnable dimension (8 total)
    "detail_level": {
      "value": "short",                  // learnable pole ("balanced"/"medium" = neutral, never gates)
      "confidence": 0.71,                // (pos + 2) / (pos + neg + 4); gates behavior at >= 0.6 with >= 3 evidence
      "evidence": { "pos": 5, "neg": 1 },
      "last_updated": 1754980000
    },
    "directness": { ... },               // full set: detail_level, directness, probe_appetite,
    "pushback_appetite": { ... },        //   support_style, feedback_tolerance, mentor_style,
    "support_style": { ... },            //   energy_level
    "feedback_tolerance": { ... },
    "mentor_style": { ... },
    "energy_level": { ... }
  },
  "topic_gravity": { "character": 12, "structure": 6, "dialogue": 3, "craft": 1 },
  "observations": [                      // the editable trail shown in "Sam's notes on you"
    { "id": "obs_1a2b3c", "text": "You want the note straight — no softening.",
      "dimension": "directness", "confidence": 0.71, "source": "rules",
      "scope": "global",                 // "global" | "project:<id>" | "idea:<id>"
      "contradictions": 0, "suppressed": false, "created": 1754980000, "updated": 1754980000 }
  ],
  "meta": { "total_turns_observed": 214, "turns_at_last_refresh": 204,
            "last_refresh": null, "refresh_count": 0 }
}
```

- `source` is `"rules"` (auto-template when a dimension first gates) or `"refresh"` (LLM session refresh).
- `scope` is added to all older observations by the v2 migration on load; scoped observations
  are kept per project/idea, global ones apply everywhere.
- `suppressed: true` is the permanent "forget this" (explicit override outranks inference).
- The relationship card injected into the system prompt is built from gated dimensions only.
- A corrupt profile is backed up to `writer_profile.json.bak` and replaced with a fresh one.

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
      "verification": {"status": "verified", "matched_scene": 1, "confidence": 0.95, "note": null}
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
      "issue": "…",                       //   scene_function | plot_thread | genre |
      "why_it_matters": "…",              //   continuity | voice | subtext (deterministic)
      "severity": "low",                  // low | medium | high
      "scene_refs": [1],
      "evidence_quote": "I'll tell you everything when this is over.",  // null when reasoning-only
      "rule_id": null,                    // knowledge-base rule id when grounded
      "verification": {
        "status": "verified",             // verified | not_found | no_quote | scene_not_found
        "matched_scene": 1,               // scene the quote matched in (verified only)
        "confidence": 0.95,
        "note": null
      }
    }
  ],
  "setup_payoff": [                       // the ledger (end-of-pipeline whole-script audit)
    {
      "setup": "MARA loads the revolver in scene 1",
      "kind": "prop",                     // prop | promise | trait | skill | information
      "setup_scenes": [1],
      "payoff_scenes": [9],
      "status": "paid",                   // paid | dangling | abandoned | red_herring
      "note": "…"                         // dangling entries fold into Plot Economy findings
    }
  ],
  "character_dials": [                    // per-character trait sliders (top ≤8 characters)
    {
      "character": "MARA",
      "traits": [
        {"trait": "agency", "score": 7, "scene_refs": [1, 4], "note": "…"}  // score 1-10
      ]
    }
  ],
  "pacing": [                             // deterministic per-scene pacing
    {
      "scene_number": 1,
      "words": 120, "beats": 3, "density": 0.5, "action_share": 0.7,
      "pace_score": 0.8, "drag": false    // drag = below-threshold pace (max 4 drags flagged)
    }
  ],
  "formatting_findings": [
    {"severity": "low", "scene_refs": [2], "message": "Missing time-of-day"}
  ],
  "stats": {                              // deterministic analytics (see screenplay_parser.stats)
    "title": "My Script", "author": "Me", "scene_count": 12,
    "estimated_page_count": 25.0, "character_count": 8, "parse_confidence": "high",
    "acts": [{"name": "Act 1", "scene_count": 4, "page_start": 1.0, "page_end": 10.0, "scene_numbers": [1,2,3,4]}],
    "pacing": {"total_pages": 25.0, "segment_pages": 10,
               "segments": [{"page_start": 1, "page_end": 10, "dialogue_words": 120, "action_words": 300, "scene_count": 4}]},
    "character_arc": [{"character": "MARA", "first_scene": 1, "last_scene": 3, "scene_count": 3,
                       "dialogue_lines": 4, "scene_presence_pct": 25.0, "quiet_gaps": null,
                       "appears_throughout": false}],
    "character_stats": {"total_dialogue_lines": 12, "characters": [{"character": "MARA", "dialogue_lines": 4, "dialogue_words": 40, "scenes_present": 3, "dialogue_share_pct": 66.7}]},
    "dialogue_action_ratio": {"dialogue_pct": 40.0, "action_pct": 60.0, "dialogue_words": 120, "action_words": 300},
    "location_usage": {"unique_locations": 2, "usage": [{"location": "STUDY", "scene_count": 3}]},
    "int_ext_and_time_breakdown": {"night_scene_pct": 50.0, "int_ext_breakdown": {...}, "time_of_day_breakdown": {...}, "night_scene_count": 6},
    "scene_length_stats": {...}, "scene_estimates": [...], "runtime_minutes": 25.0
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
  "fast_model": null,                     // optional fast model for short calls
  "timeout": 600,
  "stages": {
    "parse":   {"status": "complete", "output_paths": {"parsed": "./proj/parsed.json", "kg": "./proj/parsed.kg.json"}, "error": null, "updated_at": 0.0},
    "analyze": {"status": "complete", "output_paths": {"report_md": "./proj/report.md", "report_findings": "./proj/report.findings.json", "category_outcomes": {...}, "failed_categories": []}, "error": null, "updated_at": 0.0},
    "chat":    {"status": "complete", "output_paths": {"session_id": "abc12345"}, "error": null, "updated_at": 0.0}
  },
  "cowriter_session_id": "abc12345",
  "drafts": [{"name": "draft-1", "source_filename": "draft-1.fountain", "uploaded_at": 0.0}],
  "active_draft": null,
  "report_language": "eng",               // eng | tenglish | hindi | telugu | tamil
  "created_at": 0.0,
  "updated_at": 0.0
}
```

Stage `status` values: `pending | running | complete | failed | skipped`.

Resume semantics:
- `complete` stages are never re-run.
- A **total** analyze failure (nothing usable produced) → `failed` → rerun on next `run`/`resume`.
- A **partial** analyze failure (some categories succeeded) → `complete` with `partial_errors`
  in `output_paths`; the report is still usable. Failed categories are kept in
  `failed_categories` so `--retry-failed` / the ⚠ Retry failed button re-runs just those
  (merged into the existing report).

## progress.json — live analysis progress

Written by the orchestrator's progress callback during `analyze`; overwritten at each stage
boundary. Every write stamps a `ts` heartbeat (used by the webapp for stall detection):

```json
{"stage": "dialogue", "status": "running", "detail": "Reading dialogue & action", "ts": 1754980000.0}
```

Final states: `{"stage": "done", "status": "complete", "detail": "Analysis complete", "ts": …}`
or `{"stage": "failed", "status": "failed", "detail": "<error>", "ts": …}`.

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
      "active_persona": "writing_partner",   // default persona
      "active_mode": "peer",                 // default mode
      "awaiting_probe": false,             // peer-guardrail state (probes await an answer)
      "created_at": 0.0,
      "messages": [
        {
          "role": "user",                // user | assistant | system
          "content": "…",
          "timestamp": 0.0,
          "mode": "peer",
          "scene_refs": [1],             // scenes injected into context this turn
          "quote": {"scene_number": 1, "text": "…"},  // select-to-reply passage (optional)
          "partner": "script_consultant" // persona this turn was spoken with (writing_partner |
                                         // script_consultant); null on legacy messages — the
                                         // FV columns scope by it and fall back to the old
                                         // assistant-only view when absent
        }
      ]
    }
  },
  "current_branch": "main",
  "last_seen_content": "…",              // last script content this session saw (stale-session honesty)
  "created_at": 0.0,
  "updated_at": 0.0
}
```

## Project-level stores (webapp, all JSON arrays/dicts beside the manifest)

All written atomically (`jsonio.atomic_write_json`). Schemas (top level):

- **stash.json** — the Stash. Array of `{id, text (≤4000 chars), title (≤120), scene_number: int|null, created_at}`, newest first.
- **notes.json** — margin notes. Array of `{id, scene_number: int|null, text, anchor: str|null, created_at, updated_at}`.
- **beatboard.json** — saved scene order. `{"order": [scene numbers], "saved_at": ts}`.
- **metrics.json** — desk metrics. `{analysis_seconds, last_analysis_ts, reply_seconds (rolling ≤40), discussed, findings_open, findings_total}`.
- **working.json** — edit working copy; full ScriptDocument schema (same as parsed.json).
- **edits.json** — undo log. Array of `{id, scene_number, applied: [{old, new, similarity}], skipped: [{old, new, reason}], applied_at}`.
- **edits.redo.json** — redo stack; same record shape as edits.json.
- **dismissed_findings.json** — triage. Array of `{index: int, issue: str}`. (The fix queue
  itself is computed per-request from findings + dismissals + working copy — no file.)
  Entries gain `finding_id` when written by the GO 1+ client (legacy entries keep the
  `(index, issue)` shape and keep working).
- **finding_marks.json** — GO 2 writer-intent store (mark-addressed + defer). Dict
  `{<finding_id>: "addressed" | "deferred"}`. Id-keyed via GO 1 identity
  (category + evidence_quote hash), so marks survive report regeneration, re-scores and
  scene shifts; writer intent wins display, observed status stays visible on the card.
  Read by `findingDisposition` (app.js) before any computed status; deferred findings
  dim, leave open counts, and carry a "next pass" chip. Served on `/edits` as
  `finding_intents`; written via POST `/api/projects/<name>/findings/intent`.
- **last_pass.json** — GO 2 scorekeeping snapshot, computed lazily with an **(mtime,
  content-signature) guard** when `/edits` serves a newer report (one generation back;
  honest `null` on the first pass). The signature (`report_sig` = SHA-1 over the distinct
  finding ids) closes the same-tick hole the mtime alone cannot: a report rewritten within
  one filesystem timestamp tick keeps the same mtime, so an mtime-only guard would serve a
  stale payload (`null` after arithmetic exists, or stale Fixed/New). `{ids, issues,
  report_mtime, report_sig, payload}` where `payload` = `{last_total, still_live, fixed,
  new, ghosted_marks}` and `ghosted_marks` are finding ids the writer addressed/deferred
  that are absent from the new pass (filled only from real intents, never fabricated).
  **All counts are DISTINCT-id counts** — duplicate finding ids (same category + same
  quote/issue) are one finding, so a no-op re-analysis always reports `fixed=0, new=0`,
  never phantom progress. Drives the dock's **arrival strip pass line** — which compares
  analysis passes, NOT writer edits (both passes read the parse-of-record, so writer edits
  can never move these numbers; the writer's own progress rides `findings_status` and the
  strip's draft clause).
- **premise.json** — premise card, present when the project graduated from an idea:
  `{title, logline, premise, questions: [str], content}` (`content` only added on graduation).

## Idea store (writer-level, `<PROJECTS_DIR>/ideas/`)

- **ideas/&lt;idea_id&gt;/idea.json** — `{id, title, created_at, updated_at,
  card: {title, logline, premise, questions}, content, auto_title: bool}`.
- **ideas/&lt;idea_id&gt;/sessions/&lt;sid&gt;.json** — idea chat sessions; same schema as
  project `sessions/<id>.json` above.
- Idea sessions use the same fixed-id pattern for the preview lab:
  `<project>/sessions/preview-lab.json` is an isolated lab session (deletable; never the
  manifest-pinned one).
