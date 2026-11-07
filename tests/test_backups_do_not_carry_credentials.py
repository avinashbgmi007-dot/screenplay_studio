"""A backup must not carry the writer's API key out of the machine.

Gap 8's second half, filed: "Project and library backup tests retained a
synthetic API-key marker". Reproduced before fixing: a project whose manifest
held `sk-live-...` produced a project archive AND a library archive, each
containing `one/project.json` with the key in it — verbatim, in both.

Why this matters more than it looks. A backup is the one artifact a writer
deliberately hands to someone else: emailed to a collaborator, dropped in a
drive folder, put on a USB stick. Every other surface in this app already
refuses to carry the token — `tests/test_privacy_statement.py` sweeps
`/api/config` and `/api/health` and asserts it — but the archives were simply
never in that sweep. The principle was already stated in the codebase; the
backup was outside the net.

The key is at rest in `project.json` ON PURPOSE (gap 58: `_adopt_connection`
copies it into every project so `resume` and the CLI work without the writer
retyping it). So this is not a "the key should not be there" fix. It is: the
key belongs at rest on the writer's own disk, and must not travel in an archive
whose whole purpose is to leave that disk.

Three promises are asserted here, and the third is the one that is easy to
break:

1. the token does not appear anywhere in either archive;
2. the writer is TOLD the credential was withheld, named in the embedded
   manifest and in a response header, because a backup that silently omits
   something is the gap-72 defect wearing a security hat;
3. everything ELSE in the manifest survives — source, stages, model settings,
   drafts, title. A redaction that quietly drops the project's configuration
   would trade a confidentiality bug for a restore bug, and on a backup
   availability is the whole point.

Not claimed: an archive made before this change still contains the token.
Redaction cannot reach a file already on someone's disk, and the register says
so rather than implying otherwise.
"""

from __future__ import annotations

import io
import json
import os
import zipfile

import pytest

import screenplay_studio.webapp_server as webapp_server

SECRET = "sk-live-BACKUP-MUST-NOT-CARRY-THIS-7d21"

SCRIPT = b"""Title: Backup Desk
Author: T

INT. ROOM - DAY

Action.

ANA
A line.
"""


@pytest.fixture()
def desk(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.CONFIG["api_key"] = None
    webapp_server.app.config["TESTING"] = True
    client = webapp_server.app.test_client()

    response = client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SCRIPT), "desk.fountain"), "title": "Backup Desk"},
        content_type="multipart/form-data")
    assert response.status_code == 201, response.data[:400]

    # Put the token where the app really puts it: the per-project manifest,
    # written by _adopt_connection so resume/CLI can reach the endpoint.
    from screenplay_studio.manifest import ProjectManifest
    name = response.get_json()["project"]
    m = ProjectManifest.load(os.path.join(webapp_server.PROJECTS_DIR, name))
    m.api_key = SECRET
    m.save()
    return client, name


def _archive(response) -> zipfile.ZipFile:
    assert response.status_code == 200, response.data[:400]
    return zipfile.ZipFile(io.BytesIO(response.data))


def _files_containing(zf: zipfile.ZipFile, needle: str) -> list[str]:
    hits = []
    for name in zf.namelist():
        if name.endswith("/"):
            continue
        if needle in zf.read(name).decode("utf-8", "ignore"):
            hits.append(name)
    return hits


def test_the_project_backup_does_not_carry_the_token(desk):
    client, name = desk
    zf = _archive(client.get(f"/api/projects/{name}/backup"))

    assert "project.json" in " ".join(zf.namelist()), (
        "the archive no longer carries the manifest at all — that is a restore "
        "regression, not a redaction")
    assert _files_containing(zf, SECRET) == [], (
        "the writer's API key travelled inside their project backup")


def test_the_library_backup_does_not_carry_the_token(desk):
    client, _name = desk
    zf = _archive(client.get("/api/library/backup"))

    assert _files_containing(zf, SECRET) == [], (
        "the writer's API key travelled inside their library backup")


def test_the_writer_is_told_the_credential_was_withheld(desk):
    """A silent omission is the gap-72 defect wearing a security hat."""
    client, name = desk
    response = client.get(f"/api/projects/{name}/backup")

    assert response.headers.get("X-Backup-Credentials") == "withheld", \
        response.headers.get("X-Backup-Credentials")

    zf = _archive(response)
    manifest = json.loads(zf.read("backup-manifest.json"))
    withheld = manifest.get("credentials_withheld")
    assert withheld, f"the archive does not say what it withheld: {manifest}"
    assert "project.json" in json.dumps(withheld)


def test_the_library_backup_says_so_too(desk):
    client, _name = desk
    response = client.get("/api/library/backup")

    assert response.headers.get("X-Backup-Credentials") == "withheld"
    zf = _archive(response)
    manifest = json.loads(zf.read("library-backup.json"))
    assert manifest.get("credentials_withheld"), manifest


def test_the_rest_of_the_manifest_survives_redaction(desk):
    """Redaction must not become a restore bug.

    Everything a restored project needs — title, stages, drafts, the model it
    talked to — has to still be there. Only the token goes.
    """
    client, name = desk
    zf = _archive(client.get(f"/api/projects/{name}/backup"))

    entry = next(n for n in zf.namelist() if n.endswith("project.json"))
    restored = json.loads(zf.read(entry))

    assert restored["title"] == "Backup Desk"
    assert restored.get("server_url") == webapp_server.CONFIG["server_url"]
    # `active_draft` is legitimately None on a freshly uploaded project, so the
    # claim is that the KEY survives the redaction, not that it holds a value.
    assert "active_draft" in restored, "the draft pointer was dropped"
    assert restored.get("stages"), "the stage record vanished with the token"
    assert restored.get("drafts") == [], "the draft list was dropped"
    assert restored.get("source_filename"), "the source record was dropped"
    assert restored.get("api_key") in (None, ""), (
        f"api_key should be cleared, not merely renamed: {restored.get('api_key')!r}")


def test_a_project_with_no_token_is_not_flagged(desk):
    """No credential, nothing withheld — the header must not cry wolf."""
    client, name = desk
    from screenplay_studio.manifest import ProjectManifest
    m = ProjectManifest.load(os.path.join(webapp_server.PROJECTS_DIR, name))
    m.api_key = None
    m.save()

    response = client.get(f"/api/projects/{name}/backup")
    assert response.headers.get("X-Backup-Credentials") in (None, "none"), \
        response.headers.get("X-Backup-Credentials")
    zf = _archive(response)
    manifest = json.loads(zf.read("backup-manifest.json"))
    assert not manifest.get("credentials_withheld")
