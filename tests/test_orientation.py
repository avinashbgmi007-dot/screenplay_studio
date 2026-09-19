"""P3.12 + P3.13 — deterministic orientation (where this conversation stands).

Two facts the writer otherwise has to reconstruct: where the conversation left
off, and where their branch sits against the one it was forked from. Both are
computed from stored state (the probe flag, the message list,
`forked_at_index`) and stated as facts, so nothing is model-inferred and nothing
is invented.

One implementation, three surfaces — the mood fragment (so the persona knows),
the CLI session banner, and the CLI `/switch` output. These tests cover the
module and then each surface, because the drift between surfaces is the failure
mode the single resolver exists to prevent.
"""
import os

import pytest

from screenplay_cowriter.models import Message, Session
from screenplay_cowriter.orientation import (
    MAX_HEADING_CHARS, PERSONA_NAMES, branch_position, orientation_lines,
    resume_line,
)


class _Ctx:
    """Minimal ScriptContext stand-in — only `.data['scenes']` is read."""

    def __init__(self, scenes=None):
        self.data = {"scenes": scenes or []}


def _session_with_turn(scene_refs=(4,), persona="writing_partner", probe=True):
    s = Session.new("Gun Pen")
    b = s.branch
    b.active_persona = persona
    b.messages = [
        Message(role="user", content="have a look", scene_refs=list(scene_refs)),
        Message(role="assistant", content="What is the beat doing here?"),
    ]
    b.awaiting_probe = probe
    return s


# ---------------------------------------------------------------------------
# resume_line
# ---------------------------------------------------------------------------

def test_a_session_with_no_turns_has_nothing_to_resume():
    assert resume_line(Session.new("Empty")) is None


def test_mid_probe_is_stated_when_the_flag_is_set():
    line = resume_line(_session_with_turn(probe=True))
    assert "left off mid-probe" in line
    assert "waiting on your answer" in line


def test_the_line_changes_once_the_probe_is_answered():
    """`awaiting_probe` is a LIVE flag the engine clears on the writer's next
    turn, so this is not a stored timestamp that can go stale."""
    line = resume_line(_session_with_turn(probe=False))
    assert "mid-probe" not in line
    assert line.startswith("- Your last turn was with")


def test_it_names_the_scene_from_the_last_user_turn():
    ctx = _Ctx([{"scene_number": 4, "heading_raw": "INT. HOSPITAL - NIGHT"}])
    assert "about scene 4 (INT. HOSPITAL - NIGHT)" in resume_line(_session_with_turn(), ctx)


def test_it_names_the_scene_number_without_a_script_context():
    line = resume_line(_session_with_turn(), None)
    assert "about scene 4" in line
    assert "(" not in line


def test_it_reads_the_LAST_user_turn_not_the_first():
    s = _session_with_turn(scene_refs=(2,))
    s.branch.messages.append(Message(role="assistant", content="ok"))
    s.branch.messages.append(Message(role="user", content="now scene 9", scene_refs=[9]))
    assert "about scene 9" in resume_line(s)


def test_it_is_silent_about_scenes_when_none_were_referenced():
    line = resume_line(_session_with_turn(scene_refs=()))
    assert "about scene" not in line
    assert "waiting on your answer" in line


def test_a_heading_is_bounded():
    """A heading is script text riding into a prompt — a malformed one must not
    become a paragraph."""
    long_heading = "INT. " + "VERY LONG PLACE NAME " * 20
    ctx = _Ctx([{"scene_number": 4, "heading_raw": long_heading}])
    line = resume_line(_session_with_turn(), ctx)
    assert len(line) < MAX_HEADING_CHARS + 120
    assert "…" in line


def test_the_persona_is_named_the_way_the_writer_knows_them():
    assert "Sameer" in resume_line(_session_with_turn(persona="writing_partner"))
    assert "Dr. Sushruta" in resume_line(_session_with_turn(persona="script_consultant"))
    assert set(PERSONA_NAMES) == {"writing_partner", "script_consultant"}


def test_an_unknown_persona_falls_back_to_its_key():
    assert "producer" in resume_line(_session_with_turn(persona="producer"))
    assert "the co-writer" in resume_line(_session_with_turn(persona=None))


# ---------------------------------------------------------------------------
# branch_position
# ---------------------------------------------------------------------------

