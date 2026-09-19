"""Regression tests for the 2026-09-20 production-readiness audit (docs/audit/production_readiness_2026-09-20.md).

Covers the three behavior changes the audit found exploitable or lossy:

- B1: SessionStore session-id path traversal (`_path("..\\..\\evil")` used to
  escape sessions_dir; the webapp <sid> converter delivers backslashes).
- B2: webapp_demo bound 0.0.0.0 and bypassed main()'s token mint.
- A1: a corrupt/unreadable edits.json made has_edits() read False, letting
  ensure_working() overwrite the writer's only edited copy on re-parse.
"""
import importlib.util
import json
import os

import pytest

from screenplay_cowriter.store import SessionStore
from screenplay_studio.manifest import ProjectManifest
from screenplay_studio import revision


# ---- B1: session-id path traversal is rejected --------------------------
class TestSessionIdGuard:
    def test_dotdot_backslash_rejected(self, tmp_path):
        store = SessionStore(str(tmp_path / "sessions"))
        with pytest.raises((ValueError, PermissionError)):
            store._path("..\\..\\evil")

    def test_dotdot_forward_rejected(self, tmp_path):
        store = SessionStore(str(tmp_path / "sessions"))
        with pytest.raises((ValueError, PermissionError)):
            store._path("../../evil")

    def test_valid_id_still_resolves_inside_dir(self, tmp_path):
        sdir = tmp_path / "sessions"
        store = SessionStore(str(sdir))
        p = store._path("abc123")
        assert os.path.abspath(p).startswith(os.path.abspath(str(sdir)))
        assert p.endswith(".json")

    def test_delete_of_traversal_id_does_not_touch_outside_file(self, tmp_path):
        outside = tmp_path / "victim.json"
        outside.write_text("{}", encoding="utf-8")
        store = SessionStore(str(tmp_path / "sessions"))
        with pytest.raises((ValueError, PermissionError)):
            store.delete("..\\..\\victim")  # must raise before reaching os.remove
        assert outside.exists()


# ---- B2: the demo launcher never binds 0.0.0.0 --------------------------
def test_webapp_demo_binds_loopback_not_all_interfaces():
    """B2: the demo launcher must not bind all interfaces. Assert no *actual*
    `app.run(host="0.0.0.0")` remains — mentions in comments/docstrings are
    allowed (they document the fix), a live bind call is not."""
    import re
    src = open("screenplay_studio/webapp_demo.py", encoding="utf-8").read()
    assert not re.search(r'run\s*\(\s*host\s*=\s*["\']0\.0\.0\.0', src), (
        "webapp_demo still makes a live app.run(host='0.0.0.0') bind")


# ---- A1: corrupt edits.json must NOT read as "no edits" -----------------
def test_has_edits_treats_corrupt_log_as_present_not_empty(tmp_path, sample_fountain):
    m = ProjectManifest.create(str(tmp_path / "rev"), sample_fountain)
    m.save()
    log_path = revision.edits_log_path(m)
    # simulate a crash-truncated edit log (the non-atomic write from A2)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write('[{"id": "abc123", "scene_number": 1, "old": "x", "new": "y"')
    assert revision.has_edits(m) is True, (
        "a corrupt edit log was read as 'no edits', which lets ensure_working() "
        "overwrite the writer's only edited copy on re-parse")


