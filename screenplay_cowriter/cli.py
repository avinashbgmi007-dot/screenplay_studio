"""
CLI for Piece 3 (Co-writer).

Usage:
    # start a new session from a Piece 2 report (recommended — full context)
    python -m screenplay_cowriter chat --new "My Script" --report script.report.findings.json --script script.json

    # start a new session from just the raw script (no report yet, or skipping Piece 2)
    python -m screenplay_cowriter chat --new "My Script" --script script.json

    # resume an existing session (memory persists across runs)
    python -m screenplay_cowriter chat --resume <session_id>

    # list saved sessions
    python -m screenplay_cowriter list

In-chat slash commands:
    /fork <name>        branch off from here into a new named thread
    /switch <name>       jump to another branch
    /branches            list branches on this session
    /persona <name>       switch reader persona (script_consultant, producer, dev_exec,
                          teacher, audience, genre_specialist)
    /mode <name>          switch mode (evidence_discussion, brainstorm, character_interview)
    /history [n]          show the last n messages on the current branch (default 10)
    /delete <branch>       discard a branch (can't delete main)
    /help                 show this list
    /quit                 exit (session is already saved after every turn)
"""

import argparse
import sys

from .models import Session
from .store import SessionStore
from .llm_client import LlamaServerClient, LlamaServerError
from .context import ScriptContext, ReportContext, load_json
from .discovery import resolve_model
from .engine import CoWriterEngine
from .personas import PERSONAS, MODES


HELP_TEXT = __doc__.split("In-chat slash commands:")[1]


def _print_help():
    print("In-chat slash commands:" + HELP_TEXT)


def _load_contexts(session: Session):
    script_data = load_json(session.script_path) if session.script_path else {}
    report_data = load_json(session.report_path) if session.report_path else {}
    return ScriptContext(script_data), ReportContext(report_data)


def run_repl(session: Session, store: SessionStore, client: LlamaServerClient, memory=None):
    script_ctx, report_ctx = _load_contexts(session)
    engine = CoWriterEngine(client, script_ctx, report_ctx, store=store, memory=memory)

    print(f"\n[session {session.session_id}] \"{session.title}\" — branch: {session.current_branch}")
    print(f"Model: {session.model_id} @ {session.server_url}")
    print("Type /help for commands, /quit to exit.\n")

    while True:
        try:
            user_input = input(f"({session.current_branch}) > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession saved. Bye.")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            if _handle_command(user_input, session, store):
                break
            continue

        try:
            reply = engine.send_message(session, user_input)
            print(f"\n{reply}\n")
        except LlamaServerError as e:
            print(f"\n[error] {e}\n")
            continue  # don't save a broken turn, but keep the session alive

        store.save(session)


def _handle_command(cmd: str, session: Session, store: SessionStore) -> bool:
    """Returns True if the REPL should exit."""
    parts = cmd[1:].split(maxsplit=1)
    name = parts[0].lower() if parts else ""
    arg = parts[1].strip() if len(parts) > 1 else ""

    if name in ("quit", "exit"):
        print("Session saved. Bye.")
        return True

    elif name == "help":
        _print_help()

    elif name == "fork":
        if not arg:
            print("Usage: /fork <new_branch_name>")
        else:
            try:
                session.fork(arg)
                store.save(session)
                print(f"Forked into new branch '{arg}' from '{session.branches[arg].parent_branch}'. Now on '{arg}'.")
            except ValueError as e:
                print(f"[error] {e}")

    elif name == "switch":
        if not arg:
            print("Usage: /switch <branch_name>")
        else:
            try:
                session.switch(arg)
                store.save(session)
                print(f"Switched to branch '{arg}'.")
            except ValueError as e:
                print(f"[error] {e}")

    elif name == "branches":
        for bname, b in session.branches.items():
            marker = "*" if bname == session.current_branch else " "
            parent = f" (forked from {b.parent_branch})" if b.parent_branch else ""
            print(f" {marker} {bname} — {len(b.messages)} messages{parent}")

    elif name == "delete":
        if not arg:
            print("Usage: /delete <branch_name>")
        else:
            try:
                session.delete_branch(arg)
                store.save(session)
                print(f"Deleted branch '{arg}'.")
            except ValueError as e:
                print(f"[error] {e}")

    elif name == "persona":
        if not arg:
            print(f"Current: {session.branch.active_persona}. Available: {list(PERSONAS.keys())}")
        elif arg not in PERSONAS:
            print(f"[error] Unknown persona '{arg}'. Available: {list(PERSONAS.keys())}")
        else:
            session.branch.active_persona = arg
            store.save(session)
            print(f"Persona set to '{arg}' for branch '{session.current_branch}'.")

    elif name == "mode":
        if not arg:
            print(f"Current: {session.branch.active_mode}. Available: {list(MODES.keys())}")
        elif arg not in MODES:
            print(f"[error] Unknown mode '{arg}'. Available: {list(MODES.keys())}")
        else:
            session.branch.active_mode = arg
            store.save(session)
            print(f"Mode set to '{arg}' for branch '{session.current_branch}'.")

    elif name == "history":
        n = int(arg) if arg.isdigit() else 10
        for m in session.branch.messages[-n:]:
            print(f"[{m.role}] {m.content[:200]}")

    else:
        print(f"Unknown command '/{name}'. Type /help.")

    return False


def cmd_chat(args):
    store = SessionStore(args.sessions_dir)

    if args.resume:
        session = store.load(args.resume)
    elif args.new:
        session = store.create(title=args.new, report_path=args.report, script_path=args.script)
        session.server_url = args.server
    else:
        print("ERROR: specify --new <title> or --resume <session_id>", file=sys.stderr)
        sys.exit(1)

    server_url = args.server or session.server_url or "http://localhost:8080"
    client = LlamaServerClient(base_url=server_url, model=args.model)

    _, report_ctx = _load_contexts(session)
    try:
        model_id = resolve_model(client, report_ctx, explicit_model=args.model)
    except LlamaServerError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    session.server_url = server_url
    session.model_id = model_id
    store.save(session)

    memory = None
    if args.memory_path:
        from .memory import WriterMemory
        memory = WriterMemory.load(args.memory_path)

    run_repl(session, store, client, memory=memory)


def cmd_list(args):
    store = SessionStore(args.sessions_dir)
    sessions = store.list()
    if not sessions:
        print("No saved sessions.")
        return
    for s in sessions:
        print(f"{s['session_id']}  \"{s['title']}\"  branches={s['branches']} (on {s['current_branch']})")


def main():
    parser = argparse.ArgumentParser(prog="screenplay_cowriter")
    sub = parser.add_subparsers(dest="command", required=True)

    p_chat = sub.add_parser("chat", help="Start or resume a co-writer session")
    p_chat.add_argument("--new", help="Title for a new session")
    p_chat.add_argument("--resume", help="Resume an existing session by id")
    p_chat.add_argument("--report", help="Path to Piece 2 findings JSON")
    p_chat.add_argument("--script", help="Path to Piece 1 ScriptDocument JSON")
    p_chat.add_argument("--server", help="llama-server base URL (default: http://localhost:8080)")
    p_chat.add_argument("--model", help="Explicit model id override")
    p_chat.add_argument("--sessions-dir", default="./sessions", help="Where session files live")
    p_chat.add_argument("--memory-path", default=None, help="Optional writer relationship memory file")
    p_chat.set_defaults(func=cmd_chat)

    p_list = sub.add_parser("list", help="List saved sessions")
    p_list.add_argument("--sessions-dir", default="./sessions")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
