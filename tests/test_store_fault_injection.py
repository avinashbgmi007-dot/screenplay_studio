"""Fault injection over EVERY writer-owned store — the class behind A2/A3.

The instance (audit 2026-09-20): a crash-truncated premise.json read as "no
premise card", and the next POST then overwrote the damaged card. The class:
a store whose loader collapses "this file is unreadable" into the same value as
"this file is not there". The writer sees their work vanish, and because the
mutators load-then-save, the very next write finalises the loss.

So every store is driven through three injected faults — a crash-truncated
file, a flipped byte, and a zero-byte file — and each one must NOT read as the
missing-value:

    * miss      -> the store's documented default (the distinction is the point)
    * valid     -> real data
    * truncated / garbage / empty
                -> an ERROR, never the default
    * load-modify-write on a damaged store leaves its bytes INTACT

Registry entries carry a status:

  ``guarded`` — the fault contract above is asserted.
  ``silent``  — the defect is still present; the test asserts THAT, with the
                reason recorded, so the entry fails the moment the store is
                fixed and the marker has to be flipped. ``silent`` is a
                todo with evidence, not a skipped test.

A discovery check fails the build when a module writes a store through
``jsonio.atomic_write_json`` and is not in the registry, so a new store cannot
ship without its fault tests.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import pytest

from screenplay_studio import beatboard, metrics, notes, revision, stash_store
from screenplay_studio.manifest import ProjectManifest


def _write_raw(path: str, text: str) -> None:
    """Write bytes outside the store API — this stands in for a crash/AV/disk
    fault, so it must NOT go through atomic_write_json."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


@dataclass
class StoreCase:
    name: str
    module: str
    path: Callable[[Any], str]
    read: Callable[[Any], Any]
    seed: Callable[[Any], None]
    mutate: Callable[[Any], None]
    missing_default: Any
    status: str = "guarded"
    why: str = ""
    setup: Optional[Callable[[Any], None]] = None
    error_marker: Optional[Callable[[Any], bool]] = None
    # Some readers answer a coarse question ("is there anything here I must not
    # overwrite?") where the honest answer to damage is a conservative PRESENT,
    # not an exception. Those declare what "damage was reported" means for them.
    damage_ok: Optional[Callable[[str], bool]] = None
    # False when the store's writer is not a load-modify-write cycle (a
    # wholesale rewrite cannot clobber what it never read).
    load_modify_write: bool = True
    # "empty" (missing -> the store's default) or "error" (the store cannot
    # legitimately be absent: a project without its manifest is not a project).
    missing_reads_as: str = "empty"
    # A store may legally rewrite its own path as long as the damaged bytes are
    # still recoverable somewhere (WriterMemory renames the torn file to .bak).
    evidence_path: Optional[Callable[[Any], str]] = None


def _sample_text() -> str:
    return ("INT. ROOM - NIGHT\n\nA lamp.\n\nRAVI\n\nHello.\n")


