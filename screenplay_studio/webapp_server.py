"""
Unified backend for the web UI. One process, one port: serves the static
frontend (webapp/index.html, style.css, app.js) AND the JSON API the
frontend calls. Internally this is a thin HTTP wrapper around the exact
same Orchestrator / SessionStore / CoWriterEngine used by the CLI — no
new pipeline logic lives here, just request/response plumbing.

Usage:
    python -m screenplay_studio.webapp_server --port 8500 --projects-dir ./studio_projects

Then open http://localhost:8500 in a browser.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import queue
import re
import threading
import time
import traceback
import zipfile

from flask import Flask, Response, request, jsonify, send_from_directory, send_file

from .ideas import IdeaStore
from .manifest import ProjectManifest
from .orchestrator import Orchestrator, OrchestratorError

WEBAPP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp")

app = Flask(__name__, static_folder=None)

# Set by main() at startup — kept module-level for simplicity, matching
# the same pattern already used in screenplay_cowriter/server.py.
PROJECTS_DIR = "./studio_projects"


class ServerConfig:
    """Process-wide server settings.

    A small holder instead of a bare module-level dict so the mutable state
    is contained: writes are validated, and `to_dict()` returns a copy so
    callers (and JSON responses) can't mutate the live config by reference.
    Kept dict-compatible (CONFIG["key"] / CONFIG["key"] = v) so existing
    callers and tests keep working unchanged.
    """

    # turn_timeout: per-chat-turn generation cap (the watchdog). A turn that
    # exceeds it surfaces a "still working?" prompt instead of a silent
    # multi-minute hang. Analysis calls keep the long `timeout` — only chat
    # turns run on the short clock.
    _DEFAULTS = {"server_url": "http://localhost:8080", "model": None, "timeout": 600,
                 "fast_model": None, "turn_timeout": 120}

    def __init__(self):
        self._data = dict(self._DEFAULTS)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        if key == "timeout":
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise ValueError("timeout must be an integer number of seconds")
            if value <= 0:
                raise ValueError("timeout must be positive")
        if key == "server_url":
            # None/empty means "not set" — keep the default rather than
            # storing a truthy "None" string.
            if value is None or value == "":
                value = self._DEFAULTS["server_url"]
            else:
                value = str(value).rstrip("/")
        if key in ("model", "fast_model") and value == "":
            value = None
        if key == "turn_timeout":
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise ValueError("turn_timeout must be an integer number of seconds")
            if value <= 0:
                raise ValueError("turn_timeout must be positive")
        self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

    def to_dict(self) -> dict:
        return dict(self._data)


CONFIG = ServerConfig()


# ---------- static frontend ----------

@app.route("/")
def index():
    resp = send_from_directory(WEBAPP_DIR, "index.html")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/<path:filename>")
def static_files(filename):
    resp = send_from_directory(WEBAPP_DIR, filename)
    # No-build-step app: always revalidate JS/CSS so edits show up on reload
    # instead of serving a stale cached copy.
    resp.headers["Cache-Control"] = "no-cache"
    return resp


# ---------- helpers ----------

def _project_dir(name: str) -> str:
    return os.path.join(PROJECTS_DIR, name)


def _load_manifest(name: str) -> ProjectManifest:
    return ProjectManifest.load(_project_dir(name))


def _manifest_summary(m: ProjectManifest) -> dict:
    sessions = []
    if os.path.isdir(m.sessions_dir):
        try:
            store_mod = _import_cowriter("store")
            store = store_mod.SessionStore(m.sessions_dir)
            sessions = store.list()
        except CowriterUnavailableError:
            sessions = []  # co-writer not installed — shelf still works
    from .revision import has_edits, edits_log
    return {
        "project": os.path.basename(m.project_dir),
        "title": m.title,
        "server_url": m.server_url,
        "model_id": m.model_id,
        "stages": {name: s.status for name, s in m.stages.items()},
        "errors": {name: s.error for name, s in m.stages.items() if s.error},
        "sessions": sessions,
        "has_edits": has_edits(m),
        "edit_count": len(edits_log(m)),
        "drafts": m.drafts,
        "active_draft": m.active_draft,
        "report_language": m.report_language,
        # categories that failed in the last analyze run (partial success) —
        # the frontend offers a one-click "retry failed" when this is non-empty
        "failed_categories": (m.stage("analyze").output_paths or {}).get("failed_categories") or [],
    }


def _make_client(m: ProjectManifest):
    from screenplay_analyzer.llm_client import LlamaServerClient
    return LlamaServerClient(base_url=m.server_url, model=m.model_id, timeout=m.timeout,
                             fast_model=m.fast_model)


def _sanitize_report(report: dict) -> dict:
    """Drop non-writing feedback (dialect identification, subtitle meta-
    commentary) from a stored report before it reaches the writer. Applied at
    serve time so projects analyzed before the filter existed display the
    same clean report without a re-analysis."""
    if not isinstance(report, dict):
        return report
    findings = report.get("findings")
    if isinstance(findings, list):
        from screenplay_analyzer.feedback_filter import filter_findings
        report = dict(report)
        report["findings"] = filter_findings(findings)
    return report


def _load_report_sanitized(m: ProjectManifest) -> dict:
    with open(m.report_findings_path, "r", encoding="utf-8") as f:
        return _sanitize_report(json.load(f))


def _error(message: str, status: int = 400):
    return jsonify({"error": message}), status


class CowriterUnavailableError(Exception):
    """screenplay_cowriter isn't installed — chat features can't work."""


def _import_cowriter(name: str):
    """Lazily import a module from screenplay_cowriter, converting an
    ImportError into a clean, actionable error instead of a traceback
    (the co-writer is an optional piece; the rest of the webapp must keep
    working when it's absent)."""
    import importlib
    try:
        return importlib.import_module(f"screenplay_cowriter.{name}")
    except ImportError as e:
        raise CowriterUnavailableError(
            "The co-writer package (screenplay_cowriter) isn't installed, so chat is unavailable. "
            f"Install it alongside screenplay_studio to enable chat. ({e})"
        ) from e


# ---------- config ----------

@app.route("/api/test-connection", methods=["POST"])
def test_connection():
    body = request.get_json() or {}
    url = (body.get("server_url") or CONFIG["server_url"]).rstrip("/")
    from screenplay_analyzer.llm_client import LlamaServerClient, LlamaServerError

    client = LlamaServerClient(base_url=url, timeout=15)
    try:
        models = client.list_models()
    except LlamaServerError as e:
        return jsonify({"ok": False, "message": str(e)})

    ids = [m.get("id") or m.get("name") for m in models if isinstance(m, dict)]
    ids = [i for i in ids if i]
    if not ids:
        return jsonify({"ok": False, "message": f"Connected to {url}, but it reports no loaded model."})
    return jsonify({"ok": True, "message": f"Connected — model loaded: {ids[0]}", "models": ids})


@app.route("/api/config", methods=["GET"])
def get_config():
    cfg = CONFIG.to_dict()
    # Personas/modes come from the co-writer so the frontend dropdown never
    # drifts from the server's canonical list (falls back to empty when the
    # co-writer isn't installed; the UI then shows its built-in defaults).
    try:
        personas_mod = _import_cowriter("personas")
        cfg["personas"] = list(personas_mod.PERSONAS.keys())
        cfg["modes"] = list(personas_mod.MODES.keys())
    except CowriterUnavailableError:
        cfg["personas"] = []
        cfg["modes"] = []
    return jsonify(cfg)


@app.route("/api/config", methods=["POST"])
def set_config():
    body = request.get_json() or {}
    if "server_url" in body:
        CONFIG["server_url"] = body["server_url"]
    if "model" in body:
        CONFIG["model"] = body["model"] or None
    if "fast_model" in body:
        CONFIG["fast_model"] = body["fast_model"] or None
    if "turn_timeout" in body:
        CONFIG["turn_timeout"] = body["turn_timeout"]
    if "timeout" in body:
        try:
            CONFIG["timeout"] = int(body["timeout"])
        except (TypeError, ValueError):
            pass  # invalid timeout ignored — keep the current value
    return jsonify(CONFIG.to_dict())


# ---------- projects ----------

@app.route("/api/projects", methods=["GET"])
def list_projects():
    if not os.path.isdir(PROJECTS_DIR):
        return jsonify([])
    out = []
    for name in sorted(os.listdir(PROJECTS_DIR)):
        try:
            m = ProjectManifest.load(_project_dir(name))
            out.append(_manifest_summary(m))
        except Exception:
            continue
    out.sort(key=lambda p: p.get("title", ""))
    return jsonify(out)


@app.route("/api/sample", methods=["POST"])
def create_sample_project():
    """One-click sample page: create a project from the built-in screenplay.
    Deduplicates by title — reopening the sample keeps one shelf entry."""
    from .sample import SAMPLE_TITLE, SAMPLE_SCRIPT

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in SAMPLE_TITLE) or "project"
    project_dir = _project_dir(safe_name)
    if os.path.exists(project_dir):
        try:
            m = ProjectManifest.load(project_dir)
            return jsonify(_manifest_summary(m))
        except Exception:
            pass  # corrupt dir — fall through and re-create

    os.makedirs(project_dir, exist_ok=True)
    tmp_path = os.path.join(project_dir, "_sample.fountain")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(SAMPLE_SCRIPT)

    try:
        manifest = ProjectManifest.create(project_dir, tmp_path, title=SAMPLE_TITLE)
        manifest.server_url = CONFIG["server_url"]
        manifest.timeout = CONFIG["timeout"]
        manifest.model_id = CONFIG["model"]
        manifest.save()
        os.remove(tmp_path)
        Orchestrator(manifest).run_parse()
    except Exception as e:
        return _error(f"Could not create the sample page: {e}", 500)

    return jsonify(_manifest_summary(manifest)), 201


