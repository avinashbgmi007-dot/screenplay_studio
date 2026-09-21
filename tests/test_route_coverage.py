"""Route-coverage guard (T2c).

**Why this exists.** The audit's route claim was adjudicated by hand in pass 4,
and the hand sweep was wrong in *both* directions -- it missed a route whose path
is composed (`f"{base}/reset"`) and it credited `screenplay_cowriter.server` with
the webapp's own `/api/.../chat/sessions` paths, which made an entire
zero-coverage module look 6/7 covered. That is how a whole HTTP surface sat
untested without anyone noticing. A sweep is a snapshot; this is a gate.

**What it asserts.** Every route in each app's *authoritative* URL map must be
either

1. **exercised** by the pytest suite (measured by ``route_recorder``, a
   ``before_request`` hook -- not by grepping the test tree for path strings), or
2. **declared** in ``UNEXERCISED`` below, with a reason and a pointer to whatever
   does cover it.

An undeclared, unexercised route fails the build. So does a *stale* declaration:
if a declared route later becomes exercised, the entry must be deleted, or the
registry quietly stops describing reality.

This runs LAST (``conftest.pytest_collection_modifyitems`` moves it to the end),
because it reports on the rest of the suite.
"""

import pytest

import route_recorder

pytestmark = pytest.mark.route_coverage


# Routes the pytest suite does not drive, each with a reason and its real cover.
# Keep this honest: a route listed here that pytest later exercises must be
# removed from this table (the stale check below enforces it).
UNEXERCISED: dict[str, dict[str, str]] = {
    "webapp": {},
    "cowriter": {
        "/static/<path:filename>": (
            "Flask's auto-registered static route. `screenplay_cowriter/server.py` "
            "constructs a bare `Flask(__name__)`, so Flask adds this from the "
            "default `static/` folder -- which does not exist in that package, so "
            "the route can only ever 404. It is not a surface the server uses. "
            "(The webapp avoids this entirely: `Flask(__name__, static_folder=None)`.)"),
    },
}


def _webapp_routes() -> set[str]:
    from screenplay_studio import webapp_server
    return {r.rule for r in webapp_server.app.url_map.iter_rules()}


def _cowriter_routes() -> set[str]:
    from screenplay_cowriter import server as cow_server
    return {r.rule for r in cow_server.app.url_map.iter_rules()}


def _assert_covered(kind: str, routes: set[str]) -> None:
    hits = route_recorder.HITS[kind]
    exercised = {rule for rule, _method in hits}
    declared = UNEXERCISED.get(kind, {})

    undeclared = sorted(routes - exercised - set(declared))
    assert not undeclared, (
        f"{len(undeclared)} {kind} route(s) are neither exercised by the test "
        f"suite nor declared in UNEXERCISED:\n  "
        + "\n  ".join(undeclared)
        + "\n\nDrive each one with a test, or declare it with a reason and a "
          "pointer to what does cover it (a browser suite, a CLI path, or a real "
          "llama-server requirement).")

    stale = sorted(set(declared) & exercised)
    assert not stale, (
        f"{kind} route(s) {stale} are declared UNEXERCISED but the suite does "
        f"exercise them -- delete the stale declaration(s) so the registry keeps "
        f"describing reality.")


def test_every_webapp_route_is_exercised_or_declared():
    routes = _webapp_routes()
    assert len(routes) > 50, (
        f"parsed only {len(routes)} webapp routes -- the URL map is not loading, "
        f"so this guard would pass vacuously")
    _assert_covered("webapp", routes)


def test_every_cowriter_route_is_exercised_or_declared():
    routes = _cowriter_routes()
    assert len(routes) > 5, (
        f"parsed only {len(routes)} cowriter routes -- the URL map is not "
        f"loading, so this guard would pass vacuously")
    _assert_covered("cowriter", routes)


def test_the_recorder_is_actually_wired():
    """A recorder that recorded nothing would make the two tests above fail --
    but for the wrong reason. This pins the instrumentation itself: if the hook
    ever detaches, this says so directly.

    The bar is deliberately low: a detached hook records **zero**, and the full
    suite records hundreds, so anything above a handful separates the two states
    without being brittle when only a subset of the suite is selected.
    """
    total = sum(len(v) for v in route_recorder.HITS.values())
    assert total >= 5, (
        f"route_recorder saw only {total} request(s) -- the before_request hook "
        f"is not attached, so the coverage numbers above are meaningless")
