"""Regression tests for the SPA's cache-bust tokens (finding F5).

`index.html` carried hand-maintained `?v=` queries on its four assets, and the
guard meant to protect them matched only one of the four shapes
(`/v=hx1b1\\d\\d/` matched core.js's token and nothing else), so editing app.js
without bumping its token shipped a stale copy with every test green.

The token is now DERIVED from the asset's own bytes when the document is served.
These tests pin the invariant that removes the manual step: the token the browser
is handed is the content hash of the file it will receive.

The expected hashes are computed here from the files on disk, never read back
from the server's own helper, so this cannot pass by agreeing with itself.
"""
from __future__ import annotations

import hashlib
import os
import re

ASSETS = ("style.css", "tungsten.css", "core.js", "app.js")

# `name.ext?v=token` as it appears in the served document.
_TOKEN_RE = re.compile(
    r"(?P<asset>[A-Za-z0-9_/-]+\.(?:js|css))\?v=(?P<token>[A-Za-z0-9._-]+)"
)


def _client(monkeypatch, tmp_path):
    import screenplay_studio.webapp_server as ws
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(tmp_path))
    ws.app.config["TESTING"] = True
    return ws, ws.app.test_client()


def _tokens(html: str) -> dict:
    return {m.group("asset"): m.group("token") for m in _TOKEN_RE.finditer(html)}


def _content_hash(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:10]


def test_every_asset_token_is_the_hash_of_that_asset(monkeypatch, tmp_path):
    ws, client = _client(monkeypatch, tmp_path)
    tokens = _tokens(client.get("/").get_data(as_text=True))
    for asset in ASSETS:
        assert asset in tokens, f"{asset} carries no cache-bust token: {tokens}"
        expected = _content_hash(os.path.join(ws.WEBAPP_DIR, asset))
        assert tokens[asset] == expected, (
            f"{asset} is advertised as ?v={tokens[asset]} but its content hash is "
            f"{expected} — a returning browser would keep the stale copy"
        )


def test_tokens_are_distinct(monkeypatch, tmp_path):
    """One shared token would leave three assets permanently un-invalidated."""
    _ws, client = _client(monkeypatch, tmp_path)
    tokens = _tokens(client.get("/").get_data(as_text=True))
    assert len(set(tokens.values())) == len(tokens), tokens


def test_changing_an_asset_changes_its_token(monkeypatch, tmp_path):
    """The heart of F5: invalidating a URL must not need a human step."""
    import screenplay_studio.webapp_server as ws
    webapp = tmp_path / "webapp"
    webapp.mkdir()
    (webapp / "index.html").write_text(
        '<link rel="stylesheet" href="style.css?v=handwritten">'
        '<script src="core.js?v=handwritten"></script>'
        '<script src="app.js?v=handwritten"></script>',
        encoding="utf-8",
    )
    for name, body in (("style.css", "a{}\n"), ("core.js", "window.y = 1;\n"),
                       ("app.js", "window.x = 1;\n")):
        (webapp / name).write_text(body, encoding="utf-8")
    monkeypatch.setattr(ws, "WEBAPP_DIR", str(webapp))
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(tmp_path / "projects"))
    ws.app.config["TESTING"] = True
    client = ws.app.test_client()

    first = _tokens(client.get("/").get_data(as_text=True))
    assert set(first) == {"style.css", "core.js", "app.js"}, first
    for asset in first:
        assert first[asset] != "handwritten", (
            f"{asset} still carries the hand-written token — it was trusted "
            "instead of derived")
        assert first[asset] == _content_hash(str(webapp / asset))

    (webapp / "app.js").write_text("window.x = 2;  // changed\n", encoding="utf-8")
    second = _tokens(client.get("/").get_data(as_text=True))
    assert second["app.js"] != first["app.js"], (
        "editing app.js did not change its URL — a returning browser keeps the "
        "stale copy")
    assert second["core.js"] == first["core.js"], (
        "an untouched asset must not churn its URL")


def test_index_html_route_carries_the_same_tokens(monkeypatch, tmp_path):
    _ws, client = _client(monkeypatch, tmp_path)
    root = _tokens(client.get("/").get_data(as_text=True))
    alias = _tokens(client.get("/index.html").get_data(as_text=True))
    assert alias == root


def test_document_and_assets_still_revalidate(monkeypatch, tmp_path):
    """The token is belt-and-braces; `no-cache` is the mechanism. Pin both."""
    _ws, client = _client(monkeypatch, tmp_path)
    assert client.get("/").headers.get("Cache-Control") == "no-cache"
    for asset in ASSETS:
        assert client.get(f"/{asset}").headers.get("Cache-Control") == "no-cache", asset
