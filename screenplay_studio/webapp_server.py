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
import os
import traceback

from flask import Flask, request, jsonify, send_from_directory

from .manifest import ProjectManifest
from .orchestrator import Orchestrator, OrchestratorError

WEBAPP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp")

app = Flask(__name__, static_folder=None)

# Set by main() at startup — kept module-level for simplicity, matching
# the same pattern already used in screenplay_cowriter/server.py.
PROJECTS_DIR = "./studio_projects"
CONFIG = {"server_url": "http://localhost:8080", "model": None, "timeout": 600}


# ---------- static frontend ----------

@app.route("/")
def index():
    return send_from_directory(WEBAPP_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(WEBAPP_DIR, filename)


# ---------- helpers ----------

def _project_dir(name: str) -> str:
    return os.path.join(PROJECTS_DIR, name)


def _load_manifest(name: str) -> ProjectManifest:
    return ProjectManifest.load(_project_dir(name))


def _manifest_summary(m: ProjectManifest) -> dict:
    sessions = []
    if os.path.isdir(m.sessions_dir):
        from screenplay_cowriter.store import SessionStore
        store = SessionStore(m.sessions_dir)
        sessions = store.list()
    return {
        "project": os.path.basename(m.project_dir),
        "title": m.title,
        "server_url": m.server_url,
        "model_id": m.model_id,
        "stages": {name: s.status for name, s in m.stages.items()},
        "errors": {name: s.error for name, s in m.stages.items() if s.error},
        "sessions": sessions,
    }


def _error(message: str, status: int = 400):
    return jsonify({"error": message}), status


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
    return jsonify(CONFIG)


@app.route("/api/config", methods=["POST"])
def set_config():
    body = request.get_json() or {}
    if "server_url" in body:
        CONFIG["server_url"] = body["server_url"]
    if "model" in body:
        CONFIG["model"] = body["model"] or None
    if "timeout" in body:
        try:
            t = int(body["timeout"])
            CONFIG["timeout"] = t if t > 0 else CONFIG["timeout"]
        except (TypeError, ValueError):
            pass
    return jsonify(CONFIG)


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

    orch = Orchestrator(m)
    try:
        orch.run_analyze()
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
    import json
    with open(m.report_findings_path, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))


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
    from screenplay_cowriter.store import SessionStore
    from screenplay_cowriter.context import ScriptContext, ReportContext, load_json
    from screenplay_cowriter.engine import CoWriterEngine
    from screenplay_cowriter.llm_client import LlamaServerClient

    m = _load_manifest(project)
    store = SessionStore(m.sessions_dir)
    session = store.load(session_id)

    report_path = m.report_findings_path if m.stage("analyze").status == "complete" else None
    script_ctx = ScriptContext(load_json(m.parsed_path))
    report_ctx = ReportContext(load_json(report_path) if report_path else None)
    client = LlamaServerClient(base_url=session.server_url or CONFIG["server_url"], model=session.model_id, timeout=CONFIG["timeout"])
    engine = CoWriterEngine(client, script_ctx, report_ctx)
    return session, engine, store


@app.route("/api/projects/<name>/chat/sessions/<sid>", methods=["GET"])
def get_session(name, sid):
    try:
        session, _, _ = _load_session_and_engine(name, sid)
    except FileNotFoundError:
        return _error("Session or project not found.", 404)
    return jsonify({
        "session_id": session.session_id,
        "title": session.title,
        "current_branch": session.current_branch,
        "branches": {
            bname: {
                "messages": [msg.to_dict() for msg in b.messages],
                "parent_branch": b.parent_branch,
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

    store.save(session)
    return jsonify({"current_branch": session.current_branch})


@app.route("/api/projects/<name>/chat/sessions/<sid>/settings", methods=["POST"])
def update_settings(name, sid):
    from screenplay_cowriter.personas import PERSONAS, MODES

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

    if persona:
        session.branch.active_persona = persona
    if mode:
        session.branch.active_mode = mode
    store.save(session)
    return jsonify({"active_persona": session.branch.active_persona, "active_mode": session.branch.active_mode})


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
