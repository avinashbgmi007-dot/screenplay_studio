"""Gap 39 — `watch --once` printed FAILED and exited 0.

Measured before the fix, with the real CLI:

    $ python -m screenplay_studio.cli watch INBOX --projects-dir P --once
    FAILED: broken.fdx → Parse stage failed: unclosed token: line 2, column 21
    $ echo $?
    0

and on a mixed batch where *nothing* succeeded, still 0. Automation reads exit
status, so a failed import was indistinguishable from a clean one — a Makefile,
a cron job or a CI step would carry on as if the script had been analysed.

The register asked for three things beyond a nonzero code:
  * documented success / partial-failure / fatal semantics,
  * a nonzero result when ANY requested item fails,
  * machine-readable per-file outcomes and recovery paths.

The tests drive the real argparse entry point, not a stub, because the defect
lived in the command function between the batch and the exit.
"""
import json
import subprocess
import sys

import pytest

from screenplay_studio import cli

BROKEN_FDX = '<?xml version="1.0"?>\n<FinalDraft><Content><Paragraph'
GOOD_FOUNTAIN = "INT. ROOM - DAY\n\nA line of action.\n"


@pytest.fixture
def inbox(tmp_path):
    d = tmp_path / "inbox"
    d.mkdir()
    return d


def _run(args, cwd):
    """The real CLI as a subprocess, so the process exit status is what is read.

    Returns (exit_code, stdout, stderr). This is deliberate: asserting on a
    return value would have passed while the PROCESS still exited 0, which is
    precisely the filed defect.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "screenplay_studio.cli", *args],
        cwd=str(cwd), capture_output=True, text=True, timeout=300,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": _repo_root(),
             "SCREENPLAY_STUDIO_DEMO_MODEL": "1"},
    )
    return proc.returncode, proc.stdout, proc.stderr


def _repo_root():
    import pathlib
    return str(pathlib.Path(__file__).resolve().parents[1])


def _watch(directory, projects, extra=()):
    # Existing CLI contract tests submit completed inputs; gap 37 makes that
    # producer assertion explicit with a sibling readiness marker.
    for path in directory.iterdir() if directory.exists() else ():
        if path.suffix.lower() in {".fdx", ".fountain", ".txt", ".md", ".pdf"}:
            path.with_name(path.name + ".ready").touch()
    return ["watch", str(directory), "--projects-dir", str(projects), "--once", *extra]


# ---------------------------------------------------------------------------
# 1. The filed case, at the exit-status level
# ---------------------------------------------------------------------------

def test_a_batch_of_one_failure_exits_nonzero(tmp_path, inbox):
    (inbox / "broken.fdx").write_text(BROKEN_FDX)
    code, out, err = _run(_watch(inbox, tmp_path / "projects"), _repo_root())

    assert "FAILED" in out, "the per-file line should still be printed"
    assert code != 0, "a failed import reported success to the shell"


def test_a_mixed_batch_exits_nonzero(tmp_path, inbox):
    """The register's 'mixed batches' case. A model-less environment makes the
    good file fail at Analyze too, so this asserts on the rule, not the count:
    any failure means a nonzero exit."""
    (inbox / "good.fountain").write_text(GOOD_FOUNTAIN)
    (inbox / "broken.fdx").write_text(BROKEN_FDX)
    code, out, _ = _run(_watch(inbox, tmp_path / "projects"), _repo_root())
    assert "FAILED" in out
    assert code != 0


def test_unmarked_supported_file_reports_pending_and_exits_nonzero(tmp_path, inbox):
    source = inbox / "still-copying.fountain"
    source.write_text(GOOD_FOUNTAIN)
    projects = tmp_path / "projects"
    code, out, err = _run([
        "watch", str(inbox), "--projects-dir", str(projects), "--once", "--json",
    ], _repo_root())

    assert code == cli.WATCH_EXIT_PARTIAL
    assert "PENDING: still-copying.fountain" in out
    assert "PENDING 1 file(s)" in err
    payload = next(json.loads(line) for line in out.splitlines() if line.startswith("{"))
    assert payload["pending"] == 1
    assert payload["failed"] == 0
    assert payload["results"][0]["pending"] is True
    assert source.read_text() == GOOD_FOUNTAIN
    assert projects.exists() and list(projects.iterdir()) == []


def test_an_empty_folder_exits_zero(tmp_path, inbox):
    """The register's 'empty folders' case: cron's normal state is not an error."""
    code, out, _ = _run(_watch(inbox, tmp_path / "projects"), _repo_root())
    assert code == 0, f"an empty inbox is not a failure (stderr: out={out!r})"


def test_a_failure_explains_itself_on_stderr(tmp_path, inbox):
    """A bare nonzero with nothing in the stream is its own trap for whoever
    reads the log at 3am."""
    (inbox / "broken.fdx").write_text(BROKEN_FDX)
    _, _, err = _run(_watch(inbox, tmp_path / "projects"), _repo_root())
    assert "FAILED 1 of 1" in err


# ---------------------------------------------------------------------------
# 2. Documented semantics, asserted as a contract
# ---------------------------------------------------------------------------

def test_the_exit_codes_are_named_constants():
    assert cli.WATCH_EXIT_OK == 0
    assert cli.WATCH_EXIT_PARTIAL == 1
    assert cli.WATCH_EXIT_ERROR == 2


def test_the_batch_code_rule_is_pure_and_its_own_function():
    ok = {"filename": "a.fountain", "ok": True, "project": "A", "error": None}
    bad = {"filename": "b.fdx", "ok": False, "project": None, "error": "parse"}

    assert cli.watch_exit_code([]) == cli.WATCH_EXIT_OK, "empty batch is success"
    assert cli.watch_exit_code([ok]) == cli.WATCH_EXIT_OK
    assert cli.watch_exit_code([ok, ok]) == cli.WATCH_EXIT_OK
    assert cli.watch_exit_code([bad]) == cli.WATCH_EXIT_PARTIAL
    assert cli.watch_exit_code([ok, bad]) == cli.WATCH_EXIT_PARTIAL


def test_pending_input_is_a_partial_batch_not_a_success():
    pending = {"filename": "draft.fountain", "ok": False, "pending": True,
               "project": None, "error": "waiting for marker"}
    assert cli.watch_exit_code([pending]) == cli.WATCH_EXIT_PARTIAL


def test_partial_failure_is_1_and_not_the_usage_code():
    """2 already means 'you asked wrongly' everywhere in this CLI. A retry loop
    that retries on 1 must not also retry on a typo."""
    assert cli.WATCH_EXIT_PARTIAL != cli.WATCH_EXIT_ERROR
    bad = {"filename": "b.fdx", "ok": False, "project": None, "error": "parse"}
    assert cli.watch_exit_code([bad]) != cli.WATCH_EXIT_ERROR


def test_the_semantics_are_documented_next_to_the_code():
    import inspect
    doc = inspect.getsource(cli)
    for token in ("0  every requested file", "1  the batch ran",
                  "2  usage / configuration error"):
        assert token in doc, f"exit semantics are not documented: {token!r}"


# ---------------------------------------------------------------------------
# 3. Machine-readable outcomes
# ---------------------------------------------------------------------------

def test_json_flag_emits_per_file_outcomes(tmp_path, inbox):
    (inbox / "broken.fdx").write_text(BROKEN_FDX)
    code, out, _ = _run(_watch(inbox, tmp_path / "projects", ("--json",)), _repo_root())

    payload = None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("{"):
            payload = json.loads(line)
    assert payload is not None, f"no JSON summary in output:\n{out}"
    assert payload["total"] == 1
    assert payload["failed"] == 1
    assert payload["succeeded"] == 0
    assert payload["ok"] is False
    row = payload["results"][0]
    assert row["filename"] == "broken.fdx"
    assert row["ok"] is False
    assert row["error"], "the recovery path — the actual error — must travel with the outcome"
    assert code == cli.WATCH_EXIT_PARTIAL


def test_json_flag_agrees_with_the_exit_code(tmp_path, inbox):
    """Two sources of truth for the same fact is how dashboards and exit codes
    start disagreeing."""
    code, out, _ = _run(_watch(inbox, tmp_path / "projects", ("--json",)), _repo_root())
    payload = json.loads([ln for ln in out.splitlines() if ln.strip().startswith("{")][-1])
    assert payload["ok"] is (code == cli.WATCH_EXIT_OK)


def test_without_the_flag_no_json_is_printed(tmp_path, inbox):
    """The prose output is a contract too; a stray JSON blob would break it."""
    (inbox / "broken.fdx").write_text(BROKEN_FDX)
    _, out, _ = _run(_watch(inbox, tmp_path / "projects"), _repo_root())
    assert not [ln for ln in out.splitlines() if ln.strip().startswith("{")]


# ---------------------------------------------------------------------------
# 4. An unreadable folder is a configuration error, not a per-file outcome
# ---------------------------------------------------------------------------

def test_a_missing_watch_folder_exits_2(tmp_path):
    missing = tmp_path / "nope"
    code, _, err = _run(_watch(missing, tmp_path / "projects"), _repo_root())
    assert code == cli.WATCH_EXIT_ERROR, f"expected 2 for a bad path, got {code}"
    assert "cannot read the watch folder" in err


def test_a_missing_folder_does_not_claim_a_file_failed(tmp_path):
    """No file was requested of anything, so no file's outcome can be reported."""
    code, out, _ = _run(_watch(tmp_path / "nope", tmp_path / "projects"), _repo_root())
    assert code == cli.WATCH_EXIT_ERROR
    assert "FAILED:" not in out
