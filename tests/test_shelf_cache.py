"""The shelf digests are deferred and memoised (C10).

`_load_session_and_engine` runs for every session request — GET, DELETE,
branch switch, chat turn. It used to rebuild the writer's past-work digest and
the doctor's case file *unconditionally*, so loading a conversation paid for a
walk of the whole shelf and a JSON parse of every project on it, whether or not
the shelf had changed and whether or not a prompt would ever be built.

Two halves are pinned here:

  1. **Deferred** — the server hands the engine providers (zero-arg callables)
     and the engine resolves them only when it builds a prompt. A request that
     never generates does no shelf work at all, and the doctor's case file is
     resolved only for the persona that reads it.
  2. **Memoised** — when they are built, a stat-only fingerprint of exactly the
     files the digests read decides whether the previous result can be reused.
     A changed project, a new project and a deletion all invalidate it.
"""

import json
import shutil

import pytest

import screenplay_studio.webapp_server as webapp_server
from screenplay_cowriter.context import ReportContext, ScriptContext
from screenplay_cowriter.engine import CoWriterEngine, _resolve_prompt_block
from screenplay_cowriter.models import Session


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

class _Client:
    """Records the messages it was asked to complete, so a test can inspect the
    assembled prompt without a live model. Accepts (and ignores) the real
    client's constructor kwargs so it can stand in for LlamaServerClient."""

    def __init__(self, reply="Noted.", **kw):
        self.reply = reply
        self.messages = None

    def _remember(self, messages):
        self.messages = messages
        return self.reply

    def chat(self, messages, **kw):
        return self._remember(messages)

    def chat_stream(self, messages, on_token=None, **kw):
        if on_token:
            on_token(self.reply)
        return self._remember(messages)


def _engine(client=None, **kw):
    return CoWriterEngine(client or _Client(), ScriptContext(None), ReportContext(None), **kw)


def _system_prompt(client):
    return client.messages[0]["content"]


def _write_project(root, name, title="T", scenes=2, characters=("MARA",)):
    d = root / name
    d.mkdir(exist_ok=True)
    (d / "parsed.json").write_text(json.dumps({
        "title": title,
        "source_format": "fountain",
        "scene_count": scenes,
        "all_characters": list(characters),
        "scenes": [],
    }), encoding="utf-8")
    return d


@pytest.fixture
def shelf(tmp_path, monkeypatch):
    root = tmp_path / "shelf"
    root.mkdir()
    monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(root))
    webapp_server._SHELF_CACHE.clear()
    yield root
    webapp_server._SHELF_CACHE.clear()


@pytest.fixture
def walk_counter(monkeypatch):
    """Counts real shelf builds, leaving the real builder in place."""
    real = webapp_server._build_library
    walks = []

    def counted(lib_mod, exclude):
        walks.append(exclude)
        return real(lib_mod, exclude)

    monkeypatch.setattr(webapp_server, "_build_library", counted)
    return walks


# --------------------------------------------------------------------------
# 1. the blocks are deferred to prompt-build time
# --------------------------------------------------------------------------

class TestPromptBlocksAreDeferred:
    def test_a_provider_is_not_called_at_construction(self):
        calls = []
        _engine(writer_library_text=lambda: calls.append("lib") or "PAST WORK")
        assert calls == [], "the shelf was walked before any prompt was built"

    def test_a_provider_is_resolved_when_a_prompt_is_built(self):
        calls = []
        engine = _engine(writer_library_text=lambda: calls.append("lib") or "PAST WORK")
        engine.send_message(Session.new(title="t"), "hello")
        assert calls == ["lib"]

    def test_the_resolved_text_reaches_the_prompt(self):
        client = _Client()
        engine = _engine(client, writer_library_text=lambda: "PAST WORK — a different shelf")
        engine.send_message(Session.new(title="t"), "hello")
        assert "PAST WORK — a different shelf" in _system_prompt(client)

    def test_a_plain_string_is_still_accepted(self):
        client = _Client()
        engine = _engine(client, writer_library_text="PAST WORK — literal")
        engine.send_message(Session.new(title="t"), "hello")
        assert "PAST WORK — literal" in _system_prompt(client)

    def test_the_case_file_is_built_only_for_the_persona_that_reads_it(self):
        calls = []
        engine = _engine(doctor_case_text=lambda: calls.append("case") or "CASE FILE")

        sameer = Session.new(title="t")
        sameer.branch.active_persona = "writing_partner"
        engine.send_message(sameer, "hello")
        assert calls == [], "the case file was built for a persona that discards it"

        doctor = Session.new(title="t")
        doctor.branch.active_persona = "script_consultant"
        engine.send_message(doctor, "hello")
        assert calls == ["case"]

    def test_a_provider_that_raises_does_not_break_the_turn(self):
        def boom():
            raise OSError("the shelf is unreadable")

        engine = _engine(writer_library_text=boom, doctor_case_text=boom)
        reply = engine.send_message(Session.new(title="t"), "hello")
        assert reply, "a broken shelf took the chat down with it"

    def test_resolver_returns_text_and_none_unchanged(self):
        assert _resolve_prompt_block(None) is None
        assert _resolve_prompt_block("literal") == "literal"
        assert _resolve_prompt_block(lambda: "built") == "built"


