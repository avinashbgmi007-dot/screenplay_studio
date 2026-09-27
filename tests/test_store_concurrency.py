"""Cross-process store safety — BE-H2 (torn/lost writes) and BE-H4 (contended
reads reported as permanent damage).

The CLI and the webapp both write the same project directory; AGENTS.md
documents that as a supported configuration. Every lock in this codebase used to
be process-local (`threading.RLock` / `Lock`), which cannot serialize two
processes at all, and `atomic_write_json` wrote through a FIXED `<store>.tmp`
name that every process shared — so two writers interleaved their bytes into one
buffer and the survivor was renamed into the store.

These tests spawn REAL child processes, because that is the only way to observe
the defect: an in-process test passes on the broken code. Verified by mutation —
dropping the OS lock (leaving only the RLock) turns the first two red.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import threading
import time
from types import SimpleNamespace

import pytest

from screenplay_studio import jsonio, notes, stash_store
from screenplay_studio.manifest import ProjectManifest, _merge_manifest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHILD_TIMEOUT = 240


def _child_env() -> dict:
    """Give a child this process's import path, so it finds the repo AND the
    test dependencies however pytest happened to be launched."""
    env = dict(os.environ)
    parts = [REPO_ROOT] + [p for p in sys.path if p]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _spawn(source: str, *args) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", source, *args],
        cwd=REPO_ROOT, env=_child_env(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


# ---------------------------------------------------------------------------
# 1. The defect itself: concurrent writers on ONE store, from separate processes
# ---------------------------------------------------------------------------

_ACCUMULATE = textwrap.dedent(
    """
    import sys, time
    from screenplay_studio import jsonio

    path, worker, rounds, start_at = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4])
    # start-gate: every child begins hammering at the same instant, so the
    # windows genuinely overlap instead of the children politely queueing up.
    while time.time() < start_at:
        time.sleep(0.001)
    for k in range(rounds):
        with jsonio.lock_for(path):
            data = jsonio.load_json_store(path, {})
            data[worker] = k
            jsonio.atomic_write_json(path, data)
    """
)


def test_concurrent_processes_lose_no_update_and_never_tear_the_store(tmp_path):
    """4 processes x 40 locked load-modify-write cycles on one store.

    Keys only ever accumulate, so a correct serialization must leave every
    worker's key in the final file. Before the fix this lost updates and/or left
    the store unparseable, and the child raised on the torn read.
    """
    path = str(tmp_path / "shared.json")
    workers, rounds = 4, 40
    start_at = time.time() + 1.5

    procs = [
        _spawn(_ACCUMULATE, path, f"w{i}", str(rounds), repr(start_at))
        for i in range(workers)
    ]
    failures = []
    for i, proc in enumerate(procs):
        _out, err = proc.communicate(timeout=CHILD_TIMEOUT)
        if proc.returncode != 0:
            failures.append(f"worker {i} exited {proc.returncode}: {err.strip()[-400:]}")

    assert not failures, "child processes failed:\n" + "\n".join(failures)
    assert set(jsonio.load_json_store(path, {})) == {f"w{i}" for i in range(workers)}, (
        "lost updates: every worker's key must survive"
    )
    assert [f for f in os.listdir(tmp_path) if f.endswith(".tmp")] == [], (
        "a temp file was left behind"
    )


# ---------------------------------------------------------------------------
# 2. The lock is genuinely cross-PROCESS (the entire point of BE-H2)
# ---------------------------------------------------------------------------

_HOLD = textwrap.dedent(
    """
    import sys, time
    from screenplay_studio import jsonio

    path, hold, flag = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    with jsonio.lock_for(path):
        with open(flag, "w", encoding="utf-8") as f:
            f.write("locked")
        time.sleep(hold)
    """
)


def test_the_lock_is_actually_cross_process(tmp_path, monkeypatch):
    """A lock held by ANOTHER process must block us, and the wait must be
    bounded. An in-process RLock cannot do this — which was the whole defect —
    so the proof has to come from a second process rather than a thread."""
    path = str(tmp_path / "held.json")
    flag = str(tmp_path / "held.flag")
    jsonio.atomic_write_json(path, {"seed": 1})   # creates the lock sidecar

    proc = _spawn(_HOLD, path, "20", flag)
    try:
        deadline = time.monotonic() + 30
        while not os.path.exists(flag):
            assert proc.poll() is None, f"child died before locking: {proc.communicate()[1]}"
            assert time.monotonic() < deadline, "child never took the lock"
            time.sleep(0.02)

        monkeypatch.setattr(jsonio, "LOCK_TIMEOUT_SECONDS", 0.5)
        started = time.monotonic()
        with pytest.raises(jsonio.StoreLockTimeout):
            with jsonio.lock_for(path):
                pytest.fail("acquired a lock another process was holding")
        waited = time.monotonic() - started
        assert waited < 10, f"gave up after {waited:.1f}s — the wait must be bounded"
    finally:
        proc.kill()
        proc.communicate(timeout=30)


# ---------------------------------------------------------------------------
# 3. BE-H4: contended is not damaged
# ---------------------------------------------------------------------------


def test_transient_read_contention_is_retried_not_reported_as_damage(tmp_path, monkeypatch):
    """A read that fails only because a writer briefly holds the file open must
    be RETRIED, not escalated to StoreUnreadable ("this store is damaged",
    HTTP 503). Measured before this: 785 such escalations in one 4-process run.
    """
    path = str(tmp_path / "store.json")
    jsonio.atomic_write_json(path, {"kept": True})

    real_read = jsonio._read_text
    calls = {"n": 0}

    def flaky(p):
        calls["n"] += 1
        if calls["n"] == 1:
            raise PermissionError(13, "Access is denied")   # sharing violation
        return real_read(p)

    monkeypatch.setattr(jsonio, "_read_text", flaky)
    assert jsonio.load_json_store(path, None) == {"kept": True}
    assert calls["n"] == 2, "the read was not retried"


def test_a_genuinely_unreadable_store_still_raises(tmp_path, monkeypatch):
    """The retry must not swallow a real failure — flag, don't drop."""
    path = str(tmp_path / "store.json")
    jsonio.atomic_write_json(path, {"kept": True})

    def always_denied(_p):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(jsonio, "_read_text", always_denied)
    with pytest.raises(jsonio.StoreUnreadable):
        jsonio.load_json_store(path, None)