CASES = [
    StoreCase(
        name="margin notes",
        module="screenplay_studio/notes.py",
        path=lambda m: os.path.join(m.project_dir, notes.NOTES_FILE),
        read=lambda m: notes.load_notes(m),
        seed=lambda m: notes.add_note(m, 1, "first margin note"),
        mutate=lambda m: notes.add_note(m, 2, "note added after the damage"),
        missing_default=[],
        status="guarded",
    ),
    StoreCase(
        name="stash",
        module="screenplay_studio/stash_store.py",
        path=lambda m: stash_store.stash_path(m.project_dir),
        read=lambda m: stash_store.load_stash(m.project_dir),
        seed=lambda m: stash_store.add_to_stash(m.project_dir, "a stashed line"),
        mutate=lambda m: stash_store.add_to_stash(m.project_dir, "stashed after damage"),
        missing_default=[],
        status="guarded",
    ),
    StoreCase(
        name="beat board order",
        module="screenplay_studio/beatboard.py",
        path=lambda m: os.path.join(m.project_dir, beatboard.BOARD_FILE),
        # the store's own loader: get_order() layers a natural-order fallback on
        # top, and the fault contract is about the STORE, not that fallback.
        read=lambda m: beatboard._load(m),
        seed=lambda m: beatboard.set_order(m, [1]),
        mutate=lambda m: beatboard.set_order(m, [1, 2]),
        missing_default={},
        setup=lambda m: _working_copy(m),
        status="guarded",
    ),
    StoreCase(
        name="metrics",
        module="screenplay_studio/metrics.py",
        path=lambda m: metrics.metrics_path(m),
        read=lambda m: metrics.load(m),
        seed=lambda m: metrics.record_analysis(m, 1.5),
        mutate=lambda m: metrics.record_analysis(m, 2.5),
        missing_default={},
        status="guarded",
    ),
    StoreCase(
        name="finding intents",
        module="screenplay_studio/revision.py",
        path=lambda m: revision.finding_marks_path(m),
        read=lambda m: revision.finding_intents(m),
        seed=lambda m: revision.set_finding_intent(m, "abc123", "addressed"),
        mutate=lambda m: revision.set_finding_intent(m, "def456", "deferred"),
        missing_default={},
        status="guarded",
    ),
    StoreCase(
        name="dismissed findings",
        module="screenplay_studio/revision.py",
        path=lambda m: revision.dismissed_path(m),
        read=lambda m: revision.dismissed_finding_ids(m),
        seed=lambda m: revision.dismiss_finding(m, 0, "an issue", "abc123"),
        mutate=lambda m: revision.dismiss_finding(m, 1, "another", "def456"),
        missing_default=set(),
        status="guarded",
    ),
    StoreCase(
        name="edit log",
        module="screenplay_studio/revision.py",
        path=lambda m: revision.edits_log_path(m),
        read=lambda m: revision.has_edits(m),
        seed=lambda m: _write_raw(revision.edits_log_path(m),
                                 json.dumps([{"id": "aa11", "scene_number": 1,
                                              "applied": [{"old": "a", "new": "b"}]}])),
        mutate=lambda m: revision.has_edits(m),
        missing_default=False,
        status="guarded",
        why="A1: has_edits answers True (present-but-unreadable), not False",
        damage_ok=lambda outcome: outcome != "empty",
        load_modify_write=False,
    ),
    StoreCase(
        name="redo stack",
        module="screenplay_studio/revision.py",
        path=lambda m: revision.edits_redo_path(m),
        read=lambda m: revision.redo_stack(m),
        seed=lambda m: _write_raw(revision.edits_redo_path(m),
                                 json.dumps([{"id": "bb22", "scene_number": 1,
                                              "applied": [{"old": "a", "new": "b"}]}])),
        # The redo stack's own load-modify-write cycle is `undo_last_edit`:
        # it reads the stack, appends the undone record, and saves it back.
        mutate=lambda m: revision.undo_last_edit(m),
        missing_default=[],
        setup=lambda m: _redo_setup(m),
        status="guarded",
        why="BE-M1: a damaged edits.redo.json is reported, and the undo behind it "
            "refuses rather than overwriting the only recoverable copy",
    ),
    StoreCase(
        name="premise card",
        module="screenplay_studio/webapp_server.py",
        path=lambda m: os.path.join(m.project_dir, "premise.json"),
        read=lambda m: _premise(m),
        seed=lambda m: _write_raw(os.path.join(m.project_dir, "premise.json"),
                                  json.dumps({"title": "T", "logline": "L"})),
        mutate=lambda m: _premise_mutate(m),
        missing_default=(None, None),
        error_marker=lambda v: bool(v[1]),
        status="guarded",
        why="A3: unreadable is reported (perr), and POST refuses to overwrite it",
        load_modify_write=False,
    ),
    StoreCase(
        name="project manifest",
        module="screenplay_studio/manifest.py",
        path=lambda m: m.manifest_path,
        read=lambda m: ProjectManifest.load(m.project_dir).title,
        seed=lambda m: m.save(),
        mutate=lambda m: m.save(),
        missing_default="__never__",
        missing_reads_as="error",
        status="guarded",
        why="ProjectManifest.load lets JSONDecodeError out (test_negative pins it)",
        load_modify_write=False,
    ),
    StoreCase(
        name="idea card",
        module="screenplay_studio/ideas.py",
        path=lambda m: os.path.join(_idea_dir(m), _idea_id(), "idea.json"),
        read=lambda m: _idea(m),
        seed=lambda m: _idea_seed(m),
        mutate=lambda m: _idea_mutate(m),
        missing_default=None,
        status="guarded",
        why="H2: a corrupt idea is flagged on the shelf, not dropped (test_audit_hardening)",
        missing_reads_as="error",
    ),
    StoreCase(
        name="writer memory",
        module="screenplay_cowriter/memory.py",
        path=lambda m: _memory_path(m),
        # (a torn file was preserved as .bak, the profile is not the empty one)
        read=lambda m: _memory_state(m),
        seed=lambda m: _memory_seed(m),
        mutate=lambda m: _memory_mutate(m),
        missing_default=(False, False),
        error_marker=lambda v: v[0],
        evidence_path=lambda m: _memory_path(m) + ".bak",
        status="guarded",
        why="WriterMemory.load backs the torn file up to .bak and starts a fresh "
            "profile ('chat must never break') — damage preserved, not swallowed",
    ),
    StoreCase(
        name="cowriter session",
        module="screenplay_cowriter/models.py",
        path=lambda m: _session_path(m),
        read=lambda m: _session_read(m),
        seed=lambda m: _session_seed(m),
        mutate=lambda m: _session_mutate(m),
        missing_default=None,
        # asking for a session by id and getting nothing back is not "the writer
        # never wrote here" — it is a missing conversation, and it is reported.
        missing_reads_as="error",
        evidence_path=lambda m: _session_path(m) + ".bak",
        status="guarded",
        why="B4: SessionStore.save parks an unreadable base as .bak before the "
            "save lands, so a chat turn cannot destroy the only recoverable copy",
    ),
]