# --------------------------------------------------------------------------
# 2. the digest is memoised on a stat-only fingerprint
# --------------------------------------------------------------------------

class TestShelfDigestIsMemoised:
    def test_a_repeat_walk_is_served_from_the_fingerprint(self, shelf, walk_counter):
        _write_project(shelf, "Alpha")
        first = webapp_server._writer_library()
        second = webapp_server._writer_library()
        assert len(walk_counter) == 1, "an unchanged shelf was parsed twice"
        assert first == second
        assert [e["project"] for e in first] == ["Alpha"]

    def test_a_changed_project_invalidates(self, shelf, walk_counter):
        _write_project(shelf, "Alpha", title="Draft One")
        assert webapp_server._writer_library()[0]["title"] == "Draft One"

        _write_project(shelf, "Alpha", title="Draft Two", scenes=9)
        refreshed = webapp_server._writer_library()
        assert len(walk_counter) == 2, "the digest was served stale after an edit"
        assert refreshed[0]["title"] == "Draft Two"

    def test_a_new_project_invalidates(self, shelf, walk_counter):
        _write_project(shelf, "Alpha")
        webapp_server._writer_library()

        _write_project(shelf, "Beta")
        lib = webapp_server._writer_library()
        assert len(walk_counter) == 2
        assert {e["project"] for e in lib} == {"Alpha", "Beta"}

    def test_a_deleted_project_invalidates(self, shelf, walk_counter):
        _write_project(shelf, "Alpha")
        _write_project(shelf, "Beta")
        webapp_server._writer_library()

        shutil.rmtree(shelf / "Beta")
        lib = webapp_server._writer_library()
        assert len(walk_counter) == 2, "a deleted project stayed in the digest"
        assert {e["project"] for e in lib} == {"Alpha"}

    def test_a_corrupt_project_invalidates_when_it_appears(self, shelf, walk_counter):
        _write_project(shelf, "Alpha")
        webapp_server._writer_library()

        broken = shelf / "Broken"
        broken.mkdir()
        (broken / "parsed.json").write_text("{ torn", encoding="utf-8")
        lib = webapp_server._writer_library()
        assert len(walk_counter) == 2
        assert any(e.get("unreadable") for e in lib)

    def test_excludes_do_not_share_a_cache_entry(self, shelf, walk_counter):
        _write_project(shelf, "Alpha")
        _write_project(shelf, "Beta")
        assert len(webapp_server._writer_library(exclude="Alpha")) == 1
        assert len(webapp_server._writer_library()) == 2
        assert len(webapp_server._writer_library(exclude="Alpha")) == 1
        # one build per distinct exclude, not one per call
        assert sorted(walk_counter, key=str) == ["Alpha", None]

    def test_the_case_file_is_memoised_too(self, shelf, monkeypatch):
        _write_project(shelf, "Alpha")
        (shelf / "Alpha" / "project.json").write_text(
            json.dumps({"stages": {"analyze": {"status": "complete"}},
                        "report_findings_path": "report.findings.json"}), encoding="utf-8")
        (shelf / "Alpha" / "report.findings.json").write_text(
            json.dumps({"findings": [{"category": "structure", "severity": "high",
                                      "issue": "Sags"}]}), encoding="utf-8")

        builds = []
        real = webapp_server._build_doctor_case_file
        monkeypatch.setattr(webapp_server, "_build_doctor_case_file",
                            lambda exclude=None: builds.append(exclude) or real(exclude))

        first = webapp_server._doctor_case_file()
        second = webapp_server._doctor_case_file()
        assert len(builds) == 1, "the case file was rebuilt for an unchanged shelf"
        assert first == second

    def test_an_unlistable_shelf_is_never_cached(self, tmp_path, monkeypatch):
        monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(tmp_path / "does-not-exist"))
        webapp_server._SHELF_CACHE.clear()
        assert webapp_server._writer_library() == []
        assert webapp_server._SHELF_CACHE == {}, "a transient failure was cached"

    def test_the_cache_map_stays_bounded(self, shelf):
        for i in range(webapp_server._SHELF_CACHE_MAX + 4):
            _write_project(shelf, f"P{i}")
            webapp_server._writer_library()
        assert len(webapp_server._SHELF_CACHE) <= webapp_server._SHELF_CACHE_MAX


