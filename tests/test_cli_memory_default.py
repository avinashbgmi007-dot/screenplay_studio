"""Terminal Sameer remembers by default (review section 7, P2.11).

The status board filed this as "no `--memory-path` exists in `cli.py` or
`orchestrator.py` at all". That is true of `screenplay_studio/cli.py` and
misleading about the product: `screenplay_cowriter/cli.py:227` HAS the flag, and
the webapp wires memory by default at `PROJECTS_DIR/writer_profile.json`.

The real defect is narrower and worse: `screenplay_studio/cli.py:_run_chat_repl`
called `run_repl(session, store, engine.client)` with NO `memory` argument and
there was no flag on `run`/`resume` to supply one. So the analyzer CLI's chat
handoff — the path a writer reaches by running the pipeline and staying for the
conversation — was amnesiac in every session, always. The desk remembered; the
terminal did not.

Fixed the way H1 was: default ON, an explicit opt-out (`--no-memory`), and the
chosen path is PRINTED, because a profile of the writer now lives on their disk
by default and where it lives is something they are told, not left to discover.
"""

import argparse
import io
import os

import pytest

from screenplay_studio import cli


# --------------------------------------------------------------------------
# the default location
# --------------------------------------------------------------------------

class TestTheDefaultPath:
    def test_it_is_absolute_and_under_the_users_home(self):
        from screenplay_cowriter.memory import default_memory_path
        p = default_memory_path()
        assert os.path.isabs(p), p
        assert p.startswith(os.path.expanduser("~")), p

    def test_it_is_named_predictably(self):
        """A path the writer can guess is a path they can read, move or delete."""
        from screenplay_cowriter.memory import (
            default_memory_path, MEMORY_DIR_NAME, MEMORY_FILE_NAME,
        )
        p = default_memory_path()
        assert os.path.basename(p) == MEMORY_FILE_NAME
        assert MEMORY_DIR_NAME in p

    def test_it_is_not_a_project_directory(self):
        """Writer-level, not project-level: the profile's whole purpose is to
        follow the writer across projects, so it must not live inside one."""
        from screenplay_cowriter.memory import default_memory_path
        p = default_memory_path()
        assert "studio_projects" not in p.replace("\\", "/")


# --------------------------------------------------------------------------
# resolution
# --------------------------------------------------------------------------

def _args(**kw):
    base = {"memory_path": None, "no_memory": False}
    base.update(kw)
    return argparse.Namespace(**base)


class TestResolvingTheMemory:
    def test_the_opt_out_wins_and_says_so(self):
        memory, note = cli._resolve_memory(_args(no_memory=True, memory_path="/tmp/x.json"))
        assert memory is None
        assert "--no-memory" in note

    def test_an_explicit_path_is_used(self, tmp_path):
        target = str(tmp_path / "custom.json")
        memory, note = cli._resolve_memory(_args(memory_path=target))
        assert memory is not None and memory.path == target
        assert target in note

    def test_nothing_given_falls_back_to_the_default(self, monkeypatch, tmp_path):
        from screenplay_cowriter import memory as mem_mod
        target = str(tmp_path / "writer_profile.json")
        monkeypatch.setattr(mem_mod, "default_memory_path", lambda: target)
        memory, note = cli._resolve_memory(_args())
        assert memory is not None and memory.path == target
        assert target in note

    def test_the_notice_names_the_opt_out(self, tmp_path):
        """Disclosure: the writer is told how to turn it off in the same line."""
        _, note = cli._resolve_memory(_args(memory_path=str(tmp_path / "m.json")))
        assert "--no-memory" in note

    def test_an_unreadable_profile_degrades_instead_of_crashing(self, tmp_path):
        """A CLI must not die because a profile file is bad — and it must not
        silently forget either. It continues memoryless and SAYS so."""
        bad = tmp_path / "a_directory.json"
        bad.mkdir()  # opening a directory raises OSError
        memory, note = cli._resolve_memory(_args(memory_path=str(bad)))
        assert memory is None
        assert "unavailable" in note and str(bad) in note


# --------------------------------------------------------------------------
# the handoff actually carries it
# --------------------------------------------------------------------------

class _Engine:
    client = "client"


class TestTheHandoffCarriesIt:
    def test_run_chat_repl_passes_memory_through(self, monkeypatch):
        """The original bug in one assertion: the call omitted `memory`, so the
        profile was loaded and then dropped on the floor."""
        seen = {}

        def fake_run_repl(session, store, client, memory=None):
            seen["memory"] = memory

        import screenplay_cowriter.cli as cowriter_cli
        monkeypatch.setattr(cowriter_cli, "run_repl", fake_run_repl)

        sentinel = object()
        cli._run_chat_repl("s", _Engine(), "st", memory=sentinel)
        assert seen["memory"] is sentinel, "the chat handoff dropped the memory object"

    def test_it_still_works_with_no_memory(self, monkeypatch):
        seen = {}

        def fake_run_repl(session, store, client, memory=None):
            seen["memory"] = memory

        import screenplay_cowriter.cli as cowriter_cli
        monkeypatch.setattr(cowriter_cli, "run_repl", fake_run_repl)
        cli._run_chat_repl("s", _Engine(), "st")
        assert seen["memory"] is None


