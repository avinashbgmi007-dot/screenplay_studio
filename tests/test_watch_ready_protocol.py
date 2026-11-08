"""Gap 37: a visible inbox filename is not a producer-completion signal.

The readiness sidecar and all content are synthetic files under tmp_path. No
real screenplay, network share, or model server is used.
"""
from __future__ import annotations

import os

from screenplay_studio import watch as watch_mod
from screenplay_studio.watch import process_pending


class _NoopOrchestrator:
    def __init__(self, manifest):
        self.manifest = manifest

    def run_parse(self):
        pass

    def run_analyze(self, **kwargs):
        pass


def _paths(tmp_path):
    watch = tmp_path / "inbox"
    projects = tmp_path / "projects"
    watch.mkdir()
    return watch, projects


def test_unmarked_source_is_reported_pending_and_left_untouched(tmp_path, monkeypatch):
    watch, projects = _paths(tmp_path)
    source = watch / "draft.fountain"
    source.write_bytes(b"FIRST HALF\n")
    called = []
    monkeypatch.setattr(watch_mod, "Orchestrator", lambda *_: called.append(True))

    results = process_pending(str(watch), str(projects), "http://127.0.0.1:9")

    assert results == [{
        "filename": "draft.fountain", "ok": False, "pending": True,
        "project": None,
        "error": "waiting for a .ready completion marker; source remains in the inbox",
        "filed": None,
    }]
    assert source.read_bytes() == b"FIRST HALF\n"
    assert called == []
    assert list(projects.iterdir()) == []
    assert not (watch / "done").exists()


def test_open_writer_is_not_claimed_until_it_publishes_ready_marker(tmp_path, monkeypatch):
    watch, projects = _paths(tmp_path)
    source = watch / "still-writing.fountain"
    with open(source, "wb") as writer:
        writer.write(b"FIRST HALF\n")
        writer.flush()
        first = process_pending(str(watch), str(projects), "unused")
        assert first[0]["pending"] is True
        writer.write(b"SECOND HALF\n")
        writer.flush()
        second = process_pending(str(watch), str(projects), "unused")
        assert second[0]["pending"] is True

    monkeypatch.setattr(watch_mod, "Orchestrator", _NoopOrchestrator)
    (watch / "still-writing.fountain.ready").touch()
    result = process_pending(str(watch), str(projects), "unused")[0]

    expected = b"FIRST HALF\nSECOND HALF\n"
    assert result["ok"] is True
    assert (watch / result["filed"]).read_bytes() == expected
    project_source = projects / result["project"] / "source.fountain"
    assert project_source.read_bytes() == expected
    assert not (watch / "still-writing.fountain.ready").exists()


def test_source_mutated_during_analysis_is_not_marked_done(tmp_path, monkeypatch):
    watch, projects = _paths(tmp_path)
    source = watch / "mutating.fountain"
    source.write_bytes(b"COMPLETE CLAIM\n")
    (watch / "mutating.fountain.ready").touch()
    claimed = []
    real_create = watch_mod.ProjectManifest.create

    def create(project_dir, source_file, title=None):
        claimed.append(source_file)
        return real_create(project_dir, source_file, title=title)

    class MutatingOrchestrator(_NoopOrchestrator):
        def run_parse(self):
            with open(claimed[0], "ab") as writer:
                writer.write(b"LATE APPEND\n")

    monkeypatch.setattr(watch_mod.ProjectManifest, "create", staticmethod(create))
    monkeypatch.setattr(watch_mod, "Orchestrator", MutatingOrchestrator)
    result = process_pending(str(watch), str(projects), "unused")[0]

    assert result["ok"] is False
    assert result["project"] is None
    assert "source changed after it was marked ready" in result["error"]
    assert result["filed"].startswith("failed/")
    assert not list(projects.iterdir()), "partial project from mismatched bytes was left on the shelf"
    filed = watch / result["filed"]
    assert filed.read_bytes() == b"COMPLETE CLAIM\nLATE APPEND\n"
    note = (watch / (result["filed"] + ".error.txt")).read_text(encoding="utf-8")
    assert ".ready" in note


def test_open_or_unclaimable_ready_source_is_reported_pending(tmp_path, monkeypatch):
    watch, projects = _paths(tmp_path)
    source = watch / "open.fountain"
    source.write_bytes(b"READY BUT NOT CLAIMABLE")
    marker = watch / "open.fountain.ready"
    marker.touch()
    monkeypatch.setattr(watch_mod, "_claim", lambda *_args: (None, None, None))

    result = process_pending(str(watch), str(projects), "unused")[0]

    assert result["pending"] is True
    assert "may still be open" in result["error"]
    assert source.read_bytes() == b"READY BUT NOT CLAIMABLE"
    assert marker.exists()


def test_ready_marker_symlink_is_not_followed(tmp_path):
    watch, projects = _paths(tmp_path)
    source = watch / "linked.fountain"
    source.write_bytes(b"LOCAL SOURCE\n")
    external = tmp_path / "external-marker"
    external.write_text("outside marker", encoding="utf-8")
    try:
        os.symlink(external, str(source) + ".ready")
    except (OSError, NotImplementedError) as exc:
        import pytest
        pytest.skip(f"symlink creation is not permitted: {exc}")

    result = process_pending(str(watch), str(projects), "unused")[0]

    assert result["pending"] is True
    assert "symlink" in result["error"]
    assert source.read_bytes() == b"LOCAL SOURCE\n"
    assert not (watch / "done").exists()
