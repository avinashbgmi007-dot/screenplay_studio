"""Static frontend route blueprint."""
from flask import Blueprint, send_from_directory


def create_static_blueprint():
    bp = Blueprint("static_routes", __name__)

    @bp.route("/")
    def index():
        from screenplay_studio.state import state
        resp = send_from_directory(state.WEBAPP_DIR, "index.html")
        resp.headers["Cache-Control"] = "no-cache"
        return state._serve_spa_document(resp)

    @bp.route("/<path:filename>")
    def static_files(filename):
        from screenplay_studio.state import state
        resp = send_from_directory(state.WEBAPP_DIR, filename)
        resp.headers["Cache-Control"] = "no-cache"
        if filename == "index.html":
            state._serve_spa_document(resp)
        return resp

    return bp
