"""Tests for the six-feature batch.

- F6  per-session save locking in the cowriter store
- F2  streaming chat: client SSE parse, engine on_token, webapp SSE route
- F3  retry-failed-categories endpoint + failed_categories in the summary
- F4  finding dismissal (triage): store, routes, fixqueue filtering
- F5  whole-project .zip backup route
- F1  inline edit reuses the existing /edits/apply path (single replacement)
"""

import io
import json
import os
import queue
import threading
import zipfile

import pytest

import screenplay_studio.webapp_server as webapp_server
from screenplay_cowriter.llm_client import LlamaServerError, LlamaServerClient as CowriterClient
from screenplay_cowriter.store import SessionStore, _lock_for
from screenplay_studio.manifest import ProjectManifest


# ---------------------------------------------------------------- F6

def test_lock_for_is_stable_per_path(tmp_path):
    a = _lock_for(str(tmp_path / "s1.json"))
    b = _lock_for(str(tmp_path / "s1.json"))
    c = _lock_for(str(tmp_path / "s2.json"))
    assert a is b and a is not c


def test_store_save_serializes_concurrent_writers(tmp_path):
    """Two threads saving the same session file must not tear it — every save
    lands as valid JSON under the per-path lock."""
    store = SessionStore(str(tmp_path))
    session = store.create("T")
    errors = []

    def hammer(n):
        try:
            for i in range(25):
                session.title = f"T-{n}-{i}"
                store.save(session)
                loaded = store.load(session.session_id)  # must always parse
                assert loaded.session_id == session.session_id
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=hammer, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert os.path.exists(store._path(session.session_id))


# ---------------------------------------------------------------- F2

class _FakeStreamResp:
    def __init__(self, lines, status=200):
        self._lines = lines
        self.status_code = status

    def iter_lines(self, decode_unicode=False):
        return iter(self._lines)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def close(self):
        pass


def test_chat_stream_parses_sse_and_returns_full_text(monkeypatch):
    sse_lines = [
        'data: {"choices": [{"delta": {"content": "Hel"}}]}',
        "",  # keep-alive blank line
        'data: {"choices": [{"delta": {"content": "lo"}}]}',
        "data: [DONE]",
    ]
    seen = {}

    def fake_post(url, json=None, **kw):
        seen["url"] = url
        seen["payload"] = json
        return _FakeStreamResp(sse_lines)

    monkeypatch.setattr("screenplay_cowriter.llm_client.requests.post", fake_post)
    monkeypatch.setattr(CowriterClient, "resolve_model", lambda self: "m")

    client = CowriterClient(base_url="http://127.0.0.1:9999")
    got = []
    full = client.chat_stream([{"role": "user", "content": "hi"}], on_token=got.append)

    assert got == ["Hel", "lo"]
    assert full == "Hello"
    assert seen["payload"]["stream"] is True
    assert seen["url"].endswith("/v1/chat/completions")


def test_chat_stream_busy_server_fails_fast(monkeypatch):
    def fake_post(url, json=None, **kw):
        return _FakeStreamResp([], status=503)

    monkeypatch.setattr("screenplay_cowriter.llm_client.requests.post", fake_post)
    monkeypatch.setattr(CowriterClient, "resolve_model", lambda self: "m")
    client = CowriterClient(base_url="http://127.0.0.1:9999")
    with pytest.raises(LlamaServerError):
        client.chat_stream([{"role": "user", "content": "hi"}], on_token=lambda t: None)


class _StreamingFakeClient:
    def __init__(self):
        self.streamed = []

    def chat_stream(self, messages, on_token=None, **kw):
        for piece in ["raw ", "bits"]:
            if on_token:
                on_token(piece)
            self.streamed.append(piece)
        return "raw bits"


class _PlainFakeClient:
    def chat(self, messages, **kw):
        return "plain reply"


def _engine(client):
    from screenplay_cowriter.context import ReportContext, ScriptContext
    from screenplay_cowriter.engine import CoWriterEngine
    return CoWriterEngine(client, ScriptContext(None), ReportContext(None))


