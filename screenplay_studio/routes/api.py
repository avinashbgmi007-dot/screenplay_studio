"""API route blueprint."""
from flask import Blueprint, jsonify, request

from screenplay_studio.state import state

api_bp = Blueprint("api_routes", __name__)


def register_api_routes(bp):

    @bp.route("/api/test-connection", methods=["POST"])
    def test_connection():
        body = request.get_json() or {}
        url = (body.get("server_url") or state.CONFIG["server_url"]).rstrip("/")
        # This route GETs {url}/v1/models for whatever it is handed, so it is an
        # outbound primitive in its own right — guard it before the probe, not after.
        state._validate_server_url(url)
        from screenplay_analyzer.llm_client import LlamaServerClient, LlamaServerError

        # The token typed into the form (not yet saved) wins, so "Test Connection"
        # answers the question the writer is actually asking — does THIS URL, with
        # THIS token, work — instead of testing the last saved one.
        key = body["api_key"] if "api_key" in body else state.CONFIG.get("api_key")
        client = LlamaServerClient(base_url=url, timeout=15, extra_headers=state._auth_headers(key))
        try:
            models = client.list_models()
        except LlamaServerError as e:
            return jsonify({"ok": False, "message": str(e)})

        ids = [m.get("id") or m.get("name") for m in models if isinstance(m, dict)]
        ids = [i for i in ids if i]
        if not ids:
            return jsonify({"ok": False, "message": f"Connected to {url}, but it reports no loaded model."})
        mode = state.connection_mode(url)
        return jsonify({"ok": True, "message": f"Connected ({mode}) — model loaded: {ids[0]}",
                        "models": ids, "mode": mode})




    @bp.route("/api/real-server-check", methods=["GET"])
    def real_server_check():
        """While the demo fallback is active: is the writer's real llama-server
        back? Drives the status strip's click-to-switch affordance."""
        if not state._DEMO_MODEL_ACTIVE:
            return jsonify({"demo": False})
        url = state.CONFIG.get("real_server_url")
        if not url:
            return jsonify({"demo": True, "available": False})
        from screenplay_analyzer.llm_client import LlamaServerClient
        try:
            models = LlamaServerClient(base_url=url, timeout=5,
                                       extra_headers=state._auth_headers(state.CONFIG.get("api_key"))).list_models()
            ids = [m.get("id") or m.get("name") for m in models if isinstance(m, dict)]
            return jsonify({"demo": True, "available": bool(ids),
                            "url": url, "models": [i for i in ids if i]})
        except Exception:
            return jsonify({"demo": True, "available": False, "url": url})




    @bp.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "server_url": state.CONFIG.get("server_url"),
                        "demo_model": state._DEMO_MODEL_ACTIVE,
                        "code_rev": state._CODE_REV_AT_STARTUP})




    @bp.route("/api/rules/<rule_id>", methods=["GET"])
    def get_rule(rule_id):
        """spec §7: a card may claim "grounded in knowledge-base rule <id>", so the
        desk has to be able to answer *says who?*. This is a read of the shipped
        knowledge base — no model call, and an id that isn't a rule is a 404 rather
        than a popover that invents an authority."""
        kb = state._knowledge_base()
        if kb is None:
            return state._error("The knowledge base isn't installed, so this rule "
                          "cannot be looked up.", 503)
        try:
            rule = kb.get(rule_id)
        except KeyError:
            return state._error(f"No knowledge-base rule with id '{rule_id}'.", 404)
        return jsonify({"id": rule.id, "name": rule.name, "source": rule.attribution})




    @bp.route("/api/config", methods=["GET"])
    def get_config():
        cfg = state.CONFIG.to_dict()
        # The token is a secret and this response is readable by any page that can
        # reach the desk. Report only WHETHER one is set; the value never leaves.
        cfg["api_key_set"] = bool(cfg.pop("api_key", None))
        cfg["connection_mode"] = state.connection_mode()
        # Whether a remote URL is permitted at all is a launch-time decision, and the
        # form has to know it to enable or explain the Remote API option.
        cfg["allow_remote"] = bool(state._ALLOW_REMOTE_SERVER)
        # Personas/modes come from the co-writer so the frontend dropdown never
        # drifts from the server's canonical list (falls back to empty when the
        # co-writer isn't installed; the UI then shows its built-in defaults).
        cfg["demo_model"] = state._DEMO_MODEL_ACTIVE
        if state._DEMO_MODEL_ACTIVE:
            cfg["real_server_url"] = state.CONFIG.get("real_server_url")
        else:
            cfg.pop("real_server_url", None)  # to_dict picks up the stashed key
        try:
            personas_mod = state._import_cowriter("personas")
            cfg["personas"] = [p for p in personas_mod.PERSONAS
                               if not p.endswith("_examples")]
            cfg["modes"] = [m for m in personas_mod.MODES
                            if not m.endswith("_examples")]
        except state.CowriterUnavailableError:
            cfg["personas"] = []
            cfg["modes"] = []
        return jsonify(cfg)




    @bp.route("/api/config", methods=["POST"])
    def set_config():
        body = request.get_json() or {}
        # ---- the mode switch (see `connection_mode` above) ---------------------
        # "remote" is refused while the process opt-in is off. That is the whole
        # point of keeping the opt-in at launch: if this request could grant it,
        # the request that names the remote host would authorise sending the script
        # there, and the guard would be decorative.
        if "connection_mode" in body:
            mode = str(body.get("connection_mode") or "").strip().lower()
            if mode not in ("local", "remote"):
                raise ValueError("connection_mode must be 'local' or 'remote'")
            if mode == "remote":
                state._require_remote_optin()
                if not body.get("server_url"):
                    raise ValueError(
                        "A remote connection needs its API base URL — e.g. "
                        "https://api.example.com/v1 for an OpenAI-compatible endpoint.")
            elif "server_url" not in body:
                # "Go local" fills the local info in for you: back to the default
                # llama-server, token cleared, so switching modes is one click and
                # never leaves a remote URL pointed at a local-only desk.
                state.CONFIG["server_url"] = state.ServerConfig._DEFAULTS["server_url"]
                state.CONFIG["api_key"] = None
        if "server_url" in body:
            state.CONFIG["server_url"] = body["server_url"]
            # pointing at anything other than the demo IS the switch back:
            # the demo thread keeps running but stops answering the desk
            if state._DEMO_MODEL_ACTIVE and state.CONFIG["server_url"] != state._DEMO_URL:
                state._DEMO_MODEL_ACTIVE = False
        if "api_key" in body:
            state.CONFIG["api_key"] = body["api_key"]
        if "model" in body:
            state.CONFIG["model"] = body["model"] or None
        if "fast_model" in body:
            state.CONFIG["fast_model"] = body["fast_model"] or None
        if "turn_timeout" in body:
            state.CONFIG["turn_timeout"] = body["turn_timeout"]
        if "timeout" in body:
            try:
                state.CONFIG["timeout"] = int(body["timeout"])
            except (TypeError, ValueError):
                pass  # invalid timeout ignored — keep the current value
        if "server_url" in body or "api_key" in body or "model" in body:
            # the writer changed WHERE the model lives or HOW to reach it — carry
            # that to every existing project too. Without this, projects keep a
            # stale per-project server_url (e.g. an old port) and every LLM call
            # (chat, rewrite, analyze) silently hits a dead server while the status
            # strip shows green (it tests the global URL, not the manifest's).
            state._sync_server_url_to_projects(
                state.CONFIG["server_url"],
                body["model"] if "model" in body else state._UNSET,
                api_key=body["api_key"] if "api_key" in body else state._UNSET,
            )
        cfg = state.CONFIG.to_dict()
        cfg["api_key_set"] = bool(cfg.pop("api_key", None))
        cfg["connection_mode"] = state.connection_mode()
        cfg["allow_remote"] = bool(state._ALLOW_REMOTE_SERVER)
        return jsonify(cfg)


    # ---------- projects ----------

    @bp.route("/api/projects", methods=["GET"])
    def list_projects():
        import os
        if not os.path.isdir(state.PROJECTS_DIR):
            return jsonify([])
        out = []
        for name in sorted(os.listdir(state.PROJECTS_DIR)):
            # writer_profile.json is the co-writer's relationship-memory store —
            # internal data, not a project. It must never appear as a shelf card.
            if name == "writer_profile.json":
                continue
            # jsonio drops a `<store>.lock` sidecar beside every store it writes, and
            # one of those (writer_profile.json.lock) lands in this very directory.
            # A lock file is a FILE, not a project: without this it reached
            # _project_dir -> check_safe_id, which rejects the '.' in the name, and
            # the `except Exception` below then rendered it as a phantom
            # "unreadable" project on the writer's shelf.
            if not os.path.isdir(os.path.join(state.PROJECTS_DIR, name)):
                continue
            try:
                m = state.ProjectManifest.load(state._project_dir(name))
                out.append(state._manifest_summary(m))
            except FileNotFoundError:
                continue  # not a project (stray file / the ideas store)
            except Exception:
                # Flag, don't drop: a damaged manifest stays visible on the shelf
                # so the writer knows it exists and can remove it. Empty stage
                # dicts keep every frontend reader (stageLabel/dot/steps) safe.
                out.append({
                    "project": name,
                    "title": name,
                    "unreadable": True,
                    "stages": {"parse": {}, "analyze": {}, "chat": {}},
                    "sessions": [],
                })
        out.sort(key=lambda p: p.get("title", ""))
        return jsonify(out)




    @bp.route("/api/projects/<name>", methods=["GET"])
    def get_project(name):
        try:
            m = state._load_manifest(name)
        except FileNotFoundError:
            return state._error("Project not found.", 404)
        data = state._manifest_summary(m)
        # An idea that graduated carries its premise card alongside the pages.
        # Missing is a legitimate empty; UNREADABLE is damage and says so (A3).
        card, perr = state._load_premise(m.project_dir)
        if card is not None:
            data["premise"] = card
        if perr:
            data["premise_error"] = perr
        return jsonify(data)




    @bp.route("/api/projects/<name>/report", methods=["GET"])
    def get_report(name):
        try:
            m = state._load_manifest(name)
        except FileNotFoundError:
            return state._error("Project not found.", 404)
        if m.stage("analyze").status != "complete":
            return state._error("Analysis hasn't completed for this project yet.", 400)
        try:
            report = state._load_report_sanitized(m)
        except FileNotFoundError:
            # The manifest claims a finished analyze and the report is not on disk.
            # That is a missing fact, not a bad request and not a server fault worth
            # a stack trace: 404, worded, with no path in it.
            return state._error("The analysis report is missing from this project. Re-run "
                          "Analysis to produce one.", 404)
        return jsonify(report)




    @bp.route("/api/projects/<name>/passes", methods=["GET"])
    def get_pass_history(name):
        """spec §15.4: the revision arc — one entry per analysis this project has had.

        The store's own contract answers a damaged file (the global StoreUnreadable
        handler turns it into a 503 that says so), because "passes": [] here would
        read as "you have never analysed this script" to a writer with a history.
        """
        try:
            m = state._load_manifest(name)
        except FileNotFoundError:
            return state._error("Project not found.", 404)
        from screenplay_studio.pass_history import load_passes
        return jsonify({"passes": load_passes(m)})




    @bp.route("/api/projects/<name>/characters", methods=["GET"])
    def get_character_tracks(name):
        """Per-character track layer — presence, traits, interactions, reads —
        assembled from the knowledge graph + report. Instant (no model calls)."""
        try:
            m = state._load_manifest(name)
        except FileNotFoundError:
            return state._error("Project not found.", 404)
        report = None
        import os
        if m.stage("analyze").status == "complete" and os.path.exists(m.report_findings_path):
            report = state._load_report_sanitized(m)
        from screenplay_studio.character_track import build_character_tracks
        return jsonify({"characters": build_character_tracks(m.kg_path, report)})


    # ---------- writer's margin notes ----------

    # ---------- the Stash (saved snippets beside the script) ----------

    @bp.route("/api/projects/<name>/stash", methods=["POST"])


    @bp.route("/api/projects/<name>/stash", methods=["GET"])
    def get_stash(name):
        try:
            m = state._load_manifest(name)
        except FileNotFoundError:
            return state._error("Project not found.", 404)
        from screenplay_studio.stash_store import load_stash
        return jsonify({"stash": load_stash(m.project_dir)})




    return bp
