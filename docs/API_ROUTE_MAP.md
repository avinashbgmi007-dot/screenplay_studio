# API Route Map — Screenplay Studio Webapp

> **Generated from source:** 2026-09-06. Authoritative source of truth:
> `screenplay_studio/webapp_server.py` (Flask, port 8500) and
> `screenplay_studio/demo_model.py` (built-in demo craft model). Regenerate this
> file after adding or changing any `@app.route` in those modules.
>
> Companion docs: `docs/STATE_STORES.md` (what each endpoint reads/writes),
> `docs/UI_UX_SPECIFICATION.md` §9 (request/response shapes, error codes, SSE
> contract), `docs/DATA_FORMATS.md` (JSON schemas).

## Conventions

- Every business endpoint is prefixed `/api` and served by a single Flask process
  on `http://localhost:8500` (the same process also serves the static SPA).
- Project-scoped routes use `<name>`; chat routes add `<sid>` (session id);
  idea routes use `<idea_id>`; finding routes use `<int:index>`.
- The demo craft model runs as a **separate** Flask app (`demo_app`) exposing the
  OpenAI-compatible `/v1/models` and `/v1/chat/completions` (non-streaming + SSE).
- There is **no** standalone `server.py` (the `docs/CODEBASE_MAP.md` entry is
  stale). The only HTTP servers are `webapp_server.py` and the demo `demo_app`.

**Totals:** 84 endpoints in `webapp_server.py` + 2 in `demo_model.py` = **86**.

---

## Static / root

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/` | `index` | Serve the SPA `index.html`. |
| GET | `/<path:filename>` | `static_files` | Serve a static asset from `webapp/`. |

## Config & connection

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/api/health` | `health` | Liveness/health probe. |
| GET | `/api/config` | `get_config` | Read server config (server_url, model, fast_model, timeout, personas, modes). |
| POST | `/api/config` | `set_config` | Update server config (validated `ServerConfig`). |
| POST | `/api/test-connection` | `test_connection` | Probe the configured llama-server. |
| GET | `/api/real-server-check` | `real_server_check` | Report whether a real model is reachable (vs built-in demo). |

## Projects (collection)

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/api/projects` | `list_projects` | List all projects on the shelf. |
| POST | `/api/projects` | `create_project` | Upload/parse a new screenplay into a Project. |
| POST | `/api/sample` | `create_sample_project` | Create a sample project (dedup-guarded). |

## Projects (single)

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/api/projects/<name>` | `get_project` | Project summary (`_manifest_summary`). |
| DELETE | `/api/projects/<name>` | `delete_project` | Delete a project (guarded inside `PROJECTS_DIR`). |
| POST | `/api/projects/<name>/analyze` | `analyze_project` | Run the 12-pass analysis (resumable; `?force` resets). |
| POST | `/api/projects/<name>/analyze/retry-failed` | `retry_failed_categories` | Re-run only failed analysis categories. |
| POST | `/api/projects/<name>/reparse` | `reparse_project` | Re-parse source, regenerate KG, invalidate analysis. |
| GET | `/api/projects/<name>/backup` | `backup_project` | Download the whole project dir as a zip. |
| GET | `/api/projects/<name>/report` | `get_report` | Get the report (findings sanitized at serve time). |
| GET | `/api/projects/<name>/report/export` | `export_report` | Export the report as `.md`. |
| GET | `/api/projects/<name>/characters` | `get_character_tracks` | Assemble per-character track (KG + report, no model). |
| GET | `/api/projects/<name>/progress` | `get_progress` | Analysis progress / stage statuses. |
| GET | `/api/projects/<name>/fixqueue` | `get_fixqueue` | Severity-sorted worklist (findings + dismissal + addressed state). |
| GET | `/api/projects/<name>/metrics` | `get_metrics` | Desk metrics summary. |
| POST | `/api/projects/<name>/premise` | `save_project_premise` | Save/update the premise card (post-graduation). |
| GET | `/api/projects/<name>/script` | `get_script` | Serve the working copy (ScriptDocument). |
| POST | `/api/projects/<name>/findings/<int:index>/dismiss` | `dismiss_finding_route` | Triage a finding away (restorable). |
| POST | `/api/projects/<name>/findings/<int:index>/undismiss` | `undismiss_finding_route` | Restore a dismissed finding. |

## Stash

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/api/projects/<name>/stash` | `get_stash` | List saved snippets. |
| POST | `/api/projects/<name>/stash` | `add_stash` | Save a snippet to the Stash. |
| DELETE | `/api/projects/<name>/stash/<entry_id>` | `delete_stash_entry` | Remove a Stash entry. |

## Margin notes

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/api/projects/<name>/notes` | `get_notes` | List margin notes. |
| POST | `/api/projects/<name>/notes` | `add_note_endpoint` | Add a margin note (pinned to scene/line). |
| PATCH | `/api/projects/<name>/notes/<note_id>` | `update_note_endpoint` | Edit a margin note. |
| DELETE | `/api/projects/<name>/notes/<note_id>` | `delete_note_endpoint` | Delete a margin note. |

