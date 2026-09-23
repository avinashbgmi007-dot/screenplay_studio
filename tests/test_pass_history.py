"""`pass_history.json` — the writer's revision arc, kept beyond one generation.

Spec §15.4: the arrival strip only remembers the LAST pass. The arc ("62 -> 19
open over five passes") needs every pass, so this is an append-only store of the
numbers the analyze path already computes.

The contract this file pins is the one every store in this repo owes:
  * append twice reads back BOTH, in chronological order;
  * two processes appending at the same instant keep both entries (the lock is
    held across the READ, and it crosses processes — an in-process lock would
    pass this test while the CLI + webapp pair lost writes);
  * a damaged store raises StoreUnreadable instead of reading as "no history",
    because the next append would then silently overwrite the only copy;
  * `open` is the ledger's own arithmetic (still_present + unknown from the
    findings-status summary), never a second definition of the word.
"""
import os
import subprocess
import sys
import textwrap
import time
from types import SimpleNamespace

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from screenplay_studio import jsonio, pass_history  # noqa: E402

CHILD_TIMEOUT = 240


def _m(tmp_path):
    return SimpleNamespace(project_dir=str(tmp_path))


STATUSES = {
    "findings": [],
    "summary": {"addressed": 7, "still_present": 12, "unknown": 3},
}


def test_append_then_load_returns_the_documented_entry_shape(tmp_path):
    pass_history.append_pass(_m(tmp_path), STATUSES, failed_categories=["Plot"])
    passes = pass_history.load_passes(_m(tmp_path))
    assert len(passes) == 1
    entry = passes[0]
    assert set(entry) == {"ts", "total", "open", "addressed", "failed_categories"}
    assert entry["total"] == 22           # 7 + 12 + 3, the summary's whole ledger
    assert entry["open"] == 15            # still_present + unknown
    assert entry["addressed"] == 7
    assert entry["failed_categories"] == ["Plot"]
    assert entry["ts"] == pytest.approx(time.time(), abs=60)


def test_entries_read_back_in_chronological_order(tmp_path):
    m = _m(tmp_path)
    pass_history.append_pass(m, STATUSES)
    pass_history.append_pass(m, {"findings": [], "summary":
                                 {"addressed": 20, "still_present": 2, "unknown": 0}})
    passes = pass_history.load_passes(m)
    assert [p["open"] for p in passes] == [15, 2], "the arc reads oldest first"
    assert passes[0]["ts"] <= passes[1]["ts"]


def test_no_history_yet_reads_as_no_passes(tmp_path):
    assert pass_history.load_passes(_m(tmp_path)) == []


def test_a_damaged_store_says_so_instead_of_reading_empty(tmp_path):
    """An empty read here is the destructive answer: the next append would
    overwrite the only copy of the writer's history."""
    m = _m(tmp_path)
    with open(pass_history.path(m), "w", encoding="utf-8") as f:
        f.write("{not json")
    with pytest.raises(jsonio.StoreUnreadable):
        pass_history.load_passes(m)
    with pytest.raises(jsonio.StoreUnreadable):
        pass_history.append_pass(m, STATUSES)
    assert os.path.exists(pass_history.path(m)), "a refused append must not replace the file"


def test_an_empty_summary_still_records_the_pass(tmp_path):
    """A pass that produced no findings is a real point on the arc (0 -> 0), not
    a skipped write — convergence is a claim about the sequence."""
    m = _m(tmp_path)
    pass_history.append_pass(m, {"findings": [], "summary": {}})
    assert pass_history.load_passes(m) == [
        {"ts": pytest.approx(time.time(), abs=60), "total": 0, "open": 0,
         "addressed": 0, "failed_categories": []}]


_APPEND = textwrap.dedent(
    """
    import sys, time
    from types import SimpleNamespace
    from screenplay_studio import pass_history

    project_dir, worker, start_at = sys.argv[1], sys.argv[2], float(sys.argv[3])
    m = SimpleNamespace(project_dir=project_dir)
    # start-gate: both children append at the same instant, so the windows
    # overlap instead of the children politely queueing up.
    while time.time() < start_at:
        time.sleep(0.001)
    pass_history.append_pass(m, {"findings": [], "summary": {
        "addressed": 0, "still_present": {"w0": 40, "w1": 41}[worker], "unknown": 0}})
    """)


def _child_env():
    env = dict(os.environ)
    parts = [REPO_ROOT] + [p for p in sys.path if p]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env["PYTHONUNBUFFERED"] = "1"
    return env


def test_two_processes_appending_at_once_keep_both_entries(tmp_path):
    """Real child processes: the append is a load-modify-write, and a lock that
    only lives inside one process cannot serialize two of them. Without the OS
    byte-range lock across the read, the second writer loads the pre-append list
    and renames it over the first's file — one entry survives, silently."""
    start_at = time.time() + 1.5
    procs = [
        subprocess.Popen([sys.executable, "-c", _APPEND, str(tmp_path), f"w{i}", repr(start_at)],
                         cwd=REPO_ROOT, env=_child_env(),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for i in range(2)
    ]
    failures = []
    for i, proc in enumerate(procs):
        _out, err = proc.communicate(timeout=CHILD_TIMEOUT)
        if proc.returncode != 0:
            failures.append(f"child {i} exited {proc.returncode}: {err.strip()[-400:]}")
    assert not failures, "child processes failed:\n" + "\n".join(failures)

    passes = pass_history.load_passes(_m(tmp_path))
    assert sorted(p["open"] for p in passes) == [40, 41], (
        "both appends must survive — a lost entry is the arc lying to the writer")
    assert [f for f in os.listdir(tmp_path) if f.endswith(".tmp")] == [], (
        "a temp file was left behind")