# --------------------------------------------------------------------------
# 3. end to end: the request that never generates does no shelf work
# --------------------------------------------------------------------------

class TestNonGeneratingRequestsDoNoShelfWork:
    @pytest.fixture
    def project_with_session(self, shelf, monkeypatch):
        """A real project + a real session file, so _load_session_and_engine runs
        its real path (manifest, store, script, engine)."""
        from screenplay_cowriter import llm_client, memory
        from screenplay_cowriter.store import SessionStore
        from screenplay_studio.manifest import ProjectManifest

        monkeypatch.setattr(llm_client, "LlamaServerClient", _Client)
        monkeypatch.setattr(memory.WriterMemory, "load", classmethod(lambda cls, path: None))

        src = shelf / "draft.fountain"
        src.write_text("Title: T\n\nINT. ROOM - NIGHT\n\nA line.\n", encoding="utf-8")
        project_dir = shelf / "Alpha"
        ProjectManifest.create(str(project_dir), str(src), title="Alpha")
        # the engine loads the parsed document; the manifest only records where
        # it lives, so the parse has to exist for the real code path to run
        _write_project(shelf, "Alpha", title="Alpha")
        session = SessionStore(str(project_dir / "sessions")).create("a chat")
        return "Alpha", session.session_id

    @pytest.fixture
    def fingerprints(self, monkeypatch):
        calls = []
        real = webapp_server._shelf_fingerprint
        monkeypatch.setattr(webapp_server, "_shelf_fingerprint",
                            lambda exclude=None: calls.append(exclude) or real(exclude))
        return calls

    @pytest.fixture
    def case_builds(self, monkeypatch):
        calls = []
        real = webapp_server._build_doctor_case_file
        monkeypatch.setattr(webapp_server, "_build_doctor_case_file",
                            lambda exclude=None: calls.append(exclude) or real(exclude))
        return calls

    def test_loading_a_session_never_touches_the_shelf(
            self, project_with_session, fingerprints):
        name, sid = project_with_session
        webapp_server._load_session_and_engine(name, sid)
        assert fingerprints == [], "loading a conversation walked the shelf"

    def test_a_chat_turn_walks_the_shelf_exactly_once(
            self, project_with_session, fingerprints, case_builds):
        name, sid = project_with_session
        _, engine, _ = webapp_server._load_session_and_engine(name, sid)
        assert fingerprints == []

        engine.send_message(Session.new(title="t"), "hello")
        assert len(fingerprints) == 1, "a Sameer turn should scan the shelf once"
        assert case_builds == [], "the case file is the doctor's alone"

    def test_a_doctor_turn_builds_both_blocks_from_one_scan(
            self, project_with_session, fingerprints, case_builds):
        name, sid = project_with_session
        _, engine, _ = webapp_server._load_session_and_engine(name, sid)

        doctor = Session.new(title="t")
        doctor.branch.active_persona = "script_consultant"
        engine.send_message(doctor, "hello")
        assert case_builds != [], "the doctor's turn never built the case file"
        assert len(fingerprints) == 1, (
            "the digest and the case file must share one shelf scan, not take one each"
        )
