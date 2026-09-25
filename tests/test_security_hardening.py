"""Regression tests for the three capability-token vulnerabilities found by the
security review follow-up (see NOTES.md, "security review follow-up — three
vulnerabilities fixed").

The auth model under test: the server mints a per-process capability token at
startup and hands it out as the `studio_token` cookie from an after_request
hook; the SPA echoes it as `X-Studio-Token` on mutating requests, and
`_reject_cross_origin_writes` refuses any write that does not carry it.

The three findings, each pinned by tests below:

V1 — the cookie was issued only on 200 HTML. The SPA documents are served
     `Cache-Control: no-cache`, so every load revalidates, and an unchanged
     load answers 304 — with NO Set-Cookie. Tokens are per process, so after a
     restart the page that reloads into a 304 keeps the dead cookie and
     wrongly believes it is authenticated: every read passes (the guard only
     bites on writes), so the desk looks healthy until the first write comes
     back 403. Fix: documents re-issue the licence on 304 too — the licence
     rides every load, not only loads that move bytes.

V2 — `hmac.compare_digest` raises TypeError on a non-ASCII *str*, so sending a
     header like `X-Studio-Token: café` crashed the write guard itself: a 500
     out of the security check (whose body echoed the exception text) where a
     403 is the only correct answer. Fix: encode both sides to bytes before
     the constant-time compare.

V3 — the SSE chat route is fetched outside api(), so the streaming workbench
     flow (streamChatTurn) had NONE of api()'s stale-token recovery: after a
     restart, every chat turn died on the guard's internal string. Fix (app.js,
     pinned here at HTTP-contract + source level): the stream turn now re-mints
     via the document and retries once, exactly like _apiOnce; and the SPA's
     auth detection never assumes a cookie-less page is authenticated — the
     first write of a page's life re-fetches the document (a passive GET) to
     pick up its licence.
"""
from __future__ import annotations

import os
import re

TOKEN = "unit-test-capability-token"
WEBAPP_JS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "screenplay_studio", "webapp", "app.js")


def _client(monkeypatch, tmp_path):
    import screenplay_studio.webapp_server as ws
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(tmp_path))
    # main() mints the token; test fixtures otherwise run with the module
    # default None (guard off). These tests pin the guard, so boot token mode.
    monkeypatch.setattr(ws, "_API_TOKEN", TOKEN)
    ws.app.config["TESTING"] = True
    return ws, ws.app.test_client()


# ---------------------------------------------------------------------------
# V1 — the licence must survive revalidation (304), not only full delivery.
# ---------------------------------------------------------------------------

def test_fresh_document_sets_the_capability_cookie(monkeypatch, tmp_path):
    """Baseline for the fix: a 200 HTML document already carried the cookie."""
    _ws, client = _client(monkeypatch, tmp_path)
    r = client.get("/")
    assert r.status_code == 200
    assert "studio_token" in r.headers.get("Set-Cookie", "")


def test_revalidated_document_reissues_the_cookie(monkeypatch, tmp_path):
    """The vulnerability: a 304 carried no Set-Cookie, so a page reloaded
    after a server restart kept (and wrongly trusted) the previous process's
    token. A 304 for a document route must hand out the CURRENT token."""
    _ws, client = _client(monkeypatch, tmp_path)
    first = client.get("/")
    etag = first.headers.get("ETag")
    assert etag, "the document must be revalidatable for this test to mean anything"
    r = client.get("/", headers={"If-None-Match": etag})
    assert r.status_code == 304
    cookie = r.headers.get("Set-Cookie", "")
    assert "studio_token=" in cookie, "a revalidated page must still be issued its licence"
    assert TOKEN in cookie


def test_index_html_path_revalidates_with_the_cookie_too(monkeypatch, tmp_path):
    """The SPA document is also reachable as /index.html — same rule there."""
    _ws, client = _client(monkeypatch, tmp_path)
    r = client.get("/index.html",
                   headers={"If-Modified-Since": "Sun, 01 Feb 2043 00:00:00 GMT"})
    assert r.status_code == 304
    assert TOKEN in r.headers.get("Set-Cookie", "")


def test_subresource_revalidation_gets_no_cookie(monkeypatch, tmp_path):
    """The scoping still holds after the fix: JS/CSS are subresources that
    never write — a cookie on each revalidation is noise, not licence."""
    _ws, client = _client(monkeypatch, tmp_path)
    first = client.get("/app.js")
    assert first.status_code == 200
    assert "studio_token" not in first.headers.get("Set-Cookie", "")
    r = client.get("/app.js", headers={"If-None-Match": first.headers["ETag"]})
    assert r.status_code == 304
    assert "studio_token" not in r.headers.get("Set-Cookie", "")


# ---------------------------------------------------------------------------
# V2 — the guard answers 403 for ANY bad token and never crashes on one.
# ---------------------------------------------------------------------------