def test_a_lone_branch_has_nothing_to_say():
    assert branch_position(Session.new("Ordinary")) == []


def test_switching_back_to_the_fork_point_names_the_fork_left_behind():
    """The other half of 'switching back'. main has no parent, so without the
    children note the fork point would say nothing at all."""
    s = Session.new("T")
    s.branch.messages = [Message(role="user", content=f"t{i}") for i in range(3)]
    s.fork("alt")
    s.branch.messages.append(Message(role="user", content="mine"))
    s.switch("main")
    line = branch_position(s)[0]
    assert "Branches forked from 'main'" in line
    assert "'alt' (1 turn(s))" in line


def test_the_children_note_is_absent_when_nothing_was_forked():
    s = Session.new("T")
    s.fork("alt")
    assert branch_position(s) == [] or not any("forked from 'alt'" in ln for ln in branch_position(s))


def test_a_fork_carries_the_pending_probe():
    """Found by this pass: `fork()` copied the messages, persona and mode but
    not `awaiting_probe`, so a fork made mid-probe forgot it was waiting — and
    the fork's own last message is still Sameer's question."""
    s = _session_with_turn(probe=True)
    forked = s.fork("alt")
    assert forked.awaiting_probe is True
    assert "left off mid-probe" in resume_line(s)
    # and a fork made between turns stays between turns
    s2 = _session_with_turn(probe=False)
    assert s2.fork("alt").awaiting_probe is False


def test_the_real_fork_shape_is_read_correctly():
    """Uses `Session.fork` rather than hand-built state, so the test breaks if
    the fork contract changes (forked_at_index is the parent's message count)."""
    s = Session.new("Gun Pen")
    s.branch.messages = [Message(role="user", content=f"turn {i}") for i in range(6)]
    s.fork("alt")
    assert s.branch.forked_at_index == 6
    assert len(s.branch.messages) == 6
    # neither side has moved
    assert "Neither has moved since." in branch_position(s)[0]
    # main moves on, the fork does not
    s.branches["main"].messages += [
        Message(role="user", content="more", scene_refs=[11]),
        Message(role="user", content="more", scene_refs=[12]),
    ]
    line = branch_position(s)[0]
    assert "'main' has added 2 turn(s)" in line
    assert "this branch has not moved" in line
    assert "scene 11, scene 12" in line
    # the fork moves too
    s.branch.messages.append(Message(role="user", content="mine"))
    assert "this branch has added 1" in branch_position(s)[0]


def test_the_fork_point_is_named():
    s = Session.new("T")
    s.branch.messages = [Message(role="user", content=f"t{i}") for i in range(4)]
    s.fork("alt")
    assert "at turn 4" in branch_position(s)[0]


def test_only_the_first_three_scenes_are_named():
    s = Session.new("T")
    s.fork("alt")
    s.branches["main"].messages = [
        Message(role="user", content="x", scene_refs=[n]) for n in range(1, 8)
    ]
    line = branch_position(s)[0]
    assert "scene 1, scene 2, scene 3" in line
    assert "scene 4" not in line


def test_a_missing_parent_is_stated_not_crashed():
    s = Session.new("T")
    s.fork("alt")
    del s.branches["main"]
    line = branch_position(s)[0]
    assert "no longer on file" in line


def test_the_fork_alone_moving_is_stated():
    s = Session.new("T")
    s.fork("alt")
    s.branch.messages.append(Message(role="user", content="mine"))
    line = branch_position(s)[0]
    assert "You have added 1 turn(s) here" in line
    assert "'main' has not moved since" in line


# ---------------------------------------------------------------------------
# orientation_lines
# ---------------------------------------------------------------------------

def test_it_reads_resume_first_then_branch():
    s = _session_with_turn()
    s.fork("alt")
    lines = orientation_lines(s)
    assert "left off mid-probe" in lines[0]
    assert any("forked from" in ln for ln in lines[1:])


def test_an_ordinary_session_gets_only_the_resume_line():
    lines = orientation_lines(_session_with_turn())
    assert len(lines) == 1
    assert "left off mid-probe" in lines[0]


# ---------------------------------------------------------------------------
# surface 1: the mood fragment
# ---------------------------------------------------------------------------

def _manifest(tmp_path):
    from screenplay_studio.manifest import ProjectManifest

    src = tmp_path / "s.fountain"
    src.write_text("Title: T\n\nINT. R - NIGHT\n\nAct.\n", encoding="utf-8")
    return ProjectManifest.create(str(tmp_path / "proj"), str(src), title="T")


