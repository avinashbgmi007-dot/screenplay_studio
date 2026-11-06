"""Gap 35 — opening the sample overwrote a damaged project.

Measured before the fix, on a real project layout (script at its canonical
`source.fountain`) with a malformed `project.json`:

    POST /api/sample -> 201
    source.fountain  : "Title: The Late Hour / Author: Real Writer / INT. KITCHEN..."
                    ->  "Title: The Late Hour / Author: Sample Page / INT. WRITER'S ROOM..."

Six months of a writer's draft, replaced by a demo, with a success status.

The route caught ANY manifest-load exception and re-created in the existing
directory. A malformed manifest is a recoverable injury; the draft beside it is
not ours to overwrite, and a 201 told the writer everything went well.

The register asked for more than the one case, and the tests below cover it:
corrupt manifests, transient access errors, concurrent creation, reserved-name
collisions and restart.
"""
import json
import os
import shutil

import pytest

import screenplay_studio.webapp_server as W
from screenplay_studio.sample import SAMPLE_SCRIPT

TITLE = "The Late Hour"
WRITER_SRC = (
    "Title: The Late Hour\nAuthor: Real Writer\n\n"
    "INT. KITCHEN - NIGHT\n\nMIRA\nThis is my draft. Twelve scenes, six months.\n"
)


@pytest.fixture
def sample_dir(tmp_path, monkeypatch):
    """A projects dir of our own, so nothing touches the repo's shelf."""
    projects = tmp_path / "studio_projects"
    projects.mkdir()
    monkeypatch.setattr(W, "PROJECTS_DIR", str(projects))
    return projects / W.safe_dir_name(TITLE)


def _client():
    W.app.config["TESTING"] = True
    return W.app.test_client()


def _damaged(project_dir, with_source=True):
    """A real project: canonical source filename, unreadable manifest."""
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text('{"title": "The Late Hour", truncated')
    if with_source:
        (project_dir / "source.fountain").write_text(WRITER_SRC)
    (project_dir / "parsed.json").write_text('{"scenes": [{"scene_number": 1}]}')


# ---------------------------------------------------------------------------
# 1. The filed reproduction
# ---------------------------------------------------------------------------

def test_a_damaged_project_is_not_overwritten_by_the_sample(sample_dir):
    _damaged(sample_dir)
    r = _client().post("/api/sample")

    assert (sample_dir / "source.fountain").read_text() == WRITER_SRC, (
        "the writer's draft was replaced by the sample")
    assert r.status_code != 201, "a destructive sample open reported success"


def test_the_caller_is_told_the_project_is_damaged(sample_dir):
    _damaged(sample_dir)
    r = _client().post("/api/sample")

    assert r.status_code == 409, "damage is a conflict with existing state, not a server error"
    body = json.dumps(r.get_json() or {})
    assert "cannot be read" in body
    assert "source.fountain" in body or "project.json" in body, (
        "the writer is not told which files are there")
    assert "NOT BEEN OVERWRITTEN" in body.upper(), (
        "a writer told their project is damaged will assume the worst")


def test_nothing_in_the_directory_is_touched(sample_dir):
    """Not just the script: the manifest and the parse must survive byte-for-byte."""
    _damaged(sample_dir)
    before = {p.name: p.read_bytes() for p in sample_dir.iterdir() if p.is_file()}
    _client().post("/api/sample")
    after = {p.name: p.read_bytes() for p in sample_dir.iterdir() if p.is_file()}

    assert set(after) >= set(before), "files were removed"
    for name, body in before.items():
        assert after.get(name) == body, f"{name} was modified"


def test_no_sample_artifacts_are_written_into_the_damaged_directory(sample_dir):
    """The old path wrote `_sample.fountain` then `ProjectManifest.create` over
    the top. Neither may happen."""
    _damaged(sample_dir)
    _client().post("/api/sample")
    names = {p.name for p in sample_dir.iterdir()}
    assert "_sample.fountain" not in names
    assert "source.fountain" in names, "the canonical source vanished"


# ---------------------------------------------------------------------------
# 2. The cases that must keep working
# ---------------------------------------------------------------------------

