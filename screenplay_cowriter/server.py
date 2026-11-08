"""
HTTP server for Piece 3, matching the "each piece runs its own local
server" architecture from the original scoping. The CLI (cli.py) is a
direct-library client; this is for any future frontend/UI to integrate
against instead of shelling out to the CLI.

Usage:
    python -m screenplay_cowriter.server --port 8300 --sessions-dir ./sessions
"""

import argparse
from urllib.parse import urlparse

from flask import Flask, request, jsonify

from .store import SessionStore
from .models import Session
from .llm_client import LlamaServerClient, LlamaServerError
from .context import ScriptContext, ReportContext, load_json
from .discovery import resolve_model
from .engine import CoWriterEngine
from .personas import PERSONAS, MODES

app = Flask(__name__)
store: SessionStore = None  # set in main()
memory_path: str = None  # optional writer relationship memory file (set in main())


# Gap 83: this server was a documented front door that the architecture documents
# said did not exist, and it had NONE of the webapp's guards. It binds 127.0.0.1,
# which is why the filing is honest that no exposure was demonstrated — but a
# browser on the same machine can still reach a loopback port, and "it only listens
# locally" is a statement about the socket, not about who can drive it. The webapp
# learned this (BE-H1/BE-4): a foreign `Host` header is refused, because DNS
# rebinding makes a name that resolves to 127.0.0.1 arrive with a Host header that
# is not local. Same predicate, same answer, stated here rather than assumed to
# have been inherited.
#
# Deliberately NOT copied: the webapp's capability token. That token guards
# state-changing routes in a browser UI; this server is a scripted API whose only
# tested use is a direct client, and bolting a cookie/token dance onto it would
# break every caller to defend a surface nobody browses. Recorded as a limit in
# docs/API_ROUTE_MAP.md instead of half-implemented here.
def _host_header_is_local() -> bool:
    raw = request.host or ""
    # Reject userinfo/path/whitespace BEFORE parsing: urlparse reads
    # `evil.com@127.0.0.1` as loopback and would accept it.
    if not raw or any(ch in raw for ch in "@\\/ \t"):
        return False
    try:
        host = urlparse(f"//{raw}").hostname
    except ValueError:
        return False
    if not host:
        return False
    host = host.rstrip(".").lower()
    if host == "localhost":
        return True
    if host == "::1":
        return True
    parts = host.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return parts[0] == "127"
    return False


@app.before_request
def _reject_foreign_host():
    """Every method, reads included — the same rule the desk applies."""
    if not _host_header_is_local():
        return jsonify({"error": "request rejected: this server answers only to "
                                 "its own loopback address",
                        "host_rejected": True}), 403
    return None


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
        "requested_model_id": session.requested_model_id,
        "model_request_recorded": session.model_request_recorded,
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
    server_url = body.get("server_url", "http://localhost:8080")
    requested_model_id = body.get("model")
    draft = Session.new(
        title=body.get("title", "Untitled"),
        report_path=body.get("report_path"),
        script_path=body.get("script_path"),
    )
    client = LlamaServerClient(base_url=server_url, model=requested_model_id)
    _, report_ctx = _load_contexts(draft)
    try:
        model_id = resolve_model(client, report_ctx, explicit_model=requested_model_id)
    except LlamaServerError as e:
        return jsonify({"error": str(e)}), 502

    session = store.create(
        title=draft.title, report_path=draft.report_path, script_path=draft.script_path)
    session.server_url = server_url
    session.model_id = model_id
    session.requested_model_id = requested_model_id
    session.model_request_recorded = True
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

    client = LlamaServerClient(base_url=session.server_url, model=session.model_id,
                               fallback_to_loaded=False)
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
        store.save(session, owns_selection=True)
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
        store.save(session, owns_selection=True)
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
    store.save(session, owns_selection=True)
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
