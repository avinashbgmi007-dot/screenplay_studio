"""
HTTP server for Piece 3, matching the "each piece runs its own local
server" architecture from the original scoping. The CLI (cli.py) is a
direct-library client; this is for any future frontend/UI to integrate
against instead of shelling out to the CLI.

Usage:
    python -m screenplay_cowriter.server --port 8300 --sessions-dir ./sessions
"""

import argparse

from flask import Flask, request, jsonify

from .store import SessionStore
from .llm_client import LlamaServerClient, LlamaServerError
from .context import ScriptContext, ReportContext, load_json
from .discovery import resolve_model
from .engine import CoWriterEngine
from .personas import PERSONAS, MODES

app = Flask(__name__)
store: SessionStore = None  # set in main()
memory_path: str = None  # optional writer relationship memory file (set in main())


def _load_contexts(session):
    script_data = load_json(session.script_path) if session.script_path else {}
    report_data = load_json(session.report_path) if session.report_path else {}
    return ScriptContext(script_data), ReportContext(report_data)


def _session_summary(session):
    return {
        "session_id": session.session_id,
        "title": session.title,
        "current_branch": session.current_branch,
        "branches": {name: len(b.messages) for name, b in session.branches.items()},
        "model_id": session.model_id,
        "server_url": session.server_url,
    }


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/sessions", methods=["GET"])
def list_sessions():
    return jsonify(store.list())


@app.route("/sessions", methods=["POST"])
def create_session():
    body = request.get_json()
    session = store.create(
        title=body.get("title", "Untitled"),
        report_path=body.get("report_path"),
        script_path=body.get("script_path"),
    )
    server_url = body.get("server_url", "http://localhost:8080")
    client = LlamaServerClient(base_url=server_url, model=body.get("model"))
    _, report_ctx = _load_contexts(session)
    try:
        model_id = resolve_model(client, report_ctx, explicit_model=body.get("model"))
    except LlamaServerError as e:
        return jsonify({"error": str(e)}), 502

    session.server_url = server_url
    session.model_id = model_id
    store.save(session)
    return jsonify(_session_summary(session)), 201


@app.route("/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    try:
        session = store.load(session_id)
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        **_session_summary(session),
        "messages": [m.to_dict() for m in session.branch.messages],
    })


@app.route("/sessions/<session_id>/messages", methods=["POST"])
def send_message(session_id):
    body = request.get_json()
    text = body.get("text", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    try:
        session = store.load(session_id)
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404

    client = LlamaServerClient(base_url=session.server_url, model=session.model_id)
    script_ctx, report_ctx = _load_contexts(session)
    memory = None
    if memory_path:
        from .memory import WriterMemory
        memory = WriterMemory.load(memory_path)
    engine = CoWriterEngine(client, script_ctx, report_ctx, store=store, memory=memory)

    try:
        reply = engine.send_message(session, text)
    except LlamaServerError as e:
        return jsonify({"error": str(e)}), 502

    store.save(session)
    return jsonify({"reply": reply, "branch": session.current_branch})


@app.route("/sessions/<session_id>/fork", methods=["POST"])
def fork_session(session_id):
    body = request.get_json()
    name = body.get("name")
    if not name:
        return jsonify({"error": "name is required"}), 400
    try:
        session = store.load(session_id)
        session.fork(name, from_branch=body.get("from_branch"))
        store.save(session)
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_session_summary(session))


@app.route("/sessions/<session_id>/switch", methods=["POST"])
def switch_branch(session_id):
    body = request.get_json()
    name = body.get("name")
    try:
        session = store.load(session_id)
        session.switch(name)
        store.save(session)
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_session_summary(session))


@app.route("/sessions/<session_id>/settings", methods=["POST"])
def update_settings(session_id):
    body = request.get_json()
    try:
        session = store.load(session_id)
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404

    persona = body.get("persona")
    mode = body.get("mode")
    if persona and persona not in PERSONAS:
        return jsonify({"error": f"unknown persona, available: {list(PERSONAS.keys())}"}), 400
    if mode and mode not in MODES:
        return jsonify({"error": f"unknown mode, available: {list(MODES.keys())}"}), 400

    if persona:
        session.branch.active_persona = persona
    if mode:
        session.branch.active_mode = mode
    store.save(session)
    return jsonify(_session_summary(session))


def main():
    global store, memory_path
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8300)
    parser.add_argument("--sessions-dir", default="./sessions")
    parser.add_argument("--memory-path", default=None, help="Optional writer relationship memory file")
    args = parser.parse_args()
    store = SessionStore(args.sessions_dir)
    memory_path = args.memory_path
    app.run(host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
