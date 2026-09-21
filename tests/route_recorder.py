"""Route-exercise recorder (T2c).

Every test drives the same module-level Flask app objects
(``screenplay_studio.webapp_server.app`` and ``screenplay_cowriter.server.app``),
so a single ``before_request`` hook on each sees every request any test makes --
from any file, and through ``test_client()`` calls.

This exists because the alternative -- grepping the test tree for route path
strings -- is a heuristic that was measured wrong in **both** directions:

* it reported ``/beatboard/reset`` as unreached, but
  ``test_beatboard.py::test_reset_endpoint`` drives it (the test composes the
  path as ``f"{base}/reset"``, so the full string never appears); and
* it credited ``screenplay_cowriter.server`` with the *webapp's*
  ``/api/.../chat/sessions`` paths, making a genuinely zero-coverage module look
  6/7 covered.

Recording the request is the only way to tell "a test mentions this path" from
"a test exercises this route".
"""

HITS: dict[str, set] = {"webapp": set(), "cowriter": set()}


def record(app_key: str, rule: str, method: str) -> None:
    HITS[app_key].add((rule, method))


def _attach(app, key: str) -> None:
    if getattr(app, "_route_recorder_installed", False):
        return
    from flask import request

    def _hook():  # pragma: no cover - exercised by every request
        rule = getattr(request, "url_rule", None)
        if rule is not None:  # None on a 404: no route matched
            record(key, rule.rule, request.method)

    app.before_request(_hook)
    app._route_recorder_installed = True


def install() -> None:
    """Attach the recorder to both apps. Idempotent and failure-tolerant."""
    try:
        from screenplay_studio import webapp_server
        _attach(webapp_server.app, "webapp")
    except Exception:  # noqa: BLE001 - instrumentation must never break the suite
        pass
    try:
        from screenplay_cowriter import server as cow_server
        _attach(cow_server.app, "cowriter")
    except Exception:  # noqa: BLE001
        pass
