"""Gap 33: HTTP inference redirects/proxies must not reroute sensitive payloads.

All endpoints are local mock servers and all bodies are synthetic. The redirect
probe models a 30x hop; no external hostname is contacted. The fix deliberately
refuses redirects and ignores ambient proxy variables at the shared transport.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from screenplay_analyzer.llm_client_base import BaseLlamaClient, LlamaServerError
from screenplay_cowriter.llm_client import LlamaServerClient as CowriterClient
from screenplay_studio import stt
from screenplay_studio.stt import STTUnavailableError


class _TargetHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.server.payloads.append(self.rfile.read(length))
        self.server.headers_seen.append(dict(self.headers))
        body = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.server.gets.append(self.path)
        body = json.dumps({"data": [{"id": "m"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class _RedirectHandler(BaseHTTPRequestHandler):
    def _redirect(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.server.received.append(self.rfile.read(length))
        self.server.headers_seen.append(dict(self.headers))
        self.send_response(self.server.code)
        self.send_header("Location", self.server.destination)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_POST = _redirect
    do_GET = _redirect

    def log_message(self, *args):
        pass


@pytest.fixture
def endpoints():
    target = ThreadingHTTPServer(("127.0.0.1", 0), _TargetHandler)
    target.payloads = []
    target.headers_seen = []
    target.gets = []
    target_thread = threading.Thread(target=target.serve_forever, daemon=True)
    target_thread.start()

    redirector = ThreadingHTTPServer(("127.0.0.1", 0), _RedirectHandler)
    redirector.received = []
    redirector.headers_seen = []
    redirector.code = 307
    redirector.destination = f"http://127.0.0.1:{target.server_port}/leak"
    redirect_thread = threading.Thread(target=redirector.serve_forever, daemon=True)
    redirect_thread.start()
    try:
        yield (f"http://127.0.0.1:{redirector.server_port}",
               f"http://127.0.0.1:{target.server_port}", redirector, target)
    finally:
        redirector.shutdown()
        target.shutdown()
        redirector.server_close()
        target.server_close()
        redirect_thread.join(timeout=2)
        target_thread.join(timeout=2)


class TestEvery30xIsRefusedBeforeFollowingTheHop:

    @pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
    def test_base_analyzer_client_does_not_follow(self, endpoints, status):
        redirect_url, _target_url, redirector, target = endpoints
        redirector.code = status
        client = BaseLlamaClient(redirect_url, extra_headers={"Authorization": "Bearer synthetic"})
        with pytest.raises(LlamaServerError, match=f"HTTP {status} redirect"):
            client._post_chat({"messages": [{"content": "synthetic screenplay"}]}, busy_retries=0)
        assert redirector.received == [b'{"messages": [{"content": "synthetic screenplay"}]}']
        assert redirector.headers_seen[-1].get("Authorization") == "Bearer synthetic"
        assert target.payloads == [] and target.gets == [], (
            "the redirect destination received a replayed body or followed GET")


class TestAllProviderTransportsUseTheSameBoundary:

    def test_models_get_does_not_follow_a_redirect(self, endpoints):
        redirect_url, _target_url, redirector, target = endpoints
        redirector.code = 302
        with pytest.raises(LlamaServerError, match="HTTP 302 redirect"):
            BaseLlamaClient(redirect_url).list_models_raw()
        assert target.gets == [] and target.payloads == []

    def test_best_effort_props_probe_does_not_follow(self, endpoints):
        redirect_url, _target_url, redirector, target = endpoints
        redirector.code = 302
        # /props is best-effort: refusing a redirect should simply yield no
        # context-window hint, never break the chat or follow the second hop.
        assert BaseLlamaClient(redirect_url).context_window() is None
        assert target.gets == []
        assert redirector.received == [b""]

    def test_cowriter_blocking_request_does_not_follow(self, endpoints):
        redirect_url, _target_url, _redirector, target = endpoints
        client = CowriterClient(redirect_url, model="m")
        client._resolved_model = "m"
        with pytest.raises(LlamaServerError, match="redirect"):
            client.chat([{"role": "user", "content": "synthetic"}])
        assert target.payloads == []

    def test_cowriter_sse_request_does_not_follow(self, endpoints):
        redirect_url, _target_url, redirector, target = endpoints
        redirector.code = 308
        client = CowriterClient(redirect_url, model="m")
        client._resolved_model = "m"
        with pytest.raises(LlamaServerError, match="HTTP 308 redirect"):
            client.chat_stream([], on_token=lambda _piece: None)
        assert target.payloads == []

    def test_external_stt_audio_does_not_follow(self, endpoints, monkeypatch):
        redirect_url, _target_url, _redirector, target = endpoints
        monkeypatch.setattr(stt, "EXTERNAL_WHISPER_URL", redirect_url)
        with pytest.raises(STTUnavailableError, match="HTTP 307 redirect"):
            stt._transcribe_external(b"synthetic audio", "clip.webm", "en")
        assert target.payloads == [], "audio reached the redirect destination"


class TestAmbientProxyEnvironmentIsNotASecondRoute:

    def test_http_and_all_proxy_environment_cannot_receive_payload(self, endpoints,
                                                                    monkeypatch):
        _redirect_url, target_url, _redirector, target = endpoints
        proxy = ThreadingHTTPServer(("127.0.0.1", 0), _TargetHandler)
        proxy.payloads = []
        proxy.headers_seen = []
        proxy.gets = []
        thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        proxy_url = f"http://127.0.0.1:{proxy.server_port}"
        try:
            monkeypatch.setenv("HTTP_PROXY", proxy_url)
            monkeypatch.setenv("http_proxy", proxy_url)
            monkeypatch.setenv("ALL_PROXY", proxy_url)
            monkeypatch.setenv("all_proxy", proxy_url)
            monkeypatch.setenv("NO_PROXY", "")
            monkeypatch.setenv("no_proxy", "")
            result = BaseLlamaClient(target_url)._post_chat(
                {"messages": [{"content": "synthetic screenplay"}]},
                timeout=3, busy_retries=0)
            assert result["choices"][0]["message"]["content"] == "ok"
            assert target.payloads, "the direct configured endpoint received nothing"
            assert proxy.payloads == [], "ambient proxy environment received the payload"
        finally:
            proxy.shutdown()
            proxy.server_close()
            thread.join(timeout=2)
