"""H1 — capability token on the loopback server (regression tests).

The Origin guard rejects foreign-`Origin` pages, but a no-`Origin` blind write
(curl / form POST / no-cors fetch) sails through. Fix: when the server issues a
capability token (set as a SameSite=Strict cookie on `/`), mutating requests must
echo it back in the X-Studio-Token header. A foreign page can't read the cookie
and can't set the header without triggering CORS, so blind writes are blocked.

SECURE BY DEFAULT: a bare `python -m screenplay_studio.webapp_server` mints a
token without any flag. `--no-token` is the explicit opt-out for trusted
scripted clients (the E2E harness, curl) on a loopback-only machine. When no
token is configured at all (bare test-client fixtures, the Flask CLI path),
behavior is unchanged.
"""
from __future__ import annotations


def _make_client(monkeypatch, tmp_path):
    import screenplay_studio.webapp_server as ws
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(tmp_path))
    ws.app.config["TESTING"] = True
    return ws, ws.app.test_client()


def test_mutations_rejected_without_token_when_one_is_set(monkeypatch, tmp_path):
    ws, client = _make_client(monkeypatch, tmp_path)
    monkeypatch.setattr(ws, "_API_TOKEN", "secret-token-123")
    # a mutating request with no token header -> 403
    r = client.post("/api/projects/The_Late_Hour/analyze")
    assert r.status_code == 403


def test_mutations_allowed_with_token(monkeypatch, tmp_path):
    ws, client = _make_client(monkeypatch, tmp_path)
    monkeypatch.setattr(ws, "_API_TOKEN", "secret-token-123")
    # with the token echoed, the guard passes (the route itself may 404/400 on a
    # missing project, but it must NOT be a 403 from the token gate)
    r = client.post("/api/projects/The_Late_Hour/analyze",
                    headers={"X-Studio-Token": "secret-token-123"})
    assert r.status_code != 403


def test_get_requests_pass_without_token(monkeypatch, tmp_path):
    ws, client = _make_client(monkeypatch, tmp_path)
    monkeypatch.setattr(ws, "_API_TOKEN", "secret-token-123")
    assert client.get("/api/config").status_code == 200


def test_no_token_configured_means_guard_off(monkeypatch, tmp_path):
    ws, client = _make_client(monkeypatch, tmp_path)
    monkeypatch.setattr(ws, "_API_TOKEN", None)
    r = client.post("/api/projects/The_Late_Hour/analyze")
    assert r.status_code != 403  # not blocked by the token gate


def test_index_sets_token_cookie_when_configured(monkeypatch, tmp_path):
    ws, client = _make_client(monkeypatch, tmp_path)
    monkeypatch.setattr(ws, "_API_TOKEN", "secret-token-123")
    r = client.get("/")
    cookie = r.headers.get("Set-Cookie", "")
    assert "studio_token=secret-token-123" in cookie
    assert "SameSite=Strict" in cookie


def test_every_served_document_sets_the_token_cookie(monkeypatch, tmp_path):
    """The token is a page's LICENCE TO WRITE, so it rides on EVERY HTML
    document — not just `/`. The design labs are separate documents reached
    directly (`/preview-next/report-first.html`); when only `index()` minted
    the cookie they could not read it, so every dismissal and chat turn they
    post came back `missing or invalid capability token` — six worlds, all
    broken, and invisible while the browser harness booted with --no-token."""
    ws, client = _make_client(monkeypatch, tmp_path)
    monkeypatch.setattr(ws, "_API_TOKEN", "secret-token-123")
    for doc in ("/index.html", "/design_session.html",
                "/preview-next/index.html", "/preview-next/report-first.html"):
        r = client.get(doc)
        assert r.status_code == 200, doc
        assert "studio_token=secret-token-123" in r.headers.get("Set-Cookie", ""), doc


def test_assets_do_not_carry_the_token_cookie(monkeypatch, tmp_path):
    """Scoped to documents on purpose: a cookie on every stylesheet, font and
    script the page pulls is noise, and 'every response' would not be a check."""
    ws, client = _make_client(monkeypatch, tmp_path)
    monkeypatch.setattr(ws, "_API_TOKEN", "secret-token-123")
    for asset in ("/style.css", "/app.js", "/core.js"):
        assert "studio_token" not in client.get(asset).headers.get("Set-Cookie", "")


