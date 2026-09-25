"""BE-1 (audit 2026-09-24) — the Host header must name this machine.

The finding this closes was *executed*, not inferred. With `TRUSTED_HOSTS`
unset and `request.host` never read, a page served from a name the attacker
controls could re-point that name at 127.0.0.1 (DNS rebinding) and every read
on this server answered it:

    GET /api/projects/<name>/script   Host: evil.attacker.com   -> 200
    (the writer's screenplay, in full, with no capability cookie)

Writes were already refused (403) by the Origin check, so this was a *read*
exposure — and reads are the half of the product that promises to stay on the
machine. The defence belongs on the Host header because it is a forbidden
header name for fetch/XHR: a page cannot forge it, and it is the one part of a
rebound request that still names the attacker.

Every rejection test below fails against the pre-fix server — verified by
reverting the guard and watching them go red, which is the whole complaint the
audit made about the *previous* loopback guard (it could not fail).
"""
from __future__ import annotations

import pytest

# Names a rebound page would arrive as. `localhost.evil.com` and
# `127.0.0.1.evil.com` are the prefix-match traps net_guard exists to avoid;
# `evil.com@127.0.0.1` is the userinfo trap urlparse would read as loopback;
# `0.0.0.0` is the wildcard bind, which is never a client's own name.
FOREIGN = (
    "evil.attacker.com",
    "evil.attacker.com:8500",
    "localhost.evil.com",
    "127.0.0.1.evil.com",
    "evil.com@127.0.0.1",
    "0.0.0.0",
    "192.168.1.50:8500",
)

# Names the writer's own browser legitimately arrives as.
LOCAL = (
    "localhost",
    "localhost:8500",
    "127.0.0.1",
    "127.0.0.1:8500",
    "127.0.0.2",          # any 127.0.0.0/8 address — a static TRUSTED_HOSTS list misses this
    "[::1]:8500",
)


def _client(monkeypatch, tmp_path, token="secret-token-123"):
    import screenplay_studio.webapp_server as ws
    monkeypatch.setattr(ws, "PROJECTS_DIR", str(tmp_path))
    monkeypatch.setattr(ws, "_API_TOKEN", token)
    ws.app.config["TESTING"] = True
    return ws, ws.app.test_client()


class TestForeignHostIsRefused:
    @pytest.mark.parametrize("host", FOREIGN)
    def test_reads_are_refused(self, monkeypatch, tmp_path, host):
        """The executed defect: a GET carried no token requirement, so a foreign
        Host read the project list — and `/script` read the screenplay."""
        _, client = _client(monkeypatch, tmp_path)
        r = client.get("/api/projects", headers={"Host": host})
        assert r.status_code == 403, f"Host {host!r} was served: {r.status_code}"

    @pytest.mark.parametrize("host", FOREIGN)
    def test_the_spa_document_is_refused(self, monkeypatch, tmp_path, host):
        _, client = _client(monkeypatch, tmp_path)
        assert client.get("/", headers={"Host": host}).status_code == 403

    @pytest.mark.parametrize("host", FOREIGN)
    def test_writes_are_refused_too(self, monkeypatch, tmp_path, host):
        """Reads were the exposure, but the guard is method-blind on purpose:
        one place decides, so a future route cannot reintroduce the hole."""
        _, client = _client(monkeypatch, tmp_path)
        r = client.post("/api/projects/The_Late_Hour/analyze",
                        headers={"Host": host, "X-Studio-Token": "secret-token-123"})
        assert r.status_code == 403

    def test_a_refused_request_is_not_handed_the_capability_cookie(self, monkeypatch, tmp_path):
        """The cookie is a page's licence to WRITE. Handing it to a request the
        Host guard just turned away would license the client it refused."""
        _, client = _client(monkeypatch, tmp_path)
        r = client.get("/", headers={"Host": "evil.attacker.com"})
        assert "studio_token" not in (r.headers.get("Set-Cookie") or "")

    def test_the_rejection_names_the_host_guard_not_the_token_guard(self, monkeypatch, tmp_path):
        """Ordering is load-bearing: if the write guard ran first, a foreign-Host
        POST would be refused for the wrong reason and the diagnosis would be a
        red herring."""
        _, client = _client(monkeypatch, tmp_path)
        r = client.post("/api/projects/The_Late_Hour/analyze",
                        headers={"Host": "evil.attacker.com"})
        assert r.status_code == 403
        body = r.get_json()
        assert "loopback" in (body or {}).get("error", ""), (
            f"refused by the wrong guard: {body!r}")

    def test_a_missing_host_header_is_not_a_free_pass(self, monkeypatch, tmp_path):
        """HTTP/1.0 lets a client omit Host. Werkzeug then synthesises one from
        SERVER_NAME — which is the test client's `localhost` — so this asserts
        the guard reads the *resolved* host rather than crashing on None."""
        ws, client = _client(monkeypatch, tmp_path)
        assert ws._host_header_is_local.__module__ == "screenplay_studio.webapp_server"
        assert client.get("/api/projects").status_code == 200