def _working_copy(m) -> None:
    """The beat board reads the working copy, so the fixture project needs one."""
    from screenplay_parser import parse_fountain
    src = os.path.join(os.path.dirname(m.project_dir), "fault_fixture.fountain")
    with open(src, "w", encoding="utf-8") as f:
        f.write(_sample_text())
    parse_fountain(src).save(m.parsed_path)
    revision.ensure_working(m)


def _redo_setup(m) -> None:
    """An undo needs something to undo: a working copy plus one applied edit.

    The redo stack the case is actually about is then written by the case's own
    `seed`, so the setup stops at the edit log.
    """
    _working_copy(m)
    _write_raw(revision.edits_log_path(m),
               json.dumps([{"id": "aa11", "scene_number": 1, "applied": []}]))


def _memory_path(m) -> str:
    return os.path.join(os.path.dirname(m.project_dir), "writer_profile.json")


def _memory_state(m):
    from screenplay_cowriter.memory import WriterMemory
    path = _memory_path(m)
    mem = WriterMemory.load(path)
    return (os.path.exists(path + ".bak"), len(mem.to_dict().get("observations") or []))


def _memory_seed(m) -> None:
    from screenplay_cowriter.memory import WriterMemory
    mem = WriterMemory(_memory_path(m), profile={"schema": 2, "dimensions": {},
                                                  "observations": [{"text": "seeded"}]})
    mem.save()


def _memory_mutate(m) -> None:
    from screenplay_cowriter.memory import WriterMemory
    mem = WriterMemory.load(_memory_path(m))
    mem.save()


# ---------- the cowriter's session store (BE-B4) ----------------------------

# A fixed id so the harness can address exactly one session file from the
# manifest. `Session.new()` mints a random one; the store keys off the field.
_SESSION_ID = "fault_session"


def _sessions_dir(m) -> str:
    return os.path.join(m.project_dir, "sessions")


def _session_path(m) -> str:
    return os.path.join(_sessions_dir(m), f"{_SESSION_ID}.json")


def _session_store(m):
    from screenplay_cowriter.store import SessionStore
    return SessionStore(_sessions_dir(m))


def _session_seed(m) -> None:
    from screenplay_cowriter.models import Session
    session = Session.new(title="fault fixture session")
    session.session_id = _SESSION_ID
    _session_store(m).save(session)


def _session_read(m):
    return _session_store(m).load(_SESSION_ID).title


def _session_mutate(m) -> None:
    from screenplay_cowriter.models import Session
    session = Session.new(title="saved after the damage")
    session.session_id = _SESSION_ID
    _session_store(m).save(session)


EXEMPT = {
    # progress.json is stage telemetry: overwritten wholesale at every stage
    # transition, holds nothing a writer authored, and is deliberately
    # fail-soft (a lost progress line must never break an analysis run).
    "screenplay_studio/orchestrator.py":
        "progress.json is transient stage telemetry, rewritten at every "
        "stage transition and never the writer's work product",
    # parsed.json / working.json are regenerated from the source .fountain. The
    # only part a writer authored is the edit log, and A1 covers that.
    "screenplay_parser/models.py":
        "parsed/working copies regenerate from the fountain source; the "
        "unregenerable part (edits.json) is covered by the edit-log case",
}


