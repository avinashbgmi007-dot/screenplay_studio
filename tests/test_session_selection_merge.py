"""BE-6 — the writer's SELECTION was last-writer-wins.

`SessionStore.save` has merged branch MESSAGES across concurrent turns since H4
(`test_session_lost_update.py`). The selection — `current_branch` and each
branch's `active_persona` / `active_mode` — was not covered by that union. A chat
turn holds a snapshot taken before the writer switched branches, so its save
wrote the OLD branch back and silently undid the switch. Nothing errored, and
nothing was lost; the writer simply found themselves in the wrong room.

The fix keeps the H4 message union and, for a save that is NOT about the
selection, takes those three fields from disk instead. The four routes whose
whole purpose is to change the selection pass `owns_selection=True`.

Two layers are guarded here, because they rot for different reasons:

  * the MECHANISM — a stale message-save preserves disk's selection, an owning
    save applies its own, and the message union still happens either way.
  * the WIRING — a static check that every function in `webapp_server.py` which
    changes the selection says so. That is what stops a fifth metadata route
    from being added without the flag, which no behavioural test here would
    catch, because the new route would only misbehave under a race.
"""
from __future__ import annotations

import ast
import pathlib

import screenplay_studio.webapp_server as webapp_server
from screenplay_cowriter.models import Message, Session
from screenplay_cowriter.store import SessionStore

# The fields that ARE the writer's selection, and the Session methods that move
# `current_branch`. Kept as module constants so the static check below and the
# prose above cannot drift apart.
_SELECTION_FIELDS = ("current_branch", "active_persona", "active_mode")
_SELECTION_MUTATORS = ("fork", "switch", "checkout")


def _turn(session, text, reply="a reply"):
    session.branch.messages.append(Message(role="user", content=text))
    session.branch.messages.append(Message(role="assistant", content=reply))


def _stale_snapshot(sid):
    """A chat turn's in-memory session as it looked BEFORE another writer moved
    the selection: a fresh object on `main`, holding none of the disk state."""
    s = Session.new("T")
    s.session_id = sid
    return s


# ---- the mechanism ---------------------------------------------------------

def test_a_message_save_does_not_undo_a_concurrent_branch_switch(tmp_path):
    """The BE-6 case. A switch lands, then a turn that loaded before it saves."""
    store = SessionStore(str(tmp_path))
    sid = store.create("T").session_id

    # The writer switches to a new branch — a selection-owning save.
    owner = store.load(sid)
    owner.fork("alt")
    store.save(owner, owns_selection=True)
    assert store.load(sid).current_branch == "alt"

    # A faster turn lands a message while the stale snapshot is still in flight.
    # This message exists ONLY on disk, which is what makes the union assertion
    # below non-vacuous: the stale session cannot possibly be carrying it in, so
    # it can only reach the final state through the merge.
    faster = store.load(sid)
    faster.branches["main"].messages.append(Message(role="user", content="disk-q"))
    store.save(faster)

    # A chat turn that loaded BEFORE all of that appends its pair and saves.
    stale = _stale_snapshot(sid)
    _turn(stale, "stale-q")
    store.save(stale)  # message-only: must NOT own the selection

    final = store.load(sid)
    assert final.current_branch == "alt", \
        "a chat turn undid the writer's branch switch"

    # The union still ran, and both turns landed where they were composed: the
    # stale snapshot appended to `main`, so `main` is where it belongs. Dumping
    # it into the branch the writer moved to would be the worse failure.
    users = [m.content for m in final.branches["main"].messages]
    assert "disk-q" in users, "the message union regressed while fixing the selection"
    assert "stale-q" in users, "the saving turn's own message went missing"


