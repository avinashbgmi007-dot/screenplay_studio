"""
CLI for screenplay_studio.

Usage:
    # full pipeline: parse -> analyze -> drop into chat REPL
    python -m screenplay_studio run my_script.fdx --project my_project --server http://localhost:8080

    # only parse + analyze, skip the interactive chat handoff
    python -m screenplay_studio run my_script.fdx --project my_project --skip-chat

    # just one stage
    python -m screenplay_studio run my_script.fdx --project my_project --only parse

    # resume a project — reruns only stages that aren't already complete
    python -m screenplay_studio resume my_project --server http://localhost:8080

    # check where a project stands
    python -m screenplay_studio status my_project
"""

import argparse
import json
import os
import sys

from .manifest import ProjectManifest
from .orchestrator import Orchestrator, OrchestratorError


def _load_project(project_dir: str, command: str) -> ProjectManifest:
    """Load a project, or explain the one thing the writer can act on.

    Gap 110, measured: a project whose `project.json` is missing a field exited
    `status` with a raw `KeyError: 'project_dir'` traceback, and a directory with
    no manifest at all did the same with `FileNotFoundError`. Both are the
    writer's one-line problem — "this is not a project" / "this project file is
    broken" — so both get one line and exit 2, the conventional CLI usage error.
    """
    try:
        return ProjectManifest.load(project_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print(f"  '{project_dir}' is not a project. Point {command} at the "
              "directory that holds project.json.", file=sys.stderr)
        sys.exit(2)
    except (KeyError, ValueError, TypeError) as e:
        print(f"ERROR: the project file at '{project_dir}' is unreadable ({e}).",
              file=sys.stderr)
        print("  The file is present but incomplete or corrupt. Restoring "
              "project.json from a backup is the only safe repair; re-running "
              "the pipeline would overwrite the record of what was done.",
              file=sys.stderr)
        sys.exit(2)


def _resolve_memory(args):
    """The writer profile terminal Sameer should use, and the line to say about it.

    Defaulted ON (review section 7, P2.11). The webapp already wires memory by
    default; the terminal handoff did not, and had no flag to change that — so a
    month of learning was invisible in every terminal session. `--no-memory` is
    the explicit opt-out, and the chosen path is PRINTED: a profile of the writer
    is kept on their disk, so where it lives is something they are told rather
    than left to discover.

    Returns (memory_or_None, notice_line). Never raises for a bad profile: a CLI
    must not die because a file is unreadable, and it must not silently forget
    either — so it degrades to a memoryless session and says so.
    """
    from screenplay_cowriter.memory import WriterMemory, default_memory_path

    if getattr(args, "no_memory", False):
        return None, "Writer memory: off (--no-memory)."

    path = getattr(args, "memory_path", None) or default_memory_path()
    try:
        return WriterMemory.load(path), f"Writer memory: {path}  (--no-memory to opt out)"
    except OSError as e:
        return None, (f"Writer memory: unavailable at {path} ({e}) — "
                      f"continuing without it.")


def _run_chat_repl(session, engine, store, memory=None):
    """Hands off to the same interactive loop Piece 3's own CLI uses."""
    from screenplay_cowriter.cli import run_repl
    run_repl(session, store, engine.client, memory=memory)


def cmd_run(args):
    try:
        manifest = ProjectManifest.load(args.project)
        print(f"Resuming existing project at '{args.project}'.")
    except (KeyError, ValueError, TypeError) as e:
        # present but broken: `run` used to fall through to "looks like a new
        # project" for ANY load failure, so a corrupt manifest was silently
        # replaced by a fresh one — losing the record instead of reporting it.
        print(f"ERROR: the project file at '{args.project}' is unreadable ({e}).",
              file=sys.stderr)
        sys.exit(2)
    except FileNotFoundError:
        if not args.source:
            print("ERROR: new project needs a source file argument.", file=sys.stderr)
            sys.exit(1)
        try:
            manifest = ProjectManifest.create(args.project, args.source, title=args.title)
        except FileNotFoundError as e:
            # Gap 110: one actionable line, not a traceback through shutil.
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(2)
        except (OSError, ValueError) as e:
            print(f"ERROR: could not create a project at '{args.project}': {e}",
                  file=sys.stderr)
            sys.exit(2)
        print(f"Created new project at '{args.project}'.")

    if args.server:
        manifest.server_url = args.server
    if args.model:
        manifest.model_id = args.model
    manifest.save()

    # Gap 7 / gap 65: a CLI run is the second process in the filed evidence. It
    # takes the project's run lock before the orchestrator does anything, so it
    # cannot start alongside a web-UI analysis of the same project, and neither
    # can start alongside it. The lock is an OS file lock, so a crashed run
    # releases it; a refusal is exit 1 with a reason rather than a silent
    # second run.
    from .jsonio import run_lock
    # `args.project`, not `manifest.project_dir`: those are the same string on a
    # normal run, but the lock has to be named by the thing every other process
    # is given — the directory the user passed — so a relative path from one
    # shell and an absolute path from another still name ONE lock. That is the
    # filing error this whole gap is about, one level down.
    run_claim = run_lock(os.path.abspath(args.project))
    if not run_claim.try_acquire():
        print("Another analysis is already running for this project (in "
              "another process). Wait for it to finish before starting "
              "another.", file=sys.stderr)
        return 1
    try:
        return _run_stages(args, manifest, orch_unused=None)
    finally:
        run_claim.release()


def _run_stages(args, manifest, orch_unused=None):
    orch = Orchestrator(manifest)
    categories = tuple(args.categories.split(",")) if args.categories else None

    # P2.11: terminal Sameer remembers by default now. Resolved here — a load is
    # read-only, nothing is written until a turn is observed — but ANNOUNCED only
    # when a chat will actually run, so `--only analyze` stays quiet.
    memory, memory_note = _resolve_memory(args)
    if args.only == "chat" or (args.only is None and not args.skip_chat):
        print(memory_note)

    try:
        if args.only == "parse":
            orch.run_parse()
            print("Parse stage complete.")
        elif args.only == "analyze":
            orch.run_analyze(categories=categories, report_language=args.lang, retry_failed=args.retry_failed)
            print("Analyze stage complete.")
        elif args.only == "chat":
            session, engine, store = orch.start_chat()
            _run_chat_repl(session, engine, store, memory=memory)
        else:
            orch.run_parse()
            print("Parse stage complete.")
            orch.run_analyze(categories=categories, report_language=args.lang, retry_failed=args.retry_failed)
            print("Analyze stage complete.")
            if not args.skip_chat:
                session, engine, store = orch.start_chat()
                _run_chat_repl(session, engine, store, memory=memory)
    except OrchestratorError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print(f"Project state saved at '{args.project}' — fix the issue and rerun to resume from here.", file=sys.stderr)
        sys.exit(1)
    finally:
        # L6: this block is the only place that names WHICH stage failed and with
        # what error, so it has to print on the failure path too. It used to sit
        # after the try, which the `sys.exit` above skipped — the writer saw
        # "ERROR: ..." and then nothing at all about the state they were left in.
        _print_status(manifest)


def cmd_resume(args):
    manifest = _load_project(args.project, "resume")
    if args.server:
        manifest.server_url = args.server
    if args.model:
        manifest.model_id = args.model
    manifest.save()

    orch = Orchestrator(manifest)
    # P2.11: same default as cmd_run — resume -> chat is the same terminal Sameer.
    memory, memory_note = _resolve_memory(args)
    try:
        orch.run_parse()
        orch.run_analyze(report_language=args.lang, retry_failed=args.retry_failed)
        if not args.skip_chat:
            print(memory_note)
            session, engine, store = orch.start_chat()
            _run_chat_repl(session, engine, store, memory=memory)
    except OrchestratorError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # L6: same as cmd_run — the stage table has to survive the error path.
        _print_status(manifest)


def cmd_status(args):
    manifest = _load_project(args.project, "status")
    _print_status(manifest)


def _print_status(manifest: ProjectManifest):
    print(f"\nProject: {manifest.title} ({manifest.project_dir})")
    for name in ("parse", "analyze", "chat"):
        stage = manifest.stage(name)
        line = f"  {name:10s} {stage.status}"
        if stage.error:
            line += f" — {stage.error}"
        print(line)


def _add_memory_args(parser):
    """The two memory flags `run` and `resume` both take (P2.11).

    Memory is ON by default here, matching the webapp — the flag that exists is
    the OPT-OUT, not the opt-in. The default path is named in the help text so
    `--help` alone tells the writer where their profile will be kept.
    """
    from screenplay_cowriter.memory import default_memory_path
    parser.add_argument(
        "--memory-path", default=None,
        help=("Writer relationship memory file. Default: "
              f"{default_memory_path()} (writer-level, follows you across projects)"))
    parser.add_argument(
        "--no-memory", action="store_true",
        help="Don't load or save writer memory this run (Sameer starts cold)")


def main():
    # Gap 85: the help said nothing about the desk at all — not its port, not
    # that it binds loopback, not that it wants a token. A writer who runs
    # `--help` looking for "how do I open the app" got four pipeline commands and
    # silence. The default is READ from `webapp_server`, never restated here, so
    # this sentence cannot drift from the code it describes.
    from .webapp_server import DEFAULT_BIND, DEFAULT_PORT
    parser = argparse.ArgumentParser(
        prog="screenplay_studio",
        epilog=(f"The desk (browser UI) is not a subcommand — run "
                f"`python -m screenplay_studio.webapp_server [--port {DEFAULT_PORT}]`. "
                f"It serves the API and the SPA from ONE process, binds "
                f"{DEFAULT_BIND} only, and requires a per-process capability token "
                f"(mint-on-launch; pass --no-token only for scripted clients)."),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run (or resume) a project's pipeline")
    # Gap 111: `run` was the only command whose project came from `--project`,
    # while `resume` and `status` took it positionally — so the obvious
    # `run myproject/` was read as a SOURCE file and died on a traceback. Accept
    # both; `--project` wins when both are given, and `source` stays optional
    # because a project that already exists does not need one.
    p_run.add_argument("project_pos", nargs="?", metavar="PROJECT",
                       help="Project directory (same as --project)")
    p_run.add_argument("source", nargs="?", help="Source screenplay file (only needed for a new project)")
    p_run.add_argument("--project", dest="project_opt", help="Project directory")
    p_run.add_argument("--title", help="Project title (defaults to source filename)")
    p_run.add_argument("--server", help="llama-server base URL")
    p_run.add_argument("--model", help="Explicit model id override")
    p_run.add_argument("--categories", help="Comma-separated analyzer categories to run")
    p_run.add_argument("--only", choices=["parse", "analyze", "chat"], help="Run only one stage")
    p_run.add_argument("--skip-chat", action="store_true", help="Don't hand off to interactive chat after analyze")
    p_run.add_argument("--retry-failed", action="store_true",
                      help="Re-run only the categories that failed in the last analyze (merges into the existing report; takes precedence over --categories)")
    p_run.add_argument("--lang", choices=["eng", "tenglish", "hindi", "tamil"], default="eng",
                      help="Language of the analysis report (eng, tenglish, hindi, tamil)")
    _add_memory_args(p_run)
    p_run.set_defaults(func=cmd_run)

    p_resume = sub.add_parser("resume", help="Resume an existing project — only reruns incomplete stages")
    p_resume.add_argument("project", help="Project directory")
    p_resume.add_argument("--server", help="llama-server base URL override")
    p_resume.add_argument("--model", help="Explicit model id override")
    p_resume.add_argument("--skip-chat", action="store_true")
    p_resume.add_argument("--retry-failed", action="store_true",
                      help="Re-run only the categories that failed in the last analyze (merges into the existing report)")
    p_resume.add_argument("--lang", choices=["eng", "tenglish", "hindi", "tamil"], default="eng",
                      help="Language of the analysis report (eng, tenglish, hindi, tamil)")
    _add_memory_args(p_resume)
    p_resume.set_defaults(func=cmd_resume)

    p_status = sub.add_parser("status", help="Show a project's stage status")
    p_status.add_argument("project", help="Project directory")
    p_status.set_defaults(func=cmd_status)

    p_watch = sub.add_parser("watch", help="Auto-analyze screenplays dropped into a folder")
    p_watch.add_argument("watch_dir", help="Folder to watch for new screenplays")
    p_watch.add_argument("--projects-dir", default="./watched_projects", help="Where to create projects")
    p_watch.add_argument("--server", default="http://localhost:8080", help="llama-server base URL")
    p_watch.add_argument("--model", help="Explicit model id override")
    p_watch.add_argument("--poll", type=int, default=5, help="Seconds between scans (default 5)")
    p_watch.add_argument("--once", action="store_true", help="Process whatever's there once and exit (no loop)")
    p_watch.add_argument("--json", action="store_true",
                         help="With --once, also print a machine-readable per-file summary to stdout")
    p_watch.add_argument("--categories", help="Comma-separated analyzer categories to run")
    p_watch.add_argument("--lang", choices=["eng", "tenglish", "hindi", "tamil"], default="eng",
                      help="Language of the analysis report (eng, tenglish, hindi, tamil)")
    p_watch.set_defaults(func=cmd_watch)

    args = parser.parse_args()
    if args.command == "run":
        _resolve_run_paths(parser, args)
    # Gap 7 caught this on the way past. Every command's handler RETURNS its
    # exit status (`cmd_watch` returns WATCH_EXIT_ERROR, `cmd_run` returns 1 when
    # another process holds the run), and this line threw the value away — so
    # `sys.exit()` at interpreter exit used 0 and a failed command reported
    # success. That is gap 39's bug class (a failure that exits 0) surviving in
    # the dispatcher that gap 39 never looked at, because gap 39's fix went into
    # `cmd_watch`'s own return path.
    code = args.func(args)
    if isinstance(code, int) and code != 0:
        sys.exit(code)


def _resolve_run_paths(parser, args) -> None:
    """Turn the two accepted spellings of `run`'s arguments into one meaning.

    Rules, in order: `--project` wins; otherwise a first positional is the
    project. If only one path is given and it is a FILE, it is the source and the
    project defaults to the directory named after it (what `run script.fountain`
    has always meant). If it is a DIRECTORY, it is the project.
    """
    project = getattr(args, "project_opt", None)
    first = getattr(args, "project_pos", None)
    source = args.source

    if project and first:
        # `run --project P src.fountain` — one positional, so it is the source.
        args.source = first if source is None else source
    elif not project and first:
        if os.path.isdir(first):
            project = first
        elif os.path.isfile(first):
            # a source file: the project is its stem, as `run SRC` always meant
            source = source or first
            project = os.path.splitext(first)[0]
        else:
            parser.error(f"'{first}' is neither a project directory nor a source file")

    if not project:
        parser.error("run needs a project directory: `run PROJECT` or "
                     "`run --project PROJECT [SOURCE]`")
    args.project = project


# Exit codes for `watch --once`, documented because automation reads them.
#
# Gap 39, measured: a batch in which EVERY file failed printed `FAILED` and
# exited 0, so a CI job or a Makefile saw a failed import as success. The
# register asked for defined semantics rather than a bare nonzero, so:
#
#   0  every requested file was processed successfully
#   1  the batch ran but at least one file failed (partial failure)
#   2  usage / configuration error (argparse, bad directory) — the CLI's
#      existing convention, see `_load_project`
#
# Partial failure is 1, not 2: 2 already means "you asked wrongly" everywhere
# else in this CLI, and a script that retries on 1 should not also retry on a
# typo. A failure to list the directory at all is 2: nothing was requested of
# any file, so no file's outcome can be reported.
WATCH_EXIT_OK = 0
WATCH_EXIT_PARTIAL = 1
WATCH_EXIT_ERROR = 2


def watch_exit_code(results: list) -> int:
    """The exit code for a completed `watch --once` batch.

    Empty batch is success: `watch --once` on an empty inbox is cron's normal
    case, not an error.
    """
    if not results:
        return WATCH_EXIT_OK
    if any(not r.get("ok") for r in results):
        return WATCH_EXIT_PARTIAL
    return WATCH_EXIT_OK


def cmd_watch(args):
    from .watch import process_pending, watch_loop
    categories = tuple(args.categories.split(",")) if args.categories else None
    if args.once:
        try:
            results = process_pending(args.watch_dir, args.projects_dir, args.server, model=args.model,
                                      categories=categories, report_language=args.lang)
        except OSError as e:
            # Nothing was requested of any file, so this is a configuration
            # error, not a per-file outcome.
            print(f"ERROR: cannot read the watch folder '{args.watch_dir}': {e}", file=sys.stderr)
            sys.exit(WATCH_EXIT_ERROR)
        for r in results:
            status = "OK" if r.get("ok") else "FAILED"
            print(f"{status}: {r['filename']} → {r.get('project') or r.get('error')}")
        if getattr(args, "json", False):
            # Machine-readable per-file outcomes, asked for by the register so
            # an automation consumer never has to parse the prose above.
            print(json.dumps({
                "ok": watch_exit_code(results) == WATCH_EXIT_OK,
                "total": len(results),
                "succeeded": sum(1 for r in results if r.get("ok")),
                "failed": sum(1 for r in results if not r.get("ok")),
                "results": [
                    {"filename": r.get("filename"), "ok": bool(r.get("ok")),
                     "project": r.get("project"), "error": r.get("error")}
                    for r in results
                ],
            }))
        code = watch_exit_code(results)
        if code == WATCH_EXIT_PARTIAL:
            failed = sum(1 for r in results if not r.get("ok"))
            # A non-zero exit with no explanation in the stream is its own trap.
            print(f"FAILED {failed} of {len(results)} file(s); see above.",
                  file=sys.stderr)
        sys.exit(code)
    watch_loop(args.watch_dir, args.projects_dir, args.server,
               poll_interval=args.poll, model=args.model, categories=categories, report_language=args.lang)


if __name__ == "__main__":
    main()