@app.route("/api/projects", methods=["POST"])
def create_project():
    if "file" not in request.files:
        return _error("No file uploaded (expected multipart field 'file').")
    upload = request.files["file"]
    if not upload.filename:
        return _error("Empty filename.")

    title = request.form.get("title") or os.path.splitext(upload.filename)[0]
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in title) or "project"

    project_dir = _project_dir(safe_name)
    suffix = 1
    while os.path.exists(project_dir):
        suffix += 1
        project_dir = _project_dir(f"{safe_name}_{suffix}")

    os.makedirs(project_dir, exist_ok=True)
    ext = os.path.splitext(upload.filename)[1].lower() or ".txt"
    tmp_path = os.path.join(project_dir, f"_upload{ext}")
    upload.save(tmp_path)

    try:
        manifest = ProjectManifest.create(project_dir, tmp_path, title=title)
        manifest.server_url = CONFIG["server_url"]
        manifest.timeout = CONFIG["timeout"]
        manifest.model_id = CONFIG["model"]
        manifest.save()
        os.remove(tmp_path)

        orch = Orchestrator(manifest)
        orch.run_parse()
    except Exception as e:
        return _error(f"Could not process uploaded file: {e}", 500)

    return jsonify(_manifest_summary(manifest)), 201


@app.route("/api/projects/<name>", methods=["GET"])
def get_project(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    data = _manifest_summary(m)
    # An idea that graduated carries its premise card alongside the pages
    try:
        with open(os.path.join(m.project_dir, "premise.json"), "r", encoding="utf-8") as f:
            data["premise"] = json.load(f)
    except Exception:
        pass
    return jsonify(data)


@app.route("/api/projects/<name>", methods=["DELETE"])
def delete_project(name):
    """Remove a screenplay from the shelf (its project directory). Only the
    writer's own studio data is touched — never anything outside PROJECTS_DIR."""
    import shutil
    if not name or os.path.basename(name) != name:
        return _error("Invalid project name.", 400)
    project_dir = os.path.realpath(_project_dir(name))
    projects_root = os.path.realpath(PROJECTS_DIR)
    if not project_dir.startswith(projects_root + os.sep) and project_dir != projects_root:
        return _error("Invalid project path.", 400)
    if not os.path.isdir(project_dir) or not os.path.exists(os.path.join(project_dir, "project.json")):
        return _error("Project not found.", 404)
    shutil.rmtree(project_dir, ignore_errors=False)
    return jsonify({"ok": True, "project": name})


@app.route("/api/projects/<name>/analyze", methods=["POST"])
def analyze_project(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)

    m.server_url = CONFIG["server_url"]
    m.model_id = CONFIG["model"]
    m.fast_model = CONFIG["fast_model"]
    m.timeout = CONFIG["timeout"]
    m.save()

    # "Re-run Analysis" must actually re-run, even when a previous run
    # completed — the orchestrator short-circuits on complete by design
    # (so resume/retry never redoes finished work), so an explicit request
    # to re-analyze resets the stage first.
    body = request.get_json(silent=True) or {}
    if body.get("force"):
        from .manifest import StageStatus
        m.stages["analyze"] = StageStatus()
        if os.path.exists(m.report_findings_path):
            os.remove(m.report_findings_path)
        if os.path.exists(m.report_md_path):
            os.remove(m.report_md_path)
        if os.path.exists(m.progress_path):
            os.remove(m.progress_path)
        m.save()

    # report language: eng | tenglish | hindi | tamil — how the report reads
    report_language = body.get("report_language") or m.report_language or "eng"

    orch = Orchestrator(m)
    import time as _t
    _t0 = _t.time()
    try:
        orch.run_analyze(report_language=report_language)
    except OrchestratorError as e:
        return _error(str(e), 502)
    except Exception as e:
        traceback.print_exc()
        return _error(f"Unexpected error during analysis: {e}", 500)

    from .metrics import record_analysis
    record_analysis(m, _t.time() - _t0)
    return jsonify(_manifest_summary(m))


@app.route("/api/projects/<name>/analyze/retry-failed", methods=["POST"])
def retry_failed_categories(name):
    """Re-run ONLY the categories that failed in the last analyze run and
    merge into the existing report — the in-app face of --retry-failed.
    A partial analysis (genre gated, logline broke, server hiccup) no longer
    forces a full re-run."""
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    if m.stage("analyze").status != "complete":
        return _error("Analysis hasn't completed yet — run the full analysis first.", 400)

    m.server_url = CONFIG["server_url"]
    m.model_id = CONFIG["model"]
    m.fast_model = CONFIG["fast_model"]
    m.timeout = CONFIG["timeout"]
    m.save()

    orch = Orchestrator(m)
    import time as _t
    _t0 = _t.time()
    try:
        orch.run_analyze(retry_failed=True)
    except OrchestratorError as e:
        return _error(str(e), 502)
    except Exception as e:
        traceback.print_exc()
        return _error(f"Unexpected error during retry: {e}", 500)

    from .metrics import record_analysis
    record_analysis(m, _t.time() - _t0)
    return jsonify(_manifest_summary(m))


@app.route("/api/projects/<name>/backup", methods=["GET"])
def backup_project(name):
    """Whole-project backup as a single .zip — source, parse, knowledge graph,
    report, sessions, edits, notes, stash. The writer's archive of their own
    desk, one click, nothing leaves the machine."""
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)

    project_dir = os.path.realpath(m.project_dir)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(project_dir):
            for fname in files:
                full = os.path.join(root, fname)
                arcname = os.path.join(name, os.path.relpath(full, project_dir))
                try:
                    zf.write(full, arcname)
                except OSError:
                    continue  # a file vanishing mid-zip shouldn't kill the backup
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"{name}-backup.zip")


@app.route("/api/projects/<name>/reparse", methods=["POST"])
def reparse_project(name):
    """Re-run the parse stage on the active source file, in-app.

    The in-app fix for a mis-parsed script: re-parses the source with the
    current parser, regenerates parsed.json + the knowledge graph, refreshes
    the working copy (writer edits are preserved by revision.ensure_working),
    and invalidates the old analysis so the report/fix queue get rebuilt from
    the fresh parse on the next Run Analysis.
    """
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)

    # Re-parse must actually re-run even when parse is complete — the
    # orchestrator short-circuits on complete by design (so resume/retry never
    # redoes finished work), so an explicit re-parse resets the stage first.
    from .manifest import StageStatus
    m.stages["parse"] = StageStatus()
    m.save()

    orch = Orchestrator(m)
    try:
        orch.run_parse()
    except OrchestratorError as e:
        return _error(str(e), 502)
    except Exception as e:
        traceback.print_exc()
        return _error(f"Unexpected error during re-parse: {e}", 500)

    # The analysis (report, fix queue, findings) was built from the OLD parse
    # — it's now stale, so invalidate the analyze stage and drop its artifacts
    # so the next Run Analysis regenerates everything from the fresh parse.
    m.stages["analyze"] = StageStatus()
    m.save()
    for p in (m.report_findings_path, m.report_md_path, m.progress_path):
        if os.path.exists(p):
            os.remove(p)

    # Refresh the display copy from the fresh parse. revision.ensure_working
    # self-heals a stale working copy only when the writer has NO edits; if
    # edits exist, their work is preserved untouched (by design).
    from .revision import ensure_working
    try:
        ensure_working(m)
    except Exception:
        pass  # the viewer will rebuild it lazily on first load if this fails

    return jsonify(_manifest_summary(m))


