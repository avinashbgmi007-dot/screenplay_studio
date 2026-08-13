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
import sys

from .manifest import ProjectManifest
from .orchestrator import Orchestrator, OrchestratorError


def _run_chat_repl(session, engine, store):
    """Hands off to the same interactive loop Piece 3's own CLI uses."""
    from screenplay_cowriter.cli import run_repl
    run_repl(session, store, engine.client)


def cmd_run(args):
    try:
        manifest = ProjectManifest.load(args.project)
        print(f"Resuming existing project at '{args.project}'.")
    except FileNotFoundError:
        if not args.source:
            print("ERROR: new project needs a source file argument.", file=sys.stderr)
            sys.exit(1)
        manifest = ProjectManifest.create(args.project, args.source, title=args.title)
        print(f"Created new project at '{args.project}'.")

    if args.server:
        manifest.server_url = args.server
    if args.model:
        manifest.model_id = args.model
    manifest.save()

    orch = Orchestrator(manifest)
    categories = tuple(args.categories.split(",")) if args.categories else None

    try:
        if args.only == "parse":
            orch.run_parse()
            print("Parse stage complete.")
        elif args.only == "analyze":
            orch.run_analyze(categories=categories, report_language=args.lang, retry_failed=args.retry_failed)
            print("Analyze stage complete.")
        elif args.only == "chat":
            session, engine, store = orch.start_chat()
            _run_chat_repl(session, engine, store)
        else:
            orch.run_parse()
            print("Parse stage complete.")
            orch.run_analyze(categories=categories, report_language=args.lang, retry_failed=args.retry_failed)
            print("Analyze stage complete.")
            if not args.skip_chat:
                session, engine, store = orch.start_chat()
                _run_chat_repl(session, engine, store)
    except OrchestratorError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print(f"Project state saved at '{args.project}' — fix the issue and rerun to resume from here.", file=sys.stderr)
        sys.exit(1)

    _print_status(manifest)


def cmd_resume(args):
    manifest = ProjectManifest.load(args.project)
    if args.server:
        manifest.server_url = args.server
    if args.model:
        manifest.model_id = args.model
    manifest.save()

    orch = Orchestrator(manifest)
    try:
        orch.run_parse()
        orch.run_analyze(report_language=args.lang, retry_failed=args.retry_failed)
        if not args.skip_chat:
            session, engine, store = orch.start_chat()
            _run_chat_repl(session, engine, store)
    except OrchestratorError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    _print_status(manifest)


def cmd_status(args):
    manifest = ProjectManifest.load(args.project)
    _print_status(manifest)


def _print_status(manifest: ProjectManifest):
    print(f"\nProject: {manifest.title} ({manifest.project_dir})")
    for name in ("parse", "analyze", "chat"):
        stage = manifest.stage(name)
        line = f"  {name:10s} {stage.status}"
        if stage.error:
            line += f" — {stage.error}"
        print(line)


def main():
    parser = argparse.ArgumentParser(prog="screenplay_studio")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run (or resume) a project's pipeline")
    p_run.add_argument("source", nargs="?", help="Source screenplay file (only needed for a new project)")
    p_run.add_argument("--project", required=True, help="Project directory")
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
    p_watch.add_argument("--categories", help="Comma-separated analyzer categories to run")
    p_watch.add_argument("--lang", choices=["eng", "tenglish", "hindi", "tamil"], default="eng",
                      help="Language of the analysis report (eng, tenglish, hindi, tamil)")
    p_watch.set_defaults(func=cmd_watch)

    args = parser.parse_args()
    args.func(args)


def cmd_watch(args):
    from .watch import process_pending, watch_loop
    categories = tuple(args.categories.split(",")) if args.categories else None
    if args.once:
        results = process_pending(args.watch_dir, args.projects_dir, args.server, model=args.model,
                                  categories=categories, report_language=args.lang)
        for r in results:
            status = "OK" if r["ok"] else "FAILED"
            print(f"{status}: {r['filename']} → {r['project'] or r['error']}")
        return
    watch_loop(args.watch_dir, args.projects_dir, args.server,
               poll_interval=args.poll, model=args.model, categories=categories, report_language=args.lang)


if __name__ == "__main__":
    main()