def _premise(m):
    import screenplay_studio.webapp_server as webapp_server
    return webapp_server._load_premise(m.project_dir)


def _premise_mutate(m):
    import screenplay_studio.webapp_server as webapp_server
    path = os.path.join(m.project_dir, "premise.json")
    stored, perr = webapp_server._load_premise(m.project_dir)
    if perr:
        raise RuntimeError(perr)
    webapp_server.atomic_write_json(path, dict(stored or {}, title="changed"))


def _idea_dir(m) -> str:
    return os.path.join(os.path.dirname(m.project_dir), "ideas")


_IDEA = {}   # the id the seed created (idea ids are random)


def _idea_id() -> str:
    return _IDEA.get("id", "fault_fixture_idea")


def _idea(m):
    from screenplay_studio.ideas import IdeaStore
    return IdeaStore(_idea_dir(m)).load(_idea_id())


def _idea_seed(m) -> None:
    from screenplay_studio.ideas import IdeaStore
    _IDEA["id"] = IdeaStore(_idea_dir(m)).create("fault fixture idea")["id"]


def _idea_mutate(m) -> None:
    from screenplay_studio.ideas import IdeaStore
    IdeaStore(_idea_dir(m)).rename(_idea_id(), "renamed after damage")


# ---------- the injected faults ---------------------------------------------