## Revision / edits

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/api/projects/<name>/edits` | `get_edits` | Current edit log + redo availability. |
| POST | `/api/projects/<name>/rewrite` | `rewrite_scene_endpoint` | Request doctor's replacement candidates for a scene. |
| POST | `/api/projects/<name>/edits/apply` | `apply_edits` | Apply accepted replacements to the working copy. |
| POST | `/api/projects/<name>/edits/undo` | `undo_edits` | Undo last applied edit. |
| POST | `/api/projects/<name>/edits/redo` | `redo_edits` | Redo last undone edit. |
| POST | `/api/projects/<name>/edits/reset` | `reset_edits` | Discard working-copy edits (back to source). |
| GET | `/api/projects/<name>/export` | `export_script` | Export the working copy (e.g. `.fountain`). |

## Beat board

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/api/projects/<name>/beatboard` | `get_beatboard` | Current saved scene order. |
| PUT | `/api/projects/<name>/beatboard` | `put_beatboard` | Save a reordered scene permutation. |
| POST | `/api/projects/<name>/beatboard/reset` | `reset_beatboard` | Restore original scene order. |
| GET | `/api/projects/<name>/beatboard/export` | `export_beatboard` | Export reordered draft (`.fountain`). |

## Drafts & diff

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/api/projects/<name>/drafts` | `list_drafts` | List named drafts. |
| POST | `/api/projects/<name>/drafts` | `upload_draft` | Upload a new draft snapshot. |
| POST | `/api/projects/<name>/drafts/activate` | `activate_draft_endpoint` | Set the active draft. |
| GET | `/api/projects/<name>/diff` | `get_diff` | Diff working copy against a draft (line-level). |
| GET | `/api/projects/<name>/compare` | `get_compare` | Compare two drafts (scenes + findings). |

## Chat — project

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| POST | `/api/projects/<name>/chat/start` | `start_chat` | Start a chat session (defaults to `writing_partner`/`peer`). |
| GET | `/api/projects/<name>/chat/sessions/<sid>` | `get_session` | Get a session (messages, branches, settings). |
| DELETE | `/api/projects/<name>/chat/sessions/<sid>` | `delete_session` | Delete a session. |
| POST | `/api/projects/<name>/chat/sessions/<sid>/messages` | `send_message` | Send a turn (blocking reply). |
| POST | `/api/projects/<name>/chat/sessions/<sid>/messages/stream` | `send_message_stream` | Send a turn (SSE token stream). |
| POST | `/api/projects/<name>/chat/sessions/<sid>/fork` | `fork_session` | Fork a branch. |
| POST | `/api/projects/<name>/chat/sessions/<sid>/switch` | `switch_branch` | Switch active branch. |
| POST | `/api/projects/<name>/chat/sessions/<sid>/settings` | `update_settings` | Set persona/mode; reset to partner. |
| POST | `/api/projects/<name>/chat/sessions/<sid>/translate` | `project_translate_message` | Translate a reply (display-only). |

## Chat — idea (mirrors project)

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| POST | `/api/ideas/<idea_id>/chat/start` | `start_idea_chat` | Start an Idea chat session. |
| GET | `/api/ideas/<idea_id>/chat/sessions/<sid>` | `idea_get_session` | Get an Idea session. |
| DELETE | `/api/ideas/<idea_id>/chat/sessions/<sid>` | `idea_delete_session` | Delete an Idea session. |
| POST | `/api/ideas/<idea_id>/chat/sessions/<sid>/messages` | `idea_send_message` | Send an Idea turn (blocking). |
| POST | `/api/ideas/<idea_id>/chat/sessions/<sid>/messages/stream` | `send_idea_message_stream` | Send an Idea turn (SSE). |
| POST | `/api/ideas/<idea_id>/chat/sessions/<sid>/translate` | `idea_translate_message` | Translate an Idea reply. |
| POST | `/api/ideas/<idea_id>/chat/sessions/<sid>/settings` | `idea_update_settings` | Set Idea persona/mode. |

## Writer memory & library

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/api/writer-memory` | `get_writer_memory` | Writer profile + relationship card. |
| POST | `/api/writer-memory/observations/<obs_id>/suppress` | `suppress_writer_observation` | Forget a scoped observation. |
| POST | `/api/writer-memory/refresh` | `refresh_writer_memory` | Recompute the relationship card. |
| GET | `/api/writer-library` | `get_writer_library` | Digest of every parsed project (PAST WORK block). |

## Ideas (collection + single)

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/api/ideas` | `list_ideas` | List ideas. |
| POST | `/api/ideas` | `create_idea` | Create a new Idea (scriptless embryo). |
| GET | `/api/ideas/<idea_id>` | `get_idea` | Get an Idea (page + card). |
| POST | `/api/ideas/<idea_id>/content` | `save_idea_content` | Autosave the Idea page. |
| POST | `/api/ideas/<idea_id>/rename` | `rename_idea` | Rename an Idea. |
| POST | `/api/ideas/<idea_id>/card` | `save_idea_card` | Save the premise card. |
| DELETE | `/api/ideas/<idea_id>` | `delete_idea` | Delete an Idea. |
| POST | `/api/ideas/<idea_id>/graduate` | `graduate_idea` | Turn an Idea into a Project. |

## Preview lab (Design Lab prototypes)

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/api/preview/projects` | `preview_projects` | List projects available to the preview lab. |
| GET | `/api/preview/data/<name>` | `preview_data` | Get preview data for a project. |
| GET | `/api/preview/chat/<name>` | `preview_chat_get` | Read the isolated preview-lab session. |
| POST | `/api/preview/chat/<name>` | `preview_chat_send` | Send to the preview-lab session. |
| DELETE | `/api/preview/chat/<name>` | `preview_chat_clear` | Clear the preview-lab session. |

## Speech-to-text

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| POST | `/api/stt` | `stt_transcribe` | Transcribe audio (optional `faster-whisper`). |
| GET | `/api/stt/languages` | `stt_languages` | List supported STT languages. |

## Demo craft model (separate `demo_app`)

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/v1/models` | `models` | Advertise `demo-craft-model`. |
| POST | `/v1/chat/completions` | `chat_completions` | Non-streaming + SSE persona-distinct replies. |