# ---------------------------------------------------------------------------
# 4. BE-H3: the writer's own stores must not lose a concurrent entry
# ---------------------------------------------------------------------------


def _in_parallel(fn, args, values) -> None:
    """Run `fn(*args, value)` once per value, all starting together."""
    barrier = threading.Barrier(len(values))
    errors: list[str] = []

    def run(value):
        try:
            barrier.wait(timeout=30)
            fn(*args, value)
        except Exception as e:                      # noqa: BLE001 — reported below
            errors.append(repr(e))

    threads = [threading.Thread(target=run, args=(v,)) for v in values]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, errors


def test_two_concurrent_note_adds_both_survive(tmp_path, monkeypatch):
    """The writer's margin notes. Measured before this: two adds left ONE note,
    because the second loaded the pre-add list and wrote it back over the first.
    """
    d = tmp_path / "proj"
    d.mkdir()
    m = SimpleNamespace(project_dir=str(d))

    real_load = notes._load_raw

    def slow_load(mm):
        data = real_load(mm)
        time.sleep(0.2)          # widen the read -> write window
        return data

    monkeypatch.setattr(notes, "_load_raw", slow_load)
    _in_parallel(notes.add_note, (m, 1), ["note A", "note B"])

    assert len(notes.load_notes(m)) == 2


def test_two_concurrent_stash_adds_both_survive(tmp_path, monkeypatch):
    """The Stash — same shape, same defect, same fix."""
    d = tmp_path / "proj"
    d.mkdir()

    real_load = stash_store.load_stash

    def slow_load(project_dir):
        data = real_load(project_dir)
        time.sleep(0.2)
        return data

    monkeypatch.setattr(stash_store, "load_stash", slow_load)
    _in_parallel(stash_store.add_to_stash, (str(d),), ["line A", "line B"])

    assert len(stash_store.load_stash(str(d))) == 2


# ---------------------------------------------------------------------------
# 4b. project.json merges every field but one — and that one is a list
# ---------------------------------------------------------------------------

def _draft(name: str, filename: str, when: float = 1000.0) -> dict:
    return {"name": name, "source_filename": filename, "uploaded_at": when}


def test_a_draft_added_by_a_peer_survives_this_writers_save():
    """Two uploads in the same instant used to leave ONE draft record, because
    `drafts` is the one field `save()` writes back as this writer's whole list
    instead of merging it. The losing writer's source snapshot stays on disk with
    no manifest row pointing at it, so the draft is unreachable from the desk.
    """
    out = _merge_manifest(
        {"drafts": []},
        {"drafts": [_draft("draft-2", "mine.fountain")]},
        {"drafts": [_draft("draft-2", "theirs.fountain")]},
    )
    assert [d["source_filename"] for d in out["drafts"]] == [
        "theirs.fountain", "mine.fountain"]


