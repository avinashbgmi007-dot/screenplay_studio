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
import re
import time
import traceback

from flask import Flask, request, jsonify, send_from_directory, send_file

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

    _DEFAULTS = {"server_url": "http://localhost:8080", "model": None, "timeout": 600}

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
        if key == "model" and value == "":
            value = None
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
    }


def _make_client(m: ProjectManifest):
    from screenplay_analyzer.llm_client import LlamaServerClient
    return LlamaServerClient(base_url=m.server_url, model=m.model_id, timeout=m.timeout)


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
    return jsonify(_manifest_summary(m))


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
    try:
        orch.run_analyze(report_language=report_language)
    except OrchestratorError as e:
        return _error(str(e), 502)
    except Exception as e:
        traceback.print_exc()
        return _error(f"Unexpected error during analysis: {e}", 500)

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


# ---------- writer's margin notes ----------

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
        note = add_note(m, body.get("scene_number"), body.get("text", ""))
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
    except ValueError as e:
        return _error(str(e), 404)
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
    return jsonify({**result, "findings_status": statuses})


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
    """Latest per-stage analysis progress (written by the pipeline callback)."""
    try:
        m = _load_manifest(name)
    except FileNotFoundError:
        return _error("Project not found.", 404)
    if not os.path.exists(m.progress_path):
        stage = m.stage("analyze").status
        return jsonify({"stage": "done" if stage == "complete" else "idle", "status": "complete" if stage == "complete" else "idle", "detail": ""})
    with open(m.progress_path, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))


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
    return jsonify({"items": items, "acts": acts})


# ---------- shareable report export ----------


def _md_to_html(md: str) -> str:
    """Tiny, dependency-free markdown -> HTML renderer for the report. Handles
    the subset report.py emits: #/##/### headings, **bold**, *italic*, tables,
    - bullets, hr, and paragraphs."""
    import html as _html
    from html import escape

    lines = md.split("\n")
    out, para, in_list, in_table = [], [], False, False

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
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                continue  # separator row
            tag = "th" if out.count("<tr>") == 0 and not any("<th" in o for o in out[-2:]) else "td"
            out.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
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
    client = LlamaServerClient(base_url=session.server_url or CONFIG["server_url"], model=session.model_id, timeout=CONFIG["timeout"])
    memory = None
    try:
        mem_mod = _import_cowriter("memory")
        memory = mem_mod.WriterMemory.load(os.path.join(PROJECTS_DIR, "writer_profile.json"))
    except (CowriterUnavailableError, OSError, ValueError):
        memory = None  # memory unavailable or unreadable — never break the chat
    engine = CoWriterEngine(client, script_ctx, report_ctx, store=store, memory=memory)
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

    try:
        reply = engine.send_message(session, text)
    except Exception as e:
        return _error(f"The model server couldn't be reached or returned an error: {e}", 502)

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
    return jsonify({"profile": mem.to_dict(), "card": mem.card_text()})


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
        session, _, _ = _load_session_and_engine(project, session_id)
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
                                       model=session.model_id, timeout=CONFIG["timeout"])
    recent = [m.to_dict() for m in session.branch.messages[-16:]]
    mem.refresh(client, recent)
    return jsonify({"profile": mem.to_dict(), "card": mem.card_text()})


def main():
    global PROJECTS_DIR, CONFIG
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8500)
    parser.add_argument("--projects-dir", default="./studio_projects")
    parser.add_argument("--server", default="http://localhost:8080", help="Default llama-server URL")
    args = parser.parse_args()

    PROJECTS_DIR = args.projects_dir
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    CONFIG["server_url"] = args.server

    print(f"Projects directory: {os.path.abspath(PROJECTS_DIR)}")
    print(f"Default model server: {CONFIG['server_url']}")
    print(f"Open http://localhost:{args.port} in your browser.")
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
