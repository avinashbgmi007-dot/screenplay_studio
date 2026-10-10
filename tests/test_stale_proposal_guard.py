"""The stale-proposal guard — what the apply path does when the text moved.

The contract this file pins (`contracts_UI` §3.4, the Ink Layer's trap frame):

    POST /edits/apply with a frame whose `old` no longer stands byte-for-byte
    in the scene the writer is looking at
        → 400 {"error": "Stale proposal: the text was modified manually.",
               "stale": true}
        → and NOTHING is written.

Why it is exact equality and not containment: a writer who types "!" onto the
end of the proposed line leaves the original as an exact substring, so a
substring test passes and the frame commits over a line the writer had just
changed. That case is tested here in both directions.

The guard lives inside `apply_edit`'s `lock_for(working.json)` section, so the
verification and the mutation are one critical section — a route-level pre-check
would race the very write it is meant to protect (BE-1). `/rewrite` answers from
the same predicate (`proposal_is_landable`), so the desk can never offer a
proposal the apply path would refuse.
"""

import io
import os

import pytest

import screenplay_studio.revision as revision
import screenplay_studio.webapp_server as webapp_server


@pytest.fixture
def http_client(tmp_path, mock_server):
    webapp_server.PROJECTS_DIR = str(tmp_path / "webapp_projects")
    os.makedirs(webapp_server.PROJECTS_DIR, exist_ok=True)
    webapp_server.CONFIG["server_url"] = mock_server
    webapp_server.CONFIG["model"] = None
    webapp_server.app.config["TESTING"] = True
    return webapp_server.app.test_client()


SAMPLE_SCRIPT = b"""Title: Stale Guard Test Script
Author: Test

INT. STUDY - NIGHT

MARA takes out an old REVOLVER, setting it on the desk.

MARA
I'll tell you everything when this is over.

CUT TO:

INT. STUDY - NIGHT

The REVOLVER is still there, untouched.

MARA
Some things are better left alone.
"""

LINE = "I'll tell you everything when this is over."


def _upload(http_client, filename="script.fountain"):
    return http_client.post(
        "/api/projects",
        data={"file": (io.BytesIO(SAMPLE_SCRIPT), filename), "title": "Stale Guard"},
        content_type="multipart/form-data",
    )


def _apply(http_client, project, frames, scene_number=1):
    return http_client.post(
        f"/api/projects/{project}/edits/apply",
        json={"scene_number": scene_number, "replacements": frames},
    )


# ── the unit predicate ───────────────────────────────────────────────────────

class TestThePredicate:
    def test_the_error_is_a_valueerror(self):
        """A future route that forgets the stale contract must answer 400, not 500.

        `StaleProposalError` subclasses ValueError on purpose: every layer that
        already maps ValueError to a 400 keeps working anywhere the stale
        contract is not named.
        """
        assert issubclass(revision.StaleProposalError, ValueError)
        assert str(revision.StaleProposalError()) == revision.STALE_PROPOSAL_MESSAGE
        assert revision.STALE_PROPOSAL_MESSAGE == "Stale proposal: the text was modified manually."

    def test_exact_equality_never_containment(self):
        lines = ["he set the revolver down.".encode()]
        assert revision._still_holds(lines, b"he set the revolver down.")
        # The writer typed into the line: the old text is still an exact
        # SUBSTRING, and that is precisely why containment is the wrong test.
        assert not revision._still_holds(["he set the revolver down.!".encode()],
                                         b"he set the revolver down.")
        assert not revision._still_holds(lines, b"he set the revolver down.!")

    def test_a_whitespace_difference_is_the_edit(self):
        # No strip, no case-fold, no Unicode normalisation: a whitespace change
        # IS the manual edit this guard exists to catch.
        assert not revision._still_holds([" he set it down.".encode()], b"he set it down.")
        assert not revision._still_holds(["he set it down.".encode()], b"he  set it down.")

    def test_a_frame_spanning_a_line_break_holds_as_a_run(self):
        lines = [b"MAR A", b"you came.", b"and you stayed."]
        assert revision._still_holds(lines, b"MAR A\nyou came.")
        assert revision._still_holds(lines, b"you came.\nand you stayed.")
        assert not revision._still_holds(lines, b"you came.\nand you left.")


# ── the route contract ───────────────────────────────────────────────────────

