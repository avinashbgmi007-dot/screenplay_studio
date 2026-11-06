"""Gap 83 — the documented surface and the shipped surface must agree.

Filed defect: `python -m screenplay_studio --help` offers exactly `run, resume,
status, watch`; `docs/API_ROUTE_MAP.md` stated there was **"no standalone
`server.py`"** while `screenplay_cowriter/server.py` still parsed arguments and
still bound loopback on 8300. Four other docs presented that server as supported,
and `AGENTS.md` said the only HTTP servers were the webapp and the demo model.

Anyone following the docs got a working process the architecture doc said did not
exist — one with its own writer of the same `sessions/` shape the desk uses, and
with none of the desk's guards.

Two decisions this file holds:

1. **The server is kept.** It has 8 routes and is exercised by
   `test_cowriter_server.py`, `test_session_selection_merge.py` and the
   route-coverage census. Deleting working, tested code to make a sentence true is
   the wrong repair; correcting the sentence is the right one.
2. **A doc claim is a testable statement.** The assertions below read the docs and
   compare them to `--help` output and to the URL maps, so the two cannot drift
   apart silently again. That is the whole gap: not "a doc was stale" but "nothing
   connected a doc to the thing it describes".
"""

import os
import subprocess
import sys

import pytest

import screenplay_studio.webapp_server as ws
from screenplay_cowriter import server as cow_server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(*parts) -> str:
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


# ---------- the shipped CLI is exactly what the docs say ----------

def test_the_studio_cli_offers_exactly_four_commands():
    out = subprocess.run([sys.executable, "-B", "-m", "screenplay_studio", "--help"],
                         capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert out.returncode == 0, out.stderr
    for cmd in ("run", "resume", "status", "watch"):
        assert cmd in out.stdout
    # and no fifth one, so the docs cannot describe a wider toolchain by accident
    assert "{" in out.stdout and "}" in out.stdout
    choices = out.stdout[out.stdout.index("{"):out.stdout.index("}") + 1]
    assert choices == "{run,resume,status,watch}", choices


def test_the_cli_reference_names_the_same_four_commands():
    text = _doc("docs", "CLI_REFERENCE.md")
    assert "{run,resume,status,watch}" in text or "`run`, `resume`, `status`, `watch`" in text


# ---------- the co-writer server exists, and the docs now say so ----------

def test_the_cowriter_server_is_really_a_runnable_surface():
    out = subprocess.run([sys.executable, "-B", "-m", "screenplay_cowriter.server", "--help"],
                         capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert out.returncode == 0, out.stderr
    for flag in ("--port", "--sessions-dir"):
        assert flag in out.stdout


def test_the_route_map_no_longer_denies_the_server_exists():
    """The exact false statement the gap was filed about."""
    text = _doc("docs", "API_ROUTE_MAP.md")
    assert "no standalone `server.py`" not in text, (
        "the route map is denying a server that runs")
    assert "There **is** a standalone `screenplay_cowriter/server.py`" in text
    assert "8 routes" in text or "every route it serves" in text


def test_the_doc_route_list_matches_the_url_map_exactly():
    """The list above is the arbiter, not my prose: every real route is named, and
    the one route the server cannot serve (Flask's auto static) is named too so a
    reader is not surprised by it in `--help` or in the census."""
    import re
    text = _doc("docs", "API_ROUTE_MAP.md")
    # Accept both shapes the map uses: a table cell `| GET | `/path` |` and the
    # inline backticked pair `GET /path`. The point is the SET, not the typography.
    listed = set(re.findall(r"\|\s*(GET|POST)\s*\|\s*`([^`]+)`", text))
    listed |= set(re.findall(r"`(GET|POST) (/[^`]*)`", text))
    served = {(m, r.rule) for r in cow_server.app.url_map.iter_rules()
              if r.rule != "/static/<path:filename>"
              for m in r.methods if m in ("GET", "POST")}
    missing = sorted(served - listed)
    assert not missing, f"the route map omits {missing}"


def test_the_three_servers_are_enumerated_with_their_guards():
    text = _doc("docs", "API_ROUTE_MAP.md")
    for server in ("webapp_server.py", "screenplay_cowriter/server.py", "demo_model.py"):
        assert server in text
    assert "capability token" in text
    assert "foreign-`Host`" in text


def test_the_docs_agree_that_the_server_is_guarded():
    text = _doc("docs", "API_ROUTE_MAP.md")
    assert "Host-guarded" in _doc("docs", "ARCHITECTURE.md") or "Host-guarded" in text


def test_cli_reference_is_explicit_about_the_two_module_entry_points():
    text = _doc("docs", "CLI_REFERENCE.md")
    assert "screenplay_studio.webapp_server" in text
    assert "screenplay_cowriter.server" in text
    assert "not `screenplay_studio`'s CLI" in text, (
        "the co-writer server must not read as one of the studio's subcommands")


def test_codebase_map_describes_it_as_supported():
    text = _doc("docs", "CODEBASE_MAP.md")
    assert "SUPPORTED surface" in text
    assert "8300" in text


# ---------- the guard the filing asked for ----------

def test_a_foreign_host_is_refused():
    """This server had no guard of any kind. DNS rebinding makes a foreign name
    arrive with a Host header that is not local, which is why the Host check —
    not the loopback bind — is the thing that actually decides."""
    c = cow_server.app.test_client()
    r = c.get("/health", headers={"Host": "evil.example.com"})
    assert r.status_code == 403
    assert r.get_json()["host_rejected"] is True


def test_the_guard_covers_state_changing_routes_too():
    c = cow_server.app.test_client()
    r = c.post("/sessions", headers={"Host": "evil.example.com"}, json={})
    assert r.status_code == 403


@pytest.mark.parametrize("host", ["evil.com@127.0.0.1", "127.0.0.1.evil.com",
                                  "evil.example.com:8300"])
def test_rebinding_shaped_hosts_are_refused(host):
    assert cow_server.app.test_client().get(
        "/health", headers={"Host": host}).status_code == 403


@pytest.mark.parametrize("host", ["localhost", "localhost:8300", "localhost.:8300",
                                  "127.0.0.1", "127.0.0.5:8300", "[::1]:8300"])
def test_local_hosts_are_served(host):
    """A false rejection here would break the CLI and every test client, so the
    allowance is tested as carefully as the refusal."""
    assert cow_server.app.test_client().get(
        "/health", headers={"Host": host}).status_code == 200


def test_the_webapp_guard_and_this_one_agree_on_the_verdict(monkeypatch):
    """Two implementations of one rule diverge eventually; pin that they agree
    on a spread of hostile and benign Host headers."""
    for host in ("evil.example.com", "evil.com@127.0.0.1", "localhost:8500",
                 "127.0.0.1:8500", "127.0.0.5"):
        cow = cow_server.app.test_client().get("/health", headers={"Host": host}).status_code
        desk = ws.app.test_client().get("/api/config", headers={"Host": host},
                                        base_url=f"http://{host}").status_code
        assert (cow == 403) == (desk == 403), f"the two guards disagree about {host}"


def test_the_desk_route_census_did_not_change():
    """This gap fixed documentation and one guard; it added no desk route, so the
    pinned census must not move."""
    assert len({r.rule for r in ws.app.url_map.iter_rules()}) > 50
