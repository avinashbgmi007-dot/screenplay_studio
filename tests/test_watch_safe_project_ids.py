"""Gap 38: watch imports share the web desk's safe project-ID contract."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import re
import threading

from screenplay_studio import watch as watch_mod
from screenplay_studio.jsonio import claim_project_dir, safe_dir_name, suffixed_id
from screenplay_studio.manifest import ProjectManifest
from screenplay_studio.watch import process_pending


class _NoopOrchestrator:
    def __init__(self, manifest):
        self.manifest = manifest

    def run_parse(self):
        pass

    def run_analyze(self, **kwargs):
        pass


def test_shared_sanitizer_handles_long_mixed_and_pure_unicode_titles():
    long_id = safe_dir_name("A" * 100)
    mixed_id = safe_dir_name("Raatri రాత్రి 1")
    pure_id = safe_dir_name("రాత్రి")

    assert len(long_id) == 64
    assert len(suffixed_id(long_id, 2)) <= 64
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", mixed_id)
    assert "Raatri" in mixed_id
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", pure_id)


def test_pure_unicode_watch_name_keeps_title_and_source_but_uses_safe_id(
    tmp_path, monkeypatch
):
    inbox = tmp_path / "inbox"
    projects = tmp_path / "projects"
    inbox.mkdir()
    filename = "రాత్రి.fountain"
    (inbox / filename).write_text("synthetic screenplay\n", encoding="utf-8")
    (inbox / f"{filename}.ready").touch()
    monkeypatch.setattr(watch_mod, "Orchestrator", _NoopOrchestrator)

    result = process_pending(str(inbox), str(projects), "unused")[0]

    assert result["ok"] is True
    assert result["project"].isascii()
    assert len(result["project"]) <= 64
    manifest = ProjectManifest.load(str(projects / result["project"]))
    assert manifest.title == "రాత్రి"
    assert manifest.source_filename == filename


def test_equivalent_titles_are_claimed_as_distinct_safe_projects(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"
    projects = tmp_path / "projects"
    inbox.mkdir()
    for filename in ("café.fountain", "cafe.txt"):
        (inbox / filename).write_text("synthetic screenplay\n", encoding="utf-8")
        (inbox / f"{filename}.ready").touch()
    monkeypatch.setattr(watch_mod, "Orchestrator", _NoopOrchestrator)

    results = process_pending(str(inbox), str(projects), "unused")

    assert len(results) == 2
    assert all(result["ok"] for result in results)
    assert {result["project"] for result in results} == {"cafe", "cafe_2"}
    for result in results:
        manifest = ProjectManifest.load(str(projects / result["project"]))
        assert manifest.title == result["filename"].rsplit(".", 1)[0]
        assert manifest.source_filename == result["filename"]
        assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", result["project"])


def test_concurrent_claims_with_same_long_base_never_share_directory(tmp_path):
    projects = tmp_path / "projects"
    barrier = threading.Barrier(2)

    def claim():
        barrier.wait()
        return claim_project_dir(str(projects), "x" * 64)

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: claim(), range(2)))

    ids = {project_id for project_id, _ in claims}
    assert ids == {"x" * 64, "x" * 62 + "_2"}
    assert len({path for _, path in claims}) == 2
    assert all(len(project_id) <= 64 for project_id in ids)