def test_a_colliding_draft_label_is_not_left_ambiguous():
    """`snapshot_active` names a draft from the list length, so two concurrent
    uploads both compute "draft-2". Merging the records is only half the fix:
    /diff and /drafts/activate select BY NAME, so two rows sharing a label makes
    the loser's draft unaddressable — the newcomer gets the next free name.
    """
    out = _merge_manifest(
        {"drafts": []},
        {"drafts": [_draft("draft-2", "mine.fountain")], "active_draft": "draft-2"},
        {"drafts": [_draft("draft-2", "theirs.fountain")], "active_draft": "draft-2"},
    )
    names = [d["name"] for d in out["drafts"]]
    assert len(set(names)) == 2, names
    mine = [d for d in out["drafts"] if d["source_filename"] == "mine.fountain"][0]
    # the writer that was renumbered must not be left "active" on the peer's row
    assert out["active_draft"] == mine["name"]


def test_a_removed_draft_still_stays_removed():
    """The merge is 3-way, not a union that cannot forget: a draft this writer
    dropped must not be resurrected from the copy on disk.
    """
    a, b = _draft("draft-1", "a.fountain"), _draft("draft-2", "b.fountain")
    out = _merge_manifest({"drafts": [a, b]}, {"drafts": [a]}, {"drafts": [a, b]})
    assert out["drafts"] == [a]


def test_a_saved_manifest_reports_the_drafts_the_store_actually_holds(tmp_path):
    """After `save()` re-baselines from disk, the in-memory object must agree with
    disk. A writer that reads `m.drafts` after saving (to name the next draft, to
    label the shelf) otherwise keeps acting on the list that just lost a race.
    """
    d = tmp_path / "proj"
    d.mkdir()
    m = ProjectManifest.create(str(d), __file__, title="T")
    peer = ProjectManifest.load(str(d))
    peer.drafts.append(_draft("draft-1", "theirs.fountain"))
    peer.save()                      # the peer writes first
    m.drafts.append(_draft("draft-1", "mine.fountain"))
    m.save()                         # m read its baseline before the peer landed

    on_disk = ProjectManifest.load(str(d))
    assert [x["source_filename"] for x in on_disk.drafts] == [
        "theirs.fountain", "mine.fountain"]
    assert [x["source_filename"] for x in m.drafts] == [
        "theirs.fountain", "mine.fountain"]


# ---------------------------------------------------------------------------
# 5. The lock sidecar must stay invisible to the product
# ---------------------------------------------------------------------------


def test_a_lock_sidecar_never_becomes_a_shelf_card(tmp_path, monkeypatch):
    """jsonio drops `<store>.lock` beside every store it writes, and one of them
    (writer_profile.json.lock) lands directly in PROJECTS_DIR. It is a FILE, so
    it must never reach ProjectManifest.load -> check_safe_id, whose ValueError
    the shelf route's `except Exception` would render as a phantom "unreadable"
    project on the writer's shelf."""
    import screenplay_studio.webapp_server as webapp_server

    monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(tmp_path))
    client = webapp_server.app.test_client()
    # 201 on first create, 200 when the deduplicated sample already exists
    assert client.post("/api/sample").status_code < 300   # one REAL project

    # exactly what a store write in PROJECTS_DIR leaves behind
    jsonio.atomic_write_json(str(tmp_path / "writer_profile.json"), {})

    cards = client.get("/api/projects").get_json()
    names = [c["project"] for c in cards]
    assert "writer_profile.json.lock" not in names, "a lock sidecar became a shelf card"
    assert not any(c.get("unreadable") for c in cards), cards
    assert names, "the real project vanished from the shelf"


def test_the_backup_archive_excludes_lock_sidecars(tmp_path, monkeypatch):
    """A backup is the writer's desk, not our plumbing."""
    import io
    import zipfile

    import screenplay_studio.webapp_server as webapp_server

    monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(tmp_path))
    client = webapp_server.app.test_client()
    client.post("/api/sample")
    name = client.get("/api/projects").get_json()[0]["project"]

    resp = client.get(f"/api/projects/{name}/backup")
    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
        assert [n for n in zf.namelist() if n.endswith(".lock")] == []