def test_non_ascii_token_is_refused_not_a_crash(monkeypatch, tmp_path):
    """`café` used to raise TypeError inside compare_digest — the security
    check answering 500 (via the JSON error backstop, exception text
    included) instead of 403."""
    _ws, client = _client(monkeypatch, tmp_path)
    r = client.post("/api/config", json={"timeout": 30},
                    headers={"X-Studio-Token": "caf\u00e9"})
    assert r.status_code == 403, r.get_data(as_text=True)
    assert r.get_json() == {"error": "missing or invalid capability token"}


def test_lone_surrogate_token_is_refused_not_a_crash(monkeypatch, tmp_path):
    """Header values can even carry unpaired surrogates (WSGI decodes bytes
    lossily). Whoever answers — the HTTP layer (400) or the guard (403) —
    the security check itself must never be the one that crashes (500)."""
    _ws, client = _client(monkeypatch, tmp_path)
    r = client.post("/api/config", json={"timeout": 30},
                    headers={"X-Studio-Token": "\ud800"})
    assert r.status_code in (400, 403), r.status_code


def test_bad_and_missing_tokens_still_refused(monkeypatch, tmp_path):
    _ws, client = _client(monkeypatch, tmp_path)
    for bad in ("", "wrong", "x" * 4096):
        r = client.post("/api/config", json={"timeout": 30},
                        headers={"X-Studio-Token": bad})
        assert r.status_code == 403, f"token {bad[:12]!r} was not refused"


def test_valid_token_write_still_accepted(monkeypatch, tmp_path):
    """The guard must stay a filter, not a wall: the exact token on the
    header still writes (the SPA's whole flow depends on this)."""
    _ws, client = _client(monkeypatch, tmp_path)
    r = client.post("/api/config", json={"timeout": 30},
                    headers={"X-Studio-Token": TOKEN})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert client.get("/api/config").get_json()["timeout"] == 30


def test_stream_route_answers_the_json_403_contract(monkeypatch, tmp_path):
    """The SPA's V3 recovery keys off the stream route's 403 + this exact
    JSON shape. Pin the contract both routes (stream and api()) share, with
    a non-ASCII token — the route used to hit the same V2 crash path."""
    _ws, client = _client(monkeypatch, tmp_path)
    for tok in ("", "caf\u00e9"):
        h = {"X-Studio-Token": tok} if tok else {}
        r = client.post("/api/projects/x/chat/sessions/y/messages/stream",
                        json={"text": "hi"}, headers=h)
        assert r.status_code == 403
        assert r.get_json() == {"error": "missing or invalid capability token"}


# ---------------------------------------------------------------------------
# V3 — the SPA side: detection never assumes authentication; the stream turn
# recovers exactly like api(). pytest cannot execute app.js, so these are
# source-level contract pins (the repo's precedent: test_app_symbol_integrity)
# — the HTTP behaviour they rely on is pinned by the tests above.
# ---------------------------------------------------------------------------

def _app_js() -> str:
    with open(WEBAPP_JS, encoding="utf-8") as f:
        return f.read()


def _function_body(src: str, name: str) -> str:
    """The text of `async function name(...) { ... }` up to its closing brace
    at column 0 — the file's style puts every top-level function's `}` alone
    on a line."""
    m = re.search(rf"function {re.escape(name)}\([^)]*\)[^{{]*\{{\n", src)
    assert m, f"{name} not found (or not a top-level function) in app.js"
    end = src.index("\n}\n", m.end())
    return src[m.start():end + 3]


def test_spa_detects_a_missing_licence_before_writing():
    """Auth detection must not authenticate: a page with no cookie is NOT
    authenticated, whatever the green connection dot says, so the SPA re-mints
    its licence passively (a GET of the document) BEFORE the first write —
    and _apiOnce / streamChatTurn both go through that helper."""
    src = _app_js()
    body = _function_body(src, "_ensureStudioToken")
    assert "_studioToken()" in body
    assert 'cache: "no-store"' in body, "the licence refresh must bypass the HTTP cache"
    assert "_tokenMintFetched" in body, "one passive attempt per page load, not per write"
    assert "await _ensureStudioToken()" in _function_body(src, "_apiOnce")
    assert "await _ensureStudioToken()" in _function_body(src, "streamChatTurn")


def test_stream_chat_turn_recovers_from_a_stale_token():
    """streamChatTurn used to surface the guard's internal 403 string with no
    recovery. It must mirror _apiOnce: re-mint once, retry once, then fail
    with the writer-facing _tokenError message — never the raw server string.
    """
    body = _function_body(_app_js(), "streamChatTurn")
    assert "resp.status === 403" in body
    assert "_retry" in body, "never retried twice: a second 403 is a real rejection"
    assert "_tokenError(" in body, "the writer must see the actionable message, not the internal one"
    assert 'cache: "no-store"' in body


def test_spa_still_echoes_the_token_as_the_header():
    """Sanity pin for the whole model: the SPA reads the cookie and sends it
    as X-Studio-Token — the exact contract the guard above enforces."""
    src = _app_js()
    assert re.search(r"studio_token=", src), "the cookie name is part of the wire contract"
    assert 'headers["X-Studio-Token"]' in src
