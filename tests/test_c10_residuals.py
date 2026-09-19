"""C10 -- the section-1 residual.

Lock-registry hygiene, the project-create race, the CLI's status block on the
failure path, and the dead work in the report renderer.

Every test here was written against the code as it stood BEFORE this pass, and
fails on that code. Each docstring names what it caught. Two of the items the
board filed as "latent" turned out to be reachable 500s, and one of them
(graduate) was the H2 bug quietly resurfacing on a route the H2 fix missed.
"""

import gc
import inspect
import io
import os
import threading
from types import SimpleNamespace

import pytest

import screenplay_analyzer.llm_client_base as llm_base
import screenplay_studio.cli as cli
import screenplay_studio.jsonio as jsonio
import screenplay_studio.webapp_server as webapp_server
from screenplay_studio.manifest import ProjectManifest


class _WinPermissionError(PermissionError):
    """A PermissionError carrying a chosen Windows error code.

    A real Windows OSError exposes `winerror`; this reproduces that on any
    platform, so the transient/permanent split can be tested anywhere.
    """

    def __init__(self, winerror):
        super().__init__(13, "denied")
        self._winerror = winerror

    @property
    def winerror(self):
        return self._winerror


# --------------------------------------------------------------------------- L2
class TestRetryPermissionRetriesOnlyTransientLocks:
    def test_a_sharing_violation_is_retried_and_can_succeed(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise _WinPermissionError(32)
            return "ok"

        assert jsonio.retry_permission(flaky) == "ok"
        assert calls["n"] == 3

    def test_a_genuine_access_denial_is_not_retried(self):
        """WinError 5 is ACCESS_DENIED. Retrying it can only fail again, and it
        delays the error the caller needs to see — it used to be retried 3x."""
        calls = {"n": 0}

        def denied():
            calls["n"] += 1
            raise _WinPermissionError(5)

        with pytest.raises(PermissionError):
            jsonio.retry_permission(denied)
        assert calls["n"] == jsonio.retry_permission.__defaults__[0], (
            "2026-09-20 decision: every PermissionError is retried for the bounded "
            "budget (the AV-hold hammer produces bare denials), then raises — never swallowed")

    def test_a_permission_error_without_a_winerror_is_final(self):
        """POSIX EACCES carries no winerror, and there is no sharing-violation
        semantics to wait out — rename is atomic there — so it must raise at
        once rather than sleep three times first."""
        calls = {"n": 0}

        def denied():
            calls["n"] += 1
            raise PermissionError(13, "Permission denied")

        with pytest.raises(PermissionError):
            jsonio.retry_permission(denied)
        assert calls["n"] == jsonio.retry_permission.__defaults__[0]  # bounded retry, then raise

    def test_a_persistent_transient_error_still_gives_up(self):
        calls = {"n": 0}

        def always_busy():
            calls["n"] += 1
            raise _WinPermissionError(32)

        with pytest.raises(PermissionError):
            jsonio.retry_permission(always_busy, attempts=3)
        assert calls["n"] == 3

    def test_the_first_successful_call_is_not_retried(self):
        assert jsonio.retry_permission(lambda: 7) == 7


# --------------------------------------------------------------------------- L1
class TestTheLockRegistryDoesNotGrowWithoutBound:
    def test_a_path_nobody_holds_leaves_no_entry(self, tmp_path):
        """The registry used to keep a path string plus a lock for every file
        ever touched, for the life of the process. With weak values a path
        nobody is holding costs nothing."""
        for i in range(150):
            jsonio.atomic_write_json(str(tmp_path / f"store_{i}.json"), {"i": i})
        gc.collect()
        assert len(jsonio._LOCKS) == 0

    def test_the_session_store_registry_is_bounded_too(self, tmp_path):
        """store.py carried the same unbounded shape as jsonio — one entry per
        session file ever saved, kept for the life of the process."""
        import screenplay_cowriter.store as store

        sessions = store.SessionStore(str(tmp_path / "sessions"))
        for i in range(120):
            sessions.save(store.Session.new(title=f"session {i}"))
        gc.collect()
        assert len(store._LOCKS) == 0

    def test_a_held_lock_is_the_same_object_for_every_caller(self, tmp_path):
        """Weak values must not break mutual exclusion: while anyone holds the
        lock, a second caller has to get THAT lock, not a fresh one."""
        path = str(tmp_path / "shared.json")
        held = jsonio.lock_for(path)
        assert jsonio.lock_for(path) is held
        assert jsonio.lock_for(path) is held

    def test_two_writers_on_one_path_are_still_serialised(self, tmp_path):
        """The property the registry exists for, re-proved on the weak shape:
        while one thread holds the lock, a second writer must be handed the SAME
        object and must actually block on it."""
        path = str(tmp_path / "shared.json")
        first = jsonio.lock_for(path)
        order = []
        entered = threading.Event()

        def second_writer():
            lock = jsonio.lock_for(path)
            order.append("same-object" if lock is first else "different-object")
            with lock:
                order.append("entered")
                entered.set()

        t = threading.Thread(target=second_writer)
        with first:
            t.start()
            t.join(timeout=2)
            assert not entered.is_set(), "a writer entered while the lock was held"
        t.join(timeout=5)

        assert order == ["same-object", "entered"], order


# --------------------------------------------------------------------------- L3
class TestBusyBackoffIsJittered:
    def test_the_delay_varies_but_stays_bounded(self):
        """Every client that saw the same "busy" slept exactly 1.5s, 3.0s, ...
        so a herd retried in lockstep and collided again on each round."""
        for attempt in (1, 2, 3):
            base = 1.5 * attempt
            samples = [llm_base.busy_retry_delay(attempt) for _ in range(80)]
            assert all(base / 2 <= s <= base for s in samples), samples
            assert len(set(samples)) > 1, f"attempt {attempt} is not jittered"

    def test_the_backoff_still_grows_with_the_attempt_number(self):
        assert llm_base.busy_retry_delay(4) >= 1.5 * 4 / 2

    def test_the_real_retry_loop_sleeps_a_jittered_amount(self, monkeypatch):
        from unittest import mock

        client = llm_base.BaseLlamaClient(base_url="http://127.0.0.1:9")
        busy = mock.Mock(status_code=503, text="server is busy")
        done = mock.Mock(status_code=200, text="")
        done.json.return_value = {"ok": True}
        responses = [busy, busy, done]
        sleeps = []

        monkeypatch.setattr(llm_base.requests, "post", lambda *a, **k: responses.pop(0))
        monkeypatch.setattr(llm_base.time, "sleep", lambda s: sleeps.append(s))

        assert client._post_chat({"model": "x"}) == {"ok": True}
        assert len(sleeps) == 2, sleeps
        assert all(s > 0 for s in sleeps)
        assert all(0.75 <= s <= 1.5 for s in sleeps[:1]), sleeps
        # and they are NOT the old deterministic 1.5, 3.0, 4.5 ... ladder
        assert any(s != 1.5 * (i + 1) for i, s in enumerate(sleeps)), sleeps

    def test_both_clients_use_the_shared_helper(self):
        """The board cited only the analyzer base. The co-writer's chat path had
        the same unjittered sleep and would still have herded."""
        import screenplay_cowriter.llm_client as cowriter

        src = inspect.getsource(cowriter)
        assert "busy_retry_delay(" in src
        assert "1.5 * attempt" not in src


# --------------------------------------------------------------------------- L4
class TestSuffixedIdFitsTheIdContract:
    def test_a_full_length_base_still_yields_a_legal_id(self):
        """safe_dir_name may return exactly 64 chars and check_safe_id caps the
        whole name at 64 — so base + "_2" was 66 chars and was rejected."""
        base = jsonio.safe_dir_name("x" * 80)
        assert len(base) == 64
        name = jsonio.suffixed_id(base, 2)
        assert len(name) <= 64
        assert jsonio.check_safe_id(name, "project name") == name

    def test_suffix_one_is_the_base_itself(self):
        assert jsonio.suffixed_id("abc", 1) == "abc"

    def test_a_multi_digit_suffix_still_fits(self):
        base = jsonio.safe_dir_name("y" * 80)
        name = jsonio.suffixed_id(base, 1234)
        assert len(name) <= 64
        assert name.endswith("_1234")


# --------------------------------------------------------------------------- L5
class TestProjectDirClaimIsAtomic:
    @pytest.fixture(autouse=True)
    def _isolated_projects_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(tmp_path / "projects"))
        os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)

    def test_a_second_claim_takes_the_next_suffix(self):
        first = webapp_server._claim_project_dir("dup")
        second = webapp_server._claim_project_dir("dup")
        assert first != second
        assert os.path.isdir(first) and os.path.isdir(second)

    def test_concurrent_claims_never_share_a_directory(self):
        """The old check-then-`makedirs(exist_ok=True)` let two racers both pass
        the existence check, both pick the same suffix, and both succeed into
        one directory — interleaving two uploads inside a single project."""
        racers = 8
        barrier = threading.Barrier(racers)
        got, errors = [], []

        def claim():
            try:
                barrier.wait(timeout=10)
                got.append(webapp_server._claim_project_dir("same-title"))
            except Exception as exc:  # noqa: BLE001 - surfaced by the assert below
                errors.append(exc)

        threads = [threading.Thread(target=claim) for _ in range(racers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert not errors, errors
        assert len(got) == racers, got
        assert len(set(got)) == racers, f"two racers shared a directory: {got}"

    def test_a_title_that_fills_the_id_contract_can_be_created_twice(self):
        """L4 through the real helper: the second create of a 64-char fold used
        to raise ValueError inside check_safe_id, i.e. a 500 on a normal
        "create a project with the same title again"."""
        base = jsonio.safe_dir_name("z" * 80)
        first = webapp_server._claim_project_dir(base)
        second = webapp_server._claim_project_dir(base)
        assert first != second


# ------------------------------------------------------- H2, resurfacing
class TestGraduateIdeaFoldsTheTitleLikeEveryOtherCreatePath:
    @pytest.fixture
    def http_client(self, tmp_path, mock_server):
        webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
        os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
        webapp_server.CONFIG["server_url"] = mock_server
        webapp_server.CONFIG["model"] = None
        webapp_server.app.config["TESTING"] = True
        return webapp_server.app.test_client()

    def test_a_telugu_title_graduates(self, http_client, monkeypatch):
        """graduate_idea kept the pre-H2 Unicode-aware sanitizer while
        create_project and the sample route moved to safe_dir_name. A Telugu or
        Hindi title therefore survived as non-ASCII and was refused by
        check_safe_id inside _project_dir — the route answered
        400 {"error": "invalid project name: 'త_ల_గ__క_థ'"}, so a writer whose
        idea had a Telugu title could not graduate it at all.

        Asserting SUCCESS, not merely "not 500": a registered ValueError handler
        turns the failure into a 400, which is exactly why the loose version of
        this test passed against the broken code."""
        monkeypatch.setattr(webapp_server.Orchestrator, "run_parse", lambda self: None)
        idea = http_client.post("/api/ideas", json={"title": "Telugu idea"}).get_json()["id"]
        script = (
            "Title: Pages\nAuthor: Test\n\n"
            "INT. ROOM - DAY\n\nSomeone waits by the window.\n"
        ).encode("utf-8")

        resp = http_client.post(
            f"/api/ideas/{idea}/graduate",
            data={"title": "తెలుగు కథ", "file": (io.BytesIO(script), "pages.txt")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)
        project = resp.get_json()["project"]
        assert os.path.isdir(os.path.join(webapp_server.PROJECTS_DIR, project))

    def test_the_ascii_fold_is_what_the_route_uses(self):
        """The route must not reintroduce a Unicode-aware per-char sanitizer:
        that is the H2 shape, and it only fails on non-ASCII titles."""
        src = inspect.getsource(webapp_server.graduate_idea)
        assert "safe_dir_name(" in src
        assert 'isalnum() or c in "-_"' not in src


# --------------------------------------------------------------------------- L6
class TestCliPrintsTheStageTableOnTheFailurePath:
    def _failing_orchestrator(self, monkeypatch):
        class _FailingOrchestrator(cli.Orchestrator):
            def run_parse(self):
                raise cli.OrchestratorError("model server is down")

        monkeypatch.setattr(cli, "Orchestrator", _FailingOrchestrator)

    def _manifest(self, tmp_path):
        src = tmp_path / "pages.txt"
        src.write_text("INT. ROOM - DAY\n\nSomeone waits.\n", encoding="utf-8")
        project = str(tmp_path / "proj")
        ProjectManifest.create(project, str(src), title="T").save()
        return project

    def test_cmd_run_shows_which_stage_failed(self, tmp_path, monkeypatch, capsys):
        """The status block is the only place that names the failing stage. It
        sat AFTER the try, so `sys.exit(1)` skipped it — the writer got
        "ERROR: ..." and then nothing about the state they were left in."""
        project = self._manifest(tmp_path)
        self._failing_orchestrator(monkeypatch)
        args = SimpleNamespace(
            project=project, source=None, title=None, server=None, model=None,
            categories=None, only="parse", lang=None, retry_failed=False,
            skip_chat=True,
        )

        with pytest.raises(SystemExit):
            cli.cmd_run(args)

        out = capsys.readouterr().out
        assert "Project:" in out, "the stage table was skipped on the failure path"
        assert "parse" in out

    def test_cmd_resume_shows_which_stage_failed(self, tmp_path, monkeypatch, capsys):
        project = self._manifest(tmp_path)
        self._failing_orchestrator(monkeypatch)
        args = SimpleNamespace(
            project=project, server=None, model=None, lang=None,
            retry_failed=False, skip_chat=True,
        )

        with pytest.raises(SystemExit):
            cli.cmd_resume(args)

        assert "Project:" in capsys.readouterr().out


# --------------------------------------------------------------------------- L7
class TestReportRendererBoldSpans:
    def test_every_bold_span_renders(self):
        html = webapp_server._md_to_html("**one** and **two** and **three**")
        assert html.count("<strong>") == 3
        assert html.count("</strong>") == 3

    def test_a_lone_bold_span_renders(self):
        assert "<strong>one</strong>" in webapp_server._md_to_html("**one** span")

    def test_bold_and_italic_together(self):
        html = webapp_server._md_to_html("**a** plain *i*")
        assert "<strong>a</strong>" in html
        assert "<em>i</em>" in html

    def test_unbalanced_markers_are_left_alone(self):
        assert "<strong>" not in webapp_server._md_to_html("a ** stray")

    def test_the_dead_one_span_replace_is_gone(self):
        """It ran on every line of every report, and the regex on the very next
        line already converted every span including the first (L7)."""
        src = inspect.getsource(webapp_server._md_to_html)
        assert 'replace("**", "<strong>", 1)' not in src