def test_the_mood_fragment_carries_the_orientation_when_given_a_session(tmp_path):
    from screenplay_studio import webapp_server

    frag = webapp_server._mood_fragment(
        _manifest(tmp_path), _session_with_turn(), _Ctx(
            [{"scene_number": 4, "heading_raw": "INT. HOSPITAL - NIGHT"}]))
    assert "Where this conversation stands:" in frag
    assert "left off mid-probe" in frag
    assert "about scene 4 (INT. HOSPITAL - NIGHT)" in frag


def test_the_mood_fragment_is_unchanged_without_a_session(tmp_path):
    """The original contract: callers with no session (and the existing tests)
    get exactly the block they got before."""
    from screenplay_studio import webapp_server

    frag = webapp_server._mood_fragment(_manifest(tmp_path))
    assert "Where this conversation stands:" not in frag
    assert "Last desk visit:" in frag


def test_the_demo_models_mood_parser_still_reads_the_block(tmp_path):
    """`demo_model._mood_facts` scrapes the block with regexes; the orientation
    lines are appended AFTER the facts, and must not disturb them."""
    from screenplay_studio import webapp_server
    from screenplay_studio.demo_model import _mood_facts

    m = _manifest(tmp_path)
    m.updated_at -= 3 * 86400
    frag = webapp_server._mood_fragment(m, _session_with_turn(), _Ctx())
    facts = _mood_facts(frag)
    assert facts["visit"] == "3 day(s) ago"
    assert facts["drafts"] == 0
    assert facts["edits"] == 0


# ---------------------------------------------------------------------------
# surfaces 2 and 3: the CLI
# ---------------------------------------------------------------------------

def _cli(tmp_path):
    from screenplay_cowriter.cli import _handle_command
    from screenplay_cowriter.store import SessionStore
    return _handle_command, SessionStore(str(tmp_path / "sessions"))


def test_the_cli_switch_to_a_fork_reports_what_the_parent_did(tmp_path, capsys):
    """P3.12: switching back is exactly when the writer has lost track of what
    the branch they left has done since."""
    handle, store = _cli(tmp_path)
    s = Session.new("T")
    s.branch.messages = [Message(role="user", content=f"t{i}") for i in range(3)]
    s.fork("alt")
    s.switch("main")
    s.branches["main"].messages += [Message(role="user", content="x", scene_refs=[12])]
    handle("/switch alt", s, store)
    out = capsys.readouterr().out
    assert "Switched to branch 'alt'." in out
    assert "was forked from 'main' at turn 3" in out
    assert "'main' has added 1 turn(s) about scene 12" in out


def test_the_cli_switch_back_to_the_fork_point_names_the_fork(tmp_path, capsys):
    handle, store = _cli(tmp_path)
    s = Session.new("T")
    s.branch.messages = [Message(role="user", content=f"t{i}") for i in range(3)]
    s.fork("alt")
    s.branch.messages.append(Message(role="user", content="mine"))
    handle("/switch main", s, store)
    out = capsys.readouterr().out
    assert "Switched to branch 'main'." in out
    assert "Branches forked from 'main': 'alt' (1 turn(s))" in out


def test_the_cli_banner_prints_the_resume_line(tmp_path, capsys, monkeypatch):
    """P3.13: a terminal writer gets a bare prompt, so this is the one thing
    they cannot recover from the screen."""
    from screenplay_cowriter import cli as cli_mod
    from screenplay_cowriter.store import SessionStore

    s = _session_with_turn()
    store = SessionStore(str(tmp_path / "sessions"))
    store.save(s)
    monkeypatch.setattr(cli_mod, "_load_contexts",
                        lambda session: (_Ctx([{"scene_number": 4,
                                                "heading_raw": "INT. HOSPITAL - NIGHT"}]), None))

    class _Client:
        def __init__(self, **kw):
            pass

    monkeypatch.setattr(cli_mod, "LlamaServerClient", _Client)
    monkeypatch.setattr("builtins.input", lambda *a: "/quit")
    cli_mod.run_repl(s, store, None)
    out = capsys.readouterr().out
    assert "left off mid-probe" in out
    assert "about scene 4 (INT. HOSPITAL - NIGHT)" in out