# ---------------------------------------------------------------------------
# 6. The primitive's own contract
# ---------------------------------------------------------------------------


def test_the_lock_is_reentrant_and_leaves_no_temp_files(tmp_path):
    """A store holds the lock across its load-modify-write while
    atomic_write_json re-enters it — that nesting must not deadlock."""
    path = str(tmp_path / "store.json")
    with jsonio.lock_for(path):
        with jsonio.lock_for(path):
            jsonio.atomic_write_json(path, {"nested": True})
            assert jsonio.load_json_store(path, None) == {"nested": True}
    assert jsonio.load_json_store(path, None) == {"nested": True}
    assert [f for f in os.listdir(tmp_path) if f.endswith(".tmp")] == []


def test_a_failed_write_leaves_no_temp_file(tmp_path):
    """`object()` cannot be serialized, so json.dump raises part-way through."""
    path = str(tmp_path / "store.json")
    with pytest.raises(TypeError):
        jsonio.atomic_write_json(path, {"bad": object()})
    assert [f for f in os.listdir(tmp_path) if f.endswith(".tmp")] == []


def test_reading_a_missing_store_creates_nothing(tmp_path):
    """A read must not mutate the directory — not even a lock sidecar."""
    assert jsonio.load_json_store(str(tmp_path / "absent.json"), "DEFAULT") == "DEFAULT"
    assert os.listdir(tmp_path) == []


def test_the_lock_sidecar_sits_beside_its_store(tmp_path):
    path = str(tmp_path / "store.json")
    jsonio.atomic_write_json(path, {"a": 1})
    assert sorted(os.listdir(tmp_path)) == ["store.json", "store.json.lock"]


# ---------------------------------------------------------------------------
# 7. R6-BE-2: project.json — the one store whose cycle held no lock
# ---------------------------------------------------------------------------
# Every other writer-owned store reads under `lock_for`. The manifest did not,
# and `save()` wrote its whole in-memory copy — so a run that loaded a manifest
# minutes before (an analyze holds one for exactly that long) stamped out any
# field someone else changed in between. Holding the lock across the analyze
# instead is not the fix: the desk polls project.json every second, so that
# starves the writer's own UI for the length of a model run. The write has to
# merge.


def _manifest(tmp_path, name="proj"):
    src = tmp_path / "s.fountain"
    src.write_text("INT. ONE - DAY\n\nA.\n\nCUT TO:\n\nINT. TWO - DAY\n\nB.\n",
                   encoding="utf-8")
    return ProjectManifest.create(str(tmp_path / name), str(src))


def test_a_stale_snapshot_cannot_revert_a_field_it_never_touched(tmp_path):
    """Two writers, two different fields. The older copy may change its own
    field; it must not carry the other one backwards."""
    m = _manifest(tmp_path)
    stale = ProjectManifest.load(m.project_dir)     # read before the settings sync
    live = ProjectManifest.load(m.project_dir)
    live.server_url = "http://127.0.0.1:9999"
    live.api_key = "rotated"
    live.save()

    stale.model_id = "somewhere-else"               # a different field entirely
    stale.save()

    after = ProjectManifest.load(m.project_dir)
    assert after.model_id == "somewhere-else"
    assert after.server_url == "http://127.0.0.1:9999", (
        "a stale save reverted a settings sync that landed while it was running")
    assert after.api_key == "rotated"


def test_a_finished_analyze_does_not_unreset_a_reparse(tmp_path):
    """The exact shape from the audit: a re-parse resets `parse` to pending
    while an analyze run is in flight, and the analyze's final stamp used to
    write the whole document from its pre-reparse copy — restoring
    `parse: complete` and reporting a run built from a superseded source as
    done."""
    from screenplay_studio.manifest import StageStatus
    m = _manifest(tmp_path)
    m.mark_complete("parse")
    runner = ProjectManifest.load(m.project_dir)    # the analyze, minutes ago

    reparse = ProjectManifest.load(m.project_dir)
    reparse.stages["parse"] = StageStatus()         # re-parse queued
    reparse.save()

    runner.stages["analyze"] = StageStatus(status="complete")
    runner.save()

    after = ProjectManifest.load(m.project_dir)
    assert after.stage("analyze").status == "complete"
    assert after.stage("parse").status == "pending", (
        "a superseded snapshot stamped the re-parse's reset back to complete")


