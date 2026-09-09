"""
Demo-mode entrypoint: the webapp WITH the built-in demo craft model, bound to
0.0.0.0:$PORT (Freebuff-style hosting). Testing/deployment convenience only —

    python -m screenplay_studio.webapp_demo

The canonical launch (`python -m screenplay_studio.webapp_server`) is untouched
and still defaults to your real llama-server on :8080.
"""

import os

os.environ["SCREENPLAY_STUDIO_DEMO_MODEL"] = "1"

from .webapp_server import _use_demo_model  # noqa: E402
from .webapp_server import app  # noqa: E402


def main():
    _use_demo_model()  # env var alone also triggers it at import; explicit is clearer
    port = int(os.environ.get("PORT", "8500"))
    print(f"Demo desk on http://0.0.0.0:{port} — analysis, chat and streaming run "
          "on the built-in demo craft model (no GGUF needed).")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