class TestTheRoute:
    def test_a_fresh_frame_lands(self, http_client):
        project = _upload(http_client).get_json()["project"]
        resp = _apply(http_client, project, [{"old": LINE, "new": "I'll tell you when it's over."}])
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["applied"]) == 1
        assert "I'll tell you when it's over." in data["scene_text_after"]

    def test_refuses_when_the_line_moved_and_writes_nothing(self, http_client):
        """The measured live scenario: the same proposal applied twice.

        First call lands; the second is a frame cut from text that no longer
        exists — exactly what a writer typing while the model thinks produces.
        Before the guard the desk answered 200 with a `skipped` reason; the
        refusal is now a state the page renders.
        """
        project = _upload(http_client).get_json()["project"]
        first = _apply(http_client, project, [{"old": LINE, "new": "I'll tell you when it's over."}])
        assert first.status_code == 200 and len(first.get_json()["applied"]) == 1

        before = http_client.get(f"/api/projects/{project}/script").get_json()
        second = _apply(http_client, project, [{"old": LINE, "new": "I'll tell you when it's over."}])
        assert second.status_code == 400
        body = second.get_json()
        assert body == {"error": revision.STALE_PROPOSAL_MESSAGE, "stale": True}

        # Nothing moved — not the text, not the edit log.
        after = http_client.get(f"/api/projects/{project}/script").get_json()
        assert after == before, "a refused apply touches nothing"
        edits = http_client.get(f"/api/projects/{project}/edits").get_json()
        assert len(edits["edits"]) == 1, "the refusal is not an edit"

    def test_refuses_a_line_a_suffix_was_typed_onto(self, http_client):
        """Containment would have committed over the writer's edit.

        The writer types "!" onto the proposed line; a frame cut before that
        still matches as a substring. Exact equality is the only comparison that
        can tell "the text still stands" from "the text was edited".
        """
        project = _upload(http_client).get_json()["project"]
        typed = _apply(http_client, project, [{"old": LINE, "new": LINE + "!"}])
        assert typed.status_code == 200

        resp = _apply(http_client, project, [{"old": LINE, "new": "a replacement written for the old line"}])
        assert resp.status_code == 400
        assert resp.get_json()["stale"] is True

    def test_a_frame_whose_old_carries_the_suffix_is_refused_too(self, http_client):
        project = _upload(http_client).get_json()["project"]
        resp = _apply(http_client, project, [{"old": LINE + "!", "new": "x"}])
        assert resp.status_code == 400
        assert resp.get_json()["stale"] is True

    def test_the_frame_shape_messages_are_unchanged(self, http_client):
        """The L5 per-row messages stay: they name the offending row, which the
        older blunt copy did not. Only the STALE answer is new."""
        project = _upload(http_client).get_json()["project"]
        resp = _apply(http_client, project, ["not-a-frame"])
        assert resp.status_code == 400
        assert "replacements[0]" in resp.get_json()["error"]
        assert "stale" not in resp.get_json()

        resp = _apply(http_client, project, [{"old": 7, "new": "x"}])
        assert resp.status_code == 400
        assert "string 'old'" in resp.get_json()["error"]

    def test_a_multiline_frame_is_still_skipped_not_refused(self, http_client):
        """A frame that HOLDS as a run passes the guard, and the replacement
        engine's own long-standing rule then skips it. Unchanged behaviour: the
        guard only ever refuses frames that do not hold."""
        project = _upload(http_client).get_json()["project"]
        script = http_client.get(f"/api/projects/{project}/script").get_json()
        texts = [el["text"] for el in script["scenes"][0]["elements"]]
        i = texts.index(LINE)
        multiline = texts[i - 1] + "\n" + texts[i]          # two consecutive elements
        resp = _apply(http_client, project, [{"old": multiline, "new": "x"}])
        assert resp.status_code == 200
        assert resp.get_json()["applied"] == []
        assert resp.get_json()["skipped"][0]["reason"] == "old spans multiple lines"


# ── the producer's half of the same predicate ────────────────────────────────

class TestTheProducer:
    def test_rewrite_only_offers_frames_that_still_stand(self, http_client):
        """Both halves answer from `_still_holds`, so the desk can never offer a
        proposal the apply path will refuse — and the refusal can never say
        "modified manually" about what was really a model artifact."""
        project = _upload(http_client).get_json()["project"]
        http_client.post(f"/api/projects/{project}/analyze")
        resp = http_client.post(f"/api/projects/{project}/rewrite", json={"scene_number": 1})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["replacements"], "the mock proposes at least one candidate"
        for rep in data["replacements"]:
            assert rep["old"] in data["scene_text"], (
                "every offered frame stands verbatim in the scene the client was shown")

    def test_proposal_is_landable_reads_the_live_scene(self, http_client):
        project = _upload(http_client).get_json()["project"]
        manifest = webapp_server._load_manifest(project)
        working = revision.load_working(manifest)
        assert revision.proposal_is_landable(working, 1, LINE)
        assert not revision.proposal_is_landable(working, 1, LINE + "!")
        assert not revision.proposal_is_landable(working, 1, "a line that is not in this scene")