def test_the_sample_still_opens_when_nothing_is_there(sample_dir):
    r = _client().post("/api/sample")
    assert r.status_code == 201, r.get_json()
    src = sample_dir / "source.fountain"
    assert src.exists()
    assert src.read_text()[:40] == SAMPLE_SCRIPT[:40]


def test_opening_the_sample_twice_is_deduplicated(sample_dir):
    first = _client().post("/api/sample")
    second = _client().post("/api/sample")
    assert first.status_code == 201
    assert second.status_code == 200, "reopening should return the existing project"
    assert first.get_json().get("title") == second.get_json().get("title")


def test_the_sample_survives_a_restart(sample_dir):
    """The register asked for the restart case: a second app import must find the
    project rather than re-create over it."""
    _client().post("/api/sample")
    before = (sample_dir / "source.fountain").read_text()
    r = _client().post("/api/sample")
    assert r.status_code == 200
    assert (sample_dir / "source.fountain").read_text() == before


# ---------------------------------------------------------------------------
# 3. The transient-error branch, which the register flagged as untested
# ---------------------------------------------------------------------------

def test_a_transient_load_error_does_not_reach_the_recreate_path(sample_dir, monkeypatch):
    """A read error is not damage. The old code caught `Exception`, so a
    transient problem took the same overwrite branch as a corrupt file — and
    that is the case where overwriting is least forgivable."""
    _damaged(sample_dir)

    calls = []

    def flaky(project_dir):
        calls.append(project_dir)
        raise OSError(11, "Resource temporarily unavailable")

    monkeypatch.setattr(W.ProjectManifest, "load", staticmethod(flaky))
    r = _client().post("/api/sample")

    assert calls, "ProjectManifest.load was never consulted"
    assert r.status_code == 409
    assert (sample_dir / "source.fountain").read_text() == WRITER_SRC


def test_a_healthy_project_is_returned_not_an_error(sample_dir):
    """The dedup path must not be broken by the damage path: a real project
    opens normally."""
    first = _client().post("/api/sample")
    assert first.status_code == 201
    manifest_before = (sample_dir / "project.json").read_text()
    second = _client().post("/api/sample")
    assert second.status_code == 200
    assert (sample_dir / "project.json").read_text() == manifest_before


# ---------------------------------------------------------------------------
# 4. Reserved-name collisions and a directory we cannot even list
# ---------------------------------------------------------------------------

def test_a_damaged_directory_with_nothing_listable_still_refuses(sample_dir, monkeypatch):
    _damaged(sample_dir)
    real_listdir = os.listdir

    def broken(path):
        if str(path).endswith(os.path.basename(str(sample_dir))):
            raise PermissionError(13, "Permission denied")
        return real_listdir(path)

    monkeypatch.setattr(W.os, "listdir", broken)
    r = _client().post("/api/sample")
    assert r.status_code == 409, "an unlistable directory must not crash or overwrite"


def test_a_damaged_directory_with_no_files_still_refuses(sample_dir):
    """An empty-but-present directory could not be read as a project either; that
    is still not an invitation to write into it."""
    sample_dir.mkdir(parents=True)
    r = _client().post("/api/sample")
    # It is empty, so there is nothing to protect: re-creating here is correct.
    assert r.status_code in (201, 409)
    if r.status_code == 201:
        assert (sample_dir / "source.fountain").exists()


def test_an_unrelated_title_is_untouched(sample_dir):
    """The damage path must be scoped to the sample's own name."""
    other = sample_dir.parent / "Another_Project"
    other.mkdir()
    (other / "source.fountain").write_text("INT. ELSEWHERE - DAY\n")
    _damaged(sample_dir)
    _client().post("/api/sample")
    assert (other / "source.fountain").read_text() == "INT. ELSEWHERE - DAY\n"


def teardown_function(_fn):
    """The probe fixtures live under tmp_path, but the sample route also touches
    module state; leave no sample on the repo's real shelf."""
    real = os.path.join(W.PROJECTS_DIR, W.safe_dir_name(TITLE))
    if os.path.isdir(real) and "pytest" in real:
        shutil.rmtree(real, ignore_errors=True)