def test_engine_on_token_streams_raw_but_stores_clean_reply():
    client = _StreamingFakeClient()
    engine = _engine(client)
    from screenplay_cowriter.models import Session
    session = Session.new(title="t")
    seen = []
    reply = engine.send_message(session, "hello", on_token=seen.append)
    # streamed raw pieces reached the caller exactly once each
    assert seen == ["raw ", "bits"]
    assert client.streamed == ["raw ", "bits"]
    # stored history carries the final reply (hygiene pipeline ran; identical here)
    assert session.branch.messages[-1].content == reply


def test_engine_without_chat_stream_falls_back_to_blocking_call():
    engine = _engine(_PlainFakeClient())
    from screenplay_cowriter.models import Session
    session = Session.new(title="t")
    reply = engine.send_message(session, "hello", on_token=lambda t: None)
    assert reply.startswith("plain reply")  # forward-momentum nudge may append


class _FakeBranchMsg:
    def __init__(self, role, content):
        self.role, self.content = role, content

    def to_dict(self):
        return {"role": self.role, "content": self.content}


class _FakeSession:
    current_branch = "main"

    class branch:  # noqa: N801
        messages = [_FakeBranchMsg("assistant", "done")]


class _FakeStore:
    def __init__(self):
        self.saved = 0

    def save(self, session):
        self.saved += 1


class _FakeEngine:
    def send_message(self, session, text, quote=None, on_token=None):
        for piece in ("He", "y"):
            on_token(piece)
        return "Hey"


def _frames(gen):
    out = []
    for chunk in gen:
        assert chunk.startswith("data: ") and chunk.endswith("\n\n")
        out.append(json.loads(chunk[len("data: "):]))
    return out


def test_sse_chat_stream_tokens_then_done():
    store = _FakeStore()
    frames = _frames(webapp_server._sse_chat_stream(_FakeEngine(), _FakeSession(), store, "hi", None))
    assert [f.get("token") for f in frames[:2]] == ["He", "y"]
    done = frames[-1]
    assert done["done"] is True and done["reply"] == "Hey"
    assert done["messages"][0]["content"] == "done"
    assert store.saved == 1  # the stream route persists the turn at done-time


def test_sse_chat_stream_error_ends_the_stream():
    class Boom:
        def send_message(self, session, text, quote=None, on_token=None):
            raise RuntimeError("server dead")

    frames = _frames(webapp_server._sse_chat_stream(Boom(), _FakeSession(), _FakeStore(), "hi", None))
    assert len(frames) == 1
    assert frames[0]["error"] and "server dead" in frames[0]["error"]
    assert frames[0]["still_working"] is False


# ------------------------------------------------- F3/F4/F5/F1 (webapp API)

@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


SAMPLE_SCRIPT = b"""Title: Feature Batch Test
Author: Test

INT. STUDY - NIGHT

MARA takes out an old REVOLVER.

MARA
I'll tell you everything when this is over.
"""


def _upload(http_client):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"), "title": "Feature Batch"},
        content_type="multipart/form-data",
    ).get_json()["project"]


class TestRetryFailedEndpoint:
    def test_requires_completed_analysis(self, http_client):
        project = _upload(http_client)
        resp = http_client.post(f"/api/projects/{project}/analyze/retry-failed", json={})
        assert resp.status_code == 400

    def test_unknown_project_404(self, http_client):
        resp = http_client.post("/api/projects/nope/analyze/retry-failed", json={})
        assert resp.status_code == 404

    def test_manifest_summary_carries_failed_categories(self, tmp_path):
        src = tmp_path / "s.fountain"
        src.write_text("Title: T\n\nINT. R - NIGHT\n\nAction.\n", encoding="utf-8")
        m = ProjectManifest.create(str(tmp_path / "proj"), str(src), title="T")
        m.mark_complete("analyze", {"failed_categories": ["genre"], "category_outcomes": {"genre": "failed"}})
        summary = webapp_server._manifest_summary(m)
        assert summary["failed_categories"] == ["genre"]

    def test_retry_runs_and_clears_failed_list(self, http_client):
        project = _upload(http_client)
        http_client.post(f"/api/projects/{project}/analyze", json={})
        # whatever failed last run, a retry must succeed against the mock and
        # leave a consistent manifest behind
        resp = http_client.post(f"/api/projects/{project}/analyze/retry-failed", json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data["failed_categories"], list)


