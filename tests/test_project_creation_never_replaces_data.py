"""Gap 50 — project creation replaced orphaned source data.

The filed reproduction: a directory with no `project.json` but an existing
`synthetic source.fountain`, run through `cmd_run(..., only='parse')`, treated
as a new project and silently replaced the source with a different input.

Measured through the real CLI before the fix: exit **0**, the message *"Created
new project at '<dir>'."*, the draft gone, and no backup. The web routes were
already safe (they claim a fresh directory, or refuse a damaged one per gap 35);
the invariant lived only in callers, and the CLI had none of it.
"""

import os
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_studio.manifest import ProjectManifest

DRAFT = "Title: The Real Draft\n\nINT. ROOM - NIGHT\n\nMIRA\nFirst line.\n"
OTHER = "Title: Something Else\n\nINT. ROAD - DAY\n\nTOM\nDifferent script.\n"


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


@pytest.fixture
def root():
    return tempfile.mkdtemp()


# ---------- the filed reproduction, end to end ----------

def test_the_cli_does_not_replace_an_orphaned_source(root):
    """The exact filed scenario, through the real entry point."""
    dest = os.path.join(root, "myproject")
    os.makedirs(dest)
    orphan = _write(os.path.join(dest, "source.fountain"), DRAFT)
    newsrc = _write(os.path.join(root, "new.fountain"), OTHER)

    p = subprocess.run(
        [sys.executable, "-m", "screenplay_studio.cli", "run",
         "--project", dest, newsrc, "--only", "parse"],
        capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))),
    )

    with open(orphan, encoding="utf-8") as f:
        assert f.read() == DRAFT, "the writer's draft was replaced"

    assert p.returncode != 0, (
        "creation over existing data must not report success — "
        f"exit was {p.returncode}, stdout {p.stdout!r}")
    assert "Created new project" not in p.stdout
    assert "Nothing was overwritten" in (p.stderr + p.stdout)


def test_the_refusal_names_a_recovery(root):
    """An error that says 'refused' and nothing else is its own trap."""
    dest = os.path.join(root, "p")
    os.makedirs(dest)
    _write(os.path.join(dest, "source.fountain"), DRAFT)
    src = _write(os.path.join(root, "s.fountain"), OTHER)

    with pytest.raises(ValueError) as ei:
        ProjectManifest.create(dest, src)
    msg = str(ei.value)
    assert "source.fountain" in msg, "name the file that is in the way"
    assert "different directory" in msg
    assert "adopted in place" in msg


# ---------- what creation must still allow ----------

def test_creates_in_a_directory_that_does_not_exist(root):
    dest = os.path.join(root, "a", "b", "newproj")
    src = _write(os.path.join(root, "s.fountain"), DRAFT)
    m = ProjectManifest.create(dest, src)
    assert os.path.isfile(m.source_path)
    with open(m.source_path, encoding="utf-8") as f:
        assert f.read() == DRAFT


def test_creates_in_an_existing_empty_directory(root):
    dest = os.path.join(root, "empty")
    os.makedirs(dest)
    src = _write(os.path.join(root, "s.fountain"), DRAFT)
    assert ProjectManifest.create(dest, src).project_dir == dest


def test_creates_where_the_only_file_is_the_staged_upload(root):
    """The web routes stage `_upload.<ext>` inside the claimed directory and
    then call create on it. That must stay legal."""
    dest = os.path.join(root, "web")
    os.makedirs(dest)
    staged = _write(os.path.join(dest, "_upload.fountain"), DRAFT)
    m = ProjectManifest.create(dest, staged)
    assert os.path.isfile(m.source_path)


def test_an_orphan_can_be_adopted_in_place(root):
    """Naming the orphan as the source is the recovery the error offers, so it
    has to work — and before this fix it raised SameFileError."""
    dest = os.path.join(root, "adopt")
    os.makedirs(dest)
    orphan = _write(os.path.join(dest, "source.fountain"), DRAFT)
    m = ProjectManifest.create(dest, orphan)
    assert os.path.isfile(m.manifest_path), "a manifest must now exist"
    with open(m.source_path, encoding="utf-8") as f:
        assert f.read() == DRAFT, "adoption must not alter the bytes"


# ---------- what creation must refuse ----------

def test_refuses_an_orphaned_source(root):
    dest = os.path.join(root, "p")
    os.makedirs(dest)
    _write(os.path.join(dest, "source.fountain"), DRAFT)
    src = _write(os.path.join(root, "s.fountain"), OTHER)
    with pytest.raises(ValueError):
        ProjectManifest.create(dest, src)
    with open(os.path.join(dest, "source.fountain"), encoding="utf-8") as f:
        assert f.read() == DRAFT


def test_refuses_unrelated_data_too(root):
    """Not just scripts: anything in the destination is someone's data."""
    dest = os.path.join(root, "p")
    os.makedirs(dest)
    _write(os.path.join(dest, "notes.md"), "my notes")
    src = _write(os.path.join(root, "s.fountain"), DRAFT)
    with pytest.raises(ValueError):
        ProjectManifest.create(dest, src)
    assert os.path.isfile(os.path.join(dest, "notes.md"))


def test_refuses_a_half_built_project(root):
    """A broken project.json beside a draft is the likeliest real case: an
    interrupted create. Creation must not paper over it."""
    dest = os.path.join(root, "half")
    os.makedirs(dest)
    _write(os.path.join(dest, "project.json"), "{not json")
    _write(os.path.join(dest, "source.fountain"), DRAFT)
    src = _write(os.path.join(root, "s.fountain"), OTHER)
    with pytest.raises(ValueError):
        ProjectManifest.create(dest, src)
    with open(os.path.join(dest, "source.fountain"), encoding="utf-8") as f:
        assert f.read() == DRAFT


# ---------- the atomic claim ----------

def test_the_directory_is_claimed_rather_than_adopted():
    """The helper behind it: an existing directory is not silently reused.

    `makedirs(exist_ok=True)` cannot tell 'I created this' from 'someone else
    did'; the claim has to. Checked at the helper, because the public path
    deliberately permits an *empty* existing directory.
    """
    from screenplay_studio.manifest import _claim_directory
    root = tempfile.mkdtemp()
    fresh = os.path.join(root, "fresh")
    _claim_directory(fresh)
    assert os.path.isdir(fresh)
    nested = os.path.join(root, "x", "y", "z")
    _claim_directory(nested)
    assert os.path.isdir(nested)


def test_a_racing_copy_is_refused_not_clobbered(root):
    """The exclusive install: copy2 replaced silently, 'xb' does not."""
    import screenplay_studio.manifest as man
    dest = os.path.join(root, "race")
    src = _write(os.path.join(root, "s.fountain"), DRAFT)

    real_copyfileobj = man.shutil.copyfileobj

    def racing(src_fh, dst_fh):
        # another process wins between the refusal and the install
        raise FileExistsError("simulated race")
        return real_copyfileobj(src_fh, dst_fh)

    man.shutil.copyfileobj = racing
    try:
        with pytest.raises(ValueError) as ei:
            ProjectManifest.create(dest, src)
        assert "Nothing was overwritten" in str(ei.value)
    finally:
        man.shutil.copyfileobj = real_copyfileobj
