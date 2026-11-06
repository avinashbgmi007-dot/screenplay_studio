"""Gap 84 — the route map must be current in BOTH directions.

Filed defect: compared mechanically with the live Flask URL map, every documented
`/api` path still existed, but four live routes were undocumented —
`GET /api/rules/<rule_id>`, `GET /api/projects/<name>/passes`,
`POST /api/projects/<name>/quickcheck`, `POST /api/projects/<name>/findings/intent`.

Measured when I picked it up: still exactly those four, plus the three gap-80
recovery routes that had been added since the filing. Zero dead rows.

The filing's sharpest observation is the one worth keeping: *the document's own
totals paragraph claims a count pinned by a test; the count test can pass while
individual rows drift.* A total is a checksum over a number, not over the content —
add two routes and delete two and it still matches. So the guard here compares
SETS, in both directions, and the map gains a generated census block that
`tools/route_map.py` writes from the live URL map.

The prose is not generated. It says *what a route means* ("grounded in
knowledge-base rule <id>", "no model call") and a generator would replace that with
a path list to satisfy a checker. Human prose, mechanical census, both checked.
"""

import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "API_ROUTE_MAP.md")

sys.path.insert(0, os.path.join(ROOT, "tools"))
import route_map  # noqa: E402  (a tool, imported as a library — it is pure)


def _doc() -> str:
    with open(DOC, encoding="utf-8") as f:
        return f.read()


# ---------- the two directions ----------

def test_no_live_route_is_undocumented():
    """Direction 1: the code grew a route the map never heard about."""
    undocumented, _dead = route_map.drift(_doc())
    assert not undocumented, (
        "live routes with no row in docs/API_ROUTE_MAP.md:\n  "
        + "\n  ".join(undocumented)
        + "\n\nRun `python tools/route_map.py --write` for the census block and add "
          "a prose row saying what each route is for.")


def test_no_documented_route_is_dead():
    """Direction 2: the map describes a route that no longer exists. This is the
    direction the totals pin could never catch — a count is a checksum over a
    number, not over the content."""
    _undocumented, dead = route_map.drift(_doc())
    assert not dead, (
        "rows in docs/API_ROUTE_MAP.md with no live route:\n  " + "\n  ".join(dead))


def test_the_four_filed_routes_are_documented():
    """Named explicitly so a future regeneration cannot quietly drop them again."""
    text = _doc()
    for path in ("/api/rules/<rule_id>",
                 "/api/projects/<name>/passes",
                 "/api/projects/<name>/quickcheck",
                 "/api/projects/<name>/findings/intent"):
        assert path in text, f"{path} is not in the route map"


# ---------- the generated block is actually generated ----------

def test_the_census_block_is_present_and_marked():
    text = _doc()
    assert route_map.BEGIN in text and route_map.END in text
    assert "do not hand-edit this block" in text


def test_the_census_block_matches_the_live_map_exactly():
    """Regenerating must be a no-op when the block is current. If this fails, the
    block was hand-edited or the app changed — either way it is stale."""
    text = _doc()
    regenerated = route_map.apply(text)
    assert regenerated == text, (
        "the generated census block is stale; run `python tools/route_map.py --write`")


def test_the_census_block_counts_every_api_route():
    text = _doc()
    live = route_map.live_routes()
    assert f"**{len(live)} live `/api` routes.**" in text
    # every live path appears in the block as a table row
    block = text[text.index(route_map.BEGIN):text.index(route_map.END)]
    for (_method, path) in live:
        assert f"`{path}`" in block, f"census block is missing {path}"


# ---------- the checker itself, because a checker that cannot fail is decoration ----------

def test_the_checker_notices_a_missing_row(monkeypatch):
    text = _doc()
    stripped = re.sub(r"^\| GET \| `/api/rules/<rule_id>` \|.*\n", "", text, flags=re.M)
    undocumented, _dead = route_map.drift(stripped)
    assert "/api/rules/<x>" in undocumented


def test_the_checker_notices_a_dead_row(monkeypatch):
    text = _doc() + "\n| GET | `/api/this/does/not/exist` | `ghost` | invented |\n"
    _undocumented, dead = route_map.drift(text)
    assert "/api/this/does/not/exist" in dead


def test_the_checker_ignores_the_other_servers_in_the_same_file():
    """The map documents three servers (gap 83). Counting the co-writer's routes as
    'dead' was my first bug in this tool — the checker has to know which server it
    checks."""
    text = _doc()
    assert "`/sessions`" in text, "the co-writer table should still be in the map"
    _undocumented, dead = route_map.drift(text)
    assert not any("session" in p for p in dead)


def test_path_parameters_are_compared_by_shape_not_by_name():
    """`<int:index>` and `<index>` are the same route to a reader, and the map is
    allowed to use either."""
    assert route_map._normalise("/api/x/<int:index>") == route_map._normalise("/api/x/<index>")


# ---------- and it runs in CI, or it is a suggestion ----------

def test_ci_runs_the_route_map_check():
    with open(os.path.join(ROOT, ".github", "workflows", "ci.yml"), encoding="utf-8") as f:
        ci = f.read()
    assert "tools/route_map.py" in ci, (
        "the census is only enforced if CI runs it — a check nobody runs is a "
        "comment")
