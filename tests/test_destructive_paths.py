"""The two destructive calls in a route handler that had no guard.

Pass 12 swept every destructive filesystem call with an AST and split them by
blast radius: the two multi-file `rmtree` sites could leave a PARTIAL result, so
they were fixed; the single-file `os.remove` sites "either happen or raise", so
they were recorded and left alone. That reasoning is sound about *state* and
wrong about *reporting* — a raise is not free. The front-end reads `error` off
the response body, so an unguarded raise answers with Flask's HTML 500 and the
writer is told nothing they can act on.

Both remaining sites are here, and one of them was worse than recorded:

- `reparse_project` dropped stale analyze artifacts in an unguarded loop;
- `upload_draft` removed its temp upload in a `finally` — and **an exception in a
  `finally` replaces any in-flight exception**, so a failed cleanup discarded the
  clear "Could not process new draft" error returned just above and escaped as a
  generic 500. The writer lost the real reason.

(The pass-12 sweep itself had a bug that made it report four *already-guarded*
call sites as unguarded — it tested whether a line fell inside the FIRST statement
of a `try` body rather than inside the body's span. Caught by reading the code it
pointed at. The corrected sweep finds exactly the two sites pinned here.)
"""

import io
import os

import pytest

from screenplay_studio import webapp_server

SAMPLE_SCRIPT = b"""Title: Destructive Paths
Author: Test

INT. ROOM - NIGHT

MARA enters slowly.

MARA
I can't stay.
"""

DRAFT_SCRIPT = b"""Title: Destructive Paths
Author: Test

INT. ROOM - NIGHT

MARA enters slowly.

MARA
I can't stay.
"""


@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


def _upload(http_client):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), "script.fountain"), "title": "Paths"},
        content_type="multipart/form-data",
    )


def _refuse_only(*suffixes):
    """An `os.remove` that refuses exactly the named files and delegates the rest.

    Narrow on purpose: a blanket refusal would also break pytest's own cleanup and
    make the test pass for the wrong reason.
    """
    real_remove = os.remove

    def remove(path, *a, **kw):
        if str(path).endswith(suffixes):
            raise PermissionError(13, "Access is denied")
        return real_remove(path, *a, **kw)

    return remove


class TestReparseReportsAFailedArtifactDrop:
    def test_a_refused_drop_returns_json_naming_the_file(self, http_client, monkeypatch):
        """Failing loudly is right here — the parse succeeded, so silently
        continuing would leave a stale report on screen against a fresh parse."""
        project = _upload(http_client).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")  # so there IS a report

        monkeypatch.setattr(os, "remove", _refuse_only(".md"))
        resp = http_client.post(f"/api/projects/{project}/reparse")
        assert resp.status_code == 500, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body, "the front-end reads JSON off the body, not Flask's HTML page"
        err = body.get("error", "")
        assert "could not drop the stale analysis file" in err, err
        assert "report.md" in err, f"the message should name the file: {err!r}"


class TestDraftCleanupCannotMaskTheRealError:
    def test_a_refused_cleanup_does_not_replace_the_parse_error(self, http_client, monkeypatch):
        """The `finally` case, which is the one that actually loses information.

        `orch.run_parse()` is made to fail so the handler returns a clear JSON
        error — and the cleanup is made to fail too. Before the guard, the
        cleanup's exception REPLACED that response and escaped instead.
        """
        from screenplay_studio import orchestrator as orch_mod

        project = _upload(http_client).get_json()["project"]

        def boom(self, **kw):
            raise orch_mod.OrchestratorError("Could not connect to llama-server.")

        monkeypatch.setattr(orch_mod.Orchestrator, "run_parse", boom)
        monkeypatch.setattr(os, "remove", _refuse_only(".fountain"))

        resp = http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(DRAFT_SCRIPT), "draft.fountain")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 500, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body and "Could not process new draft" in body.get("error", ""), (
            "the cleanup's failure replaced the real error", body)
        assert "Could not connect to llama-server" in body["error"], (
            "the writer must still be told WHY the draft failed", body)

    def test_a_refused_cleanup_is_still_reported(self, http_client, monkeypatch, capsys):
        """Non-fatal, but never silent — the project's "flag, don't drop" rule."""
        project = _upload(http_client).get_json()["project"]

        monkeypatch.setattr(os, "remove", _refuse_only(".fountain"))
        resp = http_client.post(
            f"/api/projects/{project}/drafts",
            data={"file": (io.BytesIO(DRAFT_SCRIPT), "draft.fountain")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        assert "could not remove" in capsys.readouterr().out


class TestUnhandledErrorsAnswerAsJson:
    """The backstop that makes "the writer always gets a reason" a property of the
    app rather than a thing someone has to remember per call.

    Every route's own failure path returns `_error(...)` because the SPA reads
    `error` off the body. An unguarded raise ANYWHERE else produced Flask's HTML
    500 — the front-end found no `error` field and the writer was told nothing.
    """

    def test_an_unhandled_oserror_answers_as_json(self, http_client, monkeypatch):
        from screenplay_studio import beatboard

        project = _upload(http_client).get_json()["project"]

        def boom(m):
            raise OSError(13, "Access is denied")

        monkeypatch.setattr(beatboard, "reset_order", boom)
        resp = http_client.post(f"/api/projects/{project}/beatboard/reset")
        assert resp.status_code == 500, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body, "an HTML page tells the front-end nothing"
        assert "Access is denied" in body.get("error", ""), body

    def test_an_http_exception_keeps_its_status(self, http_client):
        """The handler must not swallow 404/405 into a 500 — those codes are the
        API's contract, and the SPA branches on them."""
        assert http_client.get("/api/definitely-not-a-route").status_code == 404
        assert http_client.delete("/api/health").status_code == 405
