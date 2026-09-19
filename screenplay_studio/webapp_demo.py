"""Demo-mode entrypoint: the webapp WITH the built-in demo craft model.

    python -m screenplay_studio.webapp_demo

Delegates to `screenplay_studio.webapp_server.main` with `--demo-model` forced
and the `PORT` env mapped to `--port`. Token minting and the loopback bind come
from `main()`, so this alias is exactly as safe as the canonical launch.
"""

import os

os.environ["SCREENPLAY_STUDIO_DEMO_MODEL"] = "1"

from .webapp_server import _use_demo_model  # noqa: E402


def main():
    _use_demo_model()  # env var alone also triggers it at import; explicit is clearer
    port = os.environ.get("PORT")
    import sys  # noqa: E402
    from .webapp_server import main as server_main  # noqa: E402
    # B2 (audit 2026-09-20): delegate to the canonical launch so the capability
    # token is minted by default and the bind stays loopback. The old code ran
    # the Flask app directly on ALL interfaces, skipped main(), left _API_TOKEN
    # = None, and exposed every route — including DELETE — to the LAN. PORT env
    # still maps to --port; --demo-model is explicit; the rest passes through.
    sys.argv = [sys.argv[0], "--demo-model", *(["--port", port] if port else []), *sys.argv[1:]]
    server_main()


if __name__ == "__main__":
    main()
