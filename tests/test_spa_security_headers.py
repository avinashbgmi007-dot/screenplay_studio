"""Regression tests for the SPA's Content-Security-Policy (finding FE-C1).

The escaping pass (core.js `escapeHtml` + every interpolating `innerHTML` sink)
is the fix for the stored-XSS chain. The CSP is the containment layer behind it:
if a sink is ever missed, or added later, the injected script still must not run.

These are HTTP-level assertions on the response the server actually sends, so
they hold without a browser and run in CI. The DOM-level proof — that a payload
renders inert and that an inline handler is genuinely refused — lives in
`tests/e2e_browser_xss_inert.py`, which needs chromium.

Why the policy can be this strict: the SPA makes zero external requests (no CDN,
no font host) and loads both its scripts as external files, so `script-src 'self'`
is achievable. That is also why the inline `onclick="…"` handlers built from
finding data had to become delegated listeners.
"""
from __future__ import annotations


def _client(monkeypatch, tmp_path):
    import screenplay_studio.webapp_server as ws
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(tmp_path))
    ws.app.config["TESTING"] = True
    return ws, ws.app.test_client()


def test_spa_document_carries_a_content_security_policy(monkeypatch, tmp_path):
    _ws, client = _client(monkeypatch, tmp_path)
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers.get("Content-Security-Policy"), "the SPA document must carry a CSP"


def test_index_html_path_is_hardened_too(monkeypatch, tmp_path):
    # /index.html is the same document by another route — it must not be a way
    # to load the SPA without the policy.
    _ws, client = _client(monkeypatch, tmp_path)
    r = client.get("/index.html")
    assert r.status_code == 200
    assert r.headers.get("Content-Security-Policy")


def test_script_src_is_self_with_no_inline_or_eval_escape(monkeypatch, tmp_path):
    """The whole point: no 'unsafe-inline' and no 'unsafe-eval' for scripts.

    If either creeps in, the containment layer is decorative — an injected
    handler would run again.
    """
    _ws, client = _client(monkeypatch, tmp_path)
    csp = client.get("/").headers["Content-Security-Policy"]
    script_directive = [d.strip() for d in csp.split(";") if d.strip().startswith("script-src")]
    assert script_directive, f"no script-src in policy: {csp!r}"
    assert script_directive[0] == "script-src 'self'", script_directive[0]
    assert "unsafe-eval" not in csp


def test_policy_blocks_the_dangerous_defaults(monkeypatch, tmp_path):
    _ws, client = _client(monkeypatch, tmp_path)
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
    # 'self', not 'none'. The directive's job is to stop a FOREIGN page framing
    # this desk and overlaying it with decoy controls; 'self' keeps all of that,
    # because the only origin allowed to frame the app is the app's own origin —
    # which the writer already fully trusts (it is the same server handing out
    # the capability token). 'none' additionally blanked the same-origin design
    # console (webapp/design_session.html), and because its browser suite was
    # skipped in every gate run, nothing ever said so. See the dedicated test
    # below; the console's own suite asserts the frame actually renders.
    assert "frame-ancestors 'self'" in csp
    assert "frame-ancestors 'none'" not in csp


def test_frame_ancestors_allows_only_this_origin(monkeypatch, tmp_path):
    """The relaxation is exactly one word wide, and no wider.

    `frame-ancestors *` (or `http:`/`https:`) would let any site on the internet
    frame the desk; the point of the change was to unblock the app's own design
    console and nothing else. Pinned as its own value so a future edit has to
    argue with this assertion rather than quietly widen it.
    """
    _ws, client = _client(monkeypatch, tmp_path)
    csp = client.get("/").headers["Content-Security-Policy"]
    directive = [d.strip() for d in csp.split(";")
                 if d.strip().startswith("frame-ancestors")]
    assert directive == ["frame-ancestors 'self'"], directive
    for too_wide in ("*", "http:", "https:", "data:"):
        assert too_wide not in directive[0], f"{too_wide} would allow third-party framing"


def test_style_inline_is_allowed_deliberately(monkeypatch, tmp_path):
    # index.html carries inline style="" attributes and app.js builds more;
    # style injection is not a script-execution vector, so this is a considered
    # trade rather than an oversight. Pinned so it cannot be silently widened to
    # script-src as well.
    _ws, client = _client(monkeypatch, tmp_path)
    csp = client.get("/").headers["Content-Security-Policy"]
    style = [d.strip() for d in csp.split(";") if d.strip().startswith("style-src")]
    assert style and "'unsafe-inline'" in style[0]


def test_companion_hardening_headers_present(monkeypatch, tmp_path):
    _ws, client = _client(monkeypatch, tmp_path)
    r = client.get("/")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("Referrer-Policy") == "no-referrer"


def test_preview_labs_are_left_alone(monkeypatch, tmp_path):
    """The abandoned design labs are separate documents with their own inline
    scripts. Applying the strict policy globally would break them, so the header
    is scoped to the SPA document — this pins that scoping.
    """
    _ws, client = _client(monkeypatch, tmp_path)
    r = client.get("/preview-next/canvas-first.html")
    assert r.status_code == 200
    assert not r.headers.get("Content-Security-Policy"), (
        "preview labs must not inherit the SPA policy — they use inline scripts")


def test_plain_assets_do_not_need_the_policy(monkeypatch, tmp_path):
    # CSP travels with the document and governs what it loads, so a script file
    # does not need its own header.
    _ws, client = _client(monkeypatch, tmp_path)
    r = client.get("/app.js")
    assert r.status_code == 200
    assert not r.headers.get("Content-Security-Policy")