def test_a_message_save_does_not_undo_a_concurrent_persona_change(tmp_path):
    """Same race, the other two fields. The values differ from `Branch`'s own
    defaults (`writing_partner` / `peer`), so the assertions can actually fail."""
    store = SessionStore(str(tmp_path))
    sid = store.create("T").session_id

    owner = store.load(sid)
    owner.branch.active_persona = "sameer"
    owner.branch.active_mode = "doctor"
    store.save(owner, owns_selection=True)

    stale = _stale_snapshot(sid)
    _turn(stale, "stale-q")
    store.save(stale)

    final = store.load(sid)
    assert final.branch.active_persona == "sameer", \
        "a chat turn reverted the writer's persona"
    assert final.branch.active_mode == "doctor", \
        "a chat turn reverted the writer's mode"


def test_an_owning_save_applies_its_selection_over_newer_disk_state(tmp_path):
    """The positive control, and it is load-bearing: without it the preserve
    path could be implemented as "always take disk's selection" and both tests
    above would still pass, while every switch and settings change silently
    stopped working."""
    store = SessionStore(str(tmp_path))
    sid = store.create("T").session_id

    # Disk moves on to "alt" first.
    newer = store.load(sid)
    newer.fork("alt")
    store.save(newer, owns_selection=True)

    # An owning save from a snapshot still on `main` must win anyway.
    owner = _stale_snapshot(sid)
    owner.branch.active_persona = "sharad"
    store.save(owner, owns_selection=True)

    final = store.load(sid)
    assert final.current_branch == "main", \
        "an owning save must apply its own selection, not disk's"
    assert final.branch.active_persona == "sharad"


def test_a_dangling_disk_branch_pointer_cannot_poison_a_healthy_session(tmp_path):
    """A torn or hand-edited file can name a branch it does not contain.
    Adopting that name would turn a healthy in-memory session into a `KeyError`
    on the next `session.branch` — a 500 on the next turn, caused by a save that
    was only ever meant to append a message."""
    store = SessionStore(str(tmp_path))
    sid = store.create("T").session_id

    corrupt = Session.new("T")
    corrupt.session_id = sid
    corrupt.current_branch = "ghost"  # never added to `.branches`
    corrupt.save(store._path(sid))

    healthy = _stale_snapshot(sid)
    _turn(healthy, "stale-q")
    store.save(healthy)

    final = store.load(sid)
    assert final.current_branch == "main", "a dangling pointer was adopted from disk"
    assert "ghost" not in final.branches
    assert final.branch is not None  # `session.branch` still resolves


# ---- the wiring ------------------------------------------------------------

# Every function in the two packages that BOTH changes the writer's selection and
# saves a session. Keyed by (module, name) because the names repeat across
# modules — `fork_session`, `switch_branch` and `update_settings` each exist in
# both servers.
#
# This set is asserted exactly, so adding a writer means updating it on purpose.
_EXPECTED_WRITERS = {
    ("screenplay_cowriter/cli.py", "_handle_command"),
    ("screenplay_cowriter/server.py", "fork_session"),
    ("screenplay_cowriter/server.py", "switch_branch"),
    ("screenplay_cowriter/server.py", "update_settings"),
    ("screenplay_studio/webapp_server.py", "fork_session"),
    ("screenplay_studio/webapp_server.py", "switch_branch"),
    ("screenplay_studio/webapp_server.py", "update_settings"),
    ("screenplay_studio/webapp_server.py", "idea_update_settings"),
}