# --------------------------------------------------------------------------
# the flags exist on both subcommands
# --------------------------------------------------------------------------

class TestTheFlagsExist:
    def _parsers(self):
        """Build the real parser by intercepting argparse, so the test cannot
        drift from `main()`'s actual wiring."""
        captured = {}
        real = argparse.ArgumentParser.parse_args

        def spy(self, *a, **kw):
            captured["parser"] = self
            raise SystemExit(0)

        import sys
        old_argv = sys.argv
        sys.argv = ["screenplay_studio", "run", "--project", "x", "--skip-chat"]
        argparse.ArgumentParser.parse_args = spy
        try:
            with pytest.raises(SystemExit):
                cli.main()
        finally:
            argparse.ArgumentParser.parse_args = real
            sys.argv = old_argv

        parser = captured["parser"]
        subs = {a.dest: a for a in parser._actions if isinstance(a, argparse._SubParsersAction)}
        sub = subs["command"]
        return {name: p for name, p in sub.choices.items()}

    def test_both_run_and_resume_take_the_memory_flags(self):
        parsers = self._parsers()
        for name in ("run", "resume"):
            opts = {o for a in parsers[name]._actions for o in a.option_strings}
            assert "--memory-path" in opts, f"{name} lost --memory-path"
            assert "--no-memory" in opts, f"{name} lost --no-memory"

    def test_the_help_text_names_the_default_and_the_opt_out(self):
        parsers = self._parsers()
        help_text = " ".join(
            (a.help or "") for a in parsers["run"]._actions
        )
        assert "writer_profile.json" in help_text, "the default path is not discoverable"
        assert "starts cold" in help_text or "Don't load" in help_text


# --------------------------------------------------------------------------
# the CLI announces it, and only when a chat will run
# --------------------------------------------------------------------------

class _Stage:
    status = "complete"
    error = None


class _Manifest:
    title = "T"
    project_dir = "P"
    server_url = None
    model_id = None

    def save(self):
        pass

    def stage(self, name):
        return _Stage()


class _Orch:
    def __init__(self, manifest):
        self.manifest = manifest
        self.client = None
        self.chat_started = False

    def run_parse(self):
        pass

    def run_analyze(self, **kw):
        pass

    def start_chat(self):
        self.chat_started = True
        return ("session", self, "store")


@pytest.fixture
def cli_env(monkeypatch, tmp_path):
    """Everything heavy stubbed; the real parser and the real `_resolve_memory`."""
    import screenplay_cowriter.cli as cowriter_cli

    monkeypatch.setattr(cli.ProjectManifest, "load", classmethod(lambda cls, p: _Manifest()))
    monkeypatch.setattr(cli.ProjectManifest, "create", classmethod(lambda cls, *a, **k: _Manifest()))
    monkeypatch.setattr(cli, "Orchestrator", _Orch)
    monkeypatch.setattr(cli, "_print_status", lambda m: None)
    monkeypatch.setattr(cowriter_cli, "run_repl",
                        lambda session, store, client, memory=None: None)
    return tmp_path


def _run_cli(monkeypatch, argv, capsys):
    import sys
    old = sys.argv
    sys.argv = ["screenplay_studio"] + argv
    try:
        cli.main()
    finally:
        sys.argv = old
    return capsys.readouterr().out


class TestTheCliAnnouncesIt:
    def test_the_path_is_printed_when_a_chat_will_run(self, cli_env, monkeypatch, capsys):
        out = _run_cli(monkeypatch, [
            "run", "--project", "x", "--only", "chat",
            "--memory-path", str(cli_env / "m.json"),
        ], capsys)
        assert "Writer memory:" in out
        assert str(cli_env / "m.json") in out

    def test_the_opt_out_is_honoured_end_to_end(self, cli_env, monkeypatch, capsys):
        out = _run_cli(monkeypatch, [
            "run", "--project", "x", "--only", "chat", "--no-memory",
        ], capsys)
        assert "off" in out and "--no-memory" in out

    def test_an_analyze_only_run_stays_quiet(self, cli_env, monkeypatch, capsys):
        """No chat, no memory line — otherwise the notice is noise on a
        non-interactive run that never touches the profile."""
        out = _run_cli(monkeypatch, [
            "run", "--project", "x", "--only", "analyze",
        ], capsys)
        assert "Writer memory:" not in out

    def test_skip_chat_stays_quiet(self, cli_env, monkeypatch, capsys):
        out = _run_cli(monkeypatch, [
            "run", "--project", "x", "--skip-chat",
        ], capsys)
        assert "Writer memory:" not in out


# --------------------------------------------------------------------------
# the webapp default is untouched
# --------------------------------------------------------------------------

class TestTheWebappDefaultIsUnchanged:
    def test_it_still_uses_a_project_level_profile(self):
        """P2.11 is about the TERMINAL. The webapp already wired memory and its
        path is project-scoped — changing it would silently orphan every existing
        profile."""
        import screenplay_studio.webapp_server as ws
        src = io.open(ws.__file__, encoding="utf-8").read()
        assert 'WriterMemory.load(os.path.join(PROJECTS_DIR, "writer_profile.json"))' in src