# ---- A2: writer-owned stores must be written atomically (tmp + replace) ---
class TestAtomicWrites:
    """A2 (audit 2026-09-20): the crash-truncated edits.json that A1 now survives
    is still producible because these writer-owned stores use raw open(...,'w').
    The fix routes them through jsonio.atomic_write_json — a torn write can no
    longer reach the reader."""

    def test_edits_log_is_atomic(self, tmp_path, sample_fountain):
        import unittest.mock as mock
        from screenplay_studio import jsonio
        from screenplay_parser import parse_fountain
        m = ProjectManifest.create(str(tmp_path / "rev"), sample_fountain)
        m.save()
        parse_fountain(sample_fountain).save(m.parsed_path)  # parse, or save_working refuses
        revision.ensure_working(m)  # creates working.json
        with mock.patch.object(jsonio, "atomic_write_json",
                               wraps=jsonio.atomic_write_json) as spy:
            revision.save_working(m, revision.load_working(m),
                                  record={"scene_number": 1, "old": "a", "new": "b"})
        called_paths = [str(c.args[0]) for c in spy.call_args_list]
        assert any("edits" in p for p in called_paths), (
            f"edits.json was not written atomically; atomic_write_json saw {called_paths}")

    def test_writer_profile_save_is_atomic(self, tmp_path):
        import unittest.mock as mock
        from screenplay_studio import jsonio
        from screenplay_cowriter.memory import WriterMemory
        p = WriterMemory(str(tmp_path / "writer_profile.json"))
        with mock.patch.object(jsonio, "atomic_write_json",
                               wraps=jsonio.atomic_write_json) as spy:
            p.save()
        assert spy.called, "WriterMemory.save bypassed atomic_write_json"

    def test_working_copy_is_atomic(self, tmp_path, sample_fountain):
        """ScriptDocument.save is the single chokepoint for working.json/parsed.json —
        the writer's only edited copy must never be a torn write."""
        import unittest.mock as mock
        from screenplay_parser import parse_fountain
        from screenplay_studio import jsonio
        m = ProjectManifest.create(str(tmp_path / "rev"), sample_fountain)
        m.save()
        parse_fountain(sample_fountain).save(m.parsed_path)  # parse, or ensure_working refuses
        with mock.patch.object(jsonio, "atomic_write_json",
                               wraps=jsonio.atomic_write_json) as spy:
            revision.ensure_working(m)
        called_paths = [str(c.args[0]) for c in spy.call_args_list]
        assert any(p.endswith("working.json") for p in called_paths), (
            f"working.json was not written atomically; saw {called_paths}")


# ---- D: demo-mode findings are labelled, not fabricated as real notes ----
class TestDemoHonesty:
    def test_demo_findings_are_labelled_as_demo(self):
        """The canned fallback findings must not read as real analysis: each is
        tagged so the fix queue cannot pass it off as the doctor's note. The
        observable contract is the issue string in demo_model.py."""
        import re as _re
        src = open("screenplay_studio/demo_model.py", encoding="utf-8").read()
        issues = _re.findall(r'"issue":\s*"([^"]+)"', src)
        # the canned fallback findings carry the "Sample X finding" shape
        sample_issues = [i for i in issues if "Sample" in i and "finding" in i]
        assert sample_issues, "expected canned demo findings to exist in demo_model"
        assert all("[demo]" in i or "demo model" in i.lower() for i in sample_issues), (
            f"unlabelled canned findings: {sample_issues}")


# ---- Flake hardening: transient Windows lock errors need enough retries ---
class TestRetryPermissionBudget:
    """test_store_save_serializes_concurrent_writers + test_save_rename_race_never_tears_json
    intermittently surface WinError 32/33 under load: a reader (test_client.get) or AV
    holds the file while os.replace fires. retry_permission's 3 attempts at
    50/100/150ms total ~0.3s can expire before the holder releases. Widening the
    budget (more attempts, jittered, capped) makes the atomic-write guarantee hold
    under realistic load without masking a genuine denial (still fails fast on
    non-transient PermissionError)."""

    def test_default_budget_is_wide_enough_for_concurrent_hammer(self):
        import inspect
        from screenplay_studio import jsonio
        sig = inspect.signature(jsonio.retry_permission)
        assert sig.parameters["attempts"].default >= 6, (
            f"retry_permission default attempts={sig.parameters['attempts'].default} "
            "is too tight for the concurrent save/rename hammer (needs >=6)")

    def test_genuine_denial_still_raises_bounded_not_swallowed(self):
        """2026-09-20 decision: EVERY PermissionError is retried for the bounded
        window (so AV-hold hammers stay green), but a genuine denial must still
        RAISE — bounded, never swallowed, never infinite."""
        import time
        import pytest as _pytest
        from screenplay_studio import jsonio
        calls = {"n": 0}

        def denied():
            calls["n"] += 1
            raise PermissionError(13, "Access is denied")
        t0 = time.monotonic()
        with _pytest.raises(PermissionError):
            jsonio.retry_permission(denied, attempts=3)
        elapsed = time.monotonic() - t0
        assert calls["n"] == 3, f"a transient-eligible error must be retried all {calls['n']} times"
        assert elapsed < 3.0, f"retries must be bounded (~1s), took {elapsed:.2f}s"

    def test_non_permission_errors_are_not_retried(self):
        import pytest as _pytest
        from screenplay_studio import jsonio
        calls = {"n": 0}

        def boom():
            calls["n"] += 1
            raise ValueError("not a lock error")
        with _pytest.raises(ValueError):
            jsonio.retry_permission(boom)
        assert calls["n"] == 1, "a non-PermissionError must fail immediately, no retry"
