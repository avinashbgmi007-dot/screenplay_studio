"""Gaps 110 and 111 — the CLI's failure messages and its argument spellings.

110 measured: a project whose `project.json` is missing a field exited `status`
with a raw `KeyError: 'project_dir'` traceback; a directory with no manifest did
the same with `FileNotFoundError`; and `run --project NEW missing.fountain`
raised through `shutil.copy2` AFTER creating the project directory, so a mistyped
path left an empty project on the shelf.

111 measured: `run --project P` was the only spelling, while `resume` and
`status` take the project positionally — so the obvious `run P` was read as a
source file and died on a traceback.
"""
import json
import os
import subprocess
import sys

import pytest

from screenplay_studio.manifest import ProjectManifest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "screenplay_studio.cli", *args],
                          capture_output=True, text=True, cwd=REPO)


def _broken_project(tmp_path):
    """A project.json that exists but is missing a required field."""
    proj = tmp_path / "broken"
    proj.mkdir()
    (proj / "project.json").write_text(json.dumps({"title": "X"}), encoding="utf-8")
    return str(proj)


class TestOneActionableLine:
    def test_a_broken_manifest_is_not_a_traceback(self, tmp_path):
        r = _cli("status", _broken_project(tmp_path))
        assert r.returncode == 2, "an unusable project argument is a usage error"
        assert "Traceback" not in r.stderr
        assert "unreadable" in r.stderr and "project.json" in r.stderr

    def test_a_missing_project_is_not_a_traceback(self, tmp_path):
        r = _cli("status", str(tmp_path / "nope"))
        assert r.returncode == 2
        assert "Traceback" not in r.stderr
        assert "not a project" in r.stderr

    def test_a_missing_source_creates_nothing(self, tmp_path):
        proj = tmp_path / "brand-new"
        r = _cli("run", "--project", str(proj), str(tmp_path / "missing.fountain"))
        assert r.returncode == 2
        assert "Traceback" not in r.stderr
        assert "Source screenplay not found" in r.stderr
        assert not proj.exists(), "a rejected source must not leave a project behind"

    def test_create_refuses_before_claiming_the_directory(self, tmp_path):
        proj = tmp_path / "direct"
        with pytest.raises(FileNotFoundError, match="nothing was created"):
            ProjectManifest.create(str(proj), str(tmp_path / "gone.fountain"))
        assert not proj.exists()


class TestBothArgumentSpellings:
    def test_the_project_can_be_positional(self, tmp_path):
        proj = tmp_path / "pos"
        proj.mkdir()
        ProjectManifest.create(str(proj), str(self._src(tmp_path)), title="P").save()
        r = _cli("status", str(proj))
        assert r.returncode == 0 and "P" in r.stdout

    def test_run_accepts_the_project_positionally(self, tmp_path):
        """The reported failure: `run P` read P as a source file."""
        proj = tmp_path / "r"
        proj.mkdir()
        ProjectManifest.create(str(proj), str(self._src(tmp_path)), title="R").save()
        r = _cli("run", str(proj), "--only", "parse", "--skip-chat")
        assert "required: --project" not in r.stderr, (
            "the positional spelling was rejected outright")
        assert "Traceback" not in r.stderr
        assert r.stdout.strip(), "the command never got as far as running"

    def test_usage_is_explained_when_neither_is_given(self):
        r = _cli("run")
        assert r.returncode == 2
        assert "run PROJECT" in r.stderr

    @staticmethod
    def _src(tmp_path):
        p = tmp_path / "s.fountain"
        p.write_text("INT. ROOM - DAY\n\nSomeone waits.\n", encoding="utf-8")
        return p