class TestLocalHostsStillWork:
    @pytest.mark.parametrize("host", LOCAL)
    def test_the_writer_is_served(self, monkeypatch, tmp_path, host):
        _, client = _client(monkeypatch, tmp_path)
        assert client.get("/api/projects", headers={"Host": host}).status_code == 200

    @pytest.mark.parametrize("host", LOCAL)
    def test_the_writer_still_gets_the_token_cookie(self, monkeypatch, tmp_path, host):
        """The guard must not cost the real page its licence to write."""
        _, client = _client(monkeypatch, tmp_path)
        r = client.get("/", headers={"Host": host})
        assert r.status_code == 200
        assert "studio_token=secret-token-123" in (r.headers.get("Set-Cookie") or "")

    def test_every_loopback_literal_is_accepted_by_the_predicate(self):
        """The guard is predicate-driven, not list-driven: `127.0.0.2` is a valid
        loopback address that no hand-written TRUSTED_HOSTS list would carry."""
        from screenplay_studio.net_guard import is_loopback_host
        assert is_loopback_host("127.0.0.2") is True
        assert is_loopback_host("127.0.0.1.evil.com") is False
        # the predicate answers for the bare IPv6 literal; the Host HEADER needs
        # the bracketed form, which the parametrized test below covers
        assert is_loopback_host("::1") is True

    @pytest.mark.parametrize("host", ["127.1", "2130706433", "0x7f000001",
                                      "0177.0.0.1", "127.0.0.2", "[::1]:8500"])
    def test_every_inet_aton_spelling_of_loopback_is_accepted(self, monkeypatch, tmp_path, host):
        """BE-5 (round-3 audit 2026-09-25): `ipaddress` accepts only the canonical
        textual forms, so these four legitimate ways to write 127.0.0.1 were all
        REFUSED — a false rejection with no workaround, on an app whose whole
        promise is that it is local. No browser sends them, which is why this was
        a completeness nit rather than a defect, but the guard's job is to answer
        "is this loopback?" correctly.

        `[::1]:8500` is the bracketed form an IPv6 `Host` header actually uses —
        the bare `::1` belongs to the predicate test above, because an unbracketed
        IPv6 literal is a malformed authority, not a spelling of loopback.
        """
        _, client = _client(monkeypatch, tmp_path)
        assert client.get("/api/projects", headers={"Host": host}).status_code == 200

    @pytest.mark.parametrize("host", ["3232235777", "0xc0a80101", "2886729729"])
    def test_the_inet_aton_path_does_not_open_a_bypass(self, monkeypatch, tmp_path, host):
        """The new branch must not accept a REMOTE host in a non-canonical
        spelling. `3232235777` is 192.168.1.1 and `2886729729` is 172.16.0.1 —
        private, but not loopback, and the range check must still refuse them."""
        _, client = _client(monkeypatch, tmp_path)
        assert client.get("/api/projects", headers={"Host": host}).status_code == 403

    @pytest.mark.parametrize("url", ["http://127.1:8080", "http://2130706433:8080",
                                     "http://127.0.0.1.:8080", "http://localhost.:8080"])
    def test_the_predicate_is_one_answer_for_urls_too(self, url):
        """`net_guard` exists so there is ONE "is this local?" answer. The same
        spellings reach it through `is_loopback_url` — which gates the model-server
        URL — and refusing them there was the same false rejection, one layer
        over."""
        from screenplay_studio.net_guard import is_loopback_url
        assert is_loopback_url(url) is True

    @pytest.mark.parametrize("url", ["http://3232235777:8080", "http://192.168.1.1:8080",
                                     "http://localhost.evil.com:8080",
                                     "http://evil.com.", "http://127.0.0.1.evil.com:80"])
    def test_the_url_form_refuses_remote_hosts_in_every_spelling(self, url):
        from screenplay_studio.net_guard import is_loopback_url
        assert is_loopback_url(url) is False

    @pytest.mark.parametrize("host", ["localhost.", "localhost.:8500", "127.0.0.1."])
    def test_the_dns_root_label_is_not_a_false_rejection(self, monkeypatch, tmp_path, host):
        """`localhost.` is `localhost` — the trailing dot is the root label. A
        writer who typed it must still be served, and stripping dots can only
        remove characters, so it cannot turn a foreign name into a loopback one.

        `localhost.:8500` is the form a browser actually sends, and it is why the
        dot has to be stripped from the parsed HOST rather than from the raw
        header (a raw `rstrip('.')` would leave this one broken)."""
        _, client = _client(monkeypatch, tmp_path)
        assert client.get("/api/projects", headers={"Host": host}).status_code == 200

    @pytest.mark.parametrize("host", ["evil.com.", "localhost.evil.com.", "0.0.0.0."])
    def test_the_root_label_does_not_open_a_bypass(self, monkeypatch, tmp_path, host):
        _, client = _client(monkeypatch, tmp_path)
        assert client.get("/api/projects", headers={"Host": host}).status_code == 403

    @pytest.mark.parametrize("host", ["[::1", "[::1]."])
    def test_a_malformed_ipv6_host_is_refused_not_crashed(self, monkeypatch, tmp_path, host):
        """`urlparse` raises ValueError on an unterminated IPv6 bracket, and
        `[::1].` is not a valid authority either. Both must be a 403, never a 500.
        No browser sends either form, so refusing them costs nothing."""
        _, client = _client(monkeypatch, tmp_path)
        assert client.get("/api/projects", headers={"Host": host}).status_code == 403