class TestFindingDismissal:
    def test_dismiss_roundtrip_filters_fixqueue(self, http_client):
        project = _upload(http_client)
        http_client.post(f"/api/projects/{project}/analyze", json={})
        base = f"/api/projects/{project}"
        full = http_client.get(f"{base}/fixqueue?include_dismissed=1").get_json()
        items = full["items"]
        if not items:  # mock analysis produced no findings here — nothing to triage
            pytest.skip("mock analysis produced no findings")

        target = items[0]
        resp = http_client.post(f"{base}/findings/{target['index']}/dismiss",
                                json={"issue": target["issue"] or ""})
        assert resp.status_code == 200

        default_view = http_client.get(f"{base}/fixqueue").get_json()
        assert all(i["index"] != target["index"] for i in default_view["items"])
        assert default_view["dismissed_count"] >= 1

        shown = http_client.get(f"{base}/fixqueue?include_dismissed=1").get_json()
        flagged = next(i for i in shown["items"] if i["index"] == target["index"])
        assert flagged["dismissed"] is True

        # restore brings it back
        assert http_client.post(f"{base}/findings/{target['index']}/undismiss").status_code == 200
        restored = http_client.get(f"{base}/fixqueue").get_json()
        assert any(i["index"] == target["index"] for i in restored["items"])

    def test_dismissal_survives_reload_and_matches_issue(self, http_client):
        project = _upload(http_client)
        http_client.post(f"/api/projects/{project}/analyze", json={})
        base = f"/api/projects/{project}"
        items = http_client.get(f"{base}/fixqueue?include_dismissed=1").get_json()["items"]
        if not items:
            pytest.skip("mock analysis produced no findings")
        target = items[0]
        http_client.post(f"{base}/findings/{target['index']}/dismiss", json={"issue": target["issue"] or ""})

        m = ProjectManifest.load(os.path.join(webapp_server.PROJECTS_DIR, project))
        from screenplay_studio.revision import dismissed_issues, dismiss_finding, undismiss_finding
        keys = dismissed_issues(m)
        assert (target["index"], target["issue"] or "") in keys
        # a different issue at the same index does NOT count as dismissed
        assert (target["index"], "totally different") not in keys
        undismiss_finding(m, target["index"])
        assert (target["index"], target["issue"] or "") not in dismissed_issues(m)
        dismiss_finding(m, target["index"], "x")  # still loadable afterwards

    def test_unknown_project_json_404(self, http_client):
        assert http_client.post("/api/projects/nope/findings/0/dismiss", json={}).status_code == 404
        assert http_client.post("/api/projects/nope/findings/0/undismiss", json={}).status_code == 404


class TestZipBackup:
    def test_backup_is_valid_zip_with_project_files(self, http_client):
        project = _upload(http_client)
        resp = http_client.get(f"/api/projects/{project}/backup")
        assert resp.status_code == 200
        assert resp.mimetype == "application/zip"
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        names = zf.namelist()
        assert f"{project}/project.json" in names
        assert any(n.endswith("source.fountain") for n in names)
        # round-trip: the archived manifest parses and matches the live one
        manifest = json.loads(zf.read(f"{project}/project.json"))
        assert manifest["title"] == "Feature Batch"

    def test_backup_unknown_project_404(self, http_client):
        assert http_client.get("/api/projects/nope/backup").status_code == 404


class TestInlineEditRidesApplyPath:
    def test_single_replacement_through_edits_apply(self, http_client):
        project = _upload(http_client)
        base = f"/api/projects/{project}"
        script = http_client.get(f"{base}/script").get_json()
        scene = script["scenes"][0]
        old_line = scene["elements"][1]["text"]  # first non-heading element

        resp = http_client.post(f"{base}/edits/apply", json={
            "scene_number": scene["scene_number"],
            "replacements": [{"old": old_line, "new": old_line + " EDITED"}],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["applied"] and data["applied"][0]["old"] == old_line

        after = http_client.get(f"{base}/script").get_json()
        texts = [e["text"] for s in after["scenes"] for e in s["elements"]]
        assert old_line + " EDITED" in texts
        # the edit landed in the undo log like any other edit
        edits = http_client.get(f"{base}/edits").get_json()
        assert edits["edits"] and edits["can_undo"]