def _writers_that_change_the_selection():
    """Map every selection-changing, session-saving function to whether it passes
    `owns_selection=True`."""
    repo = pathlib.Path(webapp_server.__file__).resolve().parents[1]
    found: dict[tuple[str, str], bool] = {}
    for package in ("screenplay_studio", "screenplay_cowriter"):
        for path in sorted((repo / package).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:  # a broken module is a different failure
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                mutates = saves = owns = False
                for sub in ast.walk(node):
                    if (isinstance(sub, ast.Attribute)
                            and isinstance(sub.ctx, ast.Store)
                            and sub.attr in _SELECTION_FIELDS):
                        mutates = True
                    elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                        if sub.func.attr in _SELECTION_MUTATORS:
                            mutates = True
                        if sub.func.attr == "save":
                            saves = True
                            for kw in sub.keywords:
                                if (kw.arg == "owns_selection"
                                        and getattr(kw.value, "value", None) is True):
                                    owns = True
                if mutates and saves:
                    key = (str(path.relative_to(repo)).replace("\\", "/"), node.name)
                    found[key] = owns
    return found


def test_the_cli_selection_commands_survive_a_stale_chat_save(tmp_path):
    """`_handle_command` is a dispatcher holding five selection-owning saves
    (`/fork`, `/switch`, `/delete`, `/persona`, `/mode`) and two message-only ones,
    so the static check below can only prove the flag appears *somewhere* in it.

    Each command is its own save site, so each needs driving. `/fork` and
    `/switch` are covered here; they are the two that move `current_branch`, which
    is the field the audit's race actually corrupted. The first version of this
    test was named for `/switch` and drove only `/fork` — a mutation of the
    `/switch` save left it green, which is how that was found.
    """
    from screenplay_cowriter.cli import _handle_command

    store = SessionStore(str(tmp_path))
    sid = store.create("T").session_id

    # ---- /fork
    session = store.load(sid)
    _handle_command("/fork alt", session, store)
    assert store.load(sid).current_branch == "alt", "the CLI fork did not persist"

    stale = _stale_snapshot(sid)  # a chat turn's snapshot, from before the fork
    _turn(stale, "stale-q")
    store.save(stale)
    assert store.load(sid).current_branch == "alt", \
        "a chat turn undid the CLI's /fork"

    # ---- /switch — a separate save site with its own flag.
    before_switch = store.load(sid)  # holds "alt"; disk is about to move to "main"
    fresh = store.load(sid)
    _handle_command("/switch main", fresh, store)
    assert store.load(sid).current_branch == "main", "the CLI switch did not persist"

    _turn(before_switch, "late-q")
    store.save(before_switch)  # message-only, still holding the OLD selection
    assert store.load(sid).current_branch == "main", \
        "a chat turn undid the CLI's /switch"

    # ---- /persona — the third field family, on the branch the writer is on.
    session = store.load(sid)
    _handle_command("/persona premise_doctor", session, store)
    assert store.load(sid).branch.active_persona == "premise_doctor"

    stale_persona = _stale_snapshot(sid)  # holds Branch's default persona
    _turn(stale_persona, "later-q")
    store.save(stale_persona)
    assert store.load(sid).branch.active_persona == "premise_doctor", \
        "a chat turn undid the CLI's /persona"


def test_every_writer_that_changes_the_selection_says_so():
    """The wiring half. A behavioural test cannot catch a NEW writer that forgets
    the flag — such a writer only misbehaves under a race — so this reads the
    source.

    Scoped to **both packages**, not to `webapp_server.py`. The first version of
    this guard scanned only the file the audit happened to name, which is exactly
    how `screenplay_cowriter/server.py`'s three routes were missed: the store is
    shared, so every writer of it is in scope. The suite caught that omission —
    the guard's scope was the defect, not the fix.
    """
    writers = _writers_that_change_the_selection()

    # Non-vacuity AND completeness: an AST walk that silently matched nothing, or
    # a writer that appeared and was never flagged, both have to be loud.
    assert set(writers) == _EXPECTED_WRITERS, (
        "the set of selection-changing writers moved — update this guard "
        f"deliberately. added: {sorted(set(writers) - _EXPECTED_WRITERS)}, "
        f"removed: {sorted(_EXPECTED_WRITERS - set(writers))}")

    missing = sorted(f"{mod}::{name}" for (mod, name), owns in writers.items() if not owns)
    assert not missing, (
        "these functions change the writer's selection but save without "
        f"owns_selection=True, so a concurrent chat turn can silently undo "
        f"them: {missing}")