class TestTheTwoForbiddenAreDistinguishable:
    """BE-4 (round-3 audit 2026-09-25): both guards answer 403, and they need
    DIFFERENT advice. Reloading fixes a stale capability token; it cannot fix a
    Host the desk does not answer to, because the reload re-sends the same Host
    and gets the same 403. The client could not tell them apart from the status
    code, so it told the writer to reload either way — confidently wrong advice.
    The server marks the Host branch; `_tokenError` branches on the marker.
    """

    def test_the_host_refusal_is_marked(self, monkeypatch, tmp_path):
        _, client = _client(monkeypatch, tmp_path)
        r = client.get("/api/projects", headers={"Host": "evil.attacker.com"})
        assert r.status_code == 403
        body = r.get_json()
        assert body.get("host_rejected") is True, body

    def test_the_token_refusal_is_not_marked_as_a_host_refusal(self, monkeypatch, tmp_path):
        """The marker is the ONLY thing separating the two, so a token refusal
        that claimed it would send the writer to a loopback URL that was already
        correct — the same defect, mirrored."""
        _, client = _client(monkeypatch, tmp_path)
        r = client.post("/api/projects/whatever/analyze")   # no X-Studio-Token
        assert r.status_code == 403, r.get_data(as_text=True)
        body = r.get_json()
        assert not body.get("host_rejected"), body
        assert body.get("error"), "a 403 with no reason gives the client nothing"


class TestTheGuardCoversEveryReadableSurface:
    """BE-5 (audit 2026-09-24): `/api/health` discloses the model server URL on an
    unauthenticated GET.

    The audit listed it as LOW because it was *"one of the surfaces BE-1 makes
    remotely readable"* — so the finding's own premise is that the disclosure only
    matters if a foreign page can reach it. BE-1's fix is the Host guard, and this
    pins that the guard covers the surface the finding named rather than only the
    one the other tests happen to use. Without it, the disposition rests on a
    one-off manual check.
    """

    def test_health_is_readable_from_loopback(self, monkeypatch, tmp_path):
        """The guard must not break the endpoint for the writer's own browser."""
        _, client = _client(monkeypatch, tmp_path)
        r = client.get("/api/health", headers={"Host": "127.0.0.1:8500"})
        assert r.status_code == 200, r.get_data(as_text=True)
        assert r.get_json().get("status") == "ok"

    def test_health_is_refused_for_a_foreign_host(self, monkeypatch, tmp_path):
        """What DNS rebinding sends. This is what closes BE-5: the disclosure is
        loopback-only, which is what a local health endpoint is for."""
        _, client = _client(monkeypatch, tmp_path)
        r = client.get("/api/health", headers={"Host": "evil.attacker.com"})
        assert r.status_code == 403, (
            "a foreign Host can still read /api/health — the model server URL is "
            "disclosed to whatever page asked")
        assert r.get_json().get("host_rejected") is True