# ---------- startup posture: secure by default (H1) ----------

# The app.run() kwargs of the last _launch(). E2E-1 (audit 2026-09-24): this stub
# used to be `lambda **_kw: None`, which DISCARDED the host argument — so the one
# line that decides whether this desk is reachable from the LAN was observed by
# no test in the suite. Capturing it is what makes the bind assertable.
_LAST_RUN_KWARGS: dict = {}


def _launch(monkeypatch, tmp_path, extra_argv):
    """Run webapp_server.main() in-process with app.run stubbed out.

    monkeypatch.setattr on `_API_TOKEN` gives each launch a clean slate AND
    restores the module default afterwards, so a minted token never leaks into
    the bare test-client fixtures used by the rest of the suite.
    """
    import sys
    import screenplay_studio.webapp_server as ws
    monkeypatch.setattr(ws, "_API_TOKEN", None)
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(tmp_path))
    _LAST_RUN_KWARGS.clear()
    monkeypatch.setattr(ws.app, "run", lambda **kw: _LAST_RUN_KWARGS.update(kw))
    monkeypatch.setattr(sys, "argv", ["webapp_server", "--port", "8599",
                                      "--projects-dir", str(tmp_path)] + extra_argv)
    ws.main()
    return ws


def test_default_launch_is_secure_by_default(monkeypatch, tmp_path):
    # H1: a bare launch must mint a token -- the blind no-Origin DELETE hole is
    # closed without the operator passing any flag.
    ws = _launch(monkeypatch, tmp_path, [])
    assert ws._API_TOKEN


def test_no_token_flag_is_the_explicit_opt_out(monkeypatch, tmp_path):
    ws = _launch(monkeypatch, tmp_path, ["--no-token"])
    assert ws._API_TOKEN is None


def test_require_token_flag_still_accepted(monkeypatch, tmp_path):
    # backward compatibility: the old hardening flag keeps working (now redundant)
    ws = _launch(monkeypatch, tmp_path, ["--require-token"])
    assert ws._API_TOKEN


def test_no_token_beats_require_token(monkeypatch, tmp_path):
    # the explicit opt-out wins if both are passed -- never silently hardened
    ws = _launch(monkeypatch, tmp_path, ["--require-token", "--no-token"])
    assert ws._API_TOKEN is None


def test_default_launch_token_actually_guards_writes(monkeypatch, tmp_path):
    # the minted token is wired into the same guard the routes run through
    ws = _launch(monkeypatch, tmp_path, [])
    ws.app.config["TESTING"] = True
    r = ws.app.test_client().post("/api/projects/The_Late_Hour/analyze")
    assert r.status_code == 403


# ---------- E2E-1: the bind host IS the privacy promise --------------------

def test_the_shipped_launch_binds_loopback_and_nothing_else(monkeypatch, tmp_path):
    """E2E-1 (audit 2026-09-24). `app.run(host=...)` is the entire inbound half
    of "nothing leaves this machine", and until now NO test observed it:

      * `test_webapp_demo_binds_loopback_not_all_interfaces` regexes
        `webapp_demo.py`, which has contained zero `app.run` calls since it began
        delegating to main() — so its assertion could not fail; and
      * the launch stub discarded `host` entirely.

    Consequence, before this test: flipping this one string to "0.0.0.0" left
    1684 pytest tests and 1138 browser checks green while every project on the
    machine became reachable from the LAN — and, because `/` hands the
    capability cookie to whoever asks, writable too.

    Mutation-verified: flipping the bind turns this red.
    """
    _launch(monkeypatch, tmp_path, [])
    assert _LAST_RUN_KWARGS, "main() never reached app.run()"
    assert _LAST_RUN_KWARGS["host"] == "127.0.0.1", (
        "the shipped launch does not bind loopback — this desk is on the network")
    assert _LAST_RUN_KWARGS["port"] == 8599
    assert _LAST_RUN_KWARGS["debug"] is False, (
        "debug=True ships the Werkzeug console, which is remote code execution")