_HAMMER_MANIFEST = textwrap.dedent(
    """
    import sys, time
    from screenplay_studio.manifest import ProjectManifest, StageStatus

    d, worker, rounds, start_at = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4])
    while time.time() < start_at:
        time.sleep(0.001)
    for k in range(rounds):
        m = ProjectManifest.load(d)
        m.stages[worker] = StageStatus(status="complete", output_paths={"k": str(k)})
        m.save()
    """
)


def test_four_processes_stamping_the_manifest_lose_no_stage(tmp_path):
    """Real processes, one project directory — the CLI and the webapp are a
    supported pairing, and an in-process test cannot see it."""
    import json
    m = _manifest(tmp_path)
    workers, rounds = 4, 20
    start_at = time.time() + 1.5
    procs = [_spawn(_HAMMER_MANIFEST, m.project_dir, f"w{i}", str(rounds), repr(start_at))
             for i in range(workers)]
    failures = []
    for i, proc in enumerate(procs):
        _out, err = proc.communicate(timeout=CHILD_TIMEOUT)
        if proc.returncode != 0:
            failures.append(f"worker {i} exited {proc.returncode}: {err.strip()[-400:]}")
    assert not failures, "child processes failed:\n" + "\n".join(failures)

    with open(m.manifest_path, encoding="utf-8") as f:
        stages = json.load(f)["stages"]
    missing = [f"w{i}" for i in range(workers) if f"w{i}" not in stages]
    assert not missing, f"lost stage writes: {missing} never reached the manifest"


def test_a_damaged_manifest_answers_store_damage_not_a_bad_request(tmp_path):
    """`load` read through a bare `open()`, so a torn project.json raised
    JSONDecodeError — a ValueError — and the generic 400 handler told the writer
    *their* request was bad. It is the store that is damaged, which is the 503
    answer every other store already gets."""
    import screenplay_studio.webapp_server as webapp_server

    m = _manifest(tmp_path, name="proj")
    with open(m.manifest_path, "w", encoding="utf-8") as f:
        f.write('{"title": "truncated by a power cut", "st')

    with pytest.raises(jsonio.StoreUnreadable):
        ProjectManifest.load(m.project_dir)

    monkey_projects = tmp_path / "webapp_projects"
    monkey_projects.mkdir()
    os.replace(m.project_dir, os.path.join(str(monkey_projects), "proj"))
    webapp_server.PROJECTS_DIR = str(monkey_projects)
    webapp_server.app.config["TESTING"] = True
    resp = webapp_server.app.test_client().get("/api/projects/proj")
    assert resp.status_code == 503, (
        f"a damaged manifest answered {resp.status_code}: {resp.get_json()}")
    assert resp.get_json().get("unreadable") is True


def _analysed_project(tmp_path, name="proj", server_url=None):
    """A project whose analyze stage is COMPLETE, so the report routes get past
    their stage gate and actually read `report.findings.json`."""
    import json

    import screenplay_studio.webapp_server as webapp_server
    m = _manifest(tmp_path, name=name)
    if server_url:
        # create() snapshots nothing from CONFIG — `server_url` is a manifest
        # field with a hard default (`manifest.py:78`), and `_make_client`
        # (`webapp_server.py:739`) reads the manifest, not the CONFIG. Set it
        # where the request will actually look.
        m.server_url = server_url
        m.save()
    from screenplay_parser import parse_screenplay
    parse_screenplay(str(m.source_path)).save(m.parsed_path)
    from screenplay_studio.revision import ensure_working
    ensure_working(m)
    m.mark_complete("parse")
    m.mark_complete("analyze")
    with open(m.report_findings_path, "w", encoding="utf-8") as f:
        json.dump({"findings": [], "logline": "x", "coverage": {}}, f)
    webapp_server.PROJECTS_DIR = str(os.path.dirname(m.project_dir))
    webapp_server.app.config["TESTING"] = True
    return m, webapp_server.app.test_client()


def test_a_damaged_report_answers_store_damage_not_a_bad_request(tmp_path):
    """R6-BE-7's residual, and the same contract as the manifest test above.

    `_load_report_sanitized` read through a bare `open()` + `json.load`, so a
    torn report raised JSONDecodeError — a ValueError — and the app-wide
    ValueError handler answered 400 with the parser's own sentence. The writer is
    told their REQUEST was bad, about their damaged file, and `docs/` calls the
    damage the 503 answer every other writer-owned store already gets.
    """
    m, client = _analysed_project(tmp_path)
    with open(m.report_findings_path, "w", encoding="utf-8") as f:
        f.write('{"findings": [{"issue": "truncu')

    resp = client.get(f"/api/projects/{os.path.basename(m.project_dir)}/report")
    assert resp.status_code == 503, (
        f"a damaged report answered {resp.status_code}: {resp.get_json()}")
    body = resp.get_json()
    assert body.get("unreadable") is True, body
    assert "findings" not in body, (
        "a damaged report was served as an empty one — the writer would read a "
        "torn file as a clean script")


