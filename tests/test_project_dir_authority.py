"""Fix A: the directory the app RESOLVED is the directory it writes to.

Measured on this machine on 2026-09-27, not theorised. An audit was run against a
throwaway COPY of a project with `--projects-dir` pointing outside the real tree.
It rewrote the ORIGINAL: 36 findings became 25, plus an applied page edit. Nothing
was wrong with the copy; `project.json` inside it still said
`"project_dir": "./studio_projects\\gun_pen_2"`, `ProjectManifest.load()` handed
that stored string back to every caller, and relative to the launcher's CWD the
string resolves to the real data. 21 of the 22 projects on disk store a relative
path, so this was the normal case, not a corner.

The app already has a containment guard for exactly this shape of escape
(`webapp_server.py:1253`, realpath under `PROJECTS_DIR`) — but it only fronts the
DELETE route, so the one operation that cannot undo itself was protected and every
write was not.

Fix A says: `project_dir` in the manifest is a RECORD of where the project was
created, not an INSTRUCTION to the current process. Whoever resolved the directory
(the CLI arg, `_project_dir(name)`) knows better than a file written in the past by
a different launch, so `load()` re-asserts the caller's answer.

These tests fail today with the old behaviour: the first three show the stored
path winning, the fourth shows an API write landing outside `PROJECTS_DIR`.
"""
import io
import json
import os

import pytest

import screenplay_studio.webapp_server as webapp_server
from screenplay_studio.manifest import ProjectManifest

SCRIPT = b"""Title: Authority Test
Author: Test

INT. OFFICE - DAY

RAVI
The ledger says one thing, the vault says another.
"""

# The stored value from the real incident, verbatim in shape: a relative path that
# only means the right place if the process happens to be sitting in the repo root.
STALE = "./studio_projects/{name}"

PATH_PROPS = ["manifest_path", "source_path", "parsed_path", "kg_path",
              "report_md_path", "report_findings_path", "sessions_dir", "progress_path"]


def _write_stale(dir_path: str, name: str) -> None:
    """Point a project's stored `project_dir` at a relative path, as on disk."""
    manifest = os.path.join(dir_path, "project.json")
    with open(manifest, encoding="utf-8") as f:
        data = json.load(f)
    data["project_dir"] = STALE.format(name=name)
    with open(manifest, "w", encoding="utf-8") as f:
        json.dump(data, f)


@pytest.fixture
def launched(tmp_path, mock_server, monkeypatch):
    """A server whose projects live in `tmp_path/served`, and a CWD that is NOT it.

    The separation is the whole finding: with the old code the stored relative path
    resolved against the CWD, so the process's working directory decided which
    project a request touched.
    """
    served = str(tmp_path / "served")
    os.makedirs(served, exist_ok=True)
    webapp_server.PROJECTS_DIR = served
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    client = webapp_server.app.test_client()
    resp = client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SCRIPT), "script.fountain"), "title": "Authority Test"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    name = resp.get_json()["project"]
    _write_stale(os.path.join(served, name), name)
    # A CWD that makes './studio_projects/<name>' a real-looking destination.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(str(elsewhere))
    yield client, served, name, str(elsewhere)


class TestResolvedDirectoryWins:
    def test_load_uses_the_directory_the_caller_resolved(self, tmp_path, monkeypatch):
        resolved = tmp_path / "served" / "proj"
        resolved.mkdir(parents=True)
        ProjectManifest.create(str(resolved), str(_source(tmp_path)), title="Proj")
        _write_stale(str(resolved), "proj")
        monkeypatch.chdir(str(tmp_path))

        m = ProjectManifest.load(str(resolved))

        assert m.project_dir == str(resolved)
        # The stored string is a relative path under a CWD that exists (tmp_path);
        # if it were honoured the manifest would be read from a second directory.
        assert m.manifest_path == os.path.join(str(resolved), "project.json")

    @pytest.mark.parametrize("prop", PATH_PROPS)
    def test_every_standard_path_is_under_the_resolved_dir(self, tmp_path, prop, monkeypatch):
        resolved = tmp_path / "served" / "proj"
        resolved.mkdir(parents=True)
        ProjectManifest.create(str(resolved), str(_source(tmp_path)), title="Proj")
        _write_stale(str(resolved), "proj")
        monkeypatch.chdir(str(tmp_path))

        m = ProjectManifest.load(str(resolved))

        value = getattr(m, prop)
        assert os.path.realpath(value).startswith(os.path.realpath(str(resolved)) + os.sep), \
            f"{prop} escapes the resolved dir: {value}"

    def test_save_does_not_create_the_directory_the_file_names(self, tmp_path, monkeypatch):
        resolved = tmp_path / "served" / "proj"
        resolved.mkdir(parents=True)
        m = ProjectManifest.create(str(resolved), str(_source(tmp_path)), title="Proj")
        _write_stale(str(resolved), "proj")
        monkeypatch.chdir(str(tmp_path))

        m = ProjectManifest.load(str(resolved))
        m.save()

        # `save()` calls os.makedirs(self.project_dir): with the stored string back
        # in charge, this silently creates the directory it was about to write to.
        assert not (tmp_path / "studio_projects").exists()
        assert (resolved / "project.json").exists()


class TestApiWritesStayInsideProjectsDir:
    def test_a_read_finds_what_is_in_the_served_project(self, launched):
        client, served, name, elsewhere = launched
        # A snippet that is really there, in the directory the server resolved.
        with open(os.path.join(served, name, "stash.json"), "w", encoding="utf-8") as f:
            json.dump([{"id": "s1", "text": "already saved", "title": ""}], f)

        resp = client.get(f"/api/projects/{name}/stash")

        assert resp.status_code == 200
        # Today this answers [] : the read follows the stored relative path out of
        # PROJECTS_DIR, so the writer's rail is empty for a project that has one.
        assert [e["id"] for e in resp.get_json()["stash"]] == ["s1"], \
            "the read looked somewhere other than the project it was given"
        assert not os.path.exists(os.path.join(elsewhere, "studio_projects"))

    def test_a_stash_write_lands_in_the_served_project(self, launched):
        client, served, name, elsewhere = launched

        resp = client.post(f"/api/projects/{name}/stash",
                           json={"text": "the vault", "title": "line"})

        assert resp.status_code == 201
        assert os.path.exists(os.path.join(served, name, "stash.json")), \
            "the write never reached the project the server resolved"
        assert not os.path.exists(os.path.join(elsewhere, "studio_projects")), \
            "the write followed project.json out of PROJECTS_DIR"


def _source(tmp_path):
    p = tmp_path / "src.fountain"
    p.write_text("Title: Src\n\nINT. ROOM - DAY\n\nSAM\nHello.\n", encoding="utf-8")
    return p