FAULTS = {
    "crash-truncated": lambda text: text[: max(1, len(text) // 2)],
    "flipped-byte-garbage": lambda text: "{\"broken\": [1, 2, ",
    "zero-byte": lambda text: "",
}


def _probe(case: StoreCase, m) -> str:
    """Classify what the store reads as: 'error', 'empty' (the missing-value),
    or 'data'."""
    try:
        value = case.read(m)
    except Exception as exc:  # noqa: BLE001 — an error IS the pass condition here
        return f"error:{type(exc).__name__}"
    if case.error_marker and case.error_marker(value):
        return "error:reported"
    if value == case.missing_default:
        return "empty"
    return "data"


@pytest.fixture
def project(tmp_path, sample_fountain):
    m = ProjectManifest.create(str(tmp_path / "proj"), sample_fountain)
    m.save()
    return m


def _prepared(case, project):
    """The project with the case's own prerequisites in place (a working copy
    for the beat board, for instance)."""
    if case.setup:
        case.setup(project)
    return project


# ---------- the contract ----------------------------------------------------

@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_missing_store_reads_as_its_default(case, project):
    prepared = _prepared(case, project)
    # the store must actually be absent — the fixture writes some of them
    for gone in (case.path(prepared),
                 case.evidence_path(prepared) if case.evidence_path else None):
        if gone and os.path.exists(gone):
            os.remove(gone)
    outcome = _probe(case, prepared)
    if case.missing_reads_as == "error":
        assert outcome.startswith("error"), (
            f"{case.name}: vanished store read as {outcome!r} — this store cannot "
            f"legitimately be absent, so its absence must be reported")
    else:
        assert outcome == "empty", (
            f"{case.name}: a store that was never written must read as its "
            f"default, got {outcome!r}")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_valid_store_reads_as_data(case, project):
    prepared = _prepared(case, project)
    case.seed(prepared)
    assert _probe(case, prepared) == "data", (
        f"{case.name}: seeded through the store's own API but did not read back")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
@pytest.mark.parametrize("fault", sorted(FAULTS))
def test_damage_never_reads_as_the_missing_value(case, fault, project):
    """The heart of it: 'unreadable' and 'not there' must be different answers."""
    prepared = _prepared(case, project)
    case.seed(prepared)
    path = case.path(prepared)
    with open(path, encoding="utf-8") as f:
        good = f.read()
    _write_raw(path, FAULTS[fault](good))
    outcome = _probe(case, prepared)

    damaged_ok = (case.damage_ok or (lambda o: o.startswith("error")))(outcome)
    if case.status == "guarded":
        assert damaged_ok, (
            f"{case.name}: a {fault} store read as {outcome!r} — that is the "
            f"A3 shape (a damaged file presented as 'you have nothing here'). "
            f"If this reader cannot raise, it must report the damage explicitly.")
    else:
        assert outcome == "empty", (
            f"{case.name} is marked silent ({case.why}) but now answers "
            f"{outcome!r} — the defect is fixed: flip status to 'guarded'.")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_a_write_never_overwrites_a_damaged_store(case, project):
    """Because the mutators load-then-save, a lenient loader means the next
    mundane action (adding a note) permanently destroys the damaged file."""
    if not case.load_modify_write:
        pytest.skip("not a load-modify-write store: the writer cannot clobber "
                    "what it never read")
    prepared = _prepared(case, project)
    case.seed(prepared)
    path = case.path(prepared)
    with open(path, encoding="utf-8") as f:
        good = f.read()
    damaged = FAULTS["crash-truncated"](good)
    _write_raw(path, damaged)
    try:
        case.mutate(prepared)
        raised = False
    except Exception:  # noqa: BLE001 — refusing to write is a valid outcome
        raised = True
    with open(path, encoding="utf-8") as f:
        after = f.read()

    evidence = case.evidence_path(prepared) if case.evidence_path else None
    kept = bool(evidence and os.path.exists(evidence))

    if case.status == "guarded":
        assert raised or after == damaged or after == good or kept, (
            f"{case.name}: a load-modify-write on a damaged store replaced its "
            f"bytes ({len(damaged)} -> {len(after)}) — the damaged copy was the "
            f"only recoverable evidence and it is now gone")
    else:
        assert after != damaged, (
            f"{case.name} is marked silent ({case.why}) but the mutate no longer "
            f"clobbers the damaged file — flip status to 'guarded'.")


# ---------- the damage has to reach the writer, not just the loader --------

def test_a_damaged_store_answers_the_writer_with_damage_not_emptiness(tmp_path):
    """Unit-level honesty is not enough: the SPA must not be handed an empty
    list that reads as "you never wrote anything"."""
    import screenplay_studio.webapp_server as webapp_server

    src = tmp_path / "s.fountain"
    src.write_text(_sample_text(), encoding="utf-8")
    webapp_server.PROJECTS_DIR = str(tmp_path / "projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.app.config["TESTING"] = True
    client = webapp_server.app.test_client()
    with open(src, "rb") as f:
        # werkzeug's test client takes (stream, filename) -- the reverse of the
        # requests-style (name, stream, type) tuple the browser suites use
        created = client.post("/api/projects",
                              data={"file": (f, "s.fountain"),
                                    "title": "Fault fixture"})
    assert created.status_code in (200, 201), created.data[:200]
    name = created.json["project"]

    ok = client.get(f"/api/projects/{name}/notes")
    assert ok.status_code == 200 and ok.json.get("notes") == []

    _write_raw(os.path.join(webapp_server.PROJECTS_DIR, name, notes.NOTES_FILE),
               "[{ \"id\": \"a\", \"text\": \"half a not")
    damaged = client.get(f"/api/projects/{name}/notes")
    assert damaged.status_code == 503, (
        f"damaged notes answered {damaged.status_code}: {damaged.data[:200]}")
    body = damaged.json
    assert body.get("unreadable") is True and "notes.json" in body.get("error", ""), body

    # and the write behind it is refused rather than finalised over the damage
    refused = client.post(f"/api/projects/{name}/notes",
                          json={"scene_number": 1, "text": "new note"})
    assert refused.status_code == 503, refused.data[:200]
    with open(os.path.join(webapp_server.PROJECTS_DIR, name, notes.NOTES_FILE),
              encoding="utf-8") as f:
        assert f.read().startswith("[{ \"id\": \"a\""), "the damaged file was rewritten"


# ---------- discovery: no store may ship without fault tests ----------------

def test_every_store_writer_is_in_the_registry():
    """Grep the codebase for store writers and require a registry entry per
    module, so the next store cannot be added without fault coverage."""
    root = Path(__file__).resolve().parent.parent
    writers = set()
    for path in list(root.glob("screenplay_studio/*.py")) + \
            list(root.glob("screenplay_cowriter/*.py")) + \
            list(root.glob("screenplay_parser/*.py")):
        if path.name == "jsonio.py":        # the definition itself
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"\batomic_write_json\(", text):
            writers.add(f"{path.parent.name}/{path.name}")
    covered = {c.module for c in CASES}
    uncovered = sorted(writers - covered - set(EXEMPT))
    assert not uncovered, (
        "these modules write a store but have no fault-injection entry: "
        f"{uncovered}. Add a StoreCase (or record why the store is exempt "
        f"in EXEMPT: {sorted(EXEMPT)}).")