@app.route("/api/projects/<name>/report", methods=["GET"])
def get_report(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    if m.stage("analyze").status != "complete":
        return _error("Analysis hasn't completed for this project yet.", 400)
    return jsonify(_load_report_sanitized(m))


@app.route("/api/projects/<name>/characters", methods=["GET"])
def get_character_tracks(name):
    """Per-character track layer — presence, traits, interactions, reads —
    assembled from the knowledge graph + report. Instant (no model calls)."""
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    report = None
    if m.stage("analyze").status == "complete" and os.path.exists(m.report_findings_path):
        report = _load_report_sanitized(m)
    from .character_track import build_character_tracks
    return jsonify({"characters": build_character_tracks(m.kg_path, report)})


# ---------- writer's margin notes ----------

# ---------- the Stash (saved snippets beside the script) ----------

@app.route("/api/projects/<name>/stash", methods=["GET"])
def get_stash(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    from .stash_store import load_stash
    return jsonify({"stash": load_stash(m.project_dir)})


@app.route("/api/projects/<name>/stash", methods=["POST"])
def add_stash(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    body = request.get_json(silent=True) or {}
    try:
        entry = add_stash_entry(m.project_dir, body)
    except ValueError as e:
        return _error(str(e), 400)
    return jsonify(entry), 201


def add_stash_entry(project_dir: str, body: dict) -> dict:
    from .stash_store import add_to_stash
    scene = body.get("scene_number")
    try:
        scene = int(scene) if scene is not None else None
    except (TypeError, ValueError):
        scene = None
    return add_to_stash(project_dir, body.get("text") or "", title=body.get("title") or "", scene_number=scene)


@app.route("/api/projects/<name>/stash/<entry_id>", methods=["DELETE"])
def delete_stash_entry(name, entry_id):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    from .stash_store import remove_from_stash
    if not remove_from_stash(m.project_dir, entry_id):
        return _error("Stash entry not found.", 404)
    return jsonify({"deleted": entry_id})


@app.route("/api/projects/<name>/premise", methods=["POST"])
def save_project_premise(name):
    """Edit the premise card that grew into this script (it rides alongside
    the pages after an idea graduates)."""
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    card = (request.get_json() or {}).get("card") or {}
    stored = {}
    try:
        with open(os.path.join(m.project_dir, "premise.json"), "r", encoding="utf-8") as f:
            stored = json.load(f)
    except Exception:
        pass
    for key in ("title", "logline", "premise", "questions"):
        if key in card:
            stored[key] = card[key]
    with open(os.path.join(m.project_dir, "premise.json"), "w", encoding="utf-8") as f:
        json.dump(stored, f, ensure_ascii=False, indent=2)
    return jsonify({"premise": stored})


@app.route("/api/projects/<name>/notes", methods=["GET"])
def get_notes(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    from .notes import load_notes
    return jsonify({"notes": load_notes(m)})


@app.route("/api/projects/<name>/notes", methods=["POST"])
def add_note_endpoint(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    body = request.get_json() or {}
    try:
        from .notes import add_note
        note = add_note(m, body.get("scene_number"), body.get("text", ""), anchor=body.get("anchor"))
    except ValueError as e:
        return _error(str(e), 400)
    return jsonify(note), 201


@app.route("/api/projects/<name>/notes/<note_id>", methods=["PATCH"])
def update_note_endpoint(name, note_id):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    body = request.get_json() or {}
    try:
        from .notes import update_note
        note = update_note(m, note_id, body.get("text", ""))
    except ValueError as e:
        return _error(str(e), 400)
    if note is None:
        return _error("Note not found.", 404)
    return jsonify(note)


@app.route("/api/projects/<name>/notes/<note_id>", methods=["DELETE"])
def delete_note_endpoint(name, note_id):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    from .notes import delete_note
    if not delete_note(m, note_id):
        return _error("Note not found.", 404)
    return jsonify({"ok": True})


# ---------- revision loop (script viewer / rewrites / export) ----------

@app.route("/api/projects/<name>/script", methods=["GET"])
def get_script(name):
    """The working copy of the script (edited state if edits exist, else the
    original parse) as ScriptDocument JSON — what the viewer renders."""
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    if m.stage("parse").status != "complete":
        return _error("Project hasn't been parsed yet.", 400)
    from .revision import load_working
    doc = load_working(m)
    data = doc.to_dict()
    try:
        from screenplay_parser.stats import scene_estimates
        estimates = scene_estimates(doc)
        for s in data.get("scenes", []):
            est = estimates.get(s["scene_number"])
            if est:
                s["page_estimate"] = est["minutes"]
                s["word_count"] = est["words"]
        data["runtime_minutes"] = round(sum(e["minutes"] for e in estimates.values()), 1)
    except Exception:
        pass
    return jsonify(data)


@app.route("/api/projects/<name>/edits", methods=["GET"])
def get_edits(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    from .revision import edits_log, finding_statuses, redo_stack
    statuses = finding_statuses(m) if m.stage("analyze").status == "complete" else {"findings": [], "summary": {"addressed": 0, "still_present": 0, "unknown": 0}}
    return jsonify({"edits": edits_log(m), "findings_status": statuses, "can_undo": bool(edits_log(m)), "can_redo": bool(redo_stack(m))})


@app.route("/api/projects/<name>/rewrite", methods=["POST"])
def rewrite_scene_endpoint(name):
    """Model-suggested line replacements for one scene. Generates candidates
    only — nothing is applied until the writer approves via /edits/apply."""
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    if m.stage("parse").status != "complete":
        return _error("Project hasn't been parsed yet.", 400)

    body = request.get_json() or {}
    try:
        scene_number = int(body.get("scene_number"))
    except (TypeError, ValueError):
        return _error("scene_number is required.")

    # Validate the scene BEFORE spending a model call or grounding text on it,
    # so a missing scene is a clean 404 rather than a conflated error.
    from .revision import load_working as _lw, scene_elements as _se
    try:
        _se(_lw(m), scene_number)
    except ValueError as e:
        return _error(str(e), 404)

    finding_text = ""
    finding_index = body.get("finding_index")
    if finding_index is not None:
        # Best-effort: resolve the finding to ground the rewrite in its text.
        # If the report is missing or the index is stale (e.g. after a
        # re-analysis), degrade to an ungrounded rewrite rather than failing.
        try:
            report = _load_report_sanitized(m)
            findings = report.get("findings", [])
            finding = findings[int(finding_index)]
            refs = ", ".join(f"Scene {n}" for n in (finding.get("scene_refs") or []))
            finding_text = (
                f"[{finding.get('severity', 'medium').upper()}] {refs or 'General'}: "
                f"{finding.get('issue', '')} — {finding.get('why_it_matters', '')}"
            )
            if finding.get("evidence_quote"):
                finding_text += f" Evidence: \"{finding['evidence_quote']}\""
        except (FileNotFoundError, KeyError, IndexError, ValueError):
            pass

    instruction = (body.get("instruction") or "").strip()
    try:
        from .revision import load_working, rewrite_scene, scene_text
        doc = load_working(m)
        result = rewrite_scene(_make_client(m), doc, scene_number, finding_text, instruction)
    except Exception as e:
        return _error(f"Rewrite failed: {e}", 502)

    replacements = [r for r in result.get("replacements", []) if (r.get("old") or "").strip()]
    return jsonify({
        "scene_number": scene_number,
        "note": result.get("note", ""),
        "replacements": replacements,
        "scene_text": scene_text(doc, scene_number),
    })


@app.route("/api/projects/<name>/edits/apply", methods=["POST"])
def apply_edits(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)

    body = request.get_json() or {}
    try:
        scene_number = int(body.get("scene_number"))
    except (TypeError, ValueError):
        return _error("scene_number is required.")
    replacements = body.get("replacements")
    if not isinstance(replacements, list) or not replacements:
        return _error("replacements list is required.")

    from .revision import load_working, save_working, apply_replacements, finding_statuses, scene_text
    doc = load_working(m)
    result = apply_replacements(doc, scene_number, replacements)
    if result["applied"]:
        save_working(m, doc, record={
            "scene_number": scene_number,
            "applied": result["applied"],
            "skipped": result["skipped"],
            "applied_at": time.time(),
        })
    statuses = finding_statuses(m) if m.stage("analyze").status == "complete" else {"findings": [], "summary": {"addressed": 0, "still_present": 0, "unknown": 0}}
    _record_findings_metrics(m, statuses)
    return jsonify({
        **result,
        "scene_text_after": scene_text(doc, scene_number),
        "findings_status": statuses,
    })


@app.route("/api/projects/<name>/edits/undo", methods=["POST"])
def undo_edits(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    from .revision import load_working, undo_last_edit, finding_statuses
    try:
        result = undo_last_edit(m)
    except ValueError as e:
        return _error(str(e), 400)
    statuses = finding_statuses(m) if m.stage("analyze").status == "complete" else {"findings": [], "summary": {"addressed": 0, "still_present": 0, "unknown": 0}}
    _record_findings_metrics(m, statuses)
    return jsonify({**result, "findings_status": statuses})


def _record_findings_metrics(m, statuses) -> None:
    """Findings-per-fix: how much of the last report is resolved now."""
    try:
        from .metrics import record_findings
        summary = statuses.get("summary") or {}
        open_count = (summary.get("still_present") or 0) + (summary.get("unknown") or 0)
        total = (summary.get("addressed") or 0) + (summary.get("still_present") or 0) + (summary.get("unknown") or 0)
        if total:
            record_findings(m, open_count, total)
    except Exception:
        pass  # metrics are best-effort; never break an edit


@app.route("/api/projects/<name>/metrics", methods=["GET"])
def get_metrics(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    from .metrics import summarize
    return jsonify(summarize(m))


@app.route("/api/projects/<name>/edits/redo", methods=["POST"])
def redo_edits(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    from .revision import load_working, redo_last_edit, finding_statuses
    try:
        result = redo_last_edit(m)
    except ValueError as e:
        return _error(str(e), 400)
    statuses = finding_statuses(m) if m.stage("analyze").status == "complete" else {"findings": [], "summary": {"addressed": 0, "still_present": 0, "unknown": 0}}
    _record_findings_metrics(m, statuses)
    return jsonify({**result, "findings_status": statuses})


@app.route("/api/projects/<name>/edits/reset", methods=["POST"])
def reset_edits(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    from .revision import reset_working
    reset_working(m)
    return jsonify({"ok": True, "has_edits": False})


@app.route("/api/projects/<name>/export", methods=["GET"])
def export_script(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)

    fmt = request.args.get("format", "fountain")
    if fmt not in ("fountain", "fdx", "txt"):
        return _error("format must be one of: fountain, fdx, txt.", 400)

    from screenplay_parser.export import export
    from .revision import load_working
    doc = load_working(m)
    text = export(doc, fmt)

    safe_title = "".join(c if c.isalnum() or c in "-_ " else "_" for c in (doc.title or m.title or "script"))
    ext = {"fountain": ".fountain", "fdx": ".fdx", "txt": ".txt"}[fmt]
    mimetype = {"fountain": "text/plain", "fdx": "application/xml", "txt": "text/plain"}[fmt]
    return send_file(
        io.BytesIO(text.encode("utf-8")),
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"{safe_title}{ext}",
    )


# ---------- beat board ----------

@app.route("/api/projects/<name>/beatboard", methods=["GET"])
def get_beatboard(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    from .beatboard import board_view
    return jsonify(board_view(m))


@app.route("/api/projects/<name>/beatboard", methods=["PUT"])
def put_beatboard(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    body = request.get_json() or {}
    from .beatboard import set_order
    try:
        board = set_order(m, body.get("order"))
    except ValueError as e:
        return _error(str(e), 400)
    return jsonify(board)


@app.route("/api/projects/<name>/beatboard/reset", methods=["POST"])
def reset_beatboard(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    from .beatboard import reset_order
    return jsonify(reset_order(m))


@app.route("/api/projects/<name>/beatboard/export", methods=["GET"])
def export_beatboard(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    fmt = request.args.get("format", "fountain")
    if fmt not in ("fountain", "fdx", "txt"):
        return _error("format must be one of: fountain, fdx, txt.", 400)
    from .beatboard import export_reordered
    try:
        text = export_reordered(m, fmt)
    except ValueError as e:
        return _error(str(e), 400)
    safe_title = "".join(c if c.isalnum() or c in "-_ " else "_" for c in (m.title or "script"))
    ext = {"fountain": ".fountain", "fdx": ".fdx", "txt": ".txt"}[fmt]
    mimetype = {"fountain": "text/plain", "fdx": "application/xml", "txt": "text/plain"}[fmt]
    return send_file(
        io.BytesIO(text.encode("utf-8")),
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"{safe_title}-beatboard-order{ext}",
    )


# ---------- live analysis progress ----------

@app.route("/api/projects/<name>/progress", methods=["GET"])
def get_progress(name):
    """Latest per-stage analysis progress (written by the pipeline callback).

    A run that dies hard (killed process, OOM, crash) leaves no done/failed
    write behind, so the last 'running' event would otherwise lie forever.
    Every progress write carries a ts heartbeat: if a 'running' file has gone
    silent for STALL_SECONDS, treat the run as dead and heal the manifest so
    every consumer (shelf chip, report 400, fix queue) agrees."""
    STALL_SECONDS = 30 * 60  # generous: one heavy stage on a big script can take 20+ min
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    if not os.path.exists(m.progress_path):
        stage = m.stage("analyze").status
        return jsonify({"stage": "done" if stage == "complete" else "idle", "status": "complete" if stage == "complete" else "idle", "detail": ""})
    with open(m.progress_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # ts is the heartbeat written by every run since the fix; a file without
    # it is guaranteed legacy (all current runs stamp it), so its own mtime is
    # the best available signal for when the dead run last wrote.
    ts = data.get("ts") or os.path.getmtime(m.progress_path)
    if data.get("status") == "running" and time.time() - ts > STALL_SECONDS:
        try:
            os.remove(m.progress_path)
        except OSError:
            pass
        m.mark_failed("analyze", "Analysis stopped mid-run (no progress for 30+ minutes). Re-run to start fresh.")
        return jsonify({
            "stage": "stalled", "status": "stalled",
            "detail": "Analysis appears to have stopped — no progress for 30+ minutes. Re-run Analysis to start fresh.",
        })
    return jsonify(data)


# ---------- prioritized fix queue ----------

SEVERITY_WEIGHT = {"high": 0, "major": 1, "medium": 2, "low": 3}


@app.route("/api/projects/<name>/fixqueue", methods=["GET"])
def get_fixqueue(name):
    """Findings sorted as a fix-these-first list: severity, then act, then
    original order. Each item carries its act label, scene heading, and its
    current revision status (addressed / still_present / unknown)."""
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    if m.stage("analyze").status != "complete":
        return jsonify({"items": [], "acts": []})

    report = _load_report_sanitized(m)

    from screenplay_parser.structure import assign_acts, act_for_scene
    from .revision import load_working, finding_statuses
    doc = load_working(m)
    acts = assign_acts(doc)
    act_names = {a["act"]: a["name"] for a in acts}
    scene_heading = {s.scene_number: s.heading_raw for s in doc.scenes}
    status_by_index = {s["index"]: s["status"] for s in finding_statuses(m)["findings"]}

    from .revision import dismissed_issues as _dismissed
    dismissed_keys = _dismissed(m)

    items = []
    for idx, f in enumerate(report.get("findings", [])):
        refs = f.get("scene_refs") or []
        scene = refs[0] if refs else None
        act = act_for_scene(acts, scene) if scene else None
        items.append({
            "index": idx,
            "category": f.get("category"),
            "severity": f.get("severity"),
            "issue": f.get("issue"),
            "why_it_matters": f.get("why_it_matters"),
            "scene_refs": refs,
            "scene_heading": scene_heading.get(scene) if scene else None,
            "act": act,
            "act_name": (act_names.get(act) if act else "Script-level"),
            "status": status_by_index.get(idx, "unknown"),
        })
    items.sort(key=lambda i: (SEVERITY_WEIGHT.get(i["severity"], 3), i["act"] or 4, i["index"]))

    # Triage: dismissed findings are flagged (flag-don't-drop applies to the
    # writer's own judgment too) but hidden unless explicitly asked for. A
    # dismissal only sticks while the report still says the same thing at
    # that index — a regenerated report re-opens everything honestly.
    for it in items:
        it["dismissed"] = (it["index"], (it["issue"] or "")) in dismissed_keys
    include_dismissed = request.args.get("include_dismissed") == "1"
    visible = [i for i in items if include_dismissed or not i["dismissed"]]
    return jsonify({"items": visible, "acts": acts,
                    "dismissed_count": len(items) - len(visible),
                    "total_count": len(items)})


@app.route("/api/projects/<name>/findings/<int:index>/dismiss", methods=["POST"])
def dismiss_finding_route(name, index):
    """Writer triage: 'I've read it, I'm choosing to live with this one.'
    The finding is hidden from the queue (flag-don't-drop: it stays in the
    report and comes back if the report is regenerated with a different
    issue at this index)."""
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    body = request.get_json(silent=True) or {}
    from .revision import dismiss_finding
    dismiss_finding(m, index, body.get("issue") or "")
    return jsonify({"ok": True, "index": index})


@app.route("/api/projects/<name>/findings/<int:index>/undismiss", methods=["POST"])
def undismiss_finding_route(name, index):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    from .revision import undismiss_finding
    undismiss_finding(m, index)
    return jsonify({"ok": True, "index": index})


# ---------- streaming chat (SSE) ----------


def _sse_chat_stream(engine, session, store, text, quote, manifest=None, on_success=None):
    """Shared generator behind both streaming chat routes. Raw model tokens
    stream to the browser as they arrive (perceived-latency win on slow local
    models); the FINAL event carries the cleaned, stored reply + full message
    history, so what gets persisted is byte-identical to the non-streaming
    path — streaming changes how a reply appears, never what is kept."""
    q = queue.Queue()
    result = {}
    t0 = time.time()

    def on_token(piece):
        q.put(("token", piece))

    def worker():
        try:
            result["reply"] = engine.send_message(session, text, quote=quote, on_token=on_token)
            q.put(("done", None))
        except Exception as e:  # mapped below — a failed turn must end the stream, not hang it
            result["error"] = e
            q.put(("error", str(e)))

    threading.Thread(target=worker, daemon=True).start()
    while True:
        kind, _payload = q.get()
        if kind == "token":
            yield f"data: {json.dumps({'token': _payload})}\n\n"
            continue
        if kind == "done":
            if manifest is not None:
                try:
                    from .metrics import record_reply
                    record_reply(manifest, time.time() - t0, quoted=bool(quote))
                except Exception:
                    pass  # metrics are best-effort — never break a chat turn
            if on_success is not None:
                try:
                    on_success()
                except Exception:
                    pass  # bookkeeping must never break the turn
            store.save(session)  # engine already saved under the store's lock; idempotent
            yield "data: " + json.dumps({
                "done": True,
                "reply": result["reply"],
                "branch": session.current_branch,
                "messages": [m.to_dict() for m in session.branch.messages],
            }) + "\n\n"
            return
        err = result.get("error")
        still_working = type(err).__name__ == "WatchdogTimeoutError" or "didn't respond within" in str(err)
        message = ("The model was still working when the per-turn time cap was hit." if still_working
                   else f"The model server couldn't be reached or returned an error: {err}")
        yield "data: " + json.dumps({"error": message, "still_working": still_working}) + "\n\n"
        return


def _stream_response(generator):
    return Response(generator, mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/projects/<name>/chat/sessions/<sid>/messages/stream", methods=["POST"])
def send_message_stream(name, sid):
    body = request.get_json() or {}
    text = (body.get("text") or "").strip()
    if not text:
        return _error("Message text is required.")
    try:
        session, engine, store = _load_session_and_engine(name, sid)
    except FileNotFoundError:
        return _error("Session or project not found.", 404)
    except CowriterUnavailableError as e:
        return _error(str(e), 503)
    return _stream_response(_sse_chat_stream(engine, session, store, text, body.get("quote")))


@app.route("/api/ideas/<idea_id>/chat/sessions/<sid>/messages/stream", methods=["POST"])
def send_idea_message_stream(idea_id, sid):
    body = request.get_json() or {}
    text = (body.get("text") or "").strip()
    if not text:
        return _error("Message text is required.")
    try:
        session, engine, store = _load_idea_session_and_engine(idea_id, sid)
    except FileNotFoundError:
        return _error("Session or idea not found.", 404)
    except CowriterUnavailableError as e:
        return _error(str(e), 503)
    return _stream_response(_sse_chat_stream(
        engine, session, store, text, body.get("quote"),
        on_success=lambda: setattr(session, "last_seen_content",
                                   getattr(engine, "_current_page_content", None))))


# ---------- shareable report export ----------


def _md_to_html(md: str) -> str:
    """Tiny, dependency-free markdown -> HTML renderer for the report. Handles
    the subset report.py emits: #/##/### headings, **bold**, *italic*, tables,
    - bullets, hr, and paragraphs."""
    import html as _html
    from html import escape

    lines = md.split("\n")
    out, para, in_list, in_table, table_rows = [], [], False, False, 0

    def flush_para():
        nonlocal para
        if para:
            out.append("<p>" + " ".join(para) + "</p>")
            para = []

    def inline(text):
        text = escape(text)
        text = text.replace("**", "<strong>", 1).replace("**", "</strong>", 1) if text.count("**") >= 2 else text
        # handle multiple bold spans robustly
        import re as _re
        text = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = _re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
        return text

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("|") and line.endswith("|"):
            flush_para()
            if not in_table:
                out.append("<table>")
                in_table = True
                table_rows = 0  # per-table: the FIRST row of EVERY table is a header
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                continue  # separator row
            tag = "th" if table_rows == 0 else "td"
            table_rows += 1
            out.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
            table_rows = 0
        if not line.strip():
            flush_para()
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        if line.startswith("### "):
            flush_para(); out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("## "):
            flush_para(); out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("# "):
            flush_para(); out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line == "---":
            flush_para(); out.append("<hr/>")
        elif line.startswith("- "):
            flush_para()
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{inline(line[2:])}</li>")
        else:
            if in_list:
                out.append("</ul>"); in_list = False
            para.append(inline(line))
    flush_para()
    if in_list:
        out.append("</ul>")
    if in_table:
        out.append("</table>")

    body = "\n".join(out)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Script Doctor Report</title>
<style>
  body {{ font-family: Georgia, 'Times New Roman', serif; max-width: 720px; margin: 40px auto; padding: 0 24px; color: #222; line-height: 1.6; }}
  h1 {{ font-family: 'Courier New', monospace; border-bottom: 3px double #333; padding-bottom: 8px; }}
  h2 {{ font-family: 'Courier New', monospace; margin-top: 34px; border-bottom: 1px solid #999; }}
  h3 {{ font-family: 'Courier New', monospace; margin-top: 24px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  th, td {{ border: 1px solid #bbb; padding: 5px 9px; font-size: 13.5px; text-align: left; }}
  th {{ background: #f0ece2; }}
  @media print {{ body {{ margin: 0; }} }}
</style></head>
<body>{body}</body></html>"""


@app.route("/api/projects/<name>/report/export", methods=["GET"])
def export_report(name):
    """The analysis report as a self-contained, printable HTML file — for
    sending to a partner or producer without exposing the studio server."""
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    if m.stage("analyze").status != "complete":
        return _error("Analysis hasn't completed for this project yet.", 400)
    with open(m.report_md_path, "r", encoding="utf-8") as f:
        md = f.read()
    html = _md_to_html(md)
    safe_title = "".join(c if c.isalnum() or c in "-_ " else "_" for c in (m.title or "script"))
    return send_file(
        io.BytesIO(html.encode("utf-8")),
        mimetype="text/html",
        as_attachment=True,
        download_name=f"{safe_title}-report.html",
    )


# ---------- drafts & diffing ----------

@app.route("/api/projects/<name>/drafts", methods=["GET"])
def list_drafts(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    return jsonify({"active_draft": m.active_draft, "drafts": m.drafts})


@app.route("/api/projects/<name>/drafts", methods=["POST"])
def upload_draft(name):
    """Upload a new draft: snapshots the current active draft, then re-parses
    the upload as the new active draft. Analysis is re-queued automatically."""
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)

    if "file" not in request.files:
        return _error("No file uploaded (expected multipart field 'file').")
    upload = request.files["file"]
    if not upload.filename:
        return _error("Empty filename.")

    tmp_path = os.path.join(m.project_dir, "_draft_upload" + os.path.splitext(upload.filename)[1].lower() or ".txt")
    upload.save(tmp_path)
    try:
        from .diff import upload_new_draft
        upload_new_draft(m, tmp_path, upload.filename)
        orch = Orchestrator(m)
        orch.run_parse()
    except Exception as e:
        return _error(f"Could not process new draft: {e}", 500)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return jsonify(_manifest_summary(m))


@app.route("/api/projects/<name>/drafts/activate", methods=["POST"])
def activate_draft_endpoint(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    body = request.get_json() or {}
    draft = (body.get("name") or "").strip()
    if not draft:
        return _error("A draft name is required.", 400)
    try:
        from .diff import activate_draft
        activate_draft(m, draft)
    except ValueError as e:
        return _error(str(e), 400)
    return jsonify(_manifest_summary(m))


@app.route("/api/projects/<name>/diff", methods=["GET"])
def get_diff(name):
    """Structural + findings diff between two drafts. Query params:
    from=<draft name|original>, to=<draft name|active|original>.
    Defaults: from = the previous draft, to = the active one."""
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)

    from_, to_ = _resolve_draft_pair(m, request.args.get("from"), request.args.get("to"))

    try:
        from .diff import diff_drafts
        result = diff_drafts(m, from_, to_)
    except (ValueError, FileNotFoundError) as e:
        return _error(str(e), 400)
    return jsonify(result)


@app.route("/api/projects/<name>/compare", methods=["GET"])
def get_compare(name):
    """Side-by-side compare material: aligned rows per common scene for two
    drafts (same query params and defaults as /diff)."""
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)

    from_, to_ = _resolve_draft_pair(m, request.args.get("from"), request.args.get("to"))

    try:
        from .diff import compare_drafts
        result = compare_drafts(m, from_, to_)
    except (ValueError, FileNotFoundError) as e:
        return _error(str(e), 400)
    return jsonify(result)


def _resolve_draft_pair(m, from_arg, to_arg):
    """Defaults: from = the draft before the active one, to = the active one."""
    from_ = from_arg or ""
    to_ = to_arg or ""
    if not from_:
        drafts = [d["name"] for d in m.drafts]
        if m.active_draft and m.active_draft in drafts:
            idx = drafts.index(m.active_draft)
            from_ = drafts[idx - 1] if idx > 0 else "original"
        elif drafts:
            from_ = drafts[-1]
        else:
            from_ = "original"
    if not to_:
        to_ = "active"
    return from_, to_


# ---------- chat ----------

@app.route("/api/projects/<name>/chat/start", methods=["POST"])
def start_chat(name):
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)

    m.server_url = CONFIG["server_url"]
    m.timeout = CONFIG["timeout"]
    orch = Orchestrator(m)
    try:
        session, engine, store = orch.start_chat()
    except OrchestratorError as e:
        return _error(str(e), 502)

    return jsonify({"session_id": session.session_id, "model_id": session.model_id, "branch": session.current_branch})


def _engine_base_url(session):
    """Base URL for a chat engine. Sessions remember the server they were
    created with (a remembered preference), but in DEMO mode there is exactly
    one server — the in-process one — and its port changes every restart, so
    a stale pin would 502 forever. Live config wins in demo mode."""
    if _DEMO_MODEL_ACTIVE:
        return CONFIG["server_url"]
    return session.server_url or CONFIG["server_url"]


def _load_session_and_engine(project: str, session_id: str):
    store_mod = _import_cowriter("store")
    context_mod = _import_cowriter("context")
    engine_mod = _import_cowriter("engine")
    llm_mod = _import_cowriter("llm_client")
    SessionStore = store_mod.SessionStore
    ScriptContext = context_mod.ScriptContext
    ReportContext = context_mod.ReportContext
    load_json = context_mod.load_json
    CoWriterEngine = engine_mod.CoWriterEngine
    LlamaServerClient = llm_mod.LlamaServerClient

    m = _load_manifest(project)
    store = SessionStore(m.sessions_dir)
    session = store.load(session_id)

    report_path = m.report_findings_path if m.stage("analyze").status == "complete" else None
    # The co-writer discusses the CURRENT state of the draft: if the writer has
    # applied revision edits, the working copy is the source of truth.
    from .revision import has_edits, ensure_working
    script_path = ensure_working(m) if has_edits(m) else m.parsed_path
    script_ctx = ScriptContext(load_json(script_path))
    report = _sanitize_report(load_json(report_path)) if report_path else None
    report_ctx = ReportContext(report)
    # Chat turns run on the short turn clock (the generation watchdog) — a
    # slow reply surfaces a "still working?" prompt instead of a silent
    # multi-minute hang. Analysis calls keep the long timeout; only chat
    # turns use turn_timeout.
    client = LlamaServerClient(base_url=_engine_base_url(session), model=session.model_id,
                               timeout=CONFIG["turn_timeout"], fallback_to_loaded=True)
    memory = None
    try:
        mem_mod = _import_cowriter("memory")
        memory = mem_mod.WriterMemory.load(os.path.join(PROJECTS_DIR, "writer_profile.json"))
    except (CowriterUnavailableError, OSError, ValueError):
        memory = None  # memory unavailable or unreadable — never break the chat
    # The writer's past work rides along so Sameer/the doctor can draw on
    # earlier scripts — with the current project excluded so the digest never
    # blurs into the script on the desk.
    try:
        lib_mod = _import_cowriter("writer_library")
        lib_text = lib_mod.library_digest_text(_writer_library(exclude=project))
    except Exception:
        lib_text = None
    engine = CoWriterEngine(client, script_ctx, report_ctx, store=store, memory=memory,
                            memory_scope=f"project:{project}", writer_library_text=lib_text,
                            mood_text=_mood_fragment(m), doctor_case_text=_doctor_case_file(exclude=project))
    return session, engine, store


@app.route("/api/projects/<name>/chat/sessions/<sid>", methods=["GET"])
def get_session(name, sid):
    try:
        session, _, _ = _load_session_and_engine(name, sid)
    except FileNotFoundError:
        return _error("Session or project not found.", 404)
    except CowriterUnavailableError as e:
        return _error(str(e), 503)
    # Retroactive: stored sessions written before the language-meta filter
    # existed may contain dialect/subtitle commentary — strip it at serve
    # time so old history reads the same as new replies.
    lang_meta_mod = _import_cowriter("language_meta")
    strip_language_meta = lang_meta_mod.strip_language_meta
    return jsonify({
        "session_id": session.session_id,
        "title": session.title,
        "current_branch": session.current_branch,
        "last_seen_content": getattr(session, "last_seen_content", None),
        "branches": {
            bname: {
                "messages": [
                    {**msg.to_dict(), "content": strip_language_meta(msg.content) if msg.role == "assistant" else msg.content}
                    for msg in b.messages
                ],
                "parent_branch": b.parent_branch,
                "forked_at_index": b.forked_at_index,
                "active_persona": b.active_persona,
                "active_mode": b.active_mode,
            }
            for bname, b in session.branches.items()
        },
    })


@app.route("/api/projects/<name>/chat/sessions/<sid>", methods=["DELETE"])
def delete_session(name, sid):
    """End-user control: erase this conversation with Sameer. Only the chat
    history is deleted — the writer's relationship memory (writer_profile.json)
    is deliberately kept, so Sameer's learning about how the writer works survives
    a fresh page. The frontend immediately starts a new session after this."""
    try:
        m = _load_manifest(name)
        store_mod = _import_cowriter("store")
        SessionStore = store_mod.SessionStore
        store = SessionStore(m.sessions_dir)
        store.load(sid)  # strict: 404 if the session doesn't exist
        store.delete(sid)
        # never leave the manifest pointing at a deleted session — start_chat
        # would otherwise 502 on the next message (Clear chat deletes then
        # starts fresh)
        if m.cowriter_session_id == sid:
            m.cowriter_session_id = None
            m.save()
    except FileNotFoundError:
        return _error("Session or project not found.", 404)
    return jsonify({"deleted": sid})


@app.route("/api/projects/<name>/chat/sessions/<sid>/messages", methods=["POST"])
def send_message(name, sid):
    body = request.get_json() or {}
    text = (body.get("text") or "").strip()
    if not text:
        return _error("Message text is required.")

    try:
        session, engine, store = _load_session_and_engine(name, sid)
    except FileNotFoundError:
        return _error("Session or project not found.", 404)
    except CowriterUnavailableError as e:
        return _error(str(e), 503)

    # select-to-reply: optional {"scene_number": int, "text": str}
    quote = body.get("quote")
    import time as _t
    _t0 = _t.time()
    try:
        reply = engine.send_message(session, text, quote=quote)
    except Exception as e:
        # Generation watchdog: the turn hit its per-turn cap while the model
        # was still working. Distinct from a dead server — send a 408 the
        # frontend recognizes, so it can offer "keep waiting?" instead of
        # failing the turn. Safe to retry: send_message appends the user
        # message only AFTER the model call succeeds, so nothing was stored.
        if type(e).__name__ == "WatchdogTimeoutError" or "didn't respond within" in str(e):
            return jsonify({
                "error": "The model was still working when the per-turn time cap was hit.",
                "still_working": True,
            }), 408
        return _error(f"The model server couldn't be reached or returned an error: {e}", 502)

    try:
        from .metrics import record_reply
        record_reply(_load_manifest(name), _t.time() - _t0, quoted=bool(quote))
    except Exception:
        pass  # metrics are best-effort — never break a chat turn
    store.save(session)
    return jsonify({
        "reply": reply,
        "branch": session.current_branch,
        "messages": [msg.to_dict() for msg in session.branch.messages],
    })


@app.route("/api/projects/<name>/chat/sessions/<sid>/fork", methods=["POST"])
def fork_session(name, sid):
    body = request.get_json() or {}
    new_name = (body.get("name") or "").strip()
    if not new_name:
        return _error("A name for the new branch is required.")

    try:
        session, _, store = _load_session_and_engine(name, sid)
        session.fork(new_name, from_branch=body.get("from_branch"))
    except FileNotFoundError:
        return _error("Session or project not found.", 404)
    except ValueError as e:
        return _error(str(e))
    except CowriterUnavailableError as e:
        return _error(str(e), 503)

    store.save(session)
    return jsonify({"current_branch": session.current_branch, "branches": list(session.branches.keys())})


@app.route("/api/projects/<name>/chat/sessions/<sid>/switch", methods=["POST"])
def switch_branch(name, sid):
    body = request.get_json() or {}
    branch_name = (body.get("name") or "").strip()

    try:
        session, _, store = _load_session_and_engine(name, sid)
        session.switch(branch_name)
    except FileNotFoundError:
        return _error("Session or project not found.", 404)
    except ValueError as e:
        return _error(str(e))
    except CowriterUnavailableError as e:
        return _error(str(e), 503)

    store.save(session)
    return jsonify({"current_branch": session.current_branch})


@app.route("/api/projects/<name>/chat/sessions/<sid>/settings", methods=["POST"])
def update_settings(name, sid):
    personas_mod = _import_cowriter("personas")
    PERSONAS = personas_mod.PERSONAS
    MODES = personas_mod.MODES

    body = request.get_json() or {}
    persona = body.get("persona")
    mode = body.get("mode")
    if persona and persona not in PERSONAS:
        return _error(f"Unknown persona. Available: {list(PERSONAS.keys())}")
    if mode and mode not in MODES:
        return _error(f"Unknown mode. Available: {list(MODES.keys())}")

    try:
        session, _, store = _load_session_and_engine(name, sid)
    except FileNotFoundError:
        return _error("Session or project not found.", 404)
    except CowriterUnavailableError as e:
        return _error(str(e), 503)

    if persona:
        session.branch.active_persona = persona
    if mode:
        session.branch.active_mode = mode
    store.save(session)
    return jsonify({"active_persona": session.branch.active_persona, "active_mode": session.branch.active_mode})


def _load_writer_memory():
    mem_mod = _import_cowriter("memory")
    return mem_mod.WriterMemory.load(os.path.join(PROJECTS_DIR, "writer_profile.json"))


@app.route("/api/writer-memory", methods=["GET"])
def get_writer_memory():
    try:
        mem = _load_writer_memory()
    except CowriterUnavailableError as e:
        return _error(str(e), 503)
    # The card (what Sameer actually uses) is scope-filtered: observations tagged
    # for another project/idea never leak in. The writer's own full profile
    # stays visible — it's their memory, they should see all of it.
    scope = request.args.get("scope") or None
    return jsonify({"profile": mem.to_dict(), "card": mem.card_text(scope=scope), "gated": mem.gated_dimensions()})


@app.route("/api/writer-memory/observations/<obs_id>/suppress", methods=["POST"])
def suppress_writer_observation(obs_id):
    try:
        mem = _load_writer_memory()
    except CowriterUnavailableError as e:
        return _error(str(e), 503)
    if not mem.suppress(obs_id):
        return _error("Observation not found.", 404)
    return jsonify({"ok": True})


@app.route("/api/writer-memory/refresh", methods=["POST"])
def refresh_writer_memory():
    body = request.get_json() or {}
    project = body.get("project")
    session_id = body.get("session_id")
    if not project or not session_id:
        return _error("project and session_id are required.", 400)
    try:
        session, engine, _ = _load_session_and_engine(project, session_id)
    except FileNotFoundError:
        return _error("Session or project not found.", 404)
    except CowriterUnavailableError as e:
        return _error(str(e), 503)
    try:
        mem = _load_writer_memory()
    except CowriterUnavailableError as e:
        return _error(str(e), 503)
    llm_mod = _import_cowriter("llm_client")
    client = llm_mod.LlamaServerClient(base_url=session.server_url or CONFIG["server_url"],
                                       model=session.model_id, timeout=CONFIG["timeout"],
                                       fallback_to_loaded=True)
    recent = [m.to_dict() for m in session.branch.messages[-16:]]
    mem.refresh(client, recent, scope=engine.memory_scope, entities=engine._memory_entities())
    return jsonify({"profile": mem.to_dict(), "card": mem.card_text(scope=engine.memory_scope)})


# ---------- idea room (scriptless story development) ----------


def _ideas_dir() -> str:
    return os.path.join(PROJECTS_DIR, "ideas")


def _load_idea(idea_id: str) -> dict:
    return IdeaStore(_ideas_dir()).load(idea_id)


def _idea_session_payload(session) -> dict:
    """Mirror the project get_session payload (branches, personas, fork shape)
    so the frontend reuses the exact same rendering code for idea chats."""
    lang_meta_mod = _import_cowriter("language_meta")
    strip_language_meta = lang_meta_mod.strip_language_meta
    return {
        "session_id": session.session_id,
        "title": session.title,
        "current_branch": session.current_branch,
        "last_seen_content": getattr(session, "last_seen_content", None),
        "branches": {
            bname: {
                "messages": [
                    {**msg.to_dict(), "content": strip_language_meta(msg.content) if msg.role == "assistant" else msg.content}
                    for msg in b.messages
                ],
                "parent_branch": b.parent_branch,
                "forked_at_index": b.forked_at_index,
                "active_persona": b.active_persona,
                "active_mode": b.active_mode,
            }
            for bname, b in session.branches.items()
        },
    }


def _load_idea_session_and_engine(idea_id: str, sid: str):
    """Scriptless engine: empty script/report contexts, the premise card
    injected every turn, the same writer relationship memory as the script
    desk (so Sameer's learning about the writer carries across the whole
    journey, idea room through script)."""
    store_mod = _import_cowriter("store")
    context_mod = _import_cowriter("context")
    engine_mod = _import_cowriter("engine")
    llm_mod = _import_cowriter("llm_client")
    SessionStore = store_mod.SessionStore
    ScriptContext = context_mod.ScriptContext
    ReportContext = context_mod.ReportContext
    CoWriterEngine = engine_mod.CoWriterEngine
    LlamaServerClient = llm_mod.LlamaServerClient

    meta = _load_idea(idea_id)
    store = SessionStore(IdeaStore(_ideas_dir()).sessions_dir(idea_id))
    session = store.load(sid)

    script_ctx = ScriptContext(None)
    report_ctx = ReportContext(None)
    # Idea chats run on the same short turn clock as script chats (watchdog).
    client = LlamaServerClient(base_url=_engine_base_url(session), model=session.model_id,
                               timeout=CONFIG["turn_timeout"], fallback_to_loaded=True)
    # Isolation (writer-first rule): the idea chat knows ONLY this idea — the
    # free-form page + the conversation. The past-scripts library digest is
    # deliberately NOT injected (no cross-idea content leakage until the
    # writer brings it up). Sameer's learned TONE is kept: the relationship
    # memory carries how the writer likes to work, never idea content, and
    # memory_scope pins observations to this idea.
    memory = None
    try:
        mem_mod = _import_cowriter("memory")
        memory = mem_mod.WriterMemory.load(os.path.join(PROJECTS_DIR, "writer_profile.json"))
    except (CowriterUnavailableError, OSError, ValueError):
        memory = None  # memory unavailable or unreadable — never break the chat
    premise = dict(meta.get("card") or {})
    premise["content"] = meta.get("content") or ""
    # Deterministic page-diff: what changed on the idea page since Sameer last
    # READ it (baseline persisted on the session). Computed here so ANY model
    # -- local GGUF or demo -- demonstrably notices edits without guessing.
    premise["page_update"] = _page_update_note(session.last_seen_content, premise["content"])
    engine = CoWriterEngine(client, script_ctx, report_ctx, store=store, memory=memory,
                            premise=premise,
                            memory_scope=f"idea:{idea_id}", writer_library_text=None)
    engine._current_page_content = premise["content"]
    return session, engine, store


def _page_update_note(last_seen, current):
    """Compact deterministic line-level diff of the idea page since Sameer's
    last read. Empty string when nothing changed (or no baseline yet)."""
    if last_seen is None:
        return ""
    import difflib
    old_lines = (last_seen or "").splitlines()
    new_lines = (current or "").splitlines()
    added, removed = [], []
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("delete", "replace"):
            removed.extend(old_lines[i1:i2])
        if tag in ("insert", "replace"):
            added.extend(new_lines[j1:j2])

    def _fmt(lines):
        out = []
        for ln in lines:
            t = ln.strip()
            if t:
                out.append('  - "' + (t[:120] + ("..." if len(t) > 120 else "")) + '"')
        return out

    parts = []
    a, r = _fmt(added), _fmt(removed)
    if a:
        parts.append("ADDED since your last read:\n" + "\n".join(a))
    if r:
        parts.append("REMOVED or changed since your last read:\n" + "\n".join(r))
    return "\n\n".join(parts)




# ---------- humanization v2: deterministic mood + the doctor's case file ----------
#
# Both are COMPUTED, never model-improvised: the personas color their energy
# with these facts, but cannot invent beyond them (the honest-memory guard).
# The case file stores PATTERNS about the writing across the shelf — never
# script content — so writer memory stays shared while script discussions stay
# in their own session/project.

def _mood_fragment(m) -> str | None:
    """Room state for the persona cards — facts from real project data."""
    try:
        now = time.time()
        days = max(0, int((now - (m.updated_at or now)) // 86400))
        from .revision import edits_log
        try:
            edit_count = len(edits_log(m))
        except Exception:
            edit_count = 0
        drafts = len(m.drafts or [])
        analyze_status = m.stage("analyze").status
        visit = "today" if days == 0 else f"{days} day(s) ago"
        lines = [
            "Room state (facts computed from this project — let it color your energy; "
            "never quote it as script content):",
            f"- Last desk visit: {visit}.",
            f"- {drafts} draft(s) on file; {edit_count} line edit(s) applied this revision.",
        ]
        if analyze_status == "complete":
            lines.append("- The doctor's report sits on the desk.")
        elif analyze_status in ("pending", "failed"):
            lines.append("- No analysis has been run yet.")
        return "\n".join(lines)
    except Exception:
        return None  # mood is garnish — never break a chat turn


def _doctor_case_file(exclude: str | None = None) -> str | None:
    """Dr. Sushruta's case file on the WRITER: patterns across their whole shelf,
    computed from manifests + findings + edit logs. Evidence-only — patterns and
    numbers, never passages. None when there's nothing to say."""
    try:
        root = os.path.abspath(PROJECTS_DIR)
        if not os.path.isdir(root):
            return None
        from .manifest import ProjectManifest as _PM
        from .revision import finding_statuses

        per_script = []
        category_hits: dict = {}
        total_open = total_addressed = 0
        for name in sorted(os.listdir(root)):
            pdir = os.path.join(root, name)
            if name == "ideas" or name == exclude or not os.path.isdir(pdir):
                continue
            try:
                m = _PM.load(pdir)
            except Exception:
                continue
            if m.stage("analyze").status != "complete" or not os.path.exists(m.report_findings_path):
                continue
            try:
                with open(m.report_findings_path, "r", encoding="utf-8") as f:
                    report = json.load(f)
                findings = report.get("findings", [])
                statuses = finding_statuses(m)["findings"]
                status_by_idx = {s["index"]: s["status"] for s in statuses}
                addressed = sum(1 for s in status_by_idx.values() if s == "addressed")
                open_highs = sorted({
                    (f.get("category") or "?") for i, f in enumerate(findings)
                    if status_by_idx.get(i) != "addressed" and (f.get("severity") == "high")
                })
                total_open += len(findings) - addressed
                total_addressed += addressed
                for c in open_highs:
                    category_hits[c] = category_hits.get(c, 0) + 1
                per_script.append((name, addressed, len(findings), open_highs))
            except Exception:
                continue

        if not per_script:
            return None

        lines = [
            "CASE FILE — your notes on this writer, from their whole shelf "
            "(patterns and numbers only; never invent beyond this, never quote passages):",
            f"- Scripts analyzed on the shelf: {len(per_script)}.",
        ]
        reviewed = total_open + total_addressed
        if reviewed:
            pct = round(100 * total_addressed / reviewed)
            lines.append(f"- Followthrough: {total_addressed} of {reviewed} findings addressed via edits ({pct}%).")
        recurring = sorted(((c, n) for c, n in category_hits.items() if n >= 2),
                           key=lambda x: -x[1])
        if recurring:
            cats = ", ".join(f"{c} ({n} scripts)" for c, n in recurring)
            lines.append(f"- Recurring open HIGH findings across scripts: {cats}.")
        for name, addressed, total, open_highs in per_script[:6]:
            highs = f"; open highs: {', '.join(open_highs)}" if open_highs else ""
            lines.append(f"- \u201c{name}\u201d: {addressed}/{total} findings addressed{highs}.")
        lines.append("Use this the way a doctor uses history: patterns inform the diagnosis; "
                     "the current script is judged on its own pages.")
        return "\n".join(lines)
    except Exception:
        return None  # the case file is garnish too


def _writer_library(exclude: str | None = None) -> list[dict]:
    """Digest of the writer's parsed projects — deterministic, no model calls."""
    try:
        lib_mod = _import_cowriter("writer_library")
        return lib_mod.build_library(PROJECTS_DIR, exclude=exclude)
    except (CowriterUnavailableError, OSError, ValueError):
        return []


@app.route("/api/writer-library", methods=["GET"])
def get_writer_library():
    return jsonify({"projects": _writer_library()})


@app.route("/api/ideas", methods=["GET"])
def list_ideas():
    return jsonify(IdeaStore(_ideas_dir()).list())


@app.route("/api/ideas", methods=["POST"])
def create_idea():
    body = request.get_json() or {}
    meta = IdeaStore(_ideas_dir()).create(title=(body.get("title") or "").strip())
    return jsonify(meta), 201


@app.route("/api/ideas/<idea_id>", methods=["GET"])
def get_idea(idea_id):
    try:
        return jsonify(_load_idea(idea_id))
    except FileNotFoundError:
        return _error("Idea not found.", 404)


@app.route("/api/ideas/<idea_id>/content", methods=["POST"])
def save_idea_content(idea_id):
    """Save the free-form idea page (autosaved, debounced, from the canvas).
    The shelf title follows the page's first line until the writer renames."""
    try:
        _load_idea(idea_id)
    except FileNotFoundError:
        return _error("Idea not found.", 404)
    body = request.get_json() or {}
    meta = IdeaStore(_ideas_dir()).save_content(idea_id, body.get("content") or "")
    return jsonify({"title": meta["title"], "auto_title": meta.get("auto_title", True)})


@app.route("/api/ideas/<idea_id>/rename", methods=["POST"])
def rename_idea(idea_id):
    """A deliberate rename — stops the auto-title from the page's first line."""
    try:
        _load_idea(idea_id)
    except FileNotFoundError:
        return _error("Idea not found.", 404)
    body = request.get_json() or {}
    meta = IdeaStore(_ideas_dir()).rename(idea_id, body.get("title") or "")
    return jsonify({"title": meta["title"], "auto_title": False})


@app.route("/api/ideas/<idea_id>/card", methods=["POST"])
def save_idea_card(idea_id):
    try:
        _load_idea(idea_id)
    except FileNotFoundError:
        return _error("Idea not found.", 404)
    card = (request.get_json() or {}).get("card") or {}
    meta = IdeaStore(_ideas_dir()).save_card(idea_id, card)
    return jsonify(meta)


@app.route("/api/ideas/<idea_id>", methods=["DELETE"])
def delete_idea(idea_id):
    try:
        _load_idea(idea_id)
    except FileNotFoundError:
        return _error("Idea not found.", 404)
    IdeaStore(_ideas_dir()).delete(idea_id)
    return jsonify({"deleted": idea_id})


@app.route("/api/ideas/<idea_id>/chat/start", methods=["POST"])
def start_idea_chat(idea_id):
    try:
        _load_idea(idea_id)
    except FileNotFoundError:
        return _error("Idea not found.", 404)
    store_mod = _import_cowriter("store")
    llm_mod = _import_cowriter("llm_client")
    context_mod = _import_cowriter("context")
    SessionStore = store_mod.SessionStore
    LlamaServerClient = llm_mod.LlamaServerClient
    ReportContext = context_mod.ReportContext
    try:
        from screenplay_cowriter.discovery import resolve_model
        client = LlamaServerClient(base_url=CONFIG["server_url"], timeout=CONFIG["timeout"], fallback_to_loaded=True)
        model_id = resolve_model(client, ReportContext(None), explicit_model=CONFIG["model"])
    except Exception:
        model_id = CONFIG["model"]
    store = SessionStore(IdeaStore(_ideas_dir()).sessions_dir(idea_id))
    # RESUME, don't abandon: an idea's Sameer conversation is one continuing
    # relationship. A reload (or a return visit) picks up the most recent
    # session; only a genuinely first summon (or after Clear chat) creates.
    existing = store.list()
    if existing:
        session = store.load(existing[0]["session_id"])
    else:
        session = store.create(title="Idea room")
    session.server_url = CONFIG["server_url"]
    session.model_id = model_id
    store.save(session)
    return jsonify({"session_id": session.session_id, "branch": session.current_branch})


@app.route("/api/ideas/<idea_id>/chat/sessions/<sid>", methods=["GET"])
def idea_get_session(idea_id, sid):
    try:
        session, _, _ = _load_idea_session_and_engine(idea_id, sid)
    except FileNotFoundError:
        return _error("Idea or session not found.", 404)
    except CowriterUnavailableError as e:
        return _error(str(e), 503)
    return jsonify(_idea_session_payload(session))


@app.route("/api/ideas/<idea_id>/chat/sessions/<sid>", methods=["DELETE"])
def idea_delete_session(idea_id, sid):
    """Clear the idea conversation — the premise card is kept."""
    try:
        _load_idea(idea_id)
        store_mod = _import_cowriter("store")
        SessionStore = store_mod.SessionStore
        store = SessionStore(IdeaStore(_ideas_dir()).sessions_dir(idea_id))
        store.load(sid)
        store.delete(sid)
    except FileNotFoundError:
        return _error("Idea or session not found.", 404)
    return jsonify({"deleted": sid})


@app.route("/api/ideas/<idea_id>/chat/sessions/<sid>/messages", methods=["POST"])
def idea_send_message(idea_id, sid):
    body = request.get_json() or {}
    text = (body.get("text") or "").strip()
    if not text:
        return _error("Message text is required.", 400)
    try:
        session, engine, store = _load_idea_session_and_engine(idea_id, sid)
    except FileNotFoundError:
        return _error("Idea or session not found.", 404)
    except CowriterUnavailableError as e:
        return _error(str(e), 500)
    try:
        # selection-to-reply works in the idea room too: a highlighted page
        # passage rides to the model exactly like a script quote
        reply = engine.send_message(session, text, quote=body.get("quote"))
    except Exception as e:
        # Same watchdog as the script chat route (see send_message above).
        if type(e).__name__ == "WatchdogTimeoutError" or "didn't respond within" in str(e):
            return jsonify({
                "error": "The model was still working when the per-turn time cap was hit.",
                "still_working": True,
            }), 408
        return _error(f"The model server couldn't be reached or returned an error: {e}", 502)
    # he READ the page this turn -- move the diff baseline (failed turns keep
    # the old baseline so the next attempt re-reports the same changes)
    session.last_seen_content = getattr(engine, "_current_page_content", None)
    store.save(session)
    return jsonify({
        "reply": reply,
        "branch": session.current_branch,
        "messages": [msg.to_dict() for msg in session.branch.messages],
    })


# ---------- local speech-to-text (dictation) ----------
from screenplay_studio import stt as _stt


@app.route("/api/stt", methods=["POST"])
def stt_transcribe():
    """Dictation: multipart audio in, transcribed text out. Fully local --
    faster-whisper in-process, or a user-run local whisper server."""
    f = request.files.get("audio")
    if f is None:
        return _error("No audio file part named 'audio' in the request.", 400)
    try:
        result = _stt.transcribe(f.read(), f.filename or "audio.webm",
                                 (request.form.get("language") or "auto"))
        return jsonify(result)
    except ValueError as e:
        return _error(str(e), 400)
    except _stt.STTUnavailableError as e:
        return _error(str(e), 503)
    except Exception as e:
        return _error(f"Transcription failed: {e}", 500)


@app.route("/api/stt/languages", methods=["GET"])
def stt_languages():
    return jsonify({"languages": _stt.supported_languages(),
                    "engine": "whisper-server" if _stt.EXTERNAL_WHISPER_URL else "faster-whisper"})


# ---------- ephemeral reply translation ----------
#
# "What does that mean?" -- render one assistant reply in plain English.
# The translation is DISPLAY-ONLY: never persisted to the branch, so the
# conversation keeps its mirrored register and Sameer never "remembers"
# having spoken the translated words.


# The honest target set: the registers this desk actually models. Anything
# else would be fake scope for local models.
_TRANSLATE_TARGETS = {
    "en": "plain, natural English",
    "te": "natural Telugu (Telugu script)",
    "hi": "natural Hindi (Devanagari script)",
    "teng": ("Tenglish -- Telugu written in Latin script, mixed naturally with "
             "English words, the way bilingual writers actually text"),
    "hing": ("Hinglish -- Hindi written in Latin script, mixed naturally with "
             "English words, the way bilingual writers actually text"),
}


def _translate_reply_payload(session, engine, index, target_lang="en"):
    target = (target_lang or "en").strip().lower()
    if target not in _TRANSLATE_TARGETS:
        return None, _error(
            f"Unknown translation target '{target}'. Supported: {', '.join(_TRANSLATE_TARGETS)}.", 400)
    msgs = session.branch.messages
    if not isinstance(index, int) or not (0 <= index < len(msgs)):
        return None, _error("Message index out of range.", 400)
    if msgs[index].role != "assistant":
        return None, _error("Only assistant replies can be translated.", 400)
    original = msgs[index].content.strip()
    persona = session.branch.active_persona
    sys_prompt = (
        f"[TRANSLATE TASK] Render the reply below in {_TRANSLATE_TARGETS[target]}. "
        "Keep the meaning and tone exactly -- no additions, no commentary, "
        "no disclaimers. Output only the translated reply. "
        f"[TRANSLATE TARGET: {target}]"
    )
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": original},
    ]
    try:
        raw = engine._generate(messages)
    except Exception as e:
        return None, _error(f"Translation failed: {e}", 502)
    cowriter_engine = _import_cowriter("engine")
    translation = cowriter_engine.clean_reply(raw)
    return {"index": index, "translation": translation}, None


@app.route("/api/ideas/<idea_id>/chat/sessions/<sid>/translate", methods=["POST"])
def idea_translate_message(idea_id, sid):
    body = request.get_json() or {}
    try:
        session, engine, store = _load_idea_session_and_engine(idea_id, sid)
    except FileNotFoundError:
        return _error("Idea or session not found.", 404)
    except CowriterUnavailableError as e:
        return _error(str(e), 503)
    payload, err = _translate_reply_payload(session, engine, body.get("index"), body.get("target_lang", "en"))
    return payload if payload is not None else err


@app.route("/api/projects/<name>/chat/sessions/<sid>/translate", methods=["POST"])
def project_translate_message(name, sid):
    body = request.get_json() or {}
    try:
        session, engine, store = _load_session_and_engine(name, sid)
    except FileNotFoundError:
        return _error("Project or session not found.", 404)
    payload, err = _translate_reply_payload(session, engine, body.get("index"), body.get("target_lang", "en"))
    return payload if payload is not None else err


@app.route("/api/ideas/<idea_id>/chat/sessions/<sid>/settings", methods=["POST"])
def idea_update_settings(idea_id, sid):
    """Room toggle in the idea room swaps the lens: Co-write = Sameer (explore),
    Feedback = premise doctor (validate) — same conversation, new partner."""
    body = request.get_json() or {}
    try:
        session, _, store = _load_idea_session_and_engine(idea_id, sid)
    except FileNotFoundError:
        return _error("Idea or session not found.", 404)
    except CowriterUnavailableError as e:
        return _error(str(e), 500)
    personas_mod = _import_cowriter("personas")
    PERSONAS = personas_mod.PERSONAS
    MODES = personas_mod.MODES
    persona = body.get("persona")
    mode = body.get("mode")
    if persona is not None and persona not in PERSONAS:
        return _error(f"Unknown persona '{persona}'.", 400)
    if mode is not None and mode not in MODES:
        return _error(f"Unknown mode '{mode}'.", 400)
    branch = session.branch
    if persona:
        branch.active_persona = persona
    if mode:
        branch.active_mode = mode
    store.save(session)
    return jsonify({"active_persona": branch.active_persona, "active_mode": branch.active_mode})


@app.route("/api/ideas/<idea_id>/graduate", methods=["POST"])
def graduate_idea(idea_id):
    """Upload the first pages: create a real project from the file, carry the
    premise card (premise.json) and the idea conversation (session files) so
    the thread continues on the script desk — same Sameer, same memory."""
    if "file" not in request.files:
        return _error("No file uploaded (expected multipart field 'file').", 400)
    upload = request.files["file"]
    if not upload.filename:
        return _error("Empty filename.", 400)
    try:
        _load_idea(idea_id)
    except FileNotFoundError:
        return _error("Idea not found.", 404)

    title = request.form.get("title") or os.path.splitext(upload.filename)[0]
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in title) or "project"
    project_dir = _project_dir(safe_name)
    suffix = 1
    while os.path.exists(project_dir):
        suffix += 1
        project_dir = _project_dir(f"{safe_name}_{suffix}")

    os.makedirs(project_dir, exist_ok=True)
    ext = os.path.splitext(upload.filename)[1].lower() or ".txt"
    tmp_path = os.path.join(project_dir, f"_upload{ext}")
    upload.save(tmp_path)
    try:
        manifest = ProjectManifest.create(project_dir, tmp_path, title=title)
        manifest.server_url = CONFIG["server_url"]
        manifest.timeout = CONFIG["timeout"]
        manifest.model_id = CONFIG["model"]
        manifest.save()
        os.remove(tmp_path)
        Orchestrator(manifest).run_parse()
    except Exception as e:
        return _error(f"Could not process uploaded file: {e}", 500)

    try:
        IdeaStore(_ideas_dir()).carry_into_project(idea_id, project_dir)
    except Exception:
        pass  # the pages are the point; a failed carry never blocks graduation

    # pin the carried conversation so the script desk opens on the same thread
    try:
        sessions = sorted(
            fn for fn in os.listdir(os.path.join(project_dir, "sessions")) if fn.endswith(".json")
        )
        if sessions:
            latest = max(sessions, key=lambda fn: os.path.getmtime(os.path.join(project_dir, "sessions", fn)))
            manifest.cowriter_session_id = os.path.splitext(latest)[0]
            manifest.save()
    except Exception:
        pass

    return jsonify(_manifest_summary(manifest)), 201


def main():
    global PROJECTS_DIR, CONFIG
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8500)
    parser.add_argument("--projects-dir", default="./studio_projects")
    parser.add_argument("--server", default="http://localhost:8080", help="Default llama-server URL")
    parser.add_argument("--demo-model", action="store_true",
                        help="Run with the built-in demo craft model instead of a real "
                             "llama-server — the whole desk (analysis, chat, streaming) "
                             "works live without a GGUF. Testing only; the default flow "
                             "(your llama-server on :8080) is untouched.")
    args = parser.parse_args()

    PROJECTS_DIR = args.projects_dir
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    # env-var demo trigger already pointed CONFIG at the demo server at import
    # time -- don't clobber it back to :8080 (keeps flag/env parity honest).
    if not _DEMO_MODEL_ACTIVE:
        CONFIG["server_url"] = args.server
    if args.demo_model:
        _use_demo_model()

    print(f"Projects directory: {os.path.abspath(PROJECTS_DIR)}")
    print(f"Default model server: {CONFIG['server_url']}")
    print(f"Open http://localhost:{args.port} in your browser.")
    app.run(host="127.0.0.1", port=args.port, debug=False)


_DEMO_MODEL_ACTIVE = False


def _use_demo_model() -> str:
    """Point CONFIG at the built-in demo craft model (started in-process).
    Opt-in only — never runs unless asked for by flag or env."""
    global _DEMO_MODEL_ACTIVE
    try:
        from .demo_model import start_demo_server
        url = start_demo_server()
        CONFIG["server_url"] = url
        _DEMO_MODEL_ACTIVE = True
        print("DEMO MODEL active (in-process) — no real llama-server needed.")
        return url
    except Exception as e:  # demo is a convenience — never block startup on it
        print("Demo model unavailable; keeping the configured server.")
        return CONFIG["server_url"]


# The flask CLI path (`flask --app screenplay_studio.webapp_server run`) never
# calls main(), so startup gating happens here at import. Two ways in:
#   1. SCREENPLAY_STUDIO_DEMO_MODEL=1 — explicit demo mode (env/flag parity)
#   2. Auto-fallback: the configured model server is unreachable at startup,
#      so instead of a dead desk, run on the built-in demo craft model.
# A reachable llama-server ALWAYS wins — the real flow is never hijacked.
_DEMO_ENV = os.environ.get("SCREENPLAY_STUDIO_DEMO_MODEL", "").strip()
if _DEMO_ENV not in ("", "0", "false"):
    _use_demo_model()
else:
    def _server_reachable(url: str) -> bool:
        try:
            from screenplay_analyzer.llm_client import LlamaServerClient
            return LlamaServerClient(base_url=url).is_reachable()
        except Exception:
            return False

    under_pytest = bool(os.environ.get("PYTEST_CURRENT_TEST")) or \
        any("pytest" in str(a).lower() for a in __import__("sys").argv)
    if not under_pytest and not _server_reachable(CONFIG["server_url"]):
        print("Configured model server is unreachable at startup — falling back "
              "to the built-in DEMO craft model so the desk still works.")
        print("It is used again automatically whenever your llama-server is up; "
              "set SCREENPLAY_STUDIO_DEMO_MODEL=0 to disable this fallback.")
        _use_demo_model()


if __name__ == "__main__":
    main()