def test_a_missing_report_answers_404_not_a_500(tmp_path):
    """The same route, the other missing fact: analyze says complete, the file
    is gone. FileNotFoundError escaped the view and came back as 'Unexpected
    error: [Errno 2] No such file or directory: ...' with a server path in it."""
    m, client = _analysed_project(tmp_path)
    os.remove(m.report_findings_path)

    resp = client.get(f"/api/projects/{os.path.basename(m.project_dir)}/report")
    assert resp.status_code == 404, (
        f"a missing report answered {resp.status_code}: {resp.get_data(as_text=True)[:200]}")
    assert "Errno" not in resp.get_data(as_text=True), resp.get_json()


def test_a_damaged_report_still_degrades_the_rewrite_rather_than_failing(tmp_path, mock_server):
    """The one caller that CHOOSES to swallow damage, kept on purpose.

    `/rewrite` grounds a note in the finding it answers, and its comment says a
    missing or stale report degrades to an ungrounded rewrite instead of failing.
    Making the reader honest (above) must not turn that best-effort path into a
    503, so its catch names the damage now instead of catching it by accident
    via ValueError.
    """
    m, client = _analysed_project(tmp_path, server_url=mock_server)
    with open(m.report_findings_path, "w", encoding="utf-8") as f:
        f.write('{"findings": [{"issue": "truncu')

    resp = client.post(f"/api/projects/{os.path.basename(m.project_dir)}/rewrite",
                       json={"scene_number": 1, "finding_index": 0})
    assert resp.status_code == 200, (
        f"a damaged report broke the rewrite instead of degrading it: "
        f"{resp.status_code} {resp.get_json()}")
    assert resp.get_json().get("replacements") is not None



# ---------------------------------------------------------------------------
# 9. writer_profile.json — R6-BE-4, across processes
# ---------------------------------------------------------------------------

_HAMMER_PROFILE = textwrap.dedent(
    """
    import sys, time
    from screenplay_cowriter import memory as mem

    path, rounds, start_at, text = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    while time.time() < start_at:
        time.sleep(0.001)
    for _ in range(rounds):
        # A FRESH instance per turn, which is what the webapp does per request —
        # the snapshot is read again each time, exactly as it is in production.
        mem.WriterMemory.load(path).observe(text, "idea", False, None)
    """
)


def test_two_processes_observing_one_profile_lose_no_turn(tmp_path):
    """Sameer's relationship memory is writer-level, so the CLI and the webapp
    both write `writer_profile.json` — a supported pairing per AGENTS.md.

    Its only lock was a module-level `threading.RLock`, which cannot serialize
    two processes at all, and `save()` wrote a whole in-memory snapshot. So every
    turn one process saved reverted whatever the other had just learned.
    """
    import json
    path = str(tmp_path / "writer_profile.json")
    workers, rounds = 2, 10
    start_at = time.time() + 1.5
    texts = ["just tell me straight what's wrong", "I'd like a lot more detail, please"]
    procs = [_spawn(_HAMMER_PROFILE, path, str(rounds), repr(start_at), texts[i])
             for i in range(workers)]
    failures = []
    for i, proc in enumerate(procs):
        _out, err = proc.communicate(timeout=CHILD_TIMEOUT)
        if proc.returncode != 0:
            failures.append(f"worker {i} exited {proc.returncode}: {err.strip()[-400:]}")
    assert not failures, "child processes failed:\n" + "\n".join(failures)

    with open(path, encoding="utf-8") as f:
        profile = json.load(f)
    assert profile["meta"]["total_turns_observed"] == workers * rounds, (
        f"{workers}x{rounds} turns were observed but the profile counts "
        f"{profile['meta']['total_turns_observed']}")
    # Both writers' signals survived, not just the last process to save.
    dims = profile["dimensions"]
    for dim in ("directness", "detail_level"):
        ev = dims[dim]["evidence"]
        assert ev["pos"] + ev["neg"] == rounds, (
            f"'{dim}' should hold {rounds} bumps from its own writer, got {ev}")
